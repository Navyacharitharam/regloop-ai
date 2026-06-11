# RegLoop AI — Frontend

Next.js 16 frontend for the RegLoop AI regulatory compliance platform.

## Setup

See the root [README.md](../README.md) and [CODESPACES.md](../CODESPACES.md) for full setup instructions.

**Quick start (from repo root):**
```bash
bash .devcontainer/start.sh
```

**Manual start:**
```bash
cd frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm install
npm run dev
```

Frontend runs on **http://localhost:3000** · Backend must be running on port 8000.
