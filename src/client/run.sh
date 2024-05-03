#!/bin/bash

# Number of instances to run
NUM_INSTANCES=5

# Path to your Python client script
CLIENT_SCRIPT="./MyClient.py"

# Loop to run multiple instances
for ((i=1; i<=$NUM_INSTANCES; i++)); do
    echo "Running instance $i"
    python "$CLIENT_SCRIPT" &
done

echo "All instances started"
