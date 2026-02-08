#!/bin/bash
# ===========================================
# Perchspot EC2 Instance Setup Script
# ===========================================
# Run on a fresh Ubuntu 22.04 EC2 instance
# Usage: curl -fsSL https://raw.githubusercontent.com/<repo>/main/scripts/ec2-setup.sh | bash
# Or: ./scripts/ec2-setup.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Perchspot EC2 Setup Script${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run with sudo: sudo bash ec2-setup.sh${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-ubuntu}"

echo -e "${BLUE}Step 1: Updating system packages${NC}"
apt-get update
apt-get upgrade -y

echo -e "${BLUE}Step 2: Installing Docker${NC}"
# Remove old versions
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Install prerequisites
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
usermod -aG docker ${ACTUAL_USER}

# Start and enable Docker
systemctl start docker
systemctl enable docker

echo -e "${GREEN}Docker installed successfully${NC}"
docker --version

echo -e "${BLUE}Step 3: Installing Certbot for SSL${NC}"
apt-get install -y certbot

echo -e "${BLUE}Step 4: Configuring firewall (UFW)${NC}"
# Reset UFW to defaults
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (important - do this first!)
ufw allow 22/tcp

# Allow HTTP and HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Enable firewall
ufw --force enable

echo -e "${GREEN}Firewall configured${NC}"
ufw status

echo -e "${BLUE}Step 5: Creating application directory${NC}"
mkdir -p /opt/perchspot
chown ${ACTUAL_USER}:${ACTUAL_USER} /opt/perchspot

echo -e "${BLUE}Step 6: Setting up log rotation${NC}"
cat > /etc/logrotate.d/perchspot << 'EOF'
/opt/perchspot/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root adm
    sharedscripts
}
EOF

echo -e "${BLUE}Step 7: Setting up swap (for t3.medium with 4GB RAM)${NC}"
# Create 2GB swap file if it doesn't exist
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo -e "${GREEN}2GB swap created${NC}"
else
    echo "Swap already configured"
fi

echo -e "${BLUE}Step 8: Optimizing system settings${NC}"
# Increase file descriptors
cat >> /etc/security/limits.conf << 'EOF'
* soft nofile 65536
* hard nofile 65536
EOF

# Optimize network settings
cat >> /etc/sysctl.conf << 'EOF'
# Perchspot optimizations
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 1024
vm.swappiness = 10
EOF
sysctl -p

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}EC2 Setup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Clone or upload your repository:"
echo "   cd /opt/perchspot"
echo "   git clone <your-repo-url> ."
echo ""
echo "2. Create production environment file:"
echo "   cp .env.production.example .env.production"
echo "   nano .env.production  # Edit with your values"
echo ""
echo "3. Initialize SSL certificates:"
echo "   ./scripts/init-ssl.sh yourdomain.com"
echo ""
echo "4. Start the application:"
echo "   docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "5. Import database backup (if migrating):"
echo "   ./scripts/restore-db.sh backup.sql"
echo ""
echo -e "${BLUE}Note: Log out and back in for docker group changes to take effect.${NC}"
