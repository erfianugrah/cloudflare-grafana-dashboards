# Cloudflare Logpush Dashboard

Comprehensive analytics dashboard for Cloudflare Logpush data stored in Loki. **82 panels across 9 sections** covering HTTP traffic, cache performance, security/firewall events, WAF attack analysis, threat intelligence, bot detection, and Workers.

8 template variable filters (zone, host, path, IP, country, JA4, ASN, colo) for deep drill-down. Every panel includes a description tooltip.

## Requirements

- **Grafana** 12.0+
- **Loki** 3.3+ (required for `approx_topk`)
- **Cloudflare** plan: Free or above (Logpush is available on all plans)
- A log collector (Grafana Alloy, Promtail, etc.) receiving Logpush HTTP POST data

## Sections

### Overview (8 panels)
Total requests, error rate, cache hit ratio, unique visitors, bandwidth, request rate and error rate time series.

### HTTP Requests (22 panels)
Status code breakdown (2xx/3xx/4xx/5xx), request methods, HTTP versions, top paths, top user agents, error paths, geographic distribution (geomap), top client ASNs with name resolution, device types, top referers, TLS versions and cipher suites.

### Performance (13 panels)
TTFB distribution, origin response time, DNS/TCP/TLS handshake latency, TTFB by country and by ASN, origin latency by ASN, origin error rate by IP, edge error code mapping.

### Cache Performance (11 panels)
Cache status distribution (hit/miss/dynamic/expired/etc.), hit ratio over time, hit ratio by host (zone), hit ratio by path (top 10 using `approx_topk`), tiered cache fill rate, Cache Reserve usage, edge/cache response bytes, content type distribution.

### Security & Firewall (5 panels)
Firewall event rate, action breakdown (block/challenge/js_challenge/managed_challenge), top firewall client IPs, top triggered firewall rules, action distribution over time.

### WAF Attack Analysis (6 panels)
WAF attack score distribution, attack score heatmap, unmitigated attacks (WAF score <= 20 but not blocked), security rule efficacy, RCE/SQLi/XSS individual score time series.

### Threat Intelligence (5 panels)
Threat score distribution, top talkers by request count, suspicious user agents (bot score < 30), geo anomaly detection on sensitive paths (admin, login, wp-login, phpmyadmin, xmlrpc, etc.), leaked credential check results.

### Bot Analysis (6 panels)
Bot score distribution, bot vs. human traffic ratio, top JA4 TLS fingerprints, top JA3 hashes, bot score over time, automated traffic ratio.

### Workers (6 panels)
Worker invocations, CPU time, wall time, subrequest counts, worker status codes, error rate.

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
