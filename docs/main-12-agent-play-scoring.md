# main.py — Bucle de puntuación — PLAY (jugar cartas de la mano)

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Esta es la rama `elif o.type == OptionType.PLAY:` dentro del gran bucle `for o in select.option:` de `agent()`. Para cada opción `PLAY` se resuelve `card = get_card(obs, AreaType.HAND, o.index, my_index)`; si no resuelve, `score = SCORE_VETO`. Después `data = card_table[card.id]` bifurca en dos grandes ramas según `data.cardType`:

- **`CardType.POKEMON`**: puntuación de "bajar un Pokémon de la mano", con un bloque por carta (Chikorita, Applin, Teal Mask Ogerpon ex, Meowth ex, Fezandipiti ex, Tapu Bulu, Pinsir) seguido de overrides transversales (objetivos pendientes de Poke Pad/Ultra Ball, motor Xerosic con Meowth en mano, matchup Cubchoo, **reserva de banca vs Alakazam**, rescate anti-softlock, sinergia Dipplin, límites de copias de Meowth ex, estrategia vs Comfey).
- **`else` (Trainer/Estadio)**: la mayor parte de la lógica vive ahora en scorers extraídos `_score_*_play(ctx)` que reciben el `DecisionContext` construido antes del bucle (doc 10): `_score_forest_of_vitality_play`, `_score_bug_catching_set_play`, `_score_ultra_ball_play`, `_score_night_stretcher_play`, `_score_poke_pad_play`, `_score_unfair_stamp_play`, `_score_boss_orders_play`, **`_score_xerosic_play`**, `_score_lillie_determination_play` y `_score_lanas_aid_play`; Dawn conserva su rama inline.

Constantes de escala: `SCORE_DEVELOP_BASE = 20000` (base Pokémon), `SCORE_ITEM_BASE = 10000` (base Trainer), `SCORE_SUPPORTER_VALUE_BASE = 2400`, y los pisos `SCORE_VETO = −1`, `SCORE_CANCEL = −100`, `SCORE_NEVER = −10000`, `SCORE_FORBID = −100000`. El resultado compite en la ordenación final por `(tier, score)` (doc 15): la banda ~20000–22500 marca Pokémon de desarrollo prioritario, ~4500–6800 Supporters preferentes.

## Detalle por bloque — Pokémon

### Veto de 4º ex vs Crustle/Cornerstone

Todo Pokémon parte de `score = SCORE_DEVELOP_BASE`. Contra Crustle/Cornerstone se cuentan los ex propios en mesa (`OUR_EX_IDS`); con 3 o más, un 4º ex se veta antes de evaluar la carta (`_block_4th_ex`).

### Chikorita

Máximo de línea Meganium: 2 copias vs Crustle/Cornerstone, 1 en el resto (`_max_meg_line`); alcanzado el máximo, veto. Con Mega Starmie ex activo rival y sin evolución rápida (Forest disponible + Bayleef en mano), veto. Si no: `21500`, subido a `21700` vs espejo/fuego/Crustle/agresivos/Beedrill y `21600` vs Greninja/Dragapult-Dusknoir; `+200` con Forest+Bayleef (evolución inmediata).

### Applin

- `_dragapult_snipe_setup` (Dragapult ex rival cargado Fuego+Psíquico con activo rival de retirada gratis): si Applin no puede evolucionar ya (Forest en juego + Dipplin en mano), veto — bajar Applin lo expone al snipe.
- Veto con banca llena, y vs Cubchoo si ya hay un miembro de la línea Hydrapple en juego (una sola línea viva).
- Veto con Mega Starmie ex activo sin evolución inmediata.
- Base `21200`, `20800` con un Applin ya en juego; `+200` con Forest+Dipplin; `+300` vs fuego/agresivo sin Hydrapple; con `op_bench_snipe_threat` sin Forest, la línea iniciada baja a `18000` y `−500` extra sin Dipplin en mano.

### Teal Mask Ogerpon ex

Veta la 3ª copia vs Crustle/Cornerstone salvo Mega Kangaskhan rival. Veto con banca llena. Con 2 copias en juego, una 3ª solo con Planta en mano (`20500`, sinergia Teal Dance) o con Kangaskhan + línea Meganium presente (`20500`). Resto: `21000`.

### Meowth ex — cascada completa

Meowth ex (*Last-Ditch Catch*: al bajarlo busca un Supporter del mazo) tiene la cascada más larga del bloque; la primera condición que se cumple fija el score. `_meowth_ld_free` (no apareció este turno otro Meowth que ya gastara la habilidad) guarda varias ramas.

1. **Veto por Team Rocket's Watchtower** (`watchtower_in_play`): anula la habilidad → `SCORE_VETO`. Reaparece al final como blindaje.
2. **Veto por Unfair Stamp jugable** (`_stamp_blocks_supp_chain`: nos noquearon el turno anterior y el Sello sigue en mano) → `SCORE_VETO`. El Sello **baraja toda la mano al mazo**, así que cualquier Supporter que traiga *Last-Ditch Catch* se pierde de inmediato y además se expone un cuerpo de 2 premios. Va ARRIBA de los tres motores Boss's (items 3-4 y el motor vs activo inmune `_meowth_immune_boss_engine`, `22000`): estaban exentos con el argumento de que "el Boss's se JUEGA este turno", pero es falso — todos los scorers de `_SUPP_PLAY_IDS` vetan con `cede_a_unfair_stamp`, así que ese Boss's no puede jugarse este turno y el Sello lo devuelve al mazo (registro_008 paso 90 vs Alakazam: se cavaba con `_gust_2prize_via_boss` y solo se recuperó por suerte entre las 5 cartas robadas). Orden correcto: ítems → Unfair Stamp → y solo **después**, si procede, bajar Meowth ex (el Sello es Item: al salir de la mano el flag se apaga y la cascada se re-habilita).
3. **Motor Boss's GANADOR vía Meowth → `22500`**: existe un plan de gusteo letal (`_win_via_boss_gust` o `_gust_2prize_via_boss`), Boss's NO está en mano pero SÍ en el mazo, `field_counts[Meowth_ex] < 2` con `_meowth_ld_free` y banca libre. Bajar Meowth busca el Boss's que remata (p.ej. a 1 premio de ganar, gustear un básico frágil que el activo noquea, en vez de atacar al activo que no muere). La condición era antes `field == 0`; el fix `< 2` + `_meowth_ld_free` permite la línea con un Meowth viejo ya en banca.
4. **Motor Boss's de VALOR (deny-evo) vía Meowth → `22000`**: `_deny_evo_via_boss` (pre-evo de línea ex ENERGIZADA en la banca rival, noqueable tras gustearla — Gabite/Duraludon/Morgrem…), Boss's en el mazo (no en mano), `field < 2` + `_meowth_ld_free`, banca libre y Supporter sin jugar. La maquinaria in-hand (`_boss_deny_evo`) exige Boss's en mano; sin esta rama no había camino y el agente atacaba al muro dejando evolucionar la amenaza. El fetch posterior elige Boss's a 1280 (doc 11). Con Boss's ya en mano no dispara (se juega directo sin gastar el cuerpo).
5. **Refresco de mano débil con Lillie's en el mazo → `21500`**: el activo ya es atacante listo (`_active_ready_attacker`), sin Meowth en juego, banca libre, Supporter sin jugar, Lillie's NI en mano NI perdida, mano ≤4, `_ready_attacker_count <= 2`, el ataque del activo NO es letal, sin Watchtower, y la **excepción de Froslass**: `not op_has_froslass or _ready_attacker_count <= 1` (Froslass veta salvo que el activo sea el único atacante listo y su ataque sea chip). El `21500` supera al cuerpo redundante (21000).
6. **Veto: activo listo sin condiciones de refresco** → `SCORE_VETO` (mejor desarrollar con Ultra Ball/Dawn o atacar).
7. **Veto: Lillie's YA en mano** → `SCORE_VETO` (el fetch es redundante y Lillie's barajaría la carta buscada). Si Lillie's está en el mazo, se deja pasar a `_meowth_devel_lillie`.
8. **Veto: BCS jugable + Lillie's en mano** → `SCORE_VETO`.
9. **`_meowth_devel_lillie` → `21800`**: Meowth en mano, Lillie's ni en mano ni descartada (en el mazo), sin Meowth en juego, banca libre — bajar Meowth para buscar Lillie's y jugarla el mismo turno.
10. **Veto: BCS jugable con banca ocupada** → `SCORE_VETO`.
11. **2º Meowth con activo atascado → `21700`**: exactamente 1 Meowth en juego, banca libre, `_active_cant_attack_this_turn`, Supporter sin jugar, Lillie's en el mazo, sin Froslass, no siendo el primer turno yendo primero.
12. **Vetos**: Meowth ya en juego; banca llena.
13. **Primer turno yendo primero**: solo con banca vacía y sin otros básicos jugables → `19000`; si no, veto.
14. **Turno 2 yendo segundo → `20500`**: sin Supporter jugado, mejor Supporter en mano `< 500` y mejor objetivo del mazo = Lillie's con valor `>= 650`.
15. **Supporter ya jugado** → veto (reforzado al final con `SCORE_FORBID`).
16. **Froslass rival — turno muerto → `21600`**: normalmente Froslass veta, pero si el activo no puede atacar NI retirarse, sin Meowth en juego, banca libre, Supporter sin jugar, sin Lillie's en mano y el motor (Lillie's o Lana's) en el MAZO, bajar Meowth es la única jugada útil.
17. **Turno muerto genérico → `21800`**: activo que no ataca, Supporter sin jugar, Lillie's en el mazo.
18. **Veto con Lillie's + Ultra Ball en mano** (banca ≥1, rival no Crustle/Drednaw/Sylveon, sin Boss's valioso en mazo): se prefiere Ultra Ball.
19. **Mejor Supporter en mano fuerte (≥500)**: solo se permite Meowth si busca un Boss's de alto valor vs Crustle/Drednaw/Sylveon (`21500`); si no, veto.
20. **Rama final por objetivo del mazo** (`_best_supp_in_mazo_id`/`_val`): Boss's ≥650 → `21000`; Lillie's ≥650 con `<= 2` atacantes listos (tabla `_ATK_REQS_MEOWTH`) y mano `< 4` → `20500`; Dawn ≥700 con Forest disponible → `20500`; Lana's ≥600 → `20000`; resto → veto.

### Fezandipiti ex

- `_fez_prefer_teal_lillie`: con Lillie's en mano, Supporter sin jugar, Ogerpon en mano (<2 en juego) y Planta en mano → veto (dejar ganar a Ogerpon 21000: Teal Dance + Lillie's rinde más que *Flip the Script*).
- Veto con copia en juego o banca llena.
- Vs Lucario/Crustle/Cornerstone/Sylveon: vale 2 premios y su habilidad solo sirve tras ser noqueado — con `ko_last_turn` → `22000` (`22500` con mano ≤3); si no, solo último recurso con banca vacía → `500`; resto veto.
- Turno 1 con banca de 1 → `15000`; si no, veto.
- Caso general: `22000`/`22500` con `ko_last_turn`; sin KO y banca ≤2, si toda la banca son básicos (`_all_bench_basics`) y el rival no es Lucario → `max(fez_score, 15000)`.

### Tapu Bulu

`_op_is_crustle_like` agrupa Crustle/Cornerstone/Sylveon/inmunidades. Reglas: veto con copia en juego; con ≥4 piezas en juego, Meganium y sin matchup Crustle-like → `16000`; con >2 cuerpos en juego fuera de Crustle → veto; Crustle → `22000` (`22500` con Meganium); habilidad-inmune/Cornerstone → `22500`; Sylveon → `22000`; inmune-a-ex → `21000` (`22000` con Hydrapple); `_lucario_sac_pivot` con banca libre y (`_tapu_sac_priority` o sin otro sacrificio) → `21500`; primeros 2 turnos o sin Meganium → veto; resto → `16000`. **Cierre transversal**: con ítems jugables aún en mano (`DECK_ITEM_IDS`), se rebaja a `TAPU_WAIT_FOR_ITEMS_SCORE` (`8900`) — los ítems útiles se juegan antes.

### Pinsir

`SCORE_VETO` siempre (código latente: Pinsir ya no está en el mazo actual; solo el rescate anti-softlock podría bajarlo).

### Overrides transversales tras el `if/elif` de Pokémon

- **Objetivo pendiente de Poke Pad** (`_poke_pad_target_id`): si la carta es el objetivo buscado y el score quedó ≤0, se fuerza `21000`.
- **`_ub_meowth_pending` → `21000`**: una Ultra Ball previa **de este turno** eligió buscar Meowth ex; se baja SIEMPRE con `field < 2`, `_meowth_ld_free`, banca libre y **`not state.supporterPlayed`** (guard correcto: antes exigía `not _active_ready_attacker` y con el atacante listo se atacaba sin bajarlo, desperdiciando la Ultra Ball entera; con el Supporter ya jugado la Lillie's buscada no se podría jugar y se mantiene atacar).
- **Motor Xerosic con Meowth YA en mano → `min 21500`**: vs Alakazam, Supporter libre, mano rival ≥6 (Powerful Hand nos noquea el próximo turno), Xerosic NO en mano pero SÍ en el mazo, `field < 2` + `_meowth_ld_free`, banca libre — bajar el Meowth SIEMPRE (aunque el activo ataque): Last-Ditch busca el Xerosic, se juega (rival a 3 cartas) y después se ataca. El `21500` supera el rush de Applin con Forest (`21200`): con un solo slot de banca, bajar el Applin bloquearía el motor Xerosic para siempre. **Condición añadida** (log 88162677 paso 16 vs Alakazam, PERDIDA): `not _meowth_fetch_ya_en_mano` (doc 10) — el motor solo dispara si la habilidad va a usarse de verdad. En nuestro primer turno con DOS Lillie's en mano el motor bajaba el Meowth (y además eximía al veto genérico "Lillie's ya en mano" del blindaje final) y en el paso siguiente el prompt de Last-Ditch **rechazaba** el fetch: cuerpo de 2 premios regalado, la Lillie's jugada igual y cero valor. Los casos que justificaron el motor (registro_006 p76, registro_008 p85, registro_010 p147) tienen `_meowth_devel_lillie` en False — tablero ya desarrollado o sin Lillie's en mano —, así que siguen bajando el Meowth para cavar el Xerosic.
- **Matchup Cubchoo — lista blanca** (`_CUB_ALLOWED_PLAY`): solo una línea Hydrapple, una línea Meganium, hasta 2 Ogerpon ex y 1 Meowth ex (solo si `_cub_meowth_ok`: sin copia en juego y Lillie's buscable en el mazo). El resto → veto.
- **Reserva de banca vs Alakazam**: con exactamente UN slot libre (`bench_count == 4`), Meowth ex aún no en juego y un Xerosic aún en el MAZO, se vetan los cuerpos **redundantes** (duplicado de algo en juego, o Fezandipiti ex) para reservar el último slot a Meowth ex (que busca el Xerosic). Se permiten Meowth y las primeras copias de las líneas de ataque. Nunca choca con el rescate anti-softlock (que exige `bench_count == 0`).
- **`_lucario_riolu_gust`**: se veta CUALQUIER desarrollo de Pokémon para que Boss's Orders (tier 0) gane la jugada de gustear+noquear al Riolu. **Excepción** (user, registro_006 paso 91, episodio 88710543 vs Mega Lucario): Fezandipiti ex con *Flip the Script* viva (`ko_last_turn`, ninguno en juego, banca con hueco) queda EXENTO — bajarlo no consume el Supporter, así que el Boss's se juega igual después, y vetarlo cerraba un bloqueo circular con `cede_a_unfair_stamp` + `mano_con_pokemon_o_evo` que acababa barajando al mazo el cuerpo que la Ultra Ball ya había pagado (ver `main-09`).
- **`_ub_fez_pending` → `22000`**: hermano de `_ub_meowth_pending` para la cadena UB → Fezandipiti ex → *Flip the Script*. Si la Ultra Ball de este turno eligió buscar Fezandipiti ex (objetivo `fez_tras_ko`, que solo se elige con la habilidad viva), el cuerpo BAJA aunque otro veto de la rama lo haya matado: la búsqueda se pagó con dos descartes y el único motivo de cavarlo es cobrar el robo de 3 hoy. Va **después** de todos los vetos de la rama (son justo ellos los que contradicen una búsqueda ya pagada) y respeta los límites FÍSICOS: `ko_last_turn`, ninguna copia en juego y `bench_count < 5`.
- **`_ld_supp_comprometido` (Supporters, doc 15)**: el compromiso del *Last-Ditch* no vive en esta rama sino en el bloque final de `agent()`, **después** de todos los vetos de PLAY (son ellos los que contradicen una búsqueda ya pagada): sube el `PLAY` del Supporter buscado a `max(score, SCORE_LD_SUPP_COMPROMETIDO)` (8000) mientras el hueco siga libre. No veta al resto de `_SUPP_PLAY_IDS`: el piso ya supera su banda normal (Xerosic, el más alto, ~7300) y dejarlos vivos permite que un Supporter **decisivo** (>8000, p.ej. un Boss's ganador) se quede con el turno — medido, el veto costaba −0.67 puntos de winrate.
- **Rescate anti-softlock de banca vacía**: con `bench_count == 0` y score ≤0, un básico se fuerza a jugable (`80` si es ex propio, `150` si no). Excepción `_meowth_first_turn_hold`: en nuestro primer turno con Lillie's jugable, NO se fuerza Meowth (se juega Lillie's primero; si sigue sin banca, `supporterPlayed` rehabilita el rescate).
- **Sinergia Dipplin activo + Do the Wave escalable**: si el activo es Dipplin, puede atacar, y bajar UN básico más sube `20 × banca` (con debilidad/resistencia) de "no letal" a "letal", ese básico sube a `max(score, 21900)`.
- **Blindaje final de Meowth ex**: Watchtower → veto; `_meowth_played_this_turn` (comparado con `_field_at_turn_start`) → veto; ≥2 copias → veto; 1 copia con score no forzado → veto; **Lillie's en mano → veto** (única excepción `_mw_dev_exc`: primer turno partiendo primero, banca vacía, activo = básico solo distinto de Tapu Bulu **y donk proyectado** `_meowth_antidonk_now`; user, log 88461779: en el primer turno Meowth ex solo existe para traer la Lillie's que NO tenemos, así que el desarrollo por sí solo ya no levanta el veto — solo lo levanta la supervivencia); y **`state.supporterPlayed` → `SCORE_FORBID`** (el fetch es inútil; el veto normal −1 empataba con un ataque vetado y ganaba por índice; `SCORE_FORBID` cae por debajo de atacar y de END; única excepción preservada: rescate anti-softlock con banca vacía y score > 0).
- **Estrategia vs Comfey**: SOLO Ogerpon ex, máximo 2 (`22000`/veto); excepción de arranque sin ningún cuerpo ni Ogerpon accesible → starter Applin `21000` > Chikorita `20500` > cualquiera `20000`; resto veto. **Segunda excepción, `_cf_relevo_urgente`** (autopsia jul 2026): con la **banca vacía** —aunque el activo siga vivo, que es lo que `_cf_has_body` no distinguía— cualquier **Básico** entra en esa misma escalera. Con la banca a cero el siguiente KO es bench-out y se acabó la partida; y bajar un cuerpo de la **mano** no adelgaza el mazo ni una carta, que es lo único que la defensa anti-mill protege — "solo se baja Ogerpon ex" dice con QUÉ atacamos, no obliga a quedarse sin cuerpos. Mismo patrón que la excepción del contra-estadio en la whitelist de Entrenadores: una whitelist de matchup no puede vetar la carta que impide perder en el acto. Medido: el bench-out era el **82%** de las derrotas vs comfey (5.6% de las partidas, frente al 0.4-2% de los demás matchups), mediana en el turno 5; gate n=1500 **comfey +5.1** y **comfey_yveltal_nz +4.6** (≈5σ), espejo y controles dentro del ruido. Solo Básicos: una Fase 1/2 no se banquea.

## Detalle por bloque — Trainers/Estadio

Base `score = SCORE_ITEM_BASE` y `supporter_boost = 500` bajo `itchy_pollen_active` (jugar el Supporter antes de perder la ventana de ítems).

### `_score_forest_of_vitality_play`

Vetado en nuestro primer turno yendo primero, y en turno 2 yendo segundo sin estadio rival (con estadio rival distinto → `15000`). Veto si Forest ya está en juego. Con `neutralization_zone_active` (Watchtower): reemplazarlo vale `28000` (`29000` con Chikorita/Applin/Dipplin en juego). **Nuevo**: si `watchtower_in_play` y el **motor Meowth está vivo** (menos de 2 Meowth en juego y Meowth en mano o en el mazo) → `27000` — Watchtower apaga Last-Ditch Catch por completo; antes esta situación caía al `15000` genérico y perdía contra el desarrollo. Escalera resultante: Neutralization Zone 28000–29000 > Watchtower con motor Meowth 27000 > cadena evolutiva (`_evo_chain`, incluida `_meg_fetchable_fv`: Meganium buscable con Poke Pad/Ultra Ball en mano) 21900 (`22000` con estadio rival, `+200` vs fuego/agresivo/Beedrill) > reemplazo genérico 15000 > turnos ≤4 14000/15000 > tardío 8000.

### `_score_bug_catching_set_play`

`bcs_score = 10500` de partida (−100 si Ogerpon ya en banca con Planta en mano). Recorre `CARTAS_ACTIVAS_EN_MAZO` para contar Pokémon Planta, energía y objetivos de alto valor; calcula la probabilidad de encontrar algo útil en hasta 7 cartas (hipergeométrica manual) y ajusta (`+800/+500/+200/−300`), más bonos por piezas faltantes (`+600…+150`), `+300` si faltan Meganium Y Hydrapple, `+200` sin Planta en mano (con `SCORE_BELIEF_DIG_ENERGY = 250` extra si `_energy_starved_low_draw`). Si Poke Pad es jugable y el score supera 9000, se recorta a 9000 (búsqueda determinista antes que probabilística).

### `_score_ultra_ball_play` y el motor `_ub_engine_refresh_pivot`

El scorer es ahora un orquestador de tres fases: `_ub_derive_flags` (deriva `survival_mode`, `evolve_needs_search`, `evolve_now_search`, `developed_attacker_board`, tamaño de mano) → `_ub_score_before_overrides` (cortes duros, cancelaciones por coste, valoración del objetivo vía `_eval_ub_best_target`) → `_ub_terminal_overrides` (overrides terminales, siempre al final). Antes de todo:

- **Vs Comfey**: con 2 Ogerpon en juego, `SCORE_CANCEL` (la UB solo sirve para buscar Ogerpon).
- **`_ub_engine_refresh_pivot(ctx)` → `31450`**: motor UB→Meowth→Lillie's ANTES de gastar las energías de la mano. Condiciones: Supporter sin jugar; **≥2 Plantas en mano** (forraje barato para el descarte de la UB); sin Lillie's ni Meowth ya en mano; **banca ≤1** (subdesarrollada); Meowth y Lillie's en el MAZO; `field[Meowth] < 2`; y el activo **NO noquea al rival ni con el adjunte del turno** (daño vía `_attacker_base_damage` + `_our_effective_damage`). El caso que lo motivó: el agente adjuntaba una energía y usaba Ripening Charge con la otra, la mano quedaba en [UB, Boss's] y la Ultra Ball moría sin 2 cartas que descartar. Al disparar, arma el global **`_ub_engine_pivot_turn`** para que el FETCH de esta UB elija Meowth ex (1300, doc 11). El `31450` gana al adjunte manual (~31410) y a Ripening Charge sin pivote (30000), y queda bajo los pivotes de habilidad con KO/retirada (31500–31600); la capa de tiers lo **sube al tier ENERGY** (doc 15) para que ese duelo se resuelva por score.

- **`_alakazam_dig_xerosic_engine(ctx)` con Meowth fuera de la mano → `5950`**: cava Meowth ex con la UB para que su *Last-Ditch* traiga Xerosic (capar *Powerful Hand*). **Nunca en NUESTRO primer turno** (`_pp_es_t1`; user, log 88461779 paso 16 vs Alakazam, PERDIDA): la mano rival recién robada ya supera las 7 cartas, así que el motor armaba la cadena UB→Meowth→Xerosic en el turno 1 y gastaba Ultra Ball, un cuerpo de 2 premios y el turno entero para cavar una disrupción que ni siquiera es jugable (saliendo primeros el Supporter no se ofrece) mientras el tablero se quedaba sin desarrollar. En el primer turno Meowth ex existe **solo** para traer Lillie's.

Dentro de las fases: cortes de mano `<3` y banca llena sin `evolve_needs_search` (que excluye Hydrapple ex vs rivales inmunes a ex); cancelaciones por protección de recursos (`_ub_cancel_for_stamp` — cuenta las copias sobrantes de la propia UB como fodder —, `_ub_cancel_for_fez`, `_ub_cancel_for_lillie`, `_ub_cancel_for_meowth`); selección del objetivo con `_eval_ub_best_target` (forzado a ≥950/850 cuando la cadena Meowth→Lillie's está disponible); escalado del score (`>=900` → 12500; `>=700` → 12000; `>=500` → 11200; `>=300` → 10500), penalizaciones por pocos `safe_discards`, posposición a `4500` con Lillie's en mano salvo `evolve_now_search`, protección de Lillie's como coste forzado, **modo supervivencia** (`ub_score = 25000` con banca vacía y básico solo en el mazo), `−1500` si BCS también es jugable, restricciones de primer turno y la salvaguarda terminal de banca llena.

### `_score_night_stretcher_play`

Clasifica el descarte propio en básicos/evoluciones/energía y construye `best_recovery_value` como `max()` de decenas de escenarios (recuperar piezas de línea con Forest, energía para un atacante que la necesita, energía que convierte un Syrup Storm no-letal en letal → 950, tabla específica vs Crustle/Cornerstone con `op_kang_ko_target` → 960, priorizar carga de banca sobre Lillie's → 850). Score final: `>=900` → 11800; `>=800` → 11000; `>=700` → 10400; `>0` → 9800; veto con banca llena sin nada que evolucionar ni energía útil. La lista de "energía útil" que **exime** de ese corte incluye `_ns_e_activo_paga_retirada` (registro_014 paso 141 vs Alakazam): recuperar la Planta para que el **ACTIVO pague su coste de retirada** y suba a atacar un cuerpo de banca. Antes solo `_ns_activo_no_llega_al_coste` contemplaba la retirada, y **solo para la línea Meganium** (Chikorita/Bayleef/Meganium): con un Fezandipiti ex activo a 0 energías y un Hydrapple ex de banca listo devolvía `False`, así que la Night Stretcher se vetaba por banca llena y el turno moría sin atacar. La versión nueva es deck-agnóstica: se apoya en las banderas `ability_unlock_retreat_ko/attack` del ctx (`_grass_unlocks_active_retreat`, doc 02), que ya exigen que haya un atacante de banca real esperando, más `_ns_ruta_de_carga_hasta_el_activo` (que la Planta pueda llegar al activo: adjunte manual libre, o Ripening Charge, que adjunta a cualquiera). Override: `op_kang_ko_target` con Hydrapple recuperable → `34000`.

> **La energía que paga la retirada también tiene que PUNTUAR, no solo esquivar el veto** (user, registro_021 turno 21, log 88359220). `_ns_e_activo_paga_retirada` estaba cableado **únicamente** al corte de banca llena (`_ns_banca_llena_guardar`), nunca a `_ESC_NS_RECUPERACION` — que es la lista cuyo ARGMAX produce el score. Con la banca **no** llena el ARGMAX daba `0`, el scorer devolvía `SCORE_VETO` y el agente cerraba el turno con el remate en la mesa: activo bloqueado (Fezandipiti ex, 0 energías, coste 1), un atacante de banca YA listo que noquea, y la única Planta en el **descarte**. La cadena correcta es *Night Stretcher → Planta a la mano → adjuntar al ACTIVO → RETIRAR → promover al rematador → KO*, y su primer eslabón es inalcanzable desde el resto: `_attach_enable_retreat_ko` (41000) exige una Planta **en la mano**, que es justo lo que falta. Ahora el detector se parte en dos escenarios registrados: `_ns_e_retirada_letal` → **950** (el rematador de banca noquea; mismo tier que el resto de remates, el premio de hoy manda) y `_ns_e_retirada_chip` → **860** (solo chip, pero el activo no puede atacar de ninguna forma: mismo criterio que `_attach_enable_retreat_attack`). `_ns_e_activo_paga_retirada` queda como la unión de ambos y sigue alimentando el corte de banca llena, sin cambio de comportamiento allí. Los dos son **deck-agnósticos**: todo el trabajo lo hace `_grass_unlocks_active_retreat` (`RETREAT_COST`, `_can_attack_eff`, `_bench_attacker_can_ko` — ningún id de carta). Detalle importante del diagnóstico: con un Teal Mask Ogerpon ex en banca la jugada **ya salía bien por casualidad**, vía el escenario `energia_activo_sin_teal`, que no tiene nada que ver con la retirada; el fallo solo se ve con un rematador sin habilidad de carga (Tapu Bulu, Meganium, cualquier mazo). Tampoco lo cubrían `_ns_e_remate_via_promocion` (exige `len(act.energies) >= coste`, o sea que la retirada **ya** se pueda pagar) ni `_ns_e_activo_necesita` (pasa por `_ns_activo_no_llega_al_coste`, una tabla por carta que devuelve `False` para todo lo que no sea de las líneas Meganium/Hydrapple/Ogerpon/Tapu/Pinsir). Regresión: `tests/test_energia_para_la_retirada.py`.

> **`_ns_activo_no_llega_al_coste`, ahora deck-agnóstica.** La cadena de `if act.id == ...` que decidía si la energía recuperada seguía siendo útil **sobre el activo** devolvía `False` para cualquier carta fuera de las líneas Meganium/Hydrapple/Ogerpon/Tapu/Pinsir — es decir, para todo el mazo de cualquier otro `deck.csv`. Extraída a **`_ns_umbral_energia_util(card_id)`**, con tres niveles de más específico a más general:
> 1. **Tablas curadas.** `_NS_UMBRAL_POR_RETIRADA` (línea Meganium) usa el coste de **retirada**, no el de ataque: es estrategia, no dato de carta — a esos cuerpos no los queremos atacando (Chikorita nunca usa *Growl*, Meganium es el motor *Wild Growth*), los queremos pudiendo pivotar; por eso Meganium corta en 2 y no en 4. `_NS_UMBRAL_POR_ATAQUE` (atacantes reales) usa `ATTACK_ENERGY_REQ`.
> 2. **Resto de `_DECK_POKEMON_IDS` → `None`.** La configuración los conoce y los excluye **a propósito**: Meowth ex y Fezandipiti ex tienen ataque, pero son cuerpos de utilidad y regarles una energía suelta no hace progresar ningún plan. Cuando uno de ellos es el activo y hay un rematador en banca, la jugada no es cargarlo sino **retirarlo** (`_ns_e_retirada_letal/chip`, arriba).
> 3. **Cualquier otro id → `_coste_de_ataque_min`**, derivado de `card_table` → ids de ataque → `attack_table` (mínimo coste > 0; `None` si no se puede saber). Es la rama deck-agnóstica.
>
> `_can_attack_eff` se dejó **sin** generalizar deliberadamente: `ATTACK_ENERGY_REQ` no es un dato de carta sino la lista **curada** de «cuerpos con los que de verdad atacamos», y derivar el coste del dato convertiría a Meowth ex en atacante en la veintena de puntos del fichero que la consultan (rompiendo su veto duro en banca). Equivalencia verificada: **0 flips** sobre todos los Pokémon de `deck.csv` × 0..10 energías, contra una copia literal del código anterior usada como oráculo (`test_umbral_equivale_al_original_para_todo_el_mazo`).

### `_score_poke_pad_play`

`pp_score = 9800`; veto sin objetivos buscables. Turno inicial: Applin `12800` / Chikorita `12600` si faltan; `_pp_budew_dump` (Budew rival activo bloqueará ítems) permite además piezas de evolución a `12400`. Turnos siguientes: `_pp_can_evolve_this_turn` sube a `23000`/`22000`/`20000` según inmediatez; `13000` si `_lucario_sac_pivot` con Tapu Bulu buscable. Corte de banca llena vía `_pp_evolve_needs_search` (excluye la línea Dipplin→Hydrapple: Poke Pad no busca ex), salvo `_pp_budew_dump`.

### `_score_unfair_stamp_play`

**Veto nuevo**: con Lillie's en mano, mano rival ≤3 y Supporter sin jugar → `SCORE_VETO` (regla "Sello Injusto cede a Lillie's": con la mano rival ya corta, la disrupción aporta poco y refrescar la propia rinde más; son mutuamente excluyentes porque el Stamp baraja la propia mano). Después, score según lo que quede por hacer: `2000` con Pokémon/evolución jugable, `2500` solo ítems, `3000` solo energía/estadio, `7500` nada más que jugar. Bonos: `+300` turnos ≤4, `+200` ganando en premios, `+400` Alakazam, `+350` control/Slowking, `+300` Gardevoir, `+250` Zoroark, `+350` vs agresivos/Beedrill perdiendo.

### `_score_boss_orders_play`

Vetos previos: Supporter jugado; `ko_last_turn` con Unfair Stamp en mano; vs Alakazam con Dunsparce activo rival y nuestro activo sin atacar (mantener trabado al muro). Escalera (constantes `BOSS_SCORE_*`):

1. **`win_via_boss_gust` → `BOSS_SCORE_WIN_NOW` (20000)**: gusteo que GANA la partida con el activo — supera cualquier retirada/pivote (~6500–6600); antes se puntuaba como win_via_bench (5600) y el agente retiraba en vez de rematar.
2. **`gust_2prize_via_boss` → `BOSS_SCORE_GUST_2PRIZE` (6800)**: el activo ya noquea al activo rival (1 premio) pero un ex de banca rival (≥2 premios, p.ej. Mewtwo ex) también cae tras gustearlo — cobra 2 premios y elimina al atacante más difícil. Sobre retiradas/pivotes, bajo WIN_NOW.
3. `_boss_first_turn_cede` y `_boss_empty_gust` → `BOSS_SCORE_EMPTY_GUST` (20): ceder a Lillie's en nuestro primer turno, o cuando el gusteo no es ejecutable (activo sin atacar, sin remate/redirección/muro) con Lillie's en mano.
4. `_boss_cede_dig` → `BOSS_SCORE_EMPTY_GUST`: un gusteo de DESARROLLO (prize_rank) no tiene prioridad sobre Lillie's si no hay atacante real de banca listo (`has_ready_bench_attacker`, que nunca cuenta un Applin); se exceptúan todos los gusteos valiosos (win_via_bench, defensivo, dodge, pre-evo amenaza `boss_ko_threat_preevo`, línea Alakazam, muros).
5. Muro inmune con `_boss_val >= 900` → `BOSS_SCORE_WALL_GUST` (5500); `boss_dodge_redirect` → 5500; `boss_win_via_bench` → 5600; `boss_deny_alakazam_line` → `BOSS_SCORE_PRIZE_RANK_BASE` (5200); `boss_low_value_gust` → 1500; `boss_prize_rank >= 1` → `5200 + (8 − rank) × 20`; `boss_defensive_gust` → 1500; `_boss_val <= 0` → veto; fórmula genérica `2400 + _boss_val × 1.4`.

### `_score_xerosic_play`

Xerosic's Machinations (id 1197, en el mazo a costa de −1 Poké Pad): el rival descarta hasta quedarse con 3 cartas. Vetos: `supporterPlayed`; mano rival ya ≤3 (sin efecto — p.ej. tras un Unfair Stamp este mismo turno); `ko_last_turn` con Unfair Stamp en mano (el Stamp, que es Ítem y rebaraja NUESTRA mano, va primero).

- **Disparo temprano `_xr_lethal_proj`**: con mano rival 4–5 pero Alakazam YA activo y su Powerful Hand proyectado (`20 × (mano + 2)`, misma proyección que `_op_active_attack_damage_to`) noqueando a nuestro activo → jugar Xerosic ya, sin esperar el umbral de 6.
- **Vs Alakazam** (`op_hand_count >= 6` o `_xr_lethal_proj`): `XEROSIC_SCORE_ALAKAZAM` (5900) `+ min(300, 50 × (mano_rival − 4))` → ~6000–6200 con mano ≥6 (5900–5950 con el disparo temprano). Gana a Lillie's hydra-cargado (5800, que además barajaría el Xerosic) y queda bajo GUST_2PRIZE (6800) y los pivotes defensivos (~6500–6600). Cede (`XEROSIC_SCORE_LAST_RESORT`, 20) al gusteo letal de banca con Boss's en mano, y al desarrollo si no podemos atacar con mano propia ≤3 y Lillie's en mano.
- **Genérico**: mano rival ≥7 → `XEROSIC_SCORE_GENERIC` (3380) — disrupción real contra cualquier mazo, bajo los Supporters útiles (~3450+).
- Resto (mano rival 4–6 sin Alakazam): `XEROSIC_SCORE_LAST_RESORT` (20).

### `_score_lillie_determination_play`

Baraja la mano y roba 6 (u 8 con 6 premios). Precalcula `_ready_ex_attackers`, `_lillie_pending_evo` (evolución en mano cuya pre-evo está en juego — se perdería al barajar), `_lillie_evolve_now` (¿evolucionable ESTE turno? — pre-evo en `_field_at_turn_start` o Forest en juego) y `_hydra_active_charged` (Hydrapple ex activo con ≥2 efectivas).

Escalera de vetos y valores:

- **Vs Comfey**: solo se juega con mano ≥10 (devuelve cartas al mazo, esquiva el mill); con menos, veto.
- **`_hop_keep_boss`**: vs Hop **o** con `boss_ko_threat_preevo` (pre-evo amenaza gusteable, p.ej. Duraludon), con Boss's en mano y ≥2 atacantes listos → veto (Lillie's barajaría el Boss's; solo se juega si el activo es el único atacante).
- Mano ≥10 en turnos ≤2 (fuera de nuestro primer turno) → veto; `supporterPlayed` → veto; `ko_last_turn` + Unfair Stamp con mano rival >3 → veto.
- **Guard del último Xerosic (vs Alakazam)**: con Xerosic en mano, mano rival ≥4, sin Meowth en mano y sin forma de re-buscarlo (2 Meowth ya en juego o ninguno en el mazo) → veto — Lillie's barajaría el único acceso al cap de Powerful Hand justo antes de su pico; con mano rival ≥6 la escalera ya garantiza Xerosic (6000+) > Lillie's (5800), este veto cubre el hueco 4–5. Si el Xerosic es re-buscable, Lillie's sigue su curso.
- Vs Alakazam con Unfair Stamp en mano, ≥2 atacantes ex listos y mano rival >3 → veto.
- **Nuestro primer turno**: siempre `5000` (se juega al final del turno gracias a la capa de tiers).
- **`_hydra_active_charged` → `5800 + supporter_boost`**: prioridad sobre Boss's que no gana (~5600); excepciones `boss_win_via_bench` y `boss_dodge_redirect` con Boss's en mano (si el rival esquiva, potenciar Syrup Storm es inútil).
- Veto si Boss's en mano tiene gusteo ejecutable: `prize_rank >= 1` con activo que ataca **y** (`has_ready_bench_attacker` o `boss_ko_threat_preevo`), o win_via_bench, o dodge — un gusteo de desarrollo sin segundo atacante real NO veta (conviene cavar).
- Ogerpon + Planta en mano con banca libre → `4500` (preparar el atacante antes de refrescar).
- **`_lillie_pending_evo`** (turno >2, mano >4): si `_lillie_evolve_now` → veto (evolucionar primero); si NO se puede evolucionar ya, la rama solo se alcanza en turno muerto (`not (can_attack or _bdg_retreat_ko)`) → `5000` (refrescar supera conservar piezas que hoy no bajan). Las excepciones de mano ≤4 y de "vamos a atacar" (`can_attack`/`_bdg_retreat_ko`) evitan entrar al veto.
- Mano ≤6 → `5000`. Mano >6: `5000` salvo el chequeo fino `_has_pending_evolutions`/`_can_evolve_now` que veta solo si no se puede evolucionar ya, no es turno ≤2, no hay Lana's alternativa y la mano tiene <7 cartas.

### Dawn

Veto con Supporter jugado o `ko_last_turn`+Stamp; si no, `SCORE_SUPPORTER_VALUE_BASE + _dawn_val × 1.4 + supporter_boost` (veto si `_dawn_val <= 0`).

### `_score_lanas_aid_play`

Misma fórmula base con vetos idénticos, más: **vs Comfey** solo se juega si recupera ≥2 energías del descarte (los Ogerpon son Rule Box, Lana's no los recupera). Ajustes: con línea Meganium activa, sin Planta en mano ni adjuntada y energía recuperable → `max(score, 4500)`; y si el activo no puede atacar, Lillie's está en mano sin jugar y la recuperación NO habilita un ataque (`_supp_values['_lana_enables_attack']` falso) → `min(score, 2000)` (cede a Lillie's pero sigue jugable por si Lillie's está vetada).

### Veto vs Comfey para Trainers

Con `op_is_comfey_deck`, solo se juegan Lillie's, Lana's, Boss's, Ultra Ball y Night Stretcher; cualquier otro Trainer/Estadio con score positivo → veto.

## Interacciones

- **Con la escalera de Boss's (doc 08)**: `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_deny_evo_via_boss`, `boss_win_via_bench`, `boss_dodge_redirect`, `boss_ko_threat_preevo`, `boss_deny_alakazam_line` y `_boss_prize_rank` se calculan antes del bucle; aquí se traducen a score para Boss's y condicionan cuándo Meowth sale a buscarlo (ramas 22500/22000) o cuándo Lillie's cede.
- **Con el plan de ataque (doc 07)**: `plan.attacker`/`plan.remain_hp`, `can_attack`, `_bdg_retreat_ko` y `_active_cant_attack_this_turn` vetan refrescos que competirían con rematar.
- **Con el matchup (doc 06)**: casi todos los bloques cambian con `op_is_*_deck`/`op_has_*`; la inferencia por descarte rival adelanta esos flags.
- **Con la búsqueda (doc 11)**: Ultra Ball/Poke Pad/BCS/Night Stretcher solo deciden SI se juegan aquí; QUÉ buscan se resuelve en `TO_HAND` con `_eval_ub_best_target` y `_supp_values`. `_ub_engine_pivot_turn` conecta el PLAY (31450) con el fetch (Meowth 1300).
- **Con el orden por tiers (doc 15)**: la Ultra Ball con score >31000 se promueve al tier ENERGY; los vetos (≤0) nunca se promueven.
- **Con `ATTACH`/`ABILITY` (doc 13)**: las bandas 21000–22500 de Pokémon están calibradas contra las de Teal Dance/Ripening (29000–31600) y el adjunte (8000–42000).

## Reglas derivadas de partidas

- Refresco de mano débil de Meowth (21500) y su excepción de Froslass: tres derrotas (vs Archaludon ex, Mega Starmie ex, Marnie's Grimmsnarl ex).
- Veto de Meowth con activo listo sin condiciones (vs Mega Abomasnow ex, PERDIDA).
- `SCORE_FORBID` con Supporter jugado (vs Abomasnow, PERDIDA: el veto −1 empataba con el ataque vetado y ganaba por índice).
- Motor Boss's ganador vía Meowth con `field < 2` + `_meowth_ld_free` (vs Dragapult ex, GANADA).
- `_ub_meowth_pending` con guard `not supporterPlayed` (vs Hop's, GANADA; contraejemplo vs Alakazam con Supporter jugado).
- Motor Xerosic in-hand a 21500 sobre el rush de Applin (vs Alakazam, PERDIDA: el agente bajó el Applin y los dos Meowth murieron en mano).
- `_ub_engine_refresh_pivot` a 31450 + fetch 1300 (vs Archaludon ex, PERDIDA: la UB moría sin fodder tras gastar las energías).
- Boss's WIN_NOW 20000 sobre el pivote de retirada (vs Dragapult, GANADA) y GUST_2PRIZE 6800 (vs Team Rocket Mewtwo ex, GANADA).
- Guard del último Xerosic en Lillie's y disparo temprano `_xr_lethal_proj` (auditoría anti-Alakazam).
- `_hop_keep_boss` generalizado a `boss_ko_threat_preevo` (vs Archaludon, GANADA).
- Watchtower + motor Meowth vivo → Forest 27000 (auditoría julio 2026).
