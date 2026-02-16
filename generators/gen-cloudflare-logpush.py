#!/usr/bin/env python3
"""Generate the Cloudflare Logpush Grafana dashboard JSON.

Usage:
  python3 gen-cloudflare-logpush.py            # Local deploy (hardcoded datasource UID)
  python3 gen-cloudflare-logpush.py --export   # Portable export for grafana.com / sharing
"""
import json, sys
from country_codes import COUNTRY_NAMES


EXPORT = "--export" in sys.argv

# Shorthand helpers
if EXPORT:
    DS = {"type": "loki", "uid": "${DS_LOKI}"}
else:
    DS = {"type": "loki", "uid": "loki"}

OPEN_ROWS = {"Overview"}  # Rows to keep expanded; all others collapse

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

def stat_panel(id, title, expr, legend, x, y, w=6, unit="short", thresholds=None, instant=True, desc=""):
    th = thresholds or [{"color": "green", "value": None}]
    p = {
        "datasource": DS,
        "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": th}, "unit": unit}, "overrides": []},
        "gridPos": {"h": 4, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "textMode": "auto"},
        "title": title,
        "type": "stat",
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A", "queryType": "instant", "instant": True}]
    }
    if unit == "percent":
        p["fieldConfig"]["defaults"]["max"] = 100
        p["fieldConfig"]["defaults"]["min"] = 0
    if desc: p["description"] = desc
    return p

def ts_panel(id, title, targets, x, y, w=12, h=8, unit="short", stack=True, overrides=None, fill=20, legend_calcs=None, desc=""):
    p = {
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
        "options": {"legend": {"calcs": legend_calcs or ["sum", "mean"], "displayMode": "table", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}},
        "title": title,
        "type": "timeseries",
        "targets": targets
    }
    if desc: p["description"] = desc
    return p

def bar_panel(id, title, targets, x, y, w=12, h=8, unit="short", stack=True, overrides=None, desc=""):
    p = ts_panel(id, title, targets, x, y, w, h, unit, stack, overrides)
    p["fieldConfig"]["defaults"]["custom"]["drawStyle"] = "bars"
    p["fieldConfig"]["defaults"]["custom"]["fillOpacity"] = 80
    p["fieldConfig"]["defaults"]["custom"]["showPoints"] = "never"
    if desc: p["description"] = desc
    return p

def table_panel(id, title, expr, legend, x, y, w=8, h=8, extra_overrides=None, desc=""):
    overrides = [
        {"matcher": {"id": "byName", "options": "Value #A"}, "properties": [
            {"id": "custom.width", "value": 100},
            {"id": "displayName", "value": "Count"},
            {"id": "custom.cellOptions", "value": {"mode": "basic", "type": "gauge", "valueDisplayMode": "text"}},
        ]},
        {"matcher": {"id": "byName", "options": "Time"}, "properties": [{"id": "custom.hidden", "value": True}]},
    ]
    if extra_overrides:
        overrides.extend(extra_overrides)
    p = {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": overrides
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}, "sortBy": [{"desc": True, "displayName": "Count"}]},
        "title": title,
        "type": "table",
        "transformations": [
            {"id": "sortBy", "options": {"sort": [{"field": "Value #A", "desc": True}]}},
        ],
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A", "instant": True, "format": "table"}]
    }
    if desc: p["description"] = desc
    return p

def pie_panel(id, title, expr, legend, x, y, w=6, h=8, overrides=None, desc=""):
    p = {
        "datasource": DS,
        "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"hideFrom": {"legend": False, "tooltip": False, "viz": False}}, "mappings": []}, "overrides": overrides or []},
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"displayLabels": ["percent"], "legend": {"displayMode": "table", "placement": "right", "values": ["value", "percent"]}, "pieType": "donut", "reduceOptions": {"calcs": ["sum"], "fields": "", "values": False}, "tooltip": {"mode": "single", "sort": "none"}},
        "title": title,
        "type": "piechart",
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A", "queryType": "range"}]
    }
    if desc: p["description"] = desc
    return p

def t(expr, legend, ref="A"):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref, "queryType": "range"}

def color_override(name, color):
    return {"matcher": {"id": "byName", "options": name}, "properties": [{"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}]}

def regex_color(pattern, color):
    return {"matcher": {"id": "byRegexp", "options": pattern}, "properties": [{"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}]}

def country_name_overrides():
    """Generate displayName overrides to rename ISO country codes to full names in timeseries legends."""
    return [{"matcher": {"id": "byName", "options": code}, "properties": [{"id": "displayName", "value": name}]}
            for code, name in COUNTRY_NAMES.items()]

def country_value_mappings_override(column_name):
    """Generate a table column override that maps country codes to full names via value mappings."""
    value_map = {code: {"text": f"{name} ({code.upper()})", "index": i} for i, (code, name) in enumerate(COUNTRY_NAMES.items())}
    return {"matcher": {"id": "byName", "options": column_name}, "properties": [
        {"id": "mappings", "value": [{"type": "value", "options": value_map}]}
    ]}

def asn_lookup_table_panel(id, title, http_expr, x, y, w=12, h=8, desc=""):
    """Table panel that joins HTTP ClientASN data with firewall_events ClientASNDescription for live ASN name resolution.

    Query A: HTTP metric grouped by ClientASN (the actual data).
    Query B: firewall_events lookup mapping ClientASN -> ClientASNDescription.
    Transformations merge on ClientASN and display the resolved name.
    """
    fw_lookup_expr = f'topk(1, sum by (ClientASN, ClientASNDescription) (count_over_time({fw("ClientASN", "ClientASNDescription")} [$__range])))'
    overrides = [
        {"matcher": {"id": "byName", "options": "Value #A"}, "properties": [
            {"id": "custom.width", "value": 100},
            {"id": "displayName", "value": "Count"},
            {"id": "custom.cellOptions", "value": {"mode": "basic", "type": "gauge", "valueDisplayMode": "text"}},
        ]},
        {"matcher": {"id": "byName", "options": "Time"}, "properties": [{"id": "custom.hidden", "value": True}]},
        {"matcher": {"id": "byName", "options": "Value #B"}, "properties": [{"id": "custom.hidden", "value": True}]},
    ]
    p = {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": overrides
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}, "sortBy": [{"desc": True, "displayName": "Count"}]},
        "title": title,
        "type": "table",
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "Value #B": True},
                "indexByName": {"ClientASN": 0, "ClientASNDescription": 1, "Value #A": 2},
                "renameByName": {"ClientASNDescription": "ASN Name"},
            }},
            {"id": "sortBy", "options": {"sort": [{"field": "Value #A", "desc": True}]}},
        ],
        "targets": [
            {"datasource": DS, "expr": http_expr, "legendFormat": "{{ClientASN}}", "refId": "A", "instant": True, "format": "table"},
            {"datasource": DS, "expr": fw_lookup_expr, "legendFormat": "{{ClientASN}}", "refId": "B", "instant": True, "format": "table"},
        ]
    }
    if desc: p["description"] = desc
    return p

def fw_asn_table_panel(id, title, fw_expr, x, y, w=8, h=8, desc=""):
    """Table panel for firewall ASN data using ClientASNDescription directly from firewall_events."""
    overrides = [
        {"matcher": {"id": "byName", "options": "Value #A"}, "properties": [
            {"id": "custom.width", "value": 100},
            {"id": "displayName", "value": "Count"},
            {"id": "custom.cellOptions", "value": {"mode": "basic", "type": "gauge", "valueDisplayMode": "text"}},
        ]},
        {"matcher": {"id": "byName", "options": "Time"}, "properties": [{"id": "custom.hidden", "value": True}]},
    ]
    p = {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": overrides
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}, "sortBy": [{"desc": True, "displayName": "Count"}]},
        "title": title,
        "type": "table",
        "transformations": [
            {"id": "organize", "options": {
                "excludeByName": {"Time": True},
                "indexByName": {"ClientASN": 0, "ClientASNDescription": 1, "Value #A": 2},
                "renameByName": {"ClientASNDescription": "ASN Name"},
            }},
            {"id": "sortBy", "options": {"sort": [{"field": "Value #A", "desc": True}]}},
        ],
        "targets": [{"datasource": DS, "expr": fw_expr, "legendFormat": "{{ClientASN}}", "refId": "A", "instant": True, "format": "table"}]
    }
    if desc: p["description"] = desc
    return p

def geomap_panel(id, title, expr, lookup_field, x, y, w=16, h=10, gazetteer="public/gazetteer/countries.json", desc=""):
    """Geomap panel using lookup mode to resolve country/state codes to coordinates."""
    p = {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "continuous-BlYlRd"},
                "custom": {"hideFrom": {"legend": False, "tooltip": False, "viz": False}},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 80}]},
            },
            "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "basemap": {"config": {}, "name": "Layer 0", "type": "default"},
            "controls": {"mouseWheelZoom": True, "showAttribution": True, "showDebug": False, "showMeasure": False, "showScale": False, "showZoom": True},
            "layers": [{
                "config": {
                    "color": {"field": "Value", "fixed": "dark-green"},
                    "fillOpacity": 0.4,
                    "shape": "circle",
                    "showLegend": True,
                    "size": {"field": "Value", "fixed": 5, "max": 20, "min": 3},
                },
                "location": {"gazetteer": gazetteer, "lookup": lookup_field, "mode": "lookup"},
                "name": "Markers",
                "type": "markers",
            }],
            "tooltip": {"mode": "details"},
            "view": {"id": "coords", "lat": 20, "lon": 0, "zoom": 1.5},
        },
        "title": title,
        "type": "geomap",
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": "", "refId": "A", "instant": True, "format": "table"}],
    }
    if desc: p["description"] = desc
    return p

# Shared query builders
# These return stream selector + selective | json <fields> + template variable filters.
# Only the fields actually needed by each query are parsed, avoiding full JSON parsing.
# Filter variable fields are always included automatically.

# Filter fields that template variables reference — always extracted
_HTTP_FILTER_FIELDS = ["ClientRequestHost", "ClientCountry", "ClientRequestPath", "ClientIP", "JA4", "ClientASN", "EdgeColoCode", "ZoneName"]
_HTTP_FILTERS = '| ZoneName =~ "$zone" | ClientRequestHost =~ "$host" | ClientCountry =~ "$country" | ClientRequestPath =~ "$path" | ClientIP =~ "$ip" | JA4 =~ "$ja4" | ClientASN =~ "$asn" | EdgeColoCode =~ "$colo"'
_FW_FILTER_FIELDS = ["ClientRequestHost", "ClientIP"]
_FW_FILTERS = '| ClientRequestHost =~ "$zone" | ClientRequestHost =~ "$host" | ClientIP =~ "$ip"'

def http(*fields):
    """Build HTTP logpush query fragment with selective JSON field extraction."""
    all_fields = sorted(set(_HTTP_FILTER_FIELDS + list(fields)))
    return '{job="cloudflare-logpush", dataset="http_requests"} | json ' + ', '.join(all_fields) + ' ' + _HTTP_FILTERS

def fw(*fields):
    """Build firewall logpush query fragment with selective JSON field extraction."""
    all_fields = sorted(set(_FW_FILTER_FIELDS + list(fields)))
    return '{job="cloudflare-logpush", dataset="firewall_events"} | json ' + ', '.join(all_fields) + ' ' + _FW_FILTERS

def wk(*fields):
    """Build workers logpush query fragment with selective JSON field extraction."""
    if fields:
        return '{job="cloudflare-logpush", dataset="workers_trace_events"} | json ' + ', '.join(sorted(set(fields)))
    return '{job="cloudflare-logpush", dataset="workers_trace_events"} | json'

panels = []
y = 0
pid = 1

# ============================================================
# ROW: Overview
# ============================================================
panels.append(row(pid, "Overview", y)); pid += 1; y += 1

panels.append(stat_panel(pid, "Requests",
    f"sum(count_over_time({http()} [$__range]))", "Requests", 0, y,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 1000}, {"color": "red", "value": 10000}],
    desc="Total HTTP requests across all zones over the selected time range.")); pid += 1

panels.append(stat_panel(pid, "Error Rate % (5xx)",
    f"sum(count_over_time({http('EdgeResponseStatus')} | EdgeResponseStatus >= 500 [$__range])) / sum(count_over_time({http()} [$__range])) * 100", "5xx %", 6, y,
    unit="percent", thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 5}],
    desc="Percentage of requests returning 5xx status codes (server errors) over the selected time range.")); pid += 1

panels.append(stat_panel(pid, "Cache Hit Ratio %",
    f"sum(count_over_time({http('CacheCacheStatus')} | CacheCacheStatus = `hit` [$__range])) / sum(count_over_time({http('CacheCacheStatus')} | CacheCacheStatus != `` [$__range])) * 100", "Cache Hit %", 12, y,
    unit="percent", thresholds=[{"color": "red", "value": None}, {"color": "yellow", "value": 50}, {"color": "green", "value": 80}],
    desc="Ratio of cache hits to all cacheable requests over the selected time range. Higher is better.")); pid += 1

panels.append(stat_panel(pid, "Firewall Events",
    f"sum(count_over_time({fw()} [$__range]))", "Events", 18, y,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 10}, {"color": "red", "value": 50}],
    desc="Total firewall events (blocks, challenges, logs) across all zones over the selected time range.")); pid += 1
y += 4

# Second overview row - more stats
panels.append(stat_panel(pid, "Leaked Credentials",
    f'sum(count_over_time({http("LeakedCredentialCheckResult")} | LeakedCredentialCheckResult != `` | LeakedCredentialCheckResult != `clean` [$__range]))', "Leaked", 0, y,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 10}],
    desc="Requests where Cloudflare detected leaked credentials (username/password) over the selected time range. Excludes 'clean' results.")); pid += 1

panels.append(stat_panel(pid, "High Risk WAF (score<20)",
    f"sum(count_over_time({http('WAFAttackScore')} | WAFAttackScore > 0 | WAFAttackScore <= 20 [$__range]))", "Attacks", 6, y,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 5}, {"color": "red", "value": 20}],
    desc="Requests with WAF attack score 1-20 (high risk of being an attack: SQLi, XSS, or RCE) over the selected time range.")); pid += 1

panels.append(stat_panel(pid, "Bot Traffic % (score<30)",
    f"sum(count_over_time({http('BotScore')} | BotScore > 0 | BotScore < 30 [$__range])) / sum(count_over_time({http('BotScore')} | BotScore > 0 [$__range])) * 100", "Bot %", 12, y,
    unit="percent", thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 20}, {"color": "red", "value": 50}],
    desc="Percentage of traffic classified as likely bot (BotScore 1-29) by Cloudflare Bot Management over the selected time range.")); pid += 1

panels.append(stat_panel(pid, "Worker Errors",
    f'sum(count_over_time({wk("Outcome")} | Outcome != `ok` [$__range]))', "Errors", 18, y,
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 10}],
    desc="Workers execution failures (exceptions, CPU exceeded, memory exceeded) over the selected time range.")); pid += 1
y += 4

# ============================================================
# ROW: HTTP Requests
# ============================================================
panels.append(row(pid, "HTTP Requests", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "Requests by Host", [
    t(f"sum by (ClientRequestHost) (count_over_time({http()} [$__auto]))", "{{ClientRequestHost}}")
], 0, y, desc="Request volume broken down by zone/hostname.")); pid += 1

panels.append(ts_panel(pid, "Edge Response Status Codes", [
    t(f"sum by (EdgeResponseStatus) (count_over_time({http('EdgeResponseStatus')} [$__auto]))", "{{EdgeResponseStatus}}")
], 12, y, overrides=[regex_color("5..", "red"), regex_color("4..", "orange"), regex_color("3..", "blue"), regex_color("2..", "green")],
    desc="HTTP response status codes returned by the Cloudflare edge to the client. Color-coded: 2xx=green, 3xx=blue, 4xx=orange, 5xx=red.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Requests by Method", [
    t(f"sum by (ClientRequestMethod) (count_over_time({http('ClientRequestMethod')} [$__auto]))", "{{ClientRequestMethod}}")
], 0, y, w=6, desc="Distribution of HTTP methods (GET, POST, PUT, DELETE, etc.).")); pid += 1

panels.append(bar_panel(pid, "Requests by Protocol", [
    t(f"sum by (ClientRequestProtocol) (count_over_time({http('ClientRequestProtocol')} [$__auto]))", "{{ClientRequestProtocol}}")
], 6, y, w=6, desc="HTTP protocol version distribution (HTTP/1.1, HTTP/2, HTTP/3).")); pid += 1

panels.append(bar_panel(pid, "Request Source (Eyeball vs Worker)", [
    t(f"sum by (ClientRequestSource) (count_over_time({http('ClientRequestSource')} [$__auto]))", "{{ClientRequestSource}}")
], 12, y, w=6, desc="Whether the request came from an end user (eyeball) or a Cloudflare Worker subrequest.")); pid += 1

panels.append(table_panel(pid, "Top Paths",
    f"approx_topk(20, sum by (ClientRequestPath) (count_over_time({http()} [$__range])))",
    "{{ClientRequestPath}}", 18, y, w=6,
    desc="Most requested URL paths. Uses approx_topk for probabilistic top-k over high-cardinality path data.")); pid += 1
y += 8

panels.append(table_panel(pid, "Top User Agents (Bot score < 30)",
    f'approx_topk(20, sum by (ClientRequestUserAgent) (count_over_time({http("ClientRequestUserAgent", "BotScore")} | BotScore > 0 | BotScore < 30 [$__range])))',
    "{{ClientRequestUserAgent}}", 0, y, w=12,
    desc="Most common User-Agent strings among requests classified as likely bots (BotScore 1-29).")); pid += 1

panels.append(table_panel(pid, "Top Error Paths (4xx+5xx)",
    f"approx_topk(20, sum by (ClientRequestPath) (count_over_time({http('EdgeResponseStatus')} | EdgeResponseStatus >= 400 [$__range])))",
    "{{ClientRequestPath}}", 12, y, w=12,
    desc="URL paths generating the most 4xx and 5xx errors. Useful for identifying broken endpoints or targeted attack paths.")); pid += 1
y += 8

# Edge Pathing — src:op describes how Cloudflare decided to handle the request
panels.append(ts_panel(pid, "Edge Pathing (request handling decisions)", [
    t(f'sum by (EdgePathingSrc, EdgePathingOp) (count_over_time({http("EdgePathingSrc", "EdgePathingOp")} | EdgePathingOp != `wl` [$__auto]))', "{{EdgePathingSrc}}:{{EdgePathingOp}}")
], 0, y,
    overrides=[color_override("user:ban", "red"), color_override("user:chl", "orange"),
               color_override("macro:ban", "dark-red"), color_override("macro:chl", "yellow"),
               color_override("filter:ban", "purple"), color_override("macro:temp_ok", "green")],
    desc="How Cloudflare decided to handle each request. src=decision source (user/macro/filter), op=action taken (ban/chl/wl). Allowlisted (wl) requests are excluded.")); pid += 1

panels.append(ts_panel(pid, "HTTP vs HTTPS", [
    t(f'sum by (ClientRequestScheme) (count_over_time({http("ClientRequestScheme")} [$__auto]))', "{{ClientRequestScheme}}")
], 12, y, overrides=[color_override("https", "green"), color_override("http", "red")],
    desc="Client request scheme distribution. HTTP traffic (red) may indicate misconfigured clients or lack of HTTPS redirect.")); pid += 1
y += 8

# Geography & client metadata (folded into HTTP Requests)
panels.append(geomap_panel(pid, "Requests by Country (Map)",
    f"sum by (ClientCountry) (count_over_time({http()} [$__range]))",
    "ClientCountry", 0, y, w=16, h=10,
    desc="World map showing request volume by client country (ISO 3166-1 Alpha-2). Bubble size = request count.")); pid += 1

panels.append(ts_panel(pid, "Requests by Country (Top 10)", [
    t(f"topk(10, sum by (ClientCountry) (count_over_time({http()} [$__auto])))", "{{ClientCountry}}")
], 16, y, w=8, h=10, overrides=country_name_overrides(),
    desc="Top 10 countries by request volume over time. Country codes are resolved to full names.")); pid += 1
y += 10

panels.append(ts_panel(pid, "Requests by Edge Colo (Top 10)", [
    t(f"topk(10, sum by (EdgeColoCode) (count_over_time({http()} [$__auto])))", "{{EdgeColoCode}}")
], 0, y, desc="Top 10 Cloudflare edge data centers (colos) serving requests. IATA airport codes (e.g., SIN=Singapore, NRT=Tokyo).")); pid += 1

panels.append(asn_lookup_table_panel(pid, "Top Client ASNs",
    f"topk(25, sum by (ClientASN) (count_over_time({http()} [$__range])))",
    12, y, w=12,
    desc="Top 25 Autonomous System Numbers by request count. ASN names resolved live from firewall_events ClientASNDescription field, with static fallback.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Client Device Type", [
    t(f'sum by (ClientDeviceType) (count_over_time({http("ClientDeviceType")} | ClientDeviceType != `` [$__auto]))', "{{ClientDeviceType}}")
], 0, y, w=8, desc="Device type classification (desktop, mobile, tablet) based on User-Agent parsing.")); pid += 1

panels.append(table_panel(pid, "Top Referers",
    f"approx_topk(25, sum by (ClientRequestReferer) (count_over_time({http('ClientRequestReferer')} | ClientRequestReferer != `` [$__range])))",
    "{{ClientRequestReferer}}", 8, y, w=16,
    desc="Top referring URLs. Empty referers are excluded. Uses approx_topk for high-cardinality referer data.")); pid += 1
y += 8

# SSL / TLS (folded into HTTP Requests)
panels.append(bar_panel(pid, "Client SSL Protocol", [
    t(f'sum by (ClientSSLProtocol) (count_over_time({http("ClientSSLProtocol")} | ClientSSLProtocol != `` | ClientSSLProtocol != `none` [$__auto]))', "{{ClientSSLProtocol}}")
], 0, y, w=8, desc="TLS protocol version used between client and Cloudflare edge (TLSv1.2, TLSv1.3).")); pid += 1

panels.append(bar_panel(pid, "Client SSL Cipher", [
    t(f'topk(15, sum by (ClientSSLCipher) (count_over_time({http("ClientSSLCipher")} | ClientSSLCipher != `` | ClientSSLCipher != `NONE` [$__auto])))', "{{ClientSSLCipher}}")
], 8, y, w=8, desc="TLS cipher suites negotiated between client and edge. Top 15 by request count.")); pid += 1

panels.append(bar_panel(pid, "Origin SSL Protocol", [
    t(f'sum by (OriginSSLProtocol) (count_over_time({http("OriginSSLProtocol")} | OriginSSLProtocol != `` | OriginSSLProtocol != `none` [$__auto]))', "{{OriginSSLProtocol}}")
], 16, y, w=8, desc="TLS protocol version used between Cloudflare edge and origin server.")); pid += 1
y += 8

panels.append(ts_panel(pid, "mTLS Authentication Status", [
    t(f'sum by (ClientMTLSAuthStatus) (count_over_time({http("ClientMTLSAuthStatus")} | ClientMTLSAuthStatus != `` | ClientMTLSAuthStatus != `unknown` [$__auto]))', "{{ClientMTLSAuthStatus}}")
], 0, y, w=12, overrides=[color_override("ok", "green"), color_override("absent", "blue"), color_override("untrusted", "red"), color_override("expired", "orange")],
    desc="Mutual TLS client certificate validation results. 'ok'=valid cert, 'absent'=no cert presented, 'untrusted'/'expired'=invalid cert.")); pid += 1

panels.append(ts_panel(pid, "Content Scan Results", [
    t(f'sum(count_over_time({http("ContentScanObjResults")} | ContentScanObjResults != `` | ContentScanObjResults != `[]` [$__auto]))', "Scanned Objects"),
], 12, y, w=6, desc="Cloudflare content scanning detections (malware, DLP) on request/response payloads.")); pid += 1

panels.append(ts_panel(pid, "O2O (Orange-to-Orange) Traffic", [
    t(f'sum(count_over_time({http("EdgeCFConnectingO2O")} | EdgeCFConnectingO2O = `true` [$__auto]))', "O2O Requests"),
], 18, y, w=6, desc="Requests proxied through another Cloudflare zone before reaching this zone (orange-to-orange).")); pid += 1
y += 8

# ============================================================
# ROW: Performance
# ============================================================
panels.append(row(pid, "Performance", y, desc="Request lifecycle timing: client-edge RTT, edge processing (WAF/cache), and edge-origin latency.")); pid += 1; y += 1

# Helper for percentile target sets on a metric field
def _perf_targets(field, ref_start="A", pre_filter=""):
    """Generate targets for avg, p50, p75, p90, p95, p99 of a field.
    pre_filter: optional LogQL filter inserted before unwrap (e.g. '| OriginResponseDurationMs > 0')."""
    refs = [chr(ord(ref_start) + i) for i in range(7)]
    h = http(field)
    pf = f" {pre_filter}" if pre_filter else ""
    return [
        t(f"sum(avg_over_time({h}{pf} | unwrap {field} [$__auto]))", "Avg", refs[0]),
        t(f"sum(quantile_over_time(0.50, {h}{pf} | unwrap {field} [$__auto]))", "p50 (median)", refs[1]),
        t(f"sum(quantile_over_time(0.75, {h}{pf} | unwrap {field} [$__auto]))", "p75", refs[2]),
        t(f"sum(quantile_over_time(0.90, {h}{pf} | unwrap {field} [$__auto]))", "p90", refs[3]),
        t(f"sum(quantile_over_time(0.95, {h}{pf} | unwrap {field} [$__auto]))", "p95", refs[4]),
        t(f"sum(quantile_over_time(0.99, {h}{pf} | unwrap {field} [$__auto]))", "p99", refs[5]),
    ]

perf_overrides = [color_override("Avg", "green"), color_override("p50 (median)", "blue"),
                  color_override("p75", "super-light-yellow"), color_override("p90", "yellow"),
                  color_override("p95", "orange"), color_override("p99", "red")]

# Request lifecycle breakdown — stacked view of where time is spent
# Use label_format to compute edge processing per log line (TTFB - origin) before
# aggregating, so that avg is taken over per-request differences — not avg(TTFB) - avg(origin)
# which can go negative when the sample populations differ.
# EdgeTimeToFirstByteMs is capped at 65535 (uint16) in Cloudflare's logging — when origin
# takes longer than ~65s, TTFB saturates while OriginResponseDurationMs keeps counting,
# producing nonsensical negative differences. Filter these out (<0.2% of traffic).
_h_lifecycle = http('EdgeTimeToFirstByteMs', 'OriginResponseDurationMs', 'ClientTCPRTTMs')
_ttfb_cap_filter = '| EdgeTimeToFirstByteMs < 65535'
_lf_edge_proc = '| label_format EdgeProcessingMs="{{ subf .EdgeTimeToFirstByteMs .OriginResponseDurationMs }}"'
panels.append(ts_panel(pid, "Request Lifecycle Breakdown (avg ms)", [
    t(f"sum(avg_over_time({_h_lifecycle} | unwrap ClientTCPRTTMs [$__auto]))", "Client \u2192 Edge (TCP RTT)"),
    t(f"sum(avg_over_time({_h_lifecycle} {_ttfb_cap_filter} {_lf_edge_proc} | unwrap EdgeProcessingMs [$__auto]))", "Edge Processing", "B"),
    t(f"sum(avg_over_time({_h_lifecycle} | OriginResponseDurationMs > 0 | unwrap OriginResponseDurationMs [$__auto]))", "Edge \u2192 Origin (total)", "C"),
], 0, y, w=24, unit="ms", stack=True, fill=50, legend_calcs=["mean", "lastNotNull"],
    overrides=[color_override("Client \u2192 Edge (TCP RTT)", "blue"),
               color_override("Edge Processing", "yellow"),
               color_override("Edge \u2192 Origin (total)", "orange")],
    desc="Stacked breakdown of where request time is spent. Client\u2192Edge = TCP RTT. Edge Processing = TTFB minus origin duration (WAF, bot checks, cache lookup), computed per-request via label_format. Excludes requests where EdgeTimeToFirstByteMs hit the uint16 cap (65535ms). Edge\u2192Origin = origin fetch time (cache hits excluded).")); pid += 1
y += 8

# Detailed percentile panels
panels.append(ts_panel(pid, "Edge TTFB — End to End (ms)",
    _perf_targets("EdgeTimeToFirstByteMs"),
    0, y, unit="ms", stack=False, fill=10, overrides=perf_overrides, legend_calcs=["mean", "lastNotNull"],
    desc="End-to-end Time To First Byte: from after TCP handshake to first byte sent to the client. Includes TLS negotiation, WAF processing, cache lookup, and origin response time.")); pid += 1

panels.append(ts_panel(pid, "Origin Response Duration (ms)",
    _perf_targets("OriginResponseDurationMs", pre_filter="| OriginResponseDurationMs > 0"),
    12, y, unit="ms", stack=False, fill=10, overrides=perf_overrides, legend_calcs=["mean", "lastNotNull"],
    desc="Total time for edge-to-origin request cycle: DNS resolution, TCP/TLS handshake, request send, and response receive. Includes Argo Smart Routing and Tiered Cache. Excludes cache hits (OriginResponseDurationMs=0).")); pid += 1
y += 8

panels.append(ts_panel(pid, "Client \u2192 Edge: TCP RTT (ms)",
    _perf_targets("ClientTCPRTTMs"),
    0, y, unit="ms", stack=False, fill=10, overrides=perf_overrides, legend_calcs=["mean", "lastNotNull"],
    desc="TCP round-trip time between the client and Cloudflare edge. Reflects geographic distance and network quality. Not affected by server-side processing.")); pid += 1

# Edge processing time (TTFB minus origin) — percentiles
# Use label_format with subf to compute the difference per log line, then aggregate.
# Filter out EdgeTimeToFirstByteMs >= 65535 (uint16 cap) — these produce garbage
# differences because TTFB is truncated while OriginResponseDurationMs is not.
_ep_h = http('EdgeTimeToFirstByteMs', 'OriginResponseDurationMs')
_ep_cap = '| EdgeTimeToFirstByteMs < 65535'
_ep_lf = '| label_format EdgeProcessingMs="{{ subf .EdgeTimeToFirstByteMs .OriginResponseDurationMs }}"'
_ep_refs = [chr(ord("A") + i) for i in range(6)]
panels.append(ts_panel(pid, "Edge Processing Time (ms)", [
    t(f"sum(avg_over_time({_ep_h} {_ep_cap} {_ep_lf} | unwrap EdgeProcessingMs [$__auto]))", "Avg", _ep_refs[0]),
    t(f"sum(quantile_over_time(0.50, {_ep_h} {_ep_cap} {_ep_lf} | unwrap EdgeProcessingMs [$__auto]))", "p50 (median)", _ep_refs[1]),
    t(f"sum(quantile_over_time(0.75, {_ep_h} {_ep_cap} {_ep_lf} | unwrap EdgeProcessingMs [$__auto]))", "p75", _ep_refs[2]),
    t(f"sum(quantile_over_time(0.90, {_ep_h} {_ep_cap} {_ep_lf} | unwrap EdgeProcessingMs [$__auto]))", "p90", _ep_refs[3]),
    t(f"sum(quantile_over_time(0.95, {_ep_h} {_ep_cap} {_ep_lf} | unwrap EdgeProcessingMs [$__auto]))", "p95", _ep_refs[4]),
    t(f"sum(quantile_over_time(0.99, {_ep_h} {_ep_cap} {_ep_lf} | unwrap EdgeProcessingMs [$__auto]))", "p99", _ep_refs[5]),
], 12, y, unit="ms", stack=False, fill=10, overrides=perf_overrides, legend_calcs=["mean", "lastNotNull"],
    desc="Per-request edge processing time: EdgeTimeToFirstByteMs minus OriginResponseDurationMs, computed per log line via label_format. Excludes requests where TTFB hit the uint16 cap (65535ms). Represents time spent on WAF rules, bot detection, cache lookup, and request routing at the edge.")); pid += 1
y += 8

# Origin connection timing breakdown (sub-components of OriginResponseDurationMs)
# Filter OriginResponseDurationMs > 0 to exclude cache hits where all sub-components are zero
_origin_timing = http('OriginDNSResponseTimeMs', 'OriginTCPHandshakeDurationMs', 'OriginTLSHandshakeDurationMs',
                       'OriginRequestHeaderSendDurationMs', 'OriginResponseHeaderReceiveDurationMs',
                       'OriginResponseDurationMs')
_origin_filter = '| OriginResponseDurationMs > 0'
panels.append(ts_panel(pid, "Edge \u2192 Origin Timing Breakdown (avg ms)", [
    t(f"sum(avg_over_time({_origin_timing} {_origin_filter} | unwrap OriginDNSResponseTimeMs [$__auto]))", "DNS Lookup"),
    t(f"sum(avg_over_time({_origin_timing} {_origin_filter} | unwrap OriginTCPHandshakeDurationMs [$__auto]))", "TCP Handshake", "B"),
    t(f"sum(avg_over_time({_origin_timing} {_origin_filter} | unwrap OriginTLSHandshakeDurationMs [$__auto]))", "TLS Handshake", "C"),
    t(f"sum(avg_over_time({_origin_timing} {_origin_filter} | unwrap OriginRequestHeaderSendDurationMs [$__auto]))", "Header Send", "D"),
    t(f"sum(avg_over_time({_origin_timing} {_origin_filter} | unwrap OriginResponseHeaderReceiveDurationMs [$__auto]))", "Header Receive", "E"),
], 0, y, unit="ms", stack=True, fill=50, legend_calcs=["mean", "lastNotNull"],
    overrides=[color_override("DNS Lookup", "blue"), color_override("TCP Handshake", "green"),
               color_override("TLS Handshake", "yellow"), color_override("Header Send", "orange"),
               color_override("Header Receive", "purple")],
    desc="Stacked sub-components of edge-to-origin time: DNS resolution, TCP handshake, TLS handshake, request header send, and response header receive. Excludes cache hits (OriginResponseDurationMs=0).")); pid += 1

panels.append(ts_panel(pid, "Edge \u2192 Origin by Host (avg ms)", [
    t(f"avg by (ClientRequestHost) (avg_over_time({http('OriginResponseDurationMs')} | OriginResponseDurationMs > 0 | unwrap OriginResponseDurationMs [$__auto]))", "{{ClientRequestHost}}")
], 12, y, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Average origin response duration per zone (cache hits excluded). Helps identify which hosts have slow origin servers.")); pid += 1
y += 8

# By host and by ASN breakdowns
panels.append(ts_panel(pid, "Edge TTFB by Host (avg ms)", [
    t(f"avg by (ClientRequestHost) (avg_over_time({http('EdgeTimeToFirstByteMs')} | unwrap EdgeTimeToFirstByteMs [$__auto]))", "{{ClientRequestHost}}")
], 0, y, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Average end-to-end TTFB per zone. Compare with origin duration to see how much time is edge overhead vs origin.")); pid += 1

panels.append(ts_panel(pid, "Client \u2192 Edge RTT by Host (avg ms)", [
    t(f"avg by (ClientRequestHost) (avg_over_time({http('ClientTCPRTTMs')} | unwrap ClientTCPRTTMs [$__auto]))", "{{ClientRequestHost}}")
], 12, y, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Average client TCP RTT per zone. Reflects the geographic distribution of each zone's audience.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Edge TTFB by ASN (avg ms, Top 10)", [
    t(f"topk(10, avg by (ClientASN) (avg_over_time({http('EdgeTimeToFirstByteMs')} | unwrap EdgeTimeToFirstByteMs [$__auto])))", "AS{{ClientASN}}")
], 0, y, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Average TTFB for the top 10 ASNs by latency. Identifies networks with consistently slow end-to-end performance.")); pid += 1

panels.append(ts_panel(pid, "Origin Response by Client ASN (avg ms, Top 10)", [
    t(f"topk(10, avg by (ClientASN) (avg_over_time({http('OriginResponseDurationMs')} | OriginResponseDurationMs > 0 | unwrap OriginResponseDurationMs [$__auto])))", "AS{{ClientASN}}")
], 12, y, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Average origin response duration grouped by the requesting client's ASN (cache hits excluded). No OriginASN field exists in Cloudflare Logpush. High values for specific ASNs may indicate those networks generate more cache misses or request heavier endpoints.")); pid += 1
y += 8

# Origin error rate by IP
panels.append(table_panel(pid, "Origin Error Rate by IP (5xx)",
    f"topk(20, sum by (OriginIP) (count_over_time({http('OriginIP', 'OriginResponseStatus')} | OriginResponseStatus >= 500 [$__range])))",
    "{{OriginIP}}", 0, y, w=12,
    desc="Origin server IPs returning the most 5xx errors. Helps identify unhealthy origin instances.")); pid += 1

panels.append(ts_panel(pid, "Origin vs Edge Status Mismatch", [
    t(f'topk(10, sum by (EdgeResponseStatus, OriginResponseStatus) (count_over_time({http("EdgeResponseStatus", "OriginResponseStatus")} | OriginResponseStatus > 0 | EdgeResponseStatus != OriginResponseStatus [$__auto])))', "edge={{EdgeResponseStatus}} \u2192 origin={{OriginResponseStatus}}")
], 12, y, stack=False, fill=10,
    desc="Requests where the edge status code differs from origin. Grouped by edge\u2192origin status pair, filtered to origin-fetched requests only. Shows edge transformations like 5xx\u21924xx (custom error pages) or 2xx\u21925xx (stale cache served).")); pid += 1
y += 8

# ============================================================
# ROW: Cache Performance
# ============================================================
panels.append(row(pid, "Cache Performance", y)); pid += 1; y += 1

cache_overrides = [color_override("hit", "green"), color_override("miss", "red"), color_override("dynamic", "blue"), color_override("expired", "orange")]

panels.append(ts_panel(pid, "Cache Status Over Time", [
    t(f"sum by (CacheCacheStatus) (count_over_time({http('CacheCacheStatus')} | CacheCacheStatus != `` [$__auto]))", "{{CacheCacheStatus}}")
], 0, y, overrides=cache_overrides,
    desc="Cache status distribution over time: hit, miss, dynamic (uncacheable), expired, revalidated, etc.")); pid += 1

panels.append(pie_panel(pid, "Cache Status Distribution",
    f"sum by (CacheCacheStatus) (count_over_time({http('CacheCacheStatus')} | CacheCacheStatus != `` [$__auto]))",
    "{{CacheCacheStatus}}", 12, y, overrides=cache_overrides,
    desc="Overall cache status proportions. 'dynamic' = not eligible for caching. 'hit' = served from cache.")); pid += 1

panels.append(ts_panel(pid, "Cache Hit Ratio Over Time", [
    t(f"sum(count_over_time({http('CacheCacheStatus')} | CacheCacheStatus = `hit` [$__auto])) / sum(count_over_time({http('CacheCacheStatus')} | CacheCacheStatus != `` [$__auto])) * 100", "Hit %")
], 18, y, w=6, unit="percent", stack=False, fill=10,
    desc="Cache hit ratio (%) over time. Only includes cacheable requests (excludes empty cache status).")); pid += 1
y += 8

# Cache hit ratio per host and per path
panels.append(ts_panel(pid, "Cache Hit Ratio by Host (%)", [
    t(f"sum by (ClientRequestHost) (count_over_time({http('CacheCacheStatus')} | CacheCacheStatus = `hit` [$__auto])) / sum by (ClientRequestHost) (count_over_time({http('CacheCacheStatus')} | CacheCacheStatus != `` [$__auto])) * 100", "{{ClientRequestHost}}")
], 0, y, unit="percent", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Cache hit ratio per zone. Helps identify which zones benefit most from caching.")); pid += 1

panels.append(table_panel(pid, "Cache Hit Ratio by Path (Top 10, %)",
    f"approx_topk(10, sum by (ClientRequestPath) (count_over_time({http('CacheCacheStatus')} | CacheCacheStatus = `hit` [$__range])) / sum by (ClientRequestPath) (count_over_time({http('CacheCacheStatus')} | CacheCacheStatus != `` [$__range])) * 100)",
    "{{ClientRequestPath}}", 12, y,
    extra_overrides=[
        {"matcher": {"id": "byName", "options": "ClientRequestPath"}, "properties": [{"id": "custom.width", "value": 350}]},
        {"matcher": {"id": "byName", "options": "Value #A"}, "properties": [
            {"id": "displayName", "value": "Hit %"},
            {"id": "unit", "value": "percent"},
            {"id": "custom.width", "value": 100},
            {"id": "custom.cellOptions", "value": {"mode": "basic", "type": "gauge", "valueDisplayMode": "text"}},
        ]},
    ],
    desc="Cache hit ratio for the top 10 paths by cacheability (instant query over selected range). Uses approx_topk to avoid high-cardinality series explosion.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Tiered Cache Fill Rate", [
    t(f'sum(count_over_time({http("CacheTieredFill")} | CacheTieredFill = `true` [$__auto]))', "Tiered Fill"),
    t(f'sum(count_over_time({http("CacheReserveUsed")} | CacheReserveUsed = `true` [$__auto]))', "Cache Reserve", "B"),
], 0, y, w=8, desc="Requests served via Tiered Cache (upper-tier colo) or Cache Reserve (persistent storage).")); pid += 1

panels.append(ts_panel(pid, "Edge Response Bytes", [
    t(f"sum(sum_over_time({http('EdgeResponseBytes')} | unwrap EdgeResponseBytes [$__auto]))", "Total Bytes")
], 8, y, w=8, unit="bytes", stack=False, fill=10,
    desc="Total bytes sent from edge to clients over time.")); pid += 1

panels.append(ts_panel(pid, "Cache Response Bytes", [
    t(f"sum(sum_over_time({http('CacheResponseBytes')} | unwrap CacheResponseBytes [$__auto]))", "Cached Bytes")
], 16, y, w=8, unit="bytes", stack=False, fill=10,
    desc="Bytes served from cache over time. Compare with edge response bytes to see bandwidth savings.")); pid += 1
y += 8

panels.append(pie_panel(pid, "Content Type Distribution",
    f"topk(10, sum by (EdgeResponseContentType) (count_over_time({http('EdgeResponseContentType')} | EdgeResponseContentType != `` [$__auto])))",
    "{{EdgeResponseContentType}}", 0, y, w=8, h=10,
    desc="Top 10 response content types (text/html, image/png, application/json, etc.).")); pid += 1

panels.append(ts_panel(pid, "Compression Ratio (avg)", [
    t(f"sum(avg_over_time({http('EdgeResponseCompressionRatio')} | unwrap EdgeResponseCompressionRatio [$__auto]))", "Avg Ratio")
], 8, y, w=8, unit="short", stack=False, fill=10,
    desc="Average compression ratio of edge responses. Higher = more compression. 1.0 = no compression.")); pid += 1

panels.append(ts_panel(pid, "Smart Route / Argo Usage", [
    t(f'sum(count_over_time({http("SmartRouteColoID")} | SmartRouteColoID > 0 [$__auto]))', "Smart Routed"),
    t(f'sum(count_over_time({http("SmartRouteColoID")} | SmartRouteColoID = 0 [$__auto]))', "Direct", "B"),
], 16, y, w=8, overrides=[color_override("Smart Routed", "green"), color_override("Direct", "blue")],
    desc="Requests routed via Argo Smart Routing (optimized path) vs direct edge-to-origin. SmartRouteColoID > 0 indicates smart routing.")); pid += 1
y += 10

# ============================================================
# ROW: Security & Firewall
# ============================================================
panels.append(row(pid, "Security & Firewall", y)); pid += 1; y += 1

fw_action_overrides = [color_override("block", "red"), color_override("challenge", "orange"), color_override("managedchallenge", "yellow"), color_override("jschallenge", "purple"), color_override("log", "blue"), color_override("skip", "green")]

panels.append(ts_panel(pid, "Firewall Events by Action", [
    t(f"sum by (Action) (count_over_time({fw('Action')} [$__auto]))", "{{Action}}")
], 0, y, overrides=fw_action_overrides,
    desc="Firewall events grouped by action taken: block, challenge, managedchallenge, jschallenge, log, skip, bypass, allow.")); pid += 1

panels.append(ts_panel(pid, "Firewall Events by Source", [
    t(f"sum by (Source) (count_over_time({fw('Source')} [$__auto]))", "{{Source}}")
], 12, y, desc="Which Cloudflare security product triggered the firewall event (WAF, rate limiting, IP access rules, etc.).")); pid += 1
y += 8

panels.append(table_panel(pid, "Top Firewall Client IPs",
    f"topk(20, sum by (ClientIP) (count_over_time({fw()} [$__range])))",
    "{{ClientIP}}", 0, y,
    desc="Client IPs triggering the most firewall events. Candidates for IP access rules.")); pid += 1

panels.append(table_panel(pid, "Top Firewall Rules",
    f"topk(20, sum by (RuleID, Description) (count_over_time({fw('RuleID', 'Description')} [$__range])))",
    "{{RuleID}} - {{Description}}", 8, y,
    desc="Most-triggered firewall rules by event count. Review rules with high 'log' counts for potential escalation to 'block'.")); pid += 1

panels.append(ts_panel(pid, "Firewall Events by Host", [
    t(f"sum by (ClientRequestHost) (count_over_time({fw()} [$__auto]))", "{{ClientRequestHost}}")
], 16, y, w=8, desc="Firewall event distribution across zones. Identifies which hosts are most targeted.")); pid += 1
y += 8

# Firewall events by country (geomap)
panels.append(geomap_panel(pid, "Firewall Events by Country (Map)",
    f"sum by (ClientCountry) (count_over_time({fw('ClientCountry')} [$__range]))",
    "ClientCountry", 0, y, w=16, h=10,
    desc="Geographic distribution of firewall events. Highlights countries generating the most blocked/challenged requests.")); pid += 1

panels.append(ts_panel(pid, "Firewall Events by Country (Top 10)", [
    t(f"topk(10, sum by (ClientCountry) (count_over_time({fw('ClientCountry')} [$__auto])))", "{{ClientCountry}}")
], 16, y, w=8, h=10, overrides=country_name_overrides(),
    desc="Top 10 countries by firewall event volume over time.")); pid += 1
y += 10

panels.append(table_panel(pid, "Top Attacked Paths",
    f"topk(20, sum by (ClientRequestPath) (count_over_time({fw('ClientRequestPath')} [$__range])))",
    "{{ClientRequestPath}}", 0, y, w=8,
    desc="URL paths triggering the most firewall events. Identifies commonly targeted endpoints (login, admin, API routes).")); pid += 1

panels.append(table_panel(pid, "Top Attacking User Agents",
    f"topk(20, sum by (UserAgent) (count_over_time({fw('UserAgent')} | UserAgent != `` [$__range])))",
    "{{UserAgent}}", 8, y, w=8,
    desc="User-Agent strings triggering the most firewall events. Common attack tools use distinctive UA strings.")); pid += 1

panels.append(fw_asn_table_panel(pid, "Top Attacking ASNs",
    f"topk(20, sum by (ClientASN, ClientASNDescription) (count_over_time({fw('ClientASN', 'ClientASNDescription')} [$__range])))",
    16, y, w=8,
    desc="Autonomous System Numbers generating the most firewall events. ASN names resolved live from Cloudflare ClientASNDescription field.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Firewall Events by HTTP Method", [
    t(f"sum by (ClientRequestMethod) (count_over_time({fw('ClientRequestMethod')} [$__auto]))", "{{ClientRequestMethod}}")
], 0, y, w=8, desc="HTTP methods in firewall events. POST/PUT heavy = credential stuffing or injection attacks. Unusual methods (OPTIONS, TRACE) may indicate reconnaissance.")); pid += 1

panels.append(ts_panel(pid, "Challenge Solve Rate", [
    t(f'sum(count_over_time({fw("Action")} | Action =~ "managedchallenge|challenge|jschallenge" [$__auto]))', "Challenges Issued"),
    t(f'sum(count_over_time({http("SecurityAction")} | SecurityAction =~ "managed_challenge|challenge|js_challenge" [$__auto]))', "Challenges (HTTP side)", "B"),
], 8, y, w=8, overrides=[color_override("Challenges Issued", "orange"), color_override("Challenges (HTTP side)", "yellow")],
    desc="Volume of challenge actions issued over time. Compare firewall_events challenges vs http_requests challenges to understand solve/fail rates.")); pid += 1

panels.append(pie_panel(pid, "Firewall Action Distribution",
    f"sum by (Action) (count_over_time({fw('Action')} [$__range]))",
    "{{Action}}", 16, y, w=8, overrides=fw_action_overrides,
    desc="Overall distribution of firewall actions. Review 'log' proportion — high log-only rates may indicate rules that should be escalated.")); pid += 1
y += 8

# ============================================================
# ROW: API & Rate Limiting
# ============================================================
panels.append(row(pid, "API & Rate Limiting", y, desc="Rate limiting, L7 DDoS, API Shield, and other product-specific firewall events. Uses the firewall_events Source field to filter by security product.")); pid += 1; y += 1

panels.append(ts_panel(pid, "Rate Limiting Events", [
    t(f'sum by (Action) (count_over_time({fw("Source", "Action")} | Source = `ratelimit` [$__auto]))', "{{Action}}")
], 0, y, overrides=fw_action_overrides,
    desc="Firewall events from rate limiting rules, grouped by action. Source=ratelimit in firewall_events.")); pid += 1

panels.append(ts_panel(pid, "L7 DDoS Mitigations", [
    t(f'sum by (Action) (count_over_time({fw("Source", "Action")} | Source = `l7ddos` [$__auto]))', "{{Action}}")
], 12, y, overrides=[color_override("block", "red"), color_override("managedchallenge", "orange"), color_override("log", "blue")],
    desc="L7 DDoS protection events. Cloudflare automatically detects and mitigates application-layer DDoS attacks. Source=l7ddos in firewall_events.")); pid += 1
y += 8

panels.append(ts_panel(pid, "API Shield Events", [
    t(f'sum by (Source) (count_over_time({fw("Source")} | Source =~ "apishield.*" [$__auto]))', "{{Source}}")
], 0, y, desc="API Shield events including schema validation, JWT token validation, and sequence mitigation. Covers all apishield* sources.")); pid += 1

panels.append(ts_panel(pid, "Bot Management Events", [
    t(f'sum by (Action) (count_over_time({fw("Source", "Action")} | Source =~ "botfight|botmanagement" [$__auto]))', "{{Action}}")
], 12, y, overrides=fw_action_overrides,
    desc="Bot Fight Mode and Bot Management firewall events. These are separate from the BotScore analysis — this shows enforcement actions.")); pid += 1
y += 8

panels.append(table_panel(pid, "Rate Limited Paths",
    f'topk(20, sum by (ClientRequestPath) (count_over_time({fw("Source", "ClientRequestPath")} | Source = `ratelimit` [$__range])))',
    "{{ClientRequestPath}}", 0, y, w=8,
    desc="URL paths most frequently hit by rate limiting rules. Review for false positives on legitimate high-traffic endpoints.")); pid += 1

panels.append(table_panel(pid, "Rate Limited IPs",
    f'topk(20, sum by (ClientIP) (count_over_time({fw("Source")} | Source = `ratelimit` [$__range])))',
    "{{ClientIP}}", 8, y, w=8,
    desc="Client IPs most frequently rate limited. Persistent offenders are candidates for IP block rules.")); pid += 1

panels.append(ts_panel(pid, "Security Product Coverage", [
    t(f'sum by (Source) (count_over_time({fw("Source")} [$__auto]))', "{{Source}}")
], 16, y, w=8, desc="All firewall events by security product source. Shows which Cloudflare security products are actively triggering. Full list: waf, firewallManaged, firewallCustom, ratelimit, l7ddos, botFight, ip, country, etc.")); pid += 1
y += 8

panels.append(ts_panel(pid, "WAF Rule Types (Managed vs Custom)", [
    t(f'sum(count_over_time({fw("Source")} | Source = `waf` [$__auto]))', "WAF (legacy)"),
    t(f'sum(count_over_time({fw("Source")} | Source = `firewallmanaged` [$__auto]))', "Managed Ruleset", "B"),
    t(f'sum(count_over_time({fw("Source")} | Source = `firewallcustom` [$__auto]))', "Custom Rules", "C"),
], 0, y, overrides=[color_override("WAF (legacy)", "purple"), color_override("Managed Ruleset", "orange"), color_override("Custom Rules", "blue")],
    desc="Comparison of WAF event sources: legacy WAF rules, managed rulesets (OWASP/Cloudflare), and custom WAF rules.")); pid += 1

panels.append(ts_panel(pid, "IP/Country/ASN Access Rules", [
    t(f'sum by (Source) (count_over_time({fw("Source")} | Source =~ "ip|iprange|asn|country|zonelockdown|uablock" [$__auto]))', "{{Source}}")
], 12, y, desc="Access control rule events: IP access rules, IP range, ASN rules, country blocks, zone lockdown, and UA blocking.")); pid += 1
y += 8

# ============================================================
# ROW: WAF Attack Analysis
# ============================================================
panels.append(row(pid, "WAF Attack Analysis", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "WAF Attack Score Buckets", [
    t(f"sum(count_over_time({http('WAFAttackScore')} | WAFAttackScore > 0 | WAFAttackScore <= 20 [$__auto]))", "High Risk (1-20)"),
    t(f"sum(count_over_time({http('WAFAttackScore')} | WAFAttackScore > 20 | WAFAttackScore <= 50 [$__auto]))", "Medium Risk (21-50)", "B"),
    t(f"sum(count_over_time({http('WAFAttackScore')} | WAFAttackScore > 50 [$__auto]))", "Low Risk (51+)", "C"),
], 0, y, overrides=[color_override("High Risk (1-20)", "red"), color_override("Medium Risk (21-50)", "orange"), color_override("Low Risk (51+)", "green")],
    desc="Cloudflare WAF attack score distribution. Score 1-20 = high confidence attack. Score 51+ = likely legitimate. Score 0 = not evaluated.")); pid += 1

panels.append(ts_panel(pid, "Attack Type Breakdown (score <= 20)", [
    t(f"sum(count_over_time({http('WAFSQLiAttackScore')} | WAFSQLiAttackScore > 0 | WAFSQLiAttackScore <= 20 [$__auto]))", "SQLi"),
    t(f"sum(count_over_time({http('WAFXSSAttackScore')} | WAFXSSAttackScore > 0 | WAFXSSAttackScore <= 20 [$__auto]))", "XSS", "B"),
    t(f"sum(count_over_time({http('WAFRCEAttackScore')} | WAFRCEAttackScore > 0 | WAFRCEAttackScore <= 20 [$__auto]))", "RCE", "C"),
], 12, y, overrides=[color_override("SQLi", "red"), color_override("XSS", "orange"), color_override("RCE", "purple")],
    desc="High-risk attacks (score <= 20) broken down by type: SQL injection, cross-site scripting, remote code execution.")); pid += 1
y += 8

# Unmitigated attack traffic
panels.append(table_panel(pid, "Unmitigated Attacks (WAF score<=20, not blocked)",
    f'approx_topk(20, sum by (ClientRequestPath, ClientRequestHost) (count_over_time({http("WAFAttackScore", "SecurityAction")} | WAFAttackScore > 0 | WAFAttackScore <= 20 | SecurityAction = `` [$__range])))',
    "{{ClientRequestHost}}{{ClientRequestPath}}", 0, y, w=12,
    desc="GAP ANALYSIS: High-risk attack traffic (WAF score 1-20) that was NOT blocked or challenged. Empty SecurityAction = no mitigation applied. Review these paths for WAF rule gaps.")); pid += 1

panels.append(table_panel(pid, "Security Rule Efficacy",
    f'topk(30, sum by (SecurityRuleID, SecurityRuleDescription, SecurityAction) (count_over_time({http("SecurityRuleID", "SecurityRuleDescription", "SecurityAction")} | SecurityRuleID != `` [$__range])))',
    "{{SecurityRuleID}} {{SecurityRuleDescription}} [{{SecurityAction}}]", 12, y, w=12,
    desc="All triggered security rules with their action. Review 'log' actions for rules that should be escalated to 'block'.")); pid += 1
y += 8

# Security sources and actions
panels.append(ts_panel(pid, "Security Actions on HTTP Requests", [
    t(f'sum by (SecurityAction) (count_over_time({http("SecurityAction")} | SecurityAction != `` [$__auto]))', "{{SecurityAction}}")
], 0, y, overrides=[color_override("block", "red"), color_override("challenge", "orange"), color_override("managed_challenge", "yellow"), color_override("js_challenge", "purple"), color_override("log", "blue"), color_override("skip", "green")],
    desc="All security actions applied to HTTP requests over time. Sourced from the http_requests dataset SecurityAction field (uses underscored values: block, managed_challenge, js_challenge, challenge).")); pid += 1

panels.append(ts_panel(pid, "Client IP Classification", [
    t(f'sum by (ClientIPClass) (count_over_time({http("ClientIPClass")} | ClientIPClass != `noRecord` | ClientIPClass != `` [$__auto]))', "{{ClientIPClass}}")
], 12, y, overrides=[color_override("badHost", "red"), color_override("scan", "orange"), color_override("tor", "purple"), color_override("searchEngine", "green"), color_override("monitoringService", "blue")],
    desc="Cloudflare IP threat intelligence classification. badHost = known malicious, scan = scanner, tor = Tor exit node, searchEngine = legitimate crawler.")); pid += 1
y += 8

# ============================================================
# ROW: Threat Intelligence
# ============================================================
panels.append(row(pid, "Threat Intelligence", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "Leaked Credential Check Results", [
    t(f'sum by (LeakedCredentialCheckResult) (count_over_time({http("LeakedCredentialCheckResult")} | LeakedCredentialCheckResult != `` | LeakedCredentialCheckResult != `clean` [$__auto]))', "{{LeakedCredentialCheckResult}}")
], 0, y, overrides=[color_override("password_leaked", "red"), color_override("username_and_password_leaked", "dark-red"), color_override("username_leaked", "orange"), color_override("username_password_similar", "yellow")],
    desc="Cloudflare Leaked Credential Check results. Detects credentials found in known breach databases. MITRE ATT&CK T1110.004.")); pid += 1

panels.append(ts_panel(pid, "Fraud Detection", [
    t(f'sum(count_over_time({http("FraudAttack")} | FraudAttack != `` [$__auto]))', "Fraud Attacks"),
], 12, y, desc="Cloudflare fraud detection signals on incoming requests.")); pid += 1
y += 8

panels.append(table_panel(pid, "Top Talkers (by request count)",
    f"approx_topk(25, sum by (ClientIP) (count_over_time({http()} [$__range])))",
    "{{ClientIP}}", 0, y, w=12,
    desc="Top 25 client IPs by total request volume. High-volume IPs may be bots, scrapers, or DDoS sources.")); pid += 1

panels.append(table_panel(pid, "Suspicious UAs (BotScore < 30)",
    f'approx_topk(20, sum by (ClientRequestUserAgent) (count_over_time({http("ClientRequestUserAgent", "BotScore")} | BotScore > 0 | BotScore < 30 [$__range])))',
    "{{ClientRequestUserAgent}}", 12, y, w=12,
    desc="User-Agent strings with low bot scores (1-29 = likely automated). Identify scraping tools, vulnerability scanners, and fake browsers.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Fraud Detection Tags", [
    t(f'sum by (FraudDetectionTags) (count_over_time({http("FraudDetectionTags")} | FraudDetectionTags != `` | FraudDetectionTags != `[]` [$__auto]))', "{{FraudDetectionTags}}")
], 0, y, desc="Cloudflare Turnstile and fraud detection tag distribution over time. Tags identify categories of fraudulent behavior.")); pid += 1

panels.append(table_panel(pid, "Fraud Detection IDs",
    f'topk(20, sum by (FraudDetectionIDs) (count_over_time({http("FraudDetectionIDs")} | FraudDetectionIDs != `` | FraudDetectionIDs != `[]` [$__range])))',
    "{{FraudDetectionIDs}}", 12, y, w=12,
    desc="Specific fraud detection rule IDs triggered. Each ID maps to a specific detection signal in Cloudflare's fraud detection system.")); pid += 1
y += 8

panels.append(table_panel(pid, "Top Client Regions (subnational)",
    f'topk(25, sum by (ClientRegionCode) (count_over_time({http("ClientRegionCode")} | ClientRegionCode != `` [$__range])))',
    "{{ClientRegionCode}}", 0, y, w=12,
    desc="Top client regions (ISO 3166-2 subdivision codes, e.g., US-CA, GB-LND). Provides subnational geographic granularity beyond country level.")); pid += 1

panels.append(table_panel(pid, "Firewall Events: Top Request URIs",
    f'topk(20, sum by (ClientRequestPath, ClientRequestQuery) (count_over_time({fw("ClientRequestPath", "ClientRequestQuery")} | ClientRequestQuery != `` [$__range])))',
    "{{ClientRequestPath}}?{{ClientRequestQuery}}", 12, y, w=12,
    desc="Top full request URIs (path + query string) in firewall events. Query strings may reveal injection attempts (SQLi, XSS payloads).")); pid += 1
y += 8

panels.append(table_panel(pid, "Geo Anomaly: Sensitive Paths by Country",
    f'approx_topk(20, sum by (ClientCountry, ClientRequestPath) (count_over_time({http()} | ClientRequestPath =~ `.*(admin|login|wp-login|phpmyadmin|xmlrpc|eval|exec|api/auth).*` [$__range])))',
    "{{ClientCountry}} {{ClientRequestPath}}", 0, y, w=24,
    extra_overrides=[country_value_mappings_override("ClientCountry")],
    desc="Access to sensitive paths (admin, login, wp-login, phpmyadmin, etc.) grouped by country. Unexpected countries accessing admin paths may indicate reconnaissance. MITRE ATT&CK T1595.")); pid += 1
y += 8

# ============================================================
# ROW: Bot Analysis
# ============================================================
panels.append(row(pid, "Bot Analysis", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "Bot Score Distribution", [
    t(f"sum(count_over_time({http('BotScore')} | BotScore > 0 | BotScore < 30 [$__auto]))", "Likely Bot (1-29)"),
    t(f"sum(count_over_time({http('BotScore')} | BotScore >= 30 | BotScore < 50 [$__auto]))", "Possibly Bot (30-49)", "B"),
    t(f"sum(count_over_time({http('BotScore')} | BotScore >= 50 [$__auto]))", "Likely Human (50+)", "C"),
], 0, y, overrides=[color_override("Likely Bot (1-29)", "red"), color_override("Possibly Bot (30-49)", "orange"), color_override("Likely Human (50+)", "green")],
    desc="Cloudflare Bot Management score distribution. 1-29 = likely automated, 30-49 = ambiguous, 50-99 = likely human. Score 0 = not computed.")); pid += 1

panels.append(ts_panel(pid, "Bot Score Source Engine", [
    t(f'sum by (BotScoreSrc) (count_over_time({http("BotScoreSrc")} | BotScoreSrc != `` | BotScoreSrc != `Not Computed` [$__auto]))', "{{BotScoreSrc}}")
], 12, y, desc="Which detection engine computed the bot score: Machine Learning, Heuristics, JS Fingerprinting, or Behavioral Analysis.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Verified Bot Categories", [
    t(f'sum by (VerifiedBotCategory) (count_over_time({http("VerifiedBotCategory")} | VerifiedBotCategory != `` [$__auto]))', "{{VerifiedBotCategory}}")
], 0, y, desc="Known legitimate bots verified by Cloudflare (Googlebot, Bingbot, etc.) grouped by category.")); pid += 1

panels.append(ts_panel(pid, "JS Detection Pass/Fail", [
    t(f'sum by (JSDetectionPassed) (count_over_time({http("JSDetectionPassed")} | JSDetectionPassed != `` [$__auto]))', "{{JSDetectionPassed}}")
], 12, y, overrides=[color_override("passed", "green"), color_override("failed", "red"), color_override("missing", "orange")],
    desc="JavaScript fingerprinting challenge results. 'failed' = client did not execute JS (likely headless bot). 'missing' = challenge not served.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Bot Tags Distribution", [
    t(f'sum by (BotTags) (count_over_time({http("BotTags")} | BotTags != `` | BotTags != `[]` [$__auto]))', "{{BotTags}}")
], 0, y, w=12, desc="Cloudflare Bot Management tags assigned to requests. Tags provide additional classification detail beyond the numeric BotScore (e.g., 'likely_automated', 'verified_bot').")); pid += 1

panels.append(table_panel(pid, "Bot Detection Tags Detail",
    f'topk(25, sum by (BotDetectionTags) (count_over_time({http("BotDetectionTags")} | BotDetectionTags != `` | BotDetectionTags != `[]` [$__range])))',
    "{{BotDetectionTags}}", 12, y, w=12,
    desc="Detailed bot detection signals. BotDetectionTags provides granular information about why a request was classified as bot traffic.")); pid += 1
y += 8

panels.append(table_panel(pid, "Top JA4 TLS Fingerprints",
    f'approx_topk(25, sum by (JA4) (count_over_time({http()} | JA4 != `` [$__range])))',
    "{{JA4}}", 0, y, w=12,
    desc="Top JA4 TLS fingerprints. JA4 identifies TLS client implementations (browsers, bots, libraries). Same fingerprint = same TLS stack.")); pid += 1

panels.append(table_panel(pid, "Top JA3 Hashes",
    f'approx_topk(25, sum by (JA3Hash) (count_over_time({http("JA3Hash")} | JA3Hash != `` [$__range])))',
    "{{JA3Hash}}", 12, y, w=12,
    desc="Top JA3 TLS fingerprint hashes. Legacy fingerprinting method (predecessor to JA4). Useful for identifying known malicious TLS implementations.")); pid += 1
y += 8

# ============================================================
# ROW: Request & Response Size
# ============================================================
panels.append(row(pid, "Request & Response Size", y, desc="Request and response payload size analysis. Identifies large uploads, oversized responses, and bandwidth consumption patterns.")); pid += 1; y += 1

panels.append(ts_panel(pid, "Client Request Bytes (avg)", [
    t(f"sum(avg_over_time({http('ClientRequestBytes')} | unwrap ClientRequestBytes [$__auto]))", "Avg Request Size"),
    t(f"sum(quantile_over_time(0.95, {http('ClientRequestBytes')} | unwrap ClientRequestBytes [$__auto]))", "p95 Request Size", "B"),
], 0, y, unit="bytes", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    overrides=[color_override("Avg Request Size", "green"), color_override("p95 Request Size", "orange")],
    desc="Average and p95 client request body size in bytes. Large requests may indicate file uploads, API payloads, or abuse.")); pid += 1

panels.append(ts_panel(pid, "Edge Response Body Bytes (avg)", [
    t(f"sum(avg_over_time({http('EdgeResponseBodyBytes')} | unwrap EdgeResponseBodyBytes [$__auto]))", "Avg Response Body"),
    t(f"sum(quantile_over_time(0.95, {http('EdgeResponseBodyBytes')} | unwrap EdgeResponseBodyBytes [$__auto]))", "p95 Response Body", "B"),
], 12, y, unit="bytes", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    overrides=[color_override("Avg Response Body", "blue"), color_override("p95 Response Body", "orange")],
    desc="Average and p95 edge response body size. Excludes headers. Large responses may indicate unoptimized images, large API payloads, or data exfiltration.")); pid += 1
y += 8

panels.append(table_panel(pid, "Largest Uploads by Path (avg request bytes)",
    f"topk(20, avg by (ClientRequestPath) (avg_over_time({http('ClientRequestBytes')} | ClientRequestBytes > 10000 | unwrap ClientRequestBytes [$__range])))",
    "{{ClientRequestPath}}", 0, y, w=12,
    extra_overrides=[
        {"matcher": {"id": "byName", "options": "Value #A"}, "properties": [
            {"id": "displayName", "value": "Avg Bytes"},
            {"id": "unit", "value": "bytes"},
            {"id": "custom.width", "value": 120},
            {"id": "custom.cellOptions", "value": {"mode": "basic", "type": "gauge", "valueDisplayMode": "text"}},
        ]},
    ],
    desc="Paths receiving the largest request payloads (>10KB average). Identifies file upload endpoints and potential abuse vectors.")); pid += 1

panels.append(table_panel(pid, "Largest Responses by Path (avg response bytes)",
    f"topk(20, avg by (ClientRequestPath) (avg_over_time({http('EdgeResponseBodyBytes')} | EdgeResponseBodyBytes > 100000 | unwrap EdgeResponseBodyBytes [$__range])))",
    "{{ClientRequestPath}}", 12, y, w=12,
    extra_overrides=[
        {"matcher": {"id": "byName", "options": "Value #A"}, "properties": [
            {"id": "displayName", "value": "Avg Bytes"},
            {"id": "unit", "value": "bytes"},
            {"id": "custom.width", "value": 120},
            {"id": "custom.cellOptions", "value": {"mode": "basic", "type": "gauge", "valueDisplayMode": "text"}},
        ]},
    ],
    desc="Paths serving the largest responses (>100KB average). Candidates for compression, CDN caching, or image optimization.")); pid += 1
y += 8

panels.append(ts_panel(pid, "Total Bandwidth (Request + Response)", [
    t(f"sum(sum_over_time({http('ClientRequestBytes')} | unwrap ClientRequestBytes [$__auto]))", "Request Bytes (inbound)"),
    t(f"sum(sum_over_time({http('EdgeResponseBodyBytes')} | unwrap EdgeResponseBodyBytes [$__auto]))", "Response Body Bytes (outbound)", "B"),
], 0, y, unit="bytes", stack=True, fill=50,
    overrides=[color_override("Request Bytes (inbound)", "green"), color_override("Response Body Bytes (outbound)", "blue")],
    desc="Total bandwidth: inbound (client request bytes) and outbound (edge response body bytes). Stacked to show the ratio of upload vs download traffic.")); pid += 1

panels.append(ts_panel(pid, "Response Size by Host (avg)", [
    t(f"avg by (ClientRequestHost) (avg_over_time({http('EdgeResponseBodyBytes')} | unwrap EdgeResponseBodyBytes [$__auto]))", "{{ClientRequestHost}}")
], 12, y, unit="bytes", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Average response body size per zone. Identifies which zones serve the largest payloads.")); pid += 1
y += 8

# ============================================================
# ROW: Workers
# ============================================================
panels.append(row(pid, "Workers", y)); pid += 1; y += 1

panels.append(ts_panel(pid, "Worker Outcomes", [
    t(f"sum by (Outcome) (count_over_time({wk('Outcome')} [$__auto]))", "{{Outcome}}")
], 0, y, w=8, overrides=[color_override("ok", "green"), color_override("exception", "red"), color_override("exceeded_cpu", "orange"), color_override("exceeded_memory", "yellow"), color_override("canceled", "semi-dark-blue")],
    desc="Worker execution outcomes. 'exception' = unhandled error, 'exceeded_cpu' = hit CPU time limit, 'exceeded_memory' = hit memory limit.")); pid += 1

panels.append(ts_panel(pid, "Worker CPU Time (ms)", [
    t(f"avg by (ScriptName) (avg_over_time({wk('ScriptName', 'CPUTimeMs')} | unwrap CPUTimeMs [$__auto]))", "Avg {{ScriptName}}"),
    t(f"sum(quantile_over_time(0.95, {wk('CPUTimeMs')} | unwrap CPUTimeMs [$__auto]))", "p95", "B"),
], 8, y, w=8, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="CPU time consumed per Worker invocation. Workers have a 10ms (free) or 50ms (paid) CPU time limit. Approaching the limit risks 'exceeded_cpu' outcomes.")); pid += 1

panels.append(ts_panel(pid, "Worker Wall Time (ms)", [
    t(f"avg by (ScriptName) (avg_over_time({wk('ScriptName', 'WallTimeMs')} | unwrap WallTimeMs [$__auto]))", "Avg {{ScriptName}}"),
    t(f"sum(quantile_over_time(0.95, {wk('WallTimeMs')} | unwrap WallTimeMs [$__auto]))", "p95", "B"),
], 16, y, w=8, unit="ms", stack=False, fill=10, legend_calcs=["mean", "lastNotNull"],
    desc="Total wall-clock time per Worker invocation (includes I/O wait). Wall time limit is 30s (default). Unlike CPU time, I/O wait does not count toward CPU limits.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Worker Invocations by Script", [
    t(f"sum by (ScriptName) (count_over_time({wk('ScriptName')} [$__auto]))", "{{ScriptName}}")
], 0, y, w=12, desc="Number of Worker invocations per script over time.")); pid += 1

panels.append(ts_panel(pid, "Worker Script Versions", [
    t(f'sum by (ScriptName, ScriptVersion) (count_over_time({wk("ScriptName", "ScriptVersion")} | ScriptVersion != `` [$__auto]))', "{{ScriptName}} v{{ScriptVersion}}")
], 12, y, w=6, desc="Worker script version tracking. Useful during deployments to confirm new versions are receiving traffic.")); pid += 1

panels.append(ts_panel(pid, "Worker Subrequest Count (avg)", [
    t(f"avg by (WorkerScriptName) (avg_over_time({http('WorkerScriptName', 'WorkerSubrequestCount')} | unwrap WorkerSubrequestCount [$__auto]))", "{{WorkerScriptName}}")
], 18, y, w=6, stack=False, fill=10,
    desc="Average number of subrequests (fetch calls) per Worker invocation. Workers have a 50 subrequest limit per invocation.")); pid += 1
y += 8

panels.append(bar_panel(pid, "Worker Event Types", [
    t(f'sum by (EventType) (count_over_time({wk("EventType")} [$__auto]))', "{{EventType}}")
], 0, y, w=8, desc="Worker event types: 'fetch' (HTTP request), 'cron' (scheduled trigger), 'alarm' (Durable Object alarm), 'queue' (Queue consumer). Shows the mix of invocation triggers.")); pid += 1

panels.append(table_panel(pid, "Worker Exceptions",
    f'topk(20, sum by (ScriptName, Exceptions) (count_over_time({wk("ScriptName", "Exceptions")} | Exceptions != `` | Exceptions != `[]` [$__range])))',
    "{{ScriptName}}: {{Exceptions}}", 8, y, w=8,
    desc="Worker exceptions grouped by script and error message. Exceptions are unhandled errors thrown during execution.")); pid += 1

panels.append(ts_panel(pid, "Worker Status by Script", [
    t(f'sum by (ScriptName, Status) (count_over_time({wk("ScriptName", "Status")} [$__auto]))', "{{ScriptName}} [{{Status}}]")
], 16, y, w=8, desc="Worker invocation status (ok/error) by script name. Shows the success/failure ratio per Worker.")); pid += 1
y += 8

# Build the dashboard JSON
dashboard = {}

if EXPORT:
    dashboard["__inputs"] = [
        {"name": "DS_LOKI", "label": "Loki", "description": "Loki datasource for Cloudflare Logpush data", "type": "datasource", "pluginId": "loki", "pluginName": "Loki"}
    ]
    dashboard["__elements"] = {}
    dashboard["__requires"] = [
        {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "11.0.0"},
        {"type": "datasource", "id": "loki", "name": "Loki", "version": "1.0.0"},
        {"type": "panel", "id": "barchart", "name": "Bar chart", "version": ""},
        {"type": "panel", "id": "geomap", "name": "Geomap", "version": ""},
        {"type": "panel", "id": "piechart", "name": "Pie chart", "version": ""},
        {"type": "panel", "id": "stat", "name": "Stat", "version": ""},
        {"type": "panel", "id": "table", "name": "Table", "version": ""},
        {"type": "panel", "id": "timeseries", "name": "Time series", "version": ""},
    ]

dashboard.update({
    "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]},
    "description": "Cloudflare Logpush analytics - HTTP requests, firewall events, Workers trace events, SOC/security, performance",
    "editable": True if EXPORT else False,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "id": None,
    "links": [],
    "liveNow": False,
    "panels": collapse_rows(panels),
    "schemaVersion": 39,
    "tags": ["cloudflare", "logpush", "loki", "security"],
    "templating": {"list": [
        {
            "allValue": ".*",
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "description": "Filter by Cloudflare zone name (domain). Filters HTTP requests by ZoneName field, and firewall events by ClientRequestHost (regex match). Use to isolate traffic for a specific zone.",
            "hide": 0,
            "includeAll": True,
            "label": "Zone",
            "multi": True,
            "name": "zone",
            "options": [
                {"selected": True, "text": "All", "value": "$__all"},
            ] + ([] if EXPORT else [
                {"selected": False, "text": "erfianugrah.com", "value": "erfianugrah.com"},
                {"selected": False, "text": "erfi.dev", "value": "erfi.dev"},
                {"selected": False, "text": "erfi.io", "value": "erfi.io"},
            ]),
            "query": "" if EXPORT else "erfianugrah.com,erfi.dev,erfi.io",
            "queryValue": "",
            "skipUrlSync": False,
            "type": "custom",
        },
        {
            "allValue": ".*",
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "description": "Filter by hostname (FQDN). More specific than zone — use for subdomains like blog.example.com within a zone.",
            "hide": 0,
            "includeAll": True,
            "label": "Host",
            "multi": True,
            "name": "host",
            "options": [
                {"selected": True, "text": "All", "value": "$__all"},
            ] + ([] if EXPORT else [
                {"selected": False, "text": "erfianugrah.com", "value": "erfianugrah.com"},
                {"selected": False, "text": "erfi.dev", "value": "erfi.dev"},
                {"selected": False, "text": "erfi.io", "value": "erfi.io"},
            ]),
            "query": "" if EXPORT else "erfianugrah.com,erfi.dev,erfi.io",
            "queryValue": "",
            "skipUrlSync": False,
            "type": "custom",
        },
        {
            "current": {"selected": False, "text": ".*", "value": ".*"},
            "description": "Filter by request path (regex, e.g. /api/.* or /login). Use .* for all.",
            "hide": 0,
            "label": "Path",
            "name": "path",
            "query": ".*",
            "skipUrlSync": False,
            "type": "textbox",
        },
        {
            "current": {"selected": False, "text": ".*", "value": ".*"},
            "description": "Filter by client IP (regex, e.g. 192\\.168\\.1\\..* for prefix or exact IP). Use .* for all.",
            "hide": 0,
            "label": "IP",
            "name": "ip",
            "query": ".*",
            "skipUrlSync": False,
            "type": "textbox",
        },
        {
            "allValue": ".*",
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "description": "Filter by client country (multi-select). Matches on ISO 3166-1 Alpha-2 code.",
            "hide": 0,
            "includeAll": True,
            "label": "Country",
            "multi": True,
            "name": "country",
            "options": [{"selected": True, "text": "All", "value": "$__all"}] + [
                {"selected": False, "text": f"{name} ({code.upper()})", "value": code}
                for code, name in sorted(COUNTRY_NAMES.items(), key=lambda x: x[1])
            ],
            "query": ",".join(code for code, name in sorted(COUNTRY_NAMES.items(), key=lambda x: x[1])),
            "queryValue": "",
            "skipUrlSync": False,
            "type": "custom",
        },
        {
            "current": {"selected": False, "text": ".*", "value": ".*"},
            "description": "Filter by JA4 TLS fingerprint (regex). Use .* for all.",
            "hide": 0,
            "label": "JA4",
            "name": "ja4",
            "query": ".*",
            "skipUrlSync": False,
            "type": "textbox",
        },
        {
            "current": {"selected": False, "text": ".*", "value": ".*"},
            "description": "Filter by client ASN number (regex, e.g. 13335 for Cloudflare). Use .* for all.",
            "hide": 0,
            "label": "ASN",
            "name": "asn",
            "query": ".*",
            "skipUrlSync": False,
            "type": "textbox",
        },
        {
            "current": {"selected": False, "text": ".*", "value": ".*"},
            "description": "Filter by edge colo code (regex, e.g. SIN|NRT|LAX). Use .* for all.",
            "hide": 0,
            "label": "Colo",
            "name": "colo",
            "query": ".*",
            "skipUrlSync": False,
            "type": "textbox",
        },
    ]},
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {},
    "timezone": "",
    "title": "Cloudflare Logpush",
    "uid": "cloudflare-logpush",
    "version": 1,
    "weekStart": ""
})

# Output as standalone JSON
import os
if EXPORT:
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflare-logpush-export.json")
else:
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflare-logpush.json")
with open(outpath, "w") as f:
    json.dump(dashboard, f, indent=2)
    f.write("\n")
print(f"Wrote {len(panels)} panels to {outpath}")
