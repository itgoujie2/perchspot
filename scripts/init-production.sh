#!/bin/bash
# ===========================================
# Perchspot Production Initialization Script
# ===========================================
# Generates secure random passwords and creates .env.production
# Usage: ./scripts/init-production.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Perchspot Production Initialization${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Check if .env.production already exists
if [ -f ".env.production" ]; then
    echo -e "${YELLOW}Warning: .env.production already exists!${NC}"
    read -p "Overwrite? This will generate new passwords. (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Initialization cancelled."
        exit 0
    fi
    # Backup existing file
    cp .env.production .env.production.backup.$(date +%Y%m%d-%H%M%S)
    echo "Existing file backed up."
fi

# Function to generate random string
generate_random() {
    local length=$1
    openssl rand -base64 $((length * 2)) | tr -dc 'A-Za-z0-9' | head -c $length
}

echo -e "${BLUE}Generating secure random credentials...${NC}"

# Generate passwords
MYSQL_ROOT_PASSWORD=$(generate_random 32)
MYSQL_PASSWORD=$(generate_random 32)
S3_ACCESS_KEY=$(generate_random 20)
S3_SECRET_KEY=$(generate_random 40)
JWT_SECRET_KEY=$(generate_random 64)
ADMIN_PASSWORD=$(generate_random 24)

# Prompt for domain
echo ""
read -p "Enter your domain (e.g., perchspot.com): " DOMAIN
read -p "Enter email for SSL notifications: " LETSENCRYPT_EMAIL

# Create .env.production
cat > .env.production << EOF
# ===========================================
# Perchspot Production Environment
# Generated: $(date)
# ===========================================
# WARNING: Keep this file secure and never commit to git!

# ===========================================
# Domain Configuration
# ===========================================
DOMAIN=${DOMAIN}

# ===========================================
# Database (MySQL)
# ===========================================
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD=${MYSQL_PASSWORD}

# ===========================================
# S3/MinIO Storage
# ===========================================
S3_ACCESS_KEY=${S3_ACCESS_KEY}
S3_SECRET_KEY=${S3_SECRET_KEY}

# ===========================================
# API Keys (FILL THESE IN MANUALLY)
# ===========================================
# Required: At least one LLM provider
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=

# Optional: Additional services
GOOGLE_MAPS_API_KEY=
GREATSCHOOLS_API_KEY=

# LLM Provider for Analysis
ANALYSIS_LLM_PROVIDER=gemini
ENABLE_PROPERTY_LLM_ANALYSIS=false

# ===========================================
# Stripe Payments (FILL IN LIVE KEYS)
# ===========================================
# IMPORTANT: Use LIVE keys (sk_live_, pk_live_) for production!
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# ===========================================
# Security (AUTO-GENERATED)
# ===========================================
JWT_SECRET_KEY=${JWT_SECRET_KEY}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# ===========================================
# Production Settings
# ===========================================
DEBUG=False
LOG_LEVEL=WARNING

# ===========================================
# SSL Certificate (Let's Encrypt)
# ===========================================
LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL}
EOF

# Set secure permissions
chmod 600 .env.production

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Production environment initialized!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "File created: .env.production"
echo ""
echo -e "${YELLOW}IMPORTANT: You must still add the following API keys:${NC}"
echo "  - ANTHROPIC_API_KEY or OPENAI_API_KEY or GEMINI_API_KEY"
echo "  - STRIPE_SECRET_KEY (sk_live_...)"
echo "  - STRIPE_PUBLISHABLE_KEY (pk_live_...)"
echo "  - STRIPE_WEBHOOK_SECRET"
echo ""
echo "Edit with: nano .env.production"
echo ""
echo -e "${BLUE}Generated credentials (save these securely):${NC}"
echo "  ADMIN_PASSWORD: ${ADMIN_PASSWORD}"
echo ""
echo -e "${RED}These credentials are only shown once!${NC}"
echo "The ADMIN_PASSWORD allows access to the admin portal."
