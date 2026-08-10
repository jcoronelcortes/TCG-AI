# La noche del 10 de agosto — la primera contra el meta que existe

**Esta corre sola.** Se lanzó a las 23:01:48 sobre `HEAD 450c996` y no necesita
a nadie. Este documento es lo que hay que leer al despertar.

---

## 0. Por qué esta noche no es la noche anterior otra vez

`docs/night-plan-2026-08-10-b.md` planteó seis preguntas y contestó una, a 5
partidas en vez de 2 000. Sus cinco bloques sin ejecutar siguen siendo las
preguntas correctas — pero estaban escritas contra un corpus que ya no existe.

El 9 de agosto a las 21:11 se rehizo la recolecta del top 300. El resultado no
es «los mismos mazos, actualizados»:

| | Antes | Ahora |
|---|---:|---:|
| Mazos del top 300 con contenido distinto | — | **267 de 300** |
| Listas únicas | 98 | **88** |
| Mega Lopunny / Mega Froslass | 9 mazos | **24** |
| Ogerpon Verde | 23 | 15 |
| Marnie Grimmsnarl | 115 | 108 |
| Crustle Wall | 32 | 30 |

Y `deck/real_opponents/` — el corpus que consumen el oráculo, la matriz y el
radar — era **del 7 de agosto**. Todo lo que la noche anterior iba a medir
estaba apuntando a listas retiradas.

---

## 1. Lo que la fase A ya contestó, antes de lanzar nada

### A1 · El corpus, reconstruido

`deck/real_opponents_2026-08-07/` guarda el viejo. El nuevo son **87 listas
pilotables de 88**, y la parte del meta que el arnés puede medir es el
**99,7 %**. Una sola lista (`otro_ns_zoroark_ex_2`) no arranca con el bot.

Cuatro listas del corpus son **casi copias de la nuestra** (`festival_lead_4`
comparte las 60 cartas). El bot pilota NUESTRO motor ahí, mal, así que su
winrate se lee alto y no es un matchup. Están marcadas en `pesos.csv`.

### A2 · El hallazgo de Crustle ya no se puede reproducir — y eso es una respuesta

`utils/corpus_bridge.py`, escrito para esto, empareja por **contenido** y no por
nombre, porque `real_opponents.py` numera por peso de meta y por tanto
`crustle_wall_6` **no es un mazo, es un puesto**.

| | |
|---|---:|
| Listas viejas idénticas en el corpus nuevo | 45 |
| Con deriva (≤12 cartas) | 37 |
| **Desaparecidas del top 300** | **15** |
| Listas nuevas que nadie ha medido jamás | **32** |

**El `crustle_wall_6` que medía 54,5 % está entre las 15.** La lista más cercana
del meta nuevo está a **32 cartas**, y el nombre `crustle_wall_6` ha caído sobre
un mazo que nunca ha jugado una partida contra nosotros. Seis de las dieciséis
listas `crustle_wall` nuevas son de las que nadie ha medido.

Por eso la noche lleva un bloque **B2b** que no estaba en ningún plan: medir el
mazo muerto a n=1 000 **desde el respaldo**, que es la última ocasión de saber
si el 54,5 % era real o el ±7 de 200 partidas. Una de las dos respuestas se
traslada a las seis listas nuevas y la otra no.

### A3 · El meta nuevo, y quién manda arriba

`log/noche_2026-08-10-c/A4_meta.md`. El titular no es la presencia, es la banda:

> **Mega Lopunny / Mega Froslass es el 26,7 % de los puestos 1-30** siendo solo
> el 8 % del campo. Es el arquetipo que gana, no el que más se juega.

Y en el corpus es **una sola lista**: los 24 mazos son idénticos carta por
carta. Un solo fichero vale el 8 % del meta y un cuarto del top 30.

### A4 · Un test rojo que trajo la recolecta

`tests/test_op_scaling_attacks.py::test_no_opposing_attack_scales_without_being_read`
falla ahora, y **no lo rompió ningún cambio de código**:

```
Tapu Koko ex — Linked Lightning (458): 60 de base, +20 por cada uno de sus
Pokémon en banca. Nadie lo lee.
```

La carta 329 está en **1 mazo de 408 ahora y en 0 antes** de la recolecta
(`mazo_278.csv`, Mega Kangaskhan, puesto 278). El test es exactamente el guardia
que se escribió para esto: un mazo nuevo que trae un ataque que escala y el
agente no lo ve; no revienta, se mete debajo.

**No se toca esta noche.** Meterlo en `OP_SCALING_DAMAGE` es un cambio del
agente, y una regla que aterriza a mitad de la noche significa que los bloques
de antes y los de después midieron dos agentes distintos. Con 1 mazo de 408 no
hay ninguna prisa. Decisión para mañana: ¿el número se **lee** del tablero (sí:
su banca es visible) o estaríamos adivinando?

---

## 2. Lo que está corriendo

```
log/noche_2026-08-10-c/RESUMEN.txt     ← empieza por aquí
log/noche_10ago_c.txt                  ← la traza con marcas de tiempo
```

| | Pregunta que contesta | Tamaño | Estimado |
|---|---|---|---:|
| **B1a** | ¿El residuo del oráculo existe contra las listas con las que se juega ahora? | 87 listas × 300 partidas | ~60 min |
| **B1b** | Los cinco peores **por tasa**, volcados como fixtures | 5 × 1 000, con `--dump` | ~12 min |
| **B2** | ¿Hay una `crustle_wall` que se descuelgue, con la familia entera a ±3? | 16 Crustle + 4 Lucario × 1 000 | ~33 min |
| **B2b** | El `crustle_wall_6` **retirado**: ¿54,5 % real o ruido? | 3 × 1 000, desde el respaldo | ~5 min |
| **B3** | Los invariantes a diez veces la muestra, cada violación volcada | 20 000 partidas | ~40 min |
| **B4** | Las decisiones dependientes del orden, volcadas para triarlas | 2 000 partidas | ~6 min |
| **B5** | Las propiedades a diez veces el presupuesto | 200 000 ejemplos | ~24 min |
| **B6** | El radar de colisiones **sobre las listas reales** — por primera vez | 87 listas × 400 | ~81 min |
| **B7** | ¿Cómo vamos contra el meta ponderado? No existe para estas listas | 87 × 300, con `--weights` | ~44 min |
| | | | **~4 h 30** |

Cada bloque escribe su propio log y **ninguno puede parar la noche**.

---

## 3. Qué mirar al despertar, en este orden

**Primero `RESUMEN.txt`**, que cabe en una pantalla. `rc != 0` en **B4 no es un
fallo**: la sonda de permutación informa por código de salida, y llamar fallo a
los hallazgos de una herramienta es como se enseña a ignorar el rojo.

> **B1a ya terminó (57m 17s, rc=0) y cambió cómo se lee todo lo demás.**
> **2 664 hallazgos sobre 128 338 ataques juzgados: 2,08 %**, contra el
> 1,39-1,42 % de los sintéticos. No es un orden de magnitud, así que los mazos
> cargaron bien.
>
> Lo que importa es la forma. Por familia, `crustle_wall` lidera con **4,58 %
> de media sobre dieciséis listas** — no un mazo descolgado, la familia entera —
> con `great_tusk_crustle`, el otro cascarón de Crustle, justo detrás.
> `marnie_grimmsnarl`, que es el 36 % del meta, está en **0,11 %**.
>
> **Y la tasa sola no distingue un residuo peligroso de uno inofensivo: el
> signo sí.** Una deriva positiva es el agente prediciendo MÁS daño del que el
> motor resuelve — cree que noquea, ataca contra un cuerpo que sobrevive y
> regala el turno. `crustle_wall` es **90 % positiva, mediana +40**.
> `festival_lead` tiene tasa comparable con un **44 % positiva**, y por eso su
> residuo nunca ha predicho perder.
>
> Dos cautelas: el sesgo optimista es **general** (casi todas las familias entre
> 60 % y 90 %), lo singular de Crustle es tenerlo casi puro Y la tasa más alta a
> la vez; y la deriva se resume por **mediana**, no por moda — la moda decía
> «−70» junto a «67 % positivas».
>
> **Consecuencia para B1b:** elige los cinco peores **por tasa**, criterio
> fijado antes de saber que el signo manda, y tres de sus cinco huecos se van a
> `festival_lead`. Por eso hay un **B8** encolado que arranca al terminar la
> noche y vuelca `crustle_wall_11`, `crustle_wall_12` y `great_tusk_crustle_1`,
> que son deriva positiva y B1b no alcanza.

| Log | Qué buscar | Lo que ya sabemos |
|---|---|---|
| `B1a.log` | ~~la tasa por lista~~ **el signo por familia** | Ver el recuadro de arriba: hecho y leído |
| `B1b.log` + `violaciones_oraculo/` | un JSON por hallazgo, observación incluida | Cada uno es un fixture listo para fijar. **Detectar no es ejecutar**: reproducir el tablero es otro trabajo. Los tres `festival_lead` de aquí son la familia inofensiva |
| `B8.log` | los volcados de deriva **positiva** | Suplementario, arranca solo al acabar la noche |
| `B2.log` | si alguna `crustle_wall` se descuelga de su familia | El mazo que se descolgaba ya no está. La pregunta es si el hueco lo ocupa otro o si era de aquel mazo |
| `B2b.log` | `crustle_wall_6` del respaldo a n=1 000 (±3) | A 200 partidas daba 54,5 % [47,6-61,3]. Si sube hacia 76 %, era el ±7 y no había nada |
| `B3.log` | `DECK_BELIEF`, `ILLEGAL_INDEX`, `END_EMPTY_BENCH`, `ENERGY_CAP`, `DOUBLE_ATTACH` | Los cinco a **0** sobre 2 000 partidas. `STALE_FLAG`/`STALE_READ` salen a miles y **no son defectos** |
| `B4.log` + `permutacion/` | no cuántos, sino **cuántos son `ATTACK` vs `RETREAT`** | 0,67 % es el nivel conocido. Un empate `CARD` vs `CARD` es cosmético; una bifurcación atacar-o-retirar la decide la posición en el menú |
| `B5.log` | cualquier falsación | El artefacto más valioso que puede salir, porque viene **minimizado** |
| `B6.log` | «resolution well below the median» | **Primera vez que el radar mira listas reales.** Contra los sintéticos ya señalaba `juega_supporter` en `festival_lead` |
| `B7.log` | el número ponderado contra el meta nuevo | No hay con qué comparar: es la línea base de este corpus. Las 4 casi-copias inflan; `pesos.csv` las marca |

---

## 4. La regla que no se salta

**Ningún hallazgo de esta noche se convierte en un cambio del agente sin
medirlo.** En dos días, cuatro detectores de este repositorio reportaron sus
propios fallos como defectos del agente: el oráculo tres veces (16 764 hallazgos
inexistentes en la v1), el monitor dos, el gate de mutación dos más.

Su versión de esta noche ya cobró una pieza. El ensayo en seco del guión reveló
que `listas()` usaba `find | xargs basename`, que `xargs` parte por espacios,
que este proyecto vive bajo `VS Proyectos/TCG AI` y que por tanto el censo
midió alegremente **261 mazos en vez de 87** — entre ellos dos llamados `VS` y
`TCG` — durante siete minutos, **con código de salida 0 y un log completo**. Un
número con toda la pinta de una medición.

Y si un hallazgo resulta real: **mide la frecuencia antes que el winrate.** El
arreglo del 9 de agosto corregía una creencia imposible en el 25 % de los
tableros y movía 2 decisiones en 50 955; con esa frecuencia un gate de winrate
solo puede devolver NEUTRO por construcción.

---

## 5. Lo que se hizo mientras corría

**T3.1 · La suite de `opponent_bot.py`** — hecha, commit `6165426`. Era «lo
primero de mañana» del plan anterior porque todo hallazgo de matchup descansa
sobre ese bot. 22 tests sobre la mitad de la política que nadie había fijado:
el orden del menú, la evolución por fase, el ataque por daño y no por posición,
y la rama *else* de cada regla cuya rama *then* ya estaba fijada.

Las 22 pasaron a la primera, que es cuando menos hay que fiarse de un test, así
que cada política se rompió en memoria y se volvió a correr: **siete de siete
fallan cuando su regla se rompe**.

De ahí salió una corrección al propio docstring del bot, escrita como test:
**la debilidad ×2 no puede cambiar qué ataque se elige** — los dos ataques de un
mismo atacante comparten su tipo, así que el ×2 escala a todos por igual. Donde
sí decide es en el **objetivo del gusteo**, y eso se fija aparte.

---

## 6. Lo que la noche NO hace — las tareas de manos que quedan

De `docs/testing-plan-2026-08.md`, reordenadas por lo que esta noche vuelve
urgente:

1. **T1.3 · Pares de frontera** desde `decision_grid.boundaries()`: mata por
   construcción las familias de mutantes `boundary: 1 -> 2` y `GtE -> Gt`.
2. **T1.2 · Aserciones de razón** en los 30 tests de más valor (la familia del
   gusteo de Boss's, promoción, retirada).
3. **T3.4 · Crecer y congelar el corpus dorado**: CI sigue saltándose la
   comparación, y el flip-diff es el artefacto de revisión más útil del
   proyecto.
4. **T3.3 · SPRT** para el A/B, y **T3.2 · una segunda política rival**.
5. **T4.2 · Higiene** e índice regla → fichero de test.
6. **El parámetro muerto `meganium_active`** en `_our_effective_damage`, que el
   gate de mutación señaló como mutante equivalente.

Y las dos de estrategia que la memoria tenía marcadas PENDIENTE, ninguna de las
cuales es medición:

- **El proyector «qué cuerpo, al bajarlo, sube MI daño»** (caso Dipplin / Do the
  Wave: el agente gastó un Meowth ex de 2 premios donde el Ogerpon solo ya daba
  el KO exacto). Afecta a todo atacante cuyo daño cuenta cuerpos.
- **El tempo del rival**: `_op_disruption_belief` ignora su segundo parámetro y
  nadie mira su descarte entre turnos, que es de donde sale «su mano está
  atascada».

---

## 7. El criterio de éxito

El mismo de siempre: **una lista de hallazgos reproducibles y unos detectores
que siguen validándose**, con **cero líneas cambiadas en `main.py`**.

Y uno propio de esta noche. La pregunta de la anterior era cuál de tres es
`crustle_wall`, y **el puente ya contestó que ninguna de las tres**: el mazo se
fue del meta. Lo que hay que poder escribir por la mañana, en una frase, es si
el hueco lo hereda alguna de las dieciséis listas nuevas (lo diría B2), o si
aquel 54,5 % era el ±7 de una muestra corta (lo diría B2b) — y en ese caso el
proyecto ha estado dos noches persiguiendo ruido, que también es un resultado y
de los baratos.
