# Deploy Trading Dashboard

Two deployment options:

---

## Option 1: Streamlit Community Cloud (easiest, free)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. **Deploy**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click **New app**
   - Select repo, branch (`main`), and file: `app.py`
   - Under **Advanced settings** → **Secrets**, add:
     ```
     MONGO_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"
     ```
   - Click **Deploy**

3. Your app will be live at `https://YOUR_APP.streamlit.app`

---

## Option 2: Render

1. **Push to GitHub** (same as above)

2. **Deploy via Blueprint**
   - Open: `https://dashboard.render.com/blueprint/new?repo=https://github.com/YOUR_USERNAME/YOUR_REPO`
   - Connect your GitHub if prompted
   - Click **Apply**
   - In the service **Environment** tab, add:
     - `MONGO_URI` = your MongoDB Atlas connection string
   - Save — Render will redeploy automatically

3. Your app will be live at `https://trading-dashboard-XXXX.onrender.com`

---

## MongoDB Atlas

- Use MongoDB Atlas (cloud) — local MongoDB won’t work in the cloud
- Add your deployment IP to Atlas **Network Access** (or use `0.0.0.0/0` for testing)
- Ensure your Atlas user has read/write access to the database

---

## Troubleshooting: SSL handshake failed

If you see `ServerSelectionTimeoutError: SSL handshake failed` or `TLSV1_ALERT_INTERNAL_ERROR`:

1. **Atlas Network Access** — Whitelist `0.0.0.0/0` for testing.
2. **Python version** — Python 3.13 can have SSL issues with Atlas; try 3.11 or 3.12.
3. **Network** — Disable VPN or try a different network.
4. **Connection string** — Ensure `MONGO_URI` in `.streamlit/secrets.toml` is correct.
