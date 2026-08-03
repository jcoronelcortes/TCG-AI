# Documentación del proyecto

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

Esta carpeta agrupa la documentación por módulo del agente para el *PTCG AI Battle Challenge*: `main.py` es el agente (puntuación de opciones + argmax), `cg/` el simulador de la competencia, y `utils/` y `deck/` las utilidades. La documentación de `main.py` es de **bajo nivel**: explica en detalle la lógica y la estrategia de cada función y de cada bloque principal.

## Punto de partida

- **[main.md](main.md)** — Visión general del mecanismo (scores + argmax por `(tier, score)`), glosario compartido (energía efectiva/*Wild Growth*, `OptionType`/`SelectContext`, creencia `CARTAS_ACTIVAS_EN_MAZO`, detección de matchup e inferencia por descarte, `AttackPlan`, pivotes defensivos, motor Meowth ex) y **mapa temático** de los documentos numerados. **Empieza por aquí.**

## Documentación de bajo nivel de `main.py`

Cada archivo cubre una región del código, identificada por sus funciones y banderas (no por líneas). Núcleo y ayudantes (antes de `agent()`):

1. [Constantes y configuración](main-01-constants-and-config.md) — carga de `deck.csv`, `card_table`, `RETREAT_COST`, constantes de ID, conjuntos estratégicos y constantes de puntuación `SCORE_*`/`BOSS_*`.
2. [Núcleo de cálculo: energía, daño y ataque](main-02-core-calc-helpers.md) — `AttackPlan` y los ayudantes de energía efectiva, daño y "¿puede atacar?" (`_grass_mult`, `_can_attack_eff`, `_attacker_base_damage`, `_op_active_attack_damage_to`).
3. [Seguimiento de estado y creencia del mazo](main-03-state-tracking-and-belief.md) — `CARTAS_ACTIVAS_EN_MAZO` (copias por zona), identificación de premios y heurísticas de probabilidad.
4. [Utilidades de puntuación](main-04-scoring-helpers.md) — funciones puras de valoración (`get_card`, `pokemon_score`, `prize_count`, …) con `_eval_ub_best_target` como pieza central.

Interior de `agent()`:

5. [Preámbulo y conteos de tablero](main-05-agent-setup.md) — conversión de la observación, reinicio de turno, actualización de la creencia y conteos compartidos.
6. [Detección de matchup, debilidades e inmunidades](main-06-agent-matchup-detection.md) — el escáner del tablero rival: flags `op_is_*_deck`/`op_has_*` (incluida la inferencia por el descarte rival) y amenazas puntuales.
7. [Análisis de amenaza y plan de ataque](main-07-agent-threat-and-plan.md) — cálculo del `AttackPlan` (KO, lookahead, trades) y los overrides de pivote que lo reescriben.
8. [Escalera de puntuación de Boss's Orders](main-08-agent-boss-orders.md) — cuánto conviene jugar Boss's este turno: gusteos ganadores, deny-evo, muros y modo estorbo.
9. [Valoración de Supporters y banderas de decisión](main-09-agent-supporters-and-flags.md) — umbrales de Lillie's/Dawn/Lana's y las banderas pre-computadas que vetan o fuerzan jugadas.
10. [Puntuación de energía y contextos de cambio](main-10-agent-energy-and-switch.md) — `energy_score()` (a quién cargar la energía) y los contextos `ACTIVATE`/`SWITCH`/`TO_ACTIVE`/moneda.
11. [Bucle de puntuación — búsqueda y selección de cartas](main-11-agent-card-search-scoring.md) — setup inicial, objetivo de Boss's, búsquedas `TO_HAND` (Ultra Ball, Bug Catching Set, Poke Pad, Night Stretcher, Meowth, Dawn), `DISCARD`, `DAMAGE` y `ATTACH_FROM`.
12. [Bucle de puntuación — PLAY (jugar cartas)](main-12-agent-play-scoring.md) — bajar Pokémon y jugar Trainers/Estadio; invoca los scorers extraídos `_score_*_play(ctx)`.
13. [Bucle de puntuación — ATTACH / EVOLVE / ABILITY](main-13-agent-attach-evolve-ability.md) — adjunte manual, evoluciones y habilidades (*Teal Dance*, *Ripening Charge*, *Flip the Script*, *Last-Ditch Catch*).
14. [Bucle de puntuación — RETREAT](main-14-agent-retreat-scoring.md) — cuándo retirar al activo: pivotes, sacrificios y vetos.
15. [Bucle de puntuación — ATTACK / END y finalización](main-15-agent-attack-end-finalize.md) — vetos del ataque, `END`, tiers de orden de jugada (`_play_order_tier`) y el `return` final.

Transversal:

16. [Grand Tree: motor de evolución instantánea](main-16-grand-tree.md) — el estadio compartido id 1249: cadenas derivadas del mazo, qué línea construir, la habilidad, el tier `_TIER_STADIUM_ABILITY`, la retención del Forest of Vitality y la búsqueda del Básico raíz.

Documentos de refactor:

- [Arquitectura objetivo y proceso por olas](main-refactor-arquitectura.md) — **plan vigente**: en qué paquete se parte `main.py` (25 333 líneas, de las que `agent()` son 15 500), en qué orden, y con qué puerta de verificación (`utils/sombra.py` + los 930 tests) se demuestra que cada paso no cambia ni una decisión.
- [Plan del refactor de Ultra Ball](main-refactor-ultra-ball-plan.md) — refactor ya ejecutado (`_score_ultra_ball_play` como orquestador); se conserva como referencia de método (extracción verbatim + verificación por hash).

## Integración con el simulador (`cg/`)

- [cg.api](cg-api.md) — tipos, enumeraciones y conversión de observaciones.
- [cg.game](cg-game.md) — capa de acceso a la lógica de batalla nativa.
- [cg.sim](cg-sim.md) — carga de la librería nativa y estructuras `ctypes`.
- [cg.utils](cg-utils.md) — conversión dict/JSON → dataclass.

## Herramientas (`utils/` y `deck/`)

- [Reproducción de logs — `utils/log_replay.py` y `utils/split_turns.py`](utils-log-replay.md) — ejecuta `main.agent()` sobre un log real y compara con las acciones registradas; `split_turns` parte el log en registros por turno para reproducir decisiones.
- [Empaquetado de la submission — `utils/empaquetar_proyecto.py`](utils-empaquetar-proyecto.md) — genera `submission.tar.gz` en la raíz con `main.py`, `deck.csv` y los paquetes locales que `main.py` importa (hoy `cg/`; la lista se **deriva** de sus imports, no está escrita a mano).
- `utils/extraer_puros.py` — mecanismo de las olas 1-2: mueve a un módulo del paquete los bindings **puros** de un rango de `main.py`, por rangos de líneas (para que los comentarios viajen con lo que documentan) y descartando los nombres que se mutan en algún sitio (`my_deck` es el caso: parece constante y no lo es). Tiene *dry run* por defecto.
- `utils/lint_arquitectura.py` — cuatro reglas AST del refactor (R1 mutables importados por nombre · R2 pureza de `cartas/motor/calculo` · R3 `def agent` es lo último de `main.py` · R4 imports perezosos de paquetes propios e `import main`). Corre con la suite vía `tests/test_arquitectura.py`. Ver [arquitectura del refactor](main-refactor-arquitectura.md).
- `utils/sombra.py` — gate de equivalencia del refactor: juega self-play con la versión PRE y consulta a la POST con la misma observación; cualquier discrepancia es un flip. `python utils/sombra.py <pre.py> <post.py> [n_espejo] [n_rival]` (posicionales, sin etiquetas).
- [Imagen del mazo — `deck/render_deck_image.py`](deck-render-deck-image.md) — genera `deck/deck_en.jpg` a partir de `deck.csv` y los datos oficiales del challenge.

## Pruebas

La suite de pruebas está en `tests/` (unitarias de ayudantes de `main.py`, comportamiento de `agent()`, e integración `cg/`), con **fixtures** reales en `tests/fixtures/`. Ejecutar con:

```bash
pytest -q --cov=. --cov-report=term-missing
```

Para depurar decisiones concretas contra partidas reales, ver [Reproducción de logs](utils-log-replay.md).

> Nota: la documentación numerada `main-01…15` es un mapa **temático**; si dentro de algún documento aparecen rangos de línea, corresponden a la versión del código en que se escribió — localiza el código por los nombres de funciones y banderas.
