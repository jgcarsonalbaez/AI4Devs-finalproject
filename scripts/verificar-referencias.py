#!/usr/bin/env python3
"""
verificar-referencias — integridad referencial de lo que se sube (decisión D-91).

Lo que está en este repositorio cita su origen: una decisión (D-n), un
requisito (RF-n), un ticket (HU-xx.y, H-n), un criterio (HU-xx.CA-n), un
archivo. Este script comprueba que cada cita exista. Un documento se ve bien
por fuera aunque cite algo que ya no está; solo comprobarlo lo delata.

Qué revisa, con la configuración de `scripts/referencias.txt`:

  1. Rutas. En los documentos vivos, lo que va entre comillas invertidas con
     forma de ruta, y el destino de cada enlace Markdown, debe existir: junto
     al documento, desde la raíz o dentro de `docs/trazabilidad/`. Lo que aún
     no existe porque lo crea un ticket futuro va en [previstas], con ese
     ticket; si ya existe, sobra ahí.
  2. Identificadores. Cada identificador citado en un documento vivo (ver
     FAMILIAS) debe estar definido en su fuente: una fila de tabla que empieza
     por él.
  3. Numeración retirada. Los tickets T-nn de la entrega 1 se sustituyeron por
     HU-xx.y y H-n; solo se admiten en una línea que diga «numeración anterior».
  4. Índice de la cadena. Cada archivo de `docs/trazabilidad/` está en la tabla
     de `docs/trazabilidad/README.md` y al revés; la huella (12 primeros
     caracteres de su SHA-256) coincide; y el origen declarado es coherente: una
     copia idéntica o neutralizada viene del mismo paso y con el mismo nombre.
  5. Inmutabilidad (solo con --base REF). Una copia de `docs/trazabilidad/` que
     ya existía en REF no puede haber cambiado ni desaparecido: las versiones
     nuevas se agregan, no se reescriben. Sin esto, cambiar a la vez un archivo
     y su huella en el índice pasaría en verde.

Lo que NO revisa, a propósito:
  - Si lo citado dice lo que el documento afirma que dice. Eso lo revisa una
    persona o el revisor adversarial.
  - Si cada afirmación tiene una cita. Comprueba las citas que hay, no las que
    faltan.
  - Las pruebas de `tests/`: sus datos de juguete citan a propósito cosas que
    no existen, para probar que se detectan.
  - El origen fuera del repositorio: el espacio de trabajo es privado.

Los mensajes los escribe este script, no el intérprete: si no puede leer una
fuente, lo dice y falla; nunca da por bueno lo que no pudo mirar.

Uso:   python3 scripts/verificar-referencias.py [--raiz RUTA] [--base REF]
Sale con 0 si todo resuelve, con 1 si algo está roto o si quedó ciego.
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

EXTENSIONES = (".md", ".py", ".sh", ".sql", ".ts", ".tsx", ".json", ".yml", ".yaml",
               ".css", ".mjs", ".html", ".txt")
CANDIDATO_RUTA = re.compile(r"`([^`\n]+)`")
ENLACE_MD = re.compile(r"\]\(([^)\s]+)\)")
INDICE = "docs/trazabilidad/README.md"
FILA_INDICE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{12})`\s*\|\s*([^|]+)\|")
IGNORADOS = {".git", "node_modules", ".next"}
COMANDOS = {"python3", "python", "bash", "sh", "node", "pnpm"}

# Familia → patrón con que se cita (el grupo 1 es el identificador completo).
# Se da por definido si, en las fuentes de su familia (sección [fuentes]), hay
# una fila de tabla que empieza por él: «| D-5 |», «| **H-4 (nuevo)** |»,
# «| ~~**D-7**~~ |» (una decisión superada sigue definida: se tacha, no se borra).
FAMILIAS = {
    "D": r"\b(D-\d+)\b",
    "PA": r"\b(PA-\d+)\b",
    "PA-B": r"\b(PA-B\d+)\b",
    "PA-P": r"\b(PA-P\d+)\b",
    "HU": r"\b(HU-\d{2}\.\d+)\b",
    "CA": r"\b(HU-\d{2}\.CA-\d+)\b",
    "H": r"\b(H-\d+)\b",
    "RF": r"\b(RF-\d+)\b",
    "RNF": r"\b(RNF-\d+)\b",
    "RA": r"\b(RA-\d+)\b",
    "R": r"(?<![A-Za-z-])(R-\d+)\b",
    "E": r"\b(E-\d+)\b",
    "M": r"(?<![A-Za-z-])(M-\d+)\b",
    "N": r"(?<![A-Za-z-])(N-\d+)\b",
}
RETIRADO = re.compile(r"\bT-\d{2}\b")
PERMISO_RETIRADO = "numeración anterior"


def definido(identificador, texto_fuente):
    return re.search(r"(?m)^\|\s*[~*]*" + re.escape(identificador) + r"(?![\d.])", texto_fuente) is not None


def leer_config(ruta):
    """Lee referencias.txt: secciones [vivos], [fuentes], [previstas], [no-son-rutas]."""
    secciones = {"vivos": [], "fuentes": [], "previstas": [], "no-son-rutas": []}
    actual = None
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.split("  #")[0].strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("[") and linea.endswith("]"):
            actual = linea[1:-1]
            if actual not in secciones:
                raise ValueError(f"línea {n}: sección desconocida [{actual}]")
            continue
        if actual is None:
            raise ValueError(f"línea {n}: hay texto antes de la primera sección")
        secciones[actual].append(linea)
    return secciones


def parece_ruta(texto, no_son_rutas):
    if texto in no_son_rutas:
        return False
    if " " in texto and not texto.endswith(EXTENSIONES):   # «GET /api/v1/…», «esperado / encontrado»
        return False
    if texto.startswith(("http", "/", "@", "~", "$", ".env", "-", "#", "mailto:")):
        return False
    if any(c in texto for c in "{}<>*?|=()[],;'\"") or "…" in texto or "..." in texto.replace("../", ""):
        return False
    return texto.endswith(EXTENSIONES) or ("/" in texto and not texto.endswith(":"))


def resuelve(texto, doc, raiz):
    rel = texto.rstrip("/")
    for base in (doc.parent, raiz, raiz / "docs" / "trazabilidad"):
        if (base / rel).exists():
            return True
    if "/" not in rel:   # nombre suelto: vale si hay exactamente un archivo con ese nombre
        hallados = [p for p in raiz.rglob(rel) if not IGNORADOS & set(p.relative_to(raiz).parts)]
        return len(hallados) == 1
    return False


def huella(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--base", help="referencia de git contra la que se comprueba que ninguna copia cambió")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    rotas = []
    revisadas = 0

    # --- configuración y fuentes: si no se pueden leer, se falla -------------
    try:
        cfg = leer_config(raiz / "scripts" / "referencias.txt")
    except (OSError, ValueError) as e:
        print(f"verificar-referencias: QUEDÉ CIEGO, no pude leer scripts/referencias.txt ({e}).")
        return 1
    no_son_rutas = set(cfg["no-son-rutas"])

    fuentes = {}
    for linea in cfg["fuentes"]:
        familia, _, archivos = linea.partition(":")
        texto = ""
        for a in archivos.split(","):
            p = raiz / a.strip()
            if not p.is_file():
                print(f"verificar-referencias: QUEDÉ CIEGO, falta la fuente de {familia.strip()}: {a.strip()}")
                return 1
            texto += p.read_text(encoding="utf-8") + "\n"
        fuentes[familia.strip()] = texto
    for familia in FAMILIAS:
        if familia not in fuentes:
            print(f"verificar-referencias: QUEDÉ CIEGO, la familia {familia} no tiene fuente en [fuentes].")
            return 1

    # --- 1 a 3: documentos vivos -----------------------------------------------
    vivos = []
    for patron in cfg["vivos"]:
        hallados = sorted(p for p in raiz.glob(patron) if p.is_file())
        if not hallados:
            rotas.append(f"[vivos] «{patron}» no corresponde a ningún archivo")
        vivos.extend(hallados)

    previstas = {}
    for linea in cfg["previstas"]:
        partes = linea.split()
        if len(partes) != 2:
            rotas.append(f"[previstas] «{linea}»: se espera «ruta ticket»")
            continue
        previstas[partes[0].rstrip("/")] = partes[1]

    for doc in vivos:
        rel_doc = doc.relative_to(raiz)
        for n, linea in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            candidatos = []
            for m in CANDIDATO_RUTA.finditer(linea):
                partes = m.group(1).strip().split()
                # Un comando («python3 scripts/x.py»): se revisan las rutas que lleva.
                candidatos += partes[1:] if partes and partes[0] in COMANDOS else [m.group(1).strip()]
            for m in ENLACE_MD.finditer(linea):
                destino = m.group(1).split("#")[0]
                if destino and not destino.startswith(("http", "mailto:")):
                    candidatos.append(destino)
            for texto in candidatos:
                if not parece_ruta(texto, no_son_rutas):
                    continue
                revisadas += 1
                if resuelve(texto, doc, raiz) or texto.rstrip("/") in previstas:
                    continue
                rotas.append(f"{rel_doc}:{n}: la ruta `{texto}` no existe y no está en [previstas]")
            for familia, patron in FAMILIAS.items():
                for m in re.finditer(patron, linea):
                    revisadas += 1
                    if not definido(m.group(1), fuentes[familia]):
                        rotas.append(f"{rel_doc}:{n}: {m.group(1)} no está definido en su fuente")
            if RETIRADO.search(linea) and PERMISO_RETIRADO not in linea:
                revisadas += 1
                rotas.append(f"{rel_doc}:{n}: usa la numeración retirada {RETIRADO.search(linea).group(0)}"
                             f" sin decir «{PERMISO_RETIRADO}»")

    for ruta, ticket in previstas.items():
        revisadas += 1
        if (raiz / ruta).exists():
            rotas.append(f"[previstas] `{ruta}` ya existe: sácala de la lista")
        familia = "H" if re.fullmatch(r"H-\d+", ticket) else "HU" if re.fullmatch(r"HU-\d{2}\.\d+", ticket) else None
        if familia is None or not definido(ticket, fuentes[familia]):
            rotas.append(f"[previstas] `{ruta}` la crea {ticket}, que no es un ticket definido")

    # --- 4: índice de la cadena ---------------------------------------------
    indice = raiz / INDICE
    if not indice.is_file():
        print(f"verificar-referencias: QUEDÉ CIEGO, falta el índice {INDICE}.")
        return 1
    en_indice = {}
    for n, linea in enumerate(indice.read_text(encoding="utf-8").splitlines(), 1):
        m = FILA_INDICE.match(linea)
        if not m:
            continue
        archivo, origen, h, estado = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        en_indice[archivo] = (h, n)
        revisadas += 1
        if "derivada" in estado:
            if origen.split("/")[0] != archivo.split("/")[0]:
                rotas.append(f"{INDICE}:{n}: `{archivo}` dice derivar de `{origen}`, de otro paso")
        elif origen != archivo:
            rotas.append(f"{INDICE}:{n}: `{archivo}` es copia ({estado}) pero su origen es `{origen}`")
    base = raiz / "docs" / "trazabilidad"
    en_disco = {p.relative_to(base).as_posix() for p in base.rglob("*")
                if p.is_file() and p.name != "README.md" and not p.name.startswith(".")}
    for rel in sorted(en_disco - set(en_indice)):
        rotas.append(f"{INDICE}: falta en el índice `{rel}`")
    for rel, (h, n) in sorted(en_indice.items()):
        revisadas += 1
        if rel not in en_disco:
            rotas.append(f"{INDICE}:{n}: el índice cita `{rel}`, que no existe")
        elif huella(base / rel) != h:
            rotas.append(f"{INDICE}:{n}: la huella de `{rel}` no coincide (índice {h}, archivo {huella(base / rel)})")

    # --- 5: inmutabilidad frente a una referencia de git ---------------------
    if args.base:
        r = subprocess.run(["git", "-C", str(raiz), "diff", "--no-renames", "--name-status", "--diff-filter=MD",
                            args.base, "--", "docs/trazabilidad", ":(exclude)docs/trazabilidad/README.md"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"verificar-referencias: QUEDÉ CIEGO, no pude comparar con {args.base} ({r.stderr.strip()}).")
            return 1
        for linea in r.stdout.splitlines():
            revisadas += 1
            estado, ruta = linea.split("\t", 1)
            que = "cambió" if estado == "M" else "desapareció"
            rotas.append(f"`{ruta}` {que} desde {args.base}: las copias no se reescriben; se agrega una versión nueva")

    # --- resultado ----------------------------------------------------------
    print(f"verificar-referencias: {len(vivos)} documentos vivos · {len(en_indice)} archivos en el índice"
          f" · {revisadas} referencias revisadas · {len(rotas)} rotas"
          + (f" · inmutabilidad frente a {args.base}" if args.base else " · sin comprobar inmutabilidad (falta --base)"))
    for r in rotas:
        print(f"  ROTA  {r}")
    if rotas:
        print("Corrige la cita o el archivo citado; si algo todavía no existe, declara el ticket que lo crea en [previstas].")
        return 1
    print("verificar-referencias: toda referencia resuelve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
