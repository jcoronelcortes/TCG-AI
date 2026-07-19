# Herramienta de reproducción de logs — `utils/log_replay.py`

> **Nota de corrección**: versiones anteriores de esta documentación se referían al módulo como `cg/log_replay.py` y al comando `python -m cg.log_replay`. Ambos son **incorrectos**: el módulo real vive en `utils/log_replay.py` y se invoca con `python -m utils.log_replay`.

## Índice

- [Propósito](#propósito)
- [Cómo encaja en el proyecto](#cómo-encaja-en-el-proyecto)
- [Estructura del módulo](#estructura-del-módulo)
- [Uso del comando](#uso-del-comando)
- [Interpretación de resultados](#interpretación-de-resultados)
- [Advertencias importantes](#advertencias-importantes)
- [Recomendaciones](#recomendaciones)

## Propósito

`utils/log_replay.py` reproduce un log de partida de Kaggle (`log/<id>.json`) y ejecuta el agente local `main.agent()` sobre cada observación accionable, comparando su decisión con la acción registrada en el log. Es una herramienta de **depuración fuera de línea**, útil para:

- verificar que el agente interpreta bien observaciones reales (formato de `select`/`option`);
- detectar dónde la decisión del agente **difiere** de la acción registrada (regresiones o mejoras);
- inspeccionar paso a paso qué opciones se evalúan en cada momento del juego.

No depende del motor nativo `cg` (`cg/game.py`, la `.dll`/`.so`): solo importa `agent` de `main.py` y lee JSON. Por eso puede correr en cualquier entorno con logs ya descargados.

## Cómo encaja en el proyecto

- **[`main.py`](main.md)** aporta la función `agent(obs_dict)` que se evalúa.
- **`utils/split_turns.py`** es complementario: divide un log en registros por turno (`registro_ttt_pasos_aaa_hasta_bbb.json`), útil para aislar un turno concreto antes de depurar.
- **`tests/test_cg_log_replay.py`** ejercita este módulo (`import utils.log_replay as log_replay`) dentro de la suite `pytest`.
- Para reproducir **una sola decisión** (en vez de un log entero) suele bastar con cargar el `observation` del paso y llamar `main.agent(obs)` directamente; las regresiones de decisiones puntuales se fijan con *fixtures* en `tests/fixtures/` (ver [main.md §5](main.md#5-cómo-depurar-una-decisión)).

## Estructura del módulo

### `load_log(path) -> list[Any]` (líneas 8–13)
Carga el JSON y valida que sea un objeto con la clave `steps`; si no, lanza `ValueError`. Devuelve la lista `steps` (cada elemento es un *paso*, que a su vez es una lista de *items* — una perspectiva por jugador).

### `_is_valid_selection(action, select) -> bool` (líneas 16–23)
`True` solo si `action` es una **lista no vacía de enteros**, todos dentro del rango `0 ≤ i < len(select["option"])`. Rechaza formatos inválidos o índices fuera de rango.

### `_canonical_action(action, select) -> list[int] | None` (líneas 26–34)
Normaliza la acción del log para poder compararla con la salida del agente:
- si es una lista válida de índices (`_is_valid_selection`), la devuelve tal cual;
- si es `[]` y `select` tiene **exactamente una** opción: devuelve `[0]` cuando `minCount >= 1`, o `[]` cuando `minCount == 0` (paso obligatorio de una sola opción vs. opción única opcional);
- en cualquier otro caso devuelve `None` → la acción **no es comparable** (contará como `ignored`).

### `_format_option` / `_format_select` / `_format_options` (líneas 37–56)
Formateo legible para los modos `--verbose`/`--interactive`:
- `_format_option`: una línea por opción con los campos presentes (`type`, `area`, `index`, `playerIndex`, `attackId`, `number`).
- `_format_select`: cabecera con `type`, `context`, `min`, `max` y número de opciones.
- `_format_options`: muestra las primeras `max_show=10` opciones e indica cuántas quedan ocultas (`... +N more options`).

### `_step_prompt() -> bool` (líneas 59–64)
Prompt interactivo: lee una línea; devuelve `False` si el usuario escribe `q` o corta con EOF/`Ctrl-C` (para terminar el recorrido), `True` para continuar.

### `replay_log(path, max_items=None, verbose=False, interactive=False) -> dict` (líneas 67–134)
Núcleo del recorrido. Para cada paso y **cada item** del paso:
1. Omite el item si no tiene `observation` (dict), `select` o `current`.
2. Cuenta el item como `processed`, obtiene `action = item["action"]` y calcula `agent_choice = agent(obs)`.
3. Calcula `logged_choice = _canonical_action(action, select)`.
4. En modo `verbose`/`interactive` imprime cabecera de turno (cuando cambia `current.turn`), el `select`, las opciones, la elección del agente y la del log.
5. En modo `interactive` pausa con `_step_prompt()`; si el usuario sale, devuelve el resumen parcial.
6. Si `logged_choice is not None`: `compared += 1` y compara con `agent_choice` → `matched` o `mismatched`.
7. Corta si `processed >= max_items`.

Devuelve un dict con `processed`, `compared`, `matched`, `mismatched` e `ignored` (= `processed - compared`).

### `main()` (líneas 137–158) y `if __name__ == "__main__"` (líneas 161–162)
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

- **Estado global entre llamadas.** `main.agent()` mantiene estado global entre invocaciones (`CARTAS_ACTIVAS_EN_MAZO`, `plan`, banderas `op_is_*_deck`, `we_go_first`, …). `replay_log` llama al agente en orden secuencial, como en una partida real, así que ese estado se va construyendo paso a paso. Para reproducir **una** decisión aislada de forma fiable conviene reiniciar el tracking (`main._init_cartas_tracking()` y banderas asociadas), tal como hace el *fixture* `reset_main_state` de `tests/test_main.py`.
- **Validez solo hasta la primera divergencia.** El log registra los estados que siguieron a las acciones **originales**. En cuanto el agente elige algo distinto (`mismatched`), los pasos posteriores del log ya no corresponden a la línea que jugaría el agente; los `mismatched` que aparezcan después pueden ser artefactos del cambio de rama, no errores nuevos. Para depurar, céntrate en el **primer** `mismatched`.
- **Se evalúan las dos perspectivas.** El bucle recorre todos los items de cada paso (jugador activo e inactivo). Cada item trae su propio campo `action`; el agente se ejecuta sobre cualquier observación con `select`+`current`, no solo la nuestra.

## Recomendaciones

- `--verbose` para inspeccionar `select`/opciones y confirmar que el agente interpreta bien el contexto.
- `--interactive` para detenerte en un paso concreto.
- `--max-items` para acotar el recorrido en logs largos.
- Combínalo con `utils/split_turns.py` para aislar primero el turno de interés.
