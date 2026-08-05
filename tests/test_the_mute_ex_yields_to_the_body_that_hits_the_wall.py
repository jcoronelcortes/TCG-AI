"""Against a wall, surviving is worth nothing if the survivor cannot touch it.

Scenario (`records/registro_008_pasos_058_hasta_079.json`, step 78, turn 8,
LOST vs Crustle -- episode 89679306). We retreat the active Chikorita and the
promotion menu opens:

    US (6 prizes)                             RIVAL (6 prizes)
    active **Chikorita 70**, retreating       active  **Crustle 170**/170, 2 en.
    bench  **Dipplin 80, 2 effective**        bench   Crustle 170, Crustle 150,
           Meganium 160, 0 en.                        Crustle 150
           Meowth ex 170, 0 en.
           **Teal Mask Ogerpon ex 210, 4 eff.**
           Meowth ex 170, 0 en.
    hand   Unfair Stamp, Teal Mask Ogerpon ex, 1 Grass (attachment already spent)

The agent brought up **Teal Mask Ogerpon ex**. Against this active it is a MUTE
body: *Mysterious Rock Inn* cancels the damage of our Pokemon ex, so its four
energies project 210 and land **0**. The only body that touches the wall is
**Dipplin**: *Do the Wave* does **100** on a Crustle of 170 HP -- it leaves it in
range of the Meganium/Tapu Bulu that finish it -- at the cost of one prize,
because the Crustle hits for **120** and the Dipplin has 80 HP.

Cause -- two rules of the same size, one after the other. The wall rule already
said the right thing: the unblocked non-ex attacker takes **+6000**
(`_crus_nonex_attacker`). The terminal survival band then took **-6000** straight
back off it (`PROMO_DOOMED_PENALTY`), because the Dipplin dies and the Ogerpon
does not. Net: Dipplin 715, the mute ex 3515 -- it had also collected the +3000
for being *an ex wall with energy*. The turn was given away and, two hits later,
so were two prizes.

The survival criterion was born against Archaludon (registro_005 step 64), where
EVERY candidate could hit back and the only question was who takes the punch.
Against a wall that premise breaks: the body that endures is precisely the one
the wall has switched off. "One prize for 100 damage" is not a bad trade there --
it is the only line that moves the game.

Fix: `_promo_wall_relief` (main.py, next to `_promo_survivors`). With an
ex-immune or ability-immune active, if **no survivor damages it** and some
doomed candidate **does**, the doomed penalty does not apply to the bodies that
hit. It is deliberately narrow:

  * if any body both ENDURES and HITS, the penalty stands untouched and that
    body still rules (control D below);
  * if nobody hits the wall, nothing changes: the ex wall is promoted as before
    (control B);
  * without the wall the rule cannot even open (control A);
  * `SelectContext.SWITCH` only -- our voluntary retreat, on our turn and right
    before attacking, so "it damages the wall" is a fact and not a forecast. The
    FORCED promotion after a KO (`TO_ACTIVE`) is resolved on the OPPONENT's turn
    and keeps its own criterion (registro_013 step 71,
    `test_promote_meganium_against_the_ex_immune_wall`).

Golden corpus: three flips, all the same pattern against the same wall and all
in the same direction -- registro_008 step 78 (this one), registro_010 step 88
and registro_012 step 101, where a Meowth ex with no energy (2 prizes, 0 damage)
was promoted ahead of a Dipplin that did 80 to the Crustle.

Self-play, candidate against the same bot with the rule ON and OFF:

    crustle_kangaskhan  n=6000  **68.2% [67.0-69.3]  vs  65.3% [64.1-66.5]**
                                +2.9 points, the intervals do not overlap;
                                prize differential +0.86 vs +0.71
    cornerstone_cubchoo n=3000    87.5%  vs  87.0%   (+0.5, noise)
    dragapult           n=3000    96.8%  vs  96.7%   (+0.1, noise)
    hops                n=3000    97.8%  vs  97.4%   (+0.4, noise)
    alakazam            n=3000    99.4%  vs  99.3%   (+0.1, noise)

The signal lives where the rule fires -- the ex-immune wall -- and no matchup
without one moves, which is what the SWITCH + "every survivor is mute" guards
promise.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_t8_the_mute_ex_yields_to_the_dipplin_step78.json")

DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
CHIKORITA = m.Chikorita
CRUSTLE = m.Crustle_Grass


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _opp(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _promoted(obs, action):
    return _mine(obs)["bench"][obs["select"]["option"][action[0]]["index"]]


def _bench_index(obs, card_id):
    return next(i for i, b in enumerate(_mine(obs)["bench"])
                if b is not None and b["id"] == card_id)


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_promotion_of_our_own_retreat():
    o = _obs()
    # SWITCH (3), not the forced promotion after a KO (4): our active is still
    # on the board, on our turn, and it is the one leaving.
    assert o["select"]["context"] == 3
    assert _mine(o)["active"][0]["id"] == CHIKORITA
    assert o["current"]["retreated"] is True


def test_the_rival_active_is_the_wall_that_mutes_our_ex():
    o = _obs()
    act = _opp(o)["active"][0]
    assert act["id"] == CRUSTLE and act["hp"] == 170
    assert CRUSTLE in m.EX_IMMUNE_IDS
    assert OGERPON in m.OUR_EX_IDS


def test_the_dipplin_hits_the_wall_and_dies_and_the_ex_neither():
    """The whole trade in four numbers, read with the agent's own calculators."""
    from cg.api import to_observation_class

    o = _obs()
    m.agent(_obs())            # it leaves the global state in sync with the board
    obs = to_observation_class(o)
    mine = obs.current.players[obs.current.yourIndex]
    wall = obs.current.players[1 - obs.current.yourIndex].active[0]
    bench = [b for b in mine.bench if b is not None]
    total_grass = sum(len(p.energies) for p in [mine.active[0]] + bench)

    def hits(pk):
        e = len(pk.energies) * m._grass_mult()
        base = m._attacker_base_damage(pk.id, wall, e, grass_scale=total_grass,
                                       teal_self_energy=e,
                                       bench_count=max(0, len(bench) - 1))
        if base <= 0:
            return 0
        return m._our_effective_damage(pk, wall, base,
                                       m.AGENT_STATE.meganium_in_play, False)

    dipplin = next(b for b in bench if b.id == DIPPLIN)
    ogerpon = next(b for b in bench if b.id == OGERPON)

    assert hits(dipplin) > 0                       # Do the Wave reaches the wall
    assert hits(ogerpon) == 0                      # Mysterious Rock Inn cancels it
    assert m._op_active_attack_damage_to(wall, dipplin) >= dipplin.hp   # it dies
    assert m._op_active_attack_damage_to(wall, ogerpon) < ogerpon.hp    # it endures


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_dipplin_that_hits_not_the_ex_that_endures():
    o = _obs()
    promoted = _promoted(o, m.agent(_obs()))
    assert promoted["id"] == DIPPLIN, (
        "ante un muro que anula a nuestros ex hay que subir al cuerpo que SI le "
        "hace dano, aunque muera: el ex que aguanta no le quita ni un PV y "
        "regala dos premios cuando caiga")


def test_it_brings_up_neither_the_mute_ex_nor_the_meowth():
    o = _obs()
    action = m.agent(_obs())
    assert action != [_bench_index(o, OGERPON)]
    assert action != [_bench_index(o, MEOWTH)]


# ---------------------------------------------------------------------------
# 3. The limits of the rule
# ---------------------------------------------------------------------------

def test_a_without_the_wall_the_promotion_keeps_its_criterion():
    """Control: with an active our ex CAN damage, the exemption never opens and
    the charged Ogerpon ex goes back to being the right promotion."""
    o = _obs()
    _opp(o)["active"][0]["id"] = m.Mega_Kangaskhan_ex
    assert _promoted(o, m.agent(o))["id"] == OGERPON


def test_b_if_nobody_hits_the_wall_the_ex_wall_is_still_promoted():
    """Control: with the Dipplin's energy removed nobody touches the Crustle, so
    there is nothing to exempt and the ex with energy takes the spot as before."""
    o = _obs()
    dipplin = _mine(o)["bench"][_bench_index(o, DIPPLIN)]
    dipplin["energies"] = []
    dipplin["energyCards"] = []
    assert _promoted(o, m.agent(o))["id"] != DIPPLIN


def test_d_a_survivor_that_also_hits_keeps_the_penalty_shut():
    """Control: the exemption is for "every survivor is mute", not for "somebody
    dies". With a Meganium at 4 effective -- it endures the 120 AND does 140 to
    the wall -- there IS a survivor that hits, the doomed penalty stands on the
    Dipplin and the promotion goes back to the previous logic."""
    o = _obs()
    meganium = _mine(o)["bench"][_bench_index(o, MEGANIUM)]
    meganium["energies"] = [1, 1, 1, 1]
    meganium["energyCards"] = [{"id": m.Basic_Grass_Energy, "playerIndex": 0,
                                "serial": 90 + i} for i in range(2)]
    assert _promoted(o, m.agent(o))["id"] != DIPPLIN
