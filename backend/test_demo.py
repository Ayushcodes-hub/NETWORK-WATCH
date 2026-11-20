import os
os.environ["DEMO_MODE"] = "true"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:5500"

from fastapi.testclient import TestClient
from backend.main import app

checks = [
    ("GET", "/api/health", None, 200),
    ("GET", "/api/status", None, 200),
    ("GET", "/api/alerts", None, 200),
    ("GET", "/api/events", None, 200),
    ("GET", "/api/analytics", None, 200),
    ("GET", "/api/connections", None, 200),
    ("GET", "/api/interfaces", None, 200),
    ("GET", "/api/history", None, 200),
    ("GET", "/api/export/events.csv", None, 200),
    ("GET", "/api/export/alerts.csv", None, 200),
    ("POST", "/api/capture/start", {}, 403),
]

with TestClient(app) as client:
    for method, path, payload, expected in checks:
        if method == "GET":
            response = client.get(path)
        else:
            response = client.post(path, json=payload)

        assert response.status_code == expected, (
            f"FAIL {path}: HTTP {response.status_code}; expected {expected}"
        )

        assert response.headers.get("X-Network-Watch-Mode") == "public-demo", (
            f"FAIL {path}: public demo header missing"
        )

        print(f"PASS {method} {path}")

    status = client.get("/api/status").json()
    assert status["demo_mode"] is True
    assert status["capture_running"] is False

print("\nALL 11 DEMO API CHECKS PASSED")
