import os
import time
import logging
import hashlib
import zipfile
import subprocess
from datetime import datetime, timezone

import psutil
import requests

TELEMETRY_URL = (
    "https://us-central1-erp-master-565f8."
    "cloudfunctions.net/updateTelemetry"
)
BACKUP_CHECK_URL = (
    "https://us-central1-erp-master-565f8."
    "cloudfunctions.net/checkAndResetBackup"
)
UPLOAD_URL = "https://us-central1-erp-master-565f8.cloudfunctions.net/uploadBackup"

LICENSE_KEY = os.environ.get("ERP_LICENSE_KEY", "")
INTERVAL = int(os.environ.get("AGENT_INTERVAL", "60"))
SITE_NAME = os.environ.get("ERP_SITE_NAME", "frontend")
BACKUP_DIR = os.environ.get("ERP_BACKUP_DIR", f"/sites/{SITE_NAME}/private/backups")
CONTAINER_NAME = os.environ.get("ERP_CONTAINER_NAME", "frappe_docker-backend-1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

if not LICENSE_KEY:
    raise SystemExit("ERP_LICENSE_KEY environment variable is missing")

session = requests.Session()

def get_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

logging.info("ERPNext agent started; interval=%s seconds", INTERVAL)

while True:
    try:
        # 1. Send Telemetry Metrics
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

        response = session.post(TELEMETRY_URL, json=payload, timeout=15)

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

        # 2. Check and Trigger Backup Process
        check_url = f"{BACKUP_CHECK_URL}?licenseKey={LICENSE_KEY}"
        backup_res = session.get(check_url, timeout=15)

        if backup_res.status_code == 200:
            backup_data = backup_res.json()
            if backup_data.get("trigger_backup"):
                logging.info("Backup requested by SaaS portal. Executing bench backup via Docker...")
                
                # Execute standard bench backup inside ERPNext container
                cmd = ["docker", "exec", CONTAINER_NAME, "bench", "--site", SITE_NAME, "backup"]
                subprocess.run(cmd, check=True, timeout=300)
                
                logging.info("Bench backup completed. Packaging and uploading...")

                if not os.path.exists(BACKUP_DIR):
                    raise FileNotFoundError(f"Backup directory not found at {BACKUP_DIR}")

                all_files = [
                    f for f in os.listdir(BACKUP_DIR) 
                    if os.path.isfile(os.path.join(BACKUP_DIR, f)) and not f.endswith('.zip')
                ]
                
                if not all_files:
                    raise RuntimeError("No backup files found in directory.")

                all_files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)), reverse=True)
                latest_file = all_files[0]
                timestamp_prefix = latest_file[:15]
                batch_files = [f for f in all_files if f.startswith(timestamp_prefix)]

                # Package into a single master zip file
                timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                master_zip_name = f"full_erp_backup_{timestamp_str}.zip"
                master_zip_path = os.path.join(BACKUP_DIR, master_zip_name)

                with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for fname in batch_files:
                        fpath = os.path.join(BACKUP_DIR, fname)
                        zipf.write(fpath, arcname=fname)

                # Calculate SHA-256 Hash
                file_hash = get_file_hash(master_zip_path)
                
                # Upload to Firebase Storage
                with open(master_zip_path, "rb") as f:
                    files_payload = {"file": (master_zip_name, f, "application/zip")}
                    data_payload = {"licenseKey": LICENSE_KEY, "fileHash": file_hash}
                    upload_res = session.post(UPLOAD_URL, data=data_payload, files=files_payload, timeout=300)
                
                if upload_res.status_code != 200:
                    logging.error("Firebase Upload Failed: HTTP %s; response=%s", upload_res.status_code, upload_res.text)
                else:
                    logging.info("Backup uploaded successfully: hash=%s", file_hash)

                # Clean up local master zip
                try:
                    os.remove(master_zip_path)
                except Exception:
                    pass

        else:
            logging.error("Failed to check backup status: HTTP %s", backup_res.status_code)

    except Exception:
        logging.exception("Agent loop execution failed")

    time.sleep(INTERVAL)