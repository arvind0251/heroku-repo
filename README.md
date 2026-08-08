# Simple Music Bot (xBit API + Permanent NVMe Storage)

## Features
- `/play` `/vplay` — gaana/video bajao
- `/pause` `/resume` `/skip` `/stop` `/end`
- `/queue` `/shuffle`
- `/authuser` — reply karke kisi ko permission do/hatao
- `/broadcast` — sirf owner, sab users/chats ko message
- Log group — bot start + har song play ka message
- xBit API only (yt-dlp nahi), permanent NVMe caching

## VPS Setup

### 1. System packages
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg git
```

### 2. Project setup
```bash
cd ~
mkdir musicbot && cd musicbot
# yahan saari files (config.py, database.py, queue.py, youtube.py, main.py, requirements.txt) daalo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables set karo
`.env` file banao ya seedha export karo:
```bash
export API_ID="12345"
export API_HASH="your_api_hash"
export BOT_TOKEN="your_bot_token"
export SESSION_STRING="your_assistant_session_string"
export OWNER_ID="your_telegram_user_id"
export MONGO_URL="your_mongodb_connection_string"
export LOG_GROUP_ID="-100xxxxxxxxxx"
export XBIT_API_KEY="your_xbit_api_key"
export XBIT_API_URL="https://tgapi.xbitcode.com"
export STORAGE_DIR="/root/vps_songs"
export DURATION_LIMIT="1200"
export QUEUE_LIMIT="20"
```

### 4. NVMe storage folder banao
```bash
mkdir -p /root/vps_songs
```

### 5. Run karo (tmux se, taaki band na ho)
```bash
tmux new -s musicbot
source venv/bin/activate
python3 main.py
```
Detach karne ke liye: `Ctrl+B` phir `D`

### 6. Auto-restart (PM2 se, recommended)
```bash
npm install -g pm2
pm2 start "venv/bin/python3 main.py" --name musicbot
pm2 save
pm2 startup
```

## Zaroori cheezein
- **API_ID / API_HASH** — https://my.telegram.org se
- **BOT_TOKEN** — @BotFather se naya bot bana ke
- **SESSION_STRING** — assistant/userbot account ka pyrogram session string
- **LOG_GROUP_ID** — ek group banao, bot + assistant dono ko admin banake add karo, uski chat ID
- **MONGO_URL** — MongoDB Atlas free cluster connection string
- **XBIT_API_KEY / XBIT_API_URL** — tumhare paas already hai

## Heroku Deploy

Zaroori baat: Heroku ka filesystem ephemeral hai - dyno restart/redeploy pe STORAGE_DIR khali ho jaata hai, so "permanent NVMe caching" wala feature permanent nahi rahega (bas re-download hoga, bot chalega fine). Free Heroku dynos ab nahi hain - Eco ($5/mo) ya usse upar ka plan chahiye, aur ye ek worker dyno hai (web nahi), kyunki koi HTTP port serve nahi ho raha.

### 1. Heroku CLI se deploy
```bash
heroku login
heroku create your-app-name
heroku buildpacks:add --index 1 heroku-community/apt
heroku buildpacks:add --index 2 heroku/python

heroku config:set \
  API_ID="12345" \
  API_HASH="your_api_hash" \
  BOT_TOKEN="your_bot_token" \
  SESSION_STRING="your_assistant_session_string" \
  OWNER_ID="your_telegram_user_id" \
  MONGO_URL="your_mongodb_connection_string" \
  LOG_GROUP_ID="-100xxxxxxxxxx" \
  API_KEY="your_babyapi_key" \
  BASE_URL="https://api.babiesiq.tech" \
  STORAGE_DIR="/app/vps_songs" \
  DURATION_LIMIT="18000" \
  QUEUE_LIMIT="30"

git push heroku main
heroku ps:scale worker=1 web=0
heroku logs --tail
```

### 2. Ya GitHub se direct deploy
Heroku Dashboard -> New -> Create new app -> Deploy tab -> GitHub connect -> repo select -> Manual/Automatic deploy. Uske baad Settings -> Config Vars mein upar wale saare env vars daal do. Buildpacks Settings tab se heroku-community/apt (pehle) aur heroku/python (baad mein) add karo.

Files jo isliye add ki gayi hain:
- Procfile - worker: python3 main.py (Heroku ko batata hai bot kaise chalana hai)
- Aptfile - ffmpeg (voice call streaming ke liye zaroori, apt buildpack isse install karta hai)
- app.json - one-click deploy button ke liye metadata + config var descriptions

config.py ab hardcoded secrets ki jagah environment variables se values leta hai - Heroku ho ya VPS, dono jagah same tareeke se kaam karega.

## Note
- Sirf xBit API se hi gaane fetch honge (yt-dlp bilkul use nahi hota)
- Pehli baar gaana bajne par thoda time lagega (API + download), uske baad wahi gaana `STORAGE_DIR` se instant milega
- `DURATION_LIMIT` se lambi videos automatically reject ho jayengi (storage bachane ke liye)
