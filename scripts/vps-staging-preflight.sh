#!/usr/bin/env bash
# Read-only server inventory. Never clones, edits DNS, reads wp-config or prints secrets.
set -u
managed_domain="${1:-denimyard.com}"
if [[ "$managed_domain" != "denimyard.com" ]]; then
  printf '%s\n' 'This preflight is scoped to denimyard.com.' >&2
  exit 2
fi
printf 'Server: %s\n' "$(hostname)"
printf 'SSH account: %s\n' "$(id -un)"
if [[ -r /etc/ssh/ssh_host_ed25519_key.pub ]]; then
  ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
fi
if ! command -v virtualmin >/dev/null 2>&1; then
  printf '%s\n' 'Virtualmin CLI unavailable for this account.' >&2
  exit 3
fi
source_domain=$(virtualmin list-domains --domain "$managed_domain" --name-only 2>/dev/null || true)
if [[ "$source_domain" != "$managed_domain" ]]; then
  printf '%s\n' 'Managed domain not confirmed; no staging operation should proceed.' >&2
  exit 4
fi
printf 'Source domain confirmed: %s\n' "$source_domain"
target_domain="staging.${managed_domain}"
existing_target=$(virtualmin list-domains --domain "$target_domain" --name-only 2>/dev/null || true)
if [[ "$existing_target" == "$target_domain" ]]; then
  printf 'Staging target already exists: %s (inspect before any change)\n' "$target_domain"
else
  printf 'Staging target not found: %s\n' "$target_domain"
fi
if command -v wp >/dev/null 2>&1; then wp --allow-root --version; fi
if command -v php >/dev/null 2>&1; then php -r 'echo "CLI PHP: ", PHP_VERSION, PHP_EOL;'; fi
printf '%s\n' 'Read-only preflight complete. No site, database, DNS, payment or mail setting changed.'
