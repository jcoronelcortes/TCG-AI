# main.py — Preámbulo de agent() y conteos de tablero (líneas 1292–1476)

## Rol en el agente

Este bloque es el arranque de `agent()`: convierte la observación cruda en objetos tipados, extrae las referencias de estado que el resto de la función usará constantemente (`state`, `select`, `my_state`, `op_state`, premios), actualiza el sistema de creencia de cartas ocultas (`_update_cartas_tracking`) y decide si el turno actual es "nuevo" respecto a la última llamada, reiniciando en tal caso el `AttackPlan` y varios flags de un solo turno. A continuación calcula los "conteos de tablero" (`field_counts`, `hand_counts`, `discard_counts`), detecta condiciones de campo relevantes para nuestro mazo (Meganium en juego, Forest of Vitality, banca) y condiciones de estado alterado (veneno, quemadura, sueño, parálisis, confusión), y finalmente detecta si hubo un KO en el turno anterior del rival (`ko_last_turn`) para alimentar dos banderas de secuenciación de Supporters/Habilidad.

Todo lo que se calcula aquí es **entrada compartida**: ninguna rama posterior de puntuación (Boss's Orders, Supporters, energía, PLAY, ATTACH, RETREAT, ATTACK…) recalcula estos datos; simplemente los leen como variables ya resueltas en el ámbito de `agent()` o como `global`.

## Detalle por bloque

### Conversión de la observación y caso `select is None` (líneas 1292–1295)

```python
def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_deck
```

`to_observation_class` (de `cg.api`) transforma el `dict` crudo del motor en un objeto `Observation` navegable (`obs.current`, `obs.select`, `obs.logs`). Si `obs.select` es `None` no hay ninguna decisión pendiente que puntuar: es la entrega inicial del mazo (fase de mulligan/preparación), así que se devuelve directamente `my_deck`, la lista de 60 IDs de carta que compone el mazo fijo del agente.

### Extracción de referencias de estado (líneas 1297–1304)

```python
state = obs.current
select = obs.select
context = select.context
my_index = state.yourIndex
my_state = state.players[my_index]
op_state = state.players[1 - my_index]
my_prize = len(my_state.prize)
op_prize = len(op_state.prize)
```

- `state`: el `GameState` del turno (`turn`, `firstPlayer`, `players[0|1]`, `stadium`, `retreated`, `supporterPlayed`, banderas de condición…).
- `select`: la petición de decisión actual; `context` es su `SelectContext` (MAIN, SETUP_*, SWITCH, TO_ACTIVE, ACTIVATE, TO_HAND, DISCARD, ATTACH_FROM, …), consultado constantemente en el resto de `agent()` para saber qué tipo de puntuación aplicar.
- `my_index` / `my_state` / `op_state`: `state.yourIndex` indica cuál de las dos entradas de `state.players` somos nosotros; `op_state` es simplemente la otra (`1 - my_index`).
- `my_prize` / `op_prize`: número de cartas de premio que le **quedan** a cada jugador (cuanto más bajo, más cerca de ganar). Se usan en todo el archivo para evaluar urgencia de cierre de partida.

### Actualización de la creencia de cartas (línea 1306)

```python
_update_cartas_tracking(obs, my_index, my_state)
```

Llama a la función definida en la línea 839, que: (a) si `obs.current.turn == 1` y el turno anterior registrado era mayor (nueva partida), reinicia `CARTAS_ACTIVAS_EN_MAZO` vía `_init_cartas_tracking()` y pone a `False` `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan`; (b) en el primer escaneo de la partida hace `_first_turn_scan(my_state)`, y en los siguientes procesa `obs.logs` (`_process_logs`) y resincroniza contra el estado visible (`_sync_from_state`); (c) siempre llama a `_identify_prizes(obs, my_state)`. Este paso debe ejecutarse **antes** de que el resto del preámbulo lea `CARTAS_ACTIVAS_EN_MAZO`, porque `_evolve_possible_in_play` (línea 1381) ya consulta ese diccionario.

### Declaración de variables `global` (líneas 1308–1323)

```python
global plan
global pre_turn
global meganium_in_play
global forest_in_play
global ko_last_turn
global _ko_detected_this_turn
global _prev_op_prize
global we_go_first
global op_is_crustle_deck
global op_is_cornerstone_deck
global op_has_mega_kangaskhan
global _field_at_turn_start
global _poke_pad_target_id
global _ub_meowth_pending
global _dodge_immune_serial
global _dodge_immune_turn
```

Como `agent()` se invoca una vez por cada decisión (potencialmente varias veces por turno), estas variables son el único mecanismo para conservar información **entre llamadas**. Sus valores por defecto están definidos a nivel de módulo (líneas 398–482):

| Variable | Valor inicial | Significado |
|---|---|---|
| `plan` | `AttackPlan()` (línea 398) | Objeto con `attacker`, `target`, `attack_index`, `remain_hp`, `energy` (todos `-1`/`False` por defecto); el plan de ataque calculado para el turno en curso. |
| `pre_turn` | `0` | Último `state.turn` visto; sirve para detectar cambio de turno. |
| `meganium_in_play` / `forest_in_play` | `False` | Se recalculan cada llamada más abajo (líneas 1344–1401), pero se declaran aquí porque otras funciones del módulo (p.ej. `_grass_attach_unit`) las leen como `global` fuera de `agent()`. |
| `ko_last_turn` | `False` | Si el rival noqueó algo nuestro en su último turno. |
| `_ko_detected_this_turn` | `False` | Flag de "ya detectado" para no recalcular varias veces dentro del mismo turno. |
| `_prev_op_prize` | `6` | Premios del rival en la última vez que se evaluó contexto `MAIN`; comparar contra `op_prize` actual detecta si nosotros noqueamos algo. |
| `we_go_first` | `False` | Si nosotros somos quienes empiezan la partida. |
| `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan` | `False` | Banderas de detección de matchup (se fijan en el bloque siguiente, 1477–1985). |
| `_field_at_turn_start` | `{}` | Foto de `field_counts` tomada en la primera llamada de cada turno. |
| `_poke_pad_target_id` | `0` | Carta objetivo pendiente de Poke Pad. |
| `_ub_meowth_pending` | `False` | Si hay una búsqueda de Meowth con Ultra Ball pendiente de resolver. |
| `_dodge_immune_serial`, `_dodge_immune_turn` | `None`, `-1` | Estado auxiliar de inmunidad/esquive (no se tocan en este bloque). |

### Detección de quién empieza la partida (líneas 1325–1326)

```python
if state.firstPlayer >= 0:
    we_go_first = (state.firstPlayer == state.yourIndex)
```

`state.firstPlayer` vale `-1` mientras aún no se ha resuelto el volado/orden de turno; una vez fijado, se compara contra `state.yourIndex` para saber si el agente juega primero. Es relevante más adelante (fuera de este rango) para reglas del primer turno (p.ej. veto de estadio).

### Reinicio de estado al cambiar de turno (líneas 1328–1338)

```python
if pre_turn != state.turn:
    pre_turn = state.turn
    plan = AttackPlan()

    _field_at_turn_start = None

    _ko_detected_this_turn = False

    _poke_pad_target_id = 0

    _ub_meowth_pending = False
```

Como `agent()` puede llamarse varias veces dentro del mismo turno (una por cada decisión: jugar carta, adjuntar energía, atacar…), este `if` es el único punto donde se detecta la **frontera entre turnos** comparando `pre_turn` (el último turno procesado) contra `state.turn` (el turno actual). Al cruzar la frontera: se actualiza `pre_turn`, se crea un `AttackPlan()` nuevo (se descarta cualquier plan calculado el turno anterior), se marca `_field_at_turn_start = None` (se recalculará más abajo con el campo del turno nuevo), se resetea `_ko_detected_this_turn` (para volver a poder detectar un KO en este turno), y se limpian `_poke_pad_target_id` / `_ub_meowth_pending` (objetivos pendientes de turnos anteriores ya no aplican).

### Conteos de campo, mano y descarte (líneas 1340–1348)

```python
field_counts = defaultdict(int)
hand_counts = defaultdict(int)
discard_counts = defaultdict(int)

meganium_in_play = False
forest_in_play = False
has_ogerpon = False
has_hydrapple = False
bench_count = 0
```

Estos `defaultdict(int)` se recrean en **cada** llamada (no son `global`, viven en el ámbito local de `agent()`) y se rellenan a continuación recorriendo el estado visible. `meganium_in_play` y `forest_in_play` sí son `global` (declaradas arriba) y aquí se reinician a `False` antes de recalcularse; `has_ogerpon`, `has_hydrapple` y `bench_count` son puramente locales a esta llamada.

### Recorrido de activo + banca propios (líneas 1350–1359)

```python
for card in my_state.active + my_state.bench:
    if card is None:
        continue
    field_counts[card.id] += 1
    if card.id == Meganium:
        meganium_in_play = True
    if card.id == Hydrapple_ex:
        has_hydrapple = True
    if card.id == Teal_Mask_Ogerpon_ex:
        has_ogerpon = True
```

`field_counts[card.id]` cuenta cuántas copias de cada carta tenemos en juego (activo + banca), ignorando huecos vacíos (`None`). De paso fija tres banderas puntuales usadas más adelante en la puntuación: si hay `Meganium` en juego (activa `_grass_attach_unit()` = 2 y por tanto toda la lógica de "energía Planta cuenta doble"), si hay `Hydrapple_ex`, y si hay `Teal_Mask_Ogerpon_ex`.

### Conteo de banca ocupada (líneas 1361–1363)

```python
for pokemon in my_state.bench:
    if pokemon is not None:
        bench_count += 1
```

`bench_count` es el número de espacios de banca ocupados (banca máxima = 5 habitual en este formato); se usa después para reglas de "banca llena" como la de `_evolve_possible_in_play`.

### Foto del campo al inicio de turno (líneas 1365–1366)

```python
if _field_at_turn_start is None:
    _field_at_turn_start = dict(field_counts)
```

Como `_field_at_turn_start` se puso a `None` al detectar el cambio de turno (línea 1332), la **primera** llamada de `agent()` dentro de ese turno es la que efectivamente captura la foto (`dict(field_counts)`); llamadas posteriores del mismo turno no la vuelven a pisar, preservando el campo tal como estaba al empezar el turno (antes de jugar nada), útil para comparar "qué cambió este turno".

### Limpieza de objetivo de Poke Pad ya cumplido (líneas 1368–1369)

```python
if _poke_pad_target_id > 0 and field_counts.get(_poke_pad_target_id, 0) > 0:
    _poke_pad_target_id = 0
```

Si había un objetivo de Poke Pad pendiente (`_poke_pad_target_id`, una carta que se decidió ir a buscar) y esa carta ya apareció en el campo (por ejemplo, se jugó desde la mano tras un turno anterior), el objetivo se da por cumplido y se limpia para no seguir arrastrándolo.

### Conteos de mano y descarte (líneas 1371–1375)

```python
for card in my_state.hand:
    hand_counts[card.id] += 1

for card in my_state.discard:
    discard_counts[card.id] += 1
```

Análogos a `field_counts` pero para la mano propia y el propio descarte. `hand_counts` es el más usado en el resto del archivo (comprobar si tenemos tal carta jugable ahora mismo); `discard_counts` sirve sobre todo para evaluar recuperadores (Night Stretcher, etc., fuera de este rango).

### `_evolve_possible_in_play` (líneas 1377–1394)

```python
_evolve_possible_in_play = (
    (field_counts.get(Chikorita, 0) >= 1 and
     (hand_counts.get(Bayleef, 0) >= 1 or
      CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)) or
    ...
)
```

El comentario previo (líneas 1377–1380) explica la razón: con la banca **llena** (`bench_count` al máximo), un recurso de búsqueda como Ultra Ball o Poke Pad solo aporta valor si permite **evolucionar** un Pokémon ya en juego, porque no hay hueco para banquear una pieza nueva. La condición comprueba, para cada eslabón de las dos líneas de evolución del mazo (`Chikorita→Bayleef→Meganium`, `Applin→Dipplin→Hydrapple_ex`), si tenemos la pre-evolución en juego (`field_counts`) **y** la siguiente etapa está disponible, ya sea en la mano (`hand_counts`) o localizable en el mazo (`CARTAS_ACTIVAS_EN_MAZO[...][ESTADO_MAZO] > 0`, el sistema de creencia). El resultado es un booleano local que condiciona más adelante (fuera de este rango) la puntuación de búsquedas cuando la banca está llena.

### Estadio en juego (líneas 1396–1410)

```python
stadium_id = 0
for card in state.stadium:
    stadium_id = card.id

if stadium_id == Forest_of_Vitality:
    forest_in_play = True

neutralization_zone_active = (stadium_id == Neutralization_Zone)

watchtower_in_play = (stadium_id == Team_Rockets_Watchtower)
```

`state.stadium` es una lista (normalmente de 0 o 1 elemento); el bucle se queda con el `id` del último elemento (en la práctica, el único estadio activo, o `0` si no hay ninguno). A partir de ahí:
- `forest_in_play = True` si el estadio en juego es `Forest_of_Vitality` (acelera energía Planta propia); esta variable es `global` y ya se usa en otras funciones del módulo.
- `neutralization_zone_active`: local, indica si `Neutralization_Zone` está en juego.
- `watchtower_in_play`: local; el comentario (líneas 1405–1409) explica que `Team_Rockets_Watchtower` anula las Habilidades de todos los Pokémon `{C}` en juego (ambos jugadores), lo que incluye a `Meowth ex` — su Habilidad *Last-Ditch Catch* (buscar un Supporter al banquearlo) queda anulada mientras el estadio siga en juego, así que no conviene bajar ni buscar a Meowth ex hasta poder reemplazar el estadio (p.ej. con Forest of Vitality).

### Condiciones de estado alteradas (líneas 1412–1435)

```python
is_poisoned = my_state.poisoned
is_burned = my_state.burned
is_asleep = my_state.asleep
is_paralyzed = my_state.paralyzed
is_confused = my_state.confused
has_condition = is_poisoned or is_burned or is_asleep or is_paralyzed or is_confused

condition_blocks_action = is_paralyzed or is_asleep

condition_risky_attack = is_confused

condition_passive_damage = is_poisoned or is_burned

condition_urgency = 0
if is_paralyzed:
    condition_urgency += 5000
if is_asleep:
    condition_urgency += 3000
if is_confused:
    condition_urgency += 2000
if is_poisoned:
    condition_urgency += 1500
if is_burned:
    condition_urgency += 1200
```

Se leen las cinco banderas de estado alterado de nuestro Pokémon activo (`my_state.poisoned/burned/asleep/paralyzed/confused`) y se derivan tres categorías semánticas usadas más adelante en la puntuación:
- `condition_blocks_action`: parálisis o sueño **impiden** actuar con normalidad (no se puede atacar con seguridad / retirarse en algunos casos).
- `condition_risky_attack`: la confusión hace que atacar tenga riesgo (tirada de moneda para autolesionarse).
- `condition_passive_damage`: veneno/quemadura infligen daño pasivo cada turno, lo que añade urgencia a resolver la situación (retirarse, curar, etc.).

`condition_urgency` es un acumulador numérico de prioridad: cada condición suma un peso fijo (parálisis 5000 > sueño 3000 > confusión 2000 > veneno 1500 > quemadura 1200), reflejando qué tan grave es cada una para el plan del turno (más alto = más urgente de resolver). Estos pesos "redondos" son del mismo estilo que las prioridades fuertes descritas en el glosario (`docs/main.md`, punto 2) y se usan para inflar puntuaciones de opciones que resuelven la condición.

### Detección de KO del rival en su último turno (líneas 1437–1460)

```python
ko_last_turn = _ko_detected_this_turn

if not ko_last_turn:
    for log in obs.logs:
        if hasattr(log, 'type'):
            if (log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and
                    log.playerIndex != my_index and hasattr(log, 'fromArea') and
                    log.fromArea == AreaType.PRIZE):
                ko_last_turn = True
                break

if not ko_last_turn:
    if op_prize < _prev_op_prize:
        ko_last_turn = True

if not ko_last_turn:
    if context == SelectContext.TO_ACTIVE and not state.retreated:
        ko_last_turn = True

if ko_last_turn:
    _ko_detected_this_turn = True
```

`ko_last_turn` (global) responde a "¿nos noqueó el rival un Pokémon en su turno anterior?", determinado con tres comprobaciones en cascada (cada una solo se evalúa si la anterior no encontró nada):
1. **Por logs**: se recorre `obs.logs` buscando un evento `MOVE_CARD` hecho por el rival (`playerIndex != my_index`) cuyo origen sea la zona de premios (`fromArea == AreaType.PRIZE`) — tomar un premio es la consecuencia directa de noquear.
2. **Por comparación de premios**: si `op_prize < _prev_op_prize`, el rival tiene menos premios pendientes que la última vez que se registró en contexto `MAIN` (línea 1478, justo tras este rango), lo que indica que **nosotros** noqueamos algo del rival — nótese que esta rama en realidad detecta que *el conteo de premios rival bajó*, señal indirecta reutilizada aquí como aproximación robusta cuando los logs no son concluyentes.
3. **Atajo de contexto `TO_ACTIVE`** (línea 1456, el atajo mencionado en la tarea): si la decisión pedida es `SelectContext.TO_ACTIVE` (hay que promover un Pokémon de banca al activo) y `state.retreated` es `False` (el activo no se fue por retirada voluntaria), la única otra razón para necesitar promover un nuevo activo es que el activo anterior fue **noqueado** — así que se infiere `ko_last_turn = True` sin más comprobación.

Si cualquiera de las tres condiciones se cumple, se fija `_ko_detected_this_turn = True` para que, dentro del mismo turno, llamadas posteriores a `agent()` no tengan que repetir el cálculo (la primera línea del bloque, `ko_last_turn = _ko_detected_this_turn`, ya arrastra el resultado cacheado).

### Banderas de secuenciación de Supporters/Habilidad (líneas 1462–1476)

```python
_stamp_blocks_supp_chain = (ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1)

_lillie_blocks_fez_ability = (hand_counts.get(Lillie_Determination, 0) >= 1
                              and not state.supporterPlayed)
```

Dos banderas locales, calculadas aquí (ámbito de `agent()`) porque las consulta el bloque de puntuación de la Habilidad de Fezandipiti (*Flip the Script*) en **cualquier** contexto de la decisión, no solo en `PLAY`:
- `_stamp_blocks_supp_chain`: si nos noquearon el turno anterior (`ko_last_turn`) y todavía tenemos `Unfair_Stamp` en la mano, se debe jugar primero el Stamp y **después** la Habilidad de Fezandipiti — bloquea temporalmente la Habilidad hasta que el Stamp se juegue (momento en que sale de la mano y esta bandera pasa a `False`).
- `_lillie_blocks_fez_ability`: petición explícita del usuario (según el comentario, líneas 1469–1473): si tenemos `Lillie_Determination` en mano y aún no se ha jugado ningún Supporter este turno (`not state.supporterPlayed`), se prioriza jugar Lillie's Determination antes que la Habilidad de Fezandipiti. Como Lillie's Determination es un Supporter, al jugarse desaparece de la mano y `state.supporterPlayed` pasa a `True`, con lo que esta bandera se vuelve `False` en la siguiente llamada y la Habilidad de Fezandipiti queda re-habilitada (mencionada como prioridad `30000` en el comentario, fuera de este rango).

## Interacciones

- **Con el bloque siguiente (1477–1985, detección de matchup)**: reutiliza `field_counts`, `hand_counts`, `stadium_id`, `bench_count` y las banderas `has_ogerpon`/`has_hydrapple` calculadas aquí; también es donde, justo después de este rango (línea 1478), se actualiza `_prev_op_prize = op_prize` cuando `context == SelectContext.MAIN`, cerrando el ciclo de comparación usado en la detección de `ko_last_turn`.
- **Con `AttackPlan` (línea 391)**: el `plan` global creado/reiniciado aquí (línea 1330) es el objeto que rellena el bloque de análisis de amenaza (~1985–2900) y que consulta la puntuación de ATTACK al final de `agent()`.
- **Con el sistema de creencia (`docs/main-03-state-tracking-and-belief.md`)**: `_update_cartas_tracking` y las lecturas de `CARTAS_ACTIVAS_EN_MAZO`/`ESTADO_MAZO` en `_evolve_possible_in_play` dependen de las funciones documentadas en ese archivo (`_init_cartas_tracking`, `_first_turn_scan`, `_process_logs`, `_sync_from_state`, `_identify_prizes`).
- **Con `_grass_attach_unit()` / `_can_attack_eff()` (líneas 412–465)**: dependen de la variable global `meganium_in_play` fijada en este preámbulo (línea 1354) para saber si la energía Planta cuenta doble.
- **Con la puntuación de Habilidad de Fezandipiti (fuera de este rango)**: consulta directamente `_stamp_blocks_supp_chain` y `_lillie_blocks_fez_ability` definidas aquí.
- **Con el contexto `TO_ACTIVE`/`SWITCH` (bloque 4489–5970)**: la inferencia de KO vía `context == SelectContext.TO_ACTIVE and not state.retreated` (línea 1456) es un atajo que evita depender solo de logs; si esa inferencia fuera incorrecta (p.ej. un caso donde `state.retreated` no refleja bien una retirada voluntaria), `ko_last_turn` quedaría mal fijado para el resto del turno, afectando reglas de urgencia (`condition_urgency` no depende de esto, pero sí otras reglas de Boss's/Supporters documentadas en `main-08` y `main-09`).
