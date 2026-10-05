FROM node:24-slim
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# Rewrites are resolved at build time.
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start", "--port", "3000"]
