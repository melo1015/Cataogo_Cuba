"""
Modulo comun - Utilidades compartidas de la aplicacion
Incluye: db, session, auth, translator, y utilidades
"""
import os
import uuid
import hashlib
from datetime import datetime, timedelta
from PIL import Image, ImageOps
import io

from py4web import Session, Translator, DAL, Field, action
from py4web.utils.auth import Auth
from py4web.utils.form import FormStyleDefault

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
    migrate_enabled=True,
)

# ============================================================
# SESION
# ============================================================

session = Session(secret=settings.SESSION_SECRET_KEY)

# ============================================================
# TRADUCTOR
# ============================================================

translator = Translator(os.path.join(os.path.dirname(__file__), "translations"))

# ============================================================
# AUTENTICACION
# ============================================================

auth = Auth(session, db, define_tables=False)
auth.param.registration_requires_confirmation = settings.AUTH_REGISTRATION_REQUIRES_CONFIRMATION
auth.param.registration_requires_approval = settings.AUTH_REGISTRATION_REQUIRES_APPROVAL
auth.param.allowed_actions = [
    "login",
    "logout",
    "register",
    "request_reset_password",
    "reset_password",
    "change_password",
    "change_email",
    "profile",
]

# ============================================================
# ROLES DE USUARIO
# ============================================================

ROLES = {
    "superadmin": "Administrador del sitio",
    "comerciante": "Dueno de negocio",
    "visitante": "Usuario visitante",
}

# ============================================================
# UTILIDADES DE IMAGEN
# ============================================================

def optimizar_imagen(archivo, max_size=settings.IMAGE_MEDIUM_SIZE, quality=settings.IMAGE_QUALITY):
    """
    Comprime y optimiza una imagen para conexiones lentas.
    Retorna el archivo optimizado como bytes.
    """
    try:
        img = Image.open(archivo)
        
        # Convertir a RGB si es necesario (para PNG con transparencia)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Redimensionar manteniendo proporcion
        img.thumbnail(max_size, Image.LANCZOS)
        
        # Auto-orientar segun EXIF
        img = ImageOps.exif_transpose(img)
        
        # Guardar con compresion optimizada
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)
        
        return output
    except Exception as e:
        print(f"Error optimizando imagen: {e}")
        return None

def guardar_imagen(archivo, nombre_carpeta="productos"):
    """
    Guarda una imagen optimizada en el directorio de uploads.
    Retorna la ruta relativa del archivo guardado.
    """
    if not archivo:
        return None
    
    # Crear carpeta si no existe
    carpeta = os.path.join(settings.UPLOAD_FOLDER, nombre_carpeta)
    os.makedirs(carpeta, exist_ok=True)
    
    # Generar nombre unico
    extension = ".jpg"
    nombre_unico = f"{uuid.uuid4().hex}{extension}"
    ruta_relativa = f"{nombre_carpeta}/{nombre_unico}"
    ruta_absoluta = os.path.join(settings.UPLOAD_FOLDER, ruta_relativa)
    
    # Optimizar y guardar
    optimizada = optimizar_imagen(archivo)
    if optimizada:
        with open(ruta_absoluta, "wb") as f:
            f.write(optimizada.read())
        return ruta_relativa
    
    return None

def generar_thumbnail(archivo):
    """Genera una version thumbnail de la imagen."""
    return optimizar_imagen(archivo, max_size=settings.IMAGE_THUMBNAIL_SIZE)

# ============================================================
# UTILIDADES DE FECHA
# ============================================================

def ahora_cuba():
    """Retorna la fecha/hora actual en zona horaria de Cuba (UTC-5)."""
    return datetime.utcnow() - timedelta(hours=5)

def formatear_fecha(fecha):
    """Formatea una fecha para mostrar."""
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y %H:%M")

def formatear_fecha_corta(fecha):
    """Formatea una fecha corta."""
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")

# ============================================================
# UTILIDADES DE RESPUESTA JSON
# ============================================================

def respuesta_json(exito=True, mensaje="", datos=None, codigo=200):
    """Genera una respuesta JSON estandarizada."""
    from py4web import response
    import json
    response.status = codigo
    response.headers["Content-Type"] = "application/json"
    resultado = {
        "exito": exito,
        "mensaje": mensaje,
        "datos": datos or {},
    }
    return json.dumps(resultado)

# ============================================================
# DECORADOR DE PERMISOS
# ============================================================

def requiere_rol(rol_requerido):
    """
    Decorador que verifica si el usuario tiene el rol requerido.
    Uso: @requiere_rol("superadmin") o @requiere_rol("comerciante")
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            user = auth.get_user()
            if not user:
                from py4web import redirect, URL
                return redirect(URL("auth/login"))
            
            # Verificar rol
            rol_usuario = user.get("rol", "visitante")
            if rol_requerido == "superadmin" and rol_usuario != "superadmin":
                return respuesta_json(exito=False, mensaje="Acceso denegado: requiere rol de superadmin", codigo=403)
            
            if rol_requerido == "comerciante" and rol_usuario not in ["superadmin", "comerciante"]:
                return respuesta_json(exito=False, mensaje="Acceso denegado: requiere rol de comerciante", codigo=403)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def es_superadmin():
    """Verifica si el usuario actual es superadmin."""
    user = auth.get_user()
    return user and user.get("rol") == "superadmin"

def es_comerciante():
    """Verifica si el usuario actual es comerciante o superadmin."""
    user = auth.get_user()
    if not user:
        return False
    return user.get("rol") in ["comerciante", "superadmin"]

# ============================================================
# SLUGIFY
# ============================================================

def slugify(texto):
    """Convierte un texto a slug URL-friendly."""
    import unicodedata
    import re
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    return re.sub(r"[-\s]+", "-", texto)

# ============================================================
# ESTADISTICAS
# ============================================================

def registrar_visita(negocio_id=None, producto_id=None, ip=None, user_agent=None):
    """
    Registra una visita de forma ligera (sin bloquear la respuesta).
    """
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
        print(f"Error registrando visita: {e}")

# ============================================================
# FORM STYLE CUSTOM (optimizado para conexiones lentas)
# ============================================================

FormStyleCatalogo = FormStyleDefault
