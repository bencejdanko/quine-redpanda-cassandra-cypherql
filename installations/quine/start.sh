#!/bin/bash

# Recipe file to use
RECIPE_FILE="simple-redpanda-read.yaml"
CONFIG_FILE="config.conf"
JAR_FILE="quine-1.9.0.jar"
JAR_URL="https://github.com/thatdot/quine/releases/download/v1.9.0/quine-1.9.0.jar"

# Check if the recipe file exists
if [ ! -f "$RECIPE_FILE" ]; then
    echo "Error: Recipe file '$RECIPE_FILE' not found in current directory."
    exit 1
fi

# Check if the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file '$CONFIG_FILE' not found in current directory."
    exit 1
fi

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

echo "Starting Quine with recipe: $RECIPE_FILE and config: $CONFIG_FILE ..."

# Run Quine using java -jar
# Map environment variables to Java system properties (-Dkey=value)
# Note: Environment variable names are converted: uppercase, underscores to dots.
java -Dconfig.file="$CONFIG_FILE" -Dquine.webserver.port=9500 -jar "$JAR_FILE" -r "$RECIPE_FILE" --force-config

# Note: This runs Quine in the foreground.
# To run in the background, add '&' at the end of the java command
# and consider using 'nohup' if you want it to keep running after you log out.
# Example background execution:
# nohup java ... -jar "$JAR_FILE" ... &> quine.log &
# echo "Quine started in the background. PID: $!. Logs are in quine.log"
# echo "To stop Quine, use: kill $!"

echo "Quine process started in the foreground."
echo "Press Ctrl+C to stop."
