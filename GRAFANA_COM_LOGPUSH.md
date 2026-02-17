# Cloudflare Logpush Dashboard

Comprehensive analytics dashboard for Cloudflare Logpush data stored in Loki. **135 panels across 12 sections** covering HTTP traffic, cache performance, security/firewall events, API & rate limiting, WAF attack analysis, threat intelligence, bot detection, request rate analysis, bandwidth cost analysis, and Workers.

8 template variable filters (zone, host, path, IP, country, JA4, ASN, colo) for deep drill-down. Every panel includes a description tooltip.

## Requirements

- **Grafana** 12.0+
- **Loki** 3.3+ (required for `approx_topk`)
- **Cloudflare** plan: Free or above (Logpush is available on all plans)
- A log collector (Grafana Alloy, Promtail, etc.) receiving Logpush HTTP POST data

## Sections

### Overview (8 panels)
Total requests, 5xx error rate, cache hit ratio, firewall events, leaked credentials, high-risk WAF score, bot traffic %, worker errors.

### HTTP Requests (22 panels)
Status codes (color-coded 2xx/3xx/4xx/5xx), request methods, protocols, request source (eyeball vs worker), top paths, bot user agents, error rate by path, edge pathing decisions, HTTP vs HTTPS, geomap (world map by country), requests by country and colo (top 10), top client ASNs with name resolution, device types, top referers, TLS versions/ciphers, origin SSL protocol, mTLS authentication, content scan results, orange-to-orange traffic.

### Performance (13 panels)
Request lifecycle breakdown (stacked: Client-Edge RTT, Edge Processing, Edge-Origin), TTFB/origin/RTT percentiles (avg/p50/p75/p90/p95/p99), edge processing time, origin timing sub-components (DNS/TCP/TLS/headers), by-host and by-ASN breakdowns, origin error rate by IP, edge→origin status pairs.

### Cache Performance (11 panels)
Cache status over time + pie chart, hit ratio trend, hit ratio by host (zone), hit ratio by path (top 10 using `approx_topk`), tiered cache fill rate, Cache Reserve usage, edge/cache response bytes, content type distribution, compression ratio, Argo Smart Routing usage.

### Security & Firewall (13 panels)
Firewall events by action/source/host, top client IPs, top rules, firewall events geomap + country top 10, top attacked paths, top attacking user agents, top attacking ASNs, events by HTTP method, challenge solve rate, firewall action distribution pie.

### API & Rate Limiting (9 panels)
Rate limiting events by action, L7 DDoS mitigations, API Shield events (schema validation, JWT, sequence mitigation), Bot Management enforcement events, rate limited paths/IPs tables, security product coverage (all Source values), WAF rule types (managed vs custom vs legacy), IP/country/ASN access rules.

### WAF Attack Analysis (6 panels)
WAF attack score buckets (high/medium/low risk), attack type breakdown (SQLi/XSS/RCE at score <= 20), unmitigated attacks table (low score + not blocked), security rule efficacy, security actions on HTTP requests, client IP classification.

### Threat Intelligence (9 panels)
Leaked credential check results, fraud detection signals, top talkers by IP, suspicious user agents (bot score < 30), fraud detection tags/IDs, top client regions (subnational ISO 3166-2), firewall event request URIs (path + query string), geo anomaly on sensitive paths.

### Bot Analysis (8 panels)
Bot score distribution (bot/possibly-bot/human), bot score source engine (ML/Heuristics/JS Fingerprinting), verified bot categories, JS detection pass/fail, bot traffic by path and IP (score < 30), bot detection IDs with inline value-mapped descriptions (account takeover, scraping, residential proxy, AI crawlers, machine learning, heuristic, verified bot — 33 known IDs), bot fingerprints by JA4.

### Request Rate Analysis (7 panels)
Request velocity and burst detection — mirrors Cloudflare's rate limiting request rate model. Requests/sec by IP, ASN, and edge colo (rate limiting counters are per-colo). Requests by path (count-based to avoid high-cardinality rate() explosion). Volume tables: top IPs, paths, and JA4 fingerprints by total request count using `approx_topk`.

### Request & Response Size (8 panels)
Client request bytes (avg/p95), edge response body bytes (avg/p95), largest uploads by path (>10KB), largest responses by path (>100KB), requests by host, bandwidth by host — CF→Eyeball (EdgeResponseBytes, what Cloudflare charges), bandwidth by host — Origin→CF (cache misses only, what your origin provider may charge for egress), CF→Eyeball vs Origin→CF total comparison showing bandwidth savings from caching.

### Workers (9 panels)
Worker outcomes (ok/exception/exceeded), CPU time by script (avg/p95), wall time, invocations by script, script version tracking, subrequest count, event types (fetch/cron/alarm/queue), exceptions table, status by script.

## Template Variables

| Variable | Type | Description |
|----------|------|-------------|
| `zone` | Multi-select | Cloudflare zone name (domain). Filters HTTP requests by `ZoneName`, firewall events by `ClientRequestHost` regex match. |
| `host` | Multi-select | FQDN hostname — more specific than zone for subdomains. |
| `path` | Textbox | Request path regex (e.g. `/api/.*`). Default `.*` for all. |
| `ip` | Textbox | Client IP regex. |
| `country` | Multi-select | Client country — full 249-country list (ISO 3166-1 Alpha-2). |
| `ja4` | Textbox | JA4 TLS fingerprint. |
| `asn` | Textbox | Client ASN number. |
| `colo` | Textbox | Edge colo code (IATA airport codes, e.g. `SIN\|NRT\|LAX`). |

After import, edit the **Zone** and **Host** variables to add your own domain names.

## Setup

### 1. Set up a log receiver

You need an HTTP endpoint that receives Logpush data and writes to Loki. Example using Grafana Alloy:

```alloy
loki.source.api "cloudflare" {
  http {
    listen_address = "0.0.0.0"
    listen_port    = 3500
  }
  labels = { job = "cloudflare-logpush" }
  forward_to = [loki.process.cloudflare.receiver]
}

loki.process "cloudflare" {
  stage.json { expressions = { dataset = "_dataset" } }
  stage.labels { values = { dataset = "dataset" } }
  forward_to = [loki.write.default.receiver]
}

loki.write "default" {
  endpoint { url = "http://loki:3100/loki/api/v1/push" }
}
```

### 2. Handle gzip decompression

Cloudflare Logpush always sends gzip-compressed payloads. Your reverse proxy must decompress before data reaches the log collector. Options:
- **Traefik**: Use a decompress middleware plugin
- **Nginx**: `gunzip on;`
- **Caddy**: `encode` directive

### 3. Create Cloudflare Logpush jobs

Create jobs for each dataset using the Cloudflare API or Terraform/OpenTofu. The critical piece is `output_options.record_prefix` which injects the dataset name:

```json
{
  "dataset": "http_requests",
  "destination_conf": "https://your-endpoint/loki/api/v1/push?header_Content-Type=application/json",
  "output_options": {
    "field_names": ["EdgeStartTimestamp"],
    "timestamp_format": "rfc3339",
    "record_prefix": "{\"_dataset\":\"http_requests\",",
    "record_suffix": "}",
    "record_delimiter": "\n",
    "record_template": "{{record}}"
  }
}
```

Repeat for `firewall_events` (with `"_dataset":"firewall_events"`) and optionally `workers_trace_events`.

### 4. Configure Loki

The dashboard uses `approx_topk` for high-cardinality table panels. Add to your Loki config:

```yaml
frontend:
  encoding: protobuf
query_range:
  shard_aggregations: approx_topk
```

**Important**: Loki does not watch its config file — restart after changes.

### 5. Import this dashboard

In Grafana: **Dashboards > New > Import**, enter ID `24873`, and select your Loki datasource.

## Performance Design

- **Selective JSON parsing**: Queries parse only the fields needed per panel (`| json field1, field2`) instead of all ~72 fields. This is critical for Loki performance at scale.
- **`approx_topk`**: High-cardinality table panels (paths, user agents, IPs, referers, fingerprints) use probabilistic top-k to avoid hitting the `max_query_series` limit.
- **Filter variables**: All queries include filter clauses that act as no-ops when set to `.*` and narrow scans when set to specific values.

## Troubleshooting

- **"maximum number of series (5000) reached"**: Enable `approx_topk` in Loki config and restart Loki.
- **No data**: Verify `{job="cloudflare-logpush", dataset="http_requests"} | json` returns logs in Explore.
- **Slow panels**: Reduce the time range (6h default) or use template variable filters to narrow queries.

## Source

[GitHub Repository](https://github.com/erfianugrah/cloudflare-grafana-dashboards) — includes Python generator scripts for customization and detailed setup guide.
