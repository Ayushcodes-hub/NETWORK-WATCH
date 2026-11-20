import os

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:5500"
).rstrip("/")
