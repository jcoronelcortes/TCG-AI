"""The Night Stretcher recovers Meowth ex and the same turn BENCHES it.

Sequencing error (user, registro_012 step 77, episode 91179054 vs Mega Starmie
ex, LOST). Turn 12, six prizes to three against us:

    US                                         OPPONENT
    active  Teal Mask Ogerpon ex 210/210, 4 {G} active  Mega Starmie ex 330/330
    bench   Dipplin 80/80, 1 {G}                bench   Mega Starmie ex, Cinderace,
    hand    Forest x2, Dipplin, Bayleef                 Mega Starmie ex, Staryu
    discard Meowth ex, Basic {G} x2              prizes 3 (ours: 6)
    Supporter slot FREE, three Lillie's Determination alive in the deck.

The turn played the Night Stretcher and its selection chose **Meowth ex** out of
the discard -- `fetch_supporter_from_deck` of `_RULES_NS_MEOWTH`, whose own
comment says "recover Meowth ex TO PUT IT DOWN so Last-Ditch fetches a
Supporter". Then the play ladder refused to bench it: the arm
`_active_ready_attacker and field_counts == 0` (`play.py`, the log 86511741 vs
Mega Abomasnow arm) vetoed the body because the active could already attack, and
the turn closed with Myriad Leaf Shower for 150 into a 330 HP wall -- no prize,
no Supporter, the Stretcher in the discard and the Meowth ex dead in hand. The
four refill arms that step in front of that veto all missed for reasons that had
nothing to do with the board: 21500 wants a hand of <= 4 cards and the Stretcher
had just made it FIVE, 21400 a bench of <= 1 with a doomed active, 21450 an
active that cannot pay its own retreat, 21350 an attack read as inert.

The fix is one layer above all of them, in `finalize.py`: the flags that mark a
body as ALREADY PAID FOR (`_ub_meowth_pending`, `_ub_fez_pending`) used to be
armed only when the fetch prompt belonged to an `Ultra_Ball`. What commits the
turn is not WHICH card did the fetching but that a card of ours spent itself to
put that body in hand, so the guard now reads the prompt (`select.effect is not
None and context == TO_HAND`) and the same chain works out of the discard, out
of the deck, and for any recovery or search card in any deck.

The scenario is FABRICATED with the StateBuilder rather than replayed from
`records/`, which is transient local data (`utils/split_turns.py` rewrites it
with every new game) -- the same reason `test_fez_pending_synthetic.py` exists.

Sibling of [[no-meowth-si-hay-atacante-listo]] (the `_ub_meowth_pending`
exception this generalises) and of `test_both_copies_of_the_fetch_ladder_agree`:
the half that PAYS and the half that EXECUTES have to answer the same board the
same way.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk, G

MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
FOREST = m.Forest_of_Vitality
STRETCHER = m.Night_Stretcher
GRASS = m.Basic_Grass_Energy
LILLIE = m.Lillie_Determination

MEGA_STARMIE = 1031
STARYU = 1030
CINDERACE = 666

TURN = 12


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


def _field(esc):
    """The board of step 77: a ready active that does NOT knock out, one body on
    the bench and the opponent two prizes from closing the game."""
    return (esc
            .my_active(pk(OGERPON, energies=[G, G, G, G], fisicas=4))
            .my_bench(pk(DIPPLIN, energies=[G], fisicas=1, pre_evo=[APPLIN]))
            .op_active(pk(MEGA_STARMIE, hp=330, max_hp=330))
            .op_bench(pk(MEGA_STARMIE, hp=330, max_hp=330),
                      pk(CINDERACE, hp=160, max_hp=160),
                      pk(MEGA_STARMIE, hp=330, max_hp=330),
                      pk(STARYU, hp=70, max_hp=70))
            .op_zones(hand=5, deck=31, prizes=3))


def _menu_recover(supporter_played=False):
    """Menu A: the Night Stretcher's TO_HAND prompt over our own discard.

    The options are Meowth ex and a Basic {G}: the same choice the record had,
    so picking the body is a decision and not the only door.
    """
    esc = Scenario(turn=TURN, step=77, tac=4, own_prizes=6,
                   supporter_played=supporter_played)
    return (_field(esc)
            .my_hand(FOREST, DIPPLIN, FOREST, BAYLEEF)
            .my_discard(MEOWTH, GRASS, GRASS)
            .deck(LILLIE, CHIKORITA, APPLIN)
            .fetch_discard(STRETCHER, only={MEOWTH, GRASS})
            .rest_to_discard()
            .build())


def _menu_after_recovery(supporter_played=False):
    """Menu B: the next MAIN, with the recovered Meowth ex in hand.

    Five cards in hand -- exactly the size the Stretcher itself produced, and the
    one that put the board out of reach of the `hand <= 4` refill arm.

    `menu_hand()` emits one PLAY per card in hand; the simulator did not, and the
    difference is not noise, it is the contest under test. In the record the menu
    held ONE single PLAY -- the Meowth ex -- against the attack, because our own
    Forest of Vitality was already the stadium in play (a second copy cannot
    replace itself) and Dipplin and Bayleef are evolutions, which arrive as
    EVOLVE options over a body in play and there was none they fit (the bench
    Dipplin is already evolved, and no Chikorita is in play). So the extra PLAYs
    are pruned: what is measured here is body-versus-attack.
    """
    esc = Scenario(turn=TURN, step=77, tac=5, own_prizes=6,
                   supporter_played=supporter_played)
    obs = (_field(esc)
           .my_hand(FOREST, DIPPLIN, BAYLEEF, CHIKORITA, MEOWTH)
           .my_discard(STRETCHER, GRASS, GRASS)
           .stadium(FOREST)
           .deck(LILLIE, APPLIN)
           .rest_to_discard()
           .menu_hand(with_attack=True)
           .build())
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] != int(m.OptionType.PLAY)
        or me["hand"][o["index"]]["id"] == MEOWTH]
    return obs


def _chosen(obs, choice):
    o = obs["select"]["option"][choice[0]]
    if o["type"] == int(m.OptionType.PLAY):
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        return ("PLAY", me["hand"][o["index"]]["id"])
    if o["type"] == int(m.OptionType.CARD):
        idx = o["index"]
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        return ("CARD", me["discard"][idx]["id"])
    if o["type"] == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    return (o["type"], None)


# ---------------------------------------------------------------------------
# 1. The scenario: without these conditions there is no sequencing error
# ---------------------------------------------------------------------------

def test_the_scenario_has_a_ready_active_that_takes_no_prize_and_a_free_slot():
    obs = _menu_after_recovery()
    m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    # The active can attack: that is what used to veto the body.
    assert any(o["type"] == int(m.OptionType.ATTACK)
               for o in obs["select"]["option"])
    # ...and its attack does NOT knock out a 330 HP Mega Starmie ex.
    assert m.plan.remain_hp is None or m.plan.remain_hp > 0
    assert len([b for b in me["bench"] if b]) < 5      # the Meowth fits
    assert not any(b and b["id"] == MEOWTH for b in me["bench"])
    assert obs["current"]["supporterPlayed"] is False
    assert len(me["hand"]) == 5                        # over the `hand <= 4` arm


# ---------------------------------------------------------------------------
# 2. The chain, menu by menu
# ---------------------------------------------------------------------------

def test_menu_a_the_stretcher_recovers_the_meowth_and_arms_the_pending_flag():
    obs = _menu_recover()
    assert _chosen(obs, m.agent(obs)) == ("CARD", MEOWTH)
    assert m._ub_meowth_pending is True


def test_menu_b_the_recovered_body_goes_down_instead_of_the_chip_attack():
    m.agent(_menu_recover())                  # it arms the flag
    obs = _menu_after_recovery()
    assert _chosen(obs, m.agent(obs)) == ("PLAY", MEOWTH)


# ---------------------------------------------------------------------------
# 3. Controls
# ---------------------------------------------------------------------------

def test_without_the_flag_the_old_veto_still_attacks_and_strands_the_body():
    """The bug, pinned: it is the flag that carries this board, not the ladder.

    With `_ub_meowth_pending` off, the `_active_ready_attacker` veto wins again
    and the turn closes on the chip attack with the Meowth ex dead in hand --
    which is what the record did.
    """
    m._ub_meowth_pending = False
    obs = _menu_after_recovery()
    assert _chosen(obs, m.agent(obs))[0] == "ATTACK"


def test_with_the_supporter_already_played_the_body_is_not_exposed():
    """The guard of the override is untouched: a Last-Ditch whose Supporter can
    no longer be played does not buy a 2-prize body on the bench."""
    m.agent(_menu_recover(supporter_played=True))
    obs = _menu_after_recovery(supporter_played=True)
    assert _chosen(obs, m.agent(obs))[0] == "ATTACK"
