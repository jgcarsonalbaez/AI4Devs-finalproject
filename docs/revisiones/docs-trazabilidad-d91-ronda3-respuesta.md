# Respuesta a la ronda 3 — rama `docs/trazabilidad-d91`

> Jueves 19/11/2026. Responde a `docs-trazabilidad-d91-ronda3-corrida1.md` (9 hallazgos y 2 sospechas) y
> `docs-trazabilidad-d91-ronda3-corrida2.md` (7 hallazgos). Unidos quedan **12 hallazgos distintos y 2
> sospechas**: 4 salieron en las dos corridas, 5 solo en la primera y 3 solo en la segunda. **Ninguno
> crítico.** Material: el de la ronda 2, con su respuesta y el diff de D-96 a D-99 en lugar de los
> anteriores. **Límite:** el registro de decisiones completo no entró, como en las rondas 1 y 2.

## Resumen

| Cierre | Cuántos |
|---|---|
| Corregido (1 a 8, 10, 11) | 10 |
| Corregido como puerta declarada, no automática (9) | 1 |
| Descartado, con su razón (12) | 1 |
| Sospechas: corregida la redacción, sin cambiar la decisión (S1, S2) | 2 |
| **Total** | **12 + 2 sospechas** |

## Hallazgo por hallazgo

| # | Hallazgo (corrida-número) | Cierre | Qué se hizo y por qué |
|---|---|---|---|
| 1 | La excepción de la derivada deja reescribir decisiones antiguas (c1-1) | **Corregido** | La derivada sigue pudiendo cambiar, pero cada decisión que estaba en la base tiene que seguir igual, o igual con una nota al final o tachada: crece y se marca, no se reescribe. Cuatro casos de prueba. **El control cazó en el acto dos reescrituras mías** de D-97 y D-98 al corregir esta ronda; se restauró el texto aprobado y las precisiones van como nota |
| 2 | Una ruta con `..` puede salir del repositorio y resolver contra la máquina (c1-2, c2-1) | **Corregido** | Una cita solo resuelve si el destino, ya resuelto, queda dentro del repositorio. Caso de prueba con una ruta que sube con «..» hasta un archivo del sistema operativo |
| 3 | Una fila del índice mal formada se salta en silencio (c1-3, c2-5) | **Corregido** | Toda fila que empieza por un archivo y no tiene la forma de la tabla falla. Caso de prueba con una huella en mayúsculas que repite un archivo |
| 4 | El uso `[texto][id]` no se comprueba contra su definición (c1-4) | **Corregido** | Cada uso necesita su `[id]: destino` en el mismo documento. Dentro de un bloque de código (```) nada es enlace. Tres casos de prueba |
| 5 | D-97 deja un tercer lugar con la identidad del autor, y D-98 dice «dos únicos» (c1-5) | **Corregido** | Cierto. Nota al final de D-97 y de D-98: en lo vigente son dos lugares, y el historial conserva además el usuario de la máquina (D-97). `CLAUDE.md` §2 y el README lo dicen igual |
| 6 | D-94 conserva como vigente la cobertura que D-96 declara inexistente (c1-6) | **Corregido** | La frase «Mientras tanto lo cubre…» de D-94 queda tachada. El resto de D-94 sigue vigente: el riesgo aceptado no cambió, solo su cobertura |
| 7 | El estado acepta texto de más tras uno válido (c1-7) | **Corregido** | El estado tiene que ser exactamente `idéntica`, `neutralizada` o `derivada sin nombres` (la negrita no cuenta). Caso de prueba con «idéntica alterada» |
| 8 | No hay prueba del límite de 200 y tiene un error de borde (c1-8, c2-6) | **Corregido** | Cierto: un rango de 201 elementos pasaba. Ahora cuenta elementos. Dos casos de prueba (rango de identificadores y de criterios) |
| 9 | D-99 no es una puerta verificable del tramo 8 (c1-9, c2-3) | **Corregido como puerta declarada** | `CLAUDE.md` §6: el pull request del tramo 8 no se abre sin los tickets v5 y el PRD v9 en `docs/trazabilidad/`. Es una puerta de la Dirección, que aprueba cada pull request (D-90); la integración continua no la comprueba, y así se dice. El calendario del seguimiento diario la lleva como hito |
| 10 | D-92 sigue como vigente sin marca, frente a D-98 (c2-4) | **Corregido** | Nota al final de D-92: «Precisada por D-98» |
| 11 | Faltan negativos de la derivada al desaparecer o cambiar de tipo (c2-7) | **Corregido** | Dos casos de prueba: la derivada borrada y la derivada cambiada por un enlace simbólico fallan |
| 12 | Las revisiones obligatorias quedan fuera del verificador sin una decisión que lo diga (c2-2) | **Descartado como hueco · texto precisado** | D-91 pide que lo que redactamos cite y que la cita exista; el informe del revisor no lo redactamos, y su error de cita es justo lo que la respuesta contesta. `CLAUDE.md` §7 ya decía que el verificador revisa los documentos que lista `scripts/referencias.txt`. Lo que sí estaba mal: el texto solo nombraba las corridas. Ahora nombra los informes en sus dos formas (`-ronda<N>.md` y `-corrida<M>.md`), y `CLAUDE.md` §6 admite las corridas |
| S1 | D-97 afirma sin evidencia que borrar las rutas «no es posible» (c1, sospecha) | **Redacción corregida** | Se comprobó en el fork que existe `refs/pull/1/head`. La nota de D-97 dice lo exacto: no está en nuestras manos; quitarla pide al soporte de GitHub |
| S2 | «Git exige un autor» no justifica que sea el nombre real (c1, sospecha) | **Redacción corregida** | Cierto. La nota de D-98 lo dice: git exige un nombre y un correo, no que sean los reales; los commits llevan el real desde la entrega 1 (17/10/2026, commit `a09e888`) |

## Cruce de las correcciones contra las reglas que tocan

- **Los dos informes se guardaron neutralizados (D-95):** la ruta del espacio temporal en las cabeceras,
  y en el hallazgo 5 de la corrida 1 el usuario de la máquina que el revisor citó, cambiado por
  `<usuario-de-la-máquina>`. Ese hallazgo trata justo de no repetirlo.
- **Las marcas en D-92, D-94, D-97 y D-98 son notas al final o tachados**, nunca texto cambiado: es la
  regla que la corrección 1 vuelve automática, y se comprobó corriendo el verificador contra el
  commit anterior de esta rama (`b062c63`), además de contra la rama base.
- **La regla de crecer y marcar solo mira las filas de decisiones.** La cabecera del registro y los
  puntos abiertos pueden cambiar; está declarado en el verificador.
- **La ruta dentro del repositorio** se comprueba después de resolver enlaces simbólicos, así que un
  enlace que apunta fuera tampoco resuelve.
- **Conteo:** pruebas, 52 a 64 (+12: 4 de la derivada, 2 de rangos, 3 de enlaces por referencia y
  bloques, 1 de ruta fuera, 2 del índice). Decisiones, 98 filas con negrita (sin cambio). Índice, 77
  archivos (sin cambio).

## Sobre el cierre

Esta ronda no trae críticos, y lo que encuentra ya es, en su mayoría, una **evasión deliberada** del
control (rutas que suben con «..» hasta salir del repositorio, filas con huella falsa para esconder un duplicado, reetiquetar una copia),
no un error que alguien cometería trabajando. El verificador protege contra **el error de quien
trabaja de buena fe**: una cita que quedó vieja, una copia que se editó, una decisión que se reescribió
sin darse cuenta. No protege contra quien sube cambios con mala fe: esa persona podría editar el propio
verificador en el mismo pull request, y eso lo detiene la revisión de la Dirección antes de unir, no
la integración continua. Con esa frontera declarada, se propone cerrar la refutación con esta ronda.
