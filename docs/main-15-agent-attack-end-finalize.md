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

### `ATTACK`: remate ganador y **remate suicida**

`_active_attack_wins_now and plan.attacker == 0` → `score = 99000`: si el ataque del activo noquea y **gana la partida**, es la jugada de máxima prioridad absoluta (por encima de cualquier carga/desarrollo/Teal Dance), y el tier `_TIER_WIN_ATTACK` la ejecuta primero. `_snipe_attack_wins_now` (doc 02/09) mete en esa misma banda el remate por **snipe**: si *Cruel Arrow* noquea un cuerpo de la banca rival cuyos premios nos bastan (`my_prize <= _active_snipe_ko_prizes`, con KO garantizado y sin suicidio), atacar gana igual que rematar al activo. El caso "banca rival vacía" no aplica ahí: el rival solo pierde por no poder reemplazar a su **activo**, y ese KO no lo toca.

### `ATTACK`: el snipe que cobra premio

`elif _active_snipe_ko_now and plan.attacker == 0` → `score = 8500 + 100 × _active_snipe_ko_prizes` (user, registro_004 paso 54 vs Alakazam). El *Cruel Arrow* del Fezandipiti ex activo no llegaba al muro de delante (Alakazam, 140 PV) pero **noqueaba a un Kadabra de 80 en la banca**: un premio gratis, sin coste de retirada y sin exponer otro cuerpo. Con la banda base de `1000/1100` lo ganaba cualquier pivote de retirada (6400-8900) y el turno se cerraba en blanco. La banda queda **por debajo** de los remates ganadores (99000) y de los pivotes de KO mayor (8900 `_ogerpon_lethal_promote` / 9000 `_hydra_lethal_promote` / 9600 relevo suicida), que llevan sus propias guardas de premios (doc 14).

Justo después vienen los dos frenos del **remate suicida** (flags en doc 09, auto-daño en doc 02), acotados a `plan.attacker == 0` porque el activo es el único cuerpo cuyo auto-daño midieron los flags:

- **`_suicide_loses` → `SCORE_VETO` siempre**: el auto-daño nos noquea y con ese cadáver el rival llega a 0, mientras nuestro ataque **no** cierra nuestra cuenta. Atacar es perder; pasar es estrictamente mejor.
- **`_suicide_only_draws` → `SCORE_VETO` solo si existe el relevo** (`_suicide_swap_win_promote`): los dos KOs cierran las dos cuentas → empate. Con un rematador de banca que gana limpio, se retira (doc 14, score `9600`); **sin relevo el empate es el mejor resultado disponible y se ataca igual**.

Nótese que `_suicide_hands_op_win` ya está restado dentro de `_active_attack_wins_now`, así que el `99000` nunca se concede a un remate que solo empata.

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

### Override de Ultra Ball (`TO_HAND`): marcar Meowth ex / Fezandipiti ex como pendientes

Mismo patrón para `Ultra_Ball`: si la carta con mejor puntaje entre las opciones de búsqueda es `Meowth_ex` (con puntaje > 10), se marca la bandera global `_ub_meowth_pending = True` (reseteada por turno, junto a `_ub_engine_pivot_turn`, `_poke_pad_target_id`, `plan` y `_field_at_turn_start` en el bloque `pre_turn != state.turn` del arranque de `agent()`). La rama `PLAY` la consume (doc 12): fuerza `score = 21000` para bajar el Meowth recién buscado — con los guards `field_counts[Meowth_ex] < 2`, `_meowth_ld_free` y `not state.supporterPlayed`. No hace falta guardar el id (Ultra Ball solo usa este mecanismo para Meowth ex). Nótese la relación con `_ub_engine_pivot_turn`: ese otro global se arma **antes**, al puntuar el `PLAY` de la Ultra Ball (cuando dispara `_ub_engine_refresh_pivot`), y sesga el **fetch** hacia Meowth (1300); `_ub_meowth_pending` se arma **después**, al resolverse el fetch, y sesga el **PLAY** del Meowth ya en mano — juntos encadenan UB → buscar Meowth → bajarlo → Last-Ditch → Lillie's dentro del mismo turno.

El mismo override marca `_ub_fez_pending = True` cuando la carta ganadora del fetch es `Fezandipiti_ex` (user, registro_006 paso 90, episodio 88710543 vs Mega Lucario): la rama `PLAY` (doc 12) lo consume forzando `22000` para bajar el cuerpo aunque otro veto lo haya matado. Sin él, el Fezandipiti recién cavado se quedaba en la mano y el **Unfair Stamp del propio turno lo barajaba de vuelta al mazo**: Ultra Ball, dos descartes y el robo de 3 de *Flip the Script* a la basura.

### Override del Last-Ditch Catch (`TO_HAND`): el Supporter buscado se COMPROMETE

Tercer override del mismo patrón, sobre `select.effect.id == Meowth_ex` (user, episodio 88786171 registro_002 paso 22 vs Alakazam, GANADA con error). La carta ganadora del fetch se lee del argmax de `scores`; si es un `_SUPP_PLAY_IDS` (puntaje > 10), el hueco de Supporter sigue libre **y** el Meowth que buscó es un cuerpo **PAGADO este turno** (algún Meowth ex propio con `appearThisTurn`, casando el `serial` del `effect`), se anota `_ld_supp_comprometido = <id>`.

El guard del cuerpo pagado es la diferencia clave: bajar el Meowth desde la mano cuesta 2 premios en la banca y su único pago es el Supporter, así que la búsqueda hay que **cobrarla hoy**; el *Last-Ditch* de un Meowth ex de turnos anteriores es gratis y puede guardar el Supporter para el turno siguiente sin comprometer nada (mismo criterio que `_meowth_skip_fetch`, doc 09).

El bloque consumidor vive al final de `agent()`, justo después de "revocar vetos de ORDEN" y antes de los tiers: con `MAIN`, `not supporterPlayed` y la carta comprometida **ofrecida** en este menú, se sube su `PLAY` a `max(score, SCORE_LD_SUPP_COMPROMETIDO)` (8000). Es una regla de **compromiso, no de valor**: el recurso ya se gastó, así que se aplica *después* de todos los vetos de la rama `PLAY` — son justo ellos los que contradicen una búsqueda ya pagada. En el registro el que la contradecía era `no_barajar_ultimo_xerosic` (`−1`), y el agente jugaba el `Dawn` que ya tenía en la mano dejando muerta la `Lillie's Determination` recién buscada. Se desarma solo si la carta deja de estar ofrecida (coste de una Ultra Ball, barajada…) o si el hueco ya se gastó.

Es **un solo gesto**: el piso, y NO un veto al resto de `_SUPP_PLAY_IDS` de la mano. Las dos mitades se midieron por separado (self-play vs 4 mazos rivales, 1500 partidas por celda, 6000 por variante): sin la regla 83.45%, piso + veto 82.78% (−0.67), **solo piso 83.85% (+0.40)**, solo veto 83.45%. El piso ya está por encima de la banda normal de cualquier otro Supporter (el más alto es Xerosic, ~7300), así que el compromiso gana el hueco sin vetar a nadie; lo único que añadía el veto era ganarle también a un Supporter **decisivo** (score > 8000: un Boss's que gana la partida), que es justo el caso en el que el compromiso debe ceder.

Es la **otra mitad** de `_meowth_fetch_pierde_el_turno` (doc 09): aquel *predice*, antes de bajar el Meowth, que el fetch se llevará el hueco; este *cobra* la predicción después — y cubre el caso que aquel no mira, **nuestro primer turno**, donde la línea anti-donk baja el Meowth igual.

### Veto de estadio en el primer turno propio

`_our_first_turn_guard` identifica **nuestro** primer turno de acción (turno 1 yendo primero / turno 2 yendo segundo). Tiene **dos** excepciones:

1. **`_replace_opp_stadium_ok`**: yendo segundos en el turno 2 con un estadio rival en juego (`stadium_id != 0` y distinto de `Forest_of_Vitality`), SÍ se permite jugar estadio para reemplazarlo.
2. **`_crustle_stadium_before_lillie`** (regla del user): yendo segundos en el turno 2 **contra Crustle**, con el Supporter del turno sin jugar y una `Lillie_Determination` en la mano. El veto general existe para no regalarle el Forest a un rival que lo reemplace enseguida; el mazo Crustle no juega estadio (o lleva una o dos copias sueltas), así que esa premisa no se cumple. Y conservarlo **no es gratis**: Lillie's Determination baraja la mano entera en el mazo, de modo que guardar el estadio teniendo la Lillie's en la misma mano es *perderlo*. Las dos jugadas caben en el mismo turno si el estadio va primero, y el tier `_TIER_STADIUM` (50) ya lo antepone al Supporter (tier 0). El gate es `_op_juega_crustle(op_state)` —la **línea** Crustle en el tablero (`CRUSTLE_LINE_IDS`)— y no el flag `op_is_crustle_deck`, que significa "muro inmune a ex" y también se enciende con Sylveon/Eevee: esos comparten la inmunidad, no la ausencia de estadio. Es el espejo por ORDEN de la regla `t1_segundos_crustle_estadio_antes_de_lillie` de `_REGLAS_FOREST_PLAY` (doc 04), que concede el score; sin esta excepción el veto duro de aquí lo aplastaba.

Fuera de esos dos casos, cualquier opción `PLAY` de `CardType.STADIUM` se fuerza a `−99999` y su índice se guarda en `_vetoed_stadium_idxs`, que además se filtra del `desc_indices` final (cinturón y tirantes). Es lo que hace que el estadio solo aparezca jugable a partir del turno 3.

### Revocar vetos de ORDEN sobre habilidades

Corre justo **antes** del bloque de tiers, solo en `context == SelectContext.MAIN`, y solo si `_ability_order_veto` no está vacío. Ese diccionario lo llena la rama `OptionType.ABILITY` (doc 13) con `{índice de opción: (score_real, ids de las cartas que deben jugarse antes)}` cuando una habilidad se veta por **ORDEN** ("primero X, después la habilidad") y no por **VALOR**. Hoy lo usa *Flip the Script* de Fezandipiti ex con sus dos bloqueadores, `Unfair_Stamp` (`_stamp_blocks_supp_chain`) y `Lillie_Determination` (`_lillie_blocks_fez_ability`).

**Por qué existe** (user, registro_006 paso 78 vs Archaludon ex, PERDIDA): el paso 78 ofrecía Lillie's, Boss's, *Flip the Script* del Fezandipiti ex recién bajado con una Ultra Ball, y atacar. Tres reglas correctas por separado se bloquearon en círculo — la habilidad vetada por "primero Lillie's", Lillie's vetada por `cede_a_boss_ejecutable` (−1) y Boss's degradada a `20` por `sin_atacante_banca_cede_a_lillie` — así que ninguna de las tres se jugó, el ataque (`1100`) ganó el menú y el robo de 3 se perdió. La pérdida es **irrecuperable**: la habilidad es una vez por turno y su condición de activación (que nos noquearan un Pokémon en el turno anterior) se va con el turno.

Un veto de orden solo es válido mientras el "primero X" **vaya a ocurrir**. Se revoca (`scores[i] = score_real`) en dos casos, ambos agnósticos del mazo rival — solo miran nuestra mano y el menú:

- **(a) ningún bloqueador está ofrecido y jugable** (`score > 0`) en este mismo menú: sin X jugable no hay "después de X". Es el caso del paso 78 y el de cualquier bloqueador que se quede en la mano por falta de objetivo legal.
- **(b) el bloqueador vive pero el turno se cierra en esta misma acción**: no queda ninguna otra jugada viva que no sea un bloqueador o un cierre de turno, **y** el bloqueador puntúa por debajo de la mejor opción `ATTACK`/`END`. Con ese recorte todas las opciones vivas están en el tier `0`, ningún tier puede reordenarlas y la comparación de scores es exacta, así que el cierre de turno es seguro.

Fuera de esos dos casos el veto se mantiene y el orden pedido se respeta tal cual: si el bloqueador gana el menú se juega primero y, al salir de la mano, el veto se apaga solo en el menú siguiente. Los vetos de **VALOR** (el freno de deck-out de *Flip the Script*, mazo ≤4) se evalúan antes de registrar nada y nunca se revocan.

### Orden de jugada por tiers en contexto `MAIN`

El bloque impone, dentro de las opciones ya puntuadas positivamente, la secuencia **1) estadio → 2) evoluciones (y básicos si no hay BCS pendiente) → 3) Poke Pad → 4) Bug Catching Set → 5) bajar básicos con un BCS pendiente → 6) cargar energía**, con la energía que resuelve un KO este turno conservando prioridad máxima. Solo aplica en `context == SelectContext.MAIN` y solo reordena opciones con `scores[i] > 0` — los vetos nunca son "ascendidos" por un tier alto.

**BCS antes de bajar un Pokémon** (user, log 88166559 paso 6 vs Archaludon, GANADA con error): mirar los 7 de arriba y coger hasta 2 Pokémon {G} / Energía Planta cambia **qué** cuerpo bajamos y con **qué** lo cargamos, así que decidir el cuerpo antes de esa información es decidir a ciegas. En ese log el agente bajó el Meowth ex (motor Lillie's, 21800) con el BCS (12200) en la mano y el BCS acabó trayendo un Chikorita — cuerpo de UN premio, mejor candidato que un ex de dos — con el slot ya gastado; en el turno 3 bajó los DOS Ogerpon ex y jugó el BCS con la banca ya **llena**, así que el Applin encontrado no pudo bajar. Reordenar no cuesta nada: jugar el BCS no consume la bajada, ni el adjunte, ni el ataque. Se implementa **demotando la bajada** de Pokémon a `_TIER_DEVELOP_TRAS_BCS` y **no** promoviendo el BCS, para que las EVOLUCIONES conserven `_TIER_DEVELOP` y sigan precediéndolo (promoverlo adelantaba también la evolución a Hydrapple ex y rompía sus dos tests). Consecuencia transitiva aceptada: con BCS y Poke Pad a la vez en mano, la bajada cede también al Poke Pad — coherente, ambos son cartas de cavar 7 antes de comprometerse. La democión exige que el BCS esté **ofrecido en el menú y con `score > 0`** (`_bcs_play_idx`): si no fuera jugable, posponer el cuerpo lo dejaría sin bajar. Los tiers se renumeran ×10 para insertar el nivel nuevo conservando todos los demás órdenes relativos.

```python
_TIER_WIN_ATTACK = 70
_TIER_KO_ENERGY = 60
_TIER_STADIUM = 50
_TIER_DEVELOP = 40
_TIER_POKE_PAD = 30
_TIER_BUG_SET = 20
_TIER_DEVELOP_TRAS_BCS = 15   # bajar un Pokemon cede al BCS pendiente
_TIER_ENERGY = 10
```

El resto de opciones (`ATTACK`/`END`/Supporters/Ultra Ball normal/habilidades no promovidas) se queda en el tier por defecto `0` y compite solo por `score`. Asignación:

- **`OptionType.ATTACK` con `_active_attack_wins_now and plan.attacker == 0`** → `_TIER_WIN_ATTACK`: cerrar la partida antes que cualquier carga o desarrollo.
- **`OptionType.RETREAT` con `_suicide_swap_win_promote`** → `_TIER_WIN_ATTACK` también: es la MISMA jugada (cerrar la partida este turno), solo que el rematador está en la banca. Sin este tier, la retirada (score `9600`, tier `0`) la aplastaba por **orden** cualquier carga de energía (tier ENERGY) pese a valer menos — en el registro_016 paso 184 el adjunte de la Planta puntuaba `41000` —, el turno se gastaba adjuntando y el remate no llegaba.
- **`OptionType.EVOLVE`** → siempre `_TIER_DEVELOP`: evolucionar se juega antes que cargar energía o Poke Pad.
- **`OptionType.ATTACH`**: se calcula `_po_is_ko_energy` — cierto si `plan.energy` (el plan requiere justo esta energía), `plan.remain_hp <= 0`, `plan.attacker >= 0`, y el adjunte apunta exactamente al Pokémon designado (activo si `plan.attacker == 0`, o el índice de banca `plan.attacker == 1 + inPlayIndex`). Si es así, `_TIER_KO_ENERGY`; si no, `_TIER_ENERGY`.
  - **Excepción `_tapu_future_charge`**: si el flag está activo (el activo YA noquea con su energía actual, Meganium en juego, Tapu Bulu de banca por cargar) y el adjunte apunta al **activo**, se fuerza `_po_is_ko_energy = False`. Sin esta exclusión, el tier 6 del adjunte al activo aplastaba (6 > 1) la carga de Tapu Bulu de banca (score 40000 pero tier ENERGY), desperdiciando la energía en un atacante ya listo; al bajarlo a tier ENERGY, el desempate dentro del tier lo gana Tapu por score.
- **`OptionType.PLAY`**: `Poke_Pad` → `_TIER_POKE_PAD`; `Bug_Catching_Set` → `_TIER_BUG_SET`; **`Ultra_Ball` con `scores[i] > 31000` → `_TIER_ENERGY`** — es la Ultra Ball del motor `_ub_engine_refresh_pivot` (31450, doc 12): los ítems van en tier 0 y el adjunte manual (tier ENERGY, ~31410) la aplastaba por tier pese al score; subirla al tier ENERGY hace que dentro del tier decida el score (31450 > 31410), mismo patrón que Teal Dance. La UB normal (≤12500) conserva su tier 0; `CardType.STADIUM` → `_TIER_STADIUM`; `CardType.POKEMON` → `_TIER_DEVELOP`, o **`_TIER_DEVELOP_TRAS_BCS` si hay un Bug Catching Set jugable en el menú** (`_bcs_play_idx >= 0`). Cualquier otro `PLAY` (Supporters, Night Stretcher, Unfair Stamp…) queda en tier 0.
- **`OptionType.ABILITY`**: si la carta es `Teal_Mask_Ogerpon_ex` (**Teal Dance**) → `_TIER_ENERGY`. Teal Dance adjunta 1 Planta Y roba una carta, así que debe jugarse ANTES que cualquier adjunte manual; sin esto quedaba en tier 0 (por debajo del tier ENERGY de los adjuntes) y el orden anteponía una carga manual pese a que Teal Dance puntúa más alto, desperdiciando el robo. Dentro del tier decide el score (Teal Dance ~31500 gana al adjunte ~31410). Las cargas de KO letal siguen en `_TIER_KO_ENERGY`. Con el mismo guard `score >= 29000` suben también **Ripening Charge** (`Hydrapple_ex`) y **Flip the Script** (`Fezandipiti_ex`, `FEZ_DRAW_ABILITY_SCORE` = 31700): las tres compiten por score puro dentro del tier — habilidad que HABILITA el KO de hoy (41000+) > robo de 3 de Flip the Script (31700) > cargas de desarrollo (≤ 31600). Una habilidad **degradada o vetada** (Teal Dance/Ripening de reserva a 7500, Flip the Script con el freno de deck-out o con un veto de ORDEN sin revocar) se queda en tier 0, que es justo lo que evita que domine el menú por ORDEN. `Grand_Tree` va a `_TIER_STADIUM_ABILITY`; el resto de habilidades, a tier 0.

### Redes de rescate del turno muerto

Cuatro redes finales, todas con la misma forma: se ejecutan **después** de los vetos individuales, calculan la mejor opción del menú por `(tier, score)` y, **solo si esa mejor opción no produce nada**, resucitan una jugada concreta por encima del "no hacer nada". Son deliberadamente las últimas: ninguna regla de matchup se debilita mientras el turno produzca algo.

1. **Rescate de Lillie's** (`_rescate_lil`): el Supporter no se acumula, así que con el turno muerto y Lillie's vetada en la mano, se pone a `1500`. Cede solo ante razones concretas (Xerosic vs Alakazam, aritmética de deck-out ≤10).
2. **Rescate de Meowth ex** (`_mw_rescate`): hermano del anterior cuando la Lillie's está en el MAZO. Exige `_ready_attacker_count == 0` (el turno está muerto por falta de desarrollo, que es lo que arregla refrescar) y que el fetch aporte algo (`_meowth_fetch_id` no redundante y que no pierda el hueco de Supporter).
3. **Red anti-banca-vacía** (`_sb_pick`): con `bench_count == 0`, nunca terminar el turno sin desarrollar — prefiere el buscador (Ultra Ball → básico) sobre bajar un básico cualquiera. No aplica si atacar ya gana.
4. **Red anti-turno-estéril con Ultra Ball** (`_st_basico_util` / `_st_evo_util`): con banca poblada, si el turno no produce nada y la Ultra Ball vetada tiene un objetivo **útil** en el mazo, cavar produce más que END.

Sobre la cuarta hay tres precisiones importantes, todas del mismo tipo — *"útil" significa que la carta cavada se va a poder jugar*:

- **Un turno que acaba atacando de verdad NO es un turno muerto** (registro_006 paso 98 vs Mega Lucario ex, PERDIDA). La premisa de la red es "la alternativa a cavar es END", pero `scores[mejor] <= 0` no significa END: un ATAQUE normal puntúa `−1` por defecto (es el *fallback* del argmax) y los ítems **no consumen el ataque**. En aquel turno el menú solo ofrecía dos Ultra Ball y un *Syrup Storm* de 210: la red las resucitaba a `200`, el agente pagaba 4 cartas de mano por dos Meowth ex muertos y lanzaba igual el mismo ataque tres acciones después. Ahora se recorre el menú buscando un `ATTACK` con daño real (impreso o base > 0, descartando los ya marcados `SCORE_USELESS_ATTACK` por inmunidad) — mismo criterio que el rescate de Lillie's — y si lo hay, `_st_sterile = False`.
- **Meowth ex solo cuenta como básico útil si su *Last-Ditch Catch* puede producir** (`not supporterPlayed`, sin Watchtower, `_meowth_ld_free`, menos de 2 en juego): es un cuerpo de 2 premios cuyo único valor es buscar un Supporter. Mismo criterio que la regla `last_ditch_no_produce` del fetch (doc 11) y que `_ub_cavar_meowth_se_juega`.
- Las dos guardas que ya existían: `_st_pokemon_en_menu` (si el menú ya ofrece bajar/evolucionar un Pokémon y el scorer lo vetó, el turno no está muerto por falta de cuerpos) y `_ub_coste_destruye_carta_mejor` (el veto por **coste** es aritmética de cartas y no se revoca por aburrimiento, doc 04).

La **excepción de bloqueo de Objetos** de esta red (`_st_item_lock`: con Budew en el campo rival —o contra Dragapult, que lo lleva— la Ultra Ball es *úsala o piérdela*, así que sí se permite cavar algo que sirva para el turno SIGUIENTE) ya no se calcula aquí inline: es `_bloqueo_de_items_inminente`, resuelto una vez por decisión y compartido con `_ub_meowth_para_manana` vía `ctx.item_lock_incoming` (doc 04). Motivo del reparto: esta red solo se enciende con el turno **estéril**, y el turno del registro_002 paso 17 vs Dragapult tenía un ataque de verdad (un Chikorita pegando 10) — el bloqueo de Objetos no depende de que el turno esté muerto, así que el predicado tenía que vivir fuera.

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
