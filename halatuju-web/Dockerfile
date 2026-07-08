FROM node:18-alpine AS base

# Install dependencies
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Build the app
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_PUBLIC_API_URL=https://halatuju-api-90344691621.asia-southeast1.run.app
ENV NEXT_PUBLIC_SUPABASE_URL=https://pbrrlyoyyiftckqvzvvo.supabase.co
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_ADKtlHpjwGRqWGpYd1JuCg_riPMtc3l
# Cloudflare Turnstile PUBLIC site key (secret stays in Supabase + the Edge Function).
ENV NEXT_PUBLIC_TURNSTILE_SITE_KEY=0x4AAAAAADi6qwQ0qHQQ5BSg

RUN npm run build

# Production runner
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
