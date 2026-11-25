#!/usr/bin/env python3
"""
Prueba de la validación 1 a 1 de la migración del modelo del aviso (HU-06.1,
tramo 4): la base tal como queda debe dar todo OK, y cada desvío de la spec
debe aparecer como FALLA en su fila. Misma forma que
tests/base/prueba-validacion-usuario.py.

Cada desvío se hace dentro de una transacción que se deshace al final, como
superusuario de la base local. No deja nada en la base.

Uso:  python3 tests/base/prueba-validacion-aviso-modelo.py
Sale con 0 si todos los casos dan lo esperado, y con 1 si alguno falla.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "base"))
from base_local import psql  # noqa: E402

VALIDACION = RAIZ / "supabase" / "validaciones" / "20261125170000_aviso_modelo.sql"
PERSONAS = "privilegios de anon y authenticated sobre las tres tablas"

# (nombre, desvío, None si todo debe dar OK o la fila que debe dar FALLA)
CASOS = [
    ("P1 la base tal como queda tras la migración", "", None),
    ("N1 falta una tabla", "drop table public.aviso_inicio;", "tablas cliente, asignacion y aviso_inicio"),
    ("N2 la zona del cliente admite nulo", "alter table public.cliente alter column zona_horaria drop not null;",
     "columnas de public.cliente"),
    ("N3 el alias deja de ser único en la organización",
     "alter table public.cliente drop constraint cliente_organizacion_id_alias_key;", "constraints de public.cliente"),
    ("N4 la fecha de fin pasa a ser obligatoria", "alter table public.asignacion alter column fin set not null;",
     "columnas de public.asignacion"),
    ("N5 los días laborables nacen con otro valor por defecto",
     "alter table public.asignacion alter column dias_laborables set default '{1,2,3,4,5,6}';",
     "columnas de public.asignacion"),
    ("N6 el consultor puede ser de otra organización",
     "alter table public.asignacion drop constraint asignacion_consultor_fkey;"
     "alter table public.asignacion add constraint asignacion_consultor_fkey foreign key (consultor_id) "
     "references public.usuario (id);", "constraints de public.asignacion"),
    ("N7 el horario admite fin igual a inicio",
     "alter table public.asignacion drop constraint asignacion_horario_check;"
     "alter table public.asignacion add constraint asignacion_horario_check check (hora_fin >= hora_inicio);",
     "constraints de public.asignacion"),
    ("N8 minutos_retraso pasa a ser obligatorio",
     "alter table public.aviso_inicio alter column minutos_retraso set not null;", "columnas de public.aviso_inicio"),
    ("N9 sin el único aviso por asignación y día",
     "alter table public.aviso_inicio drop constraint aviso_inicio_asignacion_id_fecha_key;",
     "constraints de public.aviso_inicio"),
    ("N10 la función de los días deja de ser inmutable",
     "alter function public.dias_laborables_validos(smallint[]) stable;",
     "función public.dias_laborables_validos(smallint[])"),
    ("N11 el bloqueo del aviso corre con privilegios de su dueño",
     "alter function public.impedir_cambio_de_aviso() security definer;", "función public.impedir_cambio_de_aviso()"),
    ("N12 el bloqueo del aviso apagado", "alter table public.aviso_inicio disable trigger aviso_inicio_no_se_cambia;",
     "disparadores de public.aviso_inicio"),
    ("N13 sin el bloqueo de vaciar la tabla", "drop trigger aviso_inicio_no_se_vacia on public.aviso_inicio;",
     "disparadores de public.aviso_inicio"),
    ("N14 reglas sin forzar en asignacion", "alter table public.asignacion no force row level security;",
     "reglas de las tres tablas, activadas y forzadas"),
    ("N15 la regla de cliente pasa a permisiva",
     "drop policy cliente_separacion on public.cliente;"
     "create policy cliente_separacion on public.cliente as permissive for all to public "
     "using (public.es_mi_organizacion(organizacion_id)) with check (public.es_mi_organizacion(organizacion_id));",
     "reglas sobre las tres tablas"),
    ("N16 una regla de más que deja ver todos los avisos",
     "create policy otra on public.aviso_inicio for select to authenticated using (true);",
     "reglas sobre las tres tablas"),
    ("N17 las personas pueden insertar avisos", "grant insert on public.aviso_inicio to authenticated;", PERSONAS),
    ("N18 quien no tiene sesión puede vaciar clientes", "grant truncate on public.cliente to anon;", PERSONAS),
    ("N19 la credencial del sistema puede insertar avisos", "grant insert on public.aviso_inicio to service_role;",
     "privilegios de service_role sobre public.aviso_inicio"),
]

FILAS = {
    "tablas cliente, asignacion y aviso_inicio", "columnas de public.cliente", "constraints de public.cliente",
    "columnas de public.asignacion", "constraints de public.asignacion", "columnas de public.aviso_inicio",
    "constraints de public.aviso_inicio", "función public.dias_laborables_validos(smallint[])",
    "función public.impedir_cambio_de_aviso()", "disparadores de public.aviso_inicio",
    "reglas de las tres tablas, activadas y forzadas", "reglas sobre las tres tablas", PERSONAS,
    "privilegios de service_role sobre public.aviso_inicio",
}


def correr(desvio: str):
    r = psql(f"begin;\n{desvio}\n{VALIDACION.read_text(encoding='utf-8')}\nrollback;\n", usuario="supabase_admin")
    if r.returncode != 0:
        return None, None, r.stderr.strip()
    filas, nombres = {}, []
    for linea in r.stdout.splitlines():
        partes = linea.split("\t")
        if len(partes) == 4:
            filas[partes[0]] = partes[3]
            nombres.append(partes[0])
        else:
            nombres.append(f"(fila mal formada: {linea!r})")
    return filas, nombres, None


def decidir(filas: dict, nombres: list, fila) -> tuple:
    """¿La salida es la esperada? Exactamente las filas de FILAS, sin repetidas; todo OK, o FALLA en `fila`."""
    if not filas:
        return False, "la validación no devolvió filas"
    if len(nombres) != len(FILAS) or set(nombres) != FILAS:
        return False, (f"no da exactamente las {len(FILAS)} filas esperadas: dio {len(nombres)}; "
                       f"faltan {sorted(FILAS - set(nombres))}, sobran {sorted(set(nombres) - FILAS)}")
    fallas = sorted(k for k, v in filas.items() if v != "OK")
    if fila is None:
        return (not fallas), ("todo OK" if not fallas else f"fallas inesperadas: {fallas}")
    return (filas.get(fila) == "FALLA"), (f"marca «{fila}»" if filas.get(fila) == "FALLA"
                                          else f"no marca «{fila}»; marcó {fallas}")


def main() -> int:
    if not VALIDACION.is_file():
        print(f"FALLA: no existe {VALIDACION.relative_to(RAIZ)}.")
        return 1
    malos = 0
    for nombre, desvio, fila in CASOS:
        filas, nombres, error = correr(desvio)
        if error is not None:
            malos += 1
            print(f"✗ {nombre}: la base rechazó el caso.\n  {error.splitlines()[0]}")
            continue
        ok, detalle = decidir(filas, nombres, fila)
        malos += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {nombre}: {detalle}")
    # Cada fila tiene al menos un desvío que la marca.
    sin_caso = sorted(FILAS - {f for _, _, f in CASOS if f})
    ok = not sin_caso
    malos += 0 if ok else 1
    print(f"{'✓' if ok else '✗'} N20 cada fila tiene un desvío que la marca: "
          f"{'sí' if ok else 'faltan ' + ', '.join(sin_caso)}")
    total = len(CASOS) + 1
    print(f"prueba-validacion-aviso-modelo: {total - malos} de {total} casos dan lo esperado.")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
