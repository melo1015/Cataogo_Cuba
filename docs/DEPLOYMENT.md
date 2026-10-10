# Despliegue de CatalogoCuba

Esta guía prepara la configuración, pero **no sustituye una prueba en el proveedor de hosting elegido**. El repositorio se mantiene en py4web.

## 1. Requisitos

- Python 3.8 o superior (CI actual usa Python 3.11).
- Dependencias instaladas desde `apps/catalogo_cuba/requirements.txt`.
- Un proceso de py4web que cargue el directorio `apps`.
- HTTPS terminado en el proveedor o proxy inverso.
- Volumen persistente para la base de datos y los archivos subidos.

## 2. Variables obligatorias

Configurar como variables de entorno en el panel del proveedor; no escribir secretos en el repositorio:

| Variable | Producción |
| --- | --- |
| `CATALOGO_CUBA_ENV` | `production` |
| `CATALOGO_CUBA_DEBUG` | `0` |
| `CATALOGO_CUBA_SECRET` | Secreto aleatorio largo y único |
| `CATALOGO_CUBA_SECURE` | `1` |
| `CATALOGO_CUBA_DB_URI` | URI de una base de datos persistente |
| `CATALOGO_CUBA_UPLOAD_FOLDER` | Ruta persistente para uploads |

Generar el secreto localmente con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

No compartir el secreto ni guardarlo en Git. Si se cambia después de publicar, las sesiones existentes pueden invalidarse.

## 3. Persistencia

La aplicación guarda estado en la base de datos y en el directorio de imágenes. Ambos deben sobrevivir a despliegues y reinicios. No usar un sistema de archivos efímero para esos datos.

SQLite puede servir para una primera instancia de bajo tráfico **con un solo proceso/escritor y almacenamiento persistente fiable**. Antes de escalar a varias réplicas o concurrencia elevada, migrar y probar una base de datos cliente-servidor compatible con pyDAL. Hacer una copia de seguridad y ensayar la restauración antes de migraciones.

## 4. Antes de aceptar usuarios o pagos

- Confirmar que el dominio redirige todo HTTP a HTTPS.
- Configurar el servidor/proxy para que py4web reciba la URL como HTTPS (esquema WSGI `https`); py4web decide el atributo `Secure` de la cookie a partir del esquema de la petición. No basta con que el certificado SSL esté solo en el proxy si el tráfico interno hace que py4web vea HTTP. Verificar en el navegador que las cookies llevan `Secure`, `HttpOnly` y `SameSite=Lax`.
- Crear el primer superadministrador mediante un procedimiento controlado; no exponer una ruta pública para asignar ese rol.
- Probar registro, login/logout, recuperación de contraseña, autorización por propietario, CRUD de productos, pedidos, pagos y aprobación administrativa con cuentas de prueba.
- Comprobar que las solicitudes POST maliciosas o anónimas se rechazan y que los errores 4xx/5xx no muestran trazas.
- Probar carga de imágenes, límites de tamaño, reinicio del servicio y persistencia de imágenes/base de datos.
- Probar una copia de seguridad y restauración.
- Configurar logs y alertas sin registrar contraseñas, cookies, secretos ni datos sensibles innecesarios.

## 5. Limitaciones conocidas antes de producción

- El pago se registra y valida manualmente; no existe confirmación automática de Transfermóvil/USDT por un proveedor financiero.
- El Service Worker puede cachear recursos, pero eso no demuestra sincronización offline completa ni entrega garantizada de pedidos. Probar la cola offline en dispositivos reales antes de anunciar esa función.
- CI valida sintaxis, importación, esquema y algunas rutas HTTP; no reemplaza pruebas completas de roles, CSRF, concurrencia ni pruebas de penetración.
- El endpoint de estado/health y las métricas de operación deben configurarse según el proveedor; no se debe marcar el servicio como listo solo porque el proceso arrancó.
