"""The Ultra Ball does not pay two cards for a body the bench has no room for.

Scenario (`records/registro_004_pasos_039_hasta_063.json`, episode 90891885,
steps 50-57, turn 4 vs Alakazam -- LOST):

    US                                          RIVAL
    active Teal Mask Ogerpon ex 210, 3 Grass    active Alakazam ex 140, 1 energy
    bench  Fezandipiti ex / Dipplin (evolved     bench  Kadabra x2, Meganium, Abra
           this turn) / Applin / Teal Mask
           Ogerpon ex / Chikorita  -> **FULL**
    hand   Ultra Ball x2, **Lillie's Determination x2**, Meganium, Dawn,
           Teal Mask Ogerpon ex, Boss's Orders   (the turn's Supporter still free)

The agent played BOTH Ultra Balls and both fetched a **Meowth ex** -- a Basic,
with the bench full and no seat for it -- paying a Teal Mask Ogerpon ex, a Dawn,
the Meganium and the Boss's Orders as their cost. Four actions later the
Lillie's Determination that was in that same hand shuffled the two Meowth back
into the deck.

Why it fired. `_RULES_UB_MEOWTH` DID have a `full_bench` rule, but near the
bottom of the ladder, below every engine. And an engine had been armed earlier
in the same turn: at steps 44-49 the bench was still at 4, so
`_alakazam_dig_xerosic_engine` scored the Ultra Ball at 5950 and set
`AGENT_STATE._ub_engine_pivot_turn = True`. At step 49 a Chikorita came back
from the discard and filled the bench; the flag does not know that. At step 50
the Ultra Ball was played on the generic valuation and the fetch read the stale
flag: `engine_pivot_turn` (1300) fired over `the_turns_supporter_is_already_in_hand`
(two Lillie's in hand!) and over `full_bench`. A promise that outlived its
premise -- see [[el-puntero-del-plan-es-una-promesa-y-caduca]].

The fix asks the question about the CARD, not about the plan, so no engine can
talk over it, and asks it of EVERY target instead of only the Meowth ex:

  * `_ub_target_has_no_seat` -- a card enters play by one of two doors and the
    card data says which: a BASIC needs a free bench seat, an evolution needs a
    body of its line already in play. With no seat, a Basic cannot be played
    this turn at all. Deck-agnostic: it names no card, it reads the stage.
  * `_eval_ub_best_target` routes every target through it (`_offer`) and the
    `Ultra_Ball` fetch of `ptcg/turn/options/card.py` clamps the same targets to
    10, so the two menus cannot disagree.
  * `full_bench` moves up in `_RULES_UB_MEOWTH`, next to the other "the
    Last-Ditch cannot produce anything" vetoes (Watchtower, Supporter spent): a
    body that cannot be put down has no ability to use.

See [[ultraball-cancelar-si-banca-llena-sin-evo-en-mazo]],
[[ultraball-solo-si-el-objetivo-se-usa-este-turno]] and
[[coherencia-menu-prompt-habilidades-disponibles]].
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
            / "alakazam_the_ultra_ball_does_not_buy_a_body_with_no_seat_step52.json")

ULTRA_BALL = m.Ultra_Ball
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
OGERPON = m.Teal_Mask_Ogerpon_ex
CHIKORITA = m.Chikorita
APPLIN = m.Applin
DIPPLIN = m.Dipplin
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex
FEZ = m.Fezandipiti_ex
TAPU = m.Tapu_Bulu


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
    yield
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _replay_until(step):
    """The turn as it happened, action by action, up to `step`.

    The whole turn matters here and a single frame will not do: the
    start-of-turn snapshot (which body is evolvable), the bench filling up at
    step 49 and the engine flag armed at steps 44-49 are all state the agent
    builds as the turn runs.
    """
    frames = _frames()
    choice = None
    for st in sorted(frames):
        if st > step:
            break
        choice = m.agent(copy.deepcopy(frames[st]))
    return frames[step], choice


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _fetched_id(obs, choice):
    opt = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The board that produced the mistake, read off the record
# ---------------------------------------------------------------------------

def test_the_board_of_step_50_has_the_bench_full_and_lillie_in_hand():
    obs = _frames()[50]
    mine = _mine(obs)
    hand = [c["id"] for c in mine["hand"]]

    assert len(mine["bench"]) == 5, "la banca esta LLENA: no cabe ningun Basico"
    assert hand.count(ULTRA_BALL) == 2
    assert hand.count(LILLIE) == 2, "el refresco que el turno acabo jugando"
    assert obs["current"]["supporterPlayed"] is False
    # no Meowth ex in play, which is all the old engine branch asked about
    assert all(p["id"] != MEOWTH for p in mine["active"] + mine["bench"])


def test_the_deck_still_offers_the_meowth_the_record_took():
    """The choice is real, not forced: the Meowth ex was on the menu."""
    obs = _frames()[52]
    fetchable = [obs["select"]["deck"][o["index"]]["id"]
                 for o in obs["select"]["option"]]
    assert MEOWTH in fetchable
    # ...and so are the evolutions, which is what a full bench can still use
    assert HYDRAPPLE in fetchable and BAYLEEF in fetchable


# ---------------------------------------------------------------------------
# 2. The fix: the search no longer buys a body with nowhere to sit
# ---------------------------------------------------------------------------

def test_the_search_does_not_fetch_a_basic_with_the_bench_full():
    obs, choice = _replay_until(52)
    assert _fetched_id(obs, choice) != MEOWTH, (
        "con la banca LLENA un Basico no puede entrar en juego este turno: "
        "el Ultra Ball estaria pagando dos cartas por un cuerpo sin asiento")


def test_what_it_fetches_is_a_card_the_board_can_still_put_into_play():
    """With no seat left, only an evolution has a door open: it goes on top of
    a body that is already there."""
    obs, choice = _replay_until(52)
    fetched = _fetched_id(obs, choice)
    assert m._evolution_stage(fetched) >= 1, (
        f"con la banca llena la busqueda solo puede traer una evolucion, "
        f"no el Basico id={fetched}")


def test_the_second_ultra_ball_does_not_fetch_a_basic_either():
    """The record chained a second Ultra Ball into a second dead Meowth ex."""
    frames = _frames()
    obs, choice = _replay_until(52)
    # the fetch prompt of the SECOND Ultra Ball is outside this fixture, but
    # the rule is the same one and the board is the same: no seat, no Basic.
    mine = _mine(frames[52])
    assert len(mine["bench"]) == 5
    assert m._ub_target_has_no_seat(MEOWTH, 0) is True


# ---------------------------------------------------------------------------
# 3. The rule on its own: deck-agnostic and about the CARD, not the plan
# ---------------------------------------------------------------------------

def test_a_basic_has_no_seat_only_when_the_bench_is_full():
    for cid in (MEOWTH, OGERPON, CHIKORITA, APPLIN, TAPU, FEZ):
        assert m._ub_target_has_no_seat(cid, 0) is True
        assert m._ub_target_has_no_seat(cid, 1) is False


def test_an_evolution_always_has_a_door_open():
    """It goes ON TOP of a body already in play, so the bench being full does
    not shut it out -- whether that body is really there is the business of the
    fetch's own line rules."""
    for cid in (BAYLEEF, DIPPLIN, MEGANIUM, HYDRAPPLE):
        assert m._ub_target_has_no_seat(cid, 0) is False
        assert m._ub_target_has_no_seat(cid, 1) is False


def test_a_card_that_is_not_a_pokemon_is_not_ruled_out():
    """`_evolution_stage` answers None outside the Pokemon: the rule speaks
    only about bodies and never vetoes anything else."""
    assert m._ub_target_has_no_seat(m.Basic_Grass_Energy, 0) is False
    assert m._ub_target_has_no_seat(ULTRA_BALL, 0) is False


# ---------------------------------------------------------------------------
# 4. The value branch stops buying the Ultra Ball for a target with no seat
# ---------------------------------------------------------------------------

def test_the_valuation_does_not_price_a_body_that_cannot_be_played():
    """The other half of the coherence: the play menu must not buy the Item for
    a target the fetch is going to refuse."""
    obs = _frames()[50]
    mine = _mine(obs)
    hand_counts = {}
    for c in mine["hand"]:
        hand_counts[c["id"]] = hand_counts.get(c["id"], 0) + 1
    assert m._ub_target_covered_by_hand(MEOWTH, hand_counts, {}, 0) is False, (
        "no hay Meowth en mano: el veto que actua aqui es el del ASIENTO, "
        "no el de la copia repetida")
    assert m._ub_target_has_no_seat(MEOWTH, 0) is True
