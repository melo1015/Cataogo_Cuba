"""Configuracion de CatalogoCuba: valores seguros para desarrollo y produccion."""
import os

# Entorno explícito: en producción no se permite activar DEBUG por accidente.
ENVIRONMENT = os.environ.get("CATALOGO_CUBA_ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"
DEBUG_REQUESTED = os.environ.get(
    "CATALOGO_CUBA_DEBUG", "0" if IS_PRODUCTION else "1"
).strip() == "1"
DEBUG = DEBUG_REQUESTED and not IS_PRODUCTION

# En producción (o con DEBUG desactivado) no se acepta una clave predecible.
SESSION_SECRET_KEY = os.environ.get("CATALOGO_CUBA_SECRET", "").strip()
if not SESSION_SECRET_KEY:
    if IS_PRODUCTION or not DEBUG:
        raise RuntimeError(
            "Falta CATALOGO_CUBA_SECRET: define una clave aleatoria antes de iniciar "
            "CatalogoCuba con debug desactivado o en produccion."
        )
    SESSION_SECRET_KEY = "catalogo-cuba-local-only-not-for-production"

# Base de datos. En despliegues con SQLite, el archivo debe residir en un volumen persistente.
DB_URI = os.environ.get("CATALOGO_CUBA_DB_URI", "sqlite://storage.db")
DB_POOL_SIZE = 0
DB_MIGRATE = True
DB_FAKE_MIGRATE = False
DB_MIGRATE_DIR = os.path.join(os.path.dirname(__file__), "databases")

# Los uploads deben persistir entre reinicios y estar fuera de directorios efímeros.
UPLOAD_FOLDER = os.path.abspath(os.environ.get(
    "CATALOGO_CUBA_UPLOAD_FOLDER",
    os.path.join(os.path.dirname(__file__), "uploads")
))

SESSION_TYPE = "cookie"
SESSION_SAMESITE = "Lax"
SESSION_EXPIRATION = 3600 * 24 * 7

AUTH_PASSWORD_MIN_LENGTH = 10
AUTH_REGISTRATION_REQUIRES_CONFIRMATION = False
AUTH_REGISTRATION_REQUIRES_APPROVAL = False  # La aprobacion de negocios se controla en la app.

SMTP_SERVER = None
SMTP_SENDER = None

MONEDA_LOCAL = "CUP"
MONEDA_EXTRANJERA = "USDT"
COSTO_SUSCRIPCION_MENSUAL_CUP = 1500
COSTO_SUSCRIPCION_MENSUAL_USDT = 5.0
DIAS_PRUEBA_GRATIS = 30

MAX_IMAGE_SIZE = 2 * 1024 * 1024
# Limite del JSON enviado a la API publica de pedidos (antes del parseo).
MAX_ORDER_REQUEST_SIZE = 64 * 1024
# IPs exactas de proxies inversos confiables, separadas por coma.
# Ejemplo: CATALOGO_CUBA_TRUSTED_PROXY_IPS=127.0.0.1,10.0.0.10
# Dejar vacio si la app no recibe trafico desde un proxy confiable.
TRUSTED_PROXY_IPS = tuple(
    ip.strip() for ip in os.environ.get("CATALOGO_CUBA_TRUSTED_PROXY_IPS", "").split(",")
    if ip.strip()
)
IMAGE_THUMBNAIL_SIZE = (300, 300)
IMAGE_MEDIUM_SIZE = (600, 600)
IMAGE_QUALITY = 75
PAGE_SIZE = 12
CACHE_MAX_AGE = 3600
