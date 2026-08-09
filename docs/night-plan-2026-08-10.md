# La noche del 9-10 de agosto — la corrida que la infraestructura estaba esperando

**La ejecutas tú.** Este documento es la tarea, no un informe.

Toda la maquinaria construida el 8 y el 9 de agosto —el oráculo diferencial, el
monitor de invariantes, el gate de mutación, los suelos de cobertura, el corpus
congelado, las propiedades— existe para producir **una lista de hallazgos**. Esa
lista no se ha generado todavía ni una sola vez a tamaño completo. Eso es lo que
hace esta noche.

---

## 0. Antes de lanzar — 2 minutos

```bash
cd "/Users/jcoronel/Desktop/VS Proyectos/TCG AI"
git status --short          # tiene que estar limpio
git log --oneline -1        # apunta el hash: todo se mide contra él
```

**Si el árbol no está limpio, commitea o guarda antes.** El gate de mutación
reescribe ficheros en disco mientras corre y los restaura al terminar; con
cambios sin guardar encima, un corte a mitad es más difícil de deshacer.

Comprobación de que el pipeline está sano (40 segundos, no es la corrida buena):

```bash
python utils/nightly.py --quick --since HEAD~1
```

Tiene que terminar con **todas las etapas OK o HALLAZGOS**, ninguna en FALLO ni
en INVÁLIDO. Si alguna sale INVÁLIDO, para: significa que un detector no puede
validarse a sí mismo y **sus números de esta noche no valdrían nada**.

---

## 1. El comando de la noche

```bash
python utils/nightly.py --full --since 69ad2e3 2>&1 | tee log/noche_10ago.txt
```

`69ad2e3` es el commit anterior al trabajo del 9 de agosto: así el gate de
mutación vigila **todo lo que se añadió hoy al agente**, que es lo que interesa
comprobar. Si prefieres cubrir solo lo último, usa `--since HEAD~1`.

Deja el portátil enchufado y sin suspender.

### Cuánto tarda, medido y no estimado

| Etapa | Tamaño en `--full` | Tiempo |
|---|---|---:|
| Suite | 1 878 tests | 16 s |
| Lint | — | 1 s |
| Corpus dorado local | 50 registros | 2 s |
| **Cobertura contra los suelos** | suite entera instrumentada | **11 min** |
| **Gate de mutación** | líneas nuevas desde `69ad2e3` | **1 min** |
| **Oráculo diferencial** | 19 mazos × 2 000 partidas | **≈57 min** |
| Monitor de invariantes | 2 000 partidas | ≈4 min |
| Sonda de permutación | 2 000 partidas | ≈6 min |
| Soak de propiedades | 20 000 ejemplos | ≈3 min |
| **Matriz de matchups** | 98 mazos reales × 200 partidas | **≈12 min** |
| | | **≈1 h 35 min** |

Los tres números en negrita son los medidos hoy directamente; el resto es
extrapolación lineal de corridas cortas reales (la escala de este simulador es
lineal: 0,1 s por partida completa).

**No es una noche entera, es hora y media.** Si quieres que la máquina trabaje
más, la §5 dice en qué gastar las horas restantes — pero no alargues por
alargar: más partidas de lo mismo compran precisión, no verdad.

---

## 2. Qué mirar al despertar, en este orden

Todo queda en `log/nightly_<fecha>_<hora>/`, con un `REPORT.md` y un log por
etapa.

**Primero, la sección «Lectura» del informe.** Está diseñada para leerse antes
que ningún número:

1. **¿Hay etapas INVÁLIDAS?** Son las que fallaron su propio auto-test. Sus
   números están *sustituidos*, no mostrados, y con razón: un detector que no
   puede demostrar que sigue funcionando y encima dice «no he encontrado nada»
   es el resultado más engañoso de los tres. Si hay alguna, esa etapa no ha
   medido nada esta noche.
2. **¿Hay etapas en FALLO?** Eso es el árbol roto, no un hallazgo.
3. **Las etapas en HALLAZGOS** son las que encontraron algo. Salida distinta de
   cero **porque ese es su informe**, no porque estén rotas.

**Después, los números, en orden de cuánto cuesta un defecto:**

| Log | Qué buscar | Qué sabemos hoy |
|---|---|---|
| `*_oracle_*.log` | `PHANTOM_KO`, `MISSED_KO`, `DAMAGE_DRIFT` | El residuo era **2 351 sobre 165 199 ataques (1,42 %)**. `festival_lead` era el 39 % de él y **sigue sin explicación** |
| `*_monitor.log` | `DECK_BELIEF`, `ILLEGAL_INDEX`, `END_EMPTY_BENCH`, `ENERGY_CAP` | Todos deberían salir **0**. `STALE_FLAG`/`STALE_READ` salen a miles y **no son defectos** (documentado en el propio fichero) |
| `*_mutation.log` | `SUPERVIVIENTES` | Hoy quedó en **cero**. Cada superviviente nuevo es la frase del test que falta |
| `*_permutation.log` | `order-dependent` | **0,6-0,7 %** es el nivel conocido. Un salto es la señal |
| `*_matrix.log` | `Matchup mas debil` | Es la única etapa que contesta «¿gana más?» |

---

## 3. Si algo se rompe

**Sáltalo y sigue.** El script ya lo hace solo salvo con la suite y el lint, que
paran la noche a propósito: una corrida sobre un árbol roto atribuye su propio
daño a la etapa equivocada.

Si tienes que cortar la corrida entera, **Ctrl-C es seguro**. El gate de
mutación atrapa SIGINT/SIGTERM y restaura el fichero que estuviera mutando; ese
mecanismo existe porque una vez dejó un módulo sin parsear en disco. Después de
cortar, comprueba:

```bash
git status --short     # tiene que volver a estar limpio
```

---

## 4. La regla que no se salta

**Ningún hallazgo de esta noche se convierte en un cambio del agente sin
medirlo.** No porque sea prudente en abstracto, sino porque en dos días
**cuatro** detectores de este repositorio reportaron sus propios fallos como
defectos del agente:

- el oráculo diferencial, tres rondas, 16 764 hallazgos inexistentes en la v1;
- el monitor, dos veces en una mañana (37 799 y 16 980);
- el gate de mutación, dos veces más, por dos causas distintas.

Todos ellos con la doctrina «valida el arnés» ya escrita. Lo único que ha
funcionado es el **auto-test que aborta la corrida**, y por eso `nightly.py`
marca INVÁLIDO por encima del código de salida.

Y si un hallazgo sí resulta real: **mide la frecuencia antes que el winrate**.
El arreglo de hoy corregía una creencia imposible en el 25 % de los tableros y
movía **2 decisiones en 50 955** — con esa frecuencia un gate de winrate solo
puede devolver NEUTRO por construcción.

---

## 5. Si quieres que la máquina trabaje más horas

En orden de lo que más aporta por hora, y ninguna de las tres es «más de lo
mismo»:

1. **El oráculo contra los mazos REALES** (`deck/real_opponents/`, 98 listas)
   en vez de los 19 sintéticos. Hoy solo se ha medido contra los sintéticos, y
   el residuo sin explicar vive justo ahí:

   ```bash
   for f in deck/real_opponents/*.csv; do
     python utils/differential_oracle.py --games 500 --opponent "$f" \
       --dump log/oracle_reales/violations
   done 2>&1 | tee log/oracle_reales.log
   ```

2. **El monitor con volcado**, para que cada violación quede como fixture lista
   para fijar:

   ```bash
   python utils/invariant_monitor.py --games 20000 \
     --dump log/monitor_soak/violations 2>&1 | tee log/monitor_soak.log
   ```

3. **El soak de propiedades a lo grande** — es la única herramienta que llega a
   tableros que ninguna partida ha producido:

   ```bash
   PTCG_HYPOTHESIS_EXAMPLES=200000 python -m pytest -q \
     tests/test_invariants.py tests/test_properties_of_any_legal_board.py \
     2>&1 | tee log/hypothesis_soak.log
   ```

---

## 6. El criterio de éxito

La noche ha valido la pena si por la mañana hay **una lista de hallazgos
reproducibles y unos detectores que siguen validándose**. No se mide en líneas
cambiadas en `main.py`: ese número debería ser **cero**, igual que anoche.

Y una corrida que no encuentre nada **es un resultado**, no una noche perdida:
significa que el residuo del oráculo bajó donde tenía que bajar y que los
invariantes aguantan. Escríbelo tal cual. El modo de fallo que este proyecto ya
conoce por su nombre es *un número que nadie leyó*.
