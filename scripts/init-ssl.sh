#!/bin/bash
# ===========================================
# Perchspot SSL Certificate Initialization
# ===========================================
# Obtains Let's Encrypt certificates for your domain
# Usage: ./scripts/init-ssl.sh yourdomain.com

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for domain argument
if [ -z "$1" ]; then
    echo -e "${RED}Error: Domain not specified${NC}"
    echo "Usage: ./scripts/init-ssl.sh yourdomain.com"
    exit 1
fi

DOMAIN="$1"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Perchspot SSL Certificate Setup${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Domain: ${DOMAIN}"
echo ""

# Load email from .env.production
if [ -f ".env.production" ]; then
    source .env.production
fi

if [ -z "${LETSENCRYPT_EMAIL}" ]; then
    read -p "Enter email for Let's Encrypt notifications: " LETSENCRYPT_EMAIL
fi

# Create directories
mkdir -p certbot/conf certbot/www

# Check if certificates already exist
if [ -d "certbot/conf/live/${DOMAIN}" ] || [ -d "certbot/conf/live/perchspot" ]; then
    echo -e "${YELLOW}Certificates already exist!${NC}"
    read -p "Renew/replace certificates? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "SSL setup cancelled."
        exit 0
    fi
fi

echo -e "${BLUE}Step 1: Creating temporary nginx config for ACME challenge${NC}"

# Create temporary nginx config for initial certificate
cat > nginx/nginx-temp.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name _;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 200 'Perchspot - Obtaining SSL certificate...';
            add_header Content-Type text/plain;
        }
    }
}
EOF

echo -e "${BLUE}Step 2: Starting temporary nginx${NC}"

# Stop any running containers
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

# Start temporary nginx
docker run -d --name temp_nginx \
    -p 80:80 \
    -v "$(pwd)/nginx/nginx-temp.conf:/etc/nginx/nginx.conf:ro" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    nginx:alpine

echo -e "${BLUE}Step 3: Obtaining certificates from Let's Encrypt${NC}"

# Obtain certificates
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "${LETSENCRYPT_EMAIL}" \
    --agree-tos \
    --no-eff-email \
    --cert-name perchspot \
    -d "${DOMAIN}"

echo -e "${BLUE}Step 4: Cleaning up temporary nginx${NC}"
docker stop temp_nginx && docker rm temp_nginx
rm nginx/nginx-temp.conf

echo -e "${BLUE}Step 5: Setting up automatic renewal${NC}"

# Create renewal script
cat > scripts/renew-ssl.sh << 'RENEW_EOF'
#!/bin/bash
# Perchspot SSL Certificate Renewal
# Run via cron: 0 0 * * * /opt/perchspot/scripts/renew-ssl.sh >> /var/log/perchspot-ssl-renew.log 2>&1

cd /opt/perchspot

# Renew certificates
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot renew --quiet

# Reload nginx if renewal occurred
if [ $? -eq 0 ]; then
    docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload
fi
RENEW_EOF

chmod +x scripts/renew-ssl.sh

# Add to crontab if not already present
CRON_CMD="0 0 * * * /opt/perchspot/scripts/renew-ssl.sh >> /var/log/perchspot-ssl-renew.log 2>&1"
(crontab -l 2>/dev/null | grep -v "renew-ssl.sh"; echo "${CRON_CMD}") | crontab -

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}SSL Certificate Setup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Certificate location: certbot/conf/live/perchspot/"
echo "Auto-renewal: Configured (daily at midnight)"
echo ""
echo "You can now start the full production stack:"
echo "  docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "Verify HTTPS is working:"
echo "  curl https://${DOMAIN}/health"
