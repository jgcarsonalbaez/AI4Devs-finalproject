// HU-03.2 · Separación por organización en el código: el único lugar por el
// que el código consulta tablas.
// Origen: openspec/specs/acceso/spec.md, requisito «Separación por organización
// en el código» (HU-03.CA-1, CA-3, CA-4; D-59) y D-67: un dato de otra
// organización responde igual que uno que no existe.
// Pruebas: tests/unit/separacion.test.ts.
//
// Es la segunda capa. La primera es la regla restrictiva de cada tabla en la
// base (es_mi_organizacion), que corta aunque este filtro faltara. Aquí, toda
// consulta sale ya filtrada por la organización de quien pregunta, y una fila
// de otra organización que llegara igual se trata como inexistente.
//
// Límite declarado: la identidad (usuario y organización de quien pregunta) la
// entrega «Sesión vigente» (HU-01.2); este módulo la recibe, no la obtiene.

/** Tablas que el código puede consultar. Una tabla nueva entra aquí, o no se consulta. */
export const TABLAS = ["organizacion", "usuario"] as const;
export type Tabla = (typeof TABLAS)[number];

/** Quién pregunta: su usuario y su organización, tal como los da la sesión vigente. */
export interface Identidad {
  usuarioId: string;
  organizacionId: string;
}

/** Lo que el código necesita del cliente oficial del servicio (from → select → eq). */
export interface Filtrable<Q> {
  eq(columna: string, valor: string): Q;
}
export interface ClienteDeDatos<Q extends Filtrable<Q>> {
  from(tabla: string): { select(columnas?: string): Q };
}
interface UnaFila {
  maybeSingle(): PromiseLike<{ data: unknown; error: { message: string } | null }>;
}

/** La misma respuesta, en código y en mensaje, para lo ajeno y lo inexistente (D-67). */
export const NO_EXISTE = Object.freeze({
  estado: "no-existe",
  codigo: 404,
  mensaje: "No encontramos lo que buscas.",
} as const);

export type Respuesta<T> = { estado: "encontrado"; dato: T } | typeof NO_EXISTE;

const IDENTIFICADOR = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** La columna que dice de qué organización es cada fila. La tabla organizacion es la excepción. */
function columnaDeOrganizacion(tabla: Tabla): string {
  return tabla === "organizacion" ? "id" : "organizacion_id";
}

/**
 * Empieza toda consulta del código: la tabla, ya filtrada por la organización
 * de quien pregunta. Sin una organización válida, o con una tabla fuera de la
 * lista, no se arma ninguna consulta.
 */
export function consultar<Q extends Filtrable<Q>>(
  cliente: ClienteDeDatos<Q>,
  identidad: Identidad,
  tabla: Tabla,
  columnas = "*",
): Q {
  if (!(TABLAS as readonly string[]).includes(tabla)) {
    throw new Error(`La tabla ${String(tabla)} no está en la lista de tablas que el código puede consultar.`);
  }
  if (!IDENTIFICADOR.test(identidad?.organizacionId ?? "")) {
    throw new Error("No se consulta sin la organización de quien pregunta.");
  }
  return cliente.from(tabla).select(columnas).eq(columnaDeOrganizacion(tabla), identidad.organizacionId);
}

/**
 * Busca una fila por su identificador. Lo propio se entrega; lo ajeno, lo
 * inexistente y un identificador mal formado responden NO_EXISTE. Un error de
 * la base no se disfraza de «no existe»: se informa con mensaje nuestro.
 */
export async function buscarPorId<T extends Record<string, unknown>, Q extends Filtrable<Q> & UnaFila>(
  cliente: ClienteDeDatos<Q>,
  identidad: Identidad,
  tabla: Tabla,
  id: string,
): Promise<Respuesta<T>> {
  if (!IDENTIFICADOR.test(id ?? "")) return NO_EXISTE;
  const { data, error } = await consultar(cliente, identidad, tabla).eq("id", id).maybeSingle();
  if (error) {
    throw new Error(`No se pudo consultar ${tabla}: ${error.message}`);
  }
  const fila = data as T | null;
  if (!fila || fila[columnaDeOrganizacion(tabla)] !== identidad.organizacionId) return NO_EXISTE;
  return { estado: "encontrado", dato: fila };
}

/**
 * Cuántas consultas directas a una tabla (`.from(...)` sobre un cliente) hay en
 * un texto de código. `Array.from(...)` no cuenta. Lo usa la prueba que vigila
 * que el código consulte solo por este módulo.
 */
export function usosDirectos(codigo: string): number {
  return (codigo.match(/(?<!Array)\s*\.\s*from\s*\(\s*["'`]/g) ?? []).length;
}
