"""The Supporter the Last-Ditch Catch brought GETS PLAYED.

Scenario (user, episode 88786171, registro_002 steps 18-22, turn 2 vs
Alakazam, WON with a mistake):

    US                                      OPPONENT
    active  Fezandipiti ex 210 0e           active  Chikorita 50 1e
    bench   Applin (and the Meowth ex that  bench   Chikorita
            comes down this very turn)
    hand    Forest of Vitality, Xerosic's Machinations, Dawn, Basic {G} Energy
    prizes left: 6 - 6      (it is OUR first turn)

The recorded sequence of turn 2:

    Poke Pad -> Applin | Bug Catching Set | play the Applin | **Ultra Ball
    (discarding 2 Grass) -> Meowth ex** | **play the Meowth ex** | **Last-Ditch
    Catch -> Lillie's Determination** | attach energy | ... and immediately after
    it plays the **DAWN** it already had in hand.

The chain was well thought out until the last step: two discarded cards were paid
for the Ultra Ball and a 2-PRIZE body on the bench (the Meowth ex)
to bring the Lillie's -- which on our first turn with 6 prizes draws EIGHT
cards -- and then the turn's only Supporter slot was spent on another
card. The Lillie's stayed dead in hand and the Meowth ex was left on the bench
given away, free, for nothing.

Cause: NOBODY forced the search to be cashed in.

  * `_meowth_fetch_loses_the_turn` PREDICTS, before putting the Meowth down, that the
    fetch will take the Supporter slot -- but it is not evaluated on OUR
    FIRST TURN (the anti-donk line puts the Meowth down anyway) and, above all, it does not
    force anything AFTER the fetch;
  * with the new hand the play scorer decided again from scratch and there a
    BOARD veto governed -- `do_not_shuffle_the_last_xerosic` (-1), which
    protects access to the Xerosic's Machinations vs Alakazam -- which knows nothing
    about the Lillie's already being PAID FOR with a 2-prize body.

Fix: `_ld_supp_comprometido`, sibling of `_ub_meowth_pending` /
`_ub_fez_pending`. When the Last-Ditch of a Meowth ex played THIS turn
(`appearThisTurn`: the body is paid for) chooses a Supporter, that id keeps
the turn's slot: a score floor above any other Supporter
(`SCORE_LD_SUPP_COMPROMETIDO`) and a veto for the rest of the `_SUPP_PLAY_IDS` in
hand. It is a rule of COMMITMENT, not of value: the resource is already spent.

What does NOT change: the Last-Ditch of a Meowth ex from PREVIOUS turns is free
and commits nothing (it can keep the Supporter for the next turn, the same
criterion as `_meowth_skip_fetch`); the floor is applied with `max()`, so a
winning Boss's keeps its score; and the commitment is reset every turn.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from patching import instalar
from state_builder import C, G, Escenario, pk

MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
DAWN = m.Dawn
XEROSIC = m.Xerosic_Machinations
BOSS = m.Boss_Orders
FOREST = m.Forest_of_Vitality
FEZ = m.Fezandipiti_ex
APPLIN = m.Applin
OGERPON = m.Teal_Mask_Ogerpon_ex
ENERGY = m.Basic_Grass_Energy

CHIKORITA_OPPONENT = 917               # the opponent's active/bench of the record
ABRA = 843                          # a basic of the Alakazam line (synthetic)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_ld_supporter_comprometido_step22.json")


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


def _observaciones():
    """The 5 observations of OUR turn 2 (turnActionCount 9..13)."""
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observaciones"]


def _by_action(obs_list):
    return {o["current"]["turnActionCount"]: o for o in obs_list}


def _play(obs, choice):
    """('PLAY'|'CARTA', card_id) / ('ATTACH'|'RETREAT'|'END', None)."""
    o = obs["select"]["option"][choice[0]]
    tipo = o["type"]
    yo = obs["current"]["yourIndex"]
    player = obs["current"]["players"][yo]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", player["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.CARD):
        if o.get("area") == int(m.AreaType.DECK) and obs["select"].get("deck"):
            return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
        return ("CARTA", None)
    if tipo == int(m.OptionType.ATTACH):
        return ("ATTACH", None)
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _plays(obs):
    return [_play(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _reproducir(obs_list):
    """Replays the turn IN ORDER and returns {turnActionCount: play}."""
    hecho = {}
    for obs in obs_list:
        hecho[obs["current"]["turnActionCount"]] = _play(obs, m.agent(obs))
    return hecho


# ---------------------------------------------------------------------------
# 1. The real turn: the chain gets cashed in
# ---------------------------------------------------------------------------

def test_step22_plays_the_lillie_the_last_ditch_brought():
    hecho = _reproducir(_observaciones())
    # The chain, step by step: the Meowth ex is played...
    assert hecho[9] == ("PLAY", MEOWTH)
    # ...its Last-Ditch Catch searches for the Lillie's...
    assert hecho[11] == ("CARTA", LILLIE)
    # ...and the turn's Supporter slot is ITS (before: Dawn).
    assert hecho[13] == ("PLAY", LILLIE)


def test_step22_the_menu_really_offered_both_plays():
    """Without both in the menu the test would discriminate nothing."""
    obs13 = _by_action(_observaciones())[13]
    plays = _plays(obs13)
    assert ("PLAY", LILLIE) in plays, plays
    assert ("PLAY", DAWN) in plays, plays
    assert ("PLAY", XEROSIC) in plays, plays


def test_step22_the_commitment_is_the_only_thing_that_decides():
    """It documents the state that made the mistake inevitable: with the board of that
    menu, the Lillie's scorer VETOES it (`do_not_shuffle_the_last_xerosic`) and the Dawn
    one scores positive. Without the commitment, Dawn wins."""
    obs_list = _observaciones()
    visto = {}
    orig = m._score_dawn_play

    def spy(ctx):
        visto["ctx"] = ctx
        return orig(ctx)

    _rest_score_dawn_play = instalar("_score_dawn_play", spy)
    try:
        _reproducir(obs_list)
    finally:
        _rest_score_dawn_play()
    ctx = visto["ctx"]
    assert m._score_lillie_determination_play(ctx) == m.SCORE_VETO
    assert orig(ctx) > 0
    # And the commitment was armed with the card the fetch brought.
    assert m._ld_supp_comprometido == LILLIE


# ---------------------------------------------------------------------------
# 2. The commitment is only born from the PAID body
# ---------------------------------------------------------------------------

def test_a_free_last_ditch_does_not_commit_the_turn():
    """A Meowth ex from PREVIOUS turns searches for free: it can keep the
    Supporter for the next turn and the rest of the hand rules. It is replicated
    by switching off `appearThisTurn` on the benched Meowth."""
    obs_list = _observaciones()
    for obs in obs_list:
        for pkm in obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]:
            if pkm["id"] == MEOWTH:
                pkm["appearThisTurn"] = False
    hecho = _reproducir(obs_list)
    assert hecho[11] == ("CARTA", LILLIE)      # the fetch does not change
    assert m._ld_supp_comprometido == 0        # but it does not commit the turn
    assert hecho[13] == ("PLAY", DAWN)         # the scorer decides, as before


def test_the_commitment_resets_each_turn():
    """The committed Supporter holds for THIS turn: if the turn changes without
    it having been played, the commitment falls (it does not drag vetoes into the next turn).
    """
    obs_list = _observaciones()
    _reproducir(obs_list)
    assert m._ld_supp_comprometido == LILLIE
    next_item = json.loads(json.dumps(_by_action(obs_list)[13]))
    next_item["current"]["turn"] += 2
    next_item["current"]["turnActionCount"] = 1
    m.agent(next_item)
    assert m._ld_supp_comprometido == 0


# ---------------------------------------------------------------------------
# 3. A synthetic generalisation: the rule names no cards
# ---------------------------------------------------------------------------

def _synthetic_menu(hand):
    """A neutral board (a mid game turn, with no special matchup) with `mano` in hand
    and a menu of one PLAY per card."""
    return (Escenario(turn=8, step=60, tac=4)
            .my_active(pk(OGERPON, energies=[G, G]))
            .my_bench(pk(MEOWTH, aparecio=True), APPLIN)
            .my_hand(*hand)
            .op_active(pk(CHIKORITA_OPPONENT, energies=[C]))
            .op_bench(pk(ABRA, hp=70, max_hp=70))
            .op_zonas(hand=5, deck=30, prizes=5)
            .menu_hand()
            .build())


def _armar(obs, sid):
    """It leaves the commitment armed on `sid` for THIS turn.

    The first call to `agent` consumes the per-turn reset (which sets the
    commitment to 0); the flag is armed afterwards, as in the real game, where it is
    written by the fetch itself mid-turn."""
    m.agent(obs)
    m._ld_supp_comprometido = sid


def test_the_commitment_wins_the_slot_over_any_other_supporter():
    """With the commitment armed, any OTHER Supporter in hand yields the
    slot -- it is tested with a pair of cards different from the record's."""
    obs = _synthetic_menu([BOSS, XEROSIC])
    plays = _plays(obs)
    assert ("PLAY", BOSS) in plays, plays
    assert ("PLAY", XEROSIC) in plays, plays

    _armar(obs, BOSS)
    assert _play(obs, m.agent(obs)) == ("PLAY", BOSS)

    m._ld_supp_comprometido = XEROSIC
    assert _play(obs, m.agent(obs)) == ("PLAY", XEROSIC)


def test_the_floor_sits_above_the_normal_supporter_band():
    """The rule is A SINGLE gesture (a floor with `max()`), without vetoing the rest: that
    only works if the floor beats the normal band of any Supporter.
    Pinning the margin here stops a future scorer from overtaking it silently.

    Its counterpart is the safety valve measured in the gate: a DECISIVE
    Supporter (a score > the floor, e.g. a Boss's that wins the game) can still
    keep the turn. Adding the veto cost -0.67 points of winrate
    (6000 games per variant); the floor alone gives +0.40."""
    obs = _synthetic_menu([BOSS, XEROSIC])
    m.agent(obs)                      # it leaves the turn's ctx built
    visto = {}
    orig = m._score_xerosic_play

    def spy(ctx):
        visto["ctx"] = ctx
        return orig(ctx)

    _rest_score_xerosic_play = instalar("_score_xerosic_play", spy)
    try:
        m.agent(obs)
    finally:
        _rest_score_xerosic_play()
    ctx = visto["ctx"]
    for sid in m._SUPP_PLAY_IDS:
        assert m._supp_play_score(ctx, sid) < m.SCORE_LD_SUPP_COMPROMETIDO


def test_the_commitment_does_not_apply_once_the_slot_is_spent():
    """`supporterPlayed` rules: the commitment does not resurrect a spent slot."""
    obs = _synthetic_menu([BOSS, XEROSIC])
    obs["current"]["supporterPlayed"] = True
    _armar(obs, BOSS)
    assert _play(obs, m.agent(obs))[1] != BOSS


def test_the_commitment_disarms_if_its_card_is_no_longer_offered():
    """If the committed Supporter disappears from hand (the cost of an Ultra
    Ball, a shuffle...) the rule must not leave the rest of the menu vetoed."""
    obs = _synthetic_menu([XEROSIC, m.Ultra_Ball])
    without_commitment = _play(obs, m.agent(obs))

    _armar(obs, BOSS)                     # committed... and no longer in hand
    assert _play(obs, m.agent(obs)) == without_commitment
