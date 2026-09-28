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
    if not negocio:
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
    if not user or not es_comerciante(user):
        raise HTTP(403)

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
def