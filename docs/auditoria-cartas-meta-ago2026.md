# Auditoría de cartas del meta — agosto 2026

Revisión **carta por carta** de los tres arquetipos con más peso del top-300 del
leaderboard (`decks_competidores/`, 300 mazos), buscando mecánicas que `main.py`
no modela. Documenta lo verificado contra el motor y lo medido, para no repetir
el trabajo.

> **Método y su límite.** El detector automático (buscar el id de carta en
> `main.py`) sirve para acotar candidatos pero **da falsos negativos**: encontró
> "conocida" la carta 1266 porque ese número existe en el fichero… como
> `Splashing_Dodge_Atk`, que es un id de **ataque**. `card_table` y
> `attack_table` son espacios de nombres distintos. El único bug real de esta
> auditoría apareció revisando las listas a mano, no con el detector.

---

## Alakazam — 19.7% del meta

**Bug encontrado y CORREGIDO: Nighttime Mine (carta 1266).**

Sube `{C}` el coste de ataque de cada Pokémon **Tera** en juego. Teal Mask
Ogerpon ex es nuestro único Tera y llevamos 4, así que su ataque pasa de 3 a 4
energías. Lo lleva el **80% de las listas Alakazam**, a 2 copias.

Verificado contra el motor (30 partidas), con separación perfecta:

| Situación | ¿El menú ofrece ATTACK? |
|---|---|
| Con mina, 3 energías | **NO** (13 casos) |
| Con mina, 4 energías | Sí (22) |
| Sin mina, 3 energías | Sí (56) |
| Sin mina, 4 energías | Sí (28) |

El agente creía tener el atacante listo, planificaba el ataque y el turno se
moría. Corregido ajustando `ATTACK_ENERGY_REQ` una vez por llamada a `agent()`
(ver `_aplicar_impuesto_tera`). Winrate: **neutro**, como todo lo demás con el
gate saturado — se conservó por ser un número demostrablemente incorrecto, no
una hipótesis.

## Marnie Grimmsnarl — 43.7% del meta

**Sin hallazgos.** El motor del arquetipo ya está modelado: Freezing Shroud (el
goteo por chequeo), Adrena-Brain (3 contadores movibles) y el +30 a banca de
Shadow Bullet. Las cartas que `main.py` no conoce son todas de **consistencia
rival** (Rare Candy, Buddy-Buddy Poffin, Team Rocket's Petrel ×4, Pokégear) y no
nos afectan mecánicamente.

Única mecánica real contra nosotros: **Handheld Fan** (mueve una energía *desde
nuestro atacante* al banquillo cuando le pegamos), pero está en el 10% de las
listas Marnie y el **4.7% del meta**. No se implementa.

## Crustle Wall — 9.0% del meta

**Es duro por construcción, no por ceguera nuestra.**

- **Hero's Cape (+100 PV)** y **Grow Grass Energy (+20 PV)**: los PV que reporta
  la observación **ya los incluyen**. No hay bug — leemos `hp`, no el impreso.
- **Jumbo Ice Cream** (×4 en el 100% de las listas): cura 80. El bot la usa —
  64 curaciones observadas en 25 partidas.
- **Mist Energy**: anula los *efectos* de nuestros ataques; el daño sí pasa.

**Distribución real de PV del muro** (2.748 observaciones), que corrige la idea
de que el muro es siempre de 150 o siempre de 250:

| PV | Frecuencia | Acumulado |
|---|---|---|
| 150 (base) | 66.0% | 66.0% |
| 170 (+1 Grow Grass) | 18.3% | 84.4% |
| 190 | 9.5% | 93.8% |
| 210 | 3.3% | 97.1% |
| ≥250 (con Hero's Cape) | 2.9% | 100% |

El **97.1%** del tiempo el muro está en ≤220 PV, así que Tapu Bulu con 4
energías **sí lo remata**. La razón de que el relevo letal casi nunca dispare no
es que el muro sea inalcanzable, sino que Tapu Bulu necesita **4 energías**.

### Spiky Energy — MEDIDO Y REVERTIDO

Devuelve 20 al Pokémon **atacante** cuando el portador activo recibe daño. Está
en el 96% de las listas Crustle (×3.9); `main.py` no la conocía.

Mecánica verificada contra el motor (25 partidas): con el defensor portando
Spiky aparece un −20 en nuestro atacante **18 veces**; sin Spiky ese valor **no
aparece nunca**. Los 12 casos de retroceso 0 con Spiky son nuestros ex pegándole
0 al muro inmune — la carta exige daño para disparar.

Se modeló sumando el retroceso a `estimated_op_damage` (es daño que nuestro
activo encaja en el intercambio). Resultado con grupo de control, 400 partidas
por matchup:

| | delta winrate | rango | positivos | delta premios |
|---|---|---|---|---|
| Con Spiky (12 listas) | −0.13 | −3.8 a +3.3 | 7/12 | +0.059 |
| Control (10 listas) | −0.05 | −1.0 a +1.8 | 4/10 | +0.018 |

Medias idénticas y 7/12 positivos: ruido. Revertido por el criterio del
proyecto — es una hipótesis de modelado, la misma clase que la proyección de
Rapid-Fire Combo, no un número ilegal como el de Nighttime Mine.

**Aviso para quien lo reimplemente:** el bloque de `active_ko_likely` corre
ANTES de que existan `total_grass` y las banderas de matchup, así que no se
puede calcular ahí el daño exacto con `_attacker_base_damage` (ocho tests
revientan con `UnboundLocalError`).

## Cynthia Garchomp — 5.3% del meta

**Hallazgo verificado y NO implementado: Cynthia's Roserade (carta 342).**

Su habilidad *Cheer* dice: «Attacks used by your Cynthia's Pokémon do **30 more
damage** to your opponent's Active Pokémon (before applying Weakness and
Resistance)». Está en el **100% de las listas**, con **3.1 copias de media**, y
`main.py` no conoce la carta.

Mecánica verificada contra el motor (30 partidas). El daño que encaja nuestro
activo se desplaza exactamente +30 cuando Roserade está en su campo:

| Sin Roserade | Con Roserade |
|---|---|
| 40 | **70** |
| 100 | **130** |
| — | 160 |

Los pares 40→70 y 100→130 son el mismo ataque con +30. El 160 sugiere que
**varias copias acumulan** (el texto no lleva cláusula de "no se acumula").

Consecuencia: `_op_active_attack_damage_to` y `_op_best_damage_vs` subestiman su
daño en 30 o más siempre que Roserade esté en juego, que es siempre en este
arquetipo. Es la misma clase de hueco que Rapid-Fire Combo.

**Por qué NO se implementa.** Es exactamente el mismo tipo de cambio que la
proyección de Rapid-Fire Combo (+50 al daño estimado de Mega Kangaskhan): se
implementó, midió NEUTRO y se revirtió. Aquí el peso es aún menor (5.3% frente
al 9% de Crustle), así que el resultado esperado es el mismo con menos margen.
Se deja documentado y medido para que, si algún día el gate recupera
resolución, no haya que redescubrirlo.

Otras cartas del arquetipo, sin impacto: **Cynthia's Power Weight** (+70 PV,
tool) llega ya sumado en el `hp` de la observación, igual que Hero's Cape;
**Fighting Gong**, **Hilda** y **Surfer** son consistencia rival.

---

## Estado del gate al cerrar la auditoría

Línea base sobre las 88 listas del top-300: **93.6% ponderado**, diferencial de
premios **+3.925**. Cobertura medible 98.8%.

Seis cambios de regla seguidos midieron NEUTRO. El cuello de botella no son las
reglas sino el instrumento: contra Marnie (43.7% del meta) ganamos ~96% porque
el bot genérico cobra 1.25 premios donde un humano cobra 6. Mientras eso no
cambie, cualquier regla nueva va a medir neutro.
