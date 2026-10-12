"""Contratos estáticos de la plantilla de despliegue Nginx para el VPS."""
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
NGINX_LIMITS = REPO_ROOT / "deploy" / "nginx" / "catalogo-cuba-limits.conf"
NGINX_SITE = REPO_ROOT / "deploy" / "nginx" / "catalogo-cuba-site.conf.example"
DEPLOY_DOC = REPO_ROOT / "docs" / "SEGURIDAD_VPS_NGINX.md"
SETTINGS = Path(__file__).resolve().parents[1] / "settings.py"


class NginxDeploymentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limits = NGINX_LIMITS.read_text(encoding="utf-8")
        cls.site = NGINX_SITE.read_text(encoding="utf-8")
        cls.docs = DEPLOY_DOC.read_text(encoding="utf-8")
        cls.settings = SETTINGS.read_text(encoding="utf-8")

    def test_rate_limit_zones_are_defined_and_used(self):
        self.assertIn("zone=catalogo_api:10m rate=10r/s", self.limits)
        self.assertIn("zone=catalogo_orders:10m rate=2r/s", self.limits)
        self.assertIn("zone=catalogo_auth:10m rate=5r/m", self.limits)
        self.assertIn("zone=catalogo_per_ip:10m", self.limits)
        self.assertIn("limit_req zone=catalogo_api burst=30 nodelay", self.site)
        self.assertIn("limit_req zone=catalogo_orders burst=6 nodelay", self.site)
        self.assertIn("location ^~ /catalogo_cuba/auth/", self.site)
        self.assertIn("limit_req zone=catalogo_auth burst=5 nodelay", self.site)
        self.assertIn("limit_conn catalogo_per_ip 20", self.site)
        self.assertIn("limit_req_status 429", self.site)

    def test_proxy_overwrites_forwarded_for_instead_of_appending_client_value(self):
        self.assertGreaterEqual(self.site.count("proxy_set_header X-Forwarded-For $remote_addr;"), 3)
        self.assertNotIn("proxy_add_x_forwarded_for", self.site)
        self.assertIn("remote_addr not in trusted_proxies", (
            Path(__file__).resolve().parents[1] / "controllers.py"
        ).read_text(encoding="utf-8"))

    def test_public_order_body_limit_matches_application_limit(self):
        self.assertIn("location ~ ^/catalogo_cuba/api/negocio/[^/]+/pedidos$", self.site)
        self.assertIn("client_max_body_size 64k;", self.site)
        self.assertIn("MAX_ORDER_REQUEST_SIZE = 64 * 1024", self.settings)

    def test_site_has_https_redirect_and_basic_security_headers(self):
        self.assertIn("return 301 https://$host$request_uri;", self.site)
        self.assertIn("listen 443 ssl http2;", self.site)
        for header in (
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Strict-Transport-Security",
        ):
            with self.subTest(header=header):
                self.assertIn(header, self.site)

    def test_document_warns_about_private_upstream_and_proxy_trust(self):
        self.assertIn("127.0.0.1:8000", self.docs)
        self.assertIn("CATALOGO_CUBA_TRUSTED_PROXY_IPS=127.0.0.1", self.docs)
        self.assertIn("no confiar en rangos amplios", self.docs.lower())
        self.assertIn("nginx -t", self.docs)
        self.assertIn("login, registro y recuperación de contraseña", self.docs.lower())
        self.assertIn("no versionar secretos", self.docs.lower())


if __name__ == "__main__":
    unittest.main()
