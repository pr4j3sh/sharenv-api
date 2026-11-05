FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY http.conf https.conf /opt/sharenv-nginx/
COPY 40-select-config.sh /docker-entrypoint.d/40-select-config.sh

RUN chmod +x /docker-entrypoint.d/40-select-config.sh
