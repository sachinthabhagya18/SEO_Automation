FROM node:22.14.0-bookworm-slim AS assets
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY backend/templates backend/templates
COPY backend/static/src backend/static/src
COPY scripts/copy-assets.mjs scripts/copy-assets.mjs
RUN npm run build

FROM python:3.14.0-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home app && mkdir -p /data/uploads && chown app:app /data/uploads
COPY --chown=app:app backend/ ./
COPY --from=assets --chown=app:app /build/backend/static/dist ./static/dist
USER app
EXPOSE 8000
