# Running RegLoop AI in GitHub Codespaces

> **Why Codespaces?** It runs entirely in the cloud — no local install, works on any PC (even 32-bit or low-RAM machines), and your browser is the only thing you need.

---

## Quick-start checklist

- [ ] Step 1 — Push code to GitHub
- [ ] Step 2 — Add `GEMINI_API_KEY` secret ← **do this BEFORE creating the Codespace**
- [ ] Step 3 — Create the Codespace (takes ~3 min first time)
- [ ] Step 4 — Make port 8000 **Public**
- [ ] Step 5 — Run `bash .devcontainer/start.sh`
- [ ] Step 6 — Open port 3000 in browser

---

## Step 1 — Push to GitHub

Open a terminal on your machine (or use the GitHub web UI to create a new repo and upload the zip).

**Option A — command line:**
```bash
cd regloop-fixed          # the folder you unzipped
git init
git add .
git commit -m "RegLoop AI"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/regloop-ai.git
git push -u origin main
```

**Option B — GitHub web UI (easiest if git isn't installed):**
1. Go to https://github.com/new → create a repo named `regloop-ai`
2. Click **"uploading an existing file"**
3. Drag-and-drop the entire unzipped `regloop-fixed` folder
4. Commit

---

## Step 2 — Add Gemini API Key as a Codespaces Secret

> Do this **before** creating the Codespace so the key is injected automatically.

1. Get a **free** Gemini key (no credit card): https://aistudio.google.com/app/apikey
2. Go to **https://github.com/settings/codespaces**
3. Click **"New secret"**
4. Name: `GEMINI_API_KEY`
5. Value: paste your key
6. Under **Repository access** → select your `regloop-ai` repo
7. Click **Add secret**

✅ The key is now stored securely. You'll never paste it into a file.

---

## Step 3 — Create the Codespace

1. Go to your `regloop-ai` repo on GitHub
2. Click the green **`<> Code`** button
3. Click the **Codespaces** tab
4. Click **"Create codespace on main"**

GitHub automatically:
- Spins up a cloud container (Python 3.12 + Node 20)
- Runs `setup.sh` — installs all Python and Node dependencies
- Writes your `GEMINI_API_KEY` to `backend/.env`

**First-time setup takes 2–4 minutes.** You'll see a VS Code editor open in your browser when it's ready.

---

## Step 4 — Make Port 8000 Public ⚠️ Required

This is the step most people miss. Your browser (outside the container) needs to reach the backend API.

1. Look at the bottom of VS Code — click the **"PORTS"** tab
2. Find the row with port **8000** (Backend API)
3. Right-click it → **"Port Visibility"** → **"Public"**

> If you skip this, you'll see "Network Error" or CORS errors when the frontend tries to call the API.

Port 3000 (Frontend) can stay as **Private** — it's only accessed via the Codespaces browser forwarding.

---

## Step 5 — Start the App

In VS Code, open a terminal: **Terminal → New Terminal** (or press `` Ctrl+` ``)

```bash
bash .devcontainer/start.sh
```

You'll see:

```
╔══════════════════════════════════════════╗
║        RegLoop AI — Starting Up          ║
╚══════════════════════════════════════════╝

  ✓ Codespaces detected
  ✓ Backend URL: https://YOUR-CODESPACE-8000.app.github.dev
  ✓ frontend/.env.local configured

▸ Starting FastAPI backend on :8000...
  Waiting for backend...
  ✓ Backend is up  (Swagger: https://YOUR-CODESPACE-8000.../api/docs)

▸ Starting Next.js frontend on :3000...
  ✓ Frontend starting...

╔══════════════════════════════════════════════════════════════╗
║  RegLoop AI is running!                                      ║
║  → Open the app:  PORTS tab → port 3000 → 🌐 Open Browser   ║
╚══════════════════════════════════════════════════════════════╝
```

Leave this terminal running. Press **Ctrl+C** to stop both servers.

---

## Step 6 — Open the App

1. Click the **PORTS** tab
2. Find port **3000** (Frontend App)
3. Click the 🌐 **globe icon** (or hover → "Open in Browser")
4. RegLoop AI opens in a new browser tab

---

## Step 7 — Run the Demo

Sample files are in the `sample_data/` folder inside the Codespace.

| File | Upload as |
|------|-----------|
| `DORA_ICT_Risk_Update_2026.pdf` | Regulatory Document |
| `ICT_Risk_Policy.pdf` | Internal Policy |
| `Vendor_Risk_Policy.pdf` | Internal Policy |
| `Incident_Response_Policy.pdf` | Internal Policy |
| `responsibility_matrix.csv` | Responsibility Matrix |

**To access sample files in your browser:**
- In the PORTS tab, open port 3000
- In the Codespace file explorer (left sidebar), find `sample_data/`
- Right-click any file → **"Download"** → it downloads to your local PC
- Then upload from your local PC into the RegLoop web UI

**Full walkthrough:**
1. Click **New Workspace** on the home page
2. Upload all 5 files
3. Click **Upload & Create Session**
4. Click **Run Full Analysis Pipeline**
5. Watch the progress bar (takes ~60–90s total)
6. Explore each tab: Obligations → Policy Mapping → Gap Analysis → Review PRs → Audit Trail → Export

---


---

## Running without a Gemini API key (demo / review mode)

The app includes a complete set of realistic DORA fallback data — 14 obligations, 14 policy mappings, 8 gap analyses (Not Covered) + 6 (Partially Covered), and 14 policy PRs with specific before/after text. This triggers automatically when the Gemini API is unavailable.

To run in fallback mode (no API key needed):

```bash
# In the backend terminal, set an invalid key so fallback triggers instantly
echo "GEMINI_API_KEY=demo_mode_no_key" > /workspaces/regloop-ai/backend/.env
echo "DATABASE_URL=sqlite+aiosqlite:///./regloop.db" >> /workspaces/regloop-ai/backend/.env
```

Then start the servers normally with `bash .devcontainer/start.sh` and run the full pipeline. All 14 obligations will be populated with realistic DORA compliance data within seconds, no quota limits, no waiting.


## Troubleshooting

### "Network Error" / CORS errors in browser
Port 8000 is not Public.
→ PORTS tab → port 8000 → right-click → **Port Visibility → Public**

### "GEMINI_API_KEY is not set"
The secret wasn't set before creating the Codespace, or the Codespace was created before adding the secret.
```bash
# Quick fix — paste your key directly:
echo "GEMINI_API_KEY=your_actual_key_here" > backend/.env
bash .devcontainer/start.sh
```

### Backend starts but analysis never completes
Check the backend log:
```bash
tail -50 /tmp/backend.log
```
Common cause: Gemini API key is invalid or rate-limited (free tier = 15 req/min).

### "Port already in use" error
```bash
pkill -f uvicorn; pkill -f "next dev"; sleep 2
bash .devcontainer/start.sh
```

### Codespace was stopped / timed out
Files are preserved. Just re-run:
```bash
bash .devcontainer/start.sh
```

### Frontend shows blank page or 404
Next.js is still compiling. Wait 15–20 seconds and refresh.

---

## After a Codespace restart

Codespaces auto-stop after 30 min of inactivity (free tier). Your files are safe. To resume:
1. Go to https://github.com/codespaces
2. Find your codespace → click **"Open"**
3. Re-run `bash .devcontainer/start.sh`
4. Re-set port 8000 to **Public** (resets on each restart)

---

## Free tier limits

| Service | Free allowance |
|---------|---------------|
| GitHub Codespaces | 120 core-hours/month (2-core = 60 hours of use) |
| Gemini 2.0 Flash | 1,500 requests/day, 15 requests/minute |

One full RegLoop analysis run = ~4 Gemini API calls (one per pipeline stage).
