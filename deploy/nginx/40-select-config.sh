#!/bin/sh
set -e

CERT_DIR=/etc/nginx/certs
CONFIG_DIR=/opt/sharenv-nginx

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
    cp "$CONFIG_DIR/https.conf" /etc/nginx/conf.d/default.conf
    echo "nginx: HTTPS enabled using $CERT_DIR/fullchain.pem"
else
    cp "$CONFIG_DIR/http.conf" /etc/nginx/conf.d/default.conf
    echo "nginx: HTTPS certificates not found; serving HTTP only"
fi
