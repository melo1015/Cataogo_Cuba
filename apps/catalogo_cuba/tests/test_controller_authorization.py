"""Pruebas unitarias de las decisiones de rol usadas por los controladores.

Se extraen las funciones reales de controllers.py y se ejecutan con dependencias
aisladas. No sustituyen pruebas HTTP autenticadas contra py4web.
"""
import ast
import unittest
from pathlib import Path


CONTROLLERS = Path(__file__).resolve().parents[1] / "controllers.py"


class FakeRoles:
    def __init__(self, roles_by_user=None):
        self.roles_by_user = roles_by_user or {}

    def get(self, user_id):
        return list(self.roles_by_user.get(user_id, []))


class FakeAuth:
    def __init__(self, user=None):
        self.user = user

    def get_user(self):
        return self.user


def load_role_helpers(roles_by_user=None, current_user=None):
    source = CONTROLLERS.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CONTROLLERS))
    names = {"_tiene_rol", "_calcular_rol", "es_superadmin", "es_comerciante"}
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    found = {node.name for node in functions}
    if found != names:
        raise AssertionError("Faltan helpers de autorización: %r" % (names - found,))

    namespace = {
        "roles_tags": FakeRoles(roles_by_user),
        "auth": FakeAuth(current_user),
    }
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(CONTROLLERS), "exec"), namespace)
    return namespace


class ControllerRoleTests(unittest.TestCase):
    def test_anonymous_user_has_no_privileged_role(self):
        helpers = load_role_helpers(current_user=None)
        self.assertFalse(helpers["es_superadmin"]())
        self.assertFalse(helpers["es_comerciante"]())
        self.assertIsNone(helpers["_calcular_rol"](None))

    def test_merchant_is_not_superadmin(self):
        helpers = load_role_helpers(
            roles_by_user={10: ["comerciante"]},
            current_user={"id": 10},
        )
        self.assertFalse(helpers["es_superadmin"]())
        self.assertTrue(helpers["es_comerciante"]())
        self.assertEqual(helpers["_calcular_rol"]({"id": 10}), "comerciante")

    def test_superadmin_has_merchant_capability(self):
        helpers = load_role_helpers(
            roles_by_user={11: ["superadmin"]},
            current_user={"id": 11},
        )
        self.assertTrue(helpers["es_superadmin"]())
        self.assertTrue(helpers["es_comerciante"]())
        self.assertEqual(helpers["_calcular_rol"]({"id": 11}), "superadmin")

    def test_unknown_user_or_role_is_denied(self):
        helpers = load_role_helpers(roles_by_user={12: ["visitante"]})
        self.assertFalse(helpers["_tiene_rol"](None, "superadmin"))
        self.assertFalse(helpers["_tiene_rol"](12, "superadmin"))
        self.assertFalse(helpers["_tiene_rol"](999, "comerciante"))

    def test_superadmin_role_takes_precedence_when_user_has_multiple_roles(self):
        helpers = load_role_helpers(roles_by_user={13: ["visitante", "comerciante", "superadmin"]})
        self.assertEqual(helpers["_calcular_rol"]({"id": 13}), "superadmin")


if __name__ == "__main__":
    unittest.main()
