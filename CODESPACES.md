# Testing RegLoop AI in GitHub Codespaces

## Step 1 — Push to GitHub

First, push this project to a GitHub repo:

```bash
cd regloop
git init
git add .
git commit -m "RegLoop AI - initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/regloop-ai.git
git push -u origin main
```

---

## Step 2 — Add your Gemini API Key as a Codespaces Secret

This is the most important step. Do it **before** creating the Codespace.

1. Go to **https://github.com/settings/codespaces**
2. Under **Secrets**, click **New secret**
3. Name: `GEMINI_API_KEY`
4. Value: your key from https://aistudio.google.com/app/apikey
5. Under **Repository access**, select your `regloop-ai` repo
6. Click **Add secret**

> ✅ The key is injected automatically into the Codespace environment — you never paste it into any file.

---

## Step 3 — Create the Codespace

1. Go to your repo on GitHub
2. Click the green **Code** button
3. Click the **Codespaces** tab
4. Click **Create codespace on main**

GitHub will:
- Spin up a container using `.devcontainer/devcontainer.json`
- Install Python 3.12 + Node.js 20
- Run `setup.sh` automatically (installs all dependencies, writes `backend/.env`)

This takes **2–3 minutes** the first time.

---

## Step 4 — Make Port 8000 Public

This is required so your **browser** can reach the backend API.

1. In VS Code (inside the Codespace), click the **PORTS** tab at the bottom
2. Find port **8000** (Backend API)
3. Right-click → **Port Visibility** → **Public**
4. Leave port **3000** as Private (it's only accessed from within the Codespace)

> ⚠️ If port 8000 stays Private, the frontend running in your browser cannot reach the API and you'll see network errors.

---

## Step 5 — Start the App

Open a terminal in the Codespace (`` Ctrl+` ``) and run:

```bash
bash .devcontainer/start.sh
```

You'll see:

```
▸ Detected Codespaces environment
  ✓ Backend URL: https://YOUR-CODESPACE-8000.app.github.dev
  ✓ Frontend configured to talk to: https://...
▸ Starting FastAPI backend on port 8000...
  ✓ Backend is up
▸ Starting Next.js frontend on port 3000...

╔══════════════════════════════════════╗
║  RegLoop AI is running!              ║
║  Frontend:  port 3000                ║
║  Backend:   port 8000  (/docs)       ║
╚══════════════════════════════════════╝
```

---

## Step 6 — Open the App

1. In the **PORTS** tab, find port **3000**
2. Click the 🌐 globe icon (or hover → **Open in Browser**)
3. The RegLoop AI app opens in a new tab

---

## Step 7 — Run the Demo with Sample Data

Sample files are in `sample_data/`:

| File | Upload as |
|------|-----------|
| `DORA_ICT_Risk_Update_2026.pdf` | Regulatory Update |
| `ICT_Risk_Policy.pdf` | Internal Policy |
| `Vendor_Risk_Policy.pdf` | Internal Policy |
| `Incident_Response_Policy.pdf` | Internal Policy |
| `responsibility_matrix.csv` | Responsibility Matrix |

**Walkthrough:**

1. Click **New Workspace**
2. Upload all 5 files in the **Upload** tab
3. Watch the pre-flight checklist turn green
4. Click **Run Compliance Analysis**
5. Watch the progress bar and obligation counter climb in real time
6. Explore **Obligations** → expand rows to see mappings, gaps, before/after diffs
7. Go to **Policy Mapping** → see all matches grouped by document
8. Go to **Gap Analysis** → see the coverage table
9. Go to **Review PRs** → Approve / Modify / Reject / Escalate each PR
10. Go to **Audit Trail** → see the traceability grid
11. Go to **Export** → download JSON and CSV

---

## Verify the API directly

The backend Swagger UI is available at:

```
https://YOUR-CODESPACE-8000.app.github.dev/docs
```

(Find the URL in the PORTS tab, port 8000)

---

## Troubleshooting

### "Network Error" or CORS errors in browser console

Port 8000 is not public. Fix:
- PORTS tab → port 8000 → right-click → Port Visibility → **Public**

### "GEMINI_API_KEY is not set"

The secret wasn't added before creating the Codespace. Fix:
```bash
echo "GEMINI_API_KEY=your_actual_key_here" > backend/.env
```
Then re-run `bash .devcontainer/start.sh`

### "Analysis stuck on Analyzing..."

Check backend terminal for errors:
```bash
cd backend && uvicorn main:app --reload --port 8000
```
Common cause: Gemini API key is invalid. Verify at https://aistudio.google.com

### Ports tab not visible

Click the **≡** menu (hamburger) → **Terminal** → **New Terminal** → then look at bottom panel tabs.

### Re-running after a restart

Codespaces persist your files but stop the servers. Just run:
```bash
bash .devcontainer/start.sh
```

---

## Free tier limits

- GitHub Codespaces: 120 core-hours/month free (2-core = 60 hours)
- Gemini 2.0 Flash: 1,500 requests/day free, 15 requests/minute
- One full analysis run uses ~14 × 4 = 56 API calls (one per obligation × 4 prompts)
