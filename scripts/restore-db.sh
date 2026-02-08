#!/bin/bash
# ===========================================
# Perchspot Database Restore Script
# ===========================================
# Usage: ./scripts/restore-db.sh <backup_file>
# Example: ./scripts/restore-db.sh backup-2024-01-15.sql

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backup file provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo "Usage: ./scripts/restore-db.sh <backup_file>"
    exit 1
fi

BACKUP_FILE="$1"

# Check if file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}Error: Backup file '${BACKUP_FILE}' not found${NC}"
    exit 1
fi

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Perchspot Database Restore${NC}"
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
    echo "Start the containers first:"
    echo "  Development: docker compose up -d mysql"
    echo "  Production:  docker compose -f docker-compose.prod.yml up -d mysql"
    exit 1
fi

echo "Restoring database to container: ${CONTAINER_NAME}"
echo "Backup file: ${BACKUP_FILE}"
echo ""

# Warning
echo -e "${YELLOW}WARNING: This will overwrite the existing database!${NC}"
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# Decompress if gzipped
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    echo "Decompressing backup file..."
    gunzip -k "${BACKUP_FILE}"
    BACKUP_FILE="${BACKUP_FILE%.gz}"
    CLEANUP_FILE=true
fi

echo "Restoring database..."

# Restore the backup
docker exec -i ${CONTAINER_NAME} mysql \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    < "${BACKUP_FILE}"

# Cleanup decompressed file if we created it
if [ "${CLEANUP_FILE}" = true ]; then
    rm "${BACKUP_FILE}"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Database restored successfully!${NC}"
echo -e "${GREEN}============================================${NC}"

# Verify restoration
echo ""
echo "Verifying restoration..."
TABLES=$(docker exec ${CONTAINER_NAME} mysql \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'housing_analysis';")

echo "Tables in database: ${TABLES}"

# Check users table
USERS=$(docker exec ${CONTAINER_NAME} mysql \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    -N -e "SELECT COUNT(*) FROM housing_analysis.users;" 2>/dev/null || echo "0")

echo "Users in database: ${USERS}"

echo ""
echo "Restore complete. You may need to restart the backend:"
echo "  docker compose restart backend"
