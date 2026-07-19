# main.py — Detección de matchup, debilidades e inmunidades (líneas 1477–1985)

## Rol en el agente

Este bloque es el **escáner de tablero rival**: a partir de lo que es visible en el activo y la banca del oponente (más algunos eventos de `obs.logs`), construye un conjunto de banderas booleanas (`op_is_*_deck`, `op_has_*`) que **clasifican el arquetipo enemigo** y detectan **inmunidades, debilidades explotables y amenazas puntuales** (daño estimado al activo, contadores de daño, esquiva, redirección). No decide ninguna jugada por sí mismo — es puramente diagnóstico — pero es la base condicional de la que dependen casi todas las ramas de puntuación que vienen después (escalera de `Boss's Orders`, elección de atacante, `energy_score`, prioridad de bajar Pokémon en el `setup`, etc.). El propio glosario (`docs/main.md`, §2 "Detección de matchup") lo resume así: "Muchas reglas de puntuación se activan **solo** contra ciertos arquetipos".

A diferencia de bloques posteriores que razonan sobre *nuestras* opciones jugables, aquí el agente mira exclusivamente el `op_state` (jugador contrario): su Pokémon activo (`op_state.active[0]`), su banca (`op_state.bench`) y, para un par de casos, el registro de eventos del turno (`obs.logs`). El resultado son variables `bool` locales a la llamada de `agent()` (no `global`, salvo `op_is_crustle_deck`, `op_is_cornerstone_deck` y `op_has_mega_kangaskhan`, declaradas `global` en la línea 1316-1318 y reinicializadas cada turno en este mismo tramo) que el resto de la función consulta cientos de veces.

## Detalle por bloque

### Cierre del tracking de premios rivales (línea 1477–1478)

```python
if context == SelectContext.MAIN:
    _prev_op_prize = op_prize
```

Guarda `op_prize` (premios que le quedan al rival, calculado en el preámbulo) en la variable global `_prev_op_prize` **solo** cuando el contexto es `MAIN`. Es la contraparte de la detección de `ko_last_turn` del preámbulo (líneas 1449-1454: `if op_prize < _prev_op_prize: ko_last_turn = True`): al fijar el valor únicamente en `MAIN` se evita que una decisión intermedia dentro del mismo turno (p.ej. elegir el objetivo de un `Ultra Ball`) pise el valor de referencia antes de que se pueda comparar en la siguiente llamada.

### `_op_best_damage_vs` — daño máximo estimado del activo rival (líneas 1480–1511)

Calcula, para un Pokémon propio dado (`my_pokemon`), el **mayor daño que el activo rival podría infligirle este turno**, asumiendo que aún puede adjuntar una energía más (`assume_attach=True` por defecto → `_avail = len(_opa.energies) + 1`). Recorre `_opd.attacks` (datos de `card_table`) y para cada ataque cuyo coste (`len(_atk.cost)`) quepa en `_avail`, se queda con el `damage` más alto (`_best = max(_best, _dmg)`). Los ataques sin daño numérico (`_dmg is None`, p.ej. ataques de estado o de contador) se descartan aquí — por eso existe la función siguiente.

Al final duplica `_best` si hay **debilidad**: `_myd.weakness == _opd.energyType` (líneas 1508-1510). Es la única comprobación de debilidad explícita de todo este tramo: compara el campo `weakness` de nuestra carta (`card_table`) contra el `energyType` del atacante rival. No hay lógica de **resistencia** (el motor/mazo de este agente no la modela aquí).

Esta función alimenta `estimated_op_damage` (línea 1548) y, por extensión, `active_ko_likely`.

### `_op_counter_threat_vs` — ataques de "contador" no capturados por daño fijo (líneas 1513–1529)

Comentario explícito (1514-1518): hay ataques como *Powerful Hand* de Alakazam ex (20 de daño por carta en la mano rival) cuyo campo `damage` es `None`, así que `_op_best_damage_vs` los ignora por completo y el agente "queda ciego a la amenaza". Esta función los estima a mano: si el activo rival es `Alakazam_ex` (línea 1524), toma el tamaño de mano propio (`_op_hand_size(op_state)`, con fallback conservador de `4` si devuelve `0`, es decir, mano oculta) y devuelve `20 * _h`. Es un caso especial *hardcodeado*, no generalizado a otras cartas de contador — documenta una carencia deliberada del modelo de daño genérico.

No se ve usada su salida (`_op_counter_threat_vs`) en el propio tramo 1477-1985 (se llama más adelante, en el análisis de amenaza/lookahead, fuera de este rango).

### Amenaza sobre el activo propio: `active_ko_likely`, `active_hp_ratio`, `estimated_op_damage`, `_teal_wall_pivot` (líneas 1531–1572)

- `active_hp_ratio = my_active.hp / max(1, my_active.maxHp)` — fracción de vida restante del activo propio.
- `_mega_line_active` — `True` si el activo es `Chikorita`/`Bayleef`/`Meganium` (línea 1540); no se usa más en este tramo, es para lógica posterior de la línea Meganium.
- `estimated_op_damage = _op_best_damage_vs(my_active)` (línea 1548).
- `active_ko_likely` se marca `True` bajo tres condiciones alternativas (1550-1555):
  1. `estimated_op_damage >= my_active.hp` (KO directo estimado).
  2. `my_active.hp <= 60 and op_energy >= 2` (heurística: activo frágil + rival con energía suficiente para un golpe grande no modelado con precisión).
  3. `active_hp_ratio <= 0.3 and op_energy >= 1` (activo muy dañado, cualquier energía rival es peligrosa).
  
  Es una heurística de seguridad que **sobreestima el riesgo** a propósito (condiciones 2 y 3 no calculan daño real) para evitar que el agente se quede pasivo con un activo condenado.
- **Pivote `_teal_wall_pivot`** (1564-1572): si `active_ko_likely` es cierto, el activo es `Teal_Mask_Ogerpon_ex`, **no** llega a 3 energía efectiva este turno (`len(my_active.energies) + _grass_attach_unit() < 3`) pero tenemos una `Basic_Grass_Energy` en mano, y en la banca hay un `Hydrapple_ex` a **vida completa** (`hp >= maxHp`), se activa el flag. Comentario (1557-1563): la jugada correcta es usar *Teal Dance* en el activo condenado (adjunta Grass + roba 1 carta) para habilitar su propio coste de retirada (1) y luego retirarlo hacia el muro de banca (`Hydrapple_ex`, 330 HP), en vez de "regalar" el activo sin sacar nada de él.

### Efectos de ataque especiales detectados en `obs.logs` (líneas 1574–1621)

- **`itchy_pollen_active`** (1574-1578): recorre `obs.logs` buscando un `LogType.ATTACK` con `cardId == Budew` jugado por el rival (`playerIndex != my_index`). Marca que *Itchy Pollen* de Budew se usó este ciclo de logs (Budew es id `235`, línea 179).
- **`op_active_dodge_immune`** / `_dodge_pending_serial` (1580-1609): sigue la secuencia *ataque → tirada de moneda* de *Splashing Dodge* de `Hops_Phantump` (id `878`, ataque `Splashing_Dodge_Atk = 1266`). Si el rival lanza ese ataque, guarda el `serial` del Pokémon activo rival en `_dodge_pending_serial`; si el siguiente log es una tirada de moneda (`COIN_FLIP_LOG_TYPE = 22`) del rival y sale cara (`head=True`) sobre ese mismo activo, marca `op_active_dodge_immune = True` y persiste el estado en las globales `_dodge_immune_serial` / `_dodge_immune_turn` (para que la inmunidad se recuerde durante el resto del turno aunque `obs.logs` ya no contenga el evento original — bloque 1604-1609, que revalida por `serial` que sigue siendo el mismo Pokémon activo).
- **`budew_on_op_field` / `budew_op_index`** (1611-1621): localiza a Budew en el activo o la banca rival (guardando su índice de banca `idx + 1` si aplica) para que reglas posteriores sepan si la amenaza de *Itchy Pollen* sigue en juego (no solo si se usó, sino si el Pokémon sigue en el tablero).

Estas tres banderas son "amenazas de banca/activo" puntuales, no clasificaciones de mazo completo, pero cumplen el mismo papel condicional para las reglas de puntuación de más abajo (evitar quedarse con Pokémon indefensos ante *dodge* o ante daño pasivo de *Itchy Pollen*).

### Inicialización de banderas `op_is_*` / `op_has_*` (líneas 1623–1659)

Bloque de declaraciones a `False` antes de escanear el tablero. Agrupa dos familias:

- **Inmunidades/estructura defensiva**: `op_has_ex_immune_active`, `op_has_ex_immune_bench`, `op_has_ability_immune_active`, `op_has_sturdy_crustle`, `op_has_dwebble_bench`, `op_has_crustle_bench`.
- **Amenazas concretas de carta**: `op_has_froslass`, `op_has_snorunt_bench`, `op_has_munkidori`, `op_has_dragapult`, `op_has_dreepy_line`, `op_has_typhlosion`, `op_has_ethan_preevo`, `op_is_fire_deck`, `op_is_mirror`, `op_bench_snipe_threat`, `op_has_latias_ex`.
- **Clasificación de arquetipo por línea evolutiva/carta clave**: `op_is_greninja_deck`, `op_is_slowking_deck`, `op_is_beedrill_deck`, `op_is_drednaw_deck`, `op_is_sylveon_deck`, `op_has_eevee_bench`, `op_has_non_immune_eevee_ex`, `op_is_dragapult_dusknoir`, `op_is_alakazam_deck`, `op_is_gardevoir_deck`, `op_is_zoroark_deck`, `op_is_aggro_deck`, `op_is_control_deck`, `op_has_mega_starmie_active`, `op_is_lucario_deck`, `op_is_cubchoo_deck`, `op_is_hop_deck`, `op_active_is_dunsparce`.

(`op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan` **no** se reinicializan aquí porque son `global` y ya se pusieron a `False` en el bloque de reinicio de turno de la línea 844-847 / se declaran `global` en 1316-1318; conservan su valor entre sub-decisiones del mismo turno salvo que el escaneo las reafirme.)

### Clasificación por el Pokémon ACTIVO rival (líneas 1660–1732)

Si `op_state.active[0]` existe, se lee `op_active_id` y se comparan contra IDs/conjuntos constantes (definidos en el bloque de constantes, líneas ~160-290):

| Condición (id `op_active_id`) | Bandera activada | Implicación estratégica |
|---|---|---|
| `id in EX_IMMUNE_IDS` = `{Crustle_Grass(345), Sylveon(330)}` | `op_has_ex_immune_active` | El activo rival **no puede ser dañado por ataques que exigen jugar contra un Pokémon `ex` propio**-tipo *muro*; empuja a usar atacantes no-`ex` (`Tapu_Bulu`, `Dipplin`, `Pinsir`). |
| `id in ABILITY_IMMUNE_IDS` = `{Cornerstone_Mask_Ogerpon_ex(117)}` | `op_has_ability_immune_active` | El activo anula Habilidades propias (Wild Growth de Meganium, Last-Ditch Catch de Meowth ex, etc.) mientras esté en juego. |
| `id == Cornerstone_Mask_Ogerpon_ex` | `op_is_cornerstone_deck = True` (global) | Mazo "muro de Habilidad": variante del matchup Crustle/Sylveon pero por bloqueo de Habilidad, no de tipo `ex`. |
| `id == Crustle_Fighting(533)` | `op_has_sturdy_crustle` | Variante Lucha de Crustle (además del Planta, id 345). |
| `id in (Crustle_Grass(345), Crustle_Fighting(533), Dwebble_Grass(344), Dwebble_Fighting(532))` | `op_is_crustle_deck = True` (global) | Mazo "muro de inmunidad ex" completo — dispara la extensa lógica anti-Crustle repartida por todo `main.py` (líneas listadas en "Interacciones"). |
| `id == Mega_Kangaskhan_ex(756)` | `op_has_mega_kangaskhan = True` (global) | Amenaza de golpe alto tipo Mega. |
| `id == Froslass(104)` | `op_has_froslass` | Amenaza específica (usada, p.ej., para no bajar `Fezandipiti_ex` en el setup — línea 8908 aprox.). |
| `id == Munkidori(112)` | `op_has_munkidori` | Habilidad de daño/control psíquica. |
| `id == Dragapult_ex(121)` | `op_has_dragapult = True`, `op_bench_snipe_threat = True` | Mazo con potencial de *snipe* a banca — penaliza bajar Pokémon frágiles en banca. |
| `id == Typhlosion(354)` | `op_has_typhlosion` | Presión de tipo Fuego. |
| `id in (Cyndaquil(352), Quilava(353))` | `op_has_ethan_preevo` | Pre-evolución de la línea Typhlosion, aún sin amenaza directa pero anticipa el arquetipo. |
| `id == Grimmsnarl_ex(648)` | `op_bench_snipe_threat = True` | Otro atacante con alcance a banca. |
| `id == Mega_Starmie_ex(1031)` **y** `len(energies) >= 1` | `op_has_mega_starmie_active = True`, `op_bench_snipe_threat = True` | Solo cuenta si ya tiene energía adjunta (evita falso positivo con un Mega Starmie recién bajado e inerte). |
| `id == Latias_ex(184)` | `op_has_latias_ex` | Bandera de matchup específico (afecta prioridad de `Boss's Orders`, línea 3517/6489). |
| `id in (Riolu(677), Mega_Lucario_ex(678))` | `op_is_lucario_deck` | Dispara los pivotes de "muro Hydrapple" (`_hydra_wall_pivot`, `_feza_lucario_wall`, ver más abajo) porque el remate de Mega Lucario (Mega Brave) es alto y predecible. |
| `id in (Cubchoo(506), Beartic(507))` | `op_is_cubchoo_deck` | Clasificación de arquetipo. |
| `id in (Hops_Phantump(878), Hops_Trevenant(879))` | `op_is_hop_deck` | Mazo con *Splashing Dodge* (ver detección de esquiva arriba). |
| `id in DUNSPARCE_IDS = {65, 305}` | `op_active_is_dunsparce` | Dunsparce activo: según comentario de la línea 280-283, **nunca** se gustea con `Boss's Orders` porque es un muro fácil de reposicionar — no aporta ventaja noquearlo o subirlo. |
| `card_table.get(op_active_id).energyType == EnergyType.FIRE` | `op_is_fire_deck = True` | Clasificación genérica por tipo de energía (no por carta específica): cualquier activo de tipo Fuego marca el matchup, acelerando la carga de `Hydrapple_ex` (ver Interacciones). |
| `id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita)` | `op_is_mirror = True` | **Espejo**: el rival juega (parte de) el mismo mazo Planta/ex. |
| `id == Mega_Greninja_ex(40)` | `op_is_greninja_deck = True`, `op_bench_snipe_threat = True` | Mazo de control/snipe de agua. |
| `id in (Slowpoke(162), Slowking(163))` | `op_is_slowking_deck = True`, `op_is_control_deck = True` | Mazo de control psíquico. |
| `id in (Weedle(-992), Kakuna(-993), Beedrill(-991))` | `op_is_beedrill_deck = True`, `op_is_aggro_deck = True` | **Ver nota de anomalía abajo**: estos tres IDs son negativos. |
| `id in (Chewtle(157), Drednaw(158))` | `op_is_drednaw_deck = True` | Clasificación de arquetipo (además interactúa con `_op_active_is_drednaw` en el análisis de amenaza posterior, penalizando/premiando atacantes concretos por su daño *Syrup Storm* estimado). |
| `id == Sylveon(330)` **o** `id in EEVEE_IDS = {43, 145, 249, 317}` | `op_is_sylveon_deck = True`, `op_is_crustle_deck = True` | La línea Eevee/Sylveon se trata como **variante del matchup "muro-ex"** (Sylveon está en `EX_IMMUNE_IDS`), de ahí que también encienda `op_is_crustle_deck`. |
| `id == Eevee_PRE_ex(249)` | `op_has_non_immune_eevee_ex = True` | Marca que el Eevee visto es el `ex` normal (no inmune), para la corrección de la línea 1815-1817. |
| `id in (Abra(741), Kadabra(742), Alakazam_ex(743))` | `op_is_alakazam_deck = True` | Habilita `_op_counter_threat_vs` (daño por tamaño de mano) y reglas específicas (p.ej. no gustear pre-evos no-`ex`, ver memoria de usuario). |
| `id in (Ralts(745), Kirlia(746), Gardevoir_ex(747))` | `op_is_gardevoir_deck = True` | Clasificación de arquetipo. |
| `id in (Zorua_N(292), Zoroark_N(293))` | `op_is_zoroark_deck = True` | Clasificación de arquetipo. |
| `id in (Raging_Bolt_ex(63), Lugia_VSTAR(337))` | `op_is_aggro_deck = True` | Mazos de golpe alto/rápido clasificados directamente como *aggro*. |

### Clasificación por la BANCA rival (líneas 1733–1809)

Repite exactamente la misma matriz de comparaciones que el bloque anterior pero iterando `enumerate(op_state.bench)`, de modo que un Pokémon de banca (aún no activo) también dispara las banderas correspondientes — la detección de matchup **no espera a que el rival ataque** con la carta reveladora, basta con que estén en juego. Añade tres matices que no están en el bloque de activo:

- `op_has_dwebble_bench` / `op_has_crustle_bench` (1741-1746) distinguen si la pieza de Crustle vista está aún en banca (pre-evolución `Dwebble`) o ya evolucionada, información usada más adelante para decidir prioridad de `Boss's Orders` (gustear al `Dwebble` antes de que evolucione, líneas 3132/3197/3869/3989/4003).
- `op_has_eevee_bench` (1793-1797): si el Pokémon de banca es cualquier Eevee de `EEVEE_IDS`, además de `op_is_sylveon_deck`/`op_is_crustle_deck`.
- `op_is_dragapult_dusknoir` (1800-1801): solo se evalúa desde la banca — si aparece `Duskull`/`Dusclops`/`Dusknoir` (id 131/132/133) en banca, se marca `op_is_dragapult_dusknoir = op_has_dragapult or op_has_dreepy_line`, es decir, requiere que **también** haya evidencia de la línea Dragapult (activo o banca) para confirmar el mazo mixto Dragapult+Dusknoir en vez de un Dusknoir suelto de otro mazo.

**Anomalía detectada — `Beedrill/Weedle/Kakuna` con IDs negativos**: en las constantes (línea 212-214) `Beedrill = -991`, `Weedle = -992`, `Kakuna = -993`. `_validate_id_constants()` (línea 334-348) salta explícitamente la validación para IDs negativos (`if _cid < 0: continue`, línea 337) y estos tres no aparecen en `_ID_NAME_EXPECTATIONS` (líneas 315-332). Como los IDs reales de Pokémon en `op_state` nunca son negativos, las comparaciones `op_active_id in (Weedle, Kakuna, Beedrill)` (línea 1715 y 1788) **nunca pueden ser verdaderas**: `op_is_beedrill_deck` es, tal como está el código, una bandera muerta/placeholder (probablemente a la espera de que se confirmen los IDs reales de esa carta). Todo lo que depende de ella (líneas 5468, 5621, 8719, 8772, 9358, 10606) queda inactivo hasta corregir esas constantes — aunque `op_is_aggro_deck` sigue pudiendo activarse por otras vías (Raging Bolt ex, Lugia VSTAR, ver tabla anterior) por lo que el *matchup* "aggro" en general no está completamente ciego.

### Corrección Eevee ex no inmune (líneas 1811–1817)

```python
if op_has_non_immune_eevee_ex and not (op_has_ex_immune_active or op_has_ex_immune_bench):
    op_is_crustle_deck = False
    op_is_sylveon_deck = False
```

Comentario (1811-1814): `Eevee_PRE_ex` (id 249) es un `ex` normal y atacable, **no** el muro Sylveon. Si el rival solo tiene esa carta de la línea Eevee (sin ningún Pokémon realmente inmune a `ex` en juego, ni activo ni banca), se **revocan** `op_is_crustle_deck` y `op_is_sylveon_deck` — que se habían encendido de forma optimista al ver cualquier `EEVEE_IDS` — y el agente vuelve a la estrategia normal contra `ex` (atacar con los propios `ex`, evolucionar `Dipplin → Hydrapple ex`). Es una corrección de falso positivo aplicada **después** de escanear todo el tablero (activo + banca), para no depender del orden en que se descubren las piezas.

### `total_grass` y pivotes de "muro Hydrapple ex" condicionados a matchup (líneas 1819–1922)

`total_grass = count_total_grass_energy(my_state)` (línea 1819) cuenta la energía Planta total en juego propio — se usa en los cálculos de daño estimado de *Syrup Storm* (`30 + 30 * total_grass`) de los tres pivotes siguientes, todos variantes del mismo patrón "retirar el activo condenado y promover un `Hydrapple_ex` sano de banca":

- **`_hydra_wall_pivot`** (1834-1855, log 85856881, partida GANADA): activo es `Teal_Mask_Ogerpon_ex` con ≥3 energías, el matchup es `op_is_lucario_deck`, `active_ko_likely` es cierto, y el propio *Myriad Leaf Shower* del Ogerpon **no llega a noquear** al activo rival este turno (`_hwp_oger_dmg < _hwp_op_hp`). Si además puede retirarse (energía física ≥ coste) y hay un `Hydrapple_ex` de banca a vida completa que **sobrevive** al mejor golpe rival (`hp > _op_best_damage_vs(...)`) y tiene ≥2 energía efectiva, se activa el pivote: mejor resistir con el muro que atacar con el Ogerpon y morir regalando 2 premios.
- **`_feza_lucario_wall`** (1869-1886, log 86342087, partida PERDIDA — regla correctiva): mismo patrón pero con `Fezandipiti_ex` activo (débil a Lucha, el `Mega Brave` de Mega Lucario ex lo noquea, 270×2=540 vs 2 premios). Si hay un `Hydrapple_ex` de banca sano que resiste, se marca `_feza_lucario_wall` (usado en `energy_score` para priorizar cargarlo) y, si ese Hydrapple **ya** tiene ≥2 energía efectiva, activa directamente `_hydra_wall_pivot` para forzar la retirada ya.
- **`_hydra_fragile_pivot`** (1902-1922, log 86027506, partida GANADA): el activo **ya es** un `Hydrapple_ex` dañado (en riesgo de KO: `active_ko_likely` o ≤50% de vida) que **no** puede retirarse todavía (energía física < coste de retirada, 3). Si hay otro `Hydrapple_ex` en banca con más vida, que sobrevive al golpe rival, con ≥2 energía efectiva, y cuyo `Syrup Storm` (con `total_grass` ya contando la energía en juego) **noquearía** al activo rival (`_hfp_bdmg >= _hfp_opa.hp`), se activa el flag — esto habilita en `energy_score` (fuera de este tramo) enrutar la energía del turno hacia el activo frágil para que alcance el coste de retirada y pueda subir al Hydrapple sano a rematar.

Los tres pivotes son exclusivos de `op_is_lucario_deck` (salvo el tercero, que es agnóstico de matchup pero comparte la mecánica) y ejemplifican cómo las banderas `op_is_*_deck` de este bloque condicionan directamente decisiones de posicionamiento, no solo de ataque.

### Confusión y elección de atacante alternativo condicionada al matchup "muro" (líneas 1924–1971)

- `_conf_ex_immune_match = op_is_crustle_deck or op_is_cornerstone_deck or op_has_ex_immune_active or op_has_ex_immune_bench` (1925-1926): combina las banderas de matchup con la detección directa de inmunidad para un único booleano "estamos en un matchup de muro".
- `_conf_can_attack_pkmn(_p)` (1928-1945): función local que, para cada Pokémon propio, calcula si tiene energía efectiva suficiente para atacar (usa `_grass_mult()` para la duplicación de Meganium) — umbrales por carta: `Hydrapple_ex` ≥2, `Dipplin` ≥1 (energía física, sin duplicar), `Teal_Mask_Ogerpon_ex` ≥3, `Tapu_Bulu` ≥4, `Pinsir` ≥2, `Fezandipiti_ex` ≥3.
- `_conf_is_matchup_attacker(_pid)` (1947-1951): si estamos en matchup de muro (`_conf_ex_immune_match`), solo cuentan como "atacante de matchup" los no-`ex` que sí pueden dañar al muro (`Tapu_Bulu`, `Dipplin`, `Pinsir`); si no, cualquiera de los seis atacantes del mazo.
- `_conf_bench_attacker_ready` / `_conf_bench_attacker_body` (1953-1958): si hay, respectivamente, un atacante de matchup en banca **listo** (con energía) o simplemente presente.
- `_conf_active_can_retreat` (1959-1966): solo si `is_confused`; usa energía efectiva (con nota explícita, 1961-1963, de que Wild Growth de Meganium puede cubrir el coste de retirada con menos cartas físicas).
- `_conf_active_can_attack`, `_conf_should_retreat`, `_conf_should_attack` (1967-1971): combinan lo anterior para, bajo confusión (`is_confused`), decidir si conviene **retirar** el activo confuso hacia un atacante de banca ya listo, o si —a falta de alternativa en banca— conviene **arriesgarse a atacar** confuso porque no hay nada mejor.

Este sub-bloque muestra que la clasificación de matchup (muro `ex`/Habilidad) no solo afecta a qué Pokémon se prioriza atacando en condiciones normales, sino también qué Pokémon **cuenta como atacante válido** a efectos de decidir si vale la pena retirarse estando confuso.

### Cierre: banderas de ataque/cambio inicializadas a `False` (líneas 1973–1985)

`can_attack`, `_active_cant_attack_this_turn`, `_hydra_pivot_active`, `_tapu_sac_pivot`, `_tapu_sac_enable_retreat`, `_prize_denial_pivot`, `_bo_active_attack_sufficient`, `can_switch`, `can_op_switch`, `has_switch_card` se inicializan aquí a `False` como preparación para el siguiente bloque (análisis de amenaza y `AttackPlan`, líneas ~1985-2900, documentado en `main-07-agent-threat-and-plan.md`) — quedan fuera del alcance de detección de matchup propiamente dicho, pero marcan el límite exacto donde termina este tramo (`if context == SelectContext.MAIN:` en la línea 1985 abre el siguiente bloque).

## Interacciones

Las banderas fijadas aquí se leen de forma extensiva en el resto de `agent()`; algunos ejemplos representativos con línea:

- **`op_is_crustle_deck` / `op_is_cornerstone_deck` / `op_has_ex_immune_active` / `op_has_ability_immune_active`**: condicionan la escalera completa de `Boss's Orders` (`main-08-agent-boss-orders.md`, p.ej. líneas 2886, 2924, 3132, 3546, 3781, 3869), la prioridad de atacante (líneas 2090-2163: penalizan `Hydrapple_ex`/`Meganium`/`Fezandipiti_ex`, `ex`, y premian `Tapu_Bulu`/`Dipplin`/`Pinsir`, no-`ex`, cuando hay inmunidad), el `energy_score` (4049-4141), y decenas de puntos en las secciones de `PLAY`/`ATTACH`/`RETREAT` (6134-6318, 7477-7654, 9100-9365, 11121-11653).
- **`op_is_fire_deck` / `op_is_aggro_deck` / `op_is_beedrill_deck`**: aceleran la prioridad de cargar `Hydrapple_ex` hasta el umbral de 2 energía efectiva (+500/+300 en `energy_score`, líneas 5467-5469) y suben la prioridad de bajar `Chikorita`/`Applin` en el `setup` (líneas 6888-6896) — la lógica es "contra mazos rápidos, hay que llegar antes a poder atacar".
- **`op_bench_snipe_threat`** (Dragapult ex, Grimmsnarl ex, Mega Greninja ex, Mega Starmie ex activo con energía): baja la prioridad de bajar Pokémon frágiles en banca durante el `setup` (líneas 6894-6896, 6925) y en `PLAY` (línea 8775) — evitar exponer objetivos fáciles de *snipe*.
- **`op_is_lucario_deck`**: activa los tres pivotes "muro Hydrapple ex" documentados arriba (1834-1922), exclusivos de este matchup por el patrón de daño predecible de Mega Lucario ex (Mega Brave).
- **`op_active_is_dunsparce`**: en combinación con `op_is_alakazam_deck`, ajusta la puntuación de `Boss's Orders` (línea 10616) — coherente con la regla de memoria del usuario "no gustear pre-evo de línea no-`ex`" y "Dunsparce nunca se gustea" (comentario línea 280-283).
- **`op_is_mirror`**: se combina con `op_is_fire_deck`/`op_is_crustle_deck` en varios puntos de `PLAY`/`ATTACH` (líneas 8717, 9365, 11121, 11259) para tratar el espejo Planta/ex como un matchup de carrera de daño puro.
- **`stadium_id`** (definido justo antes de este tramo, línea 1396, pero cuyo efecto es correlativo): `forest_in_play` (Forest of Vitality, id 1261) acelera nuestra energía Planta; `neutralization_zone_active` (id 1247) penaliza jugar `ex` propios (línea 2163-2165: `-3000` a `ex`, `+2000` a no-`ex`) — interactúa directamente con la lógica de elección de atacante de este bloque (1924-1971), reforzando la preferencia por atacantes no-`ex` cuando además hay estadio activo; `watchtower_in_play` (id 1256) anula Habilidades de Pokémon `{C}` propios (Meowth ex) y rivales.

## Reglas derivadas de partidas

- **`log 85856881`, paso 127, vs Mega Lucario ex, GANADA** (líneas 1821-1833): con el Ogerpon activo condenado pero cuyo propio ataque no noquea al rival, retirar hacia un `Hydrapple_ex` sano de banca en vez de atacar y morir — origen de `_hydra_wall_pivot`.
- **`log 86342087`, paso 130, vs Mega Lucario ex, PERDIDA** (líneas 1857-1868): partida perdida por atacar con un `Fezandipiti_ex` condenado en vez de cargar y pivotar al `Hydrapple_ex` de banca — origen de `_feza_lucario_wall`, regla correctiva explícita a partir de una derrota.
- **`log 86027506`, paso 81, vs Abomasnow, GANADA** (líneas 1888-1901): con el `Hydrapple_ex` activo dañado y sin poder retirarse aún, enrutar la energía del turno hacia él para habilitar la retirada y subir al `Hydrapple_ex` sano de banca a rematar — origen de `_hydra_fragile_pivot`.

Los tres casos comparten estructura: un matchup con remate rival alto y predecible (`op_is_lucario_deck`, o daño de *Syrup Storm* propio) donde la heurística general de "atacar si se puede" perdía valor frente a "proteger el cuerpo bueno y pivotar al muro sano" — de ahí que las tres reglas vivan justo en el bloque de detección de matchup, en vez de en el bloque de puntuación de `RETREAT`, ya que dependen de banderas de arquetipo (`op_is_lucario_deck`) fijadas aquí.
