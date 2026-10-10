"""
Controladores - CatalogoCuba
Define todas las acciones/rutas de la aplicacion (py4web)
"""
import os
from datetime import timedelta
from urllib.parse import quote

from py4web import action, request, response, redirect, URL, HTTP
from py4web.utils.form import Form, FormStyleBulma
from py4web.utils.factories import ActionFactory
from pydal.validators import IS_EMPTY_OR, IS_IN_DB

from .common import (
    db, session, auth, roles_tags, settings,
    respuesta_json, registrar_visita,
    guardar_imagen, slugify,
    asignar_rol,
    ahora_cuba, formatear_fecha,
)

# ============================================================
# HELPERS
# ============================================================

def get_client_ip():
    return request.environ.get(
        "HTTP_X_FORWARDED_FOR",
        request.environ.get("REMOTE_ADDR", "")
    )


def _tiene_rol(user_id, rol):
    """Verifica si un usuario tiene un rol (tag) determinado."""
    if not user_id:
        return False
    return rol in roles_tags.get(user_id)


def _calcular_rol(user):
    """
    Calcula el rol del usuario actual para el layout.
    Recibe 'user' ya resuelto para evitar llamadas repetidas a auth.get_user().
    """
    if not user:
        return None
    user_id = user["id"]
    if _tiene_rol(user_id, "superadmin"):
        return 'superadmin'
    if _tiene_rol(user_id, "comerciante"):
        return 'comerciante'
    return 'visitante'


def es_superadmin(user=None):
    """Verifica si el usuario actual (o pasado) es superadmin."""
    user = user or auth.get_user()
    if not user:
        return False
    return _tiene_rol(user["id"], "superadmin")


def es_comerciante(user=None):
    """Verifica si el usuario actual (o pasado) es comerciante o superadmin."""
    user = user or auth.get_user()
    if not user:
        return False
    user_id = user["id"]
    return (
        _tiene_rol(user_id, "comerciante") or
        _tiene_rol(user_id, "superadmin")
    )


def contexto_base():
    """
    Fixture que inyecta en el contexto de todas las plantillas:
      - user
      - rol
      - q_actual
    """
    user = auth.get_user()
    return dict(
        user=user,
        rol=_calcular_rol(user),
        q_actual=request.query.get('q', ''),
    )


# ActionFactory con contexto comun; cada accion puede ampliarlo
AccionBase = ActionFactory(contexto_base, db, session, auth.user)


# --- Preparadores de datos para las vistas --------------------------------

def _preparar_producto(p, negocio, con_detalle=False):
    """
    Prepara un producto con los campos que esperan las vistas.
    Si con_detalle=True, agrega badge_stock y whatsapp_url.
    """
    stock = p.stock or 0

    # Badge de estado (listado)
    badge_estado_texto = ''
    badge_estado_clase = ''
    if not p.disponible:
        badge_estado_texto, badge_estado_clase = 'Agotado', 'badge-red'
    elif p.stock is not None and stock <= 5:
        badge_estado_texto, badge_estado_clase = 'Quedan %d' % stock, 'badge-yellow'

    # Badge de stock (detalle)
    badge_stock_texto = ''
    badge_stock_clase = ''
    if p.stock is None:
        badge_stock_texto, badge_stock_clase = '', ''
    elif stock <= 0:
        badge_stock_texto, badge_stock_clase = '❌ Agotado', 'badge-red'
    elif stock <= 5:
        badge_stock_texto, badge_stock_clase = '⚠️ Quedan %d unidades' % stock, 'badge-yellow'
    else:
        badge_stock_texto, badge_stock_clase = '✅ En stock (%d)' % stock, 'badge-green'

    mostrar_precio = bool(negocio.mostrar_precios and p.precio)
    mostrar_precio_anterior = bool(p.precio_anterior and p.en_oferta and negocio.mostrar_precios)

    data = {
        'id': p.id,
        'nombre': p.nombre,
        'slug': p.slug,
        'descripcion': p.descripcion,
        'descripcion_corta': p.descripcion_corta,
        'sku': p.sku,
        'peso': p.peso,
        'stock': stock,
        'vistas': p.vistas or 0,
        'imagen_principal': p.imagen_principal,
        'en_oferta': p.en_oferta,
        'destacado': p.destacado,
        'disponible': p.disponible,
        'categoria_id': p.categoria_id,
        'mostrar_precio': mostrar_precio,
        'precio_texto': ('%.2f %s' % (p.precio, p.moneda or 'CUP')) if p.precio else None,
        'mostrar_precio_anterior': mostrar_precio_anterior,
        'precio_anterior_texto': ('%.2f %s' % (p.precio_anterior, p.moneda or 'CUP')) if p.precio_anterior else None,
        'badge_estado_texto': badge_estado_texto,
        'badge_estado_clase': badge_estado_clase,
    }

    if con_detalle:
        if isinstance(p.tags, str):
            tags = [t.strip() for t in p.tags.split(',') if t.strip()]
        else:
            tags = p.tags or []

        whatsapp_url = None
        if negocio.whatsapp:
            texto = 'Hola, me interesa el producto: %s' % p.nombre
            whatsapp_url = 'https://wa.me/%s?text=%s' % (negocio.whatsapp, quote(texto))

        data.update({
            'badge_stock_texto': badge_stock_texto,
            'badge_stock_clase': badge_stock_clase,
            'tags_lista': tags,
            'whatsapp_url': whatsapp_url,
        })

    return data


def _preparar_suscripcion(s):
    """Prepara una suscripcion para la vista admin_suscripcion."""
    if not s:
        return None

    estados_badge = {
        'activa':    ('badge-green',  '✅ Activa'),
        'prueba':    ('badge-blue',   '🎁 Periodo de prueba'),
        'vencida':   ('badge-red',    '❌ Vencida'),
        'pendiente': ('badge-yellow', '⏳ Pendiente de pago'),
    }
    clase, texto = estados_badge.get(s.estado, ('badge-yellow', s.estado))

    metodos_texto = {
        'transfermovil': '📱 Transfermovil',
        'presencial':    '💵 Pago presencial',
        'usdt':          '💎 USDT',
        'prueba':        '🎁 Gratis',
    }
    metodo_texto = metodos_texto.get(s.metodo_pago, '-')

    return {
        'id': s.id,
        'estado': s.estado,
        'estado_badge_clase': clase,
        'estado_badge_texto': texto,
        'metodo_pago_texto': metodo_texto,
        'fecha_inicio_texto': s.fecha_inicio.strftime('%d/%m/%Y') if s.fecha_inicio else '-',
        'fecha_fin_texto': s.fecha_fin.strftime('%d/%m/%Y') if s.fecha_fin else '-',
        'monto_pagado_texto': '%.2f %s' % (s.monto_pagado or 0, s.moneda_pago or 'CUP'),
        'necesita_renovacion': s.estado in ('vencida', 'pendiente'),
    }


def _preparar_pago(p, negocio_nombre=None, usuario_email=None):
    """Prepara un pago para la vista admin_suscripcion o superadmin_pagos."""
    estados = {
        'validado':   ('badge-green',  '✅ Validado'),
        'pendiente':  ('badge-yellow', '⏳ Pendiente'),
        'rechazado':  ('badge-red',    '❌ Rechazado'),
        'en_proceso': ('badge-blue',   '🔄 En proceso'),
    }
    metodos = {
        'transfermovil': '📱 Transfermovil',
        'presencial':    '💵 Presencial',
        'usdt':          '💎 USDT',
    }
    clase, texto = estados.get(p.estado, ('badge-blue', p.estado))
    metodo_texto = metodos.get(p.metodo_pago, p.metodo_pago or '-')

    return {
        'id': p.id,
        'metodo_pago_texto': metodo_texto,
        'monto_texto': '%.2f %s' % (p.monto or 0, p.moneda or 'CUP'),
        'referencia': p.referencia,
        'estado': p.estado,
        'estado_badge_clase': clase,
        'estado_badge_texto': texto,
        'fecha_solicitud_texto': p.fecha_solicitud.strftime('%d/%m/%Y %H:%M') if p.fecha_solicitud else '-',
        'fecha_validacion_texto': p.fecha_validacion.strftime('%d/%m/%Y') if p.fecha_validacion else '-',
        'nombre_negocio': negocio_nombre,
        'email_usuario': usuario_email,
        'mostrar_acciones': p.estado in ('pendiente', 'en_proceso'),
    }


# ============================================================
# RUTAS PUBLICAS
# ============================================================

@action("catalogo_cuba")
@action.uses(AccionBase, "catalogo_home.html")
def catalogo_home():
    negocios_raw = db(
        (db.negocio.activo == True) & (db.negocio.aprobado == True)
    ).select(orderby=~db.negocio.fecha_creacion, limitby=(0, 20))

    negocios = [{
        'id': n.id,
        'nombre': n.nombre,
        'slug': n.slug,
        'descripcion': n.descripcion,
        'provincia': n.provincia,
        'logo': n.logo,
    } for n in negocios_raw]

    return dict(negocios=negocios, titulo="CatalogoCuba - Directorio de Negocios")


@action("catalogo_cuba/negocio/<slug>")
@action.uses(AccionBase, "catalogo_negocio.html")
def catalogo_negocio(slug):
    negocio = db(
        (db.negocio.slug == slug) &
        (db.negocio.activo == True) &
        (db.negocio.aprobado == True)
    ).select().first()
    if not negocio:
        raise HTTP(404, "Negocio no encontrado")

    registrar_visita(negocio_id=negocio.id, ip=get_client_ip(),
                     user_agent=request.environ.get("HTTP_USER_AGENT", ""))

    categorias_raw = db(
        (db.categoria.negocio_id == negocio.id) & (db.categoria.activa == True)
    ).select(orderby=db.categoria.orden)
    categorias = [{'id': c.id, 'nombre': c.nombre, 'slug': c.slug} for c in categorias_raw]

    destacados_raw = db(
        (db.producto.negocio_id == negocio.id) &
        (db.producto.disponible == True) &
        (db.producto.destacado == True)
    ).select(orderby=~db.producto.fecha_creacion, limitby=(0, 8))
    destacados = [_preparar_producto(p, negocio) for p in destacados_raw]

    productos_raw = db(
        (db.producto.negocio_id == negocio.id) & (db.producto.disponible == True)
    ).select(orderby=~db.producto.fecha_creacion, limitby=(0, settings.PAGE_SIZE))
    productos = [_preparar_producto(p, negocio) for p in productos_raw]

    suscripcion_activa = verificar_suscripcion_activa(negocio.id)

    return dict(
        negocio=negocio,
        categorias=categorias,
        destacados=destacados,
        productos=productos,
        suscripcion_activa=suscripcion_activa,
        titulo="%s - Catalogo" % negocio.nombre,
    )


@action("catalogo_cuba/negocio/<slug>/categoria/<categoria_slug>")
@action.uses(AccionBase, "catalogo_negocio.html")
def catalogo_por_categoria(slug, categoria_slug):
    negocio = db(
        (db.negocio.slug == slug) &
        (db.negocio.activo == True) & (db.negocio.aprobado == True)
    ).select().first()
    if not negocio:
        raise HTTP(404, "Negocio no encontrado")

    categoria = db(
        (db.categoria.negocio_id == negocio.id) & (db.categoria.slug == categoria_slug)
    ).select().first()
    if not categoria:
        raise HTTP(404, "Categoria no encontrada")

    productos_raw = db(
        (db.producto.negocio_id == negocio.id) &
        (db.producto.categoria_id == categoria.id) &
        (db.producto.disponible == True)
    ).select(orderby=~db.producto.fecha_creacion)
    productos = [_preparar_producto(p, negocio) for p in productos_raw]

    categorias_raw = db(
        (db.categoria.negocio_id == negocio.id) & (db.categoria.activa == True)
    ).select(orderby=db.categoria.orden)
    categorias = [{'id': c.id, 'nombre': c.nombre, 'slug': c.slug} for c in categorias_raw]

    return dict(
        negocio=negocio,
        categorias=categorias,
        destacados=[],
        productos=productos,
        suscripcion_activa=verificar_suscripcion_activa(negocio.id),
        titulo="%s - %s" % (categoria.nombre, negocio.nombre),
    )


@action("catalogo_cuba/negocio/<slug>/producto/<producto_slug>")
@action.uses(AccionBase, "catalogo_producto.html")
def catalogo_producto_detalle(slug, producto_slug):
    negocio = db(
        (db.negocio.slug == slug) &
        (db.negocio.activo == True) & (db.negocio.aprobado == True)
    ).select().first()
    if not negocio:
        raise HTTP(404, "Negocio no encontrado")

    producto = db(
        (db.producto.negocio_id == negocio.id) & (db.producto.slug == producto_slug)
    ).select().first()
    if not producto:
        raise HTTP(404, "Producto no encontrado")

    db(db.producto.id == producto.id).update(vistas=(producto.vistas or 0) + 1)
    db.commit()

    registrar_visita(negocio_id=negocio.id, producto_id=producto.id,
                     ip=get_client_ip(),
                     user_agent=request.environ.get("HTTP_USER_AGENT", ""))

    relacionados = []
    if producto.categoria_id:
        rel_raw = db(
            (db.producto.categoria_id == producto.categoria_id) &
            (db.producto.id != producto.id) &
            (db.producto.disponible == True)
        ).select(orderby=~db.producto.vistas, limitby=(0, 4))
        relacionados = [_preparar_producto(r, negocio) for r in rel_raw]

    producto_dict = _preparar_producto(producto, negocio, con_detalle=True)

    negocio_dict = {
        'id': negocio.id,
        'nombre': negocio.nombre,
        'slug': negocio.slug,
        'logo': negocio.logo,
        'telefono': negocio.telefono,
        'whatsapp': negocio.whatsapp,
        'provincia': negocio.provincia,
        'mostrar_precios': negocio.mostrar_precios,
    }

    return dict(
        negocio=negocio_dict,
        producto=producto_dict,
        relacionados=relacionados,
        titulo="%s - %s" % (producto.nombre, negocio.nombre),
    )


# ============================================================
# BUSQUEDA PUBLICA
# ============================================================

@action("catalogo_cuba/buscar")
@action.uses(AccionBase, "catalogo_busqueda.html")
def catalogo_buscar():
    query_texto = request.query.get("q", "").strip()
    tipo = request.query.get("tipo", "productos")

    resultados = []
    negocios = []
    total_resultados = 0
    total_negocios = 0

    if query_texto:
        if tipo == "productos":
            rows = db(
                db.producto.nombre.contains(query_texto, case_sensitive=False) &
                (db.producto.disponible == True) &
                (db.producto.negocio_id == db.negocio.id) &
                (db.negocio.activo == True) & (db.negocio.aprobado == True)
            ).select(db.producto.ALL, db.negocio.ALL,
                     orderby=~db.producto.fecha_creacion, limitby=(0, 50))

            for r in rows:
                producto = r.producto
                negocio = r.negocio
                resultados.append({
                    'producto': {
                        'id': producto.id,
                        'nombre': producto.nombre,
                        'slug': producto.slug,
                        'imagen_principal': producto.imagen_principal,
                        'precio_texto': ('%.2f %s' % (producto.precio, producto.moneda or 'CUP')) if producto.precio else None,
                    },
                    'negocio': {
                        'id': negocio.id,
                        'nombre': negocio.nombre,
                        'slug': negocio.slug,
                    },
                })
            total_resultados = len(resultados)

        elif tipo == "negocios":
            neg_raw = db(
                db.negocio.nombre.contains(query_texto, case_sensitive=False) &
                (db.negocio.activo == True) & (db.negocio.aprobado == True)
            ).select(orderby=db.negocio.nombre)
            negocios = [{
                'id': n.id,
                'nombre': n.nombre,
                'slug': n.slug,
                'descripcion': n.descripcion,
                'logo': n.logo,
            } for n in neg_raw]
            total_negocios = len(negocios)

    return dict(
        query=query_texto,
        tipo=tipo,
        resultados=resultados,
        negocios=negocios,
        total_resultados=total_resultados,
        total_negocios=total_negocios,
        titulo="Buscar: %s" % query_texto if query_texto else "Buscar",
    )


# ============================================================
# API PUBLICA (JSON)
# ============================================================

@action("catalogo_cuba/api/negocio/<slug>/catalogo")
@action.uses(db, contexto_base)
def api_catalogo_negocio(slug):
    negocio = db(
        (db.negocio.slug == slug) &
        (db.negocio.activo == True) & (db.negocio.aprobado == True)
    ).select().first()
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado", codigo=404)

    if not verificar_suscripcion_activa(negocio.id):
        return respuesta_json(exito=False, mensaje="Catalogo no disponible temporalmente", codigo=403)

    categorias_raw = db(
        (db.categoria.negocio_id == negocio.id) & (db.categoria.activa == True)
    ).select(orderby=db.categoria.orden)
    categorias = [{
        'id': c.id, 'nombre': c.nombre, 'slug': c.slug,
        'descripcion': c.descripcion or '',
        'imagen': c.imagen,
    } for c in categorias_raw]

    productos_raw = db(
        (db.producto.negocio_id == negocio.id) & (db.producto.disponible == True)
    ).select(orderby=~db.producto.fecha_creacion)
    productos = [_preparar_producto(p, negocio) for p in productos_raw]

    response.headers["Cache-Control"] = "public, max-age=3600"
    return dict(
        exito=True,
        negocio={
            'id': negocio.id, 'nombre': negocio.nombre, 'slug': negocio.slug,
            'descripcion': negocio.descripcion or '',
            'logo': negocio.logo,
            'telefono': negocio.telefono or '',
            'whatsapp': negocio.whatsapp or '',
            'provincia': negocio.provincia or '',
            'municipio': negocio.municipio or '',
            'mostrar_precios': negocio.mostrar_precios,
        },
        categorias=categorias,
        productos=productos,
        total_productos=len(productos),
    )


@action("catalogo_cuba/api/negocio/<slug>/producto/<producto_slug>")
@action.uses(db, contexto_base)
def api_producto_detalle(slug, producto_slug):
    negocio = db((db.negocio.slug == slug)).select().first()
    # No exponer catalogos pendientes de aprobacion o suspendidos.
    if not negocio or not negocio.activo or not negocio.aprobado:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado", codigo=404)

    producto = db(
        (db.producto.negocio_id == negocio.id) & (db.producto.slug == producto_slug)
    ).select().first()
    if not producto:
        return respuesta_json(exito=False, mensaje="Producto no encontrado", codigo=404)

    response.headers["Cache-Control"] = "public, max-age=3600"
    return dict(exito=True, producto=_preparar_producto(producto, negocio, con_detalle=True))


# ============================================================
# PANEL DE COMERCIANTE
# ============================================================

@action("catalogo_cuba/admin")
@action.uses(AccionBase, "admin_dashboard.html")
def admin_dashboard():
    user = auth.get_user()
    if not user:
        redirect(URL("auth", "login"))
    if es_superadmin(user):
        redirect(URL("catalogo_cuba", "superadmin"))
    if not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin", "negocio", "nuevo"))

    total_productos = db(db.producto.negocio_id == negocio.id).count()
    productos_activos = db(
        (db.producto.negocio_id == negocio.id) & (db.producto.disponible == True)
    ).count()
    total_categorias = db(db.categoria.negocio_id == negocio.id).count()

    hace_7_dias = ahora_cuba() - timedelta(days=7)
    visitas_recientes = db(
        (db.visita.negocio_id == negocio.id) & (db.visita.fecha >= hace_7_dias)
    ).count()

    mas_vistos_raw = db(db.producto.negocio_id == negocio.id).select(
        orderby=~db.producto.vistas, limitby=(0, 5)
    )
    mas_vistos = [_preparar_producto(p, negocio) for p in mas_vistos_raw]

    suscripcion_raw = db(db.suscripcion.negocio_id == negocio.id).select(
        orderby=~db.suscripcion.fecha_creacion, limitby=(0, 1)
    ).first()
    suscripcion = _preparar_suscripcion(suscripcion_raw)

    bajo_stock_raw = db(
        (db.producto.negocio_id == negocio.id) &
        (db.producto.stock <= 5) & (db.producto.disponible == True)
    ).select()
    bajo_stock = [{'id': p.id, 'nombre': p.nombre, 'stock': p.stock or 0} for p in bajo_stock_raw]

    return dict(
        negocio={
            'id': negocio.id, 'nombre': negocio.nombre, 'slug': negocio.slug,
        },
        total_productos=total_productos,
        productos_activos=productos_activos,
        total_categorias=total_categorias,
        visitas_recientes=visitas_recientes,
        mas_vistos=mas_vistos,
        suscripcion=suscripcion,
        bajo_stock=bajo_stock,
        titulo="Panel - %s" % negocio.nombre,
    )


# ============================================================
# CRUD NEGOCIO
# ============================================================

@action("catalogo_cuba/admin/negocio/nuevo", method=["GET", "POST"])
@action.uses(AccionBase, "admin_negocio_form.html")
def admin_negocio_nuevo():
    user = auth.get_user()
    if not user:
        redirect(URL("auth", "login"))

    if db(db.negocio.usuario_id == user["id"]).count() > 0:
        redirect(URL("catalogo_cuba", "admin"))

    campos = [
        "nombre", "descripcion", "direccion", "telefono",
        "email", "whatsapp", "horario", "provincia", "municipio",
        "color_tema", "moneda_principal", "mostrar_precios",
        "facebook", "instagram", "telegram", "meta_descripcion",
    ]
    form = Form(db.negocio, fields=campos, deletable=False, formstyle=FormStyleBulma)

    if form.accepted:
        negocio_id = form.vars.get("id")
        nombre = form.vars.get("nombre", "")
        slug = slugify(nombre)
        contador = 1
        slug_original = slug
        while db(db.negocio.slug == slug).count() > 0:
            slug = "%s-%d" % (slug_original, contador)
            contador += 1

        db(db.negocio.id == negocio_id).update(
            usuario_id=user["id"], slug=slug,
            fecha_creacion=ahora_cuba(), fecha_actualizacion=ahora_cuba(),
            activo=True, aprobado=False,
        )
        db.suscripcion.insert(
            negocio_id=negocio_id, usuario_id=user["id"],
            fecha_inicio=ahora_cuba().date(),
            fecha_fin=(ahora_cuba() + timedelta(days=settings.DIAS_PRUEBA_GRATIS)).date(),
            estado="prueba", metodo_pago="prueba",
            monto_pagado=0, dias_prueba=settings.DIAS_PRUEBA_GRATIS,
            fecha_creacion=ahora_cuba(),
        )
        db.commit()

        # Asignar rol "comerciante" al usuario tras crear su negocio
        asignar_rol(user["id"], "comerciante")

        redirect(URL("catalogo_cuba", "admin"))

    campos_disponibles = list(form.custom.widgets.keys())
    return dict(
        form=form, modo="crear",
        campos_disponibles=campos_disponibles,
        titulo="Crear mi negocio",
    )


@action("catalogo_cuba/admin/negocio/editar", method=["GET", "POST"])
@action.uses(AccionBase, "admin_negocio_form.html")
def admin_negocio_editar():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin", "negocio", "nuevo"))

    campos = [
        "nombre", "descripcion", "logo", "direccion", "telefono",
        "email", "whatsapp", "horario", "provincia", "municipio",
        "color_tema", "moneda_principal", "mostrar_precios",
        "facebook", "instagram", "telegram", "meta_descripcion",
    ]
    form = Form(db.negocio, record=negocio, fields=campos,
                deletable=False, formstyle=FormStyleBulma)

    if form.accepted:
        db(db.negocio.id == negocio.id).update(
            fecha_actualizacion=ahora_cuba(),
            slug=slugify(form.vars.get("nombre", negocio.nombre)),
        )
        db.commit()
        redirect(URL("catalogo_cuba", "admin"))

    campos_disponibles = list(form.custom.widgets.keys())
    return dict(
        form=form, negocio=negocio, modo="editar",
        campos_disponibles=campos_disponibles,
        titulo="Editar mi negocio",
    )


# ============================================================
# CRUD PRODUCTOS
# ============================================================

@action("catalogo_cuba/admin/productos")
@action.uses(AccionBase, "admin_productos.html")
def admin_productos():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin", "negocio", "nuevo"))

    pagina = int(request.query.get("pagina", 1) or 1)
    filtro_categoria = request.query.get("categoria", "")
    filtro_nombre = request.query.get("q", "")
    por_pagina = 20

    query = db.producto.negocio_id == negocio.id
    if filtro_categoria:
        query &= db.producto.categoria_id == int(filtro_categoria)
    if filtro_nombre:
        query &= db.producto.nombre.contains(filtro_nombre, case_sensitive=False)

    total = db(query).count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    offset = (pagina - 1) * por_pagina
    productos_raw = db(query).select(orderby=~db.producto.fecha_creacion,
                                     limitby=(offset, offset + por_pagina))

    categorias_raw = db(
        (db.categoria.negocio_id == negocio.id) & (db.categoria.activa == True)
    ).select(orderby=db.categoria.orden)
    categorias = [{'id': c.id, 'nombre': c.nombre} for c in categorias_raw]
    categorias_por_id = {c['id']: c['nombre'] for c in categorias}

    productos = []
    for p in productos_raw:
        d = _preparar_producto(p, negocio)
        d['categoria_nombre'] = categorias_por_id.get(p.categoria_id)
        productos.append(d)

    return dict(
        total=total, productos=productos, categorias=categorias,
        filtro_nombre=filtro_nombre, filtro_categoria=filtro_categoria,
        pagina=pagina, total_paginas=total_paginas,
        negocio={'slug': negocio.slug},
        titulo="Mis productos",
    )


@action("catalogo_cuba/admin/producto/nuevo", method=["GET", "POST"])
@action.uses(AccionBase, "admin_producto_form.html")
def admin_producto_nuevo():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin"))

    db.producto.categoria_id.requires = IS_EMPTY_OR(
        IS_IN_DB(db(db.categoria.negocio_id == negocio.id), "categoria.id", "%(nombre)s")
    )

    campos = [
        "nombre", "descripcion", "descripcion_corta", "precio",
        "precio_anterior", "moneda", "disponible", "en_oferta",
        "stock", "sku", "categoria_id", "imagen_principal",
        "destacado", "tags", "peso", "meta_keywords",
    ]
    form = Form(db.producto, fields=campos, deletable=False, formstyle=FormStyleBulma)

    if form.accepted:
        producto_id = form.vars.get("id")
        slug = slugify(form.vars.get("nombre", ""))
        contador = 1
        original = slug
        while db((db.producto.negocio_id == negocio.id) & (db.producto.slug == slug)).count() > 0:
            slug = "%s-%d" % (original, contador)
            contador += 1

        imagen = None
        archivo = request.files.get("imagen_principal")
        if archivo and archivo.file:
            imagen = guardar_imagen(archivo.file, "productos/%s" % negocio.id)

        db(db.producto.id == producto_id).update(
            slug=slug, negocio_id=negocio.id, imagen_principal=imagen,
            fecha_creacion=ahora_cuba(), fecha_actualizacion=ahora_cuba(),
        )
        db.commit()
        redirect(URL("catalogo_cuba", "admin", "productos"))

    return dict(form=form, negocio=negocio, modo="crear",
                titulo="Nuevo producto")


@action("catalogo_cuba/admin/producto/editar/<producto_id:int>", method=["GET", "POST"])
@action.uses(AccionBase, "admin_producto_form.html")
def admin_producto_editar(producto_id):
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        raise HTTP(403)

    producto = db(
        (db.producto.id == producto_id) & (db.producto.negocio_id == negocio.id)
    ).select().first()
    if not producto:
        raise HTTP(404)

    db.producto.categoria_id.requires = IS_EMPTY_OR(
        IS_IN_DB(db(db.categoria.negocio_id == negocio.id), "categoria.id", "%(nombre)s")
    )

    campos = [
        "nombre", "descripcion", "descripcion_corta", "precio",
        "precio_anterior", "moneda", "disponible", "en_oferta",
        "stock", "sku", "categoria_id", "imagen_principal",
        "destacado", "tags", "peso", "meta_keywords",
    ]
    form = Form(db.producto, record=producto, fields=campos,
                deletable=True, formstyle=FormStyleBulma)

    if form.accepted:
        imagen = producto.imagen_principal
        archivo = request.files.get("imagen_principal")
        if archivo and archivo.file:
            nueva = guardar_imagen(archivo.file, "productos/%s" % negocio.id)
            if nueva:
                imagen = nueva

        db(db.producto.id == producto_id).update(
            slug=slugify(form.vars.get("nombre", producto.nombre)),
            imagen_principal=imagen,
            fecha_actualizacion=ahora_cuba(),
        )
        db.commit()
        redirect(URL("catalogo_cuba", "admin", "productos"))

    return dict(form=form, negocio=negocio, producto=producto,
                modo="editar", titulo="Editar: %s" % producto.nombre)


# ============================================================
# CRUD CATEGORIAS
# ============================================================

@action("catalogo_cuba/admin/categorias")
@action.uses(AccionBase, "admin_categorias.html")
def admin_categorias():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin"))

    categorias_raw = db(db.categoria.negocio_id == negocio.id).select(orderby=db.categoria.orden)

    conteo = {}
    if categorias_raw:
        rows = db(db.producto.categoria_id.belongs([c.id for c in categorias_raw])).select(
            db.producto.categoria_id, db.producto.id.count(),
            groupby=db.producto.categoria_id,
        )
        conteo = {r.producto.categoria_id: r[db.producto.id.count()] for r in rows}

    categorias = [{
        'id': c.id, 'nombre': c.nombre, 'descripcion': c.descripcion,
        'orden': c.orden or 0, 'activa': c.activa,
        'cantidad_productos': conteo.get(c.id, 0),
    } for c in categorias_raw]

    return dict(negocio=negocio, categorias=categorias, titulo="Mis categorias")


@action("catalogo_cuba/admin/categoria/nueva", method=["GET", "POST"])
@action.uses(AccionBase, "admin_categoria_form.html")
def admin_categoria_nueva():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin"))

    form = Form(db.categoria,
                fields=["nombre", "descripcion", "imagen", "orden", "activa"],
                deletable=False, formstyle=FormStyleBulma)

    if form.accepted:
        cat_id = form.vars.get("id")
        db(db.categoria.id == cat_id).update(
            slug=slugify(form.vars.get("nombre", "")),
            negocio_id=negocio.id,
            fecha_creacion=ahora_cuba(),
        )
        db.commit()
        redirect(URL("catalogo_cuba", "admin", "categorias"))

    return dict(form=form, negocio=negocio, modo="crear",
                titulo="Nueva categoria")


@action("catalogo_cuba/admin/categoria/editar/<categoria_id:int>", method=["GET", "POST"])
@action.uses(AccionBase, "admin_categoria_form.html")
def admin_categoria_editar(categoria_id):
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        raise HTTP(403)

    categoria = db(
        (db.categoria.id == categoria_id) & (db.categoria.negocio_id == negocio.id)
    ).select().first()
    if not categoria:
        raise HTTP(404)

    form = Form(db.categoria, record=categoria,
                fields=["nombre", "descripcion", "imagen", "orden", "activa"],
                deletable=True, formstyle=FormStyleBulma)

    if form.accepted:
        if not form.deleted:
            db(db.categoria.id == categoria_id).update(
                slug=slugify(form.vars.get("nombre", categoria.nombre)),
            )
            db.commit()
        redirect(URL("catalogo_cuba", "admin", "categorias"))

    return dict(form=form, negocio=negocio, categoria=categoria,
                modo="editar", titulo="Editar: %s" % categoria.nombre)


# ============================================================
# INVENTARIO
# ============================================================

@action("catalogo_cuba/admin/inventario")
@action.uses(AccionBase, "admin_inventario.html")
def admin_inventario():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin"))

    productos_raw = db(db.producto.negocio_id == negocio.id).select(orderby=db.producto.stock)

    productos = []
    agotados = 0
    bajos = 0
    for p in productos_raw:
        stock = p.stock or 0
        if stock <= 0:
            clase, estilo = 'fila-agotado', 'background:rgba(254,226,226,.3)'
            agotados += 1
        elif stock <= 5:
            clase, estilo = 'fila-bajo', 'background:rgba(254,243,199,.3)'
            bajos += 1
        else:
            clase, estilo = '', ''

        productos.append({
            'id': p.id, 'nombre': p.nombre, 'sku': p.sku,
            'stock': stock, 'imagen_principal': p.imagen_principal,
            'clase_fila': clase, 'estilo_fila': estilo,
        })

    return dict(
        negocio=negocio, productos=productos,
        total_productos=len(productos),
        productos_agotados=agotados,
        bajo_stock=bajos,
        titulo="Inventario",
    )


@action("catalogo_cuba/api/inventario/actualizar", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def api_actualizar_stock():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    try:
        data = request.json or {}
        producto_id = data.get("producto_id")
        nuevo_stock = data.get("stock")

        negocio = db(db.negocio.usuario_id == user["id"]).select().first()
        if not negocio:
            return respuesta_json(exito=False, mensaje="Negocio no encontrado")

        producto = db(
            (db.producto.id == producto_id) & (db.producto.negocio_id == negocio.id)
        ).select().first()
        if not producto:
            return respuesta_json(exito=False, mensaje="Producto no encontrado")

        db(db.producto.id == producto_id).update(
            stock=int(nuevo_stock), fecha_actualizacion=ahora_cuba(),
        )
        db.commit()
        return respuesta_json(exito=True, mensaje="Stock actualizado")
    except Exception as e:
        return respuesta_json(exito=False, mensaje="Error: %s" % str(e))


# ============================================================
# SUSCRIPCION Y PAGOS (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/suscripcion")
@action.uses(AccionBase, "admin_suscripcion.html")
def admin_suscripcion():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin"))

    suscripcion_raw = db(db.suscripcion.negocio_id == negocio.id).select(
        orderby=~db.suscripcion.fecha_creacion, limitby=(0, 1)
    ).first()
    suscripcion = _preparar_suscripcion(suscripcion_raw)

    pagos_raw = db(db.pago.negocio_id == negocio.id).select(
        orderby=~db.pago.fecha_solicitud
    )
    pagos = [_preparar_pago(p) for p in pagos_raw]

    mostrar_renovacion = (not suscripcion) or suscripcion['necesita_renovacion']

    return dict(
        negocio=negocio, suscripcion=suscripcion, pagos=pagos,
        mostrar_renovacion=mostrar_renovacion,
        costo_cup=settings.COSTO_SUSCRIPCION_MENSUAL_CUP,
        costo_usdt=settings.COSTO_SUSCRIPCION_MENSUAL_USDT,
        titulo="Mi suscripcion",
    )


@action("catalogo_cuba/admin/pago/realizar", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def admin_realizar_pago():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    try:
        negocio = db(db.negocio.usuario_id == user["id"]).select().first()
        if not negocio:
            return respuesta_json(exito=False, mensaje="Negocio no encontrado")

        metodo = request.forms.get("metodo_pago")
        monto = request.forms.get("monto")
        moneda = request.forms.get("moneda", "CUP")
        referencia = request.forms.get("referencia", "")

        suscripcion = db(
            (db.suscripcion.negocio_id == negocio.id) &
            db.suscripcion.estado.belongs(["activa", "prueba", "pendiente", "vencida"])
        ).select(orderby=~db.suscripcion.fecha_creacion, limitby=(0, 1)).first()

        if not suscripcion:
            suscripcion_id = db.suscripcion.insert(
                negocio_id=negocio.id, usuario_id=user["id"],
                fecha_inicio=ahora_cuba().date(),
                fecha_fin=(ahora_cuba() + timedelta(days=30)).date(),
                estado="pendiente", metodo_pago=metodo,
                fecha_creacion=ahora_cuba(),
            )
        else:
            suscripcion_id = suscripcion.id
            db(db.suscripcion.id == suscripcion_id).update(
                estado="pendiente", metodo_pago=metodo,
            )
        db.commit()

        pago_id = db.pago.insert(
            suscripcion_id=suscripcion_id, negocio_id=negocio.id,
            usuario_id=user["id"], monto=float(monto), moneda=moneda,
            metodo_pago=metodo, estado="pendiente", referencia=referencia,
            fecha_solicitud=ahora_cuba(),
        )
        db.commit()

        return respuesta_json(exito=True,
                              mensaje="Pago registrado correctamente. Pendiente de validacion.",
                              datos={"pago_id": pago_id})
    except Exception as e:
        return respuesta_json(exito=False, mensaje="Error: %s" % str(e))


# ============================================================
# ESTADISTICAS (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/estadisticas")
@action.uses(AccionBase, "admin_estadisticas.html")
def admin_estadisticas():
    user = auth.get_user()
    if not user or not es_comerciante(user):
        raise HTTP(403)

    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    if not negocio:
        redirect(URL("catalogo_cuba", "admin"))

    desde = ahora_cuba() - timedelta(days=30)
    visitas_raw = db(
        (db.visita.negocio_id == negocio.id) & (db.visita.fecha >= desde)
    ).select(orderby=db.visita.fecha)

    producto_ids = list({v.producto_id for v in visitas_raw if v.producto_id})
    productos_por_id = {}
    if producto_ids:
        prods = db(db.producto.id.belongs(producto_ids)).select(db.producto.id, db.producto.nombre)
        productos_por_id = {p.id: p.nombre for p in prods}

    visitas = [{
        'fecha_texto': v.fecha.strftime('%d/%m/%Y %H:%M') if v.fecha else '-',
        'ip': v.ip,
        'producto_nombre': productos_por_id.get(v.producto_id),
    } for v in visitas_raw[-50:]]

    top_raw = db(db.producto.negocio_id == negocio.id).select(
        orderby=~db.producto.vistas, limitby=(0, 10)
    )
    top_productos = [_preparar_producto(p, negocio) for p in top_raw]

    total_visitas = db(db.visita.negocio_id == negocio.id).count()
    total_productos = db(db.producto.negocio_id == negocio.id).count()

    return dict(
        negocio=negocio, visitas=visitas, top_productos=top_productos,
        total_visitas=total_visitas, total_productos=total_productos,
        titulo="Estadisticas",
    )


# ============================================================
# PANEL SUPERADMIN
# ============================================================

@action("catalogo_cuba/superadmin")
@action.uses(AccionBase, "superadmin_dashboard.html")
def superadmin_dashboard():
    user = auth.get_user()
    if not es_superadmin(user):
        raise HTTP(403, "Acceso restringido")

    total_negocios = db(db.negocio.id > 0).count()
    negocios_activos = db((db.negocio.activo == True) & (db.negocio.aprobado == True)).count()
    negocios_pendientes = db(db.negocio.aprobado == False).count()
    total_usuarios = db(db.auth_user.id > 0).count()
    total_productos = db(db.producto.id > 0).count()
    suscripciones_activas = db(db.suscripcion.estado == "activa").count()
    suscripciones_vencidas = db(db.suscripcion.estado == "vencida").count()
    suscripciones_prueba = db(db.suscripcion.estado == "prueba").count()
    pagos_pendientes = db(db.pago.estado == "pendiente").count()

    negocios_raw = db(db.negocio.id > 0).select(
        orderby=~db.negocio.fecha_creacion, limitby=(0, 10)
    )

    usuario_ids = [n.usuario_id for n in negocios_raw if n.usuario_id]
    emails = {}
    if usuario_ids:
        usuarios = db(db.auth_user.id.belongs(usuario_ids)).select()
        emails = {u.id: u.email for u in usuarios}

    negocios_recientes = []
    for n in negocios_raw:
        if n.aprobado and n.activo:
            texto, clase = 'Activo', 'badge-green'
        elif not n.aprobado:
            texto, clase = 'Pendiente', 'badge-yellow'
        else:
            texto, clase = 'Inactivo', 'badge-red'

        negocios_recientes.append({
            'id': n.id, 'nombre': n.nombre, 'slug': n.slug, 'logo': n.logo,
            'provincia': n.provincia,
            'propietario_email': emails.get(n.usuario_id, '-'),
            'badge_estado_texto': texto, 'badge_estado_clase': clase,
            'fecha_creacion_texto': n.fecha_creacion.strftime('%d/%m/%Y') if n.fecha_creacion else '-',
        })

    return dict(
        total_negocios=total_negocios,
        negocios_activos=negocios_activos,
        negocios_pendientes=negocios_pendientes,
        total_usuarios=total_usuarios,
        total_productos=total_productos,
        suscripciones_activas=suscripciones_activas,
        suscripciones_vencidas=suscripciones_vencidas,
        suscripciones_prueba=suscripciones_prueba,
        pagos_pendientes=pagos_pendientes,
        negocios_recientes=negocios_recientes,
        titulo="Panel de Administracion",
    )


# ============================================================
# GESTION DE NEGOCIOS (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/negocios")
@action.uses(AccionBase, "superadmin_negocios.html")
def superadmin_negocios():
    user = auth.get_user()
    if not es_superadmin(user):
        raise HTTP(403)

    pagina = int(request.query.get("pagina", 1) or 1)
    estado = request.query.get("estado", "")
    por_pagina = 20

    query = db.negocio.id > 0
    if estado == "activos":
        query &= (db.negocio.activo == True) & (db.negocio.aprobado == True)
    elif estado == "pendientes":
        query &= db.negocio.aprobado == False
    elif estado == "inactivos":
        query &= db.negocio.activo == False

    total = db(query).count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    offset = (pagina - 1) * por_pagina
    negocios_raw = db(query).select(orderby=~db.negocio.fecha_creacion,
                                    limitby=(offset, offset + por_pagina))

    negocio_ids = [n.id for n in negocios_raw]
    usuario_ids = [n.usuario_id for n in negocios_raw if n.usuario_id]

    emails = {}
    if usuario_ids:
        usuarios = db(db.auth_user.id.belongs(usuario_ids)).select()
        emails = {u.id: u.email for u in usuarios}

    conteo_prod = {}
    if negocio_ids:
        rows = db(db.producto.negocio_id.belongs(negocio_ids)).select(
            db.producto.negocio_id, db.producto.id.count(),
            groupby=db.producto.negocio_id,
        )
        conteo_prod = {r.producto.negocio_id: r[db.producto.id.count()] for r in rows}

    subs = {}
    if negocio_ids:
        subs_raw = db(db.suscripcion.negocio_id.belongs(negocio_ids)).select(
            orderby=~db.suscripcion.fecha_creacion
        )
        for s in subs_raw:
            if s.negocio_id not in subs:
                subs[s.negocio_id] = s

    estados_sus = {
        'activa':  ('badge-green', 'Activa'),
        'prueba':  ('badge-blue',  'Prueba'),
        'vencida': ('badge-red',   'Vencida'),
    }

    negocios = []
    for n in negocios_raw:
        if n.aprobado and n.activo:
            texto, clase = 'Activo', 'badge-green'
        elif not n.aprobado:
            texto, clase = 'Pendiente', 'badge-yellow'
        else:
            texto, clase = 'Inactivo', 'badge-red'

        s = subs.get(n.id)
        if s:
            stext, sclase = estados_sus.get(s.estado, ('badge-yellow', s.estado))
        else:
            stext, sclase = None, None

        negocios.append({
            'id': n.id, 'nombre': n.nombre, 'slug': n.slug, 'logo': n.logo,
            'telefono': n.telefono, 'provincia': n.provincia,
            'aprobado': n.aprobado, 'activo': n.activo,
            'propietario_email': emails.get(n.usuario_id, '-'),
            'cantidad_productos': conteo_prod.get(n.id, 0),
            'badge_negocio_texto': texto, 'badge_negocio_clase': clase,
            'suscripcion_estado_texto': stext, 'suscripcion_estado_clase': sclase,
        })

    return dict(
        total=total, negocios=negocios, estado_filtro=estado,
        pagina=pagina, total_paginas=total_paginas,
        titulo="Gestion de Negocios",
    )


@action("catalogo_cuba/superadmin/negocio/aprobar/<negocio_id:int>", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def superadmin_aprobar_negocio(negocio_id):
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    negocio = db.negocio[negocio_id]
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado")

    db(db.negocio.id == negocio_id).update(
        aprobado=True, activo=True, fecha_actualizacion=ahora_cuba(),
    )
    db.commit()
    return respuesta_json(exito=True, mensaje="Negocio aprobado correctamente")


@action("catalogo_cuba/superadmin/negocio/toggle/<negocio_id:int>", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def superadmin_toggle_negocio(negocio_id):
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    negocio = db.negocio[negocio_id]
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado")

    nuevo_estado = not negocio.activo
    db(db.negocio.id == negocio_id).update(
        activo=nuevo_estado, fecha_actualizacion=ahora_cuba(),
    )
    db.commit()
    return respuesta_json(exito=True,
                          mensaje="Negocio %s" % ('activado' if nuevo_estado else 'desactivado'))


# ============================================================
# GESTION DE USUARIOS (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/usuarios")
@action.uses(AccionBase, "superadmin_usuarios.html")
def superadmin_usuarios():
    user = auth.get_user()
    if not es_superadmin(user):
        raise HTTP(403)

    pagina = int(request.query.get("pagina", 1) or 1)
    rol = request.query.get("rol", "")
    por_pagina = 25

    # Filtramos por tag usando roles_tags si se especifica un rol
    if rol:
        usuarios_tagged = roles_tags.find(rol)
        ids = [u.id for u in usuarios_tagged] if usuarios_tagged else []
        query = db.auth_user.id.belongs(ids) if ids else (db.auth_user.id < 0)
    else:
        query = db.auth_user.id > 0

    total = db(query).count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    offset = (pagina - 1) * por_pagina
    usuarios_raw = db(query).select(orderby=~db.auth_user.fecha_registro,
                                    limitby=(offset, offset + por_pagina))

    usuario_ids = [u.id for u in usuarios_raw]
    negocio_slug_por_usuario = {}
    if usuario_ids:
        negocios = db(db.negocio.usuario_id.belongs(usuario_ids)).select(
            db.negocio.usuario_id, db.negocio.slug
        )
        for n in negocios:
            negocio_slug_por_usuario.setdefault(n.usuario_id, n.slug)

    usuarios = [{
        'id': u.id, 'email': u.email,
        'first_name': u.first_name, 'last_name': u.last_name,
        'roles': roles_tags.get(u.id) or [],
        'telefono': u.telefono,
        'activo': u.activo if u.activo is not None else True,
        'fecha_registro_texto': u.fecha_registro.strftime('%d/%m/%Y') if u.fecha_registro else '-',
        'negocio_slug': negocio_slug_por_usuario.get(u.id),
    } for u in usuarios_raw]

    return dict(
        total=total, usuarios=usuarios, rol_filtro=rol,
        pagina=pagina, total_paginas=total_paginas,
        titulo="Gestion de Usuarios",
    )


@action("catalogo_cuba/superadmin/usuario/cambiar-rol/<usuario_id:int>", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def superadmin_cambiar_rol(usuario_id):
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    nuevo_rol = request.forms.get("rol", "")
    if nuevo_rol not in ["superadmin", "comerciante", "visitante"]:
        return respuesta_json(exito=False, mensaje="Rol invalido")

    usuario = db.auth_user[usuario_id]
    if not usuario:
        return respuesta_json(exito=False, mensaje="Usuario no encontrado")

    # Reemplazar roles: quitar los anteriores de la lista permitida y asignar el nuevo
    for r in ["superadmin", "comerciante", "visitante"]:
        if r != nuevo_rol:
            try:
                roles_tags.remove(usuario_id, r)
            except Exception:
                pass
    asignar_rol(usuario_id, nuevo_rol)

    return respuesta_json(exito=True, mensaje="Rol actualizado")


# ============================================================
# GESTION DE SUSCRIPCIONES (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/suscripciones")
@action.uses(AccionBase, "superadmin_suscripciones.html")
def superadmin_suscripciones():
    user = auth.get_user()
    if not es_superadmin(user):
        raise HTTP(403)

    pagina = int(request.query.get("pagina", 1) or 1)
    estado = request.query.get("estado", "")
    por_pagina = 20

    query = db.suscripcion.id > 0
    if estado:
        query &= db.suscripcion.estado == estado

    total = db(query).count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    offset = (pagina - 1) * por_pagina
    sus_raw = db(query).select(orderby=~db.suscripcion.fecha_creacion,
                               limitby=(offset, offset + por_pagina))

    negocio_ids = [s.negocio_id for s in sus_raw if s.negocio_id]
    usuario_ids = [s.usuario_id for s in sus_raw if s.usuario_id]

    negocios = {}
    if negocio_ids:
        for n in db(db.negocio.id.belongs(negocio_ids)).select():
            negocios[n.id] = n.nombre
    usuarios = {}
    if usuario_ids:
        for u in db(db.auth_user.id.belongs(usuario_ids)).select():
            usuarios[u.id] = u.email

    estados_badge = {
        'activa':    ('badge-green',  'Activa'),
        'prueba':    ('badge-blue',   'Prueba'),
        'vencida':   ('badge-red',    'Vencida'),
        'pendiente': ('badge-yellow', 'Pendiente'),
    }
    metodos = {
        'transfermovil': '📱 Transfermovil',
        'presencial':    '💵 Presencial',
        'usdt':          '💎 USDT',
        'prueba':        '🎁 Gratis',
    }

    suscripciones = []
    for s in sus_raw:
        clase, texto = estados_badge.get(s.estado, ('badge', s.estado))
        suscripciones.append({
            'id': s.id,
            'nombre_negocio': negocios.get(s.negocio_id),
            'email_usuario': usuarios.get(s.usuario_id),
            'fecha_inicio_texto': s.fecha_inicio.strftime('%d/%m/%Y') if s.fecha_inicio else '-',
            'fecha_fin_texto': s.fecha_fin.strftime('%d/%m/%Y') if s.fecha_fin else '-',
            'estado_badge_texto': texto, 'estado_badge_clase': clase,
            'metodo_pago_texto': metodos.get(s.metodo_pago, s.metodo_pago or '-'),
            'monto_pagado_texto': '%.2f %s' % (s.monto_pagado or 0, s.moneda_pago or 'CUP'),
        })

    return dict(
        total=total, suscripciones=suscripciones, estado_filtro=estado,
        pagina=pagina, total_paginas=total_paginas,
        titulo="Gestion de Suscripciones",
    )


# ============================================================
# VALIDACION DE PAGOS (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/pagos")
@action.uses(AccionBase, "superadmin_pagos.html")
def superadmin_pagos():
    user = auth.get_user()
    if not es_superadmin(user):
        raise HTTP(403)

    pagina = int(request.query.get("pagina", 1) or 1)
    estado = request.query.get("estado", "pendiente")
    por_pagina = 25

    query = db.pago.id > 0
    if estado:
        query &= db.pago.estado == estado

    total = db(query).count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    offset = (pagina - 1) * por_pagina
    pagos_raw = db(query).select(orderby=~db.pago.fecha_solicitud,
                                 limitby=(offset, offset + por_pagina))

    negocio_ids = [p.negocio_id for p in pagos_raw if p.negocio_id]
    usuario_ids = [p.usuario_id for p in pagos_raw if p.usuario_id]

    negocios = {}
    if negocio_ids:
        for n in db(db.negocio.id.belongs(negocio_ids)).select():
            negocios[n.id] = n.nombre
    usuarios = {}
    if usuario_ids:
        for u in db(db.auth_user.id.belongs(usuario_ids)).select():
            usuarios[u.id] = u.email

    pagos = [_preparar_pago(p,
                            negocio_nombre=negocios.get(p.negocio_id),
                            usuario_email=usuarios.get(p.usuario_id))
             for p in pagos_raw]

    return dict(
        total=total, pagos=pagos, estado_filtro=estado,
        pagina=pagina, total_paginas=total_paginas,
        titulo="Validacion de Pagos",
    )


@action("catalogo_cuba/superadmin/pago/validar/<pago_id:int>", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def superadmin_validar_pago(pago_id):
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    pago = db.pago[pago_id]
    if not pago:
        return respuesta_json(exito=False, mensaje="Pago no encontrado")

    estado = request.forms.get("estado", "validado")
    notas = request.forms.get("notas", "")
    user = auth.get_user()

    db(db.pago.id == pago_id).update(
        estado=estado, fecha_validacion=ahora_cuba(),
        validado_por=user["id"] if user else None,
        notas_validacion=notas,
    )
    db.commit()

    if estado == "validado":
        suscripcion = db.suscripcion[pago.suscripcion_id]
        if suscripcion:
            base = max(suscripcion.fecha_fin, ahora_cuba().date()) if suscripcion.fecha_fin else ahora_cuba().date()
            nueva_fecha_fin = base + timedelta(days=30)
            db(db.suscripcion.id == pago.suscripcion_id).update(
                estado="activa", fecha_fin=nueva_fecha_fin,
                fecha_pago=ahora_cuba(),
                monto_pagado=pago.monto, moneda_pago=pago.moneda,
            )
            db.notificacion.insert(
                usuario_id=pago.usuario_id, tipo="pago_validado",
                titulo="Pago validado",
                mensaje="Su pago de %s %s ha sido validado. Su suscripcion esta activa hasta %s." % (
                    pago.monto, pago.moneda, nueva_fecha_fin.strftime('%d/%m/%Y')),
                fecha_creacion=ahora_cuba(),
            )
            db.commit()

    return respuesta_json(exito=True, mensaje="Pago %s correctamente" % estado)


# ============================================================
# CONFIGURACION GLOBAL (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/configuracion")
@action.uses(AccionBase, "superadmin_configuracion.html")
def superadmin_configuracion():
    user = auth.get_user()
    if not es_superadmin(user):
        raise HTTP(403)

    configuraciones_raw = db(db.configuracion.id > 0).select(orderby=db.configuracion.clave)
    configuraciones = [{
        'id': c.id, 'clave': c.clave, 'valor': c.valor,
        'descripcion': c.descripcion, 'tipo': c.tipo,
    } for c in configuraciones_raw]

    return dict(configuraciones=configuraciones, titulo="Configuracion Global")


@action("catalogo_cuba/superadmin/configuracion/guardar", method=["POST"])
@action.uses(db, session, auth.user, contexto_base)
def superadmin_guardar_configuracion():
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    try:
        clave = request.forms.get("clave")
        valor = request.forms.get("valor")
        tipo = request.forms.get("tipo", "string")
        descripcion = request.forms.get("descripcion", "")

        config = db(db.configuracion.clave == clave).select().first()
        if config:
            db(db.configuracion.id == config.id).update(
                valor=valor, fecha_actualizacion=ahora_cuba(),
            )
        else:
            db.configuracion.insert(
                clave=clave, valor=valor, tipo=tipo,
                descripcion=descripcion,
                fecha_actualizacion=ahora_cuba(),
            )
        db.commit()
        return respuesta_json(exito=True, mensaje="Configuracion guardada")
    except Exception as e:
        return respuesta_json(exito=False, mensaje="Error: %s" % str(e))


# ============================================================
# NOTIFICACIONES
# ============================================================

@action("catalogo_cuba/api/notificaciones")
@action.uses(db, session, auth.user)
def api_notificaciones():
    user = auth.get_user()
    if not user:
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    notifs = db(db.notificacion.usuario_id == user["id"]).select(
        orderby=~db.notificacion.fecha_creacion, limitby=(0, 20)
    )
    no_leidas = db(
        (db.notificacion.usuario_id == user["id"]) & (db.notificacion.leida == False)
    ).count()

    return respuesta_json(exito=True, datos={
        "notificaciones": [{
            "id": n.id, "tipo": n.tipo, "titulo": n.titulo,
            "mensaje": n.mensaje, "leida": n.leida,
            "fecha": formatear_fecha(n.fecha_creacion),
        } for n in notifs],
        "no_leidas": no_leidas,
    })


@action("catalogo_cuba/api/notificacion/leer/<notificacion_id:int>", method=["POST"])
@action.uses(db, session, auth.user)
def api_marcar_leida(notificacion_id):
    user = auth.get_user()
    if not user:
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)

    db(
        (db.notificacion.id == notificacion_id) &
        (db.notificacion.usuario_id == user["id"])
    ).update(leida=True, fecha_lectura=ahora_cuba())
    db.commit()
    return respuesta_json(exito=True, mensaje="Notificacion marcada como leida")


# ============================================================
# AUXILIARES
# ============================================================

def verificar_suscripcion_activa(negocio_id):
    s = db(db.suscripcion.negocio_id == negocio_id).select(
        orderby=~db.suscripcion.fecha_creacion, limitby=(0, 1)
    ).first()
    if not s:
        return False
    if s.estado in ["activa", "prueba"]:
        if s.fecha_fin and s.fecha_fin >= ahora_cuba().date():
            return True
    return False


# ============================================================
# STATIC FILES
# ============================================================

@action("catalogo_cuba/uploads/<filename:path>")
@action.uses()
def serve_uploads(filename):
    # Resolver rutas antes de abrir archivos y garantizar que permanezcan
    # dentro del directorio de uploads, incluso ante rutas manipuladas.
    raiz_uploads = os.path.realpath(settings.UPLOAD_FOLDER)
    ruta = os.path.realpath(os.path.join(raiz_uploads, filename))
    try:
        dentro_de_uploads = os.path.commonpath([raiz_uploads, ruta]) == raiz_uploads
    except ValueError:
        dentro_de_uploads = False
    if not dentro_de_uploads or not os.path.isfile(ruta):
        raise HTTP(404, "Archivo no encontrado")

    ext = os.path.splitext(filename)[1].lower()
    content_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")

    response.headers["Content-Type"] = content_type
    response.headers["Cache-Control"] = "public, max-age=86400"
    with open(ruta, "rb") as f:
        return f.read()