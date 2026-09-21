const CACHE_NAME = 'codasite-cache-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/landing/',
    '/static/manifest.json',
    // Add paths to your compiled CSS, JS, and key images here
];

// Install Event: Cache core assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// Activate Event: Clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch Event: Serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests or admin routes if needed
    if (event.request.method !== 'GET') return;

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }
            return fetch(event.request).then((networkResponse) => {
                // Optional: dynamically cache new requests
                return networkResponse;
            }).catch(() => {
                // Fallback for page navigation when offline
                if (event.request.mode === 'navigate') {
                    return caches.match('/');
                }
            });
        })
    );
});