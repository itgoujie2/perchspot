#!/bin/bash
# ===========================================
# Perchspot Database Backup Script
# ===========================================
# Usage: ./scripts/backup-db.sh [output_file]
# Example: ./scripts/backup-db.sh backup-2024-01-15.sql

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default output file with timestamp
OUTPUT_FILE="${1:-backup-$(date +%Y%m%d-%H%M%S).sql}"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Perchspot Database Backup${NC}"
echo -e "${GREEN}============================================${NC}"

# Check if running in production or development
if [ -f ".env.production" ]; then
    echo -e "${YELLOW}Production environment detected${NC}"
    source .env.production
    CONTAINER_NAME="perchspot_mysql"
else
    echo -e "${YELLOW}Development environment detected${NC}"
    CONTAINER_NAME="housing_mysql"
    MYSQL_ROOT_PASSWORD="root_password"
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}Error: MySQL container '${CONTAINER_NAME}' is not running${NC}"
    echo "Start the containers first: docker compose up -d mysql"
    exit 1
fi

echo "Backing up database from container: ${CONTAINER_NAME}"
echo "Output file: ${OUTPUT_FILE}"
echo ""

# Create backup
echo "Creating backup..."
docker exec ${CONTAINER_NAME} mysqldump \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --databases housing_analysis \
    > "${OUTPUT_FILE}"

# Compress if larger than 10MB
FILE_SIZE=$(stat -f%z "${OUTPUT_FILE}" 2>/dev/null || stat -c%s "${OUTPUT_FILE}" 2>/dev/null)
if [ "${FILE_SIZE}" -gt 10485760 ]; then
    echo "Compressing backup (size: $(numfmt --to=iec ${FILE_SIZE}))..."
    gzip "${OUTPUT_FILE}"
    OUTPUT_FILE="${OUTPUT_FILE}.gz"
fi

# Final size
FINAL_SIZE=$(stat -f%z "${OUTPUT_FILE}" 2>/dev/null || stat -c%s "${OUTPUT_FILE}" 2>/dev/null)

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Backup completed successfully!${NC}"
echo -e "${GREEN}============================================${NC}"
echo "File: ${OUTPUT_FILE}"
echo "Size: $(numfmt --to=iec ${FINAL_SIZE} 2>/dev/null || echo "${FINAL_SIZE} bytes")"
echo ""
echo "To restore on production:"
echo "  scp ${OUTPUT_FILE} ubuntu@<ec2-ip>:/opt/perchspot/"
echo "  ssh ubuntu@<ec2-ip>"
echo "  cd /opt/perchspot && ./scripts/restore-db.sh ${OUTPUT_FILE}"
