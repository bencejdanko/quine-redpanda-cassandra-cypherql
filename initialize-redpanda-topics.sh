docker exec -it redpanda-0 rpk cluster config set enable_sasl false \
  -X user=superuser \
  -X pass=secretpassword \
  -X sasl.mechanism=SCRAM-SHA-256

docker exec -it redpanda-0 rpk topic create entity-data \
  -X brokers=redpanda-0:9092

docker exec -it redpanda-0 rpk topic create entity-graph \
  -X brokers=redpanda-0:9092