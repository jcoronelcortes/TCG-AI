"""The Cubchoo lock muted a body whose energy was already dead, and we passed.

Scenario (`records/registro_007_pasos_040_hasta_050.json`, episode 91172810 vs
`crustle_cubchoo_spheal`, turn 7, LOST; the fixture is the last menu of that turn):

    US                                     RIVAL
    active  Meowth ex, 3 Grass             active  Cubchoo 70/70, 3 energies
            muted by *Snotted Up*
            (retreat cost 1)
    bench   Teal Mask Ogerpon ex **3e**,
            Teal Mask Ogerpon ex 2e,
            Dipplin 0e

*Snotted Up* (Cubchoo, 506) leaves the Defending Pokemon unable to attack on our
turn, so the menu has **no ATTACK option**. The line is there anyway: retreat the
Meowth for 1 and promote the Ogerpon ex charged to 3 — Myriad Leaf Shower counts
the energy on BOTH actives (3 + 3), 180 damage against a 70 HP Cubchoo. A prize,
and their only attacker off the board.

The agent played its whole turn (Teal Dance, attachments, supporter, Applin ->
Dipplin) and closed with **END**. Replaying the record, the RETREAT option scored
`SCORE_VETO` while `_bdg_retreat_ko` was already True: the retreat was not losing
on points, it was **vetoed**.

Cause — the anti-Cubchoo conservation veto
([[anti-cubchoo-no-retirada-pivote-conservar-energia]], registro_004 p47: against
a deck that forces a retreat every turn, a retreat that DISCARDS energy bleeds the
scarcest resource, so we PASS). Its exemption for exactly this board,
`_cubchoo_lock_stuck` ("muted active + a benched attacker that knocks out"), was
gated on `_my_active_pk.id == Hydrapple_ex` — the body it happened to be written
for (registro_008 step 82) — so a muted **Meowth ex** never reached it.

Fix: the gate is *whose energy is dead*, not *is it a Hydrapple*, and it lives in
its OWN flag — `_cubchoo_mute_cashes_prize`, for the bodies in
`NON_ATTACKER_ENERGY_WASTE_IDS` (Meowth ex, Fezandipiti ex: hand engines that do
not attack at all, so every energy on them is dead the moment it lands). It is not
folded into `_cubchoo_lock_stuck` because that flag has two other consumers — the
6000 tier of the RETREAT branch and the 24000 "charge the active to pay its
retreat" of `energy_score` — and widening those as well TRIPLES the blast radius
for no gain (see the measurement below). The charged Teal Mask Ogerpon ex of p47
stays out of THIS set on purpose: its Myriad Leaf Shower scales with its own
energy, those Grass are investment.

LATER (user, registro_010 p81): the same exemption read one question further out.
"Whose energy is dead" is still not the whole answer, because against a lock that
mutes whatever is in front the fee that decides is the ROTATION the lock will
charge next turn. `_cubchoo_mute_rotates` exempts when the cheapest body that
cashes the prize is no dearer to rotate than the one leaving — which is what
`test_a_charged_ogerpon_in_front_now_rotates_with_its_twin` below turned out to
be about, and which still keeps the PASS of p47, where the only body that knocks
out is a Hydrapple ex at retreat 3. See
`tests/test_the_lock_charges_the_rotation_not_the_retreat.py`.

Flip diff over the golden corpus: 9 flips, all END -> RETREAT, all in this same
episode — turns 7, 9, 11, 13, 15, 17, 19, 21 and 23. The board was frozen for
NINE consecutive turns with the same muted Meowth in front, the same Ogerpon ready
on the bench and the same 70 HP Cubchoo, and the turn was handed over every time.
No other record moved.

Measurement — and WHY the winrate is not the arbiter here
([[matchpoint-el-gate-no-arbitra-mide-la-frecuencia]]). `utils/shadow.py` over 300
games vs `crustle_cubchoo_spheal` (40 759 decisions): **4 flips, 0.010%** — one
decision in ten thousand — and all four are the same one, END -> RETREAT with a
lethal body already on the bench. At that frequency no reasonable n of self-play
separates the signal from the shuffle, and the differential gate reads exactly
what it should read for a change it cannot see: n=3000 vs crustle_cubchoo_spheal
**+0.3** (87.1% vs 86.8%, prizes +3.61 vs +3.58), n=3000 vs cornerstone_cubchoo
**−1.3** (87.3% vs 88.6%), mirror n=1000 51.1% [48.0-54.2], control
crustle_kangaskhan (no Cubchoo, so the gate cannot fire) +0.2. The verdict comes
from auditing the flips, not from those numbers. The variant that also widened
`_cubchoo_lock_stuck` measured 13 flips (0.031%) over the same 300 games, the extra
ones all attachments — three times the radius, same unmeasurable winrate.
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
from patching import instalar

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "cubchoo_mudo_meowth_ex_retira_y_ogerpon_noquea.json")

MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
CUBCHOO = m.Cubchoo


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
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
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs(active_id=None, ogerpon_energies=None):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    if active_id is not None:
        mine["active"][0]["id"] = active_id
    if ogerpon_energies is not None:
        for b in mine["bench"]:
            if b and b["id"] == OGERPON:
                b["energies"] = b["energies"][:ogerpon_energies]
                b["energyCards"] = b["energyCards"][:ogerpon_energies]
    return o


def _type(obs, choice):
    return obs["select"]["option"][choice[0]]["type"]


def _index_retreat(obs):
    return next(i for i, opt in enumerate(obs["select"]["option"])
                if opt["type"] == int(m.OptionType.RETREAT))


def _scores(obs):
    """The score of each menu option, spying on `_debug_log_decision`."""
    seen = {}
    orig = m._debug_log_decision

    def spy(context, select, scores, obs_, my_index, top_n=3):
        seen["scores"] = list(scores)
        return orig(context, select, scores, obs_, my_index, top_n)

    instalar("_debug_log_decision", spy)
    prev = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    try:
        m.agent(obs)
    finally:
        m._debug_log_decision = orig
        m.DEBUG_DECISIONS = prev
    return seen["scores"]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_muted_meowth_with_a_lethal_ogerpon_waiting():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine = o["current"]["players"][yo]
    opponent = o["current"]["players"][1 - yo]

    # The Cubchoo lock: their active is the Cubchoo and ours has NO attack option.
    assert opponent["active"][0]["id"] == CUBCHOO
    types = {opt["type"] for opt in o["select"]["option"]}
    assert int(m.OptionType.ATTACK) not in types
    assert int(m.OptionType.RETREAT) in types

    # Our active is a Meowth ex carrying energy it can never turn into damage.
    assert mine["active"][0]["id"] == MEOWTH
    assert MEOWTH in m.NON_ATTACKER_ENERGY_WASTE_IDS
    assert m.RETREAT_COST[MEOWTH] == 1
    assert len(mine["active"][0]["energies"]) > m.RETREAT_COST[MEOWTH]  # there IS a surplus

    # ...and the Ogerpon on the bench is READY and lethal against the 70 HP Cubchoo.
    ogerpon = next(b for b in mine["bench"] if b and b["id"] == OGERPON
                   and len(b["energies"]) >= m.ATTACK_ENERGY_REQ[OGERPON])
    assert opponent["active"][0]["hp"] == 70
    assert len(ogerpon["energies"]) >= m.ATTACK_ENERGY_REQ[OGERPON]


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_retreats_the_muted_meowth_instead_of_ending_the_turn():
    obs = _obs()
    assert _type(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_the_anti_cubchoo_veto_no_longer_kills_the_retreat():
    """The failure was a VETO (score -1), not a defeat on points: the END scores 0
    and every other option in that menu was already vetoed."""
    obs = _obs()
    scores = _scores(obs)
    assert scores[_index_retreat(obs)] > 0, scores


# ---------------------------------------------------------------------------
# 3. What is NOT broken: the exemption is about DEAD energy, not about the lock
# ---------------------------------------------------------------------------

def test_a_charged_ogerpon_in_front_now_rotates_with_its_twin():
    """THIS CONTROL WAS A STAND-IN THAT DID NOT STAND IN (user, registro_010 p81).

    It was written as "the PASS of registro_004 p47 survives", by taking THIS
    fixture and swapping the Meowth ex in front for a Teal Mask Ogerpon ex. The
    swap does not reproduce p47, because what separates the two boards is not the
    species in front -- p47's active is also a charged Teal Mask Ogerpon ex --
    but the body the retreat PROMOTES:

      * p47: the only bench body that knocks the Cubchoo out is a Hydrapple ex,
        retreat cost 3. Promoting it jams our most expensive body into a lock
        that mutes whatever is in front, and next turn's forced rotation costs
        three more energy. That PASS is right, it still stands, and it is pinned
        on the REAL board by
        `test_main_regressions_5.py::test_step47_vs_cubchoo_does_not_waste_energy_retreating`
        (fixture `cubchoo_step47_no_energy_wasting_retreat.json`) and by the
        control below.
      * this board once the swap is made: the bench holds a SECOND Teal Mask
        Ogerpon ex charged to 3, retreat cost 1, the same fee as the body
        leaving. That is a twin rotation -- one Grass for a prize today, the same
        fee to swap back tomorrow -- and it is the board of registro_010 p81, not
        the board of p47.

    So the swap produced the case the new reading is about. See
    `_cubchoo_mute_rotates` in main.py.
    """
    obs = _obs(active_id=OGERPON)
    scores = _scores(obs)
    assert scores[_index_retreat(obs)] > 0, scores
    assert _type(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_the_veto_stands_when_only_an_expensive_body_cashes_the_prize():
    """The control the one above was meant to be, on the geometry that decides.

    Same board, with the two benched Teal Mask Ogerpon ex turned into Hydrapple
    ex: they still knock the 70 HP Cubchoo out (Syrup Storm scales with the Grass
    on the whole field), but rotating one of them out again costs 3 where the
    body in front costs 1. That is p47's shape, and there the conservation veto
    is still the right answer: we PASS.
    """
    obs = _obs(active_id=OGERPON)
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in mine["bench"]:
        if b and b["id"] == OGERPON:
            b["id"] = m.Hydrapple_ex
            b["hp"] = b["maxHp"] = 330
    assert m.RETREAT_COST[m.Hydrapple_ex] > m.RETREAT_COST[OGERPON]
    scores = _scores(obs)
    assert scores[_index_retreat(obs)] <= 0, scores
    assert _type(obs, m.agent(obs)) != int(m.OptionType.RETREAT)


def test_without_a_lethal_body_on_the_bench_the_veto_stands():
    """The exemption demands a benched attacker that KNOCKS OUT, not a bare pivot:
    with the Ogerpon below its attack cost we keep the energy."""
    obs = _obs(ogerpon_energies=1)
    scores = _scores(obs)
    assert scores[_index_retreat(obs)] <= 0, scores
    assert _type(obs, m.agent(obs)) != int(m.OptionType.RETREAT)


def test_the_cubchoo_matchup_really_is_switched_on():
    """If `op_is_cubchoo_deck` were False there would be no veto to exempt and the
    tests above would pass without testing anything."""
    obs = _obs()
    capt = {}

    def tr(frame, ev, arg):
        if frame.f_code.co_name != "agent":
            return None
        if ev == "return":
            for k in ("op_is_cubchoo_deck", "_cubchoo_mute_cashes_prize", "can_attack"):
                if k in frame.f_locals:
                    capt[k] = frame.f_locals[k]
        return tr

    # Restore whatever was tracing BEFORE us: a bare `settrace(None)` uninstalls
    # coverage's tracer for the rest of the process (see the note in
    # test_cornerstone_cubchoo_brings_up_tapu.py).
    previous_tracer = sys.gettrace()
    sys.settrace(tr)
    try:
        m.agent(obs)
    finally:
        sys.settrace(previous_tracer)

    assert capt.get("op_is_cubchoo_deck") is True, capt
    assert capt.get("can_attack") is False, capt
    assert capt.get("_cubchoo_mute_cashes_prize") is True, capt
