#!/usr/bin/env python3
"""
Import JSON metrics data to a Prometheus-compatible server via Remote Write.

Supported JSON formats:

1. Label-set format (flat label dict, __name__ is the metric name):
   [
     {"__name__": "my_metric", "job": "myjob", "instance": "localhost:9090"},
     ...
   ]
   Value and timestamp are supplied via --value / --timestamp CLI args.

2. Prometheus HTTP API result format (instant or range vector):
   [
     {"metric": {"__name__": "...", ...}, "value":  [<timestamp>, "<value>"]},
     {"metric": {"__name__": "...", ...}, "values": [[<timestamp>, "<value>"], ...]},
     ...
   ]

Usage examples:
  # Label-set format with a fixed value of 1 at current time:
  python importer.py --url http://localhost:9090/api/v1/write metrics.json

  # Label-set format with a specific value and timestamp:
  python importer.py --url http://localhost:9090/api/v1/write --value 42 --timestamp 1700000000 metrics.json

  # Multiple files:
  python importer.py --url http://localhost:9090/api/v1/write *.json

  # With bearer token auth and SSL disabled:
  python importer.py --url https://mimir.example.com/api/v1/push \\
      --bearer-token MY_TOKEN --no-verify metrics.json

  # With basic auth:
  python importer.py --url https://prom.example.com/api/v1/write \\
      --username admin --password secret metrics.json

  # Grafana Cloud / Mimir (requires org ID header):
  python importer.py --url https://prometheus-prod.grafana.net/api/prom/push \\
      --bearer-token MY_TOKEN --header "X-Scope-OrgID=myorg" metrics.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from prometheus_remote_writer import RemoteWriter


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _is_label_set_format(entry: Any) -> bool:
    """Return True if entry is a flat label dict (label-set format)."""
    return isinstance(entry, dict) and "__name__" in entry and "metric" not in entry


def parse_label_set_format(
    entries: List[Dict],
    default_value: float,
    default_timestamp_ms: int,
) -> List[Dict]:
    """
    Convert a list of flat label dicts to MetricItem format required by RemoteWriter.
    Each entry maps to a single sample at default_timestamp_ms with default_value.
    """
    metrics = []
    for entry in entries:
        metric_labels = {k: str(v) for k, v in entry.items()}
        metrics.append({
            "metric": metric_labels,
            "values": [default_value],
            "timestamps": [default_timestamp_ms],
        })
    return metrics


def parse_prometheus_result_format(entries: List[Dict]) -> List[Dict]:
    """
    Convert Prometheus HTTP API query result entries to MetricItem format.

    Supports both instant vectors (entry has 'value') and
    range vectors (entry has 'values').
    """
    metrics = []
    for entry in entries:
        metric_labels = {k: str(v) for k, v in entry.get("metric", {}).items()}

        if "values" in entry:
            # Range vector: [[timestamp, "value"], ...]
            raw_pairs = entry["values"]
            timestamps = [float(pair[0]) for pair in raw_pairs]
            values = [float(pair[1]) for pair in raw_pairs]
        elif "value" in entry:
            # Instant vector: [timestamp, "value"]
            pair = entry["value"]
            timestamps = [float(pair[0])]
            values = [float(pair[1])]
        else:
            log.warning("Skipping entry with no 'value' or 'values': %s", entry)
            continue

        metrics.append({
            "metric": metric_labels,
            "values": values,
            "timestamps": timestamps,
        })
    return metrics


def load_json_file(path: Path) -> List[Any]:
    """Load a JSON file and always return a list."""
    with open(path, "r") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def parse_entries(
    entries: List[Any],
    default_value: float,
    default_timestamp_ms: int,
) -> List[Dict]:
    """Auto-detect format and convert entries to MetricItem list."""
    if not entries:
        return []

    first = entries[0]
    if _is_label_set_format(first):
        return parse_label_set_format(entries, default_value, default_timestamp_ms)
    else:
        return parse_prometheus_result_format(entries)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import JSON metrics to Prometheus via Remote Write.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="JSON file(s) to import.",
    )
    parser.add_argument(
        "--url",
        required=True,
        metavar="URL",
        help="Prometheus Remote Write endpoint (e.g. http://localhost:9090/api/v1/write).",
    )

    # Auth
    auth_group = parser.add_argument_group("authentication")
    auth_group.add_argument("--bearer-token", metavar="TOKEN", help="Bearer token for authentication.")
    auth_group.add_argument("--username", metavar="USER", help="Basic auth username.")
    auth_group.add_argument("--password", metavar="PASS", help="Basic auth password.")

    # TLS
    tls_group = parser.add_argument_group("TLS")
    tls_group.add_argument(
        "--no-verify",
        action="store_true",
        help="Disable SSL certificate verification (self-signed certs).",
    )
    tls_group.add_argument(
        "--ca-cert",
        metavar="PATH",
        help="Path to a custom CA certificate bundle.",
    )

    # Label-set format options
    ls_group = parser.add_argument_group("label-set format options")
    ls_group.add_argument(
        "--value",
        type=float,
        default=1.0,
        help="Sample value for label-set format entries (default: 1.0).",
    )
    ls_group.add_argument(
        "--timestamp",
        type=float,
        default=None,
        metavar="UNIX_TS",
        help="Unix timestamp in seconds for label-set format entries (default: now).",
    )

    # Extra headers
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra HTTP header (can be repeated). E.g. --header 'X-Scope-OrgID=myorg'.",
    )

    # Batching / misc
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        metavar="N",
        help="Max time series per request (default: 2000).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate files but do not send data.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser.parse_args()


def build_auth(args: argparse.Namespace):
    if args.bearer_token:
        return {"bearer_token": args.bearer_token}
    if args.username and args.password:
        return {"username": args.username, "password": args.password}
    if args.username or args.password:
        log.error("--username and --password must be used together.")
        sys.exit(1)
    return None


def build_verify(args: argparse.Namespace):
    if args.no_verify:
        return False
    if args.ca_cert:
        return args.ca_cert
    return True


def build_extra_headers(args: argparse.Namespace) -> Dict[str, str]:
    headers = {}
    for h in args.header:
        if "=" not in h:
            log.error("Invalid --header value %r: expected KEY=VALUE", h)
            sys.exit(1)
        key, _, value = h.partition("=")
        headers[key.strip()] = value.strip()
    return headers


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve default timestamp once for the whole run
    default_ts_s = args.timestamp if args.timestamp is not None else time.time()
    default_ts_ms = int(default_ts_s * 1000)

    # Collect all metrics from all files
    all_metrics = []
    for file_path in args.files:
        path = Path(file_path)
        if not path.is_file():
            log.error("File not found: %s", path)
            sys.exit(1)
        log.info("Loading %s ...", path)
        try:
            entries = load_json_file(path)
        except json.JSONDecodeError as e:
            log.error("Failed to parse %s: %s", path, e)
            sys.exit(1)

        metrics = parse_entries(entries, args.value, default_ts_ms)
        log.info("  → %d metric series from %s", len(metrics), path)
        all_metrics.extend(metrics)

    if not all_metrics:
        log.warning("No metrics found in provided files. Exiting.")
        sys.exit(0)

    log.info("Total series to send: %d", len(all_metrics))

    if args.dry_run:
        log.info("Dry-run mode: skipping send.")
        # Print a sample of what would be sent
        for m in all_metrics[:5]:
            log.info("  Sample: name=%s labels=%s values=%s timestamps=%s",
                     m["metric"].get("__name__", "?"),
                     {k: v for k, v in m["metric"].items() if k != "__name__"},
                     m["values"][:3],
                     m["timestamps"][:3])
        if len(all_metrics) > 5:
            log.info("  ... and %d more.", len(all_metrics) - 5)
        return

    auth = build_auth(args)
    verify = build_verify(args)
    extra_headers = build_extra_headers(args)

    with RemoteWriter(
        url=args.url,
        headers=extra_headers if extra_headers else None,
        auth=auth,
        verify=verify,
        timeout=args.timeout,
        max_series_per_request=args.batch_size,
        auto_convert_seconds_to_ms=True,
        sort_labels=True,
        logger=log,
    ) as writer:
        log.info("Sending to %s ...", args.url)
        try:
            result = writer.send(all_metrics)
        except (RuntimeError, ValueError) as e:
            log.error("Failed to send metrics: %s", e)
            sys.exit(1)

    log.info(
        "Done. requests=%d  series=%d  samples=%d  http_status=%s",
        result.requests_sent,
        result.series_sent,
        result.samples_sent,
        result.last_response.status_code if result.last_response else "N/A",
    )


if __name__ == "__main__":
    main()
