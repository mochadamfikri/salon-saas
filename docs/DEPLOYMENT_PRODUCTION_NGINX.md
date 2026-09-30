# Production Deployment: Nginx Reverse Proxy Configuration

**Target:** Production deployment behind Nginx reverse proxy for Salon SaaS API (Phase 1)

## Critical: Trusted Proxy Configuration

### The Problem

The API rate limiter uses client IP addresses to enforce per-IP rate limits. When the API runs behind a reverse proxy (Nginx, HAProxy, AWS ALB), the direct TCP peer is the proxy's internal IP (e.g., `172.18.0.1`, `127.0.0.1`), NOT the real client IP.

**Without trusted proxy configuration:**
- All requests share ONE rate limit bucket (the proxy IP)
- Legitimate users hit 429 Too Many Requests immediately
- Attackers bypass rate limiting by routing through the proxy

### The Solution

1. **Nginx strips untrusted X-Forwarded-For headers** from incoming requests
2. **Nginx sets X-Forwarded-For with the real client IP**
3. **API trusts ONLY the configured proxy IP(s)** via `TRUSTED_PROXIES` env var
4. **Firewall blocks direct access** to the API (all traffic MUST go through Nginx)

---

## Nginx Configuration

### `/etc/nginx/sites-available/salon-saas-api`

```nginx
upstream salon_api {
    # Uvicorn/Gunicorn backend (adjust port as needed)
    server 127.0.0.1:8000;
}

server {
    listen 80;
    listen [::]:80;
    server_name api.yourdomain.com;

    # Redirect HTTP to HTTPS (Let's Encrypt will handle HTTPS block)
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.yourdomain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Request body size limit (adjust for file uploads if needed)
    client_max_body_size 10M;

    location / {
        # CRITICAL: Strip any existing X-Forwarded-For from client
        # This prevents IP spoofing attacks
        proxy_set_header X-Forwarded-For $remote_addr;
        
        # Standard proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Proxy to backend
        proxy_pass http://salon_api;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint (optional, bypasses authentication)
    location /health {
        access_log off;
        proxy_pass http://salon_api;
    }
}
```

### Enable and Test

```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/salon-saas-api /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## API Configuration

### 1. Identify Nginx Internal IP

```bash
# If Nginx and API are on the same host
# The proxy peer will be 127.0.0.1

# If Nginx is in a Docker network or separate host
docker network inspect <network_name> | grep Gateway
# Or check /etc/hosts, ip addr show
```

**Common scenarios:**
- Same host: `127.0.0.1`
- Docker Compose: `172.18.0.1` (default bridge gateway)
- Kubernetes: Pod CIDR or service IP
- AWS: Private subnet CIDR (e.g., `10.0.1.0/24`)

### 2. Set TRUSTED_PROXIES Environment Variable

**`.env` (production only):**

```env
# REQUIRED in production behind Nginx/HAProxy
# Comma-separated list of trusted proxy IPs
TRUSTED_PROXIES=["127.0.0.1"]

# Or for Docker Compose bridge network:
TRUSTED_PROXIES=["172.18.0.1"]

# Multiple proxies (HAProxy → Nginx chain):
TRUSTED_PROXIES=["172.18.0.1", "10.0.1.50"]
```

**Docker Compose example:**

```yaml
services:
  api:
    image: salon-saas-api:latest
    environment:
      - TRUSTED_PROXIES=["172.18.0.1"]
    networks:
      - app_network
```

### 3. Verify Configuration

```bash
# Start API with trusted proxy config
cd /home/ubuntu/salon-saas
source .venv/bin/activate
export TRUSTED_PROXIES='["127.0.0.1"]'
uvicorn app.main:app --host 0.0.0.0 --port 8000

# From another terminal, test through Nginx
curl -H "X-Forwarded-For: 203.0.113.42, 198.51.100.1" https://api.yourdomain.com/auth/login

# Check API logs — rate limiter should extract 203.0.113.42 (real client)
# NOT 127.0.0.1 (proxy peer)
```

---

## Firewall Configuration

**Block direct access to API port (force all traffic through Nginx):**

```bash
# UFW (Ubuntu)
sudo ufw deny 8000/tcp
sudo ufw allow 'Nginx Full'
sudo ufw enable

# iptables
sudo iptables -A INPUT -p tcp --dport 8000 -s 127.0.0.1 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8000 -j DROP
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

**Docker binding (alternative):**

Bind API to `127.0.0.1:8000` instead of `0.0.0.0:8000` so it's only accessible from localhost (where Nginx runs):

```yaml
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"  # NOT exposed to internet
```

---

## Security Checklist

Before going live:

- [ ] Nginx strips client `X-Forwarded-For` (line: `proxy_set_header X-Forwarded-For $remote_addr;`)
- [ ] API `TRUSTED_PROXIES` matches Nginx internal IP exactly
- [ ] Firewall blocks direct access to API port (8000)
- [ ] SSL/TLS enabled (Let's Encrypt certificates)
- [ ] Test rate limiting: hammer an endpoint, verify 429 returns
- [ ] Test IP isolation: requests from different IPs get separate buckets
- [ ] Monitor logs for "Rate limiter Redis unavailable" warnings

---

## Testing Rate Limiting in Production

```bash
# From external host (real client IP)
for i in {1..15}; do
  curl -w "%{http_code}\n" -o /dev/null -s \
    -X POST https://api.yourdomain.com/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
  sleep 0.1
done

# Expected output:
# 401 401 401 401 401 401 401 401 401 401 (first 10 succeed, wrong password)
# 429 429 429 429 429                     (rate limit hit after 10 attempts)
```

---

## Troubleshooting

### Issue: All requests hit 429 immediately

**Cause:** `TRUSTED_PROXIES` not set, all requests share proxy IP bucket.

**Fix:** Set `TRUSTED_PROXIES` to Nginx internal IP and restart API.

### Issue: Rate limiting bypassed

**Cause:** Nginx not stripping `X-Forwarded-For`, attacker spoofing IP.

**Fix:** Verify Nginx config has `proxy_set_header X-Forwarded-For $remote_addr;` (REPLACES header, doesn't append).

### Issue: Direct access to API bypasses Nginx

**Cause:** Firewall not blocking API port.

**Fix:** Apply firewall rules above, test with `curl http://your-server-ip:8000/` (should timeout or be refused).

---

## Development vs Production

| Environment | `TRUSTED_PROXIES` | Behavior |
|-------------|-------------------|----------|
| **Development** (no proxy) | `[]` (empty, default) | Uses direct peer IP (`request.client.host`) — safe |
| **Production** (behind Nginx) | `["127.0.0.1"]` or `["172.18.0.1"]` | Parses `X-Forwarded-For` from trusted peer only |

**Never set `TRUSTED_PROXIES` in development** unless you're testing proxy behavior. An empty list is the safe default.

---

## References

- Phase 1 Checkpoint D: Redis rate limiting implementation
- `apps/api/app/core/rate_limit.py`: `_client_ip()` function
- `apps/api/app/core/config.py`: `trusted_proxies` configuration
