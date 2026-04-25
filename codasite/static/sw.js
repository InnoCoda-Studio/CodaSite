
const CACHE_NAME = 'codasite-v2'; // bump version every change

const STATIC_ASSETS = [
    '/static/css/output.css',
    '/static/images/CodaSite_logo.png',
    '/static/images/icon-192.png'
];

// 🚀 INSTALL
self.addEventListener('install', event => {
    self.skipWaiting(); // activate immediately

    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('Caching static assets...');
            return cache.addAll(STATIC_ASSETS);
        })
    );
});

// 🚀 ACTIVATE
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.map(key => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key); // delete old cache
                    }
                })
            );
        })
    );

    self.clients.claim();
});

// 🚀 FETCH STRATEGY
self.addEventListener('fetch', event => {
    const request = event.request;

    // 🧠 NEVER cache HTML (Django pages)
    if (request.headers.get('accept').includes('text/html')) {
        event.respondWith(fetch(request));
        return;
    }

    // 🧠 STATIC FILES: cache first, fallback to network
    if (request.url.includes('/static/')) {
        event.respondWith(
            caches.match(request).then(cached => {
                return cached || fetch(request);
            })
        );
        return;
    }

    // 🧠 DEFAULT: network first
    event.respondWith(
        fetch(request).catch(() => caches.match(request))
    );
});

// ///////////////////////////////////

// // static/sw.js
// const CACHE_NAME = 'codasite-v1';
// const urlsToCache = [
//     '/',
//     '/static/css/dist/styles.css', // 🎯 This is your compiled Tailwind CSS
//     '/static/images/CodaSite_logo.png',     // Your InnoCoda logo
//     '/static/images/icon-192.png'  // PWA Icon
// ];

// self.addEventListener('install', event => {
//     event.waitUntil(
//         caches.open(CACHE_NAME).then(cache => {
//             console.log('CodaSite: Caching Assets');
//             return cache.addAll(urlsToCache);
//         })
//     );
// });

// self.addEventListener('fetch', event => {
//     event.respondWith(
//         caches.match(event.request).then(response => {
//             return response || fetch(event.request);
//         })
//     );
// });