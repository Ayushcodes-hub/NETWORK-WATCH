import csv
import io
import ipaddress
import os
import socket
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import psutil
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scapy.all import (
    AsyncSniffer, conf, get_if_list,
    IP, IPv6, TCP, UDP, DNS, DNSQR, ICMP, Raw
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "backend" / "data"
DB_PATH = DATA_DIR / "network_watch.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_LOCK = threading.RLock()
STATE_LOCK = threading.RLock()
DETECTION_LOCK = threading.RLock()

capture = None
capture_running = False
capture_interface = None
capture_started_at = None
capture_error = None

stats = {
    "packets": 0,
    "bytes": 0,
    "upload_bytes": 0,
    "download_bytes": 0,
    "tcp": 0,
    "udp": 0,
    "dns": 0,
    "tls": 0,
    "icmp": 0,
    "other": 0,
    "started_at": None,
}

local_ips = set()
known_listeners = set()
listener_baseline_ready = False

syn_activity = defaultdict(deque)
dns_activity = defaultdict(deque)
seen_external_endpoints = set()
last_alert_times = {}

SUSPICIOUS_PORTS = {
    1337, 4444, 5555, 6667, 9001, 9002,
    12345, 12346, 31337
}

WATCHED_PORTS = {
    21, 22, 23, 25, 445, 1433, 3306,
    3389, 5900, 6379, 8080, 9200
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def db_connection():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with DB_LOCK:
        con = db_connection()
        con.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS packet_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            protocol TEXT,
            src_ip TEXT,
            dst_ip TEXT,
            src_port INTEGER,
            dst_port INTEGER,
            packet_size INTEGER,
            direction TEXT,
            dns_query TEXT,
            interface TEXT
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            severity TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            evidence TEXT
        );

        CREATE TABLE IF NOT EXISTS connection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            protocol TEXT,
            local_ip TEXT,
            local_port INTEGER,
            remote_ip TEXT,
            remote_port INTEGER,
            status TEXT,
            pid INTEGER,
            process TEXT
        );

        CREATE TABLE IF NOT EXISTS interface_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            name TEXT,
            bytes_sent INTEGER,
            bytes_recv INTEGER,
            packets_sent INTEGER,
            packets_recv INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_packet_time
            ON packet_events(timestamp);

        CREATE INDEX IF NOT EXISTS idx_alert_time
            ON alerts(timestamp);

        CREATE INDEX IF NOT EXISTS idx_packet_protocol
            ON packet_events(protocol);
        """)
        con.commit()
        con.close()


def refresh_local_ips():
    global local_ips
    addresses = set()

    try:
        for values in psutil.net_if_addrs().values():
            for address in values:
                if address.family in (socket.AF_INET, socket.AF_INET6):
                    ip = address.address.split("%")[0]
                    try:
                        if not ipaddress.ip_address(ip).is_loopback:
                            addresses.add(ip)
                    except ValueError:
                        pass
    except Exception:
        pass

    local_ips = addresses


def is_private_address(value):
    try:
        ip = ipaddress.ip_address(value.split("%")[0])
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except (ValueError, AttributeError):
        return True


def save_alert(severity, category, title, description, evidence=""):
    key = (category, evidence or title)
    now = time.time()

    with DETECTION_LOCK:
        previous = last_alert_times.get(key, 0)
        if now - previous < 60:
            return
        last_alert_times[key] = now

    with DB_LOCK:
        con = db_connection()
        con.execute("""
            INSERT INTO alerts
            (timestamp, severity, category, title, description, evidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp(), severity, category,
            title, description, str(evidence)
        ))
        con.commit()
        con.close()


def save_packet_event(event):
    with DB_LOCK:
        con = db_connection()
        con.execute("""
            INSERT INTO packet_events
            (timestamp, protocol, src_ip, dst_ip, src_port,
             dst_port, packet_size, direction, dns_query, interface)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event["timestamp"], event["protocol"],
            event["src_ip"], event["dst_ip"],
            event["src_port"], event["dst_port"],
            event["packet_size"], event["direction"],
            event["dns_query"], event["interface"]
        ))
        con.commit()
        con.close()


def classify_packet(packet):
    src_ip = None
    dst_ip = None

    if IP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
    elif IPv6 in packet:
        src_ip = packet[IPv6].src
        dst_ip = packet[IPv6].dst

    if not src_ip or not dst_ip:
        return None

    protocol = "OTHER"
    src_port = None
    dst_port = None
    dns_query = None

    if TCP in packet:
        protocol = "TCP"
        src_port = int(packet[TCP].sport)
        dst_port = int(packet[TCP].dport)

        # This detects a recognizable TLS handshake record,
        # not decrypted TLS content.
        if Raw in packet:
            payload = bytes(packet[Raw].load)
            if len(payload) >= 3 and payload[0] == 0x16 and payload[1] == 0x03:
                protocol = "TLS"

    elif UDP in packet:
        protocol = "UDP"
        src_port = int(packet[UDP].sport)
        dst_port = int(packet[UDP].dport)

    if DNS in packet:
        protocol = "DNS"
        try:
            if DNSQR in packet:
                dns_query = packet[DNSQR].qname.decode(
                    "utf-8", errors="replace"
                ).rstrip(".")
        except Exception:
            dns_query = None

    elif ICMP in packet:
        protocol = "ICMP"

    return {
        "timestamp": timestamp(),
        "protocol": protocol,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": dst_port,
        "packet_size": len(packet),
        "dns_query": dns_query,
    }


def detect_packet_anomalies(event, packet):
    src = event["src_ip"]
    dst = event["dst_ip"]
    dst_port = event["dst_port"]

    # Unusual destination ports from this machine.
    if src in local_ips and dst_port in SUSPICIOUS_PORTS:
        save_alert(
            "HIGH", "SUSPICIOUS_PORT",
            f"Traffic to unusual port {dst_port}",
            f"Local host {src} communicated with {dst}:{dst_port}.",
            f"{src}:{event['src_port']} -> {dst}:{dst_port}"
        )

    # Newly observed public destination.
    if src in local_ips and not is_private_address(dst):
        endpoint = (dst, dst_port)
        if endpoint not in seen_external_endpoints:
            seen_external_endpoints.add(endpoint)
            save_alert(
                "INFO", "NEW_EXTERNAL_ENDPOINT",
                "New external endpoint observed",
                f"First observed connection to {dst}:{dst_port}.",
                f"{dst}:{dst_port}"
            )

    # TCP SYN scan heuristic: SYN set, ACK not set.
    if TCP in packet and (int(packet[TCP].flags) & 0x12) == 0x02:
        if src in local_ips:
            now = time.time()
            history = syn_activity[src]
            history.append((now, dst_port))

            while history and now - history[0][0] > 60:
                history.popleft()

            unique_ports = {port for _, port in history}
            if len(unique_ports) >= 20:
                save_alert(
                    "HIGH", "PORT_SCAN_PATTERN",
                    "Possible port scanning activity",
                    f"{src} sent TCP SYN packets to "
                    f"{len(unique_ports)} distinct ports in 60 seconds.",
                    src
                )

    # DNS request burst heuristic.
    if event["protocol"] == "DNS" and src in local_ips:
        now = time.time()
        history = dns_activity[src]
        history.append(now)

        while history and now - history[0] > 60:
            history.popleft()

        if len(history) >= 100:
            save_alert(
                "MEDIUM", "DNS_BURST",
                "High DNS request volume",
                f"{src} generated at least 100 DNS packets in 60 seconds.",
                src
            )


def process_packet(packet):
    try:
        event = classify_packet(packet)
        if not event:
            return

        src = event["src_ip"]
        dst = event["dst_ip"]

        if src in local_ips:
            event["direction"] = "OUTBOUND"
        elif dst in local_ips:
            event["direction"] = "INBOUND"
        else:
            event["direction"] = "TRANSIT/UNKNOWN"

        event["interface"] = capture_interface or "Default"

        with STATE_LOCK:
            stats["packets"] += 1
            stats["bytes"] += event["packet_size"]

            if event["direction"] == "OUTBOUND":
                stats["upload_bytes"] += event["packet_size"]
            elif event["direction"] == "INBOUND":
                stats["download_bytes"] += event["packet_size"]

            stats[event["protocol"].lower() if event["protocol"].lower()
                  in stats else "other"] += 1

        save_packet_event(event)
        detect_packet_anomalies(event, packet)

    except Exception as exc:
        print("Packet processing error:", exc)


def get_connections():
    result = []

    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError):
        return result

    for item in connections:
        try:
            local_ip = item.laddr.ip if item.laddr else ""
            local_port = item.laddr.port if item.laddr else None
            remote_ip = item.raddr.ip if item.raddr else ""
            remote_port = item.raddr.port if item.raddr else None

            process = "Unknown"
            if item.pid:
                try:
                    process = psutil.Process(item.pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            result.append({
                "protocol": "TCP" if item.type == socket.SOCK_STREAM else "UDP",
                "local_ip": local_ip,
                "local_port": local_port,
                "remote_ip": remote_ip,
                "remote_port": remote_port,
                "status": item.status or "UNKNOWN",
                "pid": item.pid,
                "process": process
            })
        except Exception:
            continue

    return result


def get_interfaces():
    result = []
    counters = psutil.net_io_counters(pernic=True)
    addresses = psutil.net_if_addrs()
    stats_by_name = psutil.net_if_stats()

    for name, counter in counters.items():
        ips = []
        for address in addresses.get(name, []):
            if address.family == socket.AF_INET:
                ips.append(address.address)

        status = stats_by_name.get(name)
        result.append({
            "name": name,
            "ipv4": ", ".join(ips) or "—",
            "is_up": bool(status.isup) if status else False,
            "speed_mbps": status.speed if status else 0,
            "bytes_sent": counter.bytes_sent,
            "bytes_recv": counter.bytes_recv,
            "packets_sent": counter.packets_sent,
            "packets_recv": counter.packets_recv
        })

    return result


def monitor_listening_ports():
    global known_listeners, listener_baseline_ready

    current = set()

    try:
        for connection in psutil.net_connections(kind="inet"):
            if connection.status == psutil.CONN_LISTEN and connection.laddr:
                current.add((
                    connection.laddr.ip,
                    connection.laddr.port,
                    connection.pid
                ))
    except (psutil.AccessDenied, OSError):
        return

    # Establish baseline without reporting every existing listener.
    if not listener_baseline_ready:
        known_listeners = current
        listener_baseline_ready = True
        return

    new_listeners = current - known_listeners

    for ip, port, pid in new_listeners:
        process = "Unknown"
        if pid:
            try:
                process = psutil.Process(pid).name()
            except Exception:
                pass

        save_alert(
            "MEDIUM", "NEW_LISTENING_PORT",
            f"New listening port detected: {port}",
            f"Process {process} (PID {pid}) began listening on {ip}:{port}.",
            f"{ip}:{port}:{pid}"
        )

    known_listeners = current


def collect_history():
    now = timestamp()

    connections = get_connections()
    interfaces = get_interfaces()

    with DB_LOCK:
        con = db_connection()

        for item in connections:
            con.execute("""
                INSERT INTO connection_history
                (timestamp, protocol, local_ip, local_port,
                 remote_ip, remote_port, status, pid, process)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, item["protocol"], item["local_ip"],
                item["local_port"], item["remote_ip"],
                item["remote_port"], item["status"],
                item["pid"], item["process"]
            ))

        for item in interfaces:
            con.execute("""
                INSERT INTO interface_history
                (timestamp, name, bytes_sent, bytes_recv,
                 packets_sent, packets_recv)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                now, item["name"], item["bytes_sent"],
                item["bytes_recv"], item["packets_sent"],
                item["packets_recv"]
            ))

        con.commit()
        con.close()


def history_worker():
    while True:
        try:
            refresh_local_ips()
            monitor_listening_ports()
            collect_history()
        except Exception as exc:
            print("History worker error:", exc)

        time.sleep(30)


class CaptureRequest(BaseModel):
    interface: str | None = None

def resolve_capture_interface(requested=None):
    """Resolve friendly adapter names to their Npcap device identifiers."""
    conf.use_pcap = True

    available = get_if_list()
    adapters = list(conf.ifaces.values())

    def get_device(adapter):
        guid = getattr(adapter, "guid", None)

        if guid:
            normalized_guid = str(guid).strip("{}").lower()

            for device in available:
                if normalized_guid in device.lower():
                    return device

        return None

    # Exact Npcap device identifier.
    if requested:
        for device in available:
            if requested.strip().lower() == device.lower():
                return device

        # Friendly adapter name, e.g. WiFi.
        for adapter in adapters:
            names = [
                getattr(adapter, "name", ""),
                getattr(adapter, "description", ""),
            ]

            if any(
                requested.strip().lower() == str(name).strip().lower()
                for name in names if name
            ):
                device = get_device(adapter)
                if device:
                    return device

        raise ValueError(
            f"Interface '{requested}' was not found or has no Npcap device."
        )

    # Prefer the adapter selected by Scapy's default IPv4 route.
    try:
        route = conf.route.route("0.0.0.0")
        route_adapter = route[0]

        device = get_device(route_adapter)
        if device:
            return device

    except Exception as exc:
        print("Default route detection warning:", exc)

    # Fallback: find an adapter with an active IPv4 address.
    try:
        active_ips = set()

        for name, addresses in psutil.net_if_addrs().items():
            interface_stats = psutil.net_if_stats().get(name)

            if not interface_stats or not interface_stats.isup:
                continue

            for address in addresses:
                if address.family == socket.AF_INET:
                    ip = address.address

                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        active_ips.add(ip)

        for adapter in adapters:
            adapter_ips = getattr(adapter, "ips", {}).get(4, [])

            if any(ip in active_ips for ip in adapter_ips):
                device = get_device(adapter)
                if device:
                    return device

    except Exception as exc:
        print("Active adapter detection warning:", exc)

    raise ValueError(
        "Could not identify an active network adapter. "
        "Select an interface manually."
    )

def start_capture(interface=None):
    global capture, capture_running, capture_interface
    global capture_started_at, capture_error

    if capture_running:
        return {"message": "Capture is already running."}

    try:
        conf.use_pcap = True

        selected_device = resolve_capture_interface(interface)

        refresh_local_ips()

        sniffer = AsyncSniffer(
            iface=selected_device,
            prn=process_packet,
            store=False
        )

        sniffer.start()

        capture = sniffer
        capture_interface = selected_device
        capture_running = True
        capture_started_at = timestamp()
        capture_error = None

        with STATE_LOCK:
            stats["started_at"] = capture_started_at

        return {
            "message": "Packet capture started.",
            "interface": selected_device
        }

    except Exception as exc:
        capture_error = str(exc)
        capture_running = False
        capture = None

        print("Capture startup error:", repr(exc))

        return {"error": str(exc)}

def stop_capture():
    global capture, capture_running

    try:
        if capture and capture_running:
            capture.stop()
    except Exception as exc:
        print("Capture stop warning:", exc)

    capture_running = False
    capture = None

    return {"message": "Packet capture stopped."}


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    if not DEMO_MODE:
            refresh_local_ips()

            worker = threading.Thread(
                target=history_worker,
                daemon=True,
                name="network-history-worker"
            )
            worker.start()

    yield

    stop_capture()


app = FastAPI(
    title="NETWORK WATCH",
    version="3.0.0",
    description="Local network monitoring and security analytics",
    lifespan=lifespan
)

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static"
)


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "application": "NETWORK WATCH",
        "version": "3.0.0",
        "database": DB_PATH.exists()
    }


@app.get("/api/status")
def status():
    with STATE_LOCK:
        current = dict(stats)

    return {
        **current,
        "capture_running": capture_running,
        "capture_interface": capture_interface,
        "capture_started_at": capture_started_at,
        "capture_error": capture_error,
        "local_ips": sorted(local_ips)
    }


@app.get("/api/capture/interfaces")
def capture_interfaces():
    try:
        conf.use_pcap = True

        available = get_if_list()

        try:
            default_device = resolve_capture_interface()
        except Exception:
            default_device = None

        ordered = (
            [default_device] +
            [device for device in available if device != default_device]
            if default_device else available
        )

        return {
            "interfaces": ordered,
            "default_interface": default_device
        }

    except Exception as exc:
        return {
            "interfaces": [],
            "error": str(exc)
        }


@app.post("/api/capture/start")
def api_start_capture(request: CaptureRequest):
    return start_capture(request.interface)


@app.post("/api/capture/stop")
def api_stop_capture():
    return stop_capture()


@app.get("/api/connections")
def connections():
    return {"connections": get_connections()}


@app.get("/api/interfaces")
def interfaces():
    return {"interfaces": get_interfaces()}


@app.get("/api/alerts")
def alerts(limit: int = Query(100, ge=1, le=1000)):
    with DB_LOCK:
        con = db_connection()
        rows = con.execute("""
            SELECT * FROM alerts
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        con.close()

    return {"alerts": [dict(row) for row in rows]}


@app.get("/api/events")
def events(
    limit: int = Query(150, ge=1, le=1000),
    search: str = "",
    protocol: str = "ALL"
):
    sql = "SELECT * FROM packet_events WHERE 1=1"
    args = []

    if protocol != "ALL":
        sql += " AND protocol = ?"
        args.append(protocol.upper())

    if search:
        term = f"%{search}%"
        sql += """
            AND (
                src_ip LIKE ? OR dst_ip LIKE ?
                OR dns_query LIKE ? OR CAST(src_port AS TEXT) LIKE ?
                OR CAST(dst_port AS TEXT) LIKE ?
            )
        """
        args.extend([term] * 5)

    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)

    with DB_LOCK:
        con = db_connection()
        rows = con.execute(sql, args).fetchall()
        con.close()

    return {"events": [dict(row) for row in rows]}


@app.get("/api/analytics")
def analytics():
    with DB_LOCK:
        con = db_connection()

        protocols = con.execute("""
            SELECT protocol, COUNT(*) AS count
            FROM packet_events
            GROUP BY protocol
            ORDER BY count DESC
        """).fetchall()

        timeline = con.execute("""
            SELECT substr(timestamp, 1, 16) AS minute,
                   COUNT(*) AS packets,
                   SUM(packet_size) AS bytes
            FROM packet_events
            WHERE timestamp >= datetime('now', '-1 hour')
            GROUP BY minute
            ORDER BY minute
        """).fetchall()

        totals = con.execute("""
            SELECT COUNT(*) AS events,
                   COALESCE(SUM(packet_size), 0) AS bytes
            FROM packet_events
        """).fetchone()

        con.close()

    return {
        "protocols": [dict(row) for row in protocols],
        "timeline": [dict(row) for row in timeline],
        "totals": dict(totals)
    }


@app.get("/api/history")
def history():
    with DB_LOCK:
        con = db_connection()

        interfaces = con.execute("""
            SELECT * FROM interface_history
            ORDER BY id DESC LIMIT 100
        """).fetchall()

        connections = con.execute("""
            SELECT * FROM connection_history
            ORDER BY id DESC LIMIT 100
        """).fetchall()

        con.close()

    return {
        "interfaces": [dict(row) for row in interfaces],
        "connections": [dict(row) for row in connections]
    }


def export_csv(table, columns, filename):
    with DB_LOCK:
        con = db_connection()
        rows = con.execute(
            f"SELECT {', '.join(columns)} FROM {table} ORDER BY id DESC LIMIT 10000"
        ).fetchall()
        con.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)

    for row in rows:
        writer.writerow([row[column] for column in columns])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/export/events.csv")
def export_events():
    return export_csv(
        "packet_events",
        [
            "id", "timestamp", "protocol", "src_ip", "dst_ip",
            "src_port", "dst_port", "packet_size",
            "direction", "dns_query", "interface"
        ],
        "network_watch_events.csv"
    )


@app.get("/api/export/alerts.csv")
def export_alerts():
    return export_csv(
        "alerts",
        [
            "id", "timestamp", "severity", "category",
            "title", "description", "evidence"
        ],
        "network_watch_alerts.csv"
    )

# PUBLIC DEMO MODE MIDDLEWARE
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.deployment_config import DEMO_MODE, FRONTEND_ORIGIN
    from backend.demo_mode import build_demo_response
except ModuleNotFoundError:
    from deployment_config import DEMO_MODE, FRONTEND_ORIGIN
    from demo_mode import build_demo_response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)

@app.middleware("http")
async def public_demo_mode_middleware(request, call_next):
    if DEMO_MODE and request.url.path.startswith("/api/"):
        try:
            response = build_demo_response(
                request.url.path,
                request.query_params
            )
            if response is not None:
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Network-Watch-Mode"] = "public-demo"
                return response
        except Exception:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"error": "Demo response failed"},
                status_code=500
            )

    return await call_next(request)

