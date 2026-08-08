import asyncio
import os
import re
import time
from typing import Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from py_yt import VideosSearch

from config import BASE_URL, API_KEY, STORAGE_DIR

os.makedirs(STORAGE_DIR, exist_ok=True)


def _session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3)
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def _clean(link: str) -> str:
    if "&" in link:
        link = link.split("&")[0]
    if "?si=" in link:
        link = link.split("?si=")[0]
    elif "&si=" in link:
        link = link.split("&si=")[0]
    return link


def _wait_until_ready(stream_url: str, max_attempts: int) -> bool:
    session = requests.Session()
    try:
        for attempt in range(max_attempts):
            try:
                r = session.get(stream_url, timeout=10, stream=True, allow_redirects=True)
                r.close()
                if r.status_code in (200, 206):
                    return True
                elif r.status_code in (204, 423, 404, 410):
                    time.sleep(2)
                    continue
                elif r.status_code in (401, 403, 429):
                    return False
                else:
                    return False
            except requests.exceptions.RequestException:
                time.sleep(2)
        return False
    finally:
        session.close()


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def track(self, query: str, videoid: Union[bool, str] = None):
        link = self.base + query if videoid else _clean(query)
        results = VideosSearch(link, limit=1)
        title = duration_min = duration_sec = vidid = yturl = thumbnail = None
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            duration_sec = 0
            if duration_min:
                try:
                    parts = duration_min.split(":")
                    if len(parts) == 3:
                        duration_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_sec = int(parts[0]) * 60 + int(parts[1])
                except ValueError:
                    duration_sec = 0
        if vidid is None:
            return None, None
        details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "duration_sec": duration_sec,
            "thumb": thumbnail,
        }
        return details, vidid

    async def download(self, vidid: str, video: bool = False):
        ext = "mp4" if video else "mp3"
        local_path = os.path.join(STORAGE_DIR, f"{vidid}.{ext}")

        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            return local_path

        for attempt in range(1, 3):
            stream_url, kind_type = await self._baby_fetch(vidid, want_video=video)
            if not stream_url:
                return None

            if kind_type == "live":
                return stream_url

            saved_path = await self._save_to_storage(stream_url, local_path)
            if saved_path:
                return saved_path

        return None

    async def get_playable(self, vidid: str, video: bool = False):
        """
        Returns something playable as fast as possible:
        - local cached file if it already exists (instant)
        - otherwise the direct stream URL (playback starts as soon as it's
          ready, without waiting for the full file to download), while a
          background task saves it to STORAGE_DIR for next time.
        """
        ext = "mp4" if video else "mp3"
        local_path = os.path.join(STORAGE_DIR, f"{vidid}.{ext}")

        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            return local_path

        stream_url, kind_type = await self._baby_fetch(vidid, want_video=video)
        if not stream_url:
            return None

        if kind_type != "live":
            asyncio.create_task(self._cache_in_background(vidid, video))

        return stream_url

    async def _cache_in_background(self, vidid: str, video: bool):
        try:
            await self.download(vidid, video=video)
        except Exception as e:
            print(f"[bg-cache] EXCEPTION for {vidid}: {type(e).__name__}: {e}")

    async def _baby_fetch(self, vidid: str, want_video: bool = False):
        """Returns (stream_url, type) or (None, None)."""
        loop = asyncio.get_running_loop()
        max_attempts = 90 if want_video else 60

        def _call():
            try:
                kind = "video" if want_video else "song"
                url = f"{BASE_URL}/api/{kind}?query={vidid}&download=true&api={API_KEY}"

                session = _session()
                resp = session.get(url, timeout=60)
                print(f"[BabyAPI] GET {kind} {vidid} -> status={resp.status_code}")
                data = resp.json()
                print(f"[BabyAPI] response: {data}")
                session.close()

                stream = data.get("stream")
                if not stream:
                    print(f"[BabyAPI] no 'stream' field in response")
                    return None, None

                kind_type = data.get("type")

                if kind_type == "live":
                    return stream, kind_type

                ready = _wait_until_ready(stream, max_attempts)
                if not ready:
                    print(f"[BabyAPI] stream never became ready for {vidid}")
                    return None, None

                return stream, kind_type

            except Exception as e:
                print(f"[BabyAPI] EXCEPTION for {vidid}: {type(e).__name__}: {e}")
                return None, None

        return await loop.run_in_executor(None, _call)

    async def _save_to_storage(self, url: str, local_path: str):
        tmp_path = local_path + ".part"
        try:
            print(f"[save] Starting download to {local_path}")
            proc = await asyncio.create_subprocess_shell(
                f'curl -L "{url}" -o "{tmp_path}" -s --max-time 120'
            )
            await proc.communicate()

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 50_000:
                print(f"[save] Download too small or missing for {local_path}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return None

            os.rename(tmp_path, local_path)
            print(f"[save] Done: {local_path}")
            return local_path

        except Exception as e:
            print(f"[save] EXCEPTION saving {local_path}: {type(e).__name__}: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return None


YouTube = YouTubeAPI()
