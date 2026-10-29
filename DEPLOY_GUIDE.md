# Titan Alpha - Android & Cloud Deployment Guide (Render.com)

This application is a 100% AsyncIO algorithmic trading bot equipped with a mobile-optimized control dashboard designed for Android phones and 24/7 cloud hosting on Render.com.

---

## 1. Quick Local Test (Access from your Android Phone via Wi-Fi)

You can test the mobile dashboard right now on your local network:

1. Open PowerShell in `c:\my strategy` and run:
   ```powershell
   python app.py
   ```
2. Find your PC's local IP address by opening another PowerShell window and typing:
   ```powershell
   ipconfig
   ```
   *(Look for `IPv4 Address`, e.g., `192.168.1.50`)*
3. On your **Android Phone** (connected to the same Wi-Fi), open Chrome and navigate to:
   ```text
   http://192.168.1.50:8000
   ```
4. You will see the dark-mode mobile dashboard. Tap **START BOT** to run in Demo mode or enter real credentials for Live trading.

---

## 2. Deploy to Render.com (24/7 Free Cloud Execution)

Deploying to Render allows the bot to run 24 hours a day in the cloud without needing your computer on.

### Step 1: Create a GitHub Repository
1. Initialize git in `c:\my strategy` (or your repo folder):
   ```powershell
   git init
   git add .
   git commit -m "Initial commit of Titan Alpha Android Bot"
   ```
2. Create a new repository on [GitHub](https://github.com) (e.g. `titan-alpha-bot`).
3. Push your files to GitHub:
   ```powershell
   git remote add origin https://github.com/<your-username>/titan-alpha-bot.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Render.com
1. Go to [Render.com](https://render.com) and sign in.
2. Click **New +** $\rightarrow$ **Web Service**.
3. Select **Build and deploy from a Git repository** and connect your GitHub repo.
4. Fill in the settings (Render will automatically detect `render.yaml` or you can enter manually):
   * **Name:** `titan-alpha-trader`
   * **Language:** `Python 3`
   * **Branch:** `main`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
   * **Plan:** `Free`
5. Click **Create Web Service**.
6. Within 2 minutes, Render will provide a free HTTPS URL:
   ```text
   https://titan-alpha-trader.onrender.com
   ```

---

## 3. Add to Android Home Screen (PWA Experience)

Once your Render URL is live:
1. Open the URL (`https://titan-alpha-trader.onrender.com`) in **Chrome** on your Android phone.
2. Tap the three dots **(⋮)** in the top right corner of Chrome.
3. Select **Add to Home screen** (or **Install App**).
4. Tap **Add**.

Now you have a dedicated **Titan Alpha Bot App icon** on your Android home screen that launches full-screen, streams live ticks, and lets you start, stop, and monitor live trading with one tap.
