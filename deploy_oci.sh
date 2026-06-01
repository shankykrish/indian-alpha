#!/bin/bash
# Automated OCI deploy script for Indian-Alpha

set -e

echo "===================================================="
echo "🚀 Starting Automated Indian-Alpha Deployment on OCI"
echo "===================================================="

# 1. Update system packages
echo "📦 Updating OS Packages..."
sudo apt-get update -y

# 2. Install Git, Docker, and Docker Compose
echo "🛠️ Installing Git, Docker, and Docker-Compose..."
sudo apt-get install -y git docker.io docker-compose

# 3. Configure Docker permissions
echo "🔒 Configuring Docker permissions..."
sudo usermod -aG docker ubuntu

# 4. Clone or pull repository
echo "📥 Setting up Indian-Alpha code..."
cd /home/ubuntu
if [ -d "indian-alpha" ]; then
    echo "Existing folder found. Pulling latest commits..."
    cd indian-alpha
    git pull origin main
else
    echo "Cloning fresh repository..."
    git clone https://github.com/shankykrish/indian-alpha.git
    cd indian-alpha
fi

# 5. Create state directory and set open permissions so Docker container can write to it
echo "📂 Creating state directory and setting permissions..."
mkdir -p state state/history
sudo chmod -R 777 state

# 6. Launch Docker containers in detached mode
echo "🐳 Launching Docker containers..."
sudo docker-compose down || true
sudo docker-compose up --build -d

echo "===================================================="
echo "🟢 DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "===================================================="
echo "Your Streamlit dashboard is building and launching."
echo "You can access it at: http://152.70.66.16:8501"
echo "===================================================="
