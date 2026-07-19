# main.py — Bucle de puntuación: RETREAT (retirada del activo) (líneas 11608–12609)

## Rol en el agente

Esta es la rama `elif o.type == OptionType.RETREAT:` del gran bucle `for o in select.option:`. Decide, para **cada** opción de retirar al Pokémon activo que el motor ofrece en contexto `MAIN`, un `score` que compite con el resto de opciones del turno (jugar carta, adjuntar energía, atacar…). A diferencia de la mayoría de las ramas del bucle, RETREAT casi nunca actúa sola: **lee** un conjunto grande de banderas y el objeto `plan` que ya fueron calculados antes (preámbulo ~1420–2000, análisis de amenaza/pivotes ~2600–2820, `_ex_stuck_promo_ready` ~4555–4680, `_lucario_sac_pivot` ~5758–5794) y simplemente traduce esas conclusiones en una puntuación alta (para forzar la retirada) o en un veto `-1` (para forzar que el activo se quede a atacar o a resistir).

Estratégicamente, RETREAT es el mecanismo con el que el agente **pivota**: cambia de atacante cuando el activo está "estancado" (sin energía suficiente, bloqueado por una inmunidad, o condenado a morir sin remate), protege cuerpos valiosos (`Hydrapple ex`, ex de pocos HP) sacrificando cuerpos baratos (`Tapu Bulu`, básicos de 1 premio), y evita malgastar el coste de retirada en cambios que no aportan nada (recolocar la misma especie, subir un cuerpo que tampoco puede atacar). Todo el bloque trabaja sobre `_active_reloc = my_state.active[0]` (el Pokémon que se retiraría) y sobre `my_state.bench` (los candidatos a promoción); la promoción en sí la resuelve después el contexto `SWITCH`/`TO_ACTIVE` (`_best_promote_card`, `_refresh_promote_prefer_basic`, documentados en `main-10`), así que RETREAT solo decide **si** conviene abrir esa puerta, no **a quién** subir.

## Detalle por bloque

### Cálculo de `_same_species_retreat` (líneas 11608–11688)

```python
_active_reloc = my_state.active[0] if my_state.active else None
...
_same_species_retreat = _ss_only_same or _ss_prefer_same
```

Regla anti-desperdicio (user, log 86510119 paso 26, vs Dragapult, **PERDIDA**): si retirar el activo solo va a volver a subir un Pokémon de la **misma especie**, la retirada no cambia nada salvo gastar la energía del coste de retirada — se cancela más abajo (línea 12606). Dos condiciones se OR-ean:
- **(a) `_ss_only_same`**: todos los candidatos de banca (`_ss_bench`) comparten `id` con `_active_reloc` — literalmente no hay otra opción de promoción.
- **(b) `_ss_prefer_same`**: reproduce la lógica de "preferir básico" de la promoción (`_refresh_promote_prefer_basic`, ver `main-10`): tenemos `Lillie's Determination` en mano, ningún atacante de banca listo (`_ss_bench_atk_ready`, evaluado con `_can_attack_eff` incluyendo el adjunte de este turno) y el rival no es inmune a ex/habilidad (`_ss_prefer_basic`). Si además el activo ya es un básico no-ex (`_ss_act_is_basic`) y el básico que la promoción subiría sería de la misma especie (`_ss_same_basic` — caso especial `Applin`, que tiene máxima prioridad de promoción, o "todos los básicos candidatos son la misma especie que el activo"), retirar tampoco cambia nada.

### `_meg_retreat_for_hydra` — Meganium activo con Hydrapple ex listo en banca (líneas 11690–11703)

```python
if (_active_reloc is not None and _active_reloc.id == Meganium
        and can_switch
        and not (op_is_crustle_deck or op_has_ex_immune_active
                 or op_has_ex_immune_bench or op_is_sylveon_deck)):
    for _mrh_bp in (my_state.bench or []):
        if _mrh_bp is not None and _mrh_bp.id == Hydrapple_ex:
            _meg_retreat_for_hydra = True
```

Con `Meganium` activo y un `Hydrapple ex` **de cualquier carga** en banca, conviene retirar a Meganium (motor de energía, no atacante prioritario) para subir al ex. Al quedar Meganium en banca, `Wild Growth` se sigue aplicando (duplica energía Planta en todo el campo, no solo la del activo), así que no se pierde el multiplicador. Se excluye explícitamente si el rival es inmune a ex (`Crustle`/`Sylveon`/`op_has_ex_immune_*`): ahí Hydrapple ex haría 0 daño y no tendría sentido exponerlo.

### `_grd_prefer_attack` — preferir que el activo ataque en vez de retirarse (líneas 11705–11743)

Calcula, con la función local `_grd_damage(_p)` (répica de las fórmulas de daño de cada atacante principal contra el HP/energía actuales del activo rival `_grd_opa`), si **el activo ya puede atacar** (`_grd_active_can_attack`) y si **ningún** Pokémon propio (activo o banca) puede noquear ya al rival (`_grd_any_ko`). Si el activo puede pegar y nadie remata todavía, se marca `_grd_prefer_attack = True` — esta bandera se traduce más abajo (línea 12033) en veto directo (`score = -1`): no tiene sentido retirar a un atacante funcional cuando no hay un KO disponible que justifique el pivote. No aplica contra `Crustle`/`Cornerstone` (matchups de muro donde la lógica de bloqueo manda).

### `_active_can_ko_now` — ¿el activo ya remata este turno? (líneas 11745–11771)

Repite, para el propio `_active_reloc`, el cálculo de daño base por identidad (Dipplin, Hydrapple ex, Teal Mask Ogerpon ex, Tapu Bulu, Fezandipiti ex, Meganium, Pinsir) con sus umbrales de `ATTACK_ENERGY_REQ`, aplica `_our_effective_damage` y compara contra el HP del activo rival. Es el predicado central que después evita pivotar cuando **ya** hay un remate garantizado con el propio activo (salvo las excepciones explícitas descritas abajo).

### `_hydra_ex_protect_retreat` — proteger a Hydrapple ex activo en riesgo (líneas 11773–11799)

Si el **activo** es `Hydrapple_ex`, puede retirarse (`can_switch`), está en riesgo de KO el próximo turno (`active_ko_likely`) y **no** puede rematar ya (`not _active_can_ko_now`), se busca en banca un no-ex listo (`Dipplin` con ≥1, `Tapu_Bulu`/`Meganium` con ≥4 efectivas, `Pinsir` con ≥2) para exponerlo en su lugar. Razón: Hydrapple ex es el motor de aceleración de energía del mazo (carga a Tapu Bulu en un turno vía su habilidad/ataque), así que entregarlo (2 premios) sin necesidad es más costoso que sacrificar un cuerpo secundario.

### `_active_ex_fragile_pivot` y `_hydra_lethal_promote` — pivote letal a Hydrapple ex de banca (líneas 11801–11849)

```python
_active_ex_fragile_pivot = (
    _active_reloc is not None
    and _active_can_ko_now
    and _active_reloc.id in OUR_EX_IDS
    and _active_reloc.id != Hydrapple_ex
    and (_active_reloc.maxHp or 0) < 330
    and op_state.active and op_state.active[0] is not None
    and not (my_prize <= prize_count(op_state.active[0])))
```

Regla central del "pivote Hydrapple" (user; log 86338560 paso 114, **GANADA** vs Mega Lucario; generalizada en log 86505760 paso 55, **GANADA** vs Alakazam; caso original log 86412738 paso 145 vs Hops):
- **Caso base** (`not _active_can_ko_now`): si el activo NO puede rematar este turno, pero un `Hydrapple ex` de **banca** con ≥2 energía efectiva SÍ tiene un `Syrup Storm` letal (`30 + 30*total_grass >= HP rival`), se activa `_hydra_lethal_promote` para retirar y promoverlo.
- **Excepción `_active_ex_fragile_pivot`**: aunque el activo YA pueda noquear (`_active_can_ko_now`), si es un **ex frágil** (2 premios, distinto de Hydrapple ex, con menos de 330 HP máximos — el "muro" de referencia) y el Hydrapple ex de banca TAMBIÉN remata, **siempre** se prefiere pivotar: mismo KO, pero se deja el muro de 330 HP como activo en vez de exponer el ex frágil a los golpes del turno siguiente. La única excepción a la excepción: si atacar con el activo YA gana la partida este turno (`my_prize <= prize_count(op_state.active[0])`), no hay "turno futuro" que proteger y se ataca directo sin pivotar.

Este flag se **anula** más abajo (líneas 11912–11931) si el activo es `Tapu_Bulu` y no aplica la reserva anti-muro (ver siguiente bloque): Tapu Bulu cargado que remata siempre debe atacar en vez de cederle el turno a Hydrapple ex.

### `_ogerpon_lethal_promote` — pivote de KO con Teal Mask Ogerpon ex tras Teal Dance (líneas 11851–11898)

Regla (user, log 86583929 turno 4, vs Alakazam, **PERDIDA**): el scorer "greedy" evaluaba a los `Teal Mask Ogerpon ex` de banca por su energía **actual**, sin modelar la rampa de *Teal Dance* (adjuntar 1 Planta + robar) tras promoverlos, así que nunca "veía" esta línea de KO. Aquí se simula explícitamente:
- Condiciones previas: el activo está **estancado** (`not _active_can_ko_now`), no es ya un Ogerpon, el rival no es inmune a ex, y hay una Planta disponible para Teal Dance — en mano (`hand_counts[Basic_Grass_Energy] >= 1`) o recuperable con `Night_Stretcher` desde el descarte **o desde la energía que la propia retirada acaba de descartar del activo** (`_physical_energy(len(_active_reloc.energies)) >= 1`, siempre Planta en este mazo).
- Para cada Ogerpon de banca: `_olp_eff_after = energía_actual + _grass_attach_unit()`; si alcanza ≥3 efectivas, se calcula el daño de `Myriad Leaf Shower` (`30 + 30*(energía_tras_Teal_Dance + energía_del_rival)`) vía `_our_effective_damage`. Si iguala o supera el HP del rival, `_ogerpon_lethal_promote = True`.
- Las acciones posteriores (Night Stretcher, Teal Dance, el ataque final) ya las habilita cada scorer por separado (Teal Dance recibe 31500 cuando habilita el KO, documentado en `main-13`); RETREAT solo abre la puerta retirando al activo estancado.

### Reserva de Tapu Bulu — veto del pivote cuando Tapu ya remata (líneas 11900–11938)

```python
if (_active_reloc is not None and _active_reloc.id == Tapu_Bulu
        and _active_can_ko_now):
    _tapu_ex_immune_match = (op_is_crustle_deck or op_is_cornerstone_deck
                             or op_is_sylveon_deck)
    ...
    _tapu_reserve = (_tapu_ex_immune_match
                     and not _tapu_opa_is_immune_line
                     and not op_has_ex_immune_active)
    if not _tapu_reserve:
        _hydra_lethal_promote = False
```

Un `Tapu Bulu` activo **cargado** que ya remata al rival no debe retirarse: al ser no-ex, si lo noquean solo entrega 1 premio, así que conviene rematar con él en vez de gastar el pivote a Hydrapple ex (que sí entrega 2 premios si lo noquean). Se anula `_hydra_lethal_promote` salvo en la **excepción de reserva** (`_tapu_reserve`): en matchups ex-inmunes (`Crustle`/`Cornerstone`/`Sylveon`) donde el activo rival actual **no** pertenece a la línea inmune (Crustle/Dwebble/Sylveon/Cornerstone/`EEVEE_IDS`), sí se retira a Tapu Bulu para **reservarlo** como el único atacante capaz de dañar al muro cuando aparezca.

`_op_active_is_cubchoo` y `_cub_bench_attacker_ready` (líneas 11933–11938) se calculan aquí para el bloque de veto anti-Cubchoo de más abajo (`_conf_can_attack_pkmn` reutilizado para saber si algún cuerpo de banca ya puede atacar).

### Escalera de prioridad principal — primer bloque `if/elif` (líneas 11940–12066)

Los flags anteriores (y algunos externos calculados antes del bucle) se resuelven en una **escalera de prioridad estricta** — cada rama gana sobre las siguientes por orden de aparición:

| Score | Condición | Razón |
|---|---|---|
| `9000` | `_hydra_lethal_promote` | Prioridad **máxima**: pivote letal a Hydrapple ex de banca, cobrar el premio ya. |
| `8900` | `_ogerpon_lethal_promote` | Pivote letal a Ogerpon ex de banca vía Teal Dance, equiparado casi al máximo. |
| `-1` | `_op_active_is_cubchoo and can_switch and not _cub_bench_attacker_ready` | Vs `Cubchoo`: subir un cuerpo que TAMPOCO puede atacar solo lo expone al mismo ataque y malgasta el pivote; se espera a tener un atacante de banca cargado. |
| `8000` | `_lucario_sac_pivot and _lucario_sac_available and bench_count >= 1 and can_switch` | Anti-2-premios vs Mega Lucario en ciernes (Riolu activo con energía, nuestro turno 1 yendo segundos): retirar el `Teal Mask Ogerpon ex` y sacrificar un cuerpo de 1 premio (`Tapu_Bulu`/`Applin`/`Chikorita`, prioridad definida en `_lucario_sac_available`, calculado en líneas ~5758–5794). |
| `4000 + condition_urgency` | `_conf_should_retreat` | Confusión: activo confundido que puede pagar el coste de retirada y hay un atacante de banca de matchup listo (`_conf_bench_attacker_ready`, líneas ~1953–1969); evita el riesgo de fallar el tiro de moneda de un ataque confuso. `condition_urgency` (definido en líneas 1425–1435: paralizado +5000, dormido +3000, confuso +2000, envenenado +1500, quemado +1200) desempata contra otras condiciones simultáneas. |
| `6000` | `_hydra_ex_protect_retreat` | Proteger al Hydrapple ex activo condenado, exponer un no-ex de banca en su lugar. |
| `6000` | `_ex_stuck_promo_ready and can_switch` | Activo ex bloqueado por un muro inmune (`Crustle`/`Sylveon`) con un atacante no-ex LISTO en banca (calculado en líneas ~4555–4617, `main-13`/`main-10`): retirar evita atacar por 0. |
| `6500` | `_hydra_pivot_active` | Pivote defensivo: activo frágil (`active_ko_likely` o `active_hp_ratio<=0.6`) con un Hydrapple ex de banca a **vida completa** y ≥2 efectivas que noquea al rival (fijado en `plan.attacker` en líneas ~2608–2633). Prioridad alta para ganar sobre "atacar con el frágil". |
| `6450` | `_teal_wall_pivot and can_switch` | Ogerpon activo condenado que YA usó Teal Dance (adjuntó 1 Planta, paga el coste de retirada de 1) pero sigue sin poder atacar: subir al cuerpo de banca más fuerte (Hydrapple ex sano) en vez de regalar el activo. |
| `6450` | `_hydra_wall_pivot` | Variante "sin KO": Ogerpon (o Fezandipiti vía `_feza_lucario_wall`) activo que SÍ puede atacar pero NO noquea, con un muro Hydrapple ex sano en banca que sobrevive al golpe rival (acotado a `op_is_lucario_deck`, log 85856881 paso 127 y log 86342087 paso 130). |
| `6600` | `_tapu_sac_pivot` | Sacrificio de premios: activo ex en riesgo (o líder proactivo con Meganium en juego) con un `Tapu Bulu` de banca YA listo (≥4 efectivas) que noquea al rival; retirar el ex y subir a Tapu reduce el premio entregado si nos remata el rival (2→1). |
| `6550` | `_prize_denial_pivot` | Negación de premios (log 86211357 paso 128, **PERDIDA** vs Mega Starmie): el activo ex condenado, si lo noquean, le daría al rival los premios que le faltan para GANAR; se retira y sube el mejor cuerpo de banca de MENOS premios disponible (no exige que remate, solo que ataque; preferencia: sobrevive > daño > HP), salvo que el propio activo pueda ganar la partida YA. |
| `6400` | `_meg_retreat_for_hydra and not _active_can_ko_now` | Meganium activo → Hydrapple ex de banca (ver bloque dedicado arriba); cede si Meganium ya remata. |
| `-1` | `_nonex_active_hits_wall` | (log 86406907 paso 87, **GANADA** vs Crustle) Activo no-ex que SÍ golpea al muro inmune a ex: nunca se retira, retirarlo solo promovería un ex que hace 0 al muro. |
| `-1` | `_grd_prefer_attack` | El activo puede atacar y nadie remata todavía: mejor atacar que pivotar sin motivo. |
| `-1` | `_active_can_ko_now` | El activo YA remata: no hay razón para pivotar (las excepciones de arriba ya capturaron los casos donde SÍ conviene pivotar pese a esto). |
| `3500` / `2500` | `plan.attacker >= 1` (el plan de amenaza ya apunta a un atacante de banca) | Si el activo actual, tras revisar su energía efectiva y un posible adjunte este turno (`_ra_eff_after`), **no** podría atacar (`not _retreat_active_can_attack`): `3500` (prioridad alta, retirarse no cuesta nada). Si el activo **sí** podría atacar pero el plan igual apunta a otro atacante: `3500` en el primer caso, `2500` cuando el propio activo también podría — retirada de prioridad media (se prefiere seguir el plan pero sin urgencia extrema). |
| `-1` (fallback) | Ninguna de las anteriores | Por defecto, sin activo o sin banderas activas, no se retira. |

`plan.attacker` (documentado en `main-02`) es el "pizarrón compartido" que el análisis de amenaza ya rellenó con el atacante elegido para el turno; muchos de los flags anteriores (`_hydra_pivot_active`, `_hydra_wall_pivot`, `_tapu_sac_pivot`, `_prize_denial_pivot`) lo **reescriben** antes de llegar aquí precisamente para que esta rama `plan.attacker >= 1` los recoja de forma unificada si ninguna de las ramas más específicas de arriba disparó primero.

### Rama sin `plan.attacker` — activo sin plan de pivote explícito (líneas 12067–12601)

Cuando ninguna de las banderas anteriores fijó `plan.attacker`, el bloque cae en el `elif my_state.active and my_state.active[0] is not None:` y razona **desde cero** sobre el activo (`active`), con dos sub-familias de reglas: activos de la línea Meganium/soporte y activos "atacantes principales" (`MAIN_ATTACKERS`).

#### `_bench_ready_for_retreat` y `_fase58_promo_ready` (líneas 12079–12108)

Recalculan, para toda la banca, si hay algún atacante principal ya cargado (`_bench_ready_for_retreat`, mismos umbrales de `ATTACK_ENERGY_REQ` que en otros bloques) y si hay algún básico/stage-1 no-ex disponible como candidato de promoción "barato" (`_fase58_promo_ready`, usado más abajo en la línea 12284).

#### `_meg_only_attacker_retreat` — vs Crustle/Cornerstone con Meganium como único remate (líneas 12110–12173)

Solo si el rival es `Crustle`/`Cornerstone` y el activo **no** es ya Meganium: define `_meg_blk_ko(_p)` (daño de `Dipplin`/`Tapu_Bulu`/`Pinsir`/`Meganium` contra el activo rival vía `_our_effective_damage`) y comprueba si **ningún** otro atacante (activo o banca, excluyendo Meganium) remata ya (`_other_atk_ready_meg`), si **Meganium de banca** sí remataría (`_meganium_bench_ready_meg`) y si el activo actual no remata ya por su cuenta (`_act_ko_rival_meg`, específico para `Teal_Mask_Ogerpon_ex`/`Hydrapple_ex`). Si se cumplen las tres, `score = 3500`: retirar para dejar que Meganium en banca sea quien remate al muro.

#### Ogerpon vs Crustle/Cornerstone sin remate (líneas 12175–12228)

Si el activo es `Teal_Mask_Ogerpon_ex` contra `Crustle`/`Cornerstone`: veto si no se puede retirar (`-1`); si el propio Ogerpon YA remata al rival, veto (`-1`, debe atacar); si no remata, busca en banca un atacante que SÍ golpee al muro (`Pinsir`≥2, `Tapu_Bulu`≥4, y — solo si es específicamente Crustle — `Dipplin`≥1/`Meganium`≥4; o Hydrapple ex/Ogerpon ex si el rival no es inmune a ex) y da `score = 3400` si lo hay, `-1` si no.

#### Cornerstone específico con Habilidad (líneas 12233–12244)

Si el rival es `Cornerstone` y el activo depende de Habilidad (`OUR_ABILITY_IDS`) contra el propio `Cornerstone_Mask_Ogerpon_ex` activo rival: `score = 3400` si hay un `Tapu_Bulu` de banca con ≥4 energía, si no `-1`.

#### Crustle con ex activo (líneas 12246–12280)

Si el rival es `Crustle` y el activo es un ex nuestro: si el propio ex YA remata (`_cr_ex_can_ko`), veto `-1` (debe atacar). Si no, busca en banca `Tapu_Bulu`≥4 / `Dipplin`≥1 / `Meganium`≥4 listos (`_crustle_bench_atk`): `3400` si hay, `-1` si no.

#### Retirada preventiva por HP y disponibilidad de promoción básica (líneas 12282–12285)

```python
elif (active.id in OUR_EX_IDS and (not can_attack) and can_switch
      and estimated_op_damage >= (active.hp or 0)
      and _fase58_promo_ready):
    score = 3300
```

Si el activo ex **no puede atacar este turno**, el daño estimado del rival (`estimated_op_damage`, calculado en el preámbulo vía `_op_best_damage_vs`) lo noquearía, y hay al menos un básico/stage-1 no-ex en banca al que promover: retirarlo preventivamente (score medio, `3300`) en vez de dejarlo morir sin haber hecho nada.

#### Vetos específicos de Fezandipiti ex (líneas 12287–12292)

Si `plan.attacker == 0` (el propio Fezandipiti activo ya es el atacante planeado) o si es el segundo turno propio yendo segundos (`state.turn == 2 and not we_go_first`), veto `-1`: no retirarlo en esas circunstancias puntuales.

#### `NON_ATTACKERS` — Meganium/Meowth ex/línea Chikorita como activo (líneas 12294–12470)

```python
NON_ATTACKERS = (Meganium, Meowth_ex, Chikorita, Bayleef, Applin)
```

Sub-rama extensa para cuando el activo es un Pokémon de "desarrollo" en vez de un atacante final:

- **`_has_bench_attacker`/`_bench_has_only_non_attackers`**: si hay algún `MAIN_ATTACKERS`/`STRATEGIC_ATTACKERS` (= `MAIN_ATTACKERS`, alias explícito con comentario "incluye Meganium") en banca, y si la banca **solo** tiene no-atacantes.
- **`_HAND_PLAYABLE_ATTACKERS` (línea 12308)** — `(Tapu_Bulu, Teal_Mask_Ogerpon_ex)`: junto con `_has_attacker_in_hand` (líneas 12309–12321), comprueba si en la **mano** hay un atacante jugable este turno (banca con hueco, `bench_count < 5`, y no ya en juego) o si hay un `Fezandipiti_ex` en mano jugable a partir del turno 2. Se usa para **no** retirar cuando lo mejor es primero *bajar* ese atacante de mano en vez de forzar un pivote con lo que ya hay en banca.
- **`_bench_attacker_ready` (líneas 12331–12348)**: a diferencia de `_has_bench_attacker` (que solo mira identidad), exige que el candidato tenga la energía efectiva suficiente **ya**, o que llegue adjuntando una Planta este turno (`_grass_attach_this_turn`). El comentario documenta explícitamente el bug que esto corrige: sin esta comprobación, el agente retiraba el activo para subir a un atacante de banca SIN cargar (que tampoco podía atacar), desperdiciando el turno y el coste de retirada.
- **`_fragile_doomed_pivot` (líneas 12358–12367)**: si el activo es una pre-evolución frágil (`Chikorita`/`Bayleef`) condenada este turno (`active_ko_likely` o `estimated_op_damage >= HP`), y hay en banca **algún** cuerpo que sobreviva al mejor golpe rival (`(bp.hp or 0) > _op_best_damage_vs(bp)`), conviene retirar aunque ese cuerpo de banca todavía no pueda atacar: resguarda la pre-evolución (se evoluciona luego en banca) y evita entregarla gratis.

Con esos ingredientes, la escalera para `active.id in (Chikorita, Bayleef, Meganium)` (líneas 12369–12404):

| Score | Condición |
|---|---|
| `6500` | Vs `Crustle`, activo es `Chikorita` y **no** hay otro `Chikorita` en banca (`field_counts[Chikorita] <= 1`) con `bench_count >= 1`: regla anti-Crustle específica (log 86607718 turno 2, **PERDIMOS**) — Chikorita activo es un lastre que no daña al muro; se retira aunque no haya todavía un atacante LISTO en banca (rompe el veto general de "atacante sin energía" de la línea siguiente). |
| `6000` | `_has_bench_attacker and _bench_attacker_ready` — hay un atacante de banca cargado y listo. |
| `5800` | `_fragile_doomed_pivot` — activo frágil condenado, cuerpo de banca que sobrevive (aunque no ataque aún). |
| `-1` | `_has_bench_attacker and not _bench_attacker_ready` — hay un atacante identificado en banca pero SIN energía: mejor seguir cargándolo con el activo puesto que retirar ahora no gana nada. |
| `-1` | `_bench_has_only_non_attackers and _has_attacker_in_hand` — mejor bajar el atacante de la mano que pivotar con lo que hay en banca. |
| `5500` | Caso restante (fallback): retirar igualmente. |

Para `active.id == Meowth_ex` (líneas 12405–12463): calcula `_has_ready_bench_for_meowth` (algún `MAIN_ATTACKERS`-equivalente listo, tabla `_ATK_REQS_RETREAT`) y, si el propio Meowth ex es **débil** al tipo del activo rival (`_meowth_weak_to_op`), busca un cuerpo de banca que NO comparta esa debilidad y esté cargado (`_safe_chargeable_body`) para dar prioridad máxima (`6000`) a protegerlo retirándolo antes de que lo golpeen con ventaja de tipo. Si no hay ese riesgo mitigable, `5000` si hay cualquier atacante listo en banca, si no veto `-1`.

Para cualquier otro `NON_ATTACKERS` (fallback genérico, líneas 12464–12470): `3000` si hay un atacante identificado en banca (`_has_bench_attacker`), veto si solo hay no-atacantes y hay uno jugable en mano, si no `2500`.

#### `active.id in STRATEGIC_ATTACKERS` — el activo YA es un atacante principal (líneas 12472–12599)

Cuando el activo es uno de los siete `MAIN_ATTACKERS` y no se disparó ninguna de las ramas de matchup anteriores:

- **Si no puede atacar aún (`not _active_can_attack`)**: `2500` si hay otro atacante principal ya listo en banca (`_has_ready_bench`), si no veto `-1` (mejor seguir cargándolo).
- **Retiro defensivo por condena sin remate (líneas 12497–12522)**: si el activo puede atacar pero **no** noquea al rival (`plan.remain_hp` no queda ≤0) y el daño estimado del rival lo noquearía el turno siguiente, busca en banca un atacante principal que SOBREVIVA a ese mismo golpe rival (`(bp.hp or 0) > _op_best_damage_vs(bp)`) Y ya pueda atacar (`_can_attack_eff`): si existe, `5600` (retirar a un muro que además presiona); si no, veto `-1`. El comentario aclara el porqué: sin esta regla, el código por defecto asumía "si puedo atacar, ataco" y dejaba morir al activo condenado sin necesidad.
- **Casos especiales de bypass de habilidad enemiga (líneas 12524–12595)**: contra `Drednaw` (activo `Hydrapple_ex`/`Tapu_Bulu`, busca `Meganium`≥4 o `Dipplin`≥1 en banca, `5500`/`−1`), contra `Sylveon` (activo ex, busca `Tapu_Bulu`≥4/`Meganium`≥4/`Dipplin`≥1 no-ex en banca, `5500`/`-1`), y con `Neutralization Zone` activa contra un activo rival sin "rule box" (busca `Tapu_Bulu`/`Meganium`/`Dipplin`/`Pinsir` de banca que sí golpeen, `5000`/`-1`). Los tres siguen el mismo patrón: si el activo actual está anulado por una regla especial del rival y hay un cuerpo de banca capaz de esquivarla, se retira; si no, veto.
- **Fallback final**: `-1` en cualquier otro caso (activo listo para atacar sin amenaza inminente, o sin candidato de banca).

### Cancelación final por `_same_species_retreat` (líneas 12603–12607)

```python
if _same_species_retreat and score > 0:
    score = -1
```

Después de que **cualquiera** de las ramas anteriores asigne un `score > 0`, se aplica como último filtro la regla anti-desperdicio del primer bloque (línea 11625): si retirar solo va a recolocar la misma especie en el activo, se anula la retirada pase lo que pase. Es la única comprobación que se aplica de forma transversal a toda la escalera.

## Interacciones

- **Con `plan` (`main-02`, `main-07`)**: `plan.attacker >= 1` es la señal más fuerte de que el análisis de amenaza previo ya decidió qué atacante de banca debe recibir el turno; buena parte de la escalera de RETREAT (líneas 11940–12066) solo traduce a `score` los pivotes que el análisis de amenaza ya escribió en `plan` (`_hydra_pivot_active`, `_hydra_wall_pivot`, `_tapu_sac_pivot`, `_prize_denial_pivot`, calculados en líneas ~2598–2814).
- **Con `_ex_stuck_promo_ready` y la familia anti-muro (`main-10`/`main-13`)**: la detección de bloqueo por inmunidad (`_active_blocked_by_wall`, `_wall_bench_attacker_ready`, líneas ~4555–4617) alimenta directamente el score `6000` de la línea 11976; `_teal_dance_ko_pivot`/`_ripen_retreat_ko_pivot` (líneas ~4646–4680) son los mecanismos que CARGAN al activo bloqueado hasta que pueda pagar su propio coste de retirada, momento en que esta rama de RETREAT puede finalmente activarse.
- **Con `_lucario_sac_pivot`/`_lucario_sac_available` (líneas ~5758–5794, `main-09`)**: fijan directamente el score `8000` (línea 11970); la prioridad de sacrificio (`Tapu_Bulu` > `Applin`/`Chikorita`) depende a su vez de `_tapu_sac_priority`, que solo eleva a Tapu Bulu como sacrificio cuando de verdad aporta (matchups con protección-ex o motor `Hydrapple ex` + `Meganium`).
- **Con la promoción posterior (contexto `SWITCH`/`TO_ACTIVE`, `main-10`)**: RETREAT solo decide **si** conviene abrir la puerta de retirada; a quién se sube lo decide después `_best_promote_card` (mejor daño contra el activo rival, con bonus de HP para desempatar) o `_refresh_promote_prefer_basic` (preferir un básico de 1 premio cuando no hay ningún atacante listo y tenemos `Lillie's Determination` en mano). Los comentarios del bloque de RETREAT citan explícitamente ambas funciones para dejar claro que el "quién" no se decide aquí.
- **Con energía (`energy_score`, `main-10`)**: varios pivotes (`_hydra_fragile_pivot`, `_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`) requieren primero **rutear** la energía de este turno al activo (para que alcance su propio coste de retirada) antes de que RETREAT pueda disparar; esa parte vive en `energy_score`, no en este bloque.
- **Con `ATTACK` (líneas 12609 en adelante, `main-15`)**: cuando `plan.attacker` apunta a un Pokémon de banca, la opción de ATACAR con el activo actual queda suprimida por las propias reglas del bloque de ATTACK (que también lee `plan.attacker`), de modo que RETREAT y ATTACK actúan como un par coherente: uno abre la puerta al pivote, el otro garantiza que no se ataque con el cuerpo equivocado en el ínterin.

## Reglas derivadas de partidas

- **log 86510119** (paso 26, vs Dragapult, **PERDIDA**): origen de `_same_species_retreat` — no retirar si la promoción volvería a subir la misma especie (malgasta el coste de retirada). Cancela cualquier score positivo al final del bloque (línea 12606).
- **log 86338560** (paso 114, **GANADA** vs Mega Lucario): si el activo YA puede noquear, NO pivotar a otro Hydrapple ex de banca con menos energía solo para "lo mismo" — el activo debe atacar. Origen del guard `_active_can_ko_now` sin excepción en `_hydra_lethal_promote`.
- **log 86412738** (paso 145, vs Hops) y **log 86505760** (paso 55, **GANADA** vs Alakazam): generalización de la excepción — un ex frágil (<330 HP, ≠ Hydrapple ex) que ya remata debe ceder igualmente el turno a un Hydrapple ex de banca que también remata, para no exponer el ex frágil al contragolpe. Origen de `_active_ex_fragile_pivot`.
- **log 86583929** (turno 4, vs Alakazam, **PERDIDA**): origen de `_ogerpon_lethal_promote` — modela la rampa de *Teal Dance* al promover un Ogerpon de banca, algo que el scorer greedy (evaluando energía actual) no veía.
- **log 86406907** (paso 87, **GANADA** vs Crustle): origen de `_nonex_active_hits_wall` — un activo no-ex que SÍ golpea al muro inmune a ex nunca debe retirarse.
- **log 86607718** (turno 2, vs Crustle, **PERDIMOS**): origen de la regla anti-Crustle de `Chikorita` activo — retirar el Chikorita activo (score `6500`) aunque no haya todavía un atacante listo en banca, para evolucionarlo en banca y no dejarlo como lastre inútil contra el muro.
- **log 86211357** (paso 128, **PERDIDA** vs Mega Starmie): origen de `_prize_denial_pivot` — no atacar con un ex condenado cuyo KO le daría al rival los premios para ganar; retirarlo y subir un cuerpo de menos premios que gane tiempo.
- **log 85856881** (paso 127, **GANADA** vs Mega Lucario ex) y **log 86342087** (paso 130, **PERDIDA** vs Mega Lucario): origen de `_hydra_wall_pivot`/`_feza_lucario_wall` — pivote-muro sin KO garantizado, retirar el atacante condenado (Ogerpon o Fezandipiti) para subir un Hydrapple ex sano que sobrevive el golpe de Mega Lucario.
- **log 86027506** (paso 81, **GANADA** vs Abomasnow): origen de `_hydra_fragile_pivot` (calculado antes del bloque, en el preámbulo de amenaza) — retirar un Hydrapple ex activo dañado para proteger el KO letal con uno sano de banca; RETREAT lo materializa vía `_hydra_lethal_promote` una vez `can_switch` es `True`.
- **log 86174943** (turno 22, vs Crustle, **PERDIDA**): origen de `_keep_ogerpon_for_kang`, que **desactiva** `_ex_stuck_promo_ready` cuando el plan real del turno es Boss's Orders sobre un Mega Kangaskhan ex de banca rival (no inmune) y Ogerpon ex activo ya puede atacarlo directamente — evita un retiro innecesario a Dipplin.
- **log 85802744** (turno 16): origen de `_teal_dance_ko_pivot` — usar Teal Dance para habilitar la propia retirada de un Ogerpon bloqueado por el muro, en vez de malgastar la Planta cargando desarrolladores de banca.
- **log 86028607** (turno 22, **GANADA**): origen de `_ripen_retreat_ko_pivot` — usar la habilidad *Ripening Charge* de Hydrapple ex bloqueado para alcanzar su propio coste de retirada y ceder el turno a un no-ex listo en banca.
