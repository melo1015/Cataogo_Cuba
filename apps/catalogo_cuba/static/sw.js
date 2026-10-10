/**
 * Service Worker para CatalogoCuba
 * Proporciona modo offline completo para conexiones lentas/inestables
 * 
 * Estrategias:
 * - HTML paginas: Stale-while-revalidate (muestra cache, actualiza en background)
 * - API/JSON: Network-first con fallback a cache
 * - Imagenes: Cache-first (las imagenes no cambian frecuentemente)
 * - CSS/JS: Cache-first
 */

const CACHE_NAME = 'catalogocuba-v1';
const STATIC_CACHE = 'catalogocuba-static-v1';
const IMAGE_CACHE = 'catalogocuba-images-v1';
const API_CACHE = 'catalogocuba-api-v1';

// Recursos estaticos criticos para cachear inmediatamente
const PRECACHE_ASSETS = [
    '/catalogo_cuba/',
    '/catalogo_cuba/static/manifest.json',
];

// ============================================================
// INSTALACION
// ============================================================

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => cache.addAll(PRECACHE_ASSETS))
            .then(() => self.skipWaiting())
            .catch(err => console.log('[SW] Precache error:', err))
    );
});

// ============================================================
// ACTIVACION - Limpiar caches antiguas
// ============================================================

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(name => {
                        return name.startsWith('catalogocuba-') && 
                               name !== CACHE_NAME && 
                               name !== STATIC_CACHE && 
                               name !== IMAGE_CACHE && 
                               name !== API_CACHE;
                    })
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

// ============================================================
// INTERCEPTAR FETCH
// ============================================================

self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Solo manejar peticiones GET
    if (request.method !== 'GET') return;
    
    // Solo manejar peticiones del mismo origen o de la app
    if (!url.pathname.startsWith('/catalogo_cuba')) return;
    
    // 1. API endpoints (catalogo JSON) - Network-first con cache
    if (url.pathname.includes('/api/')) {
        event.respondWith(networkFirst(request, API_CACHE));
        return;
    }
    
    // 2. Imagenes subidas - Cache-first
    if (url.pathname.includes('/uploads/')) {
        event.respondWith(cacheFirst(request, IMAGE_CACHE));
        return;
    }
    
    // 3. Paginas HTML (catalogos, productos) - Stale-while-revalidate
    if (request.mode === 'navigate' || request.headers.get('Accept')?.includes('text/html')) {
        event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
        return;
    }
    
    // 4. CSS, JS, fuentes - Cache-first
    if (url.pathname.match(/\.(css|js|woff2?|json)$/)) {
        event.respondWith(cacheFirst(request, STATIC_CACHE));
        return;
    }
});

// ============================================================
// ESTRATEGIAS DE CACHE
// ============================================================

/**
 * Cache-first: Intenta cache primero, si no esta va a network
 * Ideal para imagenes y recursos estaticos
 */
async function cacheFirst(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    
    if (cached) return cached;
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        // Si no hay cache ni network, retornar respuesta offline
        return new Response('', { status: 503, statusText: 'Servicio no disponible offline' });
    }
}

/**
 * Network-first: Intenta network primero, fallback a cache
 * Ideal para APIs y datos dinamicos
 */
async function networkFirst(request, cacheName) {
    const cache = await caches.open(cacheName);
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
            return networkResponse;
        }
        throw new Error('Network response not ok');
    } catch (error) {
        const cached = await cache.match(request);
        if (cached) return cached;
        
        // Si es la API del catalogo, intentar devolver datos locales
        if (request.url.includes('/api/negocio/')) {
            return servirCatalogoOffline(request);
        }
        
        return new Response(
            JSON.stringify({ exito: false, mensaje: 'Sin conexion. Datos no disponibles offline.', offline: true }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
    }
}

/**
 * Stale-while-revalidate: Sirve del cache inmediatamente, actualiza en background
 * Ideal para paginas HTML
 */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    
    const fetchPromise = fetch(request).then(networkResponse => {
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    }).catch(() => cached);
    
    return cached || fetchPromise;
}

// ============================================================
// SERVIR CATALOGO OFFLINE
// ============================================================

/**
 * Extrae el slug del negocio de la URL y busca en localStorage via clients
 * Como el SW no tiene acceso a localStorage, enviamos un mensaje al client
 */
async function servirCatalogoOffline(request) {
    // Extraer slug del negocio de la URL
    const match = request.url.match(/\/api\/negocio\/([^\/]+)\/catalogo/);
    if (!match) {
        return new Response(
            JSON.stringify({ exito: false, mensaje: 'No hay datos offline para este catalogo', offline: true }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
    }
    
    const negocioSlug = match[1];
    
    // Retornar una respuesta que el frontend JS manejara
    // El frontend ya deberia tener los datos en localStorage
    return new Response(
        JSON.stringify({ 
            exito: true, 
            offline: true,
            negocio_slug: negocioSlug,
            mensaje: 'Modo offline - usando datos locales',
            source: 'service_worker_cache_check'
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
}

// ============================================================
// BACKGROUND SYNC
// ============================================================

self.addEventListener('sync', event => {
    if (event.tag === 'sync-catalogo') {
        event.waitUntil(sincronizarPedidosPendientes());
    }
});

// Background Sync funciona aunque no haya una pestaña abierta en navegadores compatibles.
// La misma clave client_uuid permite reintentar sin crear pedidos duplicados.
async function sincronizarPedidosPendientes() {
    const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('catalogocuba-orders-v1', 1);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
    try {
        const orders = await new Promise((resolve, reject) => {
            const req = db.transaction('orders', 'readonly').objectStore('orders').getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error);
        });
        for (const order of orders) {
            if (order.status !== 'pending') continue;
            try {
                const response = await fetch(order.endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(order.payload)
                });
                const result = await response.json();
                if (response.ok && result.exito) {
                    order.status = 'received';
                    order.server_result = result.datos || {};
                    order.last_error = '';
                } else if (response.status >= 500 || response.status === 429) {
                    // Rechazo temporal: pedir al navegador otro intento.
                    throw new Error('Error temporal del servidor');
                } else {
                    order.status = 'error';
                    order.last_error = result.mensaje || 'Pedido rechazado por el servidor';
                }
                await guardarPedidoEnCola(db, order);
            } catch (error) {
                if (error && error.message === 'Error temporal del servidor') {
                    db.close();
                    throw error;
                }
                order.status = 'pending';
                order.last_error = 'Sin conexión o respuesta del servidor';
                await guardarPedidoEnCola(db, order);
                db.close();
                throw error;
            }
        }
        db.close();
        const clients = await self.clients.matchAll({ type: 'window' });
        clients.forEach(client => client.postMessage({ type: 'SYNC_QUEUE_UPDATED' }));
    } catch (error) {
        // Rechazar event.waitUntil para que el navegador pueda reintentar.
        throw error;
    }
}

function guardarPedidoEnCola(db, order) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction('orders', 'readwrite');
        tx.objectStore('orders').put(order);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
    });
}

// ============================================================
// MENSAJES DEL CLIENT
// ============================================================

self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CACHE_CATALOG') {
        // Cachear catalogo completo enviado desde el cliente
        const { url, data } = event.data;
        caches.open(API_CACHE).then(cache => {
            cache.put(url, new Response(JSON.stringify(data), {
                headers: { 'Content-Type': 'application/json' }
            }));
        });
    }
});