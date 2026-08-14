"""THE TURN HAS ONE RETREAT, AND THE BODY THAT CLOSES THE GAME GETS IT.

registro_009 step 168, episode 92844329, LOST -- the far end of the turn this
agent's `_doomed_mute_pivot` fix already covers at step 150.

WHAT THE BOARD LOOKED LIKE AT STEP 168. Two prizes left for us. A Fezandipiti ex
in front with one Grass on it. On the bench, TWO Teal Mask Ogerpon ex, one at six
effective energy and one at four, against a Marnie's Grimmsnarl ex at 300 of 320
that is WEAK TO GRASS: Myriad Leaf Shower reads 30 + 30 x (6 + 2) = 270, doubled
to 540. Either of them ends the game from the front.

WHY THE AGENT DID NOT PROMOTE ONE AND ATTACK. It could not. The engine offered
exactly one option at that step -- END -- because `retreated` had been true since
step 151. A turn has ONE retreat, and it had been spent eighteen actions earlier
putting the Fezandipiti in front of the Ogerpon that was itself one Grass from
the same knockout. There is no scoring defect at step 168: by then the only door
into the active spot was already shut.

SO THIS FILE DOES NOT ADD A RULE. It pins the chain that has to hold for the
retreat to reach the right body, on any deck, because today that chain holds by
the ORDER OF THE TIERS and by score constants forty rungs apart -- and nothing
was asserting it. The record is what a silent break of it costs.

    1. the charge goes on the CLOSER before the retreat is spent (the energy
       tier runs ahead of the retreat tier);
    2. once the closer is ready, the retreat is taken;
    3. the promotion brings up the CLOSER, not the wall;
    4. and where no body closes the game, the wall keeps the retreat -- the
       ceiling, without which this would read "never promote a wall".

Deck-agnostic on purpose: every step asks "does this body's attack take the
prizes we are missing", never a card name. The Marnie board is the one the
record hands us; the assertions would read the same against any deck whose
active hands over enough prizes to end it.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m                                            # noqa: E402
import golden_corpus as gc                                  # noqa: E402
from state_builder import Scenario, pk, G                   # noqa: E402
from cg.api import OptionType                               # noqa: E402
from ptcg.state.agent_state import AGENT_STATE              # noqa: E402
from ptcg.turn.game_plan import MODE_WIN_NOW, ROUTE_PROMOTE  # noqa: E402

GRIMMSNARL_EX = 648
MUNKIDORI = 112
FROSLASS = 104
IMPIDIMP = 646
DARK = int(m.EnergyType.DARKNESS)

# Bench order shared by every board below: the closer first, the wall second.
CLOSER, WALL, SPARE = 0, 1, 2


def _board(active, bench_grass, hand, own_prizes=2, **kw):
    """Their Grimmsnarl ex in front at 300, ours split active / bench.

    `bench_grass` is what the benched Teal Mask Ogerpon ex carries: 3 is lethal
    through the weakness (360 over 300), 2 is one charge short, 1 does not even
    reach the attack's cost.
    """
    return (Scenario(turn=9, step=150, tac=1, own_prizes=own_prizes,
                     supporter_played=True, stadium_played=True, **kw)
            .my_active(active)
            .my_bench(pk(m.Teal_Mask_Ogerpon_ex, hp=130, energies=[G] * bench_grass),
                      pk(m.Hydrapple_ex),
                      pk(m.Meowth_ex, hp=70))
            .my_hand(*hand)
            .stadium(m.Forest_of_Vitality)
            .op_active(pk(GRIMMSNARL_EX, hp=300, max_hp=320,
                          energies=[DARK, DARK]))
            .op_bench(pk(MUNKIDORI, hp=70, max_hp=110, energies=[DARK]),
                      pk(FROSLASS, hp=90, max_hp=90),
                      pk(FROSLASS, hp=90, max_hp=90),
                      pk(MUNKIDORI, hp=70, max_hp=110, energies=[DARK]),
                      pk(IMPIDIMP, hp=70, max_hp=70))
            .op_zones(hand=5, deck=18, prizes=3)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard())


def _choice(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def test_the_charge_reaches_the_closer_before_the_retreat_is_spent():
    """LINK 1. The active is doomed and mute, the closer is one Grass short on
    the bench, and that Grass is in hand.

    The energy tier runs ahead of the retreat tier, so the charge lands first --
    which is the only order that leaves a retreat to spend afterwards. Reversed,
    the turn pays the retreat for a body that cannot attack and the Grass has
    nowhere useful left to go: the shape of registro_009.
    """
    gc.reset_agent(m)
    obs = _board(pk(m.Meowth_ex, hp=40, energies=[G]), 2,
                 [m.Basic_Grass_Energy, m.Ultra_Ball]).menu_hand(
        with_retreat=True, with_attachment=True).build()
    picked = _choice(obs)
    assert picked["type"] == int(OptionType.ATTACH), picked
    assert picked["inPlayArea"] == int(m.AreaType.BENCH)
    assert picked["inPlayIndex"] == CLOSER, \
        "the Grass belongs on the body that ends the game, not on a wall"


def test_with_the_grass_only_reachable_it_digs_instead_of_retreating():
    """LINK 1b. Same board with the Grass in the DECK and a card that reaches
    it. Digging keeps the retreat; retreating spends the one resource the win
    still needs. This is the decision the record got wrong."""
    gc.reset_agent(m)
    obs = _board(pk(m.Meowth_ex, hp=40, energies=[G]), 2,
                 [m.Unfair_Stamp, m.Ultra_Ball]).menu_hand(
        with_retreat=True).build()
    picked = _choice(obs)
    assert picked["type"] != int(OptionType.RETREAT), \
        "it spent the retreat while the closer was still on the bench"
    assert obs["current"]["players"][0]["hand"][picked["index"]]["id"] \
        == m.Unfair_Stamp


def test_once_the_closer_is_ready_the_retreat_is_taken_AS_THE_WIN():
    """LINK 2. Charged closer on the bench, a body in front that does not
    attack: now the retreat is exactly what the win costs, and it is paid.

    IT ASSERTS THE REASON, NOT ONLY THE MOVE. Measured with a mutant that
    switches `_win_ko_active_via_promote` off: the retreat is still chosen --
    its score merely falls from 9600 to 3200, and 3200 still beats every other
    option on this board. A test that stopped at "it retreated" would have
    watched nothing. What actually collapses is the PLAN: `win_route` empties
    and the mode drops from WIN_NOW to RACE. So that is what is pinned -- the
    turn has to KNOW the retreat is the winning move, because that is the
    reading every rung above the wall pivots is built on.
    """
    gc.reset_agent(m)
    obs = _board(pk(m.Fezandipiti_ex, energies=[G]), 3, [m.Ultra_Ball],
                 energy_played=True).menu_hand(with_retreat=True).build()
    assert _choice(obs)["type"] == int(OptionType.RETREAT)

    plan = AGENT_STATE.turn_plan
    assert plan.win_route == ROUTE_PROMOTE, plan
    assert plan.mode == MODE_WIN_NOW, plan
    assert plan.prizes_today >= plan.my_prize, plan


def test_the_promotion_brings_up_the_closer_and_not_the_wall():
    """LINK 3. The retreat is paid and the bench holds both: the body whose
    attack ends the game, and a 330 HP Hydrapple ex that would survive longer.

    Surviving longer is worth nothing on the turn that ends the game, and the
    promotion knows it.
    """
    gc.reset_agent(m)
    obs = _board(pk(m.Fezandipiti_ex, energies=[G]), 3, [m.Ultra_Ball],
                 energy_played=True).promote_after_retreat().build()
    assert _choice(obs)["index"] == CLOSER


def test_the_wall_keeps_the_retreat_when_no_body_closes_the_game():
    """THE CEILING. Same board, but the benched Ogerpon carries one Grass --
    below its attack's cost, so nothing on our side ends the game this turn.

    The wall is then worth what it always was and gets the front spot. Without
    this the rule above would read "never promote a wall", which is a different
    and much larger change than the record justifies.
    """
    gc.reset_agent(m)
    obs = _board(pk(m.Fezandipiti_ex, energies=[G]), 1, [m.Ultra_Ball],
                 energy_played=True).promote_after_retreat().build()
    assert _choice(obs)["index"] == WALL
