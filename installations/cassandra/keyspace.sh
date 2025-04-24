#!/bin/bash

# Define the CQL commands as a single string or use a here document
CQL_COMMANDS=$(cat <<EOF
CREATE KEYSPACE IF NOT EXISTS entity_graph WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE entity_graph;

CREATE TABLE IF NOT EXISTS entity_payloads (
    entity_id UUID PRIMARY KEY,
    po_box TEXT,
    postcode TEXT
);

DESCRIBE TABLE entity_payloads;
EOF
)

# Execute the CQL commands using docker exec without -it for non-interactive execution
docker exec cass_cluster cqlsh -e "$CQL_COMMANDS" -u cassandra -p cassandra

# Optional: Check the exit status
if [ $? -eq 0 ]; then
  echo "CQL commands executed successfully."
else
  echo "Error executing CQL commands." >&2
  exit 1
fi