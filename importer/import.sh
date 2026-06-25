FILE=$1
NAMESPACE="${2:-cos}"
POD_NAME="${3:-prometheus-0}"
CONTAINER_NAME="${4:-prometheus}"

promtool tsdb create-blocks-from openmetrics $FILE

for i in data/*; do
		microk8s kubectl cp $i $NAMESPACE/$POD_NAME:/var/lib/prometheus -c $CONTAINER_NAME
done

