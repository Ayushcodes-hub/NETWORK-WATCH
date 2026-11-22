# 🛰️ NETWORK WATCH

**Real-Time Network Monitoring & Heuristic Intrusion Detection Platform**

NETWORK WATCH captures and analyzes live network traffic, monitors interfaces and connections, tracks protocol activity, and flags suspicious behavior through heuristic detection — all from a clean, browser-based dashboard.

[![Windows Download](https://img.shields.io/badge/Windows-Download-0078D6?logo=windows)](https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases/latest)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?logo=github)](https://github.com/Ayushcodes-hub/NETWORK-WATCH)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Unspecified-lightgrey)](#-license)

🌐 **Project Website:** [ayushcodes-hub.github.io/NETWORK-WATCH](https://ayushcodes-hub.github.io/NETWORK-WATCH)
🚀 **Live Demo:** [frontend-1z130vhcc-a-001e.vercel.app](https://frontend-1z130vhcc-a-001e.vercel.app)

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#%EF%B8%8F-architecture)
- [Technology Stack](#-technology-stack)
- [Windows Installation (.exe)](#-windows-installation-exe)
- [Running from Source](#-running-from-source)
- [Environment Variables](#-environment-variables)
- [Online Demonstration](#-online-demonstration)
- [API Reference](#-api-reference)
- [Automated Testing](#-automated-testing)
- [Building the Executable Yourself](#-building-the-executable-yourself)
- [Data Storage](#-data-storage)
- [Security & Privacy](#-security--privacy)
- [Known Issues / Things to Fix](#-known-issues--things-to-fix)
- [Limitations](#%EF%B8%8F-limitations)
- [Disclaimer](#-disclaimer)

---

## 🔍 Overview

NETWORK WATCH provides a unified interface for observing network activity and investigating suspicious traffic patterns in real time. It combines packet capture, protocol classification, connection monitoring, historical storage, and heuristic detection in a FastAPI-powered backend paired with a lightweight vanilla JS/HTML/CSS dashboard.

It ships with two operating modes, controlled by a single `DEMO_MODE` environment variable read in `backend/deployment_config.py`:

| Mode | Purpose | Where it runs |
|---|---|---|
| 🖥️ **Local Monitoring** (`DEMO_MODE=false`) | Captures real, live network traffic on the user's own machine via Npcap/Scapy | Windows `.exe`, or `python -m uvicorn` from source |
| 🌐 **Public Demonstration** (`DEMO_MODE=true`) | Serves synthetic, hardcoded traffic data from `backend/demo_mode.py`; never touches a visitor's real traffic and hard-blocks `/api/capture/*` with HTTP 403 | Render (backend) + Vercel (frontend) |

The Windows desktop executable runs the backend locally on a **dynamically chosen free port** and automatically opens the dashboard in your default browser — no manual setup, no fixed port to remember.

---

## ✨ Features

### 📡 Network Monitoring
- Live packet capture via Scapy's `AsyncSniffer`
- Automatic network interface discovery and smart default-adapter selection (matches your OS's default route first, falls back to any active IPv4 adapter)
- Traffic volume and packet statistics (packet count, byte count)
- Upload / download traffic tracking, split by direction (`OUTBOUND` / `INBOUND` / `TRANSIT-UNKNOWN`)
- Protocol categorization — **TCP, UDP, DNS, TLS (via handshake byte detection), ICMP**, and a catch-all `OTHER`
- Real-time OS-level connection monitoring (`psutil.net_connections`), including process name/PID per connection

### 🛡️ Security Analysis (heuristics, all in `backend/main.py::detect_packet_anomalies`)
- **Suspicious port alert** — any local traffic to a hardcoded watch-list of ports (`1337, 4444, 5555, 6667, 9001, 9002, 12345, 12346, 31337`)
- **New external endpoint alert** — first-ever connection observed to a given public `ip:port` pair this session
- **Port-scan heuristic** — flags a source IP that sends TCP SYN (no ACK) packets to ≥ 20 distinct ports within a rolling 60-second window
- **DNS burst heuristic** — flags a source IP issuing ≥ 100 DNS packets within a rolling 60-second window
- **New listening port alert** — background worker diffs the OS's listening-socket set every 30s and alerts on newly opened listeners
- Alerts are de-duplicated: the same `(category, evidence)` pair is suppressed for 60 seconds to avoid spam

### 📊 Dashboard & Data
- Browser-based monitoring dashboard (Analytics, Alerts, Connections, Events, Interfaces panels)
- SQLite-backed historical storage (packet events, alerts, connection history, interface history)
- Full event & alert history with search/filter (by protocol, by IP/port/DNS substring)
- One-click CSV export for both events and alerts

---

## 🏗️ Architecture

```
                         ┌─────────────────────────────┐
                         │   Browser Dashboard (JS)    │
                         │  frontend/index.html + app.js│
                         └───────────────┬──────────────┘
                                         │ REST (fetch) + CORS
                                         ▼
                         ┌─────────────────────────────┐
                         │      FastAPI Backend        │
                         │       backend/main.py       │
                         │                              │
                         │  Scapy AsyncSniffer ───► classify_packet()
                         │        │                 ───► detect_packet_anomalies()
                         │        ▼                      │
                         │  psutil (connections,         ▼
                         │  interfaces, listeners)   SQLite (network_watch.db)
                         └───────────────┬──────────────┘
                                         │
                      DEMO_MODE=true?  ──┤── intercepted by middleware
                                         │   → backend/demo_mode.py
                                         ▼     (synthetic JSON, no real data)
```

- **Local / `.exe` mode:** `run_app.py` launches the FastAPI app with Uvicorn on `127.0.0.1` on a free ephemeral port, waits for `/api/health` to respond, then opens your browser to it automatically. The frontend's `/config.js` is overridden server-side (see `backend/main.py`, route `GET /config.js`) to point at an empty API base (`''`) so the dashboard always calls same-origin — no hardcoded URL needed locally.
- **Hosted / demo mode:** `frontend/config.js` (served statically, committed as a real file) points the Vercel-hosted frontend at the Render backend URL (`https://network-watch-api.onrender.com`). The backend's demo middleware intercepts every `/api/*` request and returns static/synthetic payloads instead of touching live sockets.

---

## 🧰 Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Packet Capture | Scapy, Npcap (Windows) |
| System/Process Monitoring | psutil |
| Frontend | HTML, CSS, vanilla JavaScript |
| Database | SQLite (WAL mode) |
| Desktop Packaging | PyInstaller (`--onefile`) |
| Backend Hosting | Render (`render.yaml`) |
| Frontend Hosting | Vercel (`frontend/vercel.json`) |
| CI/CD | GitHub Actions (`.github/workflows/release.yml`, `pages.yml`) |
| Project Website | GitHub Pages (`docs/index.html`) |

---

## 🪟 Windows Installation (.exe)

### Requirements
- Windows 10 / 11, 64-bit
- **[Npcap](https://npcap.com/)** installed — required for live packet capture, **not bundled** in the executable
- Administrator permissions (recommended; packet capture on Windows often needs them)
- A modern web browser

### 1. Download
Grab the latest build from the **[Releases page](https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases/latest)**:

```
NETWORK-WATCH.exe
```

### 2. Install Npcap
Install Npcap from the [official site](https://npcap.com/) **before** attempting live packet capture. During setup, make sure **"Install Npcap in WinPcap API-compatible Mode"** is checked if offered — this maximizes compatibility with Scapy.

### 3. Run the application
Double-click `NETWORK-WATCH.exe` (or right-click → **Run as administrator** for best results). On launch it will, in order:

1. Check whether it's running with Administrator privileges (warns if not — capture may fail without them)
2. Detect Npcap under `System32`/`SysWOW64` (warns if not found)
3. Pick a free local port, start the FastAPI/Uvicorn server on `127.0.0.1:<that port>`, and poll `/api/health` until it responds (up to 45 seconds)
4. Open the dashboard automatically in your default browser

> ⚠️ **The port is chosen automatically each run — it is not always the same number.** You don't need to remember it: the app opens the correct URL in your browser for you. Do **not** bookmark a fixed `localhost:XXXX` address and expect it to work next time.

**Keep the console window open** while using the dashboard — closing it stops the backend. Press **Ctrl+C** in the console to shut it down cleanly. If packet capture fails or shows an error in the dashboard, close the app and relaunch it **as Administrator**.

### 4. Verify the download (recommended)
Each release ships with a SHA256 checksum. Verify it in PowerShell:

```powershell
Get-FileHash .\NETWORK-WATCH.exe -Algorithm SHA256
```

Compare the output against the matching `NETWORK-WATCH.exe.sha256` file in the same release. Only download from the official [GitHub Releases](https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases) page.

---

## 🧑‍💻 Running from Source

### Requirements
- Python 3.13 (recommended — matches the CI build environment)
- [Npcap](https://npcap.com/) (Windows, required for live packet capture)
- Git
- A modern web browser

### Clone & set up a virtual environment

```powershell
git clone https://github.com/Ayushcodes-hub/NETWORK-WATCH.git
cd NETWORK-WATCH
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

*(macOS/Linux: `python3.13 -m venv .venv && source .venv/bin/activate` — note live packet capture is Windows/Npcap-oriented in this project; on Linux you'd need libpcap and root/`CAP_NET_RAW` instead, which this codebase does not specifically account for.)*

### Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

> ⚠️ See [**Known Issues**](#-known-issues--things-to-fix) below — `backend/requirements.txt` currently lists `httpx2` (a real but unrelated PyPI package) instead of `httpx`, and nothing in the codebase imports `httpx` at all. It installs fine and doesn't break anything, but it's a leftover/typo you may want to remove.

### Launch

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000** in your browser. Running this way uses `DEMO_MODE` from your environment/`.env` (defaults to `false` if unset — i.e. **real local capture mode** — see [Environment Variables](#-environment-variables)).

---

## ⚙️ Environment Variables

Read in `backend/deployment_config.py`. Copy `.env.example` to `.env` and adjust:

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `false` | `true` serves synthetic data only and blocks `/api/capture/*` (used for the public Render deployment). `false` enables real local packet capture. |
| `FRONTEND_ORIGIN` | `http://localhost:5500` | The frontend origin allowed by CORS when `DEMO_MODE=false`. Set this to your deployed/dev frontend URL. Ignored (CORS opens to `*`) when `DEMO_MODE=true`. |

Note: `run_app.py` (the `.exe`/desktop launcher) **force-sets `DEMO_MODE=false`** and `FRONTEND_ORIGIN=http://127.0.0.1` in code before importing the backend — so `.env` values are irrelevant when running the packaged executable; they only matter when running from source or deploying to Render.

---

## 🌐 Online Demonstration

The hosted demo runs entirely on synthetic network data defined in `backend/demo_mode.py` and is fully isolated from local live monitoring — it never captures a visitor's real traffic, and `/api/capture/start` / `/api/capture/stop` always return HTTP 403 in this mode.

| Component | URL |
|---|---|
| Frontend | https://frontend-1z130vhcc-a-001e.vercel.app |
| Backend | https://network-watch-api.onrender.com |

> Render's free plan spins down idle services — the first request to the demo backend after inactivity may take 30–60 seconds to respond while it cold-starts.

---

## 📡 API Reference

All endpoints are prefixed under `/api/` and served by FastAPI (`backend/main.py`). When `DEMO_MODE=true`, every one of these (except static files) is intercepted and answered with synthetic data from `backend/demo_mode.py` instead.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend health & database existence check |
| GET | `/api/status` | Live packet/byte counters, capture state, local IPs |
| GET | `/api/capture/interfaces` | List available Npcap capture devices + detected default |
| POST | `/api/capture/start` | Start live packet capture (optional `{"interface": "..."}` body) |
| POST | `/api/capture/stop` | Stop live packet capture |
| GET | `/api/connections` | Current OS-level TCP/UDP connections with process info |
| GET | `/api/interfaces` | Network interface stats (bytes/packets sent & received) |
| GET | `/api/alerts` | Security alerts (`?limit=` 1–1000, default 100) |
| GET | `/api/events` | Recorded packet events (`?limit=`, `?search=`, `?protocol=`) |
| GET | `/api/analytics` | Protocol breakdown, last-hour timeline, totals |
| GET | `/api/history` | Stored interface/connection history snapshots |
| GET | `/api/export/events.csv` | Export up to 10,000 events as CSV |
| GET | `/api/export/alerts.csv` | Export up to 10,000 alerts as CSV |

Interactive Swagger docs (auto-generated by FastAPI) are available at:

```
http://127.0.0.1:8000/docs
```

*(or whatever host/port you're running on — e.g. the dynamic port the `.exe` opens)*

---

## ✅ Automated Testing

The repo includes a regression suite (`backend/test_demo.py`) that exercises the **public demo mode only**, using FastAPI's `TestClient`:

```bash
python -m backend.test_demo
```

It forces `DEMO_MODE=true` for the test run and checks **11 conditions**:

1. `/api/health` returns 200
2. `/api/status` returns 200
3. `/api/alerts` returns 200
4. `/api/events` returns 200
5. `/api/analytics` returns 200
6. `/api/connections` returns 200
7. `/api/interfaces` returns 200
8. `/api/history` returns 200
9. `/api/export/events.csv` returns 200
10. `/api/export/alerts.csv` returns 200
11. `POST /api/capture/start` is correctly **blocked** with HTTP 403 in demo mode

Every response is also checked for the `X-Network-Watch-Mode: public-demo` header, and `/api/status` is checked to confirm `demo_mode: true` and `capture_running: false`. This same command runs automatically in CI (`.github/workflows/release.yml`) before every Windows build — a failing test blocks the release.

> There is currently no automated test coverage for real (`DEMO_MODE=false`) local capture mode — only the demo path is tested.

---

## 📦 Building the Executable Yourself

Built with PyInstaller. This is exactly the command CI runs in `.github/workflows/release.yml`:

```powershell
pip install -r backend/requirements.txt
pip install pyinstaller

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name NETWORK-WATCH `
    --add-data "frontend;frontend" `
    --collect-all scapy `
    --collect-all fastapi `
    --collect-all uvicorn `
    --collect-all starlette `
    --hidden-import backend.demo_mode `
    --hidden-import backend.deployment_config `
    run_app.py
```

**Output:** `dist/NETWORK-WATCH.exe`

This must be run on **Windows** (backtick line-continuations are PowerShell syntax; the CI job itself runs on `runs-on: windows-latest`). The entry point is `run_app.py`, not `backend/main.py` directly — `run_app.py` is what sets `DEMO_MODE=false`, finds a free port, and opens the browser.

GitHub Actions (`release.yml`) automatically builds, tests, and publishes the Windows executable (plus its `.sha256` checksum) as a GitHub Release whenever a tag matching `v*` (e.g. `v3.0.1`) is pushed to the repo.

---

## 🗄️ Data Storage

- **From source:** `backend/data/network_watch.db` (relative to the repo), created automatically on first run. Ignored by `.gitignore`.
- **From the `.exe`:** PyInstaller's `--onefile` mode extracts to a temporary folder (`sys._MEIPASS`) on every launch, so the database is deliberately stored **outside** that temp folder, at:

  ```
  %LOCALAPPDATA%\NetworkWatch\data\network_watch.db
  ```

  This is why your capture history, alerts, and events **persist between runs** of the executable even though the app itself re-extracts each time. Deleting that folder resets all local history.
- Tables: `packet_events`, `alerts`, `connection_history`, `interface_history` — all indexed on timestamp (and `packet_events` additionally on protocol). SQLite runs in WAL mode.

---

## 🔐 Security & Privacy

- The local desktop app binds its monitoring server to `127.0.0.1` only — not reachable from your network
- Local monitoring data stays in a local SQLite database on your machine (see [Data Storage](#-data-storage))
- The public demo uses synthetic data only (`backend/demo_mode.py`) and never processes real packets
- The public demo hard-blocks all `/api/capture/start` and `/api/capture/stop` requests (HTTP 403)
- "TLS" classification only detects a recognizable TLS handshake record header (`0x16 0x03` at the start of the TCP payload) — it does **not** decrypt or inspect encrypted contents
- Npcap must be installed separately for Windows packet capture; it is not bundled with the app and not installed silently by it

> ⚠️ **NETWORK WATCH is designed for authorized network monitoring only.** Only monitor networks and devices you have explicit permission to observe.

---

## 🐛 Known Issues / Things to Fix

Found while reviewing the actual source for this README — not present in earlier README drafts:

1. **`backend/requirements.txt` lists `httpx2`, not `httpx`.** `httpx2` is a real, unrelated package on PyPI, so `pip install` succeeds silently — it just installs a dependency the project never actually imports or uses anywhere. Harmless today, but worth fixing to avoid confusion (likely a typo for `httpx`).
2. **The `.exe` opens a different localhost port every launch** (chosen via an OS-assigned free port in `run_app.py::find_free_port`). This is intentional (avoids port clashes) but means you can't rely on a fixed bookmark/shortcut to the dashboard — always launch via the `.exe` itself.
3. **No `LICENSE` file was found in the repository**, so the badge above and this README cannot state real license terms. Add a `LICENSE` file if you intend this to be open source under a specific license.
4. **Linux/macOS packet capture is not actually supported by this codebase** despite Scapy being cross-platform — `run_app.py`'s Npcap detection and the interface-resolution logic in `backend/main.py` are Windows/Npcap-specific (`SystemRoot`, `System32`, `wpcap.dll`). Running from source on Linux will start the API, but live capture is unverified there.
5. **Demo-mode `/api/status` and real-mode `/api/status` have slightly different JSON shapes** (e.g. demo mode includes `"demo_mode": true` and omits `started_at`/includes different fields) — fine for the dashboard as built, but worth knowing if you build your own API client against both modes.

---

## ⚠️ Limitations

- Detection is heuristic, not signature-complete or ML-based
- Alerts may include false positives (e.g. legitimate software using an uncommon port)
- Packet capture depends on OS permissions and correct Npcap configuration
- Not a replacement for an enterprise SIEM, firewall, or production-grade IDS/IPS

---

## 📄 Disclaimer

NETWORK WATCH is an educational network monitoring and heuristic intrusion detection project, intended for authorized testing, learning, and network visibility.

**Use responsibly and comply with all applicable laws and network policies.**

---

**NETWORK WATCH** · Network Monitoring · Traffic Analytics · Security Visibility

[Repository](https://github.com/Ayushcodes-hub/NETWORK-WATCH) · [Latest Release](https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases/latest) · [Project Website](https://ayushcodes-hub.github.io/NETWORK-WATCH)
