#!/usr/bin/env python3
"""
Prueba de la validación 1 a 1 de la migración de organizacion (HU-03.1): la
base tal como queda debe dar todo OK, y cada desvío de la spec debe aparecer
como FALLA en su fila.

Cada desvío se hace dentro de una transacción que se deshace al final. No
deja nada en la base. Necesita la base local levantada con las migraciones.

Uso:  python3 tests/base/prueba-validacion-organizacion.py
Sale con 0 si todos los casos dan lo esperado, y con 1 si alguno falla.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "base"))
from base_local import psql  # noqa: E402

VALIDACION = RAIZ / "supabase" / "validaciones" / "20261123170000_organizacion.sql"

# (nombre, desvío, None si todo debe dar OK o la fila que debe dar FALLA)
CASOS = [
    ("P1 la base tal como queda tras la migración", "", None),
    ("N1 una columna de más",
     "alter table public.organizacion add column extra text;", "columnas de public.organizacion"),
    ("N2 nombre admite nulo",
     "alter table public.organizacion alter column nombre drop not null;", "columna nombre"),
    ("N3 otro valor por defecto de sesion_dias",
     "alter table public.organizacion alter column sesion_dias set default 10;", "columna sesion_dias"),
    ("N4 zona_horaria con valor por defecto",
     "alter table public.organizacion alter column zona_horaria set default 'UTC';", "columna zona_horaria"),
    ("N5 sin la comprobación de la zona",
     "alter table public.organizacion drop constraint organizacion_zona_horaria_check;",
     "constraints de public.organizacion"),
    ("N6 la comprobación de sesion_dias con otro límite",
     "alter table public.organizacion drop constraint organizacion_sesion_dias_check;"
     "alter table public.organizacion add constraint organizacion_sesion_dias_check check (sesion_dias >= 0);",
     "constraint organizacion_sesion_dias_check"),
    ("N7 reglas sin forzar",
     "alter table public.organizacion no force row level security;", "reglas de public.organizacion"),
    ("N8 la regla pasa a permisiva",
     "drop policy organizacion_separacion on public.organizacion;"
     "create policy organizacion_separacion on public.organizacion as permissive for all to public "
     "using (public.es_mi_organizacion(id)) with check (public.es_mi_organizacion(id));",
     "regla organizacion_separacion"),
    ("N9 una regla de más",
     "create policy otra on public.organizacion for select to authenticated using (true);",
     "reglas sobre public.organizacion"),
    ("N10 sesion_abierta pierde los privilegios de su dueño",
     "alter function public.sesion_abierta() security invoker;", "función public.sesion_abierta()"),
    ("N11 anon puede ejecutar sesion_abierta",
     "grant execute on function public.sesion_abierta() to anon;", "quién ejecuta public.sesion_abierta()"),
    ("N12 es_mi_organizacion sin search_path fijo",
     "alter function public.es_mi_organizacion(uuid) reset search_path;",
     "función public.es_mi_organizacion(uuid)"),
    ("N13 es_zona_horaria deja de ser inmutable",
     "alter function public.es_zona_horaria(text) stable;", "función public.es_zona_horaria(text)"),
]


def correr(desvio: str):
    r = psql(f"begin;\n{desvio}\n{VALIDACION.read_text(encoding='utf-8')}\nrollback;\n")
    if r.returncode != 0:
        return None, r.stderr.strip()
    filas = {}
    for linea in r.stdout.splitlines():
        partes = linea.split("\t")
        if len(partes) == 4:
            filas[partes[0]] = partes[3]
    return filas, None


def main() -> int:
    if not VALIDACION.is_file():
        print(f"FALLA: no existe {VALIDACION.relative_to(RAIZ)}.")
        return 1
    malos = 0
    for nombre, desvio, fila in CASOS:
        filas, error = correr(desvio)
        if error is not None:
            malos += 1
            print(f"✗ {nombre}: la base rechazó el caso.\n  {error}")
            continue
        fallas = sorted(k for k, v in filas.items() if v != "OK")
        if not filas:
            ok, detalle = False, "la validación no devolvió filas"
        elif fila is None:
            ok = not fallas
            detalle = "todo OK" if ok else f"fallas inesperadas: {fallas}"
        else:
            ok = filas.get(fila) == "FALLA"
            detalle = f"marca «{fila}»" if ok else f"no marca «{fila}»; marcó {fallas}"
        malos += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {nombre}: {detalle}")
    print(f"prueba-validacion-organizacion: {len(CASOS) - malos} de {len(CASOS)} casos dan lo esperado.")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
