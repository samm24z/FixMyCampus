# syntax=docker/dockerfile:1
# Targets: `dev` (Vite dev server, used by docker-compose.yml) and `prod` (static build behind nginx).

# ---------- dev ----------
FROM node:22-alpine AS dev
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* /app/
RUN npm install
COPY frontend /app
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---------- prod build ----------
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci
COPY frontend /app

# Same origin through nginx. These values are public: they end up in the JS bundle.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
# Empty means "use frontend/.env if it is in the build context". An empty variable would beat
# the file in Vite, so the loop unsets any that are empty before building.
ARG VITE_SUPABASE_URL=
ARG VITE_SUPABASE_ANON_KEY=
ARG VITE_ALLOWED_EMAIL_DOMAIN=
RUN for v in VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY VITE_ALLOWED_EMAIL_DOMAIN; do \
      eval "val=\$$v"; [ -n "$val" ] || unset "$v"; \
    done; \
    npm run build

# ---------- prod runtime ----------
# Unprivileged nginx: runs as uid 101 and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27.5-alpine AS prod
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:8080/healthz || exit 1
