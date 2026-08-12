"""Their blow is twenty times a hand, and we hold the card that empties it.

Scenario (`records/registro_009_pasos_105_hasta_118.json`, step 118, turn 9,
LOST vs Alakazam -- episode 92106273). Three prizes to TWO:

    US (3 prizes)                            RIVAL (2 prizes)
    active  -- (just knocked out)            active  Alakazam 140/140, 1 {P}
    bench   Meowth ex 170, 0 en.                     (Powerful Hand: 20 x hand)
            Teal Mask Ogerpon ex 210, 2 {G}  hand    **17 cards** -> 380
            Fezandipiti ex 210, 0 en.
            Tapu Bulu 140, 0 en.
            Applin 40, 0 en.
    hand    4 Grass, **Unfair Stamp**, Dawn, Tapu Bulu, Chikorita, ...

Their Alakazam took our Meganium and the menu asked who takes the front. The
Teal Mask Ogerpon ex FINISHES that Alakazam -- one Grass out of hand puts Myriad
Leaf Shower at 30+30x(3+1) = 150 on a 140 HP body -- and `_promo_kos_op` said
so, which is worth `PROMO_KO_BONUS`. It was vetoed anyway, at -30000: with their
hand at seventeen, Powerful Hand reads 20 x (17+2) = 380, that removes every
body on our bench, and a 2-prize ex their blow removes IS their remaining pile.
The 140 HP Tapu Bulu went up with no energy on it, could not attack, and the
game ended one turn later.

The veto's arithmetic is right and its premise is not. This promotion resolves
at the END of their turn: OUR turn comes first, and the hand it starts with
holds an Unfair Stamp, whose printed clause -- "only if any of your Pokemon were
Knocked Out during your opponent's last turn" -- is the very event that opened
this menu. Play it and they attack out of `STAMP_OP_HAND_AFTER` cards: 20 x
(2+2) = 80, which does not remove a 210 HP body. The number the veto is priced
on is not a fact about the board. It is a quantity WE control.

Fix, deck-agnostic: `_mp_reply_after_our_reset` re-reads the same three
projections with the two hands the Stamp prints, and `_mp_price_ends_the_game`
asks it SECOND -- only where the ordinary reading already answered "lethal", and
only ever to REMOVE a veto. Nothing here names Alakazam: it speaks for any
attack whose damage counts a hand, theirs (Powerful Hand) or ours (Resentful
Refrain, Mind Ruler).

WHY SECOND AND NOT INSTEAD. `_mp_op_hand` still feeds the rest of the family
untouched -- the survival census, `_mp_outlasts`, the doomed penalty among the
knockers. Those consumers use the projection as a FILTER, every one of them was
calibrated on the blind reading, and swapping a shared projection for a truer
one measured 47.8% against 50.5% for asking it second. The corpus says the same
thing: switching this reading off flips EXACTLY this decision and no other of
the fifty records.

WHERE IT DELIBERATELY STOPS:

  * a blow that never counted a hand is not defused by emptying one -- against a
    flat 220 the three ex stay vetoed;
  * it can only remove a veto: it never raises a score, so no body that takes no
    prize is promoted by it, and a body the reset does not actually save (a 40 HP
    Applin against 80) is not saved by it either;
  * it needs the Stamp really in hand AND worth playing (`_stamp_reset_pending`,
    the same predicate the ordering vetoes read): with no Stamp the veto stands
    and the Tapu Bulu comes back up.
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

import main as m
from patching import parcheado

OGERPON = m.Teal_Mask_Ogerpon_ex       # 210/210, 2 Grass, 2 prizes
MEOWTH = m.Meowth_ex                   # 170/170, 2 prizes
FEZ = m.Fezandipiti_ex                 # 210/210, 2 prizes
TAPU = m.Tapu_Bulu                     # 140/140, 0 energies, 1 prize
APPLIN = m.Applin                      # 40/40, 1 prize
OP_ALAKAZAM = m.Alakazam_ex            # id 743, "Alakazam": 140 HP, Powerful Hand
CERULEDGE = 797                        # Infernal Slash: a FLAT 220 for one energy
FROSLASS = 861                         # Mega Froslass ex: Resentful Refrain, 50 x OUR hand

_FIX = (ROOT / "tests" / "fixtures"
        / "alakazam_step118_the_blow_priced_on_the_hand_we_reset.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _theirs(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _bench_raw(obs, card_id):
    return next(b for b in _mine(obs)["bench"] if b and b["id"] == card_id)


def _promoted(obs):
    """The card id the agent puts in the front spot."""
    picked = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    return _mine(obs)["bench"][picked["index"]]["id"]


def _spy(obs, *fields):
    """Run the agent and keep the promotion predicates the scorer was handed.

    Always returns the parsed bench and the opposing active alongside them, so a
    test can ask a predicate about a real `Pokemon` instead of rebuilding one.
    """
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        if not seen:
            seen["bench"] = [b for b in tc.my_state.bench if b is not None]
            seen["op"] = tc._promo_op_act
            for name in fields:
                seen[name] = getattr(tc, name)
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m.score_option = original
    return seen


def _body(seen, card_id):
    return next(b for b in seen["bench"] if b.id == card_id)


def _veto(obs):
    """`{card id: _mp_price_ends_the_game(body)}` for the whole bench."""
    seen = _spy(obs, "_mp_price_ends_the_game")
    return {b.id: seen["_mp_price_ends_the_game"](b) for b in seen["bench"]}


def _scores(obs):
    """{card id: score} for the whole promotion menu."""
    out = {}

    def spy(context, select, sc, o, my_index, top_n=3):
        for i, opt in enumerate(select.option):
            card = m.get_card(o, opt.area, opt.index, my_index)
            if card is not None:
                out.setdefault(card.id, sc[i])

    with parcheado("_debug_log_decision", spy):
        m.agent(copy.deepcopy(obs))
    return out


def _without_the_stamp(obs):
    mine = _mine(obs)
    mine["hand"] = [c for c in mine["hand"] if c["id"] != m.Unfair_Stamp]
    mine["handCount"] = len(mine["hand"])
    return obs


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    obs = _obs()
    mine, theirs = _mine(obs), _theirs(obs)

    assert mine["active"] == [], "the spot is empty: a forced promotion after a KO"
    assert len(mine["prize"]) == 3 and len(theirs["prize"]) == 2, (
        "their pile is TWO: any of our ex that falls ends the game")
    assert theirs["active"][0]["id"] == OP_ALAKAZAM
    assert theirs["handCount"] == 17, (
        "seventeen cards is the whole of their attack: 20 x (17+2) = 380")

    oger = _bench_raw(obs, OGERPON)
    assert oger["hp"] == 210 and len(oger["energies"]) == 2, (
        "two of the three Grass Myriad Leaf Shower costs, and four more in hand")

    hand = [c["id"] for c in mine["hand"]]
    assert m.Unfair_Stamp in hand, "the card the whole fix is about"
    assert hand.count(m.Basic_Grass_Energy) >= 1, (
        "and the Grass that completes the Ogerpon before the Stamp shuffles it")


def test_their_blow_removes_every_body_on_our_bench_today():
    """The veto is not wrong about the arithmetic: read on TODAY's hand, 380
    goes through all five candidates."""
    seen = _spy(_obs())
    for body in seen["bench"]:
        today = m._op_active_attack_damage_to(seen["op"], body, op_hand_count=17)
        assert today >= (body.hp or 0), f"{body.id} falls to {today}"


def test_the_reset_is_what_changes_the_number():
    """20 x (17+2) = 380 today; 20 x (2+2) = 80 out of the hand the Stamp leaves
    them. The 210 HP Ogerpon is on the other side of that line."""
    seen = _spy(_obs())
    oger = _body(seen, OGERPON)

    today = m._op_active_attack_damage_to(seen["op"], oger, op_hand_count=17)
    after = m._op_active_attack_damage_to(seen["op"], oger,
                                          op_hand_count=m.STAMP_OP_HAND_AFTER)
    assert today == 380 and after == 80
    assert today >= (oger.hp or 0) > after, (
        "the same body, the same attack: only the hand it is priced on changed")


def test_the_ogerpon_finishes_that_alakazam():
    """What the veto was throwing away: the promotion is not a wall here, it is
    the knockout."""
    seen = _spy(_obs(), "_promo_kos_op")
    kos = {b.id: seen["_promo_kos_op"](b) for b in seen["bench"]}
    assert kos[OGERPON], "Myriad Leaf Shower with the attachment: 150 on 140 HP"
    assert not any(kos[i] for i in (MEOWTH, FEZ, TAPU, APPLIN)), (
        "and it is the only body on that bench that does")


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_front_spot_goes_to_the_body_that_can_still_attack():
    assert _promoted(_obs()) == OGERPON, (
        "two Grass on it, four in hand and their reply about to be worth 80")


def test_the_veto_that_chose_the_tapu_is_lifted_for_the_whole_bench():
    """The premise it is written on -- 'their blow takes this body' -- is false
    for every candidate once the reset is counted, so it is lifted for every
    candidate. Lifting it is ALL this reading does; who then goes up is decided
    by the rules that were already there."""
    assert not any(_veto(_obs()).values())


def test_the_knockout_band_is_what_promotes_it():
    """No new bonus: with the veto gone the Ogerpon is picked by
    `PROMO_KO_BONUS`, and the bodies that take no prize stay exactly where the
    ordinary chain left them."""
    scores = _scores(_obs())
    assert scores[OGERPON] > 20000
    for card_id in (MEOWTH, FEZ, TAPU, APPLIN):
        assert scores[card_id] < 1000, (
            "nothing here raises a body that does not knock out")


# ---------------------------------------------------------------------------
# 3. Boundaries
# ---------------------------------------------------------------------------

def test_with_no_stamp_in_hand_the_veto_stands():
    """The specificity of the whole change: take the one card out of that hand
    and the record's own decision comes back."""
    obs = _without_the_stamp(_obs())
    veto = _veto(copy.deepcopy(obs))
    assert veto[OGERPON] and veto[MEOWTH] and veto[FEZ], (
        "with nothing to defuse the blow, a 2-prize body their reply removes is "
        "still the game")
    assert not veto[TAPU] and not veto[APPLIN], (
        "and the 1-prize bodies were never this veto's subject: their pile is TWO")
    assert _promoted(obs) == TAPU


def test_a_blow_that_never_counted_a_hand_is_not_defused():
    """Ceruledge's Infernal Slash is a flat 220 for one energy. Emptying their
    hand does nothing to it, the veto stays, and the 1-prize wall takes the
    front exactly as before."""
    obs = _obs()
    theirs = _theirs(obs)
    theirs["active"][0]["id"] = CERULEDGE
    theirs["active"][0]["maxHp"] = 140

    veto = _veto(copy.deepcopy(obs))
    assert veto[OGERPON] and veto[MEOWTH] and veto[FEZ]
    assert _promoted(obs) == TAPU


def test_an_attack_that_counts_OUR_hand_is_re_read_and_not_waived():
    """The reading is a real recomputation, not a blanket lift. Resentful
    Refrain is 50 per card in OUR hand: the Stamp cuts ours down to
    `STAMP_OUR_HAND_AFTER`, which lowers the blow from 500 to 250 -- and 250
    still removes a 210 HP body, so the veto survives its own second question."""
    obs = _obs()
    theirs = _theirs(obs)
    theirs["active"][0]["id"] = FROSLASS
    theirs["active"][0]["hp"] = 310
    theirs["active"][0]["maxHp"] = 310

    assert 50 * m.STAMP_OUR_HAND_AFTER > _bench_raw(obs, OGERPON)["hp"], (
        "50 x 5 = 250 is still lethal on the 210: the arithmetic this test needs")

    veto = _veto(copy.deepcopy(obs))
    assert veto[OGERPON], "re-read after the reset and still lethal -> vetoed"
    assert _promoted(obs) != OGERPON


def test_the_reset_never_saves_a_body_it_does_not_save():
    """It only removes a veto where the body really is out of reach: 80 still
    goes through a 40 HP Applin, so nothing about it changed."""
    obs = _obs()
    seen = _spy(obs)
    applin = _body(seen, APPLIN)
    after = m._op_active_attack_damage_to(seen["op"], applin,
                                          op_hand_count=m.STAMP_OP_HAND_AFTER)
    assert after >= (applin.hp or 0), "the 40 HP body dies either way"
    assert _promoted(obs) != APPLIN


def test_the_printed_hands_are_the_cards_own_numbers():
    """Unfair Stamp: 'each player shuffles their hand into their deck. Then, you
    draw 5 cards, and your opponent draws 2 cards.'"""
    assert m.STAMP_OP_HAND_AFTER == 2
    assert m.STAMP_OUR_HAND_AFTER == 5
    assert m.STAMP_OP_HAND_AFTER < m.STAMP_MIN_OP_HAND, (
        "the disruption floor has to sit above the hand the card leaves them")
