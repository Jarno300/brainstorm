# ── Build stage ──────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npx vite build

# ── Production stage: nginx serving built assets ──────────
FROM nginx:1.27-alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config that supports SPAs (client-side routing)
COPY nginx.default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
