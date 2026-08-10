# La segunda noche del 9-10 de agosto — las tres preguntas que la corrida completa dejó abiertas

**La ejecutas tú.** Este documento es la tarea, no un informe.

`docs/night-plan-2026-08-10.md` era la corrida completa, y se gastó de día:
`utils/nightly.py --full` terminó a las 15:52 con 28 etapas, 1 h 38 min, cero
FALLO y cero INVÁLIDO. Esa noche ya está hecha. Lo que sigue no es repetirla más
grande: es **lo que aquella corrida preguntó y no pudo contestar con la muestra
que tenía**.

---

## 0. Qué dejó abierto, en tres frases

1. **El residuo del oráculo reproduce y sigue sin explicación.** 2 303 hallazgos
   sobre 165 104 ataques juzgados (1,39 %), contra 2 351 y 1,42 % la noche
   anterior. Medido dos veces, estable — y medido **solo contra los 19 mazos
   sintéticos** de `deck/opponents`.
2. **`crustle_wall` es la familia débil.** 18 listas reales, media 76,6 %, peor
   54,5 %, contra una media global de 91,4 % y ninguna otra familia por debajo
   de 87 %. Y `crustle_wall_6`, a 54,5 %, está **18 puntos por debajo de su
   propia familia**, no solo del resto del meta.
3. **1 698 decisiones dependientes del orden (0,67 %)** que nadie ha mirado una
   por una. Es la única etapa que salió en HALLAZGOS y su volcado nunca se ha
   triado.

**Y un cruce que conviene leer antes de lanzar nada.** `festival_lead` tiene el
**mayor** residuo del oráculo — 885 hallazgos, el 5,2 % de sus ataques juzgados,
casi cuatro veces la tasa global — y a la vez gana el **97,1 %** de sus
matchups. El residuo, por sí solo, **no predice perder**. `crustle_wall` es el
único sitio donde los dos instrumentos señalan a la vez, y por eso es el objetivo
de esta noche y no `festival_lead`.

---

## 1. Antes de lanzar — 3 minutos, y el primero no es opcional

**El árbol está sucio ahora mismo y no lo he tocado.** A las 16:56 había una
regla a medio escribir:

```
 M ptcg/cards/ids.py            SCORE_EVO_CONDITION_UNLOCK = 34000
 M ptcg/turn/options/evolve.py  la evolución que despierta al activo
```

Hay otra sesión trabajando en el mismo árbol (`tcg-ai-09`). **Decide qué mide la
noche antes de arrancarla**: commitea la regla, o guárdala con `git stash`. Lo
que haya en el árbol a la hora de lanzar es lo que se mide durante dos horas y
media, y una regla que aterriza a mitad significa que B1 y B2 midieron **dos
agentes distintos** y ninguno de sus dos números compara con el otro.

No es el peligro de la otra noche —esta corrida no ejecuta el gate de mutación,
así que nadie va a reescribir ficheros en disco—; es el peligro peor de que los
números salgan bien y no se sepa de qué.

Con el árbol ya decidido:

```bash
cd "/Users/jcoronel/Desktop/VS Proyectos/TCG AI"
git status --short           # que diga lo que quieres que diga
git log --oneline -1         # apunta el hash: todo se mide contra él
python utils/nightly.py --quick --since HEAD~1      # ~40 s
```

El `--quick` tiene que terminar sin FALLO y **sin INVÁLIDO**. Un INVÁLIDO
significa que un detector no puede validarse a sí mismo, y entonces sus números
de esta noche no valdrían nada.

---

## 2. El comando de la noche

```bash
bash utils/noche_2026-08-10.sh 2>&1 | tee log/noche_10ago_b.txt
```

Todo lo que produce vive bajo `log/noche_2026-08-10/`: un log por bloque, un
`RESUMEN.txt` con el código de salida y el tiempo de cada uno, y los volcados.
Ningún bloque puede parar la noche — el que falle deja su log y el siguiente
arranca.

Palancas, por si quieres una noche más corta o relanzar solo una parte:

```bash
SOLO=B2,B3 bash utils/noche_2026-08-10.sh          # solo esos bloques
CENSO_GAMES=150 MONITOR_GAMES=8000 bash utils/...  # media noche
PY=.venv/bin/python bash utils/...                 # otro intérprete
```

---

## 3. Los seis bloques y qué contesta cada uno

| | Pregunta que contesta | Tamaño | Tiempo |
|---|---|---|---:|
| **B1a** | ¿El residuo del 1,4 % existe igual contra los mazos con los que se juega **de verdad**? | 98 mazos reales × 300 partidas | ~45 min |
| **B1b** | Los cinco peores **por tasa**, volcados como fixtures | 5 × 1 000, con `--dump` | ~7 min |
| **B2** | ¿El 54,5 % es real, o es el ±7 que tienen 200 partidas? | 18 `crustle_wall` + 5 `mega_lucario` × 1 000 | ~18 min |
| **B3** | Los invariantes a diez veces la muestra, con cada violación volcada | 20 000 partidas | ~32 min |
| **B4** | Los 1 698 dependientes del orden, volcados para triarlos | 2 000 partidas | ~6 min |
| **B5** | Las propiedades a diez veces el presupuesto | 200 000 ejemplos | ~30 min |
| **B6** | El radar de colisiones — la herramienta construida para justo la pregunta de B2 | 19 sintéticos × 400 | ~12 min |
| | | | **~2 h 30** |

Los tiempos son extrapolación lineal de la corrida de hoy (0,07 s por partida
del oráculo, 0,094 s del monitor, 0,17 s del permutador), que es lineal y está
medida. **Lo que sí está verificado es que los seis lanzan**: he probado el
oráculo a 3 partidas contra `crustle_wall_6`, la sonda a 5, el radar a 2 y la
matriz a 2 sobre las 23 listas exactas de B2. Los cuatro contestaron. Lo que no
está verificado es el tiempo a tamaño completo.

**Por qué B1b elige por tasa y no por número de hallazgos:** un mazo que juzga el
doble de ataques reporta el doble de hallazgos con el mismo nivel de defecto.
`festival_lead` lidera en absoluto (885) y también en tasa (5,2 %); pero en el
censo de los 98 esa distinción va a decidir a qué cinco mazos se les gasta el
volcado.

**Por qué B2 lleva grupo de control:** `mega_lucario` es la familia siguiente
más débil (87,0 %). Sin ella, un número de Crustle más estrecho no se distingue
de que todo salga más estrecho.

---

## 4. Qué mirar al despertar, en este orden

**Primero `log/noche_2026-08-10/RESUMEN.txt`**, que cabe en una pantalla.
`rc != 0` en **B4 no es un fallo**: la sonda de permutación informa por código de
salida, y llamar fallo a los hallazgos de una herramienta es como se enseña a
ignorar el rojo de un pipeline.

Después, por lo que cuesta un defecto de cada clase:

| Log | Qué buscar | Qué sabemos ya |
|---|---|---|
| `B1a.log` | la tasa por mazo real | Global esperada ≈1,4 %. **Si vuelve con un orden de magnitud distinto, sospecha de la carga de los mazos antes que del agente**: estas 98 listas nunca han pasado por el oráculo |
| `B1b.log` + `violaciones_oraculo/` | un JSON por hallazgo, observación incluida | Cada uno es un fixture listo para fijar. Detectar no es ejecutar: reproducir el tablero es otro trabajo |
| `B2.log` | `crustle_wall_6` con n=1 000 (±3) | A 200 partidas daba 54,5 % [47,6-61,3]. La pregunta es si sigue solo, o si baja el resto de la familia con él |
| `B3.log` | `DECK_BELIEF`, `ILLEGAL_INDEX`, `END_EMPTY_BENCH`, `ENERGY_CAP`, `DOUBLE_ATTACH` | Los cinco a **0** sobre 2 000 partidas hoy. `STALE_FLAG`/`STALE_READ` salen a miles y **no son defectos** |
| `B4.log` + `permutacion/` | no cuántos, sino **cuántos son `ATTACK` vs `RETREAT`** | 0,67 % es el nivel conocido. Un empate `CARD` vs `CARD` es cosmético; una bifurcación atacar-o-retirar la decide la posición en el menú |
| `B5.log` | cualquier falsación | Es el artefacto más valioso que puede producir la noche, porque viene **minimizado** |
| `B6.log` | «resolution well below the median» | Hoy, a 2 partidas de ruido, ya señalaba `juega_supporter` en `festival_lead` al 23,5 % contra una mediana del 50 % |

---

## 5. La regla que no se salta

**Ningún hallazgo de esta noche se convierte en un cambio del agente sin
medirlo.** En dos días, **cuatro** detectores de este repositorio reportaron sus
propios fallos como defectos del agente: el oráculo tres veces (16 764 hallazgos
inexistentes en la v1), el monitor dos, el gate de mutación dos más. Lo único que
ha funcionado es el auto-test que aborta la corrida.

Su versión de esta noche: **B1a es la primera vez que el oráculo ve las listas
reales.** El script lanza una invocación por mazo, y no una sola con todos, justo
para que cada una corra su propio auto-test. Un censo cuyo detector no puede
demostrar que sigue funcionando es el resultado que peor engaña.

Y si un hallazgo resulta real: **mide la frecuencia antes que el winrate.** El
arreglo del 9 de agosto corregía una creencia imposible en el 25 % de los
tableros y movía **2 decisiones en 50 955**; con esa frecuencia, un gate de
winrate solo puede devolver NEUTRO por construcción.

---

## 6. Lo que la noche NO hace — las tareas de manos que quedan

De `docs/testing-plan-2026-08.md`, ordenadas por lo que esta noche vuelve urgente:

1. **T3.1 · Una suite para `opponent_bot.py`** — 1-2 días, y esta noche lo
   asciende a lo primero de mañana. **Todo el hallazgo de Crustle descansa sobre
   un bot con 13 tests, y los 13 son del motor de habilidades.** Su objetivo de
   gusteo, su prioridad de adjunte y su condición de retirada no están fijados,
   y su cobertura ni siquiera se mide (`utils/` no entra en `coverage.json`). Si
   el bot juega Crustle mal, el 54,5 % es una medida **del bot**. Los tres
   desenlaces posibles —defecto del agente, defecto del bot, matchup
   sencillamente duro— solo se distinguen con esto hecho.
2. **T1.3 · Pares de frontera** desde `decision_grid.boundaries()`: mata por
   construcción las familias de mutantes `boundary: 1 -> 2` y `GtE -> Gt`.
3. **T1.2 · Aserciones de razón** en los 30 tests de más valor (la familia del
   gusteo de Boss's, promoción, retirada).
4. **T3.4 · Crecer y congelar el corpus dorado**: hay 50 registros locales, pero
   CI sigue saltándose la comparación. El flip-diff es el artefacto de revisión
   más útil del proyecto y en un checkout limpio todavía no existe.
5. **T3.3 · SPRT** para el A/B, y **T3.2 · una segunda política rival**.
6. **T4.2 · Higiene** e índice regla → fichero de test.

Y dos correcciones al propio documento del plan, que ya está desfasado:

- **T0.3 dice «not yet in CI» y es falso**: el job `mutation` existe en
  `.github/workflows/gates.yml`, con `--self-test-only` antes de fiarse de su
  cero. Lo que de verdad queda es el parámetro muerto `meganium_active`.
- **Un trabajo de 15 minutos que B6 pide a gritos**: `utils/collision_radar.py`
  tiene `deck/opponents` escrito a fuego en la línea 344, así que **no puede
  mirar a `crustle_wall_6`**. Darle un `--opponents` como el que ya tiene
  `matchup_matrix.py` convierte el radar en la herramienta que contesta la
  pregunta de esta noche contra las listas reales.

---

## 7. El criterio de éxito

El mismo de anoche: **una lista de hallazgos reproducibles y unos detectores que
siguen validándose**, con **cero líneas cambiadas en `main.py`**.

Y uno propio de esta noche: por la mañana tiene que poderse escribir, en una
frase, cuál de las tres es `crustle_wall` — **defecto del agente** (lo dirían B1a
y B1b, con la tasa del oráculo concentrada en esas listas), **defecto del bot**
(lo diría B2 si el 54,5 % se sostiene pero el radar de B6 no encuentra ninguna
situación que colapse) o **un matchup duro y ya está** (lo diría B2 si con
n=1 000 la familia sube hacia la media y el 54,5 % era el ±7).

Una noche que conteste «ninguna de las tres, hace falta T3.1 primero» también es
un resultado. El modo de fallo que este proyecto conoce por su nombre es *un
número que nadie leyó*.
