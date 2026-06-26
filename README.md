Export example:

```sh
python3 extract_metrics.py --openmetrics --url http://<ip_address_1>/cos-prometheus-0  --range-start '2026-06-24T10:10:30.781Z' --range-end '2026-06-24T20:11:00.781Z' --match "zookeeper_.+" --output-file zookeeper.openmetrics
```

Import example:

```sh
./import.sh zookeeper.openmetrics
```
