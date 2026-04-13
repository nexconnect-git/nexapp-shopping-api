#!/bin/bash
# NexConnect AWS EC2 Deployment Script
# 
# Usage: ./deploy.sh
# Run this script on your EC2 instance (Ubuntu 22.04+ recommended)

set -e

echo "🚀 Starting NexConnect Deployment Process..."

# 1. System Updates & Docker Installation
if ! command -v docker &> /dev/null
then
    echo "📦 Docker not found. Installing Docker & Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    echo "✅ Docker installed successfully."
    echo "⚠️ NOTE: You may need to log out and log back in for docker group permissions to take effect."
else
    echo "✅ Docker is already installed."
fi

# 2. Check for .env file
if [ ! -f .env ]; then
    if [ -f .env.prod.example ]; then
        echo "⚠️ .env file not found. Copying from .env.prod.example..."
        cp .env.prod.example .env
        echo "🛑 PLEASE STOP and edit the .env file with your actual production secrets before continuing!"
        echo "Run: nano .env"
        exit 1
    else
        echo "❌ .env file is missing and no example found. Cannot proceed."
        exit 1
    fi
fi

# 3. Build & Deploy
echo "🔨 Building Docker Images for Production..."
sudo docker compose -f docker-compose.prod.yml build

echo "🚢 Starting Containers..."
sudo docker compose -f docker-compose.prod.yml up -d

echo "🧹 Cleaning up old images..."
sudo docker image prune -f

echo "🎉 Deployment Complete!"
echo "Check the status using: docker ps"
echo "View logs using: docker compose -f docker-compose.prod.yml logs -f"
