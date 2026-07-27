# main.py — Análisis de amenaza y plan de ataque

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este bloque es el corazón táctico del agente: dentro del `if context == SelectContext.MAIN:`, primero hace un **pre-escaneo barato** de qué tipos de opción hay disponibles este turno (¿puedo jugar Boss's Orders?, ¿puedo RETREAT?, ¿puedo ATTACK?) y luego ejecuta el **cálculo central del `AttackPlan`**: para cada Pokémon propio en juego (activo primero, banca solo si hay retirada disponible) y cada objetivo rival, simula el daño de su mejor ataque, lo pondera con docenas de reglas de matchup (inmunidades, cartas prioritarias, arquetipo rival) y se queda con la combinación `(atacante, objetivo, ataque)` de mayor puntaje. El resultado se guarda en el objeto global `plan` (`AttackPlan`), que actúa de "pizarrón compartido": las fases posteriores (adjunte de energía, retirada, ataque, Boss's Orders) **leen** `plan.attacker`/`plan.target`/`plan.attack_index`/`plan.remain_hp`/`plan.energy` en vez de recalcular la decisión, evitando contradicciones entre "qué energía cargo" y "quién ataca realmente".

Tras fijar el mejor puntaje, el bloque encadena una serie de **overrides de pivote** (promover un Hydrapple ex de banca, pivotar a un cuerpo de 1 premio, sacrificar premios de forma controlada…), cada uno activado por condiciones de amenaza calculadas en el bloque de detección de matchup (`active_ko_likely`, `active_hp_ratio`, `_hydra_wall_pivot`; ver `main-06`). Estos overrides pueden **reescribir `plan.attacker`** aunque ya hubiera un plan positivo, porque priorizan la supervivencia del cuerpo activo o la gestión de premios por encima del daño bruto. El bloque cierra con la detección de "activo estancado" (`_active_cant_attack_this_turn`).

## Detalle por bloque

### Pre-escaneo de opciones disponibles

Un primer bucle sobre `select.option` puebla tres banderas baratas: `can_op_switch` (hay `Boss_Orders` jugable desde la mano — solo con él tiene sentido considerar objetivos de banca rival, porque es la única forma de forzar al rival a exponerlos), `can_switch` (hay opción `RETREAT` entre las opciones, es decir, la energía física adjunta ya cubre el coste de retirada) y `can_attack`. Un segundo bucle separado busca la carta de intercambio (id 1123) con `get_card`: si está jugable, fuerza `can_switch = True` y marca `has_switch_card` — bandera derivada exclusivamente de esa carta, usada después para poner `_ret_cost = 0` (retirada gratuita) en las promociones y en los cálculos de Grass restante tras retirar. Mantener los dos bucles separados hace explícito que cada búsqueda consulta un ID distinto con efectos colaterales distintos. Después se construyen las listas planas `my_cards` y `op_cards` (`[activo] + banca`, filtrando `None`), cuyos índices `i`/`j` (0 = activo, 1..n = banca) se reutilizan tal cual como `plan.attacker`/`plan.target` — el contrato de índices que comparten todas las fases posteriores.

### Bucle principal: selección de atacante y objetivo

Solo se ejecuta a partir del turno 2. El bucle exterior recorre `my_cards` con un corte clave: los atacantes de banca (`i != 0`) solo se evalúan si `can_switch` — nunca se calculan planes imposibles de ejecutar este turno.

Para cada Pokémon se construye `attack_options` (tuplas `(energy_req, base_damage, attack_idx, colorless_ok)`, como mucho un ataque por Pokémon), replicando las fórmulas de `_attacker_base_damage` de forma inline para poder proyectar variantes con energía adicional:

- `Hydrapple_ex`: `syrup_dmg = 30 + 30 × _syrup_grass`, proyectando el adjunte del turno si no se ha usado.
- `Dipplin`: `wave_dmg = 20 × bench_count`.
- `Teal_Mask_Ogerpon_ex`: `leaf_dmg = 30 + 30 × (energía propia + energía del activo rival)` — **regla verificada con 6 registros**: *Myriad Leaf Shower* cuenta la energía de AMBOS activos; la copia inline anterior usaba solo la propia y el argmax subestimaba KOs reales (elegía otro atacante o un chip). Todas las copias inline de esta fórmula en `main.py` (scoring de ataque, `_pdp_abase`, `_ak_dmg`, `_otml_dmg`, promociones, Teal Dance) fueron alineadas con esta regla.
- `Tapu_Bulu` 220 fijo; `Meganium` 140 fijo; `Fezandipiti_ex` 100 fijo (`colorless_ok`); `Pinsir` 100 con `attack_idx = 1` (código latente: Pinsir ya no está en el mazo).

Si la energía efectiva (`len(energies) × _grass_mult()`) no alcanza el requisito, se intentan dos vías de "energía proyectada" antes de descartar la opción: el **adjunte manual** (Grass en mano y `not state.energyAttached`, sumando `_grass_attach_unit()` — 1 o 2 según Meganium; si alcanza, `more_energy = True`, si no se descarta) y, solo para atacantes de banca (`i != 0`), **Night Stretcher** (hay la carta en mano y una Grass básica en el descarte que recuperar; si con ella alcanza, marca `more_energy` y además `_ns_energy_recovery`, informativa). Si ninguna vía cubre el requisito, la opción de ataque se descarta para ese Pokémon.

### Puntaje base por atacante y matchup

`base_score` acumula bonificaciones/penalizaciones por identidad del atacante antes de mirar el objetivo concreto (`my_is_ex = id in OUR_EX_IDS` y `_op_active_is_drednaw` se calculan una vez):

- **`Hydrapple_ex`**: +200 de base; −2000 si el rival anula Habilidades (`op_has_ability_immune_active`, depende de *Ripening Charge*); si el activo rival es Drednaw y su *Syrup Storm* estimado (`30 + 30 × total_grass`) alcanzaría el tope de 200 que Drednaw anula, −3000; si no hay Drednaw, +150 contra `op_is_fire_deck` y +100 contra `op_is_aggro_deck`.
- **`Dipplin`**: +50 base; +1200 contra inmunidad a ex (no es ex, la inmunidad no le aplica); +1500 contra inmunidad de Habilidad; +2500 contra Drednaw (su daño por banca queda lejos del tope).
- **`Tapu_Bulu`**: +2200 contra inmunidad a ex (+800 extra si el rival es `Sylveon`); +2500 contra inmunidad de Habilidad; −3000 contra Drednaw (220 fijo dispara el tope y se anula); +800 contra fuego; +500 contra control/Slowking; +100 genérico en el resto.
- **`Pinsir`** (código latente): +50 base; +1300/+1600 contra inmunidad ex/Habilidad; +2300 contra Drednaw.
- **`Meganium`**: +1500 contra inmunidad a ex (+2000 extra vs Sylveon); −2000 contra inmunidad de Habilidad (depende de *Wild Growth*); +3500 contra Drednaw (140 fijo, seguro).
- **`Teal_Mask_Ogerpon_ex`**: −100 de base (su daño ya escala solo) y −2000 contra inmunidad de Habilidad.
- **`Fezandipiti_ex`**: −2000 tanto contra inmunidad a ex como de Habilidad.
- **Zona de Neutralización**: −3000 a cualquier ex propio y +2000 a los no-ex mientras el estadio siga en juego.

### Bucle interno de objetivos

Los objetivos de banca rival (`j != 0`) solo se consideran si `can_op_switch` **o** si el atacante es `Fezandipiti_ex`, cuyo *Cruel Arrow* golpea la banca sin Boss's. El cálculo de `damage` reimplementa la cadena de `_our_effective_damage` integrada en el bucle: inmunidad ex (`EX_IMMUNE_IDS` — que incluye ambos Crustle y Sylveon — contra `OUR_EX_IDS` → 0), Zona de Neutralización contra objetivos sin Rule Box, inmunidad de Habilidad (`ABILITY_IMMUNE_IDS` × `OUR_ABILITY_IDS` → 0), debilidad/resistencia Planta (salvo Fezandipiti, cuyo ataque no es Planta), tope de Drednaw (≥200 → 0) y el recorte de `Crustle_Fighting` a vida completa (Sturdy: no cae de un golpe).

El `score` del objetivo parte de `pokemon_score(op_pokemon)` (valor genérico de la amenaza: premios ×1000, energías ×150, herramientas ×100 y bonos de etapa). Vetos y escalas: objetivo indañable por inmunidad/Zona/caparazón de Drednaw → `score = -5000` (veto fuerte, nunca se elegirá); KO → se registran los premios (`prize_count`); sin KO → el valor se escala por `damage / hp` (la fracción de vida que le quitaríamos); después se suma `base_score`.

Sigue una larga cascada de **bonos por especie rival prioritaria**, cada una con un bono mayor si el golpe noquea: `Budew` +8000/+3000, `Froslass` +9000/+4000 (el mayor KO de la lista: amenaza de Habilidad a eliminar cuanto antes), `Munkidori`, `Snorunt`, la línea `Dreepy`/`Drakloak` (+6500 de KO normal, elevado a +9800 para `Drakloak` cuando `op_has_dreepy_line` confirma el mazo Dragapult — sin este boost, el snipe gratuito de *Cruel Arrow* prefería noquear a Budew, 30 HP de soporte, antes que al Stage-1 a un paso de Dragapult ex), `Dwebble_*`, los muros `EX_IMMUNE_IDS` golpeables por un no-ex, `Crustle_Fighting` dañado, líneas `Ralts`/`Kirlia`/`Gardevoir_ex`, `Abra`/`Kadabra`/`Alakazam_ex`, `Slowpoke`/`Slowking`, `Duskull`/`Dusclops`/`Dusknoir`, `Zorua_N`/`Zoroark_N`, `Typhlosion` y pre-evos, `Chewtle`/`Drednaw`, `EEVEE_IDS` y `Sylveon` (+9000/+4000, solo con daño positivo). `Fezandipiti_ex` recibe además un bono graduado por la etapa del objetivo noqueado (+5000 Stage-2, +4500 ex, +3500 básico, +3000 Stage-1; +500 por dañar al activo sin KO): *Cruel Arrow* es más valioso cuanto más cara es la pieza que corta.

**Cierre de victoria y desempates**: si el KO nos da los premios que faltan (`my_prize <= prize`), el puntaje se fija al techo de 50000 — ganar ya domina cualquier escalera; si el KO deja al rival a exactamente 1 premio restante, +4000 (estrechar su ventana de reacción); +220 por atacar con el propio activo (`i == 0`, sin retirar), +300 por golpear al activo rival (`j == 0`), y `+effective_energy` como desempate menor por energía ya invertida.

### Lookahead de intercambio (trade)

Único punto del bucle que mira un turno adelante: `_op_best_damage_vs(my_pokemon)` estima el contragolpe rival (asumiendo su adjunte). Si el golpe de vuelta noquearía a nuestro atacante: para un ex, penalización `SCORE_LOOKAHEAD_EX_TRADE` (250) escalada por `0.6 + 0.4 × _op_disruption_belief(op_state)` — la probabilidad estimada de que el rival tenga en mano con qué completar el remate interpola la sanción entre el 60% y el 100%; para un no-ex, penalización fija `SCORE_LOOKAHEAD_KO_TRADE` (120) — un intercambio de 1 premio es menos grave. Si el contragolpe es débil (≤40% de la vida del atacante), bono `SCORE_LOOKAHEAD_SAFE` (60). Es el mecanismo de "trades ex": no exponer 2 premios a cambio de poco.

### Fijación de `plan.*`

Selección de máximo simple: cada vez que `score` supera el mejor acumulado se sobrescriben los cinco campos de `plan`. `plan.remain_hp` puede ser negativo (KO con sobrante); `plan.energy = more_energy` señala "este plan requiere el adjunte (o Night Stretcher) para ser viable", leída por `energy_score` vía `_attacker_ready`.

### Promoción y remate con Hydrapple ex de banca

Con `can_switch`, activo rival presente y nuestro activo distinto de Hydrapple ex, se busca el mejor candidato de banca en dos categorías: `_hydra_mc_idx` (ya listo, ≥2 efectivas) y `_hydra_charge_idx` (llegaría a 2 con el adjunte del turno, `_grass_in_hand_promo`). **Desempate por vida** (log 86212499, GANADA vs Alakazam): antes el bucle tomaba el primer Hydrapple apto por orden de banca — normalmente el más frágil (p.ej. uno a 70 HP antes que otro a 330); ahora recorre toda la banca y, a igualdad de aptitud, elige el de mayor HP, manteniendo que un Hydrapple ya cargado prevalece sobre uno que necesita carga. El de carga solo se activa si el activo actual, de quedarse, ya podría atacar (`_ret_act_ready_now`) o no tiene requisito conocido: no se sacrifica el turno de ataque para cargar un banca que tampoco atacaría.

El daño proyectado usa `_hydra_grass_after = total_grass − _retreat_grass_units(coste)` (la retirada descarta Grass del campo y *Syrup Storm* escala con el Grass total; con `has_switch_card` el coste es 0, y *Wild Growth* hace que cada Planta pague por dos, descartando menos cartas), más la carga pendiente si el candidato la necesitaba. En paralelo se evalúa si el activo actual, de quedarse, también noquearía (`_act_can_ko`, con perfiles de daño por especie). `_promote_hydra = _hydra_can_ko or (not _act_can_ko)`: se promueve si el Hydrapple noquea, o si el activo no puede noquear de todas formas (mejor el cuerpo resistente); nunca si el Hydrapple ni siquiera daña. **Veto Tapu Bulu** (registro 010 vs Alakazam): un Tapu Bulu cargado en el activo que puede noquear ataca él mismo — es no-ex (1 premio) y no cede el remate a la Hydrapple ex (2 premios). Si procede, `plan.*` se sobrescribe apuntando al Hydrapple contra el activo rival con `plan.energy = False` (la carga ya se contabilizó).

### Reglas contra "rule box" bloqueado propio

Si el plan apunta ya a un atacante de banca (`plan.attacker >= 1`, típicamente fijado por la promoción anterior), el activo es un ex nuestro y el activo rival **no** es inmune a ex, se comprueba si el activo podría dañar de todas formas: `_rule_act_immune` cubre los dos bloqueos restantes (rival inmune a Habilidad con activo dependiente de Habilidad, o Zona de Neutralización contra un rival sin Rule Box). Si el activo sí puede dañar — perfil limitado a `Teal_Mask_Ogerpon_ex`, `Hydrapple_ex` y `Fezandipiti_ex`, con energía actual o proyectada — y el plan de banca **no** garantizaba ya el KO del mismo objetivo (`plan.target == 0 and plan.remain_hp <= 0`), se **revierte** el plan al propio activo: no retirar innecesariamente cuando el activo aporta daño real y el plan de banca no tenía asegurado el remate.

### Pivote defensivo a Hydrapple ex sano (con KO)

Si el activo propio es frágil (`active_ko_likely` o `active_hp_ratio <= 0.6`) y hay un Hydrapple ex en banca con ≥2 energías efectivas (*Wild Growth* de Meganium cuenta: duplica la Planta, así que Hydrapple ataca con menos cartas) cuyo *Syrup Storm* (`30 + 30 × total_grass` vía `_our_effective_damage`) noquea al activo rival, se fija el plan hacia él y se activa `_hydra_pivot_active` (bloquea los overrides posteriores redundantes): el KO se entrega igual pero desde el cuerpo de 330 HP, muy difícil de noquear, y el activo frágil se resguarda en banca sin regalar premios. Dos exigencias finas: el candidato debe estar **a vida completa** (`hp >= maxHp`; dañado no aporta la ventaja de muro) y, si el activo ya es un Hydrapple, el de banca debe tener **más** vida que él (pivotar entre iguales no aporta y además pierde Grass por la retirada — caso registro_023 vs Archaludon, donde el *Syrup Storm* del promovido debe seguir noqueando tras descontar el coste). Vetado si el activo es un Tapu Bulu con KO disponible (misma regla de registro 010: el no-ex remata él mismo).

### Pivote-muro a Hydrapple ex SIN KO

Complemento para cuando no hay KO disponible, solo protección (log 85856881). Si `_hydra_wall_pivot` (calculado en `main-06`, incluida su generalización a cualquier rival y la proyección de Powerful Hand vs Alakazam) está activo, no hay ya pivote con KO (`not _hydra_pivot_active`) y el plan apunta al activo (`plan.attacker == 0`), se apunta `plan.attacker` al Hydrapple de banca (a vida completa y con ≥2 efectivas) **sin exigir `can_switch`**: en el contexto MAIN inicial no existe opción RETREAT — el motor solo la expone tras elegir PASS en el menú principal. El mecanismo real es indirecto: la puntuación de ATTACK (ver `main-15`) **suprime** el ataque del activo al ver `plan.attacker >= 1` con retirada disponible, empujando al agente a PASS y, en el prompt siguiente, a retirarse hacia el muro. `plan.remain_hp` se rellena con el daño del muro (que no noquea) y `plan.energy = False`.

### Sacrificio de premios: pivote a Tapu Bulu

Dos variantes que evitan exponer un ex (2 premios) cuando un `Tapu_Bulu` de banca (1 premio, listo con ≥4 efectivas) puede tomar el mismo KO (220 de daño vía `_our_effective_damage`):

- **Defensiva**: activo ex en riesgo (`active_ko_likely` o ≤50% de vida).
- **Proactiva** (`_tapu_proactive_lead`): con Meganium en juego y sin matchup de muro (`op_is_crustle_deck`/`op_is_cornerstone_deck`/`op_is_sylveon_deck`) ni Zona de Neutralización, se permite el pivote aunque el ex esté sano — puro ahorro de premios: ¿por qué exponer 2 si 1 basta para el mismo resultado?

Condición adicional: `my_prize > prize_count(activo rival)` — si este KO ya nos diera la victoria, el caso lo resuelve el techo de 50000 del bucle principal y no hay nada que proteger. Con `can_switch` se fija el plan y `_tapu_sac_pivot = True`. Si Tapu ya remata desde banca pero **todavía no** podemos retirar al ex (le falta exactamente 1 energía física para su coste de retirada) y queda el adjunte manual del turno, se marca `_tapu_sac_enable_retreat` para que `energy_score` dirija el adjunte al ex activo y habilite la retirada — solo con Tapu ya cargado, de modo que jamás se le desvía energía a él.

### Negación de premios: pivote a un cuerpo de menos premios sin exigir KO

El más defensivo (log 86211357, PERDIDA vs Mega Starmie): si el activo es un ex condenado (`active_ko_likely`) cuyo KO le daría al rival los premios que le faltan para **ganar ya** (`op_prize >= 2` y `prize_count(activo) >= op_prize`), no conviene atacar con él. Antes se comprueba `_pdp_active_wins_now` (¿el propio activo gana ya la partida este turno? — perfiles de Hydrapple/Ogerpon/Fezandipiti, con la fórmula verificada de Myriad para Ogerpon: `30 + 30 × (energía propia + energía del activo rival)`); si gana, se ataca — ganar domina cualquier defensa. Si no, se busca en banca el mejor cuerpo que entregue **menos premios de los que el rival necesita** (`prize_count < op_prize`, es decir un no-ex) y pueda atacar este turno con o sin el adjunte proyectado, ordenado por la clave `(_pdp_survives, _pdp_dmg, _pdp_hp)`: primero sobrevivir al golpe rival estimado (`_op_best_damage_vs`), luego daño infligido, luego HP bruto. Si hay candidato, se fija el plan (con `plan.remain_hp` placeholder no-cero: aquí no importa el HP restante exacto, solo que el plan cambió de atacante) y `_prize_denial_pivot = True`. A diferencia de `_tapu_sac_pivot`, no exige KO: es ganar tiempo negando el premio letal.

### Detección de "activo estancado"

Para el activo, con `_ATK_REQS_STALL` (subconjunto de `ATTACK_ENERGY_REQ` limitado a `MAIN_ATTACKERS`, fuente única de umbrales): si ni con el adjunte llega al requisito, se evalúa la vía *Teal Dance* — si no hay Ogerpon propio con ≥1 energía (`_td_stall`) o no quedan Grass en el mazo según la creencia (`_nrg_deck`), `_active_cant_attack_this_turn = True` directamente; si la hay, se calcula la probabilidad de que **ninguna** activación de Teal Dance (que roba 1 carta; acotado a 4 activaciones) encuentre una Grass, multiplicando `(deck_total − nrg_deck) / deck_total` por activación, y se marca estancado solo si esa probabilidad supera 0.5 (más probable que no se destrabe). Finalmente, si se concluyó estancamiento pero `can_switch` y algún Pokémon de banca (excluyendo `Meowth_ex`, que no es atacante) ya cumple su requisito, se **revoca**: el activo sigue sin poder atacar, pero el equipo no está estancado y la decisión de retirar se resuelve en RETREAT (`main-14`).

## Interacciones

- **Con `AttackPlan` y los helpers de daño (`main-02`)**: este bloque es el principal escritor de `plan`; usa `_grass_mult()`, `_grass_attach_unit()`, `_retreat_cards()`, `_our_effective_damage()`, `_attacker_base_damage()`, `ATTACK_ENERGY_REQ` y `MAIN_ATTACKERS` en casi cada sub-bloque.
- **Con la detección de matchup (`main-06`)**: consume `active_ko_likely` (que ya incorpora la proyección de Powerful Hand cuando el activo rival es Alakazam), `active_hp_ratio`, `_hydra_wall_pivot`, `_op_best_damage_vs`, `total_grass` y las banderas `op_is_*`/`op_has_*`; nada de eso se recalcula aquí.
- **Con `energy_score` (`main-10`)**: lee `plan.attacker`/`plan.energy` (`_attacker_ready`) y respeta `_tapu_sac_enable_retreat` y `_hydra_fragile_pivot` para desviar el adjunte.
- **Con Boss's Orders (`main-08`)**: `plan.target` alimenta la rama de respaldo genérico de `evaluate_supporters`; `crustle_gust_worth_it` reutiliza la misma proyección de energía que este bucle.
- **Con RETREAT (`main-14`)**: `_hydra_pivot_active`, `_tapu_sac_pivot`, `_prize_denial_pivot` y `_active_cant_attack_this_turn` condicionan directamente el puntaje de la retirada; el pivote 1-premio vs Alakazam (`_alakazam_pivot_1prize`, calculado más adelante junto a los flags de decisión) generaliza el mismo patrón detectando **cualquier** cuerpo con `prize_count == 1` que noquee igual (Dipplin con `20 × (banca − 1)`, Meganium, Tapu Bulu…), para ceder 1 premio y no 2.
- **Con ATTACK (`main-15`)**: si `plan.attacker >= 1`, la opción de atacar con el activo queda suprimida o penalizada, empujando a PASS + retirada — es el mecanismo de ejecución de todos los pivotes de este bloque.
