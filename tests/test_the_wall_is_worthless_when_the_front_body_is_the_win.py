"""registro_009 step 150 vs Marnie's Grimmsnarl ex, episode 92844329, LOST.

THE BOARD. Two prizes left for us, three for them. Their Grimmsnarl ex stood in
front at 300 of 320 and it is WEAK TO GRASS, so our active Teal Mask Ogerpon ex
-- two Grass on it, Myriad Leaf Shower counting their two Darkness as well --
was exactly ONE Basic Grass away from 360 damage and the game. On their bench:
two Froslass dripping 20 a round onto every body of ours that has an Ability,
and two charged Munkidori able to aim 30 counters each wherever they like.

WHAT THE AGENT DID. It retreated. `_doomed_mute_pivot` read the active as MUTE
because the Grass was not in HAND, paid one of the Ogerpon's two Grass for the
retreat fee and put a fresh Fezandipiti ex in front. Four actions later the same
turn played the Unfair Stamp that was in hand the whole time, drew the Grass --
and attached it to a benched body, because the attacker was on the bench by then
and a turn only has one retreat.

THE TWO DEFECTS, and they are independent:

  * THE PLAN COULD NOT SEE THE LOSS. `_opponent_reply` projects one attack onto
    one body, so it answered "2 prizes, they do not close it". The truth was
    that a benched Meowth ex sat at 40 HP with two Froslass on the field: it
    died to the drip alone, for two more prizes, with no attack involved. Four
    prizes against the three they needed -- the turn had no tomorrow at all.
    `_op_prize_harvest` is that arithmetic.

  * THE WALL WAS PRICED AGAINST TURNS THAT DID NOT EXIST. Every "the active is
    doomed, put something tougher in front" pivot buys time. When the knockout
    in front of us ENDS the game there is no time to buy, and the retreat also
    burns the energy the attack was going to count.
    `_active_closes_with_one_charge` is that veto.

The first test pins the projection, the second pins the choice, and the third
pins the ceiling: the veto must NOT fire when the knockout does not close the
game, which is the board every other Marnie turn looks like.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m                                            # noqa: E402
import golden_corpus as gc                                  # noqa: E402
from state_builder import Scenario, pk, C, G                # noqa: E402
from cg.api import OptionType                               # noqa: E402
from ptcg.calc.damage import _op_prize_harvest              # noqa: E402
from ptcg.state.agent_state import AGENT_STATE              # noqa: E402

GRIMMSNARL_EX = 648
MUNKIDORI = 112
FROSLASS = 104
IMPIDIMP = 646
DARK = int(m.EnergyType.DARKNESS)


def _the_board(hand, own_prizes=2, active_grass=2, meowth_hp=40):
    """registro_009 step 150. `hand` is what we are holding when we choose."""
    return (Scenario(turn=9, step=150, tac=1, own_prizes=own_prizes,
                     supporter_played=True, stadium_played=True)
            .my_active(pk(m.Teal_Mask_Ogerpon_ex, hp=130,
                          energies=[G] * active_grass))
            .my_bench(pk(m.Meowth_ex, hp=meowth_hp),
                      pk(m.Meowth_ex, hp=70),
                      pk(m.Teal_Mask_Ogerpon_ex, hp=130, energies=[G, G]),
                      pk(m.Fezandipiti_ex))
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
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                  m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard())


def _choice(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def test_the_harvest_counts_the_prizes_that_need_no_attack():
    """Two Froslass and a 40 HP Meowth ex: two prizes with nothing attacking.

    Four in total once their Grimmsnarl ex takes the active, against the three
    they needed. `_opponent_reply` on its own answers 2 and `op_wins_next=False`
    -- which is the reading that made the agent play for a turn it did not have.
    """
    gc.reset_agent(m)
    obs = _the_board([m.Unfair_Stamp, m.Ultra_Ball, m.Meganium]).menu_hand(
        with_retreat=True).build()
    m.agent(obs)                       # refreshes the drip / movable flags

    st = m.to_observation_class(obs).current
    my_state, op_state = st.players[0], st.players[1]
    harvest = _op_prize_harvest(my_state, op_state, 5)

    assert AGENT_STATE._op_chip_per_round == 40, "two Froslass, two checkups"
    # The 40 HP Meowth ex dies to the drip on its own, and it is an ex.
    assert harvest.off_board >= 2, harvest
    # ... plus the active, which their Grimmsnarl ex finishes.
    assert harvest.kills_active
    assert harvest.prizes >= 4, harvest
    assert AGENT_STATE.turn_plan.op_prizes_offboard >= 3
    assert AGENT_STATE.turn_plan.they_close_it_without_attacking, \
        "three prizes are within reach of the drip and the moved counters alone"
    # ... and it stays DATA: `op_wins_next` keeps HEAD's reading, because the
    # 0.50% of the frozen corpus it fires on is the licence `do_or_die` states.
    # See the block that computes it in ptcg/turn/game_plan.py.
    assert not AGENT_STATE.turn_plan.op_wins_next


def test_two_munkidori_finish_two_different_bodies():
    """ADRENA-BRAIN IS A POOL, NOT A SINGLE FINISHER.

    `_ventana_de_regalo` prices the moved counters as if they could only ever
    kill one body, which is the honest reading of "is THIS body doomed" and the
    wrong one for "how many prizes is the board worth". Each charged Munkidori
    is its OWN move of up to 3 counters onto ONE of our Pokemon, so two of them
    take two separate bodies in the same turn -- which is how game 2 of the
    marnie series ended.

    Both Meowth ex are left inside one move of the drip: 70 HP, 40 of Freezing
    Shroud, 30 left = exactly three counters each. One Munkidori cashes one, two
    cash both.
    """
    gc.reset_agent(m)
    obs = _the_board([m.Ultra_Ball], meowth_hp=70).menu_hand(
        with_retreat=True).build()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    harvest = _op_prize_harvest(st.players[0], st.players[1], 5)
    assert AGENT_STATE._op_movable_cap == 60, "two charged Munkidori"
    # Both Meowth ex (2 prizes each) plus the active their Grimmsnarl ex takes.
    assert harvest.off_board >= 4, harvest
    assert harvest.prizes >= 6, harvest


def test_it_does_not_retreat_the_body_that_is_one_grass_from_the_win():
    """The Unfair Stamp is in hand and the deck still holds Grass: dig, do not
    hand the front spot away.

    The hand is the record's minus the Meganium, which was in it and which the
    simulator did NOT offer -- a Stage 2 with no Bayleef under it is not a play.
    `menu_hand` emits one PLAY per card in hand, so leaving it in would measure
    a choice the engine never gives.
    """
    gc.reset_agent(m)
    obs = _the_board([m.Unfair_Stamp, m.Ultra_Ball]).menu_hand(
        with_retreat=True).build()
    picked = _choice(obs)
    assert picked["type"] != int(OptionType.RETREAT), \
        "it retreated the attacker that wins the game"
    assert picked["type"] == int(OptionType.PLAY)
    assert obs["current"]["players"][0]["hand"][picked["index"]]["id"] \
        == m.Unfair_Stamp


def test_with_the_grass_in_hand_it_charges_the_active_and_wins():
    """The other side of the same turn: once the dig has produced the Grass, the
    charge goes to the body in FRONT -- the one whose Myriad Leaf Shower is
    lethal -- and not to a benched twin."""
    gc.reset_agent(m)
    obs = _the_board([m.Basic_Grass_Energy, m.Ultra_Ball]).menu_hand(
        with_retreat=True, with_attachment=True).build()
    picked = _choice(obs)
    assert picked["type"] != int(OptionType.RETREAT)
    assert picked["type"] == int(OptionType.ATTACH), picked
    assert picked["inPlayArea"] == int(m.AreaType.ACTIVE), \
        "the Grass belongs on the attacker that closes the game"


def test_the_veto_does_not_fire_when_the_knockout_does_not_close_the_game():
    """THE CEILING. With four prizes left the same knockout takes two of them
    and the game goes on -- so the wall is worth exactly what it always was and
    the pivot keeps its behaviour. Without this the rule would be "never retreat
    a chargeable Ogerpon", which is a different and much larger change."""
    gc.reset_agent(m)
    obs = _the_board([m.Unfair_Stamp, m.Ultra_Ball, m.Meganium],
                     own_prizes=4).menu_hand(with_retreat=True).build()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    my_state, op_state = st.players[0], st.players[1]
    assert not m._active_closes_with_one_charge(
        my_state, op_state,
        st,
        {m.Unfair_Stamp: 1, m.Ultra_Ball: 1, m.Meganium: 1}, {},
        4, 4, 4, False, False, 4)


def test_the_veto_needs_a_card_that_can_still_find_the_grass():
    """No Grass in hand, nothing in hand that reaches one: the active really is
    mute and the pivot is the only play left."""
    gc.reset_agent(m)
    obs = _the_board([m.Ultra_Ball, m.Meganium, m.Boss_Orders]).menu_hand(
        with_retreat=True).build()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    my_state, op_state = st.players[0], st.players[1]
    assert not m._active_closes_with_one_charge(
        my_state, op_state,
        st,
        {m.Ultra_Ball: 1, m.Meganium: 1, m.Boss_Orders: 1}, {},
        2, 4, 4, False, False, 4)
