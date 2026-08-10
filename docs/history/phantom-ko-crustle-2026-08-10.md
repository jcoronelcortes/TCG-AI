# El PHANTOM_KO de Crustle — 234 tableros, y lo que ya se puede descartar

**Estado: medido, sin culpable. No se ha tocado una línea del agente.**

Sale del censo B1a de la noche del 9-10 de agosto (`docs/night-plan-2026-08-10-c.md`),
el primero contra las 87 listas reales del meta recolectado el 9.

---

## 1. Dónde está

El residuo del oráculo por familia, sobre 128 338 ataques juzgados:

| familia | listas | tasa media | deriva mediana | % optimista |
|---|---:|---:|---:|---:|
| **`crustle_wall`** | 16 | **4,58 %** | **+40** | **90 %** |
| `great_tusk_crustle` | 1 | 4,06 % | −10 | 40 % |
| `festival_lead` | 11 | 3,98 % | −30 | 44 % |
| `marnie_grimmsnarl` | 9 | 0,11 % | +25 | 50 % |

No es un mazo descolgado: es la familia entera, dieciséis listas, seis de ellas
sin haber sido medidas nunca.

**Y la categoría separa mejor que la tasa.** A n=1 000 partidas por lista:

| lista | PHANTOM_KO | MISSED_KO | DAMAGE_DRIFT |
|---|---:|---:|---:|
| `crustle_wall_9` | **124** | 5 | 76 |
| `crustle_wall_6` | **110** | 2 | 55 |
| `festival_lead_10` | 2 | **112** | 616 |
| `festival_lead_8` | 6 | **91** | 442 |

`festival_lead` lidera la tasa y **gana el 97 % de sus matchups** porque su
residuo es `MISSED_KO`: predijo que quedaba vida y el cuerpo cayó — una sorpresa
buena. Crustle es `PHANTOM_KO` a veinte veces esa tasa: **predijo que el cuerpo
caía y no cayó**. Ésa se paga con el turno.

---

## 2. Qué dicen los 234 tableros volcados

`log/noche_2026-08-10-c/violaciones_oraculo/crustle_wall_{6,9}/phantom_ko_*.json`,
cada uno con la observación entera.

**El motor resuelve exactamente el daño base. Siempre.**

| par | n | daño que resolvió el motor |
|---|---:|---|
| Dipplin → Crustle | 77 | **100** con banca 5, **80** con banca 4 |
| Tapu Bulu → Mega Kangaskhan ex | 31 | **220**, sin una sola excepción |
| Meganium → Crustle | 30 | **140** en 22 de 30 |

`Do the Wave` son 20 × nuestra banca: 5 → 100, 4 → 80. Exacto. Los 220 de Tapu
Bulu y los 140 de Meganium son su daño impreso. Exacto.

**Crustle no está reduciendo nada.** La hipótesis natural —«el muro absorbe»—
está descartada por los propios números: el motor aplicó el daño completo. El
exceso es enteramente de nuestra proyección.

Lo que el agente predijo, en cambio, está por todas partes: Dipplin 180 (×29) y
200 (×19); Tapu Bulu 370 (×20); Meganium 220 (×11) y 240 (×6).

Exceso (predicho − real) sobre los 234:

```
+80  x43     +230 x33     +100 x31     +150 x28
+60  x13     +330 x12     +50  x11     +110 x8
```

---

## 3. Lo que ya se puede descartar

Tres hipótesis baratas, las tres muertas con los datos que ya hay:

1. **No es el estadio.** La distribución del exceso es la misma con
   `Forest of Vitality` (148 casos), con `Battle Cage` (77) y sin estadio (9).
   Si un estadio inflara la proyección, el reparto cambiaría con él.
2. **No es una herramienta.** Nuestro atacante va sin herramienta en **234 de
   234**.
3. **No es el doble ataque de Festival Grounds.** Ese estadio no está en mesa en
   ninguno de los 234 (ver [[festival-grounds-dipplin-doble-ataque]]).

---

## 4. Lo que queda, y por qué no se hizo esta noche

Los excesos que más se repiten —**+80** y **+100**— aparecen en pares distintos
(Dipplin 100→180, Meganium 140→220), lo que apunta a un sumando de nuestro lado
y no a un multiplicador. Confirmarlo exige **leer `_our_effective_damage` y el
proyector del plan**, no agregar más tableros.

Eso es código del agente, y la regla de la noche es que **una regla que aterriza
a mitad significa que los bloques de antes y los de después midieron dos agentes
distintos**. Por eso se para aquí.

Es la segunda vez que aparece esta clase: la primera fue Full Metal Lab, donde
«la proyección de daño del propio agente era 30 demasiado generosa» y la
encontró este mismo oráculo. Aquélla movió 2 decisiones en 50 955. **Ésta son
110-124 tableros por cada 1 000 partidas**, así que antes de tocar nada conviene
medir la frecuencia — pero el orden de magnitud ya no es el mismo.

---

## 5. Y sin embargo NO explica el matchup — B2, n=1 000 por lista

Esto hay que leerlo antes de arreglar nada, porque es lo que impide la
conclusión falsa.

La familia entera contra el grupo de control:

| | rango | media |
|---|---|---:|
| `crustle_wall` (16 listas) | 71,4 % – 85,4 % | ~77,5 % |
| `mega_lucario` (4, control) | 87,7 % – 91,3 % | ~89,3 % |

**Los intervalos ni se rozan** (el techo de Crustle es 85,4 %, el suelo del
control 87,7 %), así que Crustle sí es genuinamente ~12 puntos más duro. Y **no
hay ningún mazo descolgado**: es una banda, no un valor atípico. El 54,5 % de la
noche anterior no tiene heredero.

Pero dentro de la familia, cruzando las dos mediciones de esta misma noche:

```
correlacion tasa-del-oraculo vs winrate, n=16 listas:  r = +0.09
```

`crustle_wall_12` tiene un residuo del 5,25 % y gana el **85,4 %**;
`crustle_wall_5` tiene 1,87 % y gana el **73,0 %**. **La tasa del oráculo no
predice el winrate dentro de la familia.**

Son dos hechos separados y conviene no fundirlos:

1. **La proyección se equivoca.** 110-124 tableros por cada 1 000 partidas, con
   la observación volcada. Es un defecto de corrección y se arregla por eso.
2. **Crustle es un matchup duro.** Doce puntos por debajo del control, y el
   residuo **no** lo explica.

Arreglar (1) esperando mover (2) es exactamente el error que este proyecto ya
tiene con nombre: **mide la frecuencia antes que el winrate**. La frecuencia
justifica el arreglo; el winrate no lo va a agradecer necesariamente.

### La anomalía que sí es nueva: los premios de `crustle_wall_6`

| lista | winrate | premios |
|---|---:|---:|
| `crustle_wall_6` | 71,4 % | **−0,22** |
| `crustle_wall_4` | 71,8 % | +1,56 |
| resto de la familia | 72-85 % | +1,50 a +2,56 |

Mismo winrate que su vecino y el diferencial de premios se desploma quince
décimas. Ganamos el 71 % de las partidas **perdiendo la carrera de premios**, lo
que apunta a que esas victorias vienen por otra vía — el mazo como reloj (ver
[[el-mazo-es-el-reloj-de-la-carrera-de-premios]] y
[[deckout-vs-crustle-medido-sin-culpable]]). Es la única lista del corpus con
premios negativos y **nadie la había medido nunca**: es una de las seis listas
`crustle_wall` que el puente marcó como NUEVAS.

---

## 6. El mazo retirado, medido antes de que dejara de importar — B2b

La noche anterior preguntaba cuál de tres cosas era `crustle_wall`: defecto del
agente, defecto del bot, o un matchup duro y ya está. El puente contestó
«ninguna, el mazo se fue del meta». **B2b contesta la que quedaba: era real.**

```
crustle_wall_6 RETIRADO, desde el respaldo del 7-ago, n=1000:
    58,8 %  [55,7-61,8]   premios −0,27
    (a n=200 daba 54,5 % [47,6-61,3]; los intervalos se solapan)

sus dos vecinos del mismo corpus retirado:
    crustle_wall_2   73,5 %   premios +1,83
    crustle_wall_1   85,8 %   premios +2,31
```

**No era el ±7 de una muestra corta.** Veinticinco puntos por debajo de su
propia familia, con el intervalo estrecho. Ese mazo nos ganaba de verdad, y se
fue solo.

### Lo que sobrevivió a la rotación no es el mazo, es la firma

| | winrate | premios |
|---|---:|---:|
| `crustle_wall_6` **retirado** (7-ago) | 58,8 % | **−0,27** |
| `crustle_wall_6` **nuevo** (a 32 cartas del anterior) | 71,4 % | **−0,22** |
| cualquier otra lista de los dos corpus | 71,8-91,3 % | +1,50 a +3,27 |

Son **dos mazos distintos** que comparten nombre por accidente del puesto, y
comparten dos cosas más: ser el más débil de su corpus y ser los **únicos con la
carrera de premios en negativo**. Ganamos esas partidas sin ganar los premios.

El fenómeno sobrevivió a la rotación del meta aunque el mazo no; lo que perdió
son doce puntos de severidad. Y **el marcador no es el winrate, es el
diferencial de premios**: es lo que separa a estos dos de las otras treinta y
siete listas medidas esta noche.

Eso también dice cómo buscarlo la próxima vez que el meta rote: no por el nombre
ni por el arquetipo, sino barriendo el corpus por **premios negativos**.

---

## 7. Por dónde entrar mañana

1. Los 234 JSON son fixtures listos. **Detectar no es ejecutar**: reproducir el
   tablero es otro trabajo (ver [[detectar-no-es-ejecutar-replicar-los-tableros-del-flip]]).
2. `B8.log` añade `crustle_wall_11`, `crustle_wall_12` y `great_tusk_crustle_1`
   —las de deriva positiva que B1b no alcanzó, porque elegía por tasa y tres de
   sus cinco huecos se fueron a la familia inofensiva.
3. Empezar por **Dipplin → Crustle**, que son 77 de los 234 y el único par donde
   el daño real es una función conocida y verificable del tablero (20 × banca).
