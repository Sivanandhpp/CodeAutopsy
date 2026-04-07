# ─────────────────────────────────────────────────────────────
# CodeAutopsy Frontend — Production Dockerfile
# Stage 1: Build with Node
# Stage 2: Serve with Nginx
# ─────────────────────────────────────────────────────────────

# ─── Build stage ─────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first for Docker layer caching
COPY package.json package-lock.json ./
RUN npm ci --silent

# Copy source and build
COPY . .
RUN npm run build

# ─── Production stage ────────────────────────────────────────
FROM nginx:alpine AS production

# Copy custom nginx config for SPA routing
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA fallback: route all non-file requests to index.html
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://backend:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
    } \
    location /health { \
        proxy_pass http://backend:8000; \
    } \
    # SSE streams need special proxy config \
    location /api/analyze/stream { \
        proxy_pass http://backend:8000; \
        proxy_set_header Connection ""; \
        proxy_http_version 1.1; \
        chunked_transfer_encoding off; \
        proxy_buffering off; \
        proxy_cache off; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
