// AI Pulse Service Worker — Network-First Strategy for Feed & API
const CACHE_NAME = 'ai-pulse-v2';
const STATIC_ASSETS = [
  '/',
  '/feed',
  '/saved',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      )
    )
  );
  self.clients.claim();
});

// Network-First for API and dynamic feed routes; fallback to cache/offline
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-First for API routes and feed navigation
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/feed') || url.pathname.startsWith('/items/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // If good response, clone and update cache
          if (response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => {
          // Offline fallback
          return caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;
            // Return JSON error for API requests when offline
            if (url.pathname.startsWith('/api/')) {
              return new Response(
                JSON.stringify({ error: 'You are currently offline. Showing cached content where available.' }),
                { headers: { 'Content-Type': 'application/json' }, status: 503 }
              );
            }
            return caches.match('/feed');
          });
        })
    );
    return;
  }

  // Cache-First for static assets (js, css, images)
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
