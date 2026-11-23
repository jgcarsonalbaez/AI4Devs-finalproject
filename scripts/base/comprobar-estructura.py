#!/usr/bin/env python3
"""
Corre la comprobación de estructura (supabase/comprobaciones/estructura.sql)
contra la base local y falla si alguna tabla de negocio no cumple el
requisito «Separación por organización en la base» (HU-03.1).

Uso:  python3 scripts/base/comprobar-estructura.py
Sale con 0 si no hay fallas, y con 1 si hay alguna o si la comprobación no
dio su línea de resumen (una comprobación que no recorrió nada no comprueba).
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base_local import psql_ok  # noqa: E402

COMPROBACION = RAIZ / "supabase" / "comprobaciones" / "estructura.sql"


def main() -> int:
    salida = psql_ok(COMPROBACION.read_text(encoding="utf-8"))
    fallas, resumen = [], None
    for linea in salida.splitlines():
        partes = linea.split("\t")
        if partes[0] == "FALLA" and len(partes) == 4:
            fallas.append(partes[1:])
        elif partes[0] == "RESUMEN":
            resumen = " · ".join(partes[1:])
    if resumen is None:
        print("ERROR: la comprobación de estructura no dio su línea de resumen; no se sabe qué recorrió.")
        return 1
    for objeto, motivo, explicacion in fallas:
        print(f"  ✗ {objeto} [{motivo}]: {explicacion}")
    if fallas:
        print(f"comprobar-estructura: {len(fallas)} fallas ({resumen}).")
        return 1
    print(f"comprobar-estructura: sin fallas ({resumen}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
