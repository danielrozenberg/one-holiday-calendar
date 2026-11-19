const VERSION = "{{ version }}";
const ASSETS = {{ assets | tojson }};
const MAX_PAGES = 20;

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
    event.respondWith(networkFirst(request));
  }
});

async function networkFirst(request) {
  const cache = await caches.open(VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      await trim(cache);
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function trim(cache) {
  const pages = (await cache.keys()).filter((request) => !isAsset(request.url));
  await Promise.all(
    pages.slice(0, -MAX_PAGES).map((request) => cache.delete(request)),
  );
}
