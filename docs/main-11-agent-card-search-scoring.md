# main.py — Bucle de puntuación — búsqueda y selección de cartas (líneas 5970–8684)

## Rol en el agente

Aquí arranca el **gran bucle de puntuación** (`scores = []; for o in select.option:`) que cierra `agent()`: cada `o` es una opción concreta ofrecida por el motor y el bucle le asigna un `score` según `o.type` y el `context` de la decisión. Este documento cubre las ramas que resuelven decisiones de **elegir una carta/objetivo o responder Sí/No/Número** — todo lo que NO es jugar una carta de la mano (`PLAY`, doc 12), adjuntar/evolucionar/usar habilidad (`ATTACH`/`EVOLVE`/`ABILITY`, doc 13), retirar (`RETREAT`, doc 14) o atacar/terminar turno (`ATTACK`/`END`, doc 15). Dentro de este tramo vive, con diferencia, la lógica más extensa de selección de objetivo del archivo: promoción de nuestro propio activo (`SWITCH`/`TO_ACTIVE`), el objetivo de **Boss's Orders** cuando gustea al rival (mismo contexto, pero `o.playerIndex` del rival), la preparación inicial (`SETUP_ACTIVE_POKEMON`/`SETUP_BENCH_POKEMON`) y, sobre todo, **todas las búsquedas de carta hacia la mano** (`TO_HAND`): Bug Catching Set, Poke Pad, Night Stretcher, Ultra Ball, la habilidad de Meowth ex y Dawn, cada una con su propia escalera de prioridades por carta objetivo. Cierra con `DISCARD` (qué carta sacrificar al pagar un coste de descarte), `RECOVER_/AFFECT_SPECIAL_CONDITION` y `ATTACH_FROM`.

El patrón dominante es: **puntuar cada carta candidata según cuánto acerca al agente a su plan de partida** (completar una línea evolutiva, cargar/activar un atacante, negar premios al rival, refrescar la mano) y usar valores muy altos (300–20000) para forzar la elección correcta cuando hay una prioridad clara, dejando valores bajos (10–100) como "relleno" cuando la carta no aporta nada este turno. Muchas ramas llevan comentarios que citan el `log 86xxxxxx` de la partida real que motivó la regla — son parches dirigidos a errores observados, no heurísticas genéricas.

## Detalle por bloque

### Cabecera del bucle y `OptionType.NUMBER` (líneas 5970–5975)

```python
scores = []
for o in select.option:
    score = 0

    if o.type == OptionType.NUMBER:
        score = o.number
```

Arranca el bucle principal de `agent()`. Para `NUMBER` (p.ej. "¿cuántas cartas robar/descartar?") el puntaje es directamente el valor numérico de la opción — el agente prefiere sistemáticamente el número más alto ofrecido (más robo, más daño, etc.), sin lógica adicional en este tramo.

### `YES`/`NO` en `ACTIVATE` / `IS_FIRST` / `COIN_HEAD` (líneas 5977–5998)

```python
elif o.type == OptionType.YES:
    score = 1
    if context == SelectContext.ACTIVATE:
        score = 10
        if _meowth_skip_fetch:
            score = -1
    elif context == SelectContext.IS_FIRST:
        score = -1
        we_go_first = True
    elif context == SelectContext.COIN_HEAD:
        score = 2
elif o.type == OptionType.NO:
    if context == SelectContext.IS_FIRST:
        score = 2
        we_go_first = False
    elif context == SelectContext.ACTIVATE and _meowth_skip_fetch:
        score = 10
```

- `ACTIVATE` (confirmar activar una habilidad/efecto opcional, p.ej. *Last-Ditch Catch* de Meowth ex): por defecto `YES=10` gana sobre cualquier otro valor bajo — el agente activa habilidades opcionales salvo excepción explícita. `_meowth_skip_fetch` (calculado antes del bucle) invierte la preferencia a `NO=10` cuando buscar con Meowth ex no aporta nada (p.ej. no queda ningún Supporter útil en el mazo).
- `IS_FIRST` ("¿quieres ir primero?"): la puntuación es contraintuitiva a propósito — `YES` vale `-1` y `NO` vale `2`, así que el agente **elige ir segundo** (más robo de carta en el primer turno propio compensa perder la iniciativa de ataque); en ambos casos actualiza el global `we_go_first`, que condiciona docenas de reglas de turno 1/2 en el resto del archivo.
- `COIN_HEAD`: `YES=2` — el agente siempre llama "cara" en los volados que se lo piden (no hay información para decidir, así que la elección es arbitraria pero determinista).

### `OptionType.CARD`: obtención de la carta y `energy_count` (líneas 5999–6005)

```python
elif o.type == OptionType.CARD:
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is not None:
        energy_count = 0
        if isinstance(card, Pokemon):
            energy_count = len(card.energies)
```

`get_card` resuelve la opción `CARD` (que solo trae `area`/`index`/`playerIndex`) al objeto real de carta/Pokémon en esa zona del tablero, usando el helper de la línea ~861 (doc 04). A partir de aquí, `card.id` es el eje de todas las ramas por tipo de contexto.

---

### `SWITCH` / `TO_ACTIVE` — promover nuestro propio Pokémon (líneas 6006–6465)

`o.playerIndex == my_index` cubre dos disparadores distintos con la misma lógica de puntuación: promover tras un KO del activo, y elegir a quién retirar-y-promover voluntariamente. El objetivo es siempre "¿qué Pokémon de banca sube al puesto activo?".

#### Sacrificio dirigido para Mega Lucario ex (líneas 6007–6031)

```python
if o.playerIndex == my_index and _lucario_sac_context:
    if _tapu_sac_priority:
        if card.id == Tapu_Bulu: score = 6000
        elif card.id == Applin: score = 5500
        elif card.id == Chikorita: score = 5000
        else: score = 100
    else:
        if card.id == Applin: score = 6000
        elif card.id == Chikorita: score = 5500
        elif card.id == Tapu_Bulu: score = 200
        else: score = 100
```

Cuando `_lucario_sac_context` está activo (definido antes del bucle, doc 09) el objetivo no es promover al mejor atacante sino **entregar el mínimo de premios posible** a un Mega Lucario ex que va a noquear igual: por defecto se sacrifica primero `Applin` y `Chikorita` (1 premio, básicos prescindibles) y se reserva `Tapu_Bulu`; solo si `_tapu_sac_priority` marca que Tapu Bulu es más prescindible en este matchup concreto se invierte el orden.

#### Cálculo de "¿puede atacar?" con y sin adjunte (líneas 6032–6069)

```python
_can_attack_now = (card.id in MAIN_ATTACKERS
    and _can_attack_eff(card.id, energy_count))
...
if (not _can_attack_now and _grass_attachable_switch
        and (not state.energyAttached or _forced_promote_switch)):
    _pkmn_eff_plus1 = energy_count + _grass_attach_unit()
    if card.id == Hydrapple_ex: _can_attack_with_attach = (_pkmn_eff_plus1 >= 2)
    elif card.id == Dipplin: _can_attack_with_attach = True
    elif card.id == Teal_Mask_Ogerpon_ex: _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
    elif card.id == Tapu_Bulu: _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)
    elif card.id == Fezandipiti_ex: _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
    elif card.id == Meganium: _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)

if _can_attack_now: score = 500
elif _can_attack_with_attach: score = 350
else: score = 100
```

Base de puntuación: un candidato que **ya puede atacar** este turno (energía efectiva suficiente, vía `_can_attack_eff`/`ATTACK_ENERGY_REQ`) vale 500; uno que podría atacar **si además se le adjunta la energía Planta de la mano este turno** vale 350 (solo se evalúa si aún no se adjuntó energía, o si es una promoción forzada por activo vacío `_forced_promote_switch`); cualquier otro vale 100 de base. Encima se suma `card.hp // 10` y `energy_count` — a igualdad de capacidad de ataque, se prefiere el cuerpo más grande y más cargado.

#### Negación de premios y confusión (líneas 6076–6094)

- `op_prize <= 2 and _can_attack_now and prize_count(card) <= 1` → `+3000`: si al rival le faltan ≤2 premios para ganar, subir un atacante de **1 premio** que ya pueda pegar es decisivo — evita que el próximo KO rival cierre la partida regalando 2 premios de un ex. Nunca penaliza a un ex si es el único que puede atacar.
- `is_confused and _can_attack_now and _conf_is_matchup_attacker(card.id)` → `+2000`: al curar confusión del activo (p.ej. tras retirarlo), prioriza subir un atacante del matchup que YA puede pegar (p.ej. Dipplin vs Crustle) por encima de un muro inactivo este turno.

#### HP como muro cuando nadie puede atacar (líneas 6096–6104)

Si ni `_can_attack_now` ni `_can_attack_with_attach`: `score += card.hp // 5` (el doble de peso que el bono base de HP) y, si se conoce el daño estimado del rival (`estimated_op_damage`), `+80` si el candidato sobrevive al golpe o `-20` si no — preferir un muro que aguante sobre uno que cae igual.

#### Bonos por especie (líneas 6106–6189)

| Carta | Bono | Condición |
|---|---|---|
| `Hydrapple_ex` | `+4000` | `_teal_wall_pivot`: pivote defensivo, subir el muro de 330 HP aunque no ataque aún |
| `Hydrapple_ex` | `+60`, `+min(syrup_dmg//10,30)` si ataca, `+250` si atacaría tras adjunte, `+500` si `_cm_use_ex` | Crustle+Mega Kangaskhan: usar nuestros ex contra el Mega y reservar no-ex para Crustle |
| `Tapu_Bulu` | `+50` si ataca; `-500` si `_cm_use_ex` (reservarlo para Crustle); `+80` vs inmune-a-ex/Crustle; `+120` vs Cornerstone | |
| `Teal_Mask_Ogerpon_ex` | `+30`; `+500` si `_cm_use_ex` y puede atacar | |
| `Dipplin` | `+15`; `+40` vs inmune-a-ex; `+5000` combo específico (Crustle, activo ya retirado, sin energía, con Night Stretcher en mano y Planta en descarte) | |
| `Meganium` | `+120` si puede atacar vs Crustle/inmune-a-ex, si no `-80` | |
| `Meowth_ex` / `Fezandipiti_ex` / `Chikorita` / `Bayleef` / `Applin` | `-100` / `-100` / `-60` / `-50` / `-70` | Penalización base: son cuerpos débiles o de soporte, mal candidato para promover salvo que otras reglas los prioricen |

Regla vs Crustle sin nadie que ataque (líneas 6173–6189, **log 86607718 turno 2**): si nadie puede atacar al muro, `Teal_Mask_Ogerpon_ex` (+300, 210 HP) sube como muro desechable y `Tapu_Bulu` (-300) se reserva en banca para cargarlo a salvo como el atacante clave que sí noquea a Crustle.

#### Debilidad del activo rival y lookahead (líneas 6190–6206)

Si el `card` candidato tiene debilidad al tipo del activo rival: `-250`. Además, usando `_op_best_damage_vs`/`_op_counter_threat_vs` (helpers de amenaza, doc 07): si el rival podría noquearlo el próximo turno, `-SCORE_LOOKAHEAD_PROMOTE_KO`; si el daño rival es ≤40% de su HP (relativamente seguro), `+SCORE_LOOKAHEAD_PROMOTE_SAFE`.

#### Bonos de evolución con `Forest_of_Vitality` disponible (líneas 6207–6287)

Con `_forest_available` (estadio en juego o en mano), promover `Applin`/`Chikorita`/`Dipplin`/`Bayleef` con la evolución siguiente ya en mano suma un bono grande (300–600 según cuán completa está la línea, con extras de +100–150 si además hay energía Planta lista o energía repartida en banca, y +100 si la mega-evolución completa — Meganium — también es alcanzable). La idea: subir el eslabón que se va a evolucionar YA este mismo turno, no solo al que mejor pega ahora.

#### Bloqueo de duplicar la línea Chikorita en banca (líneas 6288–6304)

```python
if card.id in (Chikorita, Bayleef, Meganium):
    _meg_designated_attacker = False
    if (card.id == Meganium and len(card.energies) >= 4 and
            (op_is_crustle_deck or op_is_cornerstone_deck)):
        ...
        if not _meg_other_atk_p:
            _meg_designated_attacker = True
    if _meg_designated_attacker:
        score += 400
    elif bench_count > 1:
        score = -10000
```

Salvo que Meganium cargado (≥4 energía) sea el **atacante designado** vs Crustle/Cornerstone sin alternativa mejor en banca (entonces `+400`), promover cualquier miembro de la línea Chikorita cuando hay más de un Pokémon en banca es un veto casi total (`-10000`): esa línea es el motor de energía, no el activo — sacarla del banco corta el acelerador Wild Growth.

#### Inmunidades y matchups específicos del activo rival (líneas 6305–6377)

- Rival con activo inmune a ex/habilidad (`op_has_ex_immune_active`/`op_has_ability_immune_active`): `+150`/`+180` a cuerpos no-ex/no-habilidad, `-80`/`-100` a los nuestros (Crustle anula el daño ex, ciertos activos anulan habilidades).
- `op_is_fire_deck`: `Hydrapple_ex` que ataca `+40`. `op_is_control_deck`: `Tapu_Bulu` que ataca `+50`.
- Activo rival == `Drednaw`: prioriza `Meganium`/`Dipplin` que atacan (+250/+200/+180/+150) y penaliza subir nuestros ex (`Hydrapple_ex`, `Tapu_Bulu` `-150`).
- Activo rival == `Sylveon`: prioriza `Tapu_Bulu`/`Meganium`/`Dipplin` en ese orden (+280…+150) y penaliza cualquier `OUR_EX_IDS` (`-200`).
- `neutralization_zone_active` y el activo rival NO es ex/mega: mismo patrón que Sylveon con valores algo menores (+250…+140, `-200` a nuestros ex) — la Zona de Neutralización anula habilidades, así que atacar con no-ex es más fiable.

#### `plan.attacker` y evoluciones en mano (líneas 6379–6396)

- `o.index == plan.attacker - 1` → `+120`: coincide con el atacante que el `AttackPlan` (doc 07) ya identificó como el mejor.
- Con la siguiente evolución en mano: `Dipplin`+`Hydrapple_ex` en mano `+80`; `Bayleef`+`Meganium` en mano `-30` (mejor completar la evolución antes de exponer a Bayleef); `Applin`+`Dipplin` en mano `+60` (o `+20` sin Forest+Hydrapple); `Chikorita`+`Bayleef` en mano `-30` con Forest+Meganium disponible, si no `+5`.

#### Estado alterado y muro vs Crustle activo (líneas 6397–6423)

`has_condition` (activo con condición especial) suma `+50` (subir a un candidato sano). Contra `op_has_ex_immune_active` (Crustle activo): un atacante no-ex que SÍ puede atacar y dañar gana con `+6000` sobre cualquier otro; si ningún no-ex puede atacar, se prioriza un ex como muro, dando preferencia a los que ya tienen energía (`+3000 + energy_count*10`) y, entre los sin energía, a `Teal_Mask_Ogerpon_ex` (`+2500`) sobre el resto (`+2000`).

#### `_best_promote_card` y casos Mega Lucario / refresco de mano (líneas 6424–6465)

- `card is _best_promote_card` (precalculado antes del bucle según el daño efectivo contra el activo rival) → `+4000`, el bono decisivo genérico.
- `_lucario_ko_prefer_basic` (vs Mega Lucario sin atacante en banca): fuerza `score = 9000` para `Applin`, `8500` para cualquier básico, `8000` para `Dipplin` — preferir sacrificar de forma barata en premios antes que exponer un cuerpo evolucionado.
- `_refresh_promote_prefer_basic` (**log 86345562 paso 55**): si ningún cuerpo puede atacar y hay Lillie's Determination disponible para refrescar, sube un básico no-ex (`Applin` `6000`, otro básico `5500`) en vez de un ex de 2 premios — conserva los ex y su energía a salvo en banca.

---

### `SWITCH` / `TO_ACTIVE` — objetivo de Boss's Orders sobre el rival (líneas 6466–6868)

Rama `else` (línea 6466) del mismo contexto: cuando `o.playerIndex` es del **rival**, la opción representa a qué Pokémon de su banca "gustear" (subir al activo con Boss's Orders). El objetivo cambia por completo: ya no se trata de promover lo mejor propio, sino de elegir el mejor blanco rival — noquearlo si se puede, o si no, trabarlo (que no pueda retirarse ni atacar).

#### Vetos inmediatos (líneas 6468–6472)

```python
if card.id in DUNSPARCE_IDS:
    score = -100000
```

Nunca gustear un Dunsparce (ids 65/305): no aporta nada ni como KO ni como estorbo.

#### Modo estorbo cuando nuestro activo no puede atacar (líneas 6473–6516)

```python
elif _active_cant_attack_this_turn or _sel_active_cant_attack:
    _rc_target = RETREAT_COST.get(card.id, 0)
    if _rc_target <= 0:
        score = -100000
    else:
        _stall_diff = _rc_target - _target_energy_cnt
        if op_has_latias_ex and <target es básico>:
            _stall_diff = 0
        if _stall_diff >= 1:
            score += 500 + _stall_diff * 100
            if card.id in THREAT_PREEVO_IDS or card.id in EX_PREEVO_IDS:
                score -= 50
        else:
            score -= 200
```

Si nuestro activo no puede atacar este turno, Boss's Orders se usa como **estorbo**: se prioriza al objetivo con mayor coste de retirada neto (coste − energía cargada) — cuanto más le cueste al rival reposicionarse, mejor. Coste de retirada 0 es veto total (el rival lo cambia gratis). `op_has_latias_ex` anula el estorbo sobre básicos porque la habilidad de Latias ex les permite retirarse gratis. Desempate: evita clavar la pre-evolución del atacante ex principal rival (`THREAT_PREEVO_IDS`/`EX_PREEVO_IDS`, p.ej. Riolu antes de Mega Lucario ex) porque dejarla activa le permite evolucionar y atacar desde ahí.

#### Modo ofensivo: cálculo de `_boss_can_ko` (líneas 6517–6589)

Cuando nuestro activo SÍ puede atacar, primero se calcula si el ataque actual (o el mejor atacante de banca que pueda entrar) noquearía al objetivo:

```python
if _boss_atk.id == Hydrapple_ex and _boss_atk_after >= 2:
    _boss_our_dmg = 30 + 30 * total_grass
elif _boss_atk.id == Dipplin and _boss_atk_after >= 1:
    _boss_our_dmg = 20 * bench_count
elif _boss_atk.id == Teal_Mask_Ogerpon_ex and _boss_atk_after >= 3:
    ...
elif _boss_atk.id == Tapu_Bulu and _boss_atk_after >= 4:
    _boss_our_dmg = 220
elif _boss_atk.id == Fezandipiti_ex and _boss_atk_after >= 3:
    _boss_our_dmg = 100
elif _boss_atk.id == Meganium and _boss_atk_after >= 4:
    _boss_our_dmg = 140
elif _boss_atk.id == Bayleef and _boss_atk_after >= 2:
    _boss_our_dmg = 60
```

Reproduce las fórmulas de daño de cada ataque propio (mismas que en el `AttackPlan`, doc 02/07), teniendo en cuenta si aún se podría adjuntar una energía Planta este turno (`_boss_atk_after`). Después aplica ×2 por debilidad Planta / −30 por resistencia Planta (salvo `Fezandipiti_ex`, cuyo ataque no es de tipo Planta), y anula el daño (`_boss_eff_dmg = 0`) si el objetivo es inmune a ex y atacamos con un ex, o inmune a habilidad y atacamos con un atacante de habilidad. Si el daño efectivo ≥ HP del objetivo → `_boss_can_ko = True`. Si el activo actual no noquea, además revisa (líneas 6576–6588) si retirándolo y promoviendo desde banca (`_bench_attacker_can_ko`) sí se lograría el KO, considerando la energía Planta gastada en la propia retirada.

#### Tier de KO por etapa evolutiva (líneas 6590–6620)

```python
if _boss_can_ko:
    _bt_has_e = _boss_tgt_energy >= 1
    _bt_is_exmega = ...
    if _bt_is_exmega: _boss_tier = 8 if _bt_has_e else 7
    elif _boss_tgt_is_stage2: _boss_tier = 6 if _bt_has_e else 5
    elif _boss_tgt_is_stage1: _boss_tier = 4 if _bt_has_e else 3
    else: _boss_tier = 2 if _bt_has_e else 1
    score += _boss_tier * 3000
```

Cuando SÍ se puede noquear, el objetivo se ordena por tier: ex/mega con energía (8, `24000`) > ex/mega sin energía (7) > stage2 con energía (6) > stage2 sin energía (5) > stage1 con energía (4) > stage1 sin energía (3) > básico con energía (2) > básico sin energía (1). Cargar energía en el objetivo antes del KO también es un desperdicio para el rival, de ahí el peso extra por "con energía".

**Log 86504664 paso 94** (partida perdida vs Archaludon ex): una pre-evolución de línea ex ya cargada (`EX_PREEVO_IDS`, p.ej. Duraludon antes de evolucionar a Archaludon ex) recibe un tier efectivo boosteado a 19500 — por encima de cualquier objetivo no-ex (tier 6 = 18000) pero por debajo de un ex real en juego (tier 7–8) — porque noquearla borra un futuro atacante ex de 2 premios antes de que exista.

#### Modo estorbo sin KO posible (líneas 6621–6647)

Si no hay KO disponible pero el activo sí puede atacar (Boss's Orders "desperdiciado" en estorbo puro): mismo criterio de coste de retirada neto que el modo defensivo (`+diff*100`, desempate `-50` en pre-evos de amenaza). Bono adicional `+200` si el objetivo elegido es exactamente el activo actual del rival, sin energía, y el objetivo SÍ tiene energía (curioso caso límite del propio `card` == activo rival).

#### Reglas de matchup dirigidas por línea evolutiva (líneas 6649–6793)

Tres bloques casi idénticos, uno por arquetipo rival detectado (`op_has_dragapult_or_op_has_dreepy_line`, `op_is_typhlosion_deck`/`op_has_ethan_preevo`, `op_is_alakazam_deck`), cada uno mapeando la línea evolutiva completa del rival (fase 2 ex → fase 1 con habilidad de motor → básico):

| Rol en la línea | Con KO | Sin KO, sin energía para retirarse | Sin KO, con energía |
|---|---|---|---|
| Fase 2 ex (Dragapult ex / Typhlosion / Alakazam ex) | `+1200` | — | `+800` |
| Fase 1 motor (Drakloak / Quilava / Kadabra) | `+1000` | `+700` (queda CLAVADO, retrasa la evolución) | `+300` (se repositiona gratis) |
| Básico (Dreepy / Cyndaquil / Abra) | `+400` | `+500` (clavado, más estorbo que la fase 1 con energía) | `+200` |

La razón estratégica es idéntica en los tres casos: la fase 1 (Drakloak/Quilava/Kadabra) es la pieza que **habilita** al atacante final del rival mediante su habilidad de motor (roba/busca cartas); clavarla sin energía retrasa toda la línea, por eso puntúa más que clavar solo al básico cuando ninguno da KO.

#### Reglas genéricas por tier cuando no aplica ningún matchup dirigido (líneas 6794–6856)

Con KO: `_boss_tgt_is_ex`+energía `+1100`, ex sin energía `+1000`, stage2+energía `+900`, stage2 `+850`, stage1+energía `+700`, stage1 `+600`, básico con nombres específicos (`THREAT_PREEVO_IDS` `+550`, `Budew` `+500`, `Munkidori` `+450`, `Snorunt` `+400`, `Dwebble_*` `+380`, `Dreepy` `+350`, básico con energía `+300`, básico sin energía `+200`). Sin KO, la misma jerarquía pero con valores mucho menores (`+250`…`+100`), añadiendo `Froslass` (`+220`), `Drakloak` (junto a Dreepy, `+180`) y `Dwebble_*` (`+178`) como estorbos con nombre propio: son piezas que, aunque no mueran, interesa sacar del banco.

#### Vetos finales (líneas 6857–6867)

- `op_is_crustle_deck and card.id in (Dwebble_Grass, Dwebble_Fighting)` → `score = -100000`: contra Crustle, gustear un Dwebble concreto no sirve (el objetivo real es el propio Crustle o su soporte, no sus básicos intercambiables).
- `RETREAT_COST.get(card.id, 0) <= 0 and not _boss_can_ko` → `score = -100000`: regla general — un Pokémon de retirada gratis nunca es buen objetivo de estorbo (el rival lo cambia sin coste); solo vale la pena gustearlo si es un KO real.

---

### `SETUP_ACTIVE_POKEMON` (líneas 6868–6883)

```python
if card.id == Teal_Mask_Ogerpon_ex: score = 100
elif card.id in (Chikorita, Applin) and hand_counts.get(card.id, 0) >= 2: score = 7
elif card.id == Applin: score = 5
elif card.id == Chikorita: score = 3
elif card.id == Meowth_ex: score = 0
else: score = 1
```

Elección del Pokémon activo inicial (preparación de partida). `Teal_Mask_Ogerpon_ex` domina de forma aplastante (210 HP, tanque que puede sobrevivir al primer ataque rival sin información previa del matchup). Entre básicos de la línea Meganium/Hydrapple, se prefiere tener un duplicado en mano (`>=2` copias, para no depender de una sola vía de evolución) y, si hay que elegir uno solo, `Applin` (línea Hydrapple ex, más autónoma) sobre `Chikorita`. `Meowth_ex` puntúa `0` — es débil como activo inicial (su valor está en la habilidad al bajarlo, no en resistir en el puesto activo).

### `SETUP_BENCH_POKEMON` (líneas 6884–6945)

Puntuación de qué básicos bajar a la banca inicial:

| Carta | Base | Ajustes |
|---|---|---|
| `Chikorita` | `8` | `10` vs mazo fuego/agresivo (necesita el motor de energía cuanto antes) |
| `Applin` | `7` | `4` si `op_bench_snipe_threat` (rival puede snipear la banca); `8` vs fuego/agresivo |
| `Teal_Mask_Ogerpon_ex` | `6` | `7` vs mazo fuego |
| `Meowth_ex` | `-1` | Se evita bajarlo en el setup salvo mediante Ultra Ball/otras búsquedas más adelante |
| `Fezandipiti_ex` | `2` (solo si es el único Pokémon en mano) o `-1` | `0` si `op_has_froslass`; `1` si `op_bench_snipe_threat`; con más de un Pokémon en mano se reserva (`-1`) — bajarlo de salida expone un ex de 2 premios débil a Lucha antes de conocer el activo rival |
| `Tapu_Bulu` | `3` (Meganium en juego + rival inmune a ex, o Crustle) / `-1` en otro caso | |
| `Pinsir` | `3` (Crustle/Sylveon/Cornerstone) / `2` (inmune a ex) / `-1` en otro caso | |

La lógica de `Fezandipiti_ex` (líneas 6906–6928) es la más elaborada: cuenta cuántos Pokémon hay en la mano de setup y solo permite bajarlo si es la única opción, ya que revelar un ex de 2 premios débil a Lucha antes de ver el activo rival es un riesgo (crítico contra Mega Lucario ex, que aún no es detectable en esta fase).

---

### `TO_HAND` (líneas 6946–8324) — búsquedas de carta hacia la mano

Puntuación base común: `score = 200 - hand_counts[card.id] * 100` (línea 6947) — penaliza fuertemente buscar duplicados de algo que ya está en mano. A partir de ahí, `select.effect.id` determina qué origen de búsqueda es (Bug Catching Set, Poke Pad, Night Stretcher, Ultra Ball, habilidad de Meowth ex, Dawn, o un `else` genérico) y cada uno tiene su propia escalera de valores por carta.

#### Bug Catching Set (líneas 6949–7094)

```python
is_bcs_selection = (select.effect is not None and select.effect.id == Bug_Catching_Set)
if is_bcs_selection:
    score = 100
    ...
```

Bug Catching Set busca cualquier Pokémon básico/evolución. La lógica repite el mismo patrón para ambas líneas de ataque (Chikorita→Bayleef→Meganium, Applin→Dipplin→Hydrapple ex): puntuación máxima (~800–1000) a la siguiente pieza que **completa la evolución de lo que ya está en campo** (p.ej. `Bayleef` cuando hay `Chikorita` en juego → `850`, `950` si además hay Forest y Meganium en mano), intermedia si la pieza anterior está solo en mano, y baja (20–50) si la línea ya está completa o el objetivo sería redundante. `Teal_Mask_Ogerpon_ex`/`Tapu_Bulu`/`Pinsir`/`Meowth_ex`/`Fezandipiti_ex` tienen sus propias condiciones puntuales (p.ej. Pinsir solo interesa `750` vs Crustle/Cornerstone). Al final (líneas 7089–7093) un bono `+100` si la mayoría de copias de esa carta están en la zona de premios (`ESTADO_PREMIO`) y solo queda ≤1 accesible — urgencia de recuperarla antes de perder acceso. La sección 7477–7484 añade una restricción final: vs Crustle/Cornerstone, si la carta no está en la lista de "válidas" para ese matchup (`Tapu_Bulu`, `Pinsir`, y con Crustle puro también la línea Meganium/Hydrapple sin Hydrapple ex mismo), la opción queda vetada (`score = -1`).

#### Poke Pad (líneas 7095–7217)

```python
elif select.effect is not None and select.effect.id == Poke_Pad:
    score = 10
    _our_first_turn_pp = ((state.turn == 1 and we_go_first) or
                          (state.turn == 2 and not we_go_first))
    if _our_first_turn_pp:
        ...
```

Poke Pad busca un Pokémon no-Rule-Box (básico o evolución) hacia la mano. En nuestro primer turno de partida, prioriza absolutamente completar la banca básica: `Applin` `2000` o `Chikorita` `1900` si aún no se tiene ninguno de los dos. Fuera del primer turno (líneas 7112–7216), la regla usa el **tablero actual** (`field_counts`), no la foto de inicio de turno, para poder recomendar la evolución de un Pokémon recién bajado este mismo turno (p.ej. un `Bayleef` que acaba de evolucionar habilita buscar `Meganium`, aunque no se pueda jugar hasta el próximo turno). Prioriza la evolución que completa una línea ya en juego (`Meganium` con `Bayleef` en banca `1000`; `Bayleef` con `Chikorita` en banca `850`/`950` con Forest+Meganium en mano; `Dipplin` con `Applin` en banca `800`/`920`) sobre traer básicos nuevos (`Chikorita`/`Applin` `800`/`650` si la banca tiene hueco).

#### Night Stretcher (líneas 7218–7469)

```python
elif select.effect is not None and select.effect.id == Night_Stretcher:
    score = 50
    if card.id == Basic_Grass_Energy:
        score = 300
        ...
```

Night Stretcher recupera del descarte un Pokémon **o** una energía básica. La energía Planta domina en varios escenarios especiales, en este orden de prioridad:

1. `_act_hyd_ripen` (`1300`): `Hydrapple_ex` activo que no llega a la energía efectiva para atacar y sin Planta en mano — recuperar energía para cargarlo vía *Ripening Charge* (habilidad) gana sobre cualquier otro objetivo.
2. `_ns_bench_charge_sel` (`950`): vs Crustle/Cornerstone, cargar un atacante de banca (`Tapu_Bulu`, `Teal_Mask_Ogerpon_ex`, `Hydrapple_ex`, `Meganium`) que aún no llega a su requisito de energía.
3. `_active_needs_energy` sin Planta en mano ni energía adjuntada (`900`).
4. `_act_og_can_teal_attack` (`900`): Ogerpon ex activo con <3 energía efectiva pero que llegaría a ≥3 con una Planta más (habilita *Teal Dance*) — cubre el combo retirar→promover Ogerpon→Night Stretcher→Teal Dance→atacar (**log 86583929 turno 4 vs Alakazam**).
5. Sin Planta en mano en general (`600`/`700` si tampoco se adjuntó energía este turno; `750` si además hay Ogerpon ex en banca).
6. Con Hydrapple ex en juego y poca energía total (`450`); con ≥3 copias en mano, se enfría a `100`.

Para Pokémon, repite el patrón de "completar la línea evolutiva ya en juego" visto en Poke Pad/Bug Catching Set, con valores propios por carta (`Hydrapple_ex` `980` si hay `Dipplin` en juego; `Meganium` `990` si hay `Bayleef`; etc.), y usa `_field_at_turn_start` (la foto de inicio de turno) en vez del tablero actual cuando NO hay Forest en juego — para no recomendar recuperar una pieza que aún no se podría jugar esta partida sin acelerador de energía.

#### Ultra Ball (líneas 7486–8009)

El bloque más largo de todo el tramo. Ultra Ball descarta 2 cartas de la mano y busca cualquier Pokémon; por eso su objetivo debe justificar el coste de descarte.

Banderas de contexto calculadas antes de puntuar cada carta (líneas 7490–7601):
- `hand_is_weak`: pocas opciones jugables y mano corta.
- `_ub_prefer_meowth_develop`: solo hay el activo en juego (banca vacía), nada jugable en mano, sin Lillie's en mano, Meowth ex y Lillie's siguen en el mazo → conviene traer `Meowth_ex` para refrescar la mano antes que cualquier atacante (**log 85850698 paso 5, GANADA vs Lucario**).
- `_t1_going_second_meowth` / `_t1_going_second_need_ogerpon` / `_t1_going_first_need_basic`: casos de primeros turnos sin banca ni básicos jugables en mano.
- `_dipplin_priority` (`_dp_lillie_played or _dp_anti_ex or _dp_hydra_line`): solo en tres casos concretos se prioriza `Dipplin`/`Hydrapple_ex` sobre `Meowth_ex` — (1) ya se jugó una Lillie's y **no** quedan más en el mazo, (2) matchup anti-ex y Dipplin ya podría atacar tras evolucionar, (3) hay Forest+Hydrapple ex en mano y se podría evolucionar y atacar (Syrup Storm) este mismo turno. **Log 86585073 turno 4 vs Marnie, GANADA**: haber jugado ya una Lillie's no basta si aún quedan copias en el mazo — Meowth ex conserva prioridad de refresco.

Puntuación de `Meowth_ex` como objetivo (líneas 7602–7669): cascada de hasta 9 condiciones que terminan en `score = 1000` (o `1250`/`1200`/`1150`/`1100` en casos más específicos) cuando refrescar la mano es la prioridad, y `10` cuando cede el turno a otra búsqueda (Watchtower en juego, ya hay Lillie's en mano, turno 1 yendo primero, ya hay 2 copias en juego, banca llena, o se cumple `_dipplin_priority`).

Resto de cartas objetivo, todas siguiendo "completar la línea evolutiva más cercana a jugarse este turno" con techos altos (900–1200) y pisos bajos (10–200) cuando la línea ya está completa o no aplica: `Teal_Mask_Ogerpon_ex` (hasta `800`, `1050` en turno 2 yendo segundo sin banca), `Meganium` (hasta `1000`), `Hydrapple_ex` (hasta `1200` si `Dipplin` activo ya evolucionaría y atacaría este turno; degradado a `≤40` contra rivales inmunes a ex — carta muerta en ese matchup), `Bayleef`/`Dipplin`/`Chikorita`/`Applin` (500–950 según cercanía de línea), `Tapu_Bulu` (hasta `850` con Meganium+inmune a ex), `Pinsir` (hasta `900` vs Crustle/Cornerstone), `Fezandipiti_ex` (`1050` si hubo KO el turno anterior y hay hueco en banca). Al cierre (líneas 7998–8009), bono `+150` si la mayoría de copias están en premios y penalización `-150` si ya hay una copia en mano (evitar duplicar innecesariamente pese al bono de línea).

#### Habilidad de Meowth ex — *Last-Ditch Catch* (líneas 8010–8068)

```python
elif select.effect is not None and select.effect.id == Meowth_ex:
    score = 50
    ...
    if (_win_via_boss_gust or _gust_2prize_via_boss) and card.id == Boss_Orders:
        score = 1300
    elif _meowth_devel_lillie and card.id == Lillie_Determination:
        score = 1250
    elif _hand_size_sel <= 2:
        if card.id == Lillie_Determination: score = 1200
        else: score = min(_sv, 100)
```

Busca un Supporter de mazo. Prioridad máxima (`1300`) a `Boss_Orders` cuando hay una jugada de victoria por gust ya identificada (`_win_via_boss_gust`/`_gust_2prize_via_boss`, doc 08); si no, `Lillie_Determination` domina en casi todos los escenarios de mano corta o activo bloqueado (`1200`–`1250`), porque su función es robar/refrescar; con mano ya sana (`>5` cartas) y sin atacante fuerte en juego, cae a `800`–`1000`; con atacante fuerte ya en juego, se usa directamente `_supp_values` (la valoración genérica de Supporters del bloque 08/09), con `+100` extra a `Boss_Orders` vs Crustle.

#### Dawn (líneas 8069–8239)

Mismo patrón estructural que Bug Catching Set/Ultra Ball (completar la línea evolutiva más avanzada disponible), aplicado a la búsqueda de Dawn (probablemente roba 2 y descarta algo — ver doc 09 para el efecto completo). Techos por carta: `Meganium` `1000`, `Bayleef` `900`/`970`, `Hydrapple_ex` `980`, `Dipplin` `950`, `Applin` `830`, `Teal_Mask_Ogerpon_ex` `500`, `Tapu_Bulu`/`Fezandipiti_ex`/`Meowth_ex` `300`–`600` según matchup, `Basic_Grass_Energy` `400` si aún no se adjuntó energía, `Forest_of_Vitality` `600` si no hay estadio en juego ni en mano. El `else` final (línea 8236) cubre cualquier otra carta con `50 - hand_counts*30`.

#### Rama genérica / búsquedas sin efecto reconocido (líneas 8240–8324)

Cuando `select.effect` no coincide con ninguno de los anteriores (p.ej. Lana's Aid, u otro efecto de búsqueda general), se aplican bonos/penalizaciones simples y más modestos (±50 a ±200) siguiendo la misma idea de "completar línea evolutiva no duplicada" sin la granularidad de las ramas específicas.

Excepción final (líneas 8312–8324, matchup Cubchoo): para `Night_Stretcher`/`Lanas_Aid`, si el rival es `op_is_cubchoo_deck`, se fuerza recuperar solo `Basic_Grass_Energy` (`max(score, 900)`) y se vetan (`-1`) los objetivos Pokémon — el ataque de Cubchoo deja al activo sin poder atacar el próximo turno, así que ese turno conviene recargar energía en vez de recuperar un Pokémon.

---

### `DISCARD` (líneas 8325–8673)

Puntuación de qué carta descartar al pagar un coste (Ultra Ball, mano máxima, etc.). El patrón se invierte respecto a `TO_HAND`: aquí valores **altos significan "descartable sin problema"** y bajos significan "proteger". Banderas previas:
- `_has_recovery`: hay Night Stretcher/Lana's Aid en mano o mazo (permite descartar más libremente porque se puede recuperar después).
- `_protect_last_supporter` / `_protect_refresh_supporter`: aún no se jugó Supporter este turno y queda ≤1 en mano — proteger el único Supporter disponible.
- `_teal_dance_possible`: Ogerpon ex en juego/jugable + energía Planta en mano + objetivo válido para Teal Dance — condiciona cuánta energía Planta es "sobrante".

Ejemplos representativos de la escalera por carta:
- `Basic_Grass_Energy`: descartable según excedente en mano (`35`–`92` sin Teal Dance posible; `2`–`85` con Teal Dance posible, más conservador porque cada energía extra alimenta el ataque).
- `Meganium`/`Bayleef` ya en juego: muy descartables (`85`–`95`, duplicado inútil); en mano cerca de completarse: casi intocables (`3`).
- `Fezandipiti_ex`: veto total (`-10000`) si hubo KO el turno anterior y hay hueco en banca — se necesita para bajarlo y activar su habilidad tras el KO.
- `Boss_Orders`/`Lillie_Determination`/`Dawn`/`Lanas_Aid`: protegidos (`2`–`22`) mientras sean el único Supporter disponible sin jugar; entre protegidos, Lillie's se protege por encima de Boss's (cae Boss's primero si hay que sacrificar uno).
- `Night_Stretcher`: veto (`-1`) si el único objetivo recuperable sería una energía básica que ya no se puede jugar este turno (`state.energyAttached` ya True) — evita malgastar la carta.
- `Unfair_Stamp`: veto total (`-10000`) — nunca se descarta esta carta cuando hay alternativa.

---

### `RECOVER_SPECIAL_CONDITION` / `AFFECT_SPECIAL_CONDITION` / `ATTACH_FROM` (líneas 8674–8683)

```python
elif context == SelectContext.RECOVER_SPECIAL_CONDITION:
    if hasattr(card, 'id'):
        score = 50
elif context == SelectContext.AFFECT_SPECIAL_CONDITION:
    score = 50
elif context == SelectContext.ATTACH_FROM:
    score = energy_score(card, o.area == AreaType.ACTIVE)
```

Los dos primeros contextos (curar/afectar una condición especial) no tienen lógica diferenciada en este tramo: cualquier candidato válido puntúa `50` (decisión casi neutra, delegada a que el motor solo ofrezca opciones legales). `ATTACH_FROM` (elegir el objetivo de un adjunte inducido por efecto, p.ej. *Ripening Charge* eligiendo a quién mover energía) reutiliza directamente `energy_score` — la misma función de valoración de adjunte de energía usada en el contexto `ATTACH` normal (doc 10), pasando si el candidato es el activo (`o.area == AreaType.ACTIVE`).

## Interacciones

- Lee (sin recalcular) casi todo el estado construido en los bloques previos de `agent()`: `field_counts`/`hand_counts`/`discard_counts` (doc 05), `op_is_*_deck`/`op_has_*` (doc 06), `plan` (`AttackPlan`, doc 07), la escalera de Boss's Orders `_supp_values`/`_win_via_boss_gust`/`_gust_2prize_via_boss` (doc 08), banderas de Supporters/decisión como `_meowth_devel_lillie`, `_meowth_skip_fetch`, `_lucario_sac_context`, `_tapu_sac_priority`, `_cm_use_ex`, `_teal_wall_pivot`, `_lucario_ko_prefer_basic`, `_refresh_promote_prefer_basic`, `_best_promote_card`, `op_bench_snipe_threat` (doc 09), y helpers de energía como `_can_attack_eff`, `_grass_mult`, `_grass_attach_unit`, `ATTACK_ENERGY_REQ` (doc 02/10).
- Usa el sistema de creencia `CARTAS_ACTIVAS_EN_MAZO`/`ESTADO_MAZO`/`ESTADO_PREMIO` (doc 03) para decidir urgencia de búsqueda (¿quedan copias accesibles en el mazo?) en casi todas las ramas de `TO_HAND`.
- Los valores altísimos asignados aquí (hasta `24000` en el tier de KO de Boss's Orders, o `-100000` en vetos) conviven con los de los demás bloques del bucle (`PLAY`, `ATTACH`, `RETREAT`, `ATTACK`); la comparación final entre TODAS las opciones ofrecidas por el motor ocurre recién al terminar el bucle completo (finalización, doc 15), así que estos números están calibrados para no chocar con las escalas usadas en esos otros bloques.
- El contexto `SWITCH`/`TO_ACTIVE` es el único de este tramo que sirve **dos** propósitos con la misma rama de código (promover propio vs gustear rival), diferenciados por `o.playerIndex`.

## Reglas derivadas de partidas

- **log 86607718 (turno 2, vs Crustle)** — líneas 6173–6189: al promover cuando nadie puede atacar al muro, subir `Teal_Mask_Ogerpon_ex` como muro desechable y reservar `Tapu_Bulu` en banca.
- **log 86345562 (paso 55)** — líneas 6450–6465: preferir promover un básico de 1 premio (`Applin`) sobre un ex de 2 premios cuando nadie puede atacar y hay Lillie's Determination para refrescar.
- **log 86504664 (paso 94, PERDIDA vs Archaludon ex)** — líneas 6606–6620: al poder noquear, una pre-evolución energizada de una línea ex (`EX_PREEVO_IDS`) es objetivo prioritario de Boss's Orders (tier efectivo boosteado a 19500).
- **log 85850698 (paso 5, GANADA vs Lucario)** — líneas 7521–7546: con banca vacía y sin básico jugable en mano, la búsqueda de Ultra Ball debe traer siempre `Meowth_ex` en vez de `Ogerpon_ex`.
- **log 86339167 (paso 23, PERDIDA vs Mega Starmie)** — líneas 7612–7630: si ya hay una Lillie's Determination en mano, Ultra Ball no debe buscar `Meowth_ex` (redundante); mejor buscar una evolución útil.
- **log 86585073 (turno 4, vs Marnie, GANADA)** — líneas 7561–7571: haber jugado ya una Lillie's Determination no basta para privilegiar `Dipplin`/`Hydrapple_ex` sobre `Meowth_ex` en la búsqueda si aún quedan copias de Lillie's en el mazo.
- **log 86583929 (turno 4, vs Alakazam)** — líneas 7225–7242: recuperar Energía Planta con Night Stretcher para completar el combo retirar→promover Ogerpon ex→Night Stretcher→Teal Dance→atacar.
