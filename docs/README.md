# Documentación del proyecto

Esta carpeta agrupa la documentación por módulo. La documentación de `main.py` es de **bajo nivel**: explica en detalle la lógica y la estrategia de cada función y de cada bloque principal, para que un programador entienda qué hace cada parte del código y cómo funciona la lógica del juego.

## Punto de partida

- **[main.md](main.md)** — Visión general, glosario compartido (mecanismo de selección por `scores`, energía efectiva/Meganium, `OptionType`/`SelectContext`, seguimiento de creencia, detección de matchup) y **mapa de regiones** con rangos de línea. **Empieza por aquí.**

## Documentación de bajo nivel de `main.py`

Núcleo y ayudantes (antes de `agent()`):

1. [Constantes y configuración](main-01-constants-and-config.md) — líneas 1–389
2. [Núcleo de cálculo: energía, daño y ataque](main-02-core-calc-helpers.md) — 391–667
3. [Seguimiento de estado y creencia del mazo](main-03-state-tracking-and-belief.md) — 484–860
4. [Utilidades de puntuación](main-04-scoring-helpers.md) — 687–1291

Interior de `agent()` (líneas 1292–12919):

5. [Preámbulo y conteos de tablero](main-05-agent-setup.md) — 1292–1476
6. [Detección de matchup, debilidades e inmunidades](main-06-agent-matchup-detection.md) — 1477–1985
7. [Análisis de amenaza y plan de ataque](main-07-agent-threat-and-plan.md) — 1985–2900
8. [Escalera de puntuación de Boss's Orders](main-08-agent-boss-orders.md) — ~2900–3595
9. [Valoración de Supporters y banderas de decisión](main-09-agent-supporters-and-flags.md) — 3595–4489
10. [Puntuación de energía y contextos de cambio](main-10-agent-energy-and-switch.md) — 4489–5970
11. [Bucle de puntuación — búsqueda y selección de cartas](main-11-agent-card-search-scoring.md) — 5970–8684
12. [Bucle de puntuación — PLAY (jugar cartas)](main-12-agent-play-scoring.md) — 8684–11008
13. [Bucle de puntuación — ATTACH / EVOLVE / ABILITY](main-13-agent-attach-evolve-ability.md) — 11008–11608
14. [Bucle de puntuación — RETREAT](main-14-agent-retreat-scoring.md) — 11608–12609
15. [Bucle de puntuación — ATTACK / END y finalización](main-15-agent-attack-end-finalize.md) — 12609–12919

## Integración con el simulador (`cg/`)

- [cg.api](cg-api.md)
- [cg.game](cg-game.md)
- [cg.sim](cg-sim.md)
- [cg.utils](cg-utils.md)

## Herramientas de depuración (`utils/`)

- [Reproducción de logs — `utils/log_replay.py`](utils-log-replay.md) — ejecuta `main.agent()` sobre un log real y compara con las acciones registradas.
- `utils/split_turns.py` — divide un log en registros por turno (para aislar el turno a depurar).

## Pruebas

La suite de pruebas está en `tests/` (unitarias de ayudantes de `main.py`, comportamiento de `agent()`, e integración `cg/`), con **fixtures** reales en `tests/fixtures/`. Ejecutar con:

```bash
pytest -q --cov=. --cov-report=term-missing
```

Para depurar decisiones concretas contra partidas reales, ver [Reproducción de logs](utils-log-replay.md).

> Nota: la documentación numerada `main-01…15` reemplaza a los antiguos documentos temáticos de `main.py`. Cada archivo indica en su título el rango de líneas exacto que cubre.
