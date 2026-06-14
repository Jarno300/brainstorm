FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start Vite dev server with host flag
# The API URL defaults to localhost:8000 which works because
# Docker maps the backend container port to the host
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]
