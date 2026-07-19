# main.py — Análisis de amenaza y plan de ataque (líneas 1985–2900)

## Rol en el agente

Este bloque es el corazón táctico del agente: dentro del `if context == SelectContext.MAIN:` (línea 1985), primero hace un **pre-escaneo barato** de qué tipos de opción están disponibles este turno (¿puedo `PLAY` un Boss's Orders?, ¿puedo `RETREAT`?, ¿puedo `ATTACK`?) y luego ejecuta el **cálculo central del `AttackPlan`**: para cada Pokémon propio en juego (activo primero, banca después si hay retirada disponible) y cada objetivo rival, simula el daño de su mejor ataque, lo pondera con docenas de reglas específicas de matchup (inmunidades, cartas prioritarias, tipos de mazo rival) y se queda con la combinación `(atacante, objetivo, ataque)` de mayor puntaje en `best_score`. El resultado se guarda en el objeto global `plan` (`AttackPlan`, definido en líneas 391–402 y documentado en `main-02-core-calc-helpers.md`), que actúa de "pizarrón compartido": las fases posteriores del bucle de puntuación (adjunte de energía, retirada, ataque, Boss's Orders) **leen** `plan.attacker`/`plan.target`/`plan.attack_index`/`plan.remain_hp`/`plan.energy` en vez de recalcular la decisión, evitando contradicciones entre "qué energía cargo" y "quién ataca realmente".

Tras fijar el `best_score` inicial, el bloque encadena una larga serie de **overrides de pivote** (subir un Hydrapple ex de banca en vez de rematar con el activo, pivotar a un cuerpo de 1 premio para no regalar la partida, sacrificar premios de forma controlada, etc.), cada uno activado por condiciones de amenaza muy concretas (`active_ko_likely`, `active_hp_ratio`, `_hydra_wall_pivot`…) que fueron calculadas en el bloque anterior (líneas ~1477–1976, documentado en `main-06`). Estos overrides pueden **reescribir `plan.attacker`** aunque ya hubiera un `best_score` positivo, porque priorizan la supervivencia del cuerpo activo o la gestión de premios por encima del daño bruto. El bloque cierra con la detección de "activo estancado" (`_active_cant_attack_this_turn`), que alimenta la lógica de retirada obligatoria cuando ni siquiera hay forma probabilística de que el activo llegue a atacar este turno.

## Detalle por bloque

### Pre-escaneo de opciones disponibles (líneas 1985–2014)

```python
if context == SelectContext.MAIN:
    can_switch = False
    can_op_switch = False
    for o in select.option:
        if o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card is not None:
                if card.id == Boss_Orders:
                    can_op_switch = True
        elif o.type == OptionType.RETREAT:
            can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
```

El primer bucle (líneas 1988–1997) recorre `select.option` una vez para poblar tres banderas booleanas baratas:
- `can_op_switch`: `True` si `Boss's Orders` está jugable desde la mano este turno (relevante más abajo para saber si, al evaluar daño contra la banca rival, tiene sentido considerar objetivos que no sean el activo — sólo se puede "forzar" al rival a exponer un banca si tenemos Boss's disponible).
- `can_switch`: `True` si hay una opción `RETREAT` entre las opciones — es decir, si el motor nos permite retirar al activo ahora mismo (implica que la energía física adjunta ya cubre el coste de retirada).
- `can_attack`: `True` si hay una opción `ATTACK` disponible (variable declarada como global fuera de este bloque, línea 1973).

El segundo bucle (líneas 1999–2005) vuelve a recorrer `select.option` buscando específicamente la carta de ID `1123` (un objeto de intercambio/switch en mano, comentado en el código simplemente como carta con `id == 1123`); si está jugable, fuerza `can_switch = True` y marca `has_switch_card = True`. La razón de un segundo bucle separado (en vez de fusionarlo con el primero) es que ambas búsquedas necesitan `get_card(obs, AreaType.HAND, o.index, my_index)`, que sólo tiene sentido para opciones `PLAY`, pero cada una consulta un ID de carta distinto (`Boss_Orders` vs `1123`) con efectos colaterales distintos (`can_op_switch` vs `can_switch`/`has_switch_card`); mantenerlos separados evita mezclar condiciones y hace explícito que `has_switch_card` es una bandera derivada exclusivamente de la carta de intercambio, usada más adelante (línea 2502) para poner `_ret_cost = 0` (retirada gratuita) cuando se planifica una promoción de Hydrapple ex.

Después (líneas 2007–2014) se construyen las listas planas `my_cards` y `op_cards`: `[activo] + banca`, filtrando `None`. Estas listas son la base de **todos** los bucles de doble iteración `(i, my_pokemon)` × `(j, op_pokemon)` que siguen: el índice `i`/`j` sirve de índice "de posición" (0 = activo, 1..n = banca) reutilizado tal cual como `plan.attacker`/`plan.target`.

### Bucle principal de `best_score`: selección de atacante y objetivo (líneas 2016–2071)

```python
if state.turn >= 2 and len(my_cards) > 0 and len(op_cards) > 0:
    best_score = -1
    for i, my_pokemon in enumerate(my_cards):
        ...
        if i != 0 and not can_switch:
            break
```

El cálculo del plan sólo se ejecuta a partir del **turno 2** (`state.turn >= 2`, línea 2016) — en el primer turno no hay nada que atacar. `best_score` arranca en `-1` (línea 2017) para que cualquier combinación válida (puntaje ≥ 0) lo sustituya. El bucle exterior recorre `my_cards`; la condición `if i != 0 and not can_switch: break` (línea 2021–2022) es clave: **sólo se evalúan atacantes de banca (`i != 0`) si `can_switch` es `True`** (es decir, si retirarse es una opción real este turno); como `my_cards` está ordenado con el activo primero, `break` corta el bucle entero en cuanto se llega al primer Pokémon de banca sin poder retirarse, así que nunca se calculan planes "imposibles" de ejecutar en el turno actual.

Para cada `my_pokemon` se construye `attack_options`, una lista de tuplas `(energy_req, base_damage, attack_idx, colorless_ok)` con **como mucho un ataque por Pokémon** (líneas 2024–2054), replicando las fórmulas de `_attacker_base_damage` (documentadas en `main-02`) pero de forma inline para poder proyectar variantes con energía adicional:
- `Hydrapple_ex`: `syrup_dmg = 30 + 30 * _syrup_grass`, donde `_syrup_grass` es `total_grass` **más** una unidad de adjunte (`_grass_attach_unit()`) si hay una Grass básica en mano y `not state.energyAttached` (línea 2027–2031) — es decir, proyecta el daño asumiendo que este turno se adjunta energía si aún no se ha usado el adjunte manual. `colorless_ok = True`.
- `Dipplin`: `wave_dmg = 20 * bench_count` (línea 2034–2035), sin proyección de energía adicional porque su coste es fijo en 1.
- `Teal_Mask_Ogerpon_ex`: `leaf_dmg = 30 + 30 * (my_energy + op_active_energy)` (línea 2036–2042) — escala con la suma de energía propia **y del objetivo actual** (`op_cards[0]`, el activo rival), coherente con `_attacker_base_damage`.
- `Tapu_Bulu`: fijo `220` (línea 2043–2045).
- `Meganium`: fijo `140` (línea 2046–2048).
- `Fezandipiti_ex`: fijo `100`, `colorless_ok = True` (línea 2049–2051).
- `Pinsir`: fijo `100`, `attack_idx = 1` (línea 2052–2054) — a diferencia de los demás, que usan `attack_idx = 0`; refleja que el ataque relevante de Pinsir es el segundo de la carta.

El sub-bucle `for energy_req, base_damage, attack_idx, colorless_ok in attack_options:` (línea 2056) calcula `effective_energy = energy_count * _grass_mult()` (línea 2059–2063; recordar que `_grass_mult()` es un no-op según `main-02`, así que esto es sólo `len(my_pokemon.energies)`). Si `effective_energy < energy_req`, intenta **dos vías de "energía proyectada"** antes de descartar la opción:
1. **Adjunte manual disponible** (líneas 2065–2072): si hay una Grass básica en mano y `not state.energyAttached`, suma `_grass_attach_unit()` (1 o 2 según Meganium). Si con eso ya alcanza, marca `more_energy = True`; si no, `continue` (se descarta esa opción de ataque para este Pokémon).
2. **Night Stretcher desde banca** (líneas 2073–2082): sólo si `i != 0` (no aplica al activo — Night Stretcher recupera al **descarte**, no adjunta directamente al activo en este cálculo), hay `Night_Stretcher` en mano, hay una Grass básica en el descarte y `not state.energyAttached`. Si `effective_energy + _grass_attach_unit() >= energy_req`, marca `more_energy = True` y además `_ns_energy_recovery = True` (aunque esta última variable no se vuelve a leer explícitamente en el resto del bloque incluido en este documento — es informativa/reservada). Si tampoco alcanza, `continue`.

Si ninguna vía cubre el requisito, la tercera rama (`else: continue`, línea 2083–2084) descarta la opción de ataque directamente.

### Puntaje base por atacante y matchup (líneas 2086–2171)

Una vez confirmado que el ataque es viable (con o sin energía proyectada), se calcula `base_score` acumulando bonificaciones/penalizaciones **por identidad del atacante y del matchup**, todas antes de mirar el objetivo concreto:

- `my_is_ex = my_pokemon.id in OUR_EX_IDS` (línea 2086) y `_op_active_is_drednaw` (líneas 2088–2089) se calculan una vez para reutilizar en varias ramas.
- **`Hydrapple_ex`** (líneas 2090–2103): `base_score += 200` de base; `-2000` si el activo rival es inmune a Habilidad (`op_has_ability_immune_active`, porque Hydrapple depende de su Habilidad *Ripening Charge* para energía, aunque aquí el chequeo es sobre el ataque, es una penalización general de matchup); si el rival activo es `Drednaw`, estima `_syrup_dmg_est = 30 + 30 * total_grass` y si ese daño ya alcanzaría `>= 200` (el tope de daño que anula Drednaw, ver `main-02`), resta `3000` — evita que el agente insista en un ataque que la regla de Drednaw neutralizaría. Si no hay Drednaw: `+150` contra mazos de fuego (`op_is_fire_deck`), `+100` contra mazos agresivos (`op_is_aggro_deck`).
- **`Dipplin`** (líneas 2104–2113): `+50` base; `+1200` si el rival tiene un activo inmune a ex (`op_has_ex_immune_active`, p.ej. Crustle/Sylveon — Dipplin no es ex, así que puede pegarle sin que la inmunidad aplique); `+1500` si el rival es inmune a Habilidad; `+2500` si el activo rival es Drednaw (Dipplin, con daño basado en banca y no en energía, esquiva el tope de 200 de Drednaw con más margen).
- **`Tapu_Bulu`** (líneas 2114–2131): escalera de prioridad de matchup — `+2200` (y `+800` extra si específicamente el rival es `Sylveon`) si el rival es inmune a ex; `+2500` si es inmune a Habilidad; `-3000` si el rival es Drednaw (220 de daño fijo dispara el tope de Drednaw y se anula); `+800` contra mazos de fuego; `+500` contra mazos de control (`op_is_control_deck`) o Slowking (`op_is_slowking_deck`); si nada de eso aplica, `+100` de base genérica.
- **`Pinsir`** (líneas 2132–2141): `+50` base; `+1300`/`+1600` contra inmunidad a ex/Habilidad respectivamente; `+2300` contra Drednaw (100 de daño, lejos del tope 200, buena alternativa segura).
- **`Meganium`** (líneas 2142–2153): `+1500` (y `+2000` extra si el rival es `Sylveon`) contra inmunidad a ex; `-2000` contra inmunidad a Habilidad (Meganium depende de *Wild Growth*); `+3500` contra Drednaw (140 de daño fijo, seguro respecto al tope).
- **`Teal_Mask_Ogerpon_ex`** (líneas 2154–2157): `-100` de penalización base (su daño ya escala solo, no necesita empuje) y `-2000` si el rival es inmune a Habilidad.
- **`Fezandipiti_ex`** (líneas 2158–2163): `-2000` tanto si el rival es inmune a ex como si es inmune a Habilidad (su ataque *Cruel Arrow* de daño fijo no se ve favorecido especialmente por esos matchups, y probablemente compite peor que otros atacantes ahí).
- **Zona de Neutralización** (líneas 2165–2171): si `neutralization_zone_active`, penaliza `-3000` a cualquier atacante ex (`my_is_ex`) — su daño quedará anulado contra rivales sin "rule box" — y bonifica `+2000` a los no-ex, empujando al agente a preferir Tapu Bulu/Dipplin/Pinsir/Meganium mientras el estadio esté activo.

### Bucle interno de objetivos: daño, inmunidades y puntaje por Pokémon rival (líneas 2172–2412)

Por cada `op_pokemon` en `op_cards` (línea 2172), con el mismo patrón de corte que el bucle externo pero matizado: `if j != 0 and not can_op_switch and my_pokemon.id != Fezandipiti_ex: break` (línea 2176–2177) — los objetivos de banca sólo se consideran si podemos forzar el cambio (`can_op_switch`, es decir, Boss's Orders en mano) **o** si el atacante es `Fezandipiti_ex`, cuyo *Cruel Arrow* golpea directamente a la banca sin necesitar Boss's.

El cálculo de `damage` reimplementa, línea por línea, la cadena de `_our_effective_damage` (ver `main-02`) pero integrada en el bucle para poder acumular el `score` de decisión en el mismo paso:
1. Inmunidad ex (`EX_IMMUNE_IDS` + `my_is_ex` → `damage = 0`, líneas 2182–2183).
2. Zona de Neutralización sin rule box rival (líneas 2185–2188).
3. Inmunidad a Habilidad (`ABILITY_IMMUNE_IDS` + `OUR_ABILITY_IDS` → `damage = 0`, líneas 2190–2192).
4. `_drednaw_shell_active = (op_pokemon.id == Drednaw and damage > 0)` (línea 2194): se calcula pero el corte real (`damage >= 200 → 0`) se aplica más abajo (línea 2202–2203), **después** de aplicar debilidad/resistencia — a diferencia de `_our_effective_damage` en `main-02` donde el orden es el mismo (debilidad antes del tope Drednaw).
5. Debilidad/resistencia Planta, salvo `Fezandipiti_ex` (líneas 2196–2200): `×2` si `data.weakness == EnergyType.GRASS`, `-30` si `data.resistance == EnergyType.GRASS`.
6. Tope de Drednaw (línea 2202–2203).
7. Caso especial `Crustle_Fighting` a vida completa (líneas 2205–2210): si el golpe lo noquearía, se recorta a `hp - 10` y se marca `effective_ko_hp = op_pokemon.hp + 1` (una centinela que **nunca** se compara después dentro de este fragmento — es vestigial en este bloque, aunque el recorte de `damage` sí es funcional y evita computar un KO falso más abajo).

**Cálculo de `score`** (líneas 2212–2226): arranca en `score = pokemon_score(op_pokemon)` (valor "genérico" de la amenaza rival: `prize_count * 1000 + energías*150 + herramientas*100 + bonos de etapa`, ver `main-02`/glosario de `pokemon_score`). Casos:
- Si `damage <= 0` y el objetivo es inmune a ex, a Habilidad, o es el caparazón de Drednaw, o Zona de Neutralización bloqueando un ex: `score = -5000` — **veto fuerte**, nunca se elegirá atacar a un objetivo al que no se le puede hacer daño por estas razones.
- Si `op_pokemon.hp <= damage` (KO): `prize = prize_count(op_pokemon)` — se registran los premios que se ganarían.
- Si no hay KO: `score *= damage / max(1, op_pokemon.hp)` — el valor del objetivo se escala por la **fracción de vida que le quitaríamos**, así que golpear a un objetivo valioso sin noquearlo todavía puntúa, pero mucho menos que noquearlo.
- `score += base_score` (el ajuste de matchup calculado en la sección anterior).

**Bonos por especie rival "prioritaria"** (líneas 2228–2377): una larga cascada `if/elif` de IDs específicos (`Budew`, `Froslass`, `Munkidori`, `Snorunt`, `Dreepy`/`Drakloak`, `Dwebble_*`, objetivos `EX_IMMUNE_IDS` golpeables por un atacante no-ex, `Crustle_Fighting` dañado, `Ralts`/`Kirlia`, `Gardevoir_ex`, `Abra`/`Kadabra`, `Alakazam_ex`, `Slowking`/`Slowpoke`, `Duskull`/`Dusclops`, `Dusknoir`, `Zoroark_N`/`Zorua_N`, `Typhlosion`, `Cyndaquil`/`Quilava`, `Chewtle`, `Drednaw`, `EEVEE_IDS`, `Sylveon`), cada una con un bono si el golpe **noquea** (siempre mayor) y uno menor si sólo daña. Ejemplos representativos:
  - `Budew`: `+8000` si KO, `+3000` si sólo daño (línea 2228–2232).
  - `Froslass`: `+9000`/`+4000` (línea 2234–2238) — el mayor bono de KO de toda la lista, reflejando que Froslass suele ser una amenaza de Habilidad que conviene eliminar cuanto antes.
  - `Dreepy`/`Drakloak` (líneas 2252–2271): caso con comentario extenso (líneas 2254–2265) — normalmente `+6500` si KO, pero si el objetivo es específicamente `Drakloak` **y** `op_has_dreepy_line` (mazo Dragapult confirmado), sube a `+9800`. La razón documentada: sin este ajuste, noquear a `Budew` (30 HP, soporte) puntuaba más (`8000+3500+300=11800`) que noquear a `Drakloak` (Stage-1 a un paso de Dragapult ex, `6500+3000=9500`) usando el "snipe" gratuito de *Cruel Arrow* (Fezandipiti ex, daño fijo 100), y el agente disparaba mal contra Budew. `Cruel Arrow` nunca noquea al propio Dragapult ex (320 HP), así que este ajuste no interfiere con KOs de mayor premio.
  - `Sylveon`: `+9000`/`+4000`, sólo si `damage > 0` (línea 2373–2377) — es el bono más alto tras Froslass, coherente con ser el muro central del matchup Sylveon.

**Bono específico de Fezandipiti ex por etapa del objetivo** (líneas 2379–2397): si el atacante es `Fezandipiti_ex` y hay daño, se gradúa el bono de KO según la etapa evolutiva del objetivo: `+5000` si es Stage-2, `+4500` si es ex, `+3500` si no es Stage-1 (básico), `+3000` en el resto (Stage-1); si no hay KO pero `j == 0` (activo), `+500`. Esto modela que *Cruel Arrow* es más valioso cuanto más "cara" es la pieza rival que corta (matar un Stage-2 casi terminado es más disruptivo que matar un básico).

**Cierre de victoria y desempates finales** (líneas 2399–2413):
- `if my_prize <= prize: score = 50000` (línea 2399–2400) — **si este KO nos da los premios que faltan para ganar la partida**, el puntaje se fija a `50000`, un valor "techo" que domina cualquier otra consideración de la escalera (coherente con la convención de `main.md`: valores redondos altos = prioridades fijas de reglas de matchup, aquí la prioridad máxima posible: ganar ya).
- Si no gana pero hay KO (`prize > 0`): si `remaining_after_ko == 1` (al rival le quedaría exactamente 1 premio para ganar tras perder este Pokémon), `score += 4000` — prioriza dejar al rival "a un premio" cuando sea posible, presumiblemente porque estrecha la ventana de reacción del rival.
- `if i == 0: score += 220` (atacar con el propio activo, sin retirar, es ligeramente preferido a igualdad de lo demás) y `if j == 0: score += 300` (golpear al activo rival, no a la banca, también preferido a igualdad).
- `score += effective_energy` (línea 2412): desempate menor por energía ya invertida en el atacante — a igualdad de todo lo anterior, se prefiere el atacante con más energía acumulada (menos "desperdicio" de vidas útiles).

### Lookahead de intercambio (trade) tras el golpe (líneas 2414–2425)

```python
_la_return = _op_best_damage_vs(my_pokemon)
if _la_return > 0:
    if _la_return >= my_pokemon.hp:
        if my_pokemon.id in OUR_EX_IDS:
            _la_disrupt = _op_disruption_belief(op_state, False)
            score -= int(SCORE_LOOKAHEAD_EX_TRADE * (0.6 + 0.4 * _la_disrupt))
        else:
            score -= SCORE_LOOKAHEAD_KO_TRADE
    elif _la_return <= my_pokemon.hp * 0.4:
        score += SCORE_LOOKAHEAD_SAFE
```

Este es el único punto del bucle principal donde se mira **un turno hacia adelante**: `_op_best_damage_vs(my_pokemon)` (definida en línea 1480, fuera de este rango pero consumida aquí) estima el mejor daño que el activo rival podría infligirle a `my_pokemon` la próxima ronda, asumiendo que adjunta una energía más (`assume_attach=True` por defecto).
- Si ese daño de vuelta **igualaría o superaría** la vida de `my_pokemon` (`_la_return >= my_pokemon.hp`, es decir, "atacar aquí me expone a un KO de vuelta"):
  - Si `my_pokemon` es un ex (`OUR_EX_IDS`, 2 premios): penalización proporcional a `SCORE_LOOKAHEAD_EX_TRADE = 250` (línea 357) escalada por `_op_disruption_belief(op_state, False)` — una probabilidad estimada de que el rival tenga en mano una carta de disrupción/energía extra (`main-04`/línea 674: `p = 1 - (1 - 2/40)^h`, acotada a `[0.05, 0.85]`, con `h` = tamaño de mano rival). La fórmula `0.6 + 0.4 * _la_disrupt` interpola la penalización entre el 60% (rival con mano vacía, amenaza casi segura) y el 100% (`SCORE_LOOKAHEAD_EX_TRADE` completo) de la constante según cuán probable es que el rival realmente complete ese contragolpe.
  - Si no es ex (1 premio): penalización fija `SCORE_LOOKAHEAD_KO_TRADE = 120` (línea 358) — un intercambio de 1 premio por 1 premio (o el que sea) es menos grave, así que la penalización es fija y menor, sin ponderar por incertidumbre de mano rival.
- Si en cambio el contragolpe estimado es **débil** (`_la_return <= my_pokemon.hp * 0.4`, el rival dejaría a `my_pokemon` por encima del 60% de su vida): bono `SCORE_LOOKAHEAD_SAFE = 60` (línea 359) — pequeño empujón a atacar cuando además queda seguro.

Este mecanismo es lo que el glosario de `main.md` llama "trades ex": el agente no sólo maximiza el daño de este turno, sino que penaliza atacar con un ex si eso lo deja expuesto a perder 2 premios de vuelta, con la penalización graduada por la probabilidad de que el rival tenga con qué rematar.

### Fijación de `plan.*` (líneas 2426–2432)

```python
if best_score < score:
    best_score = score
    plan.attacker = i
    plan.target = j
    plan.attack_index = attack_idx
    plan.remain_hp = op_pokemon.hp - damage
    plan.energy = more_energy
```

Simple selección de máximo: cada vez que `score` supera el `best_score` acumulado, se sobrescriben los cinco campos de `plan`. `plan.remain_hp` puede ser negativo (KO con sobrante de daño) — los consumidores del plan sólo comprueban `<= 0` para inferir KO, no el valor exacto. `plan.energy = more_energy` es la señal de "este plan requiere adjuntar la Grass básica (o recuperarla con Night Stretcher) este turno para ser viable", leída después por `energy_score` (`main-10`) vía `_attacker_ready = (plan.attacker >= 0 and not plan.energy)` (línea 3579, documentado en `main-02`).

### Promoción y remate con Hydrapple ex de banca (líneas 2434–2552)

Bloque activado cuando `can_switch` es `True`, hay activo rival (`_op_act_main`) y nuestro activo (`_ret_active`) **no es ya** Hydrapple ex. Busca en la banca (líneas 2456–2471) el mejor candidato Hydrapple ex para promover, con dos categorías:
- `_hydra_mc_idx`/`_hydra_mc_pk`: un Hydrapple **ya listo** (`_mc_eff >= 2`).
- `_hydra_charge_idx`/`_hydra_charge_pk`: un Hydrapple que **necesitaría** el adjunte de este turno para llegar a 2 efectivas (`_grass_in_hand_promo` y `len(_mc_pk.energies) + _grass_attach_unit() >= 2`).

En ambos casos, a igualdad de aptitud, **se prefiere el de mayor HP** (comentario líneas 2445–2455, motivado por el caso real `log 86212499 paso 151`, partida GANADA contra Alakazam: antes el agente tomaba el primer Hydrapple apto por orden de banca — normalmente el más frágil — y aquí se corrigió para recorrer toda la banca y quedarse con el de más vida, priorizando siempre primero un Hydrapple ya cargado (`_hydra_mc_idx`) sobre uno que necesita carga (`_hydra_charge_idx`).

Si no hay ninguno ya listo pero sí uno "cargable" (líneas 2474–2497), sólo se activa la promoción del que necesita carga si el activo actual, **de quedarse**, ya podría atacar sin él (`_ret_act_ready_now`, recalculando el requisito de energía según `_ret_active.id` para las 7 líneas principales) o si no tiene requisito conocido (`_ret_req_now is None`) — es decir, no se sacrifica el turno de ataque del activo actual sólo para cargar un Hydrapple de banca que aún tampoco podría atacar.

Con el candidato fijado (`_hydra_mc_idx >= 1`, línea 2498), se calcula el daño proyectado tras la retirada: `_ret_cards = _retreat_cards(_ret_cost)` (coste de retirada en cartas físicas, `0` si `has_switch_card`), `_hydra_grass_after = max(0, total_grass - _ret_cards)` (energía Grass total en juego tras descartar por la retirada) más `+1` si el candidato necesitaba carga (`_hydra_promo_needs_charge`). `_hydra_base = 30 + 30 * _hydra_grass_after` y `_hydra_ko_dmg` vía `_our_effective_damage`. `_hydra_can_ko = (_hydra_ko_dmg > 0 and _hydra_ko_dmg >= _op_main_hp)`.

En paralelo se evalúa si el **activo actual, si se quedara**, también podría noquear (`_act_can_ko`, líneas 2516–2541, con perfiles de daño por ID análogos a los de `attack_options` pero limitados a `Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Meganium, Pinsir, Fezandipiti_ex`, es decir sin Hydrapple porque ya se excluyó por la condición de entrada).

`_promote_hydra = _hydra_can_ko or (not _act_can_ko)` (línea 2543): se promueve al Hydrapple de banca si **él sí noquea**, o si **el activo actual no puede noquear de todas formas** (en cuyo caso no hay razón para no preferir el cuerpo más resistente). Si `_hydra_ko_dmg <= 0`, se anula la promoción (línea 2545–2546) — nunca se promueve un Hydrapple que ni siquiera puede dañar. Si procede, se sobrescribe `plan.*` apuntando al Hydrapple de banca contra el activo rival (líneas 2547–2552), sin requerir adjunte (`plan.energy = False`), porque cualquier necesidad de carga ya se contabilizó en `_hydra_grass_after`.

### Reglas de matchup contra "rule box" bloqueado propio (líneas 2554–2597)

Condición de entrada: `plan.attacker >= 1` (el plan actual apunta a un atacante de banca, típicamente fijado por el bloque anterior), el activo actual es un ex nuestro (`_ret_active.id in OUR_EX_IDS`) y el activo rival **no** es inmune a ex. Calcula `_rule_act_immune` (líneas 2559–2565): si el rival es inmune a Habilidad y nuestro activo depende de Habilidad, o si la Zona de Neutralización bloquea a nuestro ex contra un rival sin rule box, el activo **no podría** dañarlo de todas formas.

Si el activo **sí** podría dañar (`not _rule_act_immune`), se calcula su perfil de daño limitado a `Teal_Mask_Ogerpon_ex`, `Hydrapple_ex` y `Fezandipiti_ex` (líneas 2567–2574) y, si con energía actual o proyectada (`_rule_needs_attach`) alcanza el requisito y el daño es positivo, se comprueba `_rule_bench_kos = (plan.target == 0 and plan.remain_hp <= 0)` — es decir, si el plan vigente (el de banca) **ya** noqueaba al activo rival. Si el activo actual también puede dañar y el plan de banca **no** era ya un KO garantizado contra el mismo objetivo (`not _rule_bench_kos`), se **revierte** el plan al propio activo (líneas 2591–2596): prioriza no retirar innecesariamente cuando el activo puede aportar daño real y el plan de banca no tenía ya asegurado el remate.

### Pivote defensivo a Hydrapple ex sano (líneas 2598–2633)

Comentario extenso (2598–2607) explica la intención: si el activo propio es frágil (`active_ko_likely or active_hp_ratio <= 0.6`) y hay un Hydrapple ex **a vida completa** en banca con energía propia suficiente (`>= 2` efectivas) para noquear al activo rival, conviene retirar el cuerpo frágil y promover el muro — su HP altísimo (330) es difícil de noquear y el KO se entrega igual. Recorre la banca (líneas 2612–2633) buscando ese candidato con `_piv_pk.hp >= _piv_pk.maxHp` (vida completa exacta, no basta con "casi llena") y `len(_piv_pk.energies) * _grass_mult() >= 2`. Si el daño proyectado (`_piv_dmg = _our_effective_damage(..., 30 + 30 * total_grass, ...)`) noquea al activo rival, fija `plan.*` y activa `_hydra_pivot_active = True` (bandera de control que bloquea overrides posteriores redundantes, p.ej. líneas 2645, 2682, 2737) y corta el bucle (`break`, línea 2633).

### Pivote-muro a Hydrapple ex SIN KO (líneas 2635–2660)

Complementa al bloque anterior para el caso en que **no hay KO disponible este turno**, sólo protección. Referencia explícita a `log 85856881 p.127`. Se activa cuando `_hydra_wall_pivot` (bandera calculada antes de línea 1985, en el bloque de matchup — ver `main-06`, líneas 1821–1855: Ogerpon activo condenado que sí puede atacar pero no noquea, con un Hydrapple ex sano de banca que sobrevive al mejor golpe rival) está activo, no hay ya un pivote con KO (`not _hydra_pivot_active`) y el plan actual sigue apuntando al propio activo (`plan.attacker == 0`). El comentario (líneas 2639–2644) explica el mecanismo de implementación: como el motor sólo expone la opción de retirada tras elegir `PASS` en el menú principal, este bloque **no** exige `can_switch`; en su lugar, apunta `plan.attacker` al Hydrapple de banca para que la sección de puntuación de `ATTACK` (fuera de este rango, `main-15`) **suprima** la opción de atacar con el Ogerpon frágil (al ver `plan.attacker >= 1`), empujando al agente a elegir `PASS` y, en el siguiente prompt, retirarse hacia el muro.

### Sacrificio de premios: pivote a Tapu Bulu (líneas 2662–2721)

Dos variantes, ambas evitando exponer un ex (2 premios) cuando hay un cuerpo de 1 premio (`Tapu_Bulu`, no-ex) listo (`>= 4` efectivas) para tomar el mismo KO:
- **Defensivo**: activo ex en riesgo (`active_ko_likely or active_hp_ratio <= 0.5`).
- **Proactivo** (`_tapu_proactive_lead`, líneas 2677–2681): con Meganium en juego y **sin** enfrentar mazos de muro/inmunidad (`op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_is_sylveon_deck`) ni Zona de Neutralización, se permite el pivote aunque el ex esté sano — la razón es puramente de gestión de premios: por qué exponer 2 premios si 1 basta para el mismo resultado.

Condición adicional: `my_prize > prize_count(_op_act_main)` — no tiene sentido este pivote defensivo/conservador si de todas formas este KO ya nos daría la victoria (ese caso ya se resuelve con el `score = 50000` del bucle principal). Si `can_switch`, fija el plan y marca `_tapu_sac_pivot = True` (líneas 2701–2708); si Tapu ya puede rematar pero retirarse **todavía no** es posible (falta 1 energía física para el coste de retirada) y aún queda el adjunte manual del turno, marca `_tapu_sac_enable_retreat = True` (líneas 2715–2720) — señal para que `energy_score` (`main-10`) dirija el adjunte de este turno al activo ex, habilitando su retirada el turno siguiente en vez de reforzar a Tapu.

### Negación de premios: pivote a un cuerpo de menos premios sin exigir KO (líneas 2722–2814)

El bloque más defensivo de todos, motivado por una **partida perdida** (`log 86211357 paso 128`, contra Mega Starmie): si el activo es un ex condenado (`active_ko_likely`) cuyo KO le daría al rival los premios que le faltan para **ganar ya** (`op_prize >= 2 and prize_count(_ret_active) >= op_prize`), no conviene atacar con él. Antes de retirarlo, comprueba si el propio activo puede **ganar la partida ya** este turno (`_pdp_active_wins_now`, líneas 2747–2763, recalculando daño de Hydrapple ex/Ogerpon/Fezandipiti); si es así, no se retira (se ataca, porque ganar domina cualquier consideración defensiva).

Si no gana ya, busca en la banca (líneas 2766–2807) el mejor cuerpo que entregue **menos premios de los que el rival necesita** (`prize_count(_pdp_pk) < op_prize`) y que ya pueda atacar este turno (con o sin adjunte proyectado). Ordena candidatos por la clave `(_pdp_survives, _pdp_dmg, _pdp_hp)` — prioridad 1: sobrevive al mejor golpe rival (`_pdp_hp > _op_best_damage_vs(_pdp_pk)`); prioridad 2: daño infligido; prioridad 3: HP bruto como último desempate. Si encuentra candidato, fija `plan.*` con `plan.remain_hp = _op_act_main.hp or 1` (nota: **no** resta el daño real — es un valor placeholder no-cero, ya que aquí el objetivo no es calcular el HP restante preciso sino simplemente marcar que el plan cambió de atacante) y activa `_prize_denial_pivot = True`.

### Detección de "activo estancado" (líneas 2816–2856)

Cierre del bloque de plan: para el activo actual, calcula si puede atacar este turno considerando sólo los 7 `MAIN_ATTACKERS` (`_ATK_REQS_STALL`, línea 2820, construido como subconjunto de `ATTACK_ENERGY_REQ` limitado a esas claves). Si `_stall_after < _stall_req` (ni con el posible adjunte de este turno llega al requisito):
- Si no hay Teal Mask Ogerpon ex en juego con al menos 1 energía (`_td_stall <= 0`, variable que cuenta cuántos Ogerpon propios tienen `len(p.energies) >= 1`, línea 2835–2838) o no quedan Grass básicas en el mazo (`_nrg_deck <= 0`), se concluye directamente `_active_cant_attack_this_turn = True`.
- Si sí hay Ogerpon con energía y quedan Grass en el mazo, se calcula una **probabilidad** de que Teal Dance (que roba 1 carta al usarse) no encuentre ninguna Grass en las cartas robadas, multiplicando `(deck_total - nrg_deck) / deck_total` una vez por cada activación de Teal Dance disponible (acotado a 4, línea 2845: `min(_td_stall, 4)`), y se marca estancado sólo si `_p_no > 0.5` (más probable que no que sí se destrabe).

Finalmente (líneas 2849–2856), si se concluyó estancamiento **pero** `can_switch` es `True`, se revisa la banca: si **cualquier** Pokémon de banca (excluyendo `Meowth_ex`) ya cumple su requisito de `_ATK_REQS_STALL`, se **revoca** el estancamiento (`_active_cant_attack_this_turn = False`) — el activo puede seguir sin poder atacar, pero como hay alternativa viable en banca, no se considera al equipo entero "estancado" (la decisión de retirar se resuelve en la puntuación de `RETREAT`, `main-14`).

> Nota de alcance: la línea 2858 abre `def evaluate_supporters() -> dict:`, el inicio de la escalera de puntuación de `Boss's Orders` documentada en `main-08-agent-boss-orders.md`. Las líneas 2861–2900 (variables `_fez_active_can_attack`, `_op_active_is_crustle`, `_tapu_can_attack`, `crustle_gust_worth_it`) ya pertenecen conceptualmente a esa escalera, no al cálculo del `AttackPlan`; se mencionan aquí sólo para marcar el límite exacto del bloque.

## Interacciones

- **Con `AttackPlan` y los helpers de daño (`main-02`, líneas 391–667)**: todo este bloque es el principal "escritor" de `plan`; usa `_grass_mult()`, `_grass_attach_unit()`, `_retreat_cards()`, `_our_effective_damage()`, `ATTACK_ENERGY_REQ` y `MAIN_ATTACKERS` en casi cada sub-bloque.
- **Con la detección de amenaza y matchup previa (líneas 1477–1976, `main-06`)**: consume directamente `active_ko_likely`, `active_hp_ratio`, `_hydra_wall_pivot` (definido líneas 1821–1855), `_op_best_damage_vs` (función definida línea 1480), `total_grass` (línea 1819) y las banderas `op_is_*_deck`/`op_has_*` calculadas en ese bloque. Ninguna de estas variables se recalcula aquí; el bloque 1985–2900 es puramente consumidor de la clasificación de matchup.
- **Con la detección de KO del turno anterior (`ko_last_turn` / `_ko_detected_this_turn`, líneas 1312–1467, fuera de este rango)**: aunque la detección en sí vive antes de la línea 1985 (compara `op_prize` contra `_prev_op_prize`, revisa `obs.logs` en busca de `MOVE_CARD` desde `AreaType.PRIZE` del rival, o infiere KO si `context == TO_ACTIVE and not state.retreated`), el resultado (`ko_last_turn`) es leído extensamente en el resto de `agent()` — incluida la puntuación de Boss's Orders inmediatamente después de este bloque (`main-08`) y decenas de puntos en PLAY/ATTACH (`main-11`–`main-13`) — para saber si la Habilidad de Fezandipiti ex (*Flip the Script*, que exige que nos hayan noqueado el turno anterior) sigue "viva" este turno. No forma parte del cálculo del `AttackPlan` en sí, pero es una precondición de contexto que el bloque de amenaza (1477–1976) y el de plan (1985–2900) comparten implícitamente al evaluar si conviene jugar de forma agresiva o defensiva.
- **Con `energy_score` (`main-10`, ~4489–5970)**: lee `plan.attacker`/`plan.energy` para decidir si el adjunte de energía de este turno debe ir al Pokémon marcado por el plan (`_attacker_ready`, línea 3579) y respeta banderas de este bloque como `_tapu_sac_enable_retreat` y `_hydra_fragile_pivot` (esta última definida en `main-06`, no aquí) para desviar el adjunte a otro objetivo cuando el plan lo requiere.
- **Con Boss's Orders (`main-08`, ~2900–3590)**: la variable `crustle_gust_worth_it` (líneas 2885–2920, ya en el límite del bloque) reutiliza `_attacker_base_damage`/`_our_effective_damage` con la misma lógica de proyección de energía (`effective_energy_after_attach`) que el bucle principal de esta sección, para decidir si vale la pena gustear un objetivo de banca rival cuando el activo rival es inmune a nuestro ex.
- **Con RETREAT (`main-14`, ~11608–12609)**: las banderas `_hydra_pivot_active`, `_tapu_sac_pivot`, `_prize_denial_pivot` y `_active_cant_attack_this_turn` fijadas en este bloque condicionan directamente si la opción `RETREAT` recibe un puntaje alto (retirar hacia el Pokémon que `plan.attacker` ya señala) en la fase de puntuación de retirada.
- **Con ATTACK (`main-15`, ~12609–12761)**: la puntuación final de la opción `ATTACK` compara el índice del Pokémon activo contra `plan.attacker`; si `plan.attacker >= 1` (el plan apunta a la banca, como en los pivotes de las líneas 2608–2814), la opción de atacar con el activo actual queda suprimida o fuertemente penalizada, empujando al agente hacia `PASS` + retirada.
