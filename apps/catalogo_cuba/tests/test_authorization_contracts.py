"""Regresiones estaticas para contratos de autorizacion sensibles.

Estas pruebas no sustituyen las pruebas HTTP autenticadas, pero evitan que
se eliminen accidentalmente las comprobaciones de rol y propiedad del recurso.
"""
import re
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
CONTROLLERS = APP_DIR / "controllers.py"
SERVICE_WORKER = APP_DIR / "static" / "sw.js"
CATALOG_TEMPLATE = APP_DIR / "templates" / "catalogo_negocio.html"


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

    def test_subscription_rejects_multiple_open_payments_and_bounds_admin_notes(self):
        body = controller_function(self.source, "admin_realizar_pago")
        self.assertIn("pago_abierto", body)
        self.assertIn('db.pago.estado.belongs(["pendiente", "en_proceso"])', body)
        self.assertIn("suscripcion_abierta_id=suscripcion_id", body)
        self.assertIn('db.pago.suscripcion_abierta_id == suscripcion_id', body)
        self.assertIn('codigo=409', body)
        validation = controller_function(self.source, "superadmin_validar_pago")
        self.assertIn("len(notas) > 2000", validation)
        self.assertIn('None if estado in ("validado", "rechazado") else pago.suscripcion_id', validation)

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
        self.assertIn("producto.stock or 0", body)
        self.assertIn("Solicitud recibida; el negocio debe confirmar disponibilidad", body)

    def test_order_state_route_loads_session_and_authenticated_user(self):
        marker = '@action("catalogo_cuba/admin/pedidos/<pedido_id>/estado", method=["POST"])\n@action.uses(session, auth.user, db)\ndef admin_actualizar_estado_pedido('
        self.assertIn(marker, self.source)

    def test_order_acceptance_is_owned_and_uses_conditional_stock_update(self):
        body = controller_function(self.source, "admin_actualizar_estado_pedido")
        self.assertIn("not es_comerciante(user)", body)
        self.assertIn("db.pedido.negocio_id == negocio.id", body)
        self.assertIn("db.producto.negocio_id == negocio.id", body)
        self.assertIn("db.producto.stock >= linea.cantidad", body)
        self.assertIn("stock=db.producto.stock - linea.cantidad", body)
        self.assertIn('db.pedido.estado == "pendiente_revision"', body)
        self.assertIn("db.rollback()", body)

    def test_dashboard_lists_only_own_pending_orders_and_renders_actions(self):
        body = controller_function(self.source, "admin_dashboard")
        template = (APP_DIR / "templates" / "admin_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("db.pedido.negocio_id == negocio.id", body)
        self.assertIn('db.pedido.estado == "pendiente_revision"', body)
        self.assertIn("pedidos_pendientes=pedidos_pendientes", body)
        self.assertIn('data-order-action="aceptado"', template)
        self.assertIn('data-order-action="rechazado"', template)
        self.assertIn("credentials:'same-origin'", template)
        self.assertIn("No hay pedidos pendientes de revisión.", template)
    def test_offline_order_queue_is_persistent_and_uses_same_id_for_retries(self):
        sw = SERVICE_WORKER.read_text(encoding="utf-8")
        template = CATALOG_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("indexedDB.open(dbName, 1)", template)
        self.assertIn("registration.sync.register('sync-catalogo')", template)
        self.assertIn("indexedDB.open('catalogocuba-orders-v1', 1)", sw)
        self.assertIn("JSON.stringify(order.payload)", sw)
        self.assertIn("SYNC_QUEUE_UPDATED", sw)
        self.assertIn("client_uuid", template)


    def test_public_search_hides_businesses_without_active_subscription(self):
        body = controller_function(self.source, "catalogo_buscar")
        self.assertIn("if not verificar_suscripcion_activa(negocio.id):", body)
        self.assertIn("if verificar_suscripcion_activa(n.id)", body)

    def test_offline_catalog_response_cannot_overwrite_local_catalog_with_empty_data(self):
        template = CATALOG_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("data.exito && Array.isArray(data.productos)", template)
        self.assertIn("catalog = getCatalog();", template)


    def test_inventory_rejects_boolean_and_fractional_quantities(self):
        body = controller_function(self.source, "api_actualizar_stock")
        self.assertIn("isinstance(producto_id_raw, bool)", body)
        self.assertIn("isinstance(stock_raw, bool)", body)
        self.assertIn("str(nuevo_stock) != str(stock_raw).strip()", body)

    def test_public_order_rejects_boolean_and_fractional_quantities(self):
        body = controller_function(self.source, "api_crear_pedido")
        self.assertIn("isinstance(producto_id_raw, bool)", body)
        self.assertIn("isinstance(cantidad_raw, bool)", body)
        self.assertIn("str(cantidad) != str(cantidad_raw).strip()", body)

    def test_uploads_allow_only_image_content_types_and_set_nosniff(self):
        body = controller_function(self.source, "serve_uploads")
        self.assertIn('if not content_type:', body)
        self.assertIn('response.headers["X-Content-Type-Options"] = "nosniff"', body)


    def test_edit_routes_avoid_slug_collisions(self):
        business = controller_function(self.source, "admin_negocio_editar")
        product = controller_function(self.source, "admin_producto_editar")
        category_create = controller_function(self.source, "admin_categoria_nueva")
        category_edit = controller_function(self.source, "admin_categoria_editar")
        self.assertIn("db.negocio.id != negocio.id", business)
        self.assertIn("db.producto.id != producto_id", product)
        self.assertIn("db.categoria.slug == slug", category_create)
        self.assertIn("db.categoria.id != categoria_id", category_edit)


    def test_authenticated_mutation_endpoints_reject_cross_origin_requests(self):
        protected = [
            "admin_actualizar_estado_pedido",
            "api_actualizar_stock",
            "admin_realizar_pago",
            "superadmin_aprobar_negocio",
            "superadmin_toggle_negocio",
            "superadmin_cambiar_rol",
            "superadmin_validar_pago",
            "superadmin_guardar_configuracion",
            "api_marcar_leida",
        ]
        crud_form_posts = [
            "admin_negocio_nuevo",
            "admin_negocio_editar",
            "admin_producto_nuevo",
            "admin_producto_editar",
            "admin_categoria_nueva",
            "admin_categoria_editar",
        ]
        for name in protected:
            with self.subTest(endpoint=name):
                body = controller_function(self.source, name)
                self.assertIn("_peticion_mismo_origen()", body)
        for name in crud_form_posts:
            with self.subTest(endpoint=name):
                body = controller_function(self.source, name)
                self.assertIn("_exigir_mismo_origen_en_post()", body)

    def test_upload_routes_reject_oversized_files_before_form_processing(self):
        for name, field in [
            ("admin_negocio_editar", "logo"),
            ("admin_producto_nuevo", "imagen_principal"),
            ("admin_producto_editar", "imagen_principal"),
            ("admin_categoria_nueva", "imagen"),
            ("admin_categoria_editar", "imagen"),
        ]:
            with self.subTest(endpoint=name):
                body = controller_function(self.source, name)
                self.assertIn("_rechazar_uploads_excesivos", body)
                self.assertIn(field, body)

    def test_superadmin_role_change_is_transactional_and_does_not_swallow_errors(self):
        body = controller_function(self.source, "superadmin_cambiar_rol")
        self.assertIn("db.commit()", body)
        self.assertIn("db.rollback()", body)
        self.assertIn("roles_actuales = roles_tags.get(usuario_id) or []", body)
        self.assertIn("No se pudo actualizar el rol", body)

    def test_configuration_errors_are_rolled_back_without_leaking_details(self):
        body = controller_function(self.source, "superadmin_guardar_configuracion")
        self.assertIn("db.rollback()", body)
        self.assertIn("No se pudo guardar la configuracion", body)
        self.assertNotIn('mensaje="Error: %s" % str(e)', body)

    def test_notification_routes_include_database_fixture(self):
        for name in ("api_notificaciones", "api_marcar_leida"):
            marker = "@action.uses(session, auth.user, db)\ndef " + name + "("
            self.assertIn(marker, self.source)

    def test_product_image_stream_is_rewound_before_optimization(self):
        for name in ("admin_producto_nuevo", "admin_producto_editar"):
            with self.subTest(endpoint=name):
                body = controller_function(self.source, name)
                self.assertIn("archivo.file.seek(0)", body)
                self.assertIn("_optimizar_upload_guardado(", body)
                self.assertIn("form.vars.get(\"imagen_principal\")", body)

if __name__ == "__main__":
    unittest.main()
