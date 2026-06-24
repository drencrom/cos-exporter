# Prometheus Metrics Extractor

A lightweight Python script to extract all metrics from a Prometheus server. No external dependencies — uses the standard library only.

## How It Works

The script queries the Prometheus [Series API](https://prometheus.io/docs/prometheus/latest/querying/api/#finding-series-by-label-matchers) endpoint:

```
GET /api/v1/series?match[]={__name__=~".+"}
```

This is equivalent to:

```bash
curl -s --data-urlencode 'match[]={__name__=~".+"}' http://localhost:9090/api/v1/series
```

## Requirements

- Python 3.10+
- A running Prometheus server

## Usage

```bash
python3 extract_metrics.py [OPTIONS]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url URL` | `http://localhost:9090` | Prometheus base URL |
| `--match REGEX` | `.+` | Metric name regex filter |
| `--verbose`, `-v` | off | Also print label sets per metric |
| `--json` | off | Output raw series data as JSON |
| `--range-start TIME` | none | Start time for querying each metric (`query_range`) |
| `--range-end TIME` | none | End time for querying each metric (`query_range`) |
| `--range-step DURATION` | `15s` | Step for range queries |

## Examples

```bash
# List all unique metric names (default: localhost:9090)
python3 extract_metrics.py

# Custom Prometheus URL
python3 extract_metrics.py --url http://my-prometheus:9090

# Show label sets for each metric
python3 extract_metrics.py --verbose

# Filter metrics by name prefix
python3 extract_metrics.py --match 'node_.+'

# Output raw JSON for further processing
python3 extract_metrics.py --json | jq '.[0]'

# Fetch time-series data for every discovered metric
python3 extract_metrics.py \
  --range-start '2015-07-01T20:10:30.781Z' \
  --range-end '2015-07-01T20:11:00.781Z' \
  --range-step '15s'
```

### Sample Output

```
Found 312 unique metrics (1847 series total)

go_gc_duration_seconds
go_goroutines
go_memstats_alloc_bytes
node_cpu_seconds_total
node_disk_io_time_seconds_total
...
```

With `--verbose`:

```
node_cpu_seconds_total
  {cpu="0", instance="localhost:9100", job="node", mode="idle"}
  {cpu="0", instance="localhost:9100", job="node", mode="user"}
  ...
```
