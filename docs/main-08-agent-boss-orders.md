# main.py — Escalera de puntuación de Boss's Orders (líneas 2858–3608)

## Rol en el agente

`Boss's Orders` es el Supporter que obliga al rival a subir un Pokémon de su banca al puesto activo. Es la única herramienta del mazo para forzar un intercambio favorable de premios (noquear a un objetivo concreto de banca, negar una evolución amenazante, o quitar de encima a un activo inmune/muro). Dentro de `evaluate_supporters()` (que arranca en la línea 2858, dentro de `agent()`), este bloque calcula `values[Boss_Orders]`: una puntuación que indica **cuánto conviene jugar Boss's Orders este turno**, sin decidir todavía a quién se sube al activo (esa elección concreta la hace `_boss_tier` y la escalera `BOSS_SCORE_*`, documentadas en otro fichero, ver «Interacciones»).

El bloque es una larga cadena `if/elif` de detección de matchup (arquetipo rival → prioridad fija) seguida de un segundo bloque mucho más fino que recalcula el valor con `max(values.get(Boss_Orders, 0), X)` en función de lo que realmente se puede noquear/negar esta vuelta, y de un tercer bloque específico para cuando **nuestro propio activo no puede atacar este turno** (defensivo/stall). El resultado se usa después tanto para decidir si el `PLAY` de la carta puntúa alto (líneas ~8684–11008) como para desempatar el objetivo concreto en la selección `TO_ACTIVE`.

## Detalle por bloque

### Preparación de banderas (líneas 2861–2896)

- `_fez_active_can_attack` (2861-2869): `True` si nuestro activo es `Fezandipiti_ex` y ya tiene (o tendría tras adjuntar) energía efectiva ≥ 3. Si nuestro propio atacante ya está listo, gran parte del ladder posterior se anula (ver rama siguiente).
- `_op_active_is_crustle` (2871-2872): el activo rival es `Crustle_Grass` o `Crustle_Fighting`.
- `_tapu_can_attack` (2873-2875): `Tapu_Bulu` está en juego, `Meganium` está en juego (duplica energía Planta) y hay algún `Tapu_Bulu` propio (banca o activo) con ≥2 energías físicas — es decir, puede llegar a las 4 efectivas necesarias para su ataque de 220.
- `crustle_gust_worth_it` (2877-2919): comentario explícito (2877-2884) — cuando nuestro activo es un Pokémon `ex` (`OUR_EX_IDS`) y el rival juega Crustle (`op_is_crustle_deck and op_has_ex_immune_active`), nuestro ataque al activo rival da 0 daño por la inmunidad de Crustle a `ex`. El bucle (2897-2917) recorre la banca rival buscando un objetivo al que **sí** hagamos daño (`_our_effective_damage > 0`, vía `_attacker_base_damage`) y que además podamos noquear (`can_ko_target`) o que **no pueda retirarse** (`target_cannot_retreat`, energía < `RETREAT_COST`). Basta un objetivo así para marcar `crustle_gust_worth_it = True`.

### Rama 0 — Crustle: bypass de la inmunidad ex (línea 2919-2920)

```python
if crustle_gust_worth_it:
    values[Boss_Orders] = BOSS_PRIORITY_CRUSTLE_GUST
```
`BOSS_PRIORITY_CRUSTLE_GUST = 990` (constante definida en línea 369). Es la prioridad más alta de todo el ladder de arquetipo: el comentario de la constante dice que debe superar tanto a los cebos de robo de Lillie's (~650) como al resto de la escalera. Razón: contra Crustle nuestro atacante `ex` está bloqueado en el activo; sin Boss's Orders simplemente no hacemos nada útil ese turno.

### Rama 1 — Fezandipiti ya listo (línea 2921-2923)

```python
elif _fez_active_can_attack:
    values[Boss_Orders] = 0
```
Si nuestro propio activo (`Fezandipiti_ex`) ya puede atacar este turno, no hace falta gustear: se prioriza el ataque normal y Boss's Orders queda a 0 (pendiente de que el segundo bloque, más abajo, lo vuelva a subir si hay una razón táctica concreta — pero ese bloque está guardado por `not _fez_active_can_attack`, ver línea 3066, así que en la práctica esta rama apaga TODO el resto salvo el tercer bloque de "activo no puede atacar").

### Rama 2 — Tapu Bulu vs banca de Crustle (línea 2924-2926)

```python
elif (op_is_crustle_deck and _tapu_can_attack and not _op_active_is_crustle and
        op_has_crustle_bench):
    values[Boss_Orders] = 950
```
Mazo Crustle, nuestro `Tapu_Bulu` (no-`ex`, no bloqueado por la inmunidad) puede atacar, el activo rival actual **no** es un Crustle, pero hay un Crustle en su banca. Razón: conviene subir ese Crustle de banca al activo para que Tapu Bulu lo noquee antes de que llegue a convertirse en el muro activo.

### Rama 3 — Mazo Drednaw (líneas 2928-2960)

Solo se evalúa si el activo rival es `Drednaw`. Se detecta si tenemos un atacante que "salta" el escudo de Drednaw (`_has_shell_bypass_attacker`: `Meganium` con ≥4 energía efectiva o `Dipplin` con ≥1 energía) y si hay objetivos válidos en banca rival distintos de otro `Drednaw` (`_drednaw_bench_targets`).
- Sin atacante bypass y con objetivos en banca → `980` (máxima prioridad de esta rama: no podemos golpear el escudo del Drednaw activo de ninguna forma, así que hay que ir a buscar otra cosa a la banca).
- Con atacante bypass y objetivos en banca:
  - Si el bypass es `Meganium` (`_meganium_can_attack`) → `500` (moderado: Meganium ya puede atacar directamente al Drednaw activo, gustear compite con eso).
  - Si el bypass es solo `Dipplin` → `850` (más alto: Dipplin reparte daño de área limitado, conviene más ir a buscar un objetivo específico en banca).

### Rama 4 — Sylveon / línea Eevee (líneas 2961-2985)

- `op_is_sylveon_deck and op_has_eevee_bench` → `850`: hay un `Eevee` en banca rival (aún sin evolucionar a Sylveon inmune).
- `op_is_sylveon_deck and op_has_ex_immune_bench and not op_has_ex_immune_active` (2964-2985): el `Sylveon`/inmune-`ex` está en la **banca**, no en el activo (así que nuestro `ex` sí podría estar atacando al activo actual). Solo se activa si tenemos un atacante no-`ex` propio listo (`Tapu_Bulu` ≥4, `Meganium` ≥4, `Dipplin` ≥1, `Pinsir` ≥2 de energía efectiva) — `_has_nonex_attacker_sylveon` — para asegurarse de que gustear al Sylveon de banca es viable (podríamos noquearlo con un atacante que la inmunidad no bloquea). Si se cumple → `900`.

### Ramas 5-14 — detección de línea evolutiva amenazante por arquetipo (líneas 2986-3057)

Cada una comprueba si el activo rival **ya es** la amenaza (en cuyo caso no hace falta gustear, se salta la rama) y si en la banca hay una pieza de la línea evolutiva de ese arquetipo:

| Rama | Condición | Score | Razón |
|---|---|---|---|
| Froslass (2986-2987) | `op_has_froslass` y el activo NO es ya `Froslass` | 850 | Froslass amenaza en banca, sacarla antes de que suba sola. |
| Budew fuera de posición (2988-2989) | `budew_on_op_field and budew_op_index >= 1` | 800 | Budew (con *Itchy Pollen*) está en banca, no en activo; se prioriza sacarlo. |
| Snorunt en banca (2990-2991) | `op_has_snorunt_bench` | 780 | Pre-evolución de Froslass detectada en banca. |
| Munkidori (2992-2993) | `op_has_munkidori` y activo ≠ Munkidori | 750 | Munkidori (control) en banca. |
| Dwebble en banca (2994-2995) | `op_has_dwebble_bench` | 740 | Pre-evolución de Crustle en banca (mazo aún no confirmado Crustle-activo). |
| Eevee genérico (2996-2997) | `op_has_eevee_bench` | 750 | Cualquier miembro de `EEVEE_IDS` en banca (rama genérica, no exclusiva de Sylveon). |
| Dreepy/Drakloak → Dragapult (2998-3013) | `op_has_dreepy_line`; compara `_DRAGAPULT_STAGE` del activo vs. mejor etapa en banca | 700 si la banca tiene una etapa **más avanzada** que el activo, si no `0` | Solo conviene gustear si eso saca una pieza más cerca de evolucionar a `Dragapult_ex` que la que ya está activa. |
| Typhlosion / línea Ethan (3014-3028) | `op_has_typhlosion or op_has_ethan_preevo`; mismo patrón `_ETHAN_STAGE` (`Cyndaquil`1/`Quilava`2/`Typhlosion`3) | 700 / 0 | Igual lógica: solo si la banca tiene una etapa más avanzada. |
| Gardevoir (3030-3032) | `op_is_gardevoir_deck` y hay `Ralts`/`Kirlia` en banca | 730 | — |
| Alakazam (3033-3047) | `op_is_alakazam_deck`; mismo patrón `_ALAKAZAM_STAGE` (`Abra`1/`Kadabra`2/`Alakazam_ex`3, aunque el "ex" es engañoso, ver guarda `NONEX_FINAL_PREEVO_IDS` más abajo) | 700 / 0 | — |
| Slowking (3049-3051) | `op_is_slowking_deck` y `Slowpoke` en banca | 710 | — |
| Dragapult/Dusknoir (3052-3054) | `op_is_dragapult_dusknoir` y `Duskull`/`Dusclops` en banca | 700 | — |
| Zoroark (3055-3057) | `op_is_zoroark_deck` y `Zorua_N` en banca | 690 | — |

### Ramas de respaldo genérico (líneas 3058-3063)

```python
elif plan.target >= 1:
    values[Boss_Orders] = 650
elif op_prize <= 2:
    values[Boss_Orders] = 500
else:
    values[Boss_Orders] = 0
```
Si ninguna regla de arquetipo aplicó: si el `AttackPlan` del turno ya identificó un objetivo válido (`plan.target >= 1`, calculado en el bloque de amenaza/plan previo, líneas ~1985-2900) se da una base de `650`; si el rival está a ≤2 premios de ganar se da `500` (presión defensiva genérica); si no, `0`.

> Estas 15 ramas de arquetipo (2919-3063) fijan un **valor base** por matchup. El siguiente bloque (3065-3409) lo puede **subir** con `max()` según haya o no una jugada táctica concreta esta vuelta, y en algunos casos lo **resetea a 0** de forma explícita cuando atacar normalmente ya es suficiente.

### Bloque fino de valoración táctica (líneas 3065-3409)

Solo se ejecuta si tenemos Boss's Orders en mano, nuestro Fezandipiti activo no está ya listo, y el rival tiene un activo:
```python
if (hand_counts.get(Boss_Orders, 0) >= 1 and not _fez_active_can_attack
        and op_state.active and op_state.active[0] is not None):
```

#### `_boss_dmg_to(_tgt, ...)` — daño estimado si gusteamos y atacamos (líneas 3072-3112)
Función interna que estima el daño que haría **nuestro activo actual** (`_bo_atk`) contra un objetivo `_tgt` si se le sube al puesto activo, considerando una posible energía adicional este turno (`_bo_attach`, solo si hay `Basic_Grass_Energy` en mano y no se adjuntó ya). Fórmulas de daño por atacante (idénticas a las usadas en el resto del motor): `Hydrapple_ex` (30+30×grass si ≥2 efectivas), `Teal_Mask_Ogerpon_ex` (30+30×energía propia+objetivo si ≥3), `Tapu_Bulu` (220 fijo si ≥4), `Fezandipiti_ex` (100 si ≥3), `Meganium` (140 si ≥4), `Dipplin` (20×banca, override opcional `_wave_bench_override`), `Pinsir` (100 si ≥2). Aplica después:
- Inmunidad `ex` (`EX_IMMUNE_IDS` + atacante en `OUR_EX_IDS` → 0) y de habilidad (`ABILITY_IMMUNE_IDS` + atacante en `OUR_ABILITY_IDS` → 0).
- Debilidad/resistencia Planta del objetivo (salvo cuando el atacante es `Fezandipiti_ex`, cuyo ataque no es de tipo Planta): ×2 si debilidad, −30 si resistencia.
- Guarda especial `Drednaw`: si el daño calculado llega a ≥200, se anula a 0 (representa que Drednaw resiste/ignora ese golpe).

#### Objetivo activo y mejor objetivo de banca (líneas 3114-3141)
- `_bo_active_dmg`: 0 si `op_active_dodge_immune` (el rival acaba de esquivar con *Splashing Dodge* de Hop's Phantump y tiene inmunidad de un turno), si no `_boss_dmg_to(activo)`.
- `_bo_can_ko_active`, `_bo_active_prize` (premios que valdría noquear al activo, solo si se puede noquear).
- Bucle de banca (3122-3141) calcula `_bo_best_bench_dmg` y `_bo_best_bench_prize` (mejor objetivo noqueable). **Guarda log 86339758 (paso 98)**: si `op_is_crustle_deck`, se salta cualquier `Dwebble_Grass`/`Dwebble_Fighting` de banca — el manejador de selección ya veta a Dwebble como objetivo de gusteo (`score=-100000`), así que no debe poder *motivar* jugar Boss's Orders tampoco (si no, el agente jugaba Boss's persiguiendo un KO a Dwebble que nunca se ejecuta, y terminaba subiendo un objetivo peor).

#### `_bo_dipplin_combo` — combo Dipplin + refuerzo de banca (líneas 3142-3166)
Si nuestro activo es `Dipplin` con ≥1 energía y hay banca libre (`bench_count < 5`) y algún básico propio en mano (`_OUR_BASICS_COMBO = (Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir)`), comprueba si **bajar ese básico primero** (banca+1, `_combo_bench`) permite que el ataque de área de Dipplin (`20×banca`) alcance para noquear un objetivo de `HIGH_PRIORITY_BENCH_TARGETS`/`THREAT_PREEVO_IDS` que con la banca actual **no** se podía noquear (`_boost_ko and not _cur_ko`). Si se cumple → `values[Boss_Orders] = max(…, 960)` y bandera `values['_boss_dipplin_combo'] = True`.

#### `_bo_win_via_bench` — gusteo letal por premios (líneas 3168-3176)
```python
_bo_win_via_bench = (_bo_best_bench_prize > 0
                     and _bo_best_bench_prize >= my_prize
                     and not (_bo_can_ko_active and my_prize <= prize_count(_bo_op_active)))
```
Si noquear el mejor objetivo de banca ya cubre los premios que nos faltan para ganar (`_bo_best_bench_prize >= my_prize`) y noquear el activo actual **no** logra lo mismo, gustear para ganar tiene prioridad máxima → `max(…, 990)`, bandera `_boss_win_via_bench`.

#### `_bo_deny_evo_target` — negar una línea evolutiva (líneas 3177-3260)
Bloque comentado extensamente en el propio código (3207-3237). Solo se evalúa si aún no se ganó por banca ni por KO del activo. Para cada Pokémon de banca rival (con la misma guarda anti-Dwebble/Crustle del log 86339758, línea 3195-3198) se comprueban tres condiciones alternativas:
- `_bo_pe_is_threat`: está en `THREAT_PREEVO_IDS` (`Riolu, Duraludon, Hops_Phantump, Dwebble_Grass, Dwebble_Fighting, Buneary`).
- `_bo_pe_is_ex_preevo_energized`: está en `EX_PREEVO_IDS` **y no** en `NONEX_FINAL_PREEVO_IDS`, tiene ≥1 energía, y noquear el activo actual da el mismo número de premios que noquear esta pieza (`prize_count(_bo_op_active) == prize_count(_bo_pe)`). **Guarda `NONEX_FINAL_PREEVO_IDS = {Abra, Kadabra}`**: aunque `Abra`/`Kadabra` están en `EX_PREEVO_IDS`, su evolución final (`Alakazam_ex = 743`) es en realidad **no-ex de 1 premio** en este entorno (el nombre de la constante es engañoso, según el comentario de la línea 306-312); negar esa línea no vale más que noquear un muro cualquiera, así que se excluye explícitamente.
- `_bo_pe_is_ex_line_vs_wall` (3215-3223): el activo rival es un **muro inofensivo sin energía** (`len(_bo_op_active.energies) == 0`, vale ≤1 premio, y no es él mismo parte de una línea `ex`/amenaza/atacante clave) y en banca hay una pre-evolución `ex` (aunque tenga 0 energía). Se gustea igualmente porque noquear el muro no corta ninguna amenaza, mientras que cortar la pre-evolución `ex` sí.
- `_bo_pe_is_energized_preevo_vs_bare_wall` (3235-3237): variante para líneas donde **ambas** etapas están en `EX_PREEVO_IDS` (p. ej. Marnie: `Impidimp`→`Morgrem`→`Grimmsnarl_ex`, ambas pre-evos en `EX_PREEVO_IDS`), así que `_bo_pe_is_ex_line_vs_wall` no aplica (exige que el activo NO esté en `EX_PREEVO_IDS`). **Log 86402439 (paso 100)**: noquear el `Impidimp` desnudo del activo (1 premio, reemplazable) rinde lo mismo en premios que gustear+noquear el `Morgrem` energizado de banca (también 1 premio), pero gustear el Morgrem corta la línea del atacante principal (`Grimmsnarl_ex`) antes de que evolucione; por eso se prioriza el Morgrem energizado cuando el activo es un muro sin energía de la misma línea.

Si el daño directo no basta, se comprueba si un atacante de banca propio podría rematar tras retirarse el activo (`_bench_attacker_can_ko`, sujeto a poder retirarse: `_bo_de_can_retreat`, contempla la carta `Switch`/id 1123 como retirada gratis). Solo se descarta el objetivo si noquear el activo ya iguala o supera los premios de negar la línea (`prize_count(_bo_op_active) >= prize_count(_bo_pe))`, salvo que sea uno de los dos casos "vs muro" (`_bo_pe_is_ex_line_vs_wall` / `_bo_pe_is_energized_preevo_vs_bare_wall`), que se priorizan igualmente. Si se encuentra un objetivo válido → `max(…, 965)`, bandera `_boss_deny_evo`.

#### `_bo_gust_key_bench` — cazar al atacante clave del mazo rival (líneas 3261-3288)
Comentario explicativo (3261-3268): si el activo rival **no** es un `KEY_BENCH_ATTACKER_IDS` (`Hops_Trevenant`, `Hops_Phantump` — atacante principal del mazo Hop) pero sí lo hay en banca y es noqueable (directo o vía retiro+ataque de banca), se prioriza gustear esa pieza aunque el activo actual valga los mismos premios. La elección fina entre Trevenant-con-energía > Trevenant-sin-energía > Phantump-con-energía > Phantump-sin-energía la resuelve `_boss_tier` en la selección de objetivo (fuera de este bloque). Si aplica → `max(…, 975)`, bandera `_boss_gust_key_bench`.

#### Redirección por esquiva / dodge (líneas 3290-3296)
```python
if op_active_dodge_immune and not _bo_win_via_bench:
    if _bo_best_bench_prize > 0:
        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 985)
    elif _bo_best_bench_dmg > 0:
        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 970)
```
Si el activo rival tiene inmunidad temporal por el "dodge" de *Splashing Dodge* (Hop's Phantump, tras acertar cara en el volado, ver detección en líneas 1580-1609), atacarlo directamente no sirve de nada este turno: conviene redirigir el golpe a la banca. `985` si hay un objetivo noqueable en banca, `970` si solo hay daño parcial disponible.

#### Boost por diferencia de premios (líneas 3298-3306)
```python
if _bo_best_bench_prize > _bo_active_prize and _bo_best_bench_prize > 0:
    _bo_trade_down = (not _bo_can_ko_active and _bo_active_dmg > 0
                      and _bo_active_prize_val > _bo_best_bench_prize)
    if not _bo_trade_down:
        _bo_prize_diff = _bo_best_bench_prize - _bo_active_prize
        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 960 + 10 * _bo_prize_diff)
```
Si el mejor objetivo de banca vale estrictamente más premios que el activo, y no estamos ya "cambiando a la baja" (dañando parcialmente un activo de más premios sin poder noquearlo), se sube el valor a `960 + 10 × diferencia_de_premios` — cuanto mayor la diferencia de premios ganados, mayor la prioridad.

#### Snipe de espejo sin energía (líneas 3308-3315)
Si podemos noquear el activo rival y este está **sin energía** (`len(_bo_op_active.energies) == 0`), se busca en banca una copia idéntica (`_bo_bp.id == _bo_op_active.id`) que sí tenga energía y sea noqueable — noquear la copia energizada en banca es mejor que noquear la copia desnuda activa. Si existe → `max(…, 955)`.

#### Boss's Orders defensivo vs KO letal inminente (líneas 3317-3385)
Comentario extenso (3317-3332): si nuestro activo va a ser noqueado el próximo turno (`estimated_op_damage >= hp del activo`) y no hay ninguna razón ofensiva mejor ya detectada (`not _bo_can_ko_active and not _bo_win_via_bench and not _bo_deny_evo_target and not _bo_gust_key_bench and not _bo_dipplin_combo`), y nuestro activo es un Básico o Fase 1 (`_bo_active_basic_or_s1`, ≤1 pre-evolución), se busca en banca rival un objetivo que:
- no pueda retirarse este turno (`_bo_dg_e < _bo_dg_rc`), y
- no pueda noquear a nuestro activo el próximo turno aun adjuntando 1 energía extra (`_bo_dg_dmg_vs_us < hp de nuestro activo`, aplicando debilidad Planta de nuestro activo al tipo del objetivo si corresponde).

Si se encuentra, se sube al activo rival ese Pokémon inofensivo para "robarle" el turno de ataque letal al rival. Si aplica → `max(…, 940)`, bandera `_boss_defensive_gust`.

#### Downgrades a 0 — "atacar ya es suficiente" (líneas 3387-3409)
Tres controles que **fuerzan el valor a 0** (no usan `max`, lo pisan) cuando ya se puede lograr lo mismo sin gastar el Supporter:
1. (3387-3399) Si `_bo_can_ko_active` y ninguna razón de banca/negación/combo aplicó: si `my_prize <= prize_count(activo)` (el KO directo ya cierra la partida o iguala lo necesario) → `0`. También si el mejor objetivo de banca no vale más premios que el activo y este ya tiene energía → `0`. También un caso específico `Crustle_Grass` con energía y banca no mejor → `0`.
2. (3401-3409) Si el activo ya recibe algo de daño (`_bo_active_dmg > 0`) sin razón de banca/negación/combo/defensiva, y ese daño lo noquea o lo deja a ≤100 HP restante (`_bo_active_remaining <= 100`), se considera que el ataque normal "ya es suficiente" → `0` y bandera `_active_attack_sufficient`.

### Boss's Orders cuando nuestro activo NO puede atacar este turno (líneas 3411-3608)

Guardado por `_active_cant_attack_this_turn` (calculado antes, líneas ~2816-2856, con una estimación probabilística de si *Teal Dance* de Ogerpon dará energía) y por tener Boss's Orders en mano.

#### Recolección de atacantes futuros (líneas 3416-3450)
Recorre activo+banca (solo banca si `can_switch`) calculando el daño potencial de cada uno de nuestros atacantes principales (mismas fórmulas que `_boss_dmg_to`, más `Bayleef` 60 y `Chikorita` 30) asumiendo 1 energía extra adjuntable este turno.

#### KO a objetivo de alto valor en banca (líneas 3452-3489)
Para cada combinación (atacante propio, objetivo de banca rival) calcula el daño efectivo (aplicando debilidad/resistencia, inmunidad `ex`/habilidad, y el tope especial de `Drednaw` ≥200→0). Si algún atacante noquea:
- objetivo `ex` o `stage2` → `_boss_ko_ex_value = max(…, 985)`.
- si no, pero el objetivo tiene ≥1 energía → `_boss_ko_energy_value = max(…, 970)`.
Se aplica el mayor de los dos a `values[Boss_Orders]`.

#### Fallback: activo rival "atascado" o stall (líneas 3491-3535)
Si no hay KO de alto valor disponible: se mide si el propio activo rival está atascado (`_op_active_stuck`, diferencia coste de retirada − energía ≥2). Si lo está, no hace falta forzar nada (`values[Boss_Orders] = 0` si no había ya un valor positivo — dejarlo atascado ahí es gratis). Si no está atascado, se busca en banca un objetivo de **stall** (diferencia retiro−energía ≥ `_stall_threshold`, que es 1 si el activo no tiene coste de retirada o 2 en caso contrario), con guarda extra: si `op_has_latias_ex`, solo cuentan Básicos (ni `stage1` ni `stage2`, porque Latias permite retirar gratis a evoluciones). Si el mejor candidato tiene diferencia ≥2 → `975`, si no → `900`.

#### Guarda final Crustle — solo amenaza inminente (líneas 3536-3575)
**Log 86507974 (paso 141)**: exclusivo de `op_is_crustle_deck` (y solo si no se disparó ya `crustle_gust_worth_it`, `_boss_ko_ex_value` ni `_boss_ko_energy_value`). Si nuestro activo no puede atacar, solo se justifica Boss's Orders defensivamente cuando el activo rival amenaza de forma **inminente**: puede atacar ya, o le falta exactamente 1 energía (`energía_actual + 1 >= coste_mínimo_del_ataque`). Si necesita ≥2 energías más, no hay nada que neutralizar todavía y se fuerza `values[Boss_Orders] = 0` (no gastar el Supporter en vano).

### Activo rival con inmunidad de habilidad (Cornerstone Ogerpon) (líneas 3577-3608)
Bloque separado, condicionado a `op_has_ability_immune_active and plan.target >= 1`:
- Si nuestro atacante planificado (`plan.attacker`) ya está listo (con o sin adjunte de energía este turno) → `max(…, 980)`: gustear libera el bloqueo de habilidad forzando un cambio de activo.
- `elif op_has_ability_immune_active and len(op_state.bench) >= 1` (3585-3607): si el plan no tiene atacante listo, busca cualquier Pokémon propio **no dependiente de habilidad** (`not in OUR_ABILITY_IDS`) que alcance el requisito de energía de `_ATK_REQS_BOSS = {Tapu_Bulu:4, Dipplin:1, Bayleef:2, Chikorita:1, Applin:1, Pinsir:2}`, con o sin adjunte este turno → `max(…, 960)`.

## Interacciones

- **Constantes globales usadas**: `BOSS_PRIORITY_CRUSTLE_GUST = 990` (línea 369, exclusiva de esta rama). Las constantes `BOSS_SCORE_WIN_VIA_BENCH`, `BOSS_SCORE_WALL_GUST`, `BOSS_SCORE_DODGE_REDIRECT`, `BOSS_SCORE_PRIZE_RANK_BASE`, `BOSS_SCORE_LOW_VALUE_GUST`, `BOSS_SCORE_DEFENSIVE_GUST`, `BOSS_SCORE_EMPTY_GUST` (líneas 383-389) **no** se usan dentro de este bloque: se consumen mucho más adelante (líneas ~10662-10682) al puntuar las opciones `TO_ACTIVE` — es decir, una vez decidido *que sí* conviene jugar Boss's Orders (con el valor calculado aquí), otra escalera decide *a quién* subir.
- Las banderas booleanas que este bloque escribe en `values` (`'_boss_win_via_bench'`, `'_boss_deny_evo'`, `'_boss_gust_key_bench'`, `'_boss_dodge_redirect'`, `'_boss_defensive_gust'`, `'_boss_dipplin_combo'`, `'_active_attack_sufficient'`) son leídas más adelante en `agent()` para justificar o vetar decisiones relacionadas (p. ej. si conviene jugar el `Boss_Orders` como `PLAY`, o si otra rama de ataque debe ceder prioridad).
- Las variables `_win_via_boss_gust`, `_gust_2prize_via_boss` y `_boss_prize_rank` (calculadas más adelante, líneas 3831-4052, fuera de este rango) son un cálculo **independiente y posterior** dentro de la misma región de "Supporters y banderas de decisión" (documento `main-09-agent-supporters-and-flags.md`): reevalúan, ya con el `AttackPlan` cerrado, si Boss's Orders "gana la partida" o "gustea a un objetivo de 2 premios", y esas banderas sí se usan para vetar/forzar Lillie's Determination y para puntuar el `PLAY` real de la carta (líneas 4773, 5734-5744, 8025, 8810-8884, 9936) y en `_boss_tier` (líneas 6590-6625) para la selección `TO_ACTIVE`.
- `DUNSPARCE_IDS` (línea 283, "nunca gustear con Boss's Orders") y `_boss_tier` no se usan dentro de este bloque de puntuación: actúan como veto en la selección de objetivo concreto (líneas 6468, 10616), no en si se juega o no la carta.
- El bloque depende de banderas de matchup calculadas antes (`op_is_crustle_deck`, `op_is_drednaw_deck`, `op_is_sylveon_deck`, `op_has_froslass`, `budew_on_op_field`, `op_has_snorunt_bench`, `op_has_munkidori`, `op_has_dwebble_bench`, `op_has_eevee_bench`, `op_has_dreepy_line`, `op_has_typhlosion`/`op_has_ethan_preevo`, `op_is_gardevoir_deck`, `op_is_alakazam_deck`, `op_is_slowking_deck`, `op_is_dragapult_dusknoir`, `op_is_zoroark_deck`, `op_has_ability_immune_active`) que se detectan en el bloque de "Detección de matchup" (líneas ~1477-1985, `main-06-agent-matchup-detection.md`), inspeccionando activo **y** banca rival visibles.
- Depende también de `plan.target` y `estimated_op_damage`, calculados en el bloque de amenaza/plan de ataque inmediatamente anterior (líneas ~1985-2900, `main-07-agent-threat-and-plan.md`), y de `_active_cant_attack_this_turn` (calculado en líneas 2816-2856, dentro de ese mismo bloque previo).

## Reglas derivadas de partidas

- **log 86339758 (paso 98)** — mazo Crustle: NO gustear ni dejar que `Dwebble_Grass`/`Dwebble_Fighting` de banca *motiven* jugar Boss's Orders, porque el manejador de selección ya veta a Dwebble como objetivo (`score=-100000`). Aplicado en dos puntos: el bucle de mejor objetivo de banca (líneas 3132-3133) y el bucle de negación de línea evolutiva (líneas 3197-3198). Sin este veto, el agente jugaba Boss's persiguiendo un KO a Dwebble que nunca se ejecutaba, y terminaba subiendo al activo un Pokémon rival *menos* trabado (p. ej. Mega Kangaskhan ex con energía) en vez de dejar el más trabado (mayor coste de retirada neto) en el puesto activo.
- **log 86402439 (paso 100)** — línea Marnie (`Impidimp` → `Morgrem` → `Grimmsnarl_ex`): cuando el activo rival es un `Impidimp` desnudo (0 energía, 1 premio) de la misma línea, gustear el `Morgrem` energizado de banca (también 1 premio) rinde el mismo premio inmediato pero además corta la evolución hacia `Grimmsnarl_ex` (atacante principal, 2 premios). Implementado en la bandera `_bo_pe_is_energized_preevo_vs_bare_wall` (líneas 3235-3237), que evita que la condición general de "activo ya vale igual o más premios" (línea 3250-3254) descarte este caso.
- **log 86507974 (paso 141)** — exclusivo mazo Crustle: cuando nuestro activo no puede atacar este turno, solo se juega Boss's Orders por motivo puramente defensivo si el activo rival es una amenaza **inminente** (puede atacar ya, o solo le falta 1 energía). Si necesita 2 o más energías, no hay ataque que neutralizar todavía, así que se fuerza `values[Boss_Orders] = 0` para no gastar el Supporter en vano (líneas 3536-3575).
- **Guarda `NONEX_FINAL_PREEVO_IDS`** (definida en línea 313, aplicada en líneas 3203 y 3217): `Abra`/`Kadabra` están en `EX_PREEVO_IDS` pero su evolución final (`Alakazam_ex`, id 743) es en realidad no-`ex` de 1 premio en este entorno — la lógica de "negar una línea `ex`" no debe aplicarse a esta línea, porque gustear+noquear la pre-evolución rinde exactamente lo mismo (1 premio) que noquear un muro cualquiera. Sin comentario de log asociado en este bloque, pero corresponde a la regla de memoria "Boss's: no gustear pre-evo de línea no-ex".
- **`Buneary` en `THREAT_PREEVO_IDS` y `EX_PREEVO_IDS`** (líneas 278 y 303, comentario "-> Mega Lopunny ex (id 849, ex de 2 premios)"): al estar en ambos conjuntos, `Buneary` en banca activa directamente `_bo_pe_is_threat` en el bloque de negación de línea evolutiva (línea 3200), lo que corresponde a la regla de memoria "Boss's: gustear Buneary vs Mega Lopunny ex" (priorizar el gusteo a `Buneary` sobre golpear a un activo que no ataca).
