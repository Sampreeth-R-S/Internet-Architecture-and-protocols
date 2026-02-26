# Dynamic Multi-Server Setup - Quick Reference

## Quick Start

### On WSL/Linux/Mac:
```bash
chmod +x run_servers.sh
./run_servers.sh 5
```

### On Windows PowerShell:
```powershell
.\run_servers.ps1 -NumServers 5
```

### Manual (Any Platform):
```bash
python generate_docker_compose.py 5
docker-compose up --build
```

---

## What You Get

When you run with `N=5`, you get:

```
Service              Port      Container Name
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Redis               6379      chat_redis
Server 1            8000      chat_server1 (ID: server1)
Server 2            8001      chat_server2 (ID: server2)
Server 3            8002      chat_server3 (ID: server3)
Server 4            8003      chat_server4 (ID: server4)
Server 5            8004      chat_server5 (ID: server5)
```

---

## Testing Cross-Server Communication

```bash
# Terminal 1: Generate and start 3 servers
python generate_docker_compose.py 3
docker-compose up -d

# Terminal 2: Check status
docker-compose ps

# Terminal 3: Client A → Server 1
python client.py
LOGIN a 1
/subscribe b

# Terminal 4: Client B → Server 3 (different server!)
SERVER_PORT=8002 python client.py
LOGIN b 1
/publish Test message!

# Terminal 3: A receives the message from B
# Notification from b: Test message!
```

✅ **This proves cross-server communication works!**

---

## Under the Hood

The generated `docker-compose.yml` ensures cross-server communication by:

1. **Shared Redis Instance**: All servers connect to the same Redis (port 6379)
2. **Shared Network**: All containers on `chat_network` bridge
3. **Pub/Sub Channels**: Messages flow through Redis channels:
   - `room:*` for room messages
   - `notify:*` for notifications
4. **Unique Server IDs**: Each server has unique `SERVER_ID` (server1, server2, etc.)

---

## Cleanup

```bash
# Stop all containers
docker-compose down

# Stop and remove volumes (Redis data)
docker-compose down -v

# View logs
docker-compose logs -f server1
```

---

## Limitations

- Minimum: 1 server
- Maximum: Limited by available ports (can extend beyond 8000-8100)
- Each server needs at least ~100MB RAM (check `docker stats`)

---

## Troubleshooting

### Port already in use?
```bash
# Find what's using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows
```

### Redis connection failed?
```bash
# Verify Redis is healthy
docker-compose ps redis
```

### Certificate issues?
```bash
python generate_certs.py
```
