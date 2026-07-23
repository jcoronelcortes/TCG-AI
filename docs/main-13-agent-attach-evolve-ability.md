# main.py — Bucle de puntuación — ATTACH, EVOLVE y ABILITY

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este tramo es la continuación del bucle `for o in select.option:` de `agent()`, justo después de `PLAY` (doc 12). Cubre las tres ramas que "desarrollan" el tablero dentro del mismo turno sin gastar el ataque: `OptionType.ATTACH` (adjuntar manualmente una Energía Planta de la mano a un Pokémon propio), `OptionType.EVOLVE` (evolucionar un Pokémon en juego con la carta de la mano) y `OptionType.ABILITY` (activar una Habilidad: *Teal Dance* de Teal Mask Ogerpon ex, *Ripening Charge* de Hydrapple ex, *Flip the Script* de Fezandipiti ex, *Last-Ditch Catch* de Meowth ex, y el estadio rival *Lumiose City* si aparece como opción).

Las tres ramas comparten el objetivo de decidir **a qué Pokémon** conviene meter la energía/evolución del turno y **con qué prioridad relativa** frente al resto de jugadas. Para ello reutilizan el estado ya calculado: `plan` (`AttackPlan`, doc 07), los flags de matchup `op_is_*_deck`/`op_has_ex_immune_*` (doc 06), los flags de "pivote" de un solo turno (`_teal_wall_pivot`, `_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`, `_ripen_bench_tapu_ko_pivot`, `_tapu_sac_enable_retreat`, `_lucario_sac_pivot`, `_tapu_future_charge`, `_active_needs_energy`, `_active_hydra_ready`, `_bench_attacker_ready`, `_active_already_kos`, `_extra_energy_enables_ko`…, docs 07/09/10) y la función anidada `energy_score()` (doc 10), compartida por el adjunte manual y el objetivo de Ripening Charge (`SelectContext.ATTACH_FROM`).

En el orden de jugada por tiers (doc 15): `EVOLVE` recibe siempre `_TIER_DEVELOP`; `ATTACH` recibe `_TIER_KO_ENERGY` cuando es la energía que remata este turno (con la excepción `_tapu_future_charge`) o `_TIER_ENERGY` en el resto; y de las `ABILITY`, **Teal Dance se promueve al tier `_TIER_ENERGY`** (para preceder al adjunte manual y que dentro del tier decida el score), mientras que Ripening Charge y las demás quedan en tier 0 compitiendo por puntaje puro contra Supporters, Ultra Ball y el propio `ATTACK`.

## Detalle por bloque

### `ATTACH` — adjunte manual de energía

```python
score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
```

El puntaje base **siempre** parte de `energy_score` (doc 10), que arranca en `8000 + hp/100000` y sube o baja (desde `SCORE_VETO` hasta 42000) según las reglas de matchup y de "no sobrecargar". El bloque `ATTACH` no repite esas reglas: las hereda y solo las **sobrescribe** en situaciones muy concretas.

#### Adjunte al ACTIVO

- **Primer turno con Ogerpon ex/Tapu Bulu bloqueados en el activo**: en nuestro primer turno (turno 1 yendo primero / turno 2 yendo segundo), si el activo es Ogerpon ex o Tapu Bulu (ninguno ataca con 1 energía), por defecto se **veta** (`SCORE_VETO`): mejor repartir la energía en banca. Única excepción `_lucario_sac_pivot`: se puntúa `8500` para cargar igualmente al Ogerpon activo, porque el plan es retirarlo después conservando la energía (paga el coste de retirada) en vez de perderla si lo sacrifican.
- **`_tapu_sac_enable_retreat` → `24000`**: con un Tapu Bulu de banca **ya listo** (≥4 efectivas) que noquea al activo rival pero el ex activo (2 premios) aún sin poder retirarse, y una sola Planta bastando para habilitar su retirada (coste de Fezandipiti ex = 1). El comentario documenta el porqué del valor: antes puntuaba 8000 y un Dipplin de banca a 0 energías (8150) ganaba el desempate, desperdiciando la carga en un no-atacante; 24000 queda sobre cualquier desarrollo de banca no letal y bajo las cargas LETALES (41000/42000).
- **`plan.attacker == 0 and plan.energy` → `+200`**: si el atacante planificado es el activo y falta energía para el ataque, pequeño empujón para ganar empates.
- **Downgrade "Ogerpon listo + energía sobrante" → `7500`**: con `plan.attacker >= 1` (ataca un cuerpo de banca), Ogerpon en juego, `score > 31000`, rival no Crustle/Cornerstone, **y sin remate vía Boss's** (`not (_win_via_boss_gust or _gust_2prize_via_boss)` — el remate ganador con `energy_score = 42000` debe prevalecer: Myriad cuenta la energía de ambos activos, así que cargar el activo + gustear un ex energizado puede ser la línea de KO), se comprueba si el activo **necesita** la energía para retirarse (`_attach_needs_for_retreat` vs `RETREAT_COST`); si NO la necesita, se rebaja a `7500` para dejar sitio a los objetivos de banca.

#### Adjunte a BANCA

- **`plan.attacker == 1 + o.inPlayIndex and plan.energy` → `+200`**: análogo para el atacante de banca planificado.
- **Prioridad de desarrollo en el primer turno con activo bloqueado**: si es nuestro primer turno, el activo es Ogerpon/Tapu sin energía (`_active_blocked_ft`) y el candidato de banca está a 0 energías, se aplica la tabla `_BENCH_ATTACKER_PRIORITY` con `score = max(score, 8000 + prioridad)`:

  | Carta | Prioridad |
  | --- | --- |
  | `Hydrapple_ex` | 900 |
  | `Dipplin` | 850 |
  | `Teal_Mask_Ogerpon_ex` | 800 |
  | `Tapu_Bulu` | 750 |
  | `Pinsir` | 650 |
  | `Applin` | 500 |
  | `Chikorita` | 400 |
  | `Fezandipiti_ex` | 200 |

  Se prioriza la línea Applin→Dipplin→Hydrapple ex (acelera energía y puede cargar a Tapu Bulu en un turno) por encima de la línea Chikorita.
- **Veto duro de Meowth ex en banca**: `SCORE_VETO` sin excepciones — Meowth ex de banca nunca ataca; el único uso válido de energía sobre él es en el ACTIVO para pagar su retirada (lo gestiona `energy_score`).

#### Overrides finales, aplicables a activo y banca

- **Capado por Bug Catching Set jugable**: si `_bcs_playable_in_hand` (y sin `itchy_pollen_active`) y el score supera 9000, se capa a `9000` — con la excepción de `_tapu_future_charge` sobre un Tapu Bulu de banca (no perder la carga del atacante futuro frente a BCS). Los adjuntes letales (≥40000) quedan fuera del rango afectado.
- **Veto por reserva de Teal Dance (`_teal_dance_ko_pivot`)**: con el pivote activo y una **sola** Planta en mano, se veta cualquier adjunte manual — esa Planta se reserva para Teal Dance (adjunta + roba), que de otro modo perdería contra el adjunte por el tier ENERGY.
- **Teal Dance precede al adjunte manual (`_teal_dance_slots`)**: si el destino del adjunte es un Ogerpon cuya opción `ABILITY` sigue disponible este turno en ese mismo slot (`(o.inPlayArea, o.inPlayIndex) in _teal_dance_slots`, doc 10), se **veta el adjunte manual**: Teal Dance adjunta la Planta Y roba, así que va primero; tras usarla la habilidad desaparece y, si se quiere una 2ª energía, el adjunte se puntúa con normalidad en el paso siguiente. Corrige el orden que imponía el tier ENERGY (el adjunte ganaba pese a que Teal Dance puntúa más alto).

### `EVOLVE` — evolucionar

```python
score = 9000 + _pkmn_energy
```

Base `9000 + energía_actual_del_pre-evo`: a igualdad, se evoluciona el Pokémon con más energía invertida. Después, `card.id` (la evolución en mano) decide la rama.

#### Rama `Meganium`

`35000` (la prioridad de desarrollo más alta del bloque), `35500` vs fuego/espejo/Crustle (donde *Wild Growth* es más valiosa). `+500` extra si el evolucionado es directamente `Chikorita`.

#### Rama `Hydrapple_ex`

Base `33000`, con overrides de matchup:

- **Vs Crustle**: `34500` si `op_kang_ko_target`; `33000` si `op_active_is_kangaskhan`; **veto** en cualquier otro caso (Crustle inmuniza a los ex — evolucionar sería regalar 2 premios sin poder atacar).
- **Vs fuego**: `33500`.
- **Vs Drednaw** y **vs Sylveon con muro activo**: escala según los Dipplin adicionales en juego y si ya hay un Hydrapple (`22000` para no duplicar; `32500` con 2+ Dipplin; `32000` con 1 no-activo; resto `22000`). La variante Sylveon añade `_tapu_ready_sv` (Tapu con ≥4 efectivas en juego → `32500` directo).
- `+500` si evoluciona directamente desde `Applin` (fuera de Crustle).
- **Guardia "no desperdiciar el KO letal de Dipplin"**: si el evolucionado es el **Dipplin activo** que puede atacar y "Do the Wave" (`20 × banca`, vía `_our_effective_damage`) YA noquearía al rival (`_dip_kos`), pero tras evolucionar Syrup Storm **no** rematará este turno (`_hydra_kos` con `total_grass` y el posible adjunte), → **veto**: se conserva el Dipplin para cobrar el KO. Si Dipplin no noquea, o Hydrapple también noquearía, se evoluciona con normalidad.

#### Rama `Bayleef`

- **En el ACTIVO**:
  - Condición de estado que bloquea la acción (`has_condition and condition_blocks_action`): `34000 + condition_urgency` (evolucionar al inmovilizado es seguro).
  - Sin posibilidad de cambio (`not can_switch`): `31300`.
  - Caso general (puede cambiar): **por defecto veto** — evolucionar el activo dejaría un Bayleef frágil arriba en vez de retirarlo y evolucionarlo a salvo en banca. Se compara la energía efectiva contra `RETREAT_COST`: si ya alcanza el coste → veto (retirar primero); si no alcanza pero hay Lillie's en mano sin Supporter jugado → `31300` (se evoluciona ya, luego Lillie's y carga); si el adjunte del turno alcanzaría el coste → veto; resto → veto.
- **En BANCA**: `32000`; `32500` vs fuego/espejo/Crustle; `34000` vs Cubchoo (la línea Meganium es la prioridad de evolución de ese matchup, por delante de la línea Hydrapple 33000; Meganium en sí vale 35000, así que el orden se preserva).

#### Rama `Dipplin`

- Con energía ya puesta o adjuntable este turno (podrá atacar): base `31500`; `32000` con inmune-a-ex rival sin Hydrapple propio; `33000` vs Drednaw; `32500` vs Sylveon.
- Sin energía este turno: base `25000`; `31000` vs Drednaw; `30500` vs Sylveon.

#### Ajuste común "no evolucionar si el activo muere de todos modos"

Aplicable a todas las cartas salvo `Meganium`, solo si el Pokémon está en el ACTIVO, `active_ko_likely` y el score es positivo:

- `_evo_can_attack`: ¿podría atacar tras evolucionar? (Hydrapple ex: ≥2 efectivas; Dipplin: ≥1 física o Planta en mano; Bayleef: nunca).
- Si **no puede atacar** y no hay condición de estado → `score = 8000` (rebaja fuerte, sin veto total: evolucionar un cuerpo condenado que ni devuelve el golpe no compite con otras jugadas del turno).
- Si **sí puede** (y no es Hydrapple ex): se estima `_evo_survives` comparando la vida que tendría el evolucionado (`_evo_hp_after` = HP máximo de la carta de evolución menos el daño ya acumulado en la pre-evolución) contra el daño rival proyectado `_evo_op_damage`. Ese daño se refina consultando `card_table`: si la evolución resultante es **débil** al `energyType` del activo rival, se toma el mejor daño impreso de sus ataques ×2; si no comparte debilidad, se toma el daño impreso sin multiplicar; en otro caso se usa `estimated_op_damage` del preámbulo. Si no sobrevive y hay **otra copia** de la pre-evolución en banca (`_bench_has_same_preevo`) → `score = 8000`: no gastar la única copia de la línea en un cuerpo condenado cuando hay otra copia para evolucionar más tarde a salvo.

Finalmente, con condición de estado activa y score positivo, se suma `condition_urgency` (parálisis +5000, dormido +3000, confusión +2000, veneno +1500, quemadura +1200) — cuanto peor la condición, más urgente resolverla evolucionando al afectado.

#### Resumen de bandas de EVOLVE

| Banda | Significado |
| --- | --- |
| `35000–35500` | Meganium (máxima prioridad de evolución; el motor Wild Growth). |
| `33000–34500` | Hydrapple ex (con overrides de matchup; `34500` solo con `op_kang_ko_target`). |
| `34000 + urgencia` | Bayleef sobre un activo inmovilizado por condición. |
| `31300–33000` | Bayleef de banca / Dipplin con energía / casos Drednaw-Sylveon-Cubchoo. |
| `25000–31000` | Dipplin sin energía este turno. |
| `9000 + energía` | Base genérica (rara vez sobrevive a las ramas específicas). |
| `8000` | Rebaja "activo condenado" (no ataca tras evolucionar, o no sobrevive con copia de reserva). |
| `SCORE_VETO` | Hydrapple vs Crustle, Bayleef en activo retirable, guardia del KO de Dipplin. |

### `ABILITY` — usar habilidades

Cada Habilidad tiene su rama por `card.id`, todas en cascada de `elif` (la primera condición que se cumple fija el score).

#### Teal Dance — Teal Mask Ogerpon ex

Adjunta una Planta de la mano al propio Ogerpon y **roba una carta**. Precálculos:

- `_crustle_atk_needs_grass`: vs Crustle con exactamente 1 Planta en mano, ¿algún Tapu Bulu (<4 ef.) / Dipplin (<1) / Pinsir (<2 ef.) en juego necesita esa Planta?
- **`_td_ko_on_active`**: solo en el ACTIVO, sin inmunidad a ex rival — calcula el daño de *Myriad Leaf Shower* con la fórmula **corregida** contando **ambos** activos: `_td_base_now = 30 + 30 × (energía_propia + energía_del_activo_rival)` (0 si <3 efectivas) y `_td_base_after` con la energía extra de Teal Dance; ambos pasan por `_our_effective_damage` para aplicar debilidad **y resistencia** (caso Duraludon: resiste −30 a Planta, y Teal Dance habilita el KO al pasar de 4 a ≥5 energías). `True` si la energía extra convierte un no-KO en KO.

Orden de evaluación:

1. Sin Planta en mano → `SCORE_VETO`.
2. `_td_ko_on_active` → **`31500`** — la energía habilita un KO inmediato.
3. Tope vs Cubchoo: físicas ≥ 2 (con Meganium) / 4 (sin) → veto.
4. Tope vs Alakazam: misma regla física → veto (la energía extra del activo solo vía `_td_ko_on_active`).
5. `_teal_wall_pivot` en el ACTIVO → **`31600`** — Ogerpon condenado que no puede atacar + Hydrapple sano en banca: Teal Dance roba y habilita la retirada de coste 1 para pivotar al muro. Debe ganar al adjunte manual (~31200).
6. `_teal_dance_ko_pivot` en el ACTIVO → **`31600`** — Ogerpon bloqueado por el muro con atacante no-ex listo en banca; Teal Dance habilita la retirada.
7. Tope vs Crustle (`not op_kang_ko_target`, físicas ≥2) → veto.
8. `_crustle_atk_needs_grass` → `7500` (otro atacante necesita esa Planta).
9. `_reserve_energy_for_hydra_evolve` fuera del activo → `7500` (reservar la Planta para la evolución del Dipplin activo).
10. `_ogerpon_energy >= 3` (ya listo): `29000` si `_extra_energy_enables_ko`; `31050` si el activo ya noquea y el área no es el activo; `31050` si es el activo con atacante de banca listo y sin KO propio; resto → veto (no sobrecargar).
11. `_active_hydra_ready` → `31300` (el Hydrapple activo ya está operativo; cargar Ogerpon vía Teal Dance).
12. `_active_needs_energy` sin `_enough_for_both` y sin atacante planificado (salvo la excepción del primer turno con Ogerpon/Tapu activo) → `7500`.
13. `_reserve_hydra_active_charge` fuera del activo → `7500`.
14. `_hydrapple_bench_needs_energy` sin `_enough_after_priorities` → `7500`.
15. Fuera del activo, sin necesidad urgente en el activo → **`31500`** (caso normal de cargar el Ogerpon de banca).
16. Resto → `31000`.

#### Ripening Charge — Hydrapple ex

Adjunta una Planta de la mano a **cualquier** Pokémon propio (el objetivo se decide después, en `ATTACH_FROM` vía `energy_score`, doc 10); aquí solo se decide si activarla y con qué prioridad.

- **`_ripen_wasted_vs_crustle`**: guardia — si el activo es un Tapu Bulu ya cargado (≥4 ef.) y ningún cuerpo de banca necesita la Planta (Tapu <4 ef., Dipplin sin energía, Meganium <4 ef.), activarla obligaría a sobrecargar al Tapu (todos los objetivos de `energy_score` darían veto y el desempate elegiría el primero). Como Hydrapple es ex y no daña a Crustle, no se pierde ningún Syrup Storm.

Orden:

1. Sin Planta en mano → `SCORE_VETO`.
2. `_ripen_retreat_ko_pivot` en el activo → **`31600`** — Hydrapple activo bloqueado por el muro con Tapu de banca ya listo; la Planta va al propio Hydrapple (fijado en `energy_score`/`ATTACH_FROM`) para alcanzar su coste de retirada efectivo y pivotar a Tapu. También dispara con `_fragile_ex_sac_pivot` como origen (retirar el ex condenado y promover un 1-premio que noquea, ver doc 10).
3. `_ripen_bench_tapu_ko_pivot` en el activo → **`31600`** — Hydrapple ya retirable pero el Tapu de banca necesita la 2ª Planta para llegar a 4 efectivas letales; el objetivo Tapu lo fija `energy_score` (+20000).
4. `_ripen_wasted_vs_crustle` → veto.
5. `_hydra_energy >= 2` (ya ataca): `29000` si `_extra_energy_enables_ko`; `30000` si el activo Hydrapple **no** noquea y hay banca cargable (`_active_hydra_cannot_ko and _bench_has_chargeable`); `30000` si `_tapu_future_charge` (dejar listo al Tapu de banca para el próximo turno); resto → veto.
6. `_active_needs_energy` sin sobra, fuera del activo → `7500`.
7. Caso general: efectiva <2 → `31150` (banca a 0 energías) o `31100`; efectiva ≥2 → `30500`.

#### Flip the Script — Fezandipiti ex

```python
if _stamp_blocks_supp_chain or _lillie_blocks_fez_ability:
    score = SCORE_VETO
else:
    score = 30000
```

Secuenciación explícita: con `Unfair_Stamp` jugable este turno (`_stamp_blocks_supp_chain`), el Stamp va **primero** (si no, barajaría de vuelta las 3 cartas robadas; con el orden correcto quedan 5 del Stamp + 3 de la habilidad = 8). Análogamente, con Lillie's en mano sin Supporter jugado (`_lillie_blocks_fez_ability`), Lillie's va antes. Al desbloquearse (la carta bloqueante se jugó), vuelve a `30000`.

#### Last-Ditch Catch — Meowth ex

`30000` incondicional: la decisión de *cuándo* bajar Meowth ex vive en la rama `PLAY` (doc 12); una vez en juego, activar la búsqueda siempre conviene (la elección del Supporter la puntúa el fetch, doc 11).

#### Lumiose City (id 1267)

`score = 1`: estadio del rival cuyo efecto activable (buscar un Básico a la banca **y terminar el turno**) puede ofrecerse como opción nuestra. Positivo pero mínimo: nunca preferido frente a otra jugada, sin vetarlo por si fuera la única opción.

#### Resto de Habilidades

`29000` por defecto.

## Interacciones

- **`energy_score()`** (doc 10): base de todo `ATTACH` y de los objetivos de Ripening Charge (`ATTACH_FROM`). Los overrides de `ATTACH` se aplican **encima** de su resultado; solo los vetos (Meowth en banca, `_teal_dance_ko_pivot`, `_teal_dance_slots`) o las subidas fijas (`_tapu_sac_enable_retreat`, prioridad de banca del primer turno) lo reemplazan.
- **`plan` (`AttackPlan`)**: `plan.attacker` y `plan.energy` deciden los `+200` de ATTACH y si una carga se trata como "energía de KO" (`_TIER_KO_ENERGY`) o normal (`_TIER_ENERGY`) en la finalización (doc 15).
- **Flags de matchup** (`op_is_crustle_deck`, `op_is_cubchoo_deck`, `op_is_alakazam_deck`, `op_is_fire_deck`, `op_is_mirror`, `op_is_drednaw_deck`, `op_is_sylveon_deck`, `op_has_ex_immune_active/bench`, `op_active_is_kangaskhan`, `op_kang_ko_target`): condicionan casi todas las ramas de `EVOLVE` y los topes/excepciones de Teal Dance y Ripening Charge.
- **Flags de pivote de un solo turno** (`_teal_wall_pivot`, `_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`, `_ripen_bench_tapu_ko_pivot`, `_tapu_sac_enable_retreat`, `_lucario_sac_pivot`, `_tapu_future_charge`, `_fragile_ex_sac_pivot`): calculados antes del bucle; conectan `ATTACH`/`ABILITY` con la rama `RETREAT` (doc 14), que ejecuta el pivote una vez la energía habilitante se adjuntó.
- **`condition_urgency`/`has_condition`/`condition_blocks_action`**: elevan la prioridad de evolucionar el activo inmovilizado (rama Bayleef y ajuste común final).
- **Orden de jugada por tiers (doc 15)**: `EVOLVE` siempre `_TIER_DEVELOP`; `ATTACH` `_TIER_KO_ENERGY` solo si es la energía de KO exacta del plan (con la excepción `_tapu_future_charge` que la baja a `_TIER_ENERGY`); **Teal Dance** se promueve a `_TIER_ENERGY` (dentro del tier gana su score ~31500 sobre el adjunte ~31410); Ripening Charge y el resto de `ABILITY` quedan en tier 0.
- **`_td_base_now/after` con energía rival**: es una de las siete copias inline de la fórmula de Myriad corregidas en la auditoría de julio 2026 (junto a `leaf_dmg` del argmax de ataque, `_pdp_abase`, `_ak_dmg`, `_otml_dmg`, `_pb_dmg` y `_acn_base`).

## Reglas derivadas de partidas

- `_tapu_sac_enable_retreat` a 24000 (vs Alakazam/Dunsparce): cargar la energía que falta al ex activo para retirarlo y subir un Tapu ya cargado que remata.
- `_teal_dance_ko_pivot`: veta el adjunte manual con 1 sola Planta y puntúa la habilidad a 31600 (Ogerpon bloqueado por el muro con atacante no-ex listo).
- Tope de 2 físicas para Teal Dance sobre Ogerpon vs Crustle, con bypass `op_kang_ko_target`.
- `_ripen_wasted_vs_crustle`: no activar Ripening Charge sin destino útil (Tapu ya cargado, banca sin necesidades) — partida GANADA vs Crustle.
- `_ripen_retreat_ko_pivot` y `_ripen_bench_tapu_ko_pivot` a 31600 (dos victorias vs Crustle).
- Teal Dance precede al adjunte manual (`_teal_dance_slots` + promoción a tier ENERGY) — vs Mega Starmie.
- `_td_ko_on_active` con resistencia modelada (Duraludon −30) y con la energía del activo rival sumada (fórmula verificada con 6 registros).
- Downgrade del adjunte al activo respetando el remate vía Boss's (vs Iono: cargar el activo + gustear un Bellibolt ex energizado era la línea de KO).
