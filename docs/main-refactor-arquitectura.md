# Refactor de `main.py` — arquitectura objetivo y proceso por olas

> Documento de **proceso**. Define en qué se parte `main.py`, en qué orden, y con qué
> instrumento se demuestra que cada paso no cambió ni una sola decisión del agente.
> Sucesor metodológico de [main-refactor-ultra-ball-plan.md](main-refactor-ultra-ball-plan.md),
> que ya validó el patrón `_score_*_play(ctx)` a pequeña escala.

---

## 0. Resultado (refactor terminado y validado)

> **Estado: cerrado.** Las siete olas están hechas y el paquete final **puntúa
> correctamente en competición**. Este documento se conserva como registro del
> método y, sobre todo, de lo que se aprendió por el camino.

| | antes | después |
|---|---:|---:|
| `main.py` | 25 333 | **10 042** (−60 %) |
| `agent()` | 15 500 | **5 996** |
| módulos | 1 | **45** (`ptcg/`, 19 406 líneas) |
| tests | 930 | **947** |

```text
ptcg/cartas     6 módulos   1 726 líneas   datos: IDs, tablas, líneas evolutivas
ptcg/motor      4 módulos     322 líneas   motor de reglas, AttackPlan, contexto
ptcg/calculo    7 módulos   1 614 líneas   energía, daño, probabilidad, rival
ptcg/estado     4 módulos     510 líneas   ESTADO, creencia del mazo, logs
ptcg/decision   9 módulos   4 653 líneas   un módulo por carta
ptcg/turno      8 módulos  10 581 líneas   fases de agent(): puntuación, cierre…
```

**El gate nunca falló en producción.** Todas las olas cerraron con `sombra` en 0
flips; la última pasada fueron **90 577 decisiones**. Y las cuatro submissions
que se subieron (olas 1, 3, 5-1er-corte y final) puntuaron igual que el original.

### Lo que queda dentro de `agent()`

Setup, detección de matchup, banderas, promoción tras KO — y **un bloque de
1 280 líneas** (`if context == SelectContext.MAIN`) que **resistió la
extracción**. Al sacarlo, el gate detectó un cambio de comportamiento real (dos
tests de retirada pasaban a atacar), no una costura de parcheo. Se descartaron,
sin encontrar la causa:

- `return`/`break` huérfanos → no hay;
- sentencias `global` dentro del bloque → no hay;
- funciones anidadas definidas dentro que sobrevivan al bloque → no hay;
- colisiones de nombre con globals de `main` → ninguna de las 45;
- live-out incompleto → los 11 coinciden con un cálculo independiente.

Se revirtió en vez de forzarlo. **Quien lo retome: el camino no explorado es usar
los flips de `sombra` (turno y paso concretos) para localizar la divergencia, en
vez de partir de los tests que fallan.**

### Las siete lecciones que costaron caro

1. **El contenedor de Kaggle `exec`uta `main.py`, no lo importa** (§2). De ahí que
   `def agent` deba ser lo último y que `import main` sea imposible.
2. **`ATTACK_ENERGY_REQ` era estado disfrazado de tabla**: 56 lectores, reescrita
   cada turno, invisible a las sentencias `global` porque mutar un dict no las
   exige. Igual que `my_deck = []` en la Ola 1.
3. **`from X import nombre` liga una COPIA.** Rompió tests tres veces
   (`card_table`, `_score_xerosic_play`, `_debug_log_decision`). Lo resuelve
   `tests/parcheo.py`, que fija el nombre allá donde esté ligado.
4. **El propio gate se rompió al mover el estado a un paquete**: `selfplay`
   cargaba dos agentes que compartían `ESTADO` vía `sys.modules`. 58 flips
   fantasma. Y al aislarlo, hubo que *devolver* el árbol a `sys.modules` o se
   creaba una segunda copia del paquete.
5. **`locals()` dentro de una función anidada no ve el ámbito de fuera.** Python
   solo crea celdas de closure para los nombres que la función referencia: al
   extraer una closure hay que escribirlos uno a uno.
6. **Las variables ligadas solo en algunas ramas** obligan a poblar contextos
   desde `locals()` y a escribir de vuelta solo lo que quedó ligado. Pasarlas
   como kwargs inventa un `NameError` en caminos que el original ni recorre.
7. **Un test verde no prueba nada si no puede fallar.** Cada red nueva se validó
   por mutación: inyectar el fallo y comprobar que se pone roja.

---

## 1. Diagnóstico medido

| Métrica | Valor |
|---|---|
| Líneas de `main.py` | **25 333** (1,37 MB) |
| Clases de módulo | 19 |
| Funciones de módulo | 198 |
| **La función `agent()`** | líneas **9834–25333** = **15 500 líneas (61 % del archivo)** |
| Variables locales asignadas dentro de `agent()` | **1 784** |
| Globals mutables entre turnos | **35** |
| Sentencias `global` | 40 |
| Tests | 63 archivos · **930 pasan, 8 skip, en 2,46 s** |
| Tests que hacen `import main as m` | 52 |
| **Escrituras de test a globals de `main`** (`m.plan = …`) | **1 285** |

### El reparto real del archivo

```text
  9 834 líneas   nivel de módulo   constantes, helpers, scorers ya extraídos
 15 500 líneas   agent()           una sola función
```

La mitad de módulo **ya está razonablemente ordenada**: constantes (954), helpers de
cálculo, y diez scorers `_score_*_play(ctx: DecisionContext)` que son funciones puras.
Ese trabajo previo es el que hace viable el resto.

El problema real es `agent()`: 15 500 líneas de código lineal donde cada fase deja
variables locales que leen las fases siguientes.

### La medición que decide el orden del refactor

Aunque `agent()` asigna 1 784 locales, **casi ninguna vive mucho**. Contando cuántas
variables se asignan antes de un punto de corte y se leen después:

| Corte (línea) | Qué separa | **Variables vivas que cruzan** |
|---:|---|---:|
| 24446 | post-proceso / finalize | **47**  ← el corte más barato |
| 10942 | setup+matchup / análisis de amenaza | **128** |
| 13476 | amenaza / supporters y banderas | **141** |
| 16728 | banderas / promoción tras KO | **198** |
| 18109 | promoción / bucle de puntuación | **223** |

**Conclusión operativa: se corta por donde el conjunto vivo es más estrecho, empezando
por el más estrecho.** Un corte de 47 variables es un `dataclass` perfectamente legible;
uno de 223 no lo es hasta que las olas previas hayan vaciado el resto.

---

## 2. Invariantes: lo que el refactor NO puede romper

Cinco restricciones duras. Cada ola se verifica contra todas.

### I1 — El contenedor de Kaggle no *importa* `main.py`: lo `exec`uta

Esta es la restricción que más condiciona el diseño, y no es evidente. El contenedor
([kaggle-environments/docker/Dockerfile](https://github.com/Kaggle/kaggle-environments/blob/master/docker/Dockerfile),
base `gcr.io/kaggle-images/python`) carga al agente con
`kaggle_environments.agent.get_last_callable`, cuyo cuerpo es literalmente:

```python
code_object = compile(raw, path_str, "exec")
env = {}
if path is not None:
    exec_dir = os.path.dirname(path)
    sys.path.append(exec_dir)     # ← el dir del agente entra en sys.path…
exec(code_object, env)
if exec_dir is not None:
    sys.path.pop()                # ← …y sale INMEDIATAMENTE después
return [v for v in env.values() if callable(v)][-1]   # ← el ÚLTIMO callable
```

De ahí salen **cuatro reglas duras**, todas verificadas empíricamente reproduciendo
este cargador *verbatim* (§2.1):

- **I1a — `ptcg` debe importarse a NIVEL DE MÓDULO en `main.py`.** El dir del agente
  está en `sys.path` solo **durante** el `exec` de `main.py`. Un `import ptcg…` diferido
  a tiempo de decisión revienta con `ModuleNotFoundError: No module named 'ptcg'` en
  mitad de una partida. (Un import perezoso de un **submódulo** de un paquete ya
  importado sí funciona — el `__path__` del padre es absoluto — pero no conviene
  depender de esa sutileza.)

- **I1b — `def agent` tiene que ser lo ÚLTIMO que liga un callable nuevo en `main.py`.**
  El cargador devuelve `[…][-1]` sobre los valores del *namespace*, y **una clase también
  es callable**. Un re-export colocado *después* de `def agent` **secuestra el punto de
  entrada**: en la prueba, `from ptcg.calculo.energia import grass_mult` tras `def agent`
  hizo que el contenedor tomara `grass_mult` como agente y muriera con
  `TypeError: grass_mult() takes 0 positional arguments but 1 was given`.
  **Es silencioso, catastrófico y los 930 tests no lo ven.** Ver el choque con I3.

- **I1c — `main.py` NO existe como módulo.** Se `exec`uta en un `dict` vacío; nunca entra
  en `sys.modules`. Verificado: `'main' in sys.modules → False`. Ningún submódulo puede
  hacer `import main` (falla con `ModuleNotFoundError: No module named 'main'`). Esto
  **elimina** una de las dos opciones de la Ola 3 (ver allí).

- **I1d — No hay `chdir`.** Por eso `main.py` lleva el *fallback*
  `/kaggle_simulations/agent/deck.csv`. Cualquier lectura de fichero nueva necesita el
  mismo doble camino.

Y sigue faltando lo de siempre: añadir `ptcg/` a `utils/empaquetar_proyecto.py` (hoy solo
mete `main.py`, `deck.csv` y `cg/`) y un **test de humo de submission**, que es el único
fallo del refactor invisible para la suite.

### I2 — `agent(obs_dict) -> list[int]` sigue viviendo en `main.py`

Es el contrato con el simulador. `main.py` termina siendo una fachada delgada.

### I3 — `main.py` debe seguir re-exportando lo que los tests tocan

52 tests hacen `import main as m` y leen atributos privados (`m._score_xerosic_play`,
`m._CtxLillie`, `m._ub_cancel_stamp`…). La fachada tiene que re-exportarlos o los tests
se caen en masa.

**⚠ I3 choca de frente con I1b.** Los re-exports son exactamente lo que uno tiende a
poner al final del archivo ("bloque de compatibilidad"), y ahí **rompen la submission
sin romper ningún test**. Regla operativa:

```python
# main.py — ORDEN OBLIGATORIO
from ptcg.cartas.ids import *          # ①  todos los imports y re-exports…
from ptcg.decision.ultra_ball import _score_ultra_ball_play   # …van ARRIBA
...
def agent(obs_dict):                   # ②  y `agent` va AL FINAL, sin excepción
    ...
# ③  NADA después de esta línea que ligue un callable nuevo
```

Se blinda con un test dedicado en la Ola 0 que aplica el cargador real a `main.py` y
afirma `fn.__name__ == "agent"`.

### I4 — Equivalencia **bit-exacta**, no "neutro"

Este agente es una heurística afinada: cada puntaje está calibrado. La política del
proyecto para cambios de estrategia es *"NEUTRO se revierte, salvo valor ilegal"*; para
un **refactor** el listón es más alto: **la decisión devuelta tiene que ser idéntica,
opción por opción**. Un refactor que mueve el winrate —aunque sea hacia arriba— es un
refactor con un bug. La mejora estratégica va en commits aparte, después.

### I5 — El estado global es la trampa mortal

Los 35 globals mutables (`plan`, `ko_last_turn`, `CARTAS_ACTIVAS_EN_MAZO`,
`op_is_crustle_deck`, `_ub_meowth_pending`, …) persisten **entre turnos**.

Al partir en módulos aparece un fallo silencioso clásico de Python:

```python
# ptcg/decision/ultra_ball.py
from ptcg.estado import ko_last_turn      # ← COPIA el valor en el momento del import

# main.py
global ko_last_turn; ko_last_turn = True  # ← rebind: el módulo de arriba NO se entera
```

El módulo se queda mirando un valor congelado del arranque. No lanza excepción, no rompe
ningún test unitario que fije el global por su cuenta — simplemente el agente decide mal
en partida real. **Regla absoluta del refactor: nunca `from … import <mutable>`; siempre
acceso por objeto** (`estado.ko_last_turn` o `ESTADO.ko_last_turn`). Se verifica con un
*linter* propio (§4, Ola 0).

---

## 2.1 Verificación empírica: el refactor modular SÍ funciona en el contenedor

No es una deducción: se reprodujo `get_last_callable` *verbatim* y se probó cada caso.

**Prueba de humo end-to-end (la que decide).** Se extrajo de verdad un bloque real de
`main.py` (`RETREAT_COST`, 105 líneas) a `ptcg/cartas/tablas.py`, se empaquetó
`main.py + deck.csv + cg/ + ptcg/` en un `submission.tar.gz`, se descomprimió en un
directorio limpio, se cargó con el cargador real y se decidió sobre una observación de
fixture, con el **CWD fuera del directorio del agente**:

```text
extraido a ptcg/: RETREAT_COST (105 lineas)
submission.tar.gz: 2,311,416 bytes
contenido: ['cg', 'deck.csv', 'main.py', 'ptcg']

callable devuelto      : agent
decision main.py orig  : [0]
decision modularizado  : [0]
IDENTICAS              : True   ✅
```

**Matriz de casos.** Lo que funciona y lo que mata la submission:

| Caso | Resultado |
|---|---|
| `main.py` actual → ¿qué callable devuelve el cargador? | ✅ `agent` |
| Fachada con `import ptcg…` arriba y `def agent` al final | ✅ funciona |
| Re-export **antes** de `def agent` (I3 bien puesto) | ✅ funciona |
| Import perezoso de un **submódulo** de un paquete ya importado | ✅ funciona (`__path__` absoluto) |
| **Re-export después de `def agent`** | ❌ el cargador devuelve `grass_mult`; `TypeError` en partida |
| **Primer toque de `ptcg` diferido a tiempo de decisión** | ❌ `ModuleNotFoundError: No module named 'ptcg'` |
| **`import main` desde un submódulo** | ❌ `ModuleNotFoundError: No module named 'main'` |

Las tres filas rojas **no las detecta ninguno de los 930 tests**, porque bajo `pytest`
`main` sí es un módulo importado normalmente y el directorio del proyecto sí está en
`sys.path` de forma permanente. Es exactamente el hueco que tapa `tests/test_submission.py`.

**Corroboración independiente:** el `main.py` actual ya hace `from cg.api import …` a
nivel de módulo y funciona en competición. Eso solo es posible si el dir del agente entra
en `sys.path` durante el `exec` — es decir, confirma este cargador desde el otro lado.
`ptcg/` viaja por la misma vía que `cg/`, que lleva meses funcionando.

**Riesgo residual:** el reto usa la convención `/kaggle_simulations/agent/`, coherente con
este cargador, pero si el runner del PTCG AI Battle tuviera un envoltorio propio, el
mecanismo podría diferir. Barato de descartar: subir la primera submission modularizada
(Ola 1, solo constantes) y comprobar que puntúa antes de seguir con las olas grandes.

---

## 3. Arquitectura objetivo

Paquete `ptcg/`, dos niveles como máximo, ~40 módulos, ninguno por encima de ~1 500 líneas.
Las regiones entre corchetes son las líneas actuales de `main.py`.

```text
main.py                       ~200   fachada: agent() + re-exports (I2, I3)
deck.csv, cg/                        sin cambios

ptcg/
  cartas/
    ids.py              ~600   IDs y grupos (MAIN_ATTACKERS, OUR_EX_IDS…)   [40-994]
    tablas.py           ~400   RETREAT_COST, ATTACK_ENERGY_REQ, HP, debilidad
    lineas.py           ~240   etapa/raíz/cadenas evolutivas                [1205-1447]

  motor/
    reglas.py            ~60   _ReglaFija, _Ajuste, _resolver_*, _E         [1009-1069]
    plan.py              ~40   AttackPlan                                   [1069-1080]
    contexto.py         ~150   DecisionContext                              [3716-3867]

  calculo/                     — funciones PURAS, sin estado global —
    energia.py          ~180   _grass_*, _physical_energy, _can_attack_eff  [1081-1205]
    planta.py           ~360   _plan_de_planta y helpers                    [1612-1972]
    probabilidad.py     ~310   _prob_*, _pesca_de_remate                    [1972-2283]
    dano.py             ~520   daño efectivo, autodaño, proyecciones        [2438-2959]

  estado/                      — el ÚNICO sitio con estado mutable —
    agente.py           ~120   EstadoAgente: los 35 globals + reset()
    tracking.py         ~155   CARTAS_ACTIVAS_EN_MAZO, creencia             [2283-2438]
    logs.py             ~250   _process_logs, ventana de KO, _sync_from_state [2959-3210]
    matchup.py          ~350   detección op_is_*_deck                       [dentro de agent()]

  decision/                    — un módulo por carta: scorer + su contexto —
    boss_orders.py      ~820   scorer [3867-4202] + gusteo objetivo [9353-9834]
    ultra_ball.py      ~2260   orquestador [5558-6807] + ctx [7504-8162] + target [3363-3716]
    lillie.py           ~700   [6807-7504]
    night_stretcher.py ~1290   scorer [4606-5261] + ctx fetch [8162-8796]
    poke_pad.py         ~680   scorer [4481-4606] + ctx [8796-9353]
    xerosic.py          ~120   [4361-4481]
    unfair_stamp.py     ~160   [4202-4361]
    bug_catching_set.py ~135   [5423-5558]
    estadios.py         ~330   Forest of Vitality [5261-5423] + Grand Tree [1447-1612]
    supporters.py       ~125   Dawn, Lana's, _mejor_supporter_de_mano       [7379-7504]

  turno/                       — las fases de agent() —
    ctx.py              ~250   TurnoCtx: el "pizarrón" que cruza las fases
    fase1_setup.py     ~1100   setup, tracking, matchup                     [9834-10942]
    fase2_amenaza.py   ~2530   amenaza, plan de ataque, pivotes             [10942-13476]
    fase3_banderas.py  ~3250   supporters, banderas, energía                [13476-16728]
    fase4_promocion.py ~1380   promoción tras KO, selección                 [16728-18109]
    fase6_finalize.py   ~890   tiers, argmax, rescates                      [24446-25334]
    puntuacion/                — fase 5, un módulo por OptionType —         [18109-24446]
      __init__.py        ~80   despacho por o.type
      card.py          ~2140   [18150-20286]   (candidato a subdividir después)
      play.py          ~1490   [20286-21778]
      retreat.py       ~1430   [22824-24252]
      ability.py        ~510   [22311-22824]
      evolve.py         ~310   [22004-22311]
      attach.py         ~230   [21778-22004]
      attack.py         ~150   [24252-24403]
      end.py             ~45   [24403-24446]
```

### Las tres decisiones de diseño que sostienen todo esto

**(a) `TurnoCtx`: el pizarrón progresivo.** Las fases no se pasan 128–223 argumentos.
Reciben un `TurnoCtx` mutable que van poblando; la fase N lee lo que escribieron las
anteriores. Es exactamente el patrón `DecisionContext` que el proyecto ya usa en los
scorers, escalado al turno completo:

```python
@dataclass
class TurnoCtx:
    obs: Observation; state: ...; select: ...; my_state: ...; op_state: ...
    field_counts: dict; hand_counts: dict; ...          # ← fase 1
    plan_ataque: ...; active_ko_likely: bool; ...       # ← fase 2
    ...

def agent(obs_dict):
    ctx = TurnoCtx.desde(obs_dict)
    if ctx.sin_seleccion: return my_deck
    fase1_setup(ctx); fase2_amenaza(ctx); fase3_banderas(ctx); fase4_promocion(ctx)
    scores = puntuacion.evaluar(ctx)
    return fase6_finalize(ctx, scores)
```

**(b) `EstadoAgente`: un objeto, no 35 nombres sueltos.** Único dueño del estado
entre turnos, con `reset()` (que hoy está duplicado a mano en el fixture
`reset_main_state` de `tests/test_main.py` y en `golden_corpus.reset_agente`).
Elimina la clase de bug de I5 por construcción.

**(c) `calculo/` es puro por contrato.** Ningún módulo bajo `calculo/`, `cartas/`
o `motor/` puede tocar `estado`. Se verifica automáticamente (§4, Ola 0), no por
disciplina.

---

## 4. El proceso: siete olas

Cada ola tiene **precondición**, **mecánica**, **verificación** y **rollback**. Ninguna
ola empieza si la anterior no está verde. Rollback siempre = `git revert` de un commit
que toca solo esa ola.

### La puerta de verificación (idéntica en todas las olas)

```text
1. pytest -q                                       →  930 passed, 8 skipped   (2,5 s)
2. python utils/sombra.py main_pre_refactor.py main.py 200 200
                                                   →  0 flips                (~35 s)
3. python -m pytest tests/test_submission.py       →  la submission arranca
```

Si (2) reporta un solo flip, la ola **no se mergea**: se arregla o se revierte. No hay
"divergencia aceptable" en un refactor (I4).

El corpus dorado (`tests/golden_corpus.py`) **no entra en la puerta**: hoy está ciego
(ver Ola 0). Si se regenera, se añade como paso 4; si no, `sombra.py` lo cubre de sobra.

---

### Ola 0 — Instrumentar (no se toca `main.py`) · ✅ HECHA

> **Estado: completada.** `main.py` quedó intacto (md5 `15339b63…` antes y después).
> La suite pasó de **930 a 943 tests** (2,46 s → 6,25 s; los 3,8 s extra son los
> subprocesos del humo de submission, y valen cada milisegundo).
>
> Construido:
> - `main_pre_refactor.py` — copia congelada, *git-ignored* por `/main_pre_*.py`.
> - `tests/kaggle_loader.py` — el cargador de Kaggle copiado *verbatim*, **sin efectos
>   secundarios** (ver abajo por qué eso es crítico).
> - `tests/test_submission.py` — 5 tests: entry point, `main` fuera de `sys.modules`,
>   paquetes empaquetados, sin `__pycache__`, y el end-to-end tar→extraer→decidir.
> - `tests/test_arquitectura.py` — 8 tests: el linter en verde + una mutación por regla.
> - `utils/lint_arquitectura.py` — R1–R4; detecta los 35 mutables **derivándolos** de las
>   sentencias `global` de `main.py`, no de una lista escrita a mano.
> - `utils/empaquetar_proyecto.py` — reescrito: los paquetes a empaquetar se **derivan**
>   de los imports de nivel de módulo de `main.py` (`paquetes_locales_de`). Hoy detecta
>   `cg` y produce un tar idéntico al anterior; cuando la Ola 1 cree `ptcg/`, se incluye
>   solo con que `main.py` lo importe. Olvidarse era el fallo más caro posible.
>
> **Dos cosas se descubrieron construyendo, no diseñando:**
>
> 1. **El humo de submission tiene que correr en subprocesos.** `cg/sim.py` llama a
>    `lib.GameInitialize()` al importarse, y hacerlo dos veces en el mismo proceso
>    **aborta el intérprete** — así que no se puede descargar `cg` de `sys.modules` para
>    recargarlo desde la copia empaquetada. Un intérprete limpio por caso lo resuelve, y
>    de paso da el aislamiento que I1a exige de verdad.
> 2. **El cargador vive en su propio módulo por una razón de fondo.** La primera versión
>    lo tenía dentro de `test_submission.py`, y el runner lo importaba de ahí — con lo
>    que arrastraba al subproceso el `sys.path.insert(ROOT)` que ese archivo hace para
>    alcanzar `utils/`. Eso **enmascaraba I1a por completo**: el paquete importado tarde
>    sí se resolvía. `tests/kaggle_loader.py` no toca `sys.path` ni importa nada del
>    proyecto.
>
> **Las tres trampas están verificadas por mutación** (inyectar el fallo y comprobar que
> la red se pone roja — un test que no puede fallar no es una red):
>
> | Mutación inyectada | Suite normal | Humo de submission |
> |---|---|---|
> | Re-export tras `def agent` (I1b) | pasa | ❌ `se quedaría con 'to_observation_class' en vez de con 'agent'` |
> | `import` de paquete propio dentro de `agent()` (I1a) | **399 pasan** | ❌ `ModuleNotFoundError: No module named 'ptcg_prueba'` |
>
> La segunda fila es la justificación entera de esta ola: la suite pasó 399 tests sin
> enterarse de un cambio que rompe la submission en la primera decisión de la partida.

Esta ola es el 80 % de la seguridad del refactor. **Nada de las olas 1–7 debe empezar
antes de terminarla.**

**Precondición:** ninguna.

**El instrumento central YA EXISTE: `utils/sombra.py`.** Hace exactamente lo que este
refactor necesita — juega self-play conducido por la versión PRE-refactor y, en cada
decisión, consulta a la POST-refactor con la **misma observación** (`deepcopy`); toda
discrepancia es un flip y devuelve *exit 1*.

Verificado hoy contra el `main.py` actual (espejo consigo mismo):

```text
$ python utils/sombra.py <copia_congelada>.py main.py 25 25
espejo: 25 partidas, 3096 decisiones
rival:  25 partidas, 2435 decisiones
TOTAL FLIPS: 0                                    → 4,1 s
```

**5 531 decisiones comparadas en 4,1 segundos.** Es ~1 300 decisiones/s, así que un gate
de `200 200` (≈45 000 decisiones) cuesta unos 35 s. A ese precio la puerta se corre en
*cada commit* de cada ola, no al final. Es además mucho más fuerte y más barato que el
gate de winrate: el winrate necesita cientos de partidas para separar señal de ruido,
mientras que **una sola decisión distinta ya es prueba de bug**. `utils/selfplay.py`
sigue siendo el gate para cambios de *estrategia*; `sombra.py` es el de *estructura*.

Ojo con el CLI: los argumentos son posicionales y sin etiquetas —
`sombra.py <pre.py> <post.py> [n_espejo] [n_rival]`. Pasarle `espejo 3` revienta con
`ValueError`.

**Mecánica — lo que sí hay que construir (tres piezas):**

1. **`main_pre_refactor.py`** — copia congelada del `main.py` de hoy, referencia fija
   del arnés. El `.gitignore` ya excluye `/main_pre_*.py`, así que ese nombre la deja
   fuera de git automáticamente.

2. **`tests/test_submission.py`** — el hueco de I1, y **el único fallo del refactor que
   los 930 tests no detectarían**. No basta con "importar y llamar": tiene que
   **reproducir el cargador de Kaggle**, porque los tres modos de fallo de §2.1 solo
   aparecen ahí. Tres aserciones:
   - `empaquetar_proyecto` mete `ptcg/` en el tar;
   - descomprimir en un temporal, `chdir` fuera, cargar con una copia *verbatim* de
     `get_last_callable` y comprobar **`fn.__name__ == "agent"`** (I1b);
   - llamar a `fn(obs)` con una observación de fixture y comparar con la decisión del
     `main.py` de referencia (I1a, I1c).

   La copia de `get_last_callable` se pega tal cual en el test; `kaggle_environments`
   **no** se añade a `requirements-dev.txt` (el agente no depende de nada externo y esa
   restricción del proyecto se mantiene).

3. **`utils/lint_arquitectura.py`** — cuatro reglas AST:
   - **R1 (I5):** ningún `from <modulo> import <nombre>` donde `<nombre>` esté en la
     lista de 35 mutables.
   - **R2 (pureza):** ningún módulo bajo `cartas/`, `motor/` o `calculo/` referencia
     `ptcg.estado`.
   - **R3 (I1b):** en `main.py`, ningún `def`/`class`/`import` que ligue un nombre nuevo
     **después** de `def agent`.
   - **R4 (I1a/I1c):** ningún `import ptcg…` dentro del cuerpo de una función, y ningún
     `import main` en todo `ptcg/`.

   Opcionalmente **`tests/test_fachada.py`**, que congela el contrato I3 (los nombres que
   tests y `utils/` consumen de `main`) para que una rotura de fachada salga como un
   fallo legible en vez de 40 errores de import.

**Sobre el corpus dorado: está ciego y no merece la pena arreglarlo para esto.**
`registros/decisiones_dorado.json` existe (2 ago) pero los `registros/registro_*.json`
que lo originaron ya no están — son datos locales *git-ignored*. Por eso
`tests/test_golden_corpus.py` sale como **skip** (`no hay registros locales que
reproducir`), y es uno de los 8 skips de la suite: la red *parece* verde pero no cubre
nada. `sombra.py` genera sus propias observaciones jugando, así que **no depende de
`registros/` y cubre este refactor de sobra**. Regenerar el corpus es útil para el
trabajo de estrategia posterior, no un bloqueante de la Ola 0.

**Verificación:** el espejo de arriba, ya en verde. Si algún día diverge consigo mismo,
el arnés tiene un bug (probable fuga de estado entre instancias) y nada de lo que diga
es fiable.

---

### Ola 1 — Datos puros · riesgo prácticamente nulo · ✅ HECHA

> **Estado: completada.** `main.py` **25 333 → 24 604 líneas**; nace
> `ptcg/cartas/ids.py` (952 líneas, 201 constantes, **310 líneas de comentario
> conservadas**). Puerta completa en verde:
>
> ```text
> pytest -q                          943 passed, 8 skipped   (4,6 s)
> sombra.py …pre… main.py 300 300    67.250 decisiones, 0 flips   (36 s)
> lint_arquitectura.py               sin infracciones
> empaquetar_proyecto.py             ptcg/ incluido AUTOMATICAMENTE
> ```
>
> **El empaquetado derivado funcionó como se diseñó:** `ptcg/__init__.py`,
> `ptcg/cartas/__init__.py` y `ptcg/cartas/ids.py` aparecieron en el tar sin tocar
> `utils/empaquetar_proyecto.py`, solo porque `main.py` importa `ptcg.cartas.ids`.
>
> **Verificación extra, más fuerte que la puerta.** Se cargaron el `main.py`
> congelado y el refactorizado como módulos independientes y se compararon **los
> 600 nombres de nivel de módulo**: 600 en ambos, ninguno perdido, ninguno nuevo.
> Aparecían 71 valores "distintos" (todos `_REGLAS_*`/`_AJUSTES_*`), pero el
> experimento de control —comparar el congelado **consigo mismo**— produce
> exactamente los mismos 71: es un artefacto de comparar objetos-función de dos
> módulos distintos, no una diferencia real. **Diferencias reales: ninguna.**
>
> **La trampa que apareció: `my_deck = []`.** Pasa cualquier filtro de "valor
> literal" y sin embargo NO es una constante: se llena leyendo `deck.csv` tres
> líneas más abajo y `agent()` lo devuelve entero en el mulligan. Moverlo habría
> dejado el mazo del agente en otro módulo con `main.py` mutando el mismo objeto
> por accidente. Por eso `utils/extraer_puros.py` descarta todo nombre que reciba
> `.append/.update/.add`, un *subscript-store*, un `global` o un `augassign`; de
> los 205 bindings de la región, ése era el único.
>
> **El import va en la cabecera, no donde cae.** La herramienta lo inserta donde
> estaba el primer rango — a media altura, tras `attack_table`. Funciona, pero se
> movió a mano al bloque de imports: es donde tiene que estar por I1a, y así lo
> avisa la propia herramienta al terminar.
>
> Queda material para la Ola 2: la herramienta encuentra 8 constantes puras más
> (50 líneas) que antes caían fuera del rango.

#### Plan original

**Mecánica:** mover a `ptcg/cartas/` las constantes de `[40-994]` (IDs, `RETREAT_COST`,
`ATTACK_ENERGY_REQ`, HP, debilidades). `main.py` añade `from ptcg.cartas.ids import *`.
Cero lógica, cero estado. `_validate_id_constants()` (línea 806) se muda con ellas y
sigue corriendo al import.

**Por qué primero:** saca ~950 líneas, ejercita el circuito completo (paquete nuevo →
empaquetado → submission → fachada → tests) con el material menos peligroso posible.
Es el ensayo del andamiaje, no del refactor.

**Verificación:** puerta completa. El humo de submission es lo que importa aquí: es la
primera vez que `ptcg/` tiene que viajar en el tar. **Y es la ola que conviene subir de
verdad a la competición** para descartar el riesgo residual de §2.1 con el cambio más
inocuo posible (constantes puras) antes de invertir en las olas grandes.

---

### Ola 2 — Helpers puros · riesgo bajo · ✅ HECHA (con recorte)

> **Estado: completada, pero mucho más pequeña de lo estimado.** `main.py`
> **24 604 → 24 362**; el paquete pasa a **8 módulos, 1 367 líneas**. Puerta:
>
> ```text
> pytest -q                          943 passed, 8 skipped
> sombra.py …pre… main.py 300 300    68.686 decisiones, 0 flips
> lint_arquitectura.py               sin infracciones
> empaquetar_proyecto.py             los 8 módulos, automáticamente
> ```
>
> Se movieron: `motor/reglas.py` (`_ReglaFija`, `_Ajuste`, `_resolver_*`, `_E`),
> `motor/plan.py` (`AttackPlan`), `calculo/energia.py`, `calculo/probabilidad.py`,
> `calculo/dano.py`, más `cartas/tablas.py` (`card_table`/`attack_table`) y
> `cartas/grupos.py` (`EVO_LINES` y compañía).
>
> **La estimación de ~1 900 líneas era optimista.** El análisis de pureza
> (`utils/pureza.py`, escrito para esto) demuestra que la mayoría de los
> "helpers puros" no lo son: de 217 definiciones de módulo, 108 están bloqueadas,
> y las causas raíz son estado real —`CARTAS_ACTIVAS_EN_MAZO`, `ATTACK_ENERGY_REQ`,
> `meganium_in_play`, `forest_in_play`—, es decir, **material de Ola 3, no de Ola 2**.
> Eso no es un fallo del plan: es la precondición haciendo su trabajo.
>
> **Hallazgo 1 — `ATTACK_ENERGY_REQ` es estado mutable disfrazado de tabla.**
> `_aplicar_impuesto_tera` le reescribe entradas en **cada** `agent()` (el impuesto
> de Nighttime Mine) y **56 sitios la leen**, pero no aparece en ninguna sentencia
> `global`: mutar un dict no lo exige. La primera versión de `utils/pureza.py` la
> daba por constante. Es la misma clase de trampa que `my_deck` en la Ola 1, y
> ahora ambas herramientas comparten la detección de mutación
> (`.append/.update/subscript-store/augassign`). **Añádela mentalmente a los 35
> globals**: son 36 piezas de estado, no 35.
>
> **Hallazgo 2 — por qué los consumidores de `card_table` NO se movieron.**
> Mover las tablas desbloqueaba 20 definiciones (`_our_effective_damage`,
> `get_card`, `prize_count`, `_etapa_evolutiva`…) y se intentó. Falló un test:
> `test_our_effective_damage_applies_weakness_and_resistance` hace
> `monkeypatch.setattr(m, "card_table", …)`, y la función movida ya no lee el
> nombre de `main` sino su propia copia. **Y actualizar el test no lo arregla**:
> cuatro módulos del paquete hacen `from ptcg.cartas.tablas import card_table`, así
> que parchear el original tampoco les llega — cada uno congeló su binding al
> importar. Es I5 exactamente, sobre una tabla que en producción nunca se
> reasigna (por eso `sombra` no habría visto nada).
>
> El arreglo correcto es acceso por objeto de módulo (`tablas.card_table`), que es
> lo que R1 ya exige para los mutables — pero eso obliga a **reescribir** el código
> movido, y ahí se pierde la garantía de extracción verbatim que hace barata esta
> ola. Se descopa: los consumidores de `card_table` van a la Ola 3, junto con la
> decisión de quién posee el estado de módulo. `cartas/tablas.py` sí se queda,
> porque `main.py` la reexporta y el parcheo de los tests sigue funcionando.
>
> **Aviso de proceso.** `git checkout -- main.py` como "deshacer" revirtió las olas
> 1 y 2 enteras: no hay commits todavía, así que el último estado guardado es el
> `main.py` original. Se recuperó desde una instantánea del scratchpad. **Comitea
> cada ola** antes de empezar la siguiente, o usa instantáneas explícitas.

#### Plan original

**Mecánica:** mover `calculo/` (energía, planta, probabilidad, daño), `cartas/lineas.py`
y `motor/`. ~1 900 líneas.

**Precondición mecánica:** para cada función candidata, un script AST comprueba que no
referencia ninguno de los 35 mutables. **Si los referencia, no es candidata de esta ola** —
espera a la Ola 3. Esto convierte "creo que es pura" en un hecho verificado.

**Verificación:** puerta completa + `lint_arquitectura.py` R2 en verde.

---

### Ola 3 — Encapsular el estado global · **la ola de mayor riesgo**

Es el pivote de todo el refactor y merece su propio commit, su propia revisión y
posiblemente su propio día.

**El obstáculo real:** los tests escriben los globals de `main` **1 285 veces**
(`m.plan = …` ×177, `m.pre_turn = …` ×79, `m.meganium_in_play = …` ×68, …). Un
`ESTADO` nuevo no recibe esas escrituras, y `main.py` no puede reenviarlas: el
`__getattr__` de módulo (PEP 562) intercepta **lecturas**, no asignaciones. Es decir,
los tests seguirían pasando mientras el agente lee un estado que nadie actualiza —
exactamente el fallo silencioso de I5, pero disfrazado de suite verde.

**Solo queda una salida viable.** La opción "conservadora" — dejar el estado en `main.py`
y que los submódulos hagan `import main` perezoso — **es imposible en el contenedor**:
por I1c, `main.py` se `exec`uta en un `dict` vacío y nunca entra en `sys.modules`, así
que `import main` muere con `ModuleNotFoundError`. Bajo `pytest` funcionaría
perfectamente (ahí `main` sí es un módulo), de modo que esa vía habría pasado los 930
tests y roto la competición. Queda descartada, no por gusto de diseño sino por el
cargador.

**La salida:** `ptcg/estado/agente.py` es el dueño del estado; un *codemod* mecánico
reescribe las 1 285 escrituras de test (`m.plan` → `m.ESTADO.plan`, 35 nombres, un `sed`
por nombre) y los dos `reset` duplicados pasan a ser `m.ESTADO.reset()`. `main.py`
re-exporta `ESTADO` **antes** de `def agent` (I1b).

El churn de tests es grande en líneas y nulo en riesgo: el *codemod* es puramente
mecánico, un error en él produce un `AttributeError` ruidoso —no una decisión mal
tomada— y la suite tarda **2,46 s**, así que el ciclo de verificación es inmediato.

**Verificación:** puerta completa + `lint_arquitectura.py` R1 en verde + la Ola 3 se
corre con el gate ampliado `sombra.py … 500 500` (~110 000 decisiones, ~90 s): el
estado entre turnos es justo lo que las partidas largas ejercitan y las cortas no.

---

### Ola 4 — Scorers a `decision/` · riesgo bajo, botín alto

**Mecánica:** mover los diez `_score_*_play(ctx)` con sus `_Ctx*` y predicados a
`ptcg/decision/`, un módulo por carta. ~7 000 líneas, el mayor bloque del refactor
por volumen y el más barato por riesgo: ya son funciones que reciben un contexto
explícito. Es el patrón que `main-refactor-ultra-ball-plan.md` validó.

**Orden dentro de la ola** (de menos a más acoplado, un commit cada uno):
`unfair_stamp` → `xerosic` → `bug_catching_set` → `poke_pad` → `estadios` →
`supporters` → `night_stretcher` → `lillie` → `boss_orders` → `ultra_ball`.

`ultra_ball` va al final: es el más grande (~2 260 líneas con su contexto) y el que más
vetos cruzados tiene con Lillie's, Stamp, Fezandipiti y Meowth.

---

### Ola 5 — Partir `agent()` en fases · el corazón

**Mecánica:** introducir `TurnoCtx` y extraer las fases **en orden de conjunto vivo
creciente**, que es justo el orden inverso al del archivo:

| Paso | Corte | Vivas | Qué se extrae |
|---|---|---:|---|
| 5.1 | 24446 | **47** | `fase6_finalize` |
| 5.2 | 10942 | 128 | `fase1_setup` (+ `estado/matchup.py`) |
| 5.3 | 13476 | 141 | `fase2_amenaza` |
| 5.4 | 16728 | 198 | `fase3_banderas` |
| 5.5 | 18109 | 223 | `fase4_promocion` |

Cada paso es un commit y una pasada completa de la puerta. Los conjuntos vivos de los
pasos tardíos **encogen** a medida que los tempranos mueven variables a `TurnoCtx`,
así que los números de arriba son cotas superiores, no el trabajo real.

**Técnica por paso:** extraer literalmente el bloque a una función que recibe `ctx`,
convirtiendo cada variable viva en un campo de `TurnoCtx`. **Sin reescribir lógica, sin
renombrar, sin "de paso arreglar esto".** Cualquier mejora que se detecte se anota y se
hace en un commit posterior, medido con `selfplay.py` como cualquier cambio de estrategia.

---

### Ola 6 — Partir el bucle de puntuación

**Mecánica:** las ~6 340 líneas de `[18109-24446]` son un `if/elif` sobre `o.type`.
Cada rama sale a su módulo bajo `turno/puntuacion/` y el `__init__` queda como tabla de
despacho `{OptionType.X: modulo.puntuar}`. Es la ola más mecánica de las grandes: las
ramas ya están separadas por construcción.

`card.py` (~2 140) y `retreat.py` (~1 430) siguen siendo grandes; se subdividen después,
con el mismo proceso, una vez que el resto esté estable.

---

### Ola 7 — `main.py` como fachada

Queda en ~200 líneas: carga de `deck.csv`, `agent()` orquestando las fases, y los
re-exports que exige I3. `main_pre_refactor.py` se retira y `sombra.py` vuelve a su uso
normal: comparar contra una copia congelada puntual antes de cada cambio grande.

---

## 5. Resumen del recorrido

| Ola | Qué | Líneas fuera de `main.py` | Riesgo |
|---|---|---:|---|
| 0 | Instrumentar (arnés, corpus, linters) | 0 | — |
| 1 | Constantes | ~950 | nulo |
| 2 | Helpers puros | ~1 900 | bajo |
| 3 | **Estado global** | ~500 | **alto** |
| 4 | Scorers de carta | ~7 000 | bajo |
| 5 | Fases de `agent()` | ~9 200 | medio-alto |
| 6 | Bucle de puntuación | ~6 340 | medio |
| 7 | Fachada | — | bajo |
| | **`main.py` final** | **~200 líneas** | |

## 6. Reglas de oro

1. **Un refactor que cambia una decisión es un bug**, aunque suba el winrate (I4).
2. **Nunca `from … import <mutable>`** (I5). Lo vigila `lint_arquitectura.py` R1.
3. **Una ola, un commit, una puerta.** Nada de olas solapadas: si algo diverge, hay que
   poder responder *qué* lo causó con un `git revert` de una línea.
4. **Cero mejoras de paso.** Toda mejora estratégica va en un commit aparte, medida con
   `selfplay.py` según la política del proyecto.
5. **La Ola 0 no se recorta.** Sin la copia congelada y sin `tests/test_submission.py`,
   las olas 3, 5 y 6 son cambios a ciegas sobre 15 500 líneas de heurística afinada.
6. **`def agent` es lo último de `main.py`.** Un re-export puesto debajo secuestra el
   punto de entrada del contenedor sin que ningún test se entere (I1b, §2.1).
