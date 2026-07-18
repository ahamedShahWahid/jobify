/** Base path console mounts under. Empty string when served from its own
 *  subdomain (console.jobify.com); "/console" when served as a path prefix
 *  on the shared origin. Every console route/link is built from this so the
 *  eventual subdomain cutover is a hostname check (see App.tsx), not a code
 *  migration. */
export const CONSOLE_BASE = window.location.hostname.startsWith("console.") ? "" : "/console";
