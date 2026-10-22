from flask import Flask, jsonify, render_template, request
from threading import Lock
from datetime import datetime, timezone
import os
import requests
import random
import time

app = Flask(__name__)
lock = Lock()
STARTED_AT = time.time()

SERVICE_URLS = {
    "firewall": os.getenv("FIREWALL_URL", "http://firewall:8001"),
    "router": os.getenv("ROUTER_URL", "http://router:8002"),
    "loadbalancer": os.getenv("LOADBALANCER_URL", "http://loadbalancer:8003"),
}

# Demo telemetry store. In production, use a database and real network telemetry.
telemetry = {
    "requests_total": 0,
    "allowed": 0,
    "blocked": 0,
    "recent_samples": [],
    "latency_samples": [],
    "anomalies": 0,
    "events": [],
}

firewall_rules = [
    {"id": 1, "source": "10.0.0.10", "destination_port": 80, "action": "ALLOW"},
    {"id": 2, "source": "10.0.0.20", "destination_port": 22, "action": "BLOCK"},
]
next_rule_id = 3

router_rules = [
    {"id": 1, "destination": "10.10.0.0/16", "next_hop": "192.168.1.1", "interface": "eth0"},
    {"id": 2, "destination": "172.16.0.0/16", "next_hop": "192.168.1.2", "interface": "eth1"},
]
next_route_id = 3

backends = [
    {"id": 1, "name": "backend-a", "url": os.getenv("BACKEND_A_URL", "http://backend-a:9001"), "enabled": True, "requests": 0, "healthy": None, "last_latency_ms": None},
    {"id": 2, "name": "backend-b", "url": os.getenv("BACKEND_B_URL", "http://backend-b:9002"), "enabled": True, "requests": 0, "healthy": None, "last_latency_ms": None},
]
lb_index = 0

def add_event(message, kind="info"):
    telemetry["events"].insert(0, {
        "time": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
        "message": message,
        "kind": kind
    })
    del telemetry["events"][30:]

def service_health(name):
    url = SERVICE_URLS[name]
    try:
        r = requests.get(url + "/health", timeout=1.5)
        return {"name": name, "status": "UP" if r.ok else "DOWN", "detail": r.json().get("service", name)}
    except requests.RequestException:
        return {"name": name, "status": "DOWN", "detail": "Service unavailable"}

@app.get("/")
def dashboard():
    return render_template("index.html")

@app.get("/networklab")
def networklab_page():
    return render_template("networklab.html")

@app.get("/firewall")
def firewall_page():
    return render_template("firewall.html")

@app.get("/router")
def router_page():
    return render_template("router.html")

@app.get("/loadbalancer")
def loadbalancer_page():
    return render_template("loadbalancer.html")

@app.get("/monitoring")
def monitoring_page():
    return render_template("monitoring.html")

@app.get("/events")
def events_page():
    return render_template("events.html")

@app.get("/api/overview")
def overview():
    with lock:
        sample_count = len(telemetry["recent_samples"])
        avg_rate = round(sum(telemetry["recent_samples"]) / sample_count, 1) if sample_count else 0
        services = [service_health(name) for name in SERVICE_URLS]
        return jsonify({
            "services": services,
            "requests_total": telemetry["requests_total"],
            "allowed": telemetry["allowed"],
            "blocked": telemetry["blocked"],
            "uptime_seconds": int(time.time() - STARTED_AT),
            "average_requests_per_minute": avg_rate,
            "anomalies": telemetry["anomalies"],
            "events": telemetry["events"][:10],
        })

@app.get("/api/firewall/rules")
def get_firewall_rules():
    with lock:
        return jsonify(firewall_rules)

@app.post("/api/firewall/rules")
def add_firewall_rule():
    global next_rule_id
    data = request.get_json(silent=True) or {}
    source = str(data.get("source", "")).strip()
    action = str(data.get("action", "")).upper()
    try:
        port = int(data.get("destination_port"))
    except (TypeError, ValueError):
        return jsonify({"error": "Destination port must be a number from 1 to 65535."}), 400
    if not source or action not in ("ALLOW", "BLOCK") or not 1 <= port <= 65535:
        return jsonify({"error": "Provide source, port 1–65535, and ALLOW or BLOCK."}), 400
    with lock:
        rule = {"id": next_rule_id, "source": source, "destination_port": port, "action": action}
        next_rule_id += 1
        firewall_rules.append(rule)
        add_event(f"Firewall rule added: {action} {source}:{port}", "success")
        return jsonify(rule), 201

@app.delete("/api/firewall/rules/<int:rule_id>")
def delete_firewall_rule(rule_id):
    with lock:
        before = len(firewall_rules)
        firewall_rules[:] = [r for r in firewall_rules if r["id"] != rule_id]
        if len(firewall_rules) == before:
            return jsonify({"error": "Rule not found"}), 404
        add_event(f"Firewall rule #{rule_id} deleted", "warning")
        return jsonify({"message": "Rule deleted"})

@app.post("/api/firewall/test")
def test_firewall():
    data = request.get_json(silent=True) or {}
    source = str(data.get("source", "")).strip()
    try:
        port = int(data.get("destination_port"))
    except (TypeError, ValueError):
        return jsonify({"error": "Port must be a number."}), 400

    # First matching rule wins; default policy is BLOCK.
    matched = None
    with lock:
        for rule in firewall_rules:
            if rule["source"] == source and rule["destination_port"] == port:
                matched = rule
                break
        action = matched["action"] if matched else "BLOCK"
        telemetry["requests_total"] += 1
        if action == "ALLOW":
            telemetry["allowed"] += 1
        else:
            telemetry["blocked"] += 1
        add_event(f"Firewall test {source}:{port} → {action}", "success" if action == "ALLOW" else "warning")
    return jsonify({"source": source, "destination_port": port, "decision": action, "matched_rule": matched, "default_policy": "BLOCK"})

@app.get("/api/router/routes")
def get_routes():
    with lock:
        return jsonify(router_rules)

@app.post("/api/router/routes")
def add_route():
    global next_route_id
    data = request.get_json(silent=True) or {}
    destination = str(data.get("destination", "")).strip()
    next_hop = str(data.get("next_hop", "")).strip()
    interface = str(data.get("interface", "")).strip()
    if not destination or not next_hop or not interface:
        return jsonify({"error": "Destination, next hop, and interface are required."}), 400
    with lock:
        route = {"id": next_route_id, "destination": destination, "next_hop": next_hop, "interface": interface}
        next_route_id += 1
        router_rules.append(route)
        add_event(f"Router route added for {destination}", "success")
        return jsonify(route), 201

@app.delete("/api/router/routes/<int:route_id>")
def delete_route(route_id):
    with lock:
        before = len(router_rules)
        router_rules[:] = [r for r in router_rules if r["id"] != route_id]
        if len(router_rules) == before:
            return jsonify({"error": "Route not found"}), 404
        add_event(f"Router route #{route_id} deleted", "warning")
        return jsonify({"message": "Route deleted"})

@app.post("/api/router/lookup")
def route_lookup():
    data = request.get_json(silent=True) or {}
    destination = str(data.get("destination", "")).strip()
    if not destination:
        return jsonify({"error": "Enter a destination network or IP."}), 400
    # Demonstration lookup: exact destination match; this is not a production CIDR router.
    with lock:
        match = next((r for r in router_rules if r["destination"] == destination), None)
        add_event(f"Route lookup for {destination}: {'MATCH' if match else 'NO ROUTE'}", "info")
    return jsonify({"destination": destination, "route": match, "decision": "FORWARD" if match else "NO ROUTE"})

@app.get("/api/loadbalancer/backends")
def get_backends():
    # Report configured state plus live health from the real backend containers.
    output = []
    for backend in backends:
        healthy = False
        try:
            response = requests.get(backend["url"] + "/health", timeout=0.8)
            healthy = response.ok
        except requests.RequestException:
            healthy = False
        backend["healthy"] = healthy
        output.append(dict(backend))
    return jsonify(output)

@app.post("/api/loadbalancer/backends/<int:backend_id>/toggle")
def toggle_backend(backend_id):
    with lock:
        backend = next((b for b in backends if b["id"] == backend_id), None)
        if not backend:
            return jsonify({"error": "Backend not found"}), 404
        backend["enabled"] = not backend["enabled"]
        add_event(f"{backend['name']} {'enabled' if backend['enabled'] else 'disabled'}", "info")
        return jsonify(backend)

@app.post("/api/loadbalancer/test")
def test_loadbalancer():
    # This sends a real HTTP request through the dedicated load-balancer container
    # and forwards it to backend-a or backend-b.
    enabled = [{"name": b["name"]} for b in backends if b["enabled"]]
    try:
        response = requests.post(SERVICE_URLS["loadbalancer"] + "/forward", json={
            "request_id": f"nfv-{int(time.time() * 1000)}",
            "payload": "Live dashboard test request",
            "enabled_backends": enabled,
        }, timeout=4)
        data = response.json()
        if not response.ok:
            add_event(f"Load balancer request failed: {data.get('error', 'unknown error')}", "danger")
            return jsonify(data), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": f"Load balancer unavailable: {exc.__class__.__name__}"}), 502

    selected = next((b for b in backends if b["name"] == data["selected_backend"]), None)
    if selected:
        selected["requests"] += 1
        selected["last_latency_ms"] = data.get("latency_ms")
    latency = float(data.get("latency_ms", 0))
    with lock:
        telemetry["requests_total"] += 1
        telemetry["allowed"] += 1
        telemetry["latency_samples"].append(latency)
        telemetry["latency_samples"] = telemetry["latency_samples"][-30:]
        add_event(f"Real HTTP request forwarded to {data['selected_backend']} in {latency} ms", "success")
    data["backend_request_count"] = selected["requests"] if selected else 0
    data["healthy_backends"] = sum(1 for b in backends if b["enabled"] and b.get("healthy") is not False)
    return jsonify(data)

@app.post("/api/traffic/simulate")
def simulate_traffic():
    data = request.get_json(silent=True) or {}
    try:
        count = max(1, min(int(data.get("count", 10)), 50))
    except (TypeError, ValueError):
        return jsonify({"error": "count must be an integer from 1 to 50"}), 400
    force_spike = bool(data.get("simulate_anomaly", False))
    latencies, successes, failures, selected_names = [], 0, 0, []
    enabled = [{"name": b["name"]} for b in backends if b["enabled"]]
    if not enabled:
        return jsonify({"error": "No enabled backends. Enable at least one backend."}), 503

    for i in range(count):
        # Explicitly controlled delay makes the anomaly demo reproducible; it is not host traffic.
        delay = 350 if force_spike and i == count - 1 else 0
        started = time.perf_counter()
        try:
            response = requests.post(SERVICE_URLS["loadbalancer"] + "/forward", json={
                "request_id": f"batch-{int(time.time() * 1000)}-{i}",
                "payload": "NFV generated HTTP test traffic",
                "enabled_backends": enabled,
                "simulate_delay_ms": delay,
            }, timeout=4)
            if response.ok:
                result_data = response.json()
                successes += 1
                selected_names.append(result_data.get("selected_backend", "unknown"))
                latency = float(result_data.get("latency_ms", (time.perf_counter() - started) * 1000))
                latencies.append(latency)
                backend = next((b for b in backends if b["name"] == result_data.get("selected_backend")), None)
                if backend:
                    backend["requests"] += 1
                    backend["last_latency_ms"] = latency
            else:
                failures += 1
        except requests.RequestException:
            failures += 1

    if not latencies and failures:
        with lock:
            telemetry["requests_total"] += count
            add_event(f"Traffic batch failed: {failures}/{count} requests unsuccessful", "danger")
        return jsonify({"error": "All generated requests failed. Check backend health and container logs.", "successes": successes, "failures": failures}), 502

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0
    # Transparent robust rule: flag an explicit delay test or a batch average above 250 ms.
    anomaly = force_spike or avg_latency > 250 or (count and failures / count >= 0.2)
    rate = round(count / max(sum(latencies) / 1000, 0.001) * 60, 1)
    with lock:
        telemetry["recent_samples"].append(rate)
        telemetry["recent_samples"] = telemetry["recent_samples"][-20:]
        telemetry["latency_samples"].extend(latencies)
        telemetry["latency_samples"] = telemetry["latency_samples"][-30:]
        telemetry["requests_total"] += count
        telemetry["allowed"] += successes
        telemetry["blocked"] += failures
        if anomaly:
            telemetry["anomalies"] += 1
            add_event(f"Anomaly alert: average latency {avg_latency} ms; {failures}/{count} failures; controlled test={force_spike}", "danger")
        else:
            add_event(f"Traffic batch completed: {successes}/{count} HTTP requests; average latency {avg_latency} ms", "success")
    return jsonify({"simulated_requests": count, "successful_requests": successes, "failed_requests": failures,
                    "requests_per_minute": rate, "average_latency_ms": avg_latency, "anomaly": anomaly,
                    "mode": "real HTTP requests through the Docker load-balancer to backend containers",
                    "selected_backends": selected_names,
                    "message": "Potential traffic anomaly detected" if anomaly else "Traffic completed within configured thresholds"})

@app.post("/api/network/send")
def send_network_request():
    """End-to-end educational flow: firewall policy check, then real HTTP forwarding."""
    data = request.get_json(silent=True) or {}
    source = str(data.get("source", "10.0.0.10")).strip()
    payload = str(data.get("payload", "Hello from the NFV network lab"))[:500]
    try:
        port = int(data.get("destination_port", 80))
    except (TypeError, ValueError):
        return jsonify({"error": "Destination port must be an integer."}), 400
    if not source or not 1 <= port <= 65535:
        return jsonify({"error": "Enter a source and a port between 1 and 65535."}), 400

    with lock:
        matched = next((r for r in firewall_rules if r["source"] == source and r["destination_port"] == port), None)
        decision = matched["action"] if matched else "BLOCK"  # default-deny policy
        telemetry["requests_total"] += 1
        if decision != "ALLOW":
            telemetry["blocked"] += 1
            add_event(f"Network lab blocked {source} → port {port} (default-deny firewall)", "warning")
            return jsonify({"decision": "BLOCK", "source": source, "destination_port": port,
                            "matched_rule": matched, "stage": "firewall", "message": "Firewall blocked this request; it was not sent to a backend."})

    enabled = [{"name": b["name"]} for b in backends if b["enabled"]]
    if not enabled:
        with lock:
            telemetry["blocked"] += 1
            add_event("Network lab request failed: no enabled backend", "danger")
        return jsonify({"decision": "ALLOW", "error": "Firewall allowed traffic, but no backend is enabled."}), 503
    try:
        response = requests.post(SERVICE_URLS["loadbalancer"] + "/forward", json={
            "request_id": f"lab-{int(time.time() * 1000)}", "payload": payload,
            "enabled_backends": enabled,
        }, timeout=4)
        result = response.json()
    except requests.RequestException as exc:
        with lock:
            telemetry["blocked"] += 1
            add_event("Network lab allowed by firewall but forwarding failed", "danger")
        return jsonify({"decision": "ALLOW", "error": f"Load balancer unavailable: {exc.__class__.__name__}"}), 502

    if not response.ok:
        with lock:
            telemetry["blocked"] += 1
            add_event("Network lab request failed at load balancer", "danger")
        return jsonify({"decision": "ALLOW", "stage": "loadbalancer", **result}), response.status_code

    chosen = next((b for b in backends if b["name"] == result.get("selected_backend")), None)
    if chosen:
        chosen["requests"] += 1
        chosen["last_latency_ms"] = result.get("latency_ms")
    with lock:
        telemetry["allowed"] += 1
        telemetry["latency_samples"].append(float(result.get("latency_ms", 0)))
        telemetry["latency_samples"] = telemetry["latency_samples"][-30:]
        add_event(f"Network lab allowed {source}:{port}; forwarded to {result.get('selected_backend')}", "success")
    return jsonify({"decision": "ALLOW", "source": source, "destination_port": port,
                    "matched_rule": matched, "stage": "backend", "forwarding": result,
                    "message": "Firewall allowed the request and the load balancer forwarded it to a backend."})

@app.get("/api/events")
def get_events():
    with lock:
        return jsonify(telemetry["events"][:20])

if __name__ == "__main__":
    # Critical: keep the Flask process in the foreground inside the container.
    app.run(host="0.0.0.0", port=5000, debug=False)
