/**
 * Service Worker for Breach Alert System
 * 
 * Features:
 * - Offline caching
 * - Background sync for missed alerts
 * - Push notifications
 * - Periodic sync for checking new breaches
 */

const CACHE_NAME = 'breach-alerts-v1';
const RUNTIME_CACHE = 'breach-alerts-runtime-v1';

// Assets to precache
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/offline.html'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Precaching assets');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME && name !== RUNTIME_CACHE)
          .map(name => {
            console.log('[Service Worker] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - network first with cache fallback
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // API requests - network first with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Clone and cache successful responses
          if (response.status === 200) {
            const responseToCache = response.clone();
            caches.open(RUNTIME_CACHE).then(cache => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        })
        .catch(() => {
          // Return cached response if available
          return caches.match(request).then(cachedResponse => {
            return cachedResponse || new Response(
              JSON.stringify({ error: 'Offline', cached: true }),
              { 
                headers: { 'Content-Type': 'application/json' },
                status: 503
              }
            );
          });
        })
    );
    return;
  }

  // Static assets - cache first
  event.respondWith(
    caches.match(request).then(cachedResponse => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request).then(response => {
        if (response.status === 200) {
          const responseToCache = response.clone();
          caches.open(RUNTIME_CACHE).then(cache => {
            cache.put(request, responseToCache);
          });
        }
        return response;
      });
    }).catch(() => {
      // Return offline page for navigation requests
      if (request.mode === 'navigate') {
        return caches.match('/offline.html');
      }
      return new Response('Network error', { status: 503 });
    })
  );
});

// Background Sync for Breach Alerts
const SYNC_TAG = 'sync-breach-alerts';

self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Sync event:', event.tag);

  if (event.tag === SYNC_TAG) {
    event.waitUntil(syncBreachAlerts());
  }
});

async function syncBreachAlerts() {
  console.log('[Service Worker] Syncing breach alerts...');

  try {
    const token = await getAuthToken();
    const response = await fetch('/api/breach-alerts/', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (response.ok) {
      const alerts = await response.json();
      
      // Notify all clients about synced alerts
      const clients = await self.clients.matchAll({ type: 'window' });
      clients.forEach(client => {
        client.postMessage({
          type: 'ALERTS_SYNCED',
          alerts: alerts
        });
      });

      console.log('[Service Worker] Sync completed successfully');
    }
  } catch (error) {
    console.error('[Service Worker] Sync failed:', error);
    throw error;
  }
}

// Push Notifications
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received');

  let data = { 
    title: 'Security Alert', 
    body: 'New breach detected' 
  };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body || 'Your credentials may have been compromised',
    icon: '/icons/breach-alert-192.png',
    badge: '/icons/badge-72.png',
    vibrate: [200, 100, 200],
    tag: data.breach_id || 'breach-alert',
    requireInteraction: true,
    actions: [
      { action: 'view', title: 'View Details', icon: '/icons/view.png' },
      { action: 'dismiss', title: 'Dismiss', icon: '/icons/dismiss.png' }
    ],
    data: {
      url: '/security/breach-alerts',
      breach_id: data.breach_id,
      severity: data.severity
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Security Alert', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notification clicked:', event.action);
  
  event.notification.close();

  if (event.action === 'view') {
    event.waitUntil(
      clients.openWindow(event.notification.data.url)
    );
  } else if (event.action === 'dismiss') {
    // Just close the notification
    return;
  } else {
    // Default action - focus or open app
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then(clientList => {
        for (let client of clientList) {
          if (client.url === '/' && 'focus' in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow('/');
        }
      })
    );
  }
});

// Periodic Background Sync (if supported)
self.addEventListener('periodicsync', (event) => {
  console.log('[Service Worker] Periodic sync:', event.tag);

  if (event.tag === 'sync-breach-alerts-periodic') {
    event.waitUntil(checkForNewBreaches());
  }
});

async function checkForNewBreaches() {
  console.log('[Service Worker] Checking for new breaches...');

  try {
    const token = await getAuthToken();
    const response = await fetch('/api/breach-alerts/check', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (response.ok) {
      const data = await response.json();
      
      if (data.new_alerts > 0) {
        await self.registration.showNotification('New Security Breach', {
          body: `${data.new_alerts} new breach alert${data.new_alerts > 1 ? 's' : ''} detected`,
          icon: '/icons/breach-alert-192.png',
          tag: 'new-breaches',
          requireInteraction: true
        });
      }
    }
  } catch (error) {
    console.error('[Service Worker] Failed to check for breaches:', error);
  }
}

// IndexedDB Helper Functions
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('BreachAlertsDB', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      if (!db.objectStoreNames.contains('settings')) {
        db.createObjectStore('settings', { keyPath: 'key' });
      }
    };
  });
}

async function getAuthToken() {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['settings'], 'readonly');
    const store = transaction.objectStore('settings');
    const request = store.get('auth_token');

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const result = request.result;
      resolve(result ? result.value : null);
    };
  });
}

async function storeAuthToken(token) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['settings'], 'readwrite');
    const store = transaction.objectStore('settings');
    const request = store.put({ key: 'auth_token', value: token });

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Message Handler
self.addEventListener('message', (event) => {
  console.log('[Service Worker] Message received:', event.data);

  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data.type === 'SYNC_ALERTS') {
    event.waitUntil(syncBreachAlerts());
  }

  if (event.data.type === 'STORE_TOKEN') {
    event.waitUntil(storeAuthToken(event.data.token));
  }
});

