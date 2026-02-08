FROM nginx:alpine

# Install curl for healthcheck
RUN apk add --no-cache curl

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Create directory for Let's Encrypt
RUN mkdir -p /var/www/certbot

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
