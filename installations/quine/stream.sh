#!/bin/bash

# Define the input file path
INPUT_FILE="public-record-addresses-2021.ndjson"
REDPANDA_CONTAINER="redpanda-0"
REDPANDA_BROKERS="redpanda-0:9092"
TOPIC_NAME="entity-data"

# Check if the input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found at $INPUT_FILE"
    exit 1
fi

# Check if the Redpanda container is running
if ! docker ps -f name="^/${REDPANDA_CONTAINER}$" --format '{{.Names}}' | grep -q "^${REDPANDA_CONTAINER}$"; then
    echo "Error: Redpanda container '$REDPANDA_CONTAINER' is not running."
    exit 1
fi

echo "Ensuring Redpanda topic '$TOPIC_NAME' exists..."
# Create the Redpanda topic (ignore error if it already exists)
docker exec "$REDPANDA_CONTAINER" rpk topic create "$TOPIC_NAME" -X brokers="$REDPANDA_BROKERS" || true

echo "Streaming data from $INPUT_FILE to Redpanda topic '$TOPIC_NAME'..."

# Stream the file content to the Redpanda topic
cat "$INPUT_FILE" | docker exec -i "$REDPANDA_CONTAINER" rpk topic produce "$TOPIC_NAME" -X brokers="$REDPANDA_BROKERS"

echo "Finished streaming data."

exit 0