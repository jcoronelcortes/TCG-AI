# TCG-AI

## Descripción

`TCG-AI` es un agente heurístico para un simulador de Pokémon Trading Card Game (PTCG). El código principal está en `main.py` y define la función `agent(obs_dict)` que toma una observación del juego y devuelve la lista de índices de acción que el agente debe ejecutar.

El proyecto usa datos de cartas y un mazo propio definido en `deck.csv`. La lógica del agente evalúa el estado del tablero, la mano, la banca, el activo rival y la métrica de premios para tomar decisiones de juego.

## Estructura del repositorio

- `main.py`
  - Agente principal del proyecto.
  - Lee `deck.csv` para cargar la lista de cartas del mazo.
  - Define constantes, identificadores de cartas, costumbres de retirada y conjuntos de cartas importantes.
  - Sigue el estado de cartas en mazo, mano, banca, descartes y premios.
  - Calcula probabilidades de búsqueda y accesibilidad de cartas ocultas.
  - Evalúa ataques, apoyos (supporters), jugadas de energía y cambios estratégicos.
  - Ordena opciones de juego usando una puntuación basada en heurísticas específicas del mazo.

- `cg/`
  - Contiene la capa de integración con el simulador.
  - `cg/api.py`: definiciones de tipos de datos y enumeraciones usadas por el agente (`AreaType`, `OptionType`, `SelectContext`, `LogType`, `CardType`, `EnergyType`, `Observation`, etc.).
  - `cg/game.py`: interfaz con la librería nativa del simulador para iniciar la batalla, seleccionar acciones y consultar el estado.
  - `cg/sim.py` y `cg/utils.py`: utilidades internas para convertir datos JSON en objetos y soporte de simulación.

- `deck.csv`
  - Lista de 60 IDs de cartas que definen el mazo del agente.

- `decks_competidores/`
  - Mazos reales del top-100 del leaderboard de Kaggle, recuperados por
    `utils/descargar_mazos_competidores.py` (60 IDs por archivo, un ID por línea).
  - `indice.csv` clasifica cada mazo por arquetipo y guarda su posición y puntaje.

- `deck/rivales_reales/`
  - El corpus anterior deduplicado (100 mazos → 39 listas únicas) y cribado por
    pilotabilidad, generado por `utils/rivales_reales.py`.
  - `pesos.csv` da a cada lista su frecuencia real en el meta; es lo que consume
    `utils/matriz_matchups.py --pesos` para calcular el winrate esperado en ladder
    en vez de una media simple entre arquetipos que no se juegan por igual.
  - `no_pilotables/` guarda las listas que el bot genérico no sabe ejecutar: no
    son un fallo, son la parte del meta que el harness todavía no puede medir.

- `EN_Card_Data.csv`
  - Datos de referencia sobre cartas en inglés, probablemente usado para análisis o comparación.

## Cómo funciona `main.py`

### Flujo general

1. `main.py` carga el mazo desde `deck.csv`.
2. Crea un diccionario de datos de carta usando `all_card_data()` de `cg.api`.
3. Inicializa el seguimiento de estados de cartas con `CARTAS_ACTIVAS_EN_MAZO`.
4. En cada llamada a `agent(obs_dict)`:
   - Convierte la observación cruda a clases de `cg.api` con `to_observation_class()`.
   - Actualiza el estado del mazo y de premios a partir de la entrada y los registros de juego.
   - Analiza el tablero propio y el rival para detectar matchups, debilidades, inmunidades y amenazas.
   - Calcula si el rival puede atacar o si nuestro activo está en riesgo.
   - Evalúa el valor de ataques, cambios, retiros y jugadas de cartas con funciones de puntuación.
   - Prioriza la secuencia de juego (estadio, evoluciones, cartas de búsqueda, carga de energía, etc.).
   - Devuelve la lista de índices de selección para el entorno.

### Estrategias clave

- Energía y Meganium
  - El agente considera la energía en términos efectivos, ya que Meganium duplica la energía básica de Planta.
  - Las funciones `_grass_mult()` y `_grass_attach_unit()` normalizan esa conversión.

- Control de matchups de cartas
  - Existen bloques específicos para cartas como `Hydrapple ex`, `Teal Mask Ogerpon ex`, `Tapu Bulu`, `Fezandipiti ex`, `Crustle` y otras.
  - El agente detecta si el rival es un mazo de muro (`Crustle`/`Sylveon`), control (`Slowking`, `Alakazam_ex`, etc.), aggro o de premios altos (`Mega Lopunny ex`, `Marnie's Grimmsnarl ex`), y ajusta el valor de ciertos ataques y supporters.
  - **Detección de anulación de habilidad**: reconoce `Team Rocket's Watchtower` (estadio) y `Froslass` (banca rival), que inutilizan las habilidades de Pokémon incoloros como `Meowth ex`, y evita jugadas que dependerían de esa habilidad (con excepciones cuando no hay presión real y conviene cavar de todos modos).

- Priorización de cartas
  - El código asigna categorías de prioridad a las opciones jugables: energía de KO, estadio, desarrollo de Pokémon, Poke Pad, Bug Catching Set y carga de energía.
  - Esto permite respetar una secuencia lógica de juego cuando hay varias opciones válidas.

- Motor de refresco de mano (`Meowth ex` → `Lillie's Determination`)
  - Con la mano débil y `Lillie's Determination` todavía en el mazo, el agente prioriza bajar `Meowth ex` a la banca: su habilidad *Last-Ditch Catch* busca un Supporter → juega `Lillie's` → baraja la mano y roba de nuevo para abrir opciones de ataque.
  - Esta prioridad supera a jugar un cuerpo redundante, un ataque débil no letal contra un muro, o un Supporter de bajo valor (p.ej. `Lana's Aid` solo para recuperar 1 energía no letal).

- Seguimiento de cartas ocultas
  - El agente mantiene una creencia del mazo y premios propios para estimar qué cartas quedan disponibles.
  - Usa probabilidades de robos y acceso para valorar efectos como `Ultra Ball`, `Poke Pad` o `Lillie`s Determination.

## Uso

Este proyecto está pensado para integrarse con un simulador que llame a la función `agent(obs_dict)`.

### Ejecutar pruebas y cobertura

```bash
pytest -q --cov=. --cov-report=term-missing
```

La suite actual ya está pasando y el reporte de cobertura se genera automáticamente en CI.

Estructura de la carpeta `tests/`:

- `tests/test_main.py`: pruebas unitarias de los ayudantes de `main.py` y pruebas de comportamiento de `agent()` (tanto con observaciones sintéticas como reproduciendo estados reales de partida).
- `tests/test_cg_*.py`: pruebas de la capa de integración `cg/` (`api`, `game`, `sim`, `utils`, `log_replay`).
- `tests/fixtures/`: observaciones reales extraídas de logs de Kaggle y guardadas como JSON auto-contenido, para fijar regresiones de decisiones concretas del agente sin depender de la carpeta `log/` (que rota). Ejemplo: `marnie_grimmsnarl_step51.json` congela el paso 51 de la partida vs `Marnie's Grimmsnarl ex` donde el agente debe bajar `Meowth ex` en vez de jugar `Lana's Aid`.

Para reproducir/depurar una decisión concreta se puede dividir un log por turnos con `utils/split_turns.py` y alimentar la observación del paso a `main.agent()` (ver [docs/utils-log-replay.md](docs/utils-log-replay.md)).

Ejemplo de uso en un entorno de simulación:

```python
from main import agent

obs = obtener_observacion_del_simulador()
seleccion = agent(obs)
```

No existe un punto de entrada `__main__` en `main.py`, por lo que el archivo se usa como biblioteca de agente.

## Simulación local de logs

`utils/log_replay.py` reproduce logs de Kaggle ejecutando el agente sobre cada observación y comparando sus decisiones con las acciones registradas. Debe invocarse como módulo desde la raíz del repositorio (necesita `main` en el path):

```bash
PYTHONPATH="$PWD" python3 -m utils.log_replay log/86699707.json --verbose
```

Opciones útiles:
- `--max-items N`: detener después de N observaciones accionables.
- `--verbose`: imprimir cada observación procesada, decisión del agente y acción registrada en el log.
- `--interactive`: ejecutar en modo paso a paso y avanzar con `Enter` o salir con `q`.

Documentación detallada de la herramienta (funciones, resultados y advertencias de uso) en [docs/utils-log-replay.md](docs/utils-log-replay.md).

## Documentación

La documentación detallada por módulo está disponible en [docs/README.md](docs/README.md); empieza por [docs/main.md](docs/main.md) (visión general y glosario).

## Dependencias

**El agente no tiene ninguna dependencia de terceros, y es deliberado.** `main.py`,
`utils/` y el simulador vendorizado en `cg/` usan sólo la biblioteca estándar más
`ctypes` para la librería nativa, porque el agente se ejecuta en el entorno de
competición de Kaggle, donde no se instala nada. Antes de importar un paquete de
terceros en `main.py` o en `utils/`, comprobar que ese entorno lo tiene.

- Python 3.10+ (probado con 3.11.5).
- Las dependencias internas del simulador definidas en `cg/` (incluidas en el repo).

Lo que sí necesita instalarse es el entorno de **desarrollo**:

```bash
python -m pip install -r requirements-dev.txt   # pytest, pytest-cov, hypothesis
python -m pytest -q
```

Sin `hypothesis`, `tests/test_invariantes.py` no colecciona y pytest aborta la
corrida entera con un error de colección — no lo salta.

`requirements-render.txt` (pillow, numpy, pandas) es aparte y **opcional**: sólo
lo usa `deck/render_deck_image.py`.

## Objetivo del proyecto

Crear un agente capaz de jugar un mazo específico de PTCG con heurísticas de valor, búsqueda de objetivos y manejo de matchups. El enfoque principal es maximizar la eficiencia de ataques y la presión sobre el rival, considerando tanto KOs como la negación de premios y las amenazas de cartas rivales.

## Notas adicionales

- El archivo `main.py` contiene muchas reglas y funciones comentadas en español, lo cual facilita la adaptación de la estrategia.
- El mazo y las constantes de carta están configurados explícitamente para un mazo de Planta / ex con soporte de `Hydrapple ex`, `Teal Mask Ogerpon ex`, `Tapu Bulu` y otros.
- Si quieres, puedo también generar una documentación más técnica con diagramas de flujo de la función `agent` y los principales módulos.