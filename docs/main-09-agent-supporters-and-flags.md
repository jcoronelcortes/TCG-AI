# main.py — Valoración de Supporters y banderas de decisión

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este tramo cierra la función interna `evaluate_supporters()` (cuya escalera de `Boss's Orders` documenta `main-08`) fijando los valores de **`Dawn`**, **`Lillie's Determination`** y **`Lana's Aid`** en el diccionario `values`, que se materializa como `_supp_values = evaluate_supporters()`. A partir de ahí, el código deriva una batería de **banderas booleanas de pre-cómputo** (`_boss_prize_rank`, `_boss_ko_threat_preevo`, `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_deny_evo_via_boss`, `_meowth_devel_lillie`, `_meowth_ld_free`, `_ctm_*`, `_active_already_kos`, …) que no puntúan nada por sí mismas: se consultan en los bloques de PLAY, ATTACH/EVOLVE/ABILITY y RETREAT para vetar, forzar o re-priorizar opciones concretas, y muchas viajan al `DecisionContext` que consumen los scorers de módulo (`_score_boss_orders_play`, `_score_xerosic_play`, `_score_lillie_determination_play`…).

El hilo conductor es evitar los dos errores típicos de una heurística miope: (a) gastar el Supporter equivocado (Boss's en un gusteo sin premio, Lillie's cuando barajaría la carta clave) y (b) bajar un cuerpo de utilidad (`Meowth_ex`, 2 premios) cuando ya hay con qué atacar. Varias reglas citan el log de la partida real que las motivó.

## Cierre de `evaluate_supporters()`

### Escalón base de `Dawn` y `_remaining_plays`

`Dawn` parte de una escalera por desarrollo del tablero: 900 sin Meganium ni Hydrapple ex en juego, 800 si solo falta Meganium, 700 si solo falta Hydrapple, y 200 residual con ambas líneas montadas. `_remaining_plays` cuenta las jugadas de desarrollo aún disponibles (adjunte pendiente, básicos bajables — Chikorita/Applin/Ogerpon — con banca libre, y las cuatro evoluciones jugables sobre piezas en juego): es el proxy de "cuánto queda por hacer con esta mano".

### Escalón base de `Lillie's Determination`

Escalera decreciente por tamaño de mano y jugadas pendientes: partida intacta (`my_prize == 6`) → 750 (800 con mano ≤3); mano ≤2 → 800; mano ≤3 → 700; `_remaining_plays <= 1` → 650; mano ≤5 → 550; mano grande → 400 (refrescar desperdiciaría cartas útiles). **Recorte vs Alakazam**: con `op_is_alakazam_deck` y mano ≥4, tope de 450 (300 si además quedan ≥2 jugadas) — contra Alakazam interesa conservar recursos, no barajarlos.

### Combo `Dawn` + `Lillie's` ambas en mano

Si falta desarrollar alguna de las dos líneas (`not (meganium_in_play and has_hydrapple)`): con `forest_in_play`, `Dawn` sube por encima de `Lillie's` (+50; Forest ya acelera la energía y Dawn trae los Pokémon que faltan); sin estadio, `Lillie's` sube por encima de `Dawn` (+50; primero refrescar). Siempre con `max()` para no bajar valores ya altos por otra regla.

### Valoración de `Lana's Aid`

Recorre el descarte propio contando `discard_basic_energy` (copias de `Basic_Grass_Energy`) y los básicos recuperables. **Corrección Rule Box** (registro 006 vs Alakazam): Lana's Aid solo recupera Pokémon **sin Regla**, así que los ex (Ogerpon, Meowth, Fezandipiti) **no** cuentan como objetivo — contarlos inflaba el valor (p.ej. 700 por un Meowth ex en el descarte) y ese "valor fantasma" bloqueaba la línea Night Stretcher → Meowth ex → Lillie's al elevar `_best_supp_in_hand_val`. Con algo recuperable, base 300 más bonos: +400/+200 por banca casi vacía (≤1/≤2), +350 por Chikorita recuperable con su línea totalmente caída, +300 análogo para Applin, +200 por Ogerpon escaso (<2 en juego), +200 con `forest_in_play` y básicos Planta recuperables, +150 con ≥3 recuperables, y bonos anti-Crustle (+350 Tapu Bulu recuperable sin copia en juego, +200 Applin con la línea vacía).

### `_lana_energy_enables_attack`

Detecta cuando Lana's **habilita un ataque este mismo turno** — la única razón para anteponerla a Lillie's sin atacante listo. Exige energía básica en el descarte y ninguna en mano (con energía en mano se preferiría el adjunte normal). Dos ramas: activo `Hydrapple_ex` (¿las energías recuperables+adjuntables — tope de 2 slots: adjunte manual + el propio Lana's — cruzan el umbral de 2 efectivas?) o un Hydrapple de banca promovible (`can_switch`/`has_switch_card`), tomando el de más energía. Si aplica, `lana_val` sube a 950 (prioridad casi máxima) y se exporta como `values['_lana_enables_attack']` para que la capa de PLAY distinga este caso al comparar Lana's contra Lillie's.

### Reglas de apertura y emergencia

- **Turno 2 en segunda posición** (`state.turn == 2 and not we_go_first`): `values[Lillie_Determination] = 1000` (máximo de la función) y Boss's/Dawn/Lana's recortados a 200 — en el turno de apertura se refresca la mano; los demás Supporters rara vez tienen objetivo útil aún.
- **Mano inicial ≥10 en los dos primeros turnos**: `values[Lillie_Determination] = -1` (veto; barajar una mano así no aporta).
- **`Dawn` de emergencia tras KO propio**: con `ko_last_turn`, `Dawn` en mano y sin Lillie's/Meowth/Ultra Ball, sin Fezandipiti en juego pero con copias en el mazo (`CARTAS_ACTIVAS_EN_MAZO`) y banca libre → `values[Dawn] = 1100` (por encima de todo: reconstruir el tablero con hasta 3 Pokémon) y Boss's/Lana's recortados a 200.
- **Veto de Boss's sin objetivo distinguible**: si ningún Pokémon de banca rival difiere del activo (`_bo_has_distinct_target`: id distinto o mismo id con distinta energía), gustear es un no-op → valor 0.
- **Veto de Boss's vs Crustle sin condiciones**: exige activo rival Crustle/Dwebble (`_cru_act_ok`) y algún no-Dwebble en su banca (`_cru_has_nondwebble_bench`); si falta cualquiera, valor 0 (reservar el Supporter para objetivos relevantes).
- **`Dawn` con banca llena vs Alakazam**: solo se juega si de verdad falta una evolución alcanzable (mapa `_ALK_DAWN_EVO`: pre-evo en juego, evolución no en mano y aún disponible en el mazo, `_alk_dawn_need_evo`); si no, valor 0 — con banca llena Dawn solo adelgaza el mazo y arriesga perder por deckout.

## Xerosic's Machinations y el guard de Lillie's

`Xerosic_Machinations` (incorporada al mazo a costa de un Poké Pad) no se valora en `evaluate_supporters` sino en la capa PLAY vía **`_score_xerosic_play(ctx)`**: el rival descarta hasta quedarse con 3 cartas — el contra natural de *Powerful Hand* (20 × carta en mano rival).

- **Vetos**: `supporterPlayed`; mano rival ya ≤3 (no quemar el Supporter para nada); Unfair Stamp pendiente tras KO (el Stamp va primero, mismo gate `_stamp_blocks_supp_chain`).
- **Disparo TEMPRANO `_xr_lethal_proj`**: con mano rival 4–5 (la rama estándar exige ≥6) pero `Alakazam_ex` **ya activo** y su Powerful Hand proyectado (`20 × (mano + 2)`, la misma proyección de `_op_active_attack_damage_to`) noqueando a nuestro activo, esperar el umbral reglamentario regala el KO: se capa la mano ahora.
- **Rama Alakazam**: con mano rival ≥6 o `_xr_lethal_proj` → `XEROSIC_SCORE_ALAKAZAM` (5900) más `min(300, 50 × (mano rival − 4))`: rango efectivo ~6000–6200 con mano ≥6, 5900 en el disparo temprano — por encima de Lillie's hydra-cargado (5800, que además barajaría el Xerosic), por debajo de `BOSS_SCORE_GUST_2PRIZE` (6800) y de los pivotes defensivos (~6500–6600). Cede a `boss_win_via_bench` con Boss's en mano (cobrar premio va primero; el `supporterPlayed` vetará el Xerosic en la re-evaluación) y a Lillie's si no podemos atacar y nuestra mano es ≤3.
- **Rama genérica**: cualquier mazo con mano rival ≥7 → `XEROSIC_SCORE_GENERIC` (3380; disrupción real, justo bajo el Lillie's típico). Resto → `XEROSIC_SCORE_LAST_RESORT` (20: solo si ningún otro Supporter tiene algo mejor que hacer).
- **Guard de Lillie's** (en `_score_lillie_determination_play`): vs Alakazam con Xerosic en mano, mano rival ≥4 y **sin forma de re-buscarlo** (sin Meowth en mano ni en mazo, o ambos Meowth ya en juego) → veto de Lillie's: barajaría el único acceso al cap de Powerful Hand justo antes de su pico. Con mano rival ≥6 la escalera ya garantiza Xerosic > Lillie's; el guard cubre el hueco 4–5. Si el Xerosic es re-buscable, Lillie's sigue su curso (Meowth lo re-busca).

El motor se completa fuera de este tramo: el fetch de Last-Ditch Catch prioriza Xerosic vs Alakazam (1260 con atacante fuerte en juego / 1200; y una rama genérica nueva para cualquier mazo con mano rival ≥7, atacante fuerte y activo que ataca, por debajo de Lillie's/Boss's), el último slot de banca se reserva para Meowth mientras Xerosic siga en el mazo, y el manejador de DISCARD lo protege del descarte. En la misma familia vive `_ub_engine_refresh_pivot` (scorer de Ultra Ball): con un activo que no noquea ni con el adjunte, banca ≤1, ≥2 energías en mano como forraje del descarte y Meowth+Lillie's en el mazo, la Ultra Ball sube al tier de energía (31450, patrón Teal Dance) para ganar al adjunte manual, y arma `_ub_engine_pivot_turn` para que su fetch elija Meowth ex (1300).

## Banderas de decisión posteriores a `_supp_values`

### `_best_supp_in_hand_val/_id` y `_best_supp_in_mazo_val/_id`

El mejor Supporter jugable ahora (entre `Boss_Orders`, `Dawn`, `Lillie_Determination`, `Lanas_Aid` físicamente en mano) y el mejor aún localizable en el mazo (`CARTAS_ACTIVAS_EN_MAZO`), referencia de los fetch (Ultra Ball, Meowth, Poke Pad).

### `_boss_prize_rank` y `_boss_ko_threat_preevo`

Solo en contexto `MAIN` con Boss's **en mano** y activo rival presente. `_bpr_active_can_ko(_tgt)` calcula si el activo propio (con el adjunte proyectado) noquea a un objetivo vía `_attacker_base_damage` + `_our_effective_damage`. Para cada banca rival (con el veto Dwebble vs Crustle del log 86339758) se asigna un rango de "rareza inversa": megaEx = 1, ex = 3, Stage-2 = 5, Stage-1 = 7; las `THREAT_PREEVO_IDS` (que incluyen `Rockets_Tarountula`, pre-evo del motor barato de la línea Rocket's Mewtwo/Spidops) se tratan como Stage-1 (7); los básicos comunes se saltan. Solo cuentan objetivos noqueables (con fallback `_bench_attacker_can_ko` tras retirar, descontando el Grass del coste, si `can_switch`); los sin energía se penalizan un punto. `_boss_prize_rank` guarda el mínimo (menor rank = objetivo más valioso), que la escalera de PLAY convierte en `BOSS_SCORE_PRIZE_RANK_BASE + (8 − rank) × 20`.

`_boss_ko_threat_preevo` se enciende si algún objetivo noqueable está en `THREAT_PREEVO_IDS` y, a diferencia del rank, **no se anula** cuando "atacar ya es suficiente": sirve para **guardar** el Boss's (vetar Lillie's) aunque el activo pudiera atacar (registro_007). El rank sí se resetea a 0 con `_active_attack_sufficient`.

### `_lucario_riolu_gust`

Vs `op_is_lucario_deck` con Supporter libre, Boss's en mano, banca propia establecida (≥2), `_supp_values['_boss_deny_evo']` confirmado y un `Riolu` en banca rival: **veta los desarrollos** (tier DEVELOP: Meowth ex, Chikorita, Tapu…) para que Boss's sobre el Riolu sea la jugada elegida, cortando la línea de Mega Lucario ex antes de que evolucione (log 86023830).

### Reexportaciones

`_boss_win_via_bench`, `_boss_dodge_redirect` y `_boss_deny_alakazam_line` se extraen de `_supp_values` a variables locales para el resto de `agent()` y para el `DecisionContext`.

### Bloque mano-O-mazo: `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_deny_evo_via_boss`

Protegido por: Supporter libre, activos en ambos bandos, banca rival, y `Boss_Orders` disponible **en mano o localizable en el mazo** — esta última condición es la que habilita el motor Meowth ex → Last-Ditch Catch → Boss's (la maquinaria in-hand de `evaluate_supporters` exige la carta en mano y deliberadamente no se relajó; este bloque es su **espejo conservador**: solo daño del ACTIVO, sin fallback de banca tras retirar).

`_mbw_dmg_to(_tgt)` calcula el daño del activo propio con el adjunte proyectado vía la tabla única `_attacker_base_damage`, aplicando inline inmunidad ex/Habilidad, debilidad/resistencia Planta (salvo Fezandipiti) y el tope de Drednaw — sin Zona de Neutralización ni el tope de Crustle a plena vida (comportamiento histórico de este sitio). Con ella:

- `_mbw_act_wins`: si noquear el activo rival ya gana la partida, no hace falta gustear y el bloque termina.
- `_win_via_boss_gust`: hay un objetivo de banca noqueable cuyo premio cubre lo que nos falta para **ganar** (veto Dwebble vs Crustle incluido). Alimenta `BOSS_SCORE_WIN_NOW` y la rama 22500 del motor Meowth ganador.
- `_gust_2prize_via_boss`: el mejor objetivo de banca noqueable vale ≥2 premios, más que el KO del activo, y no es un trade-down → alimenta `BOSS_SCORE_GUST_2PRIZE`.
- `_deny_evo_via_boss` (motor Meowth de VALOR): pre-evolución de línea ex **energizada** en banca rival (en `EX_PREEVO_IDS`, excluyendo `NONEX_FINAL_PREEVO_IDS`) que noqueamos tras gustearla. Excepciones espejo de la maquinaria in-hand: si el activo rival es también una `THREAT_PREEVO_IDS` igual o más energizada, noquearlo ya remueve la misma clase de amenaza (registro_006 vs Archaludon); y solo dispara con premios iguales al KO del activo o con un muro desnudo de ≤1 premio al frente. Regla del usuario (registro_006 vs Garchomp): privilegiar siempre derrotar la línea evolutiva del atacante ex rival. Habilita el PLAY de Meowth (22000) y el fetch de Boss's (1280).

### `_bdg_retreat_ko` y el veto del prize-rank

`_bdg_retreat_ko`: con `can_switch`, ¿algún atacante de banca noquea al activo rival tras retirar (descontando la Grass perdida por `_retreat_cards`, 0 con `has_switch_card`)? Es la comprobación que `can_attack` no cubre. **Veto** (log 85804848, PERDIDA vs Alakazam): si `_bdg_retreat_ko`, hay Lillie's en mano y no aplican `_win_via_boss_gust`/`_gust_2prize_via_boss`, se anula `_boss_prize_rank`: gustear solo para cobrar premio es redundante cuando retirar+promover ya noquea; mejor refrescar.

### `_boss_defensive_gust` (standalone, vs Crustle)

Exclusivo de `op_is_crustle_deck`: sin poder atacar, sin `_bdg_retreat_ko`, sin retirada por confusión ni gusteos valiosos, con Boss's en mano y activo rival energizado, busca en su banca un Pokémon "atascado" (coste de retirada − energía ≥ umbral) para subirlo y ganar tiempo.

### Motor Meowth ex: `_meowth_devel_lillie`, `_meowth_ld_free`, `_active_ready_attacker`, `_ready_attacker_count`

- `_meowth_devel_lillie`: Supporter libre, `Meowth_ex` en mano o en juego, y `Lillie_Determination` disponible (mano o mazo). Se permite si el tablero no está ya "lleno" de cuerpos distintos de Meowth: `_mdl_in_play` contra el tope dinámico `_mdl_max_in_play` (4 con mano de ≤2 cartas, 3 en el resto — con mano mínima hay poco más que jugar y se tolera un tablero más desarrollado). Autoriza que Last-Ditch Catch busque Lillie's y que bajar Meowth compita como desarrollo; con el tablero lleno, Meowth sería un cuerpo redundante de 2 premios y no una herramienta de refresco.
- `_meowth_ld_free`: ¿Last-Ditch Catch está disponible este turno? La Habilidad se dispara al jugar Meowth desde la mano y "no puedes usar más de 1 Habilidad Last-Ditch por turno": si algún Meowth **en juego** tiene `appearThisTurn`, ya se gastó y jugar otro no buscaría Supporter; con Meowth de turnos anteriores (o sin Meowth) la Habilidad está libre. Es guard obligatorio de todas las ramas del motor en PLAY: `_ub_meowth_pending` (21000), Meowth en mano vs Alakazam con Xerosic en el mazo (21500), `_deny_evo_via_boss` (22000) y el motor ganador `_win_via_boss_gust`/`_gust_2prize_via_boss` con Boss's en el mazo (22500, con `field_counts[Meowth_ex] < 2`).
- `_active_ready_attacker` / `_ready_attacker_count`: si el activo ya es un `MAIN_ATTACKERS` listo (`_can_attack_eff` + `can_attack`), y cuántos atacantes listos hay en total (activo + banca) — con 2+ listos, refrescar con Meowth→Lillie's aporta menos y las ramas de PLAY gradúan la prioridad con este conteo. Las excepciones que fuerzan bajar Meowth aunque haya atacante listo (`_ub_meowth_pending` con Supporter libre — el guard es `not supporterPlayed`, no `_active_ready_attacker`; y Meowth ya en mano vs Alakazam con mano rival ≥6 y Xerosic en el mazo) viven en la puntuación de PLAY (`main-12`), igual que la prohibición inversa (`supporterPlayed` → veto de Meowth, salvo rescate anti-softlock).

### Banderas anti-Crustle `_ctm_*` (con override del `plan`)

Solo vs `op_is_crustle_deck` con las tres piezas clave (Dipplin, Tapu Bulu, Meganium) en juego: `_ctm_tapu_ready`/`_ctm_tapu_high` (Tapu cargado = siempre prioritario), `_ctm_dipplin_low` (Crustle activo con ≤2 energías → priorizar Dipplin, cuyo daño escala con la banca), `_ctm_chikorita_bench`/`_ctm_applin_bench` (para el adjunte), `_ctm_charge_active_dipplin`. Dos sub-bloques **sobrescriben directamente `plan.attacker`/`plan.target`/`plan.energy`** para forzar el ataque de Dipplin o la promoción/ataque del Tapu Bulu listo — la única parte del tramo que modifica el `AttackPlan` en vez de fijar banderas.

### Necesidades y reservas de energía

- `_active_needs_energy`: por especie del activo, si necesita más energía para atacar, solo con el adjunte del turno aún libre (`not state.energyAttached`): Hydrapple <2 efectivas, Dipplin <1 física, Ogerpon <3, Tapu Bulu <4, Pinsir <2; `Meowth_ex` con 0 energía (para poder retirarse, no ataca); `Fezandipiti_ex` con lógica propia (si un adjunte lo lleva a 3, sí; si no, solo con 0); la línea Chikorita/Bayleef/Meganium usa como criterio su `RETREAT_COST` (Wild Growth también paga la retirada).
- Reservas: `_reserve_hydra_active_charge` (con exactamente 1 energía en mano que cruza el umbral de 2 del Hydrapple activo, reservarla para él, salvo `op_has_ex_immune_active` — no reservar para un ataque que el muro anularía), `_energy_starved_low_draw` (sequía real: activo necesitado, sin energía en mano ni adjunte hecho, y `_prob_draw_any(Basic_Grass_Energy, draws=2) < 0.5`), `_hydrapple_bench_needs_energy` (algún Hydrapple de banca bajo 2 efectivas), `_energy_demands_before_teal`/`_enough_after_priorities` (¿sobra energía tras las demandas prioritarias para alimentar además *Teal Dance*?), `_reserve_energy_for_hydra_evolve` (con Dipplin activo evolucionable este turno — Hydrapple o Ultra Ball en mano — y 1 sola energía, reservarla para que Hydrapple nazca listo).

### Utilidades de búsqueda y primer turno

- `_bcs_playable_in_hand`: con Bug Catching Set en mano, ¿queda en el mazo (según `CARTAS_ACTIVAS_EN_MAZO`) alguna `Basic_Grass_Energy` o algún Pokémon de tipo Planta que buscar? Determina si vale la pena jugar el objeto o guardarlo.
- `_pp_playable_in_hand`: análogo para Poke Pad — ¿queda alguna copia de las cartas que puede buscar (línea Chikorita, línea Applin sin Rule Box, Tapu Bulu)?
- Regla de primer turno de Meowth: en el primer turno propio **no** se baja Meowth ex primero, porque su fetch de Supporter quedaría barajado de vuelta por la Lillie's que cierra el turno — un fetch desperdiciado más un cuerpo de 2 premios expuesto. Variables: `_our_first_turn` (turno 1 abriendo o turno 2 en segunda posición), `_lillie_available` (Lillie's en mano o mazo), `_meowth_hand_only_card` (Meowth es la única carta de la mano) y la excepción `_meowth_lone_fetch`: primer turno, banca vacía, sin otro Meowth en juego, Meowth única carta en mano y Lillie's aún en el mazo — entonces sí se baja, porque no hay literalmente nada más que jugar.

### Estado de la banca y del daño propio

- `_bench_attacker_ready` / `_bench_attacker_needs_energy`: algún atacante de banca ya listo por umbral de especie (Hydrapple ≥2 efectivas, Ogerpon ≥3, Dipplin ≥1 física, Tapu ≥4, Meganium ≥4) / alguno de los grandes aún por debajo de su umbral. `_bench_attacker_ready` viaja al `DecisionContext` como `has_ready_bench_attacker` — el gate de la cesión `_boss_cede_dig` de `_score_boss_orders_play`: un gusteo de desarrollo (prize_rank) no supera a Lillie's si el único atacante real es el activo y la banca son básicos sin cargar (un Applin nunca cuenta como atacante listo).
- `_active_hydra_cannot_ko`: Hydrapple activo "al tope" (≥2 físicas) cuyo *Syrup Storm* no noquea — no malgastar más adjuntes en él.
- `_extra_energy_enables_ko(pokemon_id, current_energy)`: ¿una energía más convierte el no-KO en KO? Implementada para Hydrapple (escala con `total_grass`) y Ogerpon (Myriad con la fórmula verificada: energía propia + energía del activo rival).
- `_active_already_kos`: el activo ya noquea **sin** adjuntes adicionales (Fezandipiti sin ajuste Planta: su Cruel Arrow no es de tipo Planta).
- `_ogerpon_td_manual_lethal` (log 85803267): letal de Ogerpon que requiere **dos** cargas en el mismo turno (adjunte manual + Teal Dance); el escáner codicioso solo evalúa +1 energía por opción, así que este flag cubre el caso para no despriorizar el adjunte manual.

Más adelante en el mismo pre-cómputo (antes del bucle de scoring) se calculan flags hermanos que consumen estas piezas: `_fragile_ex_sac_pivot` y `_ripen_retreat_ko_pivot` (Ripening Charge habilita la retirada del ex frágil condenado para promover un cuerpo de 1 premio) y `_alakazam_pivot_1prize` (pivote 1-premio vs Alakazam **generalizado por `prize_count == 1`**, ya sin whitelist: incluye Dipplin — `20 × (banca − 1)` al promoverlo — y cualquier no-ex que noquee igual).

## Interacciones

- **`_supp_values` → PLAY**: fuente directa del puntaje de cada Supporter en mano (`_score_boss_orders_play`, `_score_lillie_determination_play`, `_score_lanas_aid_play`, `_score_xerosic_play` vía `DecisionContext`).
- **`_boss_prize_rank` / `_boss_ko_threat_preevo`**: alimentan la rama `BOSS_SCORE_PRIZE_RANK_BASE + (8 − rank) × 20` y las cesiones/vetos de Lillie's.
- **`_win_via_boss_gust` / `_gust_2prize_via_boss` / `_deny_evo_via_boss`**: dirigen el fetch de Last-Ditch Catch hacia Boss's, habilitan las ramas 22500/22000 del PLAY de Meowth (con `_meowth_ld_free` y `field_counts[Meowth_ex] < 2`), y vetan desarrollos que desperdiciarían el turno.
- **`_meowth_devel_lillie`**: condiciona el objetivo del fetch de Meowth (Lillie's) y la puntuación de bajarlo como desarrollo; el gate `forest_in_play` decide si el fetch alternativo puede ser Dawn.
- **`_ctm_*`**: overrides directos de `plan` aquí, y prioridades de ATTACH/RETREAT aguas abajo.
- **Reservas de energía y `_active_already_kos`/`_extra_energy_enables_ko`/`_ogerpon_td_manual_lethal`**: consumidas masivamente por la puntuación de ATTACH (`main-13`) y `energy_score` (`main-10`).

## Reglas derivadas de partidas

- **log 86339758** — Dwebble vetado como objetivo en `_boss_prize_rank` y en las tres variantes mano-O-mazo.
- **log 86023830** — `_lucario_riolu_gust`: Boss's sobre el Riolu por encima de cualquier desarrollo.
- **log 85804848 (PERDIDA vs Alakazam)** — con `_bdg_retreat_ko` y Lillie's en mano, el gusteo "por premio" es redundante: se anula `_boss_prize_rank`.
- **registro_006 vs Garchomp / vs Archaludon** — el deny-evo mano-O-mazo privilegia cortar la línea ex rival, salvo que el activo rival sea la misma amenaza más desarrollada.
- **registro_007 vs Archaludon** — `_boss_ko_threat_preevo` guarda el Boss's (veta Lillie's) aunque el activo pueda atacar.
- **registro 006 paso 51 vs Alakazam** — Lana's Aid no cuenta Pokémon con Rule Box: el valor fantasma bloqueaba la línea Night Stretcher → Meowth → Lillie's.
- **log 85803267** — `_ogerpon_td_manual_lethal`: letal de dos cargas (adjunte + Teal Dance) invisible para el escáner de +1 energía.
