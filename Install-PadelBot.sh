#!/bin/bash
echo "==========================================="
echo "Peakz Padel WhatsApp Bot Installer (Linux)"
echo "==========================================="
echo ""
echo "Updating apt and installing dependencies..."
sudo apt-update
sudo apt install -y python3 python3-venv python3-pip nodejs npm

echo "Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r src/requirements.txt
playwright install
playwright install-deps

echo "Setting up Node.js environment..."
cd src
npm install
cd ..

echo ""
echo "==========================================="
echo "Installation Complete!"
echo "Run './Start-PadelBot.sh' to boot the bot."
echo "==========================================="
