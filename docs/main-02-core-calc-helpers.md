# main.py — Núcleo de cálculo: energía, daño y ataque (líneas 391–667)

## Rol en el agente

Este bloque es la **fuente única de verdad** para tres preguntas que se repiten cientos de veces en `agent()`: ¿cuánta energía efectiva tengo?, ¿puede este Pokémon atacar ya (o tras adjuntar)?, y ¿cuánto daño haría un ataque concreto una vez aplicadas debilidad/resistencia/inmunidades? Aquí vive también `AttackPlan`, la estructura que memoriza "qué vamos a hacer este turno con el atacante" para que las distintas secciones del bucle de puntuación (energía, retirada, ataque, Boss's Orders) actúen de forma coherente en vez de recalcular y potencialmente contradecirse.

El concepto central que atraviesa todo el archivo es la **energía efectiva** (ver glosario en `docs/main.md`): con `Meganium` en juego (Habilidad *Wild Growth*), el simulador ya entrega `len(energies)` duplicado para energías Planta físicas, así que "efectiva" y "física" divergen y hay que ser explícito sobre en qué unidad se está razonando. Todas las funciones de este bloque dejan claro, en su nombre o su comentario, en qué unidad trabajan.

## Detalle por bloque

### `class AttackPlan` (líneas 391–402)

```python
class AttackPlan:
    attacker = -1
    target = -1
    attack_index = -1
    remain_hp = -1
    energy = False
```

Estructura de estado **mutable, con una sola instancia global** (`plan = AttackPlan()`, línea 398) que se recalcula cada turno (junto con `pre_turn = 0` y `meganium_in_play = False`, también globales de módulo). Sus campos:
- `attacker`: índice del Pokémon (activo=0, banca=1..) elegido como atacante del turno.
- `target`: índice del objetivo rival planeado.
- `attack_index`: qué ataque de `attacker` se va a usar.
- `remain_hp`: HP que le quedaría al objetivo tras el golpe (usado para decidir rematar, retirar, etc.).
- `energy`: `True` si el ataque **requiere adjuntar una energía este turno** para ser posible (aún no tiene suficiente), `False` si ya puede atacar sin más.

Estratégicamente, `plan` es el "pizarrón compartido" del turno: la fase de análisis de amenaza (líneas ~1985–2900, documentada en `main-07`) lo rellena, y fases posteriores (energía, retirada, ataque, Boss's Orders) lo **leen** en vez de re-derivar la decisión, evitando que, por ejemplo, se adjunte energía a un Pokémon distinto del que finalmente ataca. Se usa profusamente como `plan.attacker`, `plan.energy`, `_attacker_ready = (plan.attacker >= 0 and not plan.energy)` (línea 3579), etc.

### `_grass_mult()` (líneas 403–411)

Devuelve siempre `1`. Existe por razones históricas: el comentario explica que la observación del simulador **ya** aplica *Wild Growth* duplicando cada energía Planta física dentro de `energies`, por lo que `len(energies)` es directamente la energía efectiva. La función se conserva para que las llamadas heredadas `crudo * _grass_mult()` sigan siendo correctas sin tener que reescribir cada sitio del código que las usa. Es, en esencia, un no-op documentado para no romper invariantes de código antiguo.

### `_grass_attach_unit()` (líneas 412–418)

```python
def _grass_attach_unit():
    return 2 if meganium_in_play else 1
```

Calcula cuánta energía **efectiva** aporta **una sola** energía básica Planta que se está a punto de adjuntar (desde la mano o recuperada), a diferencia de `_grass_mult()` que opera sobre energía ya en juego. Con `Meganium` activo, una Planta física recién puesta cuenta como `{G}{G}` = 2 efectivas; sin él, 1. Se usa para proyectar "si adjunto esta energía, ¿llego al requisito de ataque?" antes de que la observación lo refleje.

### `_active_of(state)` (líneas 419–428)

Helper de acceso seguro: devuelve `state.active[0]` o `None`, centralizando el patrón repetido `state.active[0] if state.active and state.active[0] is not None else None`. Tolera `state is None`. Es puramente defensivo/de legibilidad, sin lógica estratégica propia; se usa en decenas de sitios para obtener el activo propio o rival sin repetir la comprobación.

### `_physical_energy(effective_len)` (líneas 429–436)

Conversión **inversa** a la de `_grass_attach_unit`: convierte una cantidad de energía efectiva (`len(energies)`, ya doblada por Wild Growth) a número de cartas físicas. Con Meganium: `efectiva // 2`; sin Meganium: `efectiva` (son iguales). Se necesita cuando el razonamiento debe hablar de **cartas reales** (p. ej. cuántas energías físicas hay que descartar, o cuántas quedan disponibles en mano/mazo), no de unidades de pago de ataque.

### `_retreat_cards(retreat_cost)` (líneas 437–448)

Calcula cuántas cartas de energía **físicas** hacen falta para pagar un coste de retirada expresado en unidades efectivas, usando división con techo (`-(-retreat_cost // _grass_attach_unit())`). Devuelve `0` si `retreat_cost <= 0`. La división con techo importa estratégicamente: con Meganium, un coste de retirada de 3 efectivas no se paga con 1.5 cartas — hacen falta 2 Plantas físicas (`-(-3 // 2) = 2`), y esa carta "de más" es relevante para decidir si retirarse es viable con la mano/banca actual.

### `ATTACK_ENERGY_REQ` y `MAIN_ATTACKERS` (líneas 449–461)

```python
ATTACK_ENERGY_REQ = {
    Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
    Tapu_Bulu: 4, Fezandipiti_ex: 3, Meganium: 4, Pinsir: 2,
    Bayleef: 2, Applin: 1, Chikorita: 1,
}
```

`ATTACK_ENERGY_REQ` es el diccionario **fuente única de verdad** (así lo llama el comentario de línea 447) del coste de energía **efectiva** para que cada carta pueda usar su ataque principal. Cubre toda la línea evolutiva Chikorita→Bayleef→Meganium (1/2/4), la línea Applin→Dipplin→Hydrapple ex (1/1/2) y los atacantes ex/no-ex del resto del mazo: Teal Mask Ogerpon ex (3), Tapu Bulu (4), Fezandipiti ex (3), Pinsir (2). Como `len(energies)` ya es efectiva (línea 447–448), estos valores se comparan **directamente** sin conversión.

`MAIN_ATTACKERS` es la tupla de los **7 atacantes "grandes"** que se evalúan en los bloques de "¿tengo algo listo para atacar?": `Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir`. Nótese que **excluye** deliberadamente `Bayleef, Applin, Chikorita` — estas son pre-evoluciones de acumulación de energía, no atacantes que el agente deba priorizar como "listos para golpear"; sí tienen entrada en `ATTACK_ENERGY_REQ` porque técnicamente pueden atacar, pero no forman parte del conjunto de "atacantes principales" que activa lógica de decisión de alto nivel (p. ej. `_ready_attacker_count`, documentado en `main-09`).

### `_can_attack_eff(card_id, raw_energy)` (líneas 462–483)

```python
def _can_attack_eff(card_id, raw_energy):
    _req = ATTACK_ENERGY_REQ.get(card_id)
    return _req is not None and raw_energy >= _req
```

Predicado central de "¿puede atacar ya?": busca el requisito en `ATTACK_ENERGY_REQ` y compara contra `raw_energy` (que debe ser `len(energies)`, ya efectiva). Si la carta no está en el diccionario (`_req is None`), devuelve `False` — es decir, cualquier Pokémon sin entrada en `ATTACK_ENERGY_REQ` se considera incapaz de atacar según este helper. Justo después del bloque (líneas 469–483) se declaran los globales de estado de partida que dependen de este tipo de cálculos y se reinician entre turnos: `forest_in_play`, `ko_last_turn`, `_ko_detected_this_turn`, `_prev_op_prize`, `we_go_first`, los flags de matchup `op_is_crustle_deck`/`op_is_cornerstone_deck`/`op_has_mega_kangaskhan`, `_field_at_turn_start`, `_poke_pad_target_id`, `_ub_meowth_pending`, y el par `_dodge_immune_serial`/`_dodge_immune_turn` (rastrea inmunidad temporal por "esquivar" una amenaza detectada).

### `_our_effective_damage(...)` (líneas 578–614)

```python
def _our_effective_damage(my_pokemon, op_pokemon, base_damage,
                          meganium_active=False, neutralization_zone=False):
```

Aplica al `base_damage` (ya calculado por `_attacker_base_damage`) todas las reglas de modificación de daño **específicas del matchup**, en este orden:
1. **Inmunidad total**: si `op_pokemon.id` está en `EX_IMMUNE_IDS` (`{Crustle_Grass, Sylveon}`) y nuestro atacante es ex (`my_is_ex`, vía `OUR_EX_IDS`), el daño es `0` — estas cartas rivales bloquean el daño de Pokémon ex.
2. **Neutralization Zone**: si está activa y nuestro atacante es ex mientras el rival **no** tiene "rule box" (ni `ex` ni `megaEx` en `card_table`), el daño es `0` (el estadio anula el daño de ex contra no-ex/no-mega).
3. **Inmunidad a Habilidad**: si el rival está en `ABILITY_IMMUNE_IDS` (`{Cornerstone_Mask_Ogerpon_ex}`) y nuestro atacante depende de Habilidad (`OUR_ABILITY_IDS`), daño `0`.
4. **Debilidad/resistencia Planta**: salvo que el atacante sea `Fezandipiti_ex` (`is_fez`, que no tiene tipo Planta y por tanto no debe recibir este bonus/penalización), si `data.weakness == EnergyType.GRASS` el daño se **duplica**; si `data.resistance == EnergyType.GRASS` se **resta 30**.
5. **Caso especial `Drednaw`**: si el daño alcanzaría `>= 200`, se anula a `0` (representa una Habilidad/regla de tope de daño de esa carta rival).
6. **Caso especial `Crustle_Fighting`**: si sigue a HP máximo (`hp == maxHp`) y el daño lo noquearía (`damage >= hp`), el daño se recorta a `hp - 10` — modela que Crustle sobrevive con 10 HP a un golpe que de otro modo sería letal (probablemente su Habilidad de "no debilitar por el primer golpe" o similar), evitando que el agente lo dé por muerto.

Devuelve `max(0, int(damage))`. Si `op_pokemon is None` o `base_damage is None`, devuelve `0`; si el rival no tiene entrada en `card_table`, devuelve `max(0, base_damage)` sin modificadores (fallback seguro).

### `_attacker_base_damage(...)` (líneas 615–646)

```python
def _attacker_base_damage(attacker_id, target, effective_energy,
                          grass_scale, teal_self_energy, bench_count):
```

Calcula el daño **base** (antes de debilidad/resistencia/inmunidad — de eso se encarga `_our_effective_damage`) de cada atacante propio, codificando las fórmulas de sus ataques principales:
- **Hydrapple ex**: `30 + 30 * grass_scale` (escala con energías Grass en juego, típicamente su propia energía adjunta).
- **Teal Mask Ogerpon ex**: `30 + 30 * (teal_self_energy + len(target.energies))` — su ataque *Teal Dance* escala con la **suma** de energía propia y energía del objetivo (por eso recibe `teal_self_energy` como parámetro separado de `effective_energy`).
- **Tapu Bulu**: fijo `220`.
- **Fezandipiti ex**: fijo `100`.
- **Meganium**: fijo `140`.
- **Dipplin**: `20 * bench_count` — escala con el tamaño de la propia banca.
- **Pinsir**: fijo `100`.

Cada rama primero comprueba `effective_energy >= req[attacker_id]` usando `ATTACK_ENERGY_REQ` como referencia; si el atacante no cumple el requisito, o su `attacker_id` no coincide con ninguno de los siete casos, devuelve `0`. No contempla las pre-evoluciones (Chikorita/Bayleef/Applin) porque, aunque `_can_attack_eff` las permite, no tienen fórmula de daño relevante aquí (sus ataques son de bajo impacto y no forman parte de `MAIN_ATTACKERS`).

### `_bench_attacker_can_ko(...)` (líneas 647–667)

```python
def _bench_attacker_can_ko(my_state, target, meganium_active, total_grass_field,
                           bench_count, retreat_grass_after, neutral_zone):
```

Recorre **todos los Pokémon de la banca propia** (`my_state.bench`) y comprueba si **alguno**, atacando con su energía actual (sin cambios de turno), podría noquear a `target`. Para cada `bp` en la banca:
1. Descarta `target is None` o sin HP (`_thp <= 0`) devolviendo `False` de entrada.
2. Calcula `eff = len(bp.energies) * _grass_mult()` (energía efectiva; recuérdese que `_grass_mult()` es un no-op, así que `eff == len(bp.energies)`).
3. Llama a `_attacker_base_damage(bp.id, target, eff, grass_scale=retreat_grass_after, teal_self_energy=e, bench_count=bench_count)` para el daño base.
4. Si `base > 0`, aplica `_our_effective_damage` con `meganium_active`/`neutral_zone` y compara contra `_thp`: si `>= _thp`, devuelve `True` inmediatamente (early-return al primer atacante de banca que sirva).

Si ningún Pokémon de banca alcanza el KO, devuelve `False` tras agotar el bucle. El parámetro `retreat_grass_after` se reutiliza como `grass_scale` — es decir, se está proyectando el daño de Hydrapple ex **después** de una retirada/cambio de energía, no con el estado actual literal. Esta función es la pieza clave que permite al agente responder "¿me conviene retirar al activo y dejar que la banca remate?" (usada, por ejemplo, en la evaluación de Boss's Orders y en la puntuación de RETREAT, líneas ~3245, ~3279, ~3888).

## Interacciones

- **Con el análisis de amenaza y `plan` (líneas ~1985–2900, `main-07`)**: esta sección puebla `plan.attacker`/`plan.target`/`plan.attack_index`/`plan.energy` invocando repetidamente `_attacker_base_damage` y `_our_effective_damage` (p. ej. líneas 2428–2432, 2511–2552, 2585–2659, 2696–2813) para decidir qué atacante y qué objetivo maximizan el resultado del turno.
- **Con la puntuación de energía (`main-10`)**: `_attacker_ready = (plan.attacker >= 0 and not plan.energy)` (línea 3579) y `_attacker_ready_with_attach` (línea 3580) leen `plan.energy` para saber si conviene priorizar el adjunte de energía sobre otras jugadas.
- **Con Boss's Orders (`main-08`)**: usa `_bench_attacker_can_ko` (líneas 3245, 3279) para valorar si, tras gustear a un objetivo rival concreto, algún Pokémon de banca propio podría rematarlo.
- **Con RETREAT (`main-14`)**: `_retreat_cards` y `_bench_attacker_can_ko` (línea 3888) informan si retirar al activo estancado y promover un atacante de banca produce un KO.
- **Con constantes globales (`main-01`)**: depende de `card_table`, `EnergyType.GRASS`, `EX_IMMUNE_IDS`, `ABILITY_IMMUNE_IDS`, `OUR_EX_IDS`, `OUR_ABILITY_IDS`, `Drednaw`, `Crustle_Fighting` y todos los IDs de carta usados como claves en `ATTACK_ENERGY_REQ`, todos definidos antes de la línea 391.
- **Nota de diseño**: `_grass_mult()` devolviendo siempre `1` mientras `_grass_attach_unit()` devuelve `2` con Meganium ilustra la distinción clave del glosario: la primera opera sobre energía **ya en juego** (que la observación ya dobla), la segunda sobre energía **a punto de adjuntarse** (que aún no ha sido doblada por el motor).
