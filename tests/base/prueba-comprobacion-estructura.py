#!/usr/bin/env python3
"""
Prueba de la comprobación de estructura (HU-03.1): un caso que debe pasar y
uno que debe fallar por cada regla del requisito «Separación por organización
en la base» (openspec/specs/acceso/spec.md).

Cada caso corre dentro de una transacción que se deshace al final: crea el
objeto del caso, corre supabase/comprobaciones/estructura.sql y vuelve todo
atrás. No deja nada en la base.

Necesita la base local levantada (`supabase start`) con las migraciones
aplicadas.

Uso:  python3 tests/base/prueba-comprobacion-estructura.py
Sale con 0 si todos los casos dan lo esperado, y con 1 si alguno falla.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "base"))
from base_local import psql  # noqa: E402

COMPROBACION = RAIZ / "supabase" / "comprobaciones" / "estructura.sql"

# Una tabla bien hecha: organización obligatoria, reglas activadas y forzadas,
# su regla restrictiva por organización para todo y para todos, y sin el
# TRUNCATE que la plataforma da por defecto a las personas.
BIEN = """
create table public.prueba_bien (id uuid primary key, organizacion_id uuid not null);
revoke truncate, trigger, references on public.prueba_bien from anon, authenticated;
alter table public.prueba_bien enable row level security;
alter table public.prueba_bien force row level security;
create policy prueba_bien_organizacion on public.prueba_bien as restrictive for all to public
  using (public.es_mi_organizacion(organizacion_id))
  with check (public.es_mi_organizacion(organizacion_id));
"""

# (nombre, preparación, None si debe pasar o (objeto, motivo) que debe aparecer)
CASOS = [
    ("P1 la base tal como queda tras las migraciones", "", None),
    ("P2 una tabla nueva bien hecha", BIEN, None),
    ("P3 una vista que consulta con los permisos de quien la usa",
     "create view public.prueba_vista with (security_invoker = true) as select id from public.organizacion;", None),
    ("P4 una función con los permisos de quien la llama",
     "create function public.prueba_invocador() returns int language sql as 'select 1';", None),

    ("N1 tabla sin organizacion_id",
     "create table public.prueba_mala (id uuid primary key);",
     ("public.prueba_mala", "sin-organizacion_id")),
    ("N2 organizacion_id que admite nulo",
     BIEN.replace("organizacion_id uuid not null", "organizacion_id uuid"),
     ("public.prueba_bien", "organizacion_id-admite-nulo")),
    ("N3 reglas sin activar",
     BIEN.replace("alter table public.prueba_bien enable row level security;", ""),
     ("public.prueba_bien", "reglas-no-activadas")),
    ("N4 reglas activadas pero no forzadas para el dueño",
     BIEN.replace("alter table public.prueba_bien force row level security;", ""),
     ("public.prueba_bien", "reglas-no-forzadas")),
    ("N5 sin ninguna regla",
     BIEN.split("create policy")[0],
     ("public.prueba_bien", "sin-regla-restrictiva")),
    ("N6 la regla por organización es permisiva, no restrictiva",
     BIEN.replace("as restrictive", "as permissive"),
     ("public.prueba_bien", "sin-regla-restrictiva")),
    ("N7 la regla restrictiva vale solo para leer",
     BIEN.replace("for all", "for select").replace(
         "\n  with check (public.es_mi_organizacion(organizacion_id))", ""),
     ("public.prueba_bien", "sin-regla-restrictiva")),
    ("N8 la regla restrictiva vale solo para un rol",
     BIEN.replace("to public", "to authenticated"),
     ("public.prueba_bien", "sin-regla-restrictiva")),
    ("N9 la regla deja escribir en cualquier organización",
     BIEN.replace("with check (public.es_mi_organizacion(organizacion_id))", "with check (true)"),
     ("public.prueba_bien", "sin-regla-restrictiva")),
    ("N10 la regla compara otra columna",
     BIEN.replace("using (public.es_mi_organizacion(organizacion_id))", "using (public.es_mi_organizacion(id))"),
     ("public.prueba_bien", "sin-regla-restrictiva")),
    ("N11 tabla en un esquema nuevo",
     "create schema prueba_otro; create table prueba_otro.t (id int);",
     ("prueba_otro.t", "sin-organizacion_id")),
    ("N12 tabla particionada sin organización",
     "create table public.prueba_part (id int, d date) partition by range (d);",
     ("public.prueba_part", "sin-organizacion_id")),
    ("N13 vista con los permisos de su dueño",
     "create view public.prueba_vista as select id from public.organizacion;",
     ("public.prueba_vista", "vista-sin-permisos-de-quien-consulta")),
    ("N14 vista materializada",
     "create materialized view public.prueba_mat as select id from public.organizacion;",
     ("public.prueba_mat", "vista-materializada")),
    ("N15 función con los privilegios de su dueño fuera de la lista",
     "create function public.prueba_definer() returns int language sql security definer as 'select 1';",
     ("public.prueba_definer()", "funcion-con-privilegios-del-dueno-fuera-de-lista")),
    ("N16 función de la lista con otra firma",
     "create function public.sesion_abierta(x int) returns boolean language sql security definer "
     "as 'select false';",
     ("public.sesion_abierta(integer)", "funcion-con-privilegios-del-dueno-fuera-de-lista")),
    ("N17 procedimiento con los privilegios de su dueño",
     "create procedure public.prueba_proc() language sql security definer as 'select 1';",
     ("public.prueba_proc()", "funcion-con-privilegios-del-dueno-fuera-de-lista")),
    # N18 y N19: solo el superusuario de la base local puede fabricar ese estado.
    ("N18 el rol de las personas es dueño de una tabla",
     BIEN + "alter table public.prueba_bien owner to authenticated;",
     ("public.prueba_bien", "rol-de-personas-es-dueno")),
    ("N19 el rol de las personas puede omitir las reglas",
     "alter role authenticated bypassrls;",
     ("authenticated", "rol-de-personas-omite-reglas")),
    ("N22 el rol de las personas puede vaciar una tabla (TRUNCATE no pasa por las reglas)",
     "grant truncate on public.organizacion to authenticated;",
     ("public.organizacion", "rol-de-personas-omite-reglas")),
    ("N23 sin sesión se puede vaciar una tabla",
     BIEN + "grant truncate on public.prueba_bien to anon;",
     ("public.prueba_bien", "rol-de-personas-omite-reglas")),
    ("N20 la regla de organizacion ya no compara su id",
     "drop policy organizacion_separacion on public.organizacion;"
     "create policy organizacion_separacion on public.organizacion as restrictive for all to public "
     "using (true) with check (true);",
     ("public.organizacion", "sin-regla-restrictiva")),
    ("N21 organizacion sin reglas forzadas",
     "alter table public.organizacion no force row level security;",
     ("public.organizacion", "reglas-no-forzadas")),
]


COMO_SUPERUSUARIO = {"N18", "N19"}


def correr(nombre: str, preparacion: str):
    """Devuelve (fallas, resumen, error) de correr la comprobación tras la preparación."""
    sql = f"begin;\n{preparacion}\n{COMPROBACION.read_text(encoding='utf-8')}\nrollback;\n"
    usuario = "supabase_admin" if nombre.split()[0] in COMO_SUPERUSUARIO else "postgres"
    r = psql(sql, usuario=usuario)
    if r.returncode != 0:
        return None, None, r.stderr.strip()
    fallas, resumen = set(), None
    for linea in r.stdout.splitlines():
        partes = linea.split("\t")
        if partes[0] == "FALLA" and len(partes) >= 3:
            fallas.add((partes[1], partes[2]))
        elif partes[0] == "RESUMEN":
            resumen = linea
    return fallas, resumen, None


def main() -> int:
    if not COMPROBACION.is_file():
        print(f"FALLA: no existe {COMPROBACION.relative_to(RAIZ)}.")
        return 1
    malos = 0
    for nombre, preparacion, esperado in CASOS:
        fallas, resumen, error = correr(nombre, preparacion)
        if error is not None:
            malos += 1
            print(f"✗ {nombre}: la base rechazó el caso.\n  {error}")
            continue
        if resumen is None:
            malos += 1
            print(f"✗ {nombre}: la comprobación no dio su línea RESUMEN.")
            continue
        if esperado is None:
            ok = not fallas
            detalle = "sin fallas" if ok else f"fallas inesperadas: {sorted(fallas)}"
        else:
            ok = esperado in fallas
            detalle = f"detecta {esperado}" if ok else f"no detecta {esperado}; dio {sorted(fallas)}"
        malos += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {nombre}: {detalle}")
    total = len(CASOS)
    print(f"prueba-comprobacion-estructura: {total - malos} de {total} casos dan lo esperado.")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
