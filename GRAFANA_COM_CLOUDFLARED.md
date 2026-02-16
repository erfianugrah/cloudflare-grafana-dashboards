# Cloudflare Tunnel (cloudflared) Dashboard

Comprehensive monitoring dashboard for [cloudflared](https://github.com/cloudflare/cloudflared) tunnel deployments. **58 panels across 9 sections** covering tunnel health, capacity planning, QUIC transport, latency analysis, and process resources.

Every panel includes a description tooltip explaining what it shows and why it matters.

## Requirements

- **Grafana** 12.0+
- **Prometheus** (or any compatible TSDB)
- **cloudflared** with `--metrics` flag enabled

## Sections

### Tunnel Overview (12 panels)
Version info, uptime, HA connection count, active concurrent requests, total request rate, error rate, response code breakdown (2xx/3xx/4xx/5xx), and current edge server locations.

### Tunnel Capacity & Scaling (7 panels)
Two-tier capacity model:
- **HTTP-only tunnels**: Requests are multiplexed over QUIC streams — no host ephemeral ports consumed. Primary metrics: concurrent requests per tunnel and request rate.
- **WARP / private network tunnels**: TCP/UDP sessions consume host ephemeral ports. Interactive calculator using Cloudflare's sizing formula with configurable port count and DNS timeout variables.

Includes a text panel documenting scaling limitations (no auto-scaling, no graceful drain, HA-only replicas).

### Traffic (4 panels)
Request rate over time, error rate, response code distribution, and error ratio percentage.

### Connections & Sessions (8 panels)
HA connection status per tunnel, tunnel registration events, timer retries, TCP/UDP active and total session counts.

### Edge Locations (2 panels)
Current edge colo connections and server location details.

### QUIC Transport (11 panels)
Per-connection metrics: latest RTT, smoothed RTT, minimum RTT, congestion window size, MTU, congestion state, lost packets by reason, sent/received frame counts, connection lifecycle (new vs closed connections), and oversized packet drops.

### Latency (4 panels)
Proxy connect latency histogram quantiles (p50/p90/p99) and RPC client/server latency distributions.

### RPC Operations (2 panels)
RPC client and server operation rates broken down by handler and method.

### Process Resources (8 panels)
CPU usage, resident/virtual memory, open file descriptors vs. max, and network I/O (bytes sent/received).

## Template Variables

| Variable | Description |
|----------|-------------|
| `job` | Prometheus job label (auto-discovered) |
| `available_ports` | Ephemeral port count for WARP capacity calculator (50000/30000/16384) |
| `dns_timeout` | DNS timeout for UDP capacity calculation (5/10/30 seconds) |

## Setup

### 1. Enable the cloudflared metrics endpoint

Add `--metrics` to your cloudflared command:

```bash
cloudflared tunnel --metrics 0.0.0.0:50000 --metrics-update-freq 5s run
```

Verify: `curl http://localhost:50000/metrics`

### 2. Configure Prometheus scraping

**ServiceMonitor (Prometheus Operator):**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: cloudflared-metrics
  namespace: cloudflared
  labels:
    app: cloudflared
spec:
  selector:
    app: cloudflared
  ports:
    - name: metrics
      port: 50000
      targetPort: 50000
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: cloudflared
  namespace: cloudflared
spec:
  endpoints:
    - port: metrics
      interval: 5s
      path: /metrics
  selector:
    matchLabels:
      app: cloudflared
```

**Static scrape config:**

```yaml
scrape_configs:
  - job_name: cloudflared
    scrape_interval: 5s
    static_configs:
      - targets: ['cloudflared-host:50000']
```

### 3. Import this dashboard

In Grafana: **Dashboards > New > Import**, enter ID `24874`, and select your Prometheus datasource.

## Notes

- `cloudflared_tunnel_active_streams` is documented by Cloudflare but has never been present in the cloudflared source code or emitted by any version. This dashboard does not use it.
- TCP/UDP session metrics will be `0` for HTTP-only tunnels — this is correct, not a bug. Those metrics are only relevant for WARP/private network tunnels.
- The dashboard uses the QUIC `conn_index` label to show per-connection transport metrics for each of the 4 HA connections.

## Source

[GitHub Repository](https://github.com/erfianugrah/cloudflare-grafana-dashboards) — includes Python generator scripts for customization.
