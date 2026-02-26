#!/usr/bin/env python3
"""
Generate docker-compose.yml with N server instances.
Usage: python generate_docker_compose.py 5
This creates 5 chat server instances on ports 8000-8004
"""

import sys
import yaml
import os

def generate_docker_compose(num_servers):
    """Generate docker-compose configuration with N server instances."""
    
    if num_servers < 1:
        print("Error: Number of servers must be at least 1")
        sys.exit(1)
    
    config = {
        'version': '3.8',
        'services': {
            'redis': {
                'image': 'redis:7-alpine',
                'container_name': 'chat_redis',
                'ports': ['6379:6379'],
                'volumes': ['redis_data:/data'],
                'networks': ['chat_network'],
                'healthcheck': {
                    'test': ['CMD', 'redis-cli', 'ping'],
                    'interval': '5s',
                    'timeout': '3s',
                    'retries': 5
                }
            }
        },
        'networks': {
            'chat_network': {
                'driver': 'bridge'
            }
        },
        'volumes': {
            'redis_data': None
        }
    }
    
    # Generate N server instances
    for i in range(1, num_servers + 1):
        port = 8000 + (i - 1)
        server_id = f"server{i}"
        
        config['services'][server_id] = {
            'build': {
                'context': '.',
                'dockerfile': 'Dockerfile'
            },
            'container_name': f'chat_server{i}',
            'environment': [
                f'SERVER_PORT={port}',
                'REDIS_HOST=redis',
                'REDIS_PORT=6379',
                'REDIS_DB=0',
                f'SERVER_ID={server_id}',
                'CERT_FILE=/app/cert.pem',
                'KEY_FILE=/app/key.pem'
            ],
            'ports': [f'{port}:{port}'],
            'depends_on': {
                'redis': {
                    'condition': 'service_healthy'
                }
            },
            'networks': ['chat_network'],
            'volumes': [
                './cert.pem:/app/cert.pem:ro',
                './key.pem:/app/key.pem:ro'
            ]
        }
    
    return config


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_docker_compose.py <number_of_servers>")
        print("Example: python generate_docker_compose.py 5")
        sys.exit(1)
    
    try:
        num_servers = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid number")
        sys.exit(1)
    
    print(f"Generating docker-compose.yml with {num_servers} server instance(s)...")
    
    config = generate_docker_compose(num_servers)
    
    # Write to docker-compose.yml
    with open('docker-compose.yml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✓ Successfully created docker-compose.yml with {num_servers} server instance(s)")
    print(f"  Redis: port 6379")
    print(f"  Servers: ports 8000-{8000 + num_servers - 1}")
    print(f"\nNext step: docker-compose up --build")


if __name__ == "__main__":
    main()
