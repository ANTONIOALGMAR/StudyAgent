FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080

# Run as non-root (porta alta, sem privilégio de bind em <1024)
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run \
    && sed -i 's|/var/run/nginx.pid|/tmp/nginx.pid|' /etc/nginx/nginx.conf
USER nginx

# O healthcheck usa o proxy /api/ do próprio nginx: valida que o front está de
# pé E que ele alcança o backend (a única dependência real do serviço).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/api/health || exit 1
