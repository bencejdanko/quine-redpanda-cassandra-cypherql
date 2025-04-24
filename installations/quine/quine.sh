#!/bin/bash

# --- Configuration ---
JAR_FILE="quine-1.9.0.jar"
JAR_URL="https://github.com/thatdot/quine/releases/download/v1.9.0/quine-1.9.0.jar"
DEFAULT_PORT="9500"

# --- Argument Parsing ---
# Use positional arguments: $1 for recipe file, $2 for config file
RECIPE_FILE=$1
CONFIG_FILE=$2

# --- Input Validation ---
# Check if recipe file was provided and exists
if [ -n "$RECIPE_FILE" ] && [ ! -f "$RECIPE_FILE" ]; then
    echo "Error: Specified recipe file '$RECIPE_FILE' not found."
    exit 1
fi

# Check if config file was provided and exists
if [ -n "$CONFIG_FILE" ] && [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Specified config file '$CONFIG_FILE' not found."
    exit 1
fi

# --- JAR Download ---
# Check if the Quine JAR file exists, download if not
if [ ! -f "$JAR_FILE" ]; then
    echo "Quine JAR '$JAR_FILE' not found. Downloading from $JAR_URL..."
    # Use curl to download, follow redirects (-L), output to file (-o)
    if curl -L -o "$JAR_FILE" "$JAR_URL"; then
        echo "Download successful."
    else
        echo "Error: Failed to download Quine JAR from $JAR_URL."
        # Clean up potentially incomplete file
        rm -f "$JAR_FILE"
        exit 1
    fi
fi

# --- Build Java Command ---
# Use an array to build the command safely, handling spaces in filenames
JAVA_CMD=("java")

# Add config file property if specified
if [ -n "$CONFIG_FILE" ]; then
    JAVA_CMD+=("-Dconfig.file=$CONFIG_FILE")
    echo "Using config file: $CONFIG_FILE"
else
    echo "No config file specified."
fi

# Add default properties (like port)
JAVA_CMD+=("-Dquine.webserver.port=$DEFAULT_PORT")

# Add JAR file
JAVA_CMD+=("-jar" "$JAR_FILE")

# Add recipe file argument if specified
if [ -n "$RECIPE_FILE" ]; then
    JAVA_CMD+=("-r" "$RECIPE_FILE")
    echo "Using recipe file: $RECIPE_FILE"
else
    echo "No recipe file specified."
fi

# --- Execute ---
echo "Starting Quine..."
# Optional: uncomment the next line to see the exact command being executed
# echo "Executing: ${JAVA_CMD[@]}"

"${JAVA_CMD[@]}"

# --- Foreground Execution Notes ---
echo # Add a newline for clarity
echo "Quine process started in the foreground."
echo "Press Ctrl+C to stop."

# Note: This runs Quine in the foreground.
# To run in the background, add '&' at the end of the java command
# and consider using 'nohup' if you want it to keep running after you log out.
# Example background execution:
# nohup "${JAVA_CMD[@]}" &> quine.log &
# echo "Quine started in the background. PID: $!. Logs are in quine.log"
# echo "To stop Quine, use: kill $!"
