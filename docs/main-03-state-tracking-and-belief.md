# main.py — Seguimiento de estado y creencia del mazo (líneas 484–860)

## Rol en el agente

Esta región implementa el sistema de **creencia** del agente: un modelo probabilístico de dónde está cada copia de cada carta de nuestro propio mazo (mano, banca/juego, descarte, premios propios ocultos, o aún en el mazo por robar). El motor de juego (`obs`) solo revela lo que está "boca arriba" — mano propia, cartas en juego, descarte — pero **nunca** el contenido del mazo restante ni de los 6 premios propios. Sin embargo, en Pokémon TCG esa información es deducible por conteo: si sabemos cuántas copias de una carta hay en el mazo (60 en total, conocidas desde `my_deck`) y vamos restando las que aparecen en mano/banca/descarte, lo que "falta" tiene que estar repartido entre el mazo restante y los premios. Cuando el simulador revela el mazo completo (p. ej. al jugar `Ultra Ball`), el agente puede además **fijar exactamente** cuántas copias de cada carta están en premios, porque cualquier copia que no aparece en esa vista completa del mazo (ni en mano/juego/descarte) tiene que estar en los premios.

Este modelo alimenta directamente las heurísticas de probabilidad (`_prob_draw_any`, `_prob_card_accessible`, `_op_disruption_belief`) que otras partes de `agent()` usan para decidir, por ejemplo, si vale la pena jugar `Ultra Ball` buscando una carta que podría estar premiada, o si es razonable esperar un robo de energía la próxima ronda.

## Detalle por bloque

### Constantes de estado y globales (líneas 484–494)

```python
ESTADO_MAZO = "MAZO"
ESTADO_BANCA = "BANCA"
ESTADO_MANO = "MANO"
ESTADO_PREMIO = "PREMIO"
ESTADO_DESCARTE = "DESCARTE"
```

Estas cinco cadenas son las claves de zona usadas como índice interno. El modelo de datos central es:

```python
CARTAS_ACTIVAS_EN_MAZO = {
    card_id: {
        ESTADO_MAZO: int,      # copias que creemos aún en el mazo (sin robar)
        ESTADO_BANCA: int,     # copias en juego (activo o banca; también pre-evoluciones, energías y tools adjuntos)
        ESTADO_MANO: int,      # copias en nuestra mano actual
        ESTADO_PREMIO: int,    # copias que creemos en nuestros premios ocultos
        ESTADO_DESCARTE: int,  # copias en el descarte
    },
    ...
}
```

Para cada `card_id` de nuestro mazo, la suma de los cinco contadores es siempre igual al número de copias de esa carta en el mazo de 60 (invariante que mantienen todas las funciones de esta región). `_cartas_first_scan_done` marca si ya se hizo el escaneo inicial de la partida (mano inicial + campo inicial); `_cartas_prizes_identified` existe como bandera declarada pero **no se usa activamente** en la lógica de reconciliación de premios (`_identify_prizes` se ejecuta en cada turno sin comprobar ni fijar esta bandera, ver más abajo — a propósito, según su propio comentario, para poder autocorregirse). `_cartas_last_turn` guarda el último `turn` observado, usado para detectar el inicio de una partida nueva (reinicio del proceso del agente reutilizando el mismo módulo Python entre partidas).

### `_init_cartas_tracking` (líneas 495–512)

Reinicializa `CARTAS_ACTIVAS_EN_MAZO` a partir de `my_deck` (la lista de 60 IDs del mazo propio, definida antes en el archivo): para cada `card_id` crea (si no existe) la entrada con los cinco contadores en 0 y luego incrementa `ESTADO_MAZO` en 1 por cada aparición del id en `my_deck`. Al terminar, cada entrada tiene todo su conteo en `ESTADO_MAZO` (estado "recién barajado, nada visto todavía"). Se llama una vez a nivel de módulo (línea 511, `_init_cartas_tracking()`) para tener el diccionario listo antes de la primera decisión, y se vuelve a llamar dentro de `_update_cartas_tracking` cuando se detecta el arranque de una partida nueva (turno 1 tras haber visto turnos > 1 previamente, ver más abajo), evitando que la creencia de una partida anterior contamine la siguiente.

### `_move_card_state` (líneas 513–520)

Ayudante atómico: mueve una copia de `card_id` de `from_state` a `to_state` (decrementa el origen, incrementa el destino), solo si hay al menos una copia en `from_state`. Devuelve `True`/`False` según si pudo mover. Es la única primitiva de mutación de `CARTAS_ACTIVAS_EN_MAZO` usada por el resto de la región — garantiza que la suma total por carta nunca cambie (una copia siempre se mueve de una zona a otra, nunca se crea ni se destruye), lo cual es la base de la técnica de "deducción por conteo" que sostiene toda la creencia de premios.

### `_belief_deck_and_prizes` (líneas 521–528)

Recorre todas las entradas de `CARTAS_ACTIVAS_EN_MAZO` y suma, por un lado, todos los `ESTADO_MAZO` (tamaño creído del mazo restante) y por otro todos los `ESTADO_PREMIO` (total de premios propios ocultos creídos). Devuelve la tupla `(deck, prize)`. Es la base para calcular probabilidades sobre el conjunto "mazo + premios", que es exactamente el universo de cartas propias que el agente **no** ve directamente.

### `_prob_draw_any` (líneas 529–553)

Calcula la probabilidad de robar al menos una copia de un conjunto de `target_ids` (acepta un único id o un iterable) en las próximas `draws` cartas robadas **del mazo** (sin contar premios). Usa la fórmula de hipergeométrica complementaria: `P(al menos uno) = 1 - P(ninguno)`, donde `P(ninguno)` se calcula iterativamente multiplicando, robo a robo, la fracción de cartas "fallo" restantes sobre el tamaño de mazo restante (`(miss - i) / (deck - i)`). Ejemplo de uso real (línea 4260): `_prob_energy_draw_soon = _prob_draw_any(Basic_Grass_Energy, draws=2)`, para estimar si el agente robará una energía básica de Planta en las próximas 2 rondas y así decidir si vale la pena arriesgar el turno actual sin adjuntar.

### `_prob_card_accessible` (líneas 554–577)

Calcula la probabilidad de que una carta (`card_id`) sea "accesible" — es decir, que **no** esté prisionera en los premios rivales-propios ocultos —, considerando el universo combinado mazo+premios (`_belief_deck_and_prizes`). Si no quedan copias creídas en mazo ni premios, devuelve 0.0. Si no hay premios ocultos (`prize <= 0`), es 100% accesible (`1.0`). En el caso general calcula `P(todas las copias premiadas)` con la misma técnica hipergeométrica que `_prob_draw_any` pero aplicada al universo mazo+premios y a `copies` (número total de copias creídas fuera de mano/juego/descarte), y devuelve el complemento `1 - p_all_prized`. Esto se usa para ponderar si vale la pena, por ejemplo, jugar una búsqueda (`Ultra Ball`, `Poke Pad`) por una carta específica: si es muy probable que las copias restantes estén en los premios (no accesibles hasta ganarlos), la búsqueda pierde valor.

### `_op_hand_size` (líneas 668–673)

Ayudante trivial y defensivo: devuelve `len(op_state.hand)` protegido con `try/except (AttributeError, TypeError)`, o 0 si `op_state.hand` es falsy/inaccesible. Se usa para estimar cuántas cartas tiene el rival en mano (línea 1525) y alimenta `_op_disruption_belief`.

### `_op_disruption_belief` (líneas 674–686)

Estima la probabilidad de que el rival tenga en mano al menos una carta de "disrupción" (p. ej. un Supporter que rompa el plan del agente), a partir del tamaño de su mano `h = _op_hand_size(op_state)`. Si `h <= 0` devuelve un piso fijo `0.05` (nunca se asume certeza total de que el rival esté vacío de opciones). En caso contrario aplica una aproximación binomial simplificada: asume una probabilidad fija `p_one = 2/40` de que una carta cualquiera del mazo rival sea una carta de disrupción relevante (aproximando el mazo rival a 40 cartas "relevantes" con 2 copias objetivo), calcula `p_none = (1 - p_one) ** h` (probabilidad de que ninguna de las `h` cartas en mano sea de disrupción) y devuelve `1 - p_none`, recortado al rango `[0.05, 0.85]` con `max`/`min`. Nótese que, a diferencia de `CARTAS_ACTIVAS_EN_MAZO`, aquí no hay seguimiento por carta del mazo rival (el agente no tiene esa granularidad de creencia sobre el mazo del oponente) — es una heurística agregada, no una deducción exacta. Ejemplo de uso (línea 2419): `_la_disrupt = _op_disruption_belief(op_state, False)`, para sopesar el riesgo de que el rival responda con una carta de interrupción antes de comprometerse a una línea de juego.

### `_first_turn_scan` (líneas 712–735)

Escaneo único (guardado por la bandera `_cartas_first_scan_done`) que se ejecuta la primera vez que el agente tiene datos de estado (`obs.current`) tras el reparto inicial. Mueve de `ESTADO_MAZO` a la zona correspondiente **todas** las cartas ya visibles en ese momento inicial:
- cada carta de `my_state.hand` → `ESTADO_MANO`;
- por cada Pokémon en `my_state.active + my_state.bench`: el propio Pokémon → `ESTADO_BANCA`, y también sus `preEvolution` (pre-evoluciones asociadas, relevante si el simulador ya modela la pila de evolución), sus `energyCards` (energías adjuntas) y sus `tools` (herramientas adjuntas) → `ESTADO_BANCA` también (es decir, "en juego" cubre tanto Pokémon activo/banca como todo lo adjunto a ellos, sin distinguir sub-zona);
- cada carta de `my_state.discard` → `ESTADO_DESCARTE` (relevante si el mulligan forzó descartes iniciales).

Al terminar marca `_cartas_first_scan_done = True`. Este es el único punto donde el agente "arranca" su creencia desde el estado cero (todo en mazo) hacia el reparto real de la partida; a partir de aquí, los cambios se siguen turno a turno vía logs y sincronización de estado (no se vuelve a barrer todo desde cero salvo reinicio de partida).

### `_area_to_estado` (líneas 736–748)

Traductor puro de la enumeración `AreaType` del simulador (`cg.api`) a las claves de zona internas: `DECK → ESTADO_MAZO`, `HAND → ESTADO_MANO`, `ACTIVE` y `BENCH → ESTADO_BANCA` (unificadas, como en `_first_turn_scan`), `DISCARD → ESTADO_DESCARTE`, `PRIZE → ESTADO_PREMIO`. Devuelve `None` para cualquier otra área no contemplada. Es el puente entre el vocabulario de eventos del motor (`LogType.MOVE_CARD`, con sus `fromArea`/`toArea`) y el vocabulario de creencia del agente.

### `_process_logs` (líneas 749–763)

Recorre `obs.logs` (los eventos ocurridos desde la última observación) y actualiza la creencia **solo para eventos que nos afectan a nosotros** (`log.playerIndex == my_index`):
- `LogType.DRAW`: una carta robada por nosotros — mueve `log.cardId` de `ESTADO_MAZO` a `ESTADO_MANO`. Este es el mecanismo principal por el que las cartas "desaparecen" del mazo creído turno a turno, más allá del escaneo inicial.
- `LogType.MOVE_CARD`: traduce `log.fromArea`/`log.toArea` con `_area_to_estado` y, si ambos son válidos y distintos, mueve la carta entre esas dos zonas internas. Cubre jugar cartas de la mano, adjuntar energías, evolucionar, descartar, etc., en el momento en que el log lo reporta (más fino/temprano que la sincronización de estado del siguiente bloque).

Cada `log` se valida primero con `hasattr(log, 'type')` para tolerar tipos de log heterogéneos, y los campos usados (`playerIndex`, `fromArea`, `toArea`, `cardId`) se comprueban con `hasattr` antes de leerse, siguiendo el estilo defensivo del resto del archivo frente a la variabilidad del `Observation`.

### `_identify_prizes` (líneas 764–799)

Es el mecanismo de **reconciliación de premios ocultos** propiamente dicho, y el corazón conceptual de esta región. Se dispara solo cuando `obs.select.deck` no es `None` y `obs.select.effect` tampoco (es decir, el turno actual es una decisión de tipo búsqueda que muestra parte o todo el mazo, como `Ultra Ball`, `Poke Pad`, `Lillie's Determination`, etc.).

Razonamiento del guard de "vista completa" (comentado extensamente en el propio código, líneas 764–784): `Ultra Ball` siempre revela el mazo entero, así que para ese efecto se reconcilia sin más comprobación. Para cualquier otro efecto, solo se reconcilia si `len(obs.select.deck) == my_state.deckCount` — es decir, si la vista mostrada cubre **todo** el mazo actual y no una porción parcial (p. ej. Bug Catching Set solo muestra las 7 cartas de arriba: `len(select.deck) < deckCount`, y reconciliar con esa vista parcial marcaría erróneamente como premiadas cartas que en realidad siguen en el resto del mazo no mostrado). Si el guard no se cumple, la función retorna sin tocar nada.

Cuando sí hay vista completa, el algoritmo es:
1. Cuenta cuántas copias de cada `card_id` aparecen realmente en `obs.select.deck` → `deck_counts` (un `defaultdict(int)`).
2. Para cada carta trackeada en `CARTAS_ACTIVAS_EN_MAZO`: `total_copies` = suma de sus cinco contadores (invariante, igual al número real de copias en el mazo de 60); `hidden` = `total_copies - ESTADO_MANO - ESTADO_BANCA - ESTADO_DESCARTE` (todo lo que no está en una zona visible ahora mismo, es decir "mazo + premios" desde la perspectiva de esta función, recortado a `>= 0` por seguridad).
3. `ESTADO_MAZO` se fija exactamente al conteo real observado en la vista (`in_deck = deck_counts.get(cid, 0)`).
4. `ESTADO_PREMIO` se fija a `hidden - in_deck` (lo que "falta" respecto a lo visto en el mazo tiene que estar en los premios), recortado a `>= 0`.

El comentario inicial de la función explica la razón de diseño: al no usar un "cerrojo de una sola vez" (a pesar de existir la bandera `_cartas_prizes_identified`, que de hecho no se consulta aquí), la creencia de premios se **recalcula en cada revelación completa** del mazo, por lo que se autocorrige si hubiera algún desajuste anterior, en vez de fijarse una única vez y arrastrar un posible error el resto de la partida.

### `_sync_from_state` (líneas 800–838)

Complementa a `_process_logs`: en lugar de razonar evento a evento, **relee el estado visible completo** (`my_state`) cada turno y corrige cualquier desajuste acumulado. Construye `actual`, un `defaultdict` por `card_id` con los conteos reales de `ESTADO_MANO`, `ESTADO_BANCA` y `ESTADO_DESCARTE` observados directamente:
- mano → `ESTADO_MANO`;
- cada Pokémon en juego (activo/banca) más sus `preEvolution`, `energyCards` y `tools` → `ESTADO_BANCA` (mismo criterio unificado que en `_first_turn_scan`);
- descarte → `ESTADO_DESCARTE`.

Luego, para cada `card_id` ya trackeado en `CARTAS_ACTIVAS_EN_MAZO`: guarda `total_copies` (suma de los cinco contadores, invariante), sobrescribe `ESTADO_MANO`/`ESTADO_BANCA`/`ESTADO_DESCARTE` con los valores reales recién leídos, y calcula `remaining = total_copies - real_mano - real_banca - real_descarte` (recortado a `>= 0`) — lo que debería repartirse entre mazo y premios. Como los premios ocultos no son observables aquí, se preserva lo que ya se creía sobre ellos, pero recortado para no exceder `remaining`: `known_premio = min(entry[ESTADO_PREMIO], remaining)`, y el resto va al mazo: `entry[ESTADO_MAZO] = remaining - known_premio`. Esta función es la razón principal por la que el invariante "suma de los cinco contadores = copias totales" se mantiene robusto incluso si algún evento de `_process_logs` se perdiera o se procesara mal (p. ej. logs no contemplados, robos por efectos especiales sin `LogType.DRAW`): la sincronización desde el estado visible actúa como corrección de "fuente de verdad" en cada turno.

### `_update_cartas_tracking` (líneas 839–860)

Función orquestadora, llamada una sola vez al principio de `agent()` (línea 1306: `_update_cartas_tracking(obs, my_index, my_state)`), antes de cualquier lógica de puntuación. Implementa el ciclo completo:

1. **Detección de partida nueva**: si `obs.current.turn == 1` y el turno anterior recordado (`_cartas_last_turn`) era `> 1`, se asume que ha empezado una partida distinta (el proceso del agente se reutiliza entre partidas) y se llama `_init_cartas_tracking()` para reiniciar la creencia desde cero, junto con el reinicio de los globales de detección de matchup `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_mega_kangaskhan` a `False`. Luego actualiza `_cartas_last_turn = obs.current.turn` incondicionalmente.
2. **Rama de arranque vs. rama normal**:
   - Si `not _cartas_first_scan_done` (y hay `obs.current`): se ejecuta `_first_turn_scan(my_state)` — el escaneo único inicial de mano/campo/descarte descrito arriba.
   - En caso contrario (turnos siguientes): se ejecuta `_process_logs(obs, my_index)` (actualización incremental desde los eventos del turno) seguido de `_sync_from_state(my_state)` (corrección/reconciliación desde el estado visible completo).
3. **Identificación de premios**: en ambos casos, al final se llama siempre `_identify_prizes(obs, my_state)`, que solo actúa si la decisión actual es una búsqueda con vista completa del mazo, como se explicó arriba.

En resumen, el ciclo por turno es: **detectar partida nueva → (escaneo inicial | logs + sync) → reconciliar premios si hay vista de mazo**. El resultado, `CARTAS_ACTIVAS_EN_MAZO`, queda listo antes de que el resto de `agent()` empiece a puntuar opciones, y es consultado profusamente más adelante (ver Interacciones).

## Interacciones

- **Consumidores directos del diccionario**: además de las funciones de probabilidad ya descritas, el bucle de puntuación de `agent()` consulta `CARTAS_ACTIVAS_EN_MAZO` directamente en varios puntos:
  - Línea ~7089–7093: al puntuar el jugar `Ultra Ball` (o similar), si `prized_copies > 0` y `total_copies - prized_copies <= 1` (es decir, casi todas las copias restantes de una carta clave están en premios), sube el puntaje en `+100` — razonamiento: urge buscarla antes de que la única copia accesible se pierda de mano.
  - Líneas ~7471 y ~7999: acceden a `entry = CARTAS_ACTIVAS_EN_MAZO[card.id]` para decisiones de búsqueda similares (contexto de tipo `CARD`/`NUMBER` sobre el mazo, documentado en `main-11-agent-card-search-scoring.md`).
  - Línea ~10399–10400: al construir la lista `searchable` de objetivos válidos para una búsqueda tipo Poke Pad, filtra por `CARTAS_ACTIVAS_EN_MAZO[cid][ESTADO_MAZO] > 0` — solo propone buscar cartas que la creencia dice que siguen físicamente en el mazo (no premiadas), evitando intentos inútiles.
- **`_prob_draw_any`** se usa para decisiones de "¿puedo esperar un turno más a robar X?" (ejemplo real: probabilidad de robar energía básica de Planta en 2 robos, línea ~4260), influyendo en la puntuación de adjuntar energía (`main-10-agent-energy-and-switch.md`).
- **`_op_disruption_belief`** y **`_op_hand_size`** alimentan el análisis de amenaza y las decisiones de Supporters (líneas ~1525, ~2419), documentadas en `main-07-agent-threat-and-plan.md` y `main-09-agent-supporters-and-flags.md` — el riesgo de que el rival tenga una carta de interrupción en mano condiciona si el agente se compromete a una línea de juego agresiva o conservadora este turno.
- **Orden de llamada obligatorio**: `_update_cartas_tracking` debe ejecutarse antes que cualquier otra lógica de `agent()` (se llama en la línea 1306, inmediatamente tras desempaquetar `my_state`/`op_state`), porque todo el resto del archivo asume que `CARTAS_ACTIVAS_EN_MAZO` refleja el turno actual.
- **Reinicio entre partidas**: la detección de "turno 1 tras turno > 1" en `_update_cartas_tracking` es la única salvaguarda contra fugas de estado entre partidas distintas dentro del mismo proceso; comparte el mecanismo con otros globales de matchup (`op_is_crustle_deck`, etc.) que también se reinician ahí mismo, aunque el reinicio general de turno (`pre_turn != state.turn`, para `plan`, `we_go_first`, etc., ver `main-05-agent-setup.md`) es una comprobación distinta y más fina (cambio de turno normal, no de partida).

## Reglas derivadas de partidas

No se encontraron comentarios con referencias a `log 86xxxxxx` dentro del rango de líneas 484–860; las anotaciones de casos concretos de partidas en este archivo se concentran en las secciones de puntuación de opciones (bucle principal de `agent()`), no en el seguimiento de estado en sí.
