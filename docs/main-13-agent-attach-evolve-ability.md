# main.py — Bucle de puntuación — ATTACH, EVOLVE y ABILITY (líneas 11008–11608)

## Rol en el agente

Este tramo es la continuación directa del bucle `for o in select.option:` de `agent()`, justo después de la puntuación de `PLAY` (main-12). Cubre las tres ramas que "desarrollan" el tablero dentro del mismo turno sin gastar el ataque: `OptionType.ATTACH` (adjuntar manualmente una Energía Planta básica de la mano a un Pokémon, activo o de banca), `OptionType.EVOLVE` (evolucionar un Pokémon en juego con la carta de evolución de la mano) y `OptionType.ABILITY` (activar una Habilidad de un Pokémon en juego: Teal Dance de Teal Mask Ogerpon ex, Ripening Charge de Hydrapple ex, Flip the Script de Fezandipiti ex, Last-Ditch Catch de Meowth ex, y la "habilidad" del estadio Lumiose City si está en juego).

Las tres ramas comparten el mismo objetivo: decidir **a qué Pokémon** conviene meter la energía/evolución de este turno y **con qué prioridad relativa** frente al resto de jugadas del turno (Boss's Orders, Supporters, Ultra Ball, ataque…). Para ello reutilizan de forma intensiva el estado ya calculado en el preámbulo y en el análisis de amenaza: `plan` (`AttackPlan`, main-07), los flags de matchup `op_is_*_deck` / `op_has_ex_immune_*` (main-06), los flags de "pivote" de un solo turno calculados justo antes del bucle (`_teal_wall_pivot`, `_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`, `_ripen_bench_tapu_ko_pivot`, `_tapu_sac_enable_retreat`, `_lucario_sac_pivot`, `_tapu_future_charge`, `_active_needs_energy`, `_active_hydra_ready`, `_bench_attacker_ready`, `_active_already_kos`, `_extra_energy_enables_ko`, …, definidos entre las líneas ~1531–5800 y documentados en main-07/main-09/main-10) y la función anidada `energy_score()` (definida en la línea 4723, dentro de main-10) que centraliza casi todas las reglas de "a qué Pokémon cargar energía" y es compartida por el adjunte manual (`ATTACH`) y por el objetivo de Ripening Charge (`SelectContext.ATTACH_FROM`).

A diferencia de `EVOLVE`, cuyas opciones siempre reciben `tier 4` (`_TIER_DEVELOP`) en el orden de jugada por tiers (línea 12862) y de `ATTACH`, que recibe `tier 6` (`_TIER_KO_ENERGY`) cuando la carga es la energía que remata al activo rival este turno o `tier 1` (`_TIER_ENERGY`) en el resto de casos (líneas 12863–12888), las opciones de `ABILITY` **no aparecen en la lista de tiers** (líneas 12858–12900): conservan siempre `tier 0`, así que Teal Dance/Ripening Charge (aunque puntúen 29000–31600) solo ganan si su puntaje bruto supera al de las demás opciones de tier 0 (Ultra Ball, Supporters, el propio `ATTACK`…), no por prioridad estructural.

## Detalle por bloque

### `ATTACH` — adjunte manual de energía (líneas 11008–11107)

```python
elif o.type == OptionType.ATTACH:
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    if card is not None and pokemon is not None:
        score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
```

El puntaje base **siempre** parte de `energy_score(pokemon, active)` (línea 11012), la misma función que puntúa el objetivo de Ripening Charge en `SelectContext.ATTACH_FROM` (main-10). `energy_score` empieza en `8000 + hp/100000` (desempate por vida, línea 4736) y va subiendo o bajando (hasta `-1` de veto o `42000` de remate ganador) según decenas de reglas de matchup y de "no sobrecargar" (Chikorita máx. 1 energía física, Tapu Bulu máx. 2/4 físicas, Teal Mask Ogerpon ex con topes distintos vs Crustle/Cubchoo/Alakazam, etc.). El bloque `ATTACH` **no repite** esas reglas: las hereda del `score` inicial y solo las **sobrescribe** en un puñado de situaciones muy específicas de "adjunte manual al activo primer turno" o "pivote de retirada". El objetivo con mayor puntaje posible dentro de esta rama es el remate letal vía `energy_score` (42000, cuando `active and (_win_via_boss_gust or _gust_2prize_via_boss)`) o el `_tapu_sac_enable_retreat` de la línea 11040 (24000), que se explican abajo.

#### Adjunte al ACTIVO (líneas 11013–11055)

- **Primer turno con Ogerpon ex/Tapu Bulu bloqueados en el activo** (líneas 11015–11025): si es nuestro primer turno (`turn==1` yendo primero o `turn==2` yendo segundo) y el activo es `Teal_Mask_Ogerpon_ex` o `Tapu_Bulu` (ninguno puede atacar aún con 0 energía), por defecto se **veta** (`score = -1`, línea 11025): cargar el activo el primer turno no sirve porque ninguno de los dos ataca con 1 sola energía, así que es mejor repartir energía en la banca. La única excepción es `_lucario_sac_pivot` (línea 11019, definido en 5765–5769: rival tiene un `Riolu` activo con energía en nuestro turno 2 yendo segundos y nuestro activo es Ogerpon ex, indicando que el próximo turno evolucionará a Mega Lucario ex y noqueará a nuestro ex de 2 premios): en ese caso se puntúa `8500` (línea 11023) para cargar igualmente al Ogerpon ex activo, porque el plan es **retirarlo después** conservando la energía en la banca (paga el coste de retirada) en vez de perderla si lo sacrifican.
- **`_tapu_sac_enable_retreat`** (líneas 11026–11040, flag calculado en 2715–2720, `log 86029588` turno 16 vs Alakazam/Dunsparce): con un Tapu Bulu de banca **ya listo** (≥4 efectivas) que noquea al activo rival pero el ex activo (2 premios) aún no puede retirarse, y **una sola** Energía Planta ya basta para habilitar su retirada (coste de retirada de Fezandipiti ex = 1), se puntúa `24000`. El comentario explica que antes se puntuaba `8000` pero un Dipplin de banca a 0 energía puntuaba `8150` (8000+150 por `plan.energy`) y ganaba el desempate por tier `ENERGY`, desperdiciando la carga en un no-atacante; `24000` se sitúa por encima de cualquier desarrollo de banca no letal pero por debajo de una carga LETAL del turno (41000/42000 de `energy_score`).
- **`plan.attacker == 0 and plan.energy`** (líneas 11041–11042): si el `AttackPlan` del turno indica que el atacante planificado es el propio activo (`índice 0`) y que hace falta energía (`plan.energy`) para completar el ataque/KO de este turno, se suma `+200` al `score` base de `energy_score` — un pequeño empujón para que la energía "correcta" gane empates dentro de su rango.
- **Bypass "Ogerpon ex listo + energía sobrante" (líneas 11044–11055)**: si ya hay un atacante planificado (`plan.attacker >= 1`), tenemos Ogerpon ex en juego (`has_ogerpon`) y `energy_score` devolvió más de `31000` (es decir, ya es un objetivo de alta prioridad no vetado), y el rival no es Crustle/Cornerstone (mazos con inmunidad a ex), se comprueba si el activo actual **necesita** esa energía para poder retirarse (`_attach_needs_for_retreat`, comparando energía actual vs `RETREAT_COST`). Si NO la necesita, se fuerza `score = 7500` (línea 11055): se rebaja deliberadamente la prioridad del adjunte al activo para dejar sitio a otros objetivos de banca cuando el activo ya no depende de esa carga para poder pivotar.

#### Adjunte a BANCA (líneas 11056–11091)

- **`plan.attacker == 1 + o.inPlayIndex and plan.energy`** (líneas 11057–11058): análogo al caso del activo — si el Pokémon de banca objetivo es el atacante planificado y el plan necesita energía, `+200` al score.
- **Prioridad de desarrollo en banca el primer turno con activo bloqueado** (líneas 11060–11082): si es nuestro primer turno y el activo está "bloqueado" (Ogerpon ex o Tapu Bulu con 0 energía, `_active_blocked_ft`) y el Pokémon de banca objetivo aún no tiene ninguna energía (`len(pokemon.energies) < 1`), se usa la tabla `_BENCH_ATTACKER_PRIORITY` (línea 11066):

  | Carta | Prioridad |
  |---|---|
  | `Hydrapple_ex` | 900 |
  | `Dipplin` | 850 |
  | `Teal_Mask_Ogerpon_ex` | 800 |
  | `Tapu_Bulu` | 750 |
  | `Pinsir` | 650 |
  | `Applin` | 500 |
  | `Chikorita` | 400 |
  | `Fezandipiti_ex` | 200 |

  El score final es `max(score, 8000 + prioridad)` (línea 11082), de forma que nunca **baja** el `energy_score` original pero sí lo eleva cuando hace falta para respetar el orden. El comentario (líneas 11072–11075) explica la razón: se prioriza la línea `Applin → Dipplin → Hydrapple ex` (acelera energía y puede cargar a Tapu Bulu en un solo turno) por encima de la línea `Chikorita → Bayleef → Meganium`.
- **Veto duro de Meowth ex en banca** (líneas 11084–11091): `if pokemon.id == Meowth_ex: score = -1`, **sin excepciones** (ni turno ni "único objetivo disponible"). El comentario es explícito: Meowth ex de banca nunca ataca, así que cualquier energía puesta ahí se desperdicia; el único uso válido de energía manual sobre Meowth ex es en el ACTIVO, para pagar su coste de retirada (gestionado por `energy_score` dentro de la rama `AreaType.ACTIVE`, no aquí).

#### Overrides finales, aplicables a activo y banca (líneas 11093–11107)

- **Bug Catching Set jugable** (líneas 11093–11098): si `_bcs_playable_in_hand` (hay una Energía Planta o un Pokémon Planta buscable en el mazo, calculado en 4293–4305) está activo, no estamos bajo `itchy_pollen_active` (habilidad rival Budew que bloquea Bug Catching Set, línea 1574) y el `score` actual supera `9000`, se **capa** el score a `9000` (línea 11098) — con una excepción: no se capa si `_tapu_future_charge` está activo y el objetivo es un Tapu Bulu de banca (para no perder la carga del atacante futuro frente a Bug Catching Set). El efecto práctico: cuando Bug Catching Set puede jugarse, la mayoría de adjuntes manuales de energía quedan por debajo de él (Bug Catching Set puntúa más arriba en su propia rama `PLAY`, ver main-12), salvo los adjuntes letales (`energy_score` ≥ 40000) que ya están fuera del rango afectado por este capado.
- **Veto por reserva de Teal Dance** (líneas 11100–11107, `_teal_dance_ko_pivot`, `log 85802744` turno 16): si está activo el pivote "Teal Dance → retirar → promover atacante letal" (definido en 4646–4655: Ogerpon ex activo bloqueado por un muro, aún no puede retirarse pero SÍ tras una Planta más, y hay un atacante no-ex listo en banca que noquea al muro) y solo queda **una** Energía Planta básica en mano (`hand_counts.get(Basic_Grass_Energy, 0) <= 1`), se **veta cualquier adjunte manual** (`score = -1`). La razón (comentario 11100–11107): esa única Planta debe reservarse para Teal Dance, que además de adjuntarla **roba una carta**; un adjunte manual competiría por el mismo recurso y, por el tier `ENERGY` del orden de jugada, podría ganarle a la habilidad.

### `EVOLVE` — evolucionar (líneas 11109–11354)

```python
elif o.type == OptionType.EVOLVE:
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    if card is not None and pokemon is not None:
        _is_active = (o.inPlayArea == AreaType.ACTIVE)
        _pkmn_energy = len(pokemon.energies)
        _has_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached)
        score = 9000 + _pkmn_energy
```

El score base es `9000 + energía_actual_del_pre-evo` (línea 11117): a igualdad del resto de factores, se prefiere evolucionar el Pokémon **con más energía ya cargada** (conserva más recursos invertidos). A partir de ahí, `card.id` (la carta de evolución en mano) decide una rama completamente distinta cada vez.

#### Rama `Meganium` (líneas 11119–11126)

```python
if card.id == Meganium:
    score = 35000
    if op_is_fire_deck or op_is_mirror or op_is_crustle_deck:
        score = 35500
    if pokemon.id == Chikorita:
        score += 500
```

Evolucionar a Meganium es la **prioridad de desarrollo más alta** de todo el bloque `EVOLVE` (35000, o 35500 contra mazos de Fuego, el espejo, o Crustle — matchups donde Wild Growth, la Habilidad de Meganium que duplica cada energía Planta, es especialmente valiosa). Si el Pokémon evolucionado es directamente `Chikorita` (evolución "saltada" en una única acción, no pasando visiblemente por Bayleef en esta opción) se añade `+500` extra.

#### Rama `Hydrapple_ex` (líneas 11127–11214)

Score base `33000`, con overrides de matchup:

- **vs Crustle** (líneas 11130–11137): `34500` si `op_kang_ko_target` (Mega Kangaskhan ex es el objetivo alcanzable con Syrup Storm, flag de 4509–4531), `33000` si el activo rival ya es Kangaskhan (`op_active_is_kangaskhan`), y **veto total** (`-1`) en cualquier otro caso de Crustle — Hydrapple ex es un `ex` y Crustle inmuniza a los `ex`, así que evolucionar a Hydrapple ex normalmente sería regalar 2 premios sin poder atacar.
- **vs Fuego**: `33500`.
- **vs Drednaw** (líneas 11141–11155) y **vs Sylveon con activo inmune a ex** (líneas 11157–11174): lógica gemela que escala el score según cuántos `Dipplin` adicionales hay en juego (`field_counts.get(Dipplin, 0)`) y si ya existe un Hydrapple ex en juego (`_has_hydrapple_already`, entonces `22000`, más bajo, para no duplicar el atacante) — con `2+` Dipplin adicionales, `32500`; con `1` y no siendo el activo, `32000`; en el resto de casos, `22000`. La variante Sylveon añade además un chequeo de `_tapu_ready_sv` (un Tapu Bulu ya con ≥4 energía efectiva en juego): si existe, `32500` directamente (ya hay un atacante alternativo listo, así que Hydrapple ex puede evolucionar con más margen).
- **`pokemon.id == Applin and not op_is_crustle_deck`** (línea 11176): `+500` extra si se evoluciona directamente desde Applin (salto de línea, análogo al caso Chikorita→Meganium).
- **Guardia "no desperdiciar el KO letal de Dipplin"** (líneas 11179–11213, reglas explícitas del usuario en el comentario): si el Pokémon a evolucionar es el **Dipplin activo** y, sin evolucionar, "Do the Wave" (20×tamaño de banca) ya noquearía al activo rival este turno (`_dip_kos`), pero tras evolucionar a Hydrapple ex **no** se podría rematar este mismo turno (Syrup Storm exige 2 energías efectivas, `_hydra_kos` calculado con `_our_effective_damage` y `total_grass`), entonces `score = -1` — **no evolucionar**, conservar el Dipplin para atacar y cobrar el KO. Si Dipplin no noquea, o si tras evolucionar Hydrapple ex también noquearía, se evoluciona con normalidad (el `score` de las ramas anteriores queda intacto).

#### Rama `Bayleef` (líneas 11215–11266)

- **En el ACTIVO** (líneas 11217–11256):
  - Si hay una condición de estado que **bloquea** la acción (`has_condition and condition_blocks_action`, es decir dormido/paralizado): `34000 + condition_urgency` (línea 11220) — evolucionar el activo inmovilizado es seguro porque no perderá el turno de todos modos.
  - Si **no puede cambiar** de activo (`not can_switch`, no hay a quién retirar/promover): `31300` (línea 11223) — evolucionar el único cuerpo disponible, aunque deje un Bayleef frágil arriba, es mejor que no hacer nada.
  - En el caso general (puede cambiar de activo), **por defecto se veta** (líneas 11224–11256): evolucionar el activo a Bayleef "in situ" deja un cuerpo débil arriba en vez de retirarlo primero y evolucionarlo ya a salvo en banca. Se calcula `_evo_active_eff` (energía efectiva actual) contra `RETREAT_COST` y, con la Planta de mano disponible, `_evo_eff_after_attach`:
    - Si ya alcanza el coste de retirada (`_evo_active_eff >= _evo_active_rc`) → veto (`-1`): mejor retirar primero.
    - Si NO alcanza pero hay `Lillie's Determination` en mano y aún no se jugó Supporter este turno → `31300` (línea 11249): se evoluciona ya porque más tarde, tras jugar Lillie's, se podrá cargar energía y de todos modos el activo va a quedar comprometido esta secuencia.
    - Si con el adjunte de este turno alcanzaría el coste (`_evo_eff_after_attach >= _evo_active_rc`) → veto también (línea 11254): se prefiere retirar primero y evolucionar en banca.
    - Cualquier otro caso → veto (línea 11256).
- **En BANCA** (líneas 11257–11266): `32000` por defecto, `32500` contra Fuego/espejo/Crustle, y `34000` contra `op_is_cubchoo_deck` — el comentario aclara que, vs Cubchoo, la línea de Meganium es la prioridad principal de evolución por delante de la de Hydrapple ex (33000), y que Meganium en sí ya puntúa 35000 (por encima de este 34000), así que el orden relativo se preserva.

#### Rama `Dipplin` (líneas 11268–11288)

- Si el Pokémon ya tiene energía o se le puede adjuntar este turno (`_pkmn_energy >= 1 or _has_energy_in_hand`, es decir podrá atacar con "Do the Wave" tras evolucionar): base `31500`, subiendo a `32000` si el rival tiene algo inmune a ex en activo o banca y aún no tenemos Hydrapple ex en juego (`not has_hydrapple`), `33000` vs Drednaw, `32500` vs Sylveon.
- Si no tiene ni tendrá energía este turno: base más baja, `25000`, con `31000` vs Drednaw y `30500` vs Sylveon — igualmente se prioriza evolucionar (para tener el cuerpo disponible) aunque no pueda atacar todavía, más aún contra los matchups donde la línea Hydrapple ex es crítica.

#### Ajuste común "no evolucionar si el activo muere de todos modos" (líneas 11289–11351)

Aplicable a **todas** las cartas salvo `Meganium` (que siempre es seguro evolucionar), solo si el Pokémon está en el ACTIVO y `active_ko_likely` (el rival probablemente noquea este turno, main-07) y el `score` calculado arriba es positivo:

- Se calcula si, tras evolucionar, el Pokémon **podría atacar este turno** (`_evo_can_attack`): para `Hydrapple_ex` requiere energía efectiva ≥2 (`ATTACK_ENERGY_REQ`); para `Dipplin`, ≥1 energía física o una Planta en mano; `Bayleef` nunca puede atacar el turno que evoluciona (`False` fijo, línea 11299).
- **Si no puede atacar** y no hay una condición de estado activa sobre el activo (líneas 11301–11302): `score = 8000` — se rebaja mucho la prioridad (evolucionar un cuerpo condenado que ni siquiera puede devolver el golpe no vale la pena tanto como otras jugadas del turno), aunque no se llega a vetar del todo.
- **Si sí puede atacar** (y no es `Hydrapple_ex`, líneas 11304–11350): se estima si el Pokémon evolucionado **sobrevivirá** al golpe rival (`_evo_survives`, comparando HP restante tras evolucionar contra el daño rival estimado, con el ajuste ×2 si hay debilidad de tipo). Si no sobrevive (`not _evo_survives`) y existe **otro** Pokémon igual al pre-evolución en banca (`_bench_has_same_preevo`), se rebaja igualmente a `8000` (línea 11350): mejor no gastar la única copia de esa línea de evolución en un cuerpo que va a morir de todos modos si hay otra copia disponible para evolucionar más tarde a salvo.

Finalmente, si hay una condición de estado activa sobre el activo y el score sigue siendo positivo, se suma `condition_urgency` (líneas 11352–11353, calculado en 1425–1435: `+5000` parálisis, `+3000` dormido, `+2000` confusión, `+1500` veneno, `+1200` quemadura) — cuantas más/peores condiciones, más urgente resolverlas evolucionando el Pokémon afectado.

### `ABILITY` — usar habilidades (líneas 11355–11607)

```python
elif o.type == OptionType.ABILITY:
    card = get_card(obs, o.area, o.index, my_index)
    if card is not None:
        if card.id == Teal_Mask_Ogerpon_ex:
            ...
```

Cada Habilidad activable tiene su propia rama por `card.id`. Todas comparten el patrón de "cascada de `elif`": la primera condición que se cumple fija el `score` y las siguientes ya no se evalúan.

#### Teal Dance — Teal Mask Ogerpon ex (líneas 11358–11496)

Teal Dance adjunta una Energía Planta de la mano al propio Ogerpon ex y además **roba una carta**. Precálculos locales (líneas 11360–11393):
- `_ogerpon_energy`: energía efectiva actual de la carta.
- `_crustle_atk_needs_grass` (líneas 11362–11372): contra Crustle, con exactamente 1 Planta en mano, comprueba si algún Tapu Bulu/Dipplin/Pinsir en juego todavía necesita esa Planta para quedar listo (Tapu <4 efectivas, Dipplin <1, Pinsir <2 efectivas).
- `_td_ko_on_active` (líneas 11374–11393): solo si el área activada es el ACTIVO y el rival tiene activo sin inmunidad a ex, calcula el daño de "Myriad Leaf Shower" (`30 + 30×(energía_propia+energía_rival)`, ×2 si el rival es débil a Planta) **antes** y **después** de la energía extra de Teal Dance; `True` si la energía extra convierte un no-KO en KO.

Orden de evaluación (líneas 11394–11496):

1. **Sin Planta en mano** (línea 11394): `score = -1` — Teal Dance no tiene nada que adjuntar.
2. **`_td_ko_on_active`** (línea 11396): `31500` — máxima prioridad: la energía habilita un KO inmediato del activo rival.
3. **Tope vs Cubchoo** (líneas 11399–11408): si `op_is_cubchoo_deck` y la energía física (`_physical_energy`) ya alcanza `2` (con Meganium) o `4` (sin Meganium), veto `-1` — no sobrecargar a Ogerpon más allá del tope físico necesario, salvo la excepción ya cubierta arriba (`_td_ko_on_active`).
4. **Tope vs Alakazam** (líneas 11409–11420): misma regla física `2`/`4`, veto `-1`.
5. **`_teal_wall_pivot`** en el ACTIVO (líneas 11421–11428, comentario: Ogerpon ex activo condenado que no puede atacar + Hydrapple ex a vida completa en banca): `31600` — usar Teal Dance para robar y habilitar la retirada de coste 1, y así pivotar al muro sin regalar el activo gratis.
6. **`_teal_dance_ko_pivot`** en el ACTIVO (líneas 11429–11438, `log 85802744` turno 16): `31600` — mismo patrón que el ATTACH: Ogerpon bloqueado por el muro pero con un atacante no-ex listo en banca; Teal Dance habilita la retirada y debe ganar al adjunte manual (~31200/24000).
7. **Tope vs Crustle** (líneas 11439–11453, `log 86583376` paso 84): si `op_is_crustle_deck`, no es `op_kang_ko_target`, y la energía física ya es ≥2, veto `-1` — Ogerpon no daña al muro Crustle, así que no conviene sobrecargarlo con más de 2 energías físicas (excepción ya cubierta por `_td_ko_on_active`/`op_kang_ko_target`).
8. **`_crustle_atk_needs_grass`** (línea 11454): `7500` — hay otro atacante en juego que necesita esa Planta más que Ogerpon.
9. **`_reserve_energy_for_hydra_evolve`** fuera del activo (línea 11457, flag de 4283–4291: activo es Dipplin con 1 Planta en mano y Hydrapple ex/Ultra Ball alcanzable este turno): `7500` — reservar la Planta para la evolución en vez de gastarla en Teal Dance de banca.
10. **`_ogerpon_energy >= 3`** (ya listo para atacar, líneas 11460–11472): dentro de este caso, si la energía extra habilita un KO mayor (`_extra_energy_enables_ko`) → `29000`; si el activo ya noquea de todos modos y el área no es el activo (`_active_already_kos and o.area != ACTIVE`) → `31050`; si el área es el activo, hay un atacante de banca listo y el activo actual no noquea (`_bench_attacker_ready and not _active_already_kos`) → `31050`; en cualquier otro caso → veto `-1` (no sobrecargar a un Ogerpon que ya puede atacar sin necesidad real).
11. **`_active_hydra_ready`** (línea 11473, activo es Hydrapple ex con energía efectiva ≥2): `31300` — preferir cargar Ogerpon (via Teal Dance) sobre otras opciones cuando el muro/atacante Hydrapple ya está operativo.
12. **`_active_needs_energy` sin suficiente para ambos** (líneas 11476–11483): si el activo necesita energía, no hay Planta para cubrir dos objetivos (`not _enough_for_both`) y no hay atacante planificado (`plan.attacker < 1`), salvo la excepción del primer turno con Ogerpon/Tapu Bulu activos: `7500`.
13. **`_reserve_hydra_active_charge`** fuera del activo (línea 11484, flag 4251–4258: activo es Hydrapple ex con exactamente 1 Planta en mano que lo llevaría de <2 a ≥2 efectivas): `7500`.
14. **`_hydrapple_bench_needs_energy` sin sobra tras prioridades** (línea 11487, flags 4266–4281): `7500`.
15. **Fuera del activo, sin necesidad urgente en el activo** (líneas 11490–11493): `31500` — el caso "normal" de cargar Ogerpon de banca cuando nada más compite por la Planta.
16. **Cualquier otro caso** (línea 11496): `31000` — valor por defecto (activo, sin ninguna de las condiciones anteriores).

#### Ripening Charge — Hydrapple ex (líneas 11497–11584)

Ripening Charge adjunta una Planta de la mano a **cualquier** Pokémon propio (el objetivo se decide después, en `SelectContext.ATTACH_FROM` vía `energy_score`, main-10); aquí solo se decide si conviene activarla y con qué prioridad.

- **`_ripen_wasted_vs_crustle`** (líneas 11500–11526, `log 85848966` paso 76, GANADA vs Crustle): guardia que evita activar Ripening Charge cuando la Planta extra no tendría destino útil — si el activo es un Tapu Bulu ya cargado a ≥4 efectivas y ningún Pokémon de banca (Tapu <4, Dipplin sin energía, Meganium <4) la necesita, activarla obligaría a sobrecargar al Tapu ya listo (porque `energy_score` devolvería `-1` para todos los objetivos y el desempate elegiría el primero, el activo). Como Hydrapple ex es `ex` y no daña a Crustle, no se pierde ningún Syrup Storm letal al no activarla.
- Orden:
  1. Sin Planta en mano (línea 11527): `-1`.
  2. **`_ripen_retreat_ko_pivot`** en el activo (línea 11529, `log 86028607` turno 22): `31600` — Hydrapple ex activo bloqueado por el muro Crustle, con un Tapu de banca ya listo (220 de daño); Ripening Charge se adjunta al propio Hydrapple para alcanzar su coste de retirada efectivo, habilitando retirarlo y subir a Tapu a rematar.
  3. **`_ripen_bench_tapu_ko_pivot`** en el activo (línea 11540, `log 86182112` paso 82): `31600` — variante donde Hydrapple ex activo YA puede retirarse pero el Tapu de banca aún no está listo (2 efectivas, necesita una 2ª Planta para llegar a 4); Ripening Charge se usa para poner esa 2ª Planta en Tapu (objetivo fijado por `energy_score` con `+20000`), en vez de perderla en Teal Dance sobre un Ogerpon capado.
  4. `_ripen_wasted_vs_crustle` (línea 11552): `-1`.
  5. **`_hydra_energy >= 2`** (Hydrapple ex ya puede atacar, líneas 11554–11569): si la energía extra habilita un KO mayor (`_extra_energy_enables_ko`) → `29000`; si el activo (siendo Hydrapple ex) **no** noquea con su daño actual pero hay un cuerpo de banca cargable (`_active_hydra_cannot_ko and _bench_has_chargeable`) → `30000` (cargar la banca en vez de repetir energía inútil en el activo); si `_tapu_future_charge` está activo (el activo ya asegura el KO y Meganium está en juego: usar Ripening Charge para dejar a Tapu Bulu de banca listo para el próximo turno) → `30000`; en cualquier otro caso → `-1` (ya no hace falta más energía).
  6. **`_active_needs_energy` sin sobra, fuera del activo** (línea 11570): `7500`.
  7. Caso general (líneas 11573–11584): si la energía efectiva de Hydrapple ex es `<2` (aún no puede atacar), `31150` si además tiene 0 energía y el objetivo es de banca, o `31100` en el resto; si ya tiene `≥2` efectivas, `30500` (menor prioridad: ya puede atacar, la energía extra es solo margen).

#### Flip the Script — Fezandipiti ex (líneas 11585–11599)

```python
if _stamp_blocks_supp_chain or _lillie_blocks_fez_ability:
    score = -1
else:
    score = 30000
```

Regla de secuenciación explícita en el comentario: si tenemos `Unfair Stamp` jugable este turno (`_stamp_blocks_supp_chain`, línea 1069/1467: nos noquearon el turno anterior y `Unfair Stamp` sigue en mano), debe jugarse **antes** que la Habilidad, porque Unfair Stamp barajaría de vuelta las 3 cartas que roba Flip the Script si se activara primero (con el orden correcto: 5 cartas de Stamp + 3 de la Habilidad = 8). De forma análoga, si hay `Lillie's Determination` en mano y aún no se jugó Supporter (`_lillie_blocks_fez_ability`, línea 1474), también se juega Lillie's antes. Mientras cualquiera de las dos condiciones bloquee, `score = -1`; en cuanto ambas dejan de aplicar (la carta bloqueante ya se jugó), la Habilidad vuelve a puntuar `30000`.

#### Last-Ditch Catch — Meowth ex (líneas 11600–11602)

`score = 30000` sin condiciones adicionales: al bajar/activar Meowth ex se busca un Supporter en el mazo de forma incondicional (la decisión de *cuándo* bajar Meowth ex ya se resuelve en la rama `PLAY`, main-12, con los flags `_meowth_devel_lillie` / `_meowth_lone_fetch`).

#### Lumiose City — id 1267 (líneas 11603–11604)

```python
elif card.id == 1267:
    score = 1
```

`1267` es el estadio *Lumiose City* (`EN_Card_Data.csv`: "Once during each player's turn, that player may search their deck for a Basic Pokémon and put it onto their Bench... their turn ends"). No pertenece a nuestro mazo (nuestro único estadio es `Forest_of_Vitality`); esta rama cubre el caso en que el estadio en juego es el del rival y el motor ofrece su efecto activable como opción nuestra. Se puntúa deliberadamente muy bajo (`1`, positivo pero mínimo) porque usarlo **termina el turno**: nunca es la jugada preferida frente a cualquier otra opción positiva, pero tampoco se veta del todo por si en algún momento fuera la única opción disponible.

#### Resto de Habilidades (líneas 11605–11606)

```python
else:
    score = 29000
```

Valor por defecto para cualquier otra Habilidad activable no cubierta explícitamente arriba.

## Interacciones

- **`energy_score()`** (línea 4723, main-10): base de todo el bloque `ATTACH`; también puntúa los objetivos de Ripening Charge (`ATTACH_FROM`, main-10/11). Los overrides de `ATTACH` documentados aquí se aplican **encima** de su resultado, nunca lo reemplazan salvo en los pocos vetos (`Meowth_ex` en banca, `_teal_dance_ko_pivot`) o subidas fijas (`_tapu_sac_enable_retreat`, prioridad de banca primer turno) explicados arriba.
- **`plan` (`AttackPlan`, main-07)**: `plan.attacker` y `plan.energy` deciden el `+200` de ATTACH (líneas 11041, 11057) y si una carga al activo se trata como "energía de KO" (`tier 6`) o "energía normal" (`tier 1`) en el orden de jugada final (líneas 12863–12888).
- **Flags de matchup (`op_is_crustle_deck`, `op_is_cubchoo_deck`, `op_is_alakazam_deck`, `op_is_fire_deck`, `op_is_mirror`, `op_is_drednaw_deck`, `op_is_sylveon_deck`, `op_has_ex_immune_active/bench`, `op_active_is_kangaskhan`, `op_kang_ko_target`, main-06)**: condicionan casi todas las ramas de `EVOLVE` (Hydrapple ex, Bayleef) y los topes/excepciones de Teal Dance y Ripening Charge en `ABILITY`.
- **Flags de "pivote" de un solo turno** (`_teal_wall_pivot` 1534–1572, `_teal_dance_ko_pivot` 4646–4655, `_ripen_retreat_ko_pivot` 4670–4679, `_ripen_bench_tapu_ko_pivot` 4695–4721, `_tapu_sac_enable_retreat` 1977/2715–2720, `_lucario_sac_pivot` 5758–5769, `_tapu_future_charge` 4546–4550): calculados **antes** del bucle principal a partir del estado del tablero; conectan `ATTACH`/`ABILITY` con la rama `RETREAT` (main-14), que es la que efectivamente ejecuta el pivote (retirar y promover) una vez la energía habilitante ya se adjuntó.
- **`condition_urgency`/`has_condition`/`condition_blocks_action`** (líneas 1417–1435, main-05/09): eleva la prioridad de evolucionar el activo cuando está inmovilizado por una condición de estado, tanto en `Bayleef` (línea 11220) como en el ajuste común final (línea 11353).
- **Orden de jugada por tiers** (líneas 12850–12900, resumido en main.md §1): `EVOLVE` siempre es `tier 4`; `ATTACH` es `tier 6` solo si es la energía de KO exacta del `plan` (con la excepción `_tapu_future_charge`, línea 12884, que la baja a `tier 1` para no aplastar la carga del atacante futuro); `ABILITY` se queda siempre en `tier 0`, compitiendo por puntaje puro con Supporters, Ultra Ball y el propio `ATTACK`.

## Reglas derivadas de partidas

- **`log 86029588`** (turno 16, paso 148, vs Alakazam/Dunsparce): origen de `_tapu_sac_enable_retreat` (ATTACH activo, línea 11040, `24000`) — cargar la energía que falta al ex activo para poder retirarlo y subir a un Tapu Bulu ya cargado que remata.
- **`log 85802744`** (turno 16, GANADA): origen de `_teal_dance_ko_pivot`, usado tanto para vetar el adjunte manual (línea 11100, mano con 1 sola Planta) como para puntuar la propia Habilidad en el activo (línea 11429, `31600`) — Ogerpon ex bloqueado por un muro con un atacante no-ex listo en banca.
- **`log 86583376`** (paso 84, vs Crustle): origen del tope de 2 energías físicas para Teal Dance sobre Ogerpon ex contra Crustle (línea 11439–11453, veto `-1`), salvo el bypass de `op_kang_ko_target`.
- **`log 85848966`** (paso 76, GANADA vs Crustle): origen de `_ripen_wasted_vs_crustle` (línea 11500–11526) — no activar Ripening Charge si la Planta extra no tiene ningún destino útil (Tapu Bulu ya cargado, nada más en banca que la necesite).
- **`log 86028607`** (turno 22, GANADA vs Crustle): origen de `_ripen_retreat_ko_pivot` (línea 11529, `31600`) — usar Ripening Charge sobre el propio Hydrapple ex activo para alcanzar el coste de retirada y pivotar a un Tapu Bulu que remata.
- **`log 86182112`** (paso 82, GANADA vs Crustle): origen de `_ripen_bench_tapu_ko_pivot` (línea 11540, `31600`) — variante donde el Hydrapple ex activo ya puede retirarse pero hace falta poner la 2ª Planta en el Tapu Bulu de banca antes de pivotar.
