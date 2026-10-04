#!/bin/sh
# Issues the first Let's Encrypt certificate for docker-compose.prod.yml.
# Usage (on the server, from the repo root, with DNS already pointing at it):
#   DOMAIN=app.example.com LETSENCRYPT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh
# Renewals afterwards are automatic (the certbot service renews via the webroot every 12h).
set -e

: "${DOMAIN:?Set DOMAIN, e.g. DOMAIN=app.example.com}"
: "${LETSENCRYPT_EMAIL:?Set LETSENCRYPT_EMAIL for expiry notices}"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "### Freeing port 80 for the one-time standalone challenge..."
$COMPOSE stop web 2>/dev/null || true

echo "### Requesting the certificate for $DOMAIN..."
$COMPOSE run --rm -p 80:80 --entrypoint "certbot certonly --standalone --preferred-challenges http \
  -d $DOMAIN --email $LETSENCRYPT_EMAIL --agree-tos --no-eff-email --non-interactive" certbot

echo "### Starting the stack with HTTPS..."
$COMPOSE up -d
echo "Done - https://$DOMAIN is live."
