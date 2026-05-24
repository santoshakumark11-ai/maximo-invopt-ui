# ─── Stage 1: Build ──────────────────────────────────────────────────────────
FROM node:20-slim AS builder

# Enable corepack for pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Copy lockfile and manifests first (layer cache)
COPY web/dashboard/package.json web/dashboard/pnpm-lock.yaml ./
COPY web/dashboard/.npmrc ./

# Install dependencies (no scripts — prevents prepare/husky running in CI)
RUN pnpm install --frozen-lockfile --ignore-scripts

# Copy source
COPY web/dashboard/ .

# Build — TypeScript check + Vite production bundle
ARG VITE_API_BASE_URL=/v1
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID=invopt-ui
ARG VITE_OIDC_REDIRECT
ARG VITE_USE_MSW=false
ARG VITE_FEATURE_FLAGS=
ARG VITE_TELEMETRY_URL=

RUN pnpm run build

# ─── Stage 2: Serve ──────────────────────────────────────────────────────────
# nginx:unprivileged runs as uid 101 — compatible with OpenShift's arbitrary UID
FROM nginxinc/nginx-unprivileged:1.25-alpine AS runtime

# Remove the default config
USER root
RUN rm /etc/nginx/conf.d/default.conf
USER 101

# Copy our custom nginx config
COPY web/dashboard/nginx.conf /etc/nginx/nginx.conf

# Copy the production build
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
