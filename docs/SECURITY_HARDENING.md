# CatalogoCuba — seguridad y lógica de negocio

Rama de trabajo: `fix/security-business-logic`

## Cambios implementados

1. **Configuración de sesión** (`apps/catalogo_cuba/settings.py`)
   - Producción identificada con `CATALOGO_CUBA_ENV=production`.
   - No permite arrancar en producción o con debug desactivado si falta `CATALOGO_CUBA_SECRET`.
   - En desarrollo conserva una clave local explícitamente no apta para producción.
   - HTTPS/cookie segura activada por defecto en producción; puede configurarse con `CATALOGO_CUBA_SECURE`.
   - `CATALOGO_CUBA_UPLOAD_FOLDER` permite declarar un directorio de archivos explícito.

2. **Creación de pagos** (`controllers.py`)
   - Valida método, moneda y cantidad en el servidor.
   - Usa `Decimal` en lugar de `float` para importes monetarios.
   - Rechaza importes no numéricos, infinitos, no positivos o fuera de rango.
   - Agrupa el alta/actualización de suscripción y la creación del pago antes de confirmar; revierte en caso de error.
   - Los mensajes de error no exponen excepciones internas.

3. **Validación administrativa de pagos**
   - Acepta solo estados permitidos.
   - Impide volver a aplicar un pago que ya está validado.
   - Actualiza pago, suscripción y notificación en una misma unidad lógica con `commit/rollback`.
   - Valida que exista la suscripción antes de activar el servicio.

4. **Inventario**
   - Rechaza booleanos, cantidades no enteras y cantidades fuera del intervalo 0–1.000.000.
   - Los errores devueltos al cliente no incluyen detalles internos.

5. **Visibilidad pública**
   - El endpoint de detalle de producto exige negocio activo, aprobado y con suscripción vigente, igual que el catálogo.
   - Los productos no disponibles no se entregan desde ese endpoint.

6. **Archivos**
   - Resuelve la ruta real y verifica que permanezca dentro del directorio de uploads.
   - Solo entrega extensiones de imagen permitidas y añade `X-Content-Type-Options: nosniff`.

7. **Slug de producto**
   - En edición, comprueba colisiones dentro del negocio y excluye el propio producto de la comprobación.
   - Genera sufijos deterministas si otro producto usa el slug.

8. **Higiene del repositorio**
   - Añade `.gitignore` para secretos, bases de datos locales, cargas privadas y artefactos Python.

## Configuración de producción

Configura al menos:

- `CATALOGO_CUBA_ENV=production`
- `CATALOGO_CUBA_DEBUG=0`
- `CATALOGO_CUBA_SECRET` con una clave criptográficamente aleatoria y privada
- `CATALOGO_CUBA_SECURE=1` cuando el sitio se publique detrás de HTTPS
- `CATALOGO_CUBA_DB_URI` y `CATALOGO_CUBA_UPLOAD_FOLDER` según el despliegue

No guardes estos valores en el repositorio. Haz una copia de seguridad de la base de datos y de uploads antes de desplegar.

## Verificación y limitaciones

- Se inspeccionaron los archivos originales de la rama principal y se aplicaron cambios sobre una rama separada.
- Se verificaron los puntos de inserción de los cambios mediante comparación textual contra el contenido recuperado de GitHub.
- **No** se ejecutó la aplicación en un entorno py4web ni se corrieron pruebas de integración o de penetración desde este cambio.
- Los cambios de lógica de negocio necesitan pruebas automatizadas y revisión humana antes de fusionar.
- La transacción de DAL está protegida por `commit/rollback`; no sustituye una prueba concurrente en el motor de base de datos.
- La protección CSRF, el control completo de propiedad para todas las rutas, la política de privacidad de uploads, el límite de frecuencia y la zona horaria siguen requiriendo una auditoría integral.
- Los importes siguen siendo introducidos por el formulario; para impedir subpagos, el importe exigible debe calcularse en servidor según el plan y la moneda elegidos, antes de aceptar el pago.

## Próximos pasos recomendados

1. Añadir pruebas automatizadas para autorización por propietario, pagos duplicados, estados no permitidos, importe inválido, inventario y traversal de rutas.
2. Revisar todas las rutas POST y protección CSRF.
3. Validar el importe exigible desde configuración de servidor, no confiar en el importe enviado por el cliente.
4. Auditar la unicidad de slug en la base de datos y corregir los datos históricos duplicados antes de añadir restricciones.
5. Completar la PWA offline y la sincronización idempotente como fase independiente.
