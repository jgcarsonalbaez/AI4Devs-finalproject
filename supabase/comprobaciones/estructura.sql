-- ============================================================
-- COMPROBACIÓN DE ESTRUCTURA — HU-03.1, de solo lectura
-- Origen: openspec/specs/acceso/spec.md, requisito «Separación por
-- organización en la base» (HU-03.CA-1 a CA-3).
--
-- Recorre TODAS las tablas de negocio y devuelve una fila por cada falla:
--   FALLA <tab> objeto <tab> motivo <tab> explicación
-- y siempre, al final, una fila RESUMEN con lo que recorrió. Sin filas FALLA,
-- la estructura cumple. La corre scripts/base/comprobar-estructura.py en la
-- integración continua, en cada cambio; su prueba es
-- tests/base/prueba-comprobacion-estructura.py.
--
-- QUÉ ES UNA TABLA DE NEGOCIO: toda tabla de cualquier esquema, salvo los de
-- la lista cerrada de abajo. Nadie declara una tabla como de negocio: una
-- tabla en un esquema nuevo se recorre igual. Si el proveedor agrega un
-- esquema propio, esta comprobación falla y lo nombra; agregarlo a la lista
-- es un cambio que se revisa.
--
-- LÍMITES DECLARADOS
--   - Prueba que la regla existe y que está escrita como se pide; que no deje
--     pasar datos lo prueban los casos con dos organizaciones (HU-03.3).
--   - «Puede omitir las reglas» cubre BYPASSRLS, superusuario y el privilegio
--     TRUNCATE, que vacía una tabla sin pasar por ellas. No revisa los
--     privilegios TRIGGER y REFERENCES: la migración los quita, pero aquí no
--     se vigilan.
-- ============================================================
SET search_path = pg_catalog;

WITH
-- Lista cerrada de esquemas ajenos, por categoría de la spec.
ajenos(esquema, categoria) AS (VALUES
  ('auth',               'servicio de autenticación'),
  ('pg_catalog',         'propio motor'),
  ('information_schema', 'propio motor'),
  ('pg_toast',           'propio motor'),
  ('storage',            'propio motor: servicio de archivos de la plataforma, sin uso en este proyecto'),
  ('realtime',           'propio motor: servicio de tiempo real de la plataforma, sin uso en este proyecto'),
  ('_realtime',          'propio motor: servicio de tiempo real de la plataforma, sin uso en este proyecto'),
  ('supabase_functions', 'propio motor: ganchos de la plataforma, sin uso en este proyecto'),
  ('extensions',         'extensiones del motor'),
  ('graphql',            'extensiones del motor'),
  ('graphql_public',     'extensiones del motor'),
  ('net',                'extensiones del motor'),
  ('vault',              'extensiones del motor'),
  ('pgbouncer',          'extensiones del motor'),
  ('supabase_migrations','registro de migraciones')
),
negocio AS (
  SELECT n.oid, n.nspname
  FROM pg_namespace n
  WHERE n.nspname NOT IN (SELECT esquema FROM ajenos)
    -- Esquemas temporales del propio motor, uno por sesión.
    AND n.nspname !~ '^pg_(toast_)?temp_[0-9]+$'
),
-- Los roles con los que consultan las personas: con sesión y sin ella.
personas(rol) AS (VALUES ('authenticated'), ('anon')),
objetos AS (
  SELECT c.oid, c.relkind, c.relowner, c.relrowsecurity, c.relforcerowsecurity, c.reloptions,
         n.nspname || '.' || c.relname AS objeto,
         (n.nspname = 'public' AND c.relname = 'organizacion') AS es_organizacion
  FROM pg_class c JOIN negocio n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
),
tablas AS (SELECT * FROM objetos WHERE relkind IN ('r', 'p')),
columna_org AS (
  SELECT t.oid, a.attnotnull
  FROM tablas t JOIN pg_attribute a
    ON a.attrelid = t.oid AND a.attname = 'organizacion_id' AND a.attnum > 0 AND NOT a.attisdropped
),
-- La regla que se pide: restrictiva, para toda orden y todo rol, que compara
-- la organización de la fila con la de quien consulta, al leer y al escribir.
regla_buena AS (
  SELECT t.oid
  FROM tablas t JOIN pg_policy p ON p.polrelid = t.oid
  WHERE NOT p.polpermissive
    AND p.polcmd = '*'
    AND p.polroles = '{0}'::oid[]
    AND pg_get_expr(p.polqual, p.polrelid)
        = CASE WHEN t.es_organizacion THEN 'public.es_mi_organizacion(id)'
               ELSE 'public.es_mi_organizacion(organizacion_id)' END
    AND pg_get_expr(p.polwithcheck, p.polrelid)
        = CASE WHEN t.es_organizacion THEN 'public.es_mi_organizacion(id)'
               ELSE 'public.es_mi_organizacion(organizacion_id)' END
),
-- Lista cerrada de funciones con los privilegios de su dueño (D-74). Solo la
-- operación de registro del aviso y auxiliares que responden sí o no sobre
-- quien consulta.
funciones_permitidas(firma) AS (VALUES
  ('public.sesion_abierta()'),
  ('public.es_mi_organizacion(uuid)')
),
definer AS (
  SELECT p.oid::regprocedure::text AS firma
  FROM pg_proc p JOIN negocio n ON n.oid = p.pronamespace
  WHERE p.prosecdef
),
fallas(objeto, motivo, explicacion) AS (
  SELECT objeto, 'sin-organizacion_id', 'la tabla no tiene la columna organizacion_id'
  FROM tablas t WHERE NOT t.es_organizacion AND t.oid NOT IN (SELECT oid FROM columna_org)
  UNION ALL
  SELECT objeto, 'organizacion_id-admite-nulo', 'organizacion_id admite nulo: la base no comprobaría la organización'
  FROM tablas t JOIN columna_org c ON c.oid = t.oid WHERE NOT t.es_organizacion AND NOT c.attnotnull
  UNION ALL
  SELECT objeto, 'reglas-no-activadas', 'las reglas de la base no están activadas'
  FROM tablas WHERE NOT relrowsecurity
  UNION ALL
  SELECT objeto, 'reglas-no-forzadas', 'las reglas no están forzadas para el dueño de la tabla'
  FROM tablas WHERE NOT relforcerowsecurity
  UNION ALL
  SELECT objeto, 'sin-regla-restrictiva',
         'no tiene la regla restrictiva por organización, para toda orden y todo rol, al leer y al escribir'
  FROM tablas WHERE oid NOT IN (SELECT oid FROM regla_buena)
  UNION ALL
  SELECT t.objeto, 'rol-de-personas-es-dueno', 'el rol ' || p.rol || ' es dueño de la tabla, o miembro de su dueño'
  FROM tablas t CROSS JOIN personas p WHERE pg_has_role(p.rol, t.relowner, 'MEMBER')
  UNION ALL
  SELECT r.rolname::text, 'rol-de-personas-omite-reglas', 'el rol puede omitir las reglas de la base'
  FROM pg_roles r JOIN personas p ON p.rol = r.rolname WHERE r.rolbypassrls OR r.rolsuper
  UNION ALL
  -- TRUNCATE vacía la tabla sin pasar por las reglas: tenerlo es omitirlas.
  SELECT t.objeto, 'rol-de-personas-omite-reglas',
         'el rol ' || p.rol || ' puede vaciar la tabla (TRUNCATE no pasa por las reglas)'
  FROM tablas t CROSS JOIN personas p WHERE has_table_privilege(p.rol, t.oid, 'TRUNCATE')
  UNION ALL
  SELECT objeto, 'vista-sin-permisos-de-quien-consulta', 'la vista no consulta con los permisos de quien la usa'
  FROM objetos o
  WHERE relkind = 'v'
    AND NOT EXISTS (SELECT 1 FROM unnest(coalesce(o.reloptions, '{}'::text[])) opcion
                    WHERE lower(opcion) IN ('security_invoker=true', 'security_invoker=on',
                                            'security_invoker=1', 'security_invoker=yes'))
  UNION ALL
  SELECT objeto, 'vista-materializada', 'una vista materializada guarda filas que no pasan por las reglas'
  FROM objetos WHERE relkind = 'm'
  UNION ALL
  SELECT objeto, 'tabla-foranea', 'una tabla foránea lee filas de fuera sin pasar por las reglas'
  FROM objetos WHERE relkind = 'f'
  UNION ALL
  SELECT firma, 'funcion-con-privilegios-del-dueno-fuera-de-lista',
         'corre con los privilegios de su dueño y no está en la lista cerrada'
  FROM definer WHERE firma NOT IN (SELECT firma FROM funciones_permitidas)
)
SELECT 'FALLA', objeto, motivo, explicacion FROM fallas
UNION ALL
SELECT 'RESUMEN',
       (SELECT count(*) FROM negocio)::text || ' esquemas de negocio',
       (SELECT count(*) FROM tablas)::text || ' tablas',
       (SELECT count(*) FROM objetos WHERE relkind <> 'r' AND relkind <> 'p')::text || ' vistas u otros · '
         || (SELECT count(*) FROM definer)::text || ' funciones con privilegios del dueño'
ORDER BY 1, 2, 3;
