{% load static %}
const CACHE_VERSION = "v2";
const CACHE_NAME = `expense-tracker-${CACHE_VERSION}`;
const PRECACHE_URLS = [
  "/manifest.json",
  "{% static 'tracker/pwa/icon-192.png' %}",
  "{% static 'tracker/pwa/icon-512.png' %}",
  "{% static 'tracker/logo.png' %}",
  "{% static 'tracker/default-avatar.png' %}",
  "{% static 'tracker/dashboard.js' %}"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        const fetchPromise = fetch(event.request).then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        });
        if (cached) {
          event.waitUntil(fetchPromise);
          return cached;
        }
        return fetchPromise;
      })
    );
    return;
  }
});
