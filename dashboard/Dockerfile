# dashboard/Dockerfile
# Serve static dashboard files with nginx:alpine

FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy dashboard assets
COPY dashboard/index.html /usr/share/nginx/html/
COPY dashboard/css /usr/share/nginx/html/css
COPY dashboard/js /usr/share/nginx/html/js
COPY dashboard/assets /usr/share/nginx/html/assets

# Custom nginx config for SPA-like behavior and gzip
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    gzip on; \
    gzip_vary on; \
    gzip_types text/plain text/css application/javascript application/json; \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1
