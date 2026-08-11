"""The KEEP floor of the forced discard is a ROLE, and only one card holds it.

Scenario (user, `registro_028_crustle_wall_8`, turn 7 action 4, vs the Crustle
wall). Their Xerosic's Machinations takes our hand of eight down to three:

    US                                      RIVAL
    active  Dipplin                         active  Crustle
    bench   Tapu Bulu, Chikorita,           bench   Mega Kangaskhan ex, Crustle,
            Teal Mask Ogerpon ex                    Dwebble, Mega Kangaskhan ex
    hand    **Lillie's Determination x2**,
            two Basic {G} Energy, Forest of
            Vitality, Fezandipiti ex,
            Meganium, Xerosic's Machinations

THE DEFECT. The ladder latches Lillie's on purpose -- `_lillie_protected_once`:
the first copy priced is the out and scores 2, the spare is released at 72,
ordinary fodder. Sixty lines further down the card-agnostic Supporter block ran

    if _dsv_live > 0 and _dsv_live > max(_dsv_rivals):
        score = min(score, DISCARD_SUPPORTER_LIVE_KEEP)      # = 2

and pulled the spare straight back to 2, because "the best Supporter I could
still play" is exactly as true of the second copy as of the first. **The latch
fired and the general rule undid it** -- [[la-regla-general-va-antes-que-su-caso-especial]] inverted, the general rule overwriting its own special case. The
turn then paid its five cards with a live Grass Energy while holding a second
Lillie's it could not play: a turn plays ONE Supporter.

`utils/duplicate_protection_audit.py` read it off all 118 discard menus of the
frozen corpus rather than off one board: FOUR records where two Lillie's came
out of that block sharing a 2 (006 t4, 007 t3, 016 t1, 028 t7). It was the
biggest group in the keep band, four times the standing Meowth ex flip.

THE FIX, and it names no card: the floor is handed out ONCE per card id per
menu (`_supp_live_keep_once`). The spares keep whatever price the ladder gave.

THE ASYMMETRY IS THE ARGUMENT. The DROP branch below it does NOT latch: "this
Supporter is dead and another one is live" is equally true of every copy, and
every copy really should go. Only a KEEP claims a job.

RADIUS, measured before and after over the same 118 menus: FOUR options changed
score in the whole corpus, all four the spare Lillie's, in exactly the four
records the census named. Nothing else moved -- not the Meowth ex pair (a Basic
is not in `_SUPP_PLAY_IDS`, so this block never speaks about it), not the two
Xerosic pairs (the value layer does not price the cap, and about the unpriced
this block says nothing).

Accepted flips in `tests/corpus/frozen_decisions.json` -- all four the same
sentence, a spare Lillie's leaving so that something the board can use stays:
006 t4 keeps Boss's Orders, 007 t3 and 028 t7 keep a Basic {G} Energy, 016 t1
keeps a Bug Catching Set.
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
import ptcg.turn.scoring as _scoring
from ptcg.cards import ids as _ids
from ptcg.cards.scoring import _SUPP_PLAY_IDS

_FINDING = (ROOT / "tests" / "fixtures"
            / "crustle_t7_the_second_copy_cannot_be_the_reason.json")
_CONTROL = (ROOT / "tests" / "fixtures"
            / "crustle_t12_the_spare_that_holds_no_role.json")

LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
LANA = m.Lanas_Aid
GRASS = m.Basic_Grass_Energy
XEROSIC = m.Xerosic_Machinations
FOREST = m.Forest_of_Vitality
MEGANIUM = m.Meganium
FEZ = m.Fezandipiti_ex

# The ladder's own price for a Lillie's the latch has already released. It is
# read from the branch, not guessed: `_lillie_protected_once` -> 72.
SOBRANTE = 72


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path=_FINDING):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _hand(obs):
    return [c["id"] for c in obs["current"]["players"][0]["hand"]]


def _discarded(obs, choice):
    hand = obs["current"]["players"][0]["hand"]
    return [hand[obs["select"]["option"][i]["index"]]["id"] for i in choice]


def _kept(obs, choice):
    dropped = list(_discarded(obs, choice))
    kept = []
    for cid in _hand(obs):
        if cid in dropped:
            dropped.remove(cid)
        else:
            kept.append(cid)
    return kept


def _run(obs=None):
    """Returns (obs, choice, [(card id, score) in menu order]).

    The scores are collected as a LIST, not a dict: a dict keyed by card id
    keeps only the last copy priced, which is precisely the reading this file
    exists to make -- the two copies of one card have to be visible separately
    or the defect is invisible.
    """
    obs = _obs() if obs is None else obs
    scores = []
    original = _scoring._TABLE[_scoring.OptionType.CARD]

    def _spy(tc, o, score):
        value = original(tc, o, score)
        if tc.context == m.SelectContext.DISCARD:
            scores.append((tc.card.id, value))
        return value

    _scoring._TABLE[_scoring.OptionType.CARD] = _spy
    try:
        return obs, m.agent(obs), scores
    finally:
        _scoring._TABLE[_scoring.OptionType.CARD] = original


def _scores_of(scores, card_id):
    return [s for cid, s in scores if cid == card_id]


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_turn_7_is_the_one_from_the_record():
    obs = _obs()
    cur = obs["current"]
    mine = cur["players"][0]
    op = cur["players"][1]

    assert cur["yourIndex"] == 0
    assert cur["turn"] == 7 and cur["turnActionCount"] == 4
    # THEIR card is what forces the discard: the effect belongs to seat 1.
    assert obs["select"]["context"] == int(m.SelectContext.DISCARD)
    assert obs["select"]["effect"]["id"] == XEROSIC
    assert obs["select"]["effect"]["playerIndex"] == 1
    # eight cards down to three
    assert obs["select"]["minCount"] == obs["select"]["maxCount"] == 5
    assert len(obs["select"]["option"]) == 8

    assert _hand(obs).count(LILLIE) == 2, "el hallazgo es la SEGUNDA copia"
    assert _hand(obs).count(GRASS) == 2
    assert sorted(_hand(obs)) == sorted(
        [LILLIE, LILLIE, GRASS, GRASS, FOREST, FEZ, MEGANIUM, XEROSIC])

    # the wall this deck cannot punch through with an ex, which is why the
    # Grass in hand is the turn's real fuel
    assert _ids.Crustle_Grass in [p["id"] for p in op["active"]]


def test_the_value_layer_makes_the_lillie_the_live_one():
    """The block only speaks when the layer has priced the card, and the KEEP
    branch only fires for the highest of the Supporters in hand. Both copies
    satisfy that sentence, which is the whole problem."""
    values = {}
    original = _scoring._TABLE[_scoring.OptionType.CARD]

    def _spy(tc, o, score):
        if tc.context == m.SelectContext.DISCARD and not values:
            values.update(tc._supp_values)
        return original(tc, o, score)

    _scoring._TABLE[_scoring.OptionType.CARD] = _spy
    try:
        m.agent(_obs())
    finally:
        _scoring._TABLE[_scoring.OptionType.CARD] = original

    assert values.get(LILLIE, 0) > 0
    # and the cap in the same hand is NOT priced: silence is not a zero
    assert XEROSIC not in values


# ---------------------------------------------------------------------------
# 2. The sentence: one copy holds the role, the other does not
# ---------------------------------------------------------------------------

def test_the_two_copies_do_not_share_the_protection():
    _obs_, _choice, scores = _run()
    lillies = _scores_of(scores, LILLIE)
    assert len(lillies) == 2
    assert len(set(lillies)) > 1, (
        f"las dos copias salieron con el mismo score {lillies}: el latch de la "
        f"escalera volvio a quedar anulado por el min() del bloque general")


def test_the_first_copy_keeps_the_floor_and_the_spare_the_ladder_price():
    _obs_, _choice, scores = _run()
    assert _scores_of(scores, LILLIE) == [
        _ids.DISCARD_SUPPORTER_LIVE_KEEP, SOBRANTE]


def test_the_spare_is_discarded_and_the_fuel_stays():
    obs, choice, _ = _run()
    kept = _kept(obs, choice)
    assert kept.count(LILLIE) == 1, (
        f"se guarda UNA Lillie's, no dos ni cero; quedo {kept}")
    assert kept.count(GRASS) == 2, (
        f"con la copia sobrante fuera, las dos energias se quedan; quedo {kept}")
    assert sorted(kept) == sorted([LILLIE, GRASS, GRASS])
    assert LILLIE in _discarded(obs, choice)


def test_the_count_of_supporters_kept_is_what_a_turn_can_play():
    """One Supporter per turn, so one Supporter survives. That is the sentence
    the floor is making, and holding a second copy of the same one cannot make
    the turn play two."""
    obs, choice, _ = _run()
    kept = _kept(obs, choice)
    assert [c for c in kept if c in _SUPP_PLAY_IDS] == [LILLIE]


# ---------------------------------------------------------------------------
# 3. Controls: the change gives nothing away and protects nothing new
# ---------------------------------------------------------------------------

def _without_the_spare(obs):
    """The same board holding ONE Lillie's, and one card fewer to discard.

    The hand index the options carry has to move with it, which is the reason
    this is done here and not by hand-editing a fixture.
    """
    hand = obs["current"]["players"][0]["hand"]
    doomed = max(i for i, c in enumerate(hand) if c["id"] == LILLIE)
    del hand[doomed]
    opciones = []
    for o in obs["select"]["option"]:
        if o["index"] == doomed:
            continue
        if o["index"] > doomed:
            o["index"] -= 1
        opciones.append(o)
    obs["select"]["option"] = opciones
    obs["select"]["minCount"] = obs["select"]["maxCount"] = 4
    return obs


def test_a_single_copy_still_gets_the_floor():
    """The change is about the SURPLUS. Take the spare away and the protection
    the block was written for is exactly as it was."""
    obs, choice, scores = _run(_without_the_spare(_obs()))
    assert _scores_of(scores, LILLIE) == [_ids.DISCARD_SUPPORTER_LIVE_KEEP]
    assert LILLIE in _kept(obs, choice)


def test_the_unpriced_cap_is_still_none_of_this_blocks_business():
    """Two Xerosic in one hand tie at their ladder price in the frozen corpus
    (registro_016 t14, registro_028 t1) and must go on tying: the latch lives
    INSIDE the branch the membership guard already closed for them."""
    _obs_, _choice, scores = _run()
    assert _scores_of(scores, XEROSIC) == [60]


def test_the_spare_that_holds_no_role_is_not_touched():
    """The control board (`registro_028` turn 12, our own Ultra Ball cost): two
    Boss's Orders and a Lana's Aid. The layer makes LANA the live one, so the
    KEEP branch never fires for the Boss's -- and the two copies tie at their
    ladder price, honestly, both of them fodder. A latch on a floor that was
    never handed out changes nothing, and this pins that it did not."""
    obs, choice, scores = _run(_obs(_CONTROL))
    assert _hand(obs).count(BOSS) == 2
    bosses = _scores_of(scores, BOSS)
    assert len(bosses) == 2 and len(set(bosses)) == 1, (
        f"empatar como forraje es la respuesta honesta aqui; salio {bosses}")
    assert bosses[0] > _ids.DISCARD_SUPPORTER_LIVE_KEEP
    # and the floor went where the role actually is
    assert _scores_of(scores, LANA) == [_ids.DISCARD_SUPPORTER_LIVE_KEEP]
    assert LANA in _kept(obs, choice)
