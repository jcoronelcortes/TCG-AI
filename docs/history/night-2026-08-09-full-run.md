# La primera corrida completa del pipeline — 9 de agosto, 14:11-15:49

`python utils/nightly.py --full --since 69ad2e3`, sobre `7bb0bb6`. **1 h 38 min**
(estimado 1 h 35). 28 etapas, **cero en FALLO, cero en INVÁLIDO**, código de
salida 0.

Es la primera vez que toda la maquinaria del 8 y 9 de agosto se ejecuta junta y
a tamaño completo. Este documento es lo que produjo.

---

## 1. Las puertas: todas verdes

| | |
|---|---|
| Suite | 1 878 tests, 16 s |
| Lint de arquitectura | sin violaciones |
| Corpus dorado local | 50 registros, sin flips |
| Suelos de cobertura | 37 módulos, **ninguno por debajo** (26 min) |
| **Gate de mutación** | sobre TODO el diff del agente del día: **cero supervivientes** |

El gate de mutación pasando a cero sobre las líneas que se escribieron hoy es el
número que más cuesta conseguir de los cinco, y esta mañana no lo hacía: valía
un superviviente en el propio arreglo de los premios.

---

## 2. El oráculo diferencial: el residuo se REPRODUCE

19 mazos × 2 000 partidas, **165 104 ataques juzgados**.

| | anoche (v4) | ahora | Δ |
|---|---:|---:|---:|
| Hallazgos | 2 351 | **2 303** | −48 |
| Tasa sobre ataques juzgados | 1,42 % | **1,39 %** | −0,03 pts |

Ninguna diferencia por mazo pasa de lo que mueve la varianza entre corridas sin
semilla (la mayor es −36 sobre `archaludon`, que tiene 101). **Eso es lo
importante:** el residuo no era ruido de una corrida. Es un número estable,
medido dos veces de forma independiente, y **sigue sin explicación**.

Dónde vive, y no se ha movido:

| Mazo | Hallazgos | % del total |
|---|---:|---:|
| `festival_lead` | 885 | 38 % |
| `crustle_great_tusk_nz` | 356 | 15 % |
| `crustle_kangaskhan` | 285 | 12 % |
| `jellicent_lock` | 170 | 7 % |
| los otros 15 | 607 | 26 % |

---

## 3. El monitor de invariantes: cero en todo lo objetivo

2 000 partidas. Los únicos contadores distintos de cero son `STALE_FLAG`
(14 851) y `STALE_READ` (2 490), que **están documentados como no-defectos** en
el propio fichero: se auditaron 743 lecturas y las tres promesas registradas
están guardadas en sus puntos de consumo.

Lo que importa es lo que **no** sale, sobre 2 000 partidas completas:

    DECK_BELIEF 0 · ILLEGAL_INDEX 0 · END_EMPTY_BENCH 0
    ENERGY_CAP 0 · DOUBLE_ATTACH 0 · AGENT_RAISED 0

El arreglo de `_identify_prizes` de esta mañana aguanta a escala: cero creencias
imposibles sobre los premios en 2 000 partidas.

---

## 4. Permutación y propiedades

- **0,67 % de decisiones dependientes del orden** sobre **253 197 decisiones**.
  El nivel conocido era 0,56-0,77 % medido sobre 40-150 partidas; ahora es un
  número sólido y no una muestra.
- **20 000 ejemplos** de hypothesis, las 6 propiedades verdes en 2 min 53 s.

---

## 5. EL HALLAZGO DE LA NOCHE: la familia Crustle

La matriz de matchups —98 listas reales del ranking × 200 partidas— por
arquetipo:

| Familia | Listas | Winrate medio | Peor |
|---|---:|---:|---:|
| **`crustle_wall`** | **18** | **76,6 %** | **54,5 %** |
| `mega_lucario` | 5 | 87,0 % | 84,0 % |
| `mega_starmie` | 3 | 89,5 % | 87,5 % |
| `ogerpon_verde` | 11 | 90,7 % | 84,0 % |
| `alakazam` | 10 | 95,8 % | 93,5 % |
| … los otros 12 arquetipos | | 94-99 % | |
| **Global** | **97** | **91,4 %** | |

`crustle_wall` está **10 puntos por debajo** de la siguiente familia peor y
**15 por debajo** de la media. Con 18 listas y 200 partidas cada una no es una
lista rara: es el arquetipo.

**Y dos detectores independientes apuntan al mismo sitio.** Los dos residuos más
grandes del oráculo después de `festival_lead` son los dos mazos de Crustle
(641 hallazgos entre los dos, el 28 % del total). El oráculo dice «el agente se
equivoca al proyectar su daño contra estos mazos» y la matriz dice «y contra
estos mazos gana mucho menos». Que coincidan no lo demuestra, pero es la
primera vez que dos herramientas construidas para cosas distintas señalan el
mismo arquetipo.

**Salvedad honesta:** la matriz mide contra el bot genérico. Un 54,5 % contra
ese bot no es un 54,5 % contra una persona. Lo que sí es comparable es el
GAP: las 97 listas se miden igual, y esta familia está 15 puntos por debajo.

---

## 6. La lista de la mañana

1. **Los 641 hallazgos del oráculo contra los dos Crustle**, cruzados con el
   54-84 % de la matriz. Es el único sitio donde dos detectores coinciden, y hay
   volcados para reproducir cada uno.
2. **`festival_lead`, 885 hallazgos, el 38 %**, medido dos veces igual. Sigue
   sin explicación desde anoche.
3. Nada más. Las puertas están verdes, los invariantes objetivos a cero y el
   gate de mutación a cero: **no hay una tercera cosa que arreglar**, y decirlo
   vale tanto como las dos primeras.

## Lo que NO haría

- **No tocar el agente por el residuo del oráculo sin reproducir un caso
  concreto primero.** 2 303 hallazgos no son 2 303 defectos: anoche el mismo
  detector tuvo tres versiones y las dos primeras reportaban miles de cosas que
  no existían.
- **No perseguir el 0,67 % de permutación.** Está en su banda histórica y es la
  medida más grande que se le ha hecho.
- **No añadir etapas al pipeline.** La que falta no es una etapa, es leer las
  dos de arriba.
