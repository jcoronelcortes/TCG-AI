# `main.py` — Grand Tree: motor de evolución instantánea

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## La carta

**Grand Tree** (Estadio, ACE SPEC, `Grand_Tree = 1249`):

> Una vez durante el turno de cada jugador, ese jugador puede buscar en su baraja 1 Pokémon de Fase 1 que evolucione de uno de sus Pokémon Básicos y ponerlo sobre ese Pokémon para hacerlo evolucionar. Si ese Pokémon ha evolucionado de esta manera, ese jugador puede buscar en su baraja 1 Pokémon de Fase 2 que evolucione de ese Pokémon y ponerlo sobre ese Pokémon para hacerlo evolucionar. Después, ese jugador baraja las cartas de su baraja. *(Los jugadores no pueden hacer evolucionar a un Pokémon Básico durante su primer turno o a un Pokémon Básico que se haya puesto en juego en este turno.)*

Tres propiedades determinan toda la lógica:

1. **Es un estadio compartido.** El texto dice «durante el turno de **cada** jugador», así que la habilidad es nuestra tanto si bajamos la carta nosotros como si la baja el rival. Por eso `grand_tree_in_play` solo mira `stadium_id`, sin importar quién sea el dueño, y la carta **no** necesita estar en `deck.csv`.
2. **Es gratis.** No gasta la carta de la mano, ni el adjunte de energía, ni la evolución manual, ni el ataque. Construye una línea entera Básico → Fase 1 → Fase 2 sacándola del mazo (y de paso lo adelgaza). Es la jugada de desarrollo más rentable del turno.
3. **Necesita una raíz preexistente.** El Básico tiene que llevar en juego desde el principio del turno (`Pokemon.appearThisTurn == False`) y no vale nuestro primer turno. Como solo puede haber **un** estadio en mesa, *Forest of Vitality* nunca convive con Grand Tree: aquí el veto de «salió este turno» no se levanta.

---

## Tablas derivadas del mazo (deck-agnósticas)

`EVO_LINES` está escrita a mano para el mazo actual. El motor de Grand Tree no puede depender de eso, así que deriva las cadenas del mazo real leyendo `CardData.evolvesFrom` (que es el **nombre** de la pre-evolución, no un id):

- `_construir_cadenas_de_mazo(deck_ids)` → `(_EVO_POR_NOMBRE, _CADENAS_MAZO)`.
  - `_EVO_POR_NOMBRE`: nombre de la pre-evolución → ids del mazo que evolucionan de ella.
  - `_CADENAS_MAZO`: tuplas `(basico_id, fase1_id, fase2_id_o_0)`. Con `deck.csv` actual son `(Applin, Dipplin, Hydrapple ex)` y `(Chikorita, Bayleef, Meganium)`.
- `_GT_BASICOS_CON_CADENA`: los Básicos que abren alguna cadena.

Se calculan **una vez al importar el módulo**. Cambiar `deck.csv` cambia las cadenas sin tocar código.

---

## Qué cuerpo construir

La regla del usuario, generalizada a cualquier mazo, vive en el valor que `_gt_planes` asigna a cada plan:

| Componente | Constante | Papel |
| --- | --- | --- |
| `_gt_valor_cuerpo(final)` | — | PV del cuerpo resultante + `40` si tiene Habilidad. Término de calidad. |
| Llegar a Fase 2 | `GT_VALOR_ETAPA2` (2000) | Una cadena completa siempre gana a una que se queda en Fase 1. |
| No repetir cuerpo | `GT_VALOR_DIVERSIFICAR` (1200) | Se suma si esa Etapa 2 **no** está ya en juego. |
| Energía del Básico | — | Desempate, misma convención que la rama `EVOLVE` (`9000 + energía`). |
| Activo condenado | `GT_PENAL_ACTIVO_CONDENADO` (1500) | Resta si el objetivo es el **activo** condenado y la evolución entrega **más premios** que el Básico. |

`GT_VALOR_DIVERSIFICAR` es deliberadamente mayor que cualquier diferencia razonable de cuerpo, así que la diversificación manda cuando aplica. Con el mazo actual eso produce exactamente lo pedido:

| Tablero | Cadena elegida | Por qué |
| --- | --- | --- |
| Meganium en juego, sin Hydrapple ex | Applin → Dipplin → **Hydrapple ex** | diversificar (1200) |
| Hydrapple ex en juego, sin Meganium | Chikorita → Bayleef → **Meganium** | diversificar (1200) |
| **Ambos** en juego | Applin → Dipplin → **Hydrapple ex** | sin diversificación decide el cuerpo: 330 PV + Habilidad > 160 PV + Habilidad |
| Ninguno en juego | Applin → Dipplin → **Hydrapple ex** | los dos diversifican; decide el cuerpo |

> El último caso (**ninguna** Etapa 2 en juego) no estaba especificado en la petición: se resuelve por el mismo criterio de calidad de cuerpo que el caso «ambos». Si se prefiere abrir por Meganium (motor *Wild Growth*), basta con cambiar `_gt_valor_cuerpo`.

### Matchups anti-ex

Con `veta_etapa_ex` (Crustle / Sylveon / cualquier `op_has_ex_immune_*`) la Etapa 2 **ex** se descarta y esa cadena se queda **expresamente** en Fase 1 (`stage2_id == 0`). El paso 2 de la carta es opcional («puede buscar»), y regalar un cuerpo de 2 premios que no puede dañar al muro es peor que no evolucionar. Espeja el veto que ya tenía la rama `EVOLVE` de Hydrapple ex vs Crustle. En la práctica esto hace ganar a la línea no-ex (Meganium), que es el resultado deseado.

---

## Integración en `agent()`

Todo el motor está **apagado** salvo que `stadium_id == Grand_Tree` (o haya una copia jugable en la mano). Con `deck.csv` actual y los mazos rivales del repo, es código inerte: el corpus dorado no registra ni un cambio de decisión y el self-play contra `HEAD` da 51.7 % [IC95 42.8–60.4] sin errores.

### 1. Estado del turno

- `grand_tree_in_play` se fija junto a `forest_in_play` / `neutralization_zone_active`.
- `_gt_planes_turno` / `_gt_plan`: el ranking de planes ejecutables y el mejor, calculados **siempre** que el estadio esté en mesa (no solo cuando el menú ofrece la habilidad), porque también los consultan la retención del Forest y las sub-selecciones.
- `_gt_ability_slot`: posición de la opción `ABILITY` del estadio en **este** menú, identificada por la **carta** (id 1249), no por el área. Su ausencia significa que la habilidad ya se usó este turno.
- `_gt_ability_pending = _gt_ability_slot is not None and _gt_plan is not None`.
- `_gt_ranking_basicos` / `_gt_quiere_basico`: soporte del *fetch* de la raíz.
- `_gt_prompt_si_no`: `select.effect.id == Grand_Tree` (confirmaciones emitidas mientras se resuelve la habilidad).

`grand_tree_in_play` y `grand_tree_ability_pending` viajan en el `DecisionContext` (con default `False`, para no romper los tests que construyen el ctx a mano).

### 2. Usar la habilidad — rama `ABILITY`

Primera comprobación de la cadena, antes de *Teal Dance*:

- sin plan ejecutable → `SCORE_VETO` (activarla sin objetivo solo baraja el mazo);
- cadena completa → `GT_SCORE_CADENA_COMPLETA` (36000);
- cadena que se detiene en Fase 1 → `GT_SCORE_SOLO_FASE1` (34000).

Ambas bandas van por encima de la evolución desde la mano (Meganium 35000 / Hydrapple ex 33000 en el caso completo): si las dos jugadas están disponibles, primero la que **no** gasta carta.

### 3. Orden de jugada — `_TIER_STADIUM_ABILITY`

Nuevo tier `55`, entre `_TIER_KO_ENERGY` (60) y `_TIER_STADIUM` (50). Es el que de verdad garantiza el orden pedido por el usuario: **si primero bajásemos nuestro estadio, el Grand Tree se iría al descarte con la cadena gratis sin cobrar**. El score por sí solo no bastaría, porque las jugadas de estadio viven en un tier superior al de las habilidades.

### 4. Forest of Vitality — «primero la habilidad, después el reemplazo»

Regla `esperar_habilidad_grand_tree` en `_REGLAS_FOREST_PLAY`, justo después de `forest_ya_en_juego`: con `grand_tree_ability_pending` la jugada del Forest se **veta**. El estadio rival no se va a ningún sitio; se usa la habilidad y, en el **mismo turno**, ya sin la opción `ABILITY` en el menú, la regla deja de disparar y el Forest se juega con su score normal (`reemplazar_estadio_rival`, 15000).

Es el mismo mecanismo que «*Teal Dance* precede al adjunte manual»: vetar mientras la habilidad siga **ofrecida**, en vez de intentar ordenar dos acciones dentro de una sola llamada a `agent()`. Como `grand_tree_ability_pending` exige un plan ejecutable, un Grand Tree inútil (sin Básico evolucionable, o con la cadena agotada en el mazo) **no** retiene el Forest.

### 5. Sub-selecciones — `_gt_score_seleccion`

El simulador resuelve la habilidad en llamadas posteriores a `agent()`, con contextos que comparte con otras cartas. Por eso el corte se hace por `select.effect.id == Grand_Tree` **antes** que cualquier otro handler, tanto en la rama `CARD` como en la rama `EVOLVE`, y no se discrimina por `context` sino por dónde está la carta:

- **área `ACTIVE`/`BENCH`** («¿qué Pokémon mío evoluciona?»): manda el `serial` del plan; el orden de `_gt_planes_turno` es el orden de preferencia. Si no aparece, se prefiere un Básico con cadena disponible.
- **cualquier otra área** (`DECK`/`LOOKING`, «¿qué carta traigo?»): la Fase 2 del plan, luego la Fase 1, y de fondo un criterio deck-agnóstico — *cualquier evolución cuya pre-evolución esté en juego*, valorada por `_gt_valor_cuerpo` y con bono si aún no tenemos ese cuerpo. Ese fondo es el que resuelve el **paso 2**: una vez ejecutado el paso 1 el Básico ya es Fase 1 y `_gt_plan` deja de apuntarlo.

Nunca devuelve un veto: estas selecciones suelen ser obligatorias una vez activada la habilidad.

La rama `EVOLVE` además dejó de asumir `AreaType.HAND` y respeta `o.area` cuando el simulador la informa (para el juego normal vale `HAND`, así que el comportamiento no cambia); la evolución de Grand Tree sale del **mazo**.

### 6. Confirmaciones `YES`/`NO`

Con `_gt_prompt_si_no` se acepta **siempre**. No hay forma fiable de saber si el prompt es el paso 1 (buscar la Fase 1) o el paso 2 (la Fase 2), y decir «no» al paso 1 tiraría la cadena entera. La preferencia por no construir una Etapa 2 ex contra un rival que las inmuniza se aplica donde sí es seguro: en la **elección del objetivo**.

### 7. Conseguir la raíz — *fetch* y bajada

Petición del usuario: «si no tenemos el Pokémon básico en mano, lo podemos buscar en el mazo o recuperar de la pila de descarte […] para así luego jugar el estadio». El Básico bajado hoy no es evolucionable hoy (`appearThisTurn`), así que esto **prepara el turno siguiente**.

- `_gt_quiere_basico` = hay estadio disponible (en mesa o jugable desde la mano) **y** ningún Básico raíz en juego **y** queda hueco en banca.
- **Búsqueda** (contexto `TO_HAND`, común a Ultra Ball / Bug Catching Set / Poke Pad / Night Stretcher / Lana's Aid): `+GT_FETCH_BONUS` (600) sobre el score ya resuelto, `+100` extra para la raíz que lleva al mejor cuerpo. Es un **desempate**: se aplica al final, nunca resucita una opción vetada, así que las whitelists de matchup y los vetos por coste siguen mandando.
- **Bajada desde la mano** (rama `PLAY`): `+GT_PLAY_BASICO_BONUS` (500), con las mismas condiciones.

### 8. Grand Tree en nuestra mano

Código inerte con `deck.csv` actual (la carta no está en el mazo), presente porque la petición es que la lógica sirva «para cualquier tipo de mazo»:

| Situación | Score |
| --- | --- |
| Estadio ya jugado este turno, o Grand Tree ya en mesa | `SCORE_VETO` |
| Nuestro primer turno | `SCORE_VETO` — no podemos evolucionar, y se lo regalaríamos al rival |
| Hay cadena cobrable **este mismo turno** | `30000` |
| La raíz está en juego pero salió hoy | `20000` si hay estadio rival que borrar, `12000` si no |
| Sin raíz | `14000` solo si hay candado rival urgente (`_contra_estadio_urgente`), si no `SCORE_VETO` |

---

## Pruebas

`tests/test_grand_tree.py` (19 casos) cubre las tablas derivadas del mazo, las cuatro combinaciones de la regla de prioridad, el matchup anti-ex, las dos restricciones de la carta (primer turno / `appearThisTurn`), la preferencia por banca con el activo condenado, el uso de la habilidad sobre el estadio **del rival**, la precedencia sobre el Forest y sobre la evolución desde la mano, las tres sub-selecciones (Pokémon en juego, carta del mazo en el paso 1 y en el paso 2) y el *fetch* de la raíz.

El builder `tests/state_builder.py` incorpora `estadio(card_id, del_rival=True)` — para estadios que no están en `deck.csv` y por tanto no consumen pool propio —, `menu_grand_tree()`, `seleccion_grand_tree_en_juego()` y `seleccion_grand_tree_mazo()`.
