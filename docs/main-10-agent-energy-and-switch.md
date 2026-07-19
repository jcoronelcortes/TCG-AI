# main.py — Puntuación de energía (energy_score) y contextos de cambio (líneas 4489–5996)

## Rol en el agente

Este bloque decide **a qué Pokémon adjuntar la energía del turno**. En el mazo Planta/ex del agente solo se puede jugar 1 energía básica por turno (salvo recuperación vía `Night Stretcher`), así que elegir el destino correcto es una de las decisiones más determinantes: define quién puede atacar, quién puede retirarse y, contra los mazos "muro" (Crustle, Cornerstone Ogerpon, Neutralization Zone), qué pieza del engine (Tapu Bulu, Dipplin, Meganium) se prepara primero. La función anidada `energy_score(pokemon, active)` (línea 4723) centraliza esa lógica y es **reutilizada por dos vías de adjunte distintas**: el adjunte manual (`OptionType.ATTACH`, resuelto más adelante en el bucle de opciones) y el objetivo de la habilidad *Ripening Charge* de Hydrapple ex (`SelectContext.ATTACH_FROM`), que adjunta una energía Planta a **cualquier** Pokémon propio. Como ambas vías llaman a la misma función, todas las reglas de tope de energía, prioridad de KO y reserva de energía se aplican de forma consistente sin importar el mecanismo de adjunte.

Justo antes de la función se calculan banderas de contexto muy específicas (pivotes de retirada contra muros inmunes a ex) que `energy_score` consulta. Justo después, el bloque cubre la preparación de otros contextos de selección: `ACTIVATE` (para decidir si activar o no la habilidad de Meowth ex), `SWITCH`/`TO_ACTIVE` (a qué Pokémon promover, con banderas de sacrificio ante Mega Lucario y de "muro" ante mazos con inmunidad a ex) y, al arrancar el bucle principal de puntuación (línea 5970), las primeras ramas de `NUMBER`/`YES`/`NO` que cubren `ACTIVATE`, `IS_FIRST` y `COIN_HEAD` (el volado de moneda inicial).

## Detalle por bloque

### Banderas previas: atacante futuro y pivotes anti-muro (líneas 4489–4722)

Antes de definir `energy_score`, el agente calcula varias condiciones fijas para ese turno:

- **`op_kang_ko_target` (4509–4531)**: si el activo rival es `Mega_Kangaskhan_ex`, calcula si `Hydrapple_ex` (en juego o alcanzable vía evolución/`Night_Stretcher`) podría noquearlo con toda la energía Planta disponible (`_syrup_max_kk = 30 + 30 * _kk_grass_max`). Sirve para levantar el tope normal de energía de Ogerpon más abajo.
- **`_tapu_bench_future` / `_tapu_future_charge` (4541–4553)**: si Meganium está en juego, el activo **ya asegura el KO este turno** (`_active_already_kos`), hay un `Tapu_Bulu` en banca con menos de 4 energías efectivas, y no estamos en un matchup especial (Crustle/Cornerstone/Neutralization Zone), se marca para cargar a Tapu Bulu como **atacante del próximo turno** (2 físicas = 4 efectivas con *Wild Growth*).
- **`_op_wall_active` / `_dmg_vs_wall(_p)` (4563–4583)**: si el activo rival es un muro inmune (a ex vía Crustle, o a habilidad vía Cornerstone), calcula el daño real de cada candidato contra ese muro (0 si el candidato es ex/depende de habilidad y está bloqueado).
- **`_ex_stuck_promo_ready` (4585–4617)**: nuestro activo es un ex bloqueado por el muro Y hay un atacante de banca ya listo que sí golpea al muro. Se exceptúa con `_keep_ogerpon_for_kang` (4604–4614): si el activo es Ogerpon ex con ≥3 energías efectivas, tenemos Boss's Orders en mano y el rival tiene un Mega Kangaskhan ex en banca (no inmune), se prefiere gustear al Kangaskhan y atacarlo con Ogerpon en vez de retirarlo.
- **`_nonex_active_hits_wall` (4628–4633)**: si el activo propio es no-ex, el rival es el muro inmune a ex y ese activo sí le hace daño, **nunca se retira** (evita malgastar el turno retirando un atacante válido).
- **`_teal_dance_ko_pivot` (4646–4655)**: activo = Ogerpon ex bloqueado por el muro, aún sin energía suficiente para retirarse, con una Planta en mano — se prioriza usar *Teal Dance* (adjunta a sí mismo + roba) en vez de gastar la energía en otro sitio, para habilitar la retirada.
- **`_ripen_retreat_ko_pivot` (4670–4679)** y **`_ripen_bench_tapu_ko_pivot` (4695–4721)**: variantes análogas para Hydrapple ex activo bloqueado por el muro: la primera dirige *Ripening Charge* al propio Hydrapple para poder retirarlo; la segunda cubre el caso en que Hydrapple ya puede retirarse pero el Tapu Bulu de banca aún necesita una 2ª Planta para llegar a las 4 efectivas de *Wood Hammer*.

Todas estas banderas son "recetas de log real" (comentarios citan partidas concretas, p.ej. `log 86174943`, `log 86028607`, `log 86182112`) que `energy_score` consulta para resolver secuencias de varios pasos (cargar → retirar → promover → rematar) con un scorer que solo mira un paso a la vez.

### `energy_score(pokemon, active)` — base y desempate (líneas 4723–4746)

```python
score = 8000 + (getattr(pokemon, 'hp', 0) or 0) / 100000.0
```

Puntaje base fijo (8000) más una fracción **diminuta** (máx. 0.0033) de la vida actual del Pokémon. Esta fracción nunca cruza los umbrales enteros del resto de ramas; solo rompe empates exactos entre candidatos idénticos (p.ej. dos Hydrapple ex en banca), favoreciendo siempre al de **más vida** (log 86212499).

Justo después, tope duro: **Chikorita nunca recibe una 2ª energía** (línea 4745, `return -1` si `_physical_energy(energy_count) >= 1`) — su único ataque cuesta 1 y cargarlo más desperdicia energía que hace falta en otros atacantes.

### Chikorita activo anti-Crustle (líneas 4748–4763)

```python
if (op_is_crustle_deck and active and pokemon.id == Chikorita
        and _physical_energy(energy_count) == 0
        and field_counts.get(Chikorita, 0) <= 1
        and bench_count >= 1
        and not state.energyAttached):
    return 41500
```
Si el turno empieza con Chikorita en el **activo**, sin copias en banca, y hay al menos un cuerpo en banca al que promover, se le da la **primera** energía (score 41500, por debajo del remate ganador de 42000) para poder **retirarlo** y evolucionarlo en banca a Meganium más tarde — Chikorita activo no ataca al muro Crustle y es un lastre de 1 premio (log 86607718).

### Remate ganador vía Boss's y muro Feza-Lucario (líneas 4765–4791)

- **4773–4774**: si hay una jugada **ganadora o de 2 premios** este turno vía Boss's Orders (`_win_via_boss_gust` o `_gust_2prize_via_boss`) que depende de que el **activo** sea el atacante, la carga al activo puntúa **42000** — la prioridad más alta de toda la función, por encima incluso de preparar a Tapu Bulu como atacante futuro (40000).
- **4786–4791 (`_feza_lucario_wall`)**: si el activo es Fezandipiti ex condenado a morir el próximo turno contra Mega Lucario ex y hay un Hydrapple ex sano en banca, se **veta** la carga al activo (`return -1`) y se prioriza Hydrapple hasta 2 energías efectivas (score 41000), para poder retirarlo y contraatacar con Syrup Storm (log 86342087).

### Topes de energía por matchup (líneas 4793–4881)

Varios topes "duros" que devuelven `-1` cuando se excede el máximo útil, para **reservar** energía en vez de desperdiciarla:

- **Tapu Bulu general (4803–4806)**: máx. 4 físicas sin Meganium / 2 con Meganium (2 físicas × *Wild Growth* = 4 efectivas, coste de *Wood Hammer*).
- **Ogerpon ex vs Crustle (4808–4833)**: en banca, tope duro de 2 físicas. En activo, tope de 3, con la única excepción de que la 3ª habilite un KO (`_extra_energy_enables_ko`) o de `op_kang_ko_target` (bypass ya visto).
- **Ogerpon ex vs Alakazam/Hop (4835–4858)**: base 2 físicas con Meganium / 4 sin Meganium; en banca es tope duro, en activo se permite una física extra solo si habilita el KO.
- **Cubchoo (4860–4881)**: topes físicos específicos por carta de toda la línea de ataque (Ogerpon, Applin, Dipplin, Hydrapple ex, y la línea Chikorita/Bayleef/Meganium con tope conjunto de 3) — el mazo rival bloqueará el ataque el próximo turno, así que se reserva energía en mano para pagar retiradas en vez de sobrecargar atacantes.

### Secuencias de retirada de Hydrapple ex (líneas 4883–4999)

Bloque dedicado a coordinar "cargar → retirar activo → promover Hydrapple ex de banca → Syrup Storm letal":

- **4891–4903**: calcula si el activo propio **ya puede retirarse** este turno (`_hls_act_retreatable`), en energía física (convertida desde efectiva si hay Meganium).
- **4914–4927**: si un Hydrapple ex de **banca** quedaría listo (≥2 efectivas) para un Syrup Storm **letal** sobre el activo rival, y el activo propio ya es retirable, esa carga puntúa **41000** — se prioriza por encima de cargar Tapu Bulu.
- **4936–4963**: si el letal está en un Hydrapple de banca pero el **activo propio aún no puede retirarse**, la carga se redirige al **activo** para completar su coste de retirada (solo si la retirada es completable este turno con la Planta en mano y los adjuntes disponibles) — score **41000**.
- **4965–4988 (`_hydra_fragile_pivot`)**: si el activo es un Hydrapple ex **frágil** (en riesgo) y hay otro sano y letal en banca, la carga va al activo frágil para poder retirarlo/protegerlo (score **41000**, log 86027506).
- **4990–4999 (`_ripen_retreat_ko_pivot`)**: variante específica para el objetivo de *Ripening Charge* contra el muro Crustle — dirige la Planta al propio Hydrapple activo bloqueado (score **41000**, log 86028607).

### Veto de carga a Tapu Bulu condenado vs Lucario (líneas 5001–5024)

Si el activo es Tapu Bulu y, tras adjuntarle 1 Planta, **seguiría** sin poder atacar (necesita 4 efectivas) ni retirarse (física < coste 3), y en banca hay un Ogerpon ex sin cargar al que *Teal Dance* podría alimentar, se **veta** el adjunte manual (`return -1`, log 85857426): la energía no sirve este turno y Tapu morirá regalando 2 premios; mejor usar Teal Dance (que además roba carta).

### Preparar atacante futuro: Tapu Bulu (líneas 5026–5032)

```python
if (_tapu_future_charge and not active and pokemon.id == Tapu_Bulu
        and len(pokemon.energies) * _grass_mult() < 4):
    return 40000
```
Segunda prioridad más alta de la función (tras el remate ganador de 42000): cuando el KO de este turno ya está asegurado y Meganium está en juego, cargar a Tapu Bulu de banca para dejarlo listo la próxima ronda.

### Meganium sobrecargado vs muros (línea 5034–5036) y confusión (5038–5049)

- Contra Crustle/Cornerstone, Meganium con ≥4 energías ya no necesita más (`-1`).
- Bloque de **confusión** (`is_confused`): si el activo está confundido, prioriza cargar un atacante de banca que aún no pueda atacar (40000) o, si el activo puede retirarse tras la carga pero el atacante de banca aún no está listo, cargar el propio activo para poder retirarlo (35000/33000) — evita seguir atacando confundido.

### Rama `op_is_cornerstone_deck` (líneas 5051–5095)

Sub-scorer dedicado cuando el rival juega Cornerstone (inmuniza a habilidad, no a ex): prioriza Tapu Bulu (`+22000` si <4 energías) y Pinsir (`+23000` si <2) como los atacantes que sí lo dañan; Ogerpon ex solo se carga si Tapu Bulu de banca ya está listo (≥4 energías, evita quedarse sin atacante); el resto de Pokémon reciben penalizaciones (`-500`/`-300`) salvo que también dependan de Tapu listo.

### Rama `op_is_crustle_deck` (líneas 5097–5263)

El sub-scorer más extenso, activo contra el mazo que inmuniza a nuestros ex:

- **5099–5119 (energía excedente)**: si el Tapu Bulu **activo** ya tiene ≥4 energías efectivas (no necesita más), la carga de este turno se **redirige** en cascada: (1) otro Tapu Bulu de banca sin completar (40000), (2) Dipplin sin energía (39000), (3) Meganium sin sus 4 efectivas (38000); si nada de eso aplica, se veta (`-1`) para **guardar** la energía.
- **5121–5156 (Tapu Bulu)**: mientras no llegue a 4 efectivas, `+20000`, con bonos si `_ctm_tapu_high` (Crustle activo y ya no conviene picar con Dipplin, definido en el bloque de banderas de main-09) o `_ctm_chikorita_bench` (+11000, hay línea Meganium en banca que se beneficiará de Wild Growth). Caso especial 5133–5139: si Meganium aún no está en juego pero se puede **evolucionar este turno** (Bayleef en juego + Meganium en mano) y las físicas actuales de Tapu ya alcanzarían 4 efectivas tras el doblado, se veta la carga (`-1`) para no desperdiciarla — mejor evolucionar primero.
- **5157–5171 (Ogerpon ex)**: solo se carga si está en el activo sin energía y hay un Tapu Bulu/Dipplin/Meganium de banca en condiciones (`_tapu_bench_og`); si no, penalización fuerte (`-500`).
- **5172–5182 (Applin)**: `+22000` si sin energía, con bono `+6500` si hay cuerpos Applin/Dipplin/Hydrapple en banca y no hay línea Chikorita.
- **5183–5196 (Dipplin)**: si `_ctm_charge_active_dipplin` (Dipplin es el activo y Crustle está débil/no es Crustle), score fijo **50000** — la prioridad más alta de toda esta rama; si `_ctm_tapu_high`, se veta (`-1`, Tapu ya es la prioridad); si no, `+23000` con energía <1.
- **5197–5204 (Pinsir)**: `+21000` si <2 energías.
- **5205–5240 (Meganium)**: si está en el activo sin energía y hay un atacante de banca ya listo para promover (`_meg_promo_ready`: Tapu Bulu ≥4 ef., Dipplin ≥1, o Pinsir ≥2 ef.), `+24000` — sacar a Meganium de en medio para no dejarlo de muro pasivo. Si ni Tapu Bulu ni Dipplin están en juego y Meganium <4 efectivas, `+19000` (es el único duplicador disponible). Si ya tiene ≥4, penalización.
- **5241–5262 (resto/default)**: nuestros ex bloqueados por el muro con `_ex_stuck_promo_ready` reciben `+24000` para cargar su coste de retirada; en otro caso, activo `+10` (con bono `+50` si hay Tapu Bulu en juego sin energía) o penalización `-300` en banca.

### Rama `neutralization_zone_active` (líneas 5265–5348)

Cuando el estadio rival anula habilidades, sub-scorer paralelo al de Crustle pero centrado en preparar atacantes que no dependen de habilidad: Tapu Bulu (`+23200` activo / `+600` banca si <4 efectivas), Dipplin (`+23200`/`+400` si <1), Pinsir (`+23000`/`+380` si <2 efectivas), Meganium (`+15000`/`+300` si <4 efectivas), Ogerpon ex (penaliza `-500` si ≥2 energías, prioriza cargarlo desde 0). Los ex propios (`OUR_EX_IDS`) se penalizan salvo que el activo rival también sea ex/mega-ex (`_op_nz_e_rb`), caso en que no se aplica penalización.

### Motor Hydrapple ex + Meganium: redirigir a banca (líneas 5350–5396)

Dos bloques hermanos, fuera de los matchups especiales:

- **5350–5371**: si Meganium está en juego, el **activo** es Hydrapple ex ya con ≥1 energía y hay banca cargable, se **veta** la carga al activo (`-1`) y se reparte entre banca: otro Hydrapple ex (20000), Ogerpon ex (19000 si <2 físicas, 5000 si no), Dipplin (18000), Meganium (17000), Tapu Bulu (16000) — desarrollar el resto del equipo mientras Hydrapple activo ya está operativo.
- **5373–5396 (`_active_hydra_capped`)**: variante cuando Hydrapple activo ya tiene ≥2 físicas (tope alcanzado) sin Meganium en juego: reparte la carga entre Ogerpon ex (hasta 3 físicas, con penalización decreciente `20000 - energy_count*100`), Meganium, Hydrapple de banca, Dipplin, Applin y Tapu Bulu (tope de 4 efectivas), en ese orden de prioridad decreciente.

### KO ya asegurado: repartir en banca (líneas 5398–5409)

```python
if _active_already_kos and not active and energy_count == 0 \
        and not op_is_crustle_deck and not op_is_cornerstone_deck \
        and not neutralization_zone_active:
    if pokemon.id in NON_ATTACKER_ENERGY_WASTE_IDS:
        return -1
    return {Hydrapple_ex: 30000, Teal_Mask_Ogerpon_ex: 29000,
            Dipplin: 28000, Meganium: 27000, Tapu_Bulu: 26000}.get(pokemon.id, 25000)
```
Si el activo ya asegura el KO de este turno, la energía se invierte en desarrollar el **siguiente** atacante de banca sin energía, con un orden de prioridad fijo por carta (Hydrapple ex primero). Se veta explícitamente cualquier cuerpo no atacante (`NON_ATTACKER_ENERGY_WASTE_IDS`, p.ej. Meowth ex/Fezandipiti cuando no son el plan de ataque) para no desperdiciar la energía en un cuerpo que no la aprovechará.

### Preparar la pre-evolución de Hydrapple (líneas 5411–5425)

Si el activo no necesita energía, no es Hydrapple ex, y hay un Dipplin/Applin en banca sin energía, se prioriza cargarlos (Dipplin 24000, Applin 23500) para adelantar la línea evolutiva Applin→Dipplin→Hydrapple ex, fuera de los matchups especiales.

### Rama por defecto — activo (líneas 5427–5588)

Rama genérica cuando ninguna de las anteriores aplicó. Primero, si `active_ko_likely` (el activo va a ser noqueado el turno rival), se calcula si el candidato **podría atacar tras la carga** (`_can_attack_after`, por umbrales propios de cada carta) o **retirarse** con un atacante de banca disponible (`_has_bench_atk_retreat`); si ninguna de las dos condiciones se cumple, se penaliza (`score - 100`) — no vale la pena cargar un Pokémon condenado que ni ataca ni puede escapar.

Después, puntuación por carta cuando está en el **activo** (`score += 10` base):
- **Hydrapple ex**: `+23200` si <2 efectivas (con bonos `+500` vs mazos de fuego, `+300` vs agresivos/Beedrill); si `_extra_energy_enables_ko`, `+15000`; si hay atacante de banca listo y el activo no noquea ya, también `+23200`; en otro caso, `-100`.
- **Dipplin**: `+23200` si sin energía (bono `+500` si el rival es inmune a ex, para no depender de Ogerpon/Hydrapple).
- **Ogerpon ex**: `+23200` si <3 efectivas; si `_extra_energy_enables_ko`, `+15000`; si hay atacante de banca listo sin necesitar más carga, `+23200`; si no, `-100`.
- **Tapu Bulu**: `+23200` con Meganium en juego (bono `+500` vs muro inmune a ex) o `+15000` sin Meganium, mientras <4 energías.
- **Meganium**: contra Drednaw o Sylveon activo, `+23200` si <4 efectivas; si no, `+23200` mientras <2 físicas.
- **Chikorita/Bayleef**: `+23200` mientras la energía efectiva no cubra su coste de retirada (se prioriza poder escapar).
- **Meowth ex**: solo se carga si hay un atacante real en banca al que promover tras retirarlo (`+23200`); si no, `-500`.
- **Fezandipiti ex**: `-100` si ya tiene ≥3 efectivas; `+23200` si la próxima carga llega a 3; si está en 0 y hay atacante de banca, `+23200`, si no `+5000`; en el resto, `-200`.
- **Pinsir**: `+23200` si <2 efectivas (bono `+500` vs muro inmune a ex).

### Rama por defecto — banca (líneas 5589–5707)

Puntuaciones análogas pero para candidatos en **banca**, con valores generalmente menores (no compiten con la prioridad del activo salvo cuando el activo ya está resuelto):
- **Ogerpon ex**: `+400`/`+250`/`+150` según tramo de energía, `-100` si ya al tope sin habilitar KO.
- **Tapu Bulu**: `-100` sin Meganium (no puede llegar a 4 efectivas); `+350` si el rival es inmune a ex y <2 físicas; si no, `+100`/`-80`.
- **Hydrapple ex**: `+23100` si <2 efectivas (bonos vs fuego/agresivo), tramos menores después.
- **Dipplin**: `+150` sin energía (bonos vs muro inmune a ex, Drednaw, Sylveon).
- **Applin**: `+40` sin energía; con 1 energía, `+50` solo si se puede evolucionar del todo este turno y no hay Meganium; si no, `-300`; con más, `-400`.
- **Meganium**: contra Drednaw o "amenaza Sylveon" (`_sylveon_threat`), `+500` si <4 efectivas; si no, penalizaciones o `+60` si Hydrapple ex es el activo sin energía propia.
- **Meowth ex**: `-100` (penaliza siempre en banca; `-50` extra si el rival tiene Froslass).
- **Fezandipiti ex**: `+300` si es el atacante planificado (`plan.attacker`) y le falta energía; `+200` si no hay otro atacante en juego; si no, `-100` (con penalización extra vs Froslass).
- **Pinsir**: `+350` si el rival es inmune a ex y <2 efectivas; si no, `+80`/`-60`.

## Contextos posteriores: ACTIVATE, promoción y volado (líneas 5710–5996)

### `_sel_active_cant_attack` (líneas 5710–5726)

Determina, usando `ATTACK_ENERGY_REQ` como fuente única, si el activo propio **no puede atacar** este turno (ni ahora ni tras adjuntar la única Planta disponible en mano). Es una bandera de contexto genérica reutilizada más adelante en el bucle principal.

### `ACTIVATE`: saltar la habilidad de Meowth ex (líneas 5728–5735)

```python
_meowth_skip_fetch = (
    context == SelectContext.ACTIVATE
    and _sel_ctx_card is not None and _sel_ctx_card.id == Meowth_ex
    and _meowth_devel_lillie
    and hand_counts.get(Lillie_Determination, 0) >= 1
    and not _win_via_boss_gust and not _gust_2prize_via_boss)
```
Cuando la carta que activa su habilidad es Meowth ex, `_meowth_devel_lillie` está activo (bandera definida en el bloque anterior de Supporters, main-09) y ya tenemos una `Lillie's Determination` en mano, se prefiere **no** buscar otro Supporter con la habilidad (para no gastar el efecto en balde), salvo que haya una jugada ganadora vía Boss's. Esta bandera se consume después, en las ramas `YES`/`NO` del bucle (líneas 5979–5997): normalmente `YES` en `ACTIVATE` puntúa 10, pero si `_meowth_skip_fetch` es cierto se invierte (`YES` → -1, `NO` → 10).

### `_boss_low_value_gust` (líneas 5737–5749)

Si el mejor gusteo posible de Boss's Orders es de bajo valor (`_boss_prize_rank >= 7`, ni gana la partida ni toma 2 premios ni protege/redirige) y vamos ganando en premios (`my_prize > op_prize`) con Lillie's disponible, se marca para preferir desarrollar mano en vez de quemar el Boss's.

### Sacrificio anti-Mega Lucario (líneas 5751–5797)

Bloque de banderas para el turno 2 yendo segundos, cuando el rival tiene un Riolu activo con energía (evolucionará a Mega Lucario ex el próximo turno y noqueará a un Ogerpon ex por 2 premios):
- **`_lucario_sac_context` / `_lucario_sac_pivot`**: detecta la amenaza y que el activo propio sea justo Ogerpon ex.
- **`_lucario_sac_available`**: hay un cuerpo barato disponible para sacrificar (Tapu Bulu, Applin o Chikorita en juego, o Tapu Bulu en mano con banca libre).
- **`_lucario_hydra_engine` / `_tapu_sac_priority`**: Tapu Bulu solo se sacrifica **primero** si de verdad aporta valor inmediato — el rival tiene protección a ex (Crustle/Cornerstone/Sylveon/inmunidades) o el motor Hydrapple ex + Meganium ya permite bajarlo cargado; si no, se prefiere sacrificar Applin > Chikorita y conservar Tapu Bulu.

Estas banderas se consumen más adelante en el bucle, en la rama `CARD` de contexto `SWITCH`/`TO_ACTIVE` (línea 6006 en adelante, ya en el territorio de `main-11`): con `_tapu_sac_priority` activo, el orden de promoción es Tapu Bulu (6000) > Applin (5500) > Chikorita (5000); si no, Applin (6000) > Chikorita (5500) > Tapu Bulu (200).

### `_lillie_protected_once` (líneas 5799–5802)

Bandera simple, inicializada en `False`, que se usa más adelante (en la puntuación de descarte) para proteger la primera copia de `Lillie's Determination` vista al valorar descartes — solo las copias sobrantes son libremente descartables.

### Promoción tras KO: `_best_promote_card` / `_forced_ko_promote` (líneas 5804–5902)

Cuando el activo propio fue noqueado (`context in (SWITCH, TO_ACTIVE)` y no hay Pokémon activo) y no estamos en el escenario de sacrificio anti-Lucario, se calcula de forma centralizada **qué Pokémon de banca promover**, iterando todos los candidatos de banca:
- Requiere que el candidato pueda atacar este turno (energía efectiva actual, o tras adjuntar si hay Planta en mano y no se ha adjuntado ya) según `ATTACK_ENERGY_REQ`.
- Estima su daño (`_pb_dmg`) con fórmulas propias por carta (Hydrapple ex: `30+30*total_grass`; Ogerpon ex: `30+30*(energía+energía rival)`; Dipplin: `20*banca_restante`; Tapu Bulu: 220 fijo; Meganium: 140 fijo; Fezandipiti ex: 100 fijo; resto: 10).
- Aplica inmunidad a ex (Crustle/Sylveon → 0), inmunidad de habilidad (Cornerstone → 0) y debilidad de tipo (×2).
- Elige el candidato por clave lexicográfica `(puede_noquear, vida_restante, daño)` — **siempre el de más vida entre los que noquean**, no necesariamente el de más daño.

**`_lucario_ko_prefer_basic` (5898–5901)**: si no hay ningún candidato capaz de atacar (`_best_promote_card is None`) y el rival es Mega Lucario, se prefiere promover un básico (Applin primero, o Dipplin) para entregar solo 1 premio en vez de un ex.

### `_refresh_promote_prefer_basic` (líneas 5904–5939)

Regla complementaria (log 86345562): al promover (por retiro o KO) cuando **ningún** cuerpo de banca puede atacar este turno (ni ahora ni tras adjuntar) y hay `Lillie's Determination` en mano, se prefiere subir un básico de 1 premio (Applin primero) en vez de un ex de 2 premios, para hacer de muro barato mientras se rehace la mano — pero **solo** si el rival no es inmune a ex/habilidad (esos matchups ya tienen su propia lógica de promoción de muro).

### Matchup Crustle + Mega Kangaskhan: reparto de atacantes (líneas 5941–5969)

```python
_cm_matchup = op_is_crustle_deck and op_has_mega_kangaskhan
...
_cm_use_ex = _cm_vs_ex_target and _cm_have_ex_attacker
```
Contra un mazo que combina Crustle (inmune a ex) con Mega Kangaskhan ex (no inmune) en banca, se calcula si tenemos un ex propio (Ogerpon ex o Hydrapple ex) capaz de atacar **este turno** al activo rival cuando ese activo NO es el muro. `_cm_use_ex` señala que corresponde usar el ex contra el objetivo no inmune y **reservar** los no-ex (sobre todo Tapu Bulu, que noquea a Crustle de un golpe) para cuando Crustle esté activo. Esta bandera se consume en la puntuación de `ATTACK` más adelante (fuera de este rango).

### Arranque del bucle de puntuación: NUMBER, ACTIVATE, IS_FIRST, COIN_HEAD (líneas 5970–5996)

```python
scores = []
for o in select.option:
    score = 0
    if o.type == OptionType.NUMBER:
        score = o.number
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
Aquí arranca el gran bucle `for o in select.option` que recorre todas las opciones ofrecidas (documentado en detalle a partir de `main-11`). Las primeras ramas cubiertas por este bloque:
- **`NUMBER`**: se copia directamente el valor numérico de la opción (`o.number`) como score — usado en preguntas de cantidad.
- **`YES` en `ACTIVATE`**: score base 10 (activar la habilidad ofrecida), invertido a -1 si `_meowth_skip_fetch` aplica.
- **`YES`/`NO` en `IS_FIRST`**: decide quién empieza la partida. El agente **siempre** elige `NO` (`we_go_first = False`, score 2) sobre `YES` (`we_go_first = True`, score -1) — prioriza ir **segundos**. Además de puntuar, esta rama es la que **actualiza la variable global `we_go_first`** que el resto del agente usa para razonar sobre el turno.
- **`YES` en `COIN_HEAD`**: score 2 fijo — el volado de moneda para decidir quién empieza no tiene lógica adicional, solo elige "cara" de forma constante.
- **`NO` en `ACTIVATE` con `_meowth_skip_fetch`**: cuando se decidió no activar la habilidad de Meowth ex por ya tener Lillie's en mano, `NO` puntúa 10 (invirtiendo la preferencia normal por `YES`).

## Interacciones

- **Reutilización dual de `energy_score`**: la función se llama tanto desde la rama `OptionType.ATTACH` del bucle principal (adjunte manual, fuera de este rango de líneas) como desde `SelectContext.ATTACH_FROM` (objetivo de *Ripening Charge*). Todas las reglas de tope, prioridad de KO y pivotes de retirada aplican igual sin importar el mecanismo — es la razón por la que casi todos los comentarios del bloque dicen explícitamente "cubre el adjunte MANUAL y el objetivo de Ripening Charge".
- **Consumo de banderas de matchup**: `energy_score` depende fuertemente de flags calculadas en bloques anteriores (`main-06` matchup, `main-07` amenaza/plan, `main-08` Boss's, `main-09` Supporters): `op_is_crustle_deck`, `op_is_cornerstone_deck`, `neutralization_zone_active`, `_active_already_kos`, `_extra_energy_enables_ko`, `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_ctm_tapu_high`/`_ctm_chikorita_bench`/`_ctm_applin_bench`/`_ctm_charge_active_dipplin` (definidas en 4102–4152).
- **Energía efectiva vs física**: casi todas las ramas distinguen entre `len(pokemon.energies)` (efectiva, ya duplicada por *Wild Growth* si Meganium está en juego) y `_physical_energy(energy_count)` (cartas reales) — los topes de energía se razonan siempre en físicas (lo que realmente se puede adjuntar/retirar), mientras que los umbrales de ataque se razonan en efectivas.
- **Encadenamiento de pivotes**: los pivotes anti-muro (`_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`, `_ripen_bench_tapu_ko_pivot`) dependen unos de otros y de que el scorer sea "codicioso" (greedy) — se re-evalúan en cada paso del turno, de modo que tras un adjunte manual que deja a Tapu Bulu listo, la siguiente llamada a `energy_score` (para el objetivo de Ripening Charge) ve un estado distinto y activa el pivote siguiente de la cadena.
- **Con la sección siguiente (`main-11`)**: las banderas `_best_promote_card`, `_lucario_ko_prefer_basic`, `_refresh_promote_prefer_basic`, `_tapu_sac_priority` y `_cm_use_ex`, aunque se calculan en este rango, se **consumen** en las ramas `CARD` de `SWITCH`/`TO_ACTIVE` que empiezan justo después (línea 5999 en adelante), ya cubiertas por el documento de búsqueda de cartas y promoción.

## Reglas derivadas de partidas

Casi todo este bloque está anotado con IDs de log reales que motivaron cada regla; los más relevantes:
- **log 86212499** (vs Alakazam, GANADA): desempate por vida entre candidatos iguales (línea 4726).
- **log 86028607** (vs Crustle, turnos 21–22, GANADA): Chikorita activo cargado para retirar (4748); pivote Ripening→retirar→Tapu (4657, 4990); pivote Ripening→cargar Tapu→retirar Hydrapple (4681).
- **log 85855786** (vs Alakazam, paso 141, GANADA): remate ganador vía Boss's tiene prioridad 42000 (4765).
- **log 86342087** (vs Mega Lucario, PERDIDA): no cargar un Fezandipiti condenado; priorizar Hydrapple de banca (4776).
- **log 86583376** (vs Crustle, paso 84): tope de 2 físicas en banca para Ogerpon ex (4808).
- **log 86174943** (vs Crustle, turno 22, PERDIDA): conservar Ogerpon ex activo para atacar a Mega Kangaskhan vía Boss's en vez de retirarlo (4595, `_keep_ogerpon_for_kang`).
- **log 86406907** (vs Crustle, paso 87, GANADA): un no-ex que golpea al muro nunca se retira (4619, `_nonex_active_hits_wall`).
- **log 85802744** (turno 16 y paso 55): pivote Teal Dance→retirar→promover (4635); no sobrecargar Tapu si Meganium es evolucionable este turno (5123).
- **log 86182112** (vs Crustle, paso 82, GANADA): pivote Ripening→Tapu de banca→retirar Hydrapple (4681).
- **log 85857426** (vs Mega Lucario, paso 37, PERDIDA): vetar carga a Tapu Bulu condenado, preferir Teal Dance (5001).
- **log 86027506** (vs Abomasnow, paso 81, GANADA): pivote de Hydrapple frágil (4965).
- **log 86345562** (paso 55): preferir promover básico con Lillie's en mano si nadie puede atacar (5904).
- **log 86607718** (vs Crustle, turno 2, PERDIDA): motivó la regla de Chikorita activo anti-Crustle (4748).
