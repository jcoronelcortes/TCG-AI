# main.py — Bucle de puntuación — búsqueda y selección de cartas

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Aquí arranca el **gran bucle de puntuación** (`scores = []; for o in select.option:`) que cierra `agent()`: cada `o` es una opción concreta ofrecida por el motor y el bucle le asigna un `score` según `o.type` y el `context` de la decisión. Este documento cubre las ramas que resuelven decisiones de **elegir una carta/objetivo o responder Sí/No/Número** — todo lo que NO es jugar una carta de la mano (`PLAY`, doc 12), adjuntar/evolucionar/usar habilidad (doc 13), retirar (doc 14) o atacar/terminar turno (doc 15). Dentro de este tramo vive la lógica más extensa de selección de objetivo del archivo: el **nuevo handler de `SelectContext.DAMAGE`** (objetivo de daño libre, p.ej. *Cruel Arrow* de Fezandipiti ex), la promoción del propio activo (`SWITCH`/`TO_ACTIVE`), el objetivo de **Boss's Orders** al gustear al rival (mismo contexto, `o.playerIndex` del rival), la preparación inicial (`SETUP_ACTIVE_POKEMON`/`SETUP_BENCH_POKEMON`) y, sobre todo, **todas las búsquedas de carta hacia la mano** (`TO_HAND`): Bug Catching Set, Poke Pad, Night Stretcher, Ultra Ball, la habilidad *Last-Ditch Catch* de Meowth ex y Dawn, cada una con su escalera de prioridades por carta objetivo. Cierra con `DISCARD` (qué carta sacrificar al pagar un coste), `RECOVER_/AFFECT_SPECIAL_CONDITION` y `ATTACH_FROM`.

El patrón dominante es puntuar cada candidata según cuánto acerca al agente a su plan (completar una línea evolutiva, cargar un atacante, negar premios, refrescar la mano), con valores altos (300–24000) para forzar la elección correcta y valores bajos (10–100) como relleno. Muchas ramas citan en comentario el log/registro real que las motivó — son parches dirigidos a errores observados, no heurísticas genéricas.

## Detalle por bloque

### Cabecera del bucle: `NUMBER`, `YES`/`NO`

- **`NUMBER`**: `score = o.number` — el agente prefiere el número más alto ofrecido (más robo, más daño), sin lógica adicional.
- **`ACTIVATE`**: `YES = 10` por defecto (activar habilidades opcionales, p.ej. *Last-Ditch Catch*); `_meowth_skip_fetch` invierte a `NO = 10` cuando buscar con Meowth ex no aporta (Lillie's ya en mano).
- **`IS_FIRST`**: `YES = −1`, `NO = 2` — el agente **elige ir segundo** (el robo extra compensa la iniciativa); ambas ramas actualizan el global `we_go_first`.
- **`COIN_HEAD`**: `YES = 2` — siempre "cara" (elección arbitraria pero determinista).

### `OptionType.CARD`: obtención de la carta

`get_card(obs, o.area, o.index, o.playerIndex)` resuelve la opción al objeto real; a partir de ahí `card.id` es el eje de todas las ramas por contexto, con `energy_count = len(card.energies)` si es un Pokémon.

---

### `SelectContext.DAMAGE` — objetivo de daño libre (Cruel Arrow)

**Handler nuevo.** Cuando el contexto es `DAMAGE` y el candidato es un Pokémon **rival**, la decisión es a quién golpea un ataque que elige objetivo libre (p.ej. *Cruel Arrow* de Fezandipiti ex, 100 fijo). Antes NO había handler y el argmax caía en la opción 0 (el activo) — en el registro que motivó la regla se apuntaba al Crustle activo, **inmune** al daño de nuestros ex, con un Dwebble de 70 HP noqueable en banca.

Regla: se evalúa **todo el campo rival** con el daño **efectivo** — `_attacker_base_damage` (con `grass_scale`, `teal_self_energy`, `bench_count`) pasado por `_our_effective_damage`, que aplica la inmunidad ex de Crustle, la Neutralization Zone, debilidad/resistencia (Cruel Arrow es daño fijo de Oscuridad, sin debilidad Planta):

1. **Objetivo NOQUEADO**: `score = 10000 + 1000 × prize_count(card) + 10 × energía + hp/10` — entre KOs, más premios > más cargado > más vida (más desarrollado).
2. **Nadie muere**: chip al que **más cerca** queda del KO — `score = 100 + 100 × daño_efectivo / hp`.
3. **Inmunes** (daño efectivo ≤ 0): `score = 1` — último recurso (la selección es obligatoria).

La rama hace `scores.append` y `continue` propia, sin pasar por el resto del bucle.

---

### `SWITCH` / `TO_ACTIVE` — promover nuestro propio Pokémon

`o.playerIndex == my_index` cubre dos disparadores con la misma puntuación: promover tras un KO del activo, y elegir a quién subir tras una retirada voluntaria.

#### Sacrificio dirigido para Mega Lucario ex

Con `_lucario_sac_context` activo (doc 10), el objetivo es **entregar el mínimo de premios** a un Mega Lucario ex que va a noquear igual: con `_tapu_sac_priority`, Tapu Bulu (6000) > Applin (5500) > Chikorita (5000); si no, Applin (6000) > Chikorita (5500) > Tapu Bulu (200); resto 100.

#### ¿Puede atacar? — base de puntuación

`_can_attack_now` usa `_can_attack_eff`/`ATTACK_ENERGY_REQ` (incluye Pinsir). `_can_attack_with_attach` añade el adjunte de este turno — la Planta puede venir de la mano **o de Night Stretcher con Planta en el descarte** (`_ns_grass_recover_switch`), y se permite aunque ya se haya adjuntado si es promoción forzada por activo vacío (`_forced_promote_switch`). Base: puede atacar ya = 500; podría con adjunte = 350; resto = 100. Encima se suma `hp // 10` y `energy_count` — a igualdad, el cuerpo más grande y cargado.

#### Negación de premios y confusión

- `op_prize <= 2` + `_can_attack_now` + `prize_count(card) <= 1` → `+3000`: con el rival a ≤2 premios de ganar, subir un atacante de 1 premio que ya pega evita que su próximo KO cierre la partida. Nunca penaliza a un ex si es el único que ataca.
- `is_confused` + `_can_attack_now` + `_conf_is_matchup_attacker(card.id)` → `+2000`: tras retirar un activo confundido, priorizar el atacante del matchup que ya pega.

#### HP como muro cuando nadie puede atacar

Sin `_can_attack_now` ni `_can_attack_with_attach`: `score += hp // 5` y, con `estimated_op_damage` conocido, `+80` si sobrevive el golpe o `−20` si no.

#### Bonos por especie

- `Hydrapple_ex`: `+4000` si `_teal_wall_pivot` (subir el muro de 330 aunque no ataque); `+60` base, `+min(syrup//10, 30)` si ataca, `+250` si atacaría tras adjunte, `+500` si `_cm_use_ex` (usar el ex contra el Mega Kangaskhan y reservar no-ex para Crustle).
- `Tapu_Bulu`: `+50` si ataca; `−500` si `_cm_use_ex` (reservarlo para Crustle); `+80` vs inmune-a-ex/Crustle; `+120` vs Cornerstone.
- `Teal_Mask_Ogerpon_ex`: `+30`; `+500` si `_cm_use_ex` y puede atacar.
- `Dipplin`: `+15`; `+40` vs inmune-a-ex; `+5000` combo específico (Crustle, activo ya retirado, sin energía, Night Stretcher en mano y Planta en descarte).
- `Meganium`: `+120` si ataca vs Crustle/inmune-a-ex, si no `−80`.
- `Meowth_ex`/`Fezandipiti_ex`/`Chikorita`/`Bayleef`/`Applin`: `−100`/`−100`/`−60`/`−50`/`−70` (cuerpos de soporte, malos candidatos salvo que otra regla los priorice).

Regla vs Crustle sin nadie que ataque: si nadie golpea al muro, `Teal_Mask_Ogerpon_ex` `+300` (muro desechable de 210 HP) y `Tapu_Bulu` `−300` (reservarlo en banca como el atacante que sí noquea a Crustle). No aplica con `_cm_use_ex`.

#### Debilidad y lookahead

Debilidad al tipo del activo rival: `−250`. Con `_op_best_damage_vs`/`_op_counter_threat_vs` (que ahora modelan **Maximum Belt**, +50 contra nuestros ex): KO probable el próximo turno → `−SCORE_LOOKAHEAD_PROMOTE_KO`; daño ≤40% del HP → `+SCORE_LOOKAHEAD_PROMOTE_SAFE`.

#### Bonos de evolución con `Forest_of_Vitality` disponible

Con `_forest_available` (estadio en juego o en mano), promover `Applin`/`Dipplin` con la evolución siguiente en mano suma bonos grandes (300–600 según cuán completa está la línea, +100–150 extra con energía lista o repartida en banca, +100 si la línea Meganium también es alcanzable): subir el eslabón que se evoluciona YA este turno.

#### Línea Chikorita: veto de promoción y atacante designado

Promover cualquier miembro de la línea Chikorita/Bayleef/Meganium con más de un Pokémon en banca es un veto casi total (`SCORE_NEVER`): esa línea es el motor Wild Growth, no el activo. Excepciones (`_meg_designated_attacker` → `+400`): Meganium cargado (≥4) como único remate vs Crustle/Cornerstone; **Meganium listo vs Alakazam** (cuerpo de 1 premio que noquea — necesario para que el pivote `_alakazam_pivot_1prize` pueda promoverlo); **Meganium bajo Neutralization Zone** contra un activo rival sin Rule Box (los ex hacen 0, Meganium 140 es el atacante designado).

#### Inmunidades y matchups específicos

- `op_has_ex_immune_active`/`op_has_ability_immune_active`: `+150`/`+180` a cuerpos no bloqueados, `−80`/`−100` a los nuestros bloqueados.
- `op_is_fire_deck`: Hydrapple ex que ataca `+40`. `op_is_control_deck`: Tapu Bulu que ataca `+50`.
- Activo rival Drednaw: Meganium/Dipplin que atacan `+250…+150`; nuestros Hydrapple/Tapu `−150`.
- Activo rival Sylveon: Tapu Bulu/Meganium/Dipplin `+280…+150`; `OUR_EX_IDS` `−200`.
- `neutralization_zone_active` con activo rival sin Rule Box: mismo patrón (`+250…+140`, ex `−200`).

#### `plan.attacker`, evoluciones en mano y Crustle activo

- `o.index == plan.attacker - 1` → `+120` (coincide con el atacante del `AttackPlan`).
- Con la siguiente evolución en mano: Dipplin+Hydrapple `+80`; Bayleef+Meganium `−30`; Applin+Dipplin `+60` (`+20` sin Forest+Hydrapple); Chikorita+Bayleef `−30` con Forest+Meganium, si no `+5`.
- `has_condition` → `+50` (subir a un candidato sano).
- Contra Crustle **activo** (`op_has_ex_immune_active`): un no-ex que SÍ ataca y daña gana con `+6000`; si ningún no-ex puede atacar, se sube un ex-muro: con energía `+3000 + energía×10`, sin energía Ogerpon ex `+2500` sobre el resto `+2000`.

#### `_best_promote_card` y overrides de refresco

- `card is _best_promote_card` → `+4000`: el bono decisivo genérico (precalculado en el doc 10 con la clave `(puede_noquear, prudencia, vida, daño)` y los overrides de Tapu Bulu y `_ak_1prize_prom`).
- `_lucario_ko_prefer_basic`: fuerza `9000` Applin, `8500` cualquier básico, `8000` Dipplin.
- `_refresh_promote_prefer_basic`: sube un básico no-ex (`Applin` 6000, otro básico 5500) en vez de un ex cuando nadie puede atacar y hay Lillie's para refrescar.

---

### `SWITCH` / `TO_ACTIVE` — objetivo de Boss's Orders sobre el rival

Rama `else` del mismo contexto (`o.playerIndex` del rival): a qué Pokémon de su banca gustear.

#### Vetos inmediatos

`card.id in DUNSPARCE_IDS` → `SCORE_FORBID`: nunca gustear un Dunsparce.

#### Modo estorbo (nuestro activo no puede atacar)

Si `_active_cant_attack_this_turn or _sel_active_cant_attack`, Boss's se usa como **estorbo**: se prioriza el mayor coste de retirada neto (`_stall_diff = coste − energía`), `score += 500 + _stall_diff × 100`. Coste de retirada 0 → `SCORE_FORBID` (el rival lo cambia gratis). `op_has_latias_ex` (habilidad *Skyliner*): nunca gustear a la propia Latias ex ni a un básico (se retiran gratis) → `SCORE_FORBID`; el objetivo correcto es un no-básico (p.ej. Drakloak). Desempate: `−50` a `THREAT_PREEVO_IDS`/`EX_PREEVO_IDS` (no dejar activa una pre-evo que evolucionaría y atacaría desde ahí).

Dos sobreescrituras dentro del estorbo:

- **Gustear la mayor evolución noqueable (mazos de Fase 2)**: generalización de la regla Alakazam (motivada por una partida vs **Cynthia's Garchomp**) — aunque el activo no pueda atacar, si podemos RETIRAR (energía ≥ coste, o carta de switch en mano) y un atacante de banca noquea al objetivo (`_bench_attacker_can_ko`, descontando el Grass gastado en la retirada), se privilegia la **mayor evolución** de la línea rival: `score = max(score, 6000 + rank×3000 + energía×50 + 300 si lleva herramienta)` con rank stage2=2 > stage1=1. Alakazam conserva su regla propia.
- **Priorizar la línea Alakazam como estorbo**: vs Alakazam, `Kadabra +350 > Abra +300 > Alakazam_ex +250` — atrapar su pre-evo corta el motor Psíquico y contrarresta el `−50` de EX_PREEVO.

#### Modo ofensivo: `_boss_can_ko`

Cuando el activo SÍ puede atacar, se calcula si el ataque actual noquearía al objetivo, reproduciendo las fórmulas de daño propias (contando el posible adjunte de este turno, `_boss_atk_after`): Hydrapple `30+30×total_grass`; Dipplin `20×banca`; **Ogerpon con la Myriad corregida** `30 + 30×(energía_del_objetivo + energía_propia_tras_adjunte)`; Tapu Bulu 220; Fezandipiti 100; Meganium 140; Bayleef 60. Aplica ×2 debilidad / −30 resistencia Planta (salvo Fezandipiti, daño no-Planta), y anula el daño si el objetivo está en `EX_IMMUNE_IDS` y atacamos con ex (nótese que `EX_IMMUNE_IDS` incluye ahora `Crustle_Fighting` además de `Crustle_Grass` y `Sylveon`), o en `ABILITY_IMMUNE_IDS` con atacante de habilidad. Si el activo no noquea, revisa si retirándolo (`_bo_can_retreat`, con el Grass descontado) un atacante de banca sí lo lograría (`_bench_attacker_can_ko`).

#### Tier de KO por etapa evolutiva

Con `_boss_can_ko`: ex/mega con energía (tier 8) > ex/mega (7) > stage2 con energía (6) > stage2 (5) > stage1 con energía (4) > stage1 (3) > básico con energía (2) > básico (1); `score += tier × 3000`.

**Boost de pre-evo ex energizada**: una pre-evo **con energía** de una línea ex (`EX_PREEVO_IDS`) recibe un tier efectivo de **19500** (`score += max(0, 19500 − tier×3000)`) — por encima de cualquier no-ex (tier 6 = 18000), por debajo de un ex real (tiers 7–8). `EX_PREEVO_IDS` incluye ahora la **línea Cynthia** (`Cynthias_Gible`, `Cynthias_Gabite` → `Cynthias_Garchomp_ex`): sin ellas el deny-evo jamás disparaba vs Cynthia y el agente atacaba al muro Spiritomb en vez de gustear el Gabite energizado. También están Dreepy/Drakloak, Riolu, Duraludon, Zorua_N, Abra/Kadabra, Ralts/Kirlia, Marnies_Impidimp/Morgrem y Buneary (→ Mega Lopunny ex). `NONEX_FINAL_PREEVO_IDS` (Abra, Kadabra) marca las líneas cuya forma final es no-ex (Alakazam id 743 es 1 premio): la lógica de "negar una línea EX" no les aplica.

#### Sin KO con activo que ataca

Estorbo puro: `+_bo_stall_diff × 100` (mismo criterio de coste neto), desempate `−50` en pre-evos de amenaza. Bono `+200` si el objetivo es el propio activo rival sin energía y el candidato sí tiene.

#### Reglas de matchup dirigidas por línea evolutiva

Tres bloques gemelos por arquetipo (`op_has_dragapult`/`op_has_dreepy_line`, `op_has_typhlosion`/`op_has_ethan_preevo`, `op_is_alakazam_deck`), mapeando la línea completa:

| Rol | Con KO | Sin KO, sin energía para retirarse | Sin KO, con energía |
| --- | --- | --- | --- |
| Fase 2 (Dragapult ex / Typhlosion / Alakazam) | `+1200` | `+800` | `+800` |
| Fase 1 motor (Drakloak / Quilava / Kadabra) | `+1000` | `+700` (queda CLAVADO, retrasa la evolución) | `+300` (se reposiciona gratis) |
| Básico (Dreepy / Cyndaquil / Abra) | `+400` | `+500` (clavado: más estorbo que la fase 1 con energía) | `+200` |

La fase 1 es la pieza que habilita al atacante final con su habilidad de motor; clavarla sin energía retrasa toda la línea.

#### Reglas genéricas por tier

Con KO: ex+energía `+1100`, ex `+1000`, stage2+energía `+900`, stage2 `+850`, stage1+energía `+700`, stage1 `+600`, básicos con nombre (`THREAT_PREEVO_IDS` `+550` — incluye ahora `Rockets_Tarountula`, motor barato de la línea Rocket's Mewtwo —, `Budew` `+500`, `Munkidori` `+450`, `Snorunt` `+400`, `Dwebble_*` `+380`, `Dreepy` `+350`, con energía `+300`, sin `+200`). Sin KO: misma jerarquía con valores menores (`+250…+100`), añadiendo `Froslass` `+220` y `Dreepy`/`Drakloak` `+180`, `Dwebble_*` `+178`.

#### Vetos finales

- Vs Crustle, gustear un `Dwebble_*` → `SCORE_FORBID`.
- Regla general: retirada gratis sin KO → `SCORE_FORBID` (solo vale gustearlo como KO real).

---

### `SETUP_ACTIVE_POKEMON`

`Teal_Mask_Ogerpon_ex` domina (100; tanque de 210 HP sin información del matchup). Entre básicos, se prefiere duplicado en mano (`Chikorita`/`Applin` con ≥2 copias = 7), luego `Applin` (5) sobre `Chikorita` (3). `Meowth_ex` = 0 (su valor es la habilidad al bajarlo, no resistir).

### `SETUP_BENCH_POKEMON`

`Chikorita` 8 (10 vs fuego/agresivo) > `Applin` 7 (4 con `op_bench_snipe_threat`; 8 vs fuego/agresivo) > `Teal_Mask_Ogerpon_ex` 6 (7 vs fuego). `Meowth_ex` → `SCORE_VETO`. `Fezandipiti_ex`: solo si es el **único** Pokémon de la mano de setup (2; 0 con Froslass; 1 con snipe) — revelar un ex de 2 premios débil a Lucha antes de ver el activo rival es un riesgo (crítico vs Mega Lucario, indetectable en el setup). `Tapu_Bulu`: 3 solo con Meganium+inmune-a-ex o vs Crustle. `Pinsir`: 3 vs Crustle/Sylveon/Cornerstone, 2 vs inmune-a-ex, veto en el resto.

---

### `TO_HAND` — búsquedas de carta hacia la mano

Base común: `score = 200 − hand_counts[card.id] × 100` (penaliza duplicados). `select.effect.id` determina el origen y su escalera propia.

#### Bug Catching Set

Busca Pokémon/Energía Planta del mazo. Patrón para ambas líneas de ataque: puntuación máxima (~800–1000) a la pieza que **completa la evolución de lo que ya está en campo** (p.ej. Bayleef con Chikorita en juego 850, 950 con Forest+Meganium en mano), intermedia si la pre-evo está solo en mano, baja (20–50) si la línea está completa. Ogerpon/Tapu/Pinsir/Meowth/Fezandipiti con condiciones puntuales (Pinsir 750 solo vs Crustle/Cornerstone). Bono `+100` si la mayoría de copias está en premios (`ESTADO_PREMIO`) con ≤1 accesible. Restricción final vs Crustle/Cornerstone: si la carta no está en la lista válida del matchup, `SCORE_VETO`.

#### Poke Pad

Busca un Pokémon sin Rule Box hacia la mano. En nuestro primer turno prioriza completar la banca básica: `Applin` 2000 / `Chikorita` 1900. Fuera del primer turno usa el **tablero actual** (`field_counts`), no la foto de inicio de turno, para recomendar la evolución de un Pokémon recién bajado: Meganium con Bayleef en banca 1000; Bayleef con Chikorita 850/950; Dipplin con Applin 800/920; básicos nuevos 800/650.

#### Night Stretcher

Recupera del descarte un Pokémon **o** una energía básica. La energía Planta domina en orden de prioridad:

1. `_act_hyd_ripen` (1300): Hydrapple ex activo que no llega a 2 efectivas y sin Planta en mano — recuperar energía para cargarlo vía *Ripening Charge* (habilidad independiente del adjunte manual, no exige `energyAttached` libre).
2. `_ns_bench_charge_sel` (950): vs Crustle/Cornerstone, cargar un atacante de banca que no llega a su requisito.
3. `_active_needs_energy` sin Planta en mano ni adjunte hecho (900).
4. `_act_og_can_teal_attack` (900): Ogerpon ex activo con <3 efectivas que llegaría a ≥3 con una Planta más (habilita Teal Dance) — cubre el combo retirar→promover Ogerpon→Night Stretcher→Teal Dance→atacar.
5. Sin Planta en mano en general (600/700; 750 con Ogerpon ex en banca).
6. Con Hydrapple en juego y poca energía total (450); con ≥3 copias en mano, 100.

Para Pokémon, repite el patrón de "completar la línea en juego" (Hydrapple ex 980 con Dipplin en juego; Meganium 990 con Bayleef; etc.), usando `_field_at_turn_start` cuando NO hay Forest (no recomendar piezas injugables este turno).

#### Ultra Ball

El bloque más largo del tramo. Banderas de contexto antes de puntuar cada carta:

- `hand_is_weak` (vía `_count_hand_play_options`): pocas jugadas y mano corta.
- `_t1_going_second_meowth` / `_t1_going_second_need_ogerpon` / `_t1_going_first_need_basic`: casos de primeros turnos sin banca ni básicos jugables.
- `_ub_prefer_meowth_develop`: banca vacía, sin básico jugable ni Lillie's en mano, Meowth ex y Lillie's en el mazo, sin Watchtower → traer Meowth ex para refrescar.
- `_dipplin_priority` (`_dp_lillie_played or _dp_anti_ex or _dp_hydra_line`): solo se privilegia Dipplin/Hydrapple sobre Meowth en 3 casos — (1) Lillie's ya jugada **y agotada** (ninguna copia queda en el mazo: haber jugado una no basta si quedan más), (2) matchup anti-ex con Dipplin capaz de atacar tras evolucionar, (3) Forest+Hydrapple en mano con evolución y ataque (Syrup Storm) este mismo turno.
- `_ub_hydra_dead_prefer_meowth` / `_ub_mega_dead_prefer_meowth`: la evolución "grande" disponible (Hydrapple sin energía para atacar / Meganium sin Bayleef en juego) quedaría **muerta** este turno y no hay atacante listo → preferir Meowth ex (motor Lillie's).
- `_ub_no_attacker_prefer_meowth`: generalización — no hay **atacante usable** este turno (ni activo que ataque, ni atacante de banca listo que se pueda subir porque el activo no puede pagar su retirada) → traer Meowth ex aunque la evolución sea jugable.

Escalera de `Meowth_ex` como objetivo: Watchtower → 10; Lillie's ya en mano → 10 (salvo excepción vs Crustle donde Meowth busca Boss's); **`_ub_engine_pivot_turn` → 1300** (esta Ultra Ball se jugó por el pivote `_ub_engine_refresh_pivot`, ver doc 12: el fetch DEBE completar la cadena Meowth→Last-Ditch→Lillie's; sobre cualquier evolución); `_ub_prefer_meowth_develop` → 1250; `_ub_hydra_dead_prefer_meowth`/`_ub_mega_dead_prefer_meowth` → 1000; `_ub_no_attacker_prefer_meowth` → 1250; `_t1_going_second_meowth` → 1200; vetos blandos (primer turno yendo primero, 2 copias en juego, un Meowth con activo que ataca, banca llena, `_dipplin_priority`) → 10; `_mega_line_active` con Lillie's en mazo → 1150; vs Dragapult-Dusknoir → 985; vs Crustle con Boss's valioso en mazo → 1100; Lillie's en mazo → 1000; otro Supporter en mazo → 850; nada → 10.

Resto de objetivos, siguiendo "completar la línea más cercana a jugarse": `Teal_Mask_Ogerpon_ex` (hasta 800/1050 en aperturas; 350/700+100 con energía para Teal Dance), `Meganium` (hasta 1000), `Hydrapple_ex` (1200 si el Dipplin activo evolucionaría y atacaría YA; 980/900; **860** para prepararlo al próximo turno si Dipplin es el único Planta en juego o la línea Meganium no es evolucionable ya; degradado a ≤40 vs inmunes-a-ex; ≤150 con `_ub_hydra_dead_prefer_meowth`), `Bayleef`/`Dipplin`/`Chikorita`/`Applin` (500–980 por cercanía; duplicados en mano → 20), `Tapu_Bulu` (750/850 con Meganium+inmune-a-ex), `Pinsir` (900 vs Crustle/Cornerstone), `Fezandipiti_ex` (1050 tras KO con hueco en banca). Cierre: `+150` si la mayoría de copias está en premios; `−150` si ya hay una copia en mano.

#### Habilidad de Meowth ex — *Last-Ditch Catch*

Busca un Supporter del mazo (`_supp_ids` incluye ahora `Xerosic_Machinations`). Escalera:

1. **`Boss_Orders` = 1300** con remate identificado (`_win_via_boss_gust`/`_gust_2prize_via_boss`).
2. **`Boss_Orders` = 1280** con **`_deny_evo_via_boss`** (motor Boss's de VALOR): hay una pre-evo de línea ex ENERGIZADA en la banca rival que noqueamos tras gustearla y el Boss's está en el mazo — cortar la línea prima sobre refrescar.
3. **`Lillie_Determination` = 1250** con `_meowth_devel_lillie`.
4. **`Xerosic_Machinations` = 1260/1200 vs Alakazam**: con mano rival ≥6 (Powerful Hand = 20×carta), Meowth busca Xerosic para capar el daño — **1260** si ya hay un atacante fuerte en juego (Hydrapple/Ogerpon; manda aunque nuestra mano quede vacía), **1200** si no (requiere mano propia ≥3).
5. **`Xerosic_Machinations` = 1100 genérico**: contra **cualquier** mazo con mano rival ≥7, atacante fuerte en juego y activo que ataca — bajo Lillie's (1200–1250) y los Boss's (1280/1300); los guards evitan que Xerosic secuestre el fetch del turno muerto.
6. Mano propia ≤2 → `Lillie_Determination` = 1200 (resto capado a 100).
7. Activo que no ataca sin energía en mano, o sin Lillie's en mano → Lillie's = 1200 (resto capado a 150).
8. Sin atacante fuerte: mano ≤5 → Lillie's = 1000; si no → Lillie's = 800 (resto capado a 200/400).
9. Con atacante fuerte: `score = _supp_values[card.id]` (valoración genérica), `+100` a Boss's vs Crustle, y el **gate de Forest para Dawn**: sin `forest_in_play`, Dawn se capa a `valor_de_Lillie's − 50` — Dawn (arma la línea evolutiva) solo interesa desde Meowth si Forest está EN JUEGO y permite el rush de evolución; sin Forest, refrescar con Lillie's da más.

#### Dawn

Mismo patrón de "completar la línea más avanzada" con `_forest_avail` (en juego o en mano): `Meganium` 1000 (Bayleef en juego) / 950–980 (Chikorita+Forest); `Bayleef` 900/970; `Hydrapple_ex` 980 (Dipplin en juego) / 900–960; `Dipplin` 880/950; `Chikorita`/`Applin` 480–850 según Forest y piezas en mano; `Teal_Mask_Ogerpon_ex` 400/500; `Tapu_Bulu` 600/700 vs inmune-a-ex; `Fezandipiti_ex` 500 tras KO; `Meowth_ex` 300 si su habilidad sería usable; `Basic_Grass_Energy` 400 si no se adjuntó aún; `Forest_of_Vitality` 600 sin estadio disponible. `else` final: `50 − hand_counts×30`.

#### Rama genérica

Para efectos no reconocidos (p.ej. Lana's Aid): bonos/penalizaciones modestos (±50 a ±200) con la misma idea de completar líneas no duplicadas.

Excepción final vs Cubchoo: para `Night_Stretcher`/`Lanas_Aid`, se fuerza recuperar solo `Basic_Grass_Energy` (`max(score, 900)`) y se vetan los Pokémon — el turno post-Cubchoo se usa para recargar energía.

---

### `DISCARD`

Puntuación de qué descartar al pagar un coste (valores **altos = descartable**, bajos = proteger). Banderas: `_has_recovery` (Night Stretcher/Lana's en mano o mazo), `_protect_last_supporter`/`_protect_refresh_supporter` (proteger el único Supporter sin jugar; el conteo incluye `Xerosic_Machinations`), `_teal_dance_possible` (condiciona cuánta Planta es "sobrante").

Escalera representativa:

- `Basic_Grass_Energy`: 35–92 sin Teal Dance posible; 2–85 con Teal Dance (más conservador). `+5` con recuperación disponible.
- `Meganium`/`Bayleef` con la línea ya en juego: 85–95; a una evolución de completarse (pre-evo en juego): **3** (casi intocable).
- `Hydrapple_ex`: **96** vs Crustle/inmunes-a-ex (carta muerta); 3 con Dipplin/Applin en juego o línea armable.
- `Fezandipiti_ex`: `SCORE_NEVER` si hubo KO el turno anterior con hueco en banca (su habilidad está viva).
- `Boss_Orders`: 2 vs Crustle/Dwebble con copia única; protegido 12–22 (cae **antes** que Lillie's si hay que soltar un Supporter).
- `Lillie_Determination`: la primera copia evaluada se protege (2–16 vía `_lillie_protected_once`); las sobrantes 72.
- **`Xerosic_Machinations`**: **5** vs Alakazam (se protege como la línea Meganium — es la carta que capa Powerful Hand); 60 en otros mazos.
- `Night_Stretcher`: `SCORE_VETO` si el único objetivo recuperable es energía muerta (`state.energyAttached`); 30–78 según duplicados.
- `Unfair_Stamp`: `SCORE_NEVER` — nunca se descarta con alternativa.
- Ítems (`Ultra_Ball` 38/95 duplicada, `Bug_Catching_Set` 45/85 bajo Itchy Pollen, `Poke_Pad` 55/85).

Override vs Comfey (mill): la prioridad de MANTENER es Energías (80) > Night Stretcher (300) > Lana's (400) > Unfair Stamp (500) > resto de entrenadores (850); un Ogerpon ex extra (ya hay 2 en juego) se descarta (850), si aún caben se conserva (120).

### `RECOVER_SPECIAL_CONDITION` / `AFFECT_SPECIAL_CONDITION` / `ATTACH_FROM`

Los dos primeros puntúan 50 fijo para cualquier candidato con `id` (decisión casi neutra; la selección fina por tipo de condición vive en `OptionType.SPECIAL_CONDITION`, doc 15). `ATTACH_FROM` (objetivo de *Ripening Charge*) reutiliza directamente `energy_score(card, o.area == AreaType.ACTIVE)` — la misma función del adjunte manual (doc 10).

## Interacciones

- Lee (sin recalcular) el estado de los bloques previos: `field_counts`/`hand_counts`/`discard_counts`, `op_is_*_deck`/`op_has_*` (incluida la **inferencia de arquetipo por el descarte rival**, que enciende los flags 2-3 turnos antes), `plan` (`AttackPlan`), la escalera de Boss's (`_supp_values`, `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_deny_evo_via_boss`), y las banderas de decisión del doc 09/10 (`_meowth_devel_lillie`, `_meowth_skip_fetch`, `_lucario_sac_context`, `_tapu_sac_priority`, `_cm_use_ex`, `_teal_wall_pivot`, `_lucario_ko_prefer_basic`, `_refresh_promote_prefer_basic`, `_best_promote_card`, `op_bench_snipe_threat`).
- Usa el sistema de creencia `CARTAS_ACTIVAS_EN_MAZO`/`ESTADO_MAZO`/`ESTADO_PREMIO` para decidir urgencia de búsqueda en casi todas las ramas de `TO_HAND`.
- `_ub_engine_pivot_turn` es un **global** que arma `_score_ultra_ball_play` (doc 12) cuando dispara `_ub_engine_refresh_pivot`; el fetch de esa misma Ultra Ball lo consume aquí (Meowth ex = 1300) y se resetea al cambiar de turno.
- `_deny_evo_via_boss` se calcula como flag **standalone** en el bloque mano-O-mazo del motor Boss's (junto a `_win_via_boss_gust`): espejo conservador de la maquinaria in-hand `_boss_deny_evo`, pensado para cuando el Boss's está en el MAZO; alimenta el fetch (1280) y la rama PLAY de Meowth ex (22000, doc 12).
- Los valores extremos de este tramo (hasta 24000 en el tier de KO de Boss's, `SCORE_FORBID` en vetos) conviven con las escalas de `PLAY`/`ATTACH`/`RETREAT`/`ATTACK`; la comparación final ocurre en la finalización (doc 15).
- El contexto `SWITCH`/`TO_ACTIVE` sirve **dos** propósitos con la misma rama (promover propio vs gustear rival), diferenciados por `o.playerIndex`.

## Reglas derivadas de partidas

- Handler de `DAMAGE`: apuntaba Cruel Arrow al Crustle activo inmune con un Dwebble de 70 HP noqueable en banca (vs Crustle, PERDIDA).
- Promover Ogerpon como muro desechable y reservar Tapu vs Crustle cuando nadie ataca (turno 2, PERDIDA).
- Preferir promover un básico de 1 premio con Lillie's disponible cuando nadie puede atacar.
- Pre-evo ex energizada como objetivo prioritario de Boss's (tier efectivo 19500; vs Archaludon ex, PERDIDA) y su extensión a la línea Cynthia (vs Cynthia's Garchomp, PERDIDA la jugada).
- Con banca vacía y sin básico jugable, Ultra Ball trae siempre Meowth ex (vs Lucario, GANADA).
- Con Lillie's ya en mano, Ultra Ball no busca Meowth ex (vs Mega Starmie, PERDIDA).
- Lillie's jugada no privilegia a Dipplin si quedan copias en el mazo (vs Marnie, GANADA).
- Night Stretcher recupera Planta para el combo Ogerpon→Teal Dance→atacar (vs Alakazam).
- Fetch de Xerosic a 1260 con atacante fuerte (vs Alakazam, PERDIDA la partida que lo motivó) y gate de Forest para Dawn (vs Marnie's Grimmsnarl ex, PERDIDA).
- `_deny_evo_via_boss` a 1280/22000 (vs Garchomp, registro con error pese a victoria).
