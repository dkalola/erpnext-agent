import os
import time
import logging
from datetime import datetime, timezone

import psutil
import requests

URL = (
    "https://us-central1-erp-master-565f8."
    "cloudfunctions.net/updateTelemetry"
)

LICENSE_KEY = os.environ.get("ERP_LICENSE_KEY", "")
INTERVAL = int(os.environ.get("AGENT_INTERVAL", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

if not LICENSE_KEY:
    raise SystemExit("ERP_LICENSE_KEY environment variable is missing")

session = requests.Session()

logging.info("ERPNext agent started; interval=%s seconds", INTERVAL)

while True:
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        payload = {
            "licenseKey": LICENSE_KEY,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "status": "active",
                "cpuUsagePercent": psutil.cpu_percent(interval=1),
                "ramUsagePercent": memory.percent,
                "diskUsagePercent": disk.percent,
                "telemetryAgent": "standalone-erpnext-agent",
            },
        }

        response = session.post(URL, json=payload, timeout=15)

        if response.ok:
            logging.info(
                "Telemetry accepted: HTTP %s; response=%s",
                response.status_code,
                response.text,
            )
        else:
            logging.error(
                "Telemetry rejected: HTTP %s; response=%s",
                response.status_code,
                response.text[:500],
            )

    except Exception:
        logging.exception("Telemetry request failed")

    time.sleep(INTERVAL)