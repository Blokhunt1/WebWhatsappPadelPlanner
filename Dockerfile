# Use official Playwright Python image (contains all system dependencies for Playwright)
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Install Node.js (20.x)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Google Chrome Stable directly via standard .deb (avoids complex GPG key ring setup on minimal containers)
RUN apt-get update && apt-get install -y wget \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory to app root
WORKDIR /app

# Install Python requirements
COPY src/requirements.txt ./src/
RUN pip3 install --no-cache-dir -r src/requirements.txt

# Install Node requirements
COPY src/package*.json ./src/
WORKDIR /app/src
RUN npm install

# Copy all source code
COPY src/ ./

# Run the Node.js bot directly
CMD ["node", "bot.js"]
