"""THE SEAT COSTS THE COVER IT LEAVES BEHIND.

A pending written by the user on 12 August 2026 from episode 92355371 step 62
(vs *Festival Lead*, LOST), and untouched until the night of the 15th:

    The Tera of a benched Teal Mask Ogerpon ex prevents ALL damage from attacks
    while it is on the BENCH. The code knows it -- `_projected_incoming`
    (ptcg/calc/damage.py) returns 0 for it there, and the RETREAT branch
    respects it -- but the promotion after a knockout charged nothing for
    pulling it out of that cover. Promoting it does two things at once:
    it gives up an untouchable body, and it stands TWO prizes in front of an
    engine that spreads knockouts.

    In the record it came up, ate 120 (Deluxe Bomb) and sat at 90 of 210, where
    the next Do the Wave -- 80 x 2 under Festival Grounds -- took it and both
    prizes with it.

THE BOARD, rebuilt with the StateBuilder because `records/` no longer holds that
episode (it is transient local data and has rotated twice since):

    US (seat 0)                          RIVAL (Festival Grounds, theirs)
    active  -- empty, forced promotion   active  Dipplin 80, bench of four
    bench   Teal Mask Ogerpon ex 210 (1G)        -> Do the Wave 20x4 = 80, twice
            Applin 40
            Chikorita 70

Every candidate is mute (none reaches its attack cost), so no knockout bonus
speaks and the seat is decided by the survival and prize bands alone. The
Ogerpon survives both waves and was promoted for it -- 334 against the Applin's
-78.

WHAT THE PRICE IS AND IS NOT. `PROMO_TERA_COVER_PRICE` is 500 and it is a PRICE,
not a veto: the body that knocks out still goes first (+20000), a body that dies
anyway still yields to a survivor (-6000), and the prize band still speaks when
nobody endures (-1500 each). It is charged only on the FORCED promotion, where
the cover is real and the choice is ours; on a voluntary retreat the body is
being asked for something it can only do from the front.

⚠️ THE FLIP IT CAUSES IN THE FROZEN CORPUS IS NOT OBVIOUSLY GOOD, and it is
written down here rather than in a commit message nobody reads:
`registro_004_alakazam_4_asiento0` turn 9 -- four mute bodies, their four
Alakazam in front -- moves from a Teal Mask Ogerpon ex (210 HP) to a Meowth ex
(170 HP). BOTH are worth two prizes, so what the price buys there is the cover
alone, and what it pays is 40 HP in front. That trade is the open question this
rule carries into its gate.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m                                      # noqa: E402
import ptcg.turn.options.card as CARD                 # noqa: E402
from state_builder import Scenario, pk, G             # noqa: E402

OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _board(bench=None, their_bench=4):
    obs = (Scenario(turn=4, step=62, tac=12, own_prizes=5, supporter_played=True)
           .my_active(pk(APPLIN))
           .my_bench(*(bench if bench is not None else
                       [pk(OGERPON, hp=210, energies=[G], fisicas=1),
                        pk(APPLIN, hp=40),
                        pk(CHIKORITA, hp=70)]))
           .my_hand(m.Basic_Grass_Energy)
           .op_active(pk(DIPPLIN, hp=80, energies=[G], fisicas=1,
                         pre_evo=[APPLIN]))
           .op_bench(*[pk(APPLIN, hp=40) for _ in range(their_bench)])
           .stadium(m.Festival_Grounds, of_the_opponent=True)
           .op_zones(hand=4, deck=20, prizes=5)
           .deck(m.Basic_Grass_Energy)
           .rest_to_discard()
           .promote_from_bench()
           .build())
    # The forced promotion has an EMPTY active spot, which is what
    # `_forced_ko_promote` reads; the builder demands an active, so it is
    # emptied here exactly as the record shows it.
    obs["current"]["players"][0]["active"] = []
    return obs


def _promoted(obs):
    choice = m.agent(json.loads(json.dumps(obs)))
    opt = obs["select"]["option"][choice[0]]
    return obs["current"]["players"][0]["bench"][opt["index"]]["id"]


def test_the_board_is_one_where_no_knockout_speaks():
    """Without this the test measures the knockout bonus, not the price."""
    obs = _board()
    mine = obs["current"]["players"][0]
    assert not mine["active"], "la promocion tiene que ser FORZADA"
    assert [b["id"] for b in mine["bench"]] == [OGERPON, APPLIN, CHIKORITA]
    # Every candidate is short of its attack cost: the seat is decided by the
    # survival and prize bands alone.
    assert len(mine["bench"][0]["energies"]) < m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON]
    assert APPLIN not in m.MAIN_ATTACKERS and CHIKORITA not in m.MAIN_ATTACKERS


def test_the_covered_ex_does_not_take_the_seat():
    assert _promoted(_board()) == APPLIN, (
        "el cuerpo que estaba INTOCABLE en la banca no paga el asiento: sube "
        "el barato")


def test_without_the_price_the_covered_ex_takes_it():
    """The attribution, pinned: this board moves because of the price."""
    original = CARD.PROMOTE_TERA_PAYS_FOR_ITS_COVER
    CARD.PROMOTE_TERA_PAYS_FOR_ITS_COVER = False
    try:
        assert _promoted(_board()) == OGERPON
    finally:
        CARD.PROMOTE_TERA_PAYS_FOR_ITS_COVER = original


def test_the_price_never_outranks_the_body_that_knocks_out():
    """The boundary that keeps it a price. The same board with the Ogerpon at
    Myriad's cost: 30 + 30 x (3 ours + 1 theirs) = 120 over their 80 HP Dipplin,
    so it takes a prize the turn it comes up -- and +20000 is untouchable by a
    500 fee."""
    obs = _board(bench=[pk(OGERPON, hp=210, energies=[G, G, G], fisicas=3),
                        pk(APPLIN, hp=40),
                        pk(CHIKORITA, hp=70)])
    assert _promoted(obs) == OGERPON


def test_the_voluntary_retreat_does_not_pay_it():
    """The other boundary: with a body still in the active spot the promotion is
    OURS to choose and the seat is being bought for something the bench cannot
    do. The price is a forced-promotion reading only."""
    obs = _board()
    obs["current"]["players"][0]["active"] = [
        pk(DIPPLIN, hp=80, energies=[G], fisicas=1, pre_evo=[APPLIN])
        if not isinstance(pk(DIPPLIN), dict) else
        {"id": DIPPLIN, "hp": 80, "maxHp": 80, "energies": [1],
         "energyCards": [{"id": 1, "playerIndex": 0, "serial": 9990}],
         "tools": [], "preEvolution": [], "appearThisTurn": False,
         "playerIndex": 0, "serial": 9989}]
    obs["select"]["context"] = int(m.SelectContext.SWITCH)
    assert _promoted(obs) == OGERPON
