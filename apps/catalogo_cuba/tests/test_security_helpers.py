"""Pruebas unitarias ejecutables de los helpers de seguridad HTTP.

Se compilan las funciones reales desde controllers.py con dependencias pequeñas
inyectadas. Así se comprueba su comportamiento sin arrancar el servidor py4web.
"""
import ast
import io
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit


CONTROLLERS = Path(__file__).resolve().parents[1] / "controllers.py"
MAX_IMAGE_SIZE = 2 * 1024 * 1024


class HTTPError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def load_security_helpers():
    source = CONTROLLERS.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CONTROLLERS))
    names = {"_peticion_mismo_origen", "_rechazar_uploads_excesivos"}
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    found = {node.name for node in functions}
    if found != names:
        raise AssertionError("No se encontraron todos los helpers de seguridad: %r" % (names - found,))

    namespace = {
        "request": SimpleNamespace(environ={}, files={}),
        "settings": SimpleNamespace(MAX_IMAGE_SIZE=MAX_IMAGE_SIZE),
        "urlsplit": urlsplit,
        "os": os,
        "HTTP": HTTPError,
    }
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(CONTROLLERS), "exec"), namespace)
    return namespace


class SecurityHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_security_helpers()
        cls.request = cls.helpers["request"]

    def setUp(self):
        self.request.environ = {}
        self.request.files = {}

    def test_origin_accepts_matching_origin_host_and_port(self):
        self.request.environ = {
            "HTTP_HOST": "catalogo.example:8443",
            "HTTP_ORIGIN": "https://catalogo.example:8443",
        }
        self.assertTrue(self.helpers["_peticion_mismo_origen"]())

    def test_origin_rejects_external_host_even_if_scheme_matches(self):
        self.request.environ = {
            "HTTP_HOST": "catalogo.example",
            "HTTP_ORIGIN": "https://attacker.example",
        }
        self.assertFalse(self.helpers["_peticion_mismo_origen"]())

    def test_origin_rejects_missing_host_or_origin_and_malformed_url(self):
        self.request.environ = {"HTTP_ORIGIN": "https://catalogo.example"}
        self.assertFalse(self.helpers["_peticion_mismo_origen"]())
        self.request.environ = {"HTTP_HOST": "catalogo.example"}
        self.assertFalse(self.helpers["_peticion_mismo_origen"]())
        self.request.environ = {
            "HTTP_HOST": "catalogo.example",
            "HTTP_ORIGIN": "not a valid origin",
        }
        self.assertFalse(self.helpers["_peticion_mismo_origen"]())

    def test_origin_falls_back_to_referer_when_origin_is_absent(self):
        self.request.environ = {
            "HTTP_HOST": "catalogo.example",
            "HTTP_REFERER": "https://catalogo.example/admin",
        }
        self.assertTrue(self.helpers["_peticion_mismo_origen"]())

    def test_upload_within_limit_is_accepted_and_stream_position_restored(self):
        stream = io.BytesIO(b"x" * 128)
        stream.seek(7)
        self.request.files = {"imagen": SimpleNamespace(file=stream)}
        self.helpers["_rechazar_uploads_excesivos"](["imagen"])
        self.assertEqual(stream.tell(), 7)

    def test_upload_over_limit_returns_http_413_and_restores_stream_position(self):
        stream = io.BytesIO(b"x" * (MAX_IMAGE_SIZE + 1))
        stream.seek(11)
        self.request.files = {"imagen": SimpleNamespace(file=stream)}
        with self.assertRaises(HTTPError) as caught:
            self.helpers["_rechazar_uploads_excesivos"](["imagen"])
        self.assertEqual(caught.exception.status, 413)
        self.assertEqual(stream.tell(), 11)

    def test_missing_upload_is_ignored(self):
        self.helpers["_rechazar_uploads_excesivos"](["imagen"])
        self.assertEqual(self.request.files, {})


if __name__ == "__main__":
    unittest.main()
