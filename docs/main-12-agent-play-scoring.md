# main.py — Bucle de puntuación — PLAY (jugar cartas de la mano) (líneas 8684–11008)

## Rol en el agente

Esta es la rama `elif o.type == OptionType.PLAY:` (línea 8684) dentro del gran bucle `for o in select.option:` de `agent()`. Para cada opción de tipo `PLAY` se resuelve `card = get_card(obs, AreaType.HAND, o.index, my_index)` (línea 8685): la carta concreta de la MANO que esa opción jugaría. Si `get_card` no la resuelve, `score = -1` (veto duro, línea 8687). En caso contrario se consulta `data = card_table[card.id]` (línea 8689) y la lógica se bifurca en dos grandes ramas según `data.cardType`:

- **`CardType.POKEMON`** (líneas 8690–9289): puntuación de "bajar un Pokémon de la mano al banco/activo", con un bloque `elif card.id == <ID>` por cada Pokémon jugable del mazo (Chikorita, Applin, Teal Mask Ogerpon ex, Meowth ex, Fezandipiti ex, Tapu Bulu, Pinsir), seguido de una batería de overrides transversales (Poke Pad/Ultra Ball pendientes, matchup Cubchoo, rescates anti-softlock, sinergia Dipplin, límites de copias de Meowth ex).
- **`else` (Trainer/Estadio)** (líneas 9290–11007): puntuación de Supporters, Ítems y Estadio, con un bloque `elif card.id == <ID>` por cada carta (Forest of Vitality, Bug Catching Set, Ultra Ball, Night Stretcher, Poke Pad, Unfair Stamp, Boss's Orders, Lillie's Determination, Dawn, Lana's Aid).

Toda esta rama depende de banderas y valores calculados **antes** del bucle (líneas ~1477–4489, documentadas en `main-06`, `main-07`, `main-08` y en la futura `main-09`): detección de matchup (`op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_has_froslass`, …), el `AttackPlan` (`plan.attacker`, `plan.energy`, `plan.remain_hp`), el contador de atacantes listos (`_ready_attacker_count`, `_active_ready_attacker`), las banderas de decisión de Meowth ex/Lillie's (`_win_via_boss_gust`, `_gust_2prize_via_boss`, `_meowth_devel_lillie`, `_bcs_playable_in_hand`, `_pp_playable_in_hand`), los valores de Supporter en mano/mazo (`_best_supp_in_hand_val`, `_best_supp_in_mazo_id`, `_best_supp_in_mazo_val`, `_supp_values`) y la escalera de Boss's Orders (`_boss_val`, `_boss_win_via_bench`, `_boss_dodge_redirect`, `_boss_defensive_gust`, `_boss_low_value_gust`, `_boss_prize_rank`). El resultado de este bloque es un `score` numérico por opción que después compite en la ordenación final (líneas ~12763–12919): valores en la banda ~20000–22500 marcan Pokémon "de desarrollo prioritario", ~4500–5800 Supporters preferentes, y `-1` es siempre veto.

## Detalle por bloque

### Veto de 4º ex vs Crustle/Cornerstone (líneas 8690–8702)

```python
score = 20000
_block_4th_ex = False
if ((op_is_crustle_deck or op_is_cornerstone_deck) and card.id in OUR_EX_IDS):
    _ex_in_play = sum(field_counts.get(_ex_id, 0) for _ex_id in OUR_EX_IDS)
    if _ex_in_play >= 3:
        _block_4th_ex = True
if _block_4th_ex:
    score = -1
```
Todo Pokémon parte de `score = 20000`. Contra Crustle/Cornerstone (mazos que golpean con daño fijo por energía/Pokémon en juego o penalizan tener muchos ex) se cuentan los ex propios ya en mesa (`OUR_EX_IDS`); con 3 o más, un 4º ex se veta por completo (`score = -1`) antes incluso de evaluar el bloque específico de esa carta — cada ex adicional aumenta el daño que reciben o el número de premios regalables en ese matchup.

### Chikorita (líneas 8703–8725)

- Cuenta la línea Meganium en juego (`_meg_line_count`) y fija `_max_meg_line` en 2 copias vs Crustle/Cornerstone (necesitan redundancia por el desgaste) o 1 en el resto; si se alcanza el máximo, veto.
- Si el rival tiene Mega Starmie ex activo (`op_has_mega_starmie_active`) y no hay forma de evolucionar rápido a Bayleef (Forest disponible + Bayleef en mano), veto: Chikorita solo es carne de cañón contra ese atacante.
- En caso contrario, `score = 21500`, subido a `21700` contra espejo/fuego/Crustle/agresivos/Beedrill y a `21600` contra Greninja/Dragapult-Dusknoir (matchups donde desplegar el acelerador de energía cuanto antes importa más). Un bonus `+200` si ya hay Forest disponible y Bayleef en mano (evolución inmediata).

### Applin (líneas 8726–8780)

- Detecta si Dragapult ex rival está "cargado para snipe" (energías Fuego+Psíquico) con el activo propio de retirada gratis (`_dragapult_snipe_setup`): en ese caso, si Applin no se puede evolucionar ya mismo a Dipplin (Forest + Dipplin en mano), se veta — bajar Applin solo lo expondría al snipe de banca.
- Veto si banca llena (`bench_count >= 5`) o si es matchup Cubchoo y ya hay un miembro de la línea Hydrapple ex en juego (solo se permite una línea viva a la vez, comentario líneas 9174–9183).
- Veto si Mega Starmie ex activo y no hay evolución inmediata disponible (misma lógica que Chikorita).
- Score base `21200`, rebajado a `20800` si ya hay un Applin en juego (redundancia); `+200` si Forest+Dipplin permiten evolucionar ya; `+300` contra fuego/agresivos si aún no hay Hydrapple ex (prioridad de desarrollo del atacante ex). Si hay amenaza de snipe de banca (`op_bench_snipe_threat`) sin Forest disponible, la línea ya iniciada se rebaja a `18000` y, si Dipplin no está en mano, se resta `500` adicional (evita exponer Applin "pelado" al snipe).

### Teal Mask Ogerpon ex (líneas 8781–8803)

Veta la 3ª copia contra Crustle/Cornerstone salvo que el rival tenga Mega Kangaskhan (mueve el vector de amenaza). Veta con banca llena. Con 2 copias ya en juego solo permite una 3ª si hay energía Planta en mano (`20500`, sinergia inmediata de *Teal Dance*) o si el rival tiene Mega Kangaskhan y hay línea Meganium presente (idem `20500`); si no, veto. En el resto de casos, `score = 21000` — Ogerpon ex es uno de los desarrollos de mayor prioridad del mazo (tanque/atacante escalable).

### Meowth ex — cascada completa (líneas 8804–9011)

Meowth ex (Habilidad *Last-Ditch Catch*: al bajarlo busca un Supporter del mazo) tiene la cascada de decisión más larga de todo el bloque PLAY. Es una secuencia de `if/elif` estrictamente jerárquica: la primera condición que se cumple fija el `score` y corta el resto.

1. **Veto por Team Rocket's Watchtower** (línea 8806): si el estadio anula habilidades de Pokémon Incoloro, Meowth ex no activa *Last-Ditch Catch* al bajarlo → `score = -1`. Este veto reaparece más abajo (línea 9277) para blindar todo el resto de reglas.
2. **`win_via_boss_gust` / `gust_2prize_via_boss` — remate con Boss's** (líneas 8810–8816): si existe un plan de gusteo letal con Boss's Orders (`_win_via_boss_gust` o `_gust_2prize_via_boss`) pero Boss's Orders NO está en la mano y SÍ queda en el mazo, y todavía no hay Meowth ex en juego con banca libre → `score = 22500`. Bajar Meowth ex busca directamente el Boss's Orders que remata la partida; máxima prioridad de toda la cascada.
3. **Refresco de mano débil con Lillie's aún en el mazo** (líneas 8817–8855, `score = 21500`): exige TODAS estas condiciones — el activo ya es un atacante listo (`_active_ready_attacker`), sin Meowth ex en juego, banca libre, sin Supporter jugado, Lillie's Determination NI en mano NI ya perdida (queda en el mazo), mano con ≤4 cartas, `_ready_attacker_count <= 2` (pocos atacantes listos: si ya hay muchos no hace falta refrescar), el ataque del activo NO es letal (`not (plan.attacker == 0 and plan.remain_hp <= 0)` — si noquea, se prefiere atacar), Watchtower inactivo, y **la excepción de Froslass**: `not op_has_froslass or _ready_attacker_count <= 1`. Es decir, Froslass veta esta rama salvo que el propio activo sea el ÚNICO atacante listo (`<=1`) — ahí no hay presión real de banquear a Meowth ex y cavar por Lillie's compensa el riesgo. Motivado por los logs **86592502** (turno 9 vs Archaludon ex), **86593647** (turno 4 vs Mega Starmie ex) y **86699707** (paso 51 vs Marnie's Grimmsnarl ex, caso Froslass con Dipplin haciendo chip vs 320 HP), las tres PERDIDAS. El valor `21500` supera al cuerpo redundante (2º Ogerpon ex, `21000`) para que Meowth ex gane el desempate.
4. **Veto: activo ya listo, sin necesidad de Supporter** (líneas 8856–8867, `score = -1`): si el activo ya puede atacar y no hay Meowth ex en juego, pero NO se cumplieron las condiciones exactas del punto 3 (por ejemplo con más de 2 atacantes listos, o mano no tan débil), se veta: mejor desarrollar con Ultra Ball/Dawn o atacar directo que gastar un cuerpo de 2 premios. Motivado por el log **86511741** (paso 57, vs Mega Abomasnow ex, PERDIDA).
5. **Veto: Lillie's YA en la mano** (líneas 8868–8880, `score = -1`): si Lillie's Determination ya está en la mano, nunca se juega Meowth ex (bajarlo y buscar otro Supporter no aporta, y Lillie's barajaría la carta buscada de vuelta al mazo). Si Lillie's NO está en mano pero SÍ en el mazo, este veto no aplica y se deja pasar a la rama 7 (`_meowth_devel_lillie`).
6. **Veto: Bug Catching Set jugable + Lillie's en mano** (líneas 8881–8886, `score = -1`): si BCS es jugable y Lillie's está en mano (sin remate Boss's pendiente), se prioriza BCS/Lillie's sobre Meowth ex.
7. **`_meowth_devel_lillie` — cadena de desarrollo Meowth→Lillie's** (líneas 8887–8894, `score = 21800`): bandera calculada antes del bucle; exige Meowth ex en mano, Lillie's NI en mano NI descartada (en el mazo), sin Meowth ex en juego y banca libre. Es la puntuación más alta de "desarrollo normal": bajar Meowth ex para ir a buscar Lillie's Determination y jugarla el mismo turno.
8. **Veto: BCS jugable con banca ocupada** (línea 8895–8897, `score = -1`).
9. **Refresco cuando el activo NO puede atacar este turno** (líneas 8898–8908, `score = 21700`): con exactamente 1 Meowth ex en juego, banca libre, `_active_cant_attack_this_turn`, sin Supporter jugado, Lillie's ni en mano ni descartada, sin Froslass rival, y no siendo nuestro primer turno yendo primero. Baja un 2º Meowth ex a buscar Lillie's cuando el activo está atascado.
10. **Veto: ya hay Meowth ex en juego** (línea 8909–8910) o **banca llena** (líneas 8911–8912): `-1`.
11. **Veto: Unfair Stamp en mano tras noquear el turno pasado** (líneas 8913–8915, `-1`): con `ko_last_turn`, se prioriza jugar Unfair Stamp.
12. **Primer turno yendo primero** (líneas 8916–8925): solo se permite bajar Meowth ex (`score = 19000`) si la banca está vacía y no hay otros básicos jugables en mano; si no, veto — se prefiere sentar un atacante real.
13. **Segundo turno yendo segundo** (líneas 8926–8934): `score = 20500` solo si no se jugó Supporter aún, el mejor Supporter en mano vale poco (`_best_supp_in_hand_val < 500`) y el mejor objetivo del mazo es justamente Lillie's Determination con valor alto (`>=650`); si no, veto.
14. **Vetos generales de cierre** (líneas 8935–8951): Supporter ya jugado (`-1`); Froslass rival (`-1`, anula la habilidad); si el activo no puede atacar y sin Supporter jugado y Lillie's ni en mano ni descartada → `21800` (mismo patrón de refresco); si ya hay banca (`>=1`) con Lillie's Y Ultra Ball en mano y el rival no es Crustle/Drednaw/Sylveon (salvo que el mejor objetivo del mazo sea un Boss's Orders muy valioso) → veto, se prefiere Ultra Ball.
15. **Mejor Supporter en mano ya es fuerte (`>=500`)** (líneas 8952–8967): solo se permite Meowth ex si busca específicamente Boss's Orders de alto valor contra Crustle (`21500`), o contra Drednaw/Sylveon (`21500`); si no, veto — no tiene sentido buscar un Supporter cuando ya hay uno bueno en mano.
16. **Rama final: elegir el mejor objetivo del mazo** (líneas 8968–9011): si `_target_id == Boss_Orders` con valor `>=650` → `21000`. Si `_target_id == Lillie_Determination` con valor `>=650`, se recalculan los atacantes listos propios contra una tabla de requisitos de energía efectiva (`_ATK_REQS_MEOWTH`: Hydrapple ex 2, Dipplin 1, Ogerpon ex 3, Tapu Bulu 4, Meganium 4, Fezandipiti ex 3, Pinsir 2) y solo se acepta si hay `<=2` atacantes listos y la mano tiene `<4` cartas → `20500`. Si el objetivo es Dawn (`>=700`) y hay Forest disponible → `20500`. Si es Lana's Aid (`>=600`) → `20000`. Cualquier otro caso deja `score = -1`.

### Fezandipiti ex (líneas 9012–9091)

- **Preferencia Teal+Lillie's** (`_fez_prefer_teal_lillie`, líneas 9021–9031): con Lillie's en mano, Supporter sin jugar, Teal Mask Ogerpon ex en mano (con menos de 2 copias en juego) y energía Planta en mano, se veta Fezandipiti ex para dejar ganar a Ogerpon ex (`21000`) — su Habilidad *Flip the Script* (roba hasta 3) no compite con Teal Dance + Lillie's refrescando la mano.
- Veto si ya hay uno en juego o banca llena.
- **Contra Lucario/Crustle/Cornerstone/Sylveon** (líneas 9036–9056): Fezandipiti ex vale 2 premios y su habilidad solo sirve tras ser noqueado; no se baja por desarrollo. Si `ko_last_turn` (la habilidad está "viva", acaban de noquearnos) → `22000` (`22500` con mano `<=3`, para robar rápido). Si no, solo como último recurso con banca vacía → `500`; en cualquier otro caso, veto.
- Primer turno con banca de 1 → `15000`; si no, veto.
- Caso general: `fez_score = 22000`/`22500` si `ko_last_turn` (igual que arriba); si no hubo KO y banca `<=2`, se calcula si toda la banca son básicos (`_all_bench_basics`) y, si es así y el rival no es Lucario, `fez_score = max(fez_score, 15000)` (desarrollo tolerado cuando no hay evoluciones que perder).

### Tapu Bulu (líneas 9092–9159)

Atacante no-ex pesado (4 energía efectiva). `_op_is_crustle_like` agrupa Crustle/Cornerstone/Sylveon/rivales con inmunidad a habilidad o a ex. Reglas: veto si ya hay uno en juego; contra tableros muy desarrollados sin Meganium ni matchup Crustle-like se cede a `16000` solo con `>=4` piezas en juego y Meganium; si hay `>2` copias en juego y no es Crustle, veto (evita saturar banca). Prioridades de matchup: Crustle `22000` (`22500` con Meganium — clave por no pagar coste de Rule Box y noquear con daño fijo); rival con habilidad inmune o Cornerstone `22500`; Sylveon `22000`; rival con inmunidad a ex `21000` (`22000` con Hydrapple ex ya en juego, refuerzo del plan). `_lucario_sac_pivot`: como sacrificio prioritario de 1 premio vs Mega Lucario, `21500`. Primer/segundo turno o sin Meganium en juego → veto (Tapu Bulu es lento sin el doblador de energía). Caso general → `16000`. **Cierre transversal** (líneas 9149–9159): si aún quedan ítems jugables en la mano (`DECK_ITEM_IDS`), Tapu Bulu se rebaja a `TAPU_WAIT_FOR_ITEMS_SCORE` (`8900`) — los ítems útiles siempre se juegan antes; cuando ya no quedan ítems de valor, Tapu Bulu recupera su prioridad.

### Pinsir (línea 9160–9162)

`score = -1` siempre: Pinsir no se baja nunca por esta rama de desarrollo (queda como opción legal de último recurso vía el rescate anti-softlock más abajo).

### Overrides transversales tras el `if/elif` de Pokémon (líneas 9164–9289)

- **Objetivo pendiente de Poke Pad** (`_poke_pad_target_id`, líneas 9164–9167): si la carta jugable es justo el objetivo que se fue a buscar con Poke Pad y el score quedó en 0/negativo, se fuerza `21000` (garantiza que la búsqueda se aproveche).
- **Meowth ex pendiente por Ultra Ball** (`_ub_meowth_pending`, líneas 9169–9172): análogo, si se buscó Meowth ex con Ultra Ball y aún no está en juego, fuerza `21000`.
- **Matchup Cubchoo — lista blanca de Pokémon jugables** (líneas 9174–9204): contra este mazo solo se permite una línea Hydrapple ex, una línea Meganium, hasta 2 Ogerpon ex y 1 Meowth ex (solo si hace falta para buscar Lillie's). Cualquier otro Pokémon (`_CUB_ALLOWED_PLAY` no lo incluye) → veto; 3ª copia de Ogerpon ex → veto; Meowth ex solo si `_cub_meowth_ok` (sin copia en juego, Lillie's ni en mano ni ya usada).
- **`_lucario_riolu_gust`** (líneas 9206–9215): con esta bandera activa (gustear+noquear un Riolu de banca rival vs Mega Lucario), se veta CUALQUIER desarrollo de Pokémon para que Boss's Orders (tier 0, Supporter) gane la jugada.
- **Rescate anti-softlock de banca vacía** (líneas 9217–9240): si `bench_count == 0` y el score sigue `<=0` y la carta es un Pokémon básico (no `stage1`/`stage2`), se fuerza una jugada legal mínima: `80` si es un ex propio (`OUR_EX_IDS`), `150` en otro caso. Excepción `_meowth_first_turn_hold`: en nuestro primer turno, con Lillie's Determination jugable en mano y Supporter aún sin jugar, NO se fuerza Meowth ex a la banca (se respeta el veto de la cascada; si tras jugar Lillie's sigue sin banca, `supporterPlayed` pasa a `True` y este rescate se reactiva).
- **Sinergia Dipplin activo + Data Wave escalable** (líneas 9242–9270): si el activo es Dipplin, puede atacar (energía ya puesta o Planta en mano sin adjunte hecho) y bajar UN Pokémon básico más a la banca sube el daño de *Data Wave* (`20 * bench_count`, doblado por debilidad Planta o reducido por resistencia) lo justo para pasar de "no letal" a "letal" contra el activo rival, se sube ese Pokémon a `max(score, 21900)` — prioriza la jugada que habilita el KO de este turno.
- **Límite de copias de Meowth ex** (líneas 9272–9288): repetido tras todo lo anterior como blindaje final — Watchtower en juego, Meowth ex ya jugado este turno (`_meowth_played_this_turn`, comparado con `_field_at_turn_start`), o ya hay `>=2` copias en juego → veto; con 1 copia en juego y score no forzado positivo → veto (no bajar un 3er/2º cuerpo redundante salvo que alguna regla anterior ya lo haya justificado explícitamente).

---

### Rama Trainer/Estadio — introducción (líneas 9290–9293)

```python
else:
    score = 10000
    supporter_boost = 500 if itchy_pollen_active else 0
```
Score base `10000` para cualquier carta no-Pokémon. `supporter_boost` (usado solo en los Supporters) añade `500` cuando Budew's *Itchy Pollen* está activo (bloquea Ítems en el próximo turno del rival): jugar el Supporter ahora, antes de perder la ventana de ítems, gana prioridad.

### Forest of Vitality (líneas 9294–9378)

Estadio que acelera energía Planta. Vetado en nuestro primer turno yendo primero (`_our_first_turn_first`, aún no hay nada que acelerar) y en nuestro segundo turno yendo segundo si NO hay estadio rival puesto (se prefiere no regalar tempo). Si el rival ya puso un estadio distinto en ese mismo turno inicial, se juega igual (`15000`, recuperar el estadio propio). Veto si Forest ya está en juego.

En el resto de turnos: si Team Rocket's Watchtower (`neutralization_zone_active`) está activo, reemplazar el estadio vale `28000` (`29000` si hay Chikorita/Applin/Dipplin en juego — piezas que la propia Habilidad de Forest ayuda a evolucionar). Si no, se calcula `_evo_chain`: ¿hay una pre-evolución en juego con su siguiente etapa en mano, o buscable vía Poke Pad/Ultra Ball para Meganium (`_meg_fetchable_fv`)? Si sí, `score = 21900` (`22000` con estadio rival puesto, `+200` extra contra fuego/agresivos/Beedrill). Si no hay cadena de evolución pendiente pero hay estadio rival, `15000`; en los primeros 4 turnos, `14000` (`15000` contra fuego/agresivo/espejo); pasado el turno 4, `8000` (Forest pierde valor tardío). Un bloque de `print` a `stderr` bajo `[FOREST-RULE]` (líneas 9370–9378) registra los valores de depuración de esta carta específicamente.

### Bug Catching Set (líneas 9379–9470)

Busca del mazo entre Pokémon Planta y Energía Planta. `bcs_score = 10500` de partida, con `-100` si Ogerpon ex ya está en banca y hay energía Planta en mano (menos urgente). Recorre `CARTAS_ACTIVAS_EN_MAZO` para contar Pokémon Planta restantes (`grass_pokemon_in_mazo`), energía restante (`energy_in_mazo`) y objetivos de "alto valor" (`high_value_in_mazo`: piezas de evolución inmediatas — Meganium/Hydrapple ex/Bayleef/Dipplin con su pre-evo en juego, Chikorita/Applin sin línea iniciada, o un 3er Ogerpon ex si aún no hay 2 en juego).

Calcula la probabilidad de encontrar algo útil en las próximas hasta-7 cartas robadas (fórmula hipergeométrica manual, líneas 9427–9438: con `total_mazo <= 7` la probabilidad es 1.0 si hay algo elegible; si no, `p_miss_all` se multiplica turno a turno). Ajusta `bcs_score` según ese `p_find` (`+800` si `>=0.9`, `+500` si `>=0.7`, `+200` si `>=0.5`, `-300` si menor) y según `high_value_in_mazo` (`+600`/`+400`/`+200`). Bonus `+300` si falta Meganium Y Hydrapple ex, `+150` si falta solo uno. Bonus `+200` si no hay energía Planta en mano ni se adjuntó este turno, con un extra `SCORE_BELIEF_DIG_ENERGY` (`250`) si el agente está "hambriento de energía con pocas cartas por robar" (`_energy_starved_low_draw`). Al final, si Poke Pad es jugable (`_pp_playable_in_hand`) y el score supera `9000`, se recorta a `9000` — Poke Pad (búsqueda determinista, sin coste de mano) tiene preferencia sobre BCS (probabilística).

### Ultra Ball (líneas 9471–10013)

El bloque más largo de la rama Trainer. `ub_score = 10000` de partida. Detecta `_ub_survival_mode` (banca vacía en un turno temprano o cualquier turno `>=2`, donde Ultra Ball es el único recurso para sentar un cuerpo).

- **`_ub_evolve_needs_search`** (líneas 9502–9515): ¿hay una pre-evolución en juego cuya siguiente etapa falta en mano pero queda en el mazo? Excluye explícitamente Hydrapple ex si el rival es inmune a ex (`_ub_op_ex_immune`), motivado por el log **86028607** (paso 47, vs Crustle): sin esta exclusión, la búsqueda "fantasma" de Hydrapple ex saltaba el corte de banca llena y jugaba una Ultra Ball inútil.
- **`_ub_evolve_now_search`** (líneas 9525–9542): variante que además exige poder completar la evolución ESTE turno (Forest en juego o la pre-evo ya estaba en juego al inicio del turno) — usada más abajo para no posponer Ultra Ball frente a Lillie's cuando sí se puede evolucionar ya.
- **`_ub_developed_attacker_board`** (líneas 9554–9558): tablero ya desarrollado (`can_attack` y `>=2` Pokémon de banca con energía) — motivado por el log **86028035** (paso 53): con un atacante listo y banca ya energizada, no vale la pena Ultra Ball para desarrollar más.
- **Cortes tempranos** (líneas 9560–9576): mano `<3` cartas → veto; banca llena sin `_ub_evolve_needs_search` → veto (salvaguarda dura, "no aporta nada este turno").
- **Cancelaciones por protección de recursos** (líneas 9579–9760): `_ub_cancel_for_stamp` (si jugar Ultra Ball obligaría a descartar Unfair Stamp, contando las copias sobrantes de la propia Ultra Ball como fodder válido — corrige el log **86403004**, paso 17, PERDIDA vs Iono); `_ub_cancel_for_fez` (protegería un Fezandipiti ex "vivo" tras KO); `_ub_cancel_for_lillie` (protege Lillie's Determination sin jugar, con un cálculo fino de qué cartas son realmente descartables sin tocarla — excluye piezas de evolución protegidas y Fezandipiti ex vivo; motivado por los logs **86210811** paso 36/37 GANADA y **86401283** paso 32 GANADA vs Alakazam); `_ub_cancel_for_meowth` (protege la cadena Meowth ex→Lillie's contando qué es "seguro" descartar sin tocar Meowth ex, con reglas específicas por carta — motivado por el log **86412738** paso 115, GANADA vs Hops).
- **Selección del objetivo** (`ub_best_target = _eval_ub_best_target(...)`, líneas 9769–9793): delega en el helper `_eval_ub_best_target` (definido antes de `agent()`, ver `main-04`). Si no hay Supporter en mano/mazo relevante pero SÍ Meowth ex y Lillie's disponibles en el mazo, se fuerza `ub_best_target = max(ub_best_target, 950)` con mano débil o línea Meganium activa, o `850` si el mejor Supporter del mazo vale `>=600` — para que Ultra Ball no ignore la cadena Meowth→Lillie's.
- Si `ub_best_target == 0` → veto. Si no, se calcula `safe_discards` (cartas que se pueden pagar como coste sin perder valor: energía sobrante, básicos ya en juego o recuperables, Forest duplicado, evoluciones ya completas, etc.) y se aplican los cortes finales: tablero desarrollado con objetivo de bajo valor → veto; objetivo `<300` con `<2` descartes seguros → veto; objetivo `<250` → veto siempre; banca llena sin evolución posible → veto (redundante con el corte de arriba, doble salvaguarda).
- **Escalado del score** (líneas 9873–9914): `ub_best_target >= 900` → `12500`; `>=700` → `12000`; `>=500` → `11200`; `>=300` → `10500`; si no, `10000`. Penaliza `-600`/`-250` si `safe_discards` es bajo. Bonus `+500` si la mano es débil y el objetivo es bueno. Si Lillie's está en mano y sin jugar, normalmente se pospone Ultra Ball a `4500` (Lillie's roba 6–8, prioridad mayor) EXCEPTO cuando la búsqueda completa una evolución este mismo turno (`_ub_evolve_now_search`) — ahí no se degrada, para desarrollar primero y barajar después.
- **Protección final de Lillie's como coste** (líneas 9916–9940): si pagar el coste de Ultra Ball obligaría a descartar la propia Lillie's Determination (`_ub_lillie_forced_discard`), se veta salvo que la búsqueda sirva para cerrar la partida (`my_prize <= 2` o remate vía Boss's).
- **Modo supervivencia** (líneas 9942–9964): si `_ub_survival_mode` y el score sigue `<=0`, sin Lillie's jugable en mano ni básico jugable en mano, pero SÍ queda algún básico en el mazo, se fuerza `ub_score = 25000` — garantiza sentar un cuerpo cuando la banca está vacía.
- Penalización `-1500` si BCS también es jugable (se prioriza BCS cuando compite). Restricciones de primer turno (`_ub_first_turn_allowed`, líneas 9971–9991): solo se permite yendo primero con banca vacía, o yendo segundo para la cadena Meowth→Lillie's, o para responder a un Budew activo rival.
- **Salvaguarda FINAL de banca llena** (líneas 9993–10011, motivada por el log **86210257** paso 86, GANADA vs Mega Starmie): control terminal que tiene la última palabra — con banca llena y sin ninguna evolución posible en juego (y fuera de modo supervivencia), `ub_score = -1` sin importar qué rama anterior lo hubiera dejado positivo.

### Night Stretcher (líneas 10014–10391)

Recupera del descarte. Recorre `my_state.discard` clasificando en `discard_basics` (Chikorita/Applin/Ogerpon ex/Tapu Bulu/Meowth ex/Fezandipiti ex/Pinsir), `discard_evos` (Bayleef/Meganium/Dipplin/Hydrapple ex) y `discard_energy`. Construye `best_recovery_value` evaluando decenas de escenarios de recuperación (recuperar Applin/Chikorita para completar líneas de evolución con Forest disponible, recuperar la pieza de evolución directamente, recuperar energía para cargar un atacante que la necesita, recuperar energía para hacer *Teal Dance* con Ogerpon ex, etc.), cada uno con su propio valor entre 700 y 990 tomado como `max()` acumulado.

Casos destacados:
- **Energía para completar un KO letal con Hydrapple ex** (líneas 10222–10242): si recuperar 1 energía Planta convierte un ataque no-letal en letal (`_now_eff < _opp_hp_leth <= _after_eff`), `best_recovery_value = 950`.
- **Matchup Crustle/Cornerstone** (líneas 10271–10317): tabla de recuperación específica (`_cc_recover_basics`/`_cc_recover_evos`) priorizando Tapu Bulu/Pinsir y, solo si además es Crustle, también Applin/Chikorita y sus evoluciones; incluye `op_kang_ko_target` (recuperar Hydrapple ex cuando el rival amenaza con Mega Kangaskhan) a `960`.
- **Priorizar carga de banca antes que Lillie's** (líneas 10319–10342): contra Crustle/Cornerstone, si algún atacante de banca (Tapu Bulu/Ogerpon ex/Hydrapple ex/Meganium) no llega a su requisito de energía (`ATTACK_ENERGY_REQ`), recuperar energía vale `850` — evita que Lillie's baraje de vuelta el Night Stretcher y la energía recién recuperada.

`ns_score` final: `>=900` → `11800`; `>=800` → `11000`; `>=700` → `10400`; `>0` → `9800`. Igual que Ultra Ball/Poke Pad, se veta con banca llena si no hay nada que evolucionar ni energía útil que recuperar (`_ns_something_to_evolve`, `_ns_energy_useful`). Override final: `op_kang_ko_target` con Hydrapple ex recuperable sube a `34000` (máxima prioridad, evita perder la carrera de premios contra Mega Kangaskhan).

### Poke Pad (líneas 10392–10530)

Busca a la mano un Pokémon sin Rule Box (`NON_RULEBOX_IDS`: Chikorita/Bayleef/Meganium/Applin/Dipplin/Tapu_Bulu — nunca ex). `pp_score = 9800` de partida; veto si no hay nada buscable (`searchable` vacío).

- **Turno inicial** (líneas 10414–10432): prioriza buscar Applin (`12800`) o Chikorita (`12600`) si aún no están en juego/mano y hay hueco en banca; con `_pp_budew_dump` (rival abrió con Budew activo yendo segundos: su *Itchy Pollen* bloqueará ítems el próximo turno propio) se permite además buscar piezas de evolución a `12400` — jugar TODAS las Poke Pad posibles este único turno disponible.
- **Turnos siguientes** (líneas 10434–10488): si se puede completar una evolución este turno (`_pp_can_evolve_this_turn`, con valores por tramo `_pp_evo_value`), el score sube a `23000`/`22000`/`20000` según cuán inmediato sea. Si no, vuelve a la lógica de básicos (`12800`/`12600`).
- Bonus `13000` si `_lucario_sac_pivot` y Tapu Bulu es buscable (sacrificio de 1 premio vs Mega Lucario).
- **Corte de banca llena** (`_pp_evolve_needs_search`, líneas 10497–10528): variante estricta que EXCLUYE la línea Dipplin→Hydrapple ex (Poke Pad no puede buscar un ex); con banca llena y sin nada que evolucionar por esta vía, veto — salvo `_pp_budew_dump`.

### Unfair Stamp (líneas 10531–10609)

Ítem de descarte/negación (nombre sugiere forzar descarte al rival o similar). Evalúa si hay Pokémon jugable en mano (`_us_has_playable_pokemon`), evolución jugable (`_us_has_playable_evo`), ítem jugable (`_us_has_playable_item`, respetando `itchy_pollen_active`), jugada de energía o de estadio. Score base según qué queda por hacer: `2000` si hay Pokémon/evolución que jugar (jugarlos primero, dejar Unfair Stamp para después), `2500` si solo quedan ítems, `3000` si solo queda energía/estadio, `7500` si no queda nada más que jugar (momento ideal para el Stamp). Bonus `+300` en los primeros 4 turnos, `+200` si vamos ganando en premios (`my_prize > op_prize + 1`), y bonus específicos de matchup: `+400` Alakazam, `+350` control/Slowking, `+300` Gardevoir, `+250` Zoroark, `+350` extra contra agresivos/Beedrill si vamos perdiendo en premios.

### Boss's Orders — puntuación al jugarlo desde la mano (líneas 10610–10687)

Esta es la puntuación FINAL de la opción PLAY de Boss's Orders; la mayor parte de la lógica de decisión (`_boss_val`, `_boss_win_via_bench`, `_boss_dodge_redirect`, `_boss_defensive_gust`, `_boss_low_value_gust`, `_boss_prize_rank`) se calculó antes del bucle (escalera de Boss's Orders, `main-08`). Vetos previos: Supporter ya jugado; `ko_last_turn` con Unfair Stamp en mano (se prefiere el Stamp); contra Alakazam con Dunsparce activo rival y nuestro activo sin poder atacar (gustear solo despejaría el muro que conviene mantener trabado).

- **`_boss_empty_gust`** (líneas 10628–10647, motivado por el log **85799299** paso 50): si nuestro activo no puede atacar este turno Y no hay ninguna forma ejecutable de aprovechar el gusteo (ni remate de banca, ni redirección por esquiva, ni gusteo defensivo, ni muro inmune) Y tenemos Lillie's en mano, se cede la prioridad con `score = BOSS_SCORE_EMPTY_GUST` (`20`) — un gusteo "vacío" (sin premio) vale menos que refrescar la mano.
- **`_boss_first_turn_cede`** (líneas 10648–10664, motivado por el log **86025936** paso 11): en nuestro primer turno, con Lillie's en mano y sin Supporter jugado, SIEMPRE se cede a Lillie's (salvo remate letal de banca) con el mismo `BOSS_SCORE_EMPTY_GUST`.
- Jerarquía de valores cuando el gusteo sí es útil: muro inmune a ex/habilidad con `_boss_val >= 900` → `BOSS_SCORE_WALL_GUST` (`5500`) `+supporter_boost`; redirección por esquiva → `BOSS_SCORE_DODGE_REDIRECT` (`5500`); remate letal de banca → `BOSS_SCORE_WIN_VIA_BENCH` (`5600`, el máximo); gusteo de bajo valor → `BOSS_SCORE_LOW_VALUE_GUST` (`1500`); si hay `_boss_prize_rank >= 1` → `BOSS_SCORE_PRIZE_RANK_BASE + (8 - _boss_prize_rank) * 20` (afinado por el rango de premios del objetivo); gusteo defensivo (típicamente vs Crustle) → `BOSS_SCORE_DEFENSIVE_GUST` (`1500`); si `_boss_val <= 0` → veto; en cualquier otro caso, fórmula genérica `2400 + int(_boss_val * 1.4) + supporter_boost`.

### Lillie's Determination (líneas 10688–10953)

Supporter que baraja la mano y roba 6 (u 8 con `my_prize == 6`). Antes de puntuar calcula `_ready_ex_attackers` (Hydrapple ex/Ogerpon ex/Fezandipiti ex con energía efectiva suficiente), `_lillie_pending_evo` (¿hay una evolución en mano cuya pre-evo ya está en juego, que se perdería al barajar?), `_lillie_evolve_now` (¿se puede completar esa evolución ESTE turno?) y `_hydra_active_charged` (Hydrapple ex activo con `>=2` energía efectiva, listo para *Syrup Storm*).

- Veto si mano ya `>=10` cartas en los 2 primeros turnos (salvo nuestro primer turno) o Supporter ya jugado o `ko_last_turn` con Unfair Stamp en mano. Veto adicional contra Alakazam con Unfair Stamp en mano y `>=2` atacantes ex listos (se prioriza el Stamp/los ataques).
- **Nuestro primer turno**: SIEMPRE `score = 5000` si está en mano, ignorando los demás vetos (log **86025936** paso 11) — se juega el turno de la mano refrescada, con las evoluciones/ítems de mayor score yendo antes por la capa de tiers.
- **`_hydra_active_charged`** (líneas 10799–10813): prioridad sobre Boss's Orders cuando Hydrapple ex activo ya está cargado — `score = 5800 + supporter_boost`, por encima del máximo normal de Boss's (`~5600`), salvo remate de banca o esquiva-redirección con Boss's en mano (motivado por el log **86343257** paso 99, PERDIDA vs Hop: si el rival esquiva, cargar más energía es inútil y se cede a Boss's).
- Veto si Boss's Orders en mano tiene un gusteo ejecutable (`_boss_prize_rank >= 1` con activo capaz de atacar, o remate de banca, o esquiva-redirección) — Boss's tiene prioridad de remate.
- `score = 4500` si Ogerpon ex + energía Planta están en mano con banca libre (preparar el siguiente atacante antes de refrescar).
- **`_lillie_pending_evo`** (líneas 10829–10864, motivado por el log **86345042** paso 44, GANADA vs Mega Lucario): si hay una evolución pendiente en mano y la mano tiene `>4` cartas, se veta Lillie's — se completan antes las evoluciones (score ~31000–35000) y los ítems. Dos excepciones: mano `<=4` cartas (el valor de robar supera conservar la línea) o si no se puede evolucionar ya pero sí se va a atacar este turno (`can_attack` o `_bdg_retreat_ko`, retirar+promover para noquear) — ahí no se veta, para no dejar la Lillie's varada tras el ataque.
- Con mano `<=6`, `score = 5000` directo. Con mano `>6`, se repite el chequeo de evoluciones pendientes (`_has_pending_evolutions`) de forma más fina y solo se veta si NO se puede evolucionar ya, no es de los 2 primeros turnos, no hay Lana's Aid alternativa sin Supporter jugado, y la mano tiene `<7` cartas — en cualquier otro caso se mantiene `5000`.

### Dawn (líneas 10954–10964)

Supporter genérico: veto si Supporter jugado o `ko_last_turn` con Unfair Stamp en mano; si no, `score = 2400 + int(_dawn_val * 1.4) + supporter_boost` (con `_dawn_val = _supp_values.get(Dawn, 0)`; veto si vale `0`).

### Lana's Aid (líneas 10965–11007)

Misma fórmula base (`2400 + int(_lana_val * 1.4) + supporter_boost`) con vetos idénticos. Dos ajustes propios:
- Con línea Meganium activa (`_mega_line_active`), score `<4500`, sin Supporter jugado, sin energía Planta en mano ni adjuntada, y con energía Planta en el descarte recuperable → se sube a `max(score, 4500)`.
- **Prioridad de Lillie's cuando Lana's no habilita ataque** (líneas 10988–11006, motivado por el log **86509038** paso 62, PERDIDA vs Mega Lucario): si el activo no puede atacar este turno y Lillie's está en mano sin jugar y la recuperación de Lana's Aid NO habilita un ataque (`not _supp_values.get('_lana_enables_attack')`), se recorta `score = min(score, 2000)` — se deja ganar a Lillie's Determination (refrescar rinde más que recuperar piezas que no atacan ya), pero Lana's se mantiene jugable por si Lillie's estuviera vetada por otra vía.

## Interacciones

- **Con la escalera de Boss's Orders (`main-08`)**: las banderas `_win_via_boss_gust`, `_gust_2prize_via_boss`, `_boss_val`, `_boss_win_via_bench`, `_boss_dodge_redirect`, `_boss_defensive_gust`, `_boss_low_value_gust` y `_boss_prize_rank` se calculan enteramente antes de este bloque; aquí solo se traducen a un `score` final para la opción concreta de jugar Boss's Orders, y también condicionan cuándo Meowth ex debe salir a buscarlo (rama 2 de la cascada) o cuándo Lillie's debe ceder prioridad.
- **Con `main-07` (plan de ataque)**: `plan.attacker`, `plan.remain_hp`, `can_attack`, `_bdg_retreat_ko` y `_active_cant_attack_this_turn` determinan si el activo/banca ya tienen un KO garantizado este turno, lo cual veta refrescos de mano (Meowth ex, Lillie's) que competirían con rematar.
- **Con `main-06` (matchup)**: casi todos los bloques de Pokémon y varias reglas de Ítems/Supporters cambian de comportamiento según `op_is_crustle_deck`, `op_is_cornerstone_deck`, `op_is_sylveon_deck`, `op_is_lucario_deck`, `op_has_froslass`, `op_has_mega_starmie_active`, `op_is_cubchoo_deck`, `op_is_alakazam_deck`, etc.
- **Con la fase de búsqueda de cartas (`main-11`, `SelectContext.TO_HAND`/`CARD`)**: Ultra Ball, Poke Pad, Bug Catching Set y Night Stretcher solo deciden SI se juegan aquí; QUÉ objetivo concreto buscan se resuelve después en la subselección `TO_HAND`/`CARD`, apoyada en `_eval_ub_best_target` y en `_supp_values`.
- **Con el orden de jugada por tiers (líneas ~12850, finalización)**: aunque una carta puntúe alto en PLAY, el tier (energía-de-KO > estadio > desarrollo/evolución > Poke Pad > Bug Catching Set > energía > resto) reordena las opciones positivas antes de devolver la lista; los vetos (`-1`) quedan siempre al final independientemente del tier.
- **Con `ATTACH`/`EVOLVE` (`main-13`, líneas 11008+)**: varias jugadas de Pokémon (p.ej. Ogerpon ex, Fezandipiti ex "sacrificio con retirada") están diseñadas para encajar con reglas de adjunte inmediatamente posteriores (`_tapu_sac_enable_retreat`, visible ya en las primeras líneas de `ATTACH`, 11026–11040).

## Reglas derivadas de partidas (`log 86xxxxxx`)

- **log 86592502** (turno 9 vs Archaludon ex, PERDIDA) — junto con 86593647 y 86699707, motiva la excepción de refresco de mano débil de Meowth ex (líneas 8832–8855): con activo listo pero mano ≤4 y Lillie's en el mazo, bajar Meowth ex para buscarla vale más que un cuerpo redundante o un ataque no letal.
- **log 86593647** (turno 4 vs Mega Starmie ex, PERDIDA) — mismo caso que el anterior.
- **log 86699707** (paso 51 vs Marnie's Grimmsnarl ex, PERDIDA) — origina la excepción de Froslass (`not op_has_froslass or _ready_attacker_count <= 1`, línea 8850): con Dipplin activo haciendo chip contra un muro de 320 HP y ningún otro atacante listo, cavar por Lillie's supera el riesgo de banquear a Meowth ex.
- **log 86511741** (paso 57, vs Mega Abomasnow ex, PERDIDA) — motiva el veto de Meowth ex cuando el activo ya es un atacante listo sin cumplir las condiciones estrictas de refresco (líneas 8856–8867).
- **log 86028607** (paso 47, vs Crustle) — motiva excluir a Hydrapple ex de `_ub_evolve_needs_search` cuando el rival es inmune a ex, para no dejar pasar una Ultra Ball inútil por el corte de banca llena (líneas 9493–9498).
- **log 86028035** (paso 53) — motiva `_ub_developed_attacker_board`: con un atacante listo y banca ya energizada, no gastar Ultra Ball en desarrollo redundante (líneas 9544–9558).
- **log 86210257** (paso 86, GANADA vs Mega Starmie) — motiva la salvaguarda final terminal de banca llena en Ultra Ball (líneas 9993–10011).
- **log 86403004** (paso 17, PERDIDA vs Iono) — motiva contar las copias sobrantes de la propia Ultra Ball como fodder válido para no cancelarse a sí misma protegiendo Unfair Stamp (líneas 9579–9601).
- **log 86210811** (paso 36/37, GANADA) — motiva el cálculo fino de `_ub_cancel_for_lillie` (qué cartas son realmente descartables sin tocar Lillie's), líneas 9619–9633.
- **log 86401283** (paso 32, GANADA vs Alakazam) — refina `_ub_cancel_for_lillie` para excluir piezas de evolución/Fezandipiti ex protegidas por el scorer de `DISCARD` (líneas 9634–9646).
- **log 86412738** (paso 115, GANADA vs Hops) — motiva `_ub_cancel_for_meowth`, protegiendo la cadena Meowth ex→Lillie's al calcular qué es fodder seguro (líneas 9690–9707).
- **log 85799299** (paso 50) — motiva `_boss_empty_gust`: ceder Boss's Orders a Lillie's cuando el gusteo no es ejecutable (activo sin poder atacar, sin remate/redirección/muro/gusteo defensivo), líneas 10628–10647.
- **log 86025936** (paso 11) — motiva dos reglas: `_boss_first_turn_cede` (Boss's cede a Lillie's en nuestro primer turno, líneas 10648–10664) y la prioridad incondicional de Lillie's en nuestro primer turno (líneas 10790–10798).
- **log 86343257** (paso 99, PERDIDA vs Hop) — motiva la excepción de `_hydra_active_charged`: si el rival esquiva (`_boss_dodge_redirect`) con Boss's en mano, se cede la prioridad de Lillie's a Boss's (líneas 10807–10812).
- **log 86345042** (paso 44, GANADA vs Mega Lucario) — motiva `_bdg_retreat_ko` como excepción al veto de `_lillie_pending_evo`: si retirar y promover un atacante de banca noquea este turno, no conservar la línea de evolución varada (líneas 10857–10863).
- **log 86509038** (paso 62, PERDIDA vs Mega Lucario) — motiva recortar el score de Lana's Aid a `min(score, 2000)` cuando no habilita un ataque y Lillie's está disponible sin jugar (líneas 10988–11006).
- **log 86029588** (turno 16 paso 148, vs Alakazam/Dunsparce) — motiva subir a `24000` el adjunte de energía al ex activo que habilita retirarlo y pivotar a un Tapu Bulu ya cargado para rematar (líneas 11026–11040, en la rama `ATTACH` inmediatamente posterior a PLAY).
