# Despliegue seguro de Catálogo Cuba en VPS con Nginx

Esta guía complementa los controles de la aplicación. La configuración es una plantilla: debe adaptarse al dominio, certificados y método real de arranque de py4web antes de producción.

## 1. Arquitectura mínima

- Internet → Nginx en puertos TCP 80/443 → py4web en `127.0.0.1:8000`.
- El proceso py4web no debe escuchar en `0.0.0.0` ni tener su puerto publicado al exterior.
- Mantener base de datos, sesiones y uploads en almacenamiento persistente; restringir sus permisos al usuario del servicio.
- No habilitar acceso SSH por contraseña si puede utilizarse una clave pública; restringir SSH por firewall a las IP administrativas cuando sea viable.

## 2. Instalar la configuración Nginx

1. Instalar y mantener Nginx desde los repositorios de seguridad de la distribución.
2. Copiar `deploy/nginx/catalogo-cuba-limits.conf` a `/etc/nginx/conf.d/catalogo-cuba-limits.conf`. Este archivo debe cargarse dentro del contexto `http {}`, como sucede normalmente con `conf.d/*.conf` en Debian/Ubuntu.
3. Copiar `deploy/nginx/catalogo-cuba-site.conf.example` a un archivo de sitio habilitado. Cambiar `catalogo.example.com` por el dominio real y confirmar que las rutas del certificado existen. No activar la plantilla sin certificado válido.
4. Configurar py4web para escuchar solo en `127.0.0.1:8000`, o actualizar el upstream si se utiliza un socket privado.
5. Comprobar sintaxis y recargar, en ese orden:

   ```sh
   sudo nginx -t
   sudo systemctl reload nginx
   ```

6. Verificar desde otra máquina que solo los puertos previstos son accesibles y que el puerto de py4web no responde directamente desde Internet.

## 3. Proxy confiable y cabeceras de IP

La plantilla establece `X-Forwarded-For $remote_addr`, reemplazando el valor que pudiera enviar el visitante. Si Nginx y py4web están en el mismo VPS y Nginx conecta a `127.0.0.1:8000`, configurar el entorno de la aplicación con:

```sh
CATALOGO_CUBA_TRUSTED_PROXY_IPS=127.0.0.1
```

La variable debe contener la IP que py4web realmente ve en `REMOTE_ADDR`, no la IP pública del visitante. Confirmarlo en un entorno de prueba antes de producción. Si el upstream es un contenedor, una IP privada distinta o un socket, configurar el valor acorde a esa topología. No confiar en rangos amplios ni en `X-Forwarded-For` recibido directamente desde Internet.

Si se añade Cloudflare u otro proxy delante de Nginx, no reutilizar esta configuración sin diseñar y verificar explícitamente la cadena de confianza: configurar el módulo real-ip únicamente para rangos oficiales de ese proveedor, bloquear el acceso directo cuando proceda y evitar que clientes puedan falsificar la IP efectiva.

## 4. Límites de solicitudes y cuerpos

- Las APIs usan una zona compartida de Nginx con límite inicial de 10 solicitudes/s por IP y ráfaga de 30.
- Login, registro y recuperación de contraseña bajo `/catalogo_cuba/auth/` tienen un límite inicial de 5 solicitudes/minuto por IP, con ráfaga de 5.
- La creación pública de pedidos usa un límite inicial de 2 solicitudes/s por IP, ráfaga de 6 y un cuerpo máximo de 64 KiB.
- El resto de la aplicación permite cuerpos de hasta 3 MiB para que los uploads legítimos no queden bloqueados por el límite de pedidos; la aplicación mantiene su propio máximo de 2 MiB por imagen.
- Nginx devuelve HTTP 429 al aplicar limitación. Ajustar las tasas según logs y carga real para no bloquear usuarios legítimos detrás de una misma IP compartida; en especial, los límites de autenticación pueden afectar a personas que comparten una IP móvil o NAT.
- Estos límites se aplican en Nginx; no sustituyen cuotas de negocio, autorización, validación ni idempotencia en la aplicación.

## 5. Variables obligatorias de producción

Configurar en el entorno protegido del servicio (no versionar secretos):

```sh
CATALOGO_CUBA_ENV=production
CATALOGO_CUBA_DEBUG=0
CATALOGO_CUBA_SECRET=<secreto-aleatorio-largo>
CATALOGO_CUBA_TRUSTED_PROXY_IPS=127.0.0.1
CATALOGO_CUBA_DB_URI=<URI-de-base-de-datos-persistente>
CATALOGO_CUBA_UPLOAD_FOLDER=<directorio-persistente-y-privado>
```

Generar un secreto criptográficamente aleatorio con un gestor de secretos o herramienta del sistema. No poner el secreto real en el repositorio, en imágenes de contenedor, en comandos guardados en el historial ni en logs. La URI de base de datos y la ruta de uploads deben coincidir con los volúmenes persistentes del despliegue. Verificar el proceso de migraciones y realizar una copia de seguridad antes de la primera actualización de esquema en producción.

## 6. Firewall, actualizaciones y copias

- Permitir 80/443 desde Internet y SSH solo según la política administrativa; bloquear el puerto de py4web.
- Mantener el sistema, Python, py4web, dependencias y Nginx actualizados.
- Ejecutar la aplicación con usuario de sistema sin privilegios; no ejecutarla como root.
- Restringir permisos de archivos de configuración y secretos.
- Respaldar base de datos y uploads; cifrar copias externas y probar restauraciones periódicamente.
- Supervisar errores 4xx/5xx, reinicios, espacio en disco y uso de memoria. No registrar contraseñas, cookies, tokens ni cuerpos de pedidos.

## 7. Verificación antes de abrir el servicio

- [ ] `nginx -t` pasa y el certificado HTTPS es válido.
- [ ] HTTP redirige a HTTPS.
- [ ] El puerto py4web no es accesible desde fuera del VPS.
- [ ] Cabeceras `X-Forwarded-For` falsas no alteran la IP del cliente.
- [ ] Una petición de pedido de más de 64 KiB recibe 413.
- [ ] El exceso de solicitudes recibe 429 y no afecta excesivamente a clientes legítimos.
- [ ] Las APIs privadas no se cachean públicamente.
- [ ] Las migraciones de la base de datos y la restauración de backups se han probado.
- [ ] Las pruebas funcionales, de autorización y PWA pasan en CI y se completa una prueba manual con navegador.

## Nota sobre los límites

Las tasas de Nginx son valores iniciales, no un resultado de pruebas de carga. La limitación por IP puede agrupar a muchos usuarios que comparten NAT o redes móviles. Revisar métricas y ajustar después de pruebas controladas. Esta guía no certifica por sí sola que el VPS esté endurecido ni que el despliegue esté listo para producción.
