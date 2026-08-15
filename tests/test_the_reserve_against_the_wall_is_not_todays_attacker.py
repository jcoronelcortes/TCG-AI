"""The answer to the wall is a RESERVE: do not retreat the ex that is attacking to spend it.

Scenario (`records/registro_006_pasos_045_hasta_061.json`, step 58, turn 6,
episode 93210034 vs Crustle / Mega Kangaskhan ex -- WON):

    US (6 prizes)                         RIVAL (6 prizes)
    active  Teal Mask Ogerpon ex          active  Mega Kangaskhan ex **300/300**
            210/210, 4 eff. energies              0 energies, Rapid-Fire Combo 200
    bench   Meganium 160/160, 4 eff.      bench   **Crustle 170/170**, 3 energies
            Teal Mask Ogerpon ex, 2 eff.          Dwebble x2
            Meowth ex, 0

The agent **retreated the Ogerpon** -- discarding an energy card -- promoted the
Meganium and attacked with it. Three things were wrong with the swap at once:

  * **Less damage.** Myriad Leaf Shower does 30 + 30·(4 own + 0 theirs) = **150**
    into the Kangaskhan. Solar Beam does **140**. The retreat paid a card to hit
    for ten less.
  * **The wrong body in front.** Rapid-Fire Combo hits for 200: the 160 HP
    Meganium dies to it, the 210 HP Ogerpon it had just pulled back **survives**.
  * **The reserve was spent for nothing.** Crustle's *Mysterious Rock Inn*
    prevents all damage from our Pokemon {ex}, so that Meganium is the only body
    of ours that can ever hurt the wall waiting on their bench -- and the wall
    was not the thing it was being sent to fight.

Cause: the two retreat branches that promote the anti-wall attacker
(`_tmo_attacker_ready` and `_crustle_bench_atk`, both scoring 3400) were guarded
by the ARCHETYPE (`op_is_crustle_deck` / `op_is_cornerstone_deck`) plus "the
active does not knock out". Both were true here -- and they are equally true of
every board where our ex damages what is in front perfectly well and simply
cannot finish a 300 HP body. The deck flag is not the body in front, the fourth
time that confusion has been paid for
([[el-muro-es-un-cuerpo-no-una-lista-de-mazo]]).

Fix (`THE_RESERVE_DOES_NOT_TAKE_THE_FRONT`): the swap is asked the only question
that pays for it -- does the body coming up do MORE to their active THIS TURN
than the one going down? With the wall actually in front our ex does 0 and the
promotion still fires by construction; with anything else in front the reserve
stays on the bench, which is where it is worth something. Strictly more, because
the retreat discards energy: a tie is a card paid for nothing.

Golden corpus: two flips, both of this class -- this step, and
`registro_023_crustle_wall_3_asiento1` turn 4 (retreating an Ogerpon ex that
hits for 180 to promote a Dipplin that hits for 80).
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

import main as m  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from recorded_deck import deck_of_record  # noqa: E402

import ptcg.turn.options.retreat as retreat_mod  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_kangaskhan_la_reserva_no_toma_el_frente_step58.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
KANGASKHAN = m.Mega_Kangaskhan_ex


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _idx(obs, tipo):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == tipo)


def _decide(obs):
    with deck_of_record():
        return m.agent(obs)


# ---------------------------------------------------------------------------
# 1. The board: without it the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_swap_that_hits_for_ten_less():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    mio, riv = cur["players"][yo], cur["players"][1 - yo]

    active = mio["active"][0]
    meganium = next(b for b in mio["bench"] if b and b["id"] == MEGANIUM)
    op_active = riv["active"][0]

    # In front of us, a 300 HP body our ex CAN damage -- not the wall.
    assert active["id"] == OGERPON and active["hp"] == 210
    assert op_active["id"] == KANGASKHAN and op_active["hp"] == 300
    cls = m.to_observation_class(o).current
    assert m._our_effective_damage(
        cls.players[yo].active[0], cls.players[1 - yo].active[0],
        150, True, False) == 150

    # The wall waits on their BENCH: that is what the Meganium is for.
    assert any(b and b["id"] in (m.Crustle_Grass, m.Crustle_Fighting)
               for b in riv["bench"])

    # Myriad Leaf Shower 150 > Solar Beam 140, and neither knocks out.
    assert 30 + 30 * (len(active["energies"]) + len(op_active["energies"])) == 150
    assert (m.attack_table[m.card_table[MEGANIUM].attacks[0]].damage or 0) == 140
    assert len(meganium["energies"]) >= 4          # it IS a ready attacker
    assert 150 < op_active["hp"]                   # no KO either way

    # And the body it would leave in front dies to what the active survives.
    assert (m.attack_table[m.card_table[KANGASKHAN].attacks[0]].damage or 0) == 200
    assert meganium["hp"] < 200 < active["hp"]

    # The menu really offers both.
    assert _idx(o, int(m.OptionType.ATTACK)) is not None
    assert _idx(o, int(m.OptionType.RETREAT)) is not None


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_ogerpon_attacks_instead_of_handing_the_front_to_the_reserve():
    o = _obs()
    ataque = _idx(o, int(m.OptionType.ATTACK))
    assert _decide(o) == [ataque], (
        "el Ogerpon ex pega 150 al Kangaskhan; retirarlo para subir el Meganium "
        "cuesta una energía, pega 140 y gasta el único cuerpo que puede herir "
        "al Crustle de su banca")


def test_without_the_rule_the_recorded_retreat_comes_back():
    """The arm the gate measures against: the flag off is the old behaviour."""
    o = _obs()
    retirada = _idx(o, int(m.OptionType.RETREAT))
    previo = retreat_mod.THE_RESERVE_DOES_NOT_TAKE_THE_FRONT
    retreat_mod.THE_RESERVE_DOES_NOT_TAKE_THE_FRONT = False
    try:
        assert _decide(o) == [retirada]
    finally:
        retreat_mod.THE_RESERVE_DOES_NOT_TAKE_THE_FRONT = previo


# ---------------------------------------------------------------------------
# 3. What does NOT change: with the wall IN FRONT the promotion still fires
# ---------------------------------------------------------------------------

def test_with_the_wall_in_front_the_reserve_still_takes_the_spot():
    """Their Crustle in the active spot: our ex does 0 and the Meganium goes up.

    The same board with the wall and the Kangaskhan swapped. It is the case the
    3400 branches were written for, and the guard has to leave it alone: with
    `Mysterious Rock Inn` in front, `_our_effective_damage` of the ex is 0 and
    any damage at all beats it.
    """
    o = _obs()
    cur = o["current"]
    riv = cur["players"][1 - cur["yourIndex"]]
    muro = next(b for b in riv["bench"]
                if b and b["id"] in (m.Crustle_Grass, m.Crustle_Fighting))
    idx = riv["bench"].index(muro)
    riv["bench"][idx], riv["active"][0] = riv["active"][0], muro

    cls = m.to_observation_class(o).current
    delante = cls.players[1 - cur["yourIndex"]].active[0]
    ogerpon = cls.players[cur["yourIndex"]].active[0]
    assert m._our_effective_damage(ogerpon, delante, 150, True, False) == 0

    assert _decide(o) == [_idx(o, int(m.OptionType.RETREAT))]
