# main.py — Detección de matchup, amenaza sobre el activo e inmunidades

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este bloque es el **escáner del tablero rival**: a partir de lo visible en el activo y la banca del oponente (más su descarte y algunos eventos de `obs.logs`), construye las banderas booleanas (`op_is_*_deck`, `op_has_*`) que **clasifican el arquetipo enemigo** y detectan **inmunidades, debilidades explotables y amenazas puntuales** (daño estimado al activo propio, contadores, esquiva, snipe a banca). No decide ninguna jugada por sí mismo — es diagnóstico puro — pero es la base condicional de casi todas las ramas de puntuación posteriores (escalera de Boss's Orders, elección de atacante, `energy_score`, prioridades de setup). Además define aquí los estimadores de daño rival (`_op_best_damage_vs`, `_op_counter_threat_vs`) y los **pivotes defensivos de posicionamiento** que dependen de esa amenaza (`_teal_wall_pivot`, `_hydra_wall_pivot`, `_feza_lucario_wall`, `_hydra_fragile_pivot`).

Salvo `op_is_crustle_deck`, `op_is_cornerstone_deck` y `op_has_mega_kangaskhan` (globales, reiniciadas al empezar una partida nueva por `_update_cartas_tracking`), todas las banderas son locales a la llamada de `agent()` y se recalculan en cada decisión.

## Detalle por bloque

### Estimadores de daño rival

- **`_op_best_damage_vs(my_pokemon, assume_attach=True)`** (función local de `agent()`): mayor daño que el activo rival podría infligir a un Pokémon propio, asumiendo que aún puede adjuntar una energía (`assume_attach`). Recorre los ataques de `card_table` quedándose con el `damage` más alto pagable; los ataques sin daño numérico (`damage is None`, p.ej. de contadores) se ignoran. Aplica dos correcciones finales: **Maximum Belt** (`Maximum_Belt`, Ace Spec): si el atacante rival la lleva como tool y el objetivo es un ex nuestro (`OUR_EX_IDS`), suma `+50` antes de debilidad — sin esto, las tools rivales eran invisibles y los pivotes creían que el muro sobrevivía a un golpe potenciado; y **debilidad** (`weakness == energyType` del atacante → `×2`). No modela resistencia.
- **`_op_counter_threat_vs(my_pokemon)`**: estima los ataques de contadores que `_op_best_damage_vs` no ve — si el activo rival es `Alakazam_ex`, devuelve `20 × mano rival` (`_op_hand_size`, con fallback conservador de 4 si la mano está oculta). Lo consume el lookahead de promociones.
- **`_op_active_attack_damage_to(op_active, target, op_hand_count=None)`** (función de módulo, documentada también en `main-02`): daño impreso máximo resuelto vía `attack_table` (los `card.attacks` son ints, no objetos, por eso `_op_best_damage_vs` devuelve 0 en muchos mazos). Aplica Maximum Belt y debilidad/resistencia del objetivo. **Proyección de Powerful Hand**: si el activo rival es `Alakazam_ex` y su ataque es `POWERFUL_HAND_ATTACK_ID`, con `op_hand_count` informado proyecta `20 × (mano + 2)` (+2 = robo del turno + Psychic Draw); sin el parámetro conserva el 0 conservador. Es la pieza que "despierta" los pivotes defensivos en el matchup Alakazam.

### Amenaza sobre el activo propio: `estimated_op_damage`, `active_ko_likely`, `_teal_wall_pivot`

- `active_hp_ratio`: fracción de vida restante del activo propio; `_mega_line_active` marca si el activo pertenece a la línea Chikorita/Bayleef/Meganium.
- `estimated_op_damage = _op_best_damage_vs(my_active)`, con una **inyección específica**: si el activo rival es `Alakazam_ex`, se toma el máximo con `_op_active_attack_damage_to(op_active, my_active, op_state.handCount)` — la proyección de Powerful Hand (20 × (mano rival + 2)). Antes el modelo creía que Alakazam pegaba 0 y ningún pivote defensivo disparaba; el ajuste está acotado al activo Alakazam para no alterar otros matchups.
- `active_ko_likely` se enciende con tres condiciones alternativas: (1) `estimated_op_damage >= my_active.hp` (KO directo estimado); (2) activo con ≤60 HP y rival con ≥2 energías; (3) `active_hp_ratio <= 0.3` con cualquier energía rival. Las condiciones 2 y 3 **sobreestiman el riesgo a propósito** para no dejar pasivo un activo condenado.
- **`_teal_wall_pivot`**: si `active_ko_likely`, el activo es `Teal_Mask_Ogerpon_ex` que **no** llega a 3 energías efectivas ni con el adjunte (`_grass_attach_unit()`), hay una `Basic_Grass_Energy` en mano y un `Hydrapple_ex` a vida completa en banca: la línea correcta es usar *Teal Dance* en el activo condenado (adjunta + roba) para habilitar su coste de retirada (1) y retirarlo hacia el muro de 330 HP, en vez de regalarlo sin sacar nada.

### Efectos de ataque detectados en `obs.logs`

- `itchy_pollen_active`: un `LogType.ATTACK` de `Budew` jugado por el rival este ciclo de logs.
- `op_active_dodge_immune` / `_dodge_pending_serial`: sigue la secuencia *ataque → tirada de moneda* de *Splashing Dodge* (`Hops_Phantump`, `Splashing_Dodge_Atk`). Si sale cara sobre el mismo activo (validado por `serial`), marca inmunidad temporal y la persiste en las globales `_dodge_immune_serial`/`_dodge_immune_turn` para recordarla el resto del turno aunque el log ya no esté.
- `budew_on_op_field` / `budew_op_index`: localiza a Budew en activo o banca rival, para que las reglas posteriores sepan si la amenaza de *Itchy Pollen* sigue en el tablero.

### Clasificación por el Pokémon ACTIVO rival

Se compara `op_active_id` contra los IDs/conjuntos constantes. Grupos principales:

| Detección | Bandera | Implicación |
| --- | --- | --- |
| `EX_IMMUNE_IDS` (`Crustle_Grass`, `Crustle_Fighting`, `Sylveon`) | `op_has_ex_immune_active` | Muro inmune al daño de nuestros ex → usar atacantes no-ex (Tapu Bulu, Dipplin, Meganium; Pinsir es código latente, ya no está en el mazo). |
| `ABILITY_IMMUNE_IDS` (`Cornerstone_Mask_Ogerpon_ex`) | `op_has_ability_immune_active`, `op_is_cornerstone_deck` | Anula Habilidades propias (Wild Growth, Last-Ditch Catch). |
| Formas de Crustle/Dwebble | `op_is_crustle_deck` (global), `op_has_sturdy_crustle` | Dispara toda la lógica anti-muro repartida por `main.py`. |
| `Mega_Kangaskhan_ex` | `op_has_mega_kangaskhan` (global) | Golpe alto tipo Mega. |
| `Froslass` / `Munkidori` / `Typhlosion` / `Cyndaquil`,`Quilava` | `op_has_froslass` / `op_has_munkidori` / `op_has_typhlosion` / `op_has_ethan_preevo` | Amenazas de carta concreta. |
| `Dragapult_ex` / `Grimmsnarl_ex` / `Mega_Greninja_ex` / `Mega_Starmie_ex` con energía | `op_has_dragapult`, `op_bench_snipe_threat`, `op_has_mega_starmie_active`, `op_is_greninja_deck` | Snipe a banca: penaliza banquear cuerpos frágiles. |
| `Latias_ex` | `op_has_latias_ex` | Skyliner: los Básicos rivales se retiran gratis (afecta el gusteo de stall de Boss's). |
| `Riolu`/`Mega_Lucario_ex`, `Cubchoo`/`Beartic`, `Hops_*`, `Comfey`/`Bramblin`/`Brambleghast` | `op_is_lucario_deck`, `op_is_cubchoo_deck`, `op_is_hop_deck`, `op_is_comfey_deck` | Arquetipos con estrategia dedicada (pivotes muro, whitelist, mill). |
| `DUNSPARCE_IDS` | `op_active_is_dunsparce` | Dunsparce nunca se gustea con Boss's (muro reposicionable). |
| Tipo de energía FIRE del activo | `op_is_fire_deck` | Clasificación genérica por tipo: acelera la carga de Hydrapple ex. |
| Cartas de nuestro propio mazo | `op_is_mirror` | Espejo Planta/ex: carrera de daño. |
| `Slowpoke`/`Slowking`, `Ralts`/`Kirlia`/`Gardevoir_ex`, `Zorua_N`/`Zoroark_N`, `Abra`/`Kadabra`/`Alakazam_ex`, `Chewtle`/`Drednaw`, `Raging_Bolt_ex`/`Lugia_VSTAR` | `op_is_slowking_deck`+`op_is_control_deck`, `op_is_gardevoir_deck`, `op_is_zoroark_deck`, `op_is_alakazam_deck`, `op_is_drednaw_deck`, `op_is_aggro_deck` | Clasificación de arquetipo. |
| `Sylveon` o `EEVEE_IDS` | `op_is_sylveon_deck` (+`op_is_crustle_deck`) | La línea Eevee se trata como variante del matchup muro-ex. |
| `Eevee_PRE_ex` | `op_has_non_immune_eevee_ex` | Para la corrección de falso positivo (abajo). |

Notas sobre el conjunto de inmunidad: `EX_IMMUNE_IDS` incluye desde la auditoría de julio 2026 **ambas** formas de Crustle (`Crustle_Grass` y `Crustle_Fighting`) además de `Sylveon` — antes la variante Lucha solo activaba `op_has_sturdy_crustle` y el cálculo de daño no la trataba como inmune a ex. `op_bench_snipe_threat` se alimenta de cuatro fuentes (Dragapult ex, Grimmsnarl ex, Mega Greninja ex y Mega Starmie ex con energía) y su único efecto es posicional: desincentivar banquear cuerpos frágiles.

### Clasificación por la BANCA rival

Repite la misma matriz iterando `op_state.bench`: la detección **no espera** a que la carta reveladora ataque, basta con que esté en juego. Matices exclusivos de banca: `op_has_dwebble_bench`/`op_has_crustle_bench` (distinguen la pieza Crustle aún sin evolucionar, para gustearla antes de que sea muro), `op_has_eevee_bench`, `op_has_snorunt_bench` (pre-evo de Froslass), `op_has_dreepy_line` (Dreepy/Drakloak vistos en cualquier zona), y `op_is_dragapult_dusknoir` (solo se confirma si al Duskull/Dusclops/Dusknoir de banca lo acompaña evidencia de la línea Dragapult, para no confundir un Dusknoir suelto de otro mazo).

**Anomalía conocida — Beedrill/Weedle/Kakuna con IDs negativos**: las constantes `Beedrill`, `Weedle`, `Kakuna` siguen valiendo IDs negativos (placeholder); `_validate_id_constants()` los salta explícitamente. Como los IDs reales nunca son negativos, `op_is_beedrill_deck` es una bandera muerta hasta corregir esas constantes; el matchup "aggro" general no queda ciego porque `op_is_aggro_deck` se activa por otras vías.

### Inferencia de arquetipo por el DESCARTE rival

Nueva capa (auditoría julio 2026): la detección por Pokémon **en juego** llega tarde contra líneas ocultas; un Pokémon del arquetipo en `op_state.discard` identifica el mazo **2-3 turnos antes** y activa las preparaciones a tiempo (reserva de banca/Xerosic vs Alakazam, plan solo-Ogerpon vs Comfey, whitelist vs Cubchoo…). El bucle sobre el descarte rival enciende únicamente los flags **estratégicos** de mazo: `op_is_alakazam_deck`, `op_is_comfey_deck`, `op_is_lucario_deck`, `op_is_hop_deck`, `op_is_cubchoo_deck`, `op_is_gardevoir_deck`, `op_is_zoroark_deck`, `op_is_slowking_deck` (+`op_is_control_deck`) y `op_is_aggro_deck`. Los flags de "muro en juego" (Crustle/Sylveon/Cornerstone, que redirigen el ataque YA) y los `op_has_*` posicionales **no** se infieren del descarte: dependen del tablero real.

### Corrección Eevee ex no inmune

`Eevee_PRE_ex` es un ex normal y atacable, no el muro Sylveon. Si `op_has_non_immune_eevee_ex` y **no** hay ningún inmune-ex real en juego (ni activo ni banca), se **revocan** `op_is_crustle_deck` y `op_is_sylveon_deck` — encendidas de forma optimista al ver cualquier `EEVEE_IDS` — y el agente vuelve a la estrategia normal contra ex. La corrección se aplica después de escanear todo el tablero para no depender del orden de descubrimiento.

### `total_grass` y pivotes de "muro Hydrapple ex"

`total_grass = count_total_grass_energy(my_state)` alimenta los cálculos de *Syrup Storm* (`30 + 30 × total_grass`) de los pivotes:

- **`_hydra_wall_pivot` (rama Mega Lucario)** — log 85856881, GANADA: a diferencia de `_teal_wall_pivot` (activo que no puede atacar), aquí el Ogerpon activo **sí** puede atacar (≥3 energías) pero su *Myriad Leaf Shower* no noquea y Mega Lucario lo remata el próximo turno (*Mega Brave* 270 > 210 HP). Si puede pagar su retirada (`_physical_energy` ≥ `RETREAT_COST`) y hay un Hydrapple ex a vida completa en banca (muro de 330 HP) que sobrevive a `_op_best_damage_vs` y tiene ≥2 efectivas, se activa el flag; el plan se apuntará al muro para **suprimir** el ataque del Ogerpon (mecanismo en `main-07`). Acotado a `op_is_lucario_deck` + `active_ko_likely` porque esta rama histórica no leía el daño rival real.
- **Generalización a cualquier rival** — registro_006 vs Archaludon, PERDIDA: el mismo patrón sin exigir `op_is_lucario_deck`. Aquí se exige el remate rival **real** vía `_op_active_attack_damage_to` (tanto para condenar al Ogerpon como para validar que el muro sobrevive); si el ataque rival no se puede leer, el helper da 0 y el pivote no dispara (conservador). Se pasa `op_state.handCount` para que **Powerful Hand sí se modele**: vs Alakazam el pivote ahora puede disparar; si a la vez hay un cuerpo de 1 premio que noquea (`_alakazam_pivot_1prize`), el retiro se dispara igual y la promoción la resuelve el bloque `op_is_alakazam_deck` de `_best_promote_card` (1 premio > muro). El daño del Ogerpon usa la fórmula verificada de Myriad: `30 + 30 × (energía propia + energía del activo rival)`.
- **`_feza_lucario_wall`** — log 86342087, PERDIDA (regla correctiva): mismo patrón con `Fezandipiti_ex` activo débil a Lucha (*Mega Brave* 270 ×2 = 540, y son 2 premios), mientras el Hydrapple de banca sobrevive (su debilidad es Fuego, no Lucha). Habilita en `energy_score` la carga del Hydrapple de banca; cuando este ya está listo (≥2 efectivas) y el Feza puede pagar su retirada (coste 1), activa directamente `_hydra_wall_pivot` para forzar la retirada — mismo mecanismo de supresión del ataque que el pivote de Ogerpon.
- **`_hydra_fragile_pivot`** — log 86027506, GANADA: el activo **ya es** un Hydrapple ex dañado que no puede pagar aún su retirada (coste 3). Si hay otro Hydrapple ex en banca con más vida, que sobrevive al golpe rival, con ≥2 efectivas y cuyo *Syrup Storm* noquearía al activo rival, el flag habilita en `energy_score` enrutar la energía del turno (adjunte + Ripening Charge) al activo frágil para alcanzar el coste de retirada; el retiro+promoción posterior lo cubre `_hydra_lethal_promote`.

### Confusión y atacante alternativo en matchup de muro

- `_conf_ex_immune_match`: booleano único de "estamos en matchup de muro" (Crustle/Cornerstone/inmunes en juego).
- `_conf_can_attack_pkmn(_p)`: si un Pokémon propio tiene energía efectiva para atacar (umbrales por carta, con `_grass_mult()`).
- `_conf_is_matchup_attacker(_pid)`: en matchup de muro solo cuentan los no-ex capaces de dañar al muro; si no, cualquier atacante del mazo.
- `_conf_bench_attacker_ready`/`_conf_bench_attacker_body`, `_conf_active_can_retreat`, `_conf_active_can_attack`, `_conf_should_retreat`, `_conf_should_attack`: bajo confusión (`is_confused`), deciden si conviene retirar el activo confuso hacia un atacante de banca listo o, a falta de alternativa, arriesgar el ataque. Coherente con la estrategia vs Comfey (activo confundido → retirar a atacante de banca).

### Cierre: banderas de ataque/cambio

`can_attack`, `_active_cant_attack_this_turn`, `_hydra_pivot_active`, `_tapu_sac_pivot`, `_tapu_sac_enable_retreat`, `_prize_denial_pivot`, `_bo_active_attack_sufficient`, `can_switch`, `can_op_switch`, `has_switch_card` se inicializan a `False` como preparación del bloque de plan de ataque (`main-07`), que abre con `if context == SelectContext.MAIN:`.

## Interacciones

- **`op_is_crustle_deck` / `op_is_cornerstone_deck` / inmunidades**: condicionan la escalera de Boss's Orders (`main-08`), la prioridad de atacante del bucle principal (`main-07`), `energy_score` (`main-10`) y decenas de puntos de PLAY/ATTACH/RETREAT.
- **`op_is_alakazam_deck`**: además de las reglas de Boss's, activa la reserva del último slot de banca para Meowth mientras Xerosic esté en el mazo, el motor Xerosic (`_score_xerosic_play`, `main-09`) y el pivote 1-premio (`_alakazam_pivot_1prize`).
- **`op_is_comfey_deck`**: activa la estrategia completa anti-mill (solo Ogerpon ex, Lillie's con mano ≥10, descarte dirigido) repartida por PLAY/DISCARD.
- **`op_bench_snipe_threat`**: baja la prioridad de banquear cuerpos frágiles en setup y PLAY.
- **`op_is_lucario_deck`**: activa los pivotes muro documentados arriba.
- **`stadium_id`** y derivados (`forest_in_play`, `neutralization_zone_active`, `watchtower_in_play`) interactúan con la elección de atacante: la Zona penaliza a los ex propios y premia a los no-ex; la Watchtower anula Last-Ditch Catch de Meowth ex.

## Reglas derivadas de partidas

- **log 85856881 (GANADA, vs Mega Lucario)**: origen de `_hydra_wall_pivot` — retirar al Ogerpon condenado que no noquea, promover el muro sano.
- **registro_006 paso 84 (PERDIDA, vs Archaludon)**: generalización del pivote-muro a cualquier rival, con daño rival real vía `_op_active_attack_damage_to`.
- **log 86342087 (PERDIDA, vs Mega Lucario)**: origen de `_feza_lucario_wall`, regla correctiva a partir de una derrota.
- **log 86027506 (GANADA, vs Abomasnow)**: origen de `_hydra_fragile_pivot` — enrutar energía al activo frágil para habilitar su retirada.

Los cuatro casos comparten estructura: un remate rival alto y legible donde "atacar si se puede" perdía frente a "proteger el cuerpo bueno y pivotar al muro sano"; por eso viven junto a la detección de matchup, de cuyas banderas dependen.
