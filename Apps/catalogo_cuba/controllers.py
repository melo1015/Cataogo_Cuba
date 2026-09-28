"""
Controladores - CatalogoCuba
Define todas las acciones/rutas de la aplicacion
"""
import os
import json
from datetime import datetime, timedelta
from py4web import action, request, response, redirect, URL, HTTP, abort
from py4web.utils.form import Form
from pydal.validators import *

from .common import (
    db, session, auth, translator,
    settings, respuesta_json, registrar_visita,
    guardar_imagen, optimizar_imagen, slugify,
    es_superadmin, es_comerciante, requiere_rol,
    ahora_cuba, formatear_fecha, formatear_fecha_corta
)

# ============================================================
# HELPERS
# ============================================================

def obtener_negocio_por_slug(slug):
    """Obtiene un negocio por su slug, verificando que este activo."""
    negocio = db(db.negocio.slug == slug)(db.negocio.activo == True)(db.negocio.aprobado == True).select().first()
    return negocio

def obtener_negocio_del_usuario():
    """Obtiene el negocio asociado al usuario actual."""
    user = auth.get_user()
    if not user:
        return None
    negocio = db(db.negocio.usuario_id == user["id"]).select().first()
    return negocio

def verificar_propietario_negocio(negocio_id):
    """Verifica que el usuario actual sea propietario del negocio."""
    user = auth.get_user()
    if not user:
        return False
    if es_superadmin():
        return True
    negocio = db(db.negocio.id == negocio_id).select().first()
    return negocio and negocio.usuario_id == user["id"]

def get_client_ip():
    """Obtiene la IP del cliente."""
    return request.environ.get("HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR", ""))

def serializar_producto(producto, negocio_slug=""):
    """Serializa un producto a diccionario para JSON."""
    categoria = None
    if producto.categoria_id:
        cat = db.categoria[producto.categoria_id]
        if cat:
            categoria = {"id": cat.id, "nombre": cat.nombre, "slug": cat.slug}
    
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "slug": producto.slug,
        "descripcion": producto.descripcion or "",
        "descripcion_corta": producto.descripcion_corta or "",
        "precio": str(producto.precio) if producto.precio else "0",
        "precio_anterior": str(producto.precio_anterior) if producto.precio_anterior else None,
        "moneda": producto.moneda or "CUP",
        "disponible": producto.disponible,
        "en_oferta": producto.en_oferta,
        "stock": producto.stock or 0,
        "sku": producto.sku or "",
        "categoria": categoria,
        "imagen_principal": f"/catalogo_cuba/uploads/{producto.imagen_principal}" if producto.imagen_principal else None,
        "destacado": producto.destacado,
        "tags": producto.tags or [],
        "peso": str(producto.peso) if producto.peso else None,
        "vistas": producto.vistas or 0,
        "negocio_slug": negocio_slug,
    }

def serializar_negocio(negocio):
    """Serializa un negocio a diccionario para JSON."""
    return {
        "id": negocio.id,
        "nombre": negocio.nombre,
        "slug": negocio.slug,
        "descripcion": negocio.descripcion or "",
        "logo": f"/catalogo_cuba/uploads/{negocio.logo}" if negocio.logo else None,
        "direccion": negocio.direccion or "",
        "telefono": negocio.telefono or "",
        "email": negocio.email or "",
        "whatsapp": negocio.whatsapp or "",
        "horario": negocio.horario or "",
        "provincia": negocio.provincia or "",
        "municipio": negocio.municipio or "",
        "color_tema": negocio.color_tema or "#2563eb",
        "moneda_principal": negocio.moneda_principal or "CUP",
        "mostrar_precios": negocio.mostrar_precios,
        "facebook": negocio.facebook or "",
        "instagram": negocio.instagram or "",
        "telegram": negocio.telegram or "",
    }

def paginar(query, pagina=1, page_size=None):
    """Pagina una consulta pyDAL."""
    if page_size is None:
        page_size = settings.PAGE_SIZE
    total = db(query).count()
    total_paginas = (total + page_size - 1) // page_size if total > 0 else 1
    pagina = max(1, min(pagina, total_paginas))
    offset = (pagina - 1) * page_size
    registros = db(query).select(limitby=(offset, offset + page_size))
    return {
        "registros": registros,
        "total": total,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "page_size": page_size,
    }

# ============================================================
# CONTEXTO COMUN PARA TEMPLATES
# ============================================================

def contexto_base():
    """Contexto base para todos los templates."""
    user = auth.get_user()
    return {
        "user": user,
        "es_superadmin": es_superadmin(),
        "es_comerciante": es_comerciante(),
        "URL": URL,
        "ahora": ahora_cuba(),
    }

# ============================================================
# RUTAS PUBLICAS - CATALOGO
# ============================================================

@action("catalogo_cuba")
@action.uses(auth, "catalogo_home.html")
def catalogo_home():
    """Pagina principal - lista de negocios activos."""
    # Obtener negocios destacados/aprobados
    negocios = db(db.negocio.activo == True)(db.negocio.aprobado == True).select(
        orderby=~db.negocio.fecha_creacion,
        limitby=(0, 20)
    )
    
    return dict(
        **contexto_base(),
        negocios=negocios,
        titulo="CatalogoCuba - Directorio de Negocios",
    )

@action("catalogo_cuba/negocio/<slug>")
@action.uses(auth, "catalogo_negocio.html")
def catalogo_negocio(slug):
    """Pagina publica de un negocio con su catalogo."""
    negocio = obtener_negocio_por_slug(slug)
    if not negocio:
        raise HTTP(404, "Negocio no encontrado")
    
    # Registrar visita
    registrar_visita(negocio_id=negocio.id, ip=get_client_ip(),
                    user_agent=request.environ.get("HTTP_USER_AGENT", ""))
    
    # Obtener categorias del negocio
    categorias = db(db.categoria.negocio_id == negocio.id)(db.categoria.activa == True).select(
        orderby=db.categoria.orden
    )
    
    # Obtener productos destacados
    destacados = db(db.producto.negocio_id == negocio.id)(
        db.producto.disponible == True)(db.producto.destacado == True).select(
        orderby=~db.producto.fecha_creacion,
        limitby=(0, 8)
    )
    
    # Obtener todos los productos disponibles
    productos = db(db.producto.negocio_id == negocio.id)(
        db.producto.disponible == True).select(
        orderby=~db.producto.fecha_creacion,
        limitby=(0, settings.PAGE_SIZE)
    )
    
    # Verificar si la suscripcion esta activa
    suscripcion_activa = verificar_suscripcion_activa(negocio.id)
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        categorias=categorias,
        destacados=destacados,
        productos=productos,
        suscripcion_activa=suscripcion_activa,
        titulo=f"{negocio.nombre} - Catalogo",
    )

@action("catalogo_cuba/negocio/<slug>/categoria/<categoria_slug>")
@action.uses(auth, "catalogo_categoria.html")
def catalogo_por_categoria(slug, categoria_slug):
    """Productos de un negocio filtrados por categoria."""
    negocio = obtener_negocio_por_slug(slug)
    if not negocio:
        raise HTTP(404, "Negocio no encontrado")
    
    categoria = db(db.categoria.negocio_id == negocio.id)(
        db.categoria.slug == categoria_slug).select().first()
    
    if not categoria:
        raise HTTP(404, "Categoria no encontrada")
    
    # Productos de esta categoria
    productos = db(db.producto.negocio_id == negocio.id)(
        db.producto.categoria_id == categoria.id)(
        db.producto.disponible == True).select(
        orderby=~db.producto.fecha_creacion
    )
    
    # Todas las categorias para el menu
    categorias = db(db.categoria.negocio_id == negocio.id)(db.categoria.activa == True).select(
        orderby=db.categoria.orden
    )
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        categoria=categoria,
        categorias=categorias,
        productos=productos,
        titulo=f"{categoria.nombre} - {negocio.nombre}",
    )

@action("catalogo_cuba/negocio/<slug>/producto/<producto_slug>")
@action.uses(auth, "catalogo_producto.html")
def catalogo_producto_detalle(slug, producto_slug):
    """Pagina de detalle de un producto."""
    negocio = obtener_negocio_por_slug(slug)
    if not negocio:
        raise HTTP(404, "Negocio no encontrado")
    
    producto = db(db.producto.negocio_id == negocio.id)(
        db.producto.slug == producto_slug).select().first()
    
    if not producto:
        raise HTTP(404, "Producto no encontrado")
    
    # Incrementar contador de vistas
    db(db.producto.id == producto.id).update(vistas=(producto.vistas or 0) + 1)
    db.commit()
    
    # Registrar visita
    registrar_visita(negocio_id=negocio.id, producto_id=producto.id,
                    ip=get_client_ip(),
                    user_agent=request.environ.get("HTTP_USER_AGENT", ""))
    
    # Productos relacionados (misma categoria)
    relacionados = []
    if producto.categoria_id:
        relacionados = db(db.producto.categoria_id == producto.categoria_id)(
            db.producto.id != producto.id)(
            db.producto.disponible == True).select(
            orderby=~db.producto.vistas,
            limitby=(0, 4)
        )
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        producto=producto,
        relacionados=relacionados,
        titulo=f"{producto.nombre} - {negocio.nombre}",
    )

# ============================================================
# BUSQUEDA PUBLICA
# ============================================================

@action("catalogo_cuba/buscar")
@action.uses(auth, "catalogo_busqueda.html")
def catalogo_buscar():
    """Busqueda publica de productos y negocios."""
    query = request.params.get("q", "").strip()
    tipo = request.params.get("tipo", "productos")
    
    resultados = []
    negocios = []
    
    if query:
        if tipo == "productos":
            resultados = db(db.producto.nombre.contains(query, case_sensitive=False))(
                db.producto.disponible == True)(
                db.producto.negocio_id == db.negocio.id)(
                db.negocio.activo == True)(
                db.negocio.aprobado == True
            ).select(
                db.producto.ALL, db.negocio.slug,
                orderby=~db.producto.fecha_creacion,
                limitby=(0, 50)
            )
        elif tipo == "negocios":
            negocios = db(db.negocio.nombre.contains(query, case_sensitive=False))(
                db.negocio.activo == True)(
                db.negocio.aprobado == True
            ).select(orderby=db.negocio.nombre)
    
    return dict(
        **contexto_base(),
        query=query,
        tipo=tipo,
        resultados=resultados,
        negocios=negocios,
        titulo=f"Buscar: {query}" if query else "Buscar",
    )

# ============================================================
# API PUBLICA - PARA MODO OFFLINE
# ============================================================

@action("catalogo_cuba/api/negocio/<slug>/catalogo")
@action.uses()
def api_catalogo_negocio(slug):
    """
    API publica que retorna el catalogo completo de un negocio en JSON.
    Usado por el Service Worker para cachear el catalogo offline.
    """
    negocio = obtener_negocio_por_slug(slug)
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado", codigo=404)
    
    # Verificar suscripcion activa
    if not verificar_suscripcion_activa(negocio.id):
        return respuesta_json(exito=False, mensaje="Catalogo no disponible temporalmente", codigo=403)
    
    # Obtener categorias
    categorias_raw = db(db.categoria.negocio_id == negocio.id)(db.categoria.activa == True).select(
        orderby=db.categoria.orden
    )
    categorias = []
    for c in categorias_raw:
        categorias.append({
            "id": c.id, "nombre": c.nombre, "slug": c.slug,
            "descripcion": c.descripcion or "",
            "imagen": f"/catalogo_cuba/uploads/{c.imagen}" if c.imagen else None,
        })
    
    # Obtener productos
    productos_raw = db(db.producto.negocio_id == negocio.id)(
        db.producto.disponible == True).select(orderby=~db.producto.fecha_creacion)
    productos = [serializar_producto(p, negocio.slug) for p in productos_raw]
    
    # Info del negocio serializada
    negocio_json = serializar_negocio(negocio)
    
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["Content-Type"] = "application/json"
    
    return json.dumps({
        "exito": True,
        "negocio": negocio_json,
        "categorias": categorias,
        "productos": productos,
        "total_productos": len(productos),
        "fecha_actualizacion": formatear_fecha(ahora_cuba()),
    })

@action("catalogo_cuba/api/negocio/<slug>/producto/<producto_slug>")
@action.uses()
def api_producto_detalle(slug, producto_slug):
    """API para obtener detalle de un producto especifico."""
    negocio = obtener_negocio_por_slug(slug)
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado", codigo=404)
    
    producto = db(db.producto.negocio_id == negocio.id)(
        db.producto.slug == producto_slug).select().first()
    
    if not producto:
        return respuesta_json(exito=False, mensaje="Producto no encontrado", codigo=404)
    
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["Content-Type"] = "application/json"
    
    return json.dumps({
        "exito": True,
        "producto": serializar_producto(producto, negocio.slug),
    })

# ============================================================
# PANEL DE COMERCIANTE - DASHBOARD
# ============================================================

@action("catalogo_cuba/admin")
@action.uses(auth, session, "admin_dashboard.html")
def admin_dashboard():
    """Dashboard principal del comerciante."""
    user = auth.get_user()
    if not user:
        return redirect(URL("auth/login"))
    
    if es_superadmin():
        return redirect(URL("catalogo_cuba/superadmin"))
    
    if not es_comerciante():
        raise HTTP(403, "Acceso denegado")
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        # Redirigir a crear negocio
        return redirect(URL("catalogo_cuba/admin/negocio/nuevo"))
    
    # Estadisticas basicas
    total_productos = db(db.producto.negocio_id == negocio.id).count()
    productos_activos = db(db.producto.negocio_id == negocio.id)(
        db.producto.disponible == True).count()
    total_categorias = db(db.categoria.negocio_id == negocio.id).count()
    
    # Visitas recientes (ultimos 7 dias)
    hace_7_dias = ahora_cuba() - timedelta(days=7)
    visitas_recientes = db(db.visita.negocio_id == negocio.id)(
        db.visita.fecha >= hace_7_dias).count()
    
    # Productos mas vistos
    mas_vistos = db(db.producto.negocio_id == negocio.id).select(
        orderby=~db.producto.vistas,
        limitby=(0, 5)
    )
    
    # Estado de suscripcion
    suscripcion = db(db.suscripcion.negocio_id == negocio.id).select(
        orderby=~db.suscripcion.fecha_creacion,
        limitby=(0, 1)
    ).first()
    
    # Productos con bajo stock
    bajo_stock = db(db.producto.negocio_id == negocio.id)(
        db.producto.stock <= 5)(
        db.producto.disponible == True).select()
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        total_productos=total_productos,
        productos_activos=productos_activos,
        total_categorias=total_categorias,
        visitas_recientes=visitas_recientes,
        mas_vistos=mas_vistos,
        suscripcion=suscripcion,
        bajo_stock=bajo_stock,
        titulo=f"Panel - {negocio.nombre}",
    )

# ============================================================
# CRUD NEGOCIO (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/negocio/nuevo")
@action.uses(auth, session, db, "admin_negocio_form.html")
def admin_negocio_nuevo():
    """Crear nuevo negocio."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    # Verificar que no tenga ya un negocio
    existe = db(db.negocio.usuario_id == user["id"]).count()
    if existe > 0:
        return redirect(URL("catalogo_cuba/admin"))
    
    form = Form(
        db.negocio,
        fields=[
            "nombre", "descripcion", "direccion", "telefono",
            "email", "whatsapp", "horario", "provincia", "municipio",
            "color_tema", "moneda_principal", "mostrar_precios",
            "facebook", "instagram", "telegram", "meta_descripcion",
        ],
        deletable=False,
        formstyle=FormStyleDefault,
    )
    
    if form.accepted:
        # Asignar usuario y generar slug
        negocio_id = form.vars.get("id")
        nombre = form.vars.get("nombre", "")
        slug = slugify(nombre)
        
        # Verificar unicidad del slug
        contador = 1
        slug_original = slug
        while db(db.negocio.slug == slug).count() > 0:
            slug = f"{slug_original}-{contador}"
            contador += 1
        
        db(db.negocio.id == negocio_id).update(
            usuario_id=user["id"],
            slug=slug,
            fecha_creacion=ahora_cuba(),
            fecha_actualizacion=ahora_cuba(),
            activo=True,
            aprobado=False,  # Requiere aprobacion del admin
        )
        db.commit()
        
        # Crear suscripcion de prueba
        db.suscripcion.insert(
            negocio_id=negocio_id,
            usuario_id=user["id"],
            fecha_inicio=ahora_cuba().date(),
            fecha_fin=(ahora_cuba() + timedelta(days=settings.DIAS_PRUEBA_GRATIS)).date(),
            estado="prueba",
            metodo_pago="prueba",
            monto_pagado=0,
            dias_prueba=settings.DIAS_PRUEBA_GRATIS,
            fecha_creacion=ahora_cuba(),
        )
        db.commit()
        
        return redirect(URL("catalogo_cuba/admin"))
    
    return dict(
        **contexto_base(),
        form=form,
        titulo="Crear mi negocio",
        modo="crear",
    )

@action("catalogo_cuba/admin/negocio/editar")
@action.uses(auth, session, db, "admin_negocio_form.html")
def admin_negocio_editar():
    """Editar negocio del comerciante."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin/negocio/nuevo"))
    
    form = Form(
        db.negocio,
        record=negocio,
        fields=[
            "nombre", "descripcion", "logo", "direccion", "telefono",
            "email", "whatsapp", "horario", "provincia", "municipio",
            "color_tema", "moneda_principal", "mostrar_precios",
            "facebook", "instagram", "telegram", "meta_descripcion",
        ],
        deletable=False,
        formstyle=FormStyleDefault,
    )
    
    if form.accepted:
        db(db.negocio.id == negocio.id).update(
            fecha_actualizacion=ahora_cuba(),
            slug=slugify(form.vars.get("nombre", negocio.nombre)),
        )
        db.commit()
        return redirect(URL("catalogo_cuba/admin"))
    
    return dict(
        **contexto_base(),
        form=form,
        negocio=negocio,
        titulo="Editar mi negocio",
        modo="editar",
    )

# ============================================================
# CRUD PRODUCTOS (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/productos")
@action.uses(auth, session, db, "admin_productos.html")
def admin_productos():
    """Listado de productos del comerciante."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin/negocio/nuevo"))
    
    # Paginacion
    pagina = int(request.params.get("pagina", 1))
    filtro_categoria = request.params.get("categoria", "")
    filtro_nombre = request.params.get("q", "")
    
    query = db.producto.negocio_id == negocio.id
    if filtro_categoria:
        query &= db.producto.categoria_id == int(filtro_categoria)
    if filtro_nombre:
        query &= db.producto.nombre.contains(filtro_nombre, case_sensitive=False)
    
    resultado = paginar(query, pagina)
    
    # Categorias para filtro
    categorias = db(db.categoria.negocio_id == negocio.id)(db.categoria.activa == True).select(
        orderby=db.categoria.orden
    )
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        productos=resultado["registros"],
        total=resultado["total"],
        pagina=resultado["pagina"],
        total_paginas=resultado["total_paginas"],
        categorias=categorias,
        filtro_categoria=filtro_categoria,
        filtro_nombre=filtro_nombre,
        titulo="Mis productos",
    )

@action("catalogo_cuba/admin/producto/nuevo")
@action.uses(auth, session, db, "admin_producto_form.html")
def admin_producto_nuevo():
    """Crear nuevo producto."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin"))
    
    # Solo categorias del negocio
    db.producto.categoria_id.requires = IS_EMPTY_OR(
        IS_IN_DB(db(db.categoria.negocio_id == negocio.id), "categoria.id", "%(nombre)s")
    )
    db.producto.negocio_id.default = negocio.id
    db.producto.negocio_id.writable = False
    db.producto.negocio_id.readable = False
    
    form = Form(
        db.producto,
        fields=[
            "nombre", "descripcion", "descripcion_corta", "precio",
            "precio_anterior", "moneda", "disponible", "en_oferta",
            "stock", "sku", "categoria_id", "imagen_principal",
            "destacado", "tags", "peso", "meta_keywords",
        ],
        deletable=False,
        formstyle=FormStyleDefault,
    )
    
    if form.accepted:
        producto_id = form.vars.get("id")
        nombre = form.vars.get("nombre", "")
        slug = slugify(nombre)
        
        # Verificar unicidad del slug dentro del negocio
        contador = 1
        slug_original = slug
        while db(db.producto.negocio_id == negocio.id)(db.producto.slug == slug).count() > 0:
            slug = f"{slug_original}-{contador}"
            contador += 1
        
        # Manejar upload de imagen
        imagen = None
        if "imagen_principal" in request.files:
            archivo = request.files["imagen_principal"].file
            imagen = guardar_imagen(archivo, f"productos/{negocio.id}")
        
        db(db.producto.id == producto_id).update(
            slug=slug,
            negocio_id=negocio.id,
            imagen_principal=imagen,
            fecha_creacion=ahora_cuba(),
            fecha_actualizacion=ahora_cuba(),
        )
        db.commit()
        
        return redirect(URL("catalogo_cuba/admin/productos"))
    
    return dict(
        **contexto_base(),
        form=form,
        negocio=negocio,
        titulo="Nuevo producto",
        modo="crear",
    )

@action("catalogo_cuba/admin/producto/editar/<producto_id:int>")
@action.uses(auth, session, db, "admin_producto_form.html")
def admin_producto_editar(producto_id):
    """Editar producto existente."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        raise HTTP(403)
    
    producto = db(db.producto.id == producto_id)(
        db.producto.negocio_id == negocio.id).select().first()
    
    if not producto:
        raise HTTP(404)
    
    # Solo categorias del negocio
    db.producto.categoria_id.requires = IS_EMPTY_OR(
        IS_IN_DB(db(db.categoria.negocio_id == negocio.id), "categoria.id", "%(nombre)s")
    )
    
    form = Form(
        db.producto,
        record=producto,
        fields=[
            "nombre", "descripcion", "descripcion_corta", "precio",
            "precio_anterior", "moneda", "disponible", "en_oferta",
            "stock", "sku", "categoria_id", "imagen_principal",
            "destacado", "tags", "peso", "meta_keywords",
        ],
        deletable=True,
        formstyle=FormStyleDefault,
    )
    
    if form.accepted:
        # Manejar upload de imagen nueva
        imagen = producto.imagen_principal
        if "imagen_principal" in request.files and request.files["imagen_principal"].file:
            archivo = request.files["imagen_principal"].file
            nueva_imagen = guardar_imagen(archivo, f"productos/{negocio.id}")
            if nueva_imagen:
                imagen = nueva_imagen
        
        db(db.producto.id == producto_id).update(
            slug=slugify(form.vars.get("nombre", producto.nombre)),
            imagen_principal=imagen,
            fecha_actualizacion=ahora_cuba(),
        )
        db.commit()
        return redirect(URL("catalogo_cuba/admin/productos"))
    
    return dict(
        **contexto_base(),
        form=form,
        negocio=negocio,
        producto=producto,
        titulo=f"Editar: {producto.nombre}",
        modo="editar",
    )

# ============================================================
# CRUD CATEGORIAS (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/categorias")
@action.uses(auth, session, db, "admin_categorias.html")
def admin_categorias():
    """Listado de categorias del comerciante."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin"))
    
    categorias = db(db.categoria.negocio_id == negocio.id).select(
        orderby=db.categoria.orden
    )
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        categorias=categorias,
        titulo="Mis categorias",
    )

@action("catalogo_cuba/admin/categoria/nueva")
@action.uses(auth, session, db, "admin_categoria_form.html")
def admin_categoria_nueva():
    """Crear nueva categoria."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin"))
    
    db.categoria.negocio_id.default = negocio.id
    db.categoria.negocio_id.writable = False
    db.categoria.negocio_id.readable = False
    
    form = Form(
        db.categoria,
        fields=["nombre", "descripcion", "imagen", "orden", "activa"],
        deletable=False,
        formstyle=FormStyleDefault,
    )
    
    if form.accepted:
        cat_id = form.vars.get("id")
        nombre = form.vars.get("nombre", "")
        db(db.categoria.id == cat_id).update(
            slug=slugify(nombre),
            negocio_id=negocio.id,
            fecha_creacion=ahora_cuba(),
        )
        db.commit()
        return redirect(URL("catalogo_cuba/admin/categorias"))
    
    return dict(
        **contexto_base(),
        form=form,
        negocio=negocio,
        titulo="Nueva categoria",
        modo="crear",
    )

@action("catalogo_cuba/admin/categoria/editar/<categoria_id:int>")
@action.uses(auth, session, db, "admin_categoria_form.html")
def admin_categoria_editar(categoria_id):
    """Editar categoria."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        raise HTTP(403)
    
    categoria = db(db.categoria.id == categoria_id)(
        db.categoria.negocio_id == negocio.id).select().first()
    
    if not categoria:
        raise HTTP(404)
    
    form = Form(
        db.categoria,
        record=categoria,
        fields=["nombre", "descripcion", "imagen", "orden", "activa"],
        deletable=True,
        formstyle=FormStyleDefault,
    )
    
    if form.accepted:
        if not form.deleted:
            db(db.categoria.id == categoria_id).update(
                slug=slugify(form.vars.get("nombre", categoria.nombre)),
            )
            db.commit()
        return redirect(URL("catalogo_cuba/admin/categorias"))
    
    return dict(
        **contexto_base(),
        form=form,
        negocio=negocio,
        categoria=categoria,
        titulo=f"Editar: {categoria.nombre}",
        modo="editar",
    )

# ============================================================
# INVENTARIO (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/inventario")
@action.uses(auth, session, db, "admin_inventario.html")
def admin_inventario():
    """Panel de inventario del comerciante."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin"))
    
    # Productos ordenados por stock (los de menor stock primero)
    productos = db(db.producto.negocio_id == negocio.id).select(
        orderby=db.producto.stock
    )
    
    # Estadisticas
    total_productos = len(productos)
    productos_agotados = sum(1 for p in productos if p.stock == 0)
    bajo_stock = sum(1 for p in productos if 0 < p.stock <= 5)
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        productos=productos,
        total_productos=total_productos,
        productos_agotados=productos_agotados,
        bajo_stock=bajo_stock,
        titulo="Inventario",
    )

@action("catalogo_cuba/api/inventario/actualizar", method=["POST"])
@action.uses(auth, session, db)
def api_actualizar_stock():
    """API para actualizar stock de un producto (AJAX)."""
    user = auth.get_user()
    if not user or not es_comerciante():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    try:
        data = request.json
        producto_id = data.get("producto_id")
        nuevo_stock = data.get("stock")
        
        negocio = obtener_negocio_del_usuario()
        if not negocio:
            return respuesta_json(exito=False, mensaje="Negocio no encontrado")
        
        producto = db(db.producto.id == producto_id)(
            db.producto.negocio_id == negocio.id).select().first()
        
        if not producto:
            return respuesta_json(exito=False, mensaje="Producto no encontrado")
        
        db(db.producto.id == producto_id).update(
            stock=int(nuevo_stock),
            fecha_actualizacion=ahora_cuba(),
        )
        db.commit()
        
        return respuesta_json(exito=True, mensaje="Stock actualizado")
    
    except Exception as e:
        return respuesta_json(exito=False, mensaje=f"Error: {str(e)}")

# ============================================================
# SUSCRIPCIONES Y PAGOS (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/suscripcion")
@action.uses(auth, session, db, "admin_suscripcion.html")
def admin_suscripcion():
    """Panel de suscripcion del comerciante."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin"))
    
    # Suscripcion actual
    suscripcion_actual = db(db.suscripcion.negocio_id == negocio.id).select(
        orderby=~db.suscripcion.fecha_creacion,
        limitby=(0, 1)
    ).first()
    
    # Historial de pagos
    pagos = db(db.pago.negocio_id == negocio.id).select(
        orderby=~db.pago.fecha_solicitud
    )
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        suscripcion=suscripcion_actual,
        pagos=pagos,
        costo_cup=settings.COSTO_SUSCRIPCION_MENSUAL_CUP,
        costo_usdt=settings.COSTO_SUSCRIPCION_MENSUAL_USDT,
        titulo="Mi suscripcion",
    )

@action("catalogo_cuba/admin/pago/realizar", method=["POST"])
@action.uses(auth, session, db)
def admin_realizar_pago():
    """Registrar un nuevo pago."""
    user = auth.get_user()
    if not user or not es_comerciante():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    try:
        negocio = obtener_negocio_del_usuario()
        if not negocio:
            return respuesta_json(exito=False, mensaje="Negocio no encontrado")
        
        metodo = request.POST.get("metodo_pago")
        monto = request.POST.get("monto")
        moneda = request.POST.get("moneda", "CUP")
        referencia = request.POST.get("referencia", "")
        
        # Obtener o crear suscripcion
        suscripcion = db(db.suscripcion.negocio_id == negocio.id)(
            db.suscripcion.estado.belongs(["activa", "prueba", "pendiente", "vencida"])).select(
            orderby=~db.suscripcion.fecha_creacion,
            limitby=(0, 1)
        ).first()
        
        if not suscripcion:
            # Crear nueva suscripcion
            suscripcion_id = db.suscripcion.insert(
                negocio_id=negocio.id,
                usuario_id=user["id"],
                fecha_inicio=ahora_cuba().date(),
                fecha_fin=(ahora_cuba() + timedelta(days=30)).date(),
                estado="pendiente",
                metodo_pago=metodo,
                fecha_creacion=ahora_cuba(),
            )
        else:
            suscripcion_id = suscripcion.id
            # Actualizar estado
            db(db.suscripcion.id == suscripcion_id).update(
                estado="pendiente",
                metodo_pago=metodo,
            )
        
        db.commit()
        
        # Crear registro de pago
        pago_id = db.pago.insert(
            suscripcion_id=suscripcion_id,
            negocio_id=negocio.id,
            usuario_id=user["id"],
            monto=float(monto),
            moneda=moneda,
            metodo_pago=metodo,
            estado="pendiente",
            referencia=referencia,
            fecha_solicitud=ahora_cuba(),
        )
        db.commit()
        
        return respuesta_json(exito=True, mensaje="Pago registrado correctamente. Pendiente de validacion.",
                            datos={"pago_id": pago_id})
    
    except Exception as e:
        return respuesta_json(exito=False, mensaje=f"Error: {str(e)}")

# ============================================================
# ESTADISTICAS (COMERCIANTE)
# ============================================================

@action("catalogo_cuba/admin/estadisticas")
@action.uses(auth, session, db, "admin_estadisticas.html")
def admin_estadisticas():
    """Estadisticas del negocio."""
    user = auth.get_user()
    if not user or not es_comerciante():
        raise HTTP(403)
    
    negocio = obtener_negocio_del_usuario()
    if not negocio:
        return redirect(URL("catalogo_cuba/admin"))
    
    # Datos para graficos
    # Visitas por dia (ultimos 30 dias)
    desde = ahora_cuba() - timedelta(days=30)
    visitas = db(db.visita.negocio_id == negocio.id)(
        db.visita.fecha >= desde).select(orderby=db.visita.fecha)
    
    # Productos mas vistos
    top_productos = db(db.producto.negocio_id == negocio.id).select(
        orderby=~db.producto.vistas,
        limitby=(0, 10)
    )
    
    # Totales
    total_visitas = db(db.visita.negocio_id == negocio.id).count()
    total_productos = db(db.producto.negocio_id == negocio.id).count()
    
    return dict(
        **contexto_base(),
        negocio=negocio,
        visitas=visitas,
        top_productos=top_productos,
        total_visitas=total_visitas,
        total_productos=total_productos,
        titulo="Estadisticas",
    )

# ============================================================
# PANEL SUPERADMIN
# ============================================================

@action("catalogo_cuba/superadmin")
@action.uses(auth, session, db, "superadmin_dashboard.html")
def superadmin_dashboard():
    """Dashboard del superadministrador."""
    if not es_superadmin():
        raise HTTP(403, "Acceso restringido a superadministradores")
    
    # Estadisticas generales
    total_negocios = db(db.negocio.id > 0).count()
    negocios_activos = db(db.negocio.activo == True)(db.negocio.aprobado == True).count()
    negocios_pendientes = db(db.negocio.aprobado == False).count()
    total_usuarios = db(db.auth_user.id > 0).count()
    total_productos = db(db.producto.id > 0).count()
    
    # Suscripciones
    suscripciones_activas = db(db.suscripcion.estado == "activa").count()
    suscripciones_vencidas = db(db.suscripcion.estado == "vencida").count()
    suscripciones_prueba = db(db.suscripcion.estado == "prueba").count()
    
    # Pagos pendientes
    pagos_pendientes = db(db.pago.estado == "pendiente").count()
    
    # Negocios recientes
    negocios_recientes = db(db.negocio.id > 0).select(
        orderby=~db.negocio.fecha_creacion,
        limitby=(0, 10)
    )
    
    return dict(
        **contexto_base(),
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
@action.uses(auth, session, db, "superadmin_negocios.html")
def superadmin_negocios():
    """Listado de todos los negocios."""
    if not es_superadmin():
        raise HTTP(403)
    
    pagina = int(request.params.get("pagina", 1))
    estado = request.params.get("estado", "")
    
    query = db.negocio.id > 0
    if estado == "activos":
        query = (db.negocio.activo == True) & (db.negocio.aprobado == True)
    elif estado == "pendientes":
        query = db.negocio.aprobado == False
    elif estado == "inactivos":
        query = db.negocio.activo == False
    
    resultado = paginar(query, pagina, page_size=20)
    
    return dict(
        **contexto_base(),
        negocios=resultado["registros"],
        total=resultado["total"],
        pagina=resultado["pagina"],
        total_paginas=resultado["total_paginas"],
        estado_filtro=estado,
        titulo="Gestion de Negocios",
    )

@action("catalogo_cuba/superadmin/negocio/aprobar/<negocio_id:int>", method=["POST"])
@action.uses(auth, session, db)
def superadmin_aprobar_negocio(negocio_id):
    """Aprobar un negocio pendiente."""
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    negocio = db.negocio[negocio_id]
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado")
    
    db(db.negocio.id == negocio_id).update(
        aprobado=True,
        activo=True,
        fecha_actualizacion=ahora_cuba(),
    )
    db.commit()
    
    return respuesta_json(exito=True, mensaje="Negocio aprobado correctamente")

@action("catalogo_cuba/superadmin/negocio/toggle/<negocio_id:int>", method=["POST"])
@action.uses(auth, session, db)
def superadmin_toggle_negocio(negocio_id):
    """Activar/desactivar un negocio."""
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    negocio = db.negocio[negocio_id]
    if not negocio:
        return respuesta_json(exito=False, mensaje="Negocio no encontrado")
    
    nuevo_estado = not negocio.activo
    db(db.negocio.id == negocio_id).update(
        activo=nuevo_estado,
        fecha_actualizacion=ahora_cuba(),
    )
    db.commit()
    
    return respuesta_json(exito=True, mensaje=f"Negocio {'activado' if nuevo_estado else 'desactivado'}")

# ============================================================
# GESTION DE USUARIOS (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/usuarios")
@action.uses(auth, session, db, "superadmin_usuarios.html")
def superadmin_usuarios():
    """Listado de usuarios."""
    if not es_superadmin():
        raise HTTP(403)
    
    pagina = int(request.params.get("pagina", 1))
    rol = request.params.get("rol", "")
    
    query = db.auth_user.id > 0
    if rol:
        query = db.auth_user.rol == rol
    
    resultado = paginar(query, pagina, page_size=25)
    
    return dict(
        **contexto_base(),
        usuarios=resultado["registros"],
        total=resultado["total"],
        pagina=resultado["pagina"],
        total_paginas=resultado["total_paginas"],
        rol_filtro=rol,
        titulo="Gestion de Usuarios",
    )

@action("catalogo_cuba/superadmin/usuario/cambiar-rol/<usuario_id:int>", method=["POST"])
@action.uses(auth, session, db)
def superadmin_cambiar_rol(usuario_id):
    """Cambiar rol de un usuario."""
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    nuevo_rol = request.POST.get("rol", "")
    if nuevo_rol not in ["superadmin", "comerciante", "visitante"]:
        return respuesta_json(exito=False, mensaje="Rol invalido")
    
    usuario = db.auth_user[usuario_id]
    if not usuario:
        return respuesta_json(exito=False, mensaje="Usuario no encontrado")
    
    db(db.auth_user.id == usuario_id).update(rol=nuevo_rol)
    db.commit()
    
    return respuesta_json(exito=True, mensaje="Rol actualizado")

# ============================================================
# GESTION DE SUSCRIPCIONES (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/suscripciones")
@action.uses(auth, session, db, "superadmin_suscripciones.html")
def superadmin_suscripciones():
    """Gestion de suscripciones."""
    if not es_superadmin():
        raise HTTP(403)
    
    pagina = int(request.params.get("pagina", 1))
    estado = request.params.get("estado", "")
    
    query = db.suscripcion.id > 0
    if estado:
        query = db.suscripcion.estado == estado
    
    resultado = paginar(query, pagina, page_size=20)
    
    return dict(
        **contexto_base(),
        suscripciones=resultado["registros"],
        total=resultado["total"],
        pagina=resultado["pagina"],
        total_paginas=resultado["total_paginas"],
        estado_filtro=estado,
        titulo="Gestion de Suscripciones",
    )

# ============================================================
# VALIDACION DE PAGOS (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/pagos")
@action.uses(auth, session, db, "superadmin_pagos.html")
def superadmin_pagos():
    """Listado de pagos para validacion."""
    if not es_superadmin():
        raise HTTP(403)
    
    pagina = int(request.params.get("pagina", 1))
    estado = request.params.get("estado", "pendiente")
    
    query = db.pago.id > 0
    if estado:
        query = db.pago.estado == estado
    
    resultado = paginar(query, pagina, page_size=25)
    
    return dict(
        **contexto_base(),
        pagos=resultado["registros"],
        total=resultado["total"],
        pagina=resultado["pagina"],
        total_paginas=resultado["total_paginas"],
        estado_filtro=estado,
        titulo="Validacion de Pagos",
    )

@action("catalogo_cuba/superadmin/pago/validar/<pago_id:int>", method=["POST"])
@action.uses(auth, session, db)
def superadmin_validar_pago(pago_id):
    """Validar un pago manualmente."""
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    pago = db.pago[pago_id]
    if not pago:
        return respuesta_json(exito=False, mensaje="Pago no encontrado")
    
    estado = request.POST.get("estado", "validado")
    notas = request.POST.get("notas", "")
    
    user = auth.get_user()
    
    db(db.pago.id == pago_id).update(
        estado=estado,
        fecha_validacion=ahora_cuba(),
        validado_por=user["id"] if user else None,
        notas_validacion=notas,
    )
    db.commit()
    
    # Si el pago se valida, actualizar la suscripcion
    if estado == "validado":
        suscripcion = db.suscripcion[pago.suscripcion_id]
        if suscripcion:
            nueva_fecha_fin = max(
                suscripcion.fecha_fin,
                ahora_cuba().date()
            ) + timedelta(days=30)
            
            db(db.suscripcion.id == pago.suscripcion_id).update(
                estado="activa",
                fecha_fin=nueva_fecha_fin,
                fecha_pago=ahora_cuba(),
                monto_pagado=pago.monto,
                moneda_pago=pago.moneda,
            )
            db.commit()
            
            # Notificar al usuario
            db.notificacion.insert(
                usuario_id=pago.usuario_id,
                tipo="pago_validado",
                titulo="Pago validado",
                mensaje=f"Su pago de {pago.monto} {pago.moneda} ha sido validado. Su suscripcion esta activa hasta {nueva_fecha_fin.strftime('%d/%m/%Y')}.",
                fecha_creacion=ahora_cuba(),
            )
            db.commit()
    
    return respuesta_json(exito=True, mensaje=f"Pago {estado} correctamente")

# ============================================================
# CONFIGURACION GLOBAL (SUPERADMIN)
# ============================================================

@action("catalogo_cuba/superadmin/configuracion")
@action.uses(auth, session, db, "superadmin_configuracion.html")
def superadmin_configuracion():
    """Configuracion global del sitio."""
    if not es_superadmin():
        raise HTTP(403)
    
    configuraciones = db(db.configuracion.id > 0).select(orderby=db.configuracion.clave)
    
    return dict(
        **contexto_base(),
        configuraciones=configuraciones,
        titulo="Configuracion Global",
    )

@action("catalogo_cuba/superadmin/configuracion/guardar", method=["POST"])
@action.uses(auth, session, db)
def superadmin_guardar_configuracion():
    """Guardar configuracion."""
    if not es_superadmin():
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    try:
        clave = request.POST.get("clave")
        valor = request.POST.get("valor")
        
        config = db(db.configuracion.clave == clave).select().first()
        if config:
            db(db.configuracion.id == config.id).update(
                valor=valor,
                fecha_actualizacion=ahora_cuba(),
            )
        else:
            db.configuracion.insert(
                clave=clave,
                valor=valor,
                fecha_actualizacion=ahora_cuba(),
            )
        db.commit()
        
        return respuesta_json(exito=True, mensaje="Configuracion guardada")
    
    except Exception as e:
        return respuesta_json(exito=False, mensaje=f"Error: {str(e)}")

# ============================================================
# API DE NOTIFICACIONES
# ============================================================

@action("catalogo_cuba/api/notificaciones")
@action.uses(auth)
def api_notificaciones():
    """API para obtener notificaciones del usuario."""
    user = auth.get_user()
    if not user:
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    notificaciones = db(db.notificacion.usuario_id == user["id"]).select(
        orderby=~db.notificacion.fecha_creacion,
        limitby=(0, 20)
    )
    
    no_leidas = db(db.notificacion.usuario_id == user["id"])(
        db.notificacion.leida == False).count()
    
    return respuesta_json(exito=True, datos={
        "notificaciones": [
            {
                "id": n.id,
                "tipo": n.tipo,
                "titulo": n.titulo,
                "mensaje": n.mensaje,
                "leida": n.leida,
                "fecha": formatear_fecha(n.fecha_creacion),
            }
            for n in notificaciones
        ],
        "no_leidas": no_leidas,
    })

@action("catalogo_cuba/api/notificacion/leer/<notificacion_id:int>", method=["POST"])
@action.uses(auth)
def api_marcar_leida(notificacion_id):
    """Marcar notificacion como leida."""
    user = auth.get_user()
    if not user:
        return respuesta_json(exito=False, mensaje="No autorizado", codigo=403)
    
    db(db.notificacion.id == notificacion_id)(
        db.notificacion.usuario_id == user["id"]).update(
        leida=True,
        fecha_lectura=ahora_cuba(),
    )
    db.commit()
    
    return respuesta_json(exito=True, mensaje="Notificacion marcada como leida")

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def verificar_suscripcion_activa(negocio_id):
    """Verifica si un negocio tiene una suscripcion activa o en prueba."""
    suscripcion = db(db.suscripcion.negocio_id == negocio_id).select(
        orderby=~db.suscripcion.fecha_creacion,
        limitby=(0, 1)
    ).first()
    
    if not suscripcion:
        return False
    
    if suscripcion.estado in ["activa", "prueba"]:
        # Verificar que no haya vencido
        if suscripcion.fecha_fin and suscripcion.fecha_fin >= ahora_cuba().date():
            return True
    
    return False

# ============================================================
# STATIC FILES
# ============================================================

@action("catalogo_cuba/uploads/<filename:path>")
@action.uses()
def serve_uploads(filename):
    """Servir archivos subidos."""
    ruta = os.path.join(settings.UPLOAD_FOLDER, filename)
    if os.path.exists(ruta):
        # Detectar content type
        ext = os.path.splitext(filename)[1].lower()
        content_type = "application/octet-stream"
        if ext in [".jpg", ".jpeg"]:
            content_type = "image/jpeg"
        elif ext == ".png":
            content_type = "image/png"
        elif ext == ".gif":
            content_type = "image/gif"
        elif ext == ".webp":
            content_type = "image/webp"
        
        response.headers["Content-Type"] = content_type
        response.headers["Cache-Control"] = "public, max-age=86400"
        
        with open(ruta, "rb") as f:
            return f.read()
    
    raise HTTP(404, "Archivo no encontrado")
