"""THE COMMITMENT PAYS FOR A SUPPORTER, NEVER FOR A PRIZE.

Scenario (user, episode 91069873, `records/registro_006_pasos_062_hasta_084.json`
step 80, turn 6 vs Marnie's Grimmsnarl ex, **WON in spite of this**):

    US (seat 1, 5 prizes)                    RIVAL (5 prizes)
    active  **Hydrapple ex, 4 effective      active  **Marnie's Grimmsnarl ex
            energies** (Syrup Storm ready)           320/320, Grass WEAKNESS,
    bench   Teal Mask Ogerpon ex 2e,                 **2 prizes**
            Meganium, Teal Mask Ogerpon      bench   **Marnie's Morgrem 100 HP
            ex 2e, **Meowth ex (benched              (1 prize)**, Munkidori 110,
            THIS turn)**                             Marnie's Impidimp 70
    hand    **Boss's Orders**, Meowth ex
    stadium theirs

Syrup Storm is `30 + 30 x Grass on the field` and Meganium's Wild Growth doubles
every Grass: 8 effective -> 270, and the Grimmsnarl ex is Grass-WEAK -> **540**.
That is a KO on a 320 HP Pokemon ex standing in the active spot: **two prizes,
served, with the attack already in the menu**.

What the agent played was **Boss's Orders on the Marnie's Morgrem**, and then the
same Syrup Storm against a 100 HP Stage 1: **one prize instead of two**, and the
Grimmsnarl ex went back to the bench alive.

THE BUG: A COMMITMENT OVERRULING A PRIZE
----------------------------------------
Earlier in the same turn (step 68) the Meowth ex benched THIS turn used its
Last-Ditch Catch to fetch that very Boss's, which arms `_ld_supp_comprometido`
([[test_ld_committed_supporter]]): the body is paid for, so the Supporter it
brought keeps the turn's only slot with a score FLOOR of
`SCORE_LD_SUPP_COMPROMETIDO` (8000).

The Boss's ladder had ALREADY said no -- `no_value`, **-1**: with the KO served
in front there is nothing to gust for. The floor lifted that -1 to 8000, which
in this menu was not competing against another Supporter but against the ATTACK
(1100), so the gust went through and the turn traded its own 2-prize KO for a
1-prize one.

THE FIX: the gust is the one Supporter that changes the board
------------------------------------------------------------
`ptcg/turn/finalize.py`, mirror of the `_ld_gust_cashes` half that already lived
next to it (there a committed REFILL yields to a Boss's that is cashing; here the
committed card IS the Boss's and its own ladder vetoed it). A refill -- Dawn,
Lillie's, Lana's, Xerosic -- only moves OUR cards, so a commitment (an argument
about a resource already spent) may overrule the resource veto that stopped it.
Boss's Orders is the only Supporter that rewrites the body in the active spot,
which is the body we KNOCK OUT: its veto is a decision about PRIZES, and no
amount of sunk Meowth ex buys prizes back.

Deck-agnostic and reason-agnostic: it reads the Boss's OWN score, not a board and
not why the ladder vetoed it. Every live rung of that ladder is above zero (the
lowest, EMPTY, is 20), so `<= 0` is the ladder's own seam.

Same family as [[el-premio-de-enfrente-se-mide-por-la-misma-ruta-que-el-gusteo]]
(a gust is a CHANGE of the body we knock out, so it can never trade prizes down)
and of [[el-puntero-del-plan-es-una-promesa-y-caduca]] (a promise written in one
step and cashed in another without re-reading the board).

**Measured:** ONE flip in a census of **390** of our decisions over all of
`records/` + `records/marnie/` + the 20 episodes of `log/` -- the intended one.
Golden corpus: 1 flip, the same one. Suite green.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

BOSS = m.Boss_Orders
LILLIE = m.Lillie_Determination
MEOWTH = m.Meowth_ex
HYDRAPPLE = m.Hydrapple_ex
MORGREM = m.Marnies_Morgrem
GRIMMSNARL = 648
SYRUP_STORM = 195

_FIX = (ROOT / "tests" / "fixtures"
        / "marnie_the_commitment_does_not_resurrect_the_vetoed_gust_step80.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    m.AGENT_STATE._ld_supp_comprometido = 0
    yield
    m.AGENT_STATE._ld_supp_comprometido = 0
    m._init_cards_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f))


def _idx_of_type(obs, tipo):
    return [o["type"] for o in obs["select"]["option"]].index(int(tipo))


def _idx_play(obs, card_id):
    yo = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


def _armar_compromiso(fx):
    """Replays the Last-Ditch of the record: it is what arms the commitment."""
    return m.agent(fx["observacion_previa"])


# ---------------------------------------------------------------------------
# 1. The board: without it the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_a_served_ko_on_a_two_prize_ex():
    obs = _fixture()["observation"]
    cur = obs["current"]
    yo = cur["yourIndex"]
    mine, rival = cur["players"][yo], cur["players"][1 - yo]

    assert mine["active"][0]["id"] == HYDRAPPLE
    assert len(mine["active"][0]["energies"]) == 4
    assert rival["active"][0]["id"] == GRIMMSNARL
    assert rival["active"][0]["hp"] == 320
    assert MORGREM in [b["id"] for b in rival["bench"]]
    # The Supporter slot is still free and the Boss's is in hand: both halves
    # of the decision are really on the table.
    assert not cur["supporterPlayed"]
    assert BOSS in [c["id"] for c in mine["hand"]]
    assert _idx_of_type(obs, m.OptionType.ATTACK) >= 0


def test_the_gust_would_trade_two_prizes_for_one():
    obs = m.to_observation_class(_fixture()["observation"])
    cur = obs.current
    yo = cur.yourIndex
    rival = cur.players[1 - yo]
    morgrem = [b for b in rival.bench if b.id == MORGREM][0]

    assert m.prize_count_op(rival.active[0]) == 2
    assert m.prize_count_op(morgrem) == 1

    # Syrup Storm reaches the 320 HP ex standing in front: the KO the turn
    # already owns is the bigger one.
    mine = cur.players[yo]
    grass = sum(len(p.energies) for p in (mine.active or []) + (mine.bench or []))
    base = m._attacker_base_damage(HYDRAPPLE, rival.active[0], len(mine.active[0].energies),
                                   grass_scale=grass, teal_self_energy=0, bench_count=len(mine.bench))
    dano = m._our_effective_damage(mine.active[0], rival.active[0], base, True, False)
    assert dano >= rival.active[0].hp


def test_the_last_ditch_arms_the_commitment_on_the_boss():
    fx = _fixture()
    _armar_compromiso(fx)
    # Without this the menu of step 80 never sees the floor and the test would
    # be green for the wrong reason.
    assert m.AGENT_STATE._ld_supp_comprometido == BOSS


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_with_the_commitment_armed_the_turn_attacks_the_two_prize_ex():
    fx = _fixture()
    _armar_compromiso(fx)
    obs = fx["observation"]

    eleccion = m.agent(obs)

    assert eleccion == [_idx_of_type(obs, m.OptionType.ATTACK)]
    assert eleccion != [_idx_play(obs, BOSS)]
    assert obs["select"]["option"][eleccion[0]]["attackId"] == SYRUP_STORM


# ---------------------------------------------------------------------------
# 3. Frontiers: what the rule must NOT change
# ---------------------------------------------------------------------------

def test_without_the_commitment_the_gust_had_already_lost():
    """The ladder was never the problem: it scored the gust a veto on its own.

    Cold, with no commitment armed, the same menu already attacks. The rule
    invents no preference -- it only stops the floor from overruling one.
    """
    obs = _fixture()["observation"]
    assert m.AGENT_STATE._ld_supp_comprometido == 0
    assert m.agent(obs) == [_idx_of_type(obs, m.OptionType.ATTACK)]


def test_a_committed_refill_is_still_resurrected():
    """The founding case (registro_002 step 22) survives untouched.

    Same board, same commitment, but the fetched Supporter is a REFILL: it only
    moves our own cards, so the floor still hands it the turn's slot.
    """
    fx = _fixture()
    obs = fx["observation"]
    yo = obs["current"]["yourIndex"]
    obs["current"]["players"][yo]["hand"][0]["id"] = LILLIE

    _armar_compromiso(fx)
    m.AGENT_STATE._ld_supp_comprometido = LILLIE

    assert m.agent(obs) == [_idx_play(obs, LILLIE)]


def test_when_the_active_is_out_of_reach_the_committed_gust_comes_back():
    """The guard reads the Boss's SCORE, not the card.

    Put the body in front out of Syrup Storm's reach and the gust stops being
    dominated: the ladder scores it alive, the commitment stands, and the
    Boss's is played again.
    """
    fx = _fixture()
    obs = fx["observation"]
    yo = obs["current"]["yourIndex"]
    rival_active = obs["current"]["players"][1 - yo]["active"][0]
    rival_active["hp"] = 700
    rival_active["maxHp"] = 700

    _armar_compromiso(fx)

    assert m.agent(obs) == [_idx_play(obs, BOSS)]
