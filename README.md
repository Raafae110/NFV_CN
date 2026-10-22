# NFV Control Center — Final-Year Project Prototype

## Features
- Hands-on Network Traffic Lab: enter source IP, destination port, and payload; the firewall policy decides whether to block or forward.
- Allowed requests are forwarded as real HTTP requests through the load-balancer container to a backend; blocked requests never reach the backend.
- Modern Flask dashboard with responsive layout.
- Separate Docker containers for dashboard, virtual firewall service, virtual router service, load balancer service, and two demo backends.
- Health checks shown in the dashboard.
- Firewall rule CRUD and access-decision test. Default policy is BLOCK.
- Router route table CRUD and exact-destination lookup simulation.
- Real HTTP POST requests forwarded by the load-balancer container to backend-a/backend-b.
- Health-aware round-robin selection; unhealthy backends are skipped automatically (self-healing failover).
- Backend request counters and measured latency displayed in the dashboard.
- Traffic batch generator and transparent latency/error threshold anomaly alerts, including a controlled delay test.
- Event log and request counters.

## Important scope and safety notes
This is an educational NFV management prototype. The load-balancer performs real HTTP forwarding between Docker containers and skips unhealthy backends. The firewall currently evaluates simulated source-IP/port policy decisions in the dashboard; it does not intercept host packets. The router is a route-table lookup simulation and does not change OS routing or perform kernel-level packet forwarding. Anomaly detection uses explicit latency/error thresholds and a controlled delay scenario; it is not a trained ML model. Explain these boundaries in your presentation.

## Requirements
- Windows 10/11
- Docker Desktop running with Linux containers / WSL 2 backend
- VS Code (recommended)

Python on the Windows host is not required to run the app because Python runs inside Docker.

## Run
Open PowerShell in this folder and run:

```powershell
docker compose config
docker compose up --build
```

Wait for Flask to print a message similar to `Running on http://127.0.0.1:5000`, then open:

http://localhost:5000

Keep this terminal open while running. To run detached instead:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail=80 dashboard
```

Stop containers:

```powershell
docker compose down
```

## If the dashboard does not open
1. Confirm all project files are saved.
2. Run `docker compose ps` and check that `dashboard`, `firewall`, `router`, and `loadbalancer` are running.
3. Run `docker compose logs --tail=100 dashboard`.
4. If port 5000 is already in use, change the compose mapping to `"5001:5000"` and browse to http://localhost:5001.
5. If Docker Compose reports a missing file or an empty Dockerfile, confirm filenames are exactly `Dockerfile`, `docker-compose.yml`, and `requirements.txt` (no `.txt` suffix on Dockerfile).

## Useful demo sequence
1. Open the dashboard and point out service health cards.
2. Test the default firewall rule: source `10.0.0.10`, port `80` → ALLOW.
3. Test an unmatched source/port → BLOCK (default policy).
4. Add a firewall rule and test it.
5. Look up route `10.10.0.0/16` → next hop `192.168.1.1`.
6. Send several load-balancer requests and show real responses from backend-a/backend-b.
7. Click “Generate 10 real HTTP requests” and show successful counts and latency.
8. Click “Run controlled anomaly test” and explain the injected 350 ms delay and threshold alert.
9. Disable backend A and send requests; the load balancer should skip it and use backend B if healthy.
10. To demonstrate real failure recovery, stop backend A with `docker compose stop backend-a`, send requests, then restore it with `docker compose start backend-a`.

## Network Traffic Lab input/output
1. Open `/networklab`.
2. Allowed example: source `10.0.0.10`, port `80`; expected output is ALLOW plus backend name, response payload, request ID, and latency.
3. Blocked example: click “Try blocked example” (source `10.0.0.99`, port `8080`); expected output is BLOCK and no backend response.
4. Add a matching ALLOW rule on the Virtual Firewall page, then repeat with that source/port to see a forwarded backend response.

Note: the firewall gate is enforced for requests sent through this lab API. It does not filter arbitrary host or container packets. The router remains a route-table lookup demo; this is not a production router/firewall.

## Architecture
Browser → Flask Dashboard/API → firewall and router management simulations
Flask Dashboard/API → load-balancer container `/forward` → health-checked backend-a/backend-b `/process` endpoints
Backend health checks and response latency → dashboard status, metrics, and event log

The firewall policy and router table remain management-plane simulations rather than Linux kernel packet filtering/routing. The HTTP load balancer does perform real forwarding inside the Docker network.

## Separate dashboard pages
The dashboard is divided into separate pages while preserving the existing API endpoints:
- Network Traffic Lab: http://localhost:5000/networklab
- Overview: http://localhost:5000/
- Virtual Firewall: http://localhost:5000/firewall
- Virtual Router: http://localhost:5000/router
- Load Balancer: http://localhost:5000/loadbalancer
- Traffic & Anomaly Monitoring: http://localhost:5000/monitoring
- System Event Log: http://localhost:5000/events

Rebuild after extracting this edition with `docker compose up --build -d`.
