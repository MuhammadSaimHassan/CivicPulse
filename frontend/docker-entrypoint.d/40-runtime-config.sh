#!/bin/sh
# Generate /config.js from environment variables at container start, so one
# image serves every environment (build once, deploy many). Only non-secret,
# display-level values belong here: everything in this file is public.
set -eu
# Allow a conservative character set so the value cannot break out of the JS string.
env_label=$(printf '%s' "${APP_ENVIRONMENT:-production}" | tr -cd 'A-Za-z0-9 ._()-' | cut -c1-40)
cat > /tmp/runtime/config.js <<JS
window.__CIVICPULSE_CONFIG__ = { environment: "${env_label}" };
JS
echo "40-runtime-config: wrote /tmp/runtime/config.js (environment=${env_label})"
