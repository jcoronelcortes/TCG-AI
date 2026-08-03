# `main.py` — Visión general y guía de lectura

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

Este documento es el **índice maestro** y el **glosario compartido** de la documentación de bajo nivel de `main.py`. Cada región del archivo tiene su propio documento detallado (ver [Mapa temático](#3-mapa-temático-documentos-detallados)); todos ellos asumen los conceptos definidos aquí.

`main.py` implementa un agente **heurístico** (sin aprendizaje) para el simulador de Pokémon TCG del *PTCG AI Battle Challenge*. Expone una única función pública:

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

### Mecanismo de selección: puntajes + argmax por `(tier, score)`

El agente NO usa árboles de búsqueda: **puntúa cada opción** y elige la de mayor puntaje. El flujo, en el gran bucle de puntuación y la finalización de `agent()`, es:

1. `scores = []`; se recorre `for o in select.option:` y a cada opción se le asigna un `score` según su `o.type` (ver `OptionType`) y el contexto. `scores.append(score)`.
2. Convención de puntaje: **mayor = mejor**. Un `score = -1` (o negativo) es un **veto** (opción no deseada). Valores altos y "redondos" (p.ej. `21500`, `40000`, `50000`) son prioridades fuertes fijadas por reglas de matchup; suelen sobrescribir el puntaje base con `max()` o asignación directa.
3. En contexto `MAIN` se aplica además un **orden de jugada por tiers** (`_play_order_tier`): energía-de-KO > estadio > evolución (y bajar básicos si no hay BCS pendiente) > Poke Pad > Bug Catching Set > bajar básicos con BCS pendiente > carga de energía > resto. Solo reordena opciones con `score > 0`, así que los vetos se respetan.
4. Se ordenan los índices por la clave `(tier, score)` descendente y se devuelven los primeros `maxCount` (con reglas extra para `SETUP_BENCH_POKEMON` y vetos de estadio del primer turno).

> Para entender una decisión concreta: el puntaje de una opción se fija en su rama `elif o.type == OptionType.X` dentro del gran bucle (o en un scorer extraído `_score_*`, ver abajo); los vetos/prioridades se calculan **antes** del bucle como banderas (`_win_via_boss_gust`, `_meowth_devel_lillie`, `op_is_crustle_deck`, `plan.*`, …).

### Scorers extraídos y `DecisionContext`

Las ramas más grandes del bucle de `PLAY` se han extraído a funciones puras de módulo `_score_<carta>_play(ctx)` que reciben un `DecisionContext` (instantánea de ~60 campos del estado del turno): `_score_boss_orders_play`, `_score_unfair_stamp_play`, `_score_xerosic_play`, `_score_poke_pad_play`, `_score_night_stretcher_play`, `_score_forest_of_vitality_play`, `_score_bug_catching_set_play`, `_score_ultra_ball_play`, `_score_lillie_determination_play` y `_score_lanas_aid_play`. La de Ultra Ball es a su vez un orquestador: `_ub_derive_flags` → `_ub_score_before_overrides` (con los predicados de veto `_ub_cancel_stamp/_fez/_lillie/_meowth` y la valoración `_ub_target_score`) → `_ub_terminal_overrides` (ver [main-refactor-ultra-ball-plan.md](main-refactor-ultra-ball-plan.md), documento histórico del refactor).

---

## 2. Conceptos y glosario compartido

### Energía efectiva y Meganium (*Wild Growth*)
El mazo es de tipo **Planta/ex**. `Meganium` (Habilidad *Wild Growth*) hace que **cada energía Planta cuente doble** para pagar ataques.
- `_grass_mult()` → `2` si hay Meganium en juego, `1` si no.
- **Energía efectiva** = energía física × multiplicador. Las comprobaciones de "¿puede atacar?" usan energía efectiva (`_can_attack_eff`), no física.
- `_physical_energy(effective_len)` hace la conversión inversa cuando hace falta razonar en cartas reales.
- `_plan_de_planta(...)` es la **lectura de mesa en clave de energía**: cuántas Plantas nuevas sabe usar el campo (`demanda`) y si alguna pone a atacar a un cuerpo hoy (`desbloquea_hoy`). Mide el déficit de cada `MAIN_ATTACKERS` en **cartas** y cuenta las vías de adjunte vivas del turno. Ver [main-02](main-02-core-calc-helpers.md).

### `OptionType` (valor numérico → significado)
`7 = PLAY` (jugar carta de la mano) · `8 = ATTACH` (adjuntar energía) · `9 = EVOLVE` · `10 = ABILITY` · `12 = RETREAT` · `13 = ATTACK` · `14 = END` (terminar turno) · `3 = CARD` (elegir un objetivo Pokémon/carta) · `6 = ENERGY` (elegir energía) · `NUMBER/YES/NO` (respuestas a efectos) · `SPECIAL_CONDITION`.

### `SelectContext` (qué decisión se pide)
`MAIN` (turno normal, todas las jugadas) · `SETUP_ACTIVE_POKEMON` / `SETUP_BENCH_POKEMON` (preparación inicial) · `SWITCH` / `TO_ACTIVE` (promover un banca al activo) · `ACTIVATE` (confirmar una habilidad/efecto) · `TO_HAND` (llevar carta a la mano: Poke Pad, Ultra Ball…) · `DISCARD` · `ATTACH_FROM` (objetivo de adjunte, p.ej. *Ripening Charge*) · `DAMAGE` (elegir objetivo de daño, p.ej. *Cruel Arrow* de Fezandipiti ex: se evalúa TODO el campo rival por daño **efectivo** — KO > chip > inmunes) · `RECOVER_/AFFECT_SPECIAL_CONDITION` · `COIN_HEAD` / `IS_FIRST`.

### Seguimiento de cartas (creencia)
`CARTAS_ACTIVAS_EN_MAZO[card_id][ESTADO]` mantiene, por carta, **cuántas copias** hay en cada zona; los estados son las claves `ESTADO_MAZO`, `ESTADO_MANO`, `ESTADO_BANCA` (en juego), `ESTADO_DESCARTE` y `ESTADO_PREMIO`. Se inicializa con `_init_cartas_tracking()`, se actualiza cada turno desde la observación visible y desde `obs.logs` (`_update_cartas_tracking`, `_move_card_state`), y cuando el simulador revela el mazo completo (p.ej. al jugar Ultra Ball) permite **fijar** qué copias están premiadas. Es lo que permite razonar sobre cartas ocultas (p.ej. "¿queda una `Lillie's Determination` en el mazo?" → `CARTAS_ACTIVAS_EN_MAZO[Lillie_Determination][ESTADO_MAZO] > 0`) y alimenta las heurísticas de probabilidad (`_prob_draw_any`, `_prob_card_accessible`, `_op_disruption_belief`).

### Estado global entre turnos
Variables `global` que persisten entre llamadas: `plan` (`AttackPlan` del turno), `we_go_first`, `meganium_in_play`, `forest_in_play`, `ko_last_turn`, `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan`, `_field_at_turn_start`, `_poke_pad_target_id`, `_ub_meowth_pending`, `_ub_fez_pending`, `_ub_engine_pivot_turn`, `_ld_supp_comprometido`, `_dodge_immune_*`. Se reinician al detectar cambio de turno (`pre_turn != state.turn`).

### Detección de matchup (`op_is_*_deck`)
Al inicio de `agent()` se inspeccionan las cartas rivales visibles para clasificar el mazo enemigo (`op_is_crustle_deck`, `op_is_fire_deck`, `op_is_alakazam_deck`, `op_is_comfey_deck`, `op_is_lucario_deck`, `op_is_gardevoir_deck`, `op_is_control_deck`, `op_is_aggro_deck`, …). Muchas reglas de puntuación se activan **solo** contra ciertos arquetipos.

**Inferencia por el descarte rival**: además del tablero, se recorre `op_state.discard` — un Pokémon del arquetipo en el descarte identifica el mazo **2-3 turnos antes** que la detección por tablero y activa los flags estratégicos (Alakazam, Comfey, Lucario, Hop, Cubchoo, Gardevoir, Zoroark, Slowking/control, aggro) a tiempo para preparar la respuesta (reserva de banca/Xerosic vs Alakazam, plan solo-Ogerpon vs Comfey…). Los flags de "muro en juego" (Crustle/Sylveon/Cornerstone) y los `op_has_*` posicionales **NO** se infieren del descarte: dependen del tablero actual.

### `AttackPlan` (el "pizarrón" del turno)
`plan` es un objeto `AttackPlan` global que memoriza la mejor combinación `(atacante, objetivo, ataque)` calculada en el análisis de amenaza (`plan.attacker`, `plan.target`, `plan.attack_index`, `plan.remain_hp`, `plan.energy`). Las fases posteriores del bucle (adjunte de energía, retirada, ataque, Boss's Orders) **leen** el plan en vez de recalcular la decisión, lo que evita contradicciones entre "qué energía cargo" y "quién ataca realmente".

### Pivotes defensivos
Banderas de un solo turno que reescriben el plan cuando el activo está condenado o el intercambio de premios es malo; se calculan antes del bucle y las leen RETREAT/SWITCH/ABILITY:
- `_hydra_wall_pivot`: el activo puede atacar pero NO noquea y muere el próximo turno → retirar y promover un Hydrapple ex sano (330 HP) que sobreviva el golpe rival (el daño rival real lo resuelve `_op_active_attack_damage_to`).
- `_fragile_ex_sac_pivot` y `_ripen_retreat_ko_pivot`: ex activo (2 premios) condenado + atacante NO-ex (1 premio) que noquea igual → *Ripening Charge* habilita la retirada, se sacrifica solo 1 premio.
- `_alakazam_pivot_1prize`: vs Alakazam, retirar el ex activo y promover **cualquier** cuerpo de 1 premio (`prize_count(bp)==1`: Dipplin, Meganium, Tapu Bulu…) que noquee igual.
- **Powerful Hand modelado en defensa**: `POWERFUL_HAND_ATTACK_ID` — si el activo rival es Alakazam ex, `_op_active_attack_damage_to` proyecta `20×(mano rival+2)`, lo que alimenta `active_ko_likely` y despierta estos pivotes en ese matchup.
- La promoción tras KO la resuelve `_best_promote_card` con prudencia de premios general: entre candidatos que noquean, prefiere al que sobrevive el golpe rival proyectado o cede 1 premio.

### Motor Meowth ex (*Last-Ditch Catch*)
`Meowth ex` busca un Supporter del mazo al bajarlo de la mano (`_meowth_ld_free` comprueba que la habilidad esté disponible). Es el eje de varias cadenas:
- **UB→Meowth→Lillie's**: `_ub_meowth_pending` (una Ultra Ball de este turno eligió buscar Meowth) fuerza bajarlo con Supporter libre; `_ub_engine_refresh_pivot` detecta el turno en el que la propia Ultra Ball debe puntuar al tier de energía para armar el motor (y `_ub_engine_pivot_turn` fuerza el fetch de esa UB a Meowth). Los **dos lados** de la cadena comprueban `_meowth_ld_free`: el de la jugada de la Ultra Ball vía `_ub_cavar_meowth_se_juega` (no cavar un Meowth que la rama PLAY va a vetar por tener la *Last-Ditch* del turno ya gastada) y el de bajar el cuerpo en el propio PLAY.
- **La cadena a un turno vista** (`_ub_meowth_para_manana`): la ÚNICA excepción a "la Ultra Ball solo se juega por un Pokémon que vayamos a jugar HOY". Con el bloqueo de Objetos encima (`_bloqueo_de_items_inminente`: Budew en el campo rival o mazo Dragapult, que lo lleva) la Ultra Ball no es un recurso que se guarda, es un recurso que **caduca** — se cava hoy el Meowth ex que se baja mañana, porque el *Itchy Pollen* bloquea Objetos pero no Pokémon, Habilidades ni Supporters. Exige además `_sin_atacante_para_manana` (el tablero tampoco ataca el turno siguiente) y tiene su mitad en el fetch (`bloqueo_de_items_manana`). Registro_002 paso 17 vs Dragapult, PERDIDA.
- **El Supporter buscado se JUEGA** (`_ld_supp_comprometido`): si el *Last-Ditch* de un Meowth ex bajado **este turno** (`appearThisTurn`: el cuerpo de 2 premios ya está pagado) elige un Supporter, ese id se queda con el único hueco del turno (piso de score por encima de la banda normal del resto de `_SUPP_PLAY_IDS`; un Supporter decisivo —un Boss's ganador— sigue pudiendo adelantarlo). Es la otra mitad de `_meowth_fetch_pierde_el_turno` (que PREDICE, antes de bajar el cuerpo, que el fetch se llevará el hueco): sin ella el agente cavaba la `Lillie's Determination` y acto seguido jugaba el `Dawn` que ya tenía en la mano (registro_002 paso 22 vs Alakazam).
- **Motores Boss's vía Meowth**: `win_via_boss_gust` / `gust_2prize_via_boss` (remate ganador o gusteo de 2 premios con Boss's en mano **o en mazo** vía Meowth) y `_deny_evo_via_boss` (negar una pre-evo energizada de línea ex gusteándola).
- **Fetch de Xerosic**: vs Alakazam (o mano rival grande), *Last-Ditch Catch* prioriza `Xerosic's Machinations` (el rival descarta hasta 3 cartas; `_score_xerosic_play` decide cuándo jugarlo, con disparo temprano si el Powerful Hand proyectado ya noquea).
- `Night Stretcher` puede recuperar el Meowth del descarte para relanzar el motor. En un **turno muerto** (`_sin_ataque_hoy`: ningún cuerpo llega a atacar hoy, ni con una energía más) y con la mano seca, esa recuperación pasa a ser la máxima prioridad del fetch (`motor_de_robo_turno_muerto`, 1250) por encima de todo el desarrollo — el desarrollo que no se juega es un turno perdido dos veces (ver `main-11`). `Forest of Vitality` reemplaza `Team Rocket's Watchtower` con prioridad alta cuando el motor está vivo (la Watchtower anula las habilidades ex).

### Cadena Fezandipiti ex (*Flip the Script*)
Robar 3 cartas si nos noquearon un Pokémon en el turno anterior: gratis, **una vez por turno** y con la condición muerta al acabar el turno. Los tres eslabones (registro_006, episodio 88710543 vs Mega Lucario):
- **Cavarlo**: el objetivo `fez_tras_ko` de la Ultra Ball (1050) solo se elige con la habilidad viva y banca libre.
- **Bajarlo**: `_ub_fez_pending` obliga a completar la búsqueda ya pagada; el veto de ORDEN de Req H (`_lucario_riolu_gust`) exime a este cuerpo porque no consume el Supporter del turno. Sin los dos, el `Unfair Stamp` del propio turno barajaba de vuelta al mazo el Fezandipiti recién cavado.
- **Recuperarlo**: `motor_de_robo_turno_muerto` en el fetch de `Night Stretcher` (1200, segundo detrás de Meowth ex, que rehace la mano entera vía Lillie's) — solo con `ko_reciente`: sin KO propio el turno anterior no hay *Flip the Script* y el cuerpo de 2 premios es un regalo.
- **Usar la habilidad**: `FEZ_DRAW_ABILITY_SCORE` (31700) + tier ENERGY la ponen por encima de las cargas no letales (*Teal Dance*, *Ripening Charge*) — se roba **antes** de decidir los adjuntes. Ceden ante ella solo el orden `Unfair Stamp` / Lillie's → habilidad (barajarían las 3 cartas; vetos DIFERIBLES en `_ability_order_veto`), el freno de deck-out (mazo ≤4) y el remate que **gana la partida** este turno.

### Nuestro mazo (arquetipo)
- **Líneas de ataque**: `Chikorita → Bayleef → Meganium` (acelerador *Wild Growth* + atacante no-ex), `Applin → Dipplin → Hydrapple ex` (atacante ex escalable; *Syrup Storm* escala con la energía Planta del campo), `Teal Mask Ogerpon ex` (tanque/atacante con *Teal Dance*; *Myriad Leaf Shower* = 30+30×(energía propia **+ energía del activo rival**)), `Tapu Bulu` (atacante no-ex pesado), `Fezandipiti ex` (*Cruel Arrow* golpea a cualquiera).
- **Utilidad**: `Meowth ex` (*Last-Ditch Catch*).
- **Supporters**: `Lillie's Determination` ×4 (baraja la mano y roba), `Boss's Orders` ×2 (sube un banca rival al activo), `Lana's Aid`, `Dawn`, `Xerosic's Machinations` ×2 (el rival descarta a 3; con copia de respaldo, la primera se juega temprano vs Alakazam).
- **Objetos**: `Ultra Ball` ×4, `Bug Catching Set` ×4, `Night Stretcher` ×2, `Poké Pad` ×1, `Unfair Stamp`.
- **Estadio**: `Forest of Vitality` ×4 (acelera energía Planta). 13 energías Planta.
- `Pinsir` ya **no** está en el mazo: su lógica en `main.py` es código latente.

---

## 3. Mapa temático (documentos detallados)

Los archivos `main-01…15` documentan `main.py` por regiones, en el orden del archivo. Núcleo y ayudantes (antes de `agent()`):

- **[main-01 — Constantes y configuración](main-01-constants-and-config.md)**: carga de `deck.csv`, `card_table`, `RETREAT_COST`, constantes de ID de carta y conjuntos por rol estratégico (`EX_IMMUNE_IDS`, `THREAT_PREEVO_IDS`, `EX_PREEVO_IDS`…), `_validate_id_constants` y las constantes de puntuación `SCORE_*`/`BOSS_*`.
- **[main-02 — Núcleo de cálculo: energía, daño y ataque](main-02-core-calc-helpers.md)**: `AttackPlan` y los ayudantes de energía efectiva (`_grass_mult`, `_can_attack_eff`, `_physical_energy`), daño (`_attacker_base_damage`, `_op_active_attack_damage_to`) y ataque.
- **[main-03 — Seguimiento de estado y creencia](main-03-state-tracking-and-belief.md)**: el sistema `CARTAS_ACTIVAS_EN_MAZO` (mazo/mano/juego/descarte/premios), la identificación de premios y las heurísticas de probabilidad (`_prob_draw_any`, `_prob_card_accessible`, `_op_disruption_belief`).
- **[main-04 — Utilidades de puntuación](main-04-scoring-helpers.md)**: funciones puras de valoración (`get_card`, `prize_count`, `pokemon_score`, `count_total_grass_energy`, `calc_syrup_storm_damage`, `_count_hand_play_options`) con `_eval_ub_best_target` como pieza central.

Interior de `agent()`:

- **[main-05 — Preámbulo y conteos](main-05-agent-setup.md)**: conversión de la observación, reinicio de turno, actualización de la creencia, conteos de campo/mano/descarte y condiciones de estado.
- **[main-06 — Detección de matchup, debilidades e inmunidades](main-06-agent-matchup-detection.md)**: el escáner del tablero rival que fija los flags `op_is_*_deck`/`op_has_*` (incluida la inferencia por descarte) y las amenazas puntuales.
- **[main-07 — Análisis de amenaza y plan de ataque](main-07-agent-threat-and-plan.md)**: pre-escaneo de opciones, cálculo del `AttackPlan` (KO, lookahead, trades) y los overrides de pivote que lo reescriben.
- **[main-08 — Escalera de Boss's Orders](main-08-agent-boss-orders.md)**: cómo `evaluate_supporters()` calcula `values[Boss_Orders]` — gusteos ganadores, deny-evo, muros y modo estorbo.
- **[main-09 — Supporters y banderas de decisión](main-09-agent-supporters-and-flags.md)**: umbrales de Lillie's/Dawn/Lana's y la batería de banderas pre-computadas (`_win_via_boss_gust`, `_meowth_devel_lillie`, `_deny_evo_via_boss`, …) que vetan o fuerzan jugadas después.
- **[main-10 — Puntuación de energía y contextos de cambio](main-10-agent-energy-and-switch.md)**: la función anidada `energy_score()` (compartida por el adjunte manual y *Ripening Charge*) y los contextos `ACTIVATE`/`SWITCH`/`TO_ACTIVE`/moneda.
- **[main-11 — Búsqueda y selección de cartas](main-11-agent-card-search-scoring.md)**: las ramas `CARD`/`NUMBER`/`YES`/`NO` del gran bucle — setup inicial, objetivo de Boss's, todas las búsquedas `TO_HAND` (Ultra Ball, Bug Catching Set, Poke Pad, Night Stretcher, Meowth, Dawn), `DISCARD`, `DAMAGE` y `ATTACH_FROM`.
- **[main-12 — PLAY (jugar cartas de la mano)](main-12-agent-play-scoring.md)**: puntuación de bajar Pokémon y de jugar Trainers/Estadio; aquí se invocan los scorers extraídos `_score_*_play(ctx)`.
- **[main-13 — ATTACH / EVOLVE / ABILITY](main-13-agent-attach-evolve-ability.md)**: adjunte manual, evoluciones y habilidades (*Teal Dance*, *Ripening Charge*, *Flip the Script*, *Last-Ditch Catch*).
- **[main-14 — RETREAT](main-14-agent-retreat-scoring.md)**: cuándo retirar al activo — pivotes, sacrificios, vetos y posponer el retiro hasta jugar el Supporter.
- **[main-15 — ATTACK / END y finalización](main-15-agent-attack-end-finalize.md)**: los vetos del ataque, `END`, y la finalización (overrides de Poke Pad/Ultra Ball, tiers de orden de jugada `_play_order_tier`, ordenación y `return`).

Transversal (toca varias regiones a la vez):

- **[main-16 — Grand Tree: motor de evolución instantánea](main-16-grand-tree.md)**: el estadio compartido `Grand_Tree` (id 1249) — cadenas evolutivas derivadas del mazo (`_CADENAS_MAZO`), elección del cuerpo a construir (`_gt_planes`), la habilidad en la rama `ABILITY`, el tier `_TIER_STADIUM_ABILITY`, la retención del Forest of Vitality y el *fetch* de la raíz.

> Nota: si algún documento numerado cita rangos de línea, corresponden a la versión del código en que se escribió; para localizar el código usa siempre los **nombres de funciones y banderas**.

Integración con el simulador (`cg/`): ver [cg.api](cg-api.md), [cg.game](cg-game.md), [cg.sim](cg-sim.md), [cg.utils](cg-utils.md). Herramientas: ver [Reproducción de logs](utils-log-replay.md), [Empaquetado de submission](utils-empaquetar-proyecto.md) y [Render de la imagen del mazo](deck-render-deck-image.md).

---

## 4. Cómo depurar una decisión

1. Reproducir el paso con la observación real: cargar el `log/<id>.json`, tomar el item con `observation.select`, `status == "ACTIVE"` y `current.yourIndex == <nuestro índice>`, y llamar `main.agent(obs)` (con `PYTHONPATH=$PWD`). La acción es una lista de índices sobre `select.option`. **Importante**: al reproducir hay que llamar a `agent()` solo con los frames `status == "ACTIVE"` del `yourIndex` propio — pasar frames del rival o inertes contamina el estado global del agente.
2. `utils/split_turns.py` divide un log en registros por turno; `utils/log_replay.py` reproduce un log completo y compara con la acción registrada (ver [utils-log-replay.md](utils-log-replay.md)).
3. Las regresiones de decisiones concretas viven en `tests/` con **fixtures** reales en `tests/fixtures/` (p.ej. `marnie_grimmsnarl_step51.json`).
4. `_debug_log_decision()` imprime el ranking de opciones cuando `PTCG_DEBUG` está activo.

> Muchas reglas de puntuación citan en comentarios el **id de partida** (`log 86xxxxxx`) que las motivó: son correcciones dirigidas por casos reales. Al modificar una rama, buscar ese id ayuda a entender la intención original.
