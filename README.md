# NETWORK WATCH

**A real-time network monitoring and heuristic intrusion detection platform.**

NETWORK WATCH captures and analyzes network traffic, monitors network interfaces and connections, tracks protocol activity, and identifies potentially suspicious behavior through heuristic detection.

[![Windows Download](https://img.shields.io/badge/Download-Windows%20EXE-blue?logo=windows)](https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases/latest)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/Ayushcodes-hub/NETWORK-WATCH)
[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)

**Project website:** https://ayushcodes-hub.github.io/NETWORK-WATCH/

**Online demonstration:** https://frontend-1z130vhcc-a-001e.vercel.app/

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Windows Installation](#windows-installation)
- [Running from Source](#running-from-source)
- [Online Demonstration](#online-demonstration)
- [API](#api)
- [Automated Testing](#automated-testing)
- [Building the Executable](#building-the-executable)
- [Security and Privacy](#security-and-privacy)
- [Limitations](#limitations)
- [Disclaimer](#disclaimer)

## Overview

NETWORK WATCH provides a unified interface for observing network activity and investigating suspicious traffic patterns.

The application combines packet capture, protocol classification, connection monitoring, historical storage, and heuristic detection in a FastAPI-powered backend with a browser-based dashboard.

It supports two distinct operating modes:

| Mode | Purpose |
|---|---|
| Local monitoring | Captures actual network traffic on the user's machine |
| Public demonstration | Displays synthetic data without capturing visitor traffic |

The Windows desktop executable runs the backend locally and opens the dashboard in the user's browser.

## Features

### Network Monitoring

- Live network packet monitoring.
- Network interface discovery.
- Traffic volume and packet statistics.
- Upload and download traffic tracking.
- TCP, UDP, DNS, TLS, ICMP and other protocol categorization.
- Connection monitoring.

### Security Analysis

- Heuristic port-scan detection.
- Suspicious port activity monitoring.
- DNS activity tracking.
- Security event and alert generation.
- Historical activity analysis.

### Dashboard and Data

- Browser-based monitoring dashboard.
- Protocol analytics.
- Traffic statistics.
- SQLite-backed historical storage.
- Event and alert history.
- CSV export functionality.

## Architecture

```mermaid
flowchart TD
    A[Network Interfaces] --> B[Npcap]
    B --> C[Scapy Packet Capture]
    C --> D[FastAPI Backend]
    D --> E[Traffic Analysis]
    D --> F[Heuristic Detection]
    D --> G[SQLite Database]
    E --> H[REST API]
    F --> H
    G --> H
    H --> I[HTML CSS JavaScript Dashboard]
```

### Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Packet capture | Scapy, Npcap |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| System monitoring | psutil |
| Local server | Uvicorn |
| Desktop packaging | PyInstaller |
| Backend hosting | Render |
| Frontend hosting | Vercel |
| Automated builds | GitHub Actions |
| Project website | GitHub Pages |

## Windows Installation

### Requirements

- Windows 10 or Windows 11, 64-bit.
- Npcap installed for live packet capture.
- Administrator permissions may be required for packet capture.
- A modern web browser.

### 1. Download

Visit:

**https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases/latest**

Download:

`NETWORK-WATCH.exe`

### 2. Install Npcap

Download Npcap from its official website:

https://npcap.com/

Install it before attempting live packet capture. Npcap is a separate system dependency and is not bundled with NETWORK WATCH.

### 3. Run the application

Double-click `NETWORK-WATCH.exe`.

The application will:

1. Check Windows permissions.
2. Detect Npcap.
3. Start the local FastAPI server.
4. Open the monitoring dashboard.
5. Begin local monitoring when initialization succeeds.

Keep the application console open while using the dashboard.

Press `Ctrl+C` in the console to shut down the application.

If packet capture fails, try running the executable as Administrator.

### 4. Verify the download

The release includes a SHA256 checksum file.

In PowerShell:

```powershell
Get-FileHash .\NETWORK-WATCH.exe -Algorithm SHA256
```

Compare the displayed hash against the corresponding `.sha256` release asset.

Only download the executable from the official GitHub Releases page.

## Running from Source

### Requirements

- Python 3.13 recommended.
- Npcap on Windows for live packet capture.
- Git.
- A modern web browser.

### Clone the repository

```powershell
git clone https://github.com/Ayushcodes-hub/NETWORK-WATCH.git
cd NETWORK-WATCH
```

### Create a virtual environment

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Start the application

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

http://127.0.0.1:8000

## Online Demonstration

The hosted demonstration uses synthetic network data.

- **Frontend:** https://frontend-1z130vhcc-a-001e.vercel.app/
- **Backend:** https://network-watch-api.onrender.com/

The public demonstration is isolated from local live monitoring. It does not capture visitors' actual network traffic.

## API

The FastAPI backend exposes endpoints for monitoring and analysis.

| Endpoint | Purpose |
|---|---|
| `/api/health` | Backend health and database status |
| `/api/status` | Monitoring and traffic statistics |
| `/api/interfaces` | Available network interfaces |
| `/api/alerts` | Security alerts |
| `/api/events` | Recorded monitoring events |
| `/api/analytics` | Traffic analytics |
| `/api/connections` | Connection information |
| `/api/history` | Historical monitoring information |
| `/api/export/events.csv` | Export events |
| `/api/export/alerts.csv` | Export alerts |

Interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

## Automated Testing

The repository includes public demonstration regression tests.

Run:

```powershell
python -m backend.test_demo
```

The test suite verifies:

- Health endpoint availability.
- Monitoring status endpoint.
- Alerts and events.
- Analytics and connections.
- Interface and history endpoints.
- CSV export endpoints.
- Public demo restrictions on packet capture.
- Public demo response isolation.

The current regression suite contains 11 API checks.

## Building the Executable

The Windows executable can be built with PyInstaller.

Install dependencies:

```powershell
pip install -r backend/requirements.txt
pip install pyinstaller
```

Build:

```powershell
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

The executable will be generated at:

`dist/NETWORK-WATCH.exe`

GitHub Actions automates the Windows build and release when a version tag beginning with `v` is pushed.

## Security and Privacy

NETWORK WATCH distinguishes local monitoring from its public synthetic-data demonstration.

- The local desktop application binds its monitoring server to `127.0.0.1`.
- Local monitoring data is stored in a SQLite database on the user's computer.
- The public demo uses synthetic data.
- The public demo blocks live packet-capture requests.
- Npcap is required separately for Windows packet capture.

The application is designed for authorized network monitoring. Only monitor networks and devices for which you have permission.

## Limitations

- Detection is heuristic, not signature-complete or machine-learning-based.
- Alerts may include false positives.
- Packet capture capabilities depend on operating-system permissions and Npcap configuration.
- The application is not a replacement for an enterprise SIEM, firewall, or production-grade IDS/IPS.

## Disclaimer

NETWORK WATCH is an educational network monitoring and heuristic intrusion detection project. It is intended for authorized testing, learning, and network visibility.

Use responsibly and comply with applicable laws and network policies.

---

**NETWORK WATCH** | Network Monitoring · Traffic Analytics · Security Visibility

[GitHub Repository](https://github.com/Ayushcodes-hub/NETWORK-WATCH) · [Latest Release](https://github.com/Ayushcodes-hub/NETWORK-WATCH/releases/latest) · [Project Website](https://ayushcodes-hub.github.io/NETWORK-WATCH/)
