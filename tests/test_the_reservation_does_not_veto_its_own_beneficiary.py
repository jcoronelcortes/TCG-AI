"""The Grass was being saved FOR the active, against the active's own dance.

Same board as `tests/test_the_dance_goes_before_the_ultra_ball.py`
(`records/registro_004_pasos_038_hasta_059.json` step 39, turn 4 vs Marnie's
Grimmsnarl ex -- episode 92486283), read one layer further down.

    active Teal Mask Ogerpon ex 210/210, ONE Grass (Myriad Leaf Shower needs 3)
    bench  Bayleef 80/110
    hand   Lana's Aid, ONE Basic Grass, Meganium, Boss's Orders, Ultra Ball

Three rules agreed the Grass belonged to that active, and between them it could
not get there:

    [1] Grass -> active (manual)    score    -1   vetoed: "Teal Dance first"
    [5] TEAL DANCE (active)         score  7500   "the active needs the Grass
                                                   and the hand holds one --
                                                   do not spend it dancing"

The second sentence is the reserve band of `ptcg/turn/options/ability.py`, and
it is right about a BENCHED Ogerpon: that dance really would eat the Grass the
active is waiting for. Teal Dance attaches to ITSELF, so on the ACTIVE it is
not competing with the reservation -- it *is* the reservation, honoured, with a
card drawn on top. The branch had an opening-turn carve-out that said exactly
this for `o.area == ACTIVE` and only on turn 1; from turn 2 on, the body every
rule agreed should get the Grass was the one body forbidden from taking it.

WHAT IT COST. 7500 is under the tier-0 ceiling, so the ability lost the ORDER
to anything above it -- and on this board that was an Ultra Ball, which paid its
cost with the very Grass. The two halves are one failure and they are fixed in
two places: this guard (the Grass reaches the body) and the ordering rule in
`ptcg/turn/finalize.py` (the search does not eat it first).

THE FIX IS THE GUARD ITS OWN SIBLING ALREADY HAD. Ripening Charge's reserve
branch, forty lines below, reads `_active_needs_energy and not _enough_for_both
and o.area != AreaType.ACTIVE`. Teal Dance's was missing the third clause. It
subsumes the opening-turn carve-out, which is the same sentence gated on turn 1.

MEASURED, because the ACTIVE dance now lands at 31000 and that is ABOVE bands
with a named reason to want the Grass elsewhere (the Applin charge of the
Dipplin/Hydrapple line, 30000). Seeded matrix, 87 real-meta decks x 400 games
per arm, both arms replaying the SAME games, run over TWO independent seed
blocks: +15 and +29 net wins out of 34,775 (+0.10 and +0.21 meta-weighted
points). Twelve decks improve in BOTH blocks and one falls in both, and the
consistent gains are the `crustle_wall` family -- the matchup the band was
feared to damage, and the weakest one the agent has.

Golden corpus: four flips, all `ATTACH->Applin/Dipplin` -> `ABILITY Teal Mask
Ogerpon ex`.
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
            / "marnie_the_dance_goes_before_the_ultra_ball_step39.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
ULTRA_BALL = m.Ultra_Ball
RESERVE_BAND = 7500
# The floor `finalize.py` asks an ability to clear before it may compete in the
# ENERGY tier. Below it, a charging ability is saying "today I am a reserve".
REAL_PLAY_FLOOR = 29000


@pytest.fixture(autouse=True)
def reset_main_state():
    import tests.golden_corpus as gc
    gc.reset_agent(m)
    yield
    gc.reset_agent(m)


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _board(with_bench_twin=False, with_search=True):
    """The menu of step 39, optionally with a second Ogerpon on the bench.

    The twin is the same card with its energy stripped, and its Teal Dance is
    appended to the menu -- which is what the engine offers for a benched
    Ogerpon with a Grass in hand. Dropping the Ultra Ball is how the raw bands
    are read: with a discard-priced play alive, the ordering rule of
    `finalize.py` parks every hand-neutral ability in front of it and the
    numbers on the menu are no longer the scorer's own.
    """
    seq = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["sequence"])
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    mine = _mine(obs)
    if not with_search:
        ub = next(i for i, c in enumerate(mine["hand"]) if c["id"] == ULTRA_BALL)
        obs["select"]["option"] = [
            o for o in obs["select"]["option"]
            if not (o.get("type") == int(m.OptionType.PLAY) and o.get("index") == ub)]
    if with_bench_twin:
        twin = copy.deepcopy(mine["active"][0])
        twin["serial"] = 999
        twin["energyCards"] = []
        twin["energies"] = []
        mine["bench"].append(twin)
        obs["select"]["option"].append(
            {"type": int(m.OptionType.ABILITY), "area": int(m.AreaType.BENCH),
             "index": len(mine["bench"]) - 1})
    return obs


def _scored(obs):
    box = {}
    import ptcg.turn.finalize as fin
    fin.TIER_CENSUS_SINK = (
        lambda ctx, sel, sc, tiers, o, mi: box.update(sc=list(sc), tier=list(tiers)))
    try:
        m.agent(obs)
    finally:
        fin.TIER_CENSUS_SINK = None
    return box["sc"], box["tier"]


def _ability(obs, area, index=0):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(m.OptionType.ABILITY)
                and o.get("area") == int(area) and o.get("index") == index)


# ---------------------------------------------------------------------------
# 1. The reservation's own conditions really hold on this board
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_the_reserve_band_is_about():
    obs = _board(with_search=False)
    mine = _mine(obs)
    active = mine["active"][0]

    # The ACTIVE is short of its attack: `_active_needs_energy`.
    assert active["id"] == OGERPON
    assert len(active["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]
    # ...and the hand cannot pay for two bodies: `not _enough_for_both`.
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 1

    # The manual attachment to that same active is vetoed, and that is the
    # other half of the trap: the Teal Dance precedence sends the Grass to the
    # ability, and the reserve band then refused to let the ability take it.
    scores, _ = _scored(obs)
    manual = next(i for i, o in enumerate(obs["select"]["option"])
                  if o.get("type") == int(m.OptionType.ATTACH)
                  and o.get("inPlayArea") == int(m.AreaType.ACTIVE))
    assert scores[manual] <= 0


# ---------------------------------------------------------------------------
# 2. The two halves of the guard
# ---------------------------------------------------------------------------

def test_the_active_dance_is_not_in_the_reserve_band():
    obs = _board(with_search=False)
    scores, tiers = _scored(obs)
    dance = _ability(obs, m.AreaType.ACTIVE)
    assert scores[dance] > RESERVE_BAND, (
        "the active's own dance IS the reservation being honoured; got "
        f"{scores[dance]}")
    assert scores[dance] >= REAL_PLAY_FLOOR and tiers[dance] > 0, (
        "and it has to clear the floor that lets it compete in the ENERGY "
        f"tier; got {scores[dance]} tier {tiers[dance]}")


def test_the_benched_dance_keeps_the_reserve_band():
    """The half that is NOT cosmetic: that Grass belongs to the active."""
    obs = _board(with_bench_twin=True, with_search=False)
    scores, tiers = _scored(obs)
    bench = _ability(obs, m.AreaType.BENCH, index=len(_mine(obs)["bench"]) - 1)
    assert scores[bench] == RESERVE_BAND and tiers[bench] == 0, (
        "a benched Ogerpon dancing eats the Grass the active is waiting for; "
        f"got {scores[bench]} tier {tiers[bench]}")


def test_the_active_dance_outranks_the_benched_one():
    """Both alive, and the order between them is the whole point."""
    obs = _board(with_bench_twin=True, with_search=False)
    scores, tiers = _scored(obs)
    active = _ability(obs, m.AreaType.ACTIVE)
    bench = _ability(obs, m.AreaType.BENCH, index=len(_mine(obs)["bench"]) - 1)
    assert (tiers[active], scores[active]) > (tiers[bench], scores[bench])
