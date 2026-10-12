"""Pruebas de humo del esquema principal de CatalogoCuba.

Estas pruebas importan la aplicación py4web en el entorno CI y verifican
que las tablas y campos críticos se definan sin arrancar un servidor HTTP.
"""
import unittest

import catalogo_cuba  # noqa: F401 - registra modelos y controladores
from catalogo_cuba.common import db


class SchemaSmokeTests(unittest.TestCase):
    def test_core_tables_are_defined(self):
        expected = {
            "auth_user",
            "negocio",
            "categoria",
            "producto",
            "suscripcion",
            "pago",
            "notificacion",
        }
        self.assertTrue(expected.issubset(set(db.tables)))

    def test_user_custom_fields_exist(self):
        self.assertIn("fecha_registro", db.auth_user.fields)
        self.assertIn("telefono", db.auth_user.fields)

    def test_product_has_inventory_and_price_fields(self):
        fields = set(db.producto.fields)
        self.assertTrue({"negocio_id", "precio", "moneda", "stock", "disponible"}.issubset(fields))

    def test_order_schema_has_idempotency_key_and_snapshot_fields(self):
        self.assertIn("pedido", db.tables)
        self.assertIn("pedido_item", db.tables)
        order_fields = set(db.pedido.fields)
        self.assertTrue({
            "client_uuid", "negocio_id", "estado", "total", "fecha_creacion"
        }.issubset(order_fields))
        item_fields = set(db.pedido_item.fields)
        self.assertTrue({
            "pedido_id", "producto_id", "cantidad", "precio_unitario", "subtotal"
        }.issubset(item_fields))
        self.assertTrue(db.pedido.client_uuid.unique)
        self.assertTrue(db.pedido.client_uuid.notnull)

    def test_payment_has_open_subscription_uniqueness_guard(self):
        self.assertIn("suscripcion_abierta_id", db.pago.fields)
        self.assertTrue(db.pago.suscripcion_abierta_id.unique)
        self.assertFalse(db.pago.suscripcion_abierta_id.notnull)

    def test_payment_has_review_state_and_audit_fields(self):
        fields = set(db.pago.fields)
        self.assertTrue(
            {"suscripcion_id", "negocio_id", "usuario_id", "monto", "moneda",
             "metodo_pago", "estado", "referencia", "fecha_validacion",
             "validado_por"}.issubset(fields)
        )


if __name__ == "__main__":
    unittest.main()
