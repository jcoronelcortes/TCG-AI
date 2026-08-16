"""THE STADIUM ABILITY NOBODY SCORED IS NOT A FREE PLAY.

USER, `records/registro_007_pasos_098_hasta_105.json` step 101, turn 7 vs a
Slowking deck, LOST.

Their stadium was Academy at Night (id 1248): "Once during EACH player's turn,
that player may put a card from their hand on top of their deck". Like Grand
Tree it is SHARED, so the simulator offered US its ability, and the menu of that
action was exactly four options:

    PLAY Lillie's Determination     <- the Supporter, still unplayed this turn
    ABILITY of the stadium (area 7)
    ATTACK Syrup Storm
    END

We had TWO cards in hand. The agent fired the stadium ability and the
sub-selection (`SelectContext.TO_DECK`, `select.effect` = the stadium) then
handed it the Lillie's: the one card that refills the hand and fixes the bench
was buried in our own deck, by us, for nothing.

WHY IT FIRED. Nothing in the code ever decided to use that stadium -- and that
is the whole point. The ABILITY scorer dispatches by card id, and everything it
does not name falls through to a generic `score = 29000`, which is the band of a
REAL play and sits above the Supporter. Academy at Night was never modelled, so
it inherited the price of a good play.

THE FIX IS BY AREA, NOT BY CARD. The one stadium ability this deck wants is
Grand Tree, decided above by id with a plan behind it (`_gt_plan`). Anything
else offered on the STADIUM area is an effect nobody scored, and an unscored
effect must not be paid for with a card from hand. A stadium printed next set
cannot repeat this through the same fallback.

The Grand Tree half of this file is the control: the veto must not be so wide
that it switches off the stadium engine that IS modelled.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import GRAND_TREE, G, Scenario, pk

ACADEMY_AT_NIGHT = m.Academy_at_Night
LILLIE = m.Lillie_Determination
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
CHIKORITA = m.Chikorita
APPLIN = m.Applin
MEGANIUM = m.Meganium
SLOWPOKE = 162


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _board(stadium_id):
    """The board of step 101, with the stadium of the field as the only variable.

    Active Hydrapple ex at 250/330 with two Grass (Syrup Storm payable), the
    bench of the record, and the hand down to its last two cards: the Lillie's
    Determination and a Meganium. The Supporter of the turn is still unplayed.
    """
    obs = (Scenario(turn=7, step=101, tac=4)
            .my_active(pk(HYDRAPPLE, hp=250, energies=[G, G],
                          pre_evo=[APPLIN, m.Dipplin]))
            .my_bench(pk(OGERPON, hp=100, energies=[G, G, G]),
                      pk(MEOWTH),
                      pk(CHIKORITA),
                      pk(OGERPON),
                      pk(APPLIN, aparecio=True))
            .my_hand(LILLIE, MEGANIUM)
            .stadium(stadium_id, of_the_opponent=True)
            .op_active(pk(SLOWPOKE, hp=80, max_hp=80))
            .op_bench(pk(SLOWPOKE, hp=80, max_hp=80))
            .op_zones(hand=10, deck=24, prizes=5)
           .menu_hand(with_attack=True, with_stadium_ability=True)
           .build())
    # `menu_hand` offers one PLAY per card in hand; the simulator does not. In
    # the record the Meganium had no Bayleef in play to evolve from, so the only
    # PLAY on the menu was the Lillie's -- which is what makes the four options
    # of the record four and not five.
    hand = obs["current"]["players"][0]["hand"]
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] != int(m.OptionType.PLAY)
        or hand[o["index"]]["id"] == LILLIE]
    return obs


def _chosen(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def test_we_do_not_use_their_academy_at_night():
    """The bug: the ability of a stadium we never modelled beat the Supporter."""
    obs = _board(ACADEMY_AT_NIGHT)
    assert _chosen(obs)["type"] != int(m.OptionType.ABILITY)


def test_the_lillie_is_played_instead_of_being_buried():
    """And what the turn does instead is the play that was there all along."""
    obs = _board(ACADEMY_AT_NIGHT)
    chosen = _chosen(obs)
    assert chosen["type"] == int(m.OptionType.PLAY)
    assert obs["current"]["players"][0]["hand"][chosen["index"]]["id"] == LILLIE


def test_the_veto_does_not_reach_the_grand_tree():
    """The control. Grand Tree is the ONE stadium ability this deck uses, and it
    is decided by id with a plan behind it: the same menu, same hand, same
    bench -- and with a Chikorita on the bench to root the chain -- still fires
    it. A veto that took this out would have cost more than the bug."""
    obs = _board(GRAND_TREE)
    assert _chosen(obs)["type"] == int(m.OptionType.ABILITY)
