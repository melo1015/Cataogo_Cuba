"""Regresión para el uso correcto de Form en el CRUD multiempresa.

Estas comprobaciones AST no reemplazan pruebas HTTP autenticadas, pero evitan
reintroducir el parámetro inexistente `fields=` y las escrituras automáticas
que podrían asignar campos internos desde el POST.
"""
import ast
import unittest
from pathlib import Path


CONTROLLERS = Path(__file__).resolve().parents[1] / "controllers.py"
TARGETS = {
    "admin_producto_nuevo": ("producto", "insert"),
    "admin_producto_editar": ("producto", "update"),
    "admin_categoria_nueva": ("categoria", "insert"),
    "admin_categoria_editar": ("categoria", "update"),
}


class CrudFormRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONTROLLERS.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(CONTROLLERS))
        cls.functions = {
            node.name: node for node in cls.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_crud_forms_use_explicit_field_objects_and_disable_dbio(self):
        for name in TARGETS:
            with self.subTest(controller=name):
                node = self.functions[name]
                forms = [
                    n for n in ast.walk(node)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "Form"
                ]
                self.assertEqual(len(forms), 1)
                form = forms[0]
                self.assertFalse(any(k.arg == "fields" for k in form.keywords))
                self.assertTrue(
                    any(k.arg == "dbio" and isinstance(k.value, ast.Constant)
                        and k.value.value is False for k in form.keywords),
                    "El formulario debe evitar la escritura automática a la BD",
                )
                self.assertTrue(
                    any(k.arg == "form_name" for k in form.keywords),
                    "Una lista de Field necesita form_name explícito",
                )
                self.assertIsInstance(form.args[0], ast.ListComp)

    def test_create_routes_assign_tenant_and_slug_on_server(self):
        for name, (table, operation) in TARGETS.items():
            if operation != "insert":
                continue
            with self.subTest(controller=name):
                source = ast.get_source_segment(self.source, self.functions[name])
                self.assertIn("db.%s.insert(**valores)" % table, source)
                self.assertIn('"negocio_id": negocio.id', source)
                self.assertIn('"slug": slug', source)
                self.assertNotIn("form.vars.get(\"id\")", source)

    def test_edit_routes_scope_update_to_owned_record(self):
        for name, (table, operation) in TARGETS.items():
            if operation != "update":
                continue
            with self.subTest(controller=name):
                node = self.functions[name]
                source = ast.get_source_segment(self.source, node)
                self.assertIn("db.%s.id == %s_id" % (
                    table, "producto" if table == "producto" else "categoria"
                ), source)
                self.assertIn("db.%s.negocio_id == negocio.id" % table, source)
                self.assertIn(").update(**valores)", source)


if __name__ == "__main__":
    unittest.main()
