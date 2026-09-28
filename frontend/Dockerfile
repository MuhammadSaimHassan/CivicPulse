# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# CivicPulse frontend. Node BUILDS, nginx SERVES; the final image contains the
# static bundle and nginx — no Node, no node_modules, no source.
#
# nginx: the assignment names 1.27-alpine, which upstream no longer patches.
# We pin the current stable line (1.30.5) so the Trivy HIGH/CRITICAL gate can
# pass. Same image family, same config. See README "Deviations".
# ---------------------------------------------------------------------------
ARG NODE_IMAGE=node:22.23.3-alpine3.24
ARG NGINX_IMAGE=nginx:1.30.5-alpine3.24

FROM ${NODE_IMAGE} AS build
WORKDIR /src
# Lockfile first: `npm ci` is cached until dependencies change.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html openapi.json ./
COPY public ./public
COPY src ./src
RUN npx tsc --noEmit && npx vite build

FROM ${NGINX_IMAGE} AS runtime
# Run as the image's unprivileged `nginx` user (uid 101): listen on 8080, keep
# the pid file, temp dirs, rendered config and runtime config.js under /tmp so
# the rest of the filesystem can be read-only.
RUN rm -f /etc/nginx/conf.d/default.conf \
 && mkdir -p /tmp/nginx /tmp/runtime \
 && chown -R 101:101 /tmp/nginx /tmp/runtime /var/cache/nginx
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY --chmod=0755 docker-entrypoint.d/40-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
COPY --from=build /src/dist /usr/share/nginx/html
ENV NGINX_ENVSUBST_OUTPUT_DIR=/tmp/nginx \
    NGINX_ENVSUBST_FILTER=BACKEND_UPSTREAM \
    BACKEND_UPSTREAM=http://backend:8000 \
    APP_ENVIRONMENT=production
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
# The base image's ENTRYPOINT renders templates and runs docker-entrypoint.d/*,
# then execs this CMD (exec form: nginx is PID 1 and receives the base image's
# STOPSIGNAL, SIGQUIT = graceful shutdown that finishes in-flight requests).
CMD ["nginx", "-g", "daemon off;"]
