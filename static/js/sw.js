const CACHE_NAME = 'calamansense-pwa-v1';

const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/static/css/fonts.css',
  '/static/css/style.css',
  '/static/css/branding.css',
  '/static/css/theme.css',
  '/static/css/dashboard.css',
  '/static/css/settings.css',
  '/static/images/calamansense-logo-transparent.png',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/js/pwa-install.js'
];

// Install: Pre-cache essential static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('Some assets failed to precache:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean up older cache versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Strategy based on request type
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Ignore non-GET requests (e.g. POST, PUT, DELETE)
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  // Ignore Django admin or media uploads
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/media/')) {
    return;
  }

  // Navigation requests (HTML pages): Network-First with cache fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          // Clone and cache the updated HTML for offline review
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return networkResponse;
        })
        .catch(async () => {
          const cachedResponse = await caches.match(request);
          if (cachedResponse) {
            return cachedResponse;
          }
          // Return generic offline page if navigation completely fails
          return new Response(
            `<!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>CalamanSense - Offline</title>
              <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f4f6f8; color: #1c252e; text-align: center; padding: 20px; }
                .card { background: white; padding: 32px 24px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); max-width: 400px; width: 100%; }
                h1 { color: #086839; font-size: 22px; margin: 12px 0 8px; }
                p { color: #637381; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }
                button { background: #086839; color: white; border: none; padding: 12px 24px; font-size: 14px; font-weight: 600; border-radius: 8px; cursor: pointer; }
              </style>
            </head>
            <body>
              <div class="card">
                <img src="/static/images/icon-192.png" width="72" height="72" alt="CalamanSense Logo" style="border-radius: 14px;">
                <h1>You are currently offline</h1>
                <p>Please check your internet connection or make sure the CalamanSense server is running.</p>
                <button onclick="window.location.reload()">Retry Connection</button>
              </div>
            </body>
            </html>`,
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        })
    );
    return;
  }

  // Static assets (CSS, JS, Fonts, Images): Cache-First with Network fallback
  if (
    url.pathname.startsWith('/static/') ||
    url.pathname === '/manifest.json' ||
    url.hostname === 'fonts.googleapis.com' ||
    url.hostname === 'fonts.gstatic.com'
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          // Revalidate in background for freshest static files
          fetch(request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
            }
          }).catch(() => {});
          return cachedResponse;
        }

        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // Default: Network fetch
  event.respondWith(fetch(request));
});

