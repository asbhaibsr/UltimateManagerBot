# 🎬 Movie Bot Pro

A feature-rich Telegram movie bot with premium subscription system.

## ✨ Features
- 🔤 Smart spelling correction
- 📺 Season number detection
- 🎬 Movie request system
- 🗑️ Auto file cleaner
- 💎 Premium subscription (Ad-free)
- ⚙️ Feature toggle system
- 👥 Force subscribe/join
- 📊 Statistics & analytics

## 🚀 Deployment on Koyeb (FREE)

### Step 1: Create MongoDB Database
1. Go to [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create FREE cluster (512MB)
3. Create database user
4. Get connection string
5. Add IP 0.0.0.0/0

### Step 2: Create Telegram Bot
1. Message @BotFather
2. Send `/newbot`
3. Set name: Movie Master Pro
4. Set username: MovieMasterProBot
5. Get BOT_TOKEN
6. Disable privacy: `/setprivacy` → Disable

### Step 3: Get API Credentials
1. Go to [my.telegram.org](https://my.telegram.org)
2. Login with your phone number
3. Go to API Development Tools
4. Create app → Get API_ID and API_HASH

### Step 4: Deploy on Koyeb
1. Sign up at [Koyeb.com](https://www.koyeb.com) (FREE)
2. Click "Create App"
3. Choose "GitHub" as source
4. Select your repository
5. Add environment variables:
   - `BOT_TOKEN`
   - `API_ID`
   - `API_HASH`
   - `MONGO_DB_URL`
   - `OWNER_ID`
   - `PORT` (set to 8080)
6. Click "Deploy"

### Step 5: Configure Bot
1. Add bot to your group
2. Make bot Admin
3. Type `/settings`
4. Configure features with buttons
5. Test with `/request Movie Name`

## 📋 Commands

### User Commands:
- `/start` - Start bot
- `/help` - Show help
- `/request Movie Name` - Request movie
- `/myrequests` - View your requests

### Admin Commands:
- `/settings` - Configure bot
- `/function` - Show all functions
- `/stats` - View statistics
- `/broadcast` - Send message to groups
- `/addpremium <group_id>` - Add premium

### Premium Features:
- Ad-free experience
- Priority support
- Faster responses
- All features unlocked

## 🔧 Environment Variables
Create `.env` file:
```env
BOT_TOKEN=your_token
API_ID=1234567
API_HASH=your_hash
MONGO_DB_URL=your_mongo_url
OWNER_ID=1234567890
PORT=8080
