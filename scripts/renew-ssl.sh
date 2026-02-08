#!/bin/bash
# ===========================================
# Perchspot SSL Certificate Renewal
# ===========================================
# Run via cron: 0 0 * * * /opt/perchspot/scripts/renew-ssl.sh >> /var/log/perchspot-ssl-renew.log 2>&1
# This script is automatically set up by init-ssl.sh

set -e

cd /opt/perchspot

echo "$(date): Starting SSL renewal check..."

# Renew certificates
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot renew --quiet

# Check if renewal occurred (certbot exits 0 either way)
if [ $? -eq 0 ]; then
    echo "$(date): Certificate renewal completed."

    # Reload nginx to pick up new certificates
    docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload
    echo "$(date): Nginx reloaded."
fi

echo "$(date): SSL renewal check finished."
