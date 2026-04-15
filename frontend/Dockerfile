FROM node:20-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package.json and install deps.
# NOTE: we intentionally don't use `npm ci` + committed lockfile because the
# lockfile has been stale in git since before this deployment (package.json
# was bumped without regenerating). Fixing it properly + CI is a separate PR.
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

# Build-time env var for API URL (will be set during Cloud Build)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:20-slim AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER node
EXPOSE 3000

CMD ["node", "server.js"]
