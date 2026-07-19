# main.py — Constantes y configuración (líneas 1–389)

## Rol en el agente

Este bloque es la capa de **configuración estática** de todo el agente: no contiene lógica de decisión, pero define el vocabulario sobre el que se construye el resto de `main.py`. Aquí se carga el mazo propio desde `deck.csv`, se indexa la base de datos de cartas del simulador (`card_table`), se tabulan los costes de retirada de *todas* las cartas del juego (`RETREAT_COST`) y se nombran con constantes Python legibles (`Teal_Mask_Ogerpon_ex`, `Boss_Orders`, `Alakazam_ex`, …) los IDs numéricos de carta que usa el motor `cg`. Sobre esas constantes se construyen conjuntos (`frozenset`/`set`) que agrupan cartas por **rol estratégico** (nuestros ex, objetivos de banca prioritarios, pre-evoluciones que esconden un ex, etc.), de forma que el resto del archivo puede escribir `if card.cardId in HIGH_PRIORITY_BENCH_TARGETS` en vez de listas de números mágicos repetidas por todo el código.

La segunda mitad del bloque define las **constantes de puntuación** (`SCORE_*`, `BOSS_*`) que fijan los valores numéricos con los que compiten las opciones en el bucle de `agent()` (documentado en `main-08` a `main-15`). Fijar estos números en un solo sitio, con comentarios que explican su posición relativa (p. ej. "por encima de Lillie's, por debajo de X"), es lo que permite razonar sobre la "escalera" de prioridades sin tener que releer todo el bucle de puntuación.

## Detalle por bloque

### Imports y carga de `deck.csv` / `card_table` (líneas 1–43)

```python
from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, SpecialConditionType, LogType, all_card_data, to_observation_class
```

- Líneas 9–30: bloque de comentario `CONVENCIONES DEL AGENTE`, glosado ya en `docs/main.md` (energía efectiva, `_grass_mult()`, `ATTACK_ENERGY_REQ`, `_attacker_base_damage`, valores de `OptionType`). Es la única "documentación interna" que el propio `main.py` trae de fábrica; el resto de `docs/main-*.md` la amplía.
- Líneas 33–37: `file_path = "deck.csv"`; si no existe en el directorio de trabajo, se reescribe a `"/kaggle_simulations/agent/" + file_path` — ruta fija del entorno de competición de Kaggle donde corre el agente en producción. El CSV se lee entero y se parte por saltos de línea (`csv = file.read().split("\n")`).
- Líneas 38–40: `my_deck` se construye leyendo las primeras 60 líneas del CSV como enteros (`int(csv[i])`) — es la lista canónica de 60 IDs de carta del mazo propio. Es el valor que `agent()` devuelve directamente cuando `obs.select is None` (entrega inicial del mazo, ver `docs/main.md` §1).
- Línea 42: `all_card = all_card_data()` — llama a la API del simulador (`cg.api`) para obtener los datos de *todas* las cartas del juego (no solo las del mazo propio), necesarios para razonar sobre cartas del rival.
- Línea 43: `card_table = {c.cardId: c for c in all_card}` — diccionario `id → Card` que es la **fuente única** consultada en todo el archivo vía `get_card(id)` (ver `main-04`) para obtener nombre, tipo, HP, ataques, debilidad, etc. de cualquier carta por su ID.

### `RETREAT_COST` (líneas 45–149)

```python
RETREAT_COST = {
    21:1, 22:3, 23:4, 24:2, 25:2, 26:1, 27:1, 28:1, 29:1, 30:3,
    ...
```

Diccionario `card_id → coste de retirada en energías` que cubre prácticamente **todo el pool de cartas del juego** (cientos de entradas, IDs 21 a 1076), no solo las del mazo propio ni las del rival conocido. Es una tabla de datos estática copiada del catálogo de cartas, necesaria porque la observación (`Pokemon`) no siempre expone el coste de retirada de forma directa y las decisiones de `RETREAT` (ver `main-14`) necesitan saber cuánta energía cuesta retirar cualquier Pokémon que pueda aparecer en el tablero (propio o rival). Al ser una tabla plana sin lógica, no requiere explicación línea a línea; lo relevante es que **cualquier carta nueva del meta** debe tener aquí su entrada o el cálculo de retirada fallará silenciosamente (probablemente tratándose como coste desconocido).

### Constantes de ID de carta — nuestro mazo (líneas 151–177)

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

Dawn = 1231
Bug_Catching_Set = 1094
Ultra_Ball = 1121
Night_Stretcher = 1097
Unfair_Stamp = 1080
Poke_Pad = 1152
Forest_of_Vitality = 1261
Neutralization_Zone = 1247
Team_Rockets_Watchtower = 1256
Basic_Grass_Energy = 1

Budew = 235
```

Nombran, con IDs reales del motor, cada pieza del arquetipo propio descrito en `docs/main.md` §2 ("Nuestro mazo"): las tres líneas de ataque (`Chikorita`→`Bayleef`→`Meganium`; `Applin`→`Dipplin`→`Hydrapple_ex`; `Teal_Mask_Ogerpon_ex` como básico independiente), los atacantes auxiliares (`Tapu_Bulu`, `Fezandipiti_ex`, `Pinsir`, `Meowth_ex`), los cuatro Supporters (`Lillie_Determination`, `Boss_Orders`, `Lanas_Aid`, `Dawn`), los Items (`Bug_Catching_Set`, `Ultra_Ball`, `Night_Stretcher`, `Unfair_Stamp`, `Poke_Pad`), el estadio propio (`Forest_of_Vitality`) y dos estadios/cartas de interferencia (`Neutralization_Zone`, `Team_Rockets_Watchtower`) y la energía básica (`Basic_Grass_Energy = 1`). `Budew` (235) es un Pokémon rival pequeño pero se define aquí junto al resto de nombres tempranos.

### Constantes de ID de carta — amenazas y matchups rivales (líneas 179–243)

```python
Crustle_Grass = 345
Dwebble_Grass = 344
Crustle_Fighting = 533
Dwebble_Fighting = 532
Sylveon = 330

Munkidori = 112
...
Buneary = 848
Mega_Lopunny_ex = 849
Gardevoir_ex = 747
...
EEVEE_IDS = {43, 145, 249, 317}
```

Bloque extenso que nombra los Pokémon (y una carta de log especial) que definen los **arquetipos rivales** que el agente sabe detectar y contrarrestar (ver `op_is_*_deck` en `main-06`):
- `Crustle_Grass`/`Crustle_Fighting` + sus pre-evos `Dwebble_Grass`/`Dwebble_Fighting`, y `Sylveon`: mazos con inmunidad a ex (ver `EX_IMMUNE_IDS` más abajo).
- `Dragapult_ex` con su línea `Dreepy`→`Drakloak`; `Grimmsnarl_ex` con `Marnies_Impidimp`→`Marnies_Morgrem`; `Latias_ex`; `Cornerstone_Mask_Ogerpon_ex` (inmune a habilidades, ver `ABILITY_IMMUNE_IDS`); `Mega_Kangaskhan_ex`; `Iron_Thorns_ex`; `Charizard_ex`.
- `Hops_Phantump`→`Hops_Trevenant` (mazo "Hop", con `Splashing_Dodge_Atk = 1266` como ataque de esquiva y `COIN_FLIP_LOG_TYPE = 22` como tipo de evento de log para detectar el volado asociado).
- `Mega_Greninja_ex`, `Mega_Starmie_ex` (mazos de esquiva/snipe con agua).
- `Slowking`/`Slowpoke` (control psíquico).
- Línea `Beedrill`/`Weedle`/`Kakuna` con IDs **negativos** (`-991`, `-992`, `-993`): convención para IDs sintéticos/no reales del motor, probablemente placeholders o variantes sin carta física estándar en `card_table`.
- `Zoroark_N`/`Zorua_N`, `Alakazam_ex`/`Abra`/`Kadabra`: línea Abra que, pese al nombre `Alakazam_ex`, es **no-ex** en este entorno (ver `NONEX_FINAL_PREEVO_IDS` más abajo — el nombre de la constante es explícitamente engañoso y se documenta el motivo en el código).
- Línea `Buneary`(848)→`Mega_Lopunny_ex`(849): comentario en línea 220–221 aclara que es Stage 1, ex de 2 premios, y que el atacante básico peligroso es `Buneary`.
- `Gardevoir_ex`/`Ralts`/`Kirlia`, `Raging_Bolt_ex`, `Lugia_VSTAR`.
- Línea `Dusknoir`: `Duskull`→`Dusclops`→`Dusknoir`.
- Línea `Typhlosion`: `Cyndaquil`→`Quilava`→`Typhlosion` (fuego, ver `FIRE_POKEMON_IDS`).
- Línea `Drednaw`: `Chewtle`→`Drednaw`.
- `Cubchoo`/`Beartic`.
- `Eevee_TWM`/`Eevee_SFA`/`Eevee_PRE_ex`/`Eevee_SSP` agrupados en `EEVEE_IDS = {43, 145, 249, 317}` — cuatro imprentas distintas de Eevee que se tratan como equivalentes a efectos de reconocimiento de amenaza.

### Conjuntos de IDs por rol estratégico (líneas 245–313)

Cada conjunto agrupa IDs ya nombrados arriba para que el resto del agente pueda preguntar pertenencia (`in`) en vez de comparar IDs sueltos.

#### `OUR_EX_IDS` (línea 245)
```python
OUR_EX_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meowth_ex, Fezandipiti_ex}
```
Los cuatro Pokémon **ex propios** (2 premios si son noqueados). Se usa para razonar sobre riesgo propio: perder cualquiera de estos regala 2 premios al rival, así que la lógica de retirada/protección (`main-14`) y de planificación de ataque (`main-07`) los trata con más cautela que a `Tapu_Bulu` o `Pinsir` (no-ex).

#### `DECK_ITEM_IDS` (líneas 247–250)
```python
DECK_ITEM_IDS = frozenset({Bug_Catching_Set, Ultra_Ball, Night_Stretcher,
                           Poke_Pad, Unfair_Stamp})
```
Los cinco Items del mazo propio. El comentario explica el motivo: se usa para **posponer** la bajada de `Tapu_Bulu` hasta haber jugado antes los Items que valgan la pena (ver `TAPU_WAIT_FOR_ITEMS_SCORE` más abajo) — Tapu Bulu ocupa banca/turno y no aporta nada por sí mismo, así que conviene agotar primero la mano de Items útiles.

#### `EX_IMMUNE_IDS` (línea 252)
```python
EX_IMMUNE_IDS = {Crustle_Grass, Sylveon}
```
Pokémon rivales con una regla de "inmunidad a ataques de Pokémon ex" (mecánica de las cartas Crustle/Sylveon del set). Se usa para saber cuándo nuestros atacantes ex (`Ogerpon ex`, `Hydrapple ex`, etc.) **no pueden dañarlos** y hay que rodear el bloqueo con un atacante no-ex o con Boss's Orders hacia otro objetivo (ver la memoria de usuario "Ogerpon energy cap vs Crustle" y las reglas anti-Crustle en `main-09`).

#### `ABILITY_IMMUNE_IDS` (línea 254)
```python
ABILITY_IMMUNE_IDS = {Cornerstone_Mask_Ogerpon_ex}
```
Pokémon rival cuya Habilidad bloquea las Habilidades de los Pokémon del jugador activo/banca contrarios (Cornerstone Mask Ogerpon ex). Permite desactivar en el cálculo de puntuación las jugadas que dependen de Habilidades propias (`OUR_ABILITY_IDS`) cuando este Pokémon está en juego.

#### `OUR_ABILITY_IDS` (línea 256)
```python
OUR_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meganium, Fezandipiti_ex, Meowth_ex, Dipplin}
```
Los seis Pokémon propios que tienen Habilidad relevante para el agente (incluye `Dipplin`, pre-evo de Hydrapple, que también tiene Habilidad propia). Se cruza con `ABILITY_IMMUNE_IDS` para saber si esas Habilidades siguen activas.

#### `NON_ATTACKER_ENERGY_WASTE_IDS` (línea 258)
```python
NON_ATTACKER_ENERGY_WASTE_IDS = {Meowth_ex, Fezandipiti_ex}
```
Pokémon propios que normalmente **no** se usan como atacantes activos (su rol es de soporte/Habilidad), así que adjuntarles energía suele ser desperdicio. Se usa en la puntuación de `ATTACH` (`main-13`) para penalizar cargar energía en ellos salvo excepción justificada.

#### `HIGH_PRIORITY_BENCH_TARGETS` (línea 260)
```python
HIGH_PRIORITY_BENCH_TARGETS = {Budew, Munkidori, Froslass, Snorunt, Dreepy, Drakloak, Dwebble_Grass, Dwebble_Fighting}
```
Pokémon rivales de banca que conviene noquear en cuanto se pueda (habilitadores de combo, pre-evos baratas de amenazas fuertes, o piezas de control) — se usa en la escalera de `Boss's Orders` (`main-08`) y en la elección de objetivo de ataque para dar prioridad a sacarlos de la banca antes de que evolucionen o activen su efecto.

#### `META_BENCH_TARGETS` (líneas 262–265)
```python
META_BENCH_TARGETS = {Slowpoke, Slowking, Weedle, Kakuna, Beedrill, Zorua_N, Zoroark_N,
                      Abra, Kadabra, Alakazam_ex, Ralts, Kirlia, Gardevoir_ex,
                      Duskull, Dusclops, Dusknoir, Cyndaquil, Quilava, Typhlosion,
                      Chewtle, Drednaw, Sylveon, 43, 145, 249, 317}
```
Lista más amplia que `HIGH_PRIORITY_BENCH_TARGETS`: engloba todas las **líneas de evolución completas** de amenazas del meta conocido (incluye los Eevee sueltos por ID en vez de `EEVEE_IDS`, curiosamente sin usar el alias del conjunto ya definido). Se usa como referencia general de "esto es una pieza de un mazo rival relevante" en la valoración de objetivos, más laxa que la lista de alta prioridad.

#### `FIRE_POKEMON_IDS`, `WATER_SNIPE_IDS`, `PSYCHIC_CONTROL_IDS` (líneas 267–271)
```python
FIRE_POKEMON_IDS = {Charizard_ex, Typhlosion, Cyndaquil, Quilava}
WATER_SNIPE_IDS = {Mega_Greninja_ex, 47}
PSYCHIC_CONTROL_IDS = {Slowking, Alakazam_ex, Gardevoir_ex}
```
Tres agrupaciones por **tipo de amenaza táctica** más que por tipo elemental literal: `FIRE_POKEMON_IDS` marca la línea Typhlosion + Charizard ex; `WATER_SNIPE_IDS` marca atacantes de agua con capacidad de "snipe" (daño dirigido a la banca, incluye el ID suelto `47` sin constante nombrada); `PSYCHIC_CONTROL_IDS` marca Pokémon psíquicos con efectos de control de mano/tablero (Slowking, Alakazam ex, Gardevoir ex). Se usan en reglas de matchup específicas para anticipar qué puede hacer el rival (daño a banca, bloqueo, etc.).

#### `THREAT_PREEVO_IDS` (líneas 273–278)
```python
Riolu = 677
Mega_Lucario_ex = 678
Duraludon = 169

THREAT_PREEVO_IDS = {Riolu, Duraludon, Hops_Phantump, Dwebble_Grass, Dwebble_Fighting,
                     Buneary}
```
Pre-evoluciones básicas cuya evolución final es una amenaza que conviene cortar de raíz (p. ej. `Riolu` → `Mega_Lucario_ex`, `Buneary` → `Mega_Lopunny_ex`). Es un conjunto más general que `EX_PREEVO_IDS` (no exige que la evolución final sea ex, solo que sea una amenaza a vigilar).

#### `DUNSPARCE_IDS` (líneas 280–283)
```python
# Dunsparce (id 65 = TEF, id 305 = JTG): NUNCA gustear con Boss's Orders (user
# req). Son muros que se retiran/reposicionan con facilidad; subirlos al activo
# rival con Boss's Orders no aporta ventaja.
DUNSPARCE_IDS = {65, 305}
```
Dos imprentas distintas de Dunsparce (sets TEF y JTG), identificadas directamente por ID porque no tienen constante nombrada. El comentario documenta un **requisito explícito del usuario**: nunca usar Boss's Orders para subir a Dunsparce al activo rival, porque es un muro barato de retirar que no representa presión real — gustearlo desperdicia el Supporter. Coincide con la memoria de usuario "Boss's: gustear Buneary vs Mega Lopunny ex", que prioriza objetivos que sí son atacantes reales.

#### `KEY_BENCH_ATTACKER_IDS` (líneas 285–293)
```python
KEY_BENCH_ATTACKER_IDS = {Hops_Trevenant, Hops_Phantump}
```
El comentario (líneas 285–292) explica el caso de uso: Pokémon clave de un mazo rival que conviene noquear en banca **aunque** el propio activo pueda noquear al activo rival, siempre que ese activo rival no sea él mismo una pieza clave (p. ej. un muro sin energía). El ejemplo dado es el mazo "Hop": su atacante clave es `Hops_Trevenant`, y su línea (`Trevenant`/`Phantump`) debe cazarse en banca antes que perder el turno pegándole a un muro. La prioridad fina entre variantes (con/sin energía, evolucionado/pre-evo) la resuelve `_boss_tier` en la selección de objetivo `TO_ACTIVE` (fuera de este bloque, ver `main-08`), documentada aquí como: Trevenant con energía > Trevenant sin energía > Phantump con energía > Phantump sin energía.

#### `EX_PREEVO_IDS` (líneas 295–304)
```python
EX_PREEVO_IDS = {
    Dreepy, Drakloak,
    Riolu,
    Duraludon,
    Zorua_N,
    Abra, Kadabra,
    Ralts, Kirlia,
    Marnies_Impidimp, Marnies_Morgrem,
    Buneary,  # -> Mega Lopunny ex (id 849, ex de 2 premios)
}
```
Pre-evoluciones (básicos y Stage 1 intermedios) cuya línea evolutiva termina en un Pokémon **ex de 2 premios** (`Dragapult ex`, `Mega Lucario ex`, `Zoroark ex`/similar, `Alakazam` — con la salvedad de `NONEX_FINAL_PREEVO_IDS` de abajo —, `Gardevoir ex`, `Grimmsnarl ex`, `Mega Lopunny ex`). Existe porque justifica una regla táctica concreta: **gustear con Boss's Orders una pre-evolución** de esta lista para noquearla en banca "corta" una línea que, de completarse, se convertiría en un atacante de 2 premios — es decir, aceptar noquear algo de 1 premio ahora a cambio de negar un ex de 2 premios después es una inversión rentable (ver ladder de Boss's Orders en `main-08`).

#### `NONEX_FINAL_PREEVO_IDS` (líneas 306–313)
```python
# ... la logica de "negar una linea EX" (que
# justifica gustear una pre-evo con Boss's para impedir un ATACANTE DE 2
# PREMIOS) NO debe aplicar a esta linea: gustear+noquear la pre-evo rinde 1
# premio, lo mismo que noquear al muro activo, asi que es un gusteo inutil.
NONEX_FINAL_PREEVO_IDS = {Abra, Kadabra}
```
Contrapartida directa de `EX_PREEVO_IDS`: aunque `Abra`/`Kadabra` están incluidos en `EX_PREEVO_IDS` (porque su evolución final usa la constante `Alakazam_ex = 743`), el comentario aclara que ese nombre es **engañoso** — el dato real de la carta en `card_table` marca `ex=False`, es decir, `Alakazam` (743) es un Pokémon de **1 premio** en este entorno, no de 2. Por tanto la regla de "gustear pre-evo para negar un ex de 2 premios" no debe dispararse para esta línea concreta: noquear a `Abra`/`Kadabra` en banca rinde el mismo premio (1) que noquear al activo, así que gustearlos con Boss's Orders sería un desperdicio del Supporter. `NONEX_FINAL_PREEVO_IDS` es el conjunto de excepción que el resto del código debe restar de `EX_PREEVO_IDS` antes de aplicar esa lógica. Coincide con la memoria de usuario "Boss's: no gustear pre-evo de línea no-ex" (743 es no-ex, 1 premio; no gustear Abra/Kadabra→Alakazam).

### `_ID_NAME_EXPECTATIONS` y `_validate_id_constants` (líneas 315–354)

```python
def _validate_id_constants():
    mismatches = []
    for _cid, _expected in _ID_NAME_EXPECTATIONS.items():
        if _cid < 0:
            continue
        _cd = card_table.get(_cid)
        _name = getattr(_cd, 'name', None) if _cd is not None else None
        if _name is None or _expected.lower() not in _name.lower():
            mismatches.append((_cid, _expected, _name))
```

`_ID_NAME_EXPECTATIONS` (líneas 315–332) es un diccionario `id → substring de nombre esperado` (p. ej. `Teal_Mask_Ogerpon_ex: "Ogerpon"`, `Meowth_ex: "Meowth"`, `Kadabra: "Kadabra"`) para las constantes más sensibles del archivo. `_validate_id_constants()` (líneas 334–348) es una **auto-comprobación de cordura** que se ejecuta al importar el módulo: para cada ID esperado, busca la carta real en `card_table` y verifica que el substring esperado aparezca en `card.name` (comparación case-insensitive); los IDs negativos (sintéticos, como `Beedrill = -991`) se saltan explícitamente porque no tienen entrada real en `card_table`. Si hay discrepancias, las imprime por `stderr` con prefijo `[WARN][ID-AUDIT]` en vez de lanzar una excepción — es un chequeo de auditoría, no un `assert` bloqueante, así que un fallo de esta validación **no impide** que el agente juegue con IDs potencialmente mal mapeados; solo deja rastro en logs. Las líneas 350–353 envuelven la llamada en un `try/except` genérico (`_ID_AUDIT_MISMATCHES = _validate_id_constants()`, o `[]` si algo falla) para que un error inesperado en la propia validación tampoco tumbe la carga del módulo.

Este mecanismo es la defensa contra el problema que describe el propio comentario de `NONEX_FINAL_PREEVO_IDS`: los datos de las cartas (sets, ex/no-ex, nombres) pueden cambiar entre versiones del catálogo del simulador, y una constante con un nombre que ya no corresponde al ID real (como pasó conceptualmente con `Alakazam_ex`) podría pasar desapercibida sin esta auditoría.

### Constantes de puntuación `SCORE_*` (líneas 355–363)

```python
SCORE_WIN_GAME = 50000

SCORE_LOOKAHEAD_EX_TRADE = 250
SCORE_LOOKAHEAD_KO_TRADE = 120
SCORE_LOOKAHEAD_SAFE = 60
SCORE_LOOKAHEAD_PROMOTE_KO = 120
SCORE_LOOKAHEAD_PROMOTE_SAFE = 40

SCORE_BELIEF_DIG_ENERGY = 250
```

- `SCORE_WIN_GAME = 50000`: el valor más alto del archivo, reservado para la opción que gana la partida inmediatamente (ver `docs/main.md` §1: valores "redondos" altos son prioridades fuertes que sobrescriben el puntaje base).
- Familia `SCORE_LOOKAHEAD_*`: puntajes usados por el análisis de "lo que pasará el próximo turno" (lookahead, ver `main-07`) al evaluar líneas de juego que dejan planteado un intercambio: `EX_TRADE` (250, intercambiar contra un ex rival) puntúa más que `KO_TRADE`/`PROMOTE_KO` (120, un KO normal) y estos más que dejar la posición simplemente `SAFE`/`PROMOTE_SAFE` (60/40, sin intercambio pero sin riesgo). El orden relativo (250 > 120 > 60 > 40) codifica la preferencia: mejor intercambio contra ex > KO simple > jugada segura.
- `SCORE_BELIEF_DIG_ENERGY = 250`: puntaje para acciones de búsqueda (creencia sobre el mazo, ver `main-03`/`main-11`) orientadas a encontrar energía, igualado al valor de `SCORE_LOOKAHEAD_EX_TRADE`.

### Constantes `BOSS_*` y ladder de Boss's Orders (líneas 365–389)

```python
BOSS_PRIORITY_CRUSTLE_GUST = 990
```
Líneas 365–369: comentario y constante para el caso Crustle — cuando el activo ex propio está bloqueado por `EX_IMMUNE_IDS` pero hay un objetivo alcanzable en banca rival que sí puede noquearse o dejarse sin retirada, este valor (990) debe superar tanto a los "cebos de robo" (Lillie's, puntuación base ~650) como al resto del ladder de Boss's. Es la codificación numérica directa de la memoria de usuario "Crustle: retirar Chikorita activo" / "Ogerpon energy cap vs Crustle".

```python
TAPU_WAIT_FOR_ITEMS_SCORE = 8900
```
Líneas 371–376: puntaje al que se **rebaja** la jugada de `Tapu_Bulu` mientras aún queden Items útiles en mano. El comentario explica el rango: queda por debajo de la banda de Items útiles (~9800+, o 9000 cuando un Item se "autolimita"), pero por encima de Items que no valen la pena jugar. El efecto neto: mientras haya Items buenos por jugar, ganan ellos; en cuanto se agotan, `Tapu_Bulu` vuelve a subir de prioridad y se juega. Aplica **solo** a Tapu Bulu (no es una regla general de secuenciación).

```python
BOSS_SCORE_WIN_VIA_BENCH = 5600      # gustada letal a un objetivo de banca
BOSS_SCORE_WALL_GUST = 5500          # rival con muro inmune (ex/habilidad) al activo
BOSS_SCORE_DODGE_REDIRECT = 5500     # redireccion por esquiva (dodge)
BOSS_SCORE_PRIZE_RANK_BASE = 5200    # gusteo que habilita KO (afinado por prize_rank)
BOSS_SCORE_LOW_VALUE_GUST = 1500     # gusteo de bajo valor
BOSS_SCORE_DEFENSIVE_GUST = 1500     # gusteo defensivo (vs Crustle)
BOSS_SCORE_EMPTY_GUST = 20           # gusteo NO ejecutable: ceder a Lillie's
```
Líneas 378–389: el comentario (378–382) sitúa esta escalera en su lugar de uso real (rama `PLAY` de Boss's Orders, ~línea 9250, documentada en `main-08` y `main-09`) y da la clave de lectura: cada rama representa un tipo de remate que puede lograrse gusteando, y a **todas menos `BOSS_SCORE_EMPTY_GUST`** se les suma después `supporter_boost`. El punto de referencia es Lillie's Determination con puntaje base 5000: las ramas por encima de 5000 (`WIN_VIA_BENCH` 5600, `WALL_GUST`/`DODGE_REDIRECT` 5500, `PRIZE_RANK_BASE` 5200) le ganan a "simplemente refrescar mano con Lillie's"; las ramas por debajo (`LOW_VALUE_GUST`/`DEFENSIVE_GUST` 1500, `EMPTY_GUST` 20) le ceden la prioridad a Lillie's porque el gusteo no aporta lo suficiente. En orden descendente de prioridad:
1. `WIN_VIA_BENCH` (5600): la gustada es letal — noquea un objetivo de banca que decide la partida.
2. `WALL_GUST` (5500) / `DODGE_REDIRECT` (5500, empatados): forzar al activo rival a salir cuando el actual es un muro inmune (`EX_IMMUNE_IDS`/`ABILITY_IMMUNE_IDS`) o cuando el rival está esquivando (dodge) y hay que redirigir el ataque.
3. `BOSS_SCORE_PRIZE_RANK_BASE` (5200): gusteo que habilita un KO normal, con el valor final afinado según `prize_rank` (cuántos premios vale el objetivo) — es una base, no un valor fijo.
4. `BOSS_SCORE_LOW_VALUE_GUST` / `BOSS_SCORE_DEFENSIVE_GUST` (1500 cada una): gusteos que no ganan a Lillie's — de bajo valor ofensivo, o puramente defensivos (p. ej. sacar un peón vs Crustle sin rematar).
5. `BOSS_SCORE_EMPTY_GUST` (20): Boss's Orders técnicamente jugable pero sin objetivo que aproveche el gusteo — puntaje mínimo, casi siempre pierde frente a cualquier otra jugada, incluida Lillie's.

## Interacciones

- `docs/main.md` §2 ("Nuestro mazo", "Detección de matchup") es la referencia previa obligatoria: este documento asume ya conocidos `OptionType`, `SelectContext`, energía efectiva y `CARTAS_ACTIVAS_EN_MAZO`.
- Las banderas `op_is_crustle_deck`, `op_is_cornerstone_deck`, etc. (definidas más adelante en `agent()`, ver `main-06`) se calculan comparando cartas visibles del rival contra los IDs/conjuntos de este bloque (`EX_IMMUNE_IDS`, `ABILITY_IMMUNE_IDS`, `KEY_BENCH_ATTACKER_IDS`, `DUNSPARCE_IDS`).
- `HIGH_PRIORITY_BENCH_TARGETS`, `META_BENCH_TARGETS`, `EX_PREEVO_IDS`, `NONEX_FINAL_PREEVO_IDS` y `KEY_BENCH_ATTACKER_IDS` alimentan directamente `_boss_tier` y la escalera `BOSS_SCORE_*` en la rama `PLAY` de Boss's Orders, documentada en `main-08-agent-boss-orders.md`.
- `RETREAT_COST` es consumido por la puntuación de `RETREAT` (`main-14-agent-retreat-scoring.md`) y por el análisis de amenaza/plan de ataque (`main-07-agent-threat-and-plan.md`) al estimar si el rival puede retirar a un objetivo antes de ser noqueado.
- `DECK_ITEM_IDS` y `TAPU_WAIT_FOR_ITEMS_SCORE` se usan juntos en la puntuación de `PLAY` de `Tapu_Bulu` (`main-12-agent-play-scoring.md`).
- `card_table` (línea 43) es la fuente que consulta `get_card()` en todo el archivo (definido en el bloque de utilidades de puntuación, `main-04-scoring-helpers.md`).

## Reglas derivadas de partidas

Este bloque de constantes no contiene comentarios que citen directamente un `log 86xxxxxx`, pero varias de sus reglas están descritas en la memoria de usuario como derivadas de partidas concretas y se corresponden con constantes/comentarios de aquí:
- `DUNSPARCE_IDS` (líneas 280–283): "user req" explícito de no gustear nunca Dunsparce, documentado literalmente en el comentario del código.
- `NONEX_FINAL_PREEVO_IDS` (líneas 306–313): corrige un error de nomenclatura (`Alakazam_ex` no es ex) que había llevado a gustear inútilmente la línea Abra/Kadabra; coincide con la memoria "Boss's: no gustear pre-evo de línea no-ex".
- `BOSS_PRIORITY_CRUSTLE_GUST` (líneas 365–369): codifica en un número la prioridad de gustear en banca cuando el activo ex propio está bloqueado por Crustle, alineado con las memorias "Ogerpon energy cap vs Crustle" y "Crustle: retirar Chikorita activo".
