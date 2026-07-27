# main.py — Núcleo de cálculo: energía, daño y ataque

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Rol en el agente

Este bloque es la **fuente única de verdad** para tres preguntas que se repiten cientos de veces en `agent()`: ¿cuánta energía efectiva tengo?, ¿puede este Pokémon atacar ya (o tras adjuntar)?, y ¿cuánto daño haría un ataque concreto una vez aplicadas debilidad/resistencia/inmunidades? Aquí vive también `AttackPlan`, la estructura que memoriza "qué vamos a hacer este turno con el atacante" para que las distintas secciones del bucle de puntuación (energía, retirada, ataque, Boss's Orders) actúen de forma coherente en vez de recalcular y potencialmente contradecirse. Desde julio 2026 el bloque incluye además el lado **defensivo** del cálculo: `_op_active_attack_damage_to` resuelve el daño real del ataque del activo rival contra un Pokémon nuestro, incluyendo la proyección de *Powerful Hand* de Alakazam y el bono de la tool rival `Maximum_Belt`.

El concepto central que atraviesa todo el archivo es la **energía efectiva** (ver glosario en `docs/main.md`): con `Meganium` en juego (Habilidad *Wild Growth*), el simulador ya entrega `len(energies)` duplicado para energías Planta físicas, así que "efectiva" y "física" divergen y hay que ser explícito sobre en qué unidad se está razonando. Todas las funciones de este bloque dejan claro, en su nombre o su comentario, en qué unidad trabajan. Las energías del **rival** en nuestra observación no están dobladas.

## Detalle por bloque

### `class AttackPlan`

```python
class AttackPlan:
    attacker = -1
    target = -1
    attack_index = -1
    remain_hp = -1
    energy = False
```

Estructura de estado **mutable, con una sola instancia global** (`plan = AttackPlan()`), que se recalcula cada turno (junto con los globales de módulo `pre_turn` y `meganium_in_play`). Sus campos:
- `attacker`: índice del Pokémon (activo=0, banca=1..) elegido como atacante del turno.
- `target`: índice del objetivo rival planeado.
- `attack_index`: qué ataque de `attacker` se va a usar.
- `remain_hp`: HP que le quedaría al objetivo tras el golpe (usado para decidir rematar, retirar, etc.).
- `energy`: `True` si el ataque **requiere adjuntar una energía este turno** para ser posible, `False` si ya puede atacar sin más.

Estratégicamente, `plan` es el "pizarrón compartido" del turno: la fase de análisis de amenaza (documentada en `main-07`) lo rellena, y fases posteriores (energía, retirada, ataque, Boss's Orders) lo **leen** en vez de re-derivar la decisión, evitando que, por ejemplo, se adjunte energía a un Pokémon distinto del que finalmente ataca. Se usa profusamente como `plan.attacker`, `plan.energy`, `_attacker_ready = (plan.attacker >= 0 and not plan.energy)`, etc.

### `_grass_mult()`

Devuelve siempre `1`. Existe por razones históricas: el comentario explica que la observación del simulador **ya** aplica *Wild Growth* duplicando cada energía Planta física dentro de `energies`, por lo que `len(energies)` es directamente la energía efectiva. La función se conserva para que las llamadas heredadas `crudo * _grass_mult()` sigan siendo correctas sin tener que reescribir cada sitio del código que las usa. Es, en esencia, un no-op documentado para no romper invariantes de código antiguo.

### `_grass_attach_unit()`

```python
def _grass_attach_unit():
    return 2 if meganium_in_play else 1
```

Calcula cuánta energía **efectiva** aporta **una sola** energía básica Planta que se está a punto de adjuntar (desde la mano o recuperada), a diferencia de `_grass_mult()` que opera sobre energía ya en juego. Con `Meganium` activo, una Planta física recién puesta cuenta como `{G}{G}` = 2 efectivas; sin él, 1. Se usa para proyectar "si adjunto esta energía, ¿llego al requisito de ataque?" antes de que la observación lo refleje.

### `_active_of(state)`

Helper de acceso seguro: devuelve `state.active[0]` o `None`, centralizando el patrón repetido `state.active[0] if state.active and state.active[0] is not None else None`. Tolera `state is None`. Es puramente defensivo/de legibilidad, sin lógica estratégica propia; se usa en decenas de sitios para obtener el activo propio o rival sin repetir la comprobación.

### `_physical_energy(effective_len)`

Conversión **inversa** a la de `_grass_attach_unit`: convierte una cantidad de energía efectiva (`len(energies)`, ya doblada por Wild Growth) a número de cartas físicas. Con Meganium: `efectiva // 2`; sin Meganium: son iguales. Se necesita cuando el razonamiento debe hablar de **cartas reales** (p. ej. cuántas energías físicas hay que descartar, o cuántas quedan disponibles en mano/mazo), no de unidades de pago de ataque.

### `_retreat_cards(retreat_cost)`

Calcula cuántas cartas de energía **físicas** hacen falta para pagar un coste de retirada expresado en unidades efectivas, usando división con techo (`-(-retreat_cost // _grass_attach_unit())`). Devuelve `0` si el coste es `<= 0`. La división con techo importa estratégicamente: con Meganium, un coste de retirada de 3 efectivas no se paga con 1.5 cartas — hacen falta 2 Plantas físicas, y esa carta "de más" es relevante para decidir si retirarse es viable con la mano/banca actual.


### `_retreat_grass_units(retreat_cost)`

Unidades **efectivas** de Planta que **desaparecen del campo** al pagar una retirada de `retreat_cost` símbolos: `_retreat_cards(coste) × _grass_attach_unit()`. Es el valor que hay que restar de `total_grass` al proyectar *Syrup Storm* tras un retiro — el coste se paga con **cartas enteras** y con *Wild Growth* cada Planta vale **dos** unidades, así que restar el coste en símbolos (o el número de cartas) **sobrestima** el daño por ese factor. Sin ella, el plan creía que un Hydrapple ex de banca noqueaba tras retirar (registro_006 paso 78 vs Archaludon ex: 10−1 = 9 unidades → 330−30 = 300 sobre 270 PV) cuando la realidad eran 8 unidades → 240; con ese KO fantasma se vetaba el ataque del activo, que **sí** noqueaba, y el turno acababa cobrando 1 premio en vez de 2. La usan los 9 sitios que proyectan "Planta tras retirar".

### `ATTACK_ENERGY_REQ` y `MAIN_ATTACKERS`

```python
ATTACK_ENERGY_REQ = {
    Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
    Tapu_Bulu: 4, Fezandipiti_ex: 3, Meganium: 4, Pinsir: 2,
    Bayleef: 2, Applin: 1, Chikorita: 1,
}
```

`ATTACK_ENERGY_REQ` es el diccionario **fuente única de verdad** (así lo llama su comentario) del coste de energía **efectiva** para que cada carta pueda usar su ataque principal. Cubre toda la línea Chikorita→Bayleef→Meganium (1/2/4), la línea Applin→Dipplin→Hydrapple ex (1/1/2) y los atacantes del resto del mazo: Teal Mask Ogerpon ex (3), Tapu Bulu (4), Fezandipiti ex (3), Pinsir (2). Como `len(energies)` ya es efectiva, estos valores se comparan **directamente** sin conversión.

`MAIN_ATTACKERS` es la tupla de los **7 atacantes "grandes"** que se evalúan en los bloques de "¿tengo algo listo para atacar?": `Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir`. Nótese que **excluye** deliberadamente `Bayleef, Applin, Chikorita` — pre-evoluciones de acumulación de energía, no atacantes que el agente deba priorizar como "listos para golpear"; sí tienen entrada en `ATTACK_ENERGY_REQ` porque técnicamente pueden atacar, pero no forman parte del conjunto que activa lógica de decisión de alto nivel (p. ej. `_ready_attacker_count`, documentado en `main-09`).

### `_can_attack_eff(card_id, raw_energy)` y globales de partida

```python
def _can_attack_eff(card_id, raw_energy):
    _req = ATTACK_ENERGY_REQ.get(card_id)
    return _req is not None and raw_energy >= _req
```

Predicado central de "¿puede atacar ya?": busca el requisito en `ATTACK_ENERGY_REQ` y compara contra `raw_energy` (que debe ser `len(energies)`, ya efectiva). Si la carta no está en el diccionario, devuelve `False` — cualquier Pokémon sin entrada se considera incapaz de atacar según este helper.

Justo después se declaran los globales de estado de partida que se reinician entre turnos/partidas: `forest_in_play`, `ko_last_turn`, `_ko_detected_this_turn`, `_prev_op_prize`, `we_go_first`, los flags de matchup `op_is_crustle_deck`/`op_is_cornerstone_deck`/`op_has_mega_kangaskhan`, `_field_at_turn_start`, `_poke_pad_target_id`, `_ub_meowth_pending` (una Ultra Ball de este turno eligió buscar Meowth ex — obliga a bajarlo con Supporter libre), `_ub_engine_pivot_turn` (el pivote `_ub_engine_refresh_pivot` puntuó la Ultra Ball al tier de energía; el **fetch** posterior de esa UB lo consume para elegir Meowth ex, porque en ese momento las energías ya se descartaron y las condiciones del pivote no se pueden recomputar; se resetea por turno), y el par `_dodge_immune_serial`/`_dodge_immune_turn` (rastrea inmunidad temporal por "esquiva" detectada).

### `_our_effective_damage(...)`

```python
def _our_effective_damage(my_pokemon, op_pokemon, base_damage,
                          meganium_active=False, neutralization_zone=False):
```

Aplica al `base_damage` (ya calculado por `_attacker_base_damage`) todas las reglas de modificación de daño **específicas del matchup**, en este orden:
1. **Inmunidad total anti-ex**: si `op_pokemon.id` está en `EX_IMMUNE_IDS` (`{Crustle_Grass, Crustle_Fighting, Sylveon}` — ambas variantes de Crustle desde la auditoría de julio 2026) y nuestro atacante es ex (vía `OUR_EX_IDS`), el daño es `0`.
2. **Neutralization Zone**: si está activa y nuestro atacante es ex mientras el rival **no** tiene "rule box" (ni `ex` ni `megaEx` en `card_table`), el daño es `0` (el estadio anula el daño de nuestros ex contra Pokémon de 1 premio; ver la memoria "Estrategia vs Neutralization Zone").
3. **Inmunidad a Habilidad**: si el rival está en `ABILITY_IMMUNE_IDS` (`{Cornerstone_Mask_Ogerpon_ex}`) y nuestro atacante tiene Habilidad (`OUR_ABILITY_IDS`), daño `0`.
4. **Debilidad/resistencia Planta**: salvo que el atacante sea `Fezandipiti_ex` (`is_fez`, que no es de tipo Planta y no debe recibir este modificador), si `data.weakness == EnergyType.GRASS` el daño se **duplica**; si `data.resistance == EnergyType.GRASS` se **resta 30**.
5. **Caso especial `Drednaw`**: si el daño alcanzaría `>= 200`, se anula a `0` (regla de tope de daño de esa carta rival).
6. **Caso especial `Crustle_Fighting`**: si sigue a HP máximo y el daño lo noquearía, el daño se recorta a `hp - 10` — modela que este Crustle sobrevive con 10 HP a un golpe que de otro modo sería letal, evitando que el agente lo dé por muerto. (En la práctica solo es alcanzable con atacantes no-ex, porque la regla 1 ya anula el daño de nuestros ex contra él.)

Devuelve `max(0, int(damage))`. Si `op_pokemon is None` o `base_damage is None`, devuelve `0`; si el rival no tiene entrada en `card_table`, devuelve `max(0, base_damage)` sin modificadores (fallback seguro).

### `_op_active_attack_damage_to(op_active, target, op_hand_count=None)`

La contraparte **defensiva** de `_our_effective_damage`: máximo daño que el activo rival puede hacerle a `target` (un Pokémon nuestro). Resuelve los IDs de ataque del rival vía `attack_table` — los `card.attacks` de `card_table` son ints, no objetos, por lo que la versión anidada `_op_best_damage_vs` (definida dentro de `agent()`, ver `main-07`) que hace `getattr(id, 'damage')` sobre esos ints daba siempre 0 para este propósito; esta función es la que lee el daño impreso real. Solo considera ataques cuyo coste (nº de energías) el rival puede pagar **asumiendo 1 energía adjuntada el próximo turno** (`avail = len(energies) + 1`). Devuelve 0 si el ataque no se puede leer (daño `None`, p. ej. ataques que ponen contadores) — el llamador queda conservador.

Dos modelados específicos:
- **Powerful Hand (proyección anti-Alakazam)**: si el activo rival es Alakazam (743) y el ataque es `POWERFUL_HAND_ATTACK_ID`, el daño impreso es 0 pero el real es 20 × carta en la mano rival. Si el llamador pasa `op_hand_count`, se proyecta `20 × (mano + 2)` (+2 = robo del turno + *Psychic Draw* al evolucionar); sin el parámetro se mantiene el 0 conservador de siempre. Sin este modelado, **todos** los pivotes defensivos (muro Hydrapple, sacrificio de ex frágil, promociones) creían que Alakazam pegaba 0 y nunca disparaban en el matchup donde más se los necesita.
- **Maximum Belt**: si el objetivo (`target`) es un ex nuestro (`OUR_EX_IDS`) y el atacante rival lleva la tool `Maximum_Belt`, se suman +50 **antes** de debilidad/resistencia.

Al final aplica la debilidad/resistencia del **objetivo** frente al tipo de energía del atacante rival (×2 / −30) y devuelve `max(0, int(best))`.

En `agent()`, la proyección de Powerful Hand se inyecta en `estimated_op_damage`/`active_ko_likely` **solo cuando el activo rival es Alakazam** (para no alterar otros matchups), lo que enciende toda la maquinaria de "activo condenado": pivotes defensivos, urgencia de retirada, protecciones (ver memoria "Powerful Hand modelado en defensa"). La función anidada `_op_best_damage_vs` de `agent()` (que estima el golpe rival contra cualquier Pokémon nuestro para lookaheads y pivotes) aplica el mismo bono de `Maximum_Belt` con idéntica condición; y `_op_counter_threat_vs` (también anidada en `agent()`) cubre la variante "contadores de daño" de Powerful Hand para el lookahead de promociones.

### `_attacker_base_damage(...)`

```python
def _attacker_base_damage(attacker_id, target, effective_energy,
                          grass_scale, teal_self_energy, bench_count):
```

Calcula el daño **base** (antes de debilidad/resistencia/inmunidad — de eso se encarga `_our_effective_damage`) de cada atacante propio, codificando las fórmulas de sus ataques principales:
- **Hydrapple ex** (*Syrup Storm*): `30 + 30 * grass_scale` — escala con las energías Grass del campo propio que le pase el llamador.
- **Teal Mask Ogerpon ex** (*Myriad Leaf Shower*): `30 + 30 * (teal_self_energy + len(target.energies))`. **Regla VERIFICADA** con el daño real de 6 registros de partidas: el ataque dice "30 más por cada Energía unida a AMBOS Pokémon Activos", es decir cuenta la energía de nuestro Ogerpon **más la del activo rival** (own 3 + opp 2 → 180; own 4 + opp 2 → 210; own 4 + opp 0 → 150; own 3 + opp 1 → 150 — con la misma energía propia el daño cambia según la del rival, así que no es solo la propia; corrige el error previo "solo energía propia"). `teal_self_energy` ya es la energía efectiva propia; `len(target.energies)` es la del activo rival **o la del objetivo que gusteamos con Boss's** (que pasa a ser el activo y por tanto suma). Las siete copias inline de esta fórmula repartidas por `agent()` (el scoring de ATTACK con `leaf_dmg`, `_pdp_abase`, `_ak_dmg`, `_otml_dmg`, `_pb_dmg` en promoción, `_td_base_now`/`_td_base_after` en el KO de Teal Dance y `_acn_base`) se corrigieron en el mismo lote para usar la fórmula de ambos activos.
- **Tapu Bulu**: fijo `220`.
- **Fezandipiti ex**: fijo `100`.
- **Meganium**: fijo `140`.
- **Dipplin** (*Do the Wave*): `20 * bench_count` — escala con el tamaño de la propia banca.
- **Pinsir**: fijo `100` (código latente: Pinsir ya no está en el `deck.csv` actual).

Cada rama primero comprueba `effective_energy >= req[attacker_id]` usando `ATTACK_ENERGY_REQ`; si el atacante no cumple el requisito, o su `attacker_id` no coincide con ninguno de los casos, devuelve `0`. No contempla las pre-evoluciones (Chikorita/Bayleef/Applin) porque, aunque `_can_attack_eff` las permite, sus ataques son de bajo impacto y no forman parte de `MAIN_ATTACKERS`.

### `_bench_attacker_can_ko(...)`

```python
def _bench_attacker_can_ko(my_state, target, meganium_active, total_grass_field,
                           bench_count, retreat_grass_after, neutral_zone):
```

Recorre **todos los Pokémon de la banca propia** (`my_state.bench`) y comprueba si **alguno**, atacando con su energía actual (sin cambios de turno), podría noquear a `target`. Para cada `bp` en la banca:
1. Descarta `target is None` o sin HP devolviendo `False` de entrada.
2. Calcula la energía efectiva del candidato (`len(bp.energies) * _grass_mult()`).
3. Llama a `_attacker_base_damage` con `grass_scale=retreat_grass_after`, `teal_self_energy` = su propia energía y `bench_count` para el daño base.
4. Si `base > 0`, aplica `_our_effective_damage` con `meganium_active`/`neutral_zone` y compara contra el HP del objetivo: si lo iguala o supera, devuelve `True` inmediatamente (early-return al primer atacante de banca que sirva).

### `_bench_attacker_best_damage(...)`

```python
def _bench_attacker_best_damage(my_state, target, meganium_active, bench_count,
                                retreat_grass_after, neutral_zone,
                                min_body_hp=0):
```

Hermano **no letal** del anterior: en vez de "¿alguien remata?" responde "¿cuánto es lo MÁXIMO que sacaríamos hoy si promovemos a alguien de banca?", devolviendo el mejor daño efectivo (`0` si nadie está listo). Mismo recorrido y mismas fórmulas (`_attacker_base_damage` con `grass_scale=retreat_grass_after` + `_our_effective_damage`), sin el early-return: se queda con el máximo. `min_body_hp` descarta candidatos con menos HP que el umbral, que es como se replica la guarda "no cambiar un ex por un cuerpo peor" del scorer de RETREAT (`main-14`) desde el lado del adjunte.

Existe porque toda la familia de pivotes de retirada exigía KO: cuando el atacante de banca solo puede hacer **chip** (activo rival de 300-400 PV, resistencia Planta, Full Metal Lab), ninguna regla disparaba y el turno se cerraba sin atacar. Lo consume `_attach_enable_retreat_attack` (`main-13`).

Si ningún Pokémon de banca alcanza el KO, devuelve `False`. El parámetro `retreat_grass_after` se reutiliza como `grass_scale` — es decir, se está proyectando el daño de Hydrapple ex **después** de una retirada/cambio de energía, no con el estado actual literal (Syrup Storm baja si el retiro descarta Grass del campo). Esta función es la pieza clave que permite al agente responder "¿me conviene retirar al activo y dejar que la banca remate?" (usada en la evaluación de Boss's Orders y en la puntuación de RETREAT).

### `_grass_unlocks_active_retreat`

Devuelve `(ko, chip)`: **¿una Planta MÁS sobre el ACTIVO paga su coste de retirada y habilita atacar con un cuerpo de banca?** Es el núcleo común de la línea *"Planta al activo → RETIRAR → atacar con el de banca"*, y lo consumen **dos rutas distintas**:

- el **adjunte manual** (`_attach_enable_retreat_ko` / `_attach_enable_retreat_attack`, que además exigen que el adjunte del turno siga libre), y
- las **habilidades de carga** (`_ability_unlock_retreat_ko` / `_ability_unlock_retreat_attack`): *Ripening Charge* adjunta a cualquiera de nuestros Pokémon y **no consume el adjunte manual**, así que la línea sigue viva con `state.energyAttached` ya puesto. Antes ese caso era invisible — las dos banderas del adjunte se apagan con `energyAttached` — y el turno moría sin atacar con el activo bloqueado y un atacante listo mirando desde la banca (registro_014 pasos 137/141 vs Alakazam).

Devuelve `(False, False)` si no hay nada que desbloquear: el activo ya paga su retirada (`e >= rc`), una Planta no le alcanza (`e + _grass_attach_unit() < rc`), o con esa Planta **ataca él** (`_can_attack_eff` → entonces no se retira). El `chip` solo se evalúa si el activo no puede atacar este turno y aplica la guarda "no cambiar un ex por un cuerpo peor" (`min_body_hp`). El Grass del campo tras retirar se aproxima descontando `_retreat_grass_units(rc)` (la retirada descarta cartas enteras).


## Interacciones

- **Con el análisis de amenaza y `plan` (`main-07`)**: esa sección puebla `plan.attacker`/`plan.target`/`plan.attack_index`/`plan.energy` invocando repetidamente `_attacker_base_damage` y `_our_effective_damage` para decidir qué atacante y qué objetivo maximizan el resultado del turno. `estimated_op_damage` y `active_ko_likely` se calculan con `_op_best_damage_vs` (anidada) y, en el matchup Alakazam, con `_op_active_attack_damage_to` pasando `op_state.handCount`.
- **Con la puntuación de energía (`main-10`)**: `_attacker_ready = (plan.attacker >= 0 and not plan.energy)` y `_attacker_ready_with_attach` leen `plan.energy` para saber si conviene priorizar el adjunte de energía sobre otras jugadas.
- **Con Boss's Orders (`main-08`)**: usa `_bench_attacker_can_ko` para valorar si, tras gustear a un objetivo rival concreto, algún Pokémon de banca propio podría rematarlo; y `_attacker_base_damage` con el objetivo gusteado como `target` para que Myriad Leaf Shower cuente la energía del objetivo que subirá al activo (`_boss_dmg_to`).
- **Con RETREAT (`main-14`)**: `_retreat_cards` y `_bench_attacker_can_ko` informan si retirar al activo estancado y promover un atacante de banca produce un KO. Los pivotes defensivos (`_hydra_wall_pivot`, `_fragile_ex_sac_pivot`, `_alakazam_pivot_1prize`) dependen del daño rival proyectado por `_op_active_attack_damage_to`/`_op_best_damage_vs`.
- **Con la Ultra Ball (`main-04`)**: `_ub_engine_refresh_pivot` usa `_attacker_base_damage` + `_our_effective_damage` para verificar que el activo no noquea ni con el adjunte antes de desviar la Ultra Ball al motor Meowth→Lillie's.
- **Con constantes globales (`main-01`)**: depende de `card_table`, `attack_table`, `EnergyType.GRASS`, `EX_IMMUNE_IDS`, `ABILITY_IMMUNE_IDS`, `OUR_EX_IDS`, `OUR_ABILITY_IDS`, `Drednaw`, `Crustle_Fighting`, `Alakazam_ex`, `POWERFUL_HAND_ATTACK_ID`, `Maximum_Belt` y todos los IDs usados como claves en `ATTACK_ENERGY_REQ`.
- **Nota de diseño**: `_grass_mult()` devolviendo siempre `1` mientras `_grass_attach_unit()` devuelve `2` con Meganium ilustra la distinción clave del glosario: la primera opera sobre energía **ya en juego** (que la observación ya dobla), la segunda sobre energía **a punto de adjuntarse** (que aún no ha sido doblada por el motor).

## Reglas derivadas de partidas

- La fórmula de *Myriad Leaf Shower* con **ambos activos** está verificada contra el daño real de 6 registros (comentario dentro de `_attacker_base_damage`); corrige el error previo de contar solo la energía propia y afecta también a las siete copias inline de la fórmula en `agent()`.
- La proyección de *Powerful Hand* en `_op_active_attack_damage_to` nace de la observación de que los pivotes defensivos nunca disparaban vs Alakazam (el modelo creía que pegaba 0).
- El bono de `Maximum_Belt` y la inclusión de `Crustle_Fighting` en `EX_IMMUNE_IDS` provienen de la auditoría estratégica de julio 2026 (tools rivales invisibles; daño fantasma de ex contra el Crustle Fighting).
