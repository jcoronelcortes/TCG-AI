"""Lana's Aid: the turn's Supporter is not spent on a DEAD card.

Scenario (user, episode **88904232** step 140, turn 10, vs Marnie's
Grimmsnarl ex --- game **WON** 1-5 on prizes; the leak did not cost the
match, but it is a leak all the same and self-play charges for it: +2.2 pp in the matchup.
Careful when citing `registro_NNN`: they are transient local data and the name gets
recycled; the stable anchor is the `EpisodeId`. When this test was written the
step lived in `records/registro_010_pasos_139_hasta_144.json`):

    US (2 prizes)                            OPPONENT (5 prizes)
    active  Hydrapple ex 240/330  6e         active  Marnie's Grimmsnarl 100/100
    bench   Meganium     100/160  2e                 (no energies)
            Meowth ex    140/170  2e
            Ogerpon ex   150/210  6e
            Meowth ex    140/170  0e
            Ogerpon ex   180/210  4e   <- bench FULL (5/5)
    hand    Ogerpon ex + Dawn + **Lana's Aid**
    discard   4x Lillie's, 3x Bug Catching Set, 2x Night Stretcher,
              2x Forest of Vitality, 1x Poke Pad and **1 Applin**
              -- NOT A SINGLE Grass Energy

The agent played **Lana's Aid**. The recovery menu had ONE single option
(`select.option` with a single element): that Applin. And that Applin is a dead
card by double entry --- with the bench FULL a Basic does not fit in any
way, and the line was already resolved with the Hydrapple ex in the active spot. The
turn's Supporter was spent to move a card from the discard to the hand.

Cause: the PLAY layer collected its base of 300 for `total_recoverable >= 1`,
which only counts cards in the discard. The SELECTION layer does know how to read the board
(`_pokemon_injugable`, `_grass_plan`; see
`test_lana_recupera_energia_no_basicos`), but by then the card is already
played: the veto had to move up a level.

The user's rule: **Lana's is played ONLY if something is needed that can be put into
play THIS turn** --- playable Pokemon or attachable Energy. It is applied with the
SAME board reading that then decides what is picked up:

  1. A VETO (`lana_val = 0`) if nothing recoverable enters play today: no
     playable Pokemon (`_pokemon_injugable`) and no live attachment route
     (`_grass_plan().slots_hoy`) for a Grass from the discard.
  2. A CEILING (`LANA_PLAY_NO_DEMAND`) if what is playable is not NEEDED: Energy that
     NOBODY asks for (every attacker in play already reaches `ATTACK_ENERGY_REQ`,
     or the hand has more Grass than fits today), or a Pokemon that fits
     on the bench but that no need bonus is claiming
     (`_lana_val_bonos == LANA_PLAY_BASE_RECUPERABLE`). A ceiling and not a veto: the
     card is still playable, it merely yields the turn to another Supporter with real
     value.

And the SAME gate in **Dawn** (block 4 of this file): with Lana's vetoed, the
turn's Supporter went into the Dawn in hand, which with a full bench and the
two lines already evolved could not bring anything playable either. The rule already
existed word for word but locked inside `op_is_alakazam_deck`; it is
generalised to every matchup and takes the pre->evo pairs from `EVO_LINES`.

Golden corpus: a single flip --- step 140 goes from playing Lana's to ATTACKING (the
same KO the real game made after throwing the Supporter away).
"""

import collections
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from patching import instalar
from cg.api import OptionType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_lana_recupera_applin_muerto_step140.json")

APPLIN = m.Applin
HYDRAPPLE = m.Hydrapple_ex


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


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    if mut.get("hueco_en_banca"):
        # Bench slots: they resurrect the Applin (it can be put down TODAY) and, from
        # 3 onwards, they leave the bench SHORT (<=2), which is a need bonus.
        mio["bench"] = mio["bench"][:-mut["hueco_en_banca"]]
    if mut.get("evo_pendiente"):
        # An Applin on the bench: its Stage 1 (Dipplin) is still in the deck, so there is
        # a REAL evolution Dawn can bring even with the bench full.
        mio["bench"][-1] = {"appearThisTurn": False, "energies": [],
                            "energyCards": [], "hp": 70, "id": m.Applin,
                            "maxHp": 70, "playerIndex": yo,
                            "preEvolution": [], "serial": 980, "tools": []}
    if mut.get("planta_en_descarte"):
        # Recoverable energy + the turn's attachment unspent: there is something that
        # CAN be put into play today.
        for k in range(mut["planta_en_descarte"]):
            mio["discard"].append({"id": m.Basic_Grass_Energy,
                                   "playerIndex": yo, "serial": 950 + k})
    if mut.get("planta_en_mano"):
        # The hand already has more Grass than fits this turn: recovering
        # another puts NOTHING on the field today. (They are added at the end: no
        # menu option points at those indexes.)
        for k in range(mut["planta_en_mano"]):
            mio["hand"].append({"id": m.Basic_Grass_Energy,
                                "playerIndex": yo, "serial": 970 + k})
        mio["handCount"] = len(mio["hand"])
    if mut.get("tapu_sin_energia"):
        # A benched Tapu Bulu at 0/4 creates real Grass DEMAND.
        mio["bench"][-1] = {"appearThisTurn": False, "energies": [],
                            "energyCards": [], "hp": 140, "id": m.Tapu_Bulu,
                            "maxHp": 140, "playerIndex": yo,
                            "preEvolution": [], "serial": 960, "tools": []}
    return o


def _hand_option(obs, card_id):
    """The index of the option that plays `card_id` from hand."""
    yo = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if (o.get("type") == int(OptionType.PLAY)
                and hand[o["index"]]["id"] == card_id):
            return i
    return None


def _lana_value(obs):
    """`values[Lanas_Aid]`: the board value that decides the PLAY layer."""
    capturado = {}
    orig = m._score_lanas_aid_play

    def spy(ctx, score):
        capturado.setdefault("v", ctx.supp_values.get(m.Lanas_Aid))
        return orig(ctx, score)

    _rest_score_lanas_aid_play = instalar("_score_lanas_aid_play", spy)
    try:
        m.agent(obs)
    finally:
        _rest_score_lanas_aid_play()
    assert "v" in capturado, "el scorer de Lana's Aid no llego a evaluarse"
    return capturado["v"]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_dead_recovery():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]

    assert not o["current"]["supporterPlayed"]        # the Supporter is alive
    assert len(mio["bench"]) == mio["benchMax"] == 5  # the bench is FULL
    assert mio["active"][0]["id"] == HYDRAPPLE        # the line is already resolved

    # Everything Lana's Aid can pick up: ONE Applin and no Grass.
    recuperable = [c["id"] for c in mio["discard"]
                   if c["id"] in (m.Chikorita, m.Applin, m.Tapu_Bulu, m.Pinsir)
                   or c["id"] == m.Basic_Grass_Energy]
    assert recuperable == [APPLIN]

    # And that Applin is a dead card: a Basic with the bench full.
    campo = collections.Counter([c["id"] for c in mio["bench"]] +
                                [mio["active"][0]["id"]])
    assert m._pokemon_injugable(APPLIN, campo, len(mio["bench"]),
                                mio["benchMax"])

    assert _hand_option(o, m.Lanas_Aid) is not None


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_does_not_play_lana_to_recover_a_dead_card():
    obs = _obs()
    lana = _hand_option(obs, m.Lanas_Aid)
    assert m.agent(obs) != [lana], (
        "con la banca llena y solo un Applin recuperable, Lana's Aid no mete "
        "nada en juego: gastar el Supporter del turno en ella es tirarlo")


def test_the_play_value_ends_up_vetoed():
    assert _lana_value(_obs()) == 0


def test_the_turn_goes_into_attacking_and_the_supporter_is_kept():
    """The complete outcome: neither Lana's nor Dawn (which with the bench full and the
    two lines already evolved brings nothing playable either). The turn is spent
    on the KO --- which in the real game was also made, AFTER throwing away the
    Supporter."""
    obs = _obs()
    attack_id = next(i for i, o in enumerate(obs["select"]["option"])
                  if o.get("type") == int(OptionType.ATTACK))
    assert m.agent(obs) == [attack_id]


# ---------------------------------------------------------------------------
# 3. The limits: when something to put into play IS needed, Lana's comes back
# ---------------------------------------------------------------------------

def test_with_a_bench_slot_the_applin_is_playable_but_not_needed():
    # The slot makes it playable, but the Applin->Hydrapple line is already in the
    # active spot and the bench is not short: no bonus claims it -> a ceiling.
    v = _lana_value(_obs(hueco_en_banca=1))
    assert 0 < v <= m.LANA_PLAY_NO_DEMAND, (
        "un Basico que cabe pero que nadie pide no vale el Supporter del "
        f"turno; obtuvo {v}")


def test_with_a_short_bench_the_body_in_the_discard_is_needed():
    # With the bench at 2 bodies, recovering a Basic IS a real need
    # (the short-bench bonus): Lana's recovers all its value.
    v = _lana_value(_obs(hueco_en_banca=3))
    assert v > m.LANA_PLAY_NO_DEMAND, (
        "con la banca corta el Applin del descarte es un cuerpo que hace "
        f"falta; obtuvo {v}")


def test_with_grass_in_the_discard_and_real_demand_lana_is_worth_it():
    # A Tapu Bulu at 0/4 on the bench + Grass in the discard + the attachment unspent:
    # there is energy that can be played TODAY and somebody asking for it.
    v = _lana_value(_obs(planta_en_descarte=3, tapu_sin_energia=True))
    assert v > m.LANA_PLAY_NO_DEMAND, (
        "con demanda real de energia Lana's no debe quedarse en el techo de "
        f"'nadie la pide'; obtuvo {v}")


def test_grass_that_cannot_reach_the_field_today_yields_the_turn():
    # The same Grass in the discard, but the HAND already has more than fits
    # this turn: what is recovered puts nothing on the field today. The card is still
    # playable (a ceiling, not a veto), it merely yields the turn's Supporter.
    v = _lana_value(_obs(planta_en_descarte=3, planta_en_mano=6))
    assert 0 < v <= m.LANA_PLAY_NO_DEMAND, (
        "energia recuperable que no llega al campo hoy: jugable, pero por "
        f"debajo del resto de Supporters; obtuvo {v}")


# ---------------------------------------------------------------------------
# 4. The SAME gate in Dawn: the Supporter is not saved by changing card
# ---------------------------------------------------------------------------
#
# With Lana's vetoed, the turn's Supporter went into the Dawn in hand: with
# the bench 5/5 and the two lines already evolved (Meganium + Hydrapple ex in
# play), the up to 3 Pokemon it searches from the deck are just as inert --- and
# they also thin the deck, which is how games are lost by deckout. The rule already
# existed word for word, but locked inside `op_is_alakazam_deck`; it had
# nothing specific to that matchup, so now it runs always and takes
# the pre->evo pairs from `EVO_LINES`.

def _dawn_value(obs):
    """`values[Dawn]`, captured in the Dawn scorer."""
    capturado = {}
    orig = m._score_dawn_play

    def spy(ctx):
        capturado.setdefault("v", ctx.supp_values.get(m.Dawn))
        return orig(ctx)

    _rest_score_dawn_play = instalar("_score_dawn_play", spy)
    try:
        m.agent(obs)
    finally:
        _rest_score_dawn_play()
    assert "v" in capturado, "el scorer de Dawn no llego a evaluarse"
    return capturado["v"]


def test_the_fixture_has_both_lines_already_evolved():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    campo = [c["id"] for c in mio["bench"]] + [mio["active"][0]["id"]]
    assert m.Meganium in campo and m.Hydrapple_ex in campo
    # No body in play admits an evolution: there is nothing Dawn can bring
    # and put on top.
    for line in m.EVO_LINES:
        for pre, evo in zip(line, line[1:]):
            assert pre not in campo, (pre, evo)
    assert _hand_option(o, m.Dawn) is not None


def test_it_does_not_play_dawn_with_a_full_bench_and_nothing_to_evolve():
    assert _dawn_value(_obs()) == 0


def test_with_a_pending_evolution_dawn_is_worth_it_again():
    # An Applin on the bench: Dawn can bring the Dipplin from the deck and evolve it
    # without taking a bench slot.
    assert _dawn_value(_obs(evo_pendiente=True)) > 0


def test_with_a_bench_slot_dawn_keeps_its_value():
    # The gate only bites with the bench FULL: with a slot, any Basic
    # Dawn brings can be put down.
    assert _dawn_value(_obs(hueco_en_banca=1)) > 0
