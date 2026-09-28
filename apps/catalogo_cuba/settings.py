"""
Configuracion de la aplicacion CatalogoCuba
Optimizado para conexiones lentas e inestables
"""
import os

# Modo debug - False en produccion
DEBUG = True

# Base de datos - SQLite para facilitar despliegue en Cuba
DB_URI = "sqlite://storage.db"
DB_POOL_SIZE = 0  # SQLite no usa pool
DB_MIGRATE = True
DB_FAKE_MIGRATE = False
DB_MIGRATE_DIR = os.path.join(os.path.dirname(__file__), "databases")

# Directorio de uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")

# Clave secreta para sesiones - cambiar en produccion
SESSION_SECRET_KEY = "catalogo-cuba-secret-key-2024"

# Configuracion de sesiones
SESSION_TYPE = "cookie"
SESSION_SECURE = False  # True si usas HTTPS
SESSION_SAMESITE = "Lax"
SESSION_EXPIRATION = 3600 * 24 * 7  # 7 dias

# Configuracion de autenticacion
AUTH_PASSWORD_MIN_LENGTH = 6
AUTH_REGISTRATION_REQUIRES_CONFIRMATION = False
AUTH_REGISTRATION_REQUIRES_APPROVAL = True  # Los nuevos comerciantes necesitan aprobacion

# Configuracion de correo (opcional, para notificaciones)
SMTP_SERVER = None
SMTP_SENDER = None

# Configuracion de precios en CUP (moneda cubana)
MONEDA_LOCAL = "CUP"
MONEDA_EXTRANJERA = "USDT"

# Costos de suscripcion (en CUP para Transfermovil, en USDT para crypto)
COSTO_SUSCRIPCION_MENSUAL_CUP = 1500
COSTO_SUSCRIPCION_MENSUAL_USDT = 5.0

# Dias de prueba gratuita
DIAS_PRUEBA_GRATIS = 30

# Tamano maximo de imagen en upload (2MB)
MAX_IMAGE_SIZE = 2 * 1024 * 1024

# Dimensiones de imagen optimizadas
IMAGE_THUMBNAIL_SIZE = (300, 300)
IMAGE_MEDIUM_SIZE = (600, 600)
IMAGE_QUALITY = 75

# Configuracion de paginacion (ligero para conexiones lentas)
PAGE_SIZE = 12

# Configuracion de cache para modo offline
CACHE_MAX_AGE = 3600  # 1 hora
