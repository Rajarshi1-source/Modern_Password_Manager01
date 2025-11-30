/**
 * Service Worker Registration Utility
 * 
 * Handles service worker lifecycle, updates, and notifications.
 */

const isLocalhost = Boolean(
  window.location.hostname === 'localhost' ||
  window.location.hostname === '[::1]' ||
  window.location.hostname.match(/^127(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}$/)
);

/**
 * Register service worker
 * @param {Object} config - Configuration options
 * @param {Function} config.onSuccess - Callback when SW is installed
 * @param {Function} config.onUpdate - Callback when SW has an update
 * @param {Function} config.onOfflineReady - Callback when offline functionality is ready
 */
export function register(config) {
  if ('serviceWorker' in navigator) {
    // Wait for page load
    window.addEventListener('load', () => {
      const swUrl = `/service-worker.js`;

      if (isLocalhost) {
        // Check if service worker exists on localhost
        checkValidServiceWorker(swUrl, config);

        navigator.serviceWorker.ready.then(() => {
          console.log(
            '[SW] This web app is being served cache-first by a service worker.'
          );
        });
      } else {
        // Register service worker
        registerValidSW(swUrl, config);
      }

      // Request notification permission
      requestNotificationPermission();
      
      // Setup background sync
      setupBackgroundSync();
    });

    // Listen for messages from service worker
    navigator.serviceWorker.addEventListener('message', (event) => {
      handleServiceWorkerMessage(event, config);
    });
  }
}

/**
 * Register valid service worker
 */
function registerValidSW(swUrl, config) {
  navigator.serviceWorker
    .register(swUrl)
    .then((registration) => {
      console.log('[SW] Service Worker registered:', registration);

      registration.onupdatefound = () => {
        const installingWorker = registration.installing;
        if (installingWorker == null) {
          return;
        }

        installingWorker.onstatechange = () => {
          if (installingWorker.state === 'installed') {
            if (navigator.serviceWorker.controller) {
              // New update available
              console.log('[SW] New content is available; please refresh.');

              if (config && config.onUpdate) {
                config.onUpdate(registration);
              }

              // Show update notification
              showUpdateNotification(registration);
            } else {
              // Content cached for offline use
              console.log('[SW] Content is cached for offline use.');

              if (config && config.onSuccess) {
                config.onSuccess(registration);
              }

              if (config && config.onOfflineReady) {
                config.onOfflineReady();
              }
            }
          }
        };
      };

      // Store auth token in service worker
      const token = localStorage.getItem('token');
      if (token && registration.active) {
        registration.active.postMessage({
          type: 'STORE_TOKEN',
          token: token
        });
      }

      // Register periodic sync if supported
      if ('periodicSync' in registration) {
        registration.periodicSync
          .register('sync-breach-alerts-periodic', {
            minInterval: 24 * 60 * 60 * 1000 // 24 hours
          })
          .then(() => {
            console.log('[SW] Periodic sync registered');
          })
          .catch((err) => {
            console.warn('[SW] Periodic sync registration failed:', err);
          });
      }
    })
    .catch((error) => {
      console.error('[SW] Error during service worker registration:', error);
    });
}

/**
 * Check if service worker exists
 */
function checkValidServiceWorker(swUrl, config) {
  fetch(swUrl, {
    headers: { 'Service-Worker': 'script' },
  })
    .then((response) => {
      const contentType = response.headers.get('content-type');
      if (
        response.status === 404 ||
        (contentType != null && contentType.indexOf('javascript') === -1)
      ) {
        // Service worker not found, reload the page
        navigator.serviceWorker.ready.then((registration) => {
          registration.unregister().then(() => {
            window.location.reload();
          });
        });
      } else {
        // Service worker found, proceed normally
        registerValidSW(swUrl, config);
      }
    })
    .catch(() => {
      console.log('[SW] No internet connection. App is running in offline mode.');
    });
}

/**
 * Request notification permission
 */
function requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission().then((permission) => {
      console.log('[SW] Notification permission:', permission);
    });
  }
}

/**
 * Setup background sync
 */
function setupBackgroundSync() {
  if ('serviceWorker' in navigator && 'sync' in navigator.serviceWorker) {
    // Listen for online event
    window.addEventListener('online', () => {
      console.log('[SW] Back online - triggering background sync');
      navigator.serviceWorker.ready.then((registration) => {
        return registration.sync.register('sync-breach-alerts');
      });
    });
  }
}

/**
 * Show update notification
 */
function showUpdateNotification(registration) {
  const shouldUpdate = window.confirm(
    'New version available! Click OK to update now.'
  );

  if (shouldUpdate) {
    if (registration.waiting) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' });
      
      // Reload page when new service worker takes over
      let refreshing = false;
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
          refreshing = true;
          window.location.reload();
        }
      });
    }
  }
}

/**
 * Handle messages from service worker
 */
function handleServiceWorkerMessage(event, config) {
  const { data } = event;

  switch (data.type) {
    case 'ALERTS_SYNCED':
      console.log('[SW] Alerts synced:', data.alerts.length);
      // Dispatch custom event for components to listen to
      window.dispatchEvent(new CustomEvent('alertsSynced', {
        detail: {
          alerts: data.alerts,
          queuedCount: data.queuedCount
        }
      }));
      break;

    case 'CACHE_UPDATED':
      console.log('[SW] Cache updated');
      break;

    default:
      console.log('[SW] Unknown message type:', data.type);
  }
}

/**
 * Unregister service worker
 */
export function unregister() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready
      .then((registration) => {
        registration.unregister();
      })
      .catch((error) => {
        console.error(error.message);
      });
  }
}

/**
 * Trigger manual sync
 */
export function triggerSync() {
  if ('serviceWorker' in navigator && 'sync' in navigator.serviceWorker) {
    navigator.serviceWorker.ready
      .then((registration) => {
        return registration.sync.register('sync-breach-alerts');
      })
      .then(() => {
        console.log('[SW] Background sync registered');
      })
      .catch((error) => {
        console.error('[SW] Background sync failed:', error);
      });
  }
}

/**
 * Check if offline
 */
export function isOffline() {
  return !navigator.onLine;
}

/**
 * Get registration
 */
export async function getRegistration() {
  if ('serviceWorker' in navigator) {
    return await navigator.serviceWorker.getRegistration();
  }
  return null;
}

export default {
  register,
  unregister,
  triggerSync,
  isOffline,
  getRegistration
};

