# main.py — Bucle de puntuación: RETREAT (retirada del activo)

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Esta es la rama `elif o.type == OptionType.RETREAT:` del gran bucle `for o in select.option:`. Decide, para cada opción de retirar al Pokémon activo, un `score` que compite con el resto de opciones del turno. RETREAT casi nunca actúa sola: **lee** las banderas y el objeto `plan` calculados antes (preámbulo de amenaza, pivotes `_hydra_pivot_active`/`_hydra_wall_pivot`/`_tapu_sac_pivot`/`_prize_denial_pivot`, `_ex_stuck_promo_ready`, `_lucario_sac_pivot`, `_fragile_ex_sac_pivot`, `_alakazam_pivot_1prize`) y las traduce en una puntuación alta (forzar la retirada) o en un veto `SCORE_VETO` (forzar que el activo se quede a atacar o resistir).

Estratégicamente, RETREAT es el mecanismo de **pivote** del agente: cambia de atacante cuando el activo está estancado (sin energía, bloqueado por una inmunidad, o condenado sin remate), protege cuerpos valiosos (Hydrapple ex, ex de pocos HP) sacrificando cuerpos baratos (Tapu Bulu, básicos de 1 premio), y evita malgastar el coste de retirada en cambios inútiles. Todo el bloque trabaja sobre `_active_reloc` (el Pokémon que se retiraría) y `my_state.bench`; la promoción en sí la resuelve después el contexto `SWITCH`/`TO_ACTIVE` (`_best_promote_card` con su clave de prudencia, `_refresh_promote_prefer_basic`, docs 10/11), así que RETREAT solo decide **si** conviene abrir esa puerta, no **a quién** subir.

## Detalle por bloque

### `_same_species_retreat` — regla anti-desperdicio

Si retirar el activo solo va a volver a subir un Pokémon de la **misma especie**, la retirada no cambia nada salvo gastar la energía del coste — se cancela al final del bloque. Dos condiciones se OR-ean:

- **`_ss_only_same`**: todos los candidatos de banca comparten `id` con `_active_reloc`.
- **`_ss_prefer_same`**: reproduce la lógica de "preferir básico" de la promoción (`_refresh_promote_prefer_basic`): con Lillie's en mano, ningún atacante de banca listo (`_ss_bench_atk_ready`, con el adjunte de este turno) y rival no inmune a ex/habilidad, si el activo ya es un básico no-ex y el básico que subiría la promoción sería de su misma especie (caso Applin, que es la máxima prioridad, o todos los básicos candidatos iguales al activo), retirar tampoco cambia nada.

La cancelación final tiene una **excepción por confusión** (vs Comfey/Brambleghast): retirar para promover un cuerpo de la misma especie SÍ aporta si el activo está confundido (`_conf_should_retreat`) — el nuevo activo no está confundido y ataca sin moneda; con dos Ogerpon ex (el plan del matchup) es el caso normal.

### `_meg_retreat_for_hydra`

Con Meganium activo, `can_switch`, y un Hydrapple ex en banca (rival SIN protección-ex): conviene retirar a Meganium (motor de energía, no atacante prioritario). En banca, *Wild Growth* se sigue aplicando a todo el campo. Excluido si el rival es inmune a ex.

### `_grd_prefer_attack`

Con la función local `_grd_damage(_p)` (réplica de las fórmulas de daño; para Ogerpon usa la Myriad **corregida** `30 + 30 × (energía_propia + energía_del_activo_rival)`) calcula si el activo **ya puede atacar** y si **ningún** Pokémon propio noquea todavía. En ese caso, `_grd_prefer_attack = True` → veto más abajo: no retirar a un atacante funcional sin un KO que justifique el pivote. No aplica vs Crustle/Cornerstone.

### `_active_can_ko_now`

¿El propio activo remata este turno? Repite el cálculo de daño por identidad (`_acn_base`: Dipplin `20×banca`, Hydrapple `30+30×total_grass`, **Ogerpon con la Myriad corregida sumando la energía rival**, Tapu 220, Fezandipiti 100, Meganium 140, Pinsir 100) pasado por `_our_effective_damage`, contra el HP del activo rival. Es el predicado central que evita pivotar cuando ya hay remate garantizado (salvo las excepciones descritas abajo).

**El KO también puede estar en la BANCA rival** (user, registro_004 paso 54 vs Alakazam). *Cruel Arrow* de Fezandipiti ex elige objetivo, así que el bloque de arriba —que solo mira al activo rival— daba `False` con un muro delante y la retirada, que además **descarta la energía del snipe**, ganaba el menú tirando un premio gratis. `_active_snipe_ko_now` (calculado con `_snipe_best_target`, ver `main-02`) fuerza `_active_can_ko_now = True` en ese caso. La variable `_active_kos_op_active` conserva el sentido **estricto** (el KO cae sobre el activo rival) para los pivotes que comparan premios.

### `_hydra_ex_protect_retreat`

Activo = Hydrapple ex, retirable, en riesgo (`active_ko_likely`) y **sin** poder rematar ya: se busca en banca un no-ex listo (Dipplin ≥1, Tapu/Meganium ≥4 ef., Pinsir ≥2 ef.) para exponerlo en su lugar — Hydrapple es el motor de aceleración del mazo y entregar 2 premios sin necesidad es peor que sacrificar un cuerpo secundario.

### `_active_ex_fragile_pivot` y `_hydra_lethal_promote` — pivote letal a Hydrapple ex de banca

- **Caso base** (`not _active_can_ko_now`): si el activo NO remata pero un Hydrapple ex de banca con ≥2 efectivas tiene un Syrup Storm letal (`30 + 30 × total_grass` efectivo ≥ HP rival), se activa `_hydra_lethal_promote` para retirar y promoverlo.
- **Excepción `_active_ex_fragile_pivot`**: aunque el activo YA noquee, si es un **ex frágil** (2 premios, distinto de Hydrapple ex, `maxHp < 330`) y el Hydrapple de banca TAMBIÉN remata, **siempre** se pivota: mismo KO, pero queda el muro de 330 como activo. Excepción de la excepción: si atacar con el activo YA gana la partida (`my_prize <= prize_count(activo_rival)`), se ataca directo.

El flag se **anula** después si el activo es Tapu Bulu que remata sin aplicar la reserva anti-muro (siguiente bloque).

### `_ogerpon_lethal_promote` — pivote de KO vía Teal Dance

El scorer greedy evaluaba a los Ogerpon de banca por su energía **actual**, sin modelar la rampa de *Teal Dance* tras promoverlos. Aquí se simula: activo **estancado** (`_olp_active_stuck`), no-Ogerpon, rival no inmune a ex, y una Planta disponible para Teal Dance — en mano, o recuperable con Night Stretcher desde el descarte **o desde la energía que la propia retirada acaba de descartar del activo**. Para cada Ogerpon de banca: si `energía + _grass_attach_unit() >= 3`, el daño de Myriad (`30 + 30 × (energía_tras_Teal_Dance + energía_rival)`) efectivo iguala o supera el HP rival → `_ogerpon_lethal_promote = True`. Las acciones posteriores (Night Stretcher, Teal Dance a 31500 vía `_td_ko_on_active`, el ataque) las habilita cada scorer; RETREAT solo abre la puerta.

Dos guardas añadidas tras registro_004 paso 54 (vs Alakazam), donde este pivote (8900) ganó el menú con un remate que **no existía**:

- **La Planta tiene que poder aterrizar.** Había una Planta en la mano, pero el adjunte manual ya estaba gastado y los tres Ogerpon habían usado su *Teal Dance* ese turno. `_olp_grass_ok` exige ahora además `_grass_attach_route_open(state, field_counts, abilities_off=meowth_ability_lock)` — adjunte manual libre o alguna habilidad de carga viva (`main-01`).
- **`_olp_active_stuck` ya no es `not _active_can_ko_now` a secas.** Un Fezandipiti ex activo con *Cruel Arrow* letal sobre la banca rival **sí** tiene premio hoy; retirarlo cuesta su energía y expone otro cuerpo. Cuando el único KO del activo es el snipe (`_active_snipe_ko_now and not _active_kos_op_active`), el pivote solo se impone si el KO del Ogerpon vale **más premios** que el del snipe; empatado o por debajo, se ataca.

### Reserva de Tapu Bulu — veto del pivote cuando Tapu ya remata

Un Tapu Bulu activo cargado que ya remata **no** se retira: al ser no-ex, si lo noquean solo entrega 1 premio, así que remata él en vez de ceder el turno a Hydrapple ex (2 premios). Se anula `_hydra_lethal_promote` salvo la **excepción de reserva** (`_tapu_reserve`): en matchups ex-inmunes (Crustle/Cornerstone/Sylveon) donde el activo rival actual **no** pertenece a la línea inmune (Crustle_Grass/Fighting, Dwebble, Sylveon, Cornerstone, `EEVEE_IDS`), sí se retira a Tapu para **reservarlo** contra el muro.

`_op_active_is_cubchoo` y `_cub_bench_attacker_ready` se calculan aquí para el veto anti-Cubchoo.

### Escalera de prioridad principal

Los flags se resuelven en una escalera estricta — cada rama gana sobre las siguientes por orden:

| Score | Condición | Razón |
| --- | --- | --- |
| `9600` | `_suicide_swap_win_promote` | **Relevo del remate suicida**: el ataque del activo noquea pero su auto-daño lo mata y con ese cadáver el rival cobra su último premio (empate o derrota); en banca hay un rematador que gana limpio. Es la única jugada que convierte el 0-0 en victoria, así que precede incluso a los pivotes letales de Hydrapple/Ogerpon — persiguen el MISMO premio con menos urgencia. |
| `9000` | `_hydra_lethal_promote` | Prioridad máxima: pivote letal a Hydrapple ex de banca, cobrar el premio ya. |
| `8900` | `_ogerpon_lethal_promote` | Pivote letal a Ogerpon de banca vía Teal Dance. |
| `SCORE_VETO` | `_op_active_is_cubchoo` sin `_cub_bench_attacker_ready` | Subir un cuerpo que TAMPOCO ataca solo lo expone al mismo bloqueo; se espera al atacante cargado. |
| `8000` | `_lucario_sac_pivot and _lucario_sac_available` (banca ≥1, `can_switch`) | Anti-2-premios vs Mega Lucario en ciernes: retirar el Ogerpon y sacrificar un cuerpo de 1 premio. |
| `4000 + condition_urgency` | `_conf_should_retreat` | Confusión: activo confundido retirable con atacante de matchup listo en banca. |
| `6000` | `_hydra_ex_protect_retreat` | Proteger al Hydrapple ex condenado, exponer un no-ex. |
| `6000` | `_ex_stuck_promo_ready and can_switch` | Ex bloqueado por muro inmune con atacante no-ex LISTO en banca: retirar evita atacar por 0. |
| `6500` | `_hydra_pivot_active` | Pivote defensivo: activo frágil con Hydrapple ex de banca a vida completa que noquea (fijado en `plan.attacker`). |
| `6450` | `_teal_wall_pivot and can_switch` | Ogerpon condenado que YA usó Teal Dance pero sigue sin atacar: subir el muro en vez de regalar el activo. |
| `6450` | `_hydra_wall_pivot` | Pivote-muro **sin KO**: Ogerpon (o Fezandipiti vía `_feza_lucario_wall`) que SÍ ataca pero NO noquea, con muro Hydrapple sano en banca que sobrevive el golpe rival. Existe la rama acotada a Mega Lucario (heurística `active_ko_likely`) y la **generalizada a cualquier rival**, que exige el remate rival REAL vía `_op_active_attack_damage_to` (resuelve el ataque por `attack_table`, proyecta el Powerful Hand de Alakazam con `op_hand_count` y suma Maximum Belt; con daño ilegible da 0 y el pivote no dispara — conservador). |
| `6600` | `_tapu_sac_pivot` | Sacrificio de premios: ex activo en riesgo con Tapu Bulu de banca listo que noquea; mismo KO cediendo 1 premio y no 2. Gana incluso sobre `_active_can_ko_now`. |
| `6550` | `_prize_denial_pivot` | Negación de premios: el KO al ex activo condenado le daría al rival los premios para GANAR; se sube el mejor cuerpo de menos premios (no exige rematar), salvo que el activo pueda ganar YA. |
| `6530` | `_doomed_ex_sac_pivot` | **Descuadre generalizado**: el ex activo puede atacar pero no noquea, el remate rival REAL (`_op_active_attack_damage_to`) lo mata el próximo turno y no hay atacante de banca listo → retirarlo y sacrificar un cuerpo de 1 premio (cede 1 en vez de 2 y conserva el ex con su energía). Se pospone mientras queden desarrollos del turno (`_doomed_pending_play`). **Guarda del snipe** (user, registro_004 t4 vs Marnie): esconder el ex solo niega premios si **allí sobrevive** — con un atacante que además pega a la banca (`OP_BENCH_SNIPE_DAMAGE` del ACTIVO rival ≥ HP del ex), retirarse concede 1 + 2 = **3** premios frente a los 2 de quedarse, así que el pivote se apaga. Se mide con el atacante que está delante, no con el flag de mesa `_op_bench_snipe_dmg` (que cae a un 30 por defecto ante cualquier goteo en juego: apagar el pivote por un sniper que está en su banca costó −3.1 puntos vs crustle/Kangaskhan). |
| `6400` | `_meg_retreat_for_hydra and not _active_can_ko_now` | Meganium activo → Hydrapple ex de banca; cede si Meganium ya remata. |
| `SCORE_VETO` | `_nonex_active_hits_wall` | Un no-ex que SÍ golpea al muro inmune-a-ex nunca se retira. |
| `SCORE_VETO` | `_grd_prefer_attack` | El activo ataca y nadie remata: mejor atacar que pivotar. |
| `SCORE_VETO` | `_active_can_ko_now` | El activo YA remata (las excepciones que sí pivotan ya dispararon arriba). |
| `3500` / `2500` | `plan.attacker >= 1` | El plan apunta a un atacante de banca: `3500` si el activo no podría atacar ni con el adjunte (`_retreat_active_can_attack` falso), `2500` si sí podría (retirada de prioridad media). |
| fallback | — | El resto cae en la rama "sin plan" de abajo, o veto. |

`plan.attacker` es el "pizarrón compartido" del análisis de amenaza; los pivotes `_hydra_pivot_active`, `_hydra_wall_pivot`, `_tapu_sac_pivot` y `_prize_denial_pivot` lo **reescriben** antes de llegar aquí, de modo que la rama `plan.attacker >= 1` los recoge si ninguna rama más específica disparó.

### Rama sin plan — el activo razona desde cero

Cuando ninguna bandera fijó el score, el bloque cae en `elif my_state.active...` y razona sobre `active` con dos sub-familias: la línea Meganium/soporte y los atacantes principales (`MAIN_ATTACKERS`).

#### `_bench_ready_for_retreat` y `_fase58_promo_ready`

Recalculan si hay algún atacante principal ya cargado en banca (umbrales `ATTACK_ENERGY_REQ`) y si hay algún básico/stage-1 no-ex (`_BASIC_OR_STAGE1_NONEX`) como candidato de promoción barato.

#### `_meg_only_attacker_retreat` — Meganium como único remate vs Crustle/Cornerstone

Solo si el rival es Crustle/Cornerstone y el activo no es Meganium: `_meg_blk_ko(_p)` calcula el KO de Dipplin/Tapu/Pinsir/Meganium contra el activo rival; si **ningún** otro atacante remata (`_other_atk_ready_meg`), un **Meganium de banca** sí (`_meganium_bench_ready_meg`) y el activo no remata por su cuenta (`_act_ko_rival_meg`, para Ogerpon calcula la Myriad corregida) → `3500`: retirar para que Meganium remate al muro.

#### Ogerpon vs Crustle/Cornerstone sin remate

Activo Ogerpon: veto sin `can_switch`; veto si él mismo remata (Myriad corregida — debe atacar); si no, busca en banca un atacante que golpee al muro (Pinsir ≥2, Tapu ≥4, y solo vs Crustle también Dipplin ≥1/Meganium ≥4; o Hydrapple/Ogerpon si el rival no es inmune a ex) → `3400` si hay, veto si no.

#### Sin poder atacar con banca lista

`(not can_attack) and can_switch and _bench_ready_for_retreat` → `3200`.

**Guarda "no cambiar un ex por un cuerpo peor"** (user, registro_009 vs Archaludon ex): si el activo está en `OUR_EX_IDS`, el `3200` solo se concede cuando algún atacante **listo** de banca (`ATTACK_ENERGY_REQ` con energía efectiva suficiente) (a) **noquea** al activo rival —medido con `_attacker_base_damage` + `_our_effective_damage` y `grass_scale = total_grass − _retreat_grass_units(coste)`— o (b) tiene **al menos tanta vida** como el que baja (pivote a un muro igual o mayor). Si no, `SCORE_VETO`: cambiar un Hydrapple ex de 330 PV por un Ogerpon ex de 210 "porque el segundo puede atacar" tira el muro y deja delante un cuerpo de 2 premios más fácil de derrotar. Con el activo no-ex la rama queda como antes.

Nótese el prerrequisito `can_switch`: si el activo **no tiene energía para pagar su propio coste de retirada**, esta rama (y todas las demás de este bloque) ni siquiera se evalúan, porque el motor no ofrece la opción `RETREAT`. Quien desbloquea el caso es el adjunte al activo desde `main-13`: `_attach_enable_retreat_ko` cuando el cuerpo de banca remata y `_attach_enable_retreat_attack` cuando solo hace chip — este último replica la guarda de arriba (`min_body_hp`) para no habilitar una retirada que después se vetaría aquí.

#### Cornerstone con activo dependiente de habilidad

Activo en `OUR_ABILITY_IDS` contra Cornerstone Mask Ogerpon ex activo: `3400` con Tapu Bulu ≥4 en banca, si no veto.

#### Crustle con ex activo

Si el propio ex remata (`_cr_ex_can_ko`, Myriad corregida) → veto (ataca). Si no: `3400` con Tapu ≥4 / Dipplin ≥1 / Meganium ≥4 en banca, veto si no.

#### Retirada preventiva por HP

Activo ex que no puede atacar, `estimated_op_damage >= hp` y `_fase58_promo_ready` → `3300`: retiro preventivo antes de morir sin haber hecho nada.

#### Vetos de Fezandipiti ex

`plan.attacker == 0` (él es el atacante planeado) o turno 2 yendo segundos → veto.

#### `NON_ATTACKERS` — Meganium/Meowth ex/línea Chikorita como activo

`NON_ATTACKERS = (Meganium, Meowth_ex, Chikorita, Bayleef, Applin)`; `STRATEGIC_ATTACKERS = MAIN_ATTACKERS` (incluye Meganium como atacante de banca). Ingredientes:

- `_has_bench_attacker` / `_bench_has_only_non_attackers`: por identidad.
- `_HAND_PLAYABLE_ATTACKERS = (Tapu_Bulu, Teal_Mask_Ogerpon_ex)` + `_has_attacker_in_hand` (con Fezandipiti ex jugable desde el turno 2): no retirar cuando lo mejor es primero **bajar** el atacante de la mano.
- `_bench_attacker_ready`: exige energía efectiva suficiente YA, o alcanzable con el adjunte del turno (`_grass_attach_this_turn`) — corrige el bug de retirar para subir a un atacante sin cargar.
- `_fragile_doomed_pivot`: pre-evolución frágil (Chikorita/Bayleef) condenada este turno con algún cuerpo de banca que sobrevive al mejor golpe rival (`_op_best_damage_vs`): conviene retirar aunque ese cuerpo no ataque aún (resguarda la línea).

Escalera para `active.id in (Chikorita, Bayleef, Meganium)`:

| Score | Condición |
| --- | --- |
| `6500` | Vs Crustle, activo Chikorita sin otra copia en juego y banca ≥1: retirarlo aunque no haya atacante listo (rompe el veto general) — Chikorita activo es un lastre que no daña al muro. |
| `6000` | `_has_bench_attacker and _bench_attacker_ready`. |
| `5800` | `_fragile_doomed_pivot`. |
| `SCORE_VETO` | Atacante en banca SIN energía (mejor seguir cargándolo). |
| `SCORE_VETO` | Solo no-atacantes en banca con atacante jugable en mano. |
| `5500` | Fallback: retirar igualmente. |

Para `active.id == Meowth_ex`: `_has_ready_bench_for_meowth` (tabla `_ATK_REQS_RETREAT`) y, si Meowth es **débil** al tipo del activo rival (`_meowth_weak_to_op`), se busca un cuerpo de banca sin esa debilidad y cargado (`_safe_chargeable_body`) → `6000` (protegerlo antes de que lo golpeen con ventaja); si no, `5000` con atacante listo, veto sin él.

Para el resto de `NON_ATTACKERS`: `3000` con atacante en banca; veto con solo no-atacantes y atacante en mano; `2500` fallback.

#### `active.id in STRATEGIC_ATTACKERS` — el activo ya es atacante principal

- **No puede atacar aún** (`not _can_attack_eff`): `2500` con otro atacante principal listo en banca (`_has_ready_bench`), veto si no (seguir cargándolo).
- **Retiro defensivo por condena sin remate**: puede atacar pero no noquea (`plan.remain_hp` no ≤0) y `estimated_op_damage >= hp` — se busca en banca un atacante principal que **sobreviva** el golpe rival (`_op_best_damage_vs`) Y pueda atacar: `5600` si existe (muro que además presiona), veto si no. Sin esta regla el código asumía "si puedo atacar, ataco" y dejaba morir al condenado.
- **Bypass de habilidad enemiga**: vs Drednaw (activo Hydrapple/Tapu, busca Meganium ≥4 o Dipplin ≥1 → `5500`/veto), vs Sylveon (activo ex, busca no-ex listo → `5500`/veto), y bajo Neutralization Zone con activo rival sin Rule Box (busca Tapu/Meganium/Dipplin/Pinsir → `5000`/veto).
- **Fallback**: veto.

### Filtros transversales de cierre

Estas comprobaciones se aplican al final, sobre el score ya asignado:

1. **`_same_species_retreat`**: cancela (`SCORE_VETO`) cualquier score positivo — salvo la excepción de confusión (`_conf_should_retreat`), ver arriba, y salvo `_suicide_swap_win_promote` (si el relevo GANA, la especie no decide nada).
2. **`_alakazam_pivot_1prize` → `max(score, 6000)`**: el pivote 1-premio vs Alakazam (doc 10: retirar el ex activo y promover CUALQUIER cuerpo de `prize_count == 1` que noquee — Dipplin/Meganium/Tapu/Pinsir) debe superar al ataque del ex (~1100) para que el motor retire en vez de atacar; el filtro siguiente ("Supporter antes de retirar") puede igualmente posponerlo a 2000, respetando ese orden.
3. **Supporter antes de retirar**: si `score > 2000` y `not state.supporterPlayed` y hay un Supporter de desarrollo jugable con valor (`Dawn`/`Lillie_Determination`/`Lanas_Aid` en mano con `_supp_values > 0`), el retiro se **pospone**: `score = 2000`, por debajo de la jugada del Supporter (≥2400). Retirar no se bloquea (sigue disponible después): el motor juega primero el Supporter (p.ej. Dawn busca la línea que se evoluciona con Forest este mismo turno) y re-evalúa el retiro en la siguiente decisión. **Excepción `_suicide_swap_win_promote`**: ese relevo CIERRA la partida este turno, así que no hay "resto del turno" al que el Supporter pueda aportar nada — y posponer el retiro es justo lo que dejaba al agente atacando con el suicida y firmando el empate (en el registro_016 paso 184 había una Lana's Aid en mano, que capaba el 9600 a 2000).
4. **Anti-Cubchoo**: el veto que conserva energía cuando la retirada-pivote solo cambiaría de atacante también exime `_suicide_swap_win_promote` — guardar energía para turnos futuros no significa nada si no hay turno futuro — y **`_ex_stuck_promo_ready`** (autopsia `cornerstone_cubchoo`, jul 2026). Esta última es una **colisión entre dos reglas de matchup**, la clase que la matriz de matchups existe para detectar: en un mazo mixto Cornerstone + Cubchoo, `op_is_cubchoo_deck` vetaba la única jugada que hace daño. Con el muro delante nuestro activo con Habilidad (o ex) hace **0**, y la retirada es la única vía para subir al cuerpo de banca que sí le pega — así que la energía del activo no es recurso invertido que proteger, es recurso **muerto**. El flag ya cubre las dos inmunidades (`op_has_ex_immune_active` + `OUR_EX_IDS`, `op_has_ability_immune_active` + `OUR_ABILITY_IDS`) y exige un atacante de banca con `_dmg_vs_wall > 0`, así que no abre la puerta a pivotes pelados. Medido: con muro + Tapu ≥4 en banca + retirada legal subíamos a Tapu el **13.7%** de las veces en las derrotas (vs **82.6-100%** en el mismo escenario contra Crustle, que no lleva Cubchoo); gate diferencial n=1000 **+5.4 puntos** en cornerstone_cubchoo, espejo y vecinos sin regresión.

## Interacciones

- **Con `plan` (docs 02/07)**: `plan.attacker >= 1` es la señal de que el análisis de amenaza ya eligió atacante de banca; buena parte de la escalera solo traduce a score los pivotes que ese análisis escribió en `plan`.
- **Con la familia anti-muro (docs 10/13)**: `_ex_stuck_promo_ready` alimenta el 6000; `_teal_dance_ko_pivot`/`_ripen_retreat_ko_pivot` son los mecanismos que CARGAN al activo bloqueado hasta poder pagar su retirada, momento en que esta rama dispara.
- **Con `_lucario_sac_pivot`/`_tapu_sac_priority` (docs 09/10)**: fijan el 8000; la prioridad de sacrificio (Tapu > Applin/Chikorita) depende de `_tapu_sac_priority`.
- **Con la promoción posterior (`SWITCH`/`TO_ACTIVE`, docs 10/11)**: RETREAT decide **si**; a quién se sube lo deciden `_best_promote_card` (clave `(puede_noquear, prudencia, vida, daño)`) o `_refresh_promote_prefer_basic`.
- **Con `energy_score` (doc 10)**: varios pivotes (`_hydra_fragile_pivot`, `_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`) requieren primero rutear la energía al activo para que alcance su coste de retirada; esa parte vive en `energy_score`.
- **Con la proyección defensiva**: `_op_active_attack_damage_to` (Powerful Hand `20 × (mano+2)` vs Alakazam, Maximum Belt +50 contra nuestros ex) despierta el `_hydra_wall_pivot` generalizado y la prudencia de la promoción en matchups donde antes el daño rival era ilegible.
- **Con `ATTACK` (doc 15)**: cuando `plan.attacker` apunta a banca, la propia rama de ATTACK se veta en paralelo (si el activo puede pagar su retirada), de modo que RETREAT y ATTACK actúan como un par coherente.

## Reglas derivadas de partidas

- `_same_species_retreat` (vs Dragapult, PERDIDA): no retirar si la promoción sube la misma especie; excepción de confusión vs Comfey.
- Guard `_active_can_ko_now` en `_hydra_lethal_promote` (vs Mega Lucario, GANADA): si el activo ya noquea, no pivotar a otro Hydrapple con menos energía.
- `_active_ex_fragile_pivot` (vs Hops; generalizado vs Alakazam, GANADA): un ex frágil (<330 HP) que ya remata cede igualmente el turno a un Hydrapple de banca que también remata.
- `_ogerpon_lethal_promote` (vs Alakazam, PERDIDA): modelar la rampa de Teal Dance al promover.
- `_nonex_active_hits_wall` (vs Crustle, GANADA): el no-ex que golpea al muro nunca se retira.
- Chikorita activo anti-Crustle a 6500 (turno 2, PERDIDA).
- `_prize_denial_pivot` (vs Mega Starmie, PERDIDA): no atacar con un ex condenado cuyo KO regala la partida.
- `_hydra_wall_pivot`/`_feza_lucario_wall` (vs Mega Lucario, una GANADA y una PERDIDA) y su generalización a cualquier rival con daño rival real (vs Archaludon ex, PERDIDA).
- `_hydra_fragile_pivot` (vs Abomasnow, GANADA): materializado aquí vía `_hydra_lethal_promote`.
- `_keep_ogerpon_for_kang` (vs Crustle, PERDIDA): desactiva `_ex_stuck_promo_ready` cuando el plan real es Boss's sobre el Mega Kangaskhan.
- "Supporter antes de retirar" (vs Archaludon ex, GANADA): posponer el retiro (score 2000) hasta jugar Dawn/Lillie's/Lana's.
- `_alakazam_pivot_1prize` elevado a 6000 y detección por `prize_count == 1` (dos registros vs Alakazam, PERDIDAS: la whitelist excluía a Dipplin y se atacaba con el ex exponiendo 2 premios al Powerful Hand).
