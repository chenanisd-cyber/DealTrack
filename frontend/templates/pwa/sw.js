{% autoescape off %}/*
 * DealTrack.be — service worker (application installable).
 *
 * Rôle volontairement limité :
 *  - sans connexion, une navigation affiche la page « hors ligne » au lieu
 *    de l'erreur du navigateur ;
 *  - les fichiers statiques (CSS, JS, police, icônes) sont servis depuis le
 *    cache puis rafraîchis en arrière-plan.
 * Aucune page du site n'est mise en cache : elles dépendent du membre
 * connecté (favoris, factures) et ne doivent pas rester sur l'appareil.
 */
const CACHE = "dealtrack-{{ version }}";
const OFFLINE_URL = "{{ precache.0 }}";
const PRECACHE = [{% for url in precache %}"{{ url }}"{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(request).then((cached) => {
          const fresh = fetch(request)
            .then((response) => {
              if (response.ok) cache.put(request, response.clone());
              return response;
            })
            .catch(() => cached);
          return cached || fresh;
        })
      )
    );
  }
});
{% endautoescape %}