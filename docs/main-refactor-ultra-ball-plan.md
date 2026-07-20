# Plan de descomposición — rama de scoring de Ultra Ball

## Progreso

- **Paso 1 — extracción verbatim: HECHO.** `_score_ultra_ball_play(ctx)` (556→2
  líneas en el bucle). Hash `2ee1c6a…` intacto; escaneo de globales por bytecode
  limpio.
- **Paso 2 — descomposición interna: EN CURSO.** Aisladas y verificadas (cada una
  con hash idéntico + escaneo de globales):
  - Fase A → `_ub_derive_flags(ctx) -> _UBFlags` (flags derivados).
  - Fases B+C+D → `_ub_score_before_overrides(ctx, _ubf)` (cortes, vetos, objetivo).
  - Fase E → `_ub_terminal_overrides(ctx, ub_score, …)` (overrides terminales).
  - `_score_ultra_ball_play` quedó como **orquestador de 4 líneas**.
  - Fase C → 4 predicados puros `_ub_cancel_{stamp,fez,lillie,meowth}(ctx) -> bool`
    (trigger + conteo verbatim; el llamador pone `ub_score = -1` si alguno cancela).
    Con tests unitarios propios.
  - Fase D → `_ub_target_score(ctx, _ubf) -> int` (valoración de objetivo + tiers).
    `_ub_score_before_overrides` quedó como orquestación fina (~40 líneas) donde la
    estructura de fases (B: cortes → C: vetos → D: objetivo) es por fin legible.
  - **DESCOMPOSICIÓN COMPLETA.** De 556 líneas monolíticas a 10 unidades aisladas
    y testeables (ver lista en `main.py`, sección scorers de Ultra Ball).
  - **Único pendiente (diferido, opcional y de mayor riesgo):** unificar los 5
    conteos de "fodder seguro" en un `_count_safe_discards` — SOLO si tras
    compararlos (ya están aislados y verbatim en los 4 predicados de C + Fase D)
    se demuestra que convergen. Si no convergen, se dejan separados.

---

Contexto: refactor Prioridad 1 (extraer
las ramas del bucle de scoring de `agent()` a funciones puras `_score_*(ctx)`).
Ya se extrajeron 6 ramas planas (Boss's, Unfair Stamp, Poke Pad, Night Stretcher,
Forest of Vitality, Bug Catching Set), todas verificadas por el **hash invariante**
de las 304 decisiones de `registros/` (`2ee1c6a…`).

Ultra Ball es la rama restante más grande (**556 líneas**) y, a diferencia de las
anteriores, **NO es plana**: entrelaza vetos de coste, búsqueda de objetivo y
overrides terminales. Por eso no se reubica a ciegas: primero se mueve verbatim y
después se descompone en pasos pequeños.

## Anatomía actual (main.py ~10392–10947)

La rama calcula `ub_score` (base 10000) en **5 fases secuenciales**:

| Fase | Líneas aprox | Qué hace | Salida |
|---|---|---|---|
| **A. Contexto derivado** | 10394–10481 | `_ub_survival_mode`, `_ub_op_ex_immune`, `_ub_evolve_needs_search`, `_ub_evolve_now_search`, `_ub_bench_energized`, `_ub_developed_attacker_board`, `hand_size` | flags locales |
| **B. Cortes duros tempranos** | 10482–10498 | `hand_size < 3` → −1; banca llena sin evo buscable → −1 | puede terminar |
| **C. Vetos por coste de descarte** | 10500–10681 | 4 guardas independientes: ¿jugar UB sacrificaría una carta valiosa como coste? (`_ub_cancel_for_stamp` / `_fez` / `_lillie` / `_meowth`) | `ub_score=-1` o sigue |
| **D. Valoración de objetivo + score** | 10683–10861 | `_eval_ub_best_target(...)` (helper ya extraído) + cadena Meowth→Lillie + conteo `safe_discards` + mapeo a tiers 10000–12500 + penalizaciones + deferral de Lillie's | `ub_score` principal |
| **E. Overrides terminales** | 10863–10945 | rescate modo-supervivencia (→25000), Bug Catching Set (−1500), gate de primer turno (→−1), salvaguarda FINAL banca llena (→−1), deferral línea Alakazam (→2000) | `ub_score` final |

Observaciones clave:
- Las Fases C y D repiten **5 veces** el patrón *"contar descartes seguros sin
  tocar la carta X"* con reglas casi idénticas (energía siempre segura; pre-evos
  seguras solo si su línea ya está en juego / en mazo / hay Night Stretcher; etc.).
  Es el mayor foco de duplicación.
- La Fase D ya **delega** el núcleo a dos helpers de módulo:
  `_count_hand_play_options` (L947) y `_eval_ub_best_target` (L973).
- La Fase E son overrides terminales en orden; el último que aplica gana.

## ⚠️ Trampa de flujo de control (corregido tras revisión)

Los cortes de las Fases B, C y D **NO son terminales**: ponen `ub_score = -1` pero
la ejecución **continúa** hasta la Fase E, que corre SIEMPRE. En particular el
rescate de modo-supervivencia (L10866) revisa `ub_score <= 0` y puede subirlo a
25000 justamente cuando un corte previo lo dejó en −1. Por eso el esqueleto NO
puede hacer `return` temprano en B/C/D: se saltaría la Fase E y cambiaría el
comportamiento. Todo debe **hilar `ub_score`** a través de las 5 fases.

## Estrategia en dos pasos (la parte segura primero)

**Paso 1 — Extracción verbatim POR SCRIPT (bajo riesgo, idéntico a las otras 6).**
Para eliminar el riesgo de transcripción de 556 líneas, la copia se hace con un
script (no a mano): se copia el RANGO EXACTO de líneas del cuerpo, se le aplica un
`dedent`, y se antepone un bloque de *rebind* `nombre = ctx.x` para cada campo (como
en `_score_night_stretcher_play`). El cuerpo queda **byte-idéntico** salvo la
indentación; los nombres desnudos resuelven a los locales reboundeados. Reemplazar
la rama por `score = _score_ultra_ball_play(ctx)`.
**Verificación:** hash `2ee1c6a…` intacto + 79 tests + escaneo de globales (abajo).
Esto NO simplifica todavía; solo aísla la función y vacía el bucle de `agent()`.

**Paso 2 — Descomposición interna (varios sub-pasos, cada uno verificado).**
Con la función ya aislada, partirla en sub-helpers puros, **uno por commit**, cada
uno guardado por el mismo hash. Esqueleto CORREGIDO (Fase E siempre se aplica; B/C/D
no retornan, hilan `ub_score`):

```
def _score_ultra_ball_play(ctx) -> int:
    f = _ub_derive_flags(ctx)                        # Fase A: flags puros
    ub_score = _ub_score_before_overrides(ctx, f)    # Fases B+C+D: una cadena
                                                     #   if/elif/else; NO retorna
    ub_score = _ub_terminal_overrides(ctx, f, ub_score)  # Fase E: SIEMPRE
    return ub_score
```

Orden sugerido de sub-pasos (del más aislado al más entrelazado):
1. **Fase E** (`_ub_terminal_overrides(ctx, f, ub_score) -> int`): cadena de `if`
   sobre un `ub_score` ya calculado; la más fácil de aislar y testear. Debe recibir
   y devolver `ub_score` (no lo recalcula).
2. **Fase A** (`_ub_derive_flags`): cálculo puro de flags → devuelve un dataclass.
3. **Fase B+C+D** (`_ub_score_before_overrides`): se aísla como bloque ANTES de
   subdividir, para conservar exactamente la cadena `if/elif/else` y el hilo de
   `ub_score`. Solo DESPUÉS, y solo si el hash lo permite, se subdividen C y D.

Sobre los 5 conteos de "descartes seguros" (Fases C y D, ~150 líneas duplicadas):
NO unificarlos de entrada. Las 5 variantes tienen reglas SUTILMENTE distintas
(p.ej. la protección especial de Hydrapple/Dipplin/Meowth en el conteo de Lillie's
difiere del de Meowth y del `safe_discards` de la Fase D). El paso seguro es
extraer CADA conteo como su propio helper con nombre, verbatim y verificado por
hash. La unificación en un único `_count_safe_discards(..., protect={...})` queda
como trabajo OPCIONAL y posterior, solo si tras aislarlos se demuestra que
realmente convergen; si no convergen, se dejan separados. Nunca unificar "a ojo".

## Campos de ctx nuevos (Paso 1)

Ya presentes en el ctx (61 campos): `state, my_state, hand_counts, field_counts,
cartas_en_mazo, field_at_turn_start, bench_count, my_prize, op_prize, we_go_first,
forest_in_play, meganium_in_play, has_hydrapple, ko_last_turn, itchy_pollen_active,
mega_line_active, evolve_possible_in_play, watchtower_in_play, budew_op_index,
best_supp_in_hand_val, best_supp_in_mazo_val, op_is_crustle_deck,
op_is_cornerstone_deck, boss_deny_alakazam_line, …`.

Faltan **6** (todos definidos antes del build del ctx — verificado):
`op_has_ex_immune_active`, `op_has_ex_immune_bench`, `can_attack`,
`budew_on_op_field`, `win_via_boss_gust`, `gust_2prize_via_boss`.

## Protocolo de verificación (invariante en todo el refactor)

1. `python3 -m pytest -q` → los 79 tests verdes.
2. Replay de los 17 `registros/` → hash **`2ee1c6a…`** idéntico (script
   `scratchpad/replay_all.py`): prueba de que **ninguna** de las 304 decisiones
   cambió.
3. **Escaneo de globales prohibidos** (paso NUEVO y obligatorio — ver abajo).
4. Sin referencias colgantes a locales removidos dentro de `agent()`.
5. **Tests de rutas frías**: cobertura + unitarios (ver abajo).
6. Añadir 2–3 tests unitarios directos por sub-helper (posibles gracias al ctx).

Cualquier sub-paso que altere el hash se revierte: indica una divergencia, no una
mejora.

### 3-bis. Escaneo de globales prohibidos (el hash NO basta)

El hash es necesario pero **insuficiente**: si el cuerpo extraído lee por error un
GLOBAL de módulo homónimo (`meganium_in_play`, `forest_in_play`, `ko_last_turn`,
`we_go_first`, `op_is_crustle_deck`, `op_is_cornerstone_deck`,
`CARTAS_ACTIVAS_EN_MAZO`, `_field_at_turn_start`) en vez del valor del ctx, el
valor suele COINCIDIR con el local del agente en las 304 decisiones → el hash
queda verde y el bug queda latente para estados futuros donde difieran.

Mitigación: **rebindear TODOS esos nombres desde `ctx.*` al inicio de la función**
y ejecutar un escaneo que exija, para cada nombre de la denylist que aparezca en el
cuerpo, una línea de rebind `nombre = ctx.…` en la cabecera. Denylist (globales
mutables del reset fixture que la rama de UB toca):

```
meganium_in_play  forest_in_play  ko_last_turn  we_go_first
op_is_crustle_deck  op_is_cornerstone_deck  CARTAS_ACTIVAS_EN_MAZO  _field_at_turn_start
```

Los nombres que son SOLO locales del agente (sin global homónimo:
`has_hydrapple`, `can_attack`, `_best_supp_in_hand_val`, `budew_on_op_field`,
`_win_via_boss_gust`, …) son seguros "por ruido": si se olvidan, la función lanza
`NameError` y las pruebas fallan a gritos. El peligro silencioso es SOLO la
denylist de globales.

### 5-bis. Cobertura del hash (rutas frías)

Los 17 registros ejercitan solo algunos de los caminos de UB. Modo-supervivencia,
casos de primer turno (`_ub_ft_case1/2/3`), Budew, Crustle/Cornerstone, etc. pueden
NO dispararse en el replay, así que un fallo de transcripción/homónimo en ellos no
alteraría el hash. Antes de dar por bueno el Paso 1:
- medir con `pytest --cov` / conteo manual qué sub-caminos de UB toca el replay, y
- añadir tests unitarios sintéticos (construyendo `ctx`) para cada camino frío
  relevante, de modo que la cobertura de la función se acerque al 100 %.

## Riesgos y mitigaciones

- **Riesgo (ALTO):** los cortes de B/C/D no son terminales; un `return` temprano
  se saltaría la Fase E (p.ej. el rescate de supervivencia a 25000). *Mitigación:*
  hilar `ub_score` por las 5 fases; Fase E SIEMPRE al final. (Corregido en el
  esqueleto de arriba.)
- **Riesgo (ALTO):** global homónimo leído en vez del ctx; el hash no lo atrapa
  cuando global == local en el replay. *Mitigación:* rebind total desde `ctx.*` +
  escaneo de globales prohibidos (§3-bis).
- **Riesgo (MEDIO):** cobertura parcial del replay; rutas frías de UB sin ejercer.
  *Mitigación:* medir cobertura + tests unitarios sintéticos por camino (§5-bis).
- **Riesgo (MEDIO):** divergencia sutil al unificar los 5 conteos de fodder.
  *Mitigación:* NO unificar de entrada; extraer cada conteo verbatim por separado,
  cada uno con su hash; unificar solo si demuestran converger.
- **Riesgo (BAJO):** error de transcripción en 556 líneas. *Mitigación:* copia por
  script (rango exacto + `dedent`), no a mano.
- **Riesgo (BAJO):** la Fase E depende del ORDEN (último override gana).
  *Mitigación:* conservar el orden exacto de los `if`.

## No incluido (fuera de alcance de este plan)

Ningún cambio de comportamiento. Reescribir tiers/umbrales o simplificar la lógica
de negocio de Ultra Ball es un trabajo aparte, posterior, con su propia validación
por replay — nunca mezclado con la extracción.
