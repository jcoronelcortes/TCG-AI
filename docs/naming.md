# Naming

The vocabulary the code uses for domain concepts, and the conventions that keep
names predictable. It exists so that two people (or the same person six months
apart) reach for the same word for the same thing.

The English terms are not invented here: they are the ones the comments,
[docs/glossary.md](glossary.md) and [docs/strategy.md](strategy.md) already use.
This page is the bridge from the Spanish names the code was written with to
those terms.

## Domain vocabulary

| Spanish | English | Notes |
|---|---|---|
| mazo | deck | the library; `deck.csv` is our list |
| mano | hand | |
| banca | bench | |
| activo | active | the Pokemon in the active spot |
| rival | opponent | the `op_` prefix already means this in flags |
| premio / premios | prize / prizes | |
| energia | energy | |
| planta | grass | the type; `grass_units` for effective energy |
| carta / cartas | card / cards | |
| descarte | discard | |
| estadio | stadium | |
| habilidad | ability | |
| ataque | attack | |
| atacante | attacker | |
| dano | damage | |
| retirada / retirar | retreat | |
| jugada / jugadas | play / plays | a menu option we choose |
| jugar | play | the verb |
| turno | turn | |
| tablero | board | |
| linea / lineas | line / lines | evolution line |
| evolucion | evolution | |
| muro | wall | a body we cannot damage |
| gusteo / gustear | gust | Boss's Orders |
| remate / rematar | finisher / finish | the KO that closes the game |
| amenaza | threat | |
| relevo | relief | the body that takes over |
| refresco | refresh | remaking the hand |
| disrupcion | disruption | |
| objetivo | target | |
| busqueda / buscar | search | a fetch from deck or discard |
| coste / costes | cost / costs | |

## Machinery vocabulary

| Spanish | English | Notes |
|---|---|---|
| estado | state | `ESTADO` -> `AGENT_STATE` (the observation's own is `state`), `EstadoAgente` -> `AgentState` |
| ESTADO_MAZO, ESTADO_MANO, ... | ZONE_DECK, ZONE_HAND, ... | belief zones, not agent state; their VALUES were translated too, they are internal keys |
| decision | decision | |
| eleccion | choice | the index we return |
| opciones | options | the menu the engine offers |
| regla / reglas | rule / rules | |
| valor | value | |
| puntuacion / puntua | score | |
| nombre | name | |
| motor | engine | |
| calculo | calc | the pure calculators |
| contexto | context | `ctx` stays `ctx` |
| depuracion | debug | |
| seguimiento / tracking | tracking | already English |
| corpus | corpus | already English |
| registro / registros | record / records | the replayed turn dumps |
| sombra | shadow | the pre/post harness |
| autopsia | autopsy | |
| partida / partidas | game / games | |
| paso / pasos | step / steps | |
| fase | phase | |
| via / vias | route / routes | a way to reach something |
| ruta | path | a filesystem path |
| clave / claves | key / keys | |
| tope / topes | cap / caps | a hard ceiling on a score |
| banda | band | a range of scores |
| limite | limit | |
| peso / pesos | weight / weights | meta share |
| red | net | a rescue that catches a dead turn |
| hueco | slot | bench slot, Supporter slot |
| forraje | fodder | cards spent to pay a cost |
| traba / trabado | stuck | cannot attack and cannot retreat |
| clavado | nailed down | the stronger form of stuck |
| cadena | chain | a sequence of plays across menus |

## Qualifiers

| Spanish | English |
|---|---|
| condenado | doomed |
| listo | ready |
| muerto | dead |
| vivo | alive |
| sano | healthy |
| herido | wounded |
| libre | free |
| lleno | full |
| vacio | empty |
| debil | weak |
| propio / propia | own |
| mejor / peor | best / worst |
| primero / ultimo | first / last |
| siguiente / anterior | next / previous |
| hoy / manana | today / tomorrow |
| inicial | starting |
| util / inutil | useful / useless |
| sube / bajar | bring up / play (a body) |
| cede | yields |
| paga | pays |

## Conventions

**Prefixes stay.** The short prefixes that group a family of helpers are already
English or neutral and do not change: `_ub_` (Ultra Ball), `_bo_` (Boss's
Orders), `_ns_` (Night Stretcher), `_ps_` (promote setup), `_op_` (opponent),
`_cf_` (Comfey), `_cub_` (Cubchoo), `_gt_` (Grand Tree), `_ld_` (Last-Ditch).

**Predicates read as claims.** A boolean is named for what it asserts, not for
what it checks: `_active_is_doomed`, not `_check_active`. Existing names that
already read this way keep their shape.

**Verbs for actions, nouns for values.** `score_boss_orders_play` returns a
score; `apply_rules` does something.

**Rule labels are data, not code.** The first argument of `_ReglaFija(...)` is a
label that shows up in `PTCG_DEBUG` traces and is quoted in docs and in the
decision notes. Those strings stay in Spanish on purpose: renaming them would
break the trail back to the write-up that justifies each rule.

**The CLI of `utils/` stays in Spanish.** Flags (`--partidas`, `--rival`,
`--pesos`, `--control-carta`) and printed output are the interface of tools that
are run by hand every day; renaming them breaks muscle memory and local scripts
for no gain.
