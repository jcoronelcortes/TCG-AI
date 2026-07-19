# main.py — Valoración de Supporters y banderas de decisión (líneas 3595–4489)

## Rol en el agente

Este tramo cierra la función interna `evaluate_supporters()` (definida desde la línea 2858, documentada en parte por `main-08-agent-boss-orders.md` para la escalera de `Boss's Orders`) fijando los umbrales de **`Lillie's Determination`**, **`Dawn`** y **`Lana's Aid`** en el diccionario `values` que después se usará como referencia (`_supp_values`) para puntuar la opción `PLAY` de cada Supporter en el bucle principal. A partir de la línea 3822 (`_supp_values = evaluate_supporters()`), el código ya no calcula valores de Supporter sino que deriva de ellos —y de otras condiciones del tablero— una batería de **banderas booleanas de una sola letra en minúscula con guion bajo** (`_win_via_boss_gust`, `_meowth_devel_lillie`, `_ctm_*`, `_active_already_kos`, etc.) que actúan como *pre-cómputo* de decisiones tácticas. Estas banderas no puntúan nada por sí mismas: se consultan más adelante (bloques PLAY ~8684–11008, ATTACH/EVOLVE/ABILITY ~11008–11608, RETREAT ~11608–12609) para vetar, forzar o re-priorizar opciones concretas — por ejemplo, evitar bajar `Meowth ex` cuando ya sobran atacantes listos, o forzar la promoción de `Tapu Bulu` cargado contra Crustle.

El hilo conductor de todo el tramo es evitar que el agente, que puntúa opción por opción sin planificación explícita, cometa dos errores típicos de una heurística miope: (a) gastar el Supporter equivocado (p. ej. `Boss's Orders` en un gusteo que no aporta premio, o `Lillie's Determination` cuando ya tenemos jugadas mejores) y (b) bajar un Pokémon de utilidad (`Meowth ex`) en vez de atacar cuando ya hay con qué ganar el turno. Varias reglas citan explícitamente el `log` de una partida real que motivó el ajuste, señal de que son parches dirigidos a errores observados, no diseño a priori.

## Detalle por bloque

### `_remaining_plays`: jugadas de desarrollo pendientes (líneas 3618–3634)

Cuenta cuántas jugadas de desarrollo (no ataque) quedan disponibles este turno: adjuntar energía (si hay `Basic_Grass_Energy` en mano y `not state.energyAttached`), bajar un básico nuevo (`Chikorita`, `Applin`, `Teal_Mask_Ogerpon_ex`) si `bench_count < 5`, o evolucionar (`Meganium` sobre `Bayleef`, `Bayleef` sobre `Chikorita`, `Hydrapple_ex` sobre `Dipplin`, `Dipplin` sobre `Applin`). Es un proxy de "cuánto nos queda por hacer con la mano actual"; se usa después para decidir si conviene ya refrescar la mano con `Lillie's Determination` en vez de seguir desarrollando.

### Escalón base de `Lillie's Determination` (líneas 3636–3649)

```python
if my_prize == 6:
    values[Lillie_Determination] = 750
    if hand_size <= 3:
        values[Lillie_Determination] = 800
elif hand_size <= 2:
    values[Lillie_Determination] = 800
elif hand_size <= 3:
    values[Lillie_Determination] = 700
elif _remaining_plays <= 1:
    values[Lillie_Determination] = 650
elif hand_size <= 5:
    values[Lillie_Determination] = 550
else:
    values[Lillie_Determination] = 400
```
Escala de prioridad decreciente según el tamaño de mano y las jugadas pendientes: mano muy pequeña (≤2–3) o partida recién empezada con 6 premios intactos (`my_prize == 6`, condición prioritaria sobre el resto) sube el valor a 750–800; si aún quedan ≥2 jugadas de desarrollo con mano razonable (4–5 cartas) el valor baja a 550; con mano grande (>5) y jugadas de sobra, 400 (bajo, porque refrescar desperdiciaría cartas útiles). La razón es que `Lillie's Determination` baraja la mano entera y roba, así que solo compensa cuando la mano es pobre en opciones.

### Penalización vs Alakazam con mano cargada (líneas 3651–3655)

Si `op_is_alakazam_deck` y `hand_size >= 4`, se limita `Lillie's Determination` a un máximo de 450 (y a 300 si además `_remaining_plays >= 2`). Contra mazos Alakazam interesa **conservar** las cartas de la mano (recursos de banco/gusteo) en vez de barajarlas, así que se recorta el valor incluso si el escalón base lo habría subido más.

### Combo `Dawn` + `Lillie's Determination` ambas en mano (líneas 3657–3667)

Cuando ambas cartas están en mano y no se cumple `meganium_in_play and has_hydrapple` (es decir, aún falta desarrollar alguna de las dos líneas de ataque principales), se prioriza una sobre otra según haya `Forest of Vitality` en juego: con `forest_in_play`, `Dawn` sube por encima de `Lillie's` (`+50`) porque Forest ya acelera la energía y Dawn puede traer los Pokémon que faltan; sin estadio, es `Lillie's` la que sube por encima de `Dawn` (`+50`) para priorizar el refresco de mano. En ambos casos se usa `max()` para no bajar un valor ya alto por otra regla.

### Valoración de `Lana's Aid` (líneas 3669–3705)

Recorre `my_state.discard` contando `discard_basic_energy` (copias de `Basic_Grass_Energy`) y `discard_basic_pokemon` (básicos recuperables: `Chikorita`, `Applin`, `Teal_Mask_Ogerpon_ex`, `Tapu_Bulu`, `Meowth_ex`, `Fezandipiti_ex`, `Pinsir`). Si `total_recoverable >= 1`:
- Base `lana_val = 300`.
- Bonus por banca vacía/casi vacía: `+400` si `bench_count <= 1`, `+200` si `bench_count <= 2` (recuperar básicos es más urgente con poca banca).
- `+350` si hay un `Chikorita` recuperable y **ninguna** copia de la línea Chikorita/Bayleef/Meganium en juego (`field_counts[...] == 0`), i.e. hace falta reconstruir la línea desde cero.
- `+300` análogo para `Applin` y la línea Applin/Dipplin/Hydrapple_ex.
- `+200` si `Teal_Mask_Ogerpon_ex` es recuperable y hay menos de 2 copias en juego.
- `+200` si `forest_in_play` y hay `Chikorita` o `Applin` recuperables (Forest acelera esas líneas, así que vale la pena traerlas de vuelta).
- `+150` si `total_recoverable >= 3` (mucho que recuperar de una sola vez).
- Bonus específico vs Crustle (`op_is_crustle_deck`): `+350` si `Tapu_Bulu` es recuperable y no hay copia en juego (es el mejor atacante no-ex contra Crustle); `+200` si `Applin` es recuperable y la línea Applin/Dipplin está vacía en juego.

### `_lana_energy_enables_attack`: Lana's como habilitador de ataque (líneas 3706–3743)

Bandera especial que detecta el caso en que `Lana's Aid` **no solo recupera recursos sino que habilita un ataque este mismo turno** — el único motivo para anteponerla a `Lillie's Determination` cuando no hay atacante listo. Condiciones previas: hay energía básica en el descarte (`discard_basic_energy >= 1`), no hay energía básica en mano (`hand_counts.get(Basic_Grass_Energy, 0) == 0`, si no se preferiría el adjunte normal) y hay un Pokémon activo. Dos ramas:
- **Activo es `Hydrapple_ex`**: calcula cuántas energías puede recuperar y adjuntar este turno (`_la_slots`, tope de 2: adjunte manual + el propio Lana's, acotado también por `discard_basic_energy`) y comprueba si eso cruza el umbral de 2 energía efectiva necesaria para atacar (`_la_cur_eff < 2 and _la_eff_after >= 2`).
- **Activo distinto pero hay `can_switch or has_switch_card`**: busca en la banca el `Hydrapple_ex` con más energía (`_la_bench_hydra`) y aplica la misma comprobación, asumiendo que se le puede promover.

Si `_lana_energy_enables_attack` es `True`, `lana_val = max(lana_val, 950)` — prioridad casi máxima, por encima de casi cualquier otro Supporter. El valor se expone también como `values['_lana_enables_attack']` (línea 3743) para que la capa de puntuación de `PLAY` (línea ~11005, documentada en `main-12`) distinga este caso concreto al comparar `Lana's Aid` contra `Lillie's Determination`.

### Turno 2 en segunda posición: `Lillie's Determination` forzada (líneas 3745–3749)

Si `state.turn == 2 and not we_go_first` (nuestro primer turno real jugando en segunda posición), se fija `values[Lillie_Determination] = 1000` (máxima prioridad posible en esta función) y se recortan `Boss_Orders`, `Dawn` y `Lana's Aid` a un tope de 200. La razón: en el turno de apertura conviene refrescar la mano inicial en vez de gastar otros Supporters, que normalmente no tienen objetivo útil todavía (banca rival vacía o mínima).

### Mano inicial demasiado grande: veto de `Lillie's Determination` (líneas 3751–3752)

Si `state.turn <= 2 and hand_size >= 10`, se pone `values[Lillie_Determination] = -1` (veto). Con una mano así de grande (post-mulligan largo) no tiene sentido barajarla de vuelta.

### `Dawn` de emergencia tras un KO propio (líneas 3754–3766)

Si hubo un KO propio el turno anterior (`ko_last_turn`) y la mano tiene `Dawn` pero **no** tiene `Lillie's Determination`, `Meowth_ex` ni `Ultra_Ball`, y no hay `Fezandipiti_ex` en juego pero sí quedan copias en el mazo (`CARTAS_ACTIVAS_EN_MAZO[Fezandipiti_ex][ESTADO_MAZO] > 0`), y hay hueco en banca (`bench_count < 5`): se fuerza `values[Dawn] = 1100` (por encima incluso del escalón base de `Lillie's`) y se recortan `Boss_Orders`/`Lana's Aid` a 200. Escenario: acabamos de perder un Pokémon y no tenemos ninguna otra herramienta de recuperación de mano/tablero en la mano actual salvo `Dawn`, así que se prioriza reconstruir el tablero (Dawn busca hasta 3 Pokémon) sobre cualquier otra jugada de Supporter.

### Veto de `Boss's Orders` sin objetivo distinguible en banca (líneas 3768–3779)

Si `values[Boss_Orders] > 0` ya fue fijado por la escalera previa (doc `main-08`), se recorre la banca rival buscando algún Pokémon **distinto** del activo (`_bo_has_distinct_target`: id diferente o mismo id con distinta cantidad de energía). Si no hay ninguno, `values[Boss_Orders] = 0`: gustear no tendría sentido porque el "nuevo" activo sería equivalente al que ya tenemos delante (mismo cuerpo, mismo estado de energía).

### Veto de `Boss's Orders` vs Crustle sin condiciones (líneas 3781–3790)

Solo contra `op_is_crustle_deck` con `values[Boss_Orders] > 0`: exige que el activo rival sea una forma de Crustle/Dwebble (`_cru_act_ok`) y que exista algún Pokémon en banca rival que **no** sea `Dwebble` (`_cru_has_nondwebble_bench`). Si falta cualquiera de las dos condiciones, se anula el valor (`= 0`). Motivo: contra Crustle interesa reservar `Boss's Orders` para objetivos de verdad relevantes, no gastar el supporter con un `Dwebble` de banca como único destino.

### `Dawn` con banca llena vs Alakazam: solo si falta una evolución (líneas 3792–3818)

Comentario largo en el propio código explica la lógica: con `op_is_alakazam_deck` y `bench_count >= 5`, jugar `Dawn` solo tiene sentido si de verdad falta una evolución alcanzable. Se define el mapa `_ALK_DAWN_EVO = {Chikorita: Bayleef, Bayleef: Meganium, Applin: Dipplin, Dipplin: Hydrapple_ex}` y se marca `_alk_dawn_need_evo = True` si para algún par `(lo, hi)` tenemos `lo` en juego, `hi` **no** en mano y `hi` sigue disponible en el mazo. Si ninguna evolución hace falta, `values[Dawn] = 0`. Razón explícita en el comentario: con banca llena no se pueden bajar básicos nuevos, así que `Dawn` solo "adelgaza" el mazo (roba/descarta) sin aportar cuerpos jugables — y arriesga quedarse sin cartas para robar (deckout).

Con esto termina `evaluate_supporters()` (`return values`, línea 3820) y se invoca en `_supp_values = evaluate_supporters()` (línea 3822).

### `_best_supp_in_hand_val` / `_best_supp_in_hand_id` (líneas 3824–3829)

Recorre los cuatro Supporters (`Boss_Orders`, `Dawn`, `Lillie_Determination`, `Lanas_Aid`) y, de los que están físicamente en mano (`hand_counts.get(sid, 0) >= 1`), se queda con el de mayor valor en `_supp_values`. Sirve de referencia rápida para saber "cuál es el mejor Supporter jugable ahora mismo" sin repetir el recorrido en cada rama posterior.

### `_boss_prize_rank`: mejor objetivo de gusteo por rareza/premio (líneas 3831–3898)

Solo se calcula en `context == SelectContext.MAIN` con `Boss_Orders` en mano y activo rival presente. Define `_bpr_active_can_ko(_tgt)` (líneas 3845–3859): calcula si el activo propio, con el posible adjunte de energía de este turno (`_bpr_attach`), puede noquear a `_tgt` usando `_attacker_base_damage` + `_our_effective_damage`.

Después recorre la banca rival (`op_state.bench`) y para cada objetivo válido:
- Se **descarta** `Dwebble_Grass`/`Dwebble_Fighting` si `op_is_crustle_deck` (comentario cita `log 86339758 paso 98`: Dwebble no debe contar en el ranking de premios de Boss's).
- Asigna un `_bpr_base` de "rareza inversa" según el tipo de carta: `megaEx` → 1 (máxima prioridad, cuesta menos rank = mejor), `ex` → 3, `stage2` → 5, `stage1` → 7, o si está en `THREAT_PREEVO_IDS` → 7 también (pre-evoluciones-amenaza tratadas como stage1). Otros tipos (básico común) quedan sin `_bpr_base` y se saltan (`continue`).
- Comprueba si el objetivo es noqueable, primero con el activo actual (`_bpr_active_can_ko`) y si no con algún atacante de banca (`_bench_attacker_can_ko`, solo si `can_switch`).
- Si es noqueable, `_bpr_rank = _bpr_base + (0 if len(energies)>=1 else 1)` (penaliza levemente los objetivos sin energía adjunta, probablemente por ser menos "urgentes" de eliminar ahora) y se guarda el mínimo (`_boss_prize_rank`) entre todos los objetivos válidos — **menor rank = objetivo más valioso** (mega/ex antes que stage1/pre-evo amenaza).

Justo después (líneas 3897–3898), si `_bo_active_attack_sufficient` (bandera de la escalera de Boss's, doc `main-08`) o `_supp_values.get('_active_attack_sufficient')` es verdadero —el activo ya tiene ataque suficiente sin necesidad de gustear—, se resetea `_boss_prize_rank = 0`: no hace falta cazar premio con Boss's si ya se gana el intercambio con el activo tal cual.

### `_lucario_riolu_gust`: cortar la línea de Mega Lucario ex (líneas 3900–3921)

Bandera muy específica de matchup, motivada por `log 86023830, paso 69` (comentario extenso en el código). Contra `op_is_lucario_deck`, si no se ha jugado Supporter (`not state.supporterPlayed`), hay `Boss_Orders` en mano, banca propia establecida (`bench_count >= 2`), `_supp_values.get('_boss_deny_evo')` es verdadero (ya hay una pre-evolución ex gusteable-y-noqueable identificada por la escalera de Boss's) y hay un `Riolu` en la banca rival, se activa `_lucario_riolu_gust = True`. Su efecto (documentado también en el comentario, se aplica en línea 9214, fuera de este tramo): **veta las jugadas de desarrollo** (tier DEVELOP, p. ej. `Meowth ex`, `Chikorita`, `Tapu...`) para forzar que `Boss's Orders` sobre el `Riolu` sea la jugada elegida, cortando la línea del atacante principal rival antes de que evolucione.

### `_boss_win_via_bench` / `_boss_dodge_redirect` (líneas 3923–3925)

Simples "reexportaciones" a variable local de flags ya calculadas dentro de `evaluate_supporters()` (`values['_boss_win_via_bench']` en línea 3175, `values['_boss_dodge_redirect']` en líneas 3293/3296 — ambas parte de la escalera de Boss's del documento `main-08`). Se extraen aquí como `bool(_supp_values.get(...))` para poder consultarlas directamente sin re-indexar el diccionario en el resto de `agent()`.

### `_best_supp_in_mazo_val` / `_best_supp_in_mazo_id` (líneas 3927–3934)

Análogo a `_best_supp_in_hand_id` pero para Supporters que **aún están en el mazo** (`CARTAS_ACTIVAS_EN_MAZO[sid][ESTADO_MAZO] > 0`), no en mano. Identifica cuál sería el mejor Supporter a buscar si se juega una carta de búsqueda (p. ej. `Ultra Ball`, `Poke Pad`, o la Habilidad de `Meowth ex`). Se usa después en el bucle de búsqueda de cartas (líneas ~8930–8971, doc `main-11`) para decidir el objetivo de un fetch.

### `_gust_2prize_via_boss` y `_win_via_boss_gust`: gusteo que gana el intercambio de premios (líneas 3936–4015)

Bloque protegido por una condición amplia: no se ha jugado Supporter, hay activo propio y rival, el rival tiene banca, y `Boss_Orders` está disponible (en mano o localizable en el mazo). Define `_mbw_dmg_to(_tgt)` (líneas 3948–3977): calcula el daño del activo propio a un objetivo dado usando `_attacker_base_damage` con el posible adjunte de este turno, aplicando manualmente debilidad/resistencia a Planta (salvo con `Fezandipiti_ex`, cuyo ataque no es de tipo Planta), inmunidad ex (`EX_IMMUNE_IDS`), inmunidad a habilidad (`ABILITY_IMMUNE_IDS`) y el tope especial de `Drednaw` (`_d >= 200` → 0 daño). Es una réplica *inline* de la lógica de daño ya vista en la escalera de Boss's (mismo patrón que en líneas 3452–3489), pero sin zona de neutralización ni el tope específico de Crustle a plena vida (el comentario en línea 3956 lo aclara explícitamente).

Con esa función:
- `_mbw_act_ko`: ¿el activo rival muere este turno sin gustear?
- `_mbw_act_wins`: además, ¿noquearlo ya sería un intercambio de premios favorable (`my_prize <= prize_count(_mbw_act)`)? Si es así, no hace falta gustear (el resto del bloque se salta).
- Si no gana ya, recorre la banca rival (vetando `Dwebble` vs Crustle, de nuevo citando `log 86339758 paso 98`) buscando un objetivo noqueable **y** que gane el intercambio de premios (`my_prize <= prize_count(_mbw_bp)`) → `_win_via_boss_gust = True`.
- Además calcula `_mbw_best_bench_prize` (el mejor valor en premios de cualquier objetivo de banca noqueable, sin exigir que "gane") y compara contra `_mbw_act_prize` (premios del activo, si es noqueable) y contra `_mbw_trade_down` (si noquear el activo directamente sería *peor* trato en premios que gustear a la banca). Si `_mbw_best_bench_prize >= 2` y supera a `_mbw_act_prize` y no hay `_mbw_trade_down`, se marca `_gust_2prize_via_boss = True`: gustear un objetivo de banca de 2 premios es mejor que noquear el activo (que valdría menos).

### `_bdg_retreat_ko`: ¿un atacante de banca ya noquea sin gustear? (líneas 4017–4031)

Si `can_switch` y hay activos en ambos bandos, calcula el coste de retirada real del activo propio (`0` si `has_switch_card`, si no `RETREAT_COST` menos el descuento por `_retreat_cards`), la energía Planta restante tras retirarse (`_bdg_grass_after`) y llama a `_bench_attacker_can_ko` para ver si, retirando y promoviendo, algún atacante de banca noquea al activo rival este turno. Es la comprobación que falta en `can_attack` (que solo mira el activo actual, no la opción de retirada).

### Veto de `_boss_prize_rank` cuando retirar+promover ya noquea (líneas 4033–4046)

Motivado por `log 85804848, paso 49` (vs Alakazam, partida **perdida**, según el comentario). Si `_bdg_retreat_ko` es verdadero, hay `Lillie's Determination` en mano, y no aplican los casos "de verdad valiosos" (`_win_via_boss_gust`, `_gust_2prize_via_boss`), se anula `_boss_prize_rank = 0`. Razón: si ya hay forma de noquear al activo rival sin gastar `Boss's Orders` (retirando y promoviendo un atacante de banca), gustear a la banca solo para "cobrar premio" es redundante — mejor refrescar la mano con `Lillie's Determination`. Los gusteos realmente valiosos (letal directo, intercambio de 2 premios) siguen puntuándose por sus propias banderas, no por `_boss_prize_rank`.

### `_boss_defensive_gust`: gusteo puramente defensivo vs Crustle (líneas 4048–4066)

Exclusivo de `op_is_crustle_deck`. Se activa cuando no se ha jugado Supporter, **no podemos atacar este turno** (`not can_attack`), no aplican `_bdg_retreat_ko` ni `_conf_should_retreat` (retirada por confusión) ni los gusteos ya valiosos (`_win_via_boss_gust`, `_gust_2prize_via_boss`), hay `Boss_Orders` en mano, el activo rival tiene al menos 1 energía adjunta y hay banca rival. Recorre la banca rival calculando, para cada Pokémon, `_bdg_rc - _bdg_e` (coste de retirada menos energía actual) contra un `_bdg_threshold` (1 si el activo rival no tiene coste de retirada, si no 2). Si algún objetivo de banca supera el umbral (está "atascado", no puede retirarse fácilmente), se marca `_boss_defensive_gust = True`. La idea: aunque no podamos atacar, gustear un Pokémon rival atascado en banca lo deja indefenso como nuevo activo, ganando tiempo mientras nuestro lado se recupera.

### `_meowth_devel_lillie`: motor Meowth ex → Lillie's Determination (líneas 4068–4081)

Bandera central del "refresco de mano" del mazo. Condiciones: no se ha jugado Supporter, tenemos `Meowth_ex` en mano o en juego, y `Lillie's Determination` está disponible (en mano o localizable en el mazo vía `CARTAS_ACTIVAS_EN_MAZO`). Calcula `_mdl_in_play`: cuántos Pokémon **distintos de `Meowth_ex`** hay ya en juego (activo + banca) — es decir, cuánto se ha desarrollado ya el tablero. Define un tope dinámico `_mdl_max_in_play = 4 if _mdl_hand_size <= 2 else 3` (con mano de 1–2 cartas se permite un tablero algo más desarrollado antes de renunciar al combo, porque hay poco más que jugar de todas formas). Si `_mdl_in_play <= _mdl_max_in_play`, se activa `_meowth_devel_lillie = True`.

Esta bandera es la que, aguas abajo (líneas 8027, 8887 en el bucle de búsqueda; 8817/8856 en `PLAY`, doc `main-11`/`main-12`), autoriza que la Habilidad de `Meowth ex` (*Last-Ditch Catch*) busque específicamente `Lillie's Determination` en vez de otro Supporter, y que bajar `Meowth ex` compita como jugada válida de desarrollo — siempre que el tablero no esté ya "lleno" de cuerpos jugados, en cuyo caso Meowth ex sería un cuerpo redundante de 2 premios en vez de una herramienta de refresco.

### `_active_ready_attacker` (líneas 4083–4091)

`True` si el Pokémon activo está en `MAIN_ATTACKERS` (`Hydrapple_ex`, `Dipplin`, `Teal_Mask_Ogerpon_ex`, `Tapu_Bulu`, `Fezandipiti_ex`, `Meganium`, `Pinsir`) y tiene energía efectiva suficiente para atacar ya (`_can_attack_eff`), además de `can_attack` general. Se usa para no malgastar jugadas de desarrollo (bajar `Meowth ex`, etc.) cuando el activo ya está listo para pegar — no haría falta "hacer tiempo" con un cuerpo de utilidad si ya se puede atacar.

### `_ready_attacker_count` (líneas 4093–4100)

Igual que `_active_ready_attacker` pero contando **todos** los atacantes listos (activo + banca) con energía suficiente para atacar ya (`_can_attack_eff`). Sirve como medida de "sobreabundancia de atacantes": si ya hay 2+ listos, refrescar la mano con Meowth ex → Lillie's aporta menos porque no hace falta desarrollar más ofensiva, y las ramas de `PLAY` (líneas 8825/8831, doc `main-12`) usan este conteo (`<= 2`, `<= 1`) para graduar esa prioridad.

### Banderas anti-Crustle `_ctm_*` (líneas 4102–4194)

Grupo de banderas y de un **override directo del `plan`** (el `AttackPlan` global), aplicable solo contra `op_is_crustle_deck`:

- **`_ctm_dipplin_low` / `_ctm_tapu_high` / `_ctm_tapu_ready`** (líneas 4102–4128): solo se calculan si el activo rival es una forma de Crustle y las tres piezas clave (`Dipplin`, `Tapu_Bulu`, `Meganium`) están en juego (`_ctm_all_in_play`). Se busca `Tapu_Bulu` cargado (activo o banca, `_can_attack_eff`) → `_ctm_tapu_ready`. Si está listo, `_ctm_tapu_high = True` (siempre priorizarlo, es el mejor atacante no-ex contra Crustle con 220 de daño). Si no está listo: si el Crustle activo tiene ≤2 energías, se prioriza cargar `Dipplin` (`_ctm_dipplin_low`, aprovechando que su daño escala con el tamaño de banca rival mientras Crustle está débil); si tiene más energía, se mantiene la prioridad en `Tapu_Bulu` (`_ctm_tapu_high`) aunque no esté listo todavía, para no dispersar recursos.
- **`_ctm_chikorita_bench` / `_ctm_applin_bench`** (líneas 4130–4138): simples comprobaciones de si hay algún miembro de la línea Chikorita o Applin en banca propia, usadas más adelante (doc `main-10`, líneas ~5150–5176) para decidir prioridades de adjunte de energía.
- **`_ctm_charge_active_dipplin`** (líneas 4140–4152): solo si `Tapu_Bulu` no está listo (`not _ctm_tapu_ready`). Si el activo propio es `Dipplin`: se activa siempre si el activo rival no es Crustle, o si es Crustle pero con ≤2 energías (mismo umbral que `_ctm_dipplin_low`). Marca que conviene cargar el `Dipplin` activo con energía.
- **Override de `plan` para forzar el ataque de `Dipplin`** (líneas 4154–4173, solo en `context == SelectContext.MAIN` y `_ctm_dipplin_low`): busca en el orden activo+banca un `Dipplin` (prefiriendo uno que ya tenga energía, `len(energies) >= 1`, sobre uno vacío) y sobrescribe directamente `plan.attacker`, `plan.target = 0`, `plan.attack_index = 0`, `plan.energy` (si aún necesita adjunte) y `plan.remain_hp`. Es una intervención directa sobre el plan de ataque calculado en el bloque de amenaza (`main-07`), no solo una bandera de puntuación.
- **Override de `plan` para forzar la promoción/ataque de `Tapu_Bulu`** (líneas 4175–4194, `_ctm_tapu_ready`): busca el índice del `Tapu_Bulu` listo (activo o banca) y sobrescribe el `plan` igual que arriba, con `plan.energy = False` (ya no necesita adjunte). Si está en banca, esto fuerza la retirada+promoción; si ya es el activo, ataca sin retirar.

Estas dos sobrescrituras de `plan` son la única parte de este tramo que modifica directamente el `AttackPlan` en vez de limitarse a fijar una variable local; el resto del `agent()` (incluida la puntuación de `ATTACK`, doc `main-15`) consulta `plan.attacker`/`plan.target`/etc. como fuente de verdad, así que estos overrides tienen efecto inmediato sobre qué ataque se ejecuta.

### `_active_needs_energy` (líneas 4196–4232)

Recalcula, por tipo de Pokémon activo, si necesita más energía para poder atacar (solo si `not state.energyAttached`, es decir, si aún no se ha gastado el adjunte del turno): `Hydrapple_ex` necesita `_act_effective < 2`; `Dipplin` necesita `_act_energy < 1`; `Teal_Mask_Ogerpon_ex` necesita `< 3`; `Tapu_Bulu` necesita `< 4`; `Pinsir` necesita `< 2`; `Meowth_ex` necesita tener 0 energía (para poder retirarse eventualmente, no para atacar — Meowth ex no ataca); `Fezandipiti_ex` tiene lógica especial (líneas 4216–4225): si ya tiene ≥3 efectiva no necesita más; si con un adjunte más llegaría a 3, sí lo necesita; si no, solo lo marca si tiene 0 energía. Para la línea Chikorita/Bayleef/Meganium (líneas 4226–4232) el criterio no es de ataque sino de **retirada**: necesita energía si la efectiva actual es menor que su `RETREAT_COST`, aprovechando que Wild Growth también paga la retirada.

### Reservas de energía para prioridades específicas (líneas 4234–4291)

Grupo de banderas que gestionan **cómo repartir** la energía disponible en mano cuando hay varias demandas compitiendo:
- `_energy_in_hand` / `_enough_for_both` (4234–4235): cuánta energía básica hay en mano y si alcanza para dos necesidades.
- `_active_hydra_ready` / `_active_hydra_capped` (4237–4247): si el activo es `Hydrapple_ex` con ≥2 efectiva (ya listo) o con ≥2 energía física (ya "al tope" del coste de su ataque, adjuntar más no sirve para el ataque en sí).
- `_bench_has_chargeable` (4249): si hay algún Pokémon en banca (no vacía) al que se le podría adjuntar energía.
- `_reserve_hydra_active_charge` (4251–4258): con exactamente 1 energía en mano, si el activo `Hydrapple_ex` está justo por debajo del umbral (`< 2` efectiva) y ese adjunte lo cruzaría (`>= 2` tras adjuntar), y no hay `op_has_ex_immune_active` (no tendría sentido reservar energía para un ataque que el rival anularía), se marca para **reservar** esa única energía para el activo en vez de repartirla.
- `_prob_energy_draw_soon` / `_energy_starved_low_draw` (4260–4264): usa `_prob_draw_any(Basic_Grass_Energy, draws=2)` para estimar la probabilidad de robar energía básica en los próximos 2 robos; si el activo necesita energía, no hay ninguna en mano, no se ha adjuntado este turno y esa probabilidad es baja (`< 0.5`), se marca `_energy_starved_low_draw` — señal de que el agente está en una situación de sequía de energía real, no solo momentánea.
- `_hydrapple_bench_needs_energy` (4266–4274): si hay energía en mano, comprueba si algún `Hydrapple_ex` de banca (no el activo) sigue por debajo de 2 efectiva.
- `_energy_demands_before_teal` / `_enough_after_priorities` (4276–4281): suma 1 por cada demanda "prioritaria" detectada (`_active_needs_energy`, `_hydrapple_bench_needs_energy`) y comprueba si sobra energía en mano después de cubrirlas — el nombre ("before_teal") sugiere que esta cuenta se usa aguas abajo para decidir si además queda margen para activar *Teal Dance* de Ogerpon con energía extra.
- `_reserve_energy_for_hydra_evolve` (4283–4291): con el activo `Dipplin`, exactamente 1 energía en mano y sin inmunidad ex rival, si es alcanzable evolucionar a `Hydrapple_ex` este turno (`Hydrapple_ex` o `Ultra_Ball` en mano) y el adjunte llevaría a `Dipplin` a ≥2 energía tras evolucionar, se reserva esa energía en vez de gastarla en otra cosa — para que, tras evolucionar, `Hydrapple_ex` nazca ya con energía suficiente.

### `_bcs_playable_in_hand` (líneas 4293–4305)

Con `Bug_Catching_Set` en mano, comprueba si buscar con él tendría objetivo útil: recorre `CARTAS_ACTIVAS_EN_MAZO` buscando, entre las cartas que aún quedan en el mazo (`ESTADO_MAZO > 0`), o bien `Basic_Grass_Energy`, o bien cualquier carta Pokémon de tipo Planta (`cardType == CardType.POKEMON and energyType == EnergyType.GRASS`). Si encuentra alguna, `_bcs_playable_in_hand = True`. Determina si vale la pena jugar el objeto en vez de guardarlo.

### `_pp_playable_in_hand` (líneas 4307–4313)

Análogo para `Poke_Pad`: comprueba si queda en el mazo alguna copia de `Chikorita`, `Bayleef`, `Meganium`, `Applin`, `Dipplin` o `Tapu_Bulu` (las cartas que Poke Pad puede buscar).

### Meowth ex en el primer turno: no adelantarlo salvo mano de una sola carta (líneas 4315–4339)

Bloque con un comentario extenso que fija la regla: en el primer turno propio **no** se debe bajar `Meowth ex` primero, porque su búsqueda (normalmente un Supporter) quedaría barajada de vuelta al jugar `Lillie's Determination` al final del turno — un fetch desperdiciado, además de dejar a Meowth ex de más como cuerpo de 2 premios. Variables:
- `_our_first_turn` (4324–4325): `True` si es el primer turno real jugando (turno 1 en primera posición o turno 2 en segunda).
- `_lillie_available` (4326–4329): si `Lillie's Determination` está en mano o localizable en el mazo.
- `_meowth_hand_only_card` (4330–4332): si `Meowth_ex` está en mano y es la **única** carta de la mano.
- `_meowth_lone_fetch` (4333–4339): `True` solo si es el primer turno, la banca está vacía, no hay ya un `Meowth_ex` en juego, `Meowth_ex` es la única carta en mano, y quedan copias de `Lillie's Determination` en el mazo. Esta es la **excepción** explícita mencionada en el comentario: si de verdad no hay nada más que jugar (mano de una sola carta, banca vacía), sí se baja `Meowth ex` para buscar `Lillie's Determination` y jugarla el turno siguiente.

### `_bench_attacker_ready` / `_bench_attacker_needs_energy` (líneas 4341–4383)

Recorren la banca (no el activo) comprobando, por especie, si algún atacante ya está listo para atacar (`_bench_attacker_ready`: `Hydrapple_ex` con `_bp_eff >= 2`, `Teal_Mask_Ogerpon_ex` con `>= 3`, `Dipplin` con `_bp_e >= 1`, `Tapu_Bulu` con `>= 4`, `Pinsir` con `>= 2`, `Meganium` con `>= 4`) o si alguno de los "grandes" (`Hydrapple_ex`, `Teal_Mask_Ogerpon_ex`, `Dipplin`, `Tapu_Bulu`) sigue **por debajo** de su umbral (`_bench_attacker_needs_energy`). Nota: `_bench_attacker_ready` es reasignada más adelante en `agent()` (línea 12334, en el bloque RETREAT) con un cálculo distinto y más local — la definición de aquí (4341) es la que alimenta las ramas anteriores a esa reasignación (p. ej. líneas 4592, 5476, 5497, 11467).

### Debilidad/resistencia Planta del activo rival (líneas 4385–4397)

`_op_active_hp`, `_op_active_weakness_grass`, `_op_active_resistance_grass`: lecturas directas de `card_table` sobre el activo rival, cacheadas aquí porque se reutilizan en varias comprobaciones de daño de las siguientes banderas (evita repetir el lookup en `card_table` y el `if` de tipo en cada sitio).

### `_active_hydra_cannot_ko` (líneas 4399–4406)

Solo si el activo es `Hydrapple_ex` "al tope" (`_active_hydra_capped`, ≥2 energía física, adjuntar más no cambia el ataque *Syrup Storm*) y el rival tiene HP > 0: calcula el daño actual (`30 + 30 * total_grass`, con el ajuste de debilidad/resistencia) y marca `True` si **no** alcanza para noquear. Se usa después (línea 11557, doc `main-13`) para no malgastar adjuntes de energía sobre un `Hydrapple_ex` que de todas formas no va a noquear este turno por mucha energía extra que reciba (su daño depende de `total_grass`, no de su propia energía, una vez alcanzado el mínimo de 2).

### `_extra_energy_enables_ko(pokemon_id, current_energy)` (líneas 4408–4440)

Función auxiliar (no una bandera simple) que responde: "¿el daño actual **no** noquea al activo rival, pero **una energía más** sí lo haría?". Implementada solo para `Hydrapple_ex` (compara `_dmg_now = 30 + 30*total_grass` contra `_dmg_extra` con un `total_grass` incrementado en `_grass_attach_unit()`) y `Teal_Mask_Ogerpon_ex` (el daño de *Myriad Leaf Shower* depende de la energía propia más la del rival, `30 + 30*(mi_efectiva + energía_rival)`). Ambas ramas aplican el mismo ajuste de debilidad (`x2`) / resistencia (`-30`) antes de comparar contra `_op_active_hp`. Para cualquier otro Pokémon devuelve `False`. Se reutiliza en muchos puntos posteriores (líneas 4831, 4856, 5473, 5494, 5596, 5627, 11462, 11555) para decidir si vale la pena priorizar un adjunte de energía puntual.

### `_active_already_kos` (líneas 4442–4469)

Comprueba, **sin contar adjuntes adicionales**, si el activo propio ya noquea al activo rival con la energía que tiene ahora mismo. Cubre `Teal_Mask_Ogerpon_ex` (≥3 efectiva), `Hydrapple_ex` (≥2 efectiva), `Tapu_Bulu` (≥4 efectiva, daño fijo 220), `Meganium` (≥4 efectiva, daño fijo 140) y `Fezandipiti_ex` (≥3 efectiva, *Cruel Arrow* con 100 de daño **fijo de tipo Oscuridad**, por lo que el código marca `_ak_is_grass = False` y **no** le aplica el ajuste de debilidad/resistencia a Planta). Se usa como base de comparación en varias ramas posteriores (líneas 4548, 5398, 5476, 5498, 11464–11468) para no malgastar recursos (energía, retirada) en situaciones donde el activo ya gana el intercambio tal cual está.

### `_ogerpon_td_manual_lethal`: letal por doble carga de Ogerpon en un turno (líneas 4471–4489+)

Motivada por `log 85803267, turno 4` (comentario extenso). El escáner "codicioso" del resto del agente solo evalúa +1 energía por opción (vía `_extra_energy_enables_ko` y `_active_already_kos`), así que no detecta un letal que requiera **dos** cargas simultáneas: adjunte manual de energía **más** la Habilidad *Teal Dance* de `Teal_Mask_Ogerpon_ex` (que adjunta 1 energía Planta adicional y además roba una carta). Condiciones: el activo es `Teal_Mask_Ogerpon_ex`, no se ha adjuntado energía este turno, el rival tiene HP > 0, el activo **no** noquea ya (`not _active_already_kos`) y hay ≥2 energías básicas en mano. Comprueba primero que la Habilidad esté disponible como opción jugable este turno (`o.type == OptionType.ABILITY and o.area == AreaType.ACTIVE` entre `select.option`, línea 4489). Si lo está, simula el resultado de sumar **dos** unidades de energía (`_otml_e_after = energías_actuales + 2 * _grass_attach_unit()`), calcula el daño de *Myriad Leaf Shower* con ese total más la energía del rival, aplica debilidad/resistencia, y si con ≥3 energía total el daño iguala o supera el HP rival, marca `_ogerpon_td_manual_lethal = True` (confirmado en línea 5440, fuera de este tramo, donde se usa para no penalizar/despriorizar el adjunte manual sobre el activo en ese turno).

## Interacciones

- **`evaluate_supporters()` → puntuación de `PLAY` de Supporters** (doc `main-12`, líneas ~8684–11008): `_supp_values` (y los valores concretos de `Lillie_Determination`, `Dawn`, `Lanas_Aid`, `Boss_Orders`) son la fuente directa de puntaje cuando el bucle principal evalúa la opción `PLAY` de cada Supporter en mano.
- **`_boss_prize_rank`** alimenta el cálculo de puntaje de `Boss's Orders` en `PLAY` (línea 10679: `score = BOSS_SCORE_PRIZE_RANK_BASE + (8 - _boss_prize_rank) * 20 + supporter_boost`) y se usa como condición de veto de `Lillie's Determination` en la rama de refresco de mano (línea 5742: `_boss_prize_rank >= 7`).
- **`_win_via_boss_gust` / `_gust_2prize_via_boss`** controlan directamente qué objetivo busca la Habilidad de `Meowth ex` o el fetch de otras cartas cuando el objetivo es `Boss_Orders` (línea 8025), vetan otras jugadas de desarrollo en el bucle de `PLAY` (líneas 8810, 8884), y participan en la condición general de "ya tenemos forma de ganar el intercambio este turno" usada también en `RETREAT` (línea 9936) y en el veto de Lillie's (línea 5734/5743).
- **`_boss_win_via_bench` / `_boss_dodge_redirect` / `_boss_defensive_gust`** convergen en el bloque de puntuación final de `Boss's Orders` en `PLAY` (líneas 10642–10832, doc `main-12`), donde deciden entre varias ramas de puntaje (`elif _boss_win_via_bench`, `elif _boss_dodge_redirect`, `elif _boss_defensive_gust`, `elif _boss_prize_rank >= 1`).
- **`_meowth_devel_lillie`** condiciona tanto el objetivo de búsqueda de la Habilidad de Meowth ex en el bucle `CARD`/`NUMBER` (líneas 8027, 8887, doc `main-11`) como la puntuación de bajar `Meowth ex` como `PLAY` (líneas 8817, 8856, doc `main-12`).
- **`_active_ready_attacker` / `_ready_attacker_count`** se consultan juntas en las mismas ramas de `PLAY` (líneas 8817–8856) para graduar cuánto vale desarrollar (Meowth ex) frente a simplemente atacar o adjuntar energía al atacante ya listo.
- **`_ctm_*`** (anti-Crustle) alimentan tanto overrides directos de `plan` (ya aplicados en este mismo tramo, líneas 4154–4194) como puntuaciones de `ATTACH` en las líneas 5147–5188 (doc `main-10`) y de `RETREAT`/promoción en el resto del archivo.
- **`_bcs_playable_in_hand` / `_pp_playable_in_hand`** se consultan en `PLAY` (líneas 8881–8895, 9469, doc `main-12`) y en la finalización (línea 11093, override de Ultra Ball/Poke Pad) para decidir si jugar el objeto de búsqueda correspondiente compite con otras jugadas de tier alto.
- **`_active_already_kos` / `_extra_energy_enables_ko` / `_ogerpon_td_manual_lethal` / `_active_hydra_cannot_ko`** son consumidas masivamente por la puntuación de `ATTACH` (doc `main-13`, líneas 4548–4856 en este mismo bloque de pre-cómputo, y 5398–5627, 11462–11557 en el bucle real) para decidir a qué Pokémon conviene adjuntar la energía del turno.
- **`_bench_attacker_ready` / `_bench_attacker_needs_energy` / `_bdg_retreat_ko`** informan tanto `ATTACH` (líneas 4592, 5476, 5497) como `RETREAT` (líneas 10832–10861, 12334–12394, doc `main-14`), determinando si conviene retirar el activo para promover un atacante de banca ya cargado en vez de seguir invirtiendo recursos en el activo actual.
- **`_lana_enables_attack`** se usa en la comparación final entre `Lana's Aid` y `Lillie's Determination` dentro de `PLAY` (línea 11005, doc `main-12`).

## Reglas derivadas de partidas

- **`log 86339758`, paso 98** (citado tres veces: líneas 3867–3870, 3988–3990, 4002–4004): vs mazo Crustle, `Dwebble_Grass`/`Dwebble_Fighting` está vetado como objetivo de gusteo tanto en el ranking de premios (`_boss_prize_rank`) como en las comprobaciones de victoria por gusteo (`_win_via_boss_gust`, `_gust_2prize_via_boss`) — Dwebble no debe contar como objetivo "válido" de `Boss's Orders`.
- **`log 86023830`, paso 69** (líneas 3900–3921): vs mazo Mega Lucario, si hay un `Riolu` gusteable-y-noqueable en banca rival y ya hay banca propia establecida, se prioriza `Boss's Orders` sobre el `Riolu` por encima de cualquier desarrollo (`_lucario_riolu_gust`), para cortar la línea del atacante principal antes de que evolucione.
- **`log 85804848`, paso 49** (vs Alakazam, partida perdida; líneas 4033–4046): si retirar y promover un atacante de banca ya noquea al activo rival este turno (`_bdg_retreat_ko`), gustear con `Boss's Orders` solo para "cobrar premio" es redundante; con `Lillie's Determination` en mano se cede prioridad a refrescar la mano, salvo que el gusteo aporte algo genuinamente distinto (letal directo o intercambio de 2 premios).
- **`log 85803267`, turno 4** (líneas 4471–4503): un letal de `Teal_Mask_Ogerpon_ex` que requiere sumar **dos** cargas de energía en el mismo turno (adjunte manual + Habilidad *Teal Dance*) no lo detecta el resto del motor (que solo evalúa +1 energía por opción); `_ogerpon_td_manual_lethal` cubre ese caso concreto para no penalizar el adjunte manual cuando en realidad completa un letal de dos pasos.
