#!/bin/bash
set -euo pipefail

# Genera certificados autofirmados para desarrollo con Subject Alternative
# Names (SANs) que cubren localhost, 127.0.0.1 y las IPs locales del host,
# de modo que el navegador no falle por CN mismatch al acceder por IP.
#
# Uso:
#   bash certs/generate-dev-certs.sh [DOMAIN]
#
# Variables de entorno:
#   DOMAIN   Hostname público adicional a incluir como SAN (opcional).
#   DAYS     Validez en días (default: 825).
#
# Requiere OpenSSL >= 1.1.1 (soporte para -addext).

CERT_DIR="$(cd "$(dirname "$0")" && pwd)"
DAYS="${DAYS:-825}"
DOMAIN="${1:-${DOMAIN:-}}"
CN="${DOMAIN:-localhost}"

# Detectar IPs del host (Linux: hostname -I; macOS/BSD: ifconfig)
IPS="127.0.0.1"
if command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
  for ip in $(hostname -I); do
    case "$ip" in
      *.*.*.*) IPS="$IPS $ip" ;;
    esac
  done
elif command -v ifconfig >/dev/null 2>&1; then
  for ip in $(ifconfig | awk '/inet / {print $2}' | grep -v '^127\.'); do
    IPS="$IPS $ip"
  done
fi

# Construir lista de SANs (deduplicada)
SANS="DNS:localhost,IP:127.0.0.1"
for ip in $IPS; do
  [ "$ip" = "127.0.0.1" ] && continue
  case ",$SANS," in
    *",IP:$ip,"*) ;;
    *) SANS="$SANS,IP:$ip" ;;
  esac
done
if [ -n "$DOMAIN" ]; then
  SANS="$SANS,DNS:$DOMAIN"
fi

echo "Generando certificado autofirmado..."
echo "  CN:    $CN"
echo "  SANs:  $SANS"
echo "  Validez: $DAYS días"

openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/C=CO/ST=Tolima/L=Ibague/O=SIAUGESMAT/CN=$CN" \
  -addext "subjectAltName=$SANS"

echo
echo "Certificados generados en: $CERT_DIR"
echo "  - $CERT_DIR/privkey.pem"
echo "  - $CERT_DIR/fullchain.pem"
echo
echo "Reiniciar nginx para aplicarlos:"
echo "  docker compose restart nginx"
