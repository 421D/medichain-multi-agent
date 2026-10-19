# --- Stage 1: build the Vite production bundle ---
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps with the same flag we use locally (radix-ui + testing-library
# peer-dep conflict with lovable-tagger). package-lock.json is the source of truth.
COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

# Build → ./dist (static assets, ready to serve)
RUN npm run build

# --- Stage 2: nginx serving the static bundle + reverse-proxying to the backend ---
FROM nginx:1.27-alpine

RUN apk add --no-cache curl

# Static assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Reverse-proxy /api and /ws to the backend service on the compose network
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Healthcheck — nginx serves index.html as 200.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost/ -o /dev/null || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
