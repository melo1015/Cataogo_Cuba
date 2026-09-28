# CatalogoCuba - Directorio de Negocios Cubanos

Aplicacion web en **py4web** para que pequenos negocios, MIPYMES y minoristas cubanos muestren su catalogo de productos. Funciona incluso con **conexiones lentas, inestables, intermitentes o con apagones** gracias a su **modo offline** completo.

---

## Caracteristicas

- **Catálogo público** para cada negocio con productos, categorías y filtros
- **Panel de administración** del negocio con CRUD completo
- **Panel de superadministración** para gestión del sitio
- **Modo offline** con Service Worker, cacheo de recursos y sincronización
- **Compresión automática** de imágenes para ahorrar ancho de banda
- **Sistema de suscripciones** con primer mes gratuito
- **Múltiples métodos de pago**: Transfermóvil, Pago presencial, USDT
- **Validación manual** de pagos para adaptarse a la realidad cubana
- **Diseño responsive** y extremadamente ligero
- **Sin dependencias pesadas** del frontend

---

## Requisitos

- Python 3.7+
- py4web
- Pillow (para compresión de imágenes)

---

## Instalación

### 1. Instalar py4web

```bash
pip install py4web
```

### 2. Instalar Pillow (para compresión de imágenes)

```bash
pip install Pillow
```

### 3. Estructura de carpetas

El proyecto debe estar ubicado en la carpeta `apps/` de py4web:

```
apps/
└── catalogo_cuba/
    ├── __init__.py
    ├── models.py
    ├── controllers.py
    ├── common.py
    ├── settings.py
    ├── README.md
    ├── templates/
    │   ├── layout.html
    │   ├── catalogo_home.html
    │   ├── catalogo_negocio.html
    │   ├── catalogo_producto.html
    │   ├── catalogo_busqueda.html
    │   ├── admin_dashboard.html
    │   ├── admin_productos.html
    │   ├── admin_producto_form.html
    │   ├── admin_categorias.html
    │   ├── admin_categoria_form.html
    │   ├── admin_negocio_form.html
    │   ├── admin_inventario.html
    │   ├── admin_suscripcion.html
    │   ├── admin_estadisticas.html
    │   ├── superadmin_dashboard.html
    │   ├── superadmin_negocios.html
    │   ├── superadmin_usuarios.html
    │   ├── superadmin_suscripciones.html
    │   ├── superadmin_pagos.html
    │   └── superadmin_configuracion.html
    ├── static/
    │   ├── sw.js
    │   ├── manifest.json
    │   ├── icon-72.png
    │   ├── icon-96.png
    │   ├── icon-128.png
    │   ├── icon-144.png
    │   ├── icon-192.png
    │   └── icon-512.png
    ├── uploads/
    └── databases/
```

### 4. Configuración

Edita el archivo `settings.py` para ajustar:

- `DB_URI`: URI de la base de datos (por defecto SQLite)
- `SESSION_SECRET_KEY`: Clave secreta para sesiones (cambiar en producción)
- `COSTO_SUSCRIPCION_MENSUAL_CUP`: Costo de suscripción en CUP
- `COSTO_SUSCRIPCION_MENSUAL_USDT`: Costo de suscripción en USDT
- `DIAS_PRUEBA_GRATIS`: Días de prueba gratuita (por defecto 30)

### 5. Ejecutar py4web

```bash
py4web run apps
```

La aplicación estará disponible en `http://localhost:8000/catalogo_cuba`

---

## Despliegue en producción

### Opción 1: Servidor propio (VPS, Nube)

```bash
# Instalar dependencias
pip install py4web Pillow

# Crear apps folder si no existe
mkdir -p apps
cd apps

# Clonar/ copiar la aplicación
# ... copiar catalogo_cuba/ ...

# Ejecutar con Rocket3 (servidor WSGI incluido en py4web)
py4web run apps --host 0.0.0.0 --port 80
```

### Opción 2: Usando Gunicorn (recomendado para producción)

```bash
pip install gunicorn

# Crear wsgi.py en la raíz de apps
```

Crear archivo `apps/wsgi.py`:
```python
import sys
import os

# Añadir el path de py4web
from py4web.core import wsgi

application = wsgi(os.path.dirname(os.path.abspath(__file__)))
```

Ejecutar:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application
```

### Opción 3: Detrás de Nginx (reverse proxy)

Configuración de Nginx:
```nginx
server {
    listen 80;
    server_name tudominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /catalogo_cuba/uploads/ {
        alias /ruta/a/apps/catalogo_cuba/uploads/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /catalogo_cuba/static/ {
        alias /ruta/a/apps/catalogo_cuba/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## Configuración inicial

### 1. Crear superadministrador

Accede a `http://tu-servidor/auth/register` y regístrate. Luego ejecuta en la consola de py4web o directamente en la base de datos:

```python
# En consola py4web o script Python
from py4web import DAL
from pydal import Field

db = DAL('sqlite://storage.db', folder='apps/catalogo_cuba/databases')

# Actualizar el usuario a superadmin
db(db.auth_user.email == 'tu-email@ejemplo.com').update(rol='superadmin', activo=True)
db.commit()
```

### 2. Configurar precios de suscripción

Accede al panel de superadmin en `http://tu-servidor/catalogo_cuba/superadmin/configuracion` para ajustar los precios.

---

## Uso

### Para visitantes
1. Accede a la página principal
2. Explora negocios y sus catálogos
3. Busca productos o negocios
4. Contacta al vendedor vía WhatsApp o teléfono

### Para comerciantes
1. Regístrate en la aplicación
2. Espera aprobación del superadmin (o aprueba tu propio negocio si eres superadmin)
3. Accede al panel de administración
4. Configura tu negocio
5. Agrega categorías y productos
6. Gestiona tu suscripción

### Para superadministradores
1. Accede al panel de superadmin
2. Gestiona negocios (aprobación, activación/desactivación)
3. Gestiona usuarios y roles
4. Valida pagos manuales
5. Configura parámetros globales

---

## Modo Offline

La aplicación implementa un **Service Worker** que proporciona:

- Cacheo automático de páginas visitadas
- Cacheo de imágenes y recursos estáticos
- Cacheo del catálogo completo de cada negocio via API
- Funcionamiento sin conexión después de la primera visita
- Sincronización en background cuando vuelve la conexión

### Cómo funciona:
1. Al visitar un negocio, el catálogo se descarga y almacena en localStorage
2. Las imágenes se cachean automáticamente
3. Si pierdes conexión, la app sigue funcionando con datos locales
4. Al recuperar conexión, se sincronizan los datos automáticamente

---

## Sistema de Pagos

### Métodos soportados:

1. **Transfermóvil**: El comerciante realiza la transferencia y registra el número de operación
2. **Pago presencial**: El comerciante coordina un pago en persona
3. **USDT (TRC20)**: Pago con criptomoneda

### Flujo de validación:
1. Comerciante registra el pago en su panel
2. Superadmin ve el pago pendiente en su panel
3. Superadmin valida o rechaza el pago
4. Si se valida, la suscripción se extiende 30 días

---

## Base de datos

La aplicación usa **SQLite** por defecto para facilitar el despliegue en entornos con recursos limitados.

Para usar **PostgreSQL**, cambia en `settings.py`:
```python
DB_URI = "postgres://usuario:password@localhost:5432/catalogocuba"
```

### Tablas principales:
- `auth_user`: Usuarios del sistema
- `negocio`: Negocios registrados
- `categoria`: Categorías de productos
- `producto`: Productos del catálogo
- `suscripcion`: Suscripciones de los negocios
- `pago`: Registro de pagos
- `visita`: Estadísticas de visitas
- `configuracion`: Configuración global
- `notificacion`: Notificaciones a usuarios

---

## Seguridad

- Autenticación con `auth` de py4web
- Roles: superadmin, comerciante, visitante
- Protección CSRF en formularios
- Validación de propiedad de recursos
- Contraseñas hasheadas con PBKDF2
- Sesiones seguras con cookies firmadas

---

## Optimizaciones para Cuba

- ✅ CSS inline crítico para carga instantánea
- ✅ Compresión automática de imágenes (75% calidad, max 600px)
- ✅ Service Worker para modo offline
- ✅ Paginación de resultados
- ✅ Sin frameworks JS pesados (React, Angular, Vue)
- ✅ Sin dependencias de CDN externas
- ✅ Páginas ligeras (< 50KB HTML típico)
- ✅ Cache agresivo de recursos estáticos
- ✅ Primera carga rápida, navegación instantánea

---

## Licencia

MIT License - Libre uso para la comunidad cubana.

---

## Soporte

Para reportar problemas o sugerir mejoras, contacta al equipo de desarrollo.

---

**CatalogoCuba** - Hecho con ❤️ para los emprendedores cubanos.
