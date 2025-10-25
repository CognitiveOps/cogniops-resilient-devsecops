# Ελάχιστο image με nginx
FROM nginx:1.25-alpine

# Προαιρετικά: αντικαθιστάς το default index.html
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 8080
# Αλλάζεις το default port 80 -> 8080 για Cloud Run
CMD ["nginx", "-g", "daemon off;"]
