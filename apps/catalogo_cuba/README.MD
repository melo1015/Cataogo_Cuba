# CatalogoCuba - Directorio de Negocios Cubanos

Aplicacion web en **py4web** para que pequenos negocios, MIPYMES y minoristas cubanos muestren su catalogo de productos. Funciona incluso con **conexiones lentas, inestables, intermitentes o con apagones** gracias a su **modo offline** completo.

---

## Caracteristicas

- **Catalogo publico** para cada negocio con productos, categorias y filtros
- **Panel de administracion** del negocio con CRUD completo
- **Panel de superadministracion** para gestion del sitio
- **Modo offline** con Service Worker, cacheo de recursos y sincronizacion
- **Instalable como PWA** en dispositivos moviles
- **Compresion automatica** de imagenes para ahorrar ancho de banda
- **Sistema de suscripciones** con primer mes gratuito
- **Multiples metodos de pago**: Transfermovil, Pago presencial, USDT
- **Validacion manual** de pagos para adaptarse a la realidad cubana
- **Diseno responsive** y extremadamente ligero
- **Sin dependencias pesadas** del frontend
- **Sistema de roles** mediante Tags de py4web (superadmin, comerciante, visitante)

---

## Requisitos

- Python 3.7+
- py4web (>= 2023.1.0)
- Pillow (>= 10.0.0) — para compresion de imagenes

---

## Instalacion

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

Si no existe `requirements.txt`, instala manualmente:

```bash
pip install py4web Pillow
```

Contenido recomendado de `requirements.txt`:

```
py4web>=2023.1.0
pillow>=10.0.0
```

### 2. Estructura de carpetas

El proyecto debe tener la siguiente estructura:

```
proyecto/
├── wsgi.py                            # Solo para despliegue con Gunicorn
├── requirements.txt
├── .gitignore
├── apps/
│   └── catalogo_cuba/
│       ├── __init__.py
│       ├── models.py
│       ├── controllers.py
│       ├── common.py
│       ├── settings.py
│       ├── README.md
│       ├── templates/
│       │   ├── layout.html
│       │   ├── auth.html
│       │   ├── error.html
│       │   ├── catalogo_home.html
│       │   ├── catalogo_negocio.html
│       │   ├── catalogo_producto.html
│       │   ├── catalogo_busqueda.html
│       │   ├── admin_dashboard.html
│       │   ├── admin_productos.html
│       │   ├── admin_producto_form.html
│       │   ├── admin_categorias.html
│       │   ├── admin_categoria_form.html
│       │   ├── admin_negocio_form.html
│       │   ├── admin_inventario.html
│       │   ├── admin_suscripcion.html
│       │   ├── admin_estadisticas.html
│       │   ├── superadmin_dashboard.html
│       │   ├── superadmin_negocios.html
│       │   ├── superadmin_usuarios.html
│       │   ├── superadmin_suscripciones.html
│       │   ├── superadmin_pagos.html
│       │   └── superadmin_configuracion.html
│       ├── static/
│       │   ├── sw.js
│       │   ├── manifest.json
│       │   ├── icon-72.png
│       │   ├── icon-96.png
│       │   ├── icon-128.png
│       │   ├── icon-144.png
│       │   ├── icon-192.png
│       │   └── icon-512.png
│       ├── uploads/
│       │   └── .gitkeep
│       └── databases/
│           └── .gitkeep
```

### 3. Configuracion

Edita el archivo `settings.py` para ajustar:

- `DB_URI`: URI de la base de datos (por defecto SQLite)
- `SESSION_SECRET_KEY`: en produccion, define `CATALOGO_CUBA_SECRET` como variable de entorno
- `COSTO_SUSCRIPCION_MENSUAL_CUP`: costo de suscripcion en CUP
- `COSTO_SUSCRIPCION_MENSUAL_USDT`: costo de suscripcion en USDT
- `DIAS_PRUEBA_GRATIS`: dias de prueba gratuita (por defecto 30)

En produccion, define la clave secreta como variable de entorno:

```bash
export CATALOGO_CUBA_SECRET="clave-larga-aleatoria-de-64-caracteres"
```

Nunca uses la clave por defecto en produccion.

### 4. Ejecutar py4web

```bash
py4web run apps
```

La aplicacion estara disponible en `http://localhost:8000/catalogo_cuba`

---

## Migracion inicial

Al ejecutar la aplicacion por primera vez, py4web crea automaticamente las tablas de la base de datos en `databases/` (gracias a `DB_MIGRATE = True` en `settings.py`).

Si cambias el esquema (por ejemplo, anades un campo a un modelo), py4web detectara el cambio y generara una nueva migracion al reiniciar.

---

## Configuracion inicial

### 1. Crear superadministrador

Registrate en la aplicacion accediendo a `/auth/register`.

Luego, asigna el rol `superadmin` usando el sistema de **Tags** de py4web:

```python
# Desde un script Python o la consola de py4web
from apps.catalogo_cuba.common import db, roles_tags

# Buscar el usuario
user = db(db.auth_user.email == 'tu-email@ejemplo.com').select().first()

# Asignar el tag "superadmin"
roles_tags.add(user.id, "superadmin")

# Activar al usuario (si la aprobacion esta activa)
user.update_record(active=True)
db.commit()
```

**NO** intentes actualizar un campo `rol` en `auth_user`: ese campo no existe.
Los roles se gestionan exclusivamente con Tags.

### 2. Configurar precios de suscripcion

Accede al panel de superadmin en `/catalogo_cuba/superadmin/configuracion` para ajustar los precios.

---

## Sistema de roles (Tags de py4web)

Los roles se gestionan con el sistema de **Tags** de py4web (`pydal.tools.tags.Tags`), siguiendo la filosofia oficial del framework, que **no utiliza grupos** como web2py.

### Asignar un rol

```python
from apps.catalogo_cuba.common import roles_tags
roles_tags.add(user_id, "comerciante")
```

### Verificar un rol

```python
if "superadmin" in roles_tags.get(user_id):
    ...
```

### Quitar un rol

```python
roles_tags.remove(user_id, "comerciante")
```

Roles disponibles:

- `superadmin`: administrador del sitio
- `comerciante`: dueno de negocio
- `visitante`: usuario registrado sin negocio

---

## Uso

### Para visitantes

1. Accede a la pagina principal
2. Explora negocios y sus catalogos
3. Busca productos o negocios
4. Contacta al vendedor via WhatsApp o telefono

### Para comerciantes

1. Registrate en la aplicacion (`/auth/register`)
2. Al crear tu negocio, se te asigna automaticamente el rol "comerciante"
3. El negocio queda pendiente de aprobacion por el superadmin
4. Una vez aprobado, tu catalogo sera visible publicamente
5. Accede al panel de administracion para gestionar tu negocio
6. Agrega categorias y productos
7. Gestiona tu suscripcion

### Para superadministradores

1. Accede al panel de superadmin
2. Gestiona negocios (aprobacion, activacion/desactivacion)
3. Gestiona usuarios y roles
4. Valida pagos manuales
5. Configura parametros globales

---

## Modo Offline

La aplicacion implementa un **Service Worker** que proporciona:

- Cacheo automatico de paginas visitadas
- Cacheo de imagenes y recursos estaticos
- Cacheo del catalogo completo de cada negocio via API
- Funcionamiento sin conexion despues de la primera visita
- Sincronizacion en background cuando vuelve la conexion

### Como funciona

1. Al visitar un negocio, el catalogo se descarga y almacena en localStorage
2. Las imagenes se cachean automaticamente
3. Si pierdes conexion, la app sigue funcionando con datos locales
4. Al recuperar conexion, se sincronizan los datos automaticamente

### Instalacion como PWA

La aplicacion es una **Progressive Web App**. Se puede instalar en el movil:

1. Abre la aplicacion en Chrome (Android) o Safari (iOS).
2. Toca el menu y selecciona "Anadir a pantalla de inicio".
3. Aparecera un icono en el movil.

Ventajas:

- Carga instantanea (recursos cacheados)
- Funciona sin conexion
- No requiere tienda de aplicaciones

---

## Sistema de Pagos

### Metodos soportados

1. **Transfermovil**: el comerciante realiza la transferencia y registra el numero de operacion
2. **Pago presencial**: el comerciante coordina un pago en persona
3. **USDT (TRC20)**: pago con criptomoneda

### Flujo de validacion

1. Comerciante registra el pago en su panel
2. Superadmin ve el pago pendiente en su panel
3. Superadmin valida o rechaza el pago
4. Si se valida, la suscripcion se extiende 30 dias

---

## Base de datos

La aplicacion usa **SQLite** por defecto para facilitar el despliegue en entornos con recursos limitados.

Para usar **PostgreSQL**, cambia en `settings.py`:

```python
DB_URI = "postgres://usuario:password@localhost:5432/catalogocuba"
```

### Tablas principales

- `auth_user`: usuarios del sistema
- `auth_user_tag_roles`: roles (tags) asignados a cada usuario
- `negocio`: negocios registrados
- `categoria`: categorias de productos
- `producto`: productos del catalogo
- `suscripcion`: suscripciones de los negocios
- `pago`: registro de pagos
- `visita`: estadisticas de visitas
- `configuracion`: configuracion global
- `notificacion`: notificaciones a usuarios

py4web tambien crea automaticamente las tablas `auth_group`, `auth_membership`, `auth_permission`, `auth_event` y `auth_cas` al instanciar `Auth`, aunque no se usan en esta aplicacion (los roles se gestionan con Tags).

---

## Seguridad

- Autenticacion con `auth` de py4web
- Roles: superadmin, comerciante, visitante — gestionados con **Tags** de py4web
- Proteccion CSRF en formularios
- Validacion de propiedad de recursos
- Contrasenas hasheadas con el algoritmo por defecto de py4web
- Sesiones seguras con cookies firmadas
- La clave secreta debe configurarse como variable de entorno en produccion

---

## Optimizaciones para Cuba

- CSS inline critico para carga instantanea
- Compresion automatica de imagenes (75% calidad, max 600px)
- Service Worker para modo offline
- Paginacion de resultados
- Sin frameworks JS pesados (React, Angular, Vue)
- Sin dependencias de CDN externas
- Paginas ligeras (< 50KB HTML tipico)
- Cache agresivo de recursos estaticos
- Primera carga rapida, navegacion instantanea

---

## Despliegue en produccion

### Opcion 1: Servidor propio (VPS, Nube)

Advertencia: **no uses py4web directamente en el puerto 80**. Usa Nginx como reverse proxy (ver Opcion 3) y py4web en un puerto interno.

```bash
pip install -r requirements.txt
py4web run apps --host 127.0.0.1 --port 8000
```

Luego configura Nginx para hacer reverse proxy del puerto 8000.

### Opcion 2: Usando Gunicorn (recomendado para produccion)

Crea `wsgi.py` en la **raiz del proyecto** (no dentro de `apps/`):

```python
# proyecto/wsgi.py
import os
from py4web.core import wsgi

application = wsgi(path=os.path.join(os.path.dirname(__file__), "apps"))
```

Ejecuta:

```bash
pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
```

Luego configura Nginx como reverse proxy del puerto 8000.

### Opcion 3: Detras de Nginx (reverse proxy)

Configuracion de Nginx:

```nginx
server {
    listen 80;
    server_name tudominio.com;
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
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

### Permisos de carpetas

En despliegue, asegura permisos de escritura en `uploads/` y `databases/` para el usuario que ejecuta py4web:

```bash
chmod -R 775 apps/catalogo_cuba/uploads
chmod -R 775 apps/catalogo_cuba/databases
chown -R www-data:www-data apps/catalogo_cuba/uploads
chown -R www-data:www-data apps/catalogo_cuba/databases
```

### HTTPS

Usa Certbot con Let's Encrypt para habilitar HTTPS en produccion:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com
```

Con HTTPS habilitado, activa `SESSION_SECURE = True` en `settings.py` (o define la variable de entorno `CATALOGO_CUBA_SECURE=1`).

---

## .gitignore recomendado

```gitignore
__pycache__/
*.py[cod]
*.sqlite
*.sqlite-journal
databases/
uploads/*
!uploads/.gitkeep
!databases/.gitkeep
.DS_Store
.env
```

---

## Licencia

MIT License - Libre uso para la comunidad cubana.

---

## Soporte

Para reportar problemas o sugerir mejoras, contacta al equipo de desarrollo.

---

**CatalogoCuba** - Hecho con carino para los emprendedores cubanos.