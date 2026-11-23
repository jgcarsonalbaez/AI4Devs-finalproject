#!/usr/bin/env bash
# Levanta la base local con solo los servicios que usa el proyecto: la base,
# el servicio de autenticación y la API. Aplica las migraciones de
# supabase/migrations al arrancar. La usan la máquina y la integración continua,
# para que las dos levanten lo mismo.
#
# Uso:  bash scripts/base/levantar-base.sh
# Necesita Docker abierto y la herramienta supabase.
set -euo pipefail

if ! command -v supabase >/dev/null 2>&1; then
  echo "ERROR: no encuentro la herramienta supabase. Instálala y repite." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker no responde. Ábrelo y repite: la base local corre ahí." >&2
  exit 1
fi

# Servicios que no se usan: archivos, tiempo real, funciones, imágenes, panel,
# su API de metadatos, registros, el agrupador de conexiones y el buzón de prueba.
NO_SE_USAN="storage-api,realtime,edge-runtime,imgproxy,studio,postgres-meta,logflare,vector,supavisor,mailpit"

if ! supabase start -x "$NO_SE_USAN"; then
  echo "ERROR: la base local no arrancó. Si una migración falló, su mensaje está arriba." >&2
  exit 1
fi
echo "OK: base local arriba, con las migraciones aplicadas."
