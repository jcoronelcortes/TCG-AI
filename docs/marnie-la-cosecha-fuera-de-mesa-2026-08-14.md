# La cosecha fuera de mesa: por qué el paso 150 ya estaba perdido

**Partida**: episodio 92844329, `records/registro_009_pasos_141_hasta_169.json`,
turno 9, contra Marnie's Grimmsnarl ex. **Perdida.**

## El tablero, tal como estaba cuando decidimos

| | |
|---|---|
| **Nuestro activo** | Teal Mask Ogerpon ex, 130/210, **2 Grass** |
| **Nuestra banca** | Meowth ex 40/170 · Meowth ex 70/170 · Teal Mask Ogerpon ex 130/210 (2 Grass) · Fezandipiti ex 210/210 |
| **Nuestros premios** | **2** |
| **Su activo** | Marnie's Grimmsnarl ex, **300/320**, 2 Darkness |
| **Su banca** | Munkidori 70/110 (1 Dark) · Froslass 90/90 · Froslass 90/90 · Munkidori 70/110 (1 Dark) · Marnie's Impidimp 70/70 |
| **Sus premios** | **3** |
| **Mano** | Unfair Stamp · Ultra Ball · Meganium |
| **Mazo** | 21 cartas, con 8 Basic Grass dentro |

El agente **se retiró**: pagó una de las dos Grass del Ogerpon como coste de
retirada y subió al Fezandipiti ex.

## Lo que la mesa valía en realidad

### 1. El remate estaba a UNA Grass

Grimmsnarl ex es **débil a Planta**. Myriad Leaf Shower es
`30 + 30 × (energía de nuestro activo + energía de su activo)`, y la debilidad
lo duplica:

| Grass en el Ogerpon | Base | Con debilidad ×2 | ¿KO sobre 300? |
|---|---|---|---|
| 2 | 0 (no llega al coste 3) | — | no |
| **3** | **180** | **360** | **sí** |
| 4 | 210 | 420 | sí |

Con 3 Grass ganábamos: 2 premios, y nos quedaban exactamente 2.
La Grass no estaba en la mano — pero sí el **Unfair Stamp**, que baraja la mano
y roba 5 de un mazo de 21 con 8 Grass dentro. En la partida real ese Stamp se
jugó **cuatro acciones después de la retirada**, robó la Grass (serial 52) y la
adjuntó a un Ogerpon de la **banca**, porque para entonces el atacante ya no
estaba delante y solo hay una retirada por turno.

### 2. No había mañana que comprar

Con dos Froslass en mesa, Freezing Shroud pone **1 contador por Froslass sobre
cada Pokémon con habilidad** en cada chequeo, y hay **dos chequeos por ronda**:
**40 de daño por ronda** a cada cuerpo nuestro con habilidad (los dos Ogerpon ex,
los dos Meowth ex, el Fezandipiti ex).

El **Meowth ex de 40 PS se muere solo**. Sin que nadie ataque. **Dos premios.**

A eso se suma Adrena-Brain: cada Munkidori cargado mueve hasta **3 contadores**
de un Pokémon suyo a **uno** nuestro. Dos Munkidori = **dos movimientos
independientes** de hasta 30 cada uno — pueden rematar **dos cuerpos distintos**
en el mismo turno, no uno.

La cuenta completa de lo que podían cobrar antes de que volviéramos a jugar:

```
Meowth ex 40 PS   − 40 de goteo                     = muerto   → 2 premios
Ogerpon activo    − 40 de goteo − ataque Grimmsnarl = muerto   → 2 premios
                                              TOTAL   4 premios
```

Necesitaban **3**. **Se retirara el agente o no, perdíamos en su turno.** El
único turno que existía era ese, y la única jugada correcta era la que lo cerraba.

## Por qué el agente no lo vio

Dos ceguera independientes, y ninguna era un error de aritmética:

**`_opponent_reply` proyecta un ataque sobre un cuerpo.** Su activo contra
nuestro activo, nada más. Respondió «2 premios, no cierran» — y era cierto de lo
que miraba. Los otros dos premios no venían de un ataque.

**El pivote de muro contaba turnos que no existían.** `_doomed_mute_pivot` leyó
el activo como MUDO (la Grass no estaba en la mano, y el censo honesto de
`_reachable_grass_for` no cuenta lo que el motor de robo puede encontrar) y
compró lo que compra siempre: tiempo. En un turno sin mañana el tiempo no vale
nada, y la retirada además quemó la energía que el ataque iba a contar.

## Lo que se cambió

### `_op_prize_harvest` — la cosecha, en `ptcg/calc/damage.py`

Una proyección de **cuántos premios pueden cobrar antes de nuestro próximo
turno**, sobre **todos** nuestros cuerpos y desde las tres fuentes a la vez:

* el goteo de Freezing Shroud, que paga todo cuerpo de `OUR_ABILITY_IDS`;
* su ataque sobre nuestro activo, y el snipe automático sobre **un** banquillo
  (se prueba cada asiento: el rival elige);
* Adrena-Brain como **bolsa** de movimientos, no como un solo remate.

La asignación se **busca**, no se estima: nuestra mesa son ≤ 6 cuerpos, así que
se prueba cada subconjunto contra los dos presupuestos (movimientos, y los
contadores que su tablero puede realmente aportar) y gana el que más premios
saca. Eso es «concentran en el de menos vida o en el que da dos premios»
escrito como aritmética en vez de como preferencia.

Publica dos números: `prizes` (todo) y `off_board` (lo que cobran **sin
atacar**). El segundo importa aparte porque **sobrevive a nuestro propio KO**:
el cuerpo que deja de replicar no es el que pone los contadores.

### `TurnPlan.op_prizes_offboard` — el dato, y su consumidor

`op_wins_next` **no** se tocó, y eso es una decisión, no un olvido. Plegar la
cosecha entera dentro lo llevaba de 18 a 88 de las 3580 decisiones del corpus
congelado (0,50 % → 2,46 %), y ese 0,50 % es la licencia que `do_or_die` declara
en su propia docstring: *la maquinaria defensiva de este agente se ha medido
negativa tres veces cuando se la hizo disparar más*. Así que la lectura entra
como dato con **un** consumidor acotado —
`TurnPlan.they_close_it_without_attacking`, que vacía los dos sacrificios de
premio: entregar un cadáver más barato no niega nada cuando cierran sin atacar.

### `_active_closes_with_one_charge` — el veto de la retirada

Los tres pivotes de muro (`_teal_wall_pivot`, `_doomed_mute_pivot`,
`_hydra_wall_pivot`) se apagan cuando el cuerpo de delante está a **una Basic
Grass** del KO **que cierra la partida** y el turno todavía puede encontrarla:

* una **ruta** que ponga la Grass en ese cuerpo (`_grass_attach_slots_for`: el
  adjunte del turno, Teal Dance, Ripening Charge);
* una Grass **alcanzable**: ya en mano, o a través de una carta que cava —
  `GRASS_DIGGER_REACH` nombra cuáles y hasta dónde llega cada una (Bug Catching
  Set, Unfair Stamp y Lillie's al MAZO; Night Stretcher y Lana's Aid al
  DESCARTE), con las Supporter contando solo mientras el hueco siga libre.

El techo está escrito a propósito: el KO tiene que **cerrar** la partida
(`my_prize <= prize_count_op(su activo)`), no bastar con estar disponible. Con
cuatro premios por delante el muro vale lo que siempre valió y el pivote no
cambia.

## El paso 168: por qué no promovió al Ogerpon y ganó

Dieciocho acciones después, al final del mismo turno, el tablero era **ganador**:
dos Teal Mask Ogerpon ex en la banca, uno con 6 energías efectivas (Meganium ya
en mesa), contra el mismo Grimmsnarl ex de 300. Myriad Leaf Shower =
`30 + 30 × (6 + 2) = 270`, ×2 por debilidad = **540**. Cualquiera de los dos
cerraba la partida desde el activo.

No lo hizo, y **no es un fallo de puntuación**: el motor ofreció **una sola
opción** en ese paso.

```
paso 150   retreated=False   opciones: PLAY, PLAY, ABILITY, RETREAT, END
paso 151   retreated=TRUE    (pagando el coste de retirada)
paso 168   retreated=TRUE    opciones: END
paso 169   retreated=TRUE    opciones: END
```

**Un turno tiene UNA retirada.** Gastada en el paso 150 para esconder al Ogerpon
detrás del Fezandipiti, la única puerta al puesto activo quedó cerrada para el
resto del turno. Los dos cerradores estaban a un asiento de distancia y ese
asiento ya no se podía comprar.

Es el mismo defecto, no uno nuevo: el paso 168 es la factura del paso 150.

### La cadena que sí funciona — y que nadie vigilaba

Sondeé la maquinaria general con tableros sintéticos, y las cuatro uniones ya
son correctas hoy: el **tier** de energía corre por delante del de retirada, así
que la carga llega al cerrador antes de gastar la retirada; con el cerrador
listo la retirada se paga; y la promoción sube al cerrador (40546) y no al muro
(259) — salvo cuando ningún cuerpo cierra, y entonces sube el muro.

Pero **nada lo fijaba**: se sostiene por el orden de los tiers y por constantes
de puntuación separadas cuarenta peldaños.
`tests/test_the_turn_has_one_retreat_and_the_closer_gets_it.py` fija las cuatro
uniones. Su arnés está validado por las dos mitades: bajo un mutante que apaga
`_win_ko_active_via_promote` se pone **rojo**, y verde al restaurar.

Ese mutante enseñó además algo que valía la pena escribir: la retirada **se
elige igual** (su puntuación solo cae de 9600 a 3200, que sigue ganando el
tablero). Lo que se derrumba es el PLAN — `win_route` se vacía y el modo baja de
`WIN_NOW` a `RACE`. Un test que se hubiera parado en «se retiró» no habría
vigilado nada; por eso éste afirma la RAZÓN.

## Medición

| Puerta | Resultado |
|---|---|
| `pytest -q` | 2592 pasan (1 fallo previo a este cambio: `test_the_card_census_closes_on_sixty`, un artefacto de `records/`) |
| Corpus congelado (50 partidas, 3580 decisiones) | **sin cambios** |
| Corpus local (11 registros) | **una** decisión volteada: `registro_009` paso 150, `RETREAT` → `PLAY Unfair Stamp` |
| `lint_architecture` | R1–R11 limpias |
| `test_submission` | 7 pasan |

Censo sobre el corpus congelado: `op_prizes_offboard >= 1` en 6 de 3580
decisiones (0,17 %), **todas** en las dos partidas de Marnie.
`they_close_it_without_attacking` no dispara en ninguna — su caso disparado está
fijado en el test, sobre el tablero del registro.

### Self-play

Sin semilla no resuelve un cambio de este tamaño, y lo dice solo: **+0,7 puntos
a n=300 y −1,2 a n=400** contra el mismo bot de Marnie, los dos dentro del ruido
y con el signo cambiado.

Con semilla el resultado es una **aserción**, no una estimación:

```
utils/selfplay.py --games 400 --base HEAD --opponent marnie_grimmsnarl --seeds 400
    candidato 378-22   HEAD 378-22   pasos 53502 / 53502   DELTA +0.0
utils/matchup_matrix.py --games 24 --base HEAD --seeds 24 --weights
    87 de 87 matchups con delta EXACTAMENTE +0.0000, en winrate Y en premios
    ponderado 94,5 % · delta ponderado +0,00 · delta de premios +0,000
```

Los dos brazos juegan **partida por partida idéntica**: el cambio no dispara ni
una vez en las 400 partidas contra el bot ni en los 87 mazos del meta. Eso es
coherente con el censo — su población es un tablero de cola — y es el límite
honesto de la medida: **el instrumento no puede resolver este cambio porque no
alcanza el tablero donde ocurre**.

> ⚠️ **Entra por decisión del usuario, no por el gate.** El cambio mide NEUTRO,
> y la política del proyecto dice que lo neutro se revierte. Lo que lo sostiene
> es el registro: una partida real perdida con el remate exacto en la mano, y el
> corpus dorado probando que la única decisión que cambia es esa. Es la misma
> licencia que `do_or_die` invoca para sí mismo — y el mismo asterisco que
> llevan las rutas de Cornerstone.
