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
        user_id = business_id = category_id = product_id = subscription_id = payment_id = order_id = order_item_id = None
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
                referencia_unica="transfermovil:ci-%s" % suffix.casefold(),
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

            # Pedido público: snapshot del precio y clave idempotente persistente.
            order_uuid = str(uuid4())
            order_id = db.pedido.insert(
                client_uuid=order_uuid,
                negocio_id=business_id,
                cliente_nombre="Cliente CI",
                cliente_telefono="+5350000000",
                estado="pendiente_revision",
                moneda="CUP",
                total="25.00",
                fecha_creacion=now,
            )
            order_item_id = db.pedido_item.insert(
                pedido_id=order_id,
                producto_id=product_id,
                nombre_producto="Producto de prueba",
                cantidad=2,
                precio_unitario="12.50",
                subtotal="25.00",
            )
            db.commit()
            self.assertEqual(db.pedido[order_id].client_uuid, order_uuid)
            self.assertEqual(db.pedido[order_id].negocio_id, business_id)
            self.assertEqual(str(db.pedido[order_id].total), "25.00")
            self.assertEqual(db.pedido_item[order_item_id].cantidad, 2)

            duplicate_order_rejected = False
            try:
                db.pedido.insert(
                    client_uuid=order_uuid,
                    negocio_id=business_id,
                    cliente_nombre="Cliente duplicado",
                    cliente_telefono="+5350000000",
                    estado="pendiente_revision",
                    moneda="CUP",
                    total="25.00",
                    fecha_creacion=now,
                )
                db.commit()
            except Exception:
                duplicate_order_rejected = True
                db.rollback()
            self.assertTrue(duplicate_order_rejected, "La base de datos acepto un pedido duplicado")
            self.assertEqual(db(db.pedido.client_uuid == order_uuid).count(), 1)

            # La aceptacion solo descuenta si la cantidad sigue disponible.
            stock_antes = db.producto[product_id].stock
            sin_stock_suficiente = db(
                (db.producto.id == product_id) &
                (db.producto.stock >= 8)
            ).update(stock=db.producto.stock - 8)
            self.assertEqual(sin_stock_suficiente, 0)
            self.assertEqual(db.producto[product_id].stock, stock_antes)

            reserva_stock = db(
                (db.producto.id == product_id) &
                (db.producto.negocio_id == business_id) &
                (db.producto.disponible == True) &
                (db.producto.stock >= 2)
            ).update(stock=db.producto.stock - 2)
            self.assertEqual(reserva_stock, 1)
            self.assertEqual(db.producto[product_id].stock, stock_antes - 2)

            primer_estado = db(
                (db.pedido.id == order_id) &
                (db.pedido.estado == "pendiente_revision")
            ).update(estado="aceptado")
            segundo_estado = db(
                (db.pedido.id == order_id) &
                (db.pedido.estado == "pendiente_revision")
            ).update(estado="rechazado")
            self.assertEqual(primer_estado, 1)
            self.assertEqual(segundo_estado, 0)
            db.commit()

            # La unicidad en base de datos bloquea referencias duplicadas aun
            # si una solicitud concurrente supera la consulta previa del controlador.
            duplicate_rejected = False
            try:
                db.pago.insert(
                    suscripcion_id=subscription_id,
                    negocio_id=business_id,
                    usuario_id=user_id,
                    monto="1500.00",
                    moneda="CUP",
                    metodo_pago="transfermovil",
                    estado="pendiente",
                    referencia="ci-%s" % suffix,
                    referencia_unica="transfermovil:ci-%s" % suffix.casefold(),
                    fecha_solicitud=now,
                )
                db.commit()
            except Exception:
                duplicate_rejected = True
                db.rollback()
            self.assertTrue(duplicate_rejected, "La base de datos acepto una referencia duplicada")
            self.assertEqual(
                db(db.pago.referencia_unica == "transfermovil:ci-%s" % suffix.casefold()).count(),
                1,
            )

            # Simular el compare-and-set usado por el controlador. Solo la
            # solicitud que cambia pendiente -> validado puede aplicar el periodo.
            fecha_fin_inicial = db.suscripcion[subscription_id].fecha_fin
            primer_cambio = db(
                (db.pago.id == payment_id) & (db.pago.estado == "pendiente")
            ).update(estado="validado")
            if primer_cambio == 1:
                db(db.suscripcion.id == subscription_id).update(
                    estado="activa",
                    fecha_fin=fecha_fin_inicial + timedelta(days=30),
                    fecha_pago=now,
                    monto_pagado="1500.00",
                    moneda_pago="CUP",
                )

            # Reintento basado en el estado antiguo: no puede validar ni ampliar
            # otra vez la suscripcion.
            segundo_cambio = db(
                (db.pago.id == payment_id) & (db.pago.estado == "pendiente")
            ).update(estado="rechazado")
            self.assertEqual(primer_cambio, 1)
            self.assertEqual(segundo_cambio, 0)
            self.assertEqual(db.pago[payment_id].estado, "validado")
            suscripcion_final = db.suscripcion[subscription_id]
            self.assertEqual(suscripcion_final.estado, "activa")
            self.assertEqual(
                suscripcion_final.fecha_fin,
                fecha_fin_inicial + timedelta(days=30),
            )
            db.commit()
        finally:
            if order_item_id:
                db(db.pedido_item.id == order_item_id).delete()
            if order_id:
                db(db.pedido.id == order_id).delete()
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
