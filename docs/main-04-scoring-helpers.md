# main.py — Utilidades de puntuación (líneas 687–1291)

## Rol en el agente

Este bloque agrupa las funciones auxiliares que el resto de `agent()` invoca repetidamente para **convertir un `Pokemon`/opción en un número comparable** o para **resolver una opción abstracta a la carta real** que representa. No contienen lógica de turno ni acceden a `select.option` directamente (salvo `_debug_log_decision`, que es pura utilidad de diagnóstico): son funciones puras que reciben datos ya extraídos (contadores, banderas, el `state`) y devuelven un entero o una tupla de enteros.

La pieza central del bloque es `_eval_ub_best_target` (972–1291), la función más larga: calcula, para cada posible objetivo de búsqueda de `Ultra Ball` (o de cualquier búsqueda equivalente en mazo), una puntuación de prioridad. El resto de funciones (`get_card`, `prize_count`, `count_total_grass_energy`, `calc_syrup_storm_damage`, `pokemon_score`, `_count_hand_play_options`) son utilidades más pequeñas que alimentan tanto a `_eval_ub_best_target` como a otras partes de `agent()` (valoración de Boss's Orders, cálculo de daño de Hydrapple ex, elección de objetivo de retiro, etc.).

## Detalle por bloque

### `_debug_log_decision` (687–711)

Imprime por `stderr` el ranking de las opciones evaluadas, pero **solo si `DEBUG_DECISIONS` es verdadero** (línea 688: `if not DEBUG_DECISIONS: return` — variable global activada por la variable de entorno `PTCG_DEBUG`, según el punto 5 de `docs/main.md`).

- **Entradas**: `context` (el `SelectContext` de la decisión), `select` (con `select.option`), `scores` (lista paralela de puntuaciones ya calculadas por el bucle principal), `obs`, `my_index`, y `top_n=3` (cuántas opciones del ranking mostrar).
- **Cálculo**: ordena los índices `range(len(scores))` por `scores[i]` descendente (línea 692: `sorted(..., key=lambda i: scores[i], reverse=True)`), imprime la cabecera con el nombre del contexto y el número de opciones, y luego, para cada una de las `top_n` mejores, imprime `#rango idx=i score=scores[i] etiqueta`.
- **Etiquetado de cada opción** (696–706): intenta resolver la carta real de la opción con `get_card(obs, _opt.area, _opt.index, my_index)`. Si existe, usa `card_table.get(_card.id)` y su atributo `.name`; si no hay carta (p.ej. una opción `YES`/`NO`), cae en `area=...` como etiqueta. Todo el bloque está envuelto en `try/except Exception: pass` (línea 705 y 709–710) para que un fallo de depuración nunca rompa la decisión real del agente.
- **Razón estratégica**: es la herramienta principal para **depurar por qué el agente eligió una opción concreta** (ver sección 5 de `docs/main.md`): muestra el top-3 con su puntaje y nombre de carta, sin necesidad de instrumentar manualmente el bucle de puntuación.

### `get_card` (861–885)

Resuelve una opción `(area, index)` a la carta u objeto `Pokemon`/`Card` real que representa, dentro de la observación del jugador `player_index`.

- **Entradas**: `obs` (Observation), `area` (`AreaType`), `index` (posición dentro de esa zona), `player_index`.
- **Salida**: el objeto `Pokemon | Card | None`.
- **Mecanismo** (864–882): un `match area` que mapea cada valor de `AreaType` a la colección correspondiente del jugador `ps = obs.current.players[player_index]` o del estado global:
  - `DECK` → `obs.select.deck[index]` (cartas visibles del mazo, p.ej. al buscar con Ultra Ball).
  - `HAND` → `ps.hand[index]`.
  - `DISCARD` → `ps.discard[index]`.
  - `ACTIVE` → `ps.active[index]`.
  - `BENCH` → `ps.bench[index]`.
  - `PRIZE` → `ps.prize[index]`.
  - `STADIUM` → `obs.current.stadium[index]`.
  - `LOOKING` → `obs.current.looking[index]` (cartas que el efecto en curso está "mirando", p.ej. resultado de un vistazo al mazo).
  - Cualquier otro valor → `None`.
- **Manejo de errores** (883–884): si el índice está fuera de rango o el atributo no existe (`IndexError, AttributeError, TypeError`), devuelve `None` en lugar de propagar la excepción.
- **Por qué es clave**: las opciones que recibe el agente (`select.option`) son abstractas — solo indican `type`, `area` e `index` —, así que **toda** la lógica de puntuación que necesita saber "¿qué carta es esta opción de `PLAY`/`EVOLVE`/`ATTACH`?" pasa primero por `get_card`. Es la bisagra entre el formato crudo del motor y el razonamiento por nombre/ID de carta que usa el resto de `main.py`.

### `prize_count` (886–896)

Calcula cuántos premios se lleva el rival si este Pokémon es noqueado.

- **Base** (888): `data = card_table[pokemon.id]`; `count = 3` si `data.megaEx`, `2` si `data.ex`, `1` en cualquier otro caso (Pokémon normal).
- **Ajuste por Legacy Energy** (889–891): si alguna de las `pokemon.energyCards` tiene `id == 12` (**Legacy Energy**, energía ACE SPEC), `count -= 1`. Esto refleja el efecto real de la carta ("si el Pokémon al que está adjunta es noqueado por daño de un ataque rival, ese jugador se lleva 1 premio menos"); la función no modela la restricción de "una vez por partida" de la carta real, solo su presencia.
- **Ajuste por Lillie's Pearl** (892–894): si alguna herramienta (`pokemon.tools`) tiene `id == 1172` (**Lillie's Pearl**) y el nombre de la carta contiene `"Lillie"`, `count -= 1` (mismo efecto de reducción de premio, pero restringido a la línea Lillie's, como en la carta real).
- **Salida**: `max(0, count)` — nunca negativo.
- **Uso**: es el ingrediente principal de `pokemon_score` (línea 916: `score = prize_count(pokemon) * 1000`) y de cualquier heurística que deba razonar en términos de "premios en juego" (p.ej. la escalera de Boss's Orders, que prioriza noquear objetivos de más premios).

### `count_total_grass_energy` (897–906)

Suma las energías de tipo `EnergyType.GRASS` adjuntas a **todos** los Pokémon en juego propios (activo + banca), recorriendo `my_state.active + my_state.bench` (899) y, para cada Pokémon no nulo, sus `pokemon.energies` (902–904).

- **Entrada**: `my_state` (el estado del jugador, con `.active` y `.bench`).
- **Salida**: entero, total de energías Planta en el campo.
- **Uso**: alimenta directamente `calc_syrup_storm_damage`.

### `calc_syrup_storm_damage` (907–913)

Calcula el daño del ataque *Syrup Storm* (de Hydrapple ex) en función de la energía Planta total en el campo.

- **Fórmula** (912): `30 + 30 * total_grass`, donde `total_grass = count_total_grass_energy(my_state)`.
- **Parámetro `has_meganium`** (909–911): existe pero el cuerpo del `if has_meganium: pass` está vacío — es decir, **actualmente no aplica ningún ajuste especial** cuando Meganium está en juego; el multiplicador de energía Planta ya se refleja en la propia cuenta física porque, según el glosario de `docs/main.md`, la observación ya duplica las energías Planta físicas cuando hay Meganium (la "energía efectiva" mencionada en la sección 2). El parámetro parece dejado como gancho para una futura distinción, pero hoy es un no-op.
- **Uso**: sirve para estimar de antemano el daño de Hydrapple ex al planear ataques/KOs (usado en el análisis de amenaza y en el `AttackPlan`).

### `pokemon_score` (914–945)

Puntúa "cuánto vale" un Pokémon propio en juego, usado para decidir, por ejemplo, a qué objetivo retirar/proteger o qué Pokémon de banca es más valioso.

- **Componente de premios** (916): `prize_count(pokemon) * 1000` — domina la puntuación; un Pokémon `ex` (2 premios) vale 1000 puntos más que un básico, uno Mega `ex` (3 premios) 2000 más.
- **Energías y herramientas** (917–918): `+150` por cada energía adjunta, `+100` por cada herramienta adjunta — refleja el "coste hundido" invertido en ese Pokémon.
- **Etapa evolutiva** (919–922): `+250` si es Stage 2 (`data.stage2`), `+130` si es Stage 1 (`data.stage1`) — un Pokémon más evolucionado es más caro de reponer.
- **Penalizaciones por ID específico** (926–927): `pid in (144, 322, 323, 337)` → `-200`. Son IDs concretos (no resueltos por nombre en este fragmento) que el agente considera de bajo valor pese a lo anterior — probablemente pre-evoluciones o Pokémon de soporte que no interesa proteger a toda costa.
- **Bonus por ID 112 con energía** (928–929): si `pid == 112` y tiene al menos 1 energía adjunta, `+300` — otro caso especial afinado a mano (probablemente una carta cuyo valor sube mucho en cuanto empieza a acumular energía, p.ej. un acelerador).
- **Bonus por atacantes clave** (931–942): tabla de bonos fijos por identidad de carta:
  - `Meganium` → `+350`
  - `Gardevoir_ex` → `+400`
  - `Typhlosion` → `+350`
  - `Slowking` → `+400`
  - `Dusknoir` → `+350`
  - `Alakazam_ex` → `+300`

  Estos bonos identifican piezas motoras del propio mazo o amenazas rivales que se manejan con esta misma función (nombres que no pertenecen al mazo Planta descrito en `docs/main.md`, como `Gardevoir_ex`, `Typhlosion`, `Slowking`, `Dusknoir`, `Alakazam_ex`, sugieren que `pokemon_score` también se usa para valorar Pokémon **rivales**, p.ej. al decidir el mejor objetivo de Boss's Orders).
- **HP** (943): `score += pokemon.hp` — suma directa de la vida restante como desempate fino.
- **Salida**: entero total, usado como criterio de comparación relativa entre Pokémon (no es una puntuación de opción del bucle principal).

### `_count_hand_play_options` (946–971)

Cuenta cuántas "jugadas" distintas ofrece la mano actual, usado como proxy de la calidad/flexibilidad de la mano (p.ej. para decidir si conviene refrescarla con Lillie's Determination o Meowth ex).

- **Entradas**: `hand_counts` (conteo de cartas en mano por ID), `field_counts` (conteo de Pokémon en juego por ID), `bench_count`, `energy_attached` (si ya se adjuntó energía este turno).
- **Salida**: tupla `(play_options, supporters_in_hand)`.
- **Evoluciones disponibles** (949–956): `+2` por cada evolución jugable detectada — Meganium en mano + Bayleef en juego; Bayleef en mano + Chikorita en juego; Hydrapple ex en mano + Dipplin en juego; Dipplin en mano + Applin en juego. El peso `+2` (frente a otros `+1`) refleja que evolucionar es una jugada de alto valor.
- **Supporters** (958–961): `supporters_in_hand` = suma de `Lillie_Determination + Boss_Orders + Dawn + Lanas_Aid` en mano; se añade entero a `play_options` (cada supporter cuenta como 1 opción de jugada) y se devuelve también por separado.
- **Energía básica** (963–964): `+1` si hay `Basic_Grass_Energy` en mano y **no** se ha adjuntado energía aún este turno.
- **Básicos de banca** (966–969): si `bench_count < 5` (banca no llena), `+1` por cada uno de `Chikorita`, `Applin`, `Teal_Mask_Ogerpon_ex` presente en mano (posibilidad de bajar un básico nuevo a banca).
- **Uso**: da una medida rápida de "cuántas cosas útiles puedo hacer con esta mano", empleada en las banderas de decisión sobre si conviene barajar/refrescar la mano (p.ej. `hand_is_weak`, mencionado como parámetro en `_eval_ub_best_target`).

### `_eval_ub_best_target` (972–1291)

Función central de este bloque: dado el estado del tablero/mano/mazo propio, calcula la **prioridad de cada posible objetivo de búsqueda** (qué carta conviene traer con Ultra Ball u otro efecto de búsqueda equivalente) y devuelve el valor del **mejor** objetivo encontrado (`ub_best_target`, inicializado a `0` en la línea 980 y actualizado con `max()` en cada rama). Un valor de `0` significa "no hay ningún objetivo que merezca la pena buscar ahora". El llamador compara este valor contra el coste/beneficio de jugar la Ultra Ball en ese momento.

**Firma y preparación (972–984)**

Parámetros: contadores de campo (`field_counts`) y mano (`hand_counts`); banderas de estado del propio mazo (`meganium_in_play`, `has_hydrapple`, `forest_in_play`, `has_energy_for_teal`); banderas del rival (`op_has_ex_immune_active`, `op_has_ex_immune_bench`, `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_active_is_budew`); `op_prize`, `bench_count`, `state`, `ko_last_turn`; valores precomputados de la mejor carta de soporte disponible en mazo/mano (`_best_supp_in_mazo_val`, `_best_supp_in_hand_val`); `supporters_in_hand`, `hand_is_weak`; `_we_go_first`; `watchtower_in_play`.

- `_bench_full = (bench_count >= 5)` (982): banca llena, no se puede bajar más básicos.
- `_hand_total = sum(hand_counts.values())` (984): tamaño total de la mano, usado más adelante para calcular cuántas cartas "sobran" para descartar de forma segura tras evolucionar en cadena.

**Turno 2 sin salida (986–1012): búsqueda de Meowth ex temprano**

Cuando es el turno 2 propio y el rival salió primero (`state.turn == 2 and not _we_go_first`):
- Si aún no se jugó supporter, no hay `Lillie's Determination` en mano, hay menos de 2 `Meowth_ex` en campo, banca no llena, no hay `watchtower_in_play`, y queda al menos un `Meowth_ex` en el mazo (988–993): se prioriza buscar Meowth ex para bajarlo y disparar su Habilidad *Last-Ditch Catch* (busca un Supporter). El valor depende de qué haya en el mazo: `1100` si queda una `Lillie's Determination` en mazo (994–996), o `950` si en su lugar quedan `Dawn`/`Lana's Aid` (997–999).
- Si la banca está vacía (`bench_count == 0`, línea 1001) y no hay ningún básico jugable en mano (`Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir`) pero el activo es un básico débil (`Applin`/`Chikorita`, 1006–1007), se prioriza buscar `Teal_Mask_Ogerpon_ex` con valor `1050` (1008–1010) — es la única pieza capaz de aportar banca de forma inmediata y sólida.
- **Retorna inmediatamente** en la línea 1012 (`return ub_best_target`): en este turno concreto no se evalúan las demás ramas (evoluciones, Tapu Bulu, etc.), solo estas dos prioridades tempranas.

**Turno 1 con salida (1014–1067): reglas de apertura**

Cuando es el turno 1 propio y salimos primero (`state.turn == 1 and _we_go_first`):
- **Regla anti-Budew** (1014–1031): si el activo rival es Budew (`op_active_is_budew`), no tenemos `Lillie's Determination` ni `Meowth_ex` (ni en mano ni en campo), banca no llena, no se jugó supporter, no hay `watchtower_in_play`, y quedan copias de `Meowth_ex` y `Lillie's Determination` en el mazo: se **retorna directamente `1100`** (máxima prioridad, ignorando el resto de la función). La razón (comentada en 1015–1021): el ataque *Itchy Pollen* de Budew bloqueará los Items en nuestro próximo turno, así que hay que adelantarse **ahora** usando la Ultra Ball para traer Meowth ex, bajarlo y que su Habilidad busque una Lillie's Determination (un Supporter, jugable incluso bajo el bloqueo de Items) para el turno siguiente.
- **Corte si ya hay desarrollo** (1033–1037): si hay algo en banca o ya hay un básico jugable en mano (`Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex, Pinsir`), se **retorna `0`** — en el primer turno propio no tiene sentido gastar Ultra Ball si ya hay con qué desarrollar banca.
- **Prioridad entre básicos** (1039–1066), si no se cortó antes: evalúa buscar el mejor básico disponible en mazo cuando el campo aún no lo tiene:
  - `Teal_Mask_Ogerpon_ex` (1041–1046): `950` base, `1000` si además hay `Basic_Grass_Energy` en mano (para poder adjuntarle energía el mismo turno).
  - `Chikorita` (1048–1055): `850` base; sube a `900` si ya hay `Applin` o `Teal_Mask_Ogerpon_ex` en campo (mejor curva de desarrollo); `+50` extra si hay `Bayleef` en mano (evolución inmediata al turno siguiente).
  - `Applin` (1057–1064): `800` base; sube a `850` si ya hay `Chikorita` o `Teal_Mask_Ogerpon_ex` en campo; `+50` si hay `Dipplin` en mano.
  - Se toma el máximo de las tres (`_best_t1_val`) y se retorna.

**Cálculo de "Meowth viable" (1069–1106): búsqueda de Meowth ex a mitad/final de partida**

- `_stamp_blocks_supp_chain` (1069): si hubo KO el turno anterior y tenemos `Unfair_Stamp` en mano, se asume que se preferirá jugar Unfair Stamp en vez de encadenar supporters vía Meowth (bandera que desactiva la búsqueda de Meowth más abajo).
- `_supp_in_hand_is_inferior` (1071–1075): si ya hay un supporter en mano pero el mejor supporter disponible en mazo (`_best_supp_in_mazo_val`) supera en más de 100 puntos al mejor supporter en mano (`_best_supp_in_hand_val`), se considera que el supporter en mano es peor y **sí** merece la pena buscar otro vía Meowth.
- `meowth_viable` (1077–1087): condición compuesta — no bloqueado por Unfair Stamp; no es el turno 1 yendo primero (ya cubierto arriba); no se jugó supporter este turno; no hay `watchtower_in_play`; **no hay supporter en mano O el que hay es inferior**; no hay ya un Meowth ex en campo; banca no llena; queda copia de Meowth ex en mazo; y el mejor supporter en mazo vale más de `200`.
- **Excepción vs Crustle** (1089–1099): si `meowth_viable` es falso pero el rival es un mazo Crustle (`op_is_crustle_deck`), se reactiva si además hay `Boss's Orders` en mazo con valor ≥900, no se jugó supporter, banca no llena, no hay Meowth ex en campo ni Boss's Orders ya en mano — es decir, contra Crustle se relaja la condición de "sin supporter en mano" para poder ir a buscar específicamente un Boss's Orders de alto valor vía Meowth.
- **Valor final de Meowth** (1100–1106): si `meowth_viable`, `meowth_val = _best_supp_in_mazo_val`, con bonus `+200` si `state.turn <= 2` (cuanto antes se dispare el motor de cartas, mejor) o `+100` si `hand_is_weak` (mano pobre que urge refrescar). Se actualiza `ub_best_target`.

**Teal Mask Ogerpon ex — refuerzo de atacante (1108–1131)**

- Con energía disponible para pagar su coste (`has_energy_for_teal`), menos de 2 copias en campo y banca no llena (1108): si queda copia en mazo, valor `650` (o `750` si aún no hay ninguna Ogerpon en campo), `+100` si hay ≥2 `Basic_Grass_Energy` en mano (1109–1115).
- Caso especial de **doble ataque** (1117–1131): si ya hay ≥2 `Teal_Mask_Ogerpon_ex` en campo, banca no llena y hay `Hydrapple_ex` en campo (necesita el hueco de banca compartido con la línea Hydrapple), se calcula un valor basado en el daño extra de *Teal Dance*: `_td_dmg_bonus = 60 si meganium_in_play else 30`; `val = 500 + _td_dmg_bonus * 2` (estima el valor de poder rotar/golpear con dos Ogerpon), `+150` si hay ≥2 energías Planta en mano, `+50` extra si ya hay ≥2 en campo.

**Cadena de evolución Meganium (1133–1192)**

`_evolvable` (1133) decide qué "foto" del campo usar para saber si algo es evolucionable este turno: si no hay `forest_in_play` y `_field_at_turn_start` tiene datos, usa el campo **al inicio del turno** (`_field_at_turn_start`); si no, usa `field_counts` (campo actual). La razón: sin Forest of Vitality, una pre-evolución bajada o evolucionada este mismo turno no puede volver a evolucionar hasta el turno siguiente, así que hay que razonar sobre lo que había *al empezar* el turno para no sobreestimar objetivos inutilizables.

Si `not meganium_in_play` (1135):
- `Bayleef` ya evolucionable en campo (1136–1138): si queda `Meganium` en mazo, prioridad `1000` (evolución inmediata, máxima prioridad estructural).
- Si no, pero hay `Chikorita` evolucionable y `Bayleef` ya en campo (1139–1153): si queda `Meganium` en mazo, `1000` si hay Forest (se puede evolucionar Chikorita→Bayleef→Meganium en la misma cadena), pero solo `280` si **no** hay Forest — porque el Bayleef fue evolucionado este mismo turno y no podrá volver a evolucionar hasta el turno próximo, así que buscar Meganium ahora es pura preparación sin efecto inmediato (comentario 1146–1152).
- Si solo hay `Chikorita` evolucionable (1154–1192):
  - Si queda `Bayleef` en mazo y **no** hay ya uno en mano (1156–1162): `850` (basta un Bayleef para evolucionar la única Chikorita; si ya hay uno en mano, buscar otro no aporta).
  - Si no, y queda `Meganium` en mazo, hay Forest disponible (en juego o en mano) y hay `Bayleef` en mano (1164–1171): calcula `_prot` (cartas a "proteger" del descarte de Ultra Ball: 1, +1 más si no hay Forest en juego todavía) y solo prioriza `900` si sobran ≥2 cartas de mano tras restar la propia Ultra Ball y `_prot` — para no arriesgarse a un descarte forzado excesivo.
  - Si el campo no tiene ninguna pieza de la línea (`Chikorita`+`Bayleef` == 0) y banca no llena (1173–1192): evalúa si conviene empezar la línea desde cero, distinguiendo si se puede encadenar directo a Meganium (`_can_chain_mega`, requiere Forest disponible y Bayleef en mano, con la misma protección de descartes) → `700`; si no se puede encadenar pero ya hay piezas de evolución en mazo o mano → `500`; si no hay nada de la línea aún → `200` (arrancar la línea desde el básico, prioridad baja).

**Cadena de evolución Hydrapple ex (1194–1254)**

Estructura simétrica a la de Meganium, aplicada a `Applin → Dipplin → Hydrapple_ex`, condicionada a `not has_hydrapple`:
- `Dipplin` evolucionable en campo (1195–1197): `950` si queda `Hydrapple_ex` en mazo.
- `Applin` evolucionable + `Dipplin` ya en campo (1198–1211): `950` con Forest, o solo `280` sin Forest (mismo razonamiento de "evolucionado este turno, no reutilizable hasta el siguiente").
- Solo `Applin` evolucionable (1212–1254):
  - Si queda `Dipplin` en mazo y no hay ya uno en mano (1214–1218): `800`.
  - Si no, y queda `Hydrapple_ex` en mazo con Forest disponible y `Dipplin` en mano (1220–1227): `850` si sobran ≥2 cartas tras proteger.
  - Si no hay ninguna pieza en campo y banca no llena (1228–1254): calcula `_can_chain_hydra` (Forest disponible + Dipplin en mano, con protección extra si además hay `Hydrapple_ex` en mano) → `950` si el propio Hydrapple ex ya está en mano (cadena completa de un tirón), o `600` si falta ese último eslabón; si no se puede encadenar, `450` con piezas disponibles en mazo/mano o `180` si no hay nada.

**Objetivos secundarios (1256–1288)**

- **Teal Mask Ogerpon ex sin energía disponible** (1256–1259): si no hay energía para pagarlo (`not has_energy_for_teal`), banca no llena, menos de 2 copias en campo, aún no hay ninguna en campo y la banca tiene ≤2 Pokémon: prioridad baja `350` (bajarlo igualmente para tenerlo listo, aunque no se pueda atacar ya).
- **Tapu Bulu contra inmunes a ex** (1261–1267): si no hay Tapu Bulu en campo, banca no llena, y el rival tiene un activo o banca inmune a ataques de Pokémon `ex` (`op_has_ex_immune_active/bench`) mientras Meganium está en juego (para poder pagar su coste de energía alto): valor `750`, o `850` si ya hay Hydrapple ex en juego (para no depender de un único atacante bloqueado).
- **Pinsir contra Crustle/Cornerstone** (1269–1275): si no hay Pinsir en campo, banca no llena, y el rival es `op_is_crustle_deck` o `op_is_cornerstone_deck`: `900`, o `950` con Meganium en juego — Pinsir es aparentemente la respuesta específica a esos arquetipos.
- **Meowth ex de refuerzo, prioridad baja** (1277–1283): condición residual — banca no llena, sin bloqueo de Unfair Stamp, mano no débil (`not hand_is_weak`, para no solaparse con la rama de arriba), sin supporter jugado ni en mano, sin Meowth ex en campo, mejor supporter en mazo ≥500: si `state.turn <= 4`, prioridad `min(_best_supp_in_mazo_val, 500)` (capada en 500 para no competir con las ramas de evolución/Ogerpon que valen más).
- **Fezandipiti ex tras KO** (1285–1288): si no hay Fezandipiti ex en campo, banca no llena y `ko_last_turn` es verdadero: prioridad muy alta `1050` — aprovechar el hueco de premio/tempo recién generado con la Habilidad de Fezandipiti (probablemente para robar/afectar al rival mientras está en desventaja de premios).

**Retorno final (1290)**: `return ub_best_target`, el máximo acumulado por todas las ramas que no retornaron antes (las ramas de los turnos 1 y 2 especiales sí retornan de forma temprana, líneas 1012, 1031 y 1067).

## Interacciones

- `get_card` es usada por `_debug_log_decision` (línea 699) y, según el índice de `docs/main.md` (secciones 1 y 3), por todo el bucle de puntuación de `agent()` para traducir cada `select.option[i]` a la carta/Pokémon real antes de decidir su puntaje.
- `prize_count` es el bloque base de `pokemon_score` (línea 916) y, según el glosario de `docs/main.md`, de la escalera de valoración de `Boss's Orders` (líneas ~2900–3590), que necesita saber cuántos premios vale cada objetivo posible.
- `count_total_grass_energy` solo se usa dentro de `calc_syrup_storm_damage`.
- `pokemon_score` y `_count_hand_play_options` alimentan banderas de decisión más adelante en `agent()` (p.ej. `hand_is_weak`, mencionado como parámetro de `_eval_ub_best_target`, y comparaciones de qué Pokémon proteger/retirar en la puntuación de `RETREAT`).
- `_eval_ub_best_target` es invocada desde el bloque de puntuación de búsqueda de cartas (`Ultra Ball` y similares, rango 5970–8684 según `docs/main.md`) para fijar el puntaje de cada carta candidata a ser buscada en el mazo; sus banderas de entrada (`meganium_in_play`, `forest_in_play`, `op_is_crustle_deck`, `_best_supp_in_mazo_val`, `hand_is_weak`, etc.) se calculan en los bloques anteriores de `agent()` (detección de matchup, líneas 1477–1985; valoración de Supporters, líneas 3590–4489).
- La regla "Meowth ex → Lillie's Determination" aparece dos veces con matices distintos: como prioridad temprana en el turno 2 sin salida (988–999, valor 1100/950) y como caso especial máximo contra Budew activo en el turno 1 con salida (1014–1031, retorno directo 1100); además como mecanismo general de mitad de partida vía `meowth_viable` (1069–1106). Esto coincide con la nota de memoria del usuario "Ultra Ball: buscar Meowth para Lillie's" y "Jugar Meowth para refrescar mano débil".
