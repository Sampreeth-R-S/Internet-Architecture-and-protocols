#!/bin/bash
# Wrapper script to easily run docker-compose with N server instances
# Usage: ./run_servers.sh 5
# This generates docker-compose.yml with 5 servers and starts them

if [ $# -eq 0 ]; then
    echo "Usage: $0 <number_of_servers>"
    echo "Example: $0 5"
    echo ""
    echo "This will:"
    echo "  1. Generate docker-compose.yml with N server instances"
    echo "  2. Start all services with docker-compose up --build"
    exit 1
fi

NUM_SERVERS=$1

# Validate input
if ! [[ "$NUM_SERVERS" =~ ^[0-9]+$ ]] || [ "$NUM_SERVERS" -lt 1 ]; then
    echo "Error: Number of servers must be a positive integer"
    exit 1
fi

echo "========================================="
echo "Chat Server Multi-Instance Launcher"
echo "========================================="
echo ""
echo "Generating configuration for $NUM_SERVERS server instance(s)..."
python generate_docker_compose.py "$NUM_SERVERS"

if [ $? -eq 0 ]; then
    echo ""
    echo "Starting services with Docker Compose..."
    echo ""
    docker-compose up --build
else
    echo "Error: Failed to generate docker-compose.yml"
    exit 1
fi
