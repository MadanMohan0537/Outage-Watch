"""
Sample site used to intentionally generate outage logs for the local
outage-detection-and-diagnosis demo.

Routes:
  GET  /                context, always works
  GET  /health           health check endpoint the agent polls
  POST /crash/<kind>      intentionally break the app in a specific way

Crash kinds:
  db          - simulated database connection failure
  memory      - simulated out-of-memory / resource exhaustion
  timeout     - simulated hang / slow downstream dependency
  nullref     - simulated unhandled exception (None attribute access)
  disk        - simulated disk full / write failure

Every crash writes a structured entry to logs/app.log with a timestamp,
error type, and a fake stack trace, then also raises a real 500 so the
health check will observe the outage.
"""

import logging
import os
import random
import time
from datetime import datetime, timezone

from flask import Flask, jsonify

app = Flask(__name__)

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("sample_site")

# Global flag the health check reads. A crash flips this to "down" until
# a human (or the agent, in a future version) resets it via /recover.
STATE = {"status": "up", "last_incident": None}

FAKE_TRACES = {
    "db": (
        "ConnectionRefusedError: [Errno 61] Connection refused\n"
        "  File \"app.py\", line 142, in get_connection\n"
        "    conn = psycopg2.connect(DATABASE_URL)\n"
        "  File \"psycopg2/__init__.py\", line 122, in connect\n"
        "    raise OperationalError(...)\n"
        "psycopg2.OperationalError: could not connect to server: Connection refused\n"
        "\tIs the server running on host \"db\" and accepting TCP/IP connections on port 5432?"
    ),
    "memory": (
        "MemoryError: Unable to allocate array\n"
        "  File \"app.py\", line 88, in process_batch\n"
        "    buf = bytearray(BATCH_SIZE)\n"
        "MemoryError\n"
        "Process killed by OOM killer (exit code 137)"
    ),
    "timeout": (
        "requests.exceptions.ReadTimeout: HTTPConnectionPool(host='payments-api', port=443): "
        "Read timed out. (read timeout=5)\n"
        "  File \"app.py\", line 210, in call_payments_api\n"
        "    resp = requests.get(url, timeout=5)\n"
        "  File \"requests/api.py\", line 73, in get\n"
        "    return request('get', url, **kwargs)"
    ),
    "nullref": (
        "AttributeError: 'NoneType' object has no attribute 'items'\n"
        "  File \"app.py\", line 55, in build_response\n"
        "    for key, value in user_profile.items():\n"
        "AttributeError: 'NoneType' object has no attribute 'items'"
    ),
    "disk": (
        "OSError: [Errno 28] No space left on device\n"
        "  File \"app.py\", line 301, in write_upload\n"
        "    f.write(chunk)\n"
        "OSError: [Errno 28] No space left on device"
    ),
}

ERROR_TYPES = {
    "db": "DatabaseConnectionError",
    "memory": "OutOfMemoryError",
    "timeout": "UpstreamTimeoutError",
    "nullref": "UnhandledNullReferenceError",
    "disk": "DiskSpaceError",
}


@app.route("/")
def index():
    return jsonify({"message": "sample site is running", "status": STATE["status"]})


@app.route("/health")
def health():
    if STATE["status"] == "down":
        return jsonify({
            "status": "down",
            "last_incident": STATE["last_incident"],
        }), 503
    return jsonify({"status": "up"}), 200


@app.route("/crash/<kind>", methods=["POST", "GET"])
def crash(kind):
    if kind not in FAKE_TRACES:
        return jsonify({
            "error": f"unknown crash kind '{kind}'",
            "valid_kinds": list(FAKE_TRACES.keys()),
        }), 400

    incident_id = f"inc-{int(time.time())}-{random.randint(100, 999)}"
    timestamp = datetime.now(timezone.utc).isoformat()
    error_type = ERROR_TYPES[kind]
    trace = FAKE_TRACES[kind]

    entry = (
        f"---- OUTAGE START ----\n"
        f"incident_id: {incident_id}\n"
        f"timestamp: {timestamp}\n"
        f"level: ERROR\n"
        f"error_type: {error_type}\n"
        f"crash_kind: {kind}\n"
        f"traceback:\n{trace}\n"
        f"---- OUTAGE END ----\n"
    )
    logger.error(entry)

    STATE["status"] = "down"
    STATE["last_incident"] = {
        "incident_id": incident_id,
        "timestamp": timestamp,
        "error_type": error_type,
        "crash_kind": kind,
    }

    return jsonify({
        "message": f"site crashed intentionally ({kind})",
        "incident_id": incident_id,
    }), 500


@app.route("/recover", methods=["POST"])
def recover():
    """Manually (or agent-) reset the site back to healthy after a fix."""
    STATE["status"] = "up"
    logger.info(
        f"---- RECOVERY ----\ntimestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"note: site manually marked healthy again\n"
    )
    return jsonify({"status": "up"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
