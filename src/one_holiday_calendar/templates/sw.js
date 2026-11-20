const VERSION = "{{ version }}";
const ASSETS = {{ assets | tojson }};
const MAX_PAGES = {{ max_pages }};

const isAsset = (url) => {
  const { pathname, search } = new URL(url);
  return ASSETS.includes(pathname + search);
};

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((name) => name !== VERSION).map((name) => caches.delete(name)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  if (isAsset(request.url)) {
    event.respondWith(
      caches.match(request).then((cached) => cached ?? fetch(request)),
    );
  } else if (request.mode === "navigate") {
    event.respondWith(networkFirst(event));
  }
});

async function networkFirst(event) {
  const { request } = event;
  try {
    const response = await fetch(request);
    if (response.ok) event.waitUntil(cachePage(request.url));
    return response;
  } catch (error) {
    const cached = await caches.match(request.url);
    if (cached) return cached;
    throw error;
  }
}

// Caches a page with its own request: teeing the navigation's response would
// pump its body through this worker, and the page would abort if it stopped.
async function cachePage(url) {
  const response = await fetch(url, { headers: { Accept: "text/html" } });
  if (!response.ok) return;
  const cache = await caches.open(VERSION);
  await cache.put(url, response);
  await trim(cache);
}

async function trim(cache) {
  const pages = (await cache.keys()).filter((request) => !isAsset(request.url));
  const excess = Math.max(pages.length - MAX_PAGES, 0);
  await Promise.all(
    pages.slice(0, excess).map((request) => cache.delete(request)),
  );
}
