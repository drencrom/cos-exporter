# Prometheus JSON Metrics Importer

Imports JSON metrics data to a Prometheus-compatible server using the
[Prometheus Remote Write](https://prometheus.io/docs/prometheus/latest/storage/#remote-storage-integrations) protocol.

## Requirements

```bash
pip install prometheus-remote-writer
```

## Supported JSON Formats

### 1. Label-set format (flat dict with `__name__`)

```json
[
  {
    "__name__": "zookeeper_JuteMaxBufferSize",
    "instance": "localhost:9998",
    "job": "zookeeper_0",
    "juju_application": "zookeeper",
    "juju_model": "observed",
    "juju_unit": "zookeeper/0"
  }
]
```

Value and timestamp are supplied via `--value` / `--timestamp` CLI arguments.

### 2. Prometheus HTTP API result format

```json
[
  {
    "metric": {"__name__": "cpu_usage", "host": "server1"},
    "values": [[1700000000, "23.5"], [1700000060, "24.1"]]
  }
]
```

Timestamps and values are read directly from the file.

## Usage

```bash
# Basic (value=1.0, timestamp=now):
python importer.py --url http://localhost:9090/api/v1/write metrics.json

# With a specific value:
python importer.py --url http://localhost:9090/api/v1/write --value 42 metrics.json

# With a specific timestamp (Unix seconds):
python importer.py --url http://localhost:9090/api/v1/write --timestamp 1700000000 metrics.json

# Multiple files:
python importer.py --url http://localhost:9090/api/v1/write dir/*.json

# Bearer token auth + skip TLS verification:
python importer.py --url https://mimir.example.com/api/v1/push \
    --bearer-token MY_TOKEN --no-verify metrics.json

# Basic auth:
python importer.py --url https://prom.example.com/api/v1/write \
    --username admin --password secret metrics.json

# Grafana Cloud / Mimir (org ID header):
python importer.py --url https://prometheus-prod.grafana.net/api/prom/push \
    --bearer-token MY_TOKEN --header "X-Scope-OrgID=myorg" metrics.json

# Custom CA certificate:
python importer.py --url https://prom.example.com/api/v1/write \
    --ca-cert /path/to/ca-bundle.crt metrics.json

# Dry-run (parse and validate without sending):
python importer.py --url http://... --dry-run metrics.json
```

## CLI Options

| Option | Default | Description |
|---|---|---|
| `--url` | *(required)* | Remote Write endpoint URL |
| `--value` | `1.0` | Sample value for label-set format |
| `--timestamp` | now | Unix timestamp in seconds for label-set format |
| `--bearer-token` | — | Bearer token authentication |
| `--username` / `--password` | — | Basic authentication |
| `--no-verify` | `False` | Disable SSL certificate verification |
| `--ca-cert` | — | Path to custom CA certificate bundle |
| `--header KEY=VALUE` | — | Extra HTTP header (repeatable) |
| `--batch-size` | `2000` | Max time series per request |
| `--timeout` | `30` | HTTP request timeout in seconds |
| `--dry-run` | `False` | Parse files but do not send |
| `--debug` | `False` | Enable debug logging |
