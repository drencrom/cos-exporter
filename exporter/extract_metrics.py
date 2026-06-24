#!/usr/bin/env python3
"""Extract all metrics from a Prometheus server."""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def write_output(output: str, output_file: str | None) -> None:
    """Write output to a file or stdout."""
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
                if not output.endswith('\n'):
                    f.write('\n')
        except OSError as e:
            print(f"Error writing output file '{output_file}': {e}", file=sys.stderr)
            sys.exit(1)
        return

    print(output)


def fetch_prometheus_api(base_url: str, endpoint: str, params: dict[str, str]) -> dict:
    """Fetch data from a Prometheus API endpoint and return decoded JSON."""
    query = urllib.parse.urlencode(params)
    url = f"{base_url.rstrip('/')}{endpoint}?{query}"

    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"Error connecting to Prometheus: {e}", file=sys.stderr)
        sys.exit(1)

    if data.get('status') != 'success':
        print(f"Prometheus returned error: {data.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    return data


def fetch_series(base_url: str, match: str = '.+') -> list[dict]:
    """Fetch all series from Prometheus matching the given regex."""
    data = fetch_prometheus_api(
        base_url,
        '/api/v1/series',
        {'match[]': '{__name__=~"%s"}' % match},
    )
    return data.get('data', [])


def extract_metric_names(series: list[dict]) -> list[str]:
    """Return sorted unique metric names from a list of series."""
    return sorted({s['__name__'] for s in series if '__name__' in s})


def fetch_metric_range_data(
    base_url: str,
    metric_names: list[str],
    start: str,
    end: str,
    step: str,
) -> dict[str, list[dict]]:
    """Fetch /query_range data for each metric name in the given period."""
    metric_data: dict[str, list[dict]] = {}
    for name in metric_names:
        response = fetch_prometheus_api(
            base_url,
            '/api/v1/query_range',
            {
                'query': name,
                'start': start,
                'end': end,
                'step': step,
            },
        )
        metric_data[name] = response.get('data', {}).get('result', [])
    return metric_data


def render_metrics(series: list[dict], verbose: bool = False) -> str:
    metric_names = extract_metric_names(series)
    lines: list[str] = [f"Found {len(metric_names)} unique metrics ({len(series)} series total)", ""]

    for name in metric_names:
        lines.append(name)
        if verbose:
            for s in series:
                if s.get('__name__') == name:
                    labels = {k: v for k, v in s.items() if k != '__name__'}
                    if labels:
                        label_str = ', '.join(f'{k}="{v}"' for k, v in sorted(labels.items()))
                        lines.append(f"  {{{label_str}}}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Extract all metrics from a Prometheus server.'
    )
    parser.add_argument(
        '--url', default='http://localhost:9090',
        help='Prometheus base URL (default: http://localhost:9090)'
    )
    parser.add_argument(
        '--match', default='.+',
        help='Metric name regex to match (default: .+ — all metrics)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Also print label sets for each metric'
    )
    parser.add_argument(
        '--json', dest='output_json', action='store_true',
        help='Output raw series data as JSON'
    )
    parser.add_argument(
        '--range-start',
        help='Query range start time (RFC3339 or unix timestamp)'
    )
    parser.add_argument(
        '--range-end',
        help='Query range end time (RFC3339 or unix timestamp)'
    )
    parser.add_argument(
        '--range-step', default='15s',
        help='Query range step width (default: 15s)'
    )
    parser.add_argument(
        '--output-file',
        help='Write output to this file instead of stdout'
    )
    args = parser.parse_args()

    if bool(args.range_start) != bool(args.range_end):
        parser.error('--range-start and --range-end must be provided together')

    series = fetch_series(args.url, args.match)
    metric_names = extract_metric_names(series)

    if args.range_start and args.range_end:
        metric_data = fetch_metric_range_data(
            args.url,
            metric_names,
            args.range_start,
            args.range_end,
            args.range_step,
        )
        write_output(json.dumps(metric_data, indent=2), args.output_file)
        return

    if args.output_json:
        write_output(json.dumps(series, indent=2), args.output_file)
    else:
        write_output(render_metrics(series, verbose=args.verbose), args.output_file)


if __name__ == '__main__':
    main()
