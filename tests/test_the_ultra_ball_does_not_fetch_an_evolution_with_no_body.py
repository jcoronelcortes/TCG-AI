"""The Ultra Ball does not fetch an evolution that has nothing to evolve TODAY.

Scenario (`records/registro_004_pasos_037_hasta_060.json`, episode 91184399,
turn 4 vs Marnie -- WON in spite of this):

    US (6 prizes)                              RIVAL (Marnie)
    active Fezandipiti ex 210, 1 {G}           active Marnie's Grimmsnarl ex 320
    bench  Meowth ex 140/170                   bench  Munkidori x2, Impidimp
           **Chikorita, played THIS turn**     stadium Spikemuth Gym (theirs)
    hand   Ultra Ball, Unfair Stamp, Meganium, Night Stretcher
    bench 2/5: THREE free seats, no Forest of Vitality anywhere

The first Ultra Ball of the turn had just benched that Chikorita (step 41). The
second one (step 43) paid its two cards with the **Meganium** of our own line
and a Night Stretcher, and the search (step 44) took a **BAYLEEF** -- the
evolution of a body that came into play this very turn, and which therefore
cannot be evolved until the next one. Three actions later the Unfair Stamp of
that same turn shuffled it back into the deck: two Items, four cards and the
line's own Stage 2 in the discard, for nothing.

Why it fired. The number that won the search is not a valuation, it is a CLAMP:
`_evo_link_state` (`ptcg/cards/lines.py`) reads the CURRENT field, saw a
Chikorita on the bench with no Bayleef anywhere and called the Bayleef the
missing LINK of the line -- `score = max(score, 900)` in the fetch ladder --
over the Applin (650) that any of the three free seats could have put down at
once. The clamp is right about the SHAPE of the line and blind to the calendar:
a body that came down this turn is not a seat this turn.

The other half of the same board is that the two menus disagreed. The VALUE
menu (`_eval_ub_best_target`) never priced that Bayleef: its Meganium-line
branches hang off `_ub_evolvable`, the start-of-turn snapshot, which has no
Chikorita in it. It bought the Item for an **Applin** at 450 and the fetch
ladder spent it on a Bayleef -- exactly what the gates of `_offer` exist to
stop (see [[coherencia-menu-prompt-habilidades-disponibles]]).

`_ub_target_cannot_be_worn` is what settles it, and it is the THIRD gate of a
sentence the other two already write: the Ultra Ball costs two cards from hand,
so it is only worth that price for a card the turn can USE. A card enters play
by one of three doors -- it is not already in hand
(`_ub_target_covered_by_hand`), it is a Basic and there is a free bench seat
(`_ub_target_has_no_seat`), or it is an evolution and a body of its line was
already in play when the turn started (this one). Both menus ask all three, and
the fetch ladder asks them LAST, after the link clamps, so no promotion can
talk over them.

Deck-agnostic: the stage and the pre-evolution are read off the card data
(`_evo_body_in_play` resolves `evolvesFrom` by NAME, so two printings of the
same Pokemon both count as a seat). It names no card, no line and no matchup.

The CONTROL that keeps the rule honest is the mirror board of
tests/test_the_ultra_ball_fetches_the_link_not_a_new_line.py: same fresh
Chikorita, but with a **Forest of Vitality** on the field, which lets a body
that came down this turn evolve at once -- and there the Bayleef IS the right
search. `_ub_wearable_bodies` is what keeps both true, and it also opens the
door for a Forest still IN HAND: one Item away from lifting the restriction,
which is the premise of the one-turn chains this same ladder prices.

See [[ultraball-solo-si-el-objetivo-se-usa-este-turno]],
[[ub-el-cuerpo-sin-asiento-no-se-compra]] and
[[la-regla-general-va-antes-que-su-caso-especial]].
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
            / "marnie_the_ultra_ball_does_not_fetch_an_evolution_with_no_body_step44.json")

_OPENING_STEP = 37
_FETCH_STEP = 44


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _replay(frames, until=_FETCH_STEP):
    """The turn as it happened, action by action, up to `until`.

    A single frame will not do, and not because of the board: the Chikorita
    goes down at step 41, so the START-OF-TURN field -- the only thing that
    knows it was not there -- is built by the agent on the FIRST menu of the
    turn (step 37) and would otherwise be snapshotted with the Chikorita
    already on the bench, which is the very confusion under test.
    """
    choice = None
    for st in sorted(frames):
        if st > until:
            break
        choice = m.agent(copy.deepcopy(frames[st]))
    return choice


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _fetchable_ids(obs):
    return [obs["select"]["deck"][o["index"]]["id"]
            for o in obs["select"]["option"]]


def _fetched_id(obs, choice):
    opt = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


def _with_forest(frames):
    """The same turn with a Forest of Vitality of ours on the field."""
    for obs in frames.values():
        obs["current"]["stadium"] = [
            {"id": m.Forest_of_Vitality, "playerIndex": 0, "serial": 999}]
    return frames


# ---------------------------------------------------------------------------
# 1. The board that produced the mistake, read off the record
# ---------------------------------------------------------------------------

def test_the_chikorita_came_down_this_very_turn_and_there_is_no_forest():
    frames = _frames()

    opening = _mine(frames[_OPENING_STEP])
    assert [p["id"] for p in opening["active"]] == [m.Fezandipiti_ex]
    assert [p["id"] for p in opening["bench"]] == [m.Meowth_ex], (
        "el turno EMPIEZA sin Chikorita: ese es el dato que el bug ignora")

    obs = frames[_FETCH_STEP]
    mine = _mine(obs)
    fresh = [p for p in mine["bench"] if p["id"] == m.Chikorita]
    assert len(fresh) == 1 and fresh[0]["appearThisTurn"], (
        "el Chikorita entro en juego ESTE turno: no puede evolucionar hoy")
    # El estadio en mesa es el RIVAL (Spikemuth Gym): no hay Forest of Vitality
    # ni en la mesa ni en la mano, que es lo unico que levantaria la
    # restriccion del cuerpo recien bajado.
    assert all(s["id"] != m.Forest_of_Vitality
               for s in (obs["current"].get("stadium") or []))
    assert all(c["id"] != m.Forest_of_Vitality for c in mine["hand"])

    # Both are on the menu: the search really had to choose between them.
    ofrecidas = _fetchable_ids(obs)
    assert m.Bayleef in ofrecidas and m.Applin in ofrecidas
    # And there is room for the Basic: nothing else explains taking the Bayleef.
    assert len(mine["bench"]) < (mine.get("benchMax") or 5)


# ---------------------------------------------------------------------------
# 2. The rule
# ---------------------------------------------------------------------------

def test_the_search_does_not_take_the_evolution_of_a_body_that_just_arrived():
    frames = _frames()
    choice = _replay(frames)
    assert _fetched_id(frames[_FETCH_STEP], choice) != m.Bayleef, (
        "el Bayleef no tiene sobre que evolucionar hasta el turno siguiente")


def test_it_takes_a_body_that_the_free_seat_can_put_down_today():
    frames = _frames()
    choice = _replay(frames)
    assert _fetched_id(frames[_FETCH_STEP], choice) == m.Applin


# ---------------------------------------------------------------------------
# 3. The control: with a Forest of Vitality the fresh body DOES evolve
# ---------------------------------------------------------------------------

def test_with_the_forest_on_the_field_the_link_is_the_right_search():
    frames = _with_forest(_frames())
    choice = _replay(frames)
    assert _fetched_id(frames[_FETCH_STEP], choice) == m.Bayleef, (
        "con Forest el Chikorita recien bajado evoluciona hoy: el eslabon vuelve"
        " a ser la busqueda correcta")


# ---------------------------------------------------------------------------
# 4. The gate, on its own
# ---------------------------------------------------------------------------

def test_the_gate_reads_the_stage_and_the_pre_evolution_off_the_card_data():
    from ptcg.decision.ultra_ball import (_ub_target_cannot_be_worn,
                                          _ub_wearable_bodies)

    # A Basic is never vetoed here: its door is the bench seat.
    assert not _ub_target_cannot_be_worn(m.Chikorita, {})
    assert not _ub_target_cannot_be_worn(m.Teal_Mask_Ogerpon_ex, {})
    # An evolution needs the body of its IMMEDIATELY lower stage.
    assert _ub_target_cannot_be_worn(m.Bayleef, {m.Fezandipiti_ex: 1})
    assert not _ub_target_cannot_be_worn(m.Bayleef, {m.Chikorita: 1})
    # One step, not the whole chain: a Meganium does not sit on a Chikorita.
    assert _ub_target_cannot_be_worn(m.Meganium, {m.Chikorita: 1})
    assert not _ub_target_cannot_be_worn(m.Meganium, {m.Bayleef: 1})
    # Neither does a card that is not a Pokemon have a body to sit on.
    assert not _ub_target_cannot_be_worn(m.Ultra_Ball, {})


def test_the_wearable_bodies_are_counted_one_body_at_a_time():
    from types import SimpleNamespace

    from ptcg.decision.ultra_ball import _ub_wearable_bodies

    def body(cid, fresh):
        return SimpleNamespace(id=cid, appearThisTurn=fresh)

    # The board of the record: the Chikorita came down this turn, so it is not
    # a seat -- even though the SPECIES is on the field.
    board = SimpleNamespace(active=[body(m.Fezandipiti_ex, False)],
                            bench=[body(m.Meowth_ex, False),
                                   body(m.Chikorita, True)])
    campo = {m.Fezandipiti_ex: 1, m.Meowth_ex: 1, m.Chikorita: 1}
    assert _ub_wearable_bodies(board, campo, {}, False) == {
        m.Fezandipiti_ex: 1, m.Meowth_ex: 1}

    # BODY BY BODY, not by species: with two Chikorita, one settled and one
    # fresh, the line does come out.
    board.bench.append(body(m.Chikorita, False))
    assert _ub_wearable_bodies(board, campo, {}, False)[m.Chikorita] == 1

    # A Forest -- on the field or one Item away in hand -- gives back the whole
    # current field: there is no "it came down this turn" any more.
    assert _ub_wearable_bodies(board, campo, {}, True) == campo

    # No board to read (the synthetic states of the unit tests): the
    # start-of-turn snapshot is the fallback.
    assert _ub_wearable_bodies(None, campo, {m.Applin: 1}, False) == {m.Applin: 1}
