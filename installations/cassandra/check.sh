#!/bin/bash

# Define the CQL commands as a single string or use a here document
CQL_COMMANDS=$(cat <<EOF
USE entity_graph;

CREATE TABLE IF NOT EXISTS processed_addresses (
    address_id uuid PRIMARY KEY,
    original_address text,
    addressee text,
    house_part text,
    po_box text,
    city text,
    state text,
    postcode text
    -- Optional: Add a timestamp for when it was processed/inserted
    -- processed_at timestamp
);

DESCRIBE TABLE processed_addresses;
EOF
)

# Execute the CQL commands using docker exec without -it for non-interactive execution
docker exec cass_cluster cqlsh -e "$CQL_COMMANDS"

# Optional: Check the exit status
if [ $? -eq 0 ]; then
  echo "CQL commands executed successfully."
else
  echo "Error executing CQL commands." >&2
  exit 1
fi