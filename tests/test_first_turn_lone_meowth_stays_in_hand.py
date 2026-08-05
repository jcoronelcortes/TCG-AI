"""Going FIRST, the lone Meowth ex is not spent to fill the bench.

Scenario (`records/registro_001_pasos_006_hasta_009.json`, step 7, episode
89627609 vs Dragapult -- WON with a mistake):

    US                                    RIVAL (Dragapult)
    active  Fezandipiti ex 210            active  Budew 30
    bench   --                            bench   Dreepy 70
    hand    **Meowth ex**, Lillie's Determination x2,
            Dawn, Forest of Vitality, Hydrapple ex (unplayable)

It is turn 1 and we go first. Every per-card veto worked: the
`no-meowth-para-lillie` rule left the Meowth ex at -1 because there were two
Lillie's in hand. Then the ANTI-EMPTY-BENCH SAFETY NET
([[nunca-terminar-turno-banca-vacia]]) lifted it to 200 and benched it anyway.

Why that net was wrong here. What it protects against is losing ON THE SPOT: with
a single body in play, a rival KO leaves us with nobody to promote. Going FIRST
our turn 1 does not attack and the opponent answers with ONE attachment, and
against the tough openers of the deck no first-turn attack in the format gets
there:

    Teal Mask Ogerpon ex 210 · Fezandipiti ex 210 · Meowth ex 170 · Tapu Bulu 140

So the empty bench costs NOTHING, and keeping the Meowth ex in hand is strictly
better: on the bench it is a free 2-prize body, and the Supporter its Last-Ditch
Catch fetches gets shuffled back into the deck by the very Lillie's we play on
turn 2 ([[no-meowth-para-lillie-si-ya-en-mano]]).

Rule (user): **turn 1 going first, behind one of those four bodies, if the ONLY
Pokemon left to bench is a Meowth ex, it is not benched -- we end the turn.**

It is UNCONDITIONAL (user, asked explicitly): it holds even with NO Lillie's in
hand and copies alive in the deck, which is the case the `_meowth_devel_lillie`
engine was built for (21800: bench the Meowth ex, Last-Ditch a Lillie's, arrive
at turn 2 with a hand -- log 88461779). On THIS turn the user's rule outranks
it, which is why the flag is applied as the ENVELOPE of the Meowth ex branch
and not as one more link in its chain of vetoes
([[techo-en-envoltorio-no-al-final-de-la-funcion]]).

THE ONE EXCEPTION the user named: a lone **Meowth ex** (170 HP) in the active
spot against an opposing **Solrock**. Cosmic Beam costs a single {F} and hits
for 70; with the four Premium Power Pro (+30 per copy, Items) it is the only
opening the opponent can assemble on their first turn that reaches 170 -- and
with an empty bench that is an instant loss. There the second Meowth ex DOES go
down as a body.

It fires on SEEING the Solrock, not on the arithmetic: how many Power Pros they
hold is invisible to us, and the {F} weakness of the Meowth ex does NOT double
the hit (the attack ignores Weakness and the simulator honours it -- measured,
see `Solrock` in ptcg/cards/ids.py). The exception is therefore a cheap safety
valve on a rare line, not a damage computation.

Boundaries of the rule:

  * it is for going FIRST only. Going second our first turn is turn 2: the
    opponent has already attacked once and has a second attachment ready, so the
    reasoning about a single energy does not hold;
  * the fragile openers of the deck (Chikorita 70, Applin 60...) are OUT: those
    do get donked, and the net has to keep working for them
    ([[matchpoint-el-gate-no-arbitra-mide-la-frecuencia]] -- the guard is on the
    body, not on the turn number);
  * with any OTHER basic in hand that one goes down instead: it is not a 2-prize
    card, so there is nothing to save;
  * a donk the damage model actually projects (`_meowth_antidonk_now`) lifts the
    hold too, so the net keeps working wherever it really applies.

Implementation: a single board flag, `_ft_hold_lone_meowth`, computed once in
`agent()` next to `_meowth_antidonk_now` and read by the three places that
decide the same thing: the envelope of the Meowth ex PLAY branch, the
anti-empty-bench net (which must not pick the Meowth) and the dead-turn Meowth
rescue (which must not fire at all).
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
from tests.state_builder import Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_t1_lone_meowth_stays_in_hand_step7.json")

MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
CHIKORITA = m.Chikorita
LILLIE = m.Lillie_Determination
FOREST = m.Forest_of_Vitality
BUDEW = m.Budew
SOLROCK = m.Solrock


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
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs_fixture():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _idx_play(obs, card_id):
    """Index of the 'PLAY <card_id>' option in the main menu, or -1."""
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


def _plays_meowth(obs):
    idx = _idx_play(obs, MEOWTH)
    assert idx >= 0, "el escenario no ofrece bajar Meowth ex: no mide nada"
    return m.agent(obs)[0] == idx


def _scenario(active, hand, op_active=BUDEW, turn=1, first_player=0):
    """Turn 1 going first: empty bench and a single body in hand."""
    return (Scenario(turn=turn, step=7, tac=1, first_player=first_player,
                      energy_played=True)
            .my_active(pk(active))
            .my_hand(*hand)
            .op_active(pk(op_active))
            .op_bench(pk(m.Dreepy))
            .op_zones(hand=6, deck=46, prizes=6)
            .menu_hand()
            .build())


# ---------------------------------------------------------------------------
# 1. The record: the scenario, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_our_first_turn_going_first_with_an_empty_bench():
    o = _obs_fixture()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert cur["turn"] == 1 and cur["firstPlayer"] == cur["yourIndex"]
    assert mine["active"][0]["id"] == FEZ and mine["active"][0]["hp"] == 210
    assert [b for b in mine["bench"] if b] == []
    assert sum(1 for c in mine["hand"] if c["id"] == LILLIE) == 2
    assert _idx_play(o, MEOWTH) >= 0, "el paso ofrecia bajar el Meowth ex"


def test_the_lone_meowth_is_not_benched_behind_a_fezandipiti():
    """The regression of the record: it used to bench it at 200."""
    assert not _plays_meowth(_obs_fixture())


# ---------------------------------------------------------------------------
# 2. The four tough openers hold the Meowth; a fragile one does not
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("active", [OGERPON, FEZ, TAPU, MEOWTH])
def test_the_tough_openers_keep_the_lone_meowth_in_hand(active):
    assert not _plays_meowth(_scenario(active, [MEOWTH, FOREST]))


def test_a_fragile_opener_still_benches_it():
    """Chikorita has 70 HP: there the donk is real and the net has to work."""
    assert _plays_meowth(_scenario(CHIKORITA, [MEOWTH, FOREST]))


# ---------------------------------------------------------------------------
# 3. The Solrock exception
# ---------------------------------------------------------------------------

def test_a_lone_meowth_against_solrock_does_bench_the_second_one():
    """Cosmic Beam + Premium Power Pro is the only turn-1 donk on 170 HP."""
    assert _plays_meowth(_scenario(MEOWTH, [MEOWTH, FOREST],
                                   op_active=SOLROCK))


def test_solrock_only_lifts_the_hold_for_the_meowth_active():
    """Behind 210 HP the Solrock line does not reach: the hold stands."""
    assert not _plays_meowth(_scenario(FEZ, [MEOWTH, FOREST],
                                       op_active=SOLROCK))


def test_the_meowth_active_holds_against_any_other_opener():
    assert not _plays_meowth(_scenario(MEOWTH, [MEOWTH, FOREST]))


# ---------------------------------------------------------------------------
# 4. Boundaries: another body in hand, and going second
# ---------------------------------------------------------------------------

def test_with_another_basic_in_hand_the_hold_does_not_fire():
    """The hold only covers the case the user described: the Meowth ex as the
    ONLY body in hand. With a Chikorita alongside it there is nothing to save --
    that one can fill the bench -- so the development ladder decides again as it
    always did (here it still prefers the Meowth ex, for its Last-Ditch fetch).
    If the hold leaked here the Meowth ex would be vetoed and the Chikorita
    would win the menu, so this asserts the boundary and not the ladder."""
    assert _plays_meowth(_scenario(FEZ, [MEOWTH, CHIKORITA, FOREST]))


def test_going_second_the_rule_does_not_apply():
    """Our first turn going second is turn 2: the opponent already attacked
    once and has a second attachment ready."""
    assert _plays_meowth(_scenario(FEZ, [MEOWTH, FOREST],
                                   turn=2, first_player=1))
