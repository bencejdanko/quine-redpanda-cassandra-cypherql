#!/bin/bash
# Script to start or create a Cassandra container with specific configurations

set -e # Exit immediately if a command exits with a non-zero status.

# Define configuration variables
CONTAINER_NAME="cass_cluster"
IMAGE_NAME="cassandra:latest"
NETWORK_NAME="data_platform_network"
VOLUME_NAME="cassandra_data"
CQL_PORT="9042"
MAX_HEAP="512M"
NEW_HEAP="100M"
CPU_LIMIT="1.0"
MEMORY_LIMIT="1G"
HEALTH_CMD="cqlsh -e 'describe keyspaces'"
HEALTH_INTERVAL="15s"
HEALTH_TIMEOUT="10s"
HEALTH_RETRIES="10"

# --- Prerequisites ---

# Ensure the Docker network exists
echo "Checking Docker network: $NETWORK_NAME..."
docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || {
    echo "Network $NETWORK_NAME not found. Creating..."
    docker network create "$NETWORK_NAME"
}

# Ensure the Docker volume exists (Docker creates named volumes automatically if they don't exist)
# You can uncomment the following lines if explicit creation is desired.
# echo "Checking Docker volume: $VOLUME_NAME..."
# docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1 || {
#   echo "Volume $VOLUME_NAME not found. Creating..."
#   docker volume create "$VOLUME_NAME"
# }

# Pull the latest image if needed (optional, ensures image is up-to-date)
# If you only want to pull if the container needs to be created, move this later.
echo "Ensuring image exists locally: $IMAGE_NAME..."
docker image inspect "$IMAGE_NAME" > /dev/null 2>&1 || {
    echo "Image not found locally. Pulling $IMAGE_NAME..."
    docker pull "$IMAGE_NAME"
}
# Alternatively, always pull the latest:
# echo "Pulling latest image: $IMAGE_NAME..."
# docker pull "$IMAGE_NAME"

# --- Container Management ---

echo "Checking container: $CONTAINER_NAME..."
# Check if container exists (by name, including stopped ones)
EXISTING_ID=$(docker ps -aq -f name=^/"${CONTAINER_NAME}"$)

if [ -z "$EXISTING_ID" ]; then
    # --- Container does not exist: Create and Run it ---
    echo "Container '$CONTAINER_NAME' not found. Creating..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "${CQL_PORT}:${CQL_PORT}" \
        -v "${VOLUME_NAME}:/var/lib/cassandra" \
        --network "$NETWORK_NAME" \
        -e MAX_HEAP_SIZE="$MAX_HEAP" \
        -e HEAP_NEWSIZE="$NEW_HEAP" \
        --health-cmd "$HEALTH_CMD" \
        --health-interval "$HEALTH_INTERVAL" \
        --health-timeout "$HEALTH_TIMEOUT" \
        --health-retries "$HEALTH_RETRIES" \
        --cpus="$CPU_LIMIT" \
        --memory="$MEMORY_LIMIT" \
        "$IMAGE_NAME"

    echo "Cassandra container '$CONTAINER_NAME' created and started successfully."
    echo "Port mapping: Host ${CQL_PORT} -> Container ${CQL_PORT}"
    echo "Volume mount: ${VOLUME_NAME} -> /var/lib/cassandra"
    echo "Network: ${NETWORK_NAME}"

else
    # --- Container exists: Check status ---
    STATUS=$(docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME")
    echo "Container '$CONTAINER_NAME' exists with status: $STATUS"

    case "$STATUS" in
        running)
            echo "Container '$CONTAINER_NAME' is already running."
            ;;
        exited|created)
            echo "Attempting to start existing container '$CONTAINER_NAME'..."
            if docker start "$CONTAINER_NAME" >/dev/null; then
                echo "Container '$CONTAINER_NAME' started successfully."
            else
                echo "ERROR: Failed to start container '$CONTAINER_NAME'. Check logs: docker logs $CONTAINER_NAME"
                exit 1 # Exit with error if start fails
            fi
            ;;
        paused)
             echo "Container '$CONTAINER_NAME' is paused. Unpause manually if needed: docker unpause $CONTAINER_NAME"
             ;;
        *) # restarting, removing, dead, etc.
            echo "Container '$CONTAINER_NAME' is in state '$STATUS'. Manual intervention may be required."
            # Optionally, you could attempt to remove and recreate here, but the request was to try starting first.
            # echo "Attempting to remove and recreate..."
            # docker rm -f "$CONTAINER_NAME" >/dev/null
            # # Then call the docker run command again (or structure the script differently)
            # exit 1 # Indicate an unexpected state was encountered
            ;;
    esac
fi

echo "---"
echo "Use 'docker logs $CONTAINER_NAME' to view logs."
echo "Use 'docker ps' or 'docker inspect $CONTAINER_NAME' to check status and health."
echo "Script finished."