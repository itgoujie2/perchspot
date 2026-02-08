#!/bin/bash
# ===========================================
# Perchspot EC2 Setup Script (Amazon Linux 2023)
# ===========================================
# Run on a fresh Amazon Linux 2023 EC2 instance
# Usage: sudo bash ec2-setup-amazon-linux.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Perchspot EC2 Setup Script (Amazon Linux)${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run with sudo: sudo bash ec2-setup-amazon-linux.sh${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-ec2-user}"

echo -e "${BLUE}Step 1: Updating system packages${NC}"
dnf update -y

echo -e "${BLUE}Step 2: Installing Docker${NC}"
# Install Docker
dnf install -y docker git

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Add user to docker group
usermod -aG docker ${ACTUAL_USER}

echo -e "${GREEN}Docker installed successfully${NC}"
docker --version

echo -e "${BLUE}Step 3: Installing Docker Compose${NC}"
# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Verify installation
docker compose version

echo -e "${BLUE}Step 4: Installing Certbot for SSL${NC}"
dnf install -y certbot

echo -e "${BLUE}Step 5: Configuring firewall${NC}"
# Amazon Linux uses firewalld or iptables
# Check if firewalld is available
if command -v firewall-cmd &> /dev/null; then
    systemctl start firewalld
    systemctl enable firewalld
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
    echo -e "${GREEN}Firewall configured with firewalld${NC}"
else
    # Use iptables as fallback
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT
    iptables -A INPUT -p tcp --dport 80 -j ACCEPT
    iptables -A INPUT -p tcp --dport 443 -j ACCEPT
    echo -e "${GREEN}Firewall configured with iptables${NC}"
fi

echo -e "${BLUE}Step 6: Creating application directory${NC}"
mkdir -p /opt/perchspot
chown ${ACTUAL_USER}:${ACTUAL_USER} /opt/perchspot

echo -e "${BLUE}Step 7: Setting up log rotation${NC}"
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

echo -e "${BLUE}Step 8: Setting up swap (for t3.medium with 4GB RAM)${NC}"
# Create 2GB swap file if it doesn't exist
if [ ! -f /swapfile ]; then
    dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo -e "${GREEN}2GB swap created${NC}"
else
    echo "Swap already configured"
fi

echo -e "${BLUE}Step 9: Optimizing system settings${NC}"
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
echo "1. Clone the repository:"
echo "   cd /opt/perchspot"
echo "   git clone https://github.com/itgoujie2/perchspot.git ."
echo ""
echo "2. Create production environment file:"
echo "   ./scripts/init-production.sh"
echo "   nano .env.production  # Add your API keys"
echo ""
echo "3. Initialize SSL certificates:"
echo "   sudo ./scripts/init-ssl.sh yourdomain.com"
echo ""
echo "4. Start the application:"
echo "   docker compose -f docker-compose.prod.yml up -d"
echo ""
echo -e "${BLUE}Note: Log out and back in for docker group changes to take effect.${NC}"
echo -e "${BLUE}Or run: newgrp docker${NC}"
