/**
 * Runtime (not build-time) configuration.
 *
 * /config.js is written by the nginx container at START-UP from environment
 * variables (see docker-entrypoint.d/40-runtime-config.sh), and loaded by
 * index.html before the bundle. Only non-secret, display-level values live
 * here — anything in a browser is public. The API address is deliberately NOT
 * configuration at all: the app calls relative /api URLs.
 */
export interface RuntimeConfig {
  environment: string;
}

declare global {
  interface Window {
    __CIVICPULSE_CONFIG__?: Partial<RuntimeConfig>;
  }
}

export function runtimeConfig(): RuntimeConfig {
  const cfg = typeof window !== "undefined" ? window.__CIVICPULSE_CONFIG__ : undefined;
  return { environment: cfg?.environment || "local" };
}
