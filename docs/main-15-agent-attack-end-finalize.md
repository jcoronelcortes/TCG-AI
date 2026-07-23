# main.py — Bucle de puntuación — ATTACK, END y finalización de la decisión

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este es el **último tramo** del gran bucle `for o in select.option:` (docs 11–14): puntúa las opciones `ATTACK`, `END` y `SPECIAL_CONDITION`, y cierra el bucle con `scores.append(score)`. A diferencia de `PLAY`/`ATTACH`/`RETREAT`, el `score` de `ATTACK` no se calcula desde cero a partir de `plan`: arranca en un valor base alto (`1000`) y se somete a una cascada de **vetos** (`SCORE_VETO`) que reflejan situaciones concretas en las que atacar AHORA es peor que la alternativa (retirar primero, jugar un Supporter, buscar con Ultra Ball, o no arriesgarse porque el rival esquiva o estamos confundidos). El diseño es deliberado: como `plan` (el `AttackPlan`, doc 07) ya decidió *cuál* es el mejor atacante/objetivo — y su argmax de ataque usa ya la fórmula **corregida** de Myriad Leaf Shower, `leaf_dmg = 30 + 30 × (energía_propia + energía_del_activo_rival)`, que antes solo contaba la propia y subestimaba KOs reales —, la rama `ATTACK` solo decide *si conviene ejecutar ya* el ataque del activo tal como está la mesa.

Tras el bucle, el bloque de **finalización** materializa `scores` en la lista de índices que `agent()` devuelve. No vuelve a puntuar por identidad de carta salvo en excepciones muy dirigidas (recordar el objetivo de Poke Pad/Ultra Ball, forzar el sacrificio de Tapu Bulu, vetar estadios en el primer turno propio); su tarea principal es **reordenar** los índices mediante el sistema de *tiers* (`_TIER_*`) que impone la secuencia de juego deseada — estadio → desarrollo → Poke Pad → Bug Catching Set → energía — con sus **cuatro excepciones** (energía de KO, `_tapu_future_charge`, Ultra Ball del motor Meowth >31000, Teal Dance), y devolver `desc_indices[:select.maxCount]`.

## Detalle por bloque

### `ATTACK`: puntaje base y riesgo de confusión

```python
score = 1000
if plan.attack_index >= 0:
    score += 100
```

Base `1000` (en ausencia de vetos, atacar suele ser la mejor jugada tras haber jugado lo demás), `+100` si el `AttackPlan` tiene un ataque válido planeado. `condition_risky_attack` (nuestro activo está confundido) matiza:

- `_conf_should_attack` (confundido, sin atacante de banca del matchup listo, y el activo sí cumple su umbral de energía): `+300` — no hay alternativa mejor, se ataca pese al riesgo de la moneda.
- Si no, pero el ataque planeado noquearía (`plan.remain_hp <= 0`): `+50` — el premio del KO justifica un empujón moderado.
- Resto: `−500` — con atacante de banca listo y sin KO garantizado, no se arriesga el golpe confuso; la lógica de retirada (doc 14) promueve al de banca.

### `ATTACK`: Hydrapple ex — ceder el turno a desarrollo si no hay KO

Cuando el activo es Hydrapple ex, `itchy_pollen_active` es falso y el ataque planeado **no** noquea, se comprueba si hay una forma productiva de invertir la acción de energía del turno (`_can_add_energy`): Planta en mano con el adjunte libre; Ogerpon en juego + Planta (Teal Dance); Ogerpon en MANO con banca libre y Planta (bajarlo y cargarlo); o Ultra Ball jugable (mano ≥3) con Planta, banca libre y un Ogerpon aún en el mazo (`CARTAS_ACTIVAS_EN_MAZO`). Si cualquiera aplica → `score = SCORE_VETO`: mejor desarrollar que golpear sin rematar con Hydrapple.

### `ATTACK`: preferir retirar hacia el atacante del plan

Si `plan.attacker >= 1` (el `AttackPlan` eligió un atacante de **banca**: la codificación es `0` = activo, `1 + índice` = banca), el score sigue positivo, y el activo **no** es el caso especial `_nonex_active_hits_wall` (no-ex que sí golpea al muro inmune-a-ex — nunca se retira con tal de "seguir el plan"), se comprueba si atacar ahora YA gana la partida (`my_prize <= prize_count(activo_rival)` con `plan.remain_hp <= 0`). Si no gana ya y el activo tiene energía para pagar su coste de retirada (`RETREAT_COST`) → `score = SCORE_VETO`: retirar primero (doc 14) y dejar que el atacante correcto suba.

### `ATTACK`: banca vacía + Ultra Ball disponible → priorizar desarrollo

Con banca vacía (riesgo de perder el board si noquean al único cuerpo) y Ultra Ball jugable (mano ≥3, sin `itchy_pollen_active`), si **ningún** básico propio está en mano pero **sí** queda alguno en el mazo, se veta el ataque salvo que sea el golpe ganador. Nótese que aquí el chequeo de "ataque ganador" usa `op_prize <= prize_count(objetivo)` — compara los premios que le faltan **al rival**, no los nuestros como en el bloque anterior (`my_prize`); es una asimetría del código actual que en la práctica solo dispara cuando al rival le quedan pocos premios y el objetivo vale muchos.

### `ATTACK`: veto en el turno 2 si Lillie's es jugable

En nuestro primer turno yendo segundos (`state.turn == 2 and not we_go_first`), si Lillie's está en mano **y** existe realmente una opción `PLAY` para ella en esta decisión, se veta atacar: con un solo turno de energía el daño es bajo, y barajar/robar con Lillie's prepara mejor el turno 3.

### `ATTACK`: Meowth ex sin banca y esquiva rival

- Activo = Meowth ex con banca vacía → veto absoluto: *Tuck Tail* devuelve a Meowth ex y sus cartas a la mano; sin banca nos quedaríamos sin Pokémon en juego (derrota inmediata).
- `op_active_dodge_immune` (el rival ganó la moneda de *Splashing Dodge* de Hops Phantump; rastreado por `_dodge_immune_serial`/`_dodge_immune_turn`) → veto: el golpe fallaría con certeza.

### `END`: solo se habilita cuando conviene renunciar al ataque

```python
if can_attack:
    _end_attack_is_risky = (condition_risky_attack and
        not (plan.remain_hp is not None and plan.remain_hp <= 0))
    if _conf_should_attack or not _end_attack_is_risky:
        score = SCORE_NEVER
```

Terminar el turno sin atacar solo es aceptable cuando atacar sería arriesgado por confusión y no hay KO en juego (`_end_attack_is_risky` cierto y `_conf_should_attack` falso); en cualquier otro escenario con `can_attack`, `END` queda castigado a `SCORE_NEVER` (−10000) para que jamás se prefiera sobre atacar o sobre cualquier jugada positiva. Este piso también es la referencia contra la que se calibró el `SCORE_FORBID` de Meowth ex con Supporter jugado (doc 12): un veto que debe caer **por debajo** incluso de END.

### `SPECIAL_CONDITION`: prioridad por severidad

Dos contextos comparten la escalera con un matiz:

- `RECOVER_SPECIAL_CONDITION` (curar una condición propia): `PARALYZE = 500`, `SLEEP = 400`, `CONFUSE = 300`, `POISON = 200`, `BURN = 150`.
- `AFFECT_SPECIAL_CONDITION` (elegir qué condición infligir): mismos valores salvo `CONFUSE = 350`.

El orden refleja severidad táctica: parálisis (bloqueo total) > sueño (bloqueo probabilístico) > confusión (arriesga el ataque) > veneno > quemadura.

### Resumen de la cascada de vetos de ATTACK

| Veto | Condición resumida | Alternativa que gana |
| --- | --- | --- |
| Hydrapple sin KO | Activo Hydrapple ex, ataque no letal, `_can_add_energy` | Adjuntar/Teal Dance/bajar Ogerpon/Ultra Ball |
| Plan apunta a banca | `plan.attacker >= 1`, no gana ya, activo retirable, no `_nonex_active_hits_wall` | RETREAT hacia el atacante del plan |
| Banca vacía + UB | Sin básico en mano, básico en el mazo, no es golpe ganador | Ultra Ball (sentar un cuerpo) |
| Turno 2 con Lillie's | Yendo segundos, Lillie's jugable en esta decisión | Lillie's Determination |
| Meowth sin banca | *Tuck Tail* dejaría el campo vacío (derrota) | Cualquier otra jugada |
| Esquiva rival | `op_active_dodge_immune` (Splashing Dodge con cara) | No malgastar el ataque |

### Cierre del bucle: `scores.append(score)`

Cada opción recorrida por todas las ramas (`CARD`/`NUMBER`/`YES`/`NO`, `PLAY`, `ATTACH`/`EVOLVE`/`ABILITY`, `RETREAT`, `ATTACK`, `END`, `SPECIAL_CONDITION`) termina con su `score` definitivo en la lista paralela `scores`, indexada 1:1 con `select.option`. A partir de aquí ninguna rama vuelve a ejecutarse: los bloques siguientes solo leen y reordenan `scores`.

### Override de Poke Pad (`TO_HAND`): recordar el objetivo básico

Cuando la decisión es la búsqueda de `Poke_Pad`, este bloque **no recalcula** puntajes: recorre `scores` (calculados por la rama `CARD` de `TO_HAND`, doc 11), busca la mejor candidata que resuelva a carta y, si su puntaje supera `10` y es un Pokémon **básico** (ni `stage1` ni `stage2`), guarda su id en la variable global `_poke_pad_target_id` (reseteada en cada cambio de turno). Ese id lo consume después la rama `PLAY` (doc 12): fuerza `score = 21000` para jugar la carta que Poke Pad trajo deliberadamente aunque su puntuación normal la descartara.

### Override forzado: sacrificar Tapu Bulu vs Riolu/Lucario

Con `_lucario_sac_pivot` activo en una búsqueda de Poke Pad, y solo si `_tapu_sac_priority` (rival con protección anti-ex, o motor Hydrapple ex + Meganium que permite bajar y cargar a Tapu de inmediato) y Tapu no está ya disponible (`_tapu_already`), se **sobrescribe directamente** `scores[idx] = 99999` para la opción que trae a Tapu Bulu — a diferencia del override anterior (que solo *recuerda*), aquí se fuerza la elección en esta misma decisión, y se fija `_poke_pad_target_id = Tapu_Bulu` por consistencia con el `PLAY` posterior.

### Override de Ultra Ball (`TO_HAND`): marcar Meowth ex como pendiente

Mismo patrón para `Ultra_Ball`: si la carta con mejor puntaje entre las opciones de búsqueda es `Meowth_ex` (con puntaje > 10), se marca la bandera global `_ub_meowth_pending = True` (reseteada por turno, junto a `_ub_engine_pivot_turn`, `_poke_pad_target_id`, `plan` y `_field_at_turn_start` en el bloque `pre_turn != state.turn` del arranque de `agent()`). La rama `PLAY` la consume (doc 12): fuerza `score = 21000` para bajar el Meowth recién buscado — con los guards `field_counts[Meowth_ex] < 2`, `_meowth_ld_free` y `not state.supporterPlayed`. No hace falta guardar el id (Ultra Ball solo usa este mecanismo para Meowth ex). Nótese la relación con `_ub_engine_pivot_turn`: ese otro global se arma **antes**, al puntuar el `PLAY` de la Ultra Ball (cuando dispara `_ub_engine_refresh_pivot`), y sesga el **fetch** hacia Meowth (1300); `_ub_meowth_pending` se arma **después**, al resolverse el fetch, y sesga el **PLAY** del Meowth ya en mano — juntos encadenan UB → buscar Meowth → bajarlo → Last-Ditch → Lillie's dentro del mismo turno.

### Veto de estadio en el primer turno propio

`_our_first_turn_guard` identifica **nuestro** primer turno de acción (turno 1 yendo primero / turno 2 yendo segundo). `_replace_opp_stadium_ok` es la única excepción: yendo segundos en el turno 2 con un estadio rival en juego (`stadium_id != 0` y distinto de `Forest_of_Vitality`), SÍ se permite jugar estadio para reemplazarlo. Fuera de eso, cualquier opción `PLAY` de `CardType.STADIUM` se fuerza a `−99999` y su índice se guarda en `_vetoed_stadium_idxs`, que además se filtra del `desc_indices` final (cinturón y tirantes). Es lo que hace que el estadio solo aparezca jugable a partir del turno 3.

### Orden de jugada por tiers en contexto `MAIN`

El bloque impone, dentro de las opciones ya puntuadas positivamente, la secuencia **1) estadio → 2) básicos/evoluciones → 3) Poke Pad → 4) Bug Catching Set → 5) cargar energía**, con la energía que resuelve un KO este turno conservando prioridad máxima. Solo aplica en `context == SelectContext.MAIN` y solo reordena opciones con `scores[i] > 0` — los vetos nunca son "ascendidos" por un tier alto.

```python
_TIER_KO_ENERGY = 6
_TIER_STADIUM = 5
_TIER_DEVELOP = 4
_TIER_POKE_PAD = 3
_TIER_BUG_SET = 2
_TIER_ENERGY = 1
```

El resto de opciones (`ATTACK`/`END`/Supporters/Ultra Ball normal/habilidades no promovidas) se queda en el tier por defecto `0` y compite solo por `score`. Asignación:

- **`OptionType.EVOLVE`** → siempre `_TIER_DEVELOP`: evolucionar se juega antes que cargar energía o Poke Pad.
- **`OptionType.ATTACH`**: se calcula `_po_is_ko_energy` — cierto si `plan.energy` (el plan requiere justo esta energía), `plan.remain_hp <= 0`, `plan.attacker >= 0`, y el adjunte apunta exactamente al Pokémon designado (activo si `plan.attacker == 0`, o el índice de banca `plan.attacker == 1 + inPlayIndex`). Si es así, `_TIER_KO_ENERGY`; si no, `_TIER_ENERGY`.
  - **Excepción `_tapu_future_charge`**: si el flag está activo (el activo YA noquea con su energía actual, Meganium en juego, Tapu Bulu de banca por cargar) y el adjunte apunta al **activo**, se fuerza `_po_is_ko_energy = False`. Sin esta exclusión, el tier 6 del adjunte al activo aplastaba (6 > 1) la carga de Tapu Bulu de banca (score 40000 pero tier ENERGY), desperdiciando la energía en un atacante ya listo; al bajarlo a tier ENERGY, el desempate dentro del tier lo gana Tapu por score.
- **`OptionType.PLAY`**: `Poke_Pad` → `_TIER_POKE_PAD`; `Bug_Catching_Set` → `_TIER_BUG_SET`; **`Ultra_Ball` con `scores[i] > 31000` → `_TIER_ENERGY`** — es la Ultra Ball del motor `_ub_engine_refresh_pivot` (31450, doc 12): los ítems van en tier 0 y el adjunte manual (tier ENERGY, ~31410) la aplastaba por tier pese al score; subirla al tier ENERGY hace que dentro del tier decida el score (31450 > 31410), mismo patrón que Teal Dance. La UB normal (≤12500) conserva su tier 0; `CardType.STADIUM` → `_TIER_STADIUM`; `CardType.POKEMON` → `_TIER_DEVELOP`. Cualquier otro `PLAY` (Supporters, Night Stretcher, Unfair Stamp…) queda en tier 0.
- **`OptionType.ABILITY`**: si la carta es `Teal_Mask_Ogerpon_ex` (**Teal Dance**) → `_TIER_ENERGY`. Teal Dance adjunta 1 Planta Y roba una carta, así que debe jugarse ANTES que cualquier adjunte manual; sin esto quedaba en tier 0 (por debajo del tier ENERGY de los adjuntes) y el orden anteponía una carga manual pese a que Teal Dance puntúa más alto, desperdiciando el robo. Dentro del tier decide el score (Teal Dance ~31500 gana al adjunte ~31410). Las cargas de KO letal siguen en `_TIER_KO_ENERGY`. Las demás habilidades (Ripening Charge incluida) quedan en tier 0.

### Ordenación final, debug y casos especiales de `return`

```python
desc_indices = [i for i, _ in sorted(
    enumerate(scores),
    key=lambda x: (_play_order_tier[x[0]], x[1]),
    reverse=True)]
```

Ordenación definitiva: primero por tier descendente y, dentro de un mismo tier, por `score` descendente. Como el tier por defecto es `0`, este sort es un superconjunto no disruptivo del comportamiento clásico (ordenar solo por score) cuando ninguna de las categorías promovidas es jugable ese turno.

`_debug_log_decision(context, select, scores, obs, my_index)` imprime por `stderr` (solo con `DEBUG_DECISIONS`/`PTCG_DEBUG` activo) el top de opciones ordenado **por score puro**, NO por `(tier, score)`: el log de depuración no refleja necesariamente el orden final devuelto cuando el sistema de tiers reordena algo — a tener presente al depurar decisiones en contexto `MAIN` (p.ej. con `utils/split_turns.py` + replay).

Dos ramas de salida especiales:

1. **`SETUP_BENCH_POKEMON`**: hay que elegir varios Pokémon a la vez. `wanted` toma los índices con `score >= 0` (nótese `>=`: aquí el 0 SÍ es aceptable) en el orden de `desc_indices`; si no alcanza `select.minCount`, se completa sin condición con los primeros `minCount` (el juego obliga al mínimo). Se devuelve recortado a `select.maxCount`.
2. **Resto de contextos**: se filtran los `_vetoed_stadium_idxs` y se devuelve `desc_indices[:select.maxCount]`.

## Interacciones

- **Con el plan de ataque (doc 07)**: toda la rama `ATTACK` lee `plan.attacker`, `plan.attack_index`, `plan.remain_hp` y `plan.energy` en modo lectura. La coherencia entre "qué energía cargo" (tier `_TIER_KO_ENERGY`) y "quién ataca" depende de que `plan` esté bien fijado — incluida la Myriad corregida de su argmax (`leaf_dmg` cuenta la energía de ambos activos), sin la cual el plan elegía otro atacante o un chip ante un KO real de Ogerpon.
- **Con `RETREAT` (doc 14)**: el veto "preferir retirar hacia el atacante del plan" es el reflejo, del lado de ATTACK, de los pivotes de retirada — cuando RETREAT puntúa alto, ATTACK se veta en paralelo para que ambas no compitan de forma contradictoria en `desc_indices`.
- **Con los Supporters (docs 09/12)**: el veto del turno 2 con Lillie's jugable depende de que la escalera de Supporters ya le dé a Lillie's un puntaje competitivo; este bloque solo evita que ATTACK le gane.
- **Con la búsqueda (`TO_HAND`, doc 11)**: los overrides de Poke Pad y Ultra Ball leen los `scores` ya calculados; no reimplementan esa puntuación, solo la consultan para decidir qué recordar. `_ub_meowth_pending` y `_ub_engine_pivot_turn` son globales que persisten dentro del turno y se resetean al cambiar de turno.
- **Con `PLAY` (doc 12)**: `_poke_pad_target_id` y `_ub_meowth_pending` son leídos por la rama `PLAY` en pasos siguientes del mismo turno para forzar que la carta buscada se juegue; la Ultra Ball de 31450 del motor Meowth es la que este bloque promueve al tier ENERGY.
- **Con `ATTACH`/`ABILITY` (doc 13)**: los tiers no recalculan la puntuación de `ATTACH`/`ABILITY`; solo deciden el **orden relativo** frente a estadio/desarrollo/Poke Pad/BCS cuando varias opciones son simultáneamente viables. Las tres promociones al tier ENERGY (adjunte no-KO, Teal Dance, UB del motor) hacen que ese trío se resuelva siempre por score puro entre sí.

## Reglas derivadas de partidas

- **Excepción `_tapu_future_charge` en el tier de ATTACH** (vs Alakazam): sin ella, cargar energía innecesaria en el activo (tier 6) se jugaba antes que cargar a Tapu Bulu de banca (score 40000, tier 1); la corrección degrada el adjunte al activo a tier ENERGY y el desempate por score favorece a Tapu.
- **Teal Dance al tier ENERGY** (vs Mega Starmie): el adjunte manual ganaba por tier pese a que Teal Dance puntúa más alto y además roba carta.
- **Ultra Ball >31000 al tier ENERGY** (vs Archaludon ex, PERDIDA): el motor `_ub_engine_refresh_pivot` puntuaba la UB a 31450 pero el adjunte manual la aplastaba por tier; la mano quedaba sin fodder y la UB moría. Con la promoción, la cadena UB→Meowth→Lillie's se juega ANTES de gastar las energías de la mano (validada también vs Marnie's y Hop's — es agnóstica del rival).
- **Myriad corregida en `leaf_dmg`** (auditoría julio 2026, verificada con 6 registros): el argmax de ataque del plan subestimaba el daño de Ogerpon al ignorar la energía del activo rival.
