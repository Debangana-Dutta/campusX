# Run OptiCampus in VS Code (Windows / PowerShell)

Open the `Campus-X` folder in VS Code, then use two terminals (Terminal > New Terminal).

**Terminal 1 - backend**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item .env.example .env      # optional; every value has a local default
cd backend
$env:PYTHONPATH = "."
uvicorn app.main:app --port 8000
```
API docs: http://localhost:8000/docs

**Terminal 2 - frontend**
```powershell
cd frontend
Copy-Item .env.example .env      # VITE_API_BASE_URL=http://localhost:8000
npm ci
npm run dev
```
Open http://localhost:5173. Demo accounts and the password are listed in README.md ("Demo accounts").

**Tests (run from the repo root, backend venv active)**
```powershell
$env:PYTHONPATH = ""
pytest
cd frontend; $env:VITE_API_BASE_URL = "http://localhost:8000"; npx vitest run; npm run build
```
Note: the latest parser changes (Hinglish, day-only moves, add-session message) have not been test-run yet; see IMPLEMENTATION_STATUS.md.
