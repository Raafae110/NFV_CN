# NFV Advanced Upgrade — Step-by-step (Windows + VS Code)

This upgrade preserves the existing ports and dashboard routes. It adds actual HTTP forwarding from the load-balancer container to the two backend containers, health-aware failover, request latency, batch traffic generation, and a controlled anomaly test.

## 1. Back up your current project

Before replacing files, duplicate your current folder in File Explorer. Keep the copy untouched so you can roll back.

## 2. Extract and open the upgraded project

1. Extract `NFV-Final-Year-Project-ADVANCED.zip` to a new folder.
2. Open that extracted folder in VS Code (the folder containing `docker-compose.yml`).
3. Confirm Docker Desktop is running with Linux containers enabled.

## 3. Rebuild the containers

In the VS Code PowerShell terminal, run:

```powershell
docker compose config
docker compose down
docker compose up --build -d
docker compose ps
```

The project keeps these host ports: dashboard `5000`, firewall `8001`, router `8002`, load balancer `8003`. Backend ports `9001` and `9002` are internal to the Compose network.

Open `http://localhost:5000`.

## 4. Test real backend forwarding

Click **Send test request** in the Load balancer panel. The output should show which backend processed the request, the measured latency, and a response payload. Repeated requests should distribute across enabled, healthy backends.

The equivalent API is:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/loadbalancer/test -ContentType 'application/json' -Body '{}'
```

## 5. Generate real HTTP test traffic

Click **Generate 10 real HTTP requests**. The dashboard should show successful/failed requests, average latency, and the backends selected. This traffic travels through the load-balancer container to the backend containers; it is not arbitrary host traffic.

## 6. Demonstrate anomaly detection

Click **Run controlled anomaly test**. One request receives a controlled 350 ms delay inside the backend test service. The dashboard should flag the latency test. This is a transparent threshold-based demonstration, not a trained ML model.

## 7. Demonstrate self-healing failover

In the terminal, stop backend A:

```powershell
docker compose stop backend-a
```

Click **Send test request** or **Generate 10 real HTTP requests**. If backend B is healthy and enabled, the load balancer should skip backend A and forward to backend B. Restore backend A afterward:

```powershell
docker compose start backend-a
```

Refresh the dashboard and wait for the backend health indicator to update.

## 8. Keep the logs visible during your presentation

```powershell
docker compose logs -f loadbalancer backend-a backend-b
```

Stop following logs with `Ctrl+C`; that does not stop the containers.

## 9. Existing features retained

- Firewall rule creation, deletion, allow/block decision test, and default BLOCK policy.
- Router route creation/deletion and exact destination lookup.
- Existing dashboard URLs and API paths.
- Docker service names and published ports.

## Important technical scope

- Load balancer: real HTTP forwarding within the Docker network, health checks, and failover.
- Firewall: source-IP/port policy decision simulation in the dashboard; it does not intercept or block host network packets.
- Router: route-table lookup simulation; it does not modify OS/kernel routing.
- Anomaly detection: controlled latency/error threshold logic; it is not a trained machine-learning model.
- In-memory counters and rules reset when the dashboard container is recreated. A database/persistent event store can be a later extension.

## Troubleshooting

If the dashboard does not open:

```powershell
docker compose ps
docker compose logs --tail=100 dashboard loadbalancer backend-a backend-b
```

If code changes do not appear, rebuild with `docker compose up --build -d`. If a backend was stopped for the demo, restore it with `docker compose start backend-a` or `docker compose start backend-b`.


## Hands-on Network Traffic Lab
Open `http://localhost:5000/networklab`. Use source `10.0.0.10` and port `80` to allow a real HTTP request to a backend. Use “Try blocked example” to test default-deny behavior. Add an ALLOW rule in the firewall page to permit another source/port combination. The firewall gate applies to requests through `/api/network/send`; it is not kernel packet filtering.
