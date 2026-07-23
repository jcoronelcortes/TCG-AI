# Reproducción de logs — `utils/log_replay.py` y `utils/split_turns.py`

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Propósito

`utils/log_replay.py` reproduce un log de partida de Kaggle (`log/<id>.json`) y ejecuta el agente local `main.agent()` sobre cada observación accionable, comparando su decisión con la acción registrada en el log. Es una herramienta de **depuración fuera de línea**, útil para:

- verificar que el agente interpreta bien observaciones reales (formato de `select`/`option`);
- detectar dónde la decisión del agente **difiere** de la acción registrada (regresiones o mejoras);
- inspeccionar paso a paso qué opciones se evalúan en cada momento del juego.

No depende del motor nativo `cg` (`cg/game.py`, la `.dll`/`.so`): solo importa `agent` de `main.py` y lee JSON. Por eso puede correr en cualquier entorno con logs ya descargados.

## Cómo encaja en el proyecto

- **[`main.py`](main.md)** aporta la función `agent(obs_dict)` que se evalúa.
- **`utils/split_turns.py`** es complementario: parte el log en registros por turno para reproducir decisiones aisladas (ver [su sección](#utilssplit_turnspy--partir-el-log-en-turnos)).
- **`tests/test_cg_log_replay.py`** ejercita este módulo (`import utils.log_replay as log_replay`) dentro de la suite `pytest`.
- Para reproducir **una sola decisión** (en vez de un log entero) suele bastar con cargar el `observation` del paso y llamar `main.agent(obs)` directamente; las regresiones de decisiones puntuales se fijan con *fixtures* en `tests/fixtures/` (ver [main.md, "Cómo depurar una decisión"](main.md#4-cómo-depurar-una-decisión)).

## Estructura del módulo

### `load_log(path) -> list`

Carga el JSON y valida que sea un objeto con la clave `steps`; si no, lanza `ValueError`. Devuelve la lista `steps` (cada elemento es un *paso*, que a su vez es una lista de *items* — una perspectiva por jugador).

### `_is_valid_selection(action, select) -> bool`

`True` solo si `action` es una **lista no vacía de enteros**, todos dentro del rango `0 ≤ i < len(select["option"])`. Rechaza formatos inválidos o índices fuera de rango.

### `_canonical_action(action, select) -> list[int] | None`

Normaliza la acción del log para poder compararla con la salida del agente:

- si es una lista válida de índices (`_is_valid_selection`), la devuelve tal cual;
- si es `[]` y `select` tiene **exactamente una** opción: devuelve `[0]` cuando `minCount >= 1`, o `[]` cuando `minCount == 0` (paso obligatorio de una sola opción vs. opción única opcional);
- en cualquier otro caso devuelve `None` → la acción **no es comparable** (contará como `ignored`).

### `_format_option` / `_format_select` / `_format_options`

Formateo legible para los modos `--verbose`/`--interactive`: una línea por opción con los campos presentes (`type`, `area`, `index`, `playerIndex`, `attackId`, `number`), cabecera con `type`/`context`/`min`/`max` y muestra de las primeras 10 opciones (`... +N more options` si hay más).

### `_step_prompt() -> bool`

Prompt interactivo: lee una línea; devuelve `False` si el usuario escribe `q` o corta con EOF/`Ctrl-C` (para terminar el recorrido), `True` para continuar.

### `replay_log(path, max_items=None, verbose=False, interactive=False) -> dict`

Núcleo del recorrido. Para cada paso y **cada item** del paso:

1. Omite el item si no tiene `observation` (dict), `select` o `current`.
2. Cuenta el item como `processed`, obtiene `action = item["action"]` y calcula `agent_choice = agent(obs)`.
3. Calcula `logged_choice = _canonical_action(action, select)`.
4. En modo `verbose`/`interactive` imprime cabecera de turno (cuando cambia `current.turn`), el `select`, las opciones, la elección del agente y la del log.
5. En modo `interactive` pausa con `_step_prompt()`; si el usuario sale, devuelve el resumen parcial.
6. Si `logged_choice is not None`: `compared += 1` y compara con `agent_choice` → `matched` o `mismatched`.
7. Corta si `processed >= max_items`.

Devuelve un dict con `processed`, `compared`, `matched`, `mismatched` e `ignored` (= `processed - compared`).

### `main()`

Punto de entrada por línea de comandos con `argparse`: argumento posicional `logfile` y las banderas `--max-items`, `--verbose`, `--interactive`. Imprime el resumen final.

## Uso del comando

Debe ejecutarse como **módulo** desde la raíz del repositorio y con la raíz en el `PYTHONPATH` (porque el módulo hace `from main import agent`):

```bash
PYTHONPATH="$PWD" python3 -m utils.log_replay <ruta-al-log-json> [--max-items N] [--verbose] [--interactive]
```

Ejemplos:

```bash
PYTHONPATH="$PWD" python3 -m utils.log_replay log/86699707.json --verbose
PYTHONPATH="$PWD" python3 -m utils.log_replay log/86699707.json --interactive
PYTHONPATH="$PWD" python3 -m utils.log_replay log/86699707.json --max-items 50
```

> **No** funciona como script suelto (`python utils/log_replay.py ...`): al ejecutarlo así, `sys.path[0]` es la carpeta `utils/` y `from main import agent` falla con `ModuleNotFoundError: No module named 'main'`. Usa siempre la forma `-m` desde la raíz.

## Interpretación de resultados

| Clave | Significado |
|---|---|
| `processed` | Observaciones accionables leídas (con `observation`, `select` y `current`). Incluye **ambas perspectivas** de cada paso. |
| `compared` | Observaciones cuya acción del log se pudo canonicalizar y por tanto comparar. |
| `matched` | La decisión del agente coincide con la acción canónica del log. |
| `mismatched` | La decisión del agente difiere de la acción canónica del log. |
| `ignored` | `processed - compared`: acciones no canonicalizables (p.ej. `[]` con varias opciones, o formato no reconocido). No son errores. |

## Advertencias importantes

- **Al reproducir, llamar a `agent()` solo con frames `status == "ACTIVE"` del `yourIndex` propio.** Los logs de Kaggle contienen, en cada paso, un item por jugador; los items del rival y los frames inertes también traen `observation`+`select`. Alimentar `agent()` con esas perspectivas contamina el estado global del agente (creencia de mazo, `plan`, flags `op_is_*`) y produce comparaciones sin sentido. `replay_log` recorre **todos** los items sin filtrar (útil para inspección de formato), así que para una reproducción fiel de la partida propia hay que filtrar por `status == "ACTIVE"` y `current.yourIndex == <nuestro índice>` — es lo que hacen los tests de regresión y el flujo con `registros/`.
- **Estado global entre llamadas.** `main.agent()` mantiene estado global entre invocaciones (`CARTAS_ACTIVAS_EN_MAZO`, `plan`, banderas `op_is_*_deck`, `we_go_first`, …). `replay_log` llama al agente en orden secuencial, como en una partida real, así que ese estado se va construyendo paso a paso. Para reproducir **una** decisión aislada de forma fiable conviene reiniciar el tracking (`main._init_cartas_tracking()` y banderas asociadas), tal como hace el *fixture* `reset_main_state` de `tests/test_main.py`.
- **Validez solo hasta la primera divergencia.** El log registra los estados que siguieron a las acciones **originales**. En cuanto el agente elige algo distinto (`mismatched`), los pasos posteriores del log ya no corresponden a la línea que jugaría el agente; los `mismatched` que aparezcan después pueden ser artefactos del cambio de rama, no errores nuevos. Para depurar, céntrate en el **primer** `mismatched`.

## Recomendaciones

- `--verbose` para inspeccionar `select`/opciones y confirmar que el agente interpreta bien el contexto.
- `--interactive` para detenerte en un paso concreto.
- `--max-items` para acotar el recorrido en logs largos.
- Combínalo con `utils/split_turns.py` para aislar primero el turno de interés.

---

## `utils/split_turns.py` — partir el log en turnos

Utilitario complementario: divide un log de partida en **registros por turno**, para poder reproducir las decisiones de un turno concreto sin recorrer la partida entera (es la base del flujo de depuración "reproducir decisiones con registros de turno").

### Funcionamiento

- **Sin parámetros**: `main()` toma automáticamente el **único** JSON de la carpeta `log/` (`find_single_log` falla con `SystemExit` si no hay ninguno o hay más de uno), **limpia** los registros antiguos de `registros/` (`clean_registros` borra solo los `registro_*.json`) y divide el log completo, del primer al último turno.
- El turno de cada paso lo resuelve `step_turn`: el mayor `observation.current.turn` entre los items del paso (el turno del jugador que está actuando); los pasos sin información de turno (p.ej. el paso inicial) se omiten.
- Por cada turno, `write_turn` genera `registros/registro_<turno>_pasos_<primero>_hasta_<ultimo>.json`. El registro conserva todas las claves de nivel superior del log original (salvo `steps`, reemplazada por los pasos del turno) y añade `turn` y `source_step_numbers` (`build_turn_record`), de modo que sigue siendo compatible con el resto de herramientas (incluido `log_replay`).

### Uso

```bash
python3 utils/split_turns.py
```

(Deja un único `<id>.json` en `log/` antes de ejecutarlo.) Después, cada registro de `registros/` puede reproducirse por separado; recuerda la advertencia de arriba: al reproducir, llama a `agent()` **solo** con los frames `status == "ACTIVE"` del `yourIndex` propio.
