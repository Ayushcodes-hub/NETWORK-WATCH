import csv
import io
from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse, PlainTextResponse


def now_iso(minutes_ago=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def demo_alerts():
    items = [
        ("HIGH", "PORT_SCAN_PATTERN", "Possible port scanning activity",
         "A simulated device attempted connections across multiple ports.",
         "192.0.2.10 scanned 20 destination ports."),
        ("MEDIUM", "DNS_BURST", "Unusually high DNS activity",
         "A simulated device generated an unusually high volume of DNS requests.",
         "Simulated DNS request burst."),
        ("INFO", "NEW_EXTERNAL_ENDPOINT", "New external endpoint observed",
         "A new external destination appeared in the simulated traffic.",
         "Destination: 198.51.100.25"),
        ("HIGH", "SUSPICIOUS_PORT", "Suspicious destination port",
         "A simulated connection used a port commonly associated with suspicious activity.",
         "Destination port: 4444"),
        ("INFO", "NETWORK_ACTIVITY", "Network activity detected",
         "The demo feed recorded a new network activity pattern.",
         "Synthetic demonstration event.")
    ]
    return [
        {
            "id": i + 1,
            "timestamp": now_iso(i * 7),
            "severity": item[0],
            "category": item[1],
            "title": item[2],
            "description": item[3],
            "evidence": item[4]
        }
        for i, item in enumerate(items)
    ]


def demo_events():
    records = [
        ("TCP", "192.0.2.10", "198.51.100.25", 51520, 443, 1420, "OUTBOUND", None),
        ("UDP", "192.0.2.10", "198.51.100.53", 53010, 53, 86, "OUTBOUND", "example.test"),
        ("TCP", "198.51.100.25", "192.0.2.10", 443, 51520, 1280, "INBOUND", None),
        ("DNS", "192.0.2.10", "198.51.100.53", 53011, 53, 92, "OUTBOUND", "demo.network.test"),
        ("ICMP", "198.51.100.1", "192.0.2.10", None, None, 64, "INBOUND", None),
        ("TCP", "192.0.2.10", "203.0.113.20", 51522, 4444, 512, "OUTBOUND", None),
        ("TLS", "192.0.2.10", "198.51.100.80", 51523, 443, 1180, "OUTBOUND", None),
        ("UDP", "192.0.2.10", "198.51.100.53", 53012, 53, 90, "OUTBOUND", "updates.example.test"),
        ("TCP", "192.0.2.20", "198.51.100.30", 51524, 80, 740, "OUTBOUND", None),
        ("TCP", "198.51.100.30", "192.0.2.20", 80, 51524, 980, "INBOUND", None)
    ]
    result = []
    for i, r in enumerate(records):
        result.append({
            "id": i + 1,
            "timestamp": now_iso(i * 2),
            "protocol": r[0],
            "src_ip": r[1],
            "dst_ip": r[2],
            "src_port": r[3],
            "dst_port": r[4],
            "packet_size": r[5],
            "direction": r[6],
            "dns_query": r[7],
            "interface": "DEMO-NETWORK"
        })
    return result


def demo_connections():
    return {"connections": [
        {"process": "Demo Browser", "pid": 1204, "protocol": "TCP",
         "local_ip": "192.0.2.10", "local_port": 51520,
         "remote_ip": "198.51.100.25", "remote_port": 443, "status": "ESTABLISHED"},
        {"process": "Demo DNS Client", "pid": 1208, "protocol": "UDP",
         "local_ip": "192.0.2.10", "local_port": 53010,
         "remote_ip": "198.51.100.53", "remote_port": 53, "status": "ESTABLISHED"},
        {"process": "Demo Update Service", "pid": 1212, "protocol": "TCP",
         "local_ip": "192.0.2.10", "local_port": 51522,
         "remote_ip": "203.0.113.20", "remote_port": 4444, "status": "ESTABLISHED"}
    ]}


def demo_interfaces():
    return {"interfaces": [
        {"name": "DEMO-NETWORK", "is_up": True, "ipv4": "192.0.2.10",
         "speed_mbps": 1000, "bytes_sent": 2677355, "bytes_recv": 4510181}
    ]}


def demo_analytics():
    return {
        "protocols": [
            {"protocol": "TCP", "count": 62},
            {"protocol": "UDP", "count": 24},
            {"protocol": "DNS", "count": 8},
            {"protocol": "TLS", "count": 5},
            {"protocol": "ICMP", "count": 1}
        ],
        "timeline": [
            {"minute": (datetime.now(timezone.utc) - timedelta(minutes=9-i)).strftime("%H:%M"),
             "count": [12, 18, 15, 24, 20, 31, 26, 34, 29, 38][i]}
            for i in range(10)
        ],
        "totals": {"count": 100, "bytes": 524288}
    }


def demo_status():
    return {
        "packets": 100,
        "bytes": 524288,
        "upload_bytes": 267735,
        "download_bytes": 256553,
        "tcp": 62,
        "udp": 24,
        "dns": 8,
        "tls": 5,
        "icmp": 1,
        "other": 0,
        "capture_running": False,
        "capture_interface": "PUBLIC DEMO FEED",
        "capture_started_at": None,
        "capture_error": None,
        "local_ips": ["192.0.2.10"],
        "demo_mode": True
    }


def build_demo_response(path, query):
    if path == "/api/health":
        return JSONResponse({
            "status": "online",
            "app": "NETWORK WATCH",
            "version": "3.0.0",
            "database": True,
            "demo_mode": True
        })

    if path == "/api/status":
        return JSONResponse(demo_status())

    if path == "/api/capture/interfaces":
        return JSONResponse({
            "interfaces": [{"name": "DEMO-NETWORK"}],
            "default_interface": "DEMO-NETWORK",
            "demo_mode": True
        })

    if path in ("/api/capture/start", "/api/capture/stop"):
        return JSONResponse({
            "success": False,
            "demo_mode": True,
            "message": "Live packet capture is disabled in the public demo. Run NETWORK WATCH locally for real capture."
        }, status_code=403)

    if path == "/api/connections":
        return JSONResponse(demo_connections())

    if path == "/api/interfaces":
        return JSONResponse(demo_interfaces())

    if path == "/api/alerts":
        limit = min(max(int(query.get("limit", 100)), 1), 500)
        return JSONResponse({"alerts": demo_alerts()[:limit]})

    if path == "/api/events":
        events = demo_events()
        protocol = query.get("protocol", "ALL").upper()
        search = query.get("search", "").lower()
        if protocol != "ALL":
            events = [e for e in events if e["protocol"] == protocol]
        if search:
            events = [e for e in events if search in str(e).lower()]
        limit = min(max(int(query.get("limit", 150)), 1), 500)
        return JSONResponse({"events": events[:limit]})

    if path == "/api/analytics":
        return JSONResponse(demo_analytics())

    if path == "/api/history":
        return JSONResponse({
            "interface_history": [],
            "connection_history": [],
            "demo_mode": True
        })

    if path == "/api/export/events.csv":
        output = io.StringIO()
        rows = demo_events()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return PlainTextResponse(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="network-events-demo.csv"'}
        )

    if path == "/api/export/alerts.csv":
        output = io.StringIO()
        rows = demo_alerts()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return PlainTextResponse(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="network-alerts-demo.csv"'}
        )

    return None
