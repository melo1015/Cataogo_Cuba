"""
Modulo comun - Utilidades compartidas de la aplicacion
Incluye: db, session, auth, y utilidades de autorizacion mediante Tags.
"""
import os
import uuid
import io
import re
import unicodedata
from datetime import datetime, timedelta

from PIL import Image, ImageOps

from py4web import Session, response
from py4web.utils.auth import Auth
from py4web.utils.form import FormStyleBulma
from pydal import DAL, Field
from pydal.tools.tags import Tags

from . import settings

# ============================================================
# BASE DE DATOS
# ============================================================

db = DAL(
    settings.DB_URI,
    folder=settings.DB_MIGRATE_DIR,
    pool_size=settings.DB_POOL_SIZE,
    migrate=settings.DB_MIGRATE,
    fake_migrate=settings.DB_FAKE_MIGRATE,
)

# ============================================================
# SESION
# ============================================================

session = Session(secret=settings.SESSION_SECRET_KEY)

# ============================================================
# AUTENTICACION
# ============================================================

auth = Auth(session, db)

auth.param.registration_requires_confirmation = settings.AUTH_REGISTRATION_REQUIRES_CONFIRMATION

# ============================================================
# AUTORIZACION MEDIANTE TAGS (mecanismo oficial de py4web)
# ============================================================

# Tags asociados a la tabla auth_user.
# Crea automaticamente la tabla auth_user_tag_roles con campos: id, path, record_id.
roles_tags = Tags(db.auth_user, 'roles')

# Roles disponibles en la aplicacion
ROLES = {
    "superadmin": "Administrador del sitio",
    "comerciante": "Dueno de negocio",
    "visitante": "Usuario visitante",
}


def asignar_rol(user_id, rol):
    """
    Asigna el rol indicado a un usuario usando el sistema de Tags de py4web.
    Un usuario puede tener multiples roles (tags).
    """
    if not user_id or rol not in ROLES:
        return False
    roles_tags.add(user_id, rol)
    return True


def quitar_rol(user_id, rol):
    """Quita el rol indicado a un usuario."""
    if not user_id or rol not in ROLES:
        return False
    roles_tags.remove(user_id, rol)
    return True


def obtener_roles(user_id):
    """Retorna la lista de roles (tags) de un usuario."""
    if not user_id:
        return []
    return roles_tags.get(user_id)


def usuario_tiene_rol(user_id, rol):
    """Verifica si un usuario tiene el rol indicado."""
    if not user_id:
        return False
    return rol in roles_tags.get(user_id)


def es_superadmin():
    """Verifica si el usuario actual es superadmin."""
    user = auth.get_user()
    if not user:
        return False
    return usuario_tiene_rol(user["id"], "superadmin")


def es_comerciante():
    """Verifica si el usuario actual es comerciante o superadmin."""
    user = auth.get_user()
    if not user:
        return False
    return (
        usuario_tiene_rol(user["id"], "comerciante") or
        usuario_tiene_rol(user["id"], "superadmin")
    )


def es_visitante():
    """Verifica si el usuario actual es visitante."""
    user = auth.get_user()
    if not user:
        return False
    return usuario_tiene_rol(user["id"], "visitante")


# ============================================================
# UTILIDADES DE IMAGEN
# ============================================================

def optimizar_imagen(archivo, max_size=settings.IMAGE_MEDIUM_SIZE, quality=settings.IMAGE_QUALITY):
    """
    Comprime y optimiza una imagen para conexiones lentas.
    Retorna un BytesIO con la imagen optimizada, o None en caso de error.
    """
    try:
        img = Image.open(archivo)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img = ImageOps.exif_transpose(img)
        img.thumbnail(max_size, Image.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)
        return output
    except Exception as e:
        print("Error optimizando imagen: %s" % e)
        return None


def guardar_imagen(archivo, nombre_carpeta="productos"):
    """
    Guarda una imagen optimizada en el directorio de uploads.
    Retorna la ruta relativa del archivo guardado, o None.
    """
    if not archivo:
        return None

    carpeta = os.path.join(settings.UPLOAD_FOLDER, nombre_carpeta)
    os.makedirs(carpeta, exist_ok=True)

    nombre_unico = "%s.jpg" % uuid.uuid4().hex
    ruta_relativa = "%s/%s" % (nombre_carpeta, nombre_unico)
    ruta_absoluta = os.path.join(settings.UPLOAD_FOLDER, ruta_relativa)

    optimizada = optimizar_imagen(archivo)
    if optimizada:
        with open(ruta_absoluta, "wb") as f:
            f.write(optimizada.read())
        return ruta_relativa

    return None


def generar_thumbnail(archivo):
    return optimizar_imagen(archivo, max_size=settings.IMAGE_THUMBNAIL_SIZE)


# ============================================================
# UTILIDADES DE FECHA
# ============================================================

def ahora_cuba():
    """Retorna la fecha/hora actual aproximada en zona horaria de Cuba (UTC-5)."""
    return datetime.utcnow() - timedelta(hours=5)


def formatear_fecha(fecha):
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y %H:%M")


def formatear_fecha_corta(fecha):
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")


# ============================================================
# UTILIDADES DE RESPUESTA JSON
# ============================================================

def respuesta_json(exito=True, mensaje="", datos=None, codigo=200):
    """
    Genera una respuesta JSON estandarizada.
    Devuelve un dict; py4web lo serializa automaticamente.
    """
    response.status = codigo
    response.headers["Content-Type"] = "application/json"
    return {
        "exito": exito,
        "mensaje": mensaje,
        "datos": datos or {},
    }


# ============================================================
# SLUGIFY
# ============================================================

def slugify(texto):
    """Convierte un texto a slug URL-friendly."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    return re.sub(r"[-\s]+", "-", texto)


# ============================================================
# ESTADISTICAS
# ============================================================

def registrar_visita(negocio_id=None, producto_id=None, ip=None, user_agent=None):
    """Registra una visita de forma ligera."""
    try:
        db.visita.insert(
            negocio_id=negocio_id,
            producto_id=producto_id,
            ip=ip,
            user_agent=user_agent,
            fecha=ahora_cuba(),
        )
        db.commit()
    except Exception as e:
        print("Error registrando visita: %s" % e)


# ============================================================
# FORM STYLE CUSTOM
# ============================================================

# En py4web no existe FormStyleDefault. Se usa FormStyleBulma.
FormStyleCatalogo = FormStyleBulma