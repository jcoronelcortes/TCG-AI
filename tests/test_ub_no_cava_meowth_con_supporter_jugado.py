"""The Ultra Ball is only played if there is something to dig for AND that something can be played.

Scenario (user, episode 88693856, registro_006 steps 98-104, turn 6 vs Mega
Lucario ex, LOST):

    US                                          OPPONENT
    active  Hydrapple ex 330  2 {G}             active  Mega Lucario ex 440/440
    bench   Teal Mask Ogerpon ex 2 {G}                  (with a Hero's Cape)
            Fezandipiti ex 0 {G}                bench   Applin, Fezandipiti ex,
            Meganium 2 {G}                              Meowth ex, Meganium
    hand    Ultra Ball x2, Hydrapple ex, Lana's Aid, Dipplin, Boss's Orders,
            Forest of Vitality, Xerosic's Machinations, Basic {G} x2
    The turn's Supporter: ALREADY PLAYED (Lillie's Determination, action 10)

The menu of action 16 offered only THREE things: the two Ultra Balls, Syrup
Storm (30 + 30 for each {G} on the field = 30 + 6x30 = **210 damage**) and ending.
The agent played BOTH Ultra Balls -- discarding Forest of Vitality, Xerosic's
Machinations, Dipplin and Lana's Aid -- to dig out the TWO Meowth ex from the deck... and
in action 22 it fired the same 210 Syrup Storm it could have fired in
action 16. Balance of the turn: -4 cards of hand and two 2-PRIZE bodies
dead in hand, for exactly nothing.

Meowth ex is worth EXCLUSIVELY its Last-Ditch Catch (searching for a Supporter).
With the turn's Supporter already played, the Supporter the fetch brings cannot
be played: the dug card is born dead -- and the PLAY branch itself knows it
([[no-meowth-si-supporter-ya-jugado]]), so much so that it vetoed playing the Meowth (-1e5)
right after having dug it out.

THREE links failed at once, which is why none of the existing vetoes
stopped the play:

  1. THE FETCH did not check that the ability could produce anything: the rule
     `lillie_en_mazo_refresco` gave 1000 to Meowth ex (beating Chikorita 30 /
     Meganium 25 / Bayleef 20) by looking only at whether a Lillie's was left in the deck.
     Fix: `last_ditch_no_produce` (with the Supporter played or the Last-Ditch
     already spent, Meowth falls to 10, as with Watchtower).
  2. THE ANTI-STERILE-TURN NET resurrected the vetoed Ultra Ball at 200 because it
     read `scores[best] <= 0` as "the turn ends in END". That is not the same: a
     normal ATTACK scores -1 by default, and Items do not consume the attack.
     Fix: a turn with an attack that does real damage is NOT sterile; and
     Meowth ex no longer counts as a "useful basic" if its Last-Ditch produces nothing.
  3. THE VETO FLOOR was SCORE_VETO (-1), the same as the attack, so in
     action 19 -- with the net already switched off -- the Ultra Ball won the tie-break
     by menu INDEX. Fix: SCORE_CANCEL (-100) in the "this Ultra Ball contributes
     nothing" vetoes, which is exactly what that constant exists for.

What does NOT change: the Ultra Ball still digs for Meowth ex when the Supporter
slot is free and the Last-Ditch available (the UB->Meowth->Lillie's and
UB->Meowth->Xerosic engines, which already required `not supporterPlayed`), and the
anti-sterile-turn net still rescues the turns that really end in END.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import instalar

MEOWTH = m.Meowth_ex
CHIKORITA = m.Chikorita
ULTRA_BALL = m.Ultra_Ball
SYRUP_STORM = 195

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_ub_no_cava_meowth_con_supporter_jugado_step98.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ub_engine_pivot_turn = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _observaciones():
    """The 7 observations of OUR turn 6 (turnActionCount 16..22)."""
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observaciones"]


def _por_accion(obs_list):
    return {o["current"]["turnActionCount"]: o for o in obs_list}


def _jugada(obs, eleccion):
    """('PLAY'|'CARTA', card_id) / ('ATTACK', attackId) / ('END', None)."""
    o = obs["select"]["option"][eleccion[0]]
    tipo = o["type"]
    yo = obs["current"]["yourIndex"]
    jugador = obs["current"]["players"][yo]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", jugador["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.CARD):
        if o.get("area") == int(m.AreaType.DECK) and obs["select"].get("deck"):
            return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
        return ("CARTA", None)
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _reproducir(obs_list):
    """Replays the turn IN ORDER and returns {turnActionCount: play}."""
    return {o["current"]["turnActionCount"]: _jugada(o, m.agent(o))
            for o in obs_list}


# ---------------------------------------------------------------------------
# 1. The real turn: it attacks instead of chaining two Ultra Balls
# ---------------------------------------------------------------------------

def test_paso98_ataca_en_vez_de_cavar_un_meowth_que_no_se_puede_jugar():
    hecho = _reproducir(_observaciones())
    assert hecho[16] == ("ATTACK", SYRUP_STORM), hecho[16]


def test_paso101_la_segunda_ultra_ball_tampoco_se_juega():
    """The real log repeats the mistake: with the 1st Ultra Ball already spent the menu
    offers Ultra Ball / Meowth ex / attack again, and it dug once more."""
    hecho = _reproducir(_observaciones())
    assert hecho[19] == ("ATTACK", SYRUP_STORM), hecho[19]


def test_el_menu_ofrecia_de_verdad_las_dos_jugadas():
    """Without the Ultra Ball AND the attack in the menu the test discriminates nothing."""
    for tac in (16, 19):
        jugadas = _jugadas(_por_accion(_observaciones())[tac])
        assert ("PLAY", ULTRA_BALL) in jugadas, (tac, jugadas)
        assert ("ATTACK", SYRUP_STORM) in jugadas, (tac, jugadas)


# ---------------------------------------------------------------------------
# 2. The three links, one by one
# ---------------------------------------------------------------------------

def test_el_fetch_no_elige_meowth_con_el_supporter_del_turno_jugado():
    """If an Ultra Ball were played even so, the fetch does NOT bring a Meowth ex: its
    Last-Ditch cannot produce a playable Supporter this turn."""
    obs_list = _observaciones()
    hecho = {}
    for o in obs_list:
        # Every menu of the record is answered (including those of the Ultra
        # Ball we would no longer play) so the fetch is reached with the state warmed up.
        hecho[o["current"]["turnActionCount"]] = _jugada(o, m.agent(o))
    assert hecho[18] == ("CARTA", CHIKORITA), hecho[18]
    assert hecho[21] == ("CARTA", CHIKORITA), hecho[21]


def test_la_ultra_ball_inutil_queda_por_debajo_del_piso_de_veto():
    """SCORE_CANCEL, not SCORE_VETO: if it tied with the attack (-1) the
    menu index tie-break would play the Ultra Ball again."""
    visto = {}
    orig = m._score_ultra_ball_play

    def espia(ctx):
        r = orig(ctx)
        visto.setdefault(ctx.state.turnActionCount, []).append(r)
        return r

    _rest_score_ultra_ball_play = instalar("_score_ultra_ball_play", espia)
    try:
        _reproducir(_observaciones())
    finally:
        _rest_score_ultra_ball_play()
    assert visto[16], visto
    for tac in (16, 19):
        for score in visto[tac]:
            assert score <= m.SCORE_CANCEL, (tac, score)
            assert score < m.SCORE_VETO, (tac, score)


def test_la_red_anti_turno_esteril_no_dispara_con_un_ataque_real():
    """The link that resurrected the vetoed Ultra Ball at 200: a turn that ends
    with a 210 Syrup Storm is not a dead turn."""
    obs16 = _por_accion(_observaciones())[16]
    m.agent(obs16)
    # If the net had fired, the Ultra Ball would have come out at 200 and the
    # agent would have chosen it; the real attack is the proof that it did not.
    assert _jugada(obs16, m.agent(obs16)) == ("ATTACK", SYRUP_STORM)


# ---------------------------------------------------------------------------
# 3. What does NOT break: with the Supporter slot free, Meowth is still
#    the fetch's target
# ---------------------------------------------------------------------------

def test_con_el_supporter_libre_el_fetch_sigue_eligiendo_meowth():
    """The new rule is a CONDITIONAL veto, not a prohibition: the same
    search menu with `supporterPlayed` False brings Meowth ex back
    (the UB -> Meowth -> Last-Ditch -> Lillie's engine)."""
    obs_list = _observaciones()
    for o in obs_list[:2]:          # it warms the state up to the fetch
        m.agent(o)
    fetch = _por_accion(obs_list)[18]
    fetch = json.loads(json.dumps(fetch))
    fetch["current"]["supporterPlayed"] = False
    assert _jugada(fetch, m.agent(fetch)) == ("CARTA", MEOWTH)
