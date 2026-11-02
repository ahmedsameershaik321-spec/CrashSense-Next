FROM node:22-bookworm-slim AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app
ARG CRASHSENSE_BACKEND_ORIGIN=http://backend:8000
ARG NEXT_PUBLIC_API_BASE_URL=/backend-api/api/v1
ARG NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB=100
ENV CRASHSENSE_BACKEND_ORIGIN=$CRASHSENSE_BACKEND_ORIGIN \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB=$NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs nextjs
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
RUN mkdir -p public && chown nextjs:nodejs public
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
