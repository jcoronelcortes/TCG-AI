# main.py — Bucle de puntuación — ATTACK, END y finalización de la decisión (líneas 12609–12919)

## Rol en el agente

Este es el **último tramo** del gran bucle `for o in select.option:` que arranca en la línea ~5970 (documentado en `main-11` a `main-14`): puntúa las opciones `ATTACK`, `END` y `SPECIAL_CONDITION`, y cierra el bucle con `scores.append(score)` (línea 12761). A diferencia de las ramas de `PLAY`/`ATTACH`/`RETREAT`, aquí el `score` de `ATTACK` no se calcula desde cero a partir de `plan`: arranca en un valor fijo alto (`1000`) y luego se somete a una cascada de **vetos** (`score = -1`) que reflejan situaciones muy concretas en las que atacar con el activo AHORA es peor que la alternativa (retirar primero, jugar un Supporter, buscar con Ultra Ball, o simplemente no arriesgarse porque el rival esquiva o porque estamos confundidos). El diseño es deliberado: como `plan` (el `AttackPlan` calculado en `main-07`) ya decidió *cuál* es el mejor atacante/objetivo/ataque posibles, la rama `ATTACK` sólo necesita decidir *si conviene ejecutar ya* el ataque del Pokémon activo tal como está la mesa, o si es mejor posponerlo un paso (retirar, cargar energía, jugar un objeto).

Tras el bucle, el bloque de **finalización** (líneas 12763–12919) es el mecanismo que materializa `scores` en la lista de índices que `agent()` devuelve. No vuelve a puntuar nada por identidad de carta salvo en tres excepciones muy dirigidas (recordar el objetivo de Poke Pad/Ultra Ball para el turno siguiente, forzar un sacrificio de Tapu Bulu, y vetar estadios en el primer turno propio); su tarea principal es **reordenar** los índices ya puntuados mediante un sistema de *tiers* que impone la secuencia de juego deseada (estadio → desarrollo → Poke Pad → Bug Catching Set → energía) sin tocar los vetos, y finalmente devolver `desc_indices[:select.maxCount]`.

## Detalle por bloque

### `ATTACK`: puntaje base y riesgo de confusión (líneas 12609–12621)

```python
elif o.type == OptionType.ATTACK:
    score = 1000
    if plan.attack_index >= 0:
        score += 100
    if condition_risky_attack:
        if _conf_should_attack:
            score += 300
        elif plan.remain_hp is not None and plan.remain_hp <= 0:
            score += 50
        else:
            score -= 500
```

`score` arranca en `1000` (línea 12610) — un valor "de base" alto porque, en ausencia de vetos, atacar suele ser la mejor jugada disponible tras haber jugado ya lo demás. Si `plan.attack_index >= 0` (el `AttackPlan` calculado en `main-07`, líneas 391–397, SÍ tiene un ataque válido planeado), suma `+100` extra (línea 12613): un pequeño refuerzo cuando el plan táctico coincide con la opción de atacar disponible.

`condition_risky_attack` (definido en línea 1421 como `is_confused`, es decir, nuestro Pokémon activo está confundido) matiza ese puntaje:

- Si `_conf_should_attack` es `True` (línea 1970: confundido, **sin** un atacante de banca listo del matchup — `_conf_bench_attacker_ready`, línea 1953 — y el activo confundido SÍ cumple el umbral de energía para atacar, `_conf_can_attack_pkmn`, línea 1928): `+300`. Es la situación de "no hay alternativa mejor", así que se empuja a atacar pese al riesgo de fallar la tirada de confusión.
- Si no, pero el ataque planeado noquearía (`plan.remain_hp <= 0`): sólo `+50` — sigue siendo arriesgado (la confusión puede hacer fallar el golpe), pero el premio de un KO justifica un empujón moderado.
- En cualquier otro caso: `-500` — con un atacante de banca listo y sin KO garantizado, es mejor **no** arriesgar el golpe confuso; el resto de la lógica de retirada (documentada en `main-14`) se encarga de promover ese atacante de banca.

### `ATTACK`: Hydrapple ex — ceder el turno a desarrollo si no hay KO (líneas 12623–12653)

```python
_active_is_hydrapple = (... my_state.active[0].id == Hydrapple_ex)
if _active_is_hydrapple and not itchy_pollen_active:
    _atk_is_ko = (plan.remain_hp is not None and plan.remain_hp <= 0)
    if not _atk_is_ko:
        _can_add_energy = False
        ...
        if _can_add_energy:
            score = -1
```

Cuando el activo es `Hydrapple_ex` (línea 12623–12624), `itchy_pollen_active` es `False` (el rival NO ha usado `Itchy Pollen` de `Budew` este turno — línea 1574–1578, lo que implicaría estar bajo un efecto que fuerza a actuar YA) y el ataque planeado **no** noquea (`_atk_is_ko` falso), el bloque comprueba si hay una forma productiva de invertir la acción de energía del turno en vez de golpear sin noquear:

- Hay `Basic_Grass_Energy` en mano y **aún no se ha usado** el adjunte manual del turno (`not state.energyAttached`, línea 12631–12633).
- Hay al menos un `Teal_Mask_Ogerpon_ex` en juego y una Planta básica en mano (línea 12635–12638) — Ogerpon en banca/activo puede recibir esa energía vía la habilidad *Ripening Charge* de Hydrapple (que adjunta a **cualquier** Pokémon; ver comentario de línea 4538).
- Hay `Teal_Mask_Ogerpon_ex` en MANO, banca con hueco (`bench_count < 5`) y energía disponible (línea 12640–12642) — vale la pena bajarlo y cargarlo en vez de atacar.
- Hay `Ultra_Ball` en mano, banca con hueco, energía en mano, **queda** un `Teal_Mask_Ogerpon_ex` en el mazo (`CARTAS_ACTIVAS_EN_MAZO`) y la mano tiene ≥3 cartas —umbral necesario para poder jugar Ultra Ball, que exige descartar 2 cartas además de la propia carta— (línea 12644–12649).

Si cualquiera de estas vías está disponible (`_can_add_energy = True`), el ataque se **veta** (`score = -1`, línea 12653): es mejor usar el turno para desarrollar el board (adjuntar/buscar) que golpear sin rematar con Hydrapple ex.

### `ATTACK`: preferir retirar hacia el atacante del plan (líneas 12655–12672)

```python
if plan.attacker >= 1 and score > 0 and not _nonex_active_hits_wall:
    _plan_atk_is_winning = False
    if plan.remain_hp is not None and plan.remain_hp <= 0:
        _op_act_plan = op_state.active[0] if op_state.active else None
        if _op_act_plan is not None and my_prize <= prize_count(_op_act_plan):
            _plan_atk_is_winning = True
    if not _plan_atk_is_winning:
        _plan_active = my_state.active[0] if my_state.active else None
        _plan_can_retreat = False
        if _plan_active is not None:
            _plan_rc = RETREAT_COST.get(_plan_active.id, 1)
            _plan_active_energy = len(_plan_active.energies)
            if _plan_active_energy >= _plan_rc:
                _plan_can_retreat = True
        if _plan_can_retreat:
            score = -1
```

`plan.attacker >= 1` significa que el `AttackPlan` calculado en `main-07` eligió como mejor atacante a un Pokémon de **banca** (la codificación es `0` = activo, `1 + índice` = banca; ver `main-07`), no al activo actual. Si además el ataque del activo aún no está vetado (`score > 0`) y el activo **no** es el caso especial de un no-ex que sí golpea el muro inmune-a-ex rival (`_nonex_active_hits_wall`, línea 4628: activo no-ex contra `op_has_ex_immune_active` con daño `> 0`), se comprueba si atacar ahora mismo YA gana la partida (`my_prize <= prize_count(_op_act_plan)`, línea 12659 — los premios que nos faltan caben en el KO planeado). Si no gana ya y el activo tiene energía suficiente para pagar su propio coste de retirada (`RETREAT_COST`), se veta el ataque (`score = -1`, línea 12671): es mejor retirar primero (documentado en `main-14`) y dejar que el atacante correcto del plan suba el turno siguiente, en vez de gastar el ataque del activo actual. La excepción `_nonex_active_hits_wall` evita que esta regla retire, contra Crustle/Sylveon, al único Pokémon (no-ex) capaz de dañar al muro con tal de "seguir el plan".

### `ATTACK`: banca vacía + Ultra Ball disponible → priorizar desarrollo (líneas 12673–12698)

```python
if (bench_count == 0 and hand_counts.get(Ultra_Ball, 0) >= 1):
    _atk_hand_size = len(my_state.hand) if my_state.hand else 0
    if _atk_hand_size >= 3 and not itchy_pollen_active:
        _atk_has_basic_in_hand = any(hand_counts.get(pid, 0) >= 1 for pid in (...))
        if not _atk_has_basic_in_hand:
            _atk_has_basic_mazo = ... # algún básico propio queda en el mazo
            if _atk_has_basic_mazo:
                _atk_is_winning = False
                if plan.remain_hp is not None and plan.remain_hp <= 0:
                    _op_act_atk = op_state.active[0] if op_state.active else None
                    if _op_act_atk is not None and op_prize <= prize_count(_op_act_atk):
                        _atk_is_winning = True
                if not _atk_is_winning:
                    score = -1
```

Con la banca vacía (`bench_count == 0`, un único Pokémon en juego: riesgo de perder el board entero si es noqueado) y `Ultra_Ball` jugable con mano suficiente (`>= 3` cartas, necesarias porque Ultra Ball exige descartar 2 además de sí misma), si **ningún** básico propio (`Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir`) está ya en mano pero **sí** queda alguno en el mazo (fetchable con Ultra Ball, vía `CARTAS_ACTIVAS_EN_MAZO`), se veta el ataque salvo que ya sea el golpe ganador de la partida. Nótese que aquí la comprobación de "ataque ganador" usa `op_prize <= prize_count(_op_act_atk)` (línea 12694) — compara los premios que le **faltan al rival**, no los que nos faltan a nosotros (`my_prize`, como en el bloque anterior, línea 12659); es una asimetría respecto al patrón hermano de líneas 12657–12660 y podría ser una inconsistencia, pero así está escrito en el código actual. En la práctica, `op_prize <= prize_count(_op_act_atk)` sólo sería `True` cuando al rival le quedan pocos premios y el objetivo KO'd vale muchos, un caso bastante más raro que el chequeo `my_prize`-based.

### `ATTACK`: veto en el turno 2 si Lillie's Determination es jugable (líneas 12699–12709)

```python
if (state.turn == 2 and not we_go_first
        and hand_counts.get(Lillie_Determination, 0) >= 1):
    _lillie_playable_now = any(
        _lo.type == OptionType.PLAY
        and get_card(obs, AreaType.HAND, _lo.index, my_index) is not None
        and get_card(obs, AreaType.HAND, _lo.index, my_index).id == Lillie_Determination
        for _lo in select.option)
    if _lillie_playable_now:
        score = -1
```

En nuestro primer turno jugando en segundo lugar (`state.turn == 2 and not we_go_first`), si `Lillie's Determination` está en mano **y** hay realmente una opción `PLAY` para jugarla ahora mismo, se veta atacar. Con un solo turno de energía cargada el daño disponible en el turno 2 suele ser bajo, así que se prioriza barajar/robar con Lillie's (puntuada en la escalera de Supporters, `main-09`) para llegar a un mejor turno 3, en vez de gastar el ataque en un golpe de bajo impacto.

### `ATTACK`: Meowth ex sin banca y esquive de Hops Phantump (líneas 12710–12721)

```python
_atk_active = my_state.active[0] if my_state.active else None
if (_atk_active is not None and _atk_active.id == Meowth_ex and bench_count == 0):
    # El ataque de Meowth ex (Tuck Tail) devuelve a Meowth ex y todas
    # sus cartas a la mano. Si Meowth ex es el UNICO Pokemon en juego
    # (banca vacia), atacar nos dejaria sin Pokemon en juego => perdemos.
    score = -1

if op_active_dodge_immune:
    score = -1
```

Si el activo es `Meowth_ex` y la banca está vacía, atacar con *Tuck Tail* (que devuelve a Meowth ex y sus cartas a la mano) nos dejaría sin ningún Pokémon en juego, lo que es una derrota inmediata: veto absoluto. Después, `op_active_dodge_immune` (calculado en líneas 1580–1609: el rival jugó *Splashing Dodge* con `Hops Phantump` y ganó la tirada de moneda, por lo que su activo es inmune a ataques este turno/serial) también veta atacar — el golpe fallaría con certeza.

### `END`: sólo se habilita cuando conviene renunciar al ataque (líneas 12723–12731)

```python
elif o.type == OptionType.END:
    if can_attack:
        _end_attack_is_risky = (
            condition_risky_attack and
            not (plan.remain_hp is not None and plan.remain_hp <= 0))
        if _conf_should_attack or not _end_attack_is_risky:
            score = -10000
```

`score` de `END` parte del valor base genérico asignado más arriba en el bucle (no se muestra en este tramo; por defecto es bajo/neutro). Aquí sólo se **penaliza fuertemente** (`-10000`, un veto de facto) cuando `can_attack` es `True` (hay una opción `ATTACK` disponible este turno, bandera precalculada en línea 1997) y NO estamos en el caso especial de "confusión arriesgada sin necesidad de atacar" (`_end_attack_is_risky`: confundidos y el ataque planeado no noquea). Es decir: terminar el turno sin atacar es aceptable únicamente cuando atacar sería arriesgado por confusión y no hay premio de KO en juego (`_end_attack_is_risky = True` y `_conf_should_attack = False`); en cualquier otro escenario donde se puede atacar, `END` queda castigado a `-10000` para que el bucle de tiers/scores jamás lo prefiera sobre atacar (o sobre cualquier otra jugada positiva).

### `SPECIAL_CONDITION`: prioridad de curación/afectación por severidad (líneas 12732–12760)

Dos contextos comparten la misma escalera de valores pero con matices:

- `RECOVER_SPECIAL_CONDITION` (curar una condición propia): `PARALYZE = 500`, `SLEEP = 400`, `CONFUSE = 300`, `POISON = 200`, `BURN = 150`.
- `AFFECT_SPECIAL_CONDITION` (elegir qué condición infligir al rival, p.ej. tras un ataque que permite elegir): mismos valores salvo `CONFUSE = 350` (en vez de `300`).

El orden refleja severidad táctica: parálisis (bloquea acción por completo) > sueño (bloquea, probabilístico) > confusión (arriesga el ataque) > veneno/quemadura (daño pasivo acumulativo, veneno algo peor que quemadura). Curar o infligir primero las condiciones más bloqueantes es la prioridad.

### Cierre del bucle: `scores.append(score)` (línea 12761)

Cierra el `for o in select.option:` que arrancó en ~5970: cada opción recorrida por todas las ramas (`CARD`/`NUMBER`/`YES`/`NO`, `PLAY`, `ATTACH`/`EVOLVE`/`ABILITY`, `RETREAT`, `ATTACK`, `END`, `SPECIAL_CONDITION`) termina aquí con su `score` definitivo añadido a la lista paralela `scores`, indexada 1:1 con `select.option`.

### Override de Poke Pad (`TO_HAND`): recordar el objetivo básico para el turno siguiente (líneas 12763–12780)

```python
if select.effect is not None and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND:
    _best_pp_score = -1
    _best_pp_id = 0
    for _pp_idx, _pp_opt in enumerate(select.option):
        if _pp_idx < len(scores) and scores[_pp_idx] > _best_pp_score:
            _pp_card = get_card(obs, _pp_opt.area, _pp_opt.index, my_index)
            if _pp_card is not None:
                _best_pp_score = scores[_pp_idx]
                _best_pp_id = _pp_card.id
    if _best_pp_id > 0 and _best_pp_score > 10:
        _pp_data = card_table.get(_best_pp_id)
        _pp_is_basic = not (_pp_data is not None and
                            (getattr(_pp_data, 'stage1', False) or getattr(_pp_data, 'stage2', False)))
        if _pp_is_basic:
            _poke_pad_target_id = _best_pp_id
```

Cuando la decisión actual es "elegir qué carta llevar a la mano" con el efecto `Poke_Pad`, este bloque **no recalcula puntajes**: recorre `scores` (ya calculados por el bucle principal para cada opción de carta candidata, en la rama `CARD` del contexto `TO_HAND` documentada en `main-11`) y busca cuál tiene el mejor puntaje entre las que sí resuelven a una carta (`get_card(...) is not None`). Si ese mejor puntaje supera `10` (evita recordar un objetivo "irrelevante", casi vetado) y la carta ganadora es un Pokémon **básico** (`not stage1 and not stage2`), guarda su id en la variable global `_poke_pad_target_id` (declarada en línea 478, reseteada a `0` en cada cambio de turno, línea 1336). Este id se usa **en un paso posterior** (típicamente el mismo turno, al puntuar `PLAY` de la carta ya en mano): en la línea 9164–9167, si `card.id == _poke_pad_target_id` y hay hueco en banca, se fuerza `score = 21000` si de otro modo sería `<= 0` — garantiza que la carta que Poke Pad trajo deliberadamente se juegue, aunque la puntuación "normal" de `PLAY` la hubiera descartado.

### Override forzado: sacrificar Tapu Bulu vs Riolu/Lucario (líneas 12781–12805)

```python
if (_lucario_sac_pivot and select.effect is not None
        and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND):
    _tapu_already = (hand_counts.get(Tapu_Bulu, 0) >= 1 or field_counts.get(Tapu_Bulu, 0) >= 1)
    if (not _tapu_already) and _tapu_sac_priority:
        for _pp_sac_idx, _pp_sac_opt in enumerate(select.option):
            _pp_sac_card = get_card(obs, _pp_sac_opt.area, _pp_sac_opt.index, my_index)
            if _pp_sac_card is not None and _pp_sac_card.id == Tapu_Bulu:
                if _pp_sac_idx < len(scores):
                    scores[_pp_sac_idx] = 99999
                _poke_pad_target_id = Tapu_Bulu
                break
```

`_lucario_sac_pivot` (línea 5765) se activa cuando es nuestro turno 2 yendo en segundo lugar, el activo rival es `Riolu` ya con energía adjunta, tenemos `Teal_Mask_Ogerpon_ex` en juego y nuestro activo es precisamente ese Ogerpon: el plan es dejar que Riolu evolucione a Lucario y nos ataque, entregando sólo el premio de un básico barato como "sacrificio" en vez de arriesgar a Ogerpon. `_tapu_sac_priority` (línea 5791) restringe **cuándo** ese sacrificio debe ser específicamente `Tapu_Bulu` en lugar de `Applin`/`Chikorita`: sólo si el rival tiene protección anti-ex (Crustle/Cornerstone/Sylveon/inmunidad a ex o Habilidad) —donde nuestros ex no pueden pegar y conviene reservar a Tapu Bulu como atacante alternativo— o si ya existe el motor Hydrapple ex + Meganium cargado (`_lucario_hydra_engine`) que permite bajar y cargar Tapu Bulu de inmediato. Si Tapu Bulu no está ya disponible (`not _tapu_already`) y aplica la prioridad, este bloque **sobrescribe directamente** `scores[_pp_sac_idx] = 99999` para la opción de Poke Pad que trae a Tapu Bulu — a diferencia del override anterior (que sólo *recuerda* el objetivo para el turno siguiente), aquí se fuerza la elección ya en **esta misma** decisión `TO_HAND`, y además se fija `_poke_pad_target_id = Tapu_Bulu` por consistencia con el paso de `PLAY` posterior.

### Override de Ultra Ball (`TO_HAND`): marcar Meowth ex como pendiente (líneas 12806–12816)

```python
if select.effect is not None and select.effect.id == Ultra_Ball and context == SelectContext.TO_HAND:
    _best_ub_score = -1
    _best_ub_id = 0
    for _ub_idx, _ub_opt in enumerate(select.option):
        if _ub_idx < len(scores) and scores[_ub_idx] > _best_ub_score:
            _ub_card = get_card(obs, _ub_opt.area, _ub_opt.index, my_index)
            if _ub_card is not None:
                _best_ub_score = scores[_ub_idx]
                _best_ub_id = _ub_card.id
    if _best_ub_id == Meowth_ex and _best_ub_score > 10:
        _ub_meowth_pending = True
```

Mismo patrón que el override de Poke Pad, pero para `Ultra_Ball`: si la carta con mejor puntaje entre las opciones de búsqueda es específicamente `Meowth_ex` (y su puntaje supera `10`), se marca la bandera global `_ub_meowth_pending = True` (línea 479, reseteada por turno en línea 1338). Al igual que `_poke_pad_target_id`, esta bandera se consulta en el paso posterior de `PLAY` (línea 9169–9172): fuerza `score = 21000` para jugar el Meowth ex recién buscado si de otro modo puntuaría `<= 0`, siempre que no haya ya un Meowth ex en juego (`field_counts[Meowth_ex] == 0`) y quede hueco en banca. No hace falta guardar el id de la carta (a diferencia de Poke Pad, que puede buscar cualquier básico) porque Ultra Ball en este mazo sólo se usa con este propósito de "recordar" para `Meowth_ex`.

### Veto de estadio en el primer turno propio (líneas 12818–12834)

```python
_vetoed_stadium_idxs = set()
_our_first_turn_guard = ((we_go_first and state.turn == 1) or
                         (not we_go_first and state.turn == 2))
_replace_opp_stadium_ok = (
    (not we_go_first) and state.turn == 2 and
    stadium_id != 0 and stadium_id != Forest_of_Vitality)
if _our_first_turn_guard and not _replace_opp_stadium_ok and select.option:
    for _gi, _go in enumerate(select.option):
        if _gi >= len(scores):
            continue
        if _go.type == OptionType.PLAY:
            _gcard = get_card(obs, AreaType.HAND, _go.index, my_index)
            if _gcard is not None:
                _gdata = card_table.get(_gcard.id)
                if _gdata is not None and _gdata.cardType == CardType.STADIUM:
                    scores[_gi] = -99999
                    _vetoed_stadium_idxs.add(_gi)
```

`_our_first_turn_guard` identifica **nuestro** primer turno de acción, sea cual sea el orden de salida: turno 1 si vamos primero, turno 2 si vamos segundo. `_replace_opp_stadium_ok` es la única excepción: yendo en segundo lugar, en el turno 2, si ya hay un estadio rival en juego (`stadium_id != 0`) que no sea ya nuestro propio `Forest_of_Vitality`, SÍ se permite jugar un estadio (para reemplazar el del rival, ya que sólo puede haber uno activo). Fuera de esa excepción, cualquier opción `PLAY` cuya carta sea de `CardType.STADIUM` se fuerza a `scores[_gi] = -99999` y su índice se guarda en `_vetoed_stadium_idxs` para excluirlo también más abajo del `desc_indices` final (línea 12916–12917), como cinturón-y-tirantes además del puntaje extremo. Esto es lo que hace que, según el comentario de la sección de tiers (línea 12840–12841), "el estadio sólo aparece jugable a partir del turno 3".

### Orden de jugada por tiers en contexto `MAIN` (líneas 12836–12901)

El bloque lleva un comentario explicativo propio en el código (líneas 12836–12849) que resume la intención: imponer, dentro de las opciones ya puntuadas positivamente, la secuencia **1) estadio → 2) básicos/evoluciones → 3) Poke Pad → 4) Bug Catching Set → 5) cargar energía**, salvo la excepción de la energía que resuelve un KO este turno, que conserva prioridad máxima. Sólo aplica en `context == SelectContext.MAIN` y sólo reordena opciones con `scores[i] > 0` (línea 12859: `if _po_i >= len(scores) or scores[_po_i] <= 0: continue`), de modo que los vetos (puntajes ≤ 0) nunca son "ascendidos" por un tier alto.

Los tiers, de mayor a menor prioridad:

```python
_TIER_KO_ENERGY = 6
_TIER_STADIUM = 5
_TIER_DEVELOP = 4
_TIER_POKE_PAD = 3
_TIER_BUG_SET = 2
_TIER_ENERGY = 1
```

(el resto de opciones, incluyendo `ATTACK`/`END`/Supporters/Ultra Ball, se quedan en el tier por defecto `0` de `_play_order_tier = [0] * len(scores)`, línea 12850, y compiten sólo por `score`).

Asignación por tipo de opción:

- `OptionType.EVOLVE` → siempre `_TIER_DEVELOP` (línea 12861–12862): evolucionar un Pokémon en juego se juega antes que cargar energía o Poke Pad.
- `OptionType.ATTACH` (línea 12863–12888): se calcula `_po_is_ko_energy` — `True` si `plan.energy` (el `AttackPlan` requiere justo esta energía para completar un KO este turno), `plan.remain_hp <= 0`, `plan.attacker >= 0`, y la opción de adjunte apunta exactamente al Pokémon designado como atacante por el plan (activo si `plan.attacker == 0`, o el índice de banca correspondiente si `plan.attacker == 1 + inPlayIndex`). Si es así, tier `_TIER_KO_ENERGY` (6, el más alto de todos); si no, `_TIER_ENERGY` (1).
  - **Excepción documentada** (comentario líneas 12873–12883, caso `user, log 86506312 paso 97, vs Alakazam`): si `_tapu_future_charge` está activo (línea 4546: Meganium en juego, el activo YA asegura el KO sin necesidad de energía extra, y hay un `Tapu_Bulu` en banca con menos de 4 de energía efectiva, fuera de los matchups Crustle/Cornerstone/Zona de Neutralización) y la opción de adjunte es sobre el **activo** (`_po_o.inPlayArea == AreaType.ACTIVE`), se fuerza `_po_is_ko_energy = False` aunque técnicamente el activo pudiera "beneficiarse" de más energía. Sin esta excepción, cargar énfasis en el activo (tier 6) aplastaría siempre a la carga de Tapu Bulu en banca como atacante futuro (puntaje `40000`, pero tier 1 `_TIER_ENERGY`), desperdiciando energía en un atacante que YA noquea en vez de preparar al atacante del turno siguiente. Al bajar el adjunte del activo a tier `_TIER_ENERGY` en este caso, el desempate dentro del mismo tier lo gana la carga de Tapu Bulu por su puntaje mayor (`40000`).
- `OptionType.PLAY` (línea 12889–12900): si la carta es `Poke_Pad` → `_TIER_POKE_PAD` (3); si es `Bug_Catching_Set` → `_TIER_BUG_SET` (2); si `card_table[...].cardType == CardType.STADIUM` → `_TIER_STADIUM` (5); si `cardType == CardType.POKEMON` (jugar un básico de mano) → `_TIER_DEVELOP` (4). Cualquier otro `PLAY` (Supporters, Ultra Ball, Night Stretcher, Unfair Stamp, etc.) se queda en tier `0` — su orden relativo frente a `ATTACK`/`END` lo decide únicamente el `score` puntuado más arriba en el bucle.

### Ordenación final, debug y casos especiales de `return` (líneas 12902–12919)

```python
desc_indices = [i for i, _ in sorted(
    enumerate(scores),
    key=lambda x: (_play_order_tier[x[0]], x[1]),
    reverse=True)]

_debug_log_decision(context, select, scores, obs, my_index)

if context == SelectContext.SETUP_BENCH_POKEMON:
    wanted = [i for i in desc_indices if scores[i] >= 0]
    if len(wanted) < select.minCount:
        wanted = desc_indices[:select.minCount]
    return wanted[:select.maxCount]

if _vetoed_stadium_idxs:
    desc_indices = [i for i in desc_indices if i not in _vetoed_stadium_idxs]

return desc_indices[:select.maxCount]
```

`desc_indices` (línea 12902–12905) es la ordenación **definitiva**: `sorted` sobre `enumerate(scores)` con clave `(_play_order_tier[x[0]], x[1])` y `reverse=True` — primero por tier descendente, y dentro de un mismo tier, por `score` descendente. Como el tier por defecto es `0` para todo lo que no entra en las cinco categorías reordenadas, este `sort` es un superconjunto no disruptivo del comportamiento "clásico" (ordenar sólo por `score`) cuando no hay estadio/desarrollo/Poke Pad/Bug Catching Set/energía jugables ese turno.

`_debug_log_decision(context, select, scores, obs, my_index)` (línea 12907, definida en línea 687) imprime por `stderr` —sólo si `DEBUG_DECISIONS` está activo (controlado por la variable de entorno `PTCG_DEBUG`, según `main.md` §5)— el top-3 de opciones ordenadas **por `score` puro** (`sorted(..., key=lambda i: scores[i], reverse=True)`, línea 692), NO por `(tier, score)`; es decir, el log de depuración no refleja necesariamente el orden final que se devuelve cuando el sistema de tiers reordena algo — hay que tener esto presente al depurar una decisión con `PTCG_DEBUG` cuando el contexto es `MAIN`.

Dos ramas de salida especiales:

1. **`SETUP_BENCH_POKEMON`** (línea 12909–12914): en la preparación inicial hay que elegir **varios** Pokémon para la banca a la vez. `wanted` toma todos los índices con `score >= 0` (nótese `>=`, no `> 0`: aquí un empate a cero SÍ es aceptable, a diferencia del resto del agente donde `0` no es necesariamente jugable) siguiendo el orden ya calculado en `desc_indices`. Si eso no alcanza el mínimo exigido por el motor (`select.minCount`), se recurre sin más condición a los primeros `minCount` de `desc_indices` (aceptando incluso opciones con score negativo) porque el juego **obliga** a completar el mínimo de la selección. Se devuelve recortado a `select.maxCount`.
2. **Resto de contextos** (línea 12916–12919): si hubo estadios vetados en el primer turno (`_vetoed_stadium_idxs`), se filtran fuera de `desc_indices` por completo —además del `-99999` ya aplicado— antes de devolver. Finalmente, `return desc_indices[:select.maxCount]` entrega la lista de índices que `agent()` propaga como resultado de toda la función.

## Interacciones

- **Con `main-07` (plan de ataque)**: toda la rama `ATTACK` lee `plan.attacker`, `plan.attack_index`, `plan.remain_hp` y `plan.energy` en modo lectura — nunca los modifica. La coherencia entre "qué energía cargo" (tier `_TIER_KO_ENERGY` en la sección de tiers) y "qué Pokémon ataca" depende de que `plan` ya esté fijado correctamente por el bloque de `main-07` antes de llegar aquí.
- **Con `main-14` (retiradas)**: la lógica de líneas 12655–12672 es el reflejo, del lado de `ATTACK`, de las reglas de retirada documentadas en `main-14` (`_ex_stuck_promo_ready`, `_teal_dance_ko_pivot`, etc.) — cuando `RETREAT` puntúa alto para promover al atacante del plan, `ATTACK` se veta en paralelo para que ambas puntuaciones no compitan de forma contradictoria dentro del mismo `desc_indices`.
- **Con `main-09` (Supporters)**: el veto de línea 12699–12709 (turno 2, Lillie's jugable) depende de que la escalera de Supporters (`main-09`) ya le dé a `Lillie's Determination` un puntaje competitivo ese turno; este bloque no calcula ese puntaje, sólo evita que `ATTACK` le gane la partida.
- **Con `main-11` (búsqueda de cartas / `TO_HAND`)**: los overrides de Poke Pad (12763–12805) y Ultra Ball (12806–12816) leen `scores` ya calculados por las ramas `CARD`/`NUMBER`/`YES`/`NO` de `main-11` para el contexto `TO_HAND`; no reimplementan esa puntuación, sólo la consultan para decidir qué recordar.
- **Con `main-12` (`PLAY`)**: `_poke_pad_target_id` y `_ub_meowth_pending`, fijados aquí, son leídos por la rama `PLAY` documentada en `main-12` (línea 9164–9172) en el/los paso(s) siguiente(s) del mismo turno, para forzar que la carta efectivamente buscada se juegue. Ambas variables son **globales** (declaradas en líneas 478–479) que persisten entre llamadas a `agent()` hasta que cambia el turno (reseteo en líneas 1336 y 1338).
- **Con `main-13` (`ATTACH`/`EVOLVE`)**: el tier `_TIER_KO_ENERGY`/`_TIER_ENERGY` de la sección de tiers no recalcula la puntuación de `ATTACH` (eso lo hace `main-13`); sólo decide en qué **orden relativo** se juega frente a estadio/desarrollo/Poke Pad/Bug Catching Set cuando varias de esas opciones son simultáneamente viables (`score > 0`) el mismo turno.

## Reglas derivadas de partidas

- **Log 86506312, paso 97 (vs Alakazam)** (líneas 12873–12883): sin la exclusión de `_tapu_future_charge` sobre el tier de `ATTACH` al activo, el sistema de tiers hacía que cargar energía "extra" e innecesaria en el activo (Hydrapple ex, que ya noqueaba) se jugara **antes** que cargar a Tapu Bulu en banca como atacante futuro, porque el tier `_TIER_KO_ENERGY` (6) del activo superaba siempre al tier `_TIER_ENERGY` (1) de Tapu Bulu, sin importar que el puntaje de Tapu Bulu (`40000`) fuera mucho mayor. La corrección degrada el adjunte al activo a tier `_TIER_ENERGY` cuando `_tapu_future_charge` está activo, dejando que el desempate por puntaje dentro del mismo tier favorezca a Tapu Bulu.
