# main.py — Puntuación de energía (`energy_score`) y contextos de cambio

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este bloque decide **a qué Pokémon adjuntar la energía del turno**. En el mazo Planta/ex del agente solo se puede jugar 1 energía básica por turno (salvo recuperación vía `Night_Stretcher`), así que elegir el destino correcto es una de las decisiones más determinantes: define quién puede atacar, quién puede retirarse y, contra los mazos "muro" (Crustle, Cornerstone Ogerpon, Neutralization Zone), qué pieza del engine (Tapu Bulu, Dipplin, Meganium) se prepara primero. La función anidada `energy_score(pokemon, active)` centraliza esa lógica y es **reutilizada por dos vías de adjunte distintas**: el adjunte manual (`OptionType.ATTACH`, resuelto más adelante en el bucle de opciones) y el objetivo de la habilidad *Ripening Charge* de Hydrapple ex (`SelectContext.ATTACH_FROM`), que adjunta una energía Planta a **cualquier** Pokémon propio. Como ambas vías llaman a la misma función, todas las reglas de tope de energía, prioridad de KO y reserva de energía se aplican de forma consistente sin importar el mecanismo de adjunte.

Justo antes de la función se calculan banderas de contexto muy específicas (pivotes de retirada contra muros inmunes a ex, sacrificio de ex frágil, letal de doble carga de Ogerpon) que `energy_score` consulta. Justo después, el bloque cubre la preparación de otros contextos de selección: `ACTIVATE` (si activar o no la habilidad de Meowth ex), la promoción centralizada (`_best_promote_card`, con la **nueva clave de prudencia de premios**), el pivote de 1 premio vs Alakazam (`_alakazam_pivot_1prize`), la construcción del `DecisionContext` (`ctx`) que consumen los scorers extraídos `_score_*_play`, el registro de los slots con *Teal Dance* pendiente (`_teal_dance_slots`) y, al arrancar el bucle principal de puntuación, las primeras ramas de `NUMBER`/`YES`/`NO` que cubren `ACTIVATE`, `IS_FIRST` y `COIN_HEAD`.

## Detalle por bloque

### Banderas previas: KO asegurado, letales de Myriad y pivotes anti-muro

Antes de definir `energy_score`, el agente calcula varias condiciones fijas para ese turno:

- **`_active_already_kos`**: ¿el activo propio ya asegura el KO al activo rival con su energía actual? Reproduce las fórmulas de daño por identidad. Para Ogerpon ex usa la fórmula **corregida** de *Myriad Leaf Shower*: `_ak_dmg = 30 + 30 × (energía_propia + energía_del_activo_rival)` — antes la energía rival (`_ak_op_e`) se computaba sin usarse, el mismo error que tenían las demás copias inline de la fórmula (regla verificada con daño real de 6 registros; ver `_attacker_base_damage`). Para Fezandipiti ex cuenta *Cruel Arrow* (100 fijo, tipo Oscuridad: **no** aplica debilidad/resistencia a Planta).
- **`_extra_energy_enables_ko(pokemon_id, current_energy)`**: ¿la energía extra de este turno convierte un no-KO en KO? También usa la Myriad corregida para Ogerpon (suma la energía del activo rival).
- **`_ogerpon_td_manual_lethal`**: letal de **doble carga** en un turno — Ogerpon ex activo con ≥2 Plantas en mano y Teal Dance disponible puede recibir adjunte manual **más** Teal Dance y alcanzar 3+ energías con daño letal (`_otml_dmg = 30 + 30 × (energía_tras_2_cargas + energía_rival)`, ×2 por debilidad). El scorer codicioso solo mira +1 energía por opción, así que ni `_active_already_kos` ni `_extra_energy_enables_ko` detectaban este letal de +2; la bandera evita despriorizar la carga al activo.
- **`op_kang_ko_target`**: si el activo rival es Mega Kangaskhan ex, calcula si Hydrapple ex (en juego o alcanzable vía evolución/Night Stretcher) podría noquearlo con toda la Planta disponible (`_syrup_max_kk = 30 + 30 × grass_máximo`). Levanta topes de energía de Ogerpon más abajo.
- **`_tapu_bench_future` / `_tapu_future_charge`**: si Meganium está en juego, el activo **ya asegura el KO** (`_active_already_kos`), hay un Tapu Bulu en banca con <4 energías efectivas y no estamos en matchup especial (Crustle/Cornerstone/Neutralization Zone), se marca para cargar a Tapu Bulu como **atacante del próximo turno** (2 físicas = 4 efectivas con *Wild Growth*).
- **`_meganium_alk_future_charge`**: análogo para el matchup Alakazam — con el KO asegurado y un Meganium de banca **parcialmente** cargado (0 < efectivas < 4), cargarlo como atacante futuro de 1 premio (140 derrota a la línea Alakazam). Su score (25000) queda por debajo de las cargas de los atacantes principales.
- **`_meganium_alk_1prize_attacker`** (43000): hermano de ESTE turno del anterior — el Meganium de banca queda a UNA Planta de su coste y su daño noquea al activo rival, así que la carga va al Meganium (se retira el ex y se promueve el 1-premio) en vez de al ex activo. **Exige `can_switch`** (registro_014 paso 136 vs Alakazam): toda la regla se apoya en "se retira el ex y se promueve Meganium", y con un Fezandipiti ex activo a 0 energías (coste de retirada 1) la retirada no era legal — el Meganium cargado se quedaba en la banca sin atacar mientras este 43000 pisaba al adjunte que SÍ habilitaba la jugada (`_attach_enable_retreat_ko`, 41000: la Planta al ACTIVO para pagar la retirada y subir al Hydrapple ex ya listo). Sin retirada legal la carga decae al tier FUTURO (25000).
- **`_op_wall_active` / `_dmg_vs_wall(_p)`**: si el activo rival es un muro inmune (a ex vía Crustle, o a habilidad vía Cornerstone), calcula el daño real de cada candidato contra ese muro vía la tabla única `_attacker_base_damage` (0 si el candidato está bloqueado por la inmunidad).
- **`_ex_stuck_promo_ready`**: nuestro activo es un ex bloqueado por el muro (`_active_blocked_by_wall`) Y hay un atacante de banca ya listo que sí golpea al muro (`_wall_bench_attacker_ready`). Se exceptúa con `_keep_ogerpon_for_kang`: si el activo es Ogerpon ex con ≥3 energías efectivas, hay Boss's Orders en mano sin Supporter jugado y el rival tiene un Mega Kangaskhan ex en banca (no inmune), se prefiere gustear al Kangaskhan y atacarlo con Ogerpon en vez de retirarlo.
- **`_nonex_active_hits_wall`**: si el activo propio es no-ex, el rival tiene el muro inmune a ex activo y ese activo sí le hace daño, **nunca se retira** (evita malgastar el turno retirando el único atacante válido).
- **`_teal_dance_ko_pivot`**: activo = Ogerpon ex bloqueado por el muro, aún sin energía suficiente para retirarse pero sí tras una Planta más, con una Planta en mano — se prioriza *Teal Dance* (adjunta a sí mismo + roba) para habilitar la retirada.
- **`_fragile_ex_sac_pivot` / `_fragile_ex_sac_attacker`**: pivote de **sacrificio a 1 premio** — el activo es un ex propio (2 premios) que será noqueado el próximo turno (`active_ko_likely` o `estimated_op_damage >= hp`), y en banca hay un atacante **no-ex** (1 premio) LISTO cuyo daño efectivo noquea al activo rival. La línea correcta es retirar el ex y promover el no-ex: mismo KO, pero si el rival responde solo cede 1 premio. No aplica si atacar con el ex ya gana la partida. Para Hydrapple ex activo, la retirada se habilita con Ripening Charge (ver `_ripen_retreat_ko_pivot`, que ahora acepta `_ex_stuck_promo_ready` **o** `_fragile_ex_sac_pivot` como disparador).
- **`_ripen_retreat_ko_pivot`** y **`_ripen_bench_tapu_ko_pivot`**: variantes para Hydrapple ex activo bloqueado por el muro: la primera dirige *Ripening Charge* al propio Hydrapple para poder retirarlo (en energía **efectiva**: con Meganium 1 Planta = 2); la segunda cubre el caso en que Hydrapple ya puede retirarse pero el Tapu Bulu de banca aún necesita una 2ª Planta para llegar a las 4 efectivas de *Wood Hammer* y noquear al muro.

Casi todas estas banderas son "recetas de log real" (los comentarios citan la partida concreta que las motivó) que `energy_score` consulta para resolver secuencias de varios pasos (cargar → retirar → promover → rematar) con un scorer que solo mira un paso a la vez.

### `energy_score(pokemon, active)` — base y desempate

```python
score = 8000 + (getattr(pokemon, 'hp', 0) or 0) / 100000.0
```

Puntaje base fijo (8000) más una fracción **diminuta** (máx. 0.0033) de la vida actual. Esa fracción nunca cruza los umbrales enteros del resto de ramas; solo rompe empates exactos entre candidatos idénticos (p.ej. dos Hydrapple ex en banca), favoreciendo siempre al de **más vida**.

Justo después, tope duro: **Chikorita nunca recibe una 2ª energía** (`SCORE_VETO` si `_physical_energy(energy_count) >= 1`) — su único ataque cuesta 1 y el excedente se desperdicia.

### Chikorita activo anti-Crustle (41500)

Si vs Crustle el turno empieza con Chikorita en el **activo** a 0 físicas, sin otra copia en juego, con al menos un cuerpo en banca y sin energía adjuntada aún, la carga al Chikorita activo devuelve **41500** (por debajo del remate ganador de 42000): la prioridad es retirarlo (coste 1) y evolucionarlo en banca — Chikorita activo no ataca al muro y es un lastre de 1 premio.

### Remate ganador vía Boss's (42000) y muro Feza-Lucario (41000)

- Si hay una jugada **ganadora o de 2 premios** este turno vía Boss's Orders (`_win_via_boss_gust` o `_gust_2prize_via_boss`) que depende de que el **activo** sea el atacante, la carga al activo devuelve **42000** — la prioridad más alta de toda la función, por encima incluso de `_tapu_future_charge` (40000).
- **`_feza_lucario_wall`**: si el activo es un Fezandipiti ex condenado a morir contra Mega Lucario ex y hay un Hydrapple ex sano en banca, se **veta** la carga al activo (`SCORE_VETO`) y se prioriza el Hydrapple de banca hasta 2 efectivas (**41000**), para retirar al Feza (coste 1) y contraatacar con Syrup Storm.

### Topes de energía por matchup

Varios topes "duros" que devuelven `SCORE_VETO` cuando se excede el máximo útil, para **reservar** energía. Todos convierten la energía efectiva de la observación (ya duplicada por *Wild Growth*) a cartas físicas con `_physical_energy`:

- **Tapu Bulu general**: máx. 4 físicas sin Meganium / 2 con Meganium.
- **Ogerpon ex vs Crustle** (`not op_kang_ko_target`): en banca, tope duro de 2 físicas; en activo, tope de 3, y la 3ª solo si habilita un KO (`_extra_energy_enables_ko`).
- **Ogerpon ex vs Alakazam/Hop** (`op_is_alakazam_deck or op_is_hop_deck`): base 2 físicas con Meganium / 4 sin; en banca tope duro, en activo se permite una física extra solo si habilita el KO.
- **Cubchoo**: topes físicos por carta de toda la línea de ataque (Ogerpon 2/4, Applin 1, Dipplin 1/2, Hydrapple 2/3, y la línea Chikorita/Bayleef/Meganium con tope conjunto de 3) — el rival bloqueará el ataque el próximo turno, así que se reserva energía en mano para pagar retiradas.

### Secuencias de retirada de Hydrapple ex (41000)

Bloque dedicado a coordinar "cargar → retirar activo → promover Hydrapple ex de banca → Syrup Storm letal":

- **`_hls_act_retreatable`**: ¿el activo propio ya puede retirarse este turno? (en energía física, convertida desde efectiva si hay Meganium).
- Si un Hydrapple ex de **banca** quedaría listo (≥2 efectivas) para un Syrup Storm **letal** y el activo propio ya es retirable → esa carga puntúa **41000**.
- Si el letal está en banca pero el **activo propio aún no puede retirarse**, la carga se redirige al **activo** para completar su coste de retirada — solo si la retirada es **completable** este turno con las Plantas de la mano y los adjuntes disponibles (1 manual + una Ripening Charge por cada Hydrapple de banca) — también **41000**.
- Esa misma regla es la que **sostiene la rama nueva de Ripening Charge** (doc 13): cuando la habilidad se activa para desbloquear la retirada, el objetivo lo elige `energy_score` y debe salir el **activo** — si la Planta cayera en desarrollo de banca la retirada seguiría bloqueada y la habilidad sería una carta tirada. Pinado por `test_alakazam_step137_ripening_charge_apunta_al_activo` (registro_014). Nótese que el bloque es **específico de Hydrapple ex letal en banca**; en el resto de casos el destino correcto sale del bono genérico de "el activo necesita la energía para retirarse".
- **`_hydra_fragile_pivot`**: activo Hydrapple ex **frágil** con otro sano y letal en banca — la carga va al activo frágil para poder retirarlo/protegerlo (41000), con el mismo chequeo de completabilidad.
- **`_ripen_retreat_ko_pivot`** en el activo: la Planta de Ripening Charge va al propio Hydrapple activo bloqueado (41000).

### Veto de carga a Tapu Bulu condenado vs Lucario

Si el activo es Tapu Bulu vs Mega Lucario y, tras adjuntarle 1 Planta, **seguiría** sin poder atacar (necesita 4 efectivas) ni retirarse (físicas < coste 3), y en banca hay un Ogerpon ex sin cargar (<3) al que Teal Dance podría alimentar, se veta el adjunte (`SCORE_VETO`): la energía no sirve este turno y Tapu morirá; mejor Teal Dance, que no pierde la energía y roba carta.

### Atacantes futuros: Tapu Bulu (40000) y Meganium vs Alakazam (25000)

- `_tapu_future_charge` + candidato Tapu Bulu de banca con <4 efectivas → **40000** (segunda prioridad tras el remate de 42000).
- `_meganium_alk_future_charge` + candidato Meganium de banca con <4 efectivas → **25000**: solo gana cuando los atacantes principales ya no necesitan la energía (sus cargas de banca a 0 valen 26000–30000).

### Meganium sobrecargado y confusión

- Contra Crustle/Cornerstone, Meganium con ≥4 energías no necesita más (`SCORE_VETO`).
- Bloque de **confusión** (`is_confused`): prioriza cargar un atacante de matchup de banca que aún no pueda atacar (40000); si el activo confundido podría retirarse tras la carga con atacante de banca listo, cargar el activo para retirarlo (35000); si no hay cuerpo de banca y el activo es el atacante del matchup, cargarlo (33000).

### Rama `op_is_cornerstone_deck`

Sub-scorer dedicado cuando el rival juega Cornerstone (inmuniza a habilidad): prioriza Tapu Bulu (`+22000` si <4 energías) y Pinsir (`+23000` si <2); Ogerpon ex solo recibe carga en el activo a 0 energías si un Tapu Bulu de banca ya está listo; el resto se penaliza (−300/−500) salvo el mismo requisito de Tapu listo.

### Rama `op_is_crustle_deck`

El sub-scorer más extenso, contra el mazo que inmuniza a nuestros ex:

- **Energía excedente** (`_ctm_active_tapu_full`): si el Tapu Bulu **activo** ya tiene ≥4 efectivas, la carga se redirige en cascada: otro Tapu Bulu de banca sin completar (40000) > Dipplin sin energía (39000) > Meganium sin sus 4 efectivas (38000); si nada aplica, se **guarda** la energía (`SCORE_VETO`).
- **Tapu Bulu**: mientras no llegue a 4 efectivas, `+20000`, con bonos por `_ctm_tapu_high` (+5000) y `_ctm_chikorita_bench` (+11000). Caso especial `_meg_evolvable_now_tapu`: si Meganium es evolucionable **este turno** (Bayleef en juego + Meganium en mano) y las físicas actuales de Tapu ya alcanzarían 4 efectivas tras el doblado, se veta la carga — mejor evolucionar primero.
- **Ogerpon ex**: solo en el activo a 0 energías con un Tapu Bulu/Dipplin/Meganium de banca en condiciones (`_tapu_bench_og`); si no, `−500`.
- **Applin**: `+22000` si sin energía, con bono `+6500` si `_ctm_applin_bench` sin línea Chikorita.
- **Dipplin**: si `_ctm_charge_active_dipplin`, score fijo **50000** (máxima prioridad de la rama); si `_ctm_tapu_high`, veto; si no, `+23000` a 0 energías.
- **Pinsir**: `+21000` si <2 energías.
- **Meganium**: activo a 0 energías con atacante de banca listo (`_meg_promo_ready`) → `+24000` (cargarle 1 para poder retirarlo, no dejarlo de muro); único duplicador disponible (sin Tapu ni Dipplin en juego) y <4 efectivas → `+19000`; si ya tiene ≥4, penalización.
- **Resto/default**: nuestros ex bloqueados con `_ex_stuck_promo_ready` reciben `+24000` para cargar su coste de retirada; en otro caso, activo `+10` (bono `+50` con Tapu Bulu a 0 en juego) o `−300` en banca.

### Rama `neutralization_zone_active`

Sub-scorer paralelo al de Crustle centrado en atacantes que no dependen de habilidad ni son ex: Tapu Bulu (`+23200` activo / `+600` banca si <4 efectivas), Dipplin (`+23200`/`+400` si <1), Pinsir (`+23000`/`+380` si <2), Meganium (`+15000`/`+300` si <4), Ogerpon ex (penaliza con ≥2 energías, prioriza cargarlo desde 0). Los ex propios (`OUR_EX_IDS`) se penalizan salvo que el activo rival también sea ex/mega-ex (`_op_nz_e_rb`) — bajo la zona nuestros ex sí dañan a un rival con Rule Box.

### Motor Hydrapple ex + Meganium: redirigir a banca

Dos bloques hermanos, fuera de los matchups especiales:

- Si Meganium está en juego, el **activo** es Hydrapple ex ya con ≥1 energía y hay banca cargable (`_bench_has_chargeable`), se **veta** la carga al activo y se reparte entre banca: otro Hydrapple ex (20000), Ogerpon ex (19000 si <2 / 5000 si no), Dipplin (18000), Meganium (17000), Tapu Bulu (16000).
- **`_active_hydra_capped`**: variante cuando Hydrapple activo ya tiene ≥2 físicas sin Meganium: reparte entre Ogerpon ex (hasta 3 físicas, `20000 − energía×100`), Meganium (18000), Hydrapple de banca (16000), Dipplin (14000), Applin (12000) y Tapu Bulu (10000, tope 4 efectivas).

### KO ya asegurado: repartir en banca

Si `_active_already_kos` y el candidato está en banca a 0 energías (fuera de matchups especiales), la energía se invierte en el **siguiente** atacante: Hydrapple ex 30000 > Ogerpon ex 29000 > Dipplin 28000 > Meganium 27000 > Tapu Bulu 26000 > resto 25000. Cualquier cuerpo de `NON_ATTACKER_ENERGY_WASTE_IDS` (Meowth ex, Fezandipiti ex) se veta.

### Preparar la pre-evolución de Hydrapple

Si el activo no necesita energía, no es Hydrapple ex, y hay un Dipplin/Applin en banca sin energía (`_bench_hydra_pre_target`), se prioriza cargarlos (Dipplin 24000, Applin 23500) para adelantar la línea Applin→Dipplin→Hydrapple ex, y se veta la carga al activo.

### Rama por defecto — activo

Cuando ninguna de las anteriores aplicó y el candidato es el **activo** (`score += 10` base). Primero, si `active_ko_likely`, se calcula si el candidato podría **atacar tras la carga** (`_can_attack_after`, umbrales por carta; para Ogerpon incluye `_ogerpon_td_manual_lethal`) o **retirarse** con un atacante de banca disponible; si ninguna se cumple, `score − 100` — no vale la pena cargar un condenado que ni ataca ni escapa.

Después, por carta:

- **Hydrapple ex**: `+23200` si <2 efectivas (bonos vs fuego `+500`, agresivos/Beedrill `+300`); `+15000` si `_extra_energy_enables_ko`; `+23200` con atacante de banca listo y activo que no noquea; si no, `−100`.
- **Dipplin**: `+23200` a 0 energías (bono `+500` vs muro inmune a ex).
- **Ogerpon ex**: `+23200` si <3 efectivas; `+15000` si `_extra_energy_enables_ko`; `+23200` con atacante de banca listo sin más carga necesaria; si no, `−100`.
- **Tapu Bulu**: `+23200` con Meganium (bono vs inmune a ex) o `+15000` sin él, mientras <4.
- **Meganium**: vs Drednaw o Sylveon activo, `+23200` mientras <4 efectivas; si no, `+23200` mientras <2 físicas.
- **Chikorita/Bayleef**: `+23200` mientras la efectiva no cubra su coste de retirada.
- **Meowth ex**: solo con atacante real en banca al que promover (`+23200`); si no, `−500`.
- **Fezandipiti ex**: `−100` con ≥3 efectivas; `+23200` si la próxima carga llega a 3; a 0 con atacante en banca `+23200`, sin él `+5000`; resto `−200`.
- **Pinsir**: `+23200` si <2 efectivas (bono vs muro inmune a ex).

### Rama por defecto — banca

Valores análogos pero menores: Ogerpon ex `+400`/`+250`/`+150` por tramo; Tapu Bulu `−100` sin Meganium, `+350` vs inmune-a-ex con <2 físicas; Hydrapple ex `+23100` si <2 efectivas (único caso alto en banca); Dipplin `+150` a 0 (bonos vs inmune-a-ex/Drednaw/Sylveon); Applin `+40`/`+50` (solo si la evolución completa es jugable ya) /`−300`/`−400`; Meganium `+500` vs Drednaw/`_sylveon_threat` con <4 efectivas; Meowth ex `−100` (−50 extra vs Froslass); Fezandipiti ex `+300` si es `plan.attacker`, `+200` si no hay otro atacante, `−100` resto; Pinsir `+350` vs inmune-a-ex con <2 efectivas.

## Contextos posteriores: ACTIVATE, promoción, `ctx` y arranque del bucle

### `_sel_active_cant_attack`

Determina, con `ATTACK_ENERGY_REQ` como fuente única, si el activo propio **no puede atacar** este turno (ni ahora ni tras adjuntar la Planta de la mano). Meowth ex cuenta siempre como "no puede" (su ataque no es un plan real). Bandera reutilizada en el bucle principal.

### `ACTIVATE`: saltar la habilidad de Meowth ex (`_meowth_skip_fetch`)

La condición vive ahora en un predicado de **tablero**, `_meowth_fetch_ya_en_mano` (`_meowth_devel_lillie` activo + `Lillie_Determination` ya en mano + sin remate vía Boss's, `_win_via_boss_gust`/`_gust_2prize_via_boss`): el Supporter que queremos jugar ya lo tenemos y solo se juega UNO por turno, así que buscar otro no aporta. `_meowth_skip_fetch` es ese predicado **más** el contexto (`ACTIVATE` con `contextCard` = Meowth ex). Separarlo importa porque el mismo predicado gobierna ahora el motor que BAJA el Meowth ex (doc 12): antes el motor Xerosic lo bajaba y este prompt rechazaba el fetch acto seguido — mismo tablero, dos respuestas opuestas y un cuerpo de 2 premios regalado (log 88162677 paso 16 vs Alakazam, PERDIDA). La bandera se consume en las ramas `YES`/`NO` del bucle: normalmente `YES` en `ACTIVATE` puntúa 10, pero con `_meowth_skip_fetch` se invierte (`YES` → −1, `NO` → 10).

### `_boss_low_value_gust`

Si el mejor gusteo de Boss's es de bajo valor (`_boss_prize_rank >= 7`, sin remate ni redirección) y vamos ganando en premios con Lillie's disponible, se marca para preferir desarrollar mano en vez de quemar el Boss's.

### Sacrificio anti-Mega Lucario

Banderas para el turno 2 yendo segundos con un Riolu rival activo energizado (evolucionará a Mega Lucario ex y noqueará un ex por 2 premios):

- **`_lucario_sac_context` / `_lucario_sac_pivot`**: detecta la amenaza y que el activo propio sea justo Ogerpon ex.
- **`_lucario_sac_available`**: hay cuerpo barato para sacrificar (Tapu Bulu, Applin o Chikorita en juego, o Tapu Bulu en mano con banca libre).
- **`_lucario_hydra_engine` / `_tapu_sac_priority`**: Tapu Bulu solo se sacrifica **primero** si aporta valor inmediato (rival con protección a ex/habilidad, o motor Hydrapple ex cargado + Meganium); si no, se sacrifica Applin > Chikorita y se conserva Tapu Bulu (`_lucario_other_sac_available`).

Estas banderas se consumen en la rama `CARD` de `SWITCH`/`TO_ACTIVE` (doc 11): con `_tapu_sac_priority`, el orden de promoción es Tapu Bulu (6000) > Applin (5500) > Chikorita (5000); si no, Applin (6000) > Chikorita (5500) > Tapu Bulu (200).

### `_lillie_protected_once`

Bandera inicializada en `False` que la puntuación de `DISCARD` usa para proteger la primera copia de Lillie's vista al valorar descartes — solo las copias sobrantes son libremente descartables.

### Promoción tras KO: `_best_promote_card` / `_forced_ko_promote`

Cuando el activo propio fue noqueado (`context in (SWITCH, TO_ACTIVE)` sin Pokémon activo) y no estamos en el sacrificio anti-Lucario, se calcula de forma centralizada **qué Pokémon de banca promover**, iterando los candidatos:

- Requiere que pueda atacar este turno (energía efectiva actual, o tras adjuntar si hay Planta en mano o Night Stretcher con Planta en el descarte) según `ATTACK_ENERGY_REQ`.
- Estima su daño `_pb_dmg` con fórmulas propias por carta: Hydrapple ex `30 + 30×total_grass`; Ogerpon ex con la Myriad **corregida** `30 + 30×(energía_propia + energía_del_activo_rival)`; Dipplin `20×(banca−1)` (él mismo la abandona al promoverse); Tapu Bulu 220; Meganium 140; Fezandipiti ex 100; resto 10.
- Aplica inmunidad a ex (Crustle/Sylveon → 0), **Neutralization Zone** (nuestros ex hacen 0 a un activo rival sin Rule Box), inmunidad de habilidad (Cornerstone → 0) y debilidad de tipo (×2).
- Elige por clave lexicográfica **`(puede_noquear, prudencia, vida, daño)`** (`_pb_key`). La **prudencia de premios** (`_pb_pref`) es la generalización de julio 2026: vale 1 si el candidato **sobrevive** el golpe rival proyectado (`_op_active_attack_damage_to`, que incluye el Powerful Hand de Alakazam pasando `op_state.handCount`) **o** cede solo 1 premio (`prize_count == 1`); vale 0 para un ex de 2 premios igualmente condenado. La prudencia **solo discrimina entre candidatos que noquean**; con daño rival ilegible (proyección 0) todos "sobreviven" y la clave queda exactamente como la clásica `(puede_noquear, vida, daño)` — conservador: solo cambia conducta con evidencia.
- Override universal de **Tapu Bulu**: si un Tapu Bulu de banca puede atacar y sus 220 noquean al rival, se promueve **siempre** (no-ex de 1 premio que remata igual que un ex).
- Override vs Alakazam (**`_ak_1prize_prom`**): preferir siempre un cuerpo de **1 premio** que noquee — la detección ya no es una whitelist Meganium/Tapu: incluye **Dipplin** (Do the Wave = `20×(banca−1)` al promoverlo) y **Pinsir** (100). Entre varios candidatos de 1 premio se sube el de más vida.

**`_lucario_ko_prefer_basic`**: si ningún candidato puede atacar (`_best_promote_card is None`) y el rival es Mega Lucario, se prefiere promover un básico (Applin primero, o Dipplin) para entregar 1 premio en vez de un ex.

### `_refresh_promote_prefer_basic`

Al promover (por retiro o KO) cuando **ningún** cuerpo de banca puede atacar este turno (`_refresh_no_attacker`, incluyendo el posible adjunte) y hay Lillie's en mano, se prefiere subir un básico de 1 premio (Applin primero) en vez de un ex de 2 premios, como muro barato mientras se rehace la mano — solo si el rival no es inmune a ex/habilidad (esos matchups ya tienen su propia lógica de muro).

### Matchup Crustle + Mega Kangaskhan: reparto de atacantes (`_cm_use_ex`)

Contra un mazo que combina Crustle (inmune a ex) con Mega Kangaskhan ex, se calcula si tenemos un ex propio (Ogerpon/Hydrapple) capaz de atacar **este turno** cuando el activo rival NO es el muro (`_cm_vs_ex_target`, `_cm_have_ex_attacker`). `_cm_use_ex` señala usar el ex contra el objetivo no inmune y **reservar** los no-ex (sobre todo Tapu Bulu, que noquea a Crustle de un golpe). Se consume en la promoción (doc 11).

### `DecisionContext` (`ctx`)

Se construye una sola vez por decisión el objeto `ctx` con las entradas invariantes que consumen los scorers extraídos `_score_*_play` (Forest, BCS, Ultra Ball, Night Stretcher, Poke Pad, Unfair Stamp, Boss's, **Xerosic**, Lillie's, Lana's; doc 12): contadores, flags de matchup, la escalera de Boss's (`win_via_boss_gust`, `gust_2prize_via_boss`, `boss_win_via_bench`, `boss_dodge_redirect`, `boss_deny_alakazam_line`, `boss_ko_threat_preevo`, `boss_prize_rank`…), `op_hand_count` (clave para Xerosic), `has_ready_bench_attacker`, etc.

### `_teal_dance_slots`

En contexto `MAIN` se recopilan las posiciones `(area, index)` de los Ogerpon que **aún pueden usar Teal Dance** este turno (aparece su opción `ABILITY`). La rama `ATTACH` (doc 13) las usa para **vetar el adjunte manual a ese mismo slot**: Teal Dance adjunta la Planta Y roba, así que precede al adjunte manual.

### `_alakazam_pivot_1prize`

En contexto `MAIN` vs Alakazam, si el activo es un ex nuestro que puede atacar, puede pagar su retirada, y en banca hay **cualquier cuerpo de 1 premio** (detección por `prize_count(bp) == 1`, ya no whitelist: Dipplin/Meganium/Tapu Bulu/Pinsir, daño vía `_attacker_base_damage`) listo que **noquea** al activo rival, se marca el pivote: retirar el ex y atacar con el 1-premio (mismo KO, cede 1 premio y no 2). No aplica si atacar con el ex ya gana la partida (`_akp_win_now`). La rama `RETREAT` lo eleva a 6000 (doc 14) y la promoción elige el cuerpo vía `_best_promote_card`/`_ak_1prize_prom`.

### Arranque del bucle: NUMBER, ACTIVATE, IS_FIRST, COIN_HEAD

Aquí arranca el gran bucle `for o in select.option` (documentado en detalle desde el doc 11). Primeras ramas:

- **`NUMBER`**: `score = o.number` — se prefiere el número más alto ofrecido.
- **`YES` en `ACTIVATE`**: score 10 (activar la habilidad), invertido a −1 si `_meowth_skip_fetch`.
- **`YES`/`NO` en `IS_FIRST`**: el agente **siempre** elige `NO` (score 2) sobre `YES` (−1) — prioriza ir **segundo**. Además actualiza el global `we_go_first`, que condiciona docenas de reglas de turno 1/2.
- **`YES` en `COIN_HEAD`**: score 2 fijo — siempre "cara".
- **`NO` en `ACTIVATE` con `_meowth_skip_fetch`**: puntúa 10 (inversión de la preferencia normal).

## Interacciones

- **Reutilización dual de `energy_score`**: se llama desde `OptionType.ATTACH` (adjunte manual) y desde `SelectContext.ATTACH_FROM` (objetivo de *Ripening Charge*). Todas las reglas de tope, prioridad de KO y pivotes de retirada aplican igual — por eso casi todos los comentarios dicen "cubre el adjunte MANUAL y el objetivo de Ripening Charge".
- **Consumo de banderas de matchup**: `energy_score` depende de flags calculadas antes (`op_is_crustle_deck`, `op_is_cornerstone_deck`, `neutralization_zone_active`, `_active_already_kos`, `_extra_energy_enables_ko`, `_win_via_boss_gust`, `_gust_2prize_via_boss`, la familia `_ctm_*`). La **inferencia por descarte rival** (doc 06) puede activar los flags de arquetipo 2-3 turnos antes que la detección por tablero, con lo que estos sub-scorers entran antes.
- **Energía efectiva vs física**: casi todas las ramas distinguen entre `len(pokemon.energies)` (efectiva, ya duplicada por *Wild Growth*) y `_physical_energy` (cartas reales) — los topes se razonan en físicas, los umbrales de ataque en efectivas.
- **Encadenamiento de pivotes**: los pivotes anti-muro (`_teal_dance_ko_pivot`, `_ripen_retreat_ko_pivot`, `_ripen_bench_tapu_ko_pivot`) se re-evalúan en cada paso del turno (scorer greedy): tras un adjunte que deja a Tapu listo, la siguiente llamada a `energy_score` ve otro estado y activa el pivote siguiente de la cadena.
- **Proyección defensiva**: `_op_active_attack_damage_to(op_active, target, op_hand_count)` modela ahora el **Powerful Hand** de Alakazam (`20 × (mano_rival + 2)`) y el **Maximum Belt** (+50 contra nuestros ex); la prudencia de `_best_promote_card` y los pivotes defensivos la consumen.
- **Con el doc 11**: `_best_promote_card`, `_lucario_ko_prefer_basic`, `_refresh_promote_prefer_basic`, `_tapu_sac_priority`, `_cm_use_ex` y `_alakazam_pivot_1prize` se calculan aquí pero se **consumen** en las ramas `CARD` de `SWITCH`/`TO_ACTIVE` y en `RETREAT` (doc 14).

## Reglas derivadas de partidas

Los comentarios del bloque citan las partidas que motivaron cada regla; las más relevantes:

- Desempate por vida entre candidatos iguales (vs Alakazam, GANADA).
- Chikorita activo cargado para retirar y pivotes Ripening→Tapu (vs Crustle, GANADA).
- Remate ganador vía Boss's con prioridad 42000 (vs Alakazam, GANADA).
- No cargar un Fezandipiti condenado; priorizar Hydrapple de banca (vs Mega Lucario, PERDIDA).
- Tope de 2 físicas en banca para Ogerpon ex vs Crustle.
- `_keep_ogerpon_for_kang`: conservar Ogerpon activo para atacar al Mega Kangaskhan vía Boss's (vs Crustle, PERDIDA).
- `_nonex_active_hits_wall`: un no-ex que golpea al muro nunca se retira (vs Crustle, GANADA).
- Pivote Teal Dance→retirar→promover; no sobrecargar Tapu si Meganium es evolucionable este turno.
- Vetar carga a Tapu Bulu condenado, preferir Teal Dance (vs Mega Lucario, PERDIDA).
- Pivote de Hydrapple frágil (vs Abomasnow, GANADA).
- Preferir promover básico con Lillie's en mano si nadie puede atacar.
- Letal de doble carga de Ogerpon (`_ogerpon_td_manual_lethal`, vs Marnie's Grimmsnarl).
- Pivote de sacrificio a 1 premio (`_fragile_ex_sac_pivot`) y pivote 1-premio vs Alakazam (`_alakazam_pivot_1prize`), ambos de registros vs Alakazam/Mega Lucario.
- Fórmula de Myriad corregida en `_ak_dmg`/`_otml_dmg`/`_pb_dmg` (auditoría julio 2026, verificada con 6 registros).
