# main.py — Preámbulo de agent() y conteos de tablero

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este bloque es el arranque de `agent()`: convierte la observación cruda en objetos tipados, extrae las referencias de estado que el resto de la función usará constantemente (`state`, `select`, `my_state`, `op_state`, premios), actualiza el sistema de creencia de cartas ocultas (`_update_cartas_tracking`) y detecta si el turno actual es "nuevo" respecto a la última llamada, reiniciando en tal caso el `AttackPlan` y los flags de un solo turno. A continuación calcula los "conteos de tablero" (`field_counts`, `hand_counts`, `discard_counts`), detecta condiciones de campo relevantes para nuestro mazo (Meganium en juego, Forest of Vitality, banca, estadios rivales) y de estado alterado (veneno, quemadura, sueño, parálisis, confusión), y finalmente detecta si el rival nos noqueó algo en su último turno (`ko_last_turn`) para alimentar dos banderas de secuenciación de Supporters/Habilidad.

Todo lo que se calcula aquí es **entrada compartida**: ninguna rama posterior de puntuación (Boss's Orders, Supporters, energía, PLAY, ATTACH, RETREAT, ATTACK…) recalcula estos datos; los leen como variables ya resueltas en el ámbito de `agent()` o como `global`.

## Detalle por bloque

### Conversión de la observación y caso sin decisión pendiente

`to_observation_class` (de `cg.api`) transforma el `dict` crudo del motor en un objeto `Observation` navegable (`obs.current`, `obs.select`, `obs.logs`). Si `obs.select` es `None` no hay ninguna decisión que puntuar: es la entrega inicial del mazo (fase de mulligan/preparación), así que se devuelve directamente `my_deck`, la lista de 60 IDs que compone el mazo fijo del agente.

### Extracción de referencias de estado

- `state` (`obs.current`): el `GameState` del turno (`turn`, `firstPlayer`, `players`, `stadium`, `retreated`, `supporterPlayed`, banderas de condición…).
- `select` / `context`: la petición de decisión actual y su `SelectContext` (MAIN, SETUP_*, SWITCH, TO_ACTIVE, ACTIVATE, TO_HAND, DISCARD, ATTACH_FROM, …), consultado en todo el resto de `agent()` para saber qué tipo de puntuación aplicar.
- `my_index` / `my_state` / `op_state`: `state.yourIndex` indica cuál de las dos entradas de `state.players` somos nosotros; `op_state` es la otra.
- `my_prize` / `op_prize`: premios que le **quedan** a cada jugador (cuanto más bajo, más cerca de ganar); se usan en todo el archivo para evaluar la urgencia de cierre de partida.

### Actualización de la creencia de cartas

`_update_cartas_tracking(obs, my_index, my_state)`: (a) si `state.turn == 1` y el turno registrado anterior era mayor (nueva partida), reinicia `CARTAS_ACTIVAS_EN_MAZO` vía `_init_cartas_tracking()` y pone a `False` los flags persistentes de matchup (`op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan`); (b) en el primer escaneo hace `_first_turn_scan(my_state)` y en los siguientes procesa `obs.logs` (`_process_logs`) y resincroniza contra el estado visible (`_sync_from_state`); (c) siempre llama a `_identify_prizes`. Este paso debe ejecutarse **antes** de que el preámbulo lea `CARTAS_ACTIVAS_EN_MAZO`, porque `_evolve_possible_in_play` ya consulta ese diccionario.

### Variables `global` del agente

Como `agent()` se invoca una vez por cada decisión (varias veces por turno), las variables `global` son el único mecanismo para conservar información **entre llamadas**. Las principales:

| Variable | Significado |
|---|---|
| `plan` | El `AttackPlan` del turno en curso (`attacker`, `target`, `attack_index`, `remain_hp`, `energy`). |
| `pre_turn` | Último `state.turn` visto; detecta el cambio de turno. |
| `meganium_in_play` / `forest_in_play` | Se recalculan en cada llamada, pero son `global` porque funciones de módulo (p.ej. `_grass_attach_unit`) las leen fuera de `agent()`. |
| `ko_last_turn` / `_ko_detected_this_turn` | Si el rival nos noqueó en su último turno, y su caché "ya detectado" dentro del turno. |
| `_prev_op_prize` | Premios del rival la última vez que se evaluó contexto `MAIN`; comparar contra `op_prize` detecta que nosotros noqueamos algo. |
| `we_go_first` | Si empezamos la partida. |
| `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan` | Flags de matchup persistentes entre sub-decisiones (el resto de `op_is_*` son locales; ver `main-06`). |
| `_field_at_turn_start` | Foto de `field_counts` tomada en la primera llamada de cada turno. |
| `_poke_pad_target_id` | Carta objetivo pendiente de un Poke Pad ya jugado (el handler de selección la prioriza). |
| `_ub_meowth_pending` | Una Ultra Ball resuelta **este turno** eligió buscar Meowth ex: obliga a bajarlo mientras el Supporter siga libre (entrada de alta prioridad en PLAY, motor Meowth→Lillie's). |
| `_ub_fez_pending` | Hermano del anterior para la cadena UB → Fezandipiti ex → *Flip the Script*: una Ultra Ball de **este turno** eligió buscar Fezandipiti ex, así que el cuerpo baja aunque otro veto lo mate (la búsqueda ya se pagó con dos descartes y el único motivo de cavarlo es cobrar el robo de 3 hoy). |
| `_ub_engine_pivot_turn` | Armado por `_ub_engine_refresh_pivot` (la Ultra Ball se puntuó como pivote de refresco del motor): fuerza que el FETCH de esa Ultra Ball elija Meowth ex. |
| `_ld_supp_comprometido` | Id del Supporter que trajo el *Last-Ditch Catch* de un Meowth ex bajado **este turno** (`appearThisTurn`: el cuerpo de 2 premios ya está pagado). Mientras el hueco de Supporter siga libre, ese id se queda con el turno: piso `SCORE_LD_SUPP_COMPROMETIDO` (8000) en su `PLAY`, por encima de la banda normal de cualquier otro Supporter. |
| `_dodge_immune_serial` / `_dodge_immune_turn` | Persistencia de la inmunidad por *Splashing Dodge* (ver `main-06`). |

### Detección de quién empieza

`state.firstPlayer` vale `-1` mientras no se resuelve el orden de turno; una vez fijado, `we_go_first = (state.firstPlayer == state.yourIndex)`. Es relevante para reglas del primer turno (veto de estadio, Lillie's forzada en el primer turno propio).

### Reinicio de estado al cambiar de turno

El `if pre_turn != state.turn:` es el único punto donde se detecta la **frontera entre turnos**. Al cruzarla: se actualiza `pre_turn`, se crea un `AttackPlan()` nuevo (se descarta el plan del turno anterior), se marca `_field_at_turn_start = None` (se recalculará con el campo del turno nuevo), se resetea `_ko_detected_this_turn`, y se limpian los cinco flags de encadenamiento de un solo turno: `_poke_pad_target_id`, `_ub_meowth_pending`, `_ub_fez_pending`, `_ub_engine_pivot_turn` y `_ld_supp_comprometido` (objetivos/motores/compromisos pendientes de turnos anteriores ya no aplican).

### Conteos de campo, mano y descarte

`field_counts`, `hand_counts` y `discard_counts` son `defaultdict(int)` recreados en **cada** llamada (ámbito local). El recorrido de `my_state.active + my_state.bench` rellena `field_counts` (copias de cada carta en juego, ignorando huecos `None`) y fija tres banderas puntuales: `meganium_in_play` (activa `_grass_attach_unit() == 2` y toda la lógica de "energía Planta cuenta doble" de *Wild Growth*), `has_hydrapple` y `has_ogerpon`. `bench_count` cuenta los espacios de banca ocupados (máximo 5). `hand_counts` es el conteo más consultado del archivo ("¿tenemos tal carta jugable ahora?"); `discard_counts` sirve sobre todo para los recuperadores (Night Stretcher, Lana's Aid).

Dos ajustes inmediatos:
- **Foto del campo**: como `_field_at_turn_start` se puso a `None` al cambiar de turno, la primera llamada del turno captura `dict(field_counts)`; las llamadas posteriores no la pisan, preservando el campo tal como estaba antes de jugar nada.
- **Limpieza de Poke Pad**: si `_poke_pad_target_id` apunta a una carta que ya apareció en el campo, el objetivo se da por cumplido y se limpia.

### `_evolve_possible_in_play`

Con la banca **llena**, un recurso de búsqueda (Ultra Ball / Poke Pad) solo aporta valor si permite **evolucionar** un Pokémon ya en juego, porque no hay hueco para banquear piezas nuevas. La condición comprueba, para cada eslabón de las dos líneas evolutivas del mazo (`Chikorita→Bayleef→Meganium`, `Applin→Dipplin→Hydrapple_ex`), si tenemos la pre-evolución en juego (`field_counts`) **y** la siguiente etapa está disponible en mano (`hand_counts`) o localizable en el mazo (`CARTAS_ACTIVAS_EN_MAZO[...][ESTADO_MAZO] > 0`). El booleano condiciona la puntuación de búsquedas cuando la banca está llena.

### Estadio en juego

El bucle sobre `state.stadium` se queda con el `id` del estadio activo (o `0`). De ahí derivan:
- `forest_in_play`: `Forest_of_Vitality` en juego (acelera la energía Planta propia); `global` porque la leen otras funciones del módulo.
- `neutralization_zone_active`: `Neutralization_Zone` en juego (anula el daño de nuestros ex a Pokémon rivales sin Rule Box; ver la estrategia dedicada en la memoria y `main-07`).
- `watchtower_in_play`: `Team_Rockets_Watchtower` anula las Habilidades de todos los Pokémon incoloros en juego (ambos jugadores) — incluye a Meowth ex, cuya Habilidad *Last-Ditch Catch* (buscar un Supporter al banquearlo) queda anulada mientras el estadio siga; no conviene bajar ni buscar Meowth ex hasta poder reemplazarlo (p.ej. con Forest of Vitality, que por eso recibe prioridad alta de reemplazo cuando el motor Meowth está vivo).

### Condiciones de estado alteradas

Se leen las cinco banderas del activo propio (`poisoned/burned/asleep/paralyzed/confused`) y se derivan tres categorías semánticas: `condition_blocks_action` (parálisis o sueño impiden actuar), `condition_risky_attack` (confusión: atacar exige tirada de moneda), `condition_passive_damage` (veneno/quemadura: daño pasivo por turno). `condition_urgency` es un acumulador numérico con pesos fijos (parálisis 5000 > sueño 3000 > confusión 2000 > veneno 1500 > quemadura 1200) que infla las puntuaciones de las opciones que resuelven la condición.

### Detección de KO del rival en su último turno

`ko_last_turn` responde a "¿nos noqueó el rival un Pokémon en su turno anterior?", con tres comprobaciones en cascada (cada una solo si la anterior no encontró nada):
1. **Por logs**: un evento `MOVE_CARD` del rival (`playerIndex != my_index`) con origen en la zona de premios (`fromArea == AreaType.PRIZE`) — tomar premio es la consecuencia directa de noquear.
2. **Por comparación de premios**: `op_prize < _prev_op_prize` (el contador de referencia se actualiza solo en contexto `MAIN`, para que decisiones intermedias del turno no pisen el valor antes de compararlo).
3. **Atajo de contexto `TO_ACTIVE`**: si la decisión pedida es promover un Pokémon al activo y `state.retreated` es `False` (no hubo retirada voluntaria), la única razón para necesitar un activo nuevo es que el anterior fue noqueado.

Si cualquiera se cumple, `_ko_detected_this_turn = True` cachea el resultado para el resto del turno.

### Banderas de secuenciación de Supporters/Habilidad

Dos banderas locales que consulta el bloque de la Habilidad de Fezandipiti (*Flip the Script*) en **cualquier** contexto:
- `_stamp_blocks_supp_chain`: si nos noquearon el turno anterior y tenemos `Unfair_Stamp` en mano, primero se juega el Stamp y **después** la Habilidad — el flag se apaga solo cuando el Stamp sale de la mano. El mismo gate (`ko_last_turn` + Stamp en mano) vetan también Boss's/Lana's/Dawn/Xerosic en sus scorers.
- `_lillie_blocks_fez_ability`: con `Lillie_Determination` en mano y `not state.supporterPlayed`, se prioriza jugar Lillie's antes que la Habilidad de Fezandipiti; al jugarse, `supporterPlayed` pasa a `True` y la Habilidad queda re-habilitada.

## Interacciones

- **Con la detección de matchup (`main-06`)**: reutiliza `field_counts`, `hand_counts`, `stadium_id`, `bench_count`, `has_ogerpon`/`has_hydrapple`; el cierre `_prev_op_prize = op_prize` en contexto `MAIN` completa el ciclo de la detección de `ko_last_turn`.
- **Con `AttackPlan` (`main-02`, `main-07`)**: el `plan` global creado/reiniciado aquí es el objeto que rellena el bloque de análisis de amenaza y que consulta la puntuación de ATTACK.
- **Con el sistema de creencia (`main-03`)**: `_update_cartas_tracking` y las lecturas de `CARTAS_ACTIVAS_EN_MAZO`/`ESTADO_MAZO` en `_evolve_possible_in_play`.
- **Con `_grass_attach_unit()` / `_can_attack_eff()`**: dependen de `meganium_in_play` fijada en este preámbulo.
- **Con el motor Ultra Ball → Meowth → Lillie's (`main-11`/`main-12`)**: `_ub_meowth_pending` y `_ub_engine_pivot_turn` son los dos hilos que conectan el FETCH de una Ultra Ball con el PLAY de Meowth ex en la siguiente decisión del mismo turno; su reset por turno evita arrastrar el compromiso a turnos donde ya no aplica.
- **Con la puntuación de la Habilidad de Fezandipiti**: consulta directamente `_stamp_blocks_supp_chain` y `_lillie_blocks_fez_ability`.
- **Con `TO_ACTIVE`/`SWITCH` (`main-14`)**: la inferencia de KO vía contexto `TO_ACTIVE` sin retirada es un atajo que evita depender solo de logs; si fuera incorrecta, `ko_last_turn` quedaría mal fijado para el resto del turno, afectando reglas de Boss's/Supporters (`main-08`, `main-09`).
