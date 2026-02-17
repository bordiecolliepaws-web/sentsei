// SentSay Service Worker — Offline/PWA support
const CACHE_NAME = 'sentsay-v4';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/js/app.js',
  '/js/state.js',
  '/js/api.js',
  '/js/ui.js',
  '/js/srs.js',
  '/js/quiz.js',
  '/js/history.js',
  '/js/shortcuts.js',
  '/manifest.json',
  'https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap'
];
const API_CACHE = 'sentsay-api-v1';
const CACHEABLE_API = ['/api/learn', '/api/learn-multi', '/api/surprise'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== API_CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // API requests: network-first, cache successful POST/GET responses for offline
  if (CACHEABLE_API.some(path => url.pathname.startsWith(path))) {
    event.respondWith(
      fetch(event.request.clone()).then(response => {
        if (response.ok) {
          // Cache a copy keyed by URL + body hash
          const cloned = response.clone();
          cacheApiResponse(event.request, cloned);
        }
        return response;
      }).catch(() => {
        // Offline: try to find cached response
        return matchApiCache(event.request).then(cached => {
          if (cached) return cached;
          return new Response(JSON.stringify({error: 'You are offline. Previously learned sentences are available from history.'}), {
            status: 503,
            headers: {'Content-Type': 'application/json'}
          });
        });
      })
    );
    return;
  }

  // Static assets: cache-first
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (response.ok && url.origin === self.location.origin) {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
        }
        return response;
      });
    }).catch(() => {
      // Offline fallback for navigation
      if (event.request.mode === 'navigate') {
        return caches.match('/');
      }
    })
  );
});

// Cache API responses keyed by a hash of the request body
async function cacheApiResponse(request, response) {
  const cache = await caches.open(API_CACHE);
  const key = await apiCacheKey(request);
  await cache.put(key, response);
}

async function matchApiCache(request) {
  const cache = await caches.open(API_CACHE);
  const key = await apiCacheKey(request);
  return cache.match(key);
}

async function apiCacheKey(request) {
  const url = new URL(request.url);
  let body = '';
  if (request.method === 'POST') {
    try {
      body = await request.clone().text();
    } catch {}
  }
  // Create a deterministic cache key URL
  return new Request(url.pathname + '?_sw_body=' + encodeURIComponent(body));
}
