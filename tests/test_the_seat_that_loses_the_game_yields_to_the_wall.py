"""A un premio suyo, el cuerpo de delante no era un cambio: era la partida.

EL REGISTRO (`records/registro_009_pasos_088_hasta_110.json`, ultimo menu --
episodio 93638940 vs Mega Froslass ex / Mega Starmie ex, turno 9, PERDIDA):

    NOSOTROS (2 premios)                   RIVAL (**1 premio**)
    activo  Tapu Bulu **90**/140, 4 simb.  activo  Mega Froslass ex 310/310
            (2 Grass fisicos x Wild Growth)        (Resentful Refrain: 50 x
    banca   Meganium 160, 2 simbolos                NUESTRA mano)
            Fezandipiti ex 210
            Teal Mask Ogerpon ex 210 x2
            **Hydrapple ex 330/330**, 2 simb.
    mano    Meowth ex, Boss's Orders, Dipplin   (TRES cartas -> 150 de dano)

Wood Hammer pega 220 y su Froslass tiene 310: no noquea. Su respuesta son 50 x 3
= **150** sobre un cuerpo de **90**, y ese cadaver vale UN premio, que es todo lo
que les queda: quedarse delante ERA perder. En la banca habia un muro de 330 que
aguanta esos 150 con 180 de sobra, y la retirada del Tapu ya estaba pagada (dos
Grass fisicos son cuatro simbolos contra un coste de tres). El agente ataco.

DOS AGUJEROS, y se tapaban el uno al otro:

  1. LA LECTURA. `_op_active_attack_damage_to` devolvia **0** para Resentful
     Refrain. La tabla `ptcg/cards/op_scaling.py` la lee bien desde que existe
     (entrada 1240, `50 * s.my_hand`), pero es OPT-IN y ninguna regla defensiva
     la pedia. Con la respuesta proyectada en cero, `active_ko_likely` es False
     y NINGUN pivote del fichero puede ver venir el noqueo.

  2. LA REGLA. Aun con el numero, ninguna frase hablaba de este tablero: la
     familia que cede el frente esta escrita cuerpo a cuerpo (`_hydra_wall_pivot`
     y `_teal_wall_pivot` exigen un Teal Mask Ogerpon ex delante,
     `_doomed_mute_pivot` un activo MUDO, `_prize_denial_pivot` y
     `_doomed_ex_sac_pivot` un ex de dos premios que abaratar). Delante habia un
     cuerpo de UN premio que SI podia atacar, y contra un monton de un premio no
     hay nada que abaratar.

Y encima de los dos, el guard que se lo llevaba: `_grd_prefer_attack` ("el activo
puede atacar y nadie noquea -> ataca") vetaba la retirada desde un peldaño POR
ENCIMA del que el plan del turno ya habia decidido. El plan apuntaba al Hydrapple
(`plan.attacker=4`, 150 de Syrup Storm), asi que el menu de ATAQUE tambien se
vetaba a si mismo (`plan.attacker >= 1`). Los dos menus se cedieron el paso y el
turno se quedo SIN JUGADA: ataque -1, retirada -1, fin -10000. El argmax cayo
sobre el ataque vetado por orden de menu -- ese `[0]` del registro no es una
eleccion, es un empate entre dos vetos.

LA FRASE (`THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL`): si su respuesta
sobre el cuerpo de delante SE LLEVA LA PARTIDA y en la banca hay uno que la
aguanta, el asiento es de ese. No compra un turno mejor: compra que haya turno.

POR QUE ES DE MAZO CUALQUIERA. No nombra ni una carta: pregunta premios (los que
paga el cuerpo de delante contra los que les quedan), dano proyectado y vida. El
tablero sintetico de mas abajo -- Dipplin delante, Meganium de muro, un Alolan
Exeggutor ex enfrente, tres cartas que este agente no tiene reglas para nombrar
-- dispara exactamente igual.

Y POR QUE AQUI SI SE LEE EL NUMERO EXACTO (`scaled=True`), que en los otros 90
sitios midio NEGATIVO (-0,10 / -0,08 / -0,05 premios, tres muestras de tres): el
modo de fallo contra el que se calibro aquella medicion es volverse pasivo, y
esta regla solo habla cuando NO moverse pierde la partida. No hay pasividad que
comprar: la alternativa con la que se compara es perder.

SON DOS MENUS Y LA FRASE ES LA MISMA EN LOS DOS. Abrir la retirada no compra
nada si el menu de PROMOCION -- otro `agent()`, otra escalera -- sienta a un
cuerpo que cae al mismo golpe, y el censo lo pillo haciendolo: 2 de 19
promociones simuladas vs `crustle_wall_1`. La segunda mitad
(`PROMO_LOSING_SEAT_WALL`) y su tablero estan en la seccion 5 de este fichero.

LO QUE ARBITRA ES EL CENSO (`utils/census_the_seat_that_loses_the_game.py`),
porque un disparo del 1-5 % no cabe en el suelo de ruido de este banco. La
retirada: **3 de 931** menus del corpus congelado con **0 flips**, 0,86-0,97 % vs
crustle/starmie con todos sus flips de la forma ATACAR -> RETIRARSE, y CERO
disparos vs alakazam o dragapult, donde la regla es literalmente el mismo codigo
de antes. La promocion: 0,22-4,71 % de los menus reales, y **cada asiento que
mueve va a un cuerpo que aguanta** (P.saved == P.flips en todas las corridas).
El gate de winrate a 1500 partidas por brazo da -0,7 / +2,1 / +0,2 vs crustle y
+1,1 / -1,5 vs starmie: cambia de signo entre corridas, o sea que no lee nada.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import OptionType
from golden_corpus import reset_agent
from ptcg.calc.damage import (_op_active_attack_damage_to,
                              _reply_reaches_match_point,
                              _wall_that_outlasts_the_losing_reply)
from state_builder import G, Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "froslass_their_match_point_the_seat_that_loses_the_game_step110.json")

TAPU = m.Tapu_Bulu
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
MEGA_FROSLASS_EX = 861
RESENTFUL_REFRAIN = 1240
ALOLAN_EXEGGUTOR_EX = 193       # 300 PV, Tropical Frenzy 150 -- ni un flag suyo
                                # vive en este agente: ese es el punto del test.

# El peldaño que la regla ocupa y los dos que no puede tocar.
LOSING_SEAT_SCORE = 6750        # la retirada
LOSING_SEAT_WALL = m.PROMO_LOSING_SEAT_WALL     # la promocion
SACRIFICE_FAMILY_TOP = 6700     # `_wall_ko_promote`, el mas alto de la familia
SNIPE_FLOOR = 8500              # el ataque que YA se lleva un premio


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)
    m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = True


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _sides(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]


def _menu_index(obs, option_type):
    for i, opt in enumerate(obs["select"]["option"]):
        if opt["type"] == int(option_type):
            return i
    raise AssertionError(f"{option_type} no esta en este menu")


def _ctx(obs, flag=True):
    """El `ScoringCtx` con el que el scorer vio ESTE tablero.

    Las lecturas que este fichero comprueba (`_op_active_attack_damage_to` con
    `scaled=True`, y el propio lector) cuelgan de `AGENT_STATE.op_scale`, que
    `agent()` construye una vez por turno. Preguntarlas fuera de un turno es
    preguntarlas contra `EMPTY_SCALE`, o sea contra ceros: por eso se leen desde
    aqui y no fabricando estados a mano.
    """
    seen = []
    original = m.score_option

    def spy(ctx, option, score):
        if not seen:
            seen.append(ctx)
        return original(ctx, option, score)

    prev = m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL
    m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = flag
    m.score_option = spy
    try:
        m.agent(obs)
    finally:
        m.score_option = original
        m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = prev
    return seen[0]


def _choice(obs, flag=True):
    """La eleccion del agente con la bandera puesta o quitada."""
    prev = m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL
    m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = flag
    try:
        return m.agent(obs)
    finally:
        m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = prev


def _scores(obs, flag=True):
    """La puntuacion de cada opcion, espiando `score_option`.

    Es la unica funcion por la que pasa cada opcion con el contexto ya
    construido, asi que lo que se lee aqui es lo que el scorer vio.
    """
    out = []
    original = m.score_option

    def spy(ctx, option, score):
        result = original(ctx, option, score)
        out.append(result)
        return result

    prev = m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL
    m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = flag
    m.score_option = spy
    try:
        m.agent(obs)
    finally:
        m.score_option = original
        m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = prev
    return out


# ---------------------------------------------------------------------------
# 1. El escenario: sin esto el test no mide nada
# ---------------------------------------------------------------------------

def test_the_fixture_is_their_match_point_with_a_wall_on_the_bench():
    obs = _obs()
    mine, theirs = _sides(obs)

    # Su monton es de UNO y el cuerpo de delante lo paga entero.
    assert len(theirs["prize"]) == 1
    active = mine["active"][0]
    assert active["id"] == TAPU and active["hp"] == 90
    assert not m.card_table[TAPU].ex and not m.card_table[TAPU].megaEx

    # Su Froslass no cae a Wood Hammer: 220 contra 310.
    front = theirs["active"][0]
    assert front["id"] == MEGA_FROSLASS_EX and front["hp"] == 310
    assert m.attack_table[m.card_table[TAPU].attacks[0]].damage == 220

    # Y en la banca esta el muro entero, con la retirada del Tapu ya pagada
    # (dos Grass fisicos = cuatro simbolos contra un coste de tres).
    wall = next(b for b in mine["bench"] if b and b["id"] == HYDRAPPLE)
    assert wall["hp"] == wall["maxHp"] == 330
    assert len(active["energies"]) == 4 >= m.card_table[TAPU].retreatCost

    # El menu es el del hallazgo: atacar, retirarse o pasar.
    assert {o["type"] for o in obs["select"]["option"]} == {
        int(OptionType.ATTACK), int(OptionType.RETREAT), int(OptionType.END)}


# ---------------------------------------------------------------------------
# 2. La lectura: el numero que nadie pedia
# ---------------------------------------------------------------------------

def test_their_scaling_attack_reads_zero_without_asking_for_it():
    """El agujero 1, aislado: la proyeccion ciega dice CERO sobre un cuerpo de
    90 que su ataque mata. Es la lectura que ven `active_ko_likely` y con ella
    todos los pivotes del fichero."""
    ctx = _ctx(_obs())
    front = ctx.op_state.active[0]
    active = ctx.my_state.active[0]

    assert m.attack_table[RESENTFUL_REFRAIN].damage == 0      # lo que imprime
    assert _op_active_attack_damage_to(
        front, active, ctx.op_state.handCount) == 0
    assert ctx.active_ko_likely is False                      # la consecuencia


def test_the_accurate_projection_sees_the_knockout_and_the_wall():
    obs = _obs()
    ctx = _ctx(obs)
    mine, theirs = _sides(obs)
    front = ctx.op_state.active[0]
    active = ctx.my_state.active[0]
    wall = next(b for b in ctx.my_state.bench if b and b.id == HYDRAPPLE)

    reply = _op_active_attack_damage_to(front, active, theirs["handCount"],
                                        scaled=True)
    assert reply == 50 * len(mine["hand"]) == 150   # su tabla, no una estimacion
    assert reply >= active.hp                       # el cuerpo de delante cae
    assert reply < wall.hp                          # y el de la banca no


def test_the_reader_names_the_wall_on_this_board():
    ctx = _ctx(_obs())
    survivor = _wall_that_outlasts_the_losing_reply(
        ctx.my_state, ctx.op_state, ctx.op_state.handCount)
    assert survivor is not None and survivor.id == HYDRAPPLE


def test_it_is_a_stricter_boundary_than_reaching_match_point():
    """La frase de al lado (`_reply_reaches_match_point`) se conforma con que su
    respuesta los DEJE a un noqueo; esta exige que se lleve la partida. Con dos
    premios en su monton la primera sigue hablando y esta se calla, que es la
    unica diferencia entre comprar un turno y comprar que haya turno."""
    two = _obs()
    _sides(two)[1]["prize"] = [None, None]              # les quedan DOS
    ctx = _ctx(two)
    assert _reply_reaches_match_point(
        ctx.my_state.active[0], ctx.op_state, ctx.op_state.active[0]) is True
    assert _wall_that_outlasts_the_losing_reply(
        ctx.my_state, ctx.op_state, ctx.op_state.handCount) is None

    one = _ctx(_obs())                                 # les queda UNO
    assert _wall_that_outlasts_the_losing_reply(
        one.my_state, one.op_state, one.op_state.handCount) is not None


# ---------------------------------------------------------------------------
# 3. La decision, y el control
# ---------------------------------------------------------------------------

def test_it_retreats_instead_of_attacking_into_their_last_prize():
    obs = _obs()
    assert m.agent(obs) == [_menu_index(obs, OptionType.RETREAT)]


def test_without_the_rule_the_turn_has_no_play_at_all():
    """El control, y lo que dice es peor que "elige mal": con la bandera quitada
    las TRES opciones estan vetadas y el ataque gana por orden de menu."""
    scores = _scores(_obs(), flag=False)
    obs = _obs()
    attack = scores[_menu_index(obs, OptionType.ATTACK)]
    retreat = scores[_menu_index(obs, OptionType.RETREAT)]
    assert attack < 0 and retreat < 0, scores      # dos vetos...
    assert attack == retreat, scores               # ...y un empate
    assert _choice(obs, flag=False) == [_menu_index(obs, OptionType.ATTACK)]


def test_with_the_rule_the_retreat_stops_being_a_veto():
    obs = _obs()
    scores = _scores(obs, flag=True)
    assert scores[_menu_index(obs, OptionType.RETREAT)] == LOSING_SEAT_SCORE
    assert (scores[_menu_index(obs, OptionType.RETREAT)]
            > scores[_menu_index(obs, OptionType.ATTACK)])


def _promotion_menu(obs):
    """El menu SWITCH que el simulador emite justo despues de cobrar el coste,
    con el peaje ya pagado (el mismo tablero que `promote_after_retreat`)."""
    from cg.api import AreaType, SelectContext, SelectType
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    active = mine["active"][0]
    mine["discard"] = list(mine["discard"]) + active["energyCards"]
    active["energyCards"], active["energies"] = [], []
    cur["retreated"] = True
    obs["select"] = {
        "type": int(SelectType.CARD), "context": int(SelectContext.SWITCH),
        "minCount": 1, "maxCount": 1,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": int(OptionType.CARD), "area": int(AreaType.BENCH),
                    "index": k, "playerIndex": 0}
                   for k in range(len(mine["bench"]))],
        "deck": None, "contextCard": None, "effect": None,
    }
    return obs


def test_the_promotion_then_seats_the_body_that_survives():
    """La otra mitad del turno: abrir la retirada no sirve si sube otro cuerpo."""
    obs = _promotion_menu(_obs())
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    choice = m.agent(obs)[0]
    assert mine["bench"][choice]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# 4. Cualquier mazo: el tablero sintetico, sin una sola carta del registro
# ---------------------------------------------------------------------------

def _synthetic(op_prizes=1, wall=True):
    """Dipplin delante, Meganium de muro, Alolan Exeggutor ex enfrente.

    Ni el activo, ni el muro, ni el rival aparecen en ninguna de las frases de
    la familia: `_hydra_wall_pivot` y `_teal_wall_pivot` piden un Teal Mask
    Ogerpon ex delante, `_doomed_mute_pivot` un activo mudo (este ataca) y los
    dos pivotes de premio un ex de dos premios (Dipplin cuesta uno).

    Tropical Frenzy son 150 impresos: mata al Dipplin de 80 y NO al Meganium de
    160. El Meganium ademas dobla el Grass del Dipplin (Wild Growth), que es lo
    que hace pagable su retirada de coste 2 con una sola carta.

    `wall=False` cambia el muro por un Applin de 40, que cae al mismo golpe.
    """
    bench = pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]) if wall else pk(APPLIN)
    return (Scenario(turn=10, step=200, tac=2, own_prizes=3)
            .my_active(pk(DIPPLIN, energies=[G, G], fisicas=1, pre_evo=[APPLIN]))
            .my_bench(bench)
            .op_active(pk(ALOLAN_EXEGGUTOR_EX, hp=300, max_hp=300,
                          energies=[G, G]))
            .op_zones(hand=4, deck=30, prizes=op_prizes)
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def test_the_synthetic_board_is_the_one_the_old_guard_owned():
    """Sin la regla, este tablero es exactamente el del registro: el activo
    puede atacar, nadie noquea, y `_grd_prefer_attack` veta la retirada.

    Con una diferencia que lo hace MEJOR control que el registro: aqui el plan
    no apunta a ningun cuerpo de la banca, asi que el ataque NO se veta a si
    mismo. La retirada no gana un empate entre vetos, gana a una jugada viva."""
    obs = _synthetic()
    scores = _scores(obs, flag=False)
    assert scores[_menu_index(obs, OptionType.RETREAT)] < 0, scores
    assert scores[_menu_index(obs, OptionType.ATTACK)] > 0, scores
    assert _choice(obs, flag=False) == [_menu_index(obs, OptionType.ATTACK)]


def test_it_fires_on_a_board_with_none_of_the_cards_of_the_record():
    obs = _synthetic()
    scores = _scores(obs, flag=True)
    assert scores[_menu_index(obs, OptionType.RETREAT)] == LOSING_SEAT_SCORE
    assert _choice(_synthetic()) == [_menu_index(obs, OptionType.RETREAT)]


def test_it_stays_silent_when_their_knockout_does_not_end_the_game():
    """El mismo tablero con DOS premios en su monton: el cuerpo de delante
    vuelve a ser un cambio y la regla no tiene nada que decir."""
    obs = _synthetic(op_prizes=2)
    scores = _scores(obs, flag=True)
    assert scores[_menu_index(obs, OptionType.RETREAT)] < 0, scores


def test_it_stays_silent_when_the_bench_dies_to_the_same_attack():
    """Y sin muro no hay frase: retirarse hacia un cuerpo que cae al mismo
    golpe no compra ningun turno -- es el mismo argumento que
    [[el-muro-que-cae-al-mismo-golpe-no-es-un-muro]]."""
    obs = _synthetic(wall=False)
    scores = _scores(obs, flag=True)
    assert scores[_menu_index(obs, OptionType.RETREAT)] < 0, scores


# ---------------------------------------------------------------------------
# 5. LA MITAD DE LA PROMOCION: el asiento tambien se elige con esta frase
# ---------------------------------------------------------------------------
#
# EL TABLERO (`_PROMO_FIXTURE`) no salio de una partida jugada por un humano sino
# del CENSO de la mitad de arriba: contando cuantas promociones simuladas tras el
# pivote sientan un cuerpo que tampoco aguanta, 2 de 19 vs `crustle_wall_1` lo
# hacian. Este es uno de esos dos, capturado entero.
#
#     NOSOTROS (5 premios)                 RIVAL (**1 premio**)
#     activo  -- retirado, peaje pagado    activo  Cornerstone Mask Ogerpon ex
#     banca   **Meganium 160/160, 4 Grass**        310/310 (Demolish 140)
#             Teal Mask Ogerpon ex 70/210  banca   Mega Kangaskhan ex, Crustle
#             Dipplin 80/80
#             Fezandipiti ex 210/210
#             Chikorita 70/70
#
# Sus 140 solo los aguanta el Meganium -- y el Meganium estaba **vetado a
# SCORE_NEVER**, porque "la linea del Meganium no sube a activo" protege el Wild
# Growth desde la banca y su unica exencion esta escrita para la promocion
# FORZADA (`_forced_ko_promote`), que aqui es False: este menu lo abrio una
# retirada nuestra. Con el unico superviviente en -10100, el asiento se lo llevo
# el Dipplin de 80 con -4745, el menos malo de una mesa entera de negativos.

_PROMO_FIXTURE = (ROOT / "tests" / "fixtures"
                  / "crustle_their_match_point_the_engine_yields_the_seat.json")

CORNERSTONE = 117
CHIKORITA_ID = m.Chikorita


def _promo_obs():
    return copy.deepcopy(
        json.load(open(_PROMO_FIXTURE, encoding="utf-8"))["observation"])


def _bench_index(obs, card_id):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return next(i for i, b in enumerate(mine["bench"])
                if b and b["id"] == card_id)


def test_the_promotion_fixture_is_their_match_point_with_one_survivor():
    obs = _promo_obs()
    mine, theirs = _sides(obs)

    assert len(theirs["prize"]) == 1
    assert theirs["active"][0]["id"] == CORNERSTONE
    assert obs["select"]["context"] == int(
        __import__("cg.api", fromlist=["SelectContext"]).SelectContext.SWITCH)

    ctx = _ctx(obs)
    survivors = [b for b in ctx.my_state.bench
                 if b is not None and ctx._losing_seat_survivor(b)]
    assert [b.id for b in survivors] == [MEGANIUM], [
        (b.id, b.hp) for b in ctx.my_state.bench if b]


def test_without_the_rule_the_only_survivor_is_vetoed_and_a_corpse_sits_down():
    """El control. Y otra vez no es "elige mal": es una mesa entera de
    negativos, con el unico superviviente **el mas negativo de todos** por la
    reserva del motor, y el argmax quedandose con el menos malo."""
    obs = _promo_obs()
    scores = _scores(obs, flag=False)
    engine = scores[_bench_index(obs, MEGANIUM)]
    seated = max(scores)
    assert engine < 0 and seated < 0, scores
    assert engine == min(scores), scores          # el que vive, el mas vetado
    assert _choice(_promo_obs(), flag=False) == [_bench_index(obs, DIPPLIN)]


def test_the_engine_reservation_yields_the_seat_to_the_only_survivor():
    obs = _promo_obs()
    scores = _scores(obs, flag=True)
    assert scores[_bench_index(obs, MEGANIUM)] >= LOSING_SEAT_WALL, scores
    assert _choice(_promo_obs()) == [_bench_index(obs, MEGANIUM)]


def test_it_does_not_lift_a_body_that_dies_to_the_same_reply():
    """Solo levanta a los que aguantan: los demas se quedan donde estaban."""
    obs = _promo_obs()
    on = _scores(obs, flag=True)
    off = _scores(_promo_obs(), flag=False)
    for card in (DIPPLIN, m.Fezandipiti_ex, CHIKORITA_ID):
        i = _bench_index(obs, card)
        assert on[i] == off[i], (card, on, off)


def test_the_ordering_between_survivors_is_preserved():
    """Con DOS que aguantan, la reserva del motor vuelve a decidir -- que es
    cuando esa reserva si tiene algo que decir. El suelo lleva sumada la
    puntuacion que traia cada uno, recortada, asi que el orden no se pierde."""
    obs = _promo_obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in mine["bench"]:
        if b["id"] == m.Fezandipiti_ex:
            b["hp"] = b["maxHp"] = 400        # ahora tambien aguanta sus 140x2
    scores = _scores(obs, flag=True)
    fez = scores[_bench_index(obs, m.Fezandipiti_ex)]
    engine = scores[_bench_index(obs, MEGANIUM)]
    assert fez >= LOSING_SEAT_WALL and engine >= LOSING_SEAT_WALL, scores
    assert fez > engine, scores                # el motor se queda en la banca
    assert _choice(obs) == [_bench_index(obs, m.Fezandipiti_ex)]


def test_it_stays_silent_when_nobody_dies_to_the_reply():
    """Evidencia positiva por los dos lados: si NADIE cae, no hay nada que
    decidir y la regla no toca ninguna puntuacion."""
    obs = _promo_obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in mine["bench"]:
        b["hp"] = b["maxHp"] = 400
    assert _scores(obs, flag=True) == _scores(_promo_obs_all_400(), flag=False)


def _promo_obs_all_400():
    obs = _promo_obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in mine["bench"]:
        b["hp"] = b["maxHp"] = 400
    return obs


# ---------------------------------------------------------------------------
# 6. La banda: la aritmetica es la especificacion
# ---------------------------------------------------------------------------

def test_the_wall_seat_outranks_every_reservation_and_yields_to_the_win():
    """POR ENCIMA de la reserva del motor (SCORE_NEVER) y del veto de precio
    (PROMO_MATCH_POINT_VETO), que a su match point condena a todo el mundo. POR
    DEBAJO del asiento que cierra la partida (15000) y del que noquea (20000):
    si nuestro noqueo va primero, su respuesta no llega a existir."""
    from ptcg.cards.ids import SCORE_NEVER
    from ptcg.cards.scoring import (PROMO_CLOSER_SEAT, PROMO_KO_BONUS,
                                    PROMO_MATCH_POINT_VETO)
    assert LOSING_SEAT_WALL > SCORE_NEVER
    assert LOSING_SEAT_WALL > PROMO_MATCH_POINT_VETO
    assert LOSING_SEAT_WALL + m.PROMO_LOSING_SEAT_RANK < PROMO_CLOSER_SEAT
    assert LOSING_SEAT_WALL + m.PROMO_LOSING_SEAT_RANK < PROMO_KO_BONUS


def test_the_seat_outranks_the_whole_pivot_family():
    """POR ENCIMA de los pivotes de sacrificio y de muro (6400-6700). Todos
    ellos ponen precio a la retirada contra los turnos que vienen despues; este
    es el unico que discute si va a haber alguno."""
    assert LOSING_SEAT_SCORE > SACRIFICE_FAMILY_TOP


def test_the_attack_that_takes_a_prize_still_has_the_last_word():
    """POR DEBAJO del ataque que ya se cobra un premio (8500+) y del que gana la
    partida (99000): esos terminan antes de que la respuesta exista."""
    assert LOSING_SEAT_SCORE < SNIPE_FLOOR
