# main.py — Constantes y configuración

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este bloque es la capa de **configuración estática** de todo el agente: no contiene lógica de decisión, pero define el vocabulario sobre el que se construye el resto de `main.py`. Aquí se carga el mazo propio desde `deck.csv`, se indexa la base de datos de cartas del simulador (`card_table`) y la de ataques (`attack_table`), se tabulan los costes de retirada de *todas* las cartas del juego (`RETREAT_COST`) y se nombran con constantes Python legibles (`Teal_Mask_Ogerpon_ex`, `Boss_Orders`, `Alakazam_ex`, …) los IDs numéricos de carta que usa el motor `cg`. Sobre esas constantes se construyen conjuntos (`frozenset`/`set`) que agrupan cartas por **rol estratégico** (nuestros ex, objetivos de banca prioritarios, pre-evoluciones que esconden un ex, etc.), de forma que el resto del archivo puede escribir `if card.cardId in HIGH_PRIORITY_BENCH_TARGETS` en vez de listas de números mágicos repetidas por todo el código.

La segunda mitad del bloque define las **constantes de puntuación con nombre** (`SCORE_*`, `BOSS_SCORE_*`, `XEROSIC_SCORE_*`, `TAPU_WAIT_FOR_ITEMS_SCORE`) que fijan los valores numéricos con los que compiten las opciones en el bucle de `agent()` (documentado en `main-08` a `main-15`). Fijar estos números en un solo sitio, con comentarios que explican su posición relativa (p. ej. "por encima de Lillie's, por debajo de X"), es lo que permite razonar sobre la "escalera" de prioridades sin tener que releer todo el bucle de puntuación.

## Detalle por bloque

### Imports, convenciones y carga de `deck.csv` / `card_table` / `attack_table`

```python
from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, SpecialConditionType, LogType, all_card_data, all_attack, to_observation_class
```

- El bloque de comentario `CONVENCIONES DEL AGENTE` al inicio del archivo (glosado también en `docs/main.md`) es la única "documentación interna" que `main.py` trae de fábrica: energía efectiva (`len(energies)` ya incluye el doblado de Wild Growth), `_grass_mult()`, `_grass_attach_unit()`, `ATTACK_ENERGY_REQ` y `_attacker_base_damage` como fuentes únicas de verdad, y los valores numéricos de `OptionType` (7=PLAY, 12=PASS, 13=ATTACK, 14=END TURN, 3=selección de objetivo).
- `file_path = "deck.csv"`; si no existe en el directorio de trabajo, se reescribe a `"/kaggle_simulations/agent/" + file_path` — ruta fija del entorno de competición de Kaggle donde corre el agente en producción. El CSV se lee entero y se parte por saltos de línea.
- `my_deck` se construye leyendo las primeras 60 líneas del CSV como enteros — es la lista canónica de 60 IDs de carta del mazo propio. Es el valor que `agent()` devuelve directamente cuando `obs.select is None` (entrega inicial del mazo, ver `docs/main.md` §1).
- `all_card = all_card_data()` llama a la API del simulador (`cg.api`) para obtener los datos de *todas* las cartas del juego (no solo las del mazo propio), necesarios para razonar sobre cartas del rival. `card_table = {c.cardId: c for c in all_card}` es el diccionario `id → Card`, la **fuente única** consultada en todo el archivo vía `get_card(...)`/`card_table.get(id)` para obtener nombre, tipo, HP, ataques, debilidad, etc.
- `attack_table = {a.attackId: a for a in all_attack()}`: tabla `attack_id → objeto Attack` (name/damage/energies). Existe porque los `card.attacks` de `card_table` son **IDs enteros, no objetos** — un `getattr(id, 'damage')` siempre da 0 —, así que esta tabla es la única forma de resolver el daño impreso real de un ataque rival. La consume `_op_active_attack_damage_to` (ver `main-02`).

### `RETREAT_COST`

Diccionario `card_id → coste de retirada en energías` que cubre prácticamente **todo el pool de cartas del juego** (cientos de entradas), no solo las del mazo propio ni las del rival conocido. Es una tabla de datos estática copiada del catálogo de cartas, necesaria porque la observación (`Pokemon`) no siempre expone el coste de retirada de forma directa y las decisiones de `RETREAT` (ver `main-14`) necesitan saber cuánta energía cuesta retirar cualquier Pokémon que pueda aparecer en el tablero (propio o rival). Al ser una tabla plana sin lógica, no requiere explicación entrada a entrada; lo relevante es que **cualquier carta nueva del meta** debe tener aquí su entrada o el cálculo de retirada fallará silenciosamente (probablemente tratándose como coste desconocido).

### Constantes de ID de carta — nuestro mazo

```python
Teal_Mask_Ogerpon_ex = 96
Chikorita = 917
Bayleef = 709
Meganium = 710
Applin = 92
Dipplin = 93
Hydrapple_ex = 150
Meowth_ex = 1071
Fezandipiti_ex = 140
Tapu_Bulu = 920

Pinsir = 25

Lillie_Determination = 1227
Boss_Orders = 1182
Lanas_Aid = 1184
Xerosic_Machinations = 1197

Dawn = 1231
Bug_Catching_Set = 1094
Ultra_Ball = 1121
Night_Stretcher = 1097
Unfair_Stamp = 1080
Poke_Pad = 1152
Forest_of_Vitality = 1261
Neutralization_Zone = 1247
Team_Rockets_Watchtower = 1256
Maximum_Belt = 1158
Basic_Grass_Energy = 1

Budew = 235
```

Nombran, con IDs reales del motor, cada pieza del arquetipo propio descrito en `docs/main.md` §2 ("Nuestro mazo"): las tres líneas de ataque (`Chikorita`→`Bayleef`→`Meganium`; `Applin`→`Dipplin`→`Hydrapple_ex`; `Teal_Mask_Ogerpon_ex` como básico independiente), los atacantes auxiliares (`Tapu_Bulu`, `Fezandipiti_ex`, `Meowth_ex`), los Supporters del mazo (`Lillie_Determination`, `Boss_Orders`, `Lanas_Aid`, `Dawn` y `Xerosic_Machinations` — este último incorporado al mazo a costa de una Poké Pad, principalmente para el matchup Alakazam, ver `_score_xerosic_play` en `main-04`), los Items (`Bug_Catching_Set`, `Ultra_Ball`, `Night_Stretcher`, `Unfair_Stamp`, `Poke_Pad`), el estadio propio (`Forest_of_Vitality`), dos estadios de interferencia rivales (`Neutralization_Zone`, `Team_Rockets_Watchtower`) y la energía básica (`Basic_Grass_Energy = 1`).

`Pinsir` conserva su constante y su lógica asociada (respuesta anti-Crustle/Cornerstone), pero **ya no está en el `deck.csv` actual**: su código es latente y solo se activaría si la carta volviera al mazo.

`Maximum_Belt` (Ace Spec) es una **tool rival**: suma +50 de daño cuando el atacante rival que la lleva golpea a un Pokémon ex nuestro (antes de debilidad). Está modelada en `_op_best_damage_vs` y `_op_active_attack_damage_to` (ver `main-02`) — antes de la auditoría de julio 2026 las tools rivales eran invisibles y los pivotes defensivos creían que un muro sobrevivía a un golpe potenciado.

`Budew` (235) es un Pokémon rival pequeño pero crítico para las reglas de apertura (su ataque *Itchy Pollen* bloquea nuestros Items), y se define aquí junto al resto de nombres tempranos.

### Constantes de ID de carta — amenazas y matchups rivales

Bloque extenso que nombra los Pokémon (y un par de valores de log especiales) que definen los **arquetipos rivales** que el agente sabe detectar y contrarrestar (ver `op_is_*_deck` en `main-06`):

- `Crustle_Grass`/`Crustle_Fighting` + sus pre-evos `Dwebble_Grass`/`Dwebble_Fighting`, y `Sylveon`: mazos con inmunidad a ex (ver `EX_IMMUNE_IDS` más abajo).
- `Comfey`/`Bramblin`/`Brambleghast`: mazo de mill/control Comfey — Comfey es su único atacante (*Flower Shower* nos hace robar 3 y nos deckea) y Brambleghast confunde a nuestro activo con *Prison Panic*. Cualquiera de los tres dispara la detección `op_is_comfey_deck` (estrategia completa en la memoria "Estrategia vs Comfey").
- `Dragapult_ex` con su línea `Dreepy`→`Drakloak`; `Grimmsnarl_ex` con `Marnies_Impidimp`→`Marnies_Morgrem`; `Latias_ex`; `Cornerstone_Mask_Ogerpon_ex` (inmune a habilidades, ver `ABILITY_IMMUNE_IDS`); `Mega_Kangaskhan_ex`; `Iron_Thorns_ex`; `Charizard_ex`.
- `Hops_Phantump`→`Hops_Trevenant` (mazo "Hop", con `Splashing_Dodge_Atk` como ataque de esquiva y `COIN_FLIP_LOG_TYPE` como tipo de evento de log para detectar el volado asociado).
- `Mega_Greninja_ex`, `Mega_Starmie_ex` (mazos de esquiva/snipe con agua); `Slowking`/`Slowpoke` (control psíquico).
- Línea `Beedrill`/`Weedle`/`Kakuna` con IDs **negativos** (`-991`, `-992`, `-993`): convención para IDs sintéticos sin entrada real en `card_table` (la auditoría de IDs los salta explícitamente).
- `Zoroark_N`/`Zorua_N`, y la línea `Abra`→`Kadabra`→`Alakazam_ex`. Pese al nombre, `Alakazam_ex` (743) es **no-ex** en este entorno (ver `NONEX_FINAL_PREEVO_IDS`). Junto a la línea se define `POWERFUL_HAND_ATTACK_ID = 1072`: el único ataque de Alakazam, *Powerful Hand*, tiene daño impreso 0 en `attack_table` pero daño real de **20 × carta en la mano rival**; la constante permite a `_op_active_attack_damage_to` reconocerlo y proyectar su daño real (ver `main-02`).
- Línea `Buneary`→`Mega_Lopunny_ex`: Buneary es el básico atacante peligroso; Mega Lopunny ex es Stage 1 y vale 2 premios.
- Línea Cynthia: `Cynthias_Gible`→`Cynthias_Gabite`→`Cynthias_Garchomp_ex` (Stage 2, ex de 2 premios). El mazo acompaña con muros de 1 premio (Cynthia's Spiritomb, Roselia); las dos pre-evos están en `EX_PREEVO_IDS` para el deny-evo de Boss's (ver abajo).
- `Gardevoir_ex`/`Ralts`/`Kirlia`, `Raging_Bolt_ex`, `Lugia_VSTAR`; líneas `Dusknoir` (`Duskull`→`Dusclops`→`Dusknoir`), `Typhlosion` (`Cyndaquil`→`Quilava`→`Typhlosion`, ver `FIRE_POKEMON_IDS`), `Drednaw` (`Chewtle`→`Drednaw`); `Cubchoo`/`Beartic`.
- `Eevee_TWM`/`Eevee_SFA`/`Eevee_PRE_ex`/`Eevee_SSP` agrupados en `EEVEE_IDS` — cuatro imprentas distintas de Eevee tratadas como equivalentes a efectos de reconocimiento de amenaza.
- Línea Rocket's Mewtwo (analizada de limitless /decks/337 en julio 2026): `Rockets_Tarountula` (motor de daño barato del mazo, 50 HP) → `Rockets_Spidops` (Stage 1, línea 4-4), y `Rockets_Mewtwo_ex` (280 HP, *Erasure Ball* 160 de daño impreso — se proyecta con la lectura normal de `attack_table`) como finisher de 2 premios, cubierto por el gusteo genérico de 2 premios de Boss's. Cortar los Tarountula con Boss's frena su tempo igual que Riolu/Duraludon, por eso `Rockets_Tarountula` está en `THREAT_PREEVO_IDS`.

### Conjuntos de IDs por rol estratégico

Cada conjunto agrupa IDs ya nombrados arriba para que el resto del agente pueda preguntar pertenencia (`in`) en vez de comparar IDs sueltos.

#### `OUR_EX_IDS`
```python
OUR_EX_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meowth_ex, Fezandipiti_ex}
```
Los cuatro Pokémon **ex propios** (2 premios si son noqueados). Se usa para razonar sobre riesgo propio: perder cualquiera de estos regala 2 premios al rival, así que la lógica de retirada/protección (`main-14`) y de planificación de ataque (`main-07`) los trata con más cautela que a `Tapu_Bulu` (no-ex). También es la condición del bono de `Maximum_Belt` y de las inmunidades anti-ex.

#### `DECK_ITEM_IDS`
```python
DECK_ITEM_IDS = frozenset({Bug_Catching_Set, Ultra_Ball, Night_Stretcher,
                           Poke_Pad, Unfair_Stamp})
```
Los cinco Items del mazo propio. El comentario explica el motivo: se usa para **posponer** la bajada de `Tapu_Bulu` hasta haber jugado antes los Items que valgan la pena (ver `TAPU_WAIT_FOR_ITEMS_SCORE` más abajo) — Tapu Bulu ocupa banca/turno y no aporta nada por sí mismo, así que conviene agotar primero la mano de Items útiles.

#### `EX_IMMUNE_IDS`
```python
EX_IMMUNE_IDS = {Crustle_Grass, Crustle_Fighting, Sylveon}
```
Pokémon rivales con la regla de "inmunidad a ataques de Pokémon ex". **Ambas variantes de Crustle** comparten la habilidad anti-ex: la Fighting (533) activaba `op_is_crustle_deck` pero faltaba en este conjunto, así que el cálculo de daño puntual creía que nuestros ex sí la dañaban — corregido en la auditoría de julio 2026. Se usa para saber cuándo nuestros atacantes ex (`Ogerpon ex`, `Hydrapple ex`, etc.) **no pueden dañarlos** y hay que rodear el bloqueo con un atacante no-ex o con Boss's Orders hacia otro objetivo (ver la memoria "Ogerpon energy cap vs Crustle" y las reglas anti-Crustle en `main-09`).

#### `CRUSTLE_LINE_IDS` y `_op_juega_crustle(op_state)`
```python
CRUSTLE_LINE_IDS = {Crustle_Grass, Crustle_Fighting,
                    Dwebble_Grass, Dwebble_Fighting}
```
La **línea** Crustle, pre-evo incluida, con su predicado de tablero `_op_juega_crustle(op_state)` (¿hay alguna en el activo o la banca rival?). Existe porque `op_is_crustle_deck` **no** significa "el rival juega Crustle" sino "el rival tiene un muro inmune a ex": también se enciende con `Sylveon` y con `EEVEE_IDS`. Para las decisiones que dependen de la **inmunidad** (a quién puede dañar nuestro ex, cuándo rodear el muro) el flag es lo correcto; para las que dependen de cómo está **construido** el mazo Crustle —señaladamente `t1_segundos_crustle_estadio_antes_de_lillie` (docs 04 y 15), que baja el estadio en nuestro primer turno porque ese mazo apenas juega estadio— hay que mirar esta lista, no el flag.

#### `ABILITY_IMMUNE_IDS`
```python
ABILITY_IMMUNE_IDS = {Cornerstone_Mask_Ogerpon_ex}
```
Pokémon rival cuya Habilidad bloquea el daño de Pokémon con Habilidad del jugador contrario (Cornerstone Mask Ogerpon ex). Permite desactivar en el cálculo de puntuación las jugadas que dependen de nuestros Pokémon con Habilidad (`OUR_ABILITY_IDS`) cuando este Pokémon está en juego.

#### `OUR_ABILITY_IDS`
```python
OUR_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meganium, Fezandipiti_ex, Meowth_ex, Dipplin}
```
Los seis Pokémon propios que tienen Habilidad relevante para el agente (incluye `Dipplin`, pre-evo de Hydrapple, que también tiene Habilidad propia). Se cruza con `ABILITY_IMMUNE_IDS` para saber si esas Habilidades siguen activas.

#### `NON_ATTACKER_ENERGY_WASTE_IDS`
```python
NON_ATTACKER_ENERGY_WASTE_IDS = {Meowth_ex, Fezandipiti_ex}
```
Pokémon propios que normalmente **no** se usan como atacantes activos (su rol es de soporte/Habilidad), así que adjuntarles energía suele ser desperdicio. Se usa en la puntuación de `ATTACH` (`main-13`) para penalizar cargar energía en ellos salvo excepción justificada.

#### `HIGH_PRIORITY_BENCH_TARGETS`
```python
HIGH_PRIORITY_BENCH_TARGETS = {Budew, Munkidori, Froslass, Snorunt, Dreepy, Drakloak, Dwebble_Grass, Dwebble_Fighting}
```
Pokémon rivales de banca que conviene noquear en cuanto se pueda (habilitadores de combo, pre-evos baratas de amenazas fuertes, o piezas de control) — se usa en la escalera de `Boss's Orders` (`main-08`) y en la elección de objetivo de ataque para dar prioridad a sacarlos de la banca antes de que evolucionen o activen su efecto.

#### `META_BENCH_TARGETS`
Lista más amplia que `HIGH_PRIORITY_BENCH_TARGETS`: engloba las **líneas de evolución completas** de amenazas del meta conocido (líneas Slowking, Beedrill, Zoroark, Alakazam, Gardevoir, Dusknoir, Typhlosion, Drednaw, Sylveon, y los cuatro Eevee sueltos por ID en vez de vía `EEVEE_IDS`). Se usa como referencia general de "esto es una pieza de un mazo rival relevante" en la valoración de objetivos, más laxa que la lista de alta prioridad.

#### `FIRE_POKEMON_IDS`, `WATER_SNIPE_IDS`, `PSYCHIC_CONTROL_IDS`
```python
FIRE_POKEMON_IDS = {Charizard_ex, Typhlosion, Cyndaquil, Quilava}
WATER_SNIPE_IDS = {Mega_Greninja_ex, 47}
PSYCHIC_CONTROL_IDS = {Slowking, Alakazam_ex, Gardevoir_ex}
```
Tres agrupaciones por **tipo de amenaza táctica** más que por tipo elemental literal: `FIRE_POKEMON_IDS` marca la línea Typhlosion + Charizard ex; `WATER_SNIPE_IDS` marca atacantes de agua con capacidad de "snipe" (daño dirigido a la banca; incluye el ID suelto `47` sin constante nombrada); `PSYCHIC_CONTROL_IDS` marca Pokémon psíquicos con efectos de control de mano/tablero. Se usan en reglas de matchup específicas para anticipar qué puede hacer el rival (daño a banca, bloqueo, etc.).

#### `THREAT_PREEVO_IDS`
```python
Riolu = 677
Mega_Lucario_ex = 678
Duraludon = 169

THREAT_PREEVO_IDS = {Riolu, Duraludon, Hops_Phantump, Dwebble_Grass, Dwebble_Fighting,
                     Buneary, Rockets_Tarountula}
```
Pre-evoluciones básicas cuya evolución final es una amenaza que conviene cortar de raíz (p. ej. `Riolu` → `Mega_Lucario_ex`, `Buneary` → `Mega_Lopunny_ex`, `Duraludon` → Archaludon ex, `Rockets_Tarountula` → `Rockets_Spidops`). Es un conjunto más general que `EX_PREEVO_IDS` (no exige que la evolución final sea ex, solo que sea una amenaza a vigilar).

#### `DUNSPARCE_IDS`
```python
DUNSPARCE_IDS = {65, 305}
```
Dos imprentas distintas de Dunsparce (sets TEF y JTG), identificadas directamente por ID porque no tienen constante nombrada. El comentario documenta un **requisito explícito del usuario**: nunca usar Boss's Orders para subir a Dunsparce al activo rival, porque es un muro barato de retirar que no representa presión real — gustearlo desperdicia el Supporter. Coincide con la memoria "Boss's: gustear Buneary vs Mega Lopunny ex", que prioriza objetivos que sí son atacantes reales.

#### `KEY_BENCH_ATTACKER_IDS`
```python
KEY_BENCH_ATTACKER_IDS = {Hops_Trevenant, Hops_Phantump}
```
El comentario explica el caso de uso: Pokémon clave de un mazo rival que conviene noquear en banca **aunque** el propio activo pueda noquear al activo rival, siempre que ese activo rival no sea él mismo una pieza clave (p. ej. un muro sin energía). El ejemplo es el mazo "Hop": su atacante clave es `Hops_Trevenant`, y su línea (`Trevenant`/`Phantump`) debe cazarse en banca antes que perder el turno pegándole a un muro. La prioridad fina entre variantes la resuelve `_boss_tier` en la selección de objetivo `TO_ACTIVE` (ver `main-08`): Trevenant con energía > Trevenant sin energía > Phantump con energía > Phantump sin energía.

#### `EX_PREEVO_IDS`
```python
EX_PREEVO_IDS = {
    Dreepy, Drakloak,
    Riolu,
    Duraludon,
    Zorua_N,
    Abra, Kadabra,
    Ralts, Kirlia,
    Marnies_Impidimp, Marnies_Morgrem,
    Buneary,
    Cynthias_Gible, Cynthias_Gabite,
}
```
Pre-evoluciones (básicos y Stage 1 intermedios) cuya línea evolutiva termina en un Pokémon **ex de 2 premios** (`Dragapult ex`, `Mega Lucario ex`, Archaludon ex, línea Zoroark, `Gardevoir ex`, `Grimmsnarl ex`, `Mega Lopunny ex`, `Cynthias_Garchomp_ex` — con la salvedad de `NONEX_FINAL_PREEVO_IDS` para la línea Abra). Justifica una regla táctica concreta: **gustear con Boss's Orders una pre-evolución** de esta lista para noquearla en banca "corta" una línea que, de completarse, se convertiría en un atacante de 2 premios — aceptar noquear algo de 1 premio ahora a cambio de negar un ex de 2 premios después es una inversión rentable (ver ladder de Boss's Orders en `main-08`).

La incorporación de `Cynthias_Gible`/`Cynthias_Gabite` corrige un fallo real (registro_006 vs Garchomp, partida ganada con error): la línea **no estaba** en este conjunto, así que el deny-evo de Boss's (`_bo_pe_is_ex_preevo_energized` / `_bo_pe_is_ex_line_vs_wall`) jamás disparaba — con Tapu Bulu listo, Boss's en mano y un Gabite **energizado** en la banca rival, el agente noqueaba al muro Spiritomb en vez de gustear+noquear el Gabite. El comentario del código deja explícito: privilegiar siempre cortar la línea evolutiva de Cynthia's Garchomp ex.

#### `NONEX_FINAL_PREEVO_IDS`
```python
NONEX_FINAL_PREEVO_IDS = {Abra, Kadabra}
```
Contrapartida directa de `EX_PREEVO_IDS`: aunque `Abra`/`Kadabra` están incluidos allí (porque su evolución final usa la constante `Alakazam_ex = 743`), el comentario aclara que ese nombre es **engañoso** — el dato real de la carta en `card_table` marca `ex=False`, es decir, Alakazam (743) es un Pokémon de **1 premio** en este entorno. Por tanto la regla de "gustear pre-evo para negar un ex de 2 premios" no debe dispararse para esta línea: noquear a `Abra`/`Kadabra` en banca rinde el mismo premio (1) que noquear al activo, así que gustearlos con Boss's Orders sería un desperdicio del Supporter. Coincide con la memoria "Boss's: no gustear pre-evo de línea no-ex". Nótese que el matchup Alakazam tiene además reglas propias posteriores (`boss_deny_alakazam_line`, motor Xerosic) que sí gustean la línea cuando el activo rival es un muro fuera de ella.

### `_ID_NAME_EXPECTATIONS` y `_validate_id_constants`

`_ID_NAME_EXPECTATIONS` es un diccionario `id → substring de nombre esperado` (p. ej. `Teal_Mask_Ogerpon_ex: "Ogerpon"`, `Kadabra: "Kadabra"`) para las constantes más sensibles del archivo. `_validate_id_constants()` es una **auto-comprobación de cordura** que se ejecuta al importar el módulo: para cada ID esperado, busca la carta real en `card_table` y verifica que el substring esperado aparezca en `card.name` (comparación case-insensitive); los IDs negativos (sintéticos, como `Beedrill = -991`) se saltan porque no tienen entrada real. Si hay discrepancias, las imprime por `stderr` con prefijo `[WARN][ID-AUDIT]` en vez de lanzar una excepción — es un chequeo de auditoría, no un `assert` bloqueante, así que un fallo de esta validación **no impide** que el agente juegue con IDs potencialmente mal mapeados; solo deja rastro en logs. La llamada está envuelta en un `try/except` genérico (`_ID_AUDIT_MISMATCHES = _validate_id_constants()`, o `[]` si algo falla) para que un error inesperado en la propia validación tampoco tumbe la carga del módulo.

Este mecanismo es la defensa contra el problema que describe el propio comentario de `NONEX_FINAL_PREEVO_IDS`: los datos de las cartas pueden cambiar entre versiones del catálogo, y una constante con un nombre que ya no corresponde al ID real (como pasó conceptualmente con `Alakazam_ex`) podría pasar desapercibida sin esta auditoría.

### Constantes de puntuación `SCORE_*`

```python
SCORE_WIN_GAME = 50000

SCORE_DEVELOP_BASE = 20000
SCORE_ITEM_BASE = 10000
SCORE_SUPPORTER_VALUE_BASE = 2400
```

- `SCORE_WIN_GAME`: el valor más alto del archivo, reservado para la opción que gana la partida inmediatamente (ver `docs/main.md` §1: valores "redondos" altos son prioridades fuertes que sobrescriben el puntaje base).
- **Anclas base de la rama PLAY**: `SCORE_DEVELOP_BASE` (bajar un Pokémon a la banca) y `SCORE_ITEM_BASE` (jugar una carta no-Pokémon). El resto de scores de desarrollo se leen como "base ± matiz". `SCORE_SUPPORTER_VALUE_BASE` es la base del valor genérico de un Supporter: los scorers de Boss's/Lana's/Dawn devuelven `BASE + int(valor * 1.4) + supporter_boost` cuando no aplica ninguna rama especial.

#### Pisos de puntuación con nombre (score floors)

```python
SCORE_VETO = -1
SCORE_CANCEL = -100
SCORE_USELESS_ATTACK = -5000
SCORE_NEVER = -10000
SCORE_FORBID = -100000
```

Escala de valores negativos **con nombre** que deja explícito el orden de "no jugar" (migración incremental de números mágicos a constantes; renombrado puro, sin cambio de comportamiento):
- `SCORE_VETO` (-1): jugada vetada/inútil — el piso general, el más común.
- `SCORE_CANCEL` (-100): cancelar **por debajo** del piso de veto (p. ej. una Ultra Ball inútil con banca llena), para que el desempate por índice del argmax no la elija cuando todo lo demás también está a -1 — se prefiere atacar/pasar antes que malgastar la carta.
- `SCORE_USELESS_ATTACK` (-5000): atacar por 0 daño (rival inmune por ex/habilidad/muro).
- `SCORE_NEVER` (-10000): nunca (p. ej. no descartar Unfair Stamp; END no letal).
- `SCORE_FORBID` (-100000): prohibido absoluto (gustear Dunsparce, retirada gratis prohibida, bajar Meowth con el Supporter ya jugado).

#### Lookahead y creencia

```python
SCORE_LOOKAHEAD_EX_TRADE = 250
SCORE_LOOKAHEAD_KO_TRADE = 120
SCORE_LOOKAHEAD_SAFE = 60
SCORE_LOOKAHEAD_PROMOTE_KO = 120
SCORE_LOOKAHEAD_PROMOTE_SAFE = 40

SCORE_BELIEF_DIG_ENERGY = 250
```

- Familia `SCORE_LOOKAHEAD_*`: puntajes usados por el análisis de "lo que pasará el próximo turno" (ver `main-07`) al evaluar líneas de juego que dejan planteado un intercambio. El orden relativo (250 > 120 > 60 > 40) codifica la preferencia: intercambio contra ex > KO simple > jugada segura.
- `SCORE_BELIEF_DIG_ENERGY`: bono para acciones de búsqueda orientadas a encontrar energía cuando la creencia del mazo (ver `main-03`) indica hambruna de energía con robo pobre (`energy_starved_low_draw`); lo consume p. ej. el scorer de Bug Catching Set.

### `BOSS_PRIORITY_CRUSTLE_GUST` y `TAPU_WAIT_FOR_ITEMS_SCORE`

```python
BOSS_PRIORITY_CRUSTLE_GUST = 990
```
Caso Crustle — cuando el activo ex propio está bloqueado por `EX_IMMUNE_IDS` pero hay un objetivo alcanzable en banca rival que sí puede noquearse o dejarse sin retirada, este valor debe superar tanto a los "cebos de robo" (Lillie's, puntuación de valor ~650) como al resto del ladder de Boss's. Es la codificación numérica directa de las memorias "Crustle: retirar Chikorita activo" / "Ogerpon energy cap vs Crustle".

```python
TAPU_WAIT_FOR_ITEMS_SCORE = 8900
```
Puntaje al que se **rebaja** la jugada de `Tapu_Bulu` mientras aún queden Items útiles en mano: queda por debajo de la banda de Items útiles (~9800+, o 9000 cuando un Item se "autolimita") pero por encima de Items que no valen la pena. Efecto neto: mientras haya Items buenos por jugar, ganan ellos; en cuanto se agotan, Tapu Bulu vuelve a subir de prioridad y se juega. Aplica **solo** a Tapu Bulu.

### Ladder `BOSS_SCORE_*` y escalera `XEROSIC_SCORE_*`

```python
BOSS_SCORE_WIN_NOW = 20000
BOSS_SCORE_GUST_2PRIZE = 6800
BOSS_SCORE_WIN_VIA_BENCH = 5600
BOSS_SCORE_WALL_GUST = 5500
BOSS_SCORE_DODGE_REDIRECT = 5500
BOSS_SCORE_PRIZE_RANK_BASE = 5200
BOSS_SCORE_LOW_VALUE_GUST = 1500
BOSS_SCORE_DEFENSIVE_GUST = 1500
BOSS_SCORE_EMPTY_GUST = 20
```

Escalera consumida por `_score_boss_orders_play` (ver `main-04` y `main-08`). Cada rama representa un tipo de remate que puede lograrse gusteando, y a **todas menos `BOSS_SCORE_EMPTY_GUST`** se les suma después `supporter_boost`. El punto de referencia es Lillie's Determination con puntaje base 5000: las ramas por encima le ganan a "simplemente refrescar mano"; las de abajo le ceden la prioridad. En orden descendente:
1. `BOSS_SCORE_WIN_NOW` (20000): gusteo que **gana la partida** con el activo (toma los premios que faltan noqueando al objetivo gusteado). Prioridad máxima: debe superar cualquier retirada/pivote defensivo (~6500-6600) — antes este remate se puntuaba como `WIN_VIA_BENCH` (5600) y perdía contra el pivote de retirada de Hydrapple ex, por lo que el agente retiraba en vez de rematar (memoria "Boss's gusteo ganador supera la retirada").
2. `BOSS_SCORE_GUST_2PRIZE` (6800): el activo ya noquea al activo rival de 1 premio, pero un **ex de banca** (p. ej. Rocket's Mewtwo ex) también es noqueable tras gustearlo y vale 2 premios — se gustea el ex. Supera retiradas/pivotes (~6600) y el ataque directo al activo (memoria "Boss's: gustear ex de 2 premios sobre atacar el activo"; flag `gust_2prize_via_boss`).
3. `BOSS_SCORE_WIN_VIA_BENCH` (5600): gustada letal a un objetivo de banca que decide la partida.
4. `BOSS_SCORE_WALL_GUST` / `BOSS_SCORE_DODGE_REDIRECT` (5500, empatados): forzar la salida del activo rival cuando es un muro inmune (`EX_IMMUNE_IDS`/`ABILITY_IMMUNE_IDS`) o cuando el rival esquiva (dodge) y hay que redirigir el ataque.
5. `BOSS_SCORE_PRIZE_RANK_BASE` (5200): gusteo que habilita un KO, afinado por `boss_prize_rank` (el scorer suma `(8 - prize_rank) * 20`); también lo usa la rama `boss_deny_alakazam_line`.
6. `BOSS_SCORE_LOW_VALUE_GUST` / `BOSS_SCORE_DEFENSIVE_GUST` (1500): gusteos que no ganan a Lillie's — de bajo valor ofensivo o puramente defensivos (vs Crustle sin remate).
7. `BOSS_SCORE_EMPTY_GUST` (20): Boss's técnicamente jugable pero el gusteo no es ejecutable como remate (activo que no puede atacar, primer turno con Lillie's en mano, gusteo de desarrollo sin atacante real de banca) — casi siempre pierde frente a cualquier otra jugada.

```python
XEROSIC_SCORE_ALAKAZAM = 5900
XEROSIC_SCORE_GENERIC = 3380
XEROSIC_SCORE_LAST_RESORT = 20
```

Escalera de `_score_xerosic_play` (ver `main-04`):
- `XEROSIC_SCORE_ALAKAZAM` (5900): capar *Powerful Hand* (20 × mano rival) vs Alakazam. Queda **sobre** Lillie's hydra-cargado (5800) y **bajo** `GUST_2PRIZE` (6800) y los pivotes defensivos (~6600); cede al gusteo letal de banca (`boss_win_via_bench`) por un guard propio dentro del scorer. El scorer suma además `min(300, 50 × (mano_rival − 4))`, con lo que el valor efectivo escala 6000-6200 con mano ≥6 (y queda en 5900 con el disparo temprano de mano 4-5).
- `XEROSIC_SCORE_GENERIC` (3380): Xerosic genérico con mano rival muy grande (≥7): valor de disrupción real, pero por debajo de una Lillie's típica (~3450).
- `XEROSIC_SCORE_LAST_RESORT` (20): sin efecto útil claro — solo se juega si ningún otro supporter puntúa.

## Interacciones

- `docs/main.md` §2 ("Nuestro mazo", "Detección de matchup") es la referencia previa obligatoria: este documento asume ya conocidos `OptionType`, `SelectContext`, energía efectiva y `CARTAS_ACTIVAS_EN_MAZO`.
- Las banderas `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_is_alakazam_deck`, `op_is_comfey_deck`, etc. (calculadas en `agent()`, ver `main-06`; desde julio 2026 también se infieren del **descarte rival**, que revela el arquetipo 2-3 turnos antes que el tablero) se calculan comparando cartas visibles del rival contra los IDs/conjuntos de este bloque (`EX_IMMUNE_IDS`, `ABILITY_IMMUNE_IDS`, `KEY_BENCH_ATTACKER_IDS`, `DUNSPARCE_IDS`, líneas Comfey/Alakazam/…).
- `HIGH_PRIORITY_BENCH_TARGETS`, `META_BENCH_TARGETS`, `EX_PREEVO_IDS`, `NONEX_FINAL_PREEVO_IDS`, `THREAT_PREEVO_IDS` y `KEY_BENCH_ATTACKER_IDS` alimentan directamente `_boss_tier`, el deny-evo y la escalera `BOSS_SCORE_*` en la rama `PLAY` de Boss's Orders (`main-08`).
- `RETREAT_COST` es consumido por la puntuación de `RETREAT` (`main-14`) y por el análisis de amenaza/plan de ataque (`main-07`) al estimar si el rival puede retirar a un objetivo antes de ser noqueado.
- `DECK_ITEM_IDS` y `TAPU_WAIT_FOR_ITEMS_SCORE` se usan juntos en la puntuación de `PLAY` de `Tapu_Bulu` (`main-12`).
- `card_table` es la fuente que consulta `get_card()` en todo el archivo (`main-04`); `attack_table` la consultan `_op_active_attack_damage_to` (`main-02`) y el handler de Cruel Arrow.
- Los pisos `SCORE_VETO`/`SCORE_CANCEL`/`SCORE_FORBID` y las escaleras `BOSS_SCORE_*`/`XEROSIC_SCORE_*` son el vocabulario de los scorers extraídos `_score_*_play` (`main-04`).

## Reglas derivadas de partidas

Varias constantes de este bloque codifican directamente reglas aprendidas de partidas concretas:
- `DUNSPARCE_IDS`: "user req" explícito de no gustear nunca Dunsparce, documentado literalmente en el comentario del código.
- `NONEX_FINAL_PREEVO_IDS`: corrige un error de nomenclatura (`Alakazam_ex` no es ex) que había llevado a gustear inútilmente la línea Abra/Kadabra.
- `EX_PREEVO_IDS` (adición de la línea Cynthia): registro_006 vs Garchomp — el deny-evo no disparaba y el agente atacaba al muro en vez de gustear el Gabite energizado.
- `EX_IMMUNE_IDS` (adición de `Crustle_Fighting`) y `Maximum_Belt`: auditoría estratégica de julio 2026.
- `BOSS_SCORE_WIN_NOW` y `BOSS_SCORE_GUST_2PRIZE`: registros 019 (vs Dragapult) y 008 (vs Rocket's Mewtwo) respectivamente, citados en los comentarios de `_score_boss_orders_play`.
- `BOSS_PRIORITY_CRUSTLE_GUST`: alineado con las memorias "Ogerpon energy cap vs Crustle" y "Crustle: retirar Chikorita activo".
