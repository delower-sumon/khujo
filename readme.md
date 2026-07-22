# Khujo MVP

This repository hosts both the **frontend** and **backend** for the Khujo minimum viable product (Bangladesh's Own Search Engine).

## Architecture Overview

- **Frontend** (`public/`): A lightweight, lightning-fast static interface built with pure Vanilla JavaScript, HTML5, and CSS3. No heavy frameworks or build steps are required.
- **Backend** (`backend/`): A Python service built with FastAPI that provides data models, search functionality via `pg_trgm`, and a crawler architecture. It connects to a PostgreSQL database (Neon).

> **Note on Legacy Code:** Folders like `src/`, `package.json`, and `vite.config.ts` belong to the old React implementation and are kept only as a reference. The active frontend is entirely in the `public/` directory.

---

## How to Run the Project Locally

Because the frontend and backend are decoupled, you need to run them in two separate terminal windows.

### 1. Start the Backend (Terminal 1)
The backend needs to run within its Python virtual environment.

```powershell
# From the project root, activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Start the FastAPI server (runs on http://localhost:8000)
python backend/main.py
```
*(The server connects to the Neon PostgreSQL database using the credentials in `backend/.env`)*

### 2. Start the Frontend (Terminal 2)
The frontend is a static site. You just need a simple HTTP server to serve the files from the `public` directory.

```powershell
# From the project root, start a simple Python HTTP server
python -m http.server 8080 --directory public
```
*(You can now access the search engine at **http://localhost:8080**)*

### 3. Stopping the Servers
To stop the servers when you are done testing:
1. Go to the terminal window where the server is running.
2. Press `Ctrl + C` on your keyboard. This will gracefully terminate the running process.
3. Repeat for both Terminal 1 and Terminal 2.

> **Troubleshooting:** If you accidentally closed the terminal without stopping the server and get a "port already in use" error next time you try to start it, you can forcefully stop it in PowerShell using its port number (e.g., for port 8000):
> ```powershell
> Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force
> ```

---

## Repository Structure

```
├── backend/                 # Python API service
│   ├── main.py              # FastAPI entry point & API routes
│   ├── crawler.py           # Content crawler script
│   ├── sql/                 # PostgreSQL schema definitions
│   └── app/                 # Database connection logic
├── public/                  # Active Frontend (Vanilla JS/CSS)
│   ├── index.html           # Landing page
│   ├── search.html          # SERP & Knowledge Graph page
│   ├── admin.html           # Human verification dashboard
│   ├── css/                 # Vanilla CSS stylesheets
│   └── js/                  # Vanilla JS logic
└── docs/                    # Architecture planning and blueprints
```

## Administrative Tools

To view and verify crawled documents before they appear in live search results, visit the Admin Dashboard locally at:
**http://localhost:8080/admin.html**
