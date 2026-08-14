"""Festival Grounds is SHARED: our Dipplin throws Do the Wave twice as well.

Scenario (user, `records/registro_006_pasos_081_hasta_086.json`, episode
91522323, turn 6 vs *Festival Lead* -- LOST):

    US (5 prizes)                        RIVAL (4 prizes)
    active  Teal Mask Ogerpon ex         active  Dipplin      80/80, 1 {G}
            **10**/210, 3 {G}            bench   Volbeat      70
    bench   Tapu Bulu   140, 1 {G}               Thwackey    100
            Applin       40                      Grookey      70
            Bayleef     110                      Applin       40
            Teal Mask Ogerpon ex 210, 1 {G}      Applin       40
    hand    Dipplin, Ultra Ball, 1 {G}   stadium **Festival Grounds** (theirs)

Their Dipplin had just used *Do the Wave* TWICE into the same body -- 210 ->
110 -> 10, with no knockout in between, which is the record's own proof that
*Festival Lead* does not need one: *"If Festival Grounds is in play, this
Pokemon may use an attack it has twice."*

The turn started well and then paid for a prize it did not have to. It evolved
the benched Applin into **Dipplin**, spent the one Grass in hand on a Teal Dance
into the BENCHED Ogerpon ex, and attacked with the 10 HP active: Myriad Leaf
Shower 30 + 30 x (3 + 1) = 150 kills their 80 HP Dipplin. **One prize.** Then
the 10 HP ex stayed in the Active spot and the reply took **two** --
`turn_plan.op_prizes_after_ko` said `2` on that very board and nothing read it.

THE TURN THAT WAS AVAILABLE. The Grass goes onto the Dipplin we had just
evolved, the ex RETREATS (cost 1, it carries 3) and *Do the Wave* = 20 x 4
benched = **80** takes the same knockout -- and then, because Festival Grounds
is on the field, **it attacks again**. Three of the five bodies they can promote
(Volbeat 70, Grookey 70, two Applin 40) die to a second 80. The prize is cashed
by a **1-prize** body that survives the reply, and the wounded ex is not merely
hidden: Teal Mask Ogerpon ex's *Tera* prevents ALL damage to it while it is on
our Bench.

WHY NOTHING FIRED. Every reading the fix needs already existed; none of them was
allowed to reach this board:

  1. `_festival_grounds_in_play` was read ONLY defensively -- their double attack
     (`op_double_attack_pending`) and the counter-stadium that switches it off
     (`switch_off_festival_lead`). The offensive half of the same card, that OUR
     Dipplin also gets the second wave, had no predicate at all. That is
     `_festival_double_wave`.
  2. `_doomed_ex_sac_pivot` -- retreat the doomed ex, hand a 1-prize body the
     front spot -- stands aside when the ex can still knock out
     (`not _active_can_ko_now`): cash the prize before it dies. Sound, and wrong
     here, because the relay takes THE SAME knockout.
  3. `_prize_denial_pivot` needs the opponent's knockout to CLOSE their count
     (`prize_count(active) >= op_prize`, i.e. 2 >= 4). It does not.
  4. `_tapu_sac_pivot` IS this sentence already -- retreat the doomed 2-prize ex,
     take the knockout with a 1-prize body -- but it is written for a Tapu Bulu
     that is ALREADY charged, and the body that was ready here needed the single
     Grass in hand.

THE FIX is `_tapu_sac_pivot` with the other attacker, gated on the stadium.
Outside Festival Grounds a Dipplin taking the front spot is a chip and
[[el-relevo-que-no-toma-premio-no-gana-el-puesto-activo]] already forbids it;
under the stadium the same body throws its attack twice. Requiring the KNOCKOUT
on the FIRST wave is what keeps the two apart: the relay never gives up the prize
the doomed ex was going to cash, it only refuses to pay two prizes for it.

AND THE COUNTER-STADIUM STOPS ARGUING WITH IT. `switch_off_festival_lead` plays
the Forest of Vitality at 26000 to switch off their double attack; on this turn
that would switch off OURS and throw the knockout away. `festival_lead_pays_us_now`
holds it back for exactly one turn -- the one where our Dipplin's wave is already
lethal. Whether the counter-stadium is worth FETCHING is still
`festival_lead_hostil`'s question and is untouched.

WHAT IS DELIBERATELY *NOT* CLAIMED. `_festival_second_wave_prizes` only counts a
second prize when EVERY body they can promote dies to the same wave. On the
record's board the 100 HP Thwackey survives an 80, so `prizes_today` stays at 1
and the pivot has to win on the price of the body in front, not on a prize the
opponent can decline. See `test_the_second_wave_does_not_count_a_prize_they_can_decline`.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "festival_lead_t6_the_stadium_arms_our_dipplin_too_step82.json")

DIPPLIN = m.Dipplin
APPLIN = m.Applin
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
BAYLEEF = m.Bayleef
FESTIVAL_GROUNDS = m.Festival_Grounds
GRASS = m.Basic_Grass_Energy
DO_THE_WAVE = m.DO_THE_WAVE_ATTACK_ID
MYRIAD = 120

THWACKEY = 90        # 100 HP: the one body on their bench that survives an 80


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _raw():
    return json.load(open(_FIXTURE, encoding="utf-8"))


def _obs(**mut):
    """The record's board at turnActionCount 2: the Applin is already a Dipplin
    on the bench and the one Grass is still in hand."""
    o = copy.deepcopy(_raw()["observation"])
    cur = o["current"]
    yo = cur["yourIndex"]
    if mut.get("without_stadium"):
        cur["stadium"] = []
    if mut.get("healthy_active"):
        # The same board with the ex NOT doomed: nothing to run from.
        cur["players"][yo]["active"][0]["hp"] = 210
    return o


def _decide(obs, prime=True):
    """Replays the turn from cold. `prime` feeds the menu that came before
    (the evolution) so the per-turn tracking sees the same turn the record saw."""
    if prime:
        m.agent(copy.deepcopy(_raw()["observacion_previa"]))
    return list(m.agent(obs))


def _bench(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]["bench"]


def _option(obs, i):
    return obs["select"]["option"][i]


# ---------------------------------------------------------------------------
# 1. The board is the one the story tells
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_board_of_the_record():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    me, rival = cur["players"][yo], cur["players"][1 - yo]

    # Festival Grounds on the table -- and it is THEIRS: the stadium is SHARED.
    assert [c["id"] for c in cur["stadium"]] == [FESTIVAL_GROUNDS]
    assert cur["stadium"][0]["playerIndex"] == 1 - yo

    # Our active is a Teal Mask Ogerpon ex at 10 HP carrying 3 Grass (retreat 1).
    act = me["active"][0]
    assert act["id"] == OGERPON and act["hp"] == 10 and act["maxHp"] == 210
    assert len(act["energies"]) == 3
    assert m.RETREAT_COST[OGERPON] == 1

    # The Dipplin the previous menu evolved is on the bench, with NO energy...
    assert [b["id"] for b in me["bench"]] == [TAPU, DIPPLIN, BAYLEEF, OGERPON]
    assert me["bench"][1]["energies"] == []
    # ...and the single Grass of the turn is still in hand, unattached.
    assert sum(1 for c in me["hand"] if c["id"] == GRASS) == 1
    assert cur["energyAttached"] is False

    # Their active is the 80 HP Dipplin the wave has to reach, over five bodies.
    assert rival["active"][0]["id"] == DIPPLIN
    assert rival["active"][0]["hp"] == 80
    assert len(rival["bench"]) == 5

    # And what the record actually did with the menu: Teal Dance on the BENCHED
    # Ogerpon ex (option 6), which spends the Grass on a body that is not
    # attacking this turn.
    assert _raw()["accion_del_registro"] == [6]
    assert _option(o, 6) == {"area": 5, "index": 3, "type": 10}


def test_do_the_wave_reaches_exactly_and_the_retreat_does_not_shrink_the_bench():
    """20 x 4 benched = 80 into 80 HP. The retreat SWAPS bodies, so the bench the
    wave counts is the same before and after
    ([[la-retirada-intercambia-cuerpos-la-banca-no-encoge]])."""
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    assert len(cur["players"][yo]["bench"]) == 4
    assert m.attack_table[DO_THE_WAVE].name == "Do the Wave"
    assert (m.attack_table[DO_THE_WAVE].damage or 0) == 0     # it is all scaling
    assert 20 * 4 == cur["players"][1 - yo]["active"][0]["hp"]


# ---------------------------------------------------------------------------
# 2. The reading: Festival Lead is ours too
# ---------------------------------------------------------------------------

def test_the_double_wave_is_read_for_our_dipplin_and_only_under_the_stadium():
    m.AGENT_STATE._festival_grounds_in_play = True
    assert m._festival_double_wave(DIPPLIN) is True
    assert m._festival_double_wave(OGERPON) is False       # only Dipplin has it
    m.AGENT_STATE._festival_grounds_in_play = False
    assert m._festival_double_wave(DIPPLIN) is False       # no stadium, no ability


def test_the_second_wave_does_not_count_a_prize_they_can_decline():
    """THEY choose who comes up, so the second wave is only a prize when EVERY
    candidate dies to it. The record's bench has a 100 HP Thwackey in it."""
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    op = m.to_observation_class(o).current.players[1 - yo]
    koed = op.active[0]

    assert THWACKEY in [b["id"] for b in cur["players"][1 - yo]["bench"]]
    assert m._festival_second_wave_prizes(op, 80, koed) == 0     # Thwackey survives
    # A wave that reaches the survivor takes the second prize.
    assert m._festival_second_wave_prizes(op, 100, koed) == 1
    # A wave that does no damage takes nothing, whatever the bench looks like.
    assert m._festival_second_wave_prizes(op, 0, koed) == 0

    # The body it knocked out is NOT a candidate to come up again, and with
    # nothing else left there is no second wave to project.
    o2 = _obs()
    o2["current"]["players"][1 - yo]["bench"] = []
    op2 = m.to_observation_class(o2).current.players[1 - yo]
    assert m._festival_second_wave_prizes(op2, 300, op2.active[0]) == 0


def test_the_second_wave_is_worth_nothing_without_the_stadium():
    o = _obs(without_stadium=True)
    _decide(o)
    assert m.AGENT_STATE._festival_grounds_in_play is False
    assert m._festival_double_wave(DIPPLIN) is False


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_grass_goes_to_the_dipplin_that_is_going_to_attack():
    o = _obs()
    choice = _decide(o)
    assert choice != _raw()["accion_del_registro"], (
        "el registro gasto la unica Grass en un Teal Dance sobre un cuerpo que "
        "no ataca este turno")
    opt = _option(o, choice[0])
    assert opt["type"] == 8, f"se esperaba un ATTACH, salio {opt}"
    assert _bench(o)[opt["inPlayIndex"]]["id"] == DIPPLIN, (
        "bajo Festival Grounds la Grass paga el Do the Wave que se lanza DOS "
        "veces, no una habilidad de banca")


def test_the_plan_hands_the_front_spot_to_the_dipplin():
    o = _obs()
    _decide(o)
    bench = _bench(o)
    idx = m.AGENT_STATE.plan.attacker - 1
    assert 0 <= idx < len(bench)
    assert bench[idx]["id"] == DIPPLIN
    assert m.AGENT_STATE.plan.energy is True      # it still needs the attachment


def test_the_doomed_ex_retreats_instead_of_cashing_the_prize_itself():
    """The menu after the attachment: the 10 HP ex can attack AND knock out, and
    it retreats anyway -- the prize is not given up, it changes hands."""
    o = _obs()
    _decide(o)                                   # ... the attachment
    after = _board_after_the_attachment()
    choice = list(m.agent(after))
    assert _option(after, choice[0])["type"] == 12, (
        "el ex condenado de 10 PV se queda delante a cobrar el premio que el "
        "relevo cobra igual, y la replica se lleva dos")


def test_and_then_the_dipplin_throws_the_wave():
    o = _obs()
    _decide(o)
    after = _board_after_the_attachment()
    m.agent(after)
    promoted = _board_after_the_retreat()
    choice = list(m.agent(promoted))
    opt = _option(promoted, choice[0])
    assert opt.get("attackId") == DO_THE_WAVE
    # ... and with the ex safe on the bench, the reply takes NOTHING.
    assert m.AGENT_STATE.turn_plan.op_prizes_after_ko == 0


def test_the_turn_still_reads_one_prize_and_two_conceded_before_the_swap():
    """The two halves the plan already measured on the record's own board: one
    prize today, TWO handed over on the reply. Nothing new is claimed about the
    first number -- the fix is about the second."""
    o = _obs()
    _decide(o)
    plan = m.AGENT_STATE.turn_plan
    assert plan.prizes_today == 1
    assert plan.op_prizes_after_ko == 2
    assert plan.op_wins_after_ko is False        # 2 of the 4 they still need


# ---------------------------------------------------------------------------
# 4. Controls: the rule needs the stadium AND a doomed body
# ---------------------------------------------------------------------------

def test_without_festival_grounds_the_turn_goes_back_to_the_record():
    """The control the fix hangs on. With no stadium the Dipplin's wave lands
    once, the relay is a chip, and the turn keeps its old shape."""
    o = _obs(without_stadium=True)
    choice = _decide(o)
    assert choice == _raw()["accion_del_registro"], (
        "sin el estadio no hay doble oleada: la Grass vuelve al Teal Dance")


def test_a_healthy_ex_does_not_hand_over_the_front_spot():
    """`active_ko_likely` is the other half: with the ex at full HP there is
    nothing to run from and the swap would only pay a retreat fee."""
    o = _obs(healthy_active=True)
    _decide(o)
    assert m.AGENT_STATE.plan.attacker == 0


def test_the_counter_stadium_waits_the_turn_the_wave_is_cashing():
    """The counter-stadium fires on their line and stands down on the turn our
    own Dipplin's wave is already lethal.

    IT MOVED, AND THAT IS THE POINT (user, registro_004 step 61). This used to
    read the GUARD of `switch_off_festival_lead`, and a guard on one rung
    forbids nothing: a ladder answers with the first rung that matches, so with
    that one silenced the Forest went down anyway at `enables_the_evolution_chain`
    (22000). The stand-down is now `their_stadium_is_paying_us_today` at the TOP
    of the ladder, so the assertion is about the ladder's ANSWER -- which is what
    the sentence was always about -- and not about which rung holds the clause.
    """
    names = [r.name for r in m._RULES_FOREST_PLAY]
    assert "switch_off_festival_lead" in names
    assert "their_stadium_is_paying_us_today" in names
    # And it is a VETO ABOVE every reason to play the card, not a clause inside
    # one of them: every rung that could play the Forest comes after it.
    assert (names.index("their_stadium_is_paying_us_today")
            < min(names.index(n) for n in ("switch_off_festival_lead",
                                           "enables_the_evolution_chain",
                                           "replace_the_opponent_stadium",
                                           "early_development")))

    # The two rungs read three fields of the ctx between them; a stand-in
    # carries them and keeps the test out of DecisionContext's 60-odd
    # required arguments.
    def ctx(hostile, paying):
        return SimpleNamespace(festival_lead_hostil=hostile,
                               festival_lead_pays_us_now=paying,
                               we_go_first=False,
                               state=SimpleNamespace(turn=6))

    veto = next(r for r in m._RULES_FOREST_PLAY
                if r.name == "their_stadium_is_paying_us_today")
    counter = next(r for r in m._RULES_FOREST_PLAY
                   if r.name == "switch_off_festival_lead")

    # Their line, our wave not cashing: the counter-stadium is played.
    assert veto.when(ctx(True, False)) is False
    assert counter.when(ctx(True, False)) is True
    # The turn it cashes: the veto answers first and the Forest stays in hand.
    assert veto.when(ctx(True, True)) is True
    assert m._score_forest_of_vitality_play(ctx(True, True)) == m.SCORE_VETO
    # It is not a matchup switch: with no hostile line the counter was already off.
    assert counter.when(ctx(False, False)) is False


def test_the_new_reading_travels_in_the_ctx_and_defaults_to_off():
    """The Forest rules read the ctx, so the field has to be there -- and off by
    default, because the tests that build a DecisionContext by hand know nothing
    about this stadium."""
    fields = m.DecisionContext.__dataclass_fields__
    assert "festival_lead_pays_us_now" in fields
    assert fields["festival_lead_pays_us_now"].default is False
    # The sibling it qualifies is untouched: fetching the counter-stadium is
    # still decided by whether THEIR line exists.
    assert fields["festival_lead_hostil"].default is False


# ---------------------------------------------------------------------------
# helpers: the boards the record never reached
# ---------------------------------------------------------------------------

def _board_after_the_attachment():
    """The record's board with the Grass on the benched Dipplin instead of on
    the Ogerpon ex: attack / retreat / end."""
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    me = cur["players"][yo]
    grass = next(c for c in me["hand"] if c["id"] == GRASS)
    me["hand"] = [c for c in me["hand"] if c["serial"] != grass["serial"]]
    me["handCount"] = len(me["hand"])
    dipplin = me["bench"][1]
    assert dipplin["id"] == DIPPLIN
    dipplin["energies"] = [1]
    dipplin["energyCards"] = [grass]
    cur["energyAttached"] = True
    cur["turnActionCount"] += 1
    o["select"]["option"] = [
        {"attackId": MYRIAD, "type": 13},
        {"type": 12},
        {"type": 14},
    ]
    return o


def _board_after_the_retreat():
    """... and once the fee is paid: Dipplin in front, the 10 HP ex on the bench
    (where its Tera makes it untouchable)."""
    o = _board_after_the_attachment()
    cur = o["current"]
    yo = cur["yourIndex"]
    me = cur["players"][yo]
    ex = me["active"][0]
    me["active"] = [me["bench"].pop(1)]
    ex["energies"] = ex["energies"][:2]
    ex["energyCards"] = ex["energyCards"][:2]
    me["bench"].append(ex)
    cur["retreated"] = True
    cur["turnActionCount"] += 1
    o["select"]["option"] = [
        {"attackId": DO_THE_WAVE, "type": 13},
        {"type": 14},
    ]
    return o
