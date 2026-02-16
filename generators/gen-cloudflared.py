#!/usr/bin/env python3
"""Generate the Cloudflare Tunnel (cloudflared) Grafana dashboard JSON.

Usage:
  python3 gen-cloudflared.py            # Local deploy (hardcoded datasource UID)
  python3 gen-cloudflared.py --export   # Portable export for grafana.com / sharing
"""
import json, os, sys

EXPORT = "--export" in sys.argv

if EXPORT:
    DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}
else:
    DS = {"type": "prometheus", "uid": "prometheus"}

OPEN_ROWS = {"Tunnel Overview"}  # Rows to keep expanded; all others collapse

def row(id, title, y, desc=""):
    r = {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "id": id, "panels": [], "title": title, "type": "row"}
    if desc: r["description"] = desc
    return r

def collapse_rows(panels):
    """Nest child panels inside collapsed rows.

    Grafana only defers queries for panels inside a collapsed row's 'panels'
    array. Panels that are siblings of a non-collapsed row execute immediately.
    """
    result = []
    current_row = None
    children = []
    for p in panels:
        if p.get("type") == "row":
            # Flush previous row
            if current_row is not None:
                if current_row["title"] not in OPEN_ROWS:
                    current_row["collapsed"] = True
                    current_row["panels"] = children
                    result.append(current_row)
                else:
                    result.append(current_row)
                    result.extend(children)
            else:
                result.extend(children)
            current_row = p
            children = []
        else:
            children.append(p)
    # Flush last row
    if current_row is not None:
        if current_row["title"] not in OPEN_ROWS:
            current_row["collapsed"] = True
            current_row["panels"] = children
            result.append(current_row)
        else:
            result.append(current_row)
            result.extend(children)
    else:
        result.extend(children)
    return result

def stat_panel(id, title, expr, legend, x, y, w=6, unit="short", thresholds=None, decimals=None, desc="", mappings=None):
    th = thresholds or [{"color": "green", "value": None}]
    p = {
        "datasource": DS,
        "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": mappings or [], "thresholds": {"mode": "absolute", "steps": th}, "unit": unit}, "overrides": []},
        "gridPos": {"h": 4, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "textMode": "auto"},
        "title": title,
        "type": "stat",
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A"}]
    }
    if desc:
        p["description"] = desc
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    if unit == "percent":
        p["fieldConfig"]["defaults"]["max"] = 100
        p["fieldConfig"]["defaults"]["min"] = 0
    return p

def ts_panel(id, title, targets, x, y, w=12, h=8, unit="short", stack=False, overrides=None, fill=20, desc="", legend_calcs=None):
    calcs = legend_calcs if legend_calcs is not None else ["mean", "max"]
    return {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisBorderShow": False, "axisCenteredZero": False, "axisLabel": "", "axisPlacement": "auto",
                    "barAlignment": 0, "drawStyle": "line", "fillOpacity": fill, "gradientMode": "none",
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "lineInterpolation": "linear", "lineWidth": 1, "pointSize": 5,
                    "scaleDistribution": {"type": "linear"}, "showPoints": "auto", "spanNulls": False,
                    "stacking": {"group": "A", "mode": "normal" if stack else "none"},
                    "thresholdsStyle": {"mode": "off"}
                },
                "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                "unit": unit
            },
            "overrides": overrides or []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        **({"description": desc} if desc else {}),
        "options": {"legend": {"calcs": calcs, "displayMode": "table", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}},
        "title": title,
        "type": "timeseries",
        "targets": targets
    }

def bar_panel(id, title, targets, x, y, w=12, h=8, unit="short", stack=True, overrides=None, desc=""):
    p = ts_panel(id, title, targets, x, y, w, h, unit, stack, overrides, desc=desc)
    p["fieldConfig"]["defaults"]["custom"]["drawStyle"] = "bars"
    p["fieldConfig"]["defaults"]["custom"]["fillOpacity"] = 80
    p["fieldConfig"]["defaults"]["custom"]["showPoints"] = "never"
    return p

def gauge_panel(id, title, expr, legend, x, y, w=6, h=6, unit="percent", thresholds=None, decimals=None, desc="", min_val=0, max_val=100):
    th = thresholds or [{"color": "green", "value": None}, {"color": "yellow", "value": 60}, {"color": "red", "value": 85}]
    p = {
        "datasource": DS,
        "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": th}, "unit": unit, "min": min_val, "max": max_val}, "overrides": []},
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"minVizHeight": 75, "minVizWidth": 75, "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdLabels": False, "showThresholdMarkers": True, "sizing": "auto"},
        "title": title,
        "type": "gauge",
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A"}]
    }
    if desc:
        p["description"] = desc
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p

def table_panel(id, title, expr, legend, x, y, w=12, h=8, desc=""):
    p = {
        "datasource": DS,
        "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}}, "overrides": []},
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}, "sortBy": [{"desc": True, "displayName": "Value"}]},
        "title": title,
        "type": "table",
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A", "instant": True, "format": "table"}]
    }
    if desc:
        p["description"] = desc
    return p

def text_panel(id, content, x, y, w=24, h=4, title="", desc=""):
    p = {
        "datasource": DS,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False}, "content": content, "mode": "markdown"},
        "title": title,
        "type": "text",
    }
    if desc:
        p["description"] = desc
    return p

def t(expr, legend, ref="A"):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}

def color_override(name, color):
    return {"matcher": {"id": "byName", "options": name}, "properties": [{"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}]}

def regex_color(pattern, color):
    return {"matcher": {"id": "byRegexp", "options": pattern}, "properties": [{"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}]}

# Job selector with template variable
JOB = '{job=~"$job"}'

panels = []
y = 0
pid = 1

# ============================================================
# ROW: Tunnel Overview
# ============================================================
panels.append(row(pid, "Tunnel Overview", y)); pid += 1; y += 1

panels.append(stat_panel(pid, "Requests/sec",
    f"sum(rate(cloudflared_tunnel_total_requests{JOB}[$__rate_interval]))", "req/s", 0, y, w=4,
    unit="reqps", thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 100}],
    desc="Rate of HTTP requests proxied through the tunnel.")); pid += 1

panels.append(stat_panel(pid, "Error Rate %",
    f"sum(rate(cloudflared_tunnel_request_errors{JOB}[$__rate_interval])) / sum(rate(cloudflared_tunnel_total_requests{JOB}[$__rate_interval])) * 100",
    "err%", 4, y, w=4, unit="percent", decimals=2,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 5}],
    desc="Percentage of requests that resulted in an error proxying to origin.")); pid += 1

panels.append(stat_panel(pid, "HA Connections",
    f"sum(cloudflared_tunnel_ha_connections{JOB})", "conns", 8, y, w=4,
    thresholds=[{"color": "red", "value": None}, {"color": "yellow", "value": 2}, {"color": "green", "value": 4}],
    desc="Number of active high-availability QUIC connections to Cloudflare edge. Each cloudflared replica establishes 4 HA connections to different edge servers for redundancy.")); pid += 1

panels.append(stat_panel(pid, "Concurrent Requests",
    f"sum(cloudflared_tunnel_concurrent_requests_per_tunnel{JOB})", "concurrent", 12, y, w=4,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50}, {"color": "red", "value": 100}],
    desc="Number of requests currently being proxied through the tunnel concurrently.")); pid += 1

panels.append(stat_panel(pid, "Stream Errors/sec",
    f"sum(rate(cloudflared_proxy_connect_streams_errors{JOB}[$__rate_interval]))", "err/s", 16, y, w=4,
    unit="short", decimals=2,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.1}, {"color": "red", "value": 1}],
    desc="Rate of failures establishing proxy connections to origin. Non-zero indicates origin connectivity problems.")); pid += 1

_ver = stat_panel(pid, "Version",
    f'build_info{JOB}', "{{version}}", 20, y, w=4,
    thresholds=[{"color": "blue", "value": None}],
    desc="Running cloudflared version. Sourced from the build_info metric labels.")
_ver["options"]["textMode"] = "name"
panels.append(_ver); pid += 1
y += 4

# Second stat row
panels.append(stat_panel(pid, "Config Version",
    f"cloudflared_orchestration_config_version{JOB}", "v{{pod}}", 0, y, w=4,
    thresholds=[{"color": "blue", "value": None}],
    desc="Remote configuration version from Cloudflare dashboard. Increments when tunnel config is updated.")); pid += 1

panels.append(stat_panel(pid, "Registrations",
    f"sum(cloudflared_tunnel_tunnel_register_success{JOB})", "registrations", 4, y, w=4,
    thresholds=[{"color": "green", "value": None}],
    desc="Total successful tunnel registration events. Should equal 4 × number of replicas after startup.")); pid += 1

panels.append(stat_panel(pid, "Active TCP Sessions",
    f"sum(cloudflared_tcp_active_sessions{JOB})", "tcp", 8, y, w=4,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50}],
    desc="Concurrent TCP sessions being proxied (e.g. SSH, private network access). Not used for HTTP tunnel traffic.")); pid += 1

panels.append(stat_panel(pid, "Active UDP Sessions",
    f"sum(cloudflared_udp_active_sessions{JOB})", "udp", 12, y, w=4,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50}],
    desc="Concurrent UDP sessions being proxied (e.g. private DNS, WARP traffic). DNS queries hold a port for 5 seconds.")); pid += 1

panels.append(stat_panel(pid, "Heartbeat Retries",
    f"sum(cloudflared_tunnel_timer_retries{JOB})", "retries", 16, y, w=4,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 5}],
    desc="Unacknowledged heartbeat count. Non-zero indicates connectivity issues between cloudflared and the edge.")); pid += 1

panels.append(stat_panel(pid, "Total Requests",
    f"sum(cloudflared_tunnel_total_requests{JOB})", "total", 20, y, w=4,
    thresholds=[{"color": "blue", "value": None}],
    desc="Cumulative total of all requests proxied since the process started.")); pid += 1
y += 4

# ============================================================
# ROW: Tunnel Capacity & Scaling
# ============================================================
panels.append(row(pid, "Tunnel Capacity & Scaling", y,
    desc="Capacity estimation for both HTTP-only tunnels (QUIC streams) and WARP/private network tunnels (TCP/UDP port-based). Based on https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-availability/system-requirements/")); pid += 1; y += 1

# --- HTTP tunnel throughput (the primary traffic for most tunnels) ---
panels.append(gauge_panel(pid, "Concurrent Requests",
    f"sum(cloudflared_tunnel_concurrent_requests_per_tunnel{JOB})",
    "concurrent", 0, y, w=6, h=6, unit="short", decimals=0,
    min_val=0, max_val=200,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50}, {"color": "red", "value": 100}],
    desc="In-flight HTTP requests across all tunnels. This is the primary load indicator for HTTP-only tunnels. Each concurrent request uses one QUIC stream. High values indicate slow origins or high traffic — consider adding replicas.")); pid += 1

panels.append(gauge_panel(pid, "HTTP Requests/sec",
    f"sum(rate(cloudflared_tunnel_total_requests{JOB}[$__rate_interval]))",
    "req/s", 6, y, w=6, h=6, unit="reqps", decimals=1,
    min_val=0, max_val=500,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 100}, {"color": "red", "value": 300}],
    desc="HTTP request throughput. For HTTP-only tunnels, this is the main scaling metric. Each request is multiplexed over QUIC streams on the 4 HA connections — no ephemeral port consumed on the host.")); pid += 1

panels.append(ts_panel(pid, "HTTP Throughput & Concurrency", [
    t(f"sum(rate(cloudflared_tunnel_total_requests{JOB}[$__rate_interval]))", "Requests/sec"),
    t(f"sum(cloudflared_tunnel_concurrent_requests_per_tunnel{JOB})", "Concurrent Requests", "B"),
], 12, y, w=12, h=6, fill=10,
    overrides=[color_override("Requests/sec", "green"), color_override("Concurrent Requests", "yellow")],
    desc="HTTP request rate and concurrency over time. For HTTP-only tunnels, these are the primary scaling signals. Rising concurrency with flat request rate means increasing origin latency.")); pid += 1
y += 6

# --- TCP/UDP port capacity (WARP / private network traffic) ---
panels.append(gauge_panel(pid, "TCP Port Capacity Used",
    f"sum(rate(cloudflared_tcp_total_sessions{JOB}[$__rate_interval])) / $available_ports * 100",
    "TCP", 0, y, w=6, h=6, decimals=2,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50}, {"color": "red", "value": 85}],
    desc="Estimated TCP port utilization. Only relevant for WARP/private network tunnels (SSH, RDP, etc.) — HTTP tunnel traffic uses QUIC streams instead of host ports. TCP ports release almost instantly; at 50,000 ports you'd need 50,001 sustained req/s to exhaust capacity.")); pid += 1

panels.append(gauge_panel(pid, "UDP Port Capacity Used",
    f"sum(rate(cloudflared_udp_total_sessions{JOB}[$__rate_interval])) * $dns_timeout / $available_ports * 100",
    "UDP", 6, y, w=6, h=6, decimals=2,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50}, {"color": "red", "value": 85}],
    desc="Estimated UDP port utilization. Only relevant for WARP/private network tunnels (private DNS, WARP UDP). DNS queries hold a port for ~5 seconds; at 50,000 ports with 5s timeout, max is 10,000 DNS queries/sec.")); pid += 1

panels.append(ts_panel(pid, "TCP/UDP Port Capacity % Over Time", [
    t(f"sum(rate(cloudflared_tcp_total_sessions{JOB}[$__rate_interval])) / $available_ports * 100", "TCP Port %"),
    t(f"sum(rate(cloudflared_udp_total_sessions{JOB}[$__rate_interval])) * $dns_timeout / $available_ports * 100", "UDP Port %", "B"),
], 12, y, w=12, h=6, unit="percent", fill=10, legend_calcs=["mean", "max"],
    overrides=[color_override("TCP Port %", "blue"), color_override("UDP Port %", "purple")],
    desc="Port capacity utilization for WARP/private network traffic. 0% is normal for HTTP-only tunnels — HTTP requests use QUIC streams, not host ports. Only non-zero when proxying TCP sessions (SSH/RDP) or UDP sessions (private DNS/WARP).")); pid += 1
y += 6

panels.append(text_panel(pid,
    "## Tunnel Scaling Reference\n\n"
    "Based on [Cloudflare tunnel system requirements](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-availability/system-requirements/):\n\n"
    "### Two types of tunnel traffic\n\n"
    "| Traffic Type | Bottleneck | Key Metric |\n"
    "|---|---|---|\n"
    "| **HTTP requests** (most common) | QUIC streams over 4 HA connections, CPU, memory | Concurrent Requests, Requests/sec |\n"
    "| **WARP / Private Network** (TCP/UDP) | Host ephemeral ports | TCP/UDP Port Capacity % |\n\n"
    "HTTP-only tunnels (like Cloudflare CDN → origin) do **not** consume host ports — requests are multiplexed "
    "over QUIC streams. The port-based capacity calculator only applies to WARP/Zero Trust private network access.\n\n"
    "### Resource recommendations\n\n"
    "| Resource | Recommendation |\n"
    "|---|---|\n"
    "| **Replicas** | ≥ 2 per location for redundancy |\n"
    "| **CPU / RAM** | 4 cores / 4 GB minimum per host |\n"
    "| **Ports** | 50,000 per host (`net.ipv4.ip_local_port_range = 11000 60999`) — WARP only |\n"
    "| **ulimit -n** | ≥ 70,000 open file descriptors |\n\n"
    "### Port capacity limits (WARP/private network only)\n\n"
    "| Traffic Type | Max Sustained / replica | Port Hold Time |\n"
    "|---|---|---|\n"
    "| **TCP requests** | 50,000 req/s | ~instant release |\n"
    "| **DNS (UDP)** | 10,000 queries/s | 5 seconds |\n"
    "| **Non-DNS UDP** | 50,000 concurrent | connection duration |\n\n"
    "### When to scale\n\n"
    "| Signal | Action |\n"
    "|---|---|\n"
    "| Concurrent requests consistently > 50 | Add replica |\n"
    "| TCP/UDP port capacity > 60% | Add replica |\n"
    "| Proxy connect latency p95 rising | Check origin health, then add replica |\n"
    "| HA connections < 4 per replica | Investigate connectivity |\n\n"
    "### ⚠ Scaling limitations\n\n"
    "cloudflared has **no auto-scaling capability or integration**. You can add replicas manually for HA, "
    "but **scaling down will break active eyeball connections** pinned to that replica — there is no graceful "
    "drain. Replicas within the same tunnel are strictly for **high availability, not load balancing** — "
    "Cloudflare does not distribute requests evenly across replicas of the same tunnel.\n\n"
    "For true horizontal scaling with controlled scale-down, run **multiple discrete tunnels** behind a "
    "load balancer (e.g. Cloudflare Load Balancing or an internal LB), so each tunnel can be "
    "drained and removed independently.\n",
    0, y, w=24, h=12, title="Scaling Guidelines",
    desc="Quick reference for Cloudflare tunnel sizing — covers both HTTP-only and WARP/private network tunnels.")); pid += 1
y += 9

# ============================================================
# ROW: Traffic
# ============================================================
panels.append(row(pid, "Traffic", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "Requests / sec", [
    t(f"sum(rate(cloudflared_tunnel_total_requests{JOB}[$__rate_interval]))", "Total Requests"),
    t(f"sum(rate(cloudflared_tunnel_request_errors{JOB}[$__rate_interval]))", "Errors", "B"),
], 0, y, overrides=[color_override("Total Requests", "green"), color_override("Errors", "red")],
    desc="Rate of requests proxied vs errors. Errors are requests that failed to reach origin (connection refused, timeout, TLS mismatch, etc.).")); pid += 1

panels.append(ts_panel(pid, "Response Status Codes", [
    t(f'sum by (status_code) (rate(cloudflared_tunnel_response_by_code{JOB}[$__rate_interval]))', "{{status_code}}")
], 12, y, overrides=[
    regex_color("^2..", "green"), regex_color("^3..", "blue"),
    regex_color("^4..", "orange"), regex_color("^5..", "red")
], desc="HTTP response status code distribution. Codes are from origin responses proxied back through the tunnel. 502/503 typically indicate origin unreachable.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Error Rate %", [
    t(f"sum(rate(cloudflared_tunnel_request_errors{JOB}[$__rate_interval])) / sum(rate(cloudflared_tunnel_total_requests{JOB}[$__rate_interval])) * 100", "Error %")
], 0, y, unit="percent", stack=False, fill=10,
    overrides=[color_override("Error %", "red")],
    legend_calcs=["mean", "lastNotNull"],
    desc="Percentage of requests resulting in proxy errors. Sustained rates above 1% warrant investigation — check origin health, TLS config, and DNS resolution.")); pid += 1

panels.append(ts_panel(pid, "Response Codes (Stacked)", [
    t(f'sum by (status_code) (increase(cloudflared_tunnel_response_by_code{JOB}[$__rate_interval]))', "{{status_code}}")
], 12, y, stack=True, overrides=[
    regex_color("^2..", "green"), regex_color("^3..", "blue"),
    regex_color("^4..", "orange"), regex_color("^5..", "red")
], desc="Stacked view of response code volume over time. Useful for seeing the proportion of success vs error responses.")); pid += 1
y += 8

# ============================================================
# ROW: Connections & Sessions
# ============================================================
panels.append(row(pid, "Connections & Sessions", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "HA Connections", [
    t(f"sum(cloudflared_tunnel_ha_connections{JOB})", "Total HA"),
    t(f"cloudflared_tunnel_ha_connections{JOB}", "{{pod}}", "B"),
], 0, y, overrides=[color_override("Total HA", "green")],
    desc="Number of active high-availability QUIC connections. Each cloudflared instance maintains 4 connections to different Cloudflare edge servers. A drop below 4 per replica means degraded redundancy.")); pid += 1

panels.append(ts_panel(pid, "Concurrent Requests per Tunnel", [
    t(f"cloudflared_tunnel_concurrent_requests_per_tunnel{JOB}", "{{pod}}")
], 12, y,
    desc="In-flight requests per tunnel instance. Spikes correlate with slow origins or large request payloads.")); pid += 1
y += 8

panels.append(ts_panel(pid, "TCP Sessions", [
    t(f"sum(cloudflared_tcp_active_sessions{JOB})", "Active TCP"),
    t(f"sum(rate(cloudflared_tcp_total_sessions{JOB}[$__rate_interval]))", "New TCP/sec", "B"),
], 0, y, overrides=[color_override("Active TCP", "green"), color_override("New TCP/sec", "blue")],
    desc="Active and new TCP sessions. TCP is used for private network access (SSH, RDP, etc.), not HTTP tunnel traffic.")); pid += 1

panels.append(ts_panel(pid, "UDP Sessions", [
    t(f"sum(cloudflared_udp_active_sessions{JOB})", "Active UDP"),
    t(f"sum(rate(cloudflared_udp_total_sessions{JOB}[$__rate_interval]))", "New UDP/sec", "B"),
], 12, y, overrides=[color_override("Active UDP", "green"), color_override("New UDP/sec", "blue")],
    desc="Active and new UDP sessions. Primarily private DNS resolution. Each DNS query holds a port for 5 seconds.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Proxy Stream Errors", [
    t(f"sum(rate(cloudflared_proxy_connect_streams_errors{JOB}[$__rate_interval]))", "Stream Errors/sec")
], 0, y, w=12, overrides=[color_override("Stream Errors/sec", "red")],
    desc="Rate of failures establishing proxy connections to origin. Causes include connection refused, DNS failure, or TLS handshake errors.")); pid += 1

panels.append(ts_panel(pid, "Heartbeat Retries", [
    t(f"cloudflared_tunnel_timer_retries{JOB}", "{{pod}}")
], 12, y, w=12,
    overrides=[color_override("{{pod}}", "orange")],
    desc="Unacknowledged heartbeat count per tunnel. Non-zero values indicate the edge hasn't responded to keepalive pings — possible network disruption or edge congestion.")); pid += 1
y += 8

panels.append(ts_panel(pid, "ICMP Requests & Replies", [
    t(f"sum(rate(cloudflared_icmp_total_requests{JOB}[$__rate_interval]))", "Requests/sec"),
    t(f"sum(rate(cloudflared_icmp_total_replies{JOB}[$__rate_interval]))", "Replies/sec", "B"),
], 0, y, w=12,
    desc="ICMP traffic proxied through the tunnel. Used for diagnostic ping through private networks.")); pid += 1

panels.append(ts_panel(pid, "Tunnel Registrations", [
    t(f"sum(cloudflared_tunnel_tunnel_register_success{JOB})", "Successful Registrations")
], 12, y, w=12,
    desc="Cumulative successful tunnel registrations. Should be 4 × replicas after initial startup. Increases indicate reconnections (e.g. after pod restarts or edge failovers).")); pid += 1
y += 8

# ============================================================
# ROW: Edge Locations
# ============================================================
panels.append(row(pid, "Edge Locations", y,
    desc="Which Cloudflare edge data centers the tunnel connections terminate at.")); pid += 1; y += 1

panels.append(table_panel(pid, "Active Edge Server Locations",
    f'cloudflared_tunnel_server_locations{JOB}',
    "{{connection_id}} → {{edge_location}}", 0, y, w=12, h=6,
    desc="Current edge PoP for each HA connection (value=1 means current, 0=previous). Connection IDs 0-3 map to the 4 HA connections per replica.")); pid += 1

panels.append(ts_panel(pid, "Config Version Over Time", [
    t(f"cloudflared_orchestration_config_version{JOB}", "{{pod}}")
], 12, y, h=6, stack=False, fill=5,
    desc="Remote configuration version over time. Step changes indicate config pushes from the Cloudflare dashboard (e.g. ingress rule updates).")); pid += 1
y += 6

# ============================================================
# ROW: QUIC Transport
# ============================================================
panels.append(row(pid, "QUIC Transport", y,
    desc="QUIC protocol metrics for the connections between cloudflared and Cloudflare edge. Each HA connection (conn_index 0-3) is an independent QUIC connection.")); pid += 1; y += 1

panels.append(ts_panel(pid, "QUIC RTT to Edge", [
    t(f"quic_client_smoothed_rtt{JOB}", "Smoothed conn={{conn_index}}"),
    t(f"quic_client_min_rtt{JOB}", "Min conn={{conn_index}}", "B"),
    t(f"quic_client_latest_rtt{JOB}", "Latest conn={{conn_index}}", "C"),
], 0, y, unit="ms", fill=10,
    desc="Round-trip time from cloudflared to the Cloudflare edge per QUIC connection. Smoothed RTT is the EWMA used by congestion control. Min RTT is the floor. Sudden increases indicate network path degradation.")); pid += 1

panels.append(ts_panel(pid, "QUIC Congestion Window", [
    t(f"quic_client_congestion_window{JOB}", "conn={{conn_index}}")
], 12, y, unit="bytes", fill=10,
    desc="QUIC congestion window size per connection. Larger windows = more data in flight. The window grows during slow start and shrinks on packet loss. A persistently small window indicates congestion.")); pid += 1
y += 8

panels.append(ts_panel(pid, "QUIC Bytes Sent / Received", [
    t(f"sum(rate(quic_client_sent_bytes{JOB}[$__rate_interval]))", "Sent"),
    t(f"sum(rate(quic_client_receive_bytes{JOB}[$__rate_interval]))", "Received", "B"),
], 0, y, unit="Bps", fill=10,
    overrides=[color_override("Sent", "green"), color_override("Received", "blue")],
    desc="Aggregate QUIC-level throughput across all connections. 'Sent' = data from cloudflared to edge (origin responses). 'Received' = data from edge to cloudflared (client requests).")); pid += 1

panels.append(ts_panel(pid, "QUIC Bytes by Connection", [
    t(f"rate(quic_client_sent_bytes{JOB}[$__rate_interval])", "Sent conn={{conn_index}}"),
    t(f"rate(quic_client_receive_bytes{JOB}[$__rate_interval])", "Recv conn={{conn_index}}", "B"),
], 12, y, unit="Bps", fill=10,
    desc="Per-connection QUIC throughput. Uneven distribution may indicate one edge PoP is handling more traffic (e.g. due to Cloudflare's Anycast routing).")); pid += 1
y += 8

panels.append(ts_panel(pid, "QUIC Packet Loss", [
    t(f"sum by (conn_index, reason) (rate(quic_client_lost_packets{JOB}[$__rate_interval]))", "conn={{conn_index}} ({{reason}})")
], 0, y, w=8, fill=10,
    overrides=[regex_color(".*", "red")],
    desc="Rate of lost QUIC packets by connection and reason. 'reordering' = detected via packet number gaps. 'timeout' = detected via RTO. Sustained loss degrades throughput and increases latency.")); pid += 1

_cong = ts_panel(pid, "QUIC Congestion State", [
    t(f"quic_client_congestion_state{JOB}", "conn={{conn_index}}")
], 8, y, w=8, fill=5,
    desc="QUIC congestion control state per connection. States: 0=SlowStart, 1=CongestionAvoidance, 2=Recovery, 3=ApplicationLimited. ApplicationLimited (3) is normal for low-traffic tunnels — means the bottleneck is traffic volume, not network capacity.")
_cong["fieldConfig"]["defaults"]["mappings"] = [{"options": {"0": {"text": "SlowStart"}, "1": {"text": "CongAvoid"}, "2": {"text": "Recovery"}, "3": {"text": "AppLimited"}}, "type": "value"}]
panels.append(_cong); pid += 1

panels.append(ts_panel(pid, "QUIC MTU / Max Payload", [
    t(f"quic_client_mtu{JOB}", "MTU conn={{conn_index}}"),
    t(f"quic_client_max_udp_payload{JOB}", "Max Payload conn={{conn_index}}", "B"),
], 16, y, w=8, unit="bytes", fill=5,
    desc="Discovered path MTU and maximum UDP payload size per connection. Default QUIC MTU is ~1375 bytes. A drop could indicate path MTU blackhole or network reconfiguration.")); pid += 1
y += 8

panels.append(ts_panel(pid, "QUIC Frames Sent", [
    t(f'sum by (frame_type) (rate(quic_client_sent_frames{JOB}[$__rate_interval]))', "{{frame_type}}")
], 0, y, stack=True, fill=80,
    desc="Rate of QUIC frames sent by type. 'Stream' frames carry actual data. 'Ping' frames are keepalives. 'ResetStream'/'StopSending' indicate cancelled requests. 'StreamDataBlocked'/'DataBlocked' indicate flow control pressure.")); pid += 1

panels.append(ts_panel(pid, "QUIC Frames Received", [
    t(f'sum by (frame_type) (rate(quic_client_received_frames{JOB}[$__rate_interval]))', "{{frame_type}}")
], 12, y, stack=True, fill=80,
    desc="Rate of QUIC frames received by type. High 'Ping' rate is normal (edge keepalives). 'MaxData'/'MaxStreamData' are flow control updates. 'ResetStream' from edge may indicate request cancellation by client.")); pid += 1
y += 8

panels.append(ts_panel(pid, "QUIC Connection Lifecycle", [
    t(f"sum(rate(quic_client_total_connections{JOB}[$__rate_interval]))", "New Connections/sec"),
    t(f"sum(rate(quic_client_closed_connections{JOB}[$__rate_interval]))", "Closed Connections/sec", "B"),
], 0, y, fill=10,
    overrides=[color_override("New Connections/sec", "green"), color_override("Closed Connections/sec", "red")],
    desc="QUIC connection creation vs closure rate. New connections happen at startup and during reconnections. Frequent closures may indicate network instability or edge-side disconnects.")); pid += 1

panels.append(ts_panel(pid, "Oversized Packet Drops", [
    t(f"sum(rate(quic_client_packet_too_big_dropped{JOB}[$__rate_interval]))", "Packets Dropped/sec")
], 12, y, fill=10,
    overrides=[color_override("Packets Dropped/sec", "red")],
    desc="Rate of QUIC packets dropped because they exceeded the path MTU. Non-zero indicates MTU discovery issues — check for MTU blackholes or misconfigured network equipment between cloudflared and edge.")); pid += 1
y += 8

# ============================================================
# ROW: Latency
# ============================================================
panels.append(row(pid, "Latency", y,
    desc="Origin-facing latency measured by cloudflared. Proxy connect = time to establish connection to origin. RPC = control plane operations.")); pid += 1; y += 1

panels.append(ts_panel(pid, "Proxy Connect Latency", [
    t(f"histogram_quantile(0.50, sum by (le) (rate(cloudflared_proxy_connect_latency_bucket{JOB}[$__rate_interval])))", "p50"),
    t(f"histogram_quantile(0.95, sum by (le) (rate(cloudflared_proxy_connect_latency_bucket{JOB}[$__rate_interval])))", "p95", "B"),
    t(f"histogram_quantile(0.99, sum by (le) (rate(cloudflared_proxy_connect_latency_bucket{JOB}[$__rate_interval])))", "p99", "C"),
], 0, y, unit="ms", stack=False, fill=10,
    overrides=[color_override("p50", "green"), color_override("p95", "yellow"), color_override("p99", "red")],
    legend_calcs=["mean", "lastNotNull"],
    desc="Time to establish and acknowledge connections to origin, in milliseconds. Includes DNS resolution, TCP handshake, and TLS handshake to origin. High p99 may indicate DNS resolution delays or origin connection pool exhaustion.")); pid += 1

panels.append(ts_panel(pid, "RPC Client Latency", [
    t(f"histogram_quantile(0.50, sum by (le) (rate(cloudflared_rpc_client_latency_secs_bucket{JOB}[$__rate_interval])))", "p50"),
    t(f"histogram_quantile(0.95, sum by (le) (rate(cloudflared_rpc_client_latency_secs_bucket{JOB}[$__rate_interval])))", "p95", "B"),
    t(f"histogram_quantile(0.99, sum by (le) (rate(cloudflared_rpc_client_latency_secs_bucket{JOB}[$__rate_interval])))", "p99", "C"),
], 12, y, unit="s", stack=False, fill=10,
    overrides=[color_override("p50", "green"), color_override("p95", "yellow"), color_override("p99", "red")],
    legend_calcs=["mean", "lastNotNull"],
    desc="Latency of RPC calls initiated by cloudflared (e.g. register_connection). These are control plane operations, not data plane. High latency here affects tunnel registration/reconnection speed.")); pid += 1
y += 8

panels.append(ts_panel(pid, "RPC Server Latency", [
    t(f"histogram_quantile(0.50, sum by (le) (rate(cloudflared_rpc_server_latency_secs_bucket{JOB}[$__rate_interval])))", "p50"),
    t(f"histogram_quantile(0.95, sum by (le) (rate(cloudflared_rpc_server_latency_secs_bucket{JOB}[$__rate_interval])))", "p95", "B"),
    t(f"histogram_quantile(0.99, sum by (le) (rate(cloudflared_rpc_server_latency_secs_bucket{JOB}[$__rate_interval])))", "p99", "C"),
], 0, y, unit="s", stack=False, fill=10,
    overrides=[color_override("p50", "green"), color_override("p95", "yellow"), color_override("p99", "red")],
    legend_calcs=["mean", "lastNotNull"],
    desc="Latency of RPC calls served by cloudflared (e.g. update_configuration from edge). High values may indicate slow config processing.")); pid += 1

panels.append(ts_panel(pid, "Proxy Connect Latency Heatmap (rate)", [
    t(f"sum(rate(cloudflared_proxy_connect_latency_bucket{JOB}[$__rate_interval])) by (le)", "{{le}}")
], 12, y, unit="ms", stack=True, fill=80,
    desc="Distribution of proxy connect latency across histogram buckets. Shows the shape of the latency distribution — bimodal patterns may indicate DNS cache hits/misses.")); pid += 1
y += 8

# ============================================================
# ROW: RPC Operations
# ============================================================
panels.append(row(pid, "RPC Operations", y,
    desc="Control plane RPC operations between cloudflared and Cloudflare edge.")); pid += 1; y += 1

panels.append(ts_panel(pid, "RPC Client Operations", [
    t(f'sum by (handler, method) (rate(cloudflared_rpc_client_operations{JOB}[$__rate_interval]))', "{{handler}}/{{method}}")
], 0, y,
    desc="Rate of RPC calls initiated by cloudflared. 'registration/register_connection' happens at startup and reconnection. Frequent calls may indicate unstable connections.")); pid += 1

panels.append(ts_panel(pid, "RPC Server Operations", [
    t(f'sum by (handler, method) (rate(cloudflared_rpc_server_operations{JOB}[$__rate_interval]))', "{{handler}}/{{method}}")
], 12, y,
    desc="Rate of RPC calls served by cloudflared. 'config/update_configuration' is triggered by Cloudflare dashboard changes. Frequent unexpected calls may indicate config flapping.")); pid += 1
y += 8

# ============================================================
# ROW: Process Resources
# ============================================================
panels.append(row(pid, "Process Resources", y,
    desc="System resource usage of the cloudflared process. Key limits: CPU cores (resource limits), memory (resource limits), file descriptors (ulimit -n, should be ≥70,000).")); pid += 1; y += 1

panels.append(ts_panel(pid, "CPU Usage", [
    t(f'rate(process_cpu_seconds_total{JOB}[$__rate_interval])', "{{pod}}")
], 0, y, unit="percentunit", stack=False, fill=10,
    desc="CPU usage as fraction of one core. 1.0 = one full core. Compare against resource limits to assess headroom.")); pid += 1

panels.append(ts_panel(pid, "Memory Usage", [
    t(f'process_resident_memory_bytes{JOB}', "RSS {{pod}}"),
    t(f'go_memstats_alloc_bytes{JOB}', "Go Heap {{pod}}", "B"),
    t(f'go_memstats_heap_idle_bytes{JOB}', "Heap Idle {{pod}}", "C"),
], 12, y, unit="bytes", stack=False, fill=10,
    desc="RSS = total process memory. Go Heap = active Go allocations. Heap Idle = memory returned to runtime but not OS. RSS is the metric to compare against k8s memory limits.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Network I/O", [
    t(f'rate(process_network_transmit_bytes_total{JOB}[$__rate_interval])', "TX {{pod}}"),
    t(f'rate(process_network_receive_bytes_total{JOB}[$__rate_interval])', "RX {{pod}}", "B"),
], 0, y, w=8, unit="Bps", stack=False, fill=10,
    overrides=[color_override("TX {{pod}}", "green"), color_override("RX {{pod}}", "blue")],
    desc="Process-level network throughput. TX = data sent to origins + edge. RX = data received from edge + origins. Should correlate with QUIC bytes but includes non-tunnel traffic (metrics scrapes, etc.).")); pid += 1

panels.append(ts_panel(pid, "Goroutines", [
    t(f'go_goroutines{JOB}', "{{pod}}")
], 8, y, w=8, stack=False, fill=10,
    desc="Number of active Go goroutines. Correlates with concurrent requests. A sustained increase without corresponding traffic may indicate goroutine leaks.")); pid += 1

panels.append(ts_panel(pid, "Open File Descriptors", [
    t(f'process_open_fds{JOB}', "Open {{pod}}"),
    t(f'process_max_fds{JOB}', "Max {{pod}}", "B"),
], 16, y, w=8, stack=False, fill=10,
    desc="Open vs maximum file descriptors. Cloudflare recommends ulimit -n ≥ 70,000. If Open approaches Max, connections will fail. In Kubernetes, check the pod's securityContext or the node's /proc/sys/fs/file-max.")); pid += 1
y += 8

panels.append(ts_panel(pid, "GC Duration", [
    t(f'rate(go_gc_duration_seconds_sum{JOB}[$__rate_interval])', "GC {{pod}}")
], 0, y, w=8, unit="s", stack=False, fill=10,
    legend_calcs=["mean", "lastNotNull"],
    desc="Rate of time spent in Go garbage collection (stop-the-world pauses). High GC pressure correlates with high allocation rate. Should be negligible (<1% of wall time).")); pid += 1

panels.append(ts_panel(pid, "Heap Objects", [
    t(f'go_memstats_heap_objects{JOB}', "{{pod}}")
], 8, y, w=8, stack=False, fill=10,
    desc="Number of live heap-allocated Go objects. Correlates with concurrent connections and requests. Rapid growth indicates memory pressure.")); pid += 1

panels.append(ts_panel(pid, "Memory Allocation Rate", [
    t(f'rate(go_memstats_alloc_bytes_total{JOB}[$__rate_interval])', "{{pod}}")
], 16, y, w=8, unit="Bps", stack=False, fill=10,
    desc="Rate of Go heap allocations. High allocation rate drives more frequent GC. Correlates with request rate — each proxied request allocates buffers.")); pid += 1
y += 8


# Build the dashboard JSON
dashboard = {}

if EXPORT:
    dashboard["__inputs"] = [
        {"name": "DS_PROMETHEUS", "label": "Prometheus", "description": "Prometheus datasource for cloudflared metrics", "type": "datasource", "pluginId": "prometheus", "pluginName": "Prometheus"}
    ]
    dashboard["__elements"] = {}
    dashboard["__requires"] = [
        {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "11.0.0"},
        {"type": "datasource", "id": "prometheus", "name": "Prometheus", "version": "1.0.0"},
        {"type": "panel", "id": "gauge", "name": "Gauge", "version": ""},
        {"type": "panel", "id": "stat", "name": "Stat", "version": ""},
        {"type": "panel", "id": "table", "name": "Table", "version": ""},
        {"type": "panel", "id": "text", "name": "Text", "version": ""},
        {"type": "panel", "id": "timeseries", "name": "Time series", "version": ""},
    ]

dashboard.update({
    "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]},
    "description": "Cloudflare Tunnel (cloudflared) monitoring — tunnel capacity & scaling, traffic, QUIC transport, connections, latency, edge locations, RPC operations, process resources",
    "editable": True if EXPORT else False,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "id": None,
    "links": [],
    "liveNow": False,
    "panels": collapse_rows(panels),
    "schemaVersion": 39,
    "tags": ["cloudflare", "tunnel", "cloudflared"],
    "templating": {"list": [
        {
            "current": {"selected": False, "text": "cloudflared-metrics", "value": "cloudflared-metrics"},
            "description": "Prometheus job name for cloudflared",
            "hide": 0,
            "includeAll": False,
            "label": "Job",
            "multi": False,
            "name": "job",
            "options": [],
            "query": {"query": 'label_values(cloudflared_tunnel_ha_connections, job)', "refId": "A"},
            "refresh": 2,
            "regex": "",
            "skipUrlSync": False,
            "type": "query",
            "datasource": DS,
        },
        {
            "current": {"selected": False, "text": "50000", "value": "50000"},
            "description": "Number of ephemeral ports available to cloudflared (default: 50000 per Cloudflare recommendation, set via net.ipv4.ip_local_port_range)",
            "hide": 0,
            "label": "Available Ports",
            "name": "available_ports",
            "options": [
                {"selected": True, "text": "50000", "value": "50000"},
                {"selected": False, "text": "30000", "value": "30000"},
                {"selected": False, "text": "16384", "value": "16384"},
            ],
            "query": "50000,30000,16384",
            "skipUrlSync": False,
            "type": "custom",
        },
        {
            "current": {"selected": False, "text": "5", "value": "5"},
            "description": "DNS UDP session timeout in seconds (default: 5s per Cloudflare docs). Each DNS query holds an ephemeral port for this duration.",
            "hide": 0,
            "label": "DNS Timeout (s)",
            "name": "dns_timeout",
            "options": [
                {"selected": True, "text": "5", "value": "5"},
                {"selected": False, "text": "10", "value": "10"},
                {"selected": False, "text": "30", "value": "30"},
            ],
            "query": "5,10,30",
            "skipUrlSync": False,
            "type": "custom",
        },
    ]},
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {},
    "timezone": "",
    "title": "Cloudflare Tunnel",
    "uid": "cloudflared-tunnel" if not EXPORT else "cloudflared-tunnel",
    "version": 1,
    "weekStart": ""
})

if EXPORT:
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflared-export.json")
else:
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflared.json")
with open(outpath, "w") as f:
    json.dump(dashboard, f, indent=2)
    f.write("\n")
print(f"Wrote {len(panels)} panels to {outpath}")
