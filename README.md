# Internet Architecture and Protocols - Chat Server Assignment

A thread-based, distributed chat server with TLS encryption, Redis state management, and Docker deployment.

## Features

### Problem 1: Thread-Based Chat Server
- TCP-based server using Python `socket` module
- One thread per connected client
- Broadcast messages to connected clients
- Graceful client disconnect handling

### Problem 2: Authentication
- Client authentication with `LOGIN <username> <password>`
- Secure password hashing using bcrypt
- Per-connection authenticated sessions

### Problem 3: Duplicate Login Handling
- **Policy: Reject Duplicate Login**
- If a user attempts to log in with an already active session, the new login is rejected
- The server returns an error message to the client
- The existing session remains unaffected

### Problem 4: Chat Rooms
- Users can join/leave rooms with `/join <room>` and `/leave` commands
- Messages broadcast only within the current room
- Default lobby room for all users on login
- View available rooms with `/rooms`

### Problem 5: Publish-Subscribe Model
- Clients can subscribe to other users: `/subscribe <username>`
- Unsubscribe from users: `/unsubscribe <username>`
- Published messages reach only subscribers
- Thread-safe implementation with graceful disconnect handling

### Problem 6: Redis Integration (Distributed State)
- User sessions stored in Redis hashes
- Room membership stored in Redis sets
- Cross-server message broadcasting via Redis Pub/Sub
- Support for multiple server instances
- Stateless servers with respect to global session/room data

### Problem 7: TLS/Encrypted Transport
- Client-server communication encrypted with TLS
- Self-signed certificates for testing (cert.pem, key.pem)
- Server certificate verification on the client side
- Rejects plaintext connections

### Problem 8: Dockerized Deployment
- Docker container for the server
- Docker Compose setup with Redis and multiple server instances
- One-command deployment: `docker-compose up --build`
- Health checks and proper networking

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | 8000 | Port for the chat server |
| `REDIS_HOST` | localhost | Redis host address |
| `REDIS_PORT` | 6379 | Redis port |
| `REDIS_DB` | 0 | Redis database number |
| `SERVER_ID` | uuid.uuid4() | Unique server identifier |
| `CERT_FILE` | cert.pem | Path to TLS certificate |
| `KEY_FILE` | key.pem | Path to TLS private key |
| `ACTIVE_TTL_SECONDS` | 15 | User active session TTL |
| `HEARTBEAT_INTERVAL_SECONDS` | 5 | Server heartbeat interval |

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (for containerized deployment)
- Redis (for distributed state management)

## Installation

### Local Setup (without Docker)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Generate TLS certificates (if not already present):**
   ```bash
   python generate_certs.py
   ```

3. **Start Redis:**
   ```bash
   # On Linux/Mac:
   redis-server
   
   # On Windows with WSL:
   redis-server
   
   # Or use Docker:
   docker run -d -p 6379:6379 redis:7-alpine
   ```

4. **Start the server:**
   ```bash
   python server.py
   ```

5. **In another terminal, start the client:**
   ```bash
   python client.py
   ```

### Docker Setup

1. **Generate certificates (if needed):**
   ```bash
   python generate_certs.py
   ```

2. **Build and start the services:**
   ```bash
   docker-compose up --build
   ```

3. **Connect to the server:**
   ```bash
   python client.py
   ```
   
   For server2 (if running), set the port:
   ```bash
   SERVER_PORT=8001 python client.py
   ```

### Running Multiple Server Instances

You can dynamically generate a `docker-compose.yml` file with **N** server instances and start them all with a single command.

#### **Using the Script (Recommended)**

**On WSL/Linux/Mac (Bash):**
```bash
chmod +x run_servers.sh
./run_servers.sh 5
```
This creates 5 server instances on ports 8000-8004 and starts them.

**On Windows (PowerShell):**
```powershell
.\run_servers.ps1 -NumServers 5
```

#### **Manual Method**

```bash
# Generate docker-compose.yml with N servers
python generate_docker_compose.py 5

# Start all services
docker-compose up --build
```

#### **Understanding the Output**

When you run the above commands with N=5:
- ✓ Redis service on port `6379`
- ✓ Server 1 on port `8000` (SERVER_ID=server1)
- ✓ Server 2 on port `8001` (SERVER_ID=server2)
- ✓ Server 3 on port `8002` (SERVER_ID=server3)
- ✓ Server 4 on port `8003` (SERVER_ID=server4)
- ✓ Server 5 on port `8004` (SERVER_ID=server5)

All servers share the same **Redis instance** and **network**, ensuring **cross-server message delivery** in rooms.

#### **Test Cross-Server Communication**

```bash
# Terminal 1: Start 4 servers
python generate_docker_compose.py 4
docker-compose up -d

# Terminal 2: Connect Client A to Server 1
python client.py
> LOGIN a 1
> /join gaming
> /subscribe b

# Terminal 3: Connect Client B to Server 3
SERVER_PORT=8002 python client.py
> LOGIN b 1
> /join gaming
> /publish Hello from Server 3!

# Terminal 2: Client A should receive the notification
# Notification from b: Hello from Server 3!
```

## Default Credentials

The server comes with pre-registered users (a-h) with password "1":

```
Username: a, Password: 1
Username: b, Password: 1
Username: c, Password: 1
... (up to h)
```

## Usage

### Client Commands

#### Room Management
- `/join <room>` - Join a specific room
- `/leave` - Return to the lobby
- `/rooms` - List all available rooms with user counts

#### User Management
- `/users` - List all online users

#### Subscriptions
- `/subscribe <username>` - Subscribe to a user's messages
- `/unsubscribe <username>` - Unsubscribe from a user

#### Messaging
- `/publish <message>` - Publish a message to all subscribers
- Type any message to broadcast in the current room

### Example Session

```
Username: a
Password: 1
Login successful. Room: lobby

/users
Users online: a

/rooms
Available rooms: lobby(1)

/join general
Joined room general

b joined general

hello everyone
a: hello everyone

/subscribe b
Subscribed to b

/publish Hello from a!
Notification from a: Hello from a!

/leave
Returned to lobby

/unsubscribe b
Unsubscribed from b
```

## Architecture

### Thread Safety
- Uses `threading.Lock()` for in-memory state protection
- Redis operations are thread-safe by design
- Atomic operations for session management

### Redis Schema

**Rooms:**
- `room:<room_name>` - Set of users in each room
- `rooms` - Set of all room names

**Users:**
- `session:<username>` - Hash with room and server info
- `active:<username>` - Active user lock with server ID
- `online_users` - Set of all online users

**Subscriptions:**
- `subscriptions:<username>` - Set of users subscribed to
- `subscribers:<username>` - Set of users subscribed to this user

**Pub/Sub:**
- `room:<room_name>` - Pub/Sub channel for room messages
- `notify:<username>` - Pub/Sub channel for notifications

### Multi-Server Deployment

When multiple servers are running:
1. Users connect to any server instance
2. Each server maintains local connection state
3. All machines share Redis for global user/room state
4. Messages broadcast via Redis Pub/Sub to all servers
5. Servers deliver messages to their local connections only

## Testing

### Basic Testing

1. **Start server and client:**
   ```bash
   # Terminal 1
   python server.py
   
   # Terminal 2
   python client.py
   ```

2. **Test room functionality:**
   ```
   /join test_room
   # Open another client
   /join test_room
   # Send a message - it should appear on both clients
   ```

3. **Test subscriptions:**
   ```
   # Client A: /publish Hello World
   # Client B: /subscribe a
   # Client A: /publish Second message
   # Client B should receive: Notification from a: Second message
   ```

### Multi-Server Testing with Docker

```bash
# Start the stack
docker-compose up --build

# Connect to server 1
python client.py  # Uses port 8000 by default

# Connect to server 2 (in another terminal)
SERVER_PORT=8001 python client.py

# Test room communication across servers
# Join the same room from both clients
# Messages should appear on both clients even though they're connected to different servers
```

## Troubleshooting

### Connection Issues
- Verify the server is running
- Check that the port is not already in use
- Ensure TLS certificates (cert.pem, key.pem) exist

### Certificate Errors
- Regenerate certificates: `python generate_certs.py`
- Ensure cert.pem and key.pem are in the same directory as the scripts

### Redis Connection Errors
- Ensure Redis is running and accessible
- Check `REDIS_HOST` and `REDIS_PORT` environment variables
- Docker Compose handles this automatically via service names

### Docker Issues
- Remove conflicting containers: `docker-compose down`
- Remove dangling images: `docker image prune`
- Rebuild images: `docker-compose up --build`

## Implementation Details

### Thread Model
- Main thread accepts connections
- Each client connection spawns a daemon thread
- Background threads for Redis Pub/Sub listening and heartbeat

### Duplicate Login Policy
- When a user logs in, the server attempts to acquire an exclusive lock in Redis
- If the lock exists (user already active), the new login is rejected
- The lock is held for `ACTIVE_TTL_SECONDS` and refreshed via heartbeat

### TLS Implementation
- Mandatory TLS wrapping at socket level
- Server provides self-signed certificate
- Client verifies server certificate (with self-signed fallback)
- All communication is encrypted end-to-end

## Files

- `server.py` - Main chat server implementation
- `client.py` - Interactive chat client
- `Dockerfile` - Container image for the server
- `docker-compose.yml` - Multi-service orchestration
- `requirements.txt` - Python dependencies
- `cert.pem` - TLS server certificate (generated)
- `key.pem` - TLS private key (generated)
- `generate_certs.py` - Certificate generation utility
- `.dockerignore` - Files excluded from Docker builds

## Performance Considerations

- **Connection limit**: Limited by system file descriptors and available memory
- **Message latency**: <100ms typical for local connections
- **Redis dependency**: Single point of contact for all servers (consider Redis Cluster for production)
- **TLS overhead**: ~5-15% CPU increase for encryption/decryption

## Security Notes

- Self-signed certificates suitable for development/testing only
- For production, use proper CA-signed certificates
- Passwords are hashed with bcrypt, never stored in plaintext
- Consider adding rate limiting for login attempts
- Redis should be network-isolated (not exposed to untrusted networks)

## Future Enhancements

1. Message persistence/history
2. Direct messaging between users
3. Admin commands for user management
4. Rate limiting and spam protection
5. Proper certificate management (CA-signed, OCSP stapling)
6. Metrics and monitoring (Prometheus, Grafana)
7. Database for persistent user storage
8. Message encryption end-to-end between users

