docker exec -it redpanda-0 rpk topic create entity-data \
  -X user=superuser \
  -X pass=secretpassword \
  -X sasl.mechanism=SCRAM-SHA-256 \
  -X brokers=redpanda-0:9092

docker exec -it redpanda-0 rpk topic create entity-graph \
  -X user=superuser \
  -X pass=secretpassword \
  -X sasl.mechanism=SCRAM-SHA-256 \
  -X brokers=redpanda-0:9092