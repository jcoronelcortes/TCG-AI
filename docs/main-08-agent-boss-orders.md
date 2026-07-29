# main.py — Escalera de puntuación de Boss's Orders

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

`Boss's Orders` obliga al rival a subir un Pokémon de su banca al puesto activo. Es la única herramienta del mazo para forzar un intercambio favorable de premios (noquear un objetivo concreto de banca, negar una evolución amenazante, o quitarse de encima un muro inmune). Su valoración tiene **dos capas**:

1. Dentro de `evaluate_supporters()` (función interna de `agent()`) se calcula `values[Boss_Orders]`: cuánto conviene jugar la carta este turno, mediante una escalera de arquetipos seguida de un bloque táctico fino que escribe además banderas auxiliares (`_boss_win_via_bench`, `_boss_deny_evo`, `_boss_deny_alakazam_line`, `_boss_gust_key_bench`, `_boss_dodge_redirect`, `_boss_defensive_gust`, `_boss_dipplin_combo`, `_active_attack_sufficient`) en el mismo diccionario `values`.
2. En el bucle de scoring de PLAY, la rama de Boss's Orders está extraída a la función de módulo **`_score_boss_orders_play(ctx)`** (refactor Prioridad 1, con `DecisionContext`), que convierte esos valores y las banderas standalone (`_win_via_boss_gust`, `_gust_2prize_via_boss`, `_boss_prize_rank`, calculadas después de `evaluate_supporters`, ver `main-09`) en el puntaje final usando las constantes con nombre `BOSS_SCORE_*`.

La elección del objetivo concreto del gusteo (a quién se sube) no ocurre aquí: la resuelve `_boss_tier` y el manejador de selección `TO_ACTIVE`.

## `evaluate_supporters()`: preparación y escalera de arquetipos

### Banderas previas

- `_fez_active_can_attack`: nuestro activo es `Fezandipiti_ex` con ≥3 efectivas (contando el posible adjunte). Si ya está listo, gran parte de la escalera se apaga.
- `_op_active_is_crustle`, `_tapu_can_attack` (Tapu Bulu + Meganium en juego y un Tapu con ≥2 energías físicas → llega a las 4 efectivas de su ataque de 220).
- `crustle_gust_worth_it`: con nuestro ex activo bloqueado por la inmunidad de Crustle, busca en la banca rival un objetivo al que **sí** hagamos daño (`_attacker_base_damage` + `_our_effective_damage`) y que podamos noquear o que no pueda retirarse (energía < `RETREAT_COST`). Basta uno para marcarla.

### Ramas de arquetipo (valor base)

Cadena `if/elif` que fija un valor base por matchup en una escala interna ~0–1000 que después `_score_boss_orders_play` traduce:

- **Crustle, bypass de inmunidad** (`crustle_gust_worth_it`) → `BOSS_PRIORITY_CRUSTLE_GUST` (990), la prioridad más alta de la escalera: con nuestro ex bloqueado al frente, sin Boss's no hacemos nada útil ese turno.
- **Fezandipiti ya listo** → 0 (se prioriza el ataque normal; el bloque táctico está guardado por `not _fez_active_can_attack`, así que esta rama apaga casi todo salvo la rama de "activo sin poder atacar").
- **Tapu Bulu vs banca de Crustle** → 950: mazo Crustle, Tapu puede atacar, el activo rival no es Crustle pero hay uno en banca — subirlo y noquearlo antes de que llegue a muro activo.
- **Mazo Drednaw**: sin atacante que "salte" el escudo (`_has_shell_bypass_attacker`: Meganium cargado o Dipplin) y con objetivos de banca → 980; con bypass, 500 si el bypass es Meganium (ya puede atacar al Drednaw directamente) u 850 si es solo Dipplin.
- **Sylveon / línea Eevee**: Eevee en banca aún evolucionable → 850; Sylveon inmune en **banca** (no activo) con un atacante no-ex propio listo que pueda noquearlo (`_has_nonex_attacker_sylveon`) → 900.
- **Líneas evolutivas amenazantes por arquetipo** (valores 690–850): Froslass en banca (850), Budew fuera de posición (800), Snorunt (780), Munkidori (750), Dwebble en banca (740), Eevee genérico (750), Dreepy/Drakloak (700, solo si la banca tiene una etapa **más avanzada** que el activo, mapa `_DRAGAPULT_STAGE`), línea Ethan/Typhlosion (700, `_ETHAN_STAGE`), Gardevoir (730), Alakazam (700, `_ALAKAZAM_STAGE`), Slowking (710), Dragapult/Dusknoir (700), Zoroark (690). Cada rama exige que el activo rival no sea ya la amenaza (si lo es, no hace falta gustear).
- **Respaldo genérico**: `plan.target >= 1` (el `AttackPlan` ya identificó objetivo de banca) → 650; rival a ≤2 premios → 500; si no, 0.

## Bloque táctico fino

Solo se ejecuta con `Boss_Orders` **en mano**, `not _fez_active_can_attack` y activo rival presente. Este gate in-hand es deliberado y **no se relajó** al construir el motor Meowth: la maquinaria de este bloque (con fallbacks de retirada+ataque de banca) es cara y está pensada para decidir el PLAY inmediato; el caso "Boss's en el MAZO" lo cubre el bloque standalone mano-O-mazo (`_win_via_boss_gust`/`_gust_2prize_via_boss`/`_deny_evo_via_boss`, ver `main-09`), que replica las condiciones de forma **conservadora** (solo daño del activo, sin fallback de banca) para alimentar el fetch de Last-Ditch Catch.

### `_boss_dmg_to(_tgt, _wave_bench_override=None)`

Función interna: daño estimado de **nuestro activo actual** contra un objetivo si se le sube al activo, considerando el posible adjunte del turno. Umbrales y fórmulas por atacante (Hydrapple `30+30×total_grass` con ≥2 efectivas; Ogerpon con ≥3; Tapu 220 con ≥4; Fezandipiti 100 con ≥3; Meganium 140 con ≥4; Dipplin `20×banca` con override opcional; Pinsir 100 con ≥2). Aplica inmunidad ex y de Habilidad, la **Zona de Neutralización** (nuestro ex contra un objetivo sin Rule Box → 0: gustearlo sería inútil), debilidad/resistencia Planta (salvo Fezandipiti) y el tope de Drednaw (≥200 → 0).

### Sub-bloques (cada uno sube el valor con `max()` y deja su bandera)

- **Objetivo activo y mejor banca**: `_bo_active_dmg` (0 si `op_active_dodge_immune`), `_bo_can_ko_active`, `_bo_best_bench_dmg`/`_bo_best_bench_prize`. **Guarda Dwebble** (log 86339758): vs Crustle, los `Dwebble_*` de banca se saltan — el manejador de selección ya los veta como objetivo de gusteo, así que tampoco deben *motivar* jugar la carta (sin la guarda, el agente jugaba Boss's persiguiendo un KO a Dwebble que nunca se ejecutaba y acababa subiendo un rival menos trabado).
- **`_bo_dipplin_combo`** (→ 960): con Dipplin activo con energía, banca libre y un básico propio en mano (`_OUR_BASICS_COMBO`), comprueba si bajar el básico primero hace que `20×banca` alcance para noquear un objetivo de `HIGH_PRIORITY_BENCH_TARGETS`/`THREAT_PREEVO_IDS` que con la banca actual no caía → bandera `_boss_dipplin_combo`.
- **`_bo_win_via_bench`** (→ 990): noquear el mejor objetivo de banca cubre los premios que nos faltan (`_bo_best_bench_prize >= my_prize`) y el KO del activo no logra lo mismo → bandera `_boss_win_via_bench`.
- **`_bo_deny_evo_target` (negar línea evolutiva)**: para cada banca rival se comprueban: `_bo_pe_is_threat` (en `THREAT_PREEVO_IDS`: `Riolu`, `Duraludon`, `Hops_Phantump`, `Dwebble_*`, `Buneary`, **`Rockets_Tarountula`** — pre-evo barata del motor de la línea Rocket's Mewtwo, añadida en la auditoría); `_bo_pe_is_ex_preevo_energized` (en `EX_PREEVO_IDS` — que ahora incluye **la línea Cynthia: `Cynthias_Gible` y `Cynthias_Gabite`** — con ≥1 energía y premios iguales a los del activo; la guarda `NONEX_FINAL_PREEVO_IDS` excluye Abra/Kadabra porque su forma final `Alakazam_ex` vale 1 premio); `_bo_pe_is_ex_line_vs_wall` (activo rival = muro inofensivo sin energía y pre-evo ex en banca aunque esté sin cargar); y `_bo_pe_is_energized_preevo_vs_bare_wall` (log 86402439, línea Marnie: ambas etapas en `EX_PREEVO_IDS`, activo Impidimp desnudo → gustear el Morgrem energizado corta la línea de Grimmsnarl ex por el mismo premio). Si el daño directo no basta, hay fallback con `_bench_attacker_can_ko` tras retirar (`_bo_de_can_retreat`, contempla la carta de intercambio). El descarte por "el activo ya rinde igual o más premios" se refina con `_bo_active_prize_dominates`: para pre-evos AMENAZA solo domina si el activo rinde **estrictamente** más premios (registro_007 vs Archaludon: con premios iguales, gustear la pre-evo gana porque además remueve al atacante) **o** si el activo rival es él mismo una `THREAT_PREEVO_IDS` igual o más desarrollada (`energía >=` la de banca; registro_006: atacar al Duraludon grande con Hero's Cape en vez de gustear la copia débil de banca). La adición de la línea Cynthia corrige que el deny-evo jamás disparara vs Cynthia: el agente atacaba al muro Spiritomb en vez de gustear el Gabite energizado; la regla general es **privilegiar siempre cortar la línea evolutiva del atacante ex rival**. Bandera `_boss_deny_evo`.
- **`_bo_deny_alakazam_line`** (→ 965; registro 010, GANADA): cuando el activo rival está **fuera** de la línea Alakazam (p.ej. un Dunsparce-muro) y en banca hay una pieza Abra/Kadabra/Alakazam noqueable (directa o tras retirar), se gustea para cortar el desarrollo del atacante Psíquico (prioridad de objetivo Kadabra > Abra > Alakazam, elegida por el manejador de selección). No contradice la regla "no gustear pre-evo de línea no-ex": esa aplica cuando el activo rival ya es de la línea (atacarlo ya la golpea); como Abra/Kadabra están en `NONEX_FINAL_PREEVO_IDS`, el deny-evo genérico los ignora y esta regla los cubre solo en el caso "activo fuera de línea". Bandera `_boss_deny_alakazam_line`.
- **`_bo_gust_key_bench`** (→ 975): el activo rival no es un `KEY_BENCH_ATTACKER_IDS` (línea Hop: Trevenant/Phantump) pero sí lo hay en banca y es noqueable → cazar al atacante clave aunque el activo valga los mismos premios; la preferencia fina (evolución con energía > sin energía > pre-evo) la resuelve `_boss_tier`. Bandera `_boss_gust_key_bench`.
- **Redirección por esquiva** (→ 985 con KO en banca, 970 con solo daño): con `op_active_dodge_immune` (Splashing Dodge con cara), atacar al activo no sirve este turno; se redirige el golpe a banca. Bandera `_boss_dodge_redirect`.
- **Boost por diferencia de premios**: si el mejor objetivo de banca vale estrictamente más premios que el activo y no estamos "cambiando a la baja" (`_bo_trade_down`: dañar parcialmente un activo que vale más), el valor sube a `960 + 10 × diferencia`.
- **Snipe de espejo sin energía** (→ 955): si el activo rival noqueable está sin energía y hay una copia idéntica energizada en banca, mejor noquear la copia cargada.
- **Gusteo defensivo vs KO letal inminente** (→ 940): si nuestro activo (Básico/Fase 1) morirá el próximo turno (`estimated_op_damage >= hp`) y no hay razón ofensiva mejor, buscar en banca rival un Pokémon que no pueda retirarse ni noquearnos (aun adjuntando una energía, con la debilidad de nuestro activo aplicada), y subirlo para robarle al rival su turno de ataque letal. Bandera `_boss_defensive_gust` (variante in-hand; hay otra standalone vs Crustle en `main-09`).
- **Downgrades a 0** ("atacar ya es suficiente"): si el KO directo del activo ya cierra/iguala lo necesario, o el mejor objetivo de banca no vale más que el activo energizado, o el daño al activo lo deja a ≤100 HP — el valor se pisa a 0 y se marca `_active_attack_sufficient`.

### Rama "nuestro activo NO puede atacar este turno"

Guardada por `_active_cant_attack_this_turn` (ver `main-07`) y Boss's en mano. Recolecta el daño potencial de todos los atacantes propios (incluidos Bayleef y Chikorita, con daños menores) asumiendo un adjunte, y busca KOs de alto valor en banca rival aplicando debilidad/resistencia, inmunidades y el tope de Drednaw: objetivo ex o Stage-2 noqueable → `_boss_ko_ex_value` (985); si no, objetivo con ≥1 energía → `_boss_ko_energy_value` (970). Sin KO valioso: si el propio activo rival está "atascado" (coste de retirada − energía ≥2), se deja trabado (valor 0 — mantenerlo ahí es gratis); si no, se busca un objetivo de **stall** en banca contra un umbral dinámico (1 si el activo rival no tiene coste de retirada, 2 en caso contrario; diferencia ≥2 → 975, si no → 900), con la guarda de `op_has_latias_ex`: solo cuentan Básicos, porque *Skyliner* retira gratis a las evoluciones. **Guarda Crustle** (log 86507974): solo se justifica el gusteo defensivo si el activo rival amenaza de forma inminente (puede atacar ya o le falta exactamente 1 energía para su ataque con daño); con ≥2 energías de distancia no hay ataque que neutralizar y el valor se fuerza a 0.

### Activo rival con inmunidad de Habilidad (Cornerstone)

Bloque separado: si `op_has_ability_immune_active` y el atacante del plan (`plan.attacker`) ya está listo con o sin adjunte, gustear libera el bloqueo de Habilidad forzando el cambio de activo (→ 980); si el plan no tiene atacante listo, basta cualquier Pokémon propio no dependiente de Habilidad (`not in OUR_ABILITY_IDS`) que alcance su requisito de `_ATK_REQS_BOSS` con o sin adjunte (→ 960, `_has_non_ability_attacker_ready`).

## `_score_boss_orders_play(ctx)`: del valor a la puntuación de PLAY

Función de módulo con `DecisionContext`. Orden de resolución:

1. **Vetos** (`SCORE_VETO`): `supporterPlayed`; Unfair Stamp pendiente tras KO (el Stamp va primero); y la regla Dunsparce — vs Alakazam con Dunsparce activo rival y nuestro activo sin poder atacar, no despejar el muro.
2. **`ctx.win_via_boss_gust` → `BOSS_SCORE_WIN_NOW`**: gusteo GANADOR (el activo noquea un objetivo de banca y con ello toma los premios que faltan). Debe superar cualquier retirada/pivote defensivo — antes se puntuaba como win_via_bench y el agente **retiraba en vez de rematar** (registro 019 vs Dragapult).
3. **`ctx.gust_2prize_via_boss` → `BOSS_SCORE_GUST_2PRIZE`**: el activo ya noquea al activo rival (1 premio) pero un ex de banca noqueable vale 2 (registro_008 vs Rocket's Mewtwo ex): cobrar 2 premios y eliminar al atacante difícil. Por encima de retiradas/pivotes, por debajo del remate ganador.
4. **Cesiones a Lillie's → `BOSS_SCORE_EMPTY_GUST`**: `_boss_first_turn_cede` (en nuestro primer turno con Lillie's en mano, Lillie's siempre va primero); `_boss_empty_gust` (activo sin poder atacar y sin razón valiosa: el gusteo no es ejecutable como remate); y `_boss_cede_dig` (con Lillie's en mano y **sin atacante real de banca listo** — `ctx.has_ready_bench_attacker`, que nunca cuenta un Applin —, un gusteo de desarrollo no encadena y conviene cavar; se exceptúan todos los gusteos valiosos, incluidos `boss_ko_threat_preevo` y `boss_deny_alakazam_line`).
5. **Escalera de valor**: muro inmune activo con valor alto → `BOSS_SCORE_WALL_GUST`; `boss_dodge_redirect` → `BOSS_SCORE_DODGE_REDIRECT`; `boss_win_via_bench` → `BOSS_SCORE_WIN_VIA_BENCH`; `boss_deny_alakazam_line` → `BOSS_SCORE_PRIZE_RANK_BASE`; `_boss_unlock_gust` → `BOSS_SCORE_UNLOCK_GUST` (ver abajo); `boss_low_value_gust` → `BOSS_SCORE_LOW_VALUE_GUST`; `boss_prize_rank >= 1` → `BOSS_SCORE_PRIZE_RANK_BASE + (8 − rank) × 20`; `boss_defensive_gust` → `BOSS_SCORE_DEFENSIVE_GUST`.
6. **Fallback**: sin valor positivo → veto; si no, `SCORE_SUPPORTER_VALUE_BASE + int(valor × 1.4)` (la conversión genérica valor-de-supporter → score de PLAY). Todas las ramas positivas suman `ctx.supporter_boost` (el empujón cuando la mano está "vacía" de alternativas).

**Gusteo des-lockeador (`gusteo_deslockea_habilidades`, autopsia iron_thorns p018 t10)**: con Iron Thorns ex de ACTIVO rival, *Initialization* anula Teal Dance / Ripening / Last-Ditch / Flip the Script — todo el motor propio. El lock es **posicional**: gustear con Boss's cualquier cuerpo **no-locker** de su banca lo apaga en el acto (a diferencia de la Watchtower, que es estadio). Guards de `_boss_unlock_gust`: Iron Thorns ex en el activo rival, un no-locker en su banca, y que el des-lockeo sirva HOY (Ogerpon ex / Hydrapple ex en juego, o Meowth ex en mano — encadena Boss's → Meowth → Last-Ditch). En la **selección de objetivo**, el modo estorbo tiene el `SCORE_FORBID` espejo `estorbo_crea_lock_iron_thorns`: nunca subir un Iron Thorns ex como estorbo (crearía/mantendría el lock); el modo ofensivo no se toca (gustearlo para noquearlo cobra 2 premios).

Jerarquía numérica de las constantes: `BOSS_SCORE_WIN_NOW` (20000, techo: gana la partida) ≫ `BOSS_SCORE_GUST_2PRIZE` (6800, supera retiradas/pivotes ~6500-6600) > `XEROSIC_SCORE_ALAKAZAM` > Lillie's hydra-cargado > `BOSS_SCORE_WIN_VIA_BENCH` (5600) ≈ `BOSS_SCORE_WALL_GUST` (5500) ≈ `BOSS_SCORE_DODGE_REDIRECT` (5500) > `BOSS_SCORE_PRIZE_RANK_BASE` (5200, afinado por rank) > `BOSS_SCORE_UNLOCK_GUST` (2600, des-lockear habilidades) > `BOSS_SCORE_LOW_VALUE_GUST` (1500) ≈ `BOSS_SCORE_DEFENSIVE_GUST` (1500) ≫ `BOSS_SCORE_EMPTY_GUST` (20, cede a Lillie's).

## Interacciones

- Las banderas escritas en `values` se releen como `_supp_values.get(...)` tras `evaluate_supporters()` y alimentan tanto `_score_boss_orders_play` (vía `DecisionContext`) como los vetos/forzados de otras jugadas (`_lucario_riolu_gust`, cesiones de Lillie's, fetch de Meowth).
- `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_deny_evo_via_boss` y `_boss_prize_rank`/`_boss_ko_threat_preevo` son cálculos **independientes y posteriores** (documento `main-09`): reevalúan con el `AttackPlan` cerrado y con Boss's en mano **o en el mazo**, y son los que habilitan el motor Meowth ex → Last-Ditch Catch → Boss's.
- `DUNSPARCE_IDS` y `_boss_tier` actúan en la selección de objetivo (`TO_ACTIVE`), no aquí.
- El bloque depende de las banderas de matchup de `main-06` y de `plan.target`/`estimated_op_damage`/`_active_cant_attack_this_turn` de `main-07`.

## Reglas derivadas de partidas

- **log 86339758** — Dwebble vetado como motivador y como objetivo del gusteo vs Crustle (aplicado en el mejor-objetivo de banca, en deny-evo y en las variantes standalone).
- **log 86402439** — línea Marnie: gustear el Morgrem energizado en vez de noquear al Impidimp desnudo (`_bo_pe_is_energized_preevo_vs_bare_wall`).
- **registro_006 vs Garchomp (GANADA con error)** — la línea Cynthia no estaba en `EX_PREEVO_IDS` y el deny-evo no disparaba; ahora se gustea el Gabite energizado en vez de atacar al muro.
- **registro_006 vs Archaludon** — `_bo_active_prize_dominates`: si el activo rival es la misma amenaza (Duraludon con más energía/tools), atacarlo domina sobre gustear la copia débil de banca.
- **log 86507974** — vs Crustle, gusteo defensivo solo ante amenaza inminente.
- **registro 019 vs Dragapult** — el gusteo ganador debe superar la retirada (`BOSS_SCORE_WIN_NOW`).
- **registro_008 vs Rocket's Mewtwo ex** — el gusteo de 2 premios supera el KO del activo de 1 (`BOSS_SCORE_GUST_2PRIZE`).
- **registro 010 vs Alakazam** — `_boss_deny_alakazam_line`: cortar la línea cuando el activo rival está fuera de ella.
