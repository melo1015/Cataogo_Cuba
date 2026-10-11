"""Contratos de regresión para el funcionamiento offline/PWA.

Estas pruebas estructurales no sustituyen una prueba real en navegador sin red,
pero detectan regresiones en el alcance del Service Worker y la cola de pedidos.
"""
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


class OfflinePwaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controllers = (APP / "controllers.py").read_text(encoding="utf-8")
        cls.layout = (APP / "templates" / "layout.html").read_text(encoding="utf-8")
        cls.catalog = (APP / "templates" / "catalogo_negocio.html").read_text(encoding="utf-8")
        cls.sw = (APP / "static" / "sw.js").read_text(encoding="utf-8")
        cls.offline_page = APP / "static" / "offline.html"

    def test_service_worker_is_served_from_app_root_with_wide_scope_header(self):
        self.assertIn('@action("catalogo_cuba/sw.js", method=["GET"])', self.controllers)
        self.assertIn('response.headers["Service-Worker-Allowed"] = "/catalogo_cuba/"', self.controllers)
        self.assertIn("URL('catalogo_cuba', 'sw.js')", self.layout)
        self.assertIn("{ scope: '/catalogo_cuba/' }", self.layout)
        self.assertNotIn("URL('static', 'sw.js')", self.layout)

    def test_uncached_offline_navigation_has_fallback_page(self):
        self.assertTrue(self.offline_page.is_file(), "Falta la página de fallback offline")
        self.assertIn("'/catalogo_cuba/static/offline.html'", self.sw)
        self.assertIn("cache.match('/catalogo_cuba/static/offline.html')", self.sw)
        self.assertRegex(self.sw, r"catch\(async \(\) => \{[\s\S]*?offline\.html")

    def test_offline_orders_retry_only_while_pending(self):
        self.assertIn("indexedDB.open('catalogocuba-orders-v1', 1)", self.sw)
        manifest = (APP / "static" / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"start_url": "/catalogo_cuba/catalogo_cuba"', manifest)
        self.assertIn("event.tag === 'sync-catalogo'", self.sw)
        self.assertRegex(
            self.catalog,
            r"allQueued\(\)\)\.filter\(o => o\.slug === slug && o\.status === 'pending'\)",
        )
        self.assertIn("client_uuid: uuid()", self.catalog)
        self.assertIn("db(db.pedido.client_uuid == client_uuid)", self.controllers)

    def test_private_pages_and_authenticated_apis_are_never_cached(self):
        self.assertIn("/(admin|superadmin|auth)", self.sw)
        self.assertIn("/api/(notificaciones|notificacion|inventario)", self.sw)
        self.assertIn("if (!url.pathname.includes('/api/negocio/')) return;", self.sw)

    def test_catalogue_keeps_local_copy_without_overwriting_with_error_payload(self):
        self.assertIn("localStorage.setItem('catalogo_' + slug, JSON.stringify(data))", self.catalog)
        self.assertIn("Una respuesta offline incompleta no debe reemplazar", self.catalog)
        self.assertIn("async function cacheFirst", self.sw)
        self.assertIn("async function networkFirst", self.sw)


if __name__ == "__main__":
    unittest.main()
