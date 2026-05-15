// Service Worker — Web Push notifications
self.addEventListener('push', e => {
  let p = {}
  try { p = JSON.parse(e.data?.text() || '{}') } catch {}
  e.waitUntil(self.registration.showNotification(p.title || '📊 Market Alert', {
    body:     p.body || 'Market state changed',
    tag:      `market-${p.tf}`,
    renotify: true,
    data:     { url: self.location.origin },
  }))
})
self.addEventListener('notificationclick', e => {
  e.notification.close()
  e.waitUntil(clients.openWindow(e.notification.data?.url || '/'))
})
self.addEventListener('install',  () => self.skipWaiting())
self.addEventListener('activate', e => e.waitUntil(clients.claim()))
