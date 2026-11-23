#!/usr/bin/env python3
"""
Corre todas las validaciones 1 a 1 de supabase/validaciones/ contra la base
local y falla si alguna fila no dice OK.

Cada validación es de solo lectura y devuelve filas con cuatro columnas:
objeto · esperado · encontrado · estado (OK o FALLA). Una validación que no
devuelve ninguna fila también hace fallar: una validación vacía no valida.

Uso:  python3 scripts/base/correr-validaciones.py [fichero.sql ...]
Sin argumentos corre todas, en orden de nombre. Sale con 0 si todo está OK.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base_local import psql_ok  # noqa: E402

CARPETA = RAIZ / "supabase" / "validaciones"


def validar(fichero: Path) -> tuple[int, int, list[str]]:
    """Devuelve (filas, fallas, líneas para mostrar) de una validación."""
    salida = psql_ok(fichero.read_text(encoding="utf-8"))
    filas = [linea.split("\t") for linea in salida.splitlines() if linea.strip()]
    mostrar, fallas = [], 0
    for fila in filas:
        if len(fila) != 4:
            fallas += 1
            mostrar.append(f"  ✗ fila mal formada (se esperaban 4 columnas): {fila}")
            continue
        objeto, esperado, encontrado, estado = fila
        if estado == "OK":
            mostrar.append(f"  ✓ {objeto}")
        else:
            fallas += 1
            mostrar.append(f"  ✗ {objeto}\n      esperado:   {esperado}\n      encontrado: {encontrado}")
    return len(filas), fallas, mostrar


def main(argumentos: list[str]) -> int:
    ficheros = [Path(a) for a in argumentos] or sorted(CARPETA.glob("*.sql"))
    if not ficheros:
        print(f"ERROR: no hay validaciones en {CARPETA.relative_to(RAIZ)}.")
        return 1
    total_fallas = 0
    for f in ficheros:
        filas, fallas, mostrar = validar(f)
        print(f"{f.name}:")
        print("\n".join(mostrar))
        if filas == 0:
            fallas += 1
            print("  ✗ la validación no devolvió ninguna fila")
        total_fallas += fallas
    if total_fallas:
        print(f"correr-validaciones: {total_fallas} comprobaciones no coinciden con la spec.")
        return 1
    print(f"correr-validaciones: {len(ficheros)} validaciones, todas sus filas OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
