"""Cubchoo ↔ immune wall collision: the anti-Cubchoo veto killed the pivot to the wall.

Scenario (autopsy `cornerstone_cubchoo`, Jul 2026; a fixture captured from
self-play, turn 22):

    US                                        RIVAL
    active  Teal Mask Ogerpon ex, 6 energies  active  Cornerstone Mask Ogerpon ex
            (retreat cost 1)                          210/210
    bench   Hydrapple ex 4e, Ogerpon ex 4e,
            Meowth ex, Meganium, **Tapu Bulu 4e**

*Cornerstone Stance* cancels the damage of attacks from Pokémon **with an Ability**:
Teal Mask Ogerpon ex (Teal Dance) does **0** to it. The only body on the bench that
touches it is **Tapu Bulu** — no Ability, no ex rule box — and it is **charged to 4**,
exactly its *Wood Hammer* cost (220, which knocks out the 210 wall). The active retreats
for **1**. The play is obvious: retreat and bring up Tapu.

The agent **attacked for 0** and closed the turn.

Cause — a **collision between two matchup rules**, the class of bug the matchup
matrix was built to detect. The deck is mixed (Cornerstone + Cubchoo), so
`op_is_cubchoo_deck` is True and it fired the anti-Cubchoo veto of the
RETREAT branch (the memory "Anti-Cubchoo: no retreat-pivot, keep the energy"): against a
deck that discards energy, retreating an active with energy on it destroys invested
resource, so we PASS. That veto already had four exceptions
(`_cubchoo_lock_stuck`, `_cc_cashes_dead_body`, `_suicide_swap_win_promote`,
`active_ko_likely`) but **not** the wall's.

And the veto's argument does not apply here: the energy of a body that does **zero**
to the rival active is not invested resource, it is **dead** resource — and retreating is
the only route to turn it into damage.

Fix: `_ex_stuck_promo_ready` exempts it from the veto. That flag already distinguishes the two
immunities (`op_has_ex_immune_active` + our ex, or `op_has_ability_immune_active`
+ our bodies with an Ability) and on top of that requires an attacker on the bench
that DOES hit the wall (`_dmg_vs_wall > 0`), so it does not open the door to bare
pivots.

Measurement (250 instrumented games): with the wall in front, a Tapu ≥4 on the bench and
the retreat LEGAL, we brought up Tapu only **13.7%** of the time in prize
losses (36% in the wins). The same scenario against Crustle — an equivalent wall
**without** Cubchoo in the deck — gave **82.6-100%**, which is what put the
focus on the collision. In 167 of 169 of those menus the active was Teal Mask Ogerpon
ex and the turn closed by attacking for 0 (67 times).

Differential gate n=1000: **cornerstone_cubchoo +5.4 points** (77.6% vs 72.2%,
≈2.8σ). Triple validation: mirror 51.7% [48.6-54.8] (no general regression),
crustle_kangaskhan −1.1, iron_thorns +1.5, comfey −1.8 (all noise). When it was
measured, `cornerstone_cubchoo` was the ONLY deck in `deck/opponents/` with
Cubchoo, so the `op_is_cubchoo_deck` gate could not fire anywhere else and the
exemption could not leak.

THAT IS NO LONGER TRUE, and whoever re-measures this rule has to know it:
`crustle_cubchoo_spheal.csv` (harvested from episode 91172810, the deck of
`records/registro_007_pasos_040_hasta_050.json`) carries two Cubchoo of its own,
alongside a Crustle wall and the Spheal that sleeps our active. The gate fires
against it too. The numbers above were taken before that deck existed and were
never re-run against it.
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
            / "cornerstone_cubchoo_sube_tapu_no_ataca_por_0.json")

TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
CORNERSTONE = 117               # Cornerstone Mask Ogerpon ex (ABILITY_IMMUNE_IDS)


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


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    if "energia_tapu" in mut:
        for b in o["current"]["players"][yo]["bench"]:
            if b and b["id"] == TAPU:
                b["energies"] = b["energies"][:mut["energia_tapu"]]
    return o


def _tipo(obs, choice):
    return obs["select"]["option"][choice[0]]["type"]


def _scores(obs):
    """The score of each menu option, spying on `_debug_log_decision`."""
    visto = {}
    orig = m._debug_log_decision

    def spy(context, select, scores, obs_, my_index, top_n=3):
        visto["scores"] = list(scores)
        return orig(context, select, scores, obs_, my_index, top_n)

    _restore_spy = instalar("_debug_log_decision", spy)
    prev = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    try:
        m.agent(obs)
    finally:
        m._debug_log_decision = orig
        m.DEBUG_DECISIONS = prev
    return visto["scores"]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_wall_scenario():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    opponent = o["current"]["players"][1 - yo]

    assert opponent["active"][0]["id"] == CORNERSTONE
    assert mio["active"][0]["id"] == OGERPON              # it has an Ability -> it does 0
    assert OGERPON in m.OUR_ABILITY_IDS
    assert CORNERSTONE in m.ABILITY_IMMUNE_IDS
    # Tapu Bulu: no Ability and no ex rule box -> it DOES hit, and it is READY.
    tapu = next(b for b in mio["bench"] if b and b["id"] == TAPU)
    assert len(tapu["energies"]) >= m.ATTACK_ENERGY_REQ[TAPU]
    assert TAPU not in m.OUR_ABILITY_IDS and TAPU not in m.OUR_EX_IDS
    # ...and the active's retreat is legal and cheap.
    assert m.RETREAT_COST[OGERPON] == 1
    tipos = {opt["type"] for opt in o["select"]["option"]}
    assert int(m.OptionType.RETREAT) in tipos
    assert int(m.OptionType.ATTACK) in tipos


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_retreats_to_bring_up_tapu_instead_of_attacking_for_zero():
    obs = _obs()
    assert _tipo(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_the_anti_cubchoo_veto_no_longer_kills_the_retreat():
    """The failure was a VETO (score −1), not a defeat on points."""
    obs = _obs()
    scores = _scores(obs)
    idx_retreat = next(i for i, opt in enumerate(obs["select"]["option"])
                   if opt["type"] == int(m.OptionType.RETREAT))
    idx_attack = next(i for i, opt in enumerate(obs["select"]["option"])
                   if opt["type"] == int(m.OptionType.ATTACK))
    assert scores[idx_retreat] > 0, scores
    assert scores[idx_retreat] > scores[idx_attack], scores


def _flags_de_agent(obs, names):
    """Reads LOCAL variables of `agent()` on return.

    `op_is_cubchoo_deck` (like `op_kang_ko_target`) is local, not global: reading it
    with `m.<flag>` gives the value left by the test's reset, not the decision's.
    """
    capt = {}

    def tr(frame, ev, arg):
        if frame.f_code.co_name != "agent":
            return None
        if ev == "return":
            for k in names:
                if k in frame.f_locals:
                    capt[k] = frame.f_locals[k]
        return tr

    # Put back whatever was tracing BEFORE us, which under `--cov-context=test`
    # is coverage's own tracer. A bare `settrace(None)` uninstalls it for the REST
    # OF THE PROCESS: line coverage recovers on the next test, but the dynamic
    # CONTEXT does not, so every test that runs after this file is recorded
    # under the empty context. Measured: 225 contexts for 1 843 tests, 11 test
    # files of 153, which silently broke the line->test map that
    # utils/gate_mutation.py selects its tests with.
    _previous_tracer = sys.gettrace()
    sys.settrace(tr)
    try:
        m.agent(obs)
    finally:
        sys.settrace(_previous_tracer)
    return capt


def test_the_cubchoo_matchup_really_is_switched_on():
    """If `op_is_cubchoo_deck` were False the veto would not exist and the tests
    above would pass without testing the exemption. The Cubchoo is detected by the
    rival DISCARD, which is where it is in this fixture."""
    obs = _obs()
    yo = obs["current"]["yourIndex"]
    discard = obs["current"]["players"][1 - yo]["discard"]
    assert any(m.card_table[c["id"]].name.startswith("Cubchoo") for c in discard)

    flags = _flags_de_agent(obs, ("op_is_cubchoo_deck", "_ex_stuck_promo_ready"))
    assert flags.get("op_is_cubchoo_deck") is True, flags
    assert flags.get("_ex_stuck_promo_ready") is True, flags


# ---------------------------------------------------------------------------
# 3. What is NOT broken: the exemption requires a REAL attacker against the wall
# ---------------------------------------------------------------------------

def test_without_a_charged_tapu_the_anti_cubchoo_veto_stands():
    """With the Tapu below its attack cost there is no pivot to the wall to
    justify, so the anti-Cubchoo behaviour returns: keep the energy."""
    obs = _obs(energia_tapu=1)
    scores = _scores(obs)
    idx_retreat = next(i for i, opt in enumerate(obs["select"]["option"])
                   if opt["type"] == int(m.OptionType.RETREAT))
    assert scores[idx_retreat] <= 0, scores
    assert _tipo(obs, m.agent(obs)) != int(m.OptionType.RETREAT)
