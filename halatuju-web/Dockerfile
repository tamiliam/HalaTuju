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

# The design sandbox is built from this same image, with two arguments changed. Both DEFAULT to
# the production values, so an ordinary build is byte-identical to before this line existed —
# `SANDBOX` empty means `pageExtensions` never picks up `page.sandbox.tsx` and no sandbox code
# enters the bundle at all (see next.config.js).
#
#   docker build --build-arg SANDBOX=1 --build-arg API_URL=https://api.invalid .
#
# API_URL is deliberately pointed at an unresolvable host for the sandbox: the fixtures answer
# every call, so a request escaping to the network is a bug, and it should fail rather than
# quietly reach the live API.
ARG SANDBOX=
ARG API_URL=https://halatuju-api-90344691621.asia-southeast1.run.app
ENV NEXT_PUBLIC_SANDBOX=${SANDBOX}
ENV NEXT_PUBLIC_API_URL=${API_URL}
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
