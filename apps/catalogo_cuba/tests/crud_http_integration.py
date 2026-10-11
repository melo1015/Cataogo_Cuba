"""HTTP integration test for authenticated, multi-tenant CRUD routes.

Run from the repository root with PYTHONPATH=apps and a dedicated SQLite URI.
The test seeds two merchants, logs in through py4web's real HTTP API, and
checks create/edit access plus cross-tenant isolation over HTTP.
"""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from html.parser import HTMLParser

os.environ.setdefault("CATALOGO_CUBA_DEBUG", "1")
os.environ.setdefault("CATALOGO_CUBA_SECRET", "ci-only-crud-http-secret")
os.environ.setdefault("CATALOGO_CUBA_DB_URI", "sqlite://catalogo_cuba_crud_http.db")
sys.path.insert(0, os.path.abspath("apps"))

from catalogo_cuba import models  # noqa: E402,F401
from catalogo_cuba.common import auth, db, asignar_rol  # noqa: E402

BASE = "http://127.0.0.1:8766"
APP_PREFIX = "/catalogo_cuba"
CRUD_PREFIX = APP_PREFIX + "/catalogo_cuba/admin"


class HiddenInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "input":
            return
        item = dict(attrs)
        if item.get("type", "").lower() == "hidden" and item.get("name"):
            self.values[item["name"]] = item.get("value", "")


def request(opener, path, data=None, headers=None, method=None):
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers=headers or {},
        method=method or ("POST" if data is not None else "GET"),
    )
    try:
        response = opener.open(req, timeout=8)
        return response.getcode(), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def seed():
    # The integration database is dedicated to this test; reset only its test data.
    auth.param.registration_requires_confirmation = False
    auth.param.registration_requires_approval = False
    auth.param.login_after_registration = False
    email_a = "crud-merchant-a@example.test"
    email_b = "crud-merchant-b@example.test"
    for email in (email_a, email_b):
        old = db(db.auth_user.email == email).select().first()
        if old:
            db(db.auth_user.id == old.id).delete()
    db.commit()

    def create_user(email, first_name):
        result = auth.register(
            {
                "email": email,
                "username": email.split("@")[0],
                "password": "TestPassword123!",
                "first_name": first_name,
                "last_name": "Integration",
            },
            send=False,
            validate=True,
        )
        if result.get("errors") or not result.get("id"):
            raise AssertionError("Could not seed test user %s: %r" % (email, result))
        user_id = result["id"]
        asignar_rol(user_id, "comerciante")
        return user_id

    user_a = create_user(email_a, "MerchantA")
    user_b = create_user(email_b, "MerchantB")
    business_a = db.negocio.insert(
        nombre="Negocio HTTP A", slug="negocio-http-a", usuario_id=user_a,
        activo=True, aprobado=True, moneda_principal="CUP",
    )
    business_b = db.negocio.insert(
        nombre="Negocio HTTP B", slug="negocio-http-b", usuario_id=user_b,
        activo=True, aprobado=True, moneda_principal="CUP",
    )
    category_a = db.categoria.insert(
        nombre="Categoria A", slug="categoria-a", negocio_id=business_a, activa=True,
    )
    category_b = db.categoria.insert(
        nombre="Categoria B", slug="categoria-b", negocio_id=business_b, activa=True,
    )
    product_a = db.producto.insert(
        nombre="Producto A", slug="producto-a", negocio_id=business_a,
        categoria_id=category_a, precio=10, moneda="CUP", disponible=True, stock=3,
    )
    product_b = db.producto.insert(
        nombre="Producto B", slug="producto-b", negocio_id=business_b,
        categoria_id=category_b, precio=20, moneda="CUP", disponible=True, stock=4,
    )
    db.commit()
    return {
        "a": (email_a, user_a, business_a, category_a, product_a),
        "b": (email_b, user_b, business_b, category_b, product_b),
    }


def login(email):
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    payload = urllib.parse.urlencode(
        {"email": email, "password": "TestPassword123!"}
    ).encode()
    status, body = request(
        opener,
        APP_PREFIX + "/auth/api/login",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if status not in (200, 201) or not list(jar):
        raise AssertionError("HTTP login failed for %s: status=%s body=%s" % (email, status, body[-1000:]))
    return opener


def form_payload(opener, path, values):
    status, body = request(opener, path)
    if status != 200:
        raise AssertionError("Expected CRUD form HTTP 200 at %s, got %s" % (path, status))
    parser = HiddenInputs()
    parser.feed(body)
    payload = dict(parser.values)
    payload.update(values)
    return payload


def post_form(opener, path, payload):
    data = urllib.parse.urlencode(payload, doseq=True).encode()
    return request(
        opener,
        path,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE,
            "Referer": BASE + path,
        },
    )


def main():
    seeded = seed()
    server_env = os.environ.copy()
    server = subprocess.Popen(
        [
            "py4web", "run", "--yes", "--host", "127.0.0.1", "--port", "8766",
            "--app_names", "catalogo_cuba", "--server", "wsgiref",
            "--quiet", "--watch", "off", "apps",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=server_env,
    )
    try:
        last_error = None
        for _ in range(50):
            if server.poll() is not None:
                output = server.stdout.read().decode("utf-8", errors="replace")
                raise RuntimeError("py4web exited before readiness: " + output[-8000:])
            try:
                status, _ = request(urllib.request.build_opener(), APP_PREFIX + "/auth/login")
                if status == 200:
                    break
                last_error = "login page HTTP %s" % status
            except Exception as exc:
                last_error = repr(exc)
            time.sleep(0.4)
        else:
            raise RuntimeError("py4web did not become ready: %r" % last_error)

        email_a, _, _, category_a, product_a = seeded["a"]
        email_b, _, _, category_b, product_b = seeded["b"]
        client_a = login(email_a)
        client_b = login(email_b)

        # Own create/edit pages must be accessible to an authenticated merchant.
        for path in (
            CRUD_PREFIX + "/producto/nuevo",
            CRUD_PREFIX + "/categoria/nueva",
            CRUD_PREFIX + "/producto/editar/%s" % product_a,
            CRUD_PREFIX + "/categoria/editar/%s" % category_a,
        ):
            status, body = request(client_a, path)
            if status != 200:
                raise AssertionError("Merchant A cannot access own CRUD form %s: HTTP %s %s" % (path, status, body[-500:]))

        # Foreign resources must be hidden even if their numeric IDs are known.
        for path in (
            CRUD_PREFIX + "/producto/editar/%s" % product_b,
            CRUD_PREFIX + "/categoria/editar/%s" % category_b,
        ):
            status, _ = request(client_a, path)
            if status != 404:
                raise AssertionError("Cross-tenant edit should return 404 for %s, got %s" % (path, status))

        # Create a category through the actual POST handler.
        category_path = CRUD_PREFIX + "/categoria/nueva"
        category_payload = form_payload(client_a, category_path, {
            "nombre": "Categoria creada por HTTP",
            "descripcion": "Integracion",
            "orden": "0",
            "activa": "on",
        })
        status, body = post_form(client_a, category_path, category_payload)
        if status not in (200, 302, 303):
            if status >= 500:
                server.terminate()
                output, _ = server.communicate(timeout=10)
                raise RuntimeError(
                    "Category create POST failed: HTTP %s %s. Server output: %s"
                    % (status, body[-1000:], output[-12000:])
                )
            raise AssertionError("Category create POST failed: HTTP %s %s" % (status, body[-1000:]))
        created_category = db(
            (db.categoria.negocio_id == seeded["a"][2]) &
            (db.categoria.nombre == "Categoria creada por HTTP")
        ).select().first()
        if not created_category:
            raise AssertionError("Category POST returned without creating an owned category")

        # A foreign category must be rejected by the product form validator.
        product_path = CRUD_PREFIX + "/producto/nuevo"
        before_count = db(db.producto.negocio_id == seeded["a"][2]).count()
        product_payload = form_payload(client_a, product_path, {
            "nombre": "Producto con categoria ajena",
            "descripcion": "Debe rechazarse",
            "descripcion_corta": "Test HTTP",
            "precio": "11.00",
            "precio_anterior": "",
            "moneda": "CUP",
            "disponible": "on",
            "en_oferta": "",
            "stock": "1",
            "sku": "HTTP-FOREIGN-CATEGORY",
            "categoria_id": str(category_b),
            "destacado": "",
            "tags": "",
            "peso": "",
            "meta_keywords": "",
        })
        status, body = post_form(client_a, product_path, product_payload)
        after_count = db(db.producto.negocio_id == seeded["a"][2]).count()
        if status >= 500 or after_count != before_count:
            raise AssertionError(
                "Foreign category must be rejected without creating product: HTTP %s, count %s->%s, body=%s"
                % (status, before_count, after_count, body[-1000:])
            )

        # A valid create/edit round trip must preserve server-side tenant ownership.
        product_payload["nombre"] = "Producto creado por HTTP"
        product_payload["categoria_id"] = str(created_category.id)
        product_payload["sku"] = "HTTP-OWN-CATEGORY"
        status, body = post_form(client_a, product_path, product_payload)
        if status not in (200, 302, 303):
            raise AssertionError("Product create POST failed: HTTP %s %s" % (status, body[-1000:]))
        created_product = db(
            (db.producto.negocio_id == seeded["a"][2]) &
            (db.producto.nombre == "Producto creado por HTTP")
        ).select().first()
        if not created_product:
            raise AssertionError("Product POST returned without creating an owned product")

        edit_path = CRUD_PREFIX + "/producto/editar/%s" % created_product.id
        edit_payload = form_payload(client_a, edit_path, {
            "nombre": "Producto editado por HTTP",
            "descripcion": "Actualizado por prueba",
            "descripcion_corta": "Editado",
            "precio": "12.50",
            "precio_anterior": "",
            "moneda": "CUP",
            "disponible": "on",
            "en_oferta": "",
            "stock": "2",
            "sku": "HTTP-EDITED",
            "categoria_id": str(created_category.id),
            "destacado": "",
            "tags": "",
            "peso": "",
            "meta_keywords": "",
        })
        status, body = post_form(client_a, edit_path, edit_payload)
        if status not in (200, 302, 303):
            raise AssertionError("Product edit POST failed: HTTP %s %s" % (status, body[-1000:]))
        updated = db(db.producto.id == created_product.id).select().first()
        if not updated or updated.nombre != "Producto editado por HTTP" or updated.negocio_id != seeded["a"][2]:
            raise AssertionError("Product edit did not persist correctly within the owning business")

        # Merchant B's original product must remain untouched.
        untouched = db(db.producto.id == product_b).select().first()
        if not untouched or untouched.nombre != "Producto B" or untouched.negocio_id != seeded["b"][2]:
            raise AssertionError("Merchant A changed Merchant B's product")
        print("Authenticated CRUD HTTP integration passed: login, category/product create, product edit, foreign category rejection, and cross-tenant 404 isolation.")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        db.commit()


if __name__ == "__main__":
    main()
