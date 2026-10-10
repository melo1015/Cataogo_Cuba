"""
Configuracion de la aplicacion CatalogoCuba
Optimizado para conexiones lentas e inestables
"""
import os

# ============================================================
# ENTORNO
# ============================================================

# Modo debug - False en produccion
DEBUG = os.environ.get("CATALOGO_CUBA_DEBUG", "0") == "1

# ============================================================
# BASE DE DATOS - SQLite para facilitar despliegue en Cuba
# ============================================================

DB_URI = os.environ.get("CATALOGO_CUBA_DB_URI", "sqlite://storage.db")
DB_POOL_SIZE = 0   # SQLite no usa pool
DB_MIGRATE = True
DB_FAKE_MIGRATE = False
DB_MIGRATE_DIR = os.path.join(os.path.dirname(__file__), "databases")

# ============================================================
# DIRECTORIO DE UPLOADS
# ============================================================

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")

# ============================================================
# SESIONES
# ============================================================

# Clave secreta para sesiones - CAMBIAR EN PRODUCCION
# En produccion, define la variable de entorno CATALOGO_CUBA_SECRET.
SESSION_SECRET_KEY = os.environ.get("CATALOGO_CUBA_SECRET")
if not SESSION_SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Define CATALOGO_CUBA_SECRET antes de iniciar en modo seguro.")
    SESSION_SECRET_KEY = "catalogo-cuba-local-development-only"

# Configuracion de sesiones
SESSION_TYPE = "cookie"
SESSION_SECURE = os.environ.get("CATALOGO_CUBA_SECURE", "0") == "1"
SESSION_SAMESITE = "Lax"
SESSION_EXPIRATION = 3600 * 24 * 7   # 7 dias

# ============================================================
# AUTENTICACION
# ============================================================

AUTH_PASSWORD_MIN_LENGTH = 6

# En py4web, 'registration_requires_confirmation' existe como parametro.
# 'registration_requires_approval' NO existe como parametro de Auth.
# La aprobacion manual se implementa con un hook on_signup en models.py.
AUTH_REGISTRATION_REQUIRES_CONFIRMATION = False
AUTH_REGISTRATION_REQUIRES_APPROVAL = False   # Ver on_signup en models.py

# ============================================================
# CORREO (opcional, no usado actualmente)
# ============================================================

SMTP_SERVER = None
SMTP_SENDER = None

# ============================================================
# MONEDA Y PRECIOS
# ============================================================

MONEDA_LOCAL = "CUP"
MONEDA_EXTRANJERA = "USDT"

# Costos de suscripcion
COSTO_SUSCRIPCION_MENSUAL_CUP = 1500
COSTO_SUSCRIPCION_MENSUAL_USDT = 5.0

# Dias de prueba gratuita
DIAS_PRUEBA_GRATIS = 30

# ============================================================
# IMAGENES
# ============================================================

# Tamano maximo de imagen en upload (2MB)
MAX_IMAGE_SIZE = 2 * 1024 * 1024

# Dimensiones de imagen optimizadas
IMAGE_THUMBNAIL_SIZE = (300, 300)
IMAGE_MEDIUM_SIZE = (600, 600)
IMAGE_QUALITY = 75

# ============================================================
# PAGINACION
# ============================================================

# Ligero para conexiones lentas
PAGE_SIZE = 12

# ============================================================
# CACHE / MODO OFFLINE
# ============================================================

CACHE_MAX_AGE = 3600   # 1 hora