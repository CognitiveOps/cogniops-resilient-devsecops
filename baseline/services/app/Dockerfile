FROM nginx:1.27-alpine

# Minimal site so we always have a 200
RUN mkdir -p /usr/share/nginx/html
COPY index.html /usr/share/nginx/html/index.html

# Nginx on port 8080 (Cloud Run + tests both use this)
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=2s --retries=10 CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1

CMD ["nginx","-g","daemon off;"]
