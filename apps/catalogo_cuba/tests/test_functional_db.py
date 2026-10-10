"""Pruebas de persistencia de los flujos de datos principales.

Estas pruebas ejercitan inserts/lecturas reales sobre la base SQLite aislada
del job CI. No simulan peticiones HTTP ni sustituyen las pruebas de controladores.
"""
import unittest
from datetime import date, datetime, timedelta
from uuid import uuid4

from catalogo_cuba.common import db


class DatabaseFlowTests(unittest.TestCase):
    def test_business_product_subscription_and_payment_round_trip(self):
        suffix = uuid4().hex[:12]
        user_id = business_id = category_id = product_id = subscription_id = payment_id = None
        try:
            user_id = db.auth_user.insert(
                email="ci-%s@example.invalid" % suffix,
                password="not-a-real-password-hash",
                first_name="CI",
                last_name="Test",
            )
            db.commit()

            now = datetime.utcnow()
            business_id = db.negocio.insert(
                nombre="Negocio CI %s" % suffix,
                slug="negocio-ci-%s" % suffix,
                usuario_id=user_id,
                activo=True,
                aprobado=False,
                fecha_creacion=now,
                fecha_actualizacion=now,
            )
            category_id = db.categoria.insert(
                nombre="General",
                slug="general-%s" % suffix,
                negocio_id=business_id,
            )
            product_id = db.producto.insert(
                nombre="Producto de prueba",
                slug="producto-%s" % suffix,
                negocio_id=business_id,
                categoria_id=category_id,
                precio="12.50",
                moneda="CUP",
                stock=7,
                disponible=True,
            )
            subscription_id = db.suscripcion.insert(
                negocio_id=business_id,
                usuario_id=user_id,
                fecha_inicio=date.today(),
                fecha_fin=date.today() + timedelta(days=30),
                estado="pendiente",
            )
            payment_id = db.pago.insert(
                suscripcion_id=subscription_id,
                negocio_id=business_id,
                usuario_id=user_id,
                monto="1500.00",
                moneda="CUP",
                metodo_pago="transfermovil",
                estado="pendiente",
                referencia="CI-%s" % suffix,
                fecha_solicitud=now,
            )
            db.commit()

            business = db.negocio[business_id]
            product = db.producto[product_id]
            payment = db.pago[payment_id]
            self.assertEqual(business.usuario_id, user_id)
            self.assertFalse(business.aprobado)
            self.assertEqual(product.negocio_id, business_id)
            self.assertEqual(product.stock, 7)
            self.assertEqual(str(payment.monto), "1500.00")
            self.assertEqual(payment.suscripcion_id, subscription_id)
        finally:
            if payment_id:
                db(db.pago.id == payment_id).delete()
            if subscription_id:
                db(db.suscripcion.id == subscription_id).delete()
            if product_id:
                db(db.producto.id == product_id).delete()
            if category_id:
                db(db.categoria.id == category_id).delete()
            if business_id:
                db(db.negocio.id == business_id).delete()
            if user_id:
                db(db.auth_user.id == user_id).delete()
            db.commit()


if __name__ == "__main__":
    unittest.main()
