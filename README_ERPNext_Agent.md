# Standalone ERPNext Agent

A lightweight Python service that runs in its own Docker container,
independently of the ERPNext/Frappe scheduler. The initial version sends
system telemetry to the configured Firebase Cloud Function at a regular
interval.

> **Current scope:** telemetry only. This version does **not** run
> ERPNext backup code or trigger backups.

## 1. What it currently does

-   Runs as a separate Docker container named `erpnext-agent`.
-   Sends an HTTPS `POST` request to the Firebase telemetry endpoint.
-   Includes the configured license key, timestamp, CPU usage, RAM
    usage, disk usage, and agent identifier.
-   Repeats according to `AGENT_INTERVAL` (60 seconds by default).
-   Uses Docker's `restart: unless-stopped` policy so Docker can restart
    the container after a failure or host restart, provided Docker
    itself is running.

### Important metric limitation

The current `agent.py` uses `psutil` from **inside the agent
container**. Its CPU, RAM, and disk values describe the agent
container's view of its environment; they should not yet be treated as
reliable metrics for the physical host or the separate ERPNext
containers. Monitoring the real ERPNext environment is a future step.

## 2. Expected folder structure

This directory is expected to be:

`$HOME/Desktop/ERP/ERP Base/frappe_docker/erpnext-agent`

Files:

``` text
erpnext-agent/
├── Dockerfile
├── requirements.txt
├── agent.py
├── .env.agent
├── docker-compose.agent.yml
└── README.md
```

## 3. Configuration

The `.env.agent` file should contain:

``` dotenv
ERP_LICENSE_KEY=YOUR_EXISTING_LICENSE_KEY
AGENT_INTERVAL=60
```

-   Replace the placeholder with your existing license key on your own
    machine.
-   `AGENT_INTERVAL` is in seconds.
-   Keep `.env.agent` private. Do not commit it to Git, paste it into
    chats, or include it in screenshots.

Recommended: add `.env.agent` to `.gitignore` if this folder is tracked
by Git.

## 4. Build and start

Open Terminal on your Mac and run:

``` bash
cd "$HOME/Desktop/ERP/ERP Base/frappe_docker/erpnext-agent"
docker compose -f docker-compose.agent.yml up -d --build
```

This builds the image if needed and starts the agent in the background.
It does not rebuild or restart the existing ERPNext services.

## 5. View logs and verify telemetry

Follow logs live:

``` bash
docker logs -f erpnext-agent
```

Show the latest 30 log lines:

``` bash
docker logs --tail=30 erpnext-agent
```

Look for a startup message and telemetry acceptance messages, such as an
HTTP success response. A successful HTTP response means the endpoint
accepted the request; confirm that the expected telemetry fields and
`lastHeartbeat` are updating in Firestore/the portal as an additional
check.

## 6. Common management commands

Check whether the container is running:

``` bash
docker ps --filter name=erpnext-agent
```

Stop the agent:

``` bash
docker stop erpnext-agent
```

Start the existing container again:

``` bash
docker start erpnext-agent
```

Restart it:

``` bash
docker restart erpnext-agent
```

Stop and remove the container (does not remove the source files):

``` bash
docker compose -f docker-compose.agent.yml down
```

Rebuild after changing `agent.py`, `Dockerfile`, or `requirements.txt`:

``` bash
docker compose -f docker-compose.agent.yml up -d --build
```

## 7. Troubleshooting

### Container logs say the license key is missing

Check that `.env.agent` exists in this directory and contains a
non-empty `ERP_LICENSE_KEY` value. After changing environment values,
recreate the container:

``` bash
docker compose -f docker-compose.agent.yml up -d --build --force-recreate
```

### HTTP errors or request failures

Inspect the logs:

``` bash
docker logs --tail=100 erpnext-agent
```

Check the endpoint response and verify that the license is valid in the
portal/Firestore configuration. Do not post your license key in support
messages.

### Container does not exist

Confirm you are in the `erpnext-agent` directory and use the same
Compose file:

``` bash
cd "$HOME/Desktop/ERP/ERP Base/frappe_docker/erpnext-agent"
docker compose -f docker-compose.agent.yml ps
```

## 8. Does this run the ERPNext backup code?

**No. The current agent does not run your backup code.** It only sends
telemetry. It does not import or call
`server.backup.trigger_backup_process`, execute `bench backup`, or send
backup commands to the ERPNext container.

The old backup function or Frappe scheduler hooks are separate from this
agent. To run backups through this container, we must deliberately
implement and test a secure integration with the actual ERPNext site.
The agent currently has no configured access to the ERPNext container or
its backup directories, and should not be assumed to back up any data.

## 9. Planned next steps

1.  Collect metrics for the actual ERPNext containers/host, not only the
    agent container.
2.  Add a secure backup trigger and status reporting workflow.
3.  Add ERPNext site/worker/scheduler health checks.
4.  Add authenticated, authorized commands from the SaaS portal.

Keep the first version simple and test each capability before adding the
next one.
