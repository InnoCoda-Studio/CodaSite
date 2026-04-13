// static/sw.js
const CACHE_NAME = 'codasite-v1';
const urlsToCache = [
    '/',
    '/static/css/dist/styles.css', // 🎯 This is your compiled Tailwind CSS
    '/static/images/CodaSite_logo.png',     // Your InnoCoda logo
    '/static/images/icon-192.png'  // PWA Icon
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('CodaSite: Caching Assets');
            return cache.addAll(urlsToCache);
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});