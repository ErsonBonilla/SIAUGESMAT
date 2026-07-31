# Certificados SSL

## Desarrollo

Ejecutar desde la raíz del proyecto:

```bash
bash certs/generate-dev-certs.sh
```

El script genera `fullchain.pem` y `privkey.pem` autofirmados (válidos 825 días
por defecto) e incluye **Subject Alternative Names (SANs)** para:

- `DNS:localhost` y `IP:127.0.0.1`
- Las IPs locales del host (detectadas automáticamente)
- Un hostname público opcional (ver abajo)

Esto evita el error de "CN mismatch" al acceder por IP o por el nombre del
servidor. Requiere OpenSSL >= 1.1.1.

### Incluir un hostname público

```bash
bash certs/generate-dev-certs.sh siaugesmat.ut.edu.co
```

O mediante variable de entorno:

```bash
DOMAIN=siaugesmat.ut.edu.co bash certs/generate-dev-certs.sh
```

### Aplicar los certificados

```bash
docker compose restart nginx
```

> En Windows PowerShell puede generar los certs con Docker (si no hay OpenSSL
> local), usando los mismos parámetros:
> ```bash
> docker run --rm -v "${PWD}/certs:/certs" alpine/openssl req -x509 -nodes \
>   -days 825 -newkey rsa:2048 -keyout /certs/privkey.pem -out /certs/fullchain.pem \
>   -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
> ```

## Producción

Reemplazar los archivos `certs/fullchain.pem` y `certs/privkey.pem` con
certificados reales emitidos por una CA (Let's Encrypt, DigiCert, etc.):

1. Colocar el certificado y su cadena en `certs/fullchain.pem`.
2. Colocar la clave privada en `certs/privkey.pem`.
3. Aplicar los cambios:

   ```bash
   docker compose restart nginx
   ```

El directorio `certs/` está en `.gitignore` — no se comitean certificados.

> **Renovación:** si se usa Let's Encrypt, configurar la renovación automática
> (p. ej. un cron que ejecute `certbot renew` y luego `docker compose exec nginx
> nginx -s reload`).
