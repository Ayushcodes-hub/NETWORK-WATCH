# NETWORK WATCH

A network monitoring and heuristic intrusion detection dashboard built with Python, FastAPI, Scapy and JavaScript.

## Features
- Network packet monitoring
- Protocol and traffic analytics
- Connection monitoring
- Port scanning detection
- Suspicious port detection
- DNS activity monitoring
- Security alerts
- CSV exports
- Public synthetic-data demonstration

## Architecture
- Backend: FastAPI
- Frontend: HTML, CSS, JavaScript
- Packet capture: Scapy and Npcap
- Database: SQLite
- Deployment: Render and Vercel

## Local execution

Install dependencies:

    pip install -r backend/requirements.txt

Start the backend:

    uvicorn backend.main:app --reload

Open http://127.0.0.1:8000

## Public demo

The hosted demonstration uses synthetic network data. It does not capture visitors' actual network traffic.

## Disclaimer

Educational network monitoring and heuristic detection project. Not a replacement for a production-grade intrusion detection system.
