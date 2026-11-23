#!/usr/bin/env python3
"""
Prueba con datos de lo que entrega HU-03.1 en la base, por las dos puertas:
la API de la base, con el pase de una persona, y el SQL directo.

- sesion_abierta(): «Por comprobar al construir HU-03.1» de
  openspec/specs/acceso/spec.md, requisito «Separación por organización en
  la base». Sí con la sesión abierta; no con el pase de una sesión cerrada.
- organizacion: hasta el tramo 3 nadie la ve ni la cambia por la API (D-100),
  ni con sesión ni sin ella.
- Las constraints de organizacion, con un caso que pasa y uno que no.

Crea una cuenta de prueba con correo de example.com y una organización de
prueba, que quita al terminar. La cuenta queda en la base local: es
desechable y `supabase db reset` la borra.

Necesita la base local levantada (`supabase start`) con las migraciones.

Uso:  python3 tests/base/prueba-acceso-organizacion.py
Sale con 0 si todos los casos dan lo esperado, y con 1 si alguno falla.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "base"))
from base_local import psql, psql_ok  # noqa: E402


def entorno() -> dict:
    """URL y claves de la base local, tal como las da `supabase status`."""
    try:
        r = subprocess.run(["supabase", "status", "-o", "env"], cwd=RAIZ, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        sys.exit("ERROR: no encuentro la herramienta supabase; sin ella no sé la URL ni las claves de la base local.")
    valores = {}
    for linea in r.stdout.splitlines():
        if "=" in linea:
            k, v = linea.split("=", 1)
            valores[k.strip()] = v.strip().strip('"')
    faltan = [k for k in ("API_URL", "ANON_KEY", "SERVICE_ROLE_KEY") if not valores.get(k)]
    if faltan:
        sys.exit(f"ERROR: `supabase status` no dio {', '.join(faltan)}. ¿Está levantada la base local?")
    return valores


ENV = entorno()


def api(metodo: str, ruta: str, cuerpo=None, pase=None, clave=None, cabeceras=None):
    """Petición a la API local. Devuelve (código, cuerpo ya leído)."""
    h = {"apikey": clave or ENV["ANON_KEY"], "Content-Type": "application/json"}
    if pase:
        h["Authorization"] = "Bearer " + pase
    h.update(cabeceras or {})
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(ENV["API_URL"] + ruta, data=datos, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            texto = resp.read().decode()
            return resp.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def entrar(correo: str, clave: str) -> str:
    codigo, cuerpo = api("POST", "/auth/v1/token?grant_type=password", {"email": correo, "password": clave})
    if codigo != 200:
        sys.exit(f"ERROR: la cuenta de prueba no pudo entrar ({codigo}): {cuerpo}")
    return cuerpo["access_token"]


def main() -> int:
    resultados = []

    def caso(nombre: str, ok: bool, detalle: str):
        resultados.append(ok)
        print(f"{'✓' if ok else '✗'} {nombre}: {detalle}")

    # Preparación: una organización y una cuenta con dos sesiones.
    nombre_org = f"Organización de prueba {uuid.uuid4()}"
    org_id = psql_ok(f"insert into public.organizacion (nombre, zona_horaria) "
                     f"values ('{nombre_org}', 'America/Panama') returning id;").strip()
    correo, clave = f"prueba-{uuid.uuid4()}@example.com", f"Prueba-{uuid.uuid4()}"
    codigo, cuerpo = api("POST", "/auth/v1/admin/users", {"email": correo, "password": clave, "email_confirm": True},
                         pase=ENV["SERVICE_ROLE_KEY"], clave=ENV["SERVICE_ROLE_KEY"])
    if codigo != 200:
        sys.exit(f"ERROR: no se pudo crear la cuenta de prueba ({codigo}): {cuerpo}")
    pase_a, pase_b = entrar(correo, clave), entrar(correo, clave)

    try:
        # sesion_abierta(): la comprobación que la spec dejó para este ticket.
        c, r = api("POST", "/rest/v1/rpc/sesion_abierta", {}, pase=pase_a)
        caso("P1 sesión abierta", (c, r) == (200, True), f"respondió {c} {r}")
        c, _ = api("POST", "/auth/v1/logout?scope=local", {}, pase=pase_a)
        if c != 204:
            sys.exit(f"ERROR: no se pudo cerrar la sesión A ({c}).")
        c, r = api("POST", "/rest/v1/rpc/sesion_abierta", {}, pase=pase_a)
        caso("N1 pase de una sesión cerrada, sin expirar", (c, r) == (200, False), f"respondió {c} {r}")
        c, r = api("POST", "/rest/v1/rpc/sesion_abierta", {}, pase=pase_b)
        caso("P2 la otra sesión de la misma cuenta sigue abierta", (c, r) == (200, True), f"respondió {c} {r}")
        c, r = api("POST", "/rest/v1/rpc/sesion_abierta", {})
        caso("N2 sin pase no se puede preguntar", c in (401, 403), f"respondió {c}")

        # organizacion por la API: nadie la ve ni la cambia hasta el tramo 3 (D-100).
        filtro = f"/rest/v1/organizacion?id=eq.{org_id}&select=id"
        c, r = api("GET", filtro, pase=pase_b)
        caso("N3 con sesión no se ve la organización", (c, r) == (200, []), f"respondió {c} {r}")
        c, r = api("GET", filtro)
        caso("N4 sin sesión no se ve la organización", (c, r) == (200, []), f"respondió {c} {r}")
        c, r = api("POST", "/rest/v1/organizacion", {"nombre": f"Intrusa {uuid.uuid4()}", "zona_horaria": "UTC"},
                   pase=pase_b)
        caso("N5 con sesión no se crea una organización", c in (401, 403), f"respondió {c}")
        c, r = api("PATCH", f"/rest/v1/organizacion?id=eq.{org_id}", {"sesion_dias": 1}, pase=pase_b,
                   cabeceras={"Prefer": "return=representation"})
        dias = psql_ok(f"select sesion_dias from public.organizacion where id = '{org_id}';").strip()
        caso("N6 con sesión no se cambia una organización", c in (200, 401, 403) and dias == "30",
             f"respondió {c}; sesion_dias quedó en {dias}")

        # Constraints, por SQL directo, dentro de una transacción que se deshace.
        def inserta(valores: str) -> bool:
            r = psql(f"begin; insert into public.organizacion (nombre, zona_horaria, sesion_dias) "
                     f"values {valores}; rollback;")
            return r.returncode == 0

        caso("P3 zona horaria de la lista estándar", inserta(f"('P3 {uuid.uuid4()}', 'America/Lima', 1)"),
             "se acepta")
        caso("N7 zona horaria que la base no reconoce", not inserta(f"('N7 {uuid.uuid4()}', 'America/Atlantida', 30)"),
             "se rechaza")
        caso("N8 desplazamiento escrito como zona", not inserta(f"('N8 {uuid.uuid4()}', 'UTC+5', 30)"),
             "se rechaza")
        caso("N9 sesion_dias en cero", not inserta(f"('N9 {uuid.uuid4()}', 'UTC', 0)"), "se rechaza")
        caso("N10 nombre repetido", not inserta(f"('{nombre_org}', 'UTC', 30)"), "se rechaza")
        caso("N11 sin zona horaria",
             psql("begin; insert into public.organizacion (nombre) values ('N11'); rollback;").returncode != 0,
             "se rechaza")
    finally:
        psql_ok(f"delete from public.organizacion where id = '{org_id}';")

    malos = resultados.count(False)
    print(f"prueba-acceso-organizacion: {len(resultados) - malos} de {len(resultados)} casos dan lo esperado.")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
