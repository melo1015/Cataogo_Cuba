"""Regresiones para convenciones de fixtures de py4web.

Estas comprobaciones complementan el smoke test HTTP: protegen el orden de
Template, el uso de fixtures reales y las dependencias del contexto común.
"""
import re
import unittest
from pathlib import Path


CONTROLLERS = Path(__file__).resolve().parents[1] / "controllers.py"


class Py4webFixtureConventionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONTROLLERS.read_text(encoding="utf-8")

    def test_templates_are_first_in_action_uses(self):
        self.assertNotRegex(
            self.source,
            r'@action\\.uses\\(\\*AccionBase,\\s*["\'][^"\']+\\.html["\']\\)',
            "En py4web la plantilla debe ser el primer fixture.",
        )
        self.assertGreater(
            len(re.findall(r'@action\\.uses\\(["\'][^"\']+\\.html["\'],\\s*\\*AccionBase\\)', self.source)),
            0,
            "No se encontraron vistas que declaren primero la plantilla.",
        )

    def test_plain_helper_is_not_registered_as_fixture(self):
        self.assertNotRegex(
            self.source,
            r"@action\\.uses\\(contexto_base\\)",
        )
        self.assertNotRegex(
            self.source,
            r"@action\\.uses\\(session,\\s*auth\\.user,\\s*contexto_base\\)",
        )

    def test_common_context_fixture_declares_prerequisites(self):
        self.assertIn("self.__prerequisites__ = [session, db]", self.source)
        self.assertIn("AccionBase = (db, ContextoBaseFixture())", self.source)


if __name__ == "__main__":
    unittest.main()
