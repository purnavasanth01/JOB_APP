// Service worker: network first, so every open gets the newest version from GitHub Pages.
// The cache is only a fallback when the phone is offline. It also shows the job notifications
// that the job listener sends (Web Push).
const CACHE = "jobs-app";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request, { cache: "no-store" })
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});

// A push from the job listener: { title, body, tag, url, top }
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: "New jobs", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(
    self.registration.showNotification(d.title || "New jobs", {
      body: d.body || "",
      tag: d.tag || undefined,
      icon: "icon-192.png",
      requireInteraction: !!d.top,          // 👑 top-25 jobs stay on screen until you tap them
      data: { url: d.url || "./" },
    })
  );
});

// Tapping a notification opens the app (or brings it to the front and refreshes the jobs).
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "./", self.location.href).href;
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.startsWith(self.registration.scope)) {
          c.postMessage("refresh");
          return c.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
