#!/usr/bin/env python3
"""
Prueba de scripts/verificar-referencias.py: un caso positivo y uno negativo por regla,
y un negativo por cada familia de identificador.

Monta un repositorio de juguete en un directorio temporal, copia ahí el
verificador y lo corre con --raiz. No toca este repositorio.

Uso:  python3 tests/harness/prueba-verificar-referencias.py
Sale con 0 si todos los casos dan lo esperado, y con 1 si alguno falla.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERIFICADOR = Path(__file__).resolve().parents[2] / "scripts" / "verificar-referencias.py"
FAMILIAS = ["D", "PA", "PA-B", "PA-P", "HU", "CA", "H", "RF", "RNF", "RA", "R", "E", "M", "N"]

CONFIG = "[vivos]\ndoc.md\n\n[fuentes]\n" + "".join(f"{f}: fuentes.md\n" for f in FAMILIAS) + """
[previstas]
{previstas}

[no-son-rutas]
America/Panama  # zona horaria
"""

# Un identificador definido y uno sin definir por familia.
DEFINIDOS = {"D": "D-1", "PA": "PA-1", "PA-B": "PA-B1", "PA-P": "PA-P1", "HU": "HU-01.1", "CA": "HU-01.CA-1",
             "H": "H-4", "RF": "RF-1", "RNF": "RNF-1", "RA": "RA-1", "R": "R-1", "E": "E-1", "M": "M-1", "N": "N-1"}
SIN_DEFINIR = {"D": "D-99", "PA": "PA-99", "PA-B": "PA-B99", "PA-P": "PA-P99", "HU": "HU-09.9", "CA": "HU-01.CA-99",
               "H": "H-9", "RF": "RF-99", "RNF": "RNF-99", "RA": "RA-99", "R": "R-99", "E": "E-99", "M": "M-99",
               "N": "N-99"}

FUENTES = "\n".join(
    ["| ~~**D-2**~~ | una decisión superada |", "| **H-4 (nuevo)** | un ticket nuevo |"]
    + [f"| {i} | definido |" for f, i in DEFINIDOS.items() if f != "H"])

DOC_SANO = "\n".join([
    "Cita la copia `docs/trazabilidad/01-Paso/a.md`, el paso `01-Paso/a.md` y un [enlace](sub/unico.txt#arriba).",
    "Identificadores: " + " · ".join(DEFINIDOS.values()) + " · D-2.",
    "Se comprueba con `python3 scripts/verificar-referencias.py`.",
    "Zona `America/Panama`; ruta de API `GET /api/v1/avisos`; plantilla `docs/revisiones/<rama>.md`; [web](https://example.com).",
    "Nombre suelto único: `unico.txt`.",
    "El ticket T-05 (numeración anterior) pasó a HU-01.1.",
])


def huella(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def montar(dir_, doc=DOC_SANO, previstas="", indice_extra="", huella_mala=False, sin_config=False,
           sin_fuente=False, archivo_extra=False, duplicado=False, origen="01-Paso/a.md"):
    raiz = Path(dir_)
    (raiz / "scripts").mkdir()
    shutil.copy(VERIFICADOR, raiz / "scripts" / "verificar-referencias.py")
    if not sin_config:
        (raiz / "scripts" / "referencias.txt").write_text(CONFIG.format(previstas=previstas), encoding="utf-8")
    if not sin_fuente:
        (raiz / "fuentes.md").write_text(FUENTES, encoding="utf-8")
    (raiz / "doc.md").write_text(doc, encoding="utf-8")
    # En una subcarpeta: junto al documento la cita resolvería sin buscar, y es legítima.
    (raiz / "sub").mkdir()
    (raiz / "sub" / "unico.txt").write_text("x", encoding="utf-8")
    if duplicado:
        (raiz / "otra").mkdir()
        (raiz / "otra" / "unico.txt").write_text("y", encoding="utf-8")
    paso = raiz / "docs" / "trazabilidad" / "01-Paso"
    paso.mkdir(parents=True)
    contenido = "copia fechada"
    (paso / "a.md").write_text(contenido, encoding="utf-8")
    if archivo_extra:
        (paso / "b.md").write_text("sin fila en el índice", encoding="utf-8")
    h = "000000000000" if huella_mala else huella(contenido)
    indice = ("| Archivo | Origen | Huella | Estado |\n|---|---|---|---|\n"
              f"| `01-Paso/a.md` | `{origen}` | `{h}` | idéntica |\n" + indice_extra)
    (raiz / "docs" / "trazabilidad" / "README.md").write_text(indice, encoding="utf-8")
    return raiz


def correr(raiz, *extra):
    r = subprocess.run([sys.executable, str(raiz / "scripts" / "verificar-referencias.py"), "--raiz", str(raiz), *extra],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def git(raiz, *args):
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


def con_git(dir_, cambio):
    """Repositorio con un commit base; después aplica `cambio` y vuelve a fijar la huella del índice."""
    raiz = montar(dir_)
    git(raiz, "init", "-q")
    git(raiz, "add", ".")
    git(raiz, "-c", "user.email=autora@example.com", "-c", "user.name=Autora", "commit", "-q", "-m", "base")
    copia = raiz / "docs" / "trazabilidad" / "01-Paso" / "a.md"
    indice = raiz / "docs" / "trazabilidad" / "README.md"
    if cambio == "reescribir":   # cambia la copia y su huella a la vez: sin --base pasaría
        copia.write_text("copia alterada", encoding="utf-8")
        indice.write_text(indice.read_text(encoding="utf-8").replace(huella("copia fechada"), huella("copia alterada")),
                          encoding="utf-8")
    elif cambio == "agregar":    # una versión nueva se agrega con su fila
        (copia.parent / "a-v2.md").write_text("versión nueva", encoding="utf-8")
        with indice.open("a", encoding="utf-8") as f:
            f.write(f"| `01-Paso/a-v2.md` | `01-Paso/a-v2.md` | `{huella('versión nueva')}` | idéntica |\n")
    return raiz


CASOS = [
    # (nombre, cómo montar, salida esperada, texto que debe aparecer)
    ("positivo: todo resuelve", lambda d: correr(montar(d)), 0, "toda referencia resuelve"),
    ("negativo: ruta que no existe", lambda d: correr(montar(d, doc=DOC_SANO + "\nVer `no/existe.md`.")), 1,
     "la ruta `no/existe.md` no existe"),
    ("negativo: enlace Markdown que no existe", lambda d: correr(montar(d, doc=DOC_SANO + "\n[fuente](docs/no-existe.md)")),
     1, "la ruta `docs/no-existe.md` no existe"),
    ("negativo: numeración retirada sin aviso", lambda d: correr(montar(d, doc=DOC_SANO + "\nVer T-07.")), 1,
     "numeración retirada T-07"),
    ("positivo: ruta prevista con ticket válido",
     lambda d: correr(montar(d, doc=DOC_SANO + "\nMigraciones en `supabase/migrations/`.",
                             previstas="supabase/migrations  HU-01.1")), 0, "toda referencia resuelve"),
    ("negativo: ruta prevista que ya existe", lambda d: correr(montar(d, previstas="sub/unico.txt  HU-01.1")), 1,
     "ya existe: sácala de la lista"),
    ("negativo: ruta prevista con ticket inexistente",
     lambda d: correr(montar(d, previstas="supabase/migrations  HU-09.9")), 1, "que no es un ticket definido"),
    ("negativo: nombre suelto repetido", lambda d: correr(montar(d, duplicado=True)), 1, "la ruta `unico.txt` no existe"),
    ("negativo: archivo fuera del índice", lambda d: correr(montar(d, archivo_extra=True)), 1,
     "falta en el índice `01-Paso/b.md`"),
    ("negativo: huella que no coincide", lambda d: correr(montar(d, huella_mala=True)), 1,
     "la huella de `01-Paso/a.md` no coincide"),
    ("negativo: fila del índice sin archivo",
     lambda d: correr(montar(d, indice_extra="| `01-Paso/z.md` | `01-Paso/z.md` | `111111111111` | idéntica |\n")), 1,
     "el índice cita `01-Paso/z.md`, que no existe"),
    ("negativo: origen de una copia que no coincide", lambda d: correr(montar(d, origen="otro/no-existe.md")), 1,
     "pero su origen es `otro/no-existe.md`"),
    ("negativo: sin configuración queda ciego y falla", lambda d: correr(montar(d, sin_config=True)), 1, "QUEDÉ CIEGO"),
    ("negativo: sin fuente queda ciego y falla", lambda d: correr(montar(d, sin_fuente=True)), 1, "QUEDÉ CIEGO"),
    ("positivo: agregar una versión nueva no rompe la inmutabilidad",
     lambda d: correr(con_git(d, "agregar"), "--base", "HEAD"), 0, "toda referencia resuelve"),
    ("límite declarado: sin --base, reescribir copia y huella a la vez pasa…",
     lambda d: correr(con_git(d, "reescribir")), 0, "sin comprobar inmutabilidad"),
    ("negativo: …y con --base se detecta", lambda d: correr(con_git(d, "reescribir"), "--base", "HEAD"), 1,
     "`docs/trazabilidad/01-Paso/a.md` cambió desde HEAD"),
    ("negativo: --base con una referencia que no existe queda ciego",
     lambda d: correr(con_git(d, "agregar"), "--base", "no-existe"), 1, "QUEDÉ CIEGO"),
] + [
    (f"negativo: identificador sin definir de la familia {f}",
     (lambda i: lambda d: correr(montar(d, doc=DOC_SANO + f"\nSegún {i}.")))(i), 1, f"{i} no está definido")
    for f, i in SIN_DEFINIR.items()
]


def main():
    fallos = 0
    for nombre, ejecutar, codigo, texto in CASOS:
        with tempfile.TemporaryDirectory() as d:
            obtenido, salida = ejecutar(d)
        ok = obtenido == codigo and texto in salida
        print(f"{'OK   ' if ok else 'FALLA'} {nombre}")
        if not ok:
            fallos += 1
            print(f"      esperado: salida {codigo} con «{texto}»\n      encontrado: salida {obtenido}\n"
                  + "\n".join("      | " + l for l in salida.splitlines()))
    print(f"\nprueba-verificar-referencias: {len(CASOS) - fallos} de {len(CASOS)} casos dan lo esperado.")
    if fallos:
        sys.exit(1)


if __name__ == "__main__":
    main()
