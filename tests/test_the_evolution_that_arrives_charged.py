"""The evolution we are fetching brings its own attachment with it.

We already model this for THEM. `OP_EVO_ENERGY_ON_PLAY` (ptcg/cards/ids.py)
exists because projecting an opposing evolution as "the energies of the body
underneath plus their one attachment" under-read a whole attack cost against an
Archaludon ex, whose Assemble Alloy pays part of that cost on the way in. The
same arithmetic was still being asked of OUR OWN line, and with the same hole.

`_ub_hydra_can_attack_now` (ptcg/turn/options/card.py) is the projection behind
`dead_hydra_prefers_meowth`: before spending an Ultra Ball on a Hydrapple ex it
asks whether that Hydrapple would be able to ATTACK this turn, and if not it
prefers the Meowth ex refill -- a 2-prize body that cannot attack is not worth
two cards. It counted the Dipplin's energy plus the turn's manual attachment
and stopped there. But Syrup Storm costs TWO and the Hydrapple ex prints
Ripening Charge: "once during your turn you may attach a Basic {G} Energy from
your hand to 1 of your Pokemon". The body being fetched has not used its ability
-- it does not exist on the board yet -- so it arrives carrying one of the two
attachments it needs. The projection was one short of the truth, and always in
the same direction: it called a line dead that closes on its own.

That the ability is usable the turn the body evolves is not an assumption: in
the record below the Hydrapple ex evolves at step 69 and the engine offers its
Ripening Charge at step 70.

WHERE IT COMES FROM (user, episode 92595425, turn 4 vs a Dragapult ex deck,
LOST). The turn had an Applin in front, a Hydrapple ex in hand and an Ultra Ball
for the missing Dipplin, and it ended with the 330 HP body in play at ZERO
energy, no attack thrown and no Grass left in hand. THIS RULE DOES NOT FLIP ANY
STEP OF THAT RECORD, and the honest reason is worth writing down: by the time
the fetch menu came up the turn's manual attachment had already been spent on a
benched Ogerpon and the hand held no Grass, so the budget really was empty. What
the record gives is the SHAPE -- the board the turn would have had one decision
earlier, which is the one built below.

THE BUDGET IS THE HAND, and that is the second half. Two routes -- the manual
attachment and the arriving Ripening Charge -- are two CARDS, so a hand with one
Grass buys one of them however many routes are open. Without that cap the fix
would read every gapped line as alive.

Coverage: both halves separately (the manual attachment plus the arriving
charge; and the arriving charge alone, on a turn that already attached), and the
budget boundary that keeps them honest.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from golden_corpus import reset_agent
from patching import parcheado
from state_builder import Scenario, pk

G = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _board(grass_in_hand=2, dipplin_energy=0, already_attached=False):
    """An Ultra Ball fetch with the Hydrapple line one piece short.

    A Dipplin in front with a Hydrapple ex in the deck: the fetch either buys
    the attacker of this turn or it does not, and that is exactly what
    `_ub_hydra_can_attack_now` is asked. The Meowth ex and the Lillie's in the
    deck are what make the refill branch a real alternative -- without them
    `dead_hydra_prefers_meowth` cannot fire and the board proves nothing.
    """
    return (Scenario(turn=6, step=1, tac=1, energy_played=already_attached)
            .my_active(pk(m.Dipplin, pre_evo=[m.Applin],
                          energies=[G] * dipplin_energy,
                          fisicas=dipplin_energy))
            .my_bench(pk(m.Teal_Mask_Ogerpon_ex), pk(m.Meowth_ex))
            .my_hand(*([G] * grass_in_hand))
            .op_active(pk(271, hp=120, max_hp=120))       # Kilowattrel, neutral
            .op_zones(hand=4, deck=40, prizes=5)
            .deck(m.Hydrapple_ex, m.Meowth_ex, m.Lillie_Determination,
                  m.Teal_Mask_Ogerpon_ex, m.Tapu_Bulu)
            .fetch_ultra_ball()
            .rest_to_discard()
            .build())


def _fetched(obs):
    choice = m.agent(obs)
    assert choice, f"the agent cancelled the fetch: {choice}"
    return obs["select"]["deck"][obs["select"]["option"][choice[0]]["index"]]["id"]


def _score_of(obs, card_id):
    """What the fetch ladder priced that candidate at.

    THE DECISION IS NOT THE OBSERVABLE HERE, and the reason is the point of the
    last test in this file: `dead_hydra_prefers_meowth` is one of three
    consecutive refill rules and switching it off hands the answer to the next
    one, so the card that comes out of the deck does not move yet. What DOES
    move is the Hydrapple candidate's own price: `yields_to_meowth_refresh`
    (ptcg/decision/ultra_ball.py) is keyed on that very flag and clamps it to
    150. Reading the score reads the projection.
    """
    seen = {}

    def spy(context, select, scores, o, my_index, top_n=3):
        seen["scores"] = list(scores)

    with parcheado("_debug_log_decision", spy):
        m.agent(obs)
    for i, option in enumerate(obs["select"]["option"]):
        if obs["select"]["deck"][option["index"]]["id"] == card_id:
            return seen["scores"][i]
    raise AssertionError(f"{card_id} is not a candidate of this fetch")


HYDRA_LIVE = 980      # `dipplin_evolvable`, the branch's own band
HYDRA_CLAMPED = 150   # ...after `yields_to_meowth_refresh` calls the line dead


# ---------------------------------------------------------------------------
# 1. Both attachments: the turn's own, and the one the body brings
# ---------------------------------------------------------------------------

def test_the_line_that_closes_with_the_arriving_charge_is_not_dead():
    """Dipplin at zero, two Grass in hand, the attachment unspent: the manual
    one and the arriving Ripening Charge are the two Syrup Storm costs, so the
    Hydrapple ex attacks the turn it lands and is not priced as dead."""
    assert _score_of(_board(), m.Hydrapple_ex) == HYDRA_LIVE


# ---------------------------------------------------------------------------
# 2. The arriving charge ALONE, on a turn that has already attached
# ---------------------------------------------------------------------------

def test_the_arriving_charge_alone_closes_a_line_one_short():
    """The manual attachment is spent and the Dipplin carries one: the body
    being fetched supplies the second cost by itself. This is the half the old
    arithmetic could not see at all -- with `energyAttached` set it added
    nothing and declared the line dead."""
    assert _score_of(_board(grass_in_hand=1, dipplin_energy=1,
                            already_attached=True), m.Hydrapple_ex) == HYDRA_LIVE


# ---------------------------------------------------------------------------
# 3. The boundary: two routes are still two CARDS
# ---------------------------------------------------------------------------

def test_one_grass_buys_one_attachment_however_many_routes_are_open():
    """Both routes are open and the hand holds a single Grass: the line lands
    one short of Syrup Storm, the Hydrapple ex would not attack, and the refill
    keeps the search. Without this cap the fix would call every gapped line
    alive."""
    assert _score_of(_board(grass_in_hand=1), m.Hydrapple_ex) == HYDRA_CLAMPED
    assert _fetched(_board(grass_in_hand=1)) == m.Meowth_ex


def test_a_line_two_attachments_short_stays_dead():
    """Nothing in hand to pay with: no route buys anything."""
    assert _score_of(_board(grass_in_hand=0), m.Hydrapple_ex) == HYDRA_CLAMPED
    assert _fetched(_board(grass_in_hand=0)) == m.Meowth_ex


# ---------------------------------------------------------------------------
# 4. What this rule does NOT buy, and who owns it
# ---------------------------------------------------------------------------

def test_the_search_still_refills_because_the_next_refill_rule_takes_over():
    """The projection is fixed and the CARD does not change, on purpose.

    `_RULES_UB_MEOWTH` asks three refill rules in a row --
    `dead_hydra_prefers_meowth`, `dead_meganium_prefers_meowth`,
    `no_attacker_prefers_meowth`, all in the 1000-1250 band -- and switching the
    first one off hands the answer to the second, which beats the Hydrapple
    branch's 980 just the same. The file's own note on phase E4 of the Marnie
    plan (ptcg/turn/options/card.py) says exactly this: "the real hook is not
    `_dipplin_priority` but that family, and turning it around is a TRADE, not
    a fix".

    Making that family yield WAS written and measured (a
    `_ub_search_arms_an_attacker` in ptcg/decision/ultra_ball.py: the search
    completes a line that reaches its cost this turn). It closed this board --
    the fetch became the Hydrapple ex -- and it was REVERTED: +0.00 on the
    weighted matrix over its own affected group at 800 games per matchup, and
    no binary contradiction against the engine to earn the exception that keeps
    a neutral change. What survives here is the arithmetic, which does have one:
    the engine offers the arriving Ripening Charge on the turn the body evolves
    in 29 of 29 recorded turns.

    So this test is not an expectation, it is a BOUNDARY: it records what this
    change is and is not worth, and what it would take to move it.
    """
    assert _fetched(_board()) == m.Meowth_ex
