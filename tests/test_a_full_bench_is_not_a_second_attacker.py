"""A full bench is not a second attacker: the reasonless gust loses the fetch.

Scenario (user, 15 August 2026, turn 9 against a Marnie's / Froslass board --
reported from a game and reproduced here synthetically, because what decided it
is a COUNT and not a card list; every assertion below fails without the fix):

    US                                     THEM
    active  Teal Mask Ogerpon ex 140/210,   Marnie's Grimmsnarl ex, charged --
            CHARGED -- it attacks today             it knocks our active out
    bench   Bayleef   (waiting for a                next turn
                       Meganium)            bench   two Froslass, dripping 10 a
            Applin    (waiting for a Dipplin)               turn onto every body
            Teal Mask Ogerpon ex, ONE {G} of                of ours with an
            the three its attack costs                      ability
            Meowth ex, just benched -- the
            Last-Ditch is the decision

Four bodies behind the front and not one of them can attack. Our attacker was
one hit away from being knocked out and there was nothing to take over; the
Last-Ditch Catch brought a **Boss's Orders**.

WHY, AND IT IS A HEAD COUNT. `lillie_development` (1250) is fed by
`_meowth_devel_lillie`, which asks `bodies_in_play <= 3`. It measures how FULL
the bench is: it read four bodies, answered "already developed", and the refill
lost its band. The chain then fell through to `supporter_value`, where the raw
scale prices Boss's Orders **850** against Lillie's Determination **650** -- and
the gust won a comparison the board never asked for. Every one of those four
bodies was a card, not an attack: the same LISTO IS NOT UTILIZABLE that
`boss_beats_the_untouchable_active` and `_a_body_can_attack_this_turn` are
written around.

THE FIX is `the_gust_without_a_reason_yields_to_the_second_wave` in
`_RULES_MEOWTH_FETCH`. What the refill competes with is the SECOND WAVE, so the
second wave is what gets counted -- `_ready_attacker_count`, the bodies that can
pay an attack cost right now -- and it is read together with
`_active_doomed_real`, exactly the pair the PLAY half of this same engine
(`ptcg/turn/options/play.py`, the 21450 and 21600 arms) already reads before it
spends two prizes of Meowth ex on a refill. The two halves of one engine now
answer the same board the same way.

IT PRICES THE GUST, IT DOES NOT CROWN THE REFILL. The first version of this rule
lifted the refill to the development band instead, and
`test_with_the_slot_free_the_dawn_wins_again` caught it: with a Forest of
Vitality on the field the **Dawn** assembles a line and evolves it the same turn,
which buys the second attacker more directly than eight cards do. The claim here
is about the gust, so the gust is what is priced; the rest of the ladder goes on
choosing among the cards that build our own board.

It never talks over a gust that HAS a reason -- the gust that ends the game
(1300), the one worth two prizes, the line cut (1280), the bench behind an
untouchable active (1270) all return above this rung, so reaching it means the
ladder found no reason at all.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
import golden_corpus as gc  # noqa: E402
from state_builder import Scenario, pk, G  # noqa: E402

OGERPON = m.Teal_Mask_Ogerpon_ex
BAYLEEF = m.Bayleef
APPLIN = m.Applin
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
DAWN = m.Dawn
GRIMMSNARL = m.Grimmsnarl_ex     # THEIR body: read only through its damage
GRASS = m.Basic_Grass_Energy
RULE = "the_gust_without_a_reason_yields_to_the_second_wave"


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


# ---------------------------------------------------------------------------
# 1. The board: which Supporter the Last-Ditch really brings
# ---------------------------------------------------------------------------

def _bench_that_cannot_attack():
    """The reported bench: two bodies waiting for an evolution and an Ogerpon ex
    one third of the way to its cost."""
    return [pk(BAYLEEF, hp=80, pre_evo=[m.Chikorita]),
            pk(APPLIN, hp=40),
            pk(OGERPON, energies=[G], fisicas=1),
            pk(MEOWTH, aparecio=True)]


def _bench_with_a_second_attacker():
    """The same four bodies, only the benched Ogerpon ex is CHARGED."""
    return [pk(BAYLEEF, hp=80, pre_evo=[m.Chikorita]),
            pk(APPLIN, hp=40),
            pk(OGERPON, energies=[G] * 3, fisicas=3),
            pk(MEOWTH, aparecio=True)]


def _board(bench, active_hp=140):
    gc.reset_agent(m)
    return (Scenario(turn=9, step=90, tac=3, own_prizes=4)
            .my_active(pk(OGERPON, hp=active_hp, energies=[G] * 3, fisicas=3))
            .my_bench(*bench)
            .my_hand(GRASS, m.Ultra_Ball, m.Night_Stretcher, m.Poke_Pad, GRASS)
            .op_active(pk(GRIMMSNARL, hp=320, max_hp=320, energies=[G] * 3,
                          pre_evo=[m.Marnies_Impidimp, m.Marnies_Morgrem]))
            .op_bench(pk(m.Froslass, hp=90, max_hp=90),
                      pk(m.Froslass, hp=90, max_hp=90))
            .op_zones(hand=5, deck=25, prizes=4)
            .deck(LILLIE, BOSS, m.Hydrapple_ex, GRASS)
            .rest_to_discard()
            .menu_hand(with_attachment=True, with_attack=True)
            .build())


def _fetch(obs):
    """(id, value, trace) the Last-Ditch ladder resolves on this board, read off
    the real chain as `agent()` walks it."""
    seen = {}
    original = m._resolve_rules

    def spy(rules, adjustments, ctx, default):
        out = original(rules, adjustments, ctx, default)
        if rules is m._RULES_MEOWTH_FETCH:
            seen[ctx.card_id] = out
        return out

    m._resolve_rules = spy
    try:
        m.agent(obs)
    finally:
        m._resolve_rules = original
    assert seen, "el tablero no llego a resolver el fetch del Last-Ditch"
    card_id, (value, trace) = max(seen.items(), key=lambda kv: kv[1][0])
    return card_id, value, trace


def test_the_reported_board_does_not_fetch_the_gust():
    """The regression: with nothing behind a dying attacker, the fetch is not a
    Boss's Orders."""
    card_id, _, trace = _fetch(_board(_bench_that_cannot_attack()))
    assert card_id == LILLIE, (
        f"sin segundo atacante y con el activo condenado, el Last-Ditch compra "
        f"la segunda ola; trajo {card_id} ({trace})")


def test_the_reason_is_the_second_wave_and_not_the_bench_size():
    """The control that keeps the rule to what it says.

    The SAME four bodies, the same hand, the same opponent -- only the benched
    Ogerpon ex is charged. The second wave exists, and the ladder goes back to
    what it did before the fix. That is the proof it reads the wave and not the
    head count."""
    card_id, _, trace = _fetch(_board(_bench_with_a_second_attacker()))
    assert card_id == BOSS, (
        f"con un cuerpo cargado esperando, la escalera queda intacta; "
        f"eligio {card_id} ({trace})")


def test_a_healthy_active_leaves_the_ladder_untouched():
    """The other control: the same undeveloped bench, but their attacker does
    not knock our active out. The turn is not the one this rule is about."""
    card_id, _, trace = _fetch(_board(_bench_that_cannot_attack(),
                                      active_hp=210))
    assert card_id == BOSS, (
        f"con el activo sano la escalera queda intacta; eligio {card_id} "
        f"({trace})")


# ---------------------------------------------------------------------------
# 2. The band: which gusts still take the fetch
# ---------------------------------------------------------------------------

def _ctx(card_id, **kw):
    """A fetch candidate on the reported board: our only charged body is the one
    in front, it dies next turn, and no gust has declared a reason yet."""
    field = dict(sv=850, hand_counts={}, supp_values={}, hand_size=4,
                 strong_attacker=True, op_hand_count=5,
                 active_cant_attack=False, win_via_boss=False,
                 gust2_via_boss=False, deny_evo_via_boss=False,
                 devel_lillie=False, alakazam=False, first_turn=False,
                 lillie_alcanzable=True, gust_over_immune_active=False,
                 recovery_ko=False, hand_supp_val=0, a_body_can_attack=True,
                 my_prize=4, lone_ready_attacker=True, active_doomed=True)
    field.update(kw)
    return m._CtxMeowthFetch(
        card_id, field["sv"], field["hand_counts"], field["supp_values"],
        field["hand_size"], field["strong_attacker"], field["op_hand_count"],
        field["active_cant_attack"], field["win_via_boss"],
        field["gust2_via_boss"], field["deny_evo_via_boss"],
        field["devel_lillie"], field["alakazam"], field["first_turn"],
        field["lillie_alcanzable"], field["gust_over_immune_active"],
        field["recovery_ko"], field["hand_supp_val"],
        field["a_body_can_attack"], field["my_prize"],
        field["lone_ready_attacker"], field["active_doomed"])


def _score(card_id, **kw):
    value, _ = m._resolve_rules(m._RULES_MEOWTH_FETCH, [], _ctx(card_id, **kw),
                               50)
    return value


def test_the_gust_with_no_reason_falls_to_the_forced_pick_band():
    """850 on the raw scale, 40 once the ladder has found no reason for it --
    the same band `copy_already_in_hand` uses, so a deck holding no other
    Supporter still brings it."""
    assert _score(BOSS) == 40


@pytest.mark.parametrize("reason,flags", [
    ("the gust that ends the game", dict(win_via_boss=True)),
    ("the gust worth two prizes", dict(gust2_via_boss=True)),
    ("the line cut", dict(deny_evo_via_boss=True)),
    ("the bench behind an untouchable active",
     dict(gust_over_immune_active=True)),
])
def test_a_gust_with_a_reason_still_takes_the_fetch(reason, flags):
    assert _score(BOSS, **flags) >= 1270, (
        f"{reason} se resuelve por encima de esta regla y se lleva el fetch")


def test_both_premises_are_required():
    """Either half alone leaves the gust on its raw value."""
    assert _score(BOSS, active_doomed=False) == 850
    assert _score(BOSS, lone_ready_attacker=False) == 850


def test_the_first_turn_ladder_is_untouched():
    """Turn one is decided above, by `first_turn_lillie_only` and its yield: the
    refill at 1400, the rest degraded there and not here."""
    assert _score(LILLIE, first_turn=True, sv=650) == 1400
    assert _score(BOSS, first_turn=True) == 40   # first_turn_rest_yields_to_lillie


def test_the_flags_default_to_the_old_behaviour():
    """A caller that carries neither reading gets the ladder as it was."""
    assert _score(BOSS, lone_ready_attacker=False, active_doomed=False) == 850


def test_the_rule_names_no_archetype_and_no_deck():
    """Deck-agnostic by construction: two readings of OUR board and the one
    Supporter that rewrites THEIRS."""
    rule = next(r for r in m._RULES_MEOWTH_FETCH if r.name == RULE)
    assert rule.when(_ctx(BOSS)) is True
    for other in (LILLIE, DAWN, m.Lanas_Aid, m.Xerosic_Machinations):
        assert rule.when(_ctx(other)) is False, (
            "solo el gusteo se abarata: el resto de la escalera sigue "
            "decidiendo entre las cartas que construyen nuestro tablero")


def test_the_two_halves_of_the_engine_read_the_same_pair():
    """The PLAY side spends two prizes on the refill under
    `_active_doomed_real and _ready_attacker_count <= 1`; the FETCH now answers
    that same board. Pinned as source, because a chain and a branch far apart
    drifting is exactly how this bug happened."""
    play = (ROOT / "ptcg" / "turn" / "options" / "play.py").read_text()
    assert "_active_doomed_real" in play and "_ready_attacker_count <= 1" in play
    card = (ROOT / "ptcg" / "turn" / "options" / "card.py").read_text()
    assert "lone_ready_attacker=(_ready_attacker_count <= 1)" in card
    assert "active_doomed=bool(_active_doomed_real)" in card
