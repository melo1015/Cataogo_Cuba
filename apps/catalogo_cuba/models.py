"""
Modelos de datos - CatalogoCuba
Define todas las tablas de la base de datos usando pyDAL (py4web).
"""
from datetime import datetime

from pydal import Field
from pydal.validators import (
    IS_NOT_EMPTY, IS_SLUG, IS_EMPTY_OR, IS_IMAGE,
    IS_IN_SET, IS_DECIMAL_IN_RANGE,
)

from .common import db, auth, roles_tags, asignar_rol
from . import settings

# ============================================================
# TABLAS DE AUTENTICACION (auth)
# ============================================================
# En py4web, Auth ya crea automaticamente sus tablas al instanciarse
# en common.py. NO se debe llamar a auth.define_tables() (no existe en py4web).

# Campos personalizados en auth_user que el resto del sistema espera
if "fecha_registro" not in db.auth_user.fields:
    db.auth_user.define_field("fecha_registro", "datetime", default=None)

if "telefono" not in db.auth_user.fields:
    db.auth_user.define_field("telefono", "string", length=20, default="")

db.auth_user.fecha_registro.writable = False
db.auth_user.fecha_registro.readable = True


# ============================================================
# TABLA DE NEGOCIOS
# ============================================================

db.define_table(
    "negocio",
    Field("nombre", "string", length=200, notnull=True, label="Nombre del negocio",
          requires=IS_NOT_EMPTY()),
    Field("slug", "string", length=200, unique=True, notnull=True, label="URL amigable",
          requires=[IS_NOT_EMPTY(), IS_SLUG()]),
    Field("descripcion", "text", default="", label="Descripcion del negocio"),
    Field("logo", "upload", uploadfolder=settings.UPLOAD_FOLDER, label="Logo",
          requires=IS_EMPTY_OR(IS_IMAGE(maxsize=(800, 800)))),
    Field("direccion", "string", length=300, default="", label="Direccion"),
    Field("telefono", "string", length=20, default="", label="Telefono de contacto"),
    Field("email", "string", length=128, default="", label="Correo electronico"),
    Field("whatsapp", "string", length=20, default="", label="WhatsApp"),
    Field("horario", "string", length=200, default="", label="Horario de atencion"),
    Field("provincia", "string", length=50, default="", label="Provincia",
          requires=IS_EMPTY_OR(IS_IN_SET({
              'Pinar del Rio': 'Pinar del Rio',
              'Artemisa': 'Artemisa',
              'La Habana': 'La Habana',
              'Mayabeque': 'Mayabeque',
              'Matanzas': 'Matanzas',
              'Cienfuegos': 'Cienfuegos',
              'Villa Clara': 'Villa Clara',
              'Sancti Spiritus': 'Sancti Spiritus',
              'Ciego de Avila': 'Ciego de Avila',
              'Camaguey': 'Camaguey',
              'Las Tunas': 'Las Tunas',
              'Holguin': 'Holguin',
              'Granma': 'Granma',
              'Santiago de Cuba': 'Santiago de Cuba',
              'Guantanamo': 'Guantanamo',
              'Isla de la Juventud': 'Isla de la Juventud'
          }))),
    Field("municipio", "string", length=50, default="", label="Municipio"),
    Field("usuario_id", "reference auth_user", notnull=True, label="Dueno del negocio"),
    Field("activo", "boolean", default=True, label="Negocio activo"),
    Field("aprobado", "boolean", default=False, label="Aprobado por admin"),
    Field("fecha_creacion", "datetime", default=None, label="Fecha de creacion"),
    Field("fecha_actualizacion", "datetime", default=None, label="Ultima actualizacion"),
    Field("color_tema", "string", length=7, default="#2563eb", label="Color del tema"),
    Field("moneda_principal", "string", length=10, default="CUP", label="Moneda principal",
          requires=IS_IN_SET({
              'CUP': 'CUP (Peso Cubano)',
              'MLC': 'MLC',
              'USD': 'USD',
              'USDT': 'USDT'
          })),
    Field("mostrar_precios", "boolean", default=True, label="Mostrar precios publicamente"),
    Field("meta_descripcion", "string", length=300, default="", label="Meta descripcion SEO"),
    Field("facebook", "string", length=200, default="", label="Facebook"),
    Field("instagram", "string", length=200, default="", label="Instagram"),
    Field("telegram", "string", length=200, default="", label="Telegram"),
    format="%(nombre)s",
)

# ============================================================
# TABLA DE CATEGORIAS
# ============================================================

db.define_table(
    "categoria",
    Field("nombre", "string", length=100, notnull=True, label="Nombre de categoria",
          requires=IS_NOT_EMPTY()),
    Field("slug", "string", length=100, notnull=True, label="Slug"),
    Field("descripcion", "text", default="", label="Descripcion"),
    Field("negocio_id", "reference negocio", notnull=True, label="Negocio"),
    Field("imagen", "upload", uploadfolder=settings.UPLOAD_FOLDER, label="Imagen de categoria",
          requires=IS_EMPTY_OR(IS_IMAGE(maxsize=(800, 800)))),
    Field("orden", "integer", default=0, label="Orden de visualizacion"),
    Field("activa", "boolean", default=True, label="Activa"),
    Field("fecha_creacion", "datetime", default=None, label="Fecha de creacion"),
    format="%(nombre)s",
)

# ============================================================
# TABLA DE PRODUCTOS
# ============================================================

db.define_table(
    "producto",
    Field("nombre", "string", length=200, notnull=True, label="Nombre del producto",
          requires=IS_NOT_EMPTY()),
    Field("slug", "string", length=200, notnull=True, label="Slug"),
    Field("descripcion", "text", default="", label="Descripcion"),
    Field("descripcion_corta", "string", length=200, default="", label="Descripcion corta"),
    Field("precio", "decimal(10,2)", default=0.0, label="Precio",
          requires=IS_DECIMAL_IN_RANGE(0, 99999999.99)),
    Field("precio_anterior", "decimal(10,2)", default=None, label="Precio anterior"),
    Field("moneda", "string", length=10, default="CUP", label="Moneda",
          requires=IS_IN_SET({
              'CUP': 'CUP',
              'MLC': 'MLC',
              'USD': 'USD',
              'USDT': 'USDT'
          })),
    Field("disponible", "boolean", default=True, label="Disponible"),
    Field("en_oferta", "boolean", default=False, label="En oferta"),
    Field("stock", "integer", default=0, label="Cantidad en stock"),
    Field("sku", "string", length=50, default="", label="Codigo SKU"),
    Field("categoria_id", "reference categoria", default=None, label="Categoria"),
    Field("negocio_id", "reference negocio", notnull=True, label="Negocio"),
    Field("imagen_principal", "upload", uploadfolder=settings.UPLOAD_FOLDER, label="Imagen principal",
          requires=IS_EMPTY_OR(IS_IMAGE(maxsize=(1200, 1200)))),
    Field("imagenes_adicionales", "list:string", default=[], label="Imagenes adicionales"),
    Field("orden", "integer", default=0, label="Orden"),
    Field("destacado", "boolean", default=False, label="Producto destacado"),
    Field("tags", "list:string", default=[], label="Etiquetas"),
    Field("meta_keywords", "string", length=200, default="", label="Palabras clave SEO"),
    Field("peso", "decimal(8,2)", default=None, label="Peso (kg)"),
    Field("fecha_creacion", "datetime", default=None, label="Fecha de creacion"),
    Field("fecha_actualizacion", "datetime", default=None, label="Ultima actualizacion"),
    Field("vistas", "integer", default=0, label="Contador de vistas"),
    format="%(nombre)s",
)

# ============================================================
# TABLA DE SUSCRIPCIONES
# ============================================================

db.define_table(
    "suscripcion",
    Field("negocio_id", "reference negocio", notnull=True, label="Negocio"),
    Field("usuario_id", "reference auth_user", notnull=True, label="Usuario"),
    Field("fecha_inicio", "date", notnull=True, label="Fecha de inicio"),
    Field("fecha_fin", "date", notnull=True, label="Fecha de vencimiento"),
    Field("estado", "string", length=20, default="activa", label="Estado",
          requires=IS_IN_SET({
              'activa': 'Activa',
              'pendiente': 'Pendiente de pago',
              'vencida': 'Vencida',
              'suspendida': 'Suspendida',
              'cancelada': 'Cancelada',
              'prueba': 'Periodo de prueba'
          })),
    Field("metodo_pago", "string", length=30, default=None, label="Metodo de pago",
          requires=IS_EMPTY_OR(IS_IN_SET({
              'transfermovil': 'Transfermovil',
              'presencial': 'Pago presencial',
              'usdt': 'USDT (cripto)',
              'prueba': 'Periodo de prueba'
          }))),
    Field("monto_pagado", "decimal(10,2)", default=0.0, label="Monto pagado"),
    Field("moneda_pago", "string", length=10, default="CUP", label="Moneda de pago"),
    Field("dias_prueba", "integer", default=settings.DIAS_PRUEBA_GRATIS, label="Dias de prueba"),
    Field("fecha_pago", "datetime", default=None, label="Fecha del ultimo pago"),
    Field("fecha_creacion", "datetime", default=None, label="Fecha de creacion"),
    Field("notas", "text", default="", label="Notas"),
    format="%(negocio_id)s - %(estado)s",
)

# ============================================================
# TABLA DE PAGOS
# ============================================================

db.define_table(
    "pago",
    Field("suscripcion_id", "reference suscripcion", notnull=True, label="Suscripcion"),
    Field("negocio_id", "reference negocio", notnull=True, label="Negocio"),
    Field("usuario_id", "reference auth_user", notnull=True, label="Usuario que realizo el pago"),
    Field("monto", "decimal(10,2)", notnull=True, label="Monto"),
    Field("moneda", "string", length=10, default="CUP", label="Moneda"),
    Field("metodo_pago", "string", length=30, notnull=True, label="Metodo de pago",
          requires=IS_IN_SET({
              'transfermovil': 'Transfermovil',
              'presencial': 'Pago presencial',
              'usdt': 'USDT (cripto)'
          })),
    Field("estado", "string", length=20, default="pendiente", label="Estado del pago",
          requires=IS_IN_SET({
              'pendiente': 'Pendiente de validacion',
              'validado': 'Validado',
              'rechazado': 'Rechazado',
              'en_proceso': 'En proceso'
          })),
    Field("referencia", "string", length=100, default="", label="Referencia/Numero de transaccion"),
    Field("comprobante", "upload", uploadfolder=settings.UPLOAD_FOLDER, label="Comprobante de pago",
          requires=IS_EMPTY_OR(IS_IMAGE(maxsize=(2000, 2000)))),
    Field("fecha_solicitud", "datetime", default=None, label="Fecha de solicitud"),
    Field("fecha_validacion", "datetime", default=None, label="Fecha de validacion"),
    Field("validado_por", "reference auth_user", default=None, label="Validado por"),
    Field("notas_validacion", "text", default="", label="Notas de validacion"),
    Field("direccion_usdt", "string", length=100, default="", label="Direccion USDT (para pagos crypto)"),
    Field("hash_transaccion", "string", length=100, default="", label="Hash de transaccion blockchain"),
    format="%(referencia)s - %(estado)s",
)

# ============================================================
# TABLA DE ESTADISTICAS (VISITAS)
# ============================================================

db.define_table(
    "visita",
    Field("negocio_id", "reference negocio", default=None, label="Negocio visitado"),
    Field("producto_id", "reference producto", default=None, label="Producto visitado"),
    Field("ip", "string", length=50, default="", label="Direccion IP"),
    Field("user_agent", "string", length=500, default="", label="User Agent"),
    Field("fecha", "datetime", default=None, label="Fecha y hora"),
    Field("sesion_id", "string", length=100, default="", label="ID de sesion"),
    format="%(fecha)s",
)

# ============================================================
# TABLA DE CONFIGURACION DEL SITIO
# ============================================================

db.define_table(
    "configuracion",
    Field("clave", "string", length=100, unique=True, notnull=True, label="Clave"),
    Field("valor", "text", default="", label="Valor"),
    Field("descripcion", "string", length=300, default="", label="Descripcion"),
    Field("tipo", "string", length=20, default="string", label="Tipo de dato",
          requires=IS_IN_SET({
              'string': 'Texto',
              'integer': 'Entero',
              'decimal': 'Decimal',
              'boolean': 'Booleano',
              'json': 'JSON'
          })),
    Field("editable", "boolean", default=True, label="Editable por admin"),
    Field("fecha_actualizacion", "datetime", default=None, label="Ultima actualizacion"),
    format="%(clave)s",
)

# ============================================================
# TABLA DE NOTIFICACIONES
# ============================================================

db.define_table(
    "notificacion",
    Field("usuario_id", "reference auth_user", notnull=True, label="Destinatario"),
    Field("tipo", "string", length=30, notnull=True, label="Tipo",
          requires=IS_IN_SET({
              'pago_recibido': 'Pago recibido',
              'pago_validado': 'Pago validado',
              'suscripcion_vencida': 'Suscripcion vencida',
              'suscripcion_renovada': 'Suscripcion renovada',
              'negocio_aprobado': 'Negocio aprobado',
              'producto_bajo_stock': 'Producto con bajo stock',
              'general': 'Notificacion general'
          })),
    Field("titulo", "string", length=200, notnull=True, label="Titulo"),
    Field("mensaje", "text", notnull=True, label="Mensaje"),
    Field("leida", "boolean", default=False, label="Leida"),
    Field("url", "string", length=300, default="", label="URL de accion"),
    Field("fecha_creacion", "datetime", default=None, label="Fecha de creacion"),
    Field("fecha_lectura", "datetime", default=None, label="Fecha de lectura"),
    format="%(titulo)s",
)

# ============================================================
# HOOKS DE AUTH
# ============================================================

@auth.on_signup
def _on_signup(user):
    """Asigna rol 'visitante' y fecha_registro al nuevo usuario."""
    try:
        user.update_record(fecha_registro=datetime.utcnow())
        asignar_rol(user["id"], "visitante")
    except Exception as e:
        print("Error en on_signup: %s" % e)


# ============================================================
# COMMIT DE MODELOS
# ============================================================

db.commit()