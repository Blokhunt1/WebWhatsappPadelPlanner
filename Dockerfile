# Use official Playwright Python image (contains all system dependencies for Playwright)
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Install Node.js (20.x)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Google Chrome Stable to use for WhatsApp Web (bypasses bot detection better than bundled chromium)
RUN apt-get update && apt-get install -y wget gnupg \
    && wget -q -O - https://dl.ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
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
