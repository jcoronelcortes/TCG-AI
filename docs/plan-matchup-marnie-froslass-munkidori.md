# Plan de matchup: Marnie's Grimmsnarl ex + Froslass + Munkidori

Analisis de `registros/marnie/partida_1|2|3` (tres DERROTAS) y plan de mejora.
Fecha: 2026-08-02.

> **Estado**: Fases A y B **implementadas** (`_op_chip_per_round`,
> `_op_movable_dmg`, `_ventana_de_regalo`, gate nuevo de `_ripen_heal_serial`,
> `RIPEN_HEAL_EX_ABILITY_SCORE`). Tests en
> `tests/test_marnie_ventana_de_regalo.py`. Fases C, D y E pendientes.
> Ver "7. Lo implementado y lo medido" al final.

---

## 1. El marcador: las tres se perdieron por UN premio

| Partida | Turnos | Premios que tomamos | Premios que tomo el rival | Golpe final |
|---|---|---|---|---|
| 1 | 15 | 5 de 6 | 6 de 6 | Shadow Bullet al Hydrapple ex activo (110 PV) |
| 2 | 13 | 5 de 6 | 6 de 6 | **Munkidori mueve 30 contadores** al Meganium de banca (30 PV) |
| 3 | 7  | 4 de 6 | 6 de 6 | Shadow Bullet al Tapu Bulu promovido |

No perdimos por falta de dano. Nuestro ataque funciono perfectamente: cada
Marnie's Grimmsnarl ex que llego al puesto activo murio de un golpe
(Syrup Storm hizo 540, 900, 1020 y 1260; Myriad Leaf Shower, 420). **Perdimos
la carrera de premios por el goteo**, no por el intercambio de golpes.

### Premios regalados SIN que el rival atacara

| Partida | Cuerpo | Premios | Causa |
|---|---|---|---|
| 1 | Meowth ex (banca) | 2 | Froslass + Munkidori |
| 2 | Teal Mask Ogerpon ex (banca) | 2 | Munkidori x2 (60 contadores) |
| 2 | Meganium (banca) | 1 | Munkidori (**el premio que perdio la partida**) |
| 3 | Teal Mask Ogerpon ex (activo) | 2 | Froslass + Munkidori |

**7 premios de 18** los cobro el rival sin gastar un ataque. En la partida 1
el rival ataco **3 veces en 15 turnos** y aun asi tomo los 6 premios.

---

## 2. El mecanismo del rival, cuantificado

Mazo rival medido en los tres logs (identico en los tres): 3x Grimmsnarl ex,
3x Rare Candy, **2x Froslass**, **4x Munkidori**, 4x Spikemuth Gym, 10 energias
Oscuras.

### Las tres fuentes de dano

1. **Freezing Shroud (Froslass)** — 1 contador (10) a *cada* Pokemon con
   habilidad, de ambos lados, **en cada Chequeo Pokemon**. Hay **DOS chequeos por
   ronda** (al final de nuestro turno y al final del suyo). Con 2 Froslass en
   juego: **40 de dano por ronda a cada cuerpo nuestro con habilidad**.
2. **Shadow Bullet** — 180 al activo + **30 automaticos a un banquillo** que
   elige el rival. Sin debilidad ni resistencia en banca.
3. **Adrena-Brain (Munkidori)** — mueve hasta **30 contadores** desde uno de SUS
   Pokemon a **cualquiera de los nuestros** (activo o banca), una vez por turno
   por Munkidori con energia Oscura. Con 3 Munkidori energizados: **90 de dano
   dirigible** por turno.

La municion de Munkidori es *renovable*: su propio Froslass carga 10 contadores
por chequeo sobre cada Munkidori y sobre el Grimmsnarl ex (todos tienen
habilidad). Es decir, **el rival se auto-abastece de contadores**.

### La ventana de regalo

Dano maximo concentrable sobre UN cuerpo nuestro por ronda:

```
banca : 40 (2 Froslass x 2 chequeos) + 30 (snipe) + 30 x n_Munkidori  = hasta 160
activo: 40 (2 Froslass x 2 chequeos) + 180 (Shadow Bullet) + 30 x n_M = hasta 310
```

Todo cuerpo nuestro **con habilidad** por debajo de ese umbral es un premio
gratis. Lo importante: **Munkidori es elastico**. Si curamos al cuerpo A, el
rival apunta al B. Por eso el objetivo correcto no es "salvar a este cuerpo"
sino **sacar a TODOS nuestros cuerpos de la ventana**, o al menos al de mas
premios.

### Quien SI y quien NO paga el peaje de Froslass

| Con habilidad (paga 40/ronda) | Sin habilidad (paga 0) |
|---|---|
| Teal Mask Ogerpon ex (Teal Dance) | **Tapu Bulu** (140 PV, 1 premio, 220 de dano) |
| Hydrapple ex (Ripening Charge) | Chikorita / Bayleef |
| Meganium (Wild Growth) | Applin |
| Dipplin (Festival Lead) | |
| Meowth ex (Last-Ditch) | |
| Fezandipiti ex (Flip the Script) | |

Esta asimetria es la palanca principal del matchup y hoy el agente la ignora
por completo.

### La otra asimetria: el Tera del Ogerpon **no** protege del goteo

Teal Mask Ogerpon ex en banca previene "todo el dano infligido por **ataques**".
Eso corta el snipe de 30 de Shadow Bullet (verificado: `value: 0` en el log de
la partida 1) pero **NO corta ni los contadores de Froslass ni los que mueve
Munkidori**, que no son dano de ataque. En la partida 2 el Ogerpon de banca
murio con 60 contadores movidos por dos Munkidori. Refugiarlo en la banca no lo
salva.

---

## 3. Diagnostico: cinco defectos, todos reproducibles en HEAD

Todos verificados corriendo el agente actual sobre las observaciones del log.

### D1 — La amenaza a la banca esta modelada en 30 cuando son hasta 160

`_op_bench_snipe_dmg` solo lee `OP_BENCH_SNIPE_DAMAGE[Grimmsnarl_ex] = 30`.
Ignora Freezing Shroud y Adrena-Brain.

Reproducido en `partida_2/registro_010` paso 121 (`_op_bench_snipe_dmg == 30`).
En ese mismo turno el Ogerpon de banca estaba a **80 PV** y murio antes de
nuestro siguiente turno: 20 de Froslass + 60 de dos Munkidori = 80 exactos.

Es la causa raiz de D2.

### D2 — Ripening Charge no cura NUNCA: usamos la curacion 1 vez en 3 partidas

El detector `_ripen_heal_serial` (main.py ~16430) exige que el cuerpo *muera al
golpe proyectado* y *sobreviva con +30*. Con `_rh_thr = _op_bench_snipe_dmg = 30`
para la banca, ningun cuerpo por encima de 30 PV entra jamas al detector.

Balance de los tres logs:

```
Partida 1 : 410 de dano de Froslass encajado — 1 curacion usada (y al cuerpo equivocado)
Partida 2 : 620 de dano de Froslass encajado — 0 curaciones
Partida 3 :  60 de dano de Froslass encajado — 0 curaciones
```

Ademas hay un segundo veto letal: `if _rh_thr >= min(_rh_max, _rh_hp + 30): continue`
("si curar no basta, no cures"). Contra un mazo que reparte 40/ronda a toda la
mesa, ese corte apaga la curacion justo cuando mas hace falta.

**Contrafactual medido** (dano recibido por cada cuerpo desde nuestro turno
anterior, es decir lo que habria que haber prevenido):

| Partida | Cuerpo noqueado | Premios | Dano en la ventana |
|---|---|---|---|
| 2 | **Meganium** (banca) | 1 | **30** ← una sola Ripening Charge lo salva |
| 3 | **Teal Mask Ogerpon ex** (activo) | 2 | **30** ← una sola Ripening Charge lo salva |
| 1 | Meowth ex (banca) | 2 | 50 |
| 2 | Hydrapple ex (activo) | 2 | 80 |
| 2 | Teal Mask Ogerpon ex (banca) | 2 | 80 |

En la partida 2 el premio que decidio el juego (Meganium, 1 premio, con ambos
jugadores a 1 premio) necesitaba **exactamente una curacion de 30**.

### D3 — Apilamos energia sobre cuerpos que estan muriendo

Partida 2, turno 10: el agente actual elige **Teal Dance sobre el Ogerpon de
banca que esta a 80/210 con 8 energias efectivas** (opcion `[23]`), teniendo
disponible la Ripening Charge del Hydrapple activo (opcion `[22]`). Ese Ogerpon
murio ese mismo turno **con 5 energias Planta encima**.

Energias Planta perdidas con cuerpos noqueados (de 13 en el mazo):

```
Partida 1 : 3    Partida 2 : 8  (5 en un solo Ogerpon de banca)    Partida 3 : 4
```

Teal Dance solo se carga **a si misma**, asi que usarla "por el robo" sobre un
Ogerpon de banca condenado convierte el motor de robo en una tuberia de energia
hacia el descarte. Matiz importante: mientras el cuerpo VIVE la energia no se
desperdicia (Syrup Storm escala con la Planta de *toda* nuestra mesa); el
desperdicio ocurre en el KO.

### D4 — Boss's Orders sube al Froslass y despues no lo noqueamos

`values[Boss_Orders] = 850` cuando hay Froslass fuera del puesto activo
(main.py ~12198). **Sin ninguna condicion de KO.**

Partida 1: lo hicimos en el turno 4 y otra vez en el turno 6, con **Tapu Bulu
activo a 0-1 energias**. En ambos casos pasamos el turno sin atacar: gastamos el
Supporter del turno, le regalamos al rival una retirada gratis y el Froslass
siguio poniendo 40 por ronda. Reproducido en HEAD (`registro_004` pasos 43-45:
el agente elige Boss's, elige Froslass, y termina el turno).

El mazo ya tiene la regla "el gusteo de linea exige RELEVO"; la rama de Froslass
y la de Munkidori quedaron fuera.

### D5 — Banqueamos cuerpos-habilidad de 2 premios que no atacan

Meowth ex y Fezandipiti ex en banca son, en este matchup, **2 premios que pagan
40 por ronda a Froslass y no aportan nada tras su primer uso**.

Partida 1: Meowth ex bajado en el turno 2, muerto en el turno 9 **solo de
contadores**, 2 premios, sin que el rival gastara nada. Partida 2: Meowth ex y
Fezandipiti ex ocuparon banca los 13 turnos absorbiendo 40/ronda cada uno, dano
que Munkidori podia redirigir en cualquier momento.

---

## 4. Plan de mejora

Orden por impacto medido. Cada punto trae su criterio de aceptacion.

### Fase A — Percepcion: modelar el goteo (habilita todo lo demas)

**A1. `_op_chip_per_round`** — dano recurrente por ronda a cada cuerpo NUESTRO
con habilidad: `10 * n_froslass_en_juego * 2`. Es 0 si no hay Froslass.
Contarlo tambien sobre nuestro ACTIVO (hoy no se cuenta en ningun sitio).

**A2. `_op_movable_damage`** — alcance de Adrena-Brain:
`30 * n_munkidori_con_energia_oscura`, acotado por los contadores realmente
disponibles en la mesa rival (`sum(maxHp - hp)` de sus Pokemon). Es dano
**dirigible a cualquier cuerpo nuestro**, activo o banca.

**A3. `_ventana_de_regalo(pokemon)`** — sustituye a `_op_bench_snipe_dmg` como
umbral de amenaza:

```
banca  : _op_chip_per_round + snipe_automatico + _op_movable_damage
         (el snipe NO cuenta para Teal Mask Ogerpon ex en banca: Tera lo bloquea)
activo : _op_chip_per_round + mejor_ataque_rival + _op_movable_damage
```

Un cuerpo esta **"en ventana"** si `hp <= _ventana_de_regalo(cuerpo)`.

*Generalizacion*: A1/A2 valen para cualquier mazo con dano recurrente entre
turnos o movible; no atarlos a `op_is_marnie_deck` sino a la presencia de
Froslass / Munkidori en mesa, como ya hacen `op_has_froslass` / `op_has_munkidori`.

**Aceptacion A**: en `partida_2/registro_010` paso 121, `_ventana_de_regalo` del
Ogerpon de banca (80 PV) debe dar >= 80. Fixture nuevo.

### Fase B — Ripening Charge como negacion de premios

**B1. Reescribir el gate de `_ripen_heal_serial`** con dos cambios:

- el umbral pasa a ser `_ventana_de_regalo` (A3), no `_op_bench_snipe_dmg`;
- el objetivo deja de ser "el que muere" y pasa a ser **el que SALE de la
  ventana con +30**, priorizando premios: `ex en ventana > no-ex en ventana`,
  y a igualdad el de menos vida.

**B2. Curacion preventiva acotada.** Cuando *ningun* cuerpo sale de la ventana
con +30 (caso partida 2 turno 10: todos dentro), la habilidad **no se
desperdicia**: se cura al cuerpo de **mas premios** que este en ventana, para
obligar al rival a gastar mas Munkidori en el mismo objetivo. Es el unico caso
en el que se cura "sin garantia", y solo mientras haya >= 1 ex en ventana.

**B3. Prioridad de la habilidad.** `RIPEN_HEAL_ABILITY_SCORE` (31250) hoy pierde
contra Teal Dance de desarrollo cuando el detector no se arma. Con el detector
armado y un **ex en ventana**, la curacion debe ganar a Teal Dance (31500) —
banda propuesta ~31550, siempre por debajo de las bandas letales (41000+) y del
remate ganador. Un robo de una carta no vale 2 premios.

**Aceptacion B**: fixtures `marnie_ripening_salva_meganium_p2_step121` y
`marnie_ripening_activo_en_ventana_p3_step78`; en ambos el agente debe elegir la
Ripening Charge del Hydrapple y dirigir la Planta al cuerpo indicado.

### Fase C — No alimentar cuerpos condenados

**C1. Veto de carga sobre cuerpo en ventana.** Teal Dance y el adjunte manual
sobre un cuerpo que esta **en ventana** y **no ataca este turno** se vetan (o se
degradan por debajo de cualquier alternativa util). Excepcion: si esa carga
completa el coste de ataque de un cuerpo que ataca AHORA, o si es la unica via
de carga viva del turno y hay un remate pendiente.

**C2. Tope de energia por cuerpo en este matchup.** Ningun cuerpo pasa de su
coste de ataque + 1 mientras haya Munkidori en mesa. En la partida 2 llegamos a
**10 energias efectivas** en un Ogerpon de banca; el excedente sobre 3 (coste de
Myriad Leaf Shower) fue puro regalo. Reutilizar el patron ya existente de
`_ogerpon_base_phys_cap` / topes vs Crustle.

**C3. Reparto por supervivencia.** Con varias vias de carga vivas en el turno
(manual + Teal Dance + Ripening Charge), repartir hacia el cuerpo que **saldra
de la ventana**, no hacia el que ya tiene mas energia. La energia rinde igual
para Syrup Storm este en el cuerpo que este — pero solo si el cuerpo sobrevive.

**Aceptacion C**: en `partida_2/registro_010` paso 121 el agente ya no debe
elegir `[23]` (Teal Dance sobre el Ogerpon a 80 PV con 8 energias).

### Fase D — Gustear solo lo que podemos matar

**D1.** Condicionar `values[Boss_Orders] = 850` (Froslass) y `= 750` (Munkidori)
a que **nuestro activo pueda noquear al objetivo este turno**, contando todas
las vias de carga que quedan vivas. Es la misma puerta que ya aplica el gusteo
de linea evolutiva.

Froslass tiene 90 PV: Myriad Leaf Shower con 3 energias en nuestro activo hace
30 + 30*3 = 120; Wood Hammer hace 220. Matarlo es trivial **si hay atacante
listo**; sin atacante listo, el gusteo es peor que no jugar nada.

**D2. Valorar el KO de Froslass por lo que apaga.** Un Froslass menos son
20 de dano por ronda menos **sobre cada uno de nuestros cuerpos con habilidad**
— con 4 cuerpos en mesa, 80 de dano por ronda. Eso vale mas que el premio de 1
que da. El bono de 9000 en `_atk_act_ko` para Froslass (main.py ~11121) es
razonable; lo que falta es que Boss's no dispare sin KO.

**Aceptacion D**: en `partida_1/registro_004` paso 43 el agente NO debe jugar
Boss's Orders (activo Tapu Bulu a 0 energias, ningun atacante promovible).

### Fase E — Higiene de banca contra Froslass

**E1. Contabilizar el peaje al bajar un cuerpo-habilidad.** Con Froslass en
mesa, bajar Meowth ex o Fezandipiti ex a la banca cuesta `20 * n_froslass` de
dano por ronda **y pone 2 premios al alcance de Munkidori**. La regla: solo se
bajan si se cobran ESTE turno (Last-Ditch / Flip the Script) **y** el tablero
puede permitirse el premio (p.ej. no estamos en match point del rival).

**E2. Preferir relleno sin habilidad.** Con Froslass en mesa, Tapu Bulu,
Chikorita, Bayleef y Applin son bancas de coste cero frente al goteo. **Tapu
Bulu es la pieza clave del matchup**: 140 PV, 1 premio, sin habilidad, y
Wood Hammer (220) noquea al Grimmsnarl ex por debilidad Planta (440) sin
exponernos a un cuerpo de 2 premios.

**E3. Cadena Applin -> Dipplin -> Hydrapple ex el mismo turno con Forest of
Vitality.** Applin (40 PV) muere al snipe de 30 + un contador; dejarlo un turno
en banca es un premio regalado (partida 3). Forest of Vitality permite evolucionar
Pokemon Planta el turno en que se juegan, asi que la linea entera puede montarse
en un turno. Ojo: el rival juega **4x Spikemuth Gym** y nos quita el Forest cada
turno, asi que la ventana es de un solo turno — hay que reservar las piezas.
La evolucion ademas sube los PV maximos sin borrar contadores, lo que **saca al
cuerpo de la ventana** igual que una curacion.

**E4. El ancla del matchup: Hydrapple ex.** 330 PV, sin habilidad de Froslass que
lo mate rapido, y su Ripening Charge es nuestra unica curacion. En la partida 3
nunca lo montamos y perdimos en 7 turnos. Prioridad de busqueda (Ultra Ball /
Bug Catching Set / Dawn) vs Marnie: **linea Hydrapple > Meowth ex**.

---

## 5. Lo que este plan NO promete

**Ripening Charge no gana la carrera de atricion por si sola.** Cura 30 por
turno; dos Froslass reparten 40 por ronda **a cada** cuerpo con habilidad. La
curacion solo compra tiempo. El plan gana premios por tres vias, en este orden:

1. **matar los Froslass** (D1/D2) — apaga la fuente, no el sintoma;
2. **reducir la superficie** (E1/E2) — menos cuerpos con habilidad, menos peaje;
3. **negar el premio concreto** (B1/B2) — sacar de la ventana al cuerpo de mas
   premios.

Y sin perder el foco: **la regla de tener un atacante activo y otro en banca es
inviolable**. Ninguna de las reglas C1/C2/C3 puede vetar la carga que arma al
atacante del turno ni la que arma al de repuesto; el veto solo alcanza a la
energia **excedente** sobre cuerpos que no atacan.

---

## 6. Como medirlo

1. **Fixtures de decision** (`tests/fixtures/`), uno por criterio de aceptacion.
   Baratos y deterministas; entran en el corpus dorado.
2. **Diferencial de matchup**:
   `python utils/selfplay.py --partidas 400 --rival deck/rivales/marnie_grimmsnarl.csv --base HEAD`
   El mazo rival del repo tiene 4 Froslass y 4 Munkidori (mas agresivo que el de
   los logs, que trae 2 y 4) — conviene ademas un CSV que replique el de los logs
   (3x Grimmsnarl, 3x Rare Candy, 2x Froslass) para no sobreajustar.
3. **Gate global**: `python utils/selfplay.py --partidas 400 --base HEAD` mas la
   matriz de matchups, para confirmar que las reglas nuevas (que se activan por
   presencia de Froslass/Munkidori, no por matchup completo) no rompen nada.
4. **Frecuencia de disparo antes que winrate**: por cada regla, contar cuantas
   veces cambia la decision en el corpus. Una regla que dispara 0 veces es
   INERTE y no se mide por winrate.

---

## 7. Lo implementado y lo medido (Fases A y B)

### Codigo

| Pieza | Donde |
|---|---|
| `FREEZING_SHROUD_COUNTER`, `CHECKUPS_PER_ROUND`, `ADRENA_BRAIN_MOVE` | bloque "LA VENTANA DE REGALO", junto a `OP_BENCH_SNIPE_DAMAGE` |
| `_op_chip_per_round`, `_op_movable_dmg` | globals; se recalculan en el escaneo del campo rival |
| `_ventana_de_regalo(pokemon, es_activo, golpe, incluir_movible=True)` | junto a `_ripen_energy_capped` |
| gate nuevo de `_ripen_heal_serial` + `_ripen_heal_ex` | detector de curacion |
| `RIPEN_HEAL_EX_ABILITY_SCORE = 31550` | banda de la habilidad cuando el cuerpo salvado es un ex |

Una correccion importante frente al plan original: el dano movible es
**ELASTICO**, asi que medir siempre con el techo (`golpe + goteo + movible`)
dejaba a media mesa "condenada" y volvia a apagar la curacion — el mismo fallo
que medirla solo con el snipe, en espejo. Por eso `_ventana_de_regalo` distingue
la ventana **GARANTIZADA** (lo que llega si o si) de la **COMPLETA**, y el
detector ordena en dos grados: salir de la completa (el rival no puede matarlo)
antes que salir de la garantizada (le obliga a gastar el Adrena-Brain, que solo
alcanza a un cuerpo). Despues, premios, menos vida y banca antes que activo.

### Medicion

- **Frecuencia de disparo**: 7 flips en 202 decisiones nuestras sobre los tres
  logs (3.5%). No es inerte. Los flips relevantes:
  - **P2 paso 121** (el caso medido): antes Teal Dance sobre el Ogerpon ex de
    banca a 80 PV que murio ese turno; ahora Ripening Charge. Idem pasos 123/125.
  - **P1 pasos 149/151/163**: usa Ripening Charge antes de atacar. Verificado
    que el ataque NO se pierde: quitando la habilidad del menu el agente elige
    `attackId 195` (el Syrup Storm que noquea). Es un reordenado, no un cambio
    de jugada.
  - **P1 paso 64**: deja de jugar Boss's Orders (el gusteo de Froslass sin
    atacante listo, defecto D4) y juega Xerosic's Machinations. Flip incidental
    en la direccion correcta, pero **conviene revisarlo** al abordar la Fase D.
- **Suite**: 902 pasan. El unico fallo (`test_dragapult_no_bajar_tapu_bulu::
  test_replay_fiel...`) es PREVIO y ajeno: busca
  `registros/registro_003_pasos_018_hasta_056.json`, que ya no existe porque
  `registros/` se reemplazo con las carpetas de marnie.
- **Corpus dorado**: no se pudo correr por la misma razon (no quedan registros
  sueltos en `registros/`).
- **Self-play**: ver la seccion 8. Con el harness viejo salia neutro POR
  CONSTRUCCION (el bot no usaba habilidades); con el harness arreglado sigue
  saliendo neutro, y ahi si es un resultado.

---

## 8. El harness: `BotRival` ya usa habilidades

Hasta 2026-08-02 `utils/bot_rival.py` decia en su propio docstring *"Nunca
RETREAT ni ABILITY"*. El bot **jamas activaba Adrena-Brain**, justo el motor que
cobro 5 de los 7 premios gratis de los logs, asi que cualquier regla contra ese
motor salia NEUTRA por construccion. Arreglado:

- **ABILITY** entra en el menu entre PLAY y ATTACK, con guardas anti-bucle (una
  activacion por Pokemon y por turno + `MAX_HABILIDADES_POR_TURNO`). Esa era la
  razon declarada para excluirlas.
- **Mover/poner contadores** (Adrena-Brain y familia): origen = el cuerpo propio
  mas danado; cantidad = la **MAXIMA** ofrecida (el fallback generico cogia el
  minimo: 1 contador, 10 de dano); destino = el cuerpo rival que **muere** con
  esos contadores, a mas premios mejor, y si ninguno muere el de menos vida.
- **ATTACH**: al activo, salvo que el activo ya tenga energia y haya un cuerpo
  con habilidad **condicionada a energia** todavia seco (se detecta por el texto
  `"Energy attached"` de `skills`, sin cablear ids). Sin esto Munkidori nunca se
  encendia y Adrena-Brain no llegaba a existir.

Verificado: en 8 partidas el bot activa 26 habilidades y mueve **250 de dano**
con Adrena-Brain sobre nuestros cuerpos bajos (Ogerpon ex a 20, Meganium a 10,
Fezandipiti ex a 30) — el mecanismo de los logs. Sin forfeits ni topes de pasos
contra dragapult / crustle / alakazam / comfey / iron_thorns.

**Consecuencia**: el nivel absoluto del bot baja (~94% -> ~90.5% en el matchup
Marnie). Los **deltas** entre versiones de main.py siguen siendo comparables
(ambos lados juegan contra el mismo bot), pero **los winrates absolutos
historicos ya no lo son**.

### Y con el harness arreglado, Fase A+B mide NEUTRO

| Version | Winrate vs bot+marnie (n=600) |
|---|---|
| Con la ventana de regalo | 90.3% [87.7-92.4] (542/600) |
| Sin el cambio | 90.5% [87.9-92.6] (543/600) |

Una partida de diferencia. En 120 partidas instrumentadas la regla **si** cambia
el juego — 85 curaciones frente a 71 (+20%) y 75.670 frente a 79.120 de
contadores encajados (-4,4%) — pero eso son **0,7 curaciones por partida**: la
habilidad exige Hydrapple ex en juego, Planta en mano, ningun remate pendiente y
un cuerpo que salga de la ventana con +30. Dispara demasiado poco para mover el
marcador.

Es exactamente lo que anticipaba la seccion 5: **curar no gana la carrera de
atricion**. Arregla las decisiones concretas que perdieron las partidas 2 y 3
(los 7 flips lo confirman), pero el volumen esta en las otras dos vias:

1. **Fase D — matar los Froslass**: cada Froslass que cae son 20 por ronda menos
   sobre CADA cuerpo nuestro con habilidad. Con 4 cuerpos en mesa, 80 por ronda.
2. **Fase E — reducir la superficie**: cada cuerpo-habilidad que no bajamos son
   40 por ronda que el rival no reparte y 1-2 premios que Munkidori no alcanza.

Ese es el siguiente trabajo, y ahora hay con que medirlo.

---

## 9. Fase D implementada, y el limite de lo que se puede medir

### D1: el gusteo APAGAFUEGOS exige KO

Las ramas de Froslass (850) y Munkidori (750) marcan ahora `_bo_apagafuegos`, y
mas abajo -- ya con `_boss_dmg_to` disponible -- se **revoca el Boss's a 0** si
nuestro activo no noquea a esa pieza este turno. Se revoca ANTES de las subidas
por remate, asi que un `_bo_win_via_bench` sigue pudiendo levantarlo por sus
propios motivos.

Efecto en los logs: los DOS gusteos desperdiciados de la partida 1 (turnos 4 y
6, Tapu Bulu activo a 0 energias, turno terminado sin atacar) pasan a jugar
**Xerosic's Machinations**. Total con A+B: **8 flips en 202 decisiones (4%)**,
todos revisados uno a uno.

### La medicion: NEUTRO, y con el harness al limite de su potencia

El winrate no tiene potencia aqui: el bot gana ~9% de las partidas, asi que
un punto de diferencia son ~8 partidas de 800. Por eso se midio ademas la
magnitud que las reglas atacan directamente — **premios cedidos por partida** y
cuantos de ellos llegan **sin que el rival ataque** — que tiene mucha menos
varianza. Cuatro variantes, mismo bot, n=700 por brazo:

| Variante | Victorias | Premios cedidos | De ellos sin ataque | Curaciones |
|---|---|---|---|---|
| A+B+D (`main.py`) | 91.3% | 2.36 | 1.53 | 610 |
| Solo A+B | 89.6% | 2.60 | 1.69 | 618 |
| Solo D | 90.6% | 2.54 | 1.70 | 376 |
| Nada | 91.3% | 2.49 | 1.59 | 401 |

**El orden se invierte entre tiradas.** Una pasada previa con n=250 daba
exactamente la clasificacion contraria (A+B+D el PEOR con 2.82 premios cedidos,
"nada" el mejor con 2.39). Con el orden volteandose al cambiar la muestra, la
lectura honesta es que **no hay efecto medible ni a favor ni en contra**. Sin
colateral en otros matchups (dragapult 97.6 vs 98.8, crustle 64.0 vs 64.8,
alakazam 99.6 vs 100.0 con n=250: 1-3 partidas de diferencia).

### Por que se conservan

No son inertes (8 flips) ni miden negativo, y arreglan decisiones concretas y
verificables de partidas reales:

- partida 2 turno 10: Teal Dance sobre un Ogerpon ex que murio ese mismo turno
  con 5 Plantas encima, teniendo la curacion disponible;
- partida 1 turnos 4 y 6: Boss's Orders quemado en un Froslass que no podiamos
  tocar, y turno terminado sin atacar.

Pero conviene decirlo sin adornos: **no hay evidencia agregada de que ganen
partidas**. Si aparece una medicion negativa consistente, revertir es barato
(los tres hunks estan aislados).

### El techo del harness

El bot generico gana ~9%: no monta Rare Candy con criterio, no gustea, no
secuencia. Las tres partidas de `registros/marnie` las perdimos contra un rival
que si hacia todo eso. Mientras el rival de referencia sea tan debil, **ninguna
regla fina de este matchup va a mover el marcador de forma medible**, porque las
partidas ya estan ganadas o perdidas por margenes mucho mayores. La siguiente
inversion con mas retorno no es una regla mas: es un rival de referencia que
juegue el mazo Marnie de verdad. **Hecho en la seccion 10.**

---

## 10. El rival de referencia, a fondo — y el veredicto

### El mazo no era el de los logs

`deck/rivales/marnie_grimmsnarl.csv` **no tiene Rare Candy ni Boss's Orders**
(4x Froslass, 4x Munkidori, 4x de cada pieza de la linea, y ningun acelerador).
El mazo de las tres partidas si: 3x Rare Candy, 2x Boss's Orders, 2x Froslass,
3x Grimmsnarl ex, 10 Oscuras. Sin Rare Candy el Grimmsnarl ex llega tardisimo y
media amenaza no ocurre.

Nuevo `deck/rivales/marnie_grimmsnarl_log.csv`: las 60 cartas exactas extraidas
del primer paso de los registros (los tres mazos son identicos entre si).

### El bot, ademas de habilidades

Sobre lo de la seccion 8, `utils/bot_rival.py` gana cuatro piezas mas:

- **RETREAT** cuando el activo no tiene NINGUN ataque disponible. Sin esto un
  cuerpo gusteado se quedaba clavado delante para siempre y cualquier gusteo
  rival, aunque no rematara, ganaba la partida solo — justo el escenario que la
  Fase D evita, medido contra un bot que no sabia castigarlo.
- **EVOLVE** por etapa: Fase 2 antes que Fase 1 y, a igualdad, la del activo.
- **ATTACK** por dano EFECTIVO contra el defensor (debilidad x2), no impreso.
- **Elegir activo**: promocion/retirada al cuerpo con mas energia; y el objetivo
  de GUSTEO (un SWITCH sobre la banca rival) al que se puede NOQUEAR, a mas
  premios mejor.

Verificado en 40 partidas contra el mazo del log: 141 retiradas, 148
habilidades, 34 Boss's jugados y el Grimmsnarl ex evolucionando ya en el turno
3. Tests en `tests/test_bot_rival.py` (13).

### Veredicto: A, B y D no miden

Cuatro mediciones independientes contra el mazo fiel y el bot fuerte:

| n por brazo | A+B+D | Solo A+B | Nada |
|---|---|---|---|
| 800 (1a) | 1.49 px / 0.46 sin ataque | 1.47 / 0.45 | 1.68 / 0.64 |
| 800 (2a) | 1.64 / 0.61 | 1.64 / 0.67 | 1.72 / 0.62 |
| **1500** | **1.72 / 0.65** | — | **1.76 / 0.66** |

La primera tirada parecia una mejora clara (-28% de premios cedidos sin ataque).
**No replico.** Con n=1500 por brazo — la muestra mas grande y limpia — la
diferencia es 0.04 premios por partida y 0.01 en los cedidos sin ataque, con el
winrate a 96.3% frente a 96.4%. Es cero.

Conclusion firme: **A, B y D no tienen efecto agregado medible**, ni siquiera
contra un rival que si ejecuta el motor. Se conservan porque arreglan decisiones
que estan mal por si mismas (los 8 flips) y porque nada mide negativo, pero no
son una mejora de winrate y no hay que venderlas como tal.

Lo que si queda como mejora permanente es el **harness**: un rival que usa
habilidades, se retira, gustea y evoluciona con criterio, y un mazo Marnie fiel
al de las partidas. Cualquier trabajo futuro en este matchup — empezando por las
Fases C y E, que siguen pendientes y sin escribir — se mide ahora contra algo
que se parece al rival real.

---

## 11. Fases C y E: lo implementado, lo rechazado y lo medido

Ciclo 2-ago-2026. Se cierran las dos fases que quedaban.

### C — no alimentar a un cuerpo condenado (implementado)

`_cuerpo_condenado(pokemon, active)` + techo `SCORE_CARGA_CONDENADA` (20),
aplicado en un **ENVOLTORIO** de `energy_score`.

Tres cosas que no estaban en el plan y que decidio el codigo:

1. **El tope "coste de ataque + 1" de C2 NO se implementa: su premisa es falsa.**
   El plan dice que en el Ogerpon de banca con 10 energias "el excedente sobre 3
   fue puro regalo". No lo es: `_attacker_base_damage` -- verificado contra el
   dano REAL de seis registros -- calcula *Myriad Leaf Shower* como
   `30 + 30 x (energia propia + energia del activo rival)`, y *Syrup Storm* como
   `30 + 30 x` la Planta de TODA nuestra mesa. Un Ogerpon con 8 energias pega
   270+; no esta sobrecargado. Lo que convierte la energia en regalo no es el
   exceso sino el **KO**, exactamente como dice el propio D3 del plan ("mientras
   el cuerpo VIVE la energia no se desperdicia; el desperdicio ocurre en el KO").
   Un tope por sobrecarga habria sido un nerf de dano disfrazado de higiene.

2. **La ventana se mide COMPLETA aqui y GARANTIZADA en la curacion.** No es una
   inconsistencia: son dos apuestas con coste distinto. Un falso positivo de
   Ripening Charge gasta la habilidad entera en un cuerpo que moria igual; un
   falso positivo aqui solo desvia la Planta a otro cuerpo NUESTRO -- y para
   Syrup Storm da lo mismo donde caiga. Falso positivo casi gratis, falso
   negativo = un premio.

3. **El techo va en un envoltorio, no al final de `energy_score`.** Puesto al
   final del cuerpo de la funcion disparaba **0 veces**: `_energy_score_base`
   tiene ~60 `return` repartidos (topes por matchup, bandas de banca a 0,
   pivotes de retirada) y la cola generica es una rama minoritaria. El
   envoltorio es el unico punto por el que salen todas. Solo capa por DEBAJO de
   `SCORE_CARGA_LETAL_FLOOR` (41000): la banda letal es energia que cobra o
   niega un premio HOY y ahi el cuerpo no muere sin haber pagado.

**Criterio de aceptacion del plan**: el paso 121 ya no elige `[23]` -- pero eso
ya lo arreglaron las Fases A y B; hoy elige `[22]` (Ripening Charge) con y sin la
Fase C. Lo que la Fase C cambia en ese tablero es el DESTINO de la Planta: el
Meganium a 90 PV (17000, dentro de la ventana) deja de ser el objetivo y la
recibe el Ogerpon ex de 130 PV.

### E — higiene de banca

**E1 (implementado):** Fezandipiti ex se une a la lista de matchups donde no se
baja por desarrollo -- ahora tambien `op_has_froslass`. Con Froslass en mesa son
2 premios CON habilidad que pagan 20 por ronda sin que el rival gaste nada.
Conserva las dos salidas que ya tenian Lucario/Crustle/Cornerstone/Sylveon: se
baja si *Flip the Script* esta viva (se cobra HOY) o si la banca esta VACIA
(donde un KO al activo es la derrota). Meowth ex ya estaba protegido.

**E2 (medido e INERTE, no se implementa):** un bono de desempate de 500 al
relleno que no paga peaje cambio **0 decisiones**, en los 929 pasos de los
registros y en los sondeos sinteticos. Entre nuestros Basicos no hay pareja que
compita de verdad en la banda de desarrollo: Meowth ex y Fezandipiti ex los
deciden sus propios motores (>21000, y ambos ya gateados por Froslass) y el
unico rival de Tapu Bulu es un 2o Ogerpon ex, que puntua muy por encima de un
desempate. Se aplica el criterio de la seccion 6.4.

**E3 (implementado):** un Applin recien bajado tiene **40 PV** y NO tiene
habilidad, asi que no paga el goteo de Froslass -- pero el snipe automatico (30)
mas **un solo** contador movido por Adrena-Brain ya lo matan. Con la ventana
capaz de cobrarlo y sin poder evolucionarlo este turno (`_applin_evolvable_now`
= Forest EN JUEGO + Dipplin en mano), el basico no se baja: se **reservan las
piezas** hasta poder encadenar Applin->Dipplin->Hydrapple ex de una vez. Misma
forma que los vetos de Mega Starmie y Dragapult que ya vivian en esa rama; lo
que cambia es que el umbral sale de la VENTANA y no de una lista de mazos. Sin
Munkidori en mesa `_op_movable_dmg` es 0, el snipe pelado no llega a los 40 PV y
la regla no se enciende.

**E4 (probada y NO implementada), y el motivo importa.** Sumar un disyuntor
"ancla Hydrapple" a `_dipplin_priority` **si** hace efecto -- sube el fetch de
Dipplin de 150 a 800 -- pero **no decide nunca**: 0 flips en los 929 pasos y 0
tambien en el escenario sintetico fabricado para ella. La traza lo explica:
`cede_a_dipplin_prioritario` (10) vive al FINAL de `_REGLAS_UB_MEOWTH`, por
detras de `hydra_muerto_prefiere_meowth` / `meganium_muerto_prefiere_meowth` /
`sin_atacante_prefiere_meowth` (1000-1250), que es justo la familia que dispara
en los tableros de este matchup.

O sea: **el hook real de E4 no es `_dipplin_priority`, es esa familia** -- y
darle la vuelta es un INTERCAMBIO, no un arreglo. Esas reglas dicen "si la
evolucion no aporta hoy y no hay atacante, refresca", cada una con su registro
detras; E4 dice lo contrario apoyandose en UNA partida (la 3). Con el winrate
saturado el harness no puede arbitrar ese intercambio, asi que no se cambia a
ciegas. Si alguien lo retoma: el experimento es capar esa familia cuando la
ventana esta viva y la linea Hydrapple sigue incompleta, y medirlo por **premios
cedidos**, no por winrate.

### Medicion

| | flips en registros | selfplay vs log (n=3000/brazo) | vs csv agresivo (n=3000/brazo) |
|---|---|---|---|
| C1 + E1 + E3 | **2** de 929 | 96.7% vs 96.1% control | 90.8% vs 90.8% control |

Los dos flips son correctos:

- `partida_1` paso 172 (C1): la Planta deja de ir a un Meganium a **30/160**
  (ventana = 20 de goteo + 30 dirigibles) y va al Ogerpon ex **intacto**.
- `partida_1` paso ~116 (E3): con dos Froslass y un Munkidori cargado enfrente,
  deja de bajar un Applin pelado y juega el Unfair Stamp.

La frecuencia de la PRECONDICION de C1 es alta -- el 24% de los cuerpos puntuados
(369 de 1538) esta dentro de la ventana en los turnos con goteo --, asi que la
regla no esta dormida: es que los tres registros tienen pocos ATTACH con la mesa
ya desarrollada.

El winrate es **NEUTRO**, igual que A/B/D. **Calibracion del ruido**, medida sin
querer y util para leer esta tabla: contra `dragapult.csv` -- un mazo que **no
lleva ni Froslass ni Munkidori**, asi que los dos brazos son codigo
BEHAVIORALMENTE IDENTICO -- la misma comparacion dio **97.3% vs 96.3%** con
n=1500. Un punto entero de diferencia entre dos agentes que juegan igual: ese es
el suelo de ruido del simulador, y el +0.6 de la tabla esta muy por debajo.

**Contencion**: de los 17 mazos de `deck/rivales/`, solo los dos de Marnie llevan
Froslass o Munkidori (ids 104/112), asi que ninguna otra medicion de matchup
puede moverse. Tests: `tests/test_marnie_fase_c_y_e_higiene_de_banca.py` (9, con
grupo de control en cada uno).

> **Actualizacion (ago 2026) — esa contencion ya NO se sostiene contra el meta
> real.** Medido sobre el top-100 del leaderboard (`decks_competidores/`):
>
> - **Froslass (104) si es exclusiva de Marnie**: 49 de 49.
> - **Munkidori (112) NO lo es**: esta en 55 de los 100 mazos, y 6 de ellos no
>   son Marnie -- los **cinco** mazos Dragapult del top-100 lo llevan, mas un
>   Crustle.
>
> Consecuencia practica: tocar la ventana mueve tambien el matchup **Dragapult**,
> asi que ya no vale leer un cambio de esta familia solo por los mazos de Marnie.
> El corpus `deck/rivales_reales/` (con sus pesos de meta) es el que hay que usar
> para medirlo.
>
> El codigo no necesito cambio: la ventana se calcula desde las CARTAS en mesa,
> no desde el arquetipo, asi que ya trataba bien esos mazos. Lo que faltaba era
> fijarlo -- `tests/test_marnie_ventana_de_regalo.py` incluye ahora tres casos
> con rival **Dragapult**. Ojo con el matiz que sale ahi: Adrena-Brain solo mueve
> contadores que YA existen, y sin Froslass que los fabrique la unica municion es
> el dano que hayamos puesto nosotros. Con el tablero rival intacto el movible es
> **0, y eso es correcto** -- es la diferencia real entre Marnie (municion
> renovable) y un Dragapult que simplemente lleva Munkidori.
