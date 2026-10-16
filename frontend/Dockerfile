# Development image: the validation bench is deliberately disabled in production.
FROM node:22-bookworm-slim
ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund && chown -R node:node /app
COPY --chown=node:node tsconfig.json ./
COPY --chown=node:node app ./app
COPY --chown=node:node lib ./lib
COPY --chown=node:node scripts ./scripts
USER node
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "dev", "--hostname", "0.0.0.0"]
