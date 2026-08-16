"""The seat a search buys is evolvable today.

Origin (user, `records/registro_003_pasos_019_hasta_029.json`, step 22, episode
93495939 vs **Budew / Dragapult** -- WON):

    US (6 prizes)                          RIVAL (6 prizes)
    active  Teal Mask Ogerpon ex, 1 {G}    active  **Budew** 30/30
    bench   Teal Mask Ogerpon ex x2        bench   Dreepy x4
    hand    Unfair Stamp, Lillie's,
            Xerosic's, **Dipplin**,        stadium **OUR Forest of Vitality**
            **Hydrapple ex**, **Poke Pad**

        [0] PLAY Lillie's Determination   <-- played (shuffled the whole line back)
        [1] PLAY Xerosic's Machinations
        [2] END

THE STEP ITSELF IS NOT THE DEFECT, and reading it as one is the trap. Their
Budew's *Itchy Pollen* had the Item lock on, and the engine's own menu proves
it: the two Items in hand (the Poke Pad at hand index 5, the Unfair Stamp at 0)
are simply not among the options. The Pad could not be played, so no search was
declined. What the board DOES expose is the reading behind it -- the hand held
the Stage 1 and the Stage 2 of a line, our own Forest of Vitality was on the
field, and the only missing piece was a Basic sitting in the deck.

`Forest of Vitality`: *each player's {G} Pokemon can evolve into {G} Pokemon
during the turn they play those Pokemon, except during their first turn.* So
that Basic is not development for tomorrow: benched and evolved twice it is a
**Hydrapple ex the same turn**, and the Poke Pad -- which cannot fetch a Rule
Box card -- is the only card that buys the bottom of that line at all.

WHAT WAS MISSING, AND WHERE. Every "rush" rung in the package asks for the
pre-evolution to be ALREADY ON THE BOARD (`c.field.get(Applin, 0) >= 1`), and
none of them asked the same question of a seat the search itself is about to
buy. Four of the five searchers work around it with a rung of their own -- the
Ultra Ball's `_v_ub_applin_arrancar` (980 with Forest + Dipplin + Hydrapple ex
in hand), the Bug Catching Set's `line_from_scratch_rush`, Dawn's
`rush_with_dipplin`, the Night Stretcher's `applin_combo_completo` -- and the
POKE PAD had none. On that board its fetch ladder fell through to `fb_applin`,
**650**, the lowest rung it has, and lost to `fb_chikorita` at **800**: a lone
Basic that starts nothing this turn outranking the Basic that becomes a Stage 2
before the turn ends. Its play scorer told the same story, pricing the Pad at
`secure_applin`/`secure_chikorita` (12600 / 12800, the development band) instead
of `evolution_this_turn` (23000).

THE CORRECTION IS DECK-AGNOSTIC BY CONSTRUCTION. `_line_climb_from_hand` walks
the chain through `_direct_evolution_ids` -- the reverse index of `evolvesFrom`,
the whole card database -- and answers "how far up would the HAND carry this
body the moment it lands". `_line_in_play_from` is the guard the other rungs
spell out per deck (`field.get(Applin) + field.get(Dipplin) + ... == 0`),
written once and matched by NAME. Neither knows what our sixty cards are, so a
deck whose engine sits on another line gets the same reading without editing
either file.
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
from rule_trace import assert_reason, resolve  # noqa: E402
from state_builder import (FOREST_OF_VITALITY, G, Scenario, pk)  # noqa: E402

APPLIN = m.Applin
BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin
GRASS = m.Basic_Grass_Energy
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
POKE_PAD = m.Poke_Pad
TAPU = m.Tapu_Bulu
DREEPY = 119

# THE RECORD IT CAME FROM IS TRANSIENT AND WAS RE-HARVESTED AWAY THE SAME DAY.
# `records/` is git-ignored working data: a fresh harvest replaced episode
# 93495939 with another game and renumbered every file, so a test keyed on
# `registro_003_pasos_019_hasta_029.json` skipped silently instead of asserting
# anything -- exactly the failure mode "a test that pins the NAME of a transient
# record breaks when you harvest" describes. The observation is pinned in
# `tests/fixtures/` instead, which is the same thing every other record-derived
# test in this suite does.
_FIXTURE = ROOT / "tests" / "fixtures" / "the_seat_the_search_buys_step22.json"


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


# ---------------------------------------------------------------------------
# 1. The record: what step 22 actually offered
# ---------------------------------------------------------------------------

def test_step_22_never_offered_the_poke_pad_the_item_lock_was_on():
    """The step that raised the question declined nothing: with Budew active,
    the engine did not put either Item in the menu."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    assert obs["step"] == 22
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    # The board the question is about: the line's top half in hand, our own
    # Forest on the field, no Applin anywhere in play.
    hand = [c["id"] for c in mine["hand"]]
    assert POKE_PAD in hand and DIPPLIN in hand and HYDRAPPLE in hand
    assert [s["id"] for s in cur["stadium"]] == [FOREST_OF_VITALITY]
    field = [b["id"] for b in mine["active"] + mine["bench"]]
    assert APPLIN not in field and DIPPLIN not in field

    # ...and the reason nothing could be done about it: their active is Budew
    # and the menu holds no PLAY option for any Item in hand.
    assert theirs["active"][0]["id"] == m.Budew
    playable = {hand[o["index"]] for o in obs["select"]["option"]
                if o.get("type") == int(m.OptionType.PLAY)}
    assert POKE_PAD not in playable
    assert playable == {m.Lillie_Determination, m.Xerosic_Machinations}


# ---------------------------------------------------------------------------
# 2. The chain reader, on its own
# ---------------------------------------------------------------------------

def test_the_climb_counts_the_steps_the_hand_can_pay_for():
    """`_line_climb_from_hand` answers in STEPS, and only for links the hand
    actually holds."""
    assert m._line_climb_from_hand(APPLIN, {DIPPLIN: 1, HYDRAPPLE: 1}) \
        == (2, HYDRAPPLE)
    assert m._line_climb_from_hand(APPLIN, {DIPPLIN: 1}) == (1, DIPPLIN)
    # The top without the bridge is not a climb: the Hydrapple ex cannot sit on
    # an Applin.
    assert m._line_climb_from_hand(APPLIN, {HYDRAPPLE: 1}) == (0, APPLIN)
    assert m._line_climb_from_hand(APPLIN, {}) == (0, APPLIN)
    # The same code, the other line, with nothing written down about it.
    assert m._line_climb_from_hand(CHIKORITA, {BAYLEEF: 1, MEGANIUM: 1}) \
        == (2, MEGANIUM)


def test_a_body_already_standing_means_the_search_is_not_starting_the_line():
    assert not m._line_in_play_from(APPLIN, {OGERPON: 2})
    assert m._line_in_play_from(APPLIN, {APPLIN: 1})
    assert m._line_in_play_from(APPLIN, {HYDRAPPLE: 1})
    # A different line's body says nothing about this one.
    assert not m._line_in_play_from(APPLIN, {CHIKORITA: 1, MEGANIUM: 1})


# ---------------------------------------------------------------------------
# 3. The fetch: which card the Pad brings
# ---------------------------------------------------------------------------

class _StateStub:
    turn = 5


def _fetch_score(card_id, hand, field, bench_count=2, forest=True,
                 first_turn=False):
    m.AGENT_STATE.we_go_first = True
    m.AGENT_STATE.forest_in_play = forest
    m.AGENT_STATE.meganium_in_play = field.get(MEGANIUM, 0) >= 1
    state = _StateStub()
    state.turn = 1 if first_turn else 5
    ctx = m._CtxPPFetch(card_id, hand, field, bench_count, state)
    return resolve(m._RULES_PP_FETCH, [], ctx, default=50)


def test_the_pad_fetches_the_basic_that_finishes_today_not_the_one_that_starts():
    """The inversion the record exposed: Chikorita 800 over Applin 650."""
    hand = {DIPPLIN: 1, HYDRAPPLE: 1, POKE_PAD: 1}
    field = {OGERPON: 3}

    applin, why_applin = _fetch_score(APPLIN, hand, field)
    chikorita, _ = _fetch_score(CHIKORITA, hand, field)

    assert_reason(why_applin, "rush_seat_the_hand_completes")
    assert applin > chikorita, (applin, chikorita)


def test_one_step_is_worth_less_than_two_but_still_beats_a_bare_basic():
    """A Stage 1 today and a Stage 2 today are not the same purchase."""
    two, _ = _fetch_score(APPLIN, {DIPPLIN: 1, HYDRAPPLE: 1}, {OGERPON: 3})
    one, _ = _fetch_score(APPLIN, {DIPPLIN: 1}, {OGERPON: 3})
    bare, _ = _fetch_score(APPLIN, {}, {OGERPON: 3})
    assert two > one > bare


def test_without_the_forest_the_seat_is_for_tomorrow_and_the_rung_is_silent():
    """The stadium is the whole reason the Basic is playable-and-evolvable in
    one turn. Without it, nothing above the old fallback."""
    _, why = _fetch_score(APPLIN, {DIPPLIN: 1, HYDRAPPLE: 1}, {OGERPON: 3},
                          forest=False)
    assert_reason(why, "fb_applin")


def test_a_forest_still_in_hand_counts_the_same_as_one_on_the_field():
    """`_forest_disponible`, the reading the Ultra Ball already uses: the
    stadium can still be played this turn."""
    m.AGENT_STATE.we_go_first = True
    m.AGENT_STATE.forest_in_play = False
    m.AGENT_STATE.meganium_in_play = False
    ctx = m._CtxPPFetch(APPLIN,
                        {DIPPLIN: 1, HYDRAPPLE: 1, m.Forest_of_Vitality: 1},
                        {OGERPON: 3}, 2, _StateStub())
    _, why = resolve(m._RULES_PP_FETCH, [], ctx, default=50)
    assert_reason(why, "rush_seat_the_hand_completes")


def test_a_full_bench_has_no_seat_to_sell():
    _, why = _fetch_score(APPLIN, {DIPPLIN: 1, HYDRAPPLE: 1}, {OGERPON: 3},
                          bench_count=5)
    assert "rush_seat_the_hand_completes" not in " ".join(why)


def test_the_line_already_on_the_board_does_not_need_a_second_basic():
    """With an Applin standing, the Dipplin and the Hydrapple ex in hand have a
    seat without the search: buying another Basic is development."""
    _, why = _fetch_score(APPLIN, {DIPPLIN: 1, HYDRAPPLE: 1},
                          {OGERPON: 2, APPLIN: 1})
    assert why[-1].split("=")[0] != "rush_seat_the_hand_completes"


def test_the_first_turn_still_belongs_to_the_opening_rungs():
    """Forest's own text excludes it, and the opening ladder outranks it."""
    _, why = _fetch_score(APPLIN, {DIPPLIN: 1, HYDRAPPLE: 1}, {OGERPON: 1},
                          first_turn=True)
    assert_reason(why, "t1_applin")


# ---------------------------------------------------------------------------
# 4. The play: what the Pad is worth on that board
# ---------------------------------------------------------------------------

def _board(hand, deck, bench, forest=True):
    sc = (Scenario(turn=5, step=41, tac=1, first_player=0,
                   energy_played=True, stadium_played=True)
          .my_active(pk(OGERPON, energies=[G, G]))
          .my_bench(*bench)
          .my_hand(*hand)
          .op_active(pk(DREEPY, hp=70))
          .op_bench(pk(DREEPY, hp=70))
          .op_zones(hand=4, deck=35, prizes=6))
    if forest:
        sc = sc.stadium(FOREST_OF_VITALITY)
    return sc.deck(*deck).rest_to_discard().menu_hand().build()


def _pad_play_score(obs, monkeypatch):
    """The score the Pad's own branch produced, taken from the live turn.

    The DecisionContext is built once inside `agent()` and never handed out, so
    the honest way to read the Pad's price is to watch its scorer at the call
    site the turn actually uses (`ptcg/turn/options/play.py`).
    """
    import ptcg.turn.options.play as play
    seen = []
    real = play._score_poke_pad_play

    def _spy(ctx):
        value = real(ctx)
        seen.append(value)
        return value

    monkeypatch.setattr(play, "_score_poke_pad_play", _spy)
    m.agent(obs)
    assert seen, "the Poke Pad branch never ran"
    return max(seen)


def test_the_pad_is_priced_as_the_line_it_assembles_not_as_a_body_it_stocks(monkeypatch):
    """23000 (`evolution_this_turn`) and not 12600/12800 (the development
    band): what the Pad buys here is a Stage 2 before the turn ends."""
    obs = _board(hand=[POKE_PAD, DIPPLIN, HYDRAPPLE, GRASS],
                 deck=[APPLIN, APPLIN, CHIKORITA, BAYLEEF, MEGANIUM, TAPU],
                 bench=[pk(OGERPON, energies=[G])])
    assert _pad_play_score(obs, monkeypatch) >= 22000


def test_without_the_forest_the_same_hand_is_ordinary_development(monkeypatch):
    obs = _board(hand=[POKE_PAD, DIPPLIN, HYDRAPPLE, GRASS],
                 deck=[APPLIN, APPLIN, CHIKORITA, BAYLEEF, MEGANIUM, TAPU],
                 bench=[pk(OGERPON, energies=[G])],
                 forest=False)
    assert _pad_play_score(obs, monkeypatch) < 20000
