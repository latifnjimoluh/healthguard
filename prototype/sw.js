const CACHE_NAME = 'healthguard-cache-v1';
const ASSETS_TO_CACHE = [
  '/app/screens/e1_login.html',
  '/app/screens/e2_dashboard.html',
  '/app/screens/e3_consultation.html',
  '/app/screens/e4_decision_tree.html',
  '/app/screens/e5_result.html',
  '/app/screens/e6_patient_record.html',
  '/app/screens/e7_settings.html',
  '/app/css/healthguard.css',
  '/app/js/nav.js',
  '/app/manifest.json'
];

// Installation du Service Worker et mise en cache des ressources
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Mise en cache des ressources statiques');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

// Activation et nettoyage des anciens caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[SW] Nettoyage ancien cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Stratégie de cache : Cache First, then Network
self.addEventListener('fetch', (event) => {
  // On ne met pas en cache les appels API (ceux commençant par /api)
  if (event.request.url.includes('/api/v1/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
