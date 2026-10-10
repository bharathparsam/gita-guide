const CACHE_VERSION = "gita-guide-shell-v1";
const APP_SHELL = "/";
const CORE_ASSETS = [
  APP_SHELL,
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-512.png",
  "/icons/apple-touch-icon.png",
];

async function cacheResponse(cache, request) {
  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

async function cacheShell() {
  const cache = await caches.open(CACHE_VERSION);
  const shellResponse = await fetch(APP_SHELL, { cache: "reload" });
  if (!shellResponse.ok) throw new Error("Unable to cache the app shell");

  await cache.put(APP_SHELL, shellResponse.clone());
  const html = await shellResponse.text();
  const assetPaths = Array.from(html.matchAll(/(?:src|href)="([^"#]+)"/g), (match) => match[1])
    .filter((path) => path.startsWith("/_next/static/"));

  await Promise.allSettled([
    ...CORE_ASSETS.slice(1).map((path) => cacheResponse(cache, path)),
    ...assetPaths.map((path) => cacheResponse(cache, path)),
  ]);
}

self.addEventListener("install", (event) => {
  event.waitUntil(cacheShell().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(async (response) => {
          if (response.ok) {
            const cache = await caches.open(CACHE_VERSION);
            await cache.put(APP_SHELL, response.clone());
          }
          return response;
        })
        .catch(async () => (await caches.match(APP_SHELL)) || Response.error()),
    );
    return;
  }

  const isStaticAsset =
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/manifest.webmanifest";
  if (!isStaticAsset) return;

  event.respondWith(
    caches.match(request).then(async (cached) => (
      cached || cacheResponse(await caches.open(CACHE_VERSION), request)
    )),
  );
});
