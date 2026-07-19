# `main.py` — Visión general y guía de lectura

Este documento es el **índice maestro** y el **glosario compartido** de la documentación de bajo nivel de `main.py`. Cada región del archivo tiene su propio documento detallado (ver [Mapa de regiones](#4-mapa-de-regiones-documentos-detallados)); todos ellos asumen los conceptos definidos aquí.

`main.py` (~12.900 líneas) implementa un agente **heurístico** (sin aprendizaje) para un simulador de Pokémon TCG. Expone una única función pública:

```python
def agent(obs_dict: dict) -> list[int]
```

que recibe la observación cruda del juego y devuelve la **lista de índices de opción** que el motor debe ejecutar.

---

## 1. El contrato `agent(obs_dict)`

- **Entrada** `obs_dict`: un diccionario que `to_observation_class()` (de `cg.api`) convierte en un objeto `Observation` con:
  - `obs.current` (`state`): estado del turno — `turn`, `yourIndex`, `firstPlayer`, `players[0|1]`, `stadium`, banderas de estado, etc.
  - `obs.select`: la decisión pedida — `context` (un `SelectContext`), `option` (lista de opciones jugables), `minCount`/`maxCount`, `effect`, `deck`.
  - `obs.logs`: eventos ocurridos desde la última observación (ataques, adjuntes, evoluciones, KOs, volados de moneda…).
- **Salida**: lista de enteros que indexan `select.option`. Longitud entre `minCount` y `maxCount`.
- **Caso especial**: si `obs.select is None`, se devuelve `my_deck` (la lista de 60 IDs) — es la entrega inicial del mazo / mulligan.

### Mecanismo de selección (cómo se elige la opción)

El agente NO usa árboles de búsqueda: **puntúa cada opción** y elige la de mayor puntaje. El flujo, al final de `agent()` (líneas ~5970 y ~12760–12919), es:

1. `scores = []`; se recorre `for o in select.option:` y a cada opción se le asigna un `score` según su `o.type` (ver `OptionType`) y el contexto. `scores.append(score)`.
2. Convención de puntaje: **mayor = mejor**. Un `score = -1` (o negativo) es un **veto** (opción no deseada). Valores altos y "redondos" (p.ej. `21500`, `40000`, `50000`) son prioridades fuertes fijadas por reglas de matchup; suelen sobrescribir el puntaje base con `max()` o asignación directa.
3. En contexto `MAIN` se aplica además un **orden de jugada por tiers** (`_play_order_tier`, ~12850): energía-de-KO(6) > estadio(5) > desarrollo de Pokémon/evolución(4) > Poke Pad(3) > Bug Catching Set(2) > carga de energía(1) > resto(0). Solo reordena opciones con `score > 0`, así que los vetos se respetan.
4. Se ordenan los índices por la clave `(tier, score)` descendente y se devuelven los primeros `maxCount` (con reglas extra para `SETUP_BENCH_POKEMON` y vetos de estadio del primer turno).

> Para entender una decisión concreta: el puntaje de una opción se fija en su rama `elif o.type == OptionType.X` dentro del gran bucle; los vetos/prioridades se calculan **antes** del bucle como banderas (`_win_via_boss_gust`, `_meowth_devel_lillie`, `op_is_crustle_deck`, `plan.*`, …).

---

## 2. Conceptos y glosario compartido

### Energía efectiva y Meganium
El mazo es de tipo **Planta/ex**. `Meganium` (Habilidad *Wild Growth*) hace que **cada energía Planta cuente doble** para pagar ataques.
- `_grass_mult()` → `2` si hay Meganium en juego, `1` si no.
- **Energía efectiva** = energía física × multiplicador. Las comprobaciones de "¿puede atacar?" usan energía efectiva (`_can_attack_eff`), no física.
- `_physical_energy(effective_len)` hace la conversión inversa cuando hace falta razonar en cartas reales.

### `OptionType` (valor numérico → significado)
`7 = PLAY` (jugar carta de la mano) · `8 = ATTACH` (adjuntar energía) · `9 = EVOLVE` · `10 = ABILITY` · `12 = RETREAT` · `13 = ATTACK` · `14 = END` (terminar turno) · `3 = CARD` (elegir un objetivo Pokémon/carta) · `6 = ENERGY` (elegir energía) · `NUMBER/YES/NO` (respuestas a efectos) · `SPECIAL_CONDITION`.

### `SelectContext` (qué decisión se pide)
`MAIN` (turno normal, todas las jugadas) · `SETUP_ACTIVE_POKEMON` / `SETUP_BENCH_POKEMON` (preparación inicial) · `SWITCH` / `TO_ACTIVE` (promover un banca al activo) · `ACTIVATE` (confirmar una habilidad/efecto) · `TO_HAND` (llevar carta a la mano: Poke Pad, Ultra Ball…) · `DISCARD` · `ATTACH_FROM` (objetivo de adjunte, p.ej. *Ripening Charge*) · `RECOVER_/AFFECT_SPECIAL_CONDITION` · `COIN_HEAD` / `IS_FIRST`.

### Seguimiento de cartas (creencia)
`CARTAS_ACTIVAS_EN_MAZO[card_id][ESTADO]` mantiene, por carta, **cuántas copias** hay en cada zona (mazo, mano, banca, activo, descarte, premios). `ESTADO_MAZO` es el índice de "en el mazo". Se actualiza cada turno desde la observación visible y desde `obs.logs`. Es lo que permite razonar sobre cartas ocultas (p.ej. "¿queda una `Lillie's Determination` en el mazo?" → `CARTAS_ACTIVAS_EN_MAZO[Lillie_Determination][ESTADO_MAZO] > 0`).

### Estado global entre turnos
Variables `global` que persisten entre llamadas: `plan` (`AttackPlan` del turno), `we_go_first`, `meganium_in_play`, `forest_in_play`, `ko_last_turn`, `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan`, `_field_at_turn_start`, `_poke_pad_target_id`, `_ub_meowth_pending`, `_dodge_immune_*`. Se reinician al detectar cambio de turno (`pre_turn != state.turn`).

### Detección de matchup (`op_is_*_deck`)
Al inicio de `agent()` se inspeccionan las cartas rivales visibles para clasificar el mazo enemigo (`op_is_crustle_deck`, `op_is_fire_deck`, `op_is_alakazam_deck`, `op_has_mega_starmie_active`, …). Muchas reglas de puntuación se activan **solo** contra ciertos arquetipos.

### Nuestro mazo (arquetipo)
- **Líneas de ataque**: `Chikorita → Bayleef → Meganium` (acelerador + atacante), `Applin → Dipplin → Hydrapple ex` (atacante ex escalable), `Teal Mask Ogerpon ex` (tanque/atacante con *Teal Dance*), `Tapu Bulu` (atacante no-ex pesado), `Fezandipiti ex`, `Pinsir`.
- **Utilidad**: `Meowth ex` (Habilidad *Last-Ditch Catch*: al bajarlo, busca un Supporter).
- **Supporters**: `Lillie's Determination` (baraja la mano y roba), `Boss's Orders` (sube un banca rival al activo), `Lana's Aid`, `Dawn`.
- **Objetos**: `Ultra Ball`, `Night Stretcher`, `Bug Catching Set`, `Poke Pad`, `Unfair Stamp`.
- **Estadio**: `Forest of Vitality` (acelera energía Planta).

---

## 3. Estructura de alto nivel de `main.py`

| Rango de líneas | Contenido |
|---|---|
| 1–389 | Imports, carga de `deck.csv`, `card_table`, `RETREAT_COST`, constantes de ID de carta, conjuntos de IDs (matchup/amenaza), `_validate_id_constants`, constantes `SCORE_*`/`BOSS_*`. |
| 391–670 | Núcleo de cálculo: `AttackPlan` y ayudantes de energía/daño/ataque. |
| 495–860 | Seguimiento de estado y creencia del mazo/premios. |
| 861–1291 | Utilidades de puntuación puntual (`get_card`, `pokemon_score`, `_eval_ub_best_target`, …). |
| 1292–12919 | `agent()` — la función principal (ver desglose abajo). |

### `agent()` por dentro

| Rango | Bloque |
|---|---|
| 1292–1476 | Preámbulo: conversión, estado, reinicio de turno, conteos de campo/mano. |
| 1477–1985 | Recuento de tablero, estadio, **detección de matchup**, debilidades/inmunidades. |
| 1985–2900 | Pre-escaneo de opciones, **análisis de amenaza** y cálculo del `AttackPlan` (KO, lookahead, trades). |
| ~2900–3590 | **Escalera de puntuación de `Boss's Orders`** (`values[Boss_Orders]`). |
| 3590–4489 | Valoración de Supporters (Lillie/Lana/Dawn), banderas de decisión (`_win_via_boss_gust`, `_bcs_playable_in_hand`, `_meowth_devel_lillie`, `_ready_attacker_count`, flags anti-Crustle). |
| 4489–5970 | `energy_score` (puntuación de adjunte de energía) y contextos `ACTIVATE`/`SWITCH`/`TO_ACTIVE`/moneda. |
| 5970–8684 | **Bucle de puntuación** — contexto de **búsqueda de cartas** (`NUMBER/YES/NO` y `CARD`: mazo, descarte, a-mano, setup). |
| 8684–11008 | Bucle — puntuación de **`PLAY`**. |
| 11008–11608 | Bucle — **`ATTACH` / `EVOLVE` / `ABILITY`**. |
| 11608–12609 | Bucle — **`RETREAT`**. |
| 12609–12761 | Bucle — **`ATTACK` / `END` / `SPECIAL_CONDITION`**. |
| 12763–12919 | **Finalización**: overrides de Poke Pad / Ultra Ball, veto de estadio, tiers de orden de jugada, ordenación y `return`. |

---

## 4. Mapa de regiones (documentos detallados)

Núcleo y ayudantes:
- [Constantes y configuración](main-01-constants-and-config.md)
- [Núcleo de cálculo: energía, daño y ataque](main-02-core-calc-helpers.md)
- [Seguimiento de estado y creencia](main-03-state-tracking-and-belief.md)
- [Utilidades de puntuación](main-04-scoring-helpers.md)

Interior de `agent()`:
- [Preámbulo y conteos](main-05-agent-setup.md)
- [Detección de matchup, debilidades e inmunidades](main-06-agent-matchup-detection.md)
- [Análisis de amenaza y plan de ataque](main-07-agent-threat-and-plan.md)
- [Escalera de Boss's Orders](main-08-agent-boss-orders.md)
- [Supporters y banderas de decisión](main-09-agent-supporters-and-flags.md)
- [Puntuación de energía y contextos de cambio](main-10-agent-energy-and-switch.md)
- [Puntuación de búsqueda de cartas](main-11-agent-card-search-scoring.md)
- [Puntuación de PLAY](main-12-agent-play-scoring.md)
- [Puntuación de ATTACH / EVOLVE / ABILITY](main-13-agent-attach-evolve-ability.md)
- [Puntuación de RETREAT](main-14-agent-retreat-scoring.md)
- [Puntuación de ATTACK / END y finalización](main-15-agent-attack-end-finalize.md)

Integración con el simulador (`cg/`): ver [cg.api](cg-api.md), [cg.game](cg-game.md), [cg.sim](cg-sim.md), [cg.utils](cg-utils.md). Herramientas de depuración: ver [Reproducción de logs (`utils/log_replay.py`)](utils-log-replay.md).

---

## 5. Cómo depurar una decisión

1. Reproducir el paso con la observación real: cargar el `log/<id>.json`, tomar el item con `observation.select` y `current.yourIndex == <nuestro índice>`, y llamar `main.agent(obs)` (con `PYTHONPATH=$PWD`). La acción es una lista de índices sobre `select.option`.
2. `utils/split_turns.py` divide un log en turnos; `utils/log_replay.py` reproduce un log completo y compara con la acción registrada (ver [utils-log-replay.md](utils-log-replay.md)).
3. Las regresiones de decisiones concretas viven en `tests/` con **fixtures** reales en `tests/fixtures/` (p.ej. `marnie_grimmsnarl_step51.json`).
4. `_debug_log_decision()` imprime el ranking de opciones cuando `PTCG_DEBUG` está activo.

> Muchas reglas de puntuación citan en comentarios el **id de partida** (`log 86xxxxxx`) que las motivó: son correcciones dirigidas por casos reales. Al modificar una rama, buscar ese id ayuda a entender la intención original.
