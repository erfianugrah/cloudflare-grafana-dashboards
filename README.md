# Cloudflare Grafana Dashboards

Two comprehensive Grafana dashboards for monitoring Cloudflare infrastructure:

1. **Cloudflare Tunnel (cloudflared)** &mdash; 58 panels across 9 sections, powered by Prometheus
2. **Cloudflare Logpush** &mdash; 122 panels across 12 sections, powered by Loki

Both dashboards are available as importable JSON and as Python generators for customization.

## Table of Contents

- [Quick Start](#quick-start)
- [Dashboard: Cloudflare Tunnel (cloudflared)](#dashboard-cloudflare-tunnel-cloudflared)
  - [Requirements](#cloudflared-requirements)
  - [Setup](#cloudflared-setup)
  - [Sections](#cloudflared-sections)
  - [Template Variables](#cloudflared-template-variables)
- [Dashboard: Cloudflare Logpush](#dashboard-cloudflare-logpush)
  - [Requirements](#logpush-requirements)
  - [Architecture](#logpush-architecture)
  - [Setup](#logpush-setup)
  - [Sections](#logpush-sections)
  - [Template Variables](#logpush-template-variables)
- [Generators](#generators)
- [LogQL Performance Notes](#logql-performance-notes)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Quick Start

### Import a dashboard

1. In Grafana, go to **Dashboards > New > Import**
2. Upload the JSON file from `dashboards/` or paste its contents
3. Select your datasource when prompted (Prometheus for cloudflared, Loki for logpush)
4. Click **Import**

### Or install from Grafana.com

1. In Grafana, go to **Dashboards > New > Import**
2. Enter the dashboard ID:
   - **Cloudflare Logpush**: `24873` &mdash; [grafana.com/grafana/dashboards/24873](https://grafana.com/grafana/dashboards/24873)
   - **Cloudflare Tunnel (cloudflared)**: `24874` &mdash; [grafana.com/grafana/dashboards/24874](https://grafana.com/grafana/dashboards/24874)
3. Select your datasource and click **Import**

---

## Dashboard: Cloudflare Tunnel (cloudflared)

Monitors the health, performance, and capacity of your [cloudflared](https://github.com/cloudflare/cloudflared) tunnel deployment using Prometheus metrics.

### Cloudflared Requirements

| Component | Minimum Version | Notes |
|-----------|-----------------|-------|
| Grafana | 12.0+ | Uses timeseries, stat, gauge, table, barchart, text panels |
| Prometheus | 2.x+ | Any Prometheus-compatible TSDB (VictoriaMetrics, Thanos, etc.) |
| cloudflared | 2024.1.0+ | Must have metrics endpoint enabled |

### Cloudflared Setup

#### 1. Enable cloudflared metrics endpoint

cloudflared exposes Prometheus metrics via the `--metrics` flag. Add it to your cloudflared command:

```bash
cloudflared tunnel \
  --metrics 0.0.0.0:50000 \
  --metrics-update-freq 5s \
  run
```

Verify metrics are exposed:

```bash
curl http://localhost:50000/metrics
```

You should see metrics like `cloudflared_tunnel_total_requests`, `cloudflared_tunnel_ha_connections`, etc.

#### 2. Configure Prometheus scraping

**Option A: ServiceMonitor (Prometheus Operator)**

If you run cloudflared in Kubernetes with the Prometheus Operator:

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
  type: ClusterIP
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: cloudflared
  namespace: cloudflared
  labels:
    app: cloudflared
    release: prometheus  # match your Prometheus selector
spec:
  endpoints:
    - port: metrics
      interval: 5s
      path: /metrics
  namespaceSelector:
    matchNames:
      - cloudflared
  selector:
    matchLabels:
      app: cloudflared
```

**Option B: Static scrape config**

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: cloudflared
    scrape_interval: 5s
    static_configs:
      - targets: ['cloudflared-host:50000']
```

#### 3. Import the dashboard

Import `dashboards/cloudflare-tunnel.json` into Grafana and select your Prometheus datasource.

### Cloudflared Sections

| Section | Panels | Description |
|---------|--------|-------------|
| **Tunnel Overview** | 12 | Version, uptime, HA connections, active requests, request/error rates, response codes, server locations |
| **Tunnel Capacity & Scaling** | 7 | Two-tier capacity model: HTTP request concurrency for standard tunnels, TCP/UDP session-based capacity calculator for WARP/private network tunnels |
| **Traffic** | 4 | Request rate over time, error rate, response code breakdown, error ratio |
| **Connections & Sessions** | 8 | HA connection status, tunnel registrations, timer retries, TCP/UDP active and total sessions |
| **Edge Locations** | 2 | Server locations map and current edge colo connections |
| **QUIC Transport** | 11 | Per-connection RTT (latest, smoothed, min), congestion window, MTU, connection state, lost packets, sent/received frames, connection lifecycle (new vs closed), oversized packet drops |
| **Latency** | 4 | Proxy connect latency histograms (p50/p90/p99), RPC client/server latency |
| **RPC Operations** | 2 | RPC client and server operation rates by method |
| **Process Resources** | 8 | CPU, memory (RSS/virtual), open file descriptors, network I/O |

#### Capacity Model

The dashboard includes a two-tier capacity model:

- **HTTP-only tunnels** (standard): Requests are multiplexed over QUIC streams. No host ephemeral ports consumed. Primary metrics: `cloudflared_tunnel_concurrent_requests_per_tunnel` and `rate(cloudflared_tunnel_total_requests)`.
- **WARP / private network tunnels**: TCP/UDP sessions consume host ephemeral ports. Uses Cloudflare's sizing formula: `TCP capacity = sessions/s / ports`, `UDP capacity = sessions/s * dns_timeout / ports`.

### Cloudflared Template Variables

| Variable | Type | Description |
|----------|------|-------------|
| `job` | Query | Prometheus job label (auto-discovered) |
| `available_ports` | Custom | Ephemeral port count for capacity calculation (50000/30000/16384) |
| `dns_timeout` | Custom | DNS timeout for UDP capacity calculation (5/10/30 seconds) |

---

## Dashboard: Cloudflare Logpush

Visualizes Cloudflare Logpush data (HTTP requests, firewall events, Workers trace events) stored in Loki. Provides deep visibility into traffic patterns, cache performance, security events, bot activity, and threat intelligence.

### Logpush Requirements

| Component | Minimum Version | Notes |
|-----------|-----------------|-------|
| Grafana | 12.0+ | Uses timeseries, stat, table, piechart, geomap, barchart panels |
| Loki | 3.3+ | Required for `approx_topk` support |
| Log collector | Any | Grafana Alloy, Promtail, or any HTTP endpoint that writes to Loki |
| Cloudflare plan | Free+ | Logpush is available on all plans |

### Logpush Architecture

```
Cloudflare Logpush  ──(gzip HTTP POST)──>  Ingress / Reverse Proxy
                                                    │
                                           (decompress gzip)
                                                    │
                                              Log Collector
                                            (Alloy / Promtail)
                                                    │
                                          (extract dataset label)
                                                    │
                                                  Loki
                                                    │
                                                 Grafana
```

The key architectural decisions:

1. **Dataset as a label**: Each Logpush dataset (http_requests, firewall_events, workers_trace_events) is stored under a single Loki stream `{job="cloudflare-logpush"}` with a `dataset` label. This allows one receiver endpoint to handle all datasets.
2. **Selective JSON parsing**: Dashboard queries use `| json field1, field2` to parse only the fields needed per panel, not the full ~72 fields in http_requests. This is critical for Loki performance.
3. **`approx_topk` for high cardinality**: Table panels querying high-cardinality fields (paths, user agents, IPs, referers, fingerprints) use `approx_topk` instead of `topk` to avoid materializing all series before filtering.

### Logpush Setup

#### 1. Set up a log receiver endpoint

You need an HTTP endpoint that accepts Logpush POST requests and writes to Loki. The example below uses Grafana Alloy, but any pipeline that writes to Loki with the correct labels works.

**Grafana Alloy configuration:**

```alloy
// Cloudflare Logpush receiver
// Logpush sends gzip-compressed NDJSON. Your reverse proxy or pipeline
// must decompress it before it reaches this endpoint.

loki.source.api "cloudflare" {
  http {
    listen_address = "0.0.0.0"
    listen_port    = 3500
  }

  labels = {
    job = "cloudflare-logpush",
  }

  forward_to = [loki.process.cloudflare.receiver]
}

loki.process "cloudflare" {
  // Extract the dataset name injected by Logpush output_options
  stage.json {
    expressions = {
      dataset = "_dataset",
    }
  }

  stage.labels {
    values = {
      dataset = "dataset",
    }
  }

  forward_to = [loki.write.default.receiver]
}

loki.write "default" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

The `_dataset` field is injected by Logpush via `output_options.record_prefix` (see step 3 below).

#### 2. Handle gzip decompression

Cloudflare Logpush always sends gzip-compressed payloads. Alloy's `loki.source.api` does **not** decompress gzip automatically. You must decompress before the data reaches Alloy.

**Options:**

- **Traefik plugin**: Use a middleware plugin that decompresses gzip request bodies. See [decompress middleware example](#traefik-decompress-middleware).
- **Nginx**: Use `gunzip on;` directive.
- **Caddy**: Use the `encode` directive or a request body filter.
- **Standalone proxy**: A small Go/Python service that decompresses and forwards.

#### 3. Create Cloudflare Logpush jobs

Create Logpush jobs for each dataset you want to monitor. The `record_prefix` in `output_options` is critical — it injects the dataset name into each log line so the receiver can route them.

**Using the Cloudflare API:**

```bash
# HTTP Requests dataset
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/logpush/jobs" \
  -H "Authorization: Bearer {api_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "http-requests-to-loki",
    "destination_conf": "https://your-logpush-endpoint.example.com/loki/api/v1/push?header_Content-Type=application/json",
    "dataset": "http_requests",
    "enabled": true,
    "frequency": "low",
    "logpull_options": "fields=BotDetectionIDs,BotScore,BotScoreSrc,BotTags,CacheCacheStatus,CacheResponseBytes,CacheResponseStatus,CacheTieredFill,ClientASN,ClientCountry,ClientDeviceType,ClientIP,ClientIPClass,ClientMTLSAuthCertFingerprint,ClientMTLSAuthStatus,ClientRequestBytes,ClientRequestHost,ClientRequestMethod,ClientRequestPath,ClientRequestProtocol,ClientRequestReferer,ClientRequestScheme,ClientRequestSource,ClientRequestURI,ClientRequestUserAgent,ClientSSLCipher,ClientSSLProtocol,ClientSrcPort,ClientTCPRTTMs,ClientXRequestedWith,ContentScanObjResults,ContentScanObjTypes,Cookies,EdgeCFConnectingO2O,EdgeColoCode,EdgeColoID,EdgeEndTimestamp,EdgePathingOp,EdgePathingSrc,EdgePathingStatus,EdgeRateLimitAction,EdgeRateLimitID,EdgeRequestHost,EdgeResponseBodyBytes,EdgeResponseBytes,EdgeResponseCompressionRatio,EdgeResponseContentType,EdgeResponseStatus,EdgeServerIP,EdgeStartTimestamp,EdgeTimeToFirstByteMs,FirewallMatchesActions,FirewallMatchesRuleIDs,FirewallMatchesSources,JA3Hash,JA4,LeakedCredentialCheckResult,OriginDNSResponseTimeMs,OriginIP,OriginRequestHeaderSendDurationMs,OriginResponseBytes,OriginResponseDurationMs,OriginResponseHTTPExpires,OriginResponseHTTPLastModified,OriginResponseHeaderReceiveDurationMs,OriginResponseStatus,OriginResponseTime,OriginSSLProtocol,OriginTCPHandshakeDurationMs,OriginTLSHandshakeDurationMs,ParentRayID,RayID,RequestHeaders,SecurityAction,SecurityActions,SecurityRuleDescription,SecurityRuleID,SecurityRuleIDs,SecuritySources,SmartPlacementOriginIP,UpperTierColoID,WAFAttackScore,WAFRCEAttackScore,WAFSQLiAttackScore,WAFXSSAttackScore,WorkerCPUTime,WorkerStatus,WorkerSubrequest,WorkerSubrequestCount,WorkerWallTimeUs,ZoneName&timestamps=rfc3339",
    "output_options": {
      "field_names": ["EdgeStartTimestamp"],
      "timestamp_format": "rfc3339",
      "record_prefix": "{\"_dataset\":\"http_requests\",",
      "record_suffix": "}",
      "record_delimiter": "\n",
      "record_template": "{{record}}"
    }
  }'
```

```bash
# Firewall Events dataset
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/logpush/jobs" \
  -H "Authorization: Bearer {api_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "firewall-events-to-loki",
    "destination_conf": "https://your-logpush-endpoint.example.com/loki/api/v1/push?header_Content-Type=application/json",
    "dataset": "firewall_events",
    "enabled": true,
    "frequency": "low",
    "logpull_options": "fields=Action,ClientASN,ClientASNDescription,ClientCountry,ClientIP,ClientIPClass,ClientRefererHost,ClientRefererPath,ClientRefererQuery,ClientRefererScheme,ClientRequestHost,ClientRequestMethod,ClientRequestPath,ClientRequestProtocol,ClientRequestQuery,ClientRequestScheme,ClientRequestUserAgent,Datetime,Description,EdgeColoCode,EdgeResponseStatus,Kind,LeakedCredentialCheckResult,MatchIndex,Metadata,OriginResponseStatus,OriginatorRayID,RayID,Ref,RuleID,Source&timestamps=rfc3339",
    "output_options": {
      "field_names": ["Datetime"],
      "timestamp_format": "rfc3339",
      "record_prefix": "{\"_dataset\":\"firewall_events\",",
      "record_suffix": "}",
      "record_delimiter": "\n",
      "record_template": "{{record}}"
    }
  }'
```

```bash
# Workers Trace Events dataset (optional)
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/logpush/jobs" \
  -H "Authorization: Bearer {api_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "workers-trace-to-loki",
    "destination_conf": "https://your-logpush-endpoint.example.com/loki/api/v1/push?header_Content-Type=application/json",
    "dataset": "workers_trace_events",
    "enabled": true,
    "frequency": "low",
    "output_options": {
      "field_names": ["EventTimestampMs"],
      "timestamp_format": "rfc3339",
      "record_prefix": "{\"_dataset\":\"workers_trace_events\",",
      "record_suffix": "}",
      "record_delimiter": "\n",
      "record_template": "{{record}}"
    }
  }'
```

**Using OpenTofu / Terraform:**

```hcl
resource "cloudflare_logpush_job" "http_requests" {
  zone_id          = var.zone_id
  name             = "http-requests-to-loki"
  dataset          = "http_requests"
  destination_conf = "https://your-logpush-endpoint.example.com/loki/api/v1/push?header_Content-Type=application/json"
  enabled          = true
  frequency        = "low"

  logpull_options = "fields=BotScore,BotScoreSrc,CacheCacheStatus,CacheResponseBytes,ClientASN,ClientCountry,ClientDeviceType,ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestPath,ClientRequestProtocol,ClientRequestReferer,ClientRequestUserAgent,ClientSSLCipher,ClientSSLProtocol,EdgeColoCode,EdgeResponseBytes,EdgeResponseContentType,EdgeResponseStatus,EdgeStartTimestamp,EdgeTimeToFirstByteMs,JA3Hash,JA4,OriginDNSResponseTimeMs,OriginIP,OriginResponseDurationMs,OriginResponseStatus,OriginTCPHandshakeDurationMs,OriginTLSHandshakeDurationMs,RayID,SecurityAction,SecurityRuleDescription,SecurityRuleID,WAFAttackScore,WAFRCEAttackScore,WAFSQLiAttackScore,WAFXSSAttackScore,WorkerCPUTime,WorkerStatus,WorkerSubrequest,WorkerSubrequestCount,WorkerWallTimeUs,ZoneName&timestamps=rfc3339"

  output_options {
    field_names      = ["EdgeStartTimestamp"]
    timestamp_format = "rfc3339"
    record_prefix    = "{\"_dataset\":\"http_requests\","
    record_suffix    = "}"
    record_delimiter = "\n"
    record_template  = "{{record}}"
  }
}

resource "cloudflare_logpush_job" "firewall_events" {
  zone_id          = var.zone_id
  name             = "firewall-events-to-loki"
  dataset          = "firewall_events"
  destination_conf = "https://your-logpush-endpoint.example.com/loki/api/v1/push?header_Content-Type=application/json"
  enabled          = true
  frequency        = "low"

  logpull_options = "fields=Action,ClientASN,ClientASNDescription,ClientCountry,ClientIP,ClientIPClass,ClientRefererHost,ClientRefererPath,ClientRefererQuery,ClientRefererScheme,ClientRequestHost,ClientRequestMethod,ClientRequestPath,ClientRequestProtocol,ClientRequestQuery,ClientRequestScheme,ClientRequestUserAgent,ContentScanObjResults,ContentScanObjSizes,ContentScanObjTypes,Datetime,Description,EdgeColoCode,EdgeResponseStatus,Kind,LeakedCredentialCheckResult,MatchIndex,Metadata,OriginResponseStatus,OriginatorRayID,RayID,Ref,RuleID,Source,UserAgent&timestamps=rfc3339"

  output_options {
    field_names      = ["Datetime"]
    timestamp_format = "rfc3339"
    record_prefix    = "{\"_dataset\":\"firewall_events\","
    record_suffix    = "}"
    record_delimiter = "\n"
    record_template  = "{{record}}"
  }
}
```

#### 4. Configure Loki for optimal performance

The logpush dashboard uses `approx_topk` (probabilistic top-k using count-min sketch) for high-cardinality table panels. This requires Loki 3.3+ with specific config:

```yaml
# Add to your Loki config
frontend:
  encoding: protobuf

query_range:
  shard_aggregations: approx_topk
```

> **Important**: Loki does not watch its config file. You must restart Loki after config changes.

Also ensure reasonable limits for the volume of Logpush data:

```yaml
limits_config:
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20
  max_query_series: 5000
```

#### 5. Import the dashboard

Import `dashboards/cloudflare-logpush.json` into Grafana and select your Loki datasource.

After import, edit the **Zone** and **Host** template variables to add your own domain names (the exported dashboard ships with empty options so you can configure your own).

### Logpush Sections

| Section | Panels | Description |
|---------|--------|-------------|
| **Overview** | 8 | Total requests, error rate, cache hit ratio, firewall events, leaked credentials, WAF high risk, bot traffic %, worker errors |
| **HTTP Requests** | 22 | Status codes (color-coded), methods, protocols, request source, top paths, bot UAs, error paths, edge pathing, HTTP/HTTPS, geomap, country/colo top 10, ASNs, device types, referers, TLS versions/ciphers, mTLS, content scan, O2O |
| **Performance** | 13 | Request lifecycle breakdown (stacked), TTFB/origin/RTT percentiles, edge processing time, origin timing sub-components, by-host and by-ASN breakdowns, origin errors by IP |
| **Cache Performance** | 11 | Cache status over time + pie, hit ratio trend, by host, by path (approx_topk), tiered cache, Cache Reserve, response bytes, content types, compression ratio, Argo/Smart Routing |
| **Security & Firewall** | 13 | Events by action/source/host, top IPs/rules, firewall geomap + country top 10, top attacked paths/UAs/ASNs, events by HTTP method, challenge solve rate, action distribution pie |
| **API & Rate Limiting** | 9 | Rate limiting events, L7 DDoS mitigations, API Shield events, Bot Management events, rate limited paths/IPs, security product coverage, WAF rule types (managed vs custom), IP/country/ASN access rules |
| **WAF Attack Analysis** | 6 | WAF score buckets, attack type breakdown (SQLi/XSS/RCE), unmitigated attacks, security rule efficacy, security actions on HTTP, client IP classification |
| **Threat Intelligence** | 9 | Leaked credentials, fraud detection, top talkers, suspicious UAs, fraud detection tags/IDs, top client regions (subnational), firewall request URIs, geo anomaly on sensitive paths |
| **Bot Analysis** | 9 | Bot score distribution, score source engine, verified bot categories, JS detection, bot tags, bot detection tags, bot detection IDs (ATO/scraping/residential proxy/AI crawlers with value mappings), top JA4 fingerprints, top JA3 hashes |
| **Request Rate Analysis** | 7 | Requests/sec by IP, path, ASN, and edge colo. Burst detection tables: top IPs, paths, and JA4 fingerprints by peak request rate. Our version of Cloudflare's rate limiting request rate model. |
| **Request & Response Size** | 6 | Client request bytes (avg/p95), edge response body bytes (avg/p95), largest uploads/responses by path, total bandwidth (stacked), response size by host |
| **Workers** | 9 | Outcomes, CPU time, wall time, invocations by script, script versions, subrequest count, event types, exceptions table, status by script |

### Logpush Template Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `zone` | Custom (multi) | `.*` (All) | Filter by Cloudflare zone name (domain). Uses `ZoneName` for HTTP, `ClientRequestHost` regex match for firewall events. |
| `host` | Custom (multi) | `.*` (All) | Filter by FQDN hostname. More specific than zone — for subdomains. |
| `path` | Textbox | `.*` | Filter by request path (regex). |
| `ip` | Textbox | `.*` | Filter by client IP (regex). |
| `country` | Custom (multi) | `.*` (All) | Filter by client country (ISO 3166-1 Alpha-2). Full 249-country list included. |
| `ja4` | Textbox | `.*` | Filter by JA4 TLS fingerprint. |
| `asn` | Textbox | `.*` | Filter by client ASN number. |
| `colo` | Textbox | `.*` | Filter by edge colo code (IATA airport codes). |

---

## Generators

The `generators/` directory contains the Python scripts that produce the dashboard JSON files. Use these to customize the dashboards for your environment or to add/remove panels.

### Usage

```bash
cd generators/

# Generate local version (hardcoded datasource UID)
python3 gen-cloudflared.py
python3 gen-cloudflare-logpush.py

# Generate portable export for Grafana.com / sharing
python3 gen-cloudflared.py --export
python3 gen-cloudflare-logpush.py --export
```

### Files

| File | Description |
|------|-------------|
| `gen-cloudflared.py` | Cloudflare Tunnel dashboard generator (Prometheus) |
| `gen-cloudflare-logpush.py` | Cloudflare Logpush dashboard generator (Loki) |
| `country_codes.py` | ISO 3166-1 Alpha-2 country code mapping (249 entries) |

### Customization

The generators use helper functions to define panels:

- `ts_panel()` &mdash; Time series panel
- `stat_panel()` &mdash; Stat panel
- `table_panel()` &mdash; Table panel (instant queries)
- `bar_panel()` &mdash; Bar chart panel
- `pie_panel()` &mdash; Pie/donut chart panel
- `geomap_panel()` &mdash; Geographic map panel
- `gauge_panel()` &mdash; Gauge panel (cloudflared only)
- `text_panel()` &mdash; Text/markdown panel (cloudflared only)
- `row()` &mdash; Collapsible row separator

To add a panel, append to the `panels` list. To modify queries, edit the `http()`, `fw()`, or `wk()` helper functions which handle selective JSON field extraction and filter injection.

---

## LogQL Performance Notes

### Selective JSON parsing

Every Logpush log line contains 60-80+ JSON fields. Parsing all of them with `| json` on every query is extremely expensive. The dashboard queries use selective parsing:

```logql
# Bad — parses all ~72 fields
{job="cloudflare-logpush", dataset="http_requests"} | json | ...

# Good — parses only the 2 fields needed
{job="cloudflare-logpush", dataset="http_requests"} | json EdgeResponseStatus, ClientCountry | ...
```

The generator's `http()` function automatically includes filter variable fields (`ZoneName`, `ClientRequestHost`, `ClientCountry`, `ClientRequestPath`, `ClientIP`, `JA4`, `ClientASN`, `EdgeColoCode`) plus any additional fields the specific query needs.

### `approx_topk` vs `topk`

For high-cardinality fields (request paths, user agents, IPs, referers, TLS fingerprints), `topk` materializes ALL unique values before picking the top N. With thousands of unique paths, this easily hits Loki's `max_query_series` limit (typically 5000).

`approx_topk` (Loki 3.3+) uses a count-min sketch to estimate the top-k without materializing all series. It requires:

```yaml
# Loki config
frontend:
  encoding: protobuf
query_range:
  shard_aggregations: approx_topk  # string, not a YAML list
```

### Filter variables

All dashboard queries include filter clauses for template variables. When a variable is set to `.*` (the default), the filter is effectively a no-op. When set to a specific value, it narrows the query at the LogQL level, reducing the data Loki must scan.

---

## Traefik Decompress Middleware

If you use Traefik as your reverse proxy, Cloudflare Logpush sends gzip-compressed POST bodies that must be decompressed before reaching Alloy. Here is a minimal Traefik plugin middleware:

<details>
<summary>decompress.go</summary>

```go
package decompress

import (
    "bytes"
    "compress/gzip"
    "context"
    "fmt"
    "io"
    "net/http"
    "strconv"
    "strings"
)

type Config struct{}

func CreateConfig() *Config {
    return &Config{}
}

type Decompress struct {
    next http.Handler
    name string
}

func New(ctx context.Context, next http.Handler, config *Config, name string) (http.Handler, error) {
    return &Decompress{next: next, name: name}, nil
}

func (d *Decompress) ServeHTTP(rw http.ResponseWriter, req *http.Request) {
    encoding := strings.ToLower(req.Header.Get("Content-Encoding"))
    if encoding != "gzip" {
        d.next.ServeHTTP(rw, req)
        return
    }

    gzReader, err := gzip.NewReader(req.Body)
    if err != nil {
        http.Error(rw, fmt.Sprintf("failed to create gzip reader: %v", err), http.StatusBadRequest)
        return
    }
    defer gzReader.Close()

    decompressed, err := io.ReadAll(gzReader)
    if err != nil {
        http.Error(rw, fmt.Sprintf("failed to decompress body: %v", err), http.StatusBadRequest)
        return
    }

    req.Body = io.NopCloser(bytes.NewReader(decompressed))
    req.ContentLength = int64(len(decompressed))
    req.Header.Set("Content-Length", strconv.Itoa(len(decompressed)))
    req.Header.Del("Content-Encoding")

    d.next.ServeHTTP(rw, req)
}
```

</details>

Apply it as a Traefik middleware on your Logpush IngressRoute:

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: decompress
spec:
  plugin:
    decompress: {}
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: alloy-logpush
spec:
  entryPoints:
    - websecure
  routes:
    - kind: Rule
      match: Host(`logpush.example.com`)
      middlewares:
        - name: decompress
      services:
        - kind: Service
          name: alloy-logpush
          port: 3500
```

---

## Troubleshooting

### "maximum number of series (5000) reached"

This means a query is producing too many unique label combinations. The dashboard uses `approx_topk` to avoid this, but if you see it:

1. Ensure Loki has `approx_topk` enabled (see [Loki config](#4-configure-loki-for-optimal-performance))
2. Restart Loki after config changes (it does not watch its config file)
3. Narrow the time range or use template variable filters to reduce cardinality

### No data in panels

1. Verify Logpush is sending data: check your log collector's logs for incoming requests
2. Verify data is in Loki: `{job="cloudflare-logpush"} | json` should return log lines
3. Verify the `dataset` label exists: `{job="cloudflare-logpush", dataset="http_requests"}`
4. Check that `output_options.record_prefix` includes the `_dataset` field in your Logpush job config

### Panels load slowly

1. Enable selective JSON parsing (already done in the default dashboard)
2. Enable `approx_topk` in Loki config
3. Reduce the dashboard time range (6h is the default, 24h+ with high traffic can be slow)
4. Add `max_query_parallelism: 2` to Loki `limits_config` for better query scheduling

### cloudflared metrics missing

1. Verify the `--metrics` flag is set and the port is accessible
2. Check `curl http://<cloudflared-host>:<metrics-port>/metrics` returns data
3. Verify Prometheus is scraping the target (check Prometheus Targets page)
4. `cloudflared_tunnel_active_streams` is documented by Cloudflare but has never been present in the cloudflared source code or emitted by any version. This is a documentation-only metric.

---

## License

MIT License. See [LICENSE](LICENSE).
