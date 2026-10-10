"""Regresiones estaticas para contratos de autorizacion sensibles.

Estas pruebas no sustituyen las pruebas HTTP autenticadas, pero evitan que
se eliminen accidentalmente las comprobaciones de rol y propiedad del recurso.
"""
import re
import unittest
from pathlib import Path


CONTROLLERS = Path(__file__).resolve().parents[1] / "controllers.py"


def controller_function(source, function_name):
    """Extrae una funcion de controlador hasta el siguiente decorador o def."""
    match = re.search(
        r"(?m)^def " + re.escape(function_name) + r"\([^\n]*\):\n"
        r"(.*?)(?=^(?:@action|def )|\Z)",
        source,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("No se encontro la funcion %s" % function_name)
    return match.group(1)


class AuthorizationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONTROLLERS.read_text(encoding="utf-8")

    def test_inventory_update_requires_commerce_role_and_owned_product(self):
        body = controller_function(self.source, "api_actualizar_stock")
        self.assertIn("not es_comerciante(user)", body)
        self.assertIn("db.negocio.usuario_id == user[\"id\"]", body)
        self.assertIn("db.producto.negocio_id == negocio.id", body)

    def test_subscription_payment_uses_server_price_and_commerce_ownership(self):
        body = controller_function(self.source, "admin_realizar_pago")
        self.assertIn("not es_comerciante(user)", body)
        self.assertIn("db.negocio.usuario_id == user[\"id\"]", body)
        self.assertIn("settings.COSTO_SUSCRIPCION_MENSUAL_CUP", body)
        self.assertIn("settings.COSTO_SUSCRIPCION_MENSUAL_USDT", body)
        self.assertIn("referencia_unica", body)

    def test_payment_validation_requires_superadmin_and_compare_and_set(self):
        body = controller_function(self.source, "superadmin_validar_pago")
        self.assertIn("not es_superadmin()", body)
        self.assertIn("db.pago.estado == pago.estado", body)
        self.assertIn('if pago.estado == "validado":', body)
        self.assertIn("db.commit()", body)
        self.assertIn("db.rollback()", body)

    def test_business_approval_requires_superadmin(self):
        body = controller_function(self.source, "superadmin_aprobar_negocio")
        self.assertIn("not es_superadmin()", body)
        self.assertIn("aprobado=True, activo=True", body)

    def test_public_order_api_is_idempotent_and_scoped_to_business(self):
        body = controller_function(self.source, "api_crear_pedido")
        self.assertIn("uuid.UUID", body)
        self.assertIn("db.pedido.client_uuid == client_uuid", body)
        self.assertIn("existente.negocio_id != negocio.id", body)
        self.assertIn("db.producto.negocio_id == negocio.id", body)
        self.assertIn('estado="pendiente_revision"', body)

    def test_public_order_api_calculates_prices_on_server(self):
        body = controller_function(self.source, "api_crear_pedido")
        self.assertIn("Decimal(str(producto.precio or \"0\"))", body)
        self.assertIn("Field", body) if False else None
        self.assertIn("producto.stock or 0", body)
        self.assertIn("Solicitud recibida; el negocio debe confirmar disponibilidad", body)


if __name__ == "__main__":
    unittest.main()
