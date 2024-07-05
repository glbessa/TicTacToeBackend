# Use the official NGINX base image
FROM nginx:latest

# Copy the NGINX configuration file
COPY default.conf /etc/nginx/default.conf
COPY ssl.conf /etc/nginx/ssl.conf
COPY common.conf /etc/nginx/common.conf

COPY ./private/* /etc/ssl/private/

# Start NGINX when the container launches
CMD ["nginx", "-g", "daemon off;"]