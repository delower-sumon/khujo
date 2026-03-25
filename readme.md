# Khujo MVP

This repository hosts both the **frontend** and **backend** for the Khujo minimum viable product.

## Overview

- **Frontend** (`src/`): React 18 + TypeScript application built with Vite. Uses Tailwind CSS for styling and implements a simple search interface.
- **Backend** (`backend/`): Python service (FastAPI) providing data models, a crawl queue, search functionality, and transliteration. A virtual environment is expected under `.venv`.

## Getting Started

1. **Backend setup**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1   # Windows PowerShell
   pip install -r requirements.txt
   # run the server
   follow devserver 
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **Frontend setup**
   ```bash
   npm install
   npm run dev   # starts Vite dev server at http://localhost:5173
   ```

3. **Build for production**
   - Backend: package or deploy as needed (no build step).
   - Frontend: `npm run build` - output appears in `dist/`.

## Repository Structure

```
├── backend/             # Python API service
│   ├── main.py          # FastAPI entry point
│   ├── app/
│   │   ├── database.py
│   │   ├── models/      # ORM and schema definitions
│   │   ├── services/    # business logic components
│   │   └── ...
│   └── requirements.txt
├── src/                 # React frontend
│   ├── App.tsx
│   ├── index.css
│   ├── components/
│   ├── pages/
│   └── ...
├── package.json         # Node dependencies & scripts
├── tsconfig.json        # TypeScript config
├── vite.config.ts       # Vite config
├── tailwind.config.js   # Tailwind config
└── README.md            # ← you are here
```

## Scripts

- **Frontend**
  - `npm run dev` – start development server
  - `npm run build` – create production build
  - `npm run preview` – preview production build
- **Backend**
  - `python backend/main.py` (or use uvicorn) to launch service

## Contributing

- Keep logic modular and well-documented.
- Use type hints in Python and interfaces/types in TypeScript.
- Avoid committing generated files (`__pycache__`, `node_modules`, etc.); a suitable `.gitignore` is already in place.

## Notes

- Frontend entrypoint is `src/main.tsx`; **do not modify** `index.html` other than adding links or meta tags.
- Backend uses SQLite by default (check `database.py`).

---


