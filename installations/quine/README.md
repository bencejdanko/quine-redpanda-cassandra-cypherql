Start quine:

```bash
./quine.sh simple-redpanda-read.yaml config.conf
```

Call for nodes with the API:

```bash
curl -X "POST" "http://127.0.0.1:9500/api/v1/query/cypher" \
     -H 'Content-Type: text/plain' \
     -d "CALL recentNodes(1)"
```