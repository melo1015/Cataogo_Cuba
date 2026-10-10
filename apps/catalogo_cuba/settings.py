"""Configuracion de CatalogoCuba: valores seguros y compatibles con desarrollo local."""
import os

ENVIRONMENT = os.environ.get("CATALOGO_CUBA_ENV", "development").strip().lower()
DEBUG = os.environ.get("CATALOGO_CUBA_DEBUG", "1" if ENVIRONMENT != "production" else "0") == "1"
IS_PRODUCTION = ENVIRONMENT == "production"

# En produccion nunca iniciar con una clave de sesion predecible.
SESSION_SECRET_KEY = os.environ.get("CATALOGO_CUBA_SECRET", "").strip()
if not SESSION_SECRET_KEY:
    if IS_PRODUCTION or not DEBUG:
        raise RuntimeError(
            "Falta CATALOGO_CUBA_SECRET: define una clave aleatoria antes de iniciar "
            "CatalogoCuba con debug desactivado o en produccion."
        )
    SESSION_SECRET_KEY = "catalogo-cuba-local-only-not-for-production"

DB_URI = os.environ.get("CATALOGO_CUBA_DB_URI", "sqlite://storage.db")
DB_POOL_SIZE = 0
DB_MIGRATE = True
DB_FAKE_MIGRATE = False
DB_MIGRATE_DIR = os.path.join(os.path.dirname(__file__), "databases")
UPLOAD_FOLDER = os.path.abspath(os.environ.get(
    "CATALOGO_CUBA_UPLOAD_FOLDER",
    os.path.join(os.path.dirname(__file__), "uploads")
))

SESSION_TYPE = "cookie"
SESSION_SECURE = os.environ.get(
    "CATALOGO_CUBA_SECURE", "1" if IS_PRODUCTION else "0"
) == "1"
SESSION_SAMESITE = "Lax"
SESSION_EXPIRATION = 3600 * 24 * 7

AUTH_PASSWORD_MIN_LENGTH = 10
AUTH_REGISTRATION_REQUIRES_CONFIRMATION = False
AUTH_REGISTRATION_REQUIRES_APPROVAL = False

SMTP_SERVER = None
SMTP_SENDER = None

MONEDA_LOCAL = "CUP"
MONEDA_EXTRANJERA = "USDT"
COSTO_SUSCRIPCION_MENSUAL_CUP = 1500
COSTO_SUSCRIPCION_MENSUAL_USDT = 5.0
DIAS_PRUEBA_GRATIS = 30

MAX_IMAGE_SIZE = 2 * 1024 * 1024
IMAGE_THUMBNAIL_SIZE = (300, 300)
IMAGE_MEDIUM_SIZE = (600, 600)
IMAGE_QUALITY = 75
PAGE_SIZE = 12
CACHE_MAX_AGE = 3600
