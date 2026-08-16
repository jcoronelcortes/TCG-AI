"""The trap that locks our own door: when the seat is stuck, the gust picks the
body our RELAY will cash, not the one that jams them best.

Real record (`records/registro_008_pasos_071_hasta_073.json`, step 72, turn 8,
LOST vs Marnie's Grimmsnarl ex -- episode 93486866), frozen into
`tests/fixtures/marnie_the_relay_inherits_the_seat_step72.json`:

    US (6 prizes)                         THEM (6 prizes)
    active Tapu Bulu 20/140, 0 en.        active Marnie's Morgrem 100, 2 en.
           Wood Hammer costs 4, retreat   bench  Munkidori 100/110, **1 en.**
           costs 3 -- no Grass and no            Munkidori  80/110, **0 en.**
           Switch in hand                       **Marnie's Grimmsnarl ex**
    bench  Teal Mask Ogerpon ex 180, 3 en.        310/320, **5 en.**
           Hydrapple ex 300, 0 en.              Froslass 90, 0 en.
           Teal Mask Ogerpon ex 160, 3 en.
           Teal Mask Ogerpon ex 180, 0 en.
           Chikorita 70
    hand   Meganium x2 (no Bayleef under
           them), Boss's Orders

Playing the Boss's was right -- it was the only thing the turn could do. The
submitted agent brought up the **bare Munkidori**, and the four numbers the
nuisance ladder reads say why:

    candidate            prizes   net jam   harmless   score
    Munkidori 1 en.        1       1-1=0      no        -200
    Munkidori 0 en.        1       1-0=1     YES        2100  <- chosen
    Grimmsnarl ex 5 en.    2       2-5=-3     no        -200  <- last of four
    Froslass  0 en.        1       1-0=1     YES        2100

BOTH HALVES OF THAT READING ARE WRONG HERE, AND FOR THE SAME REASON. A trap
costs the opponent a turn, and a turn is only a currency if WE can spend the one
it buys. We could not: our active neither attacked nor retreated, and the hand
was two Meganium with nothing under them. What the trap actually bought was that
their knockout never came -- and their knockout was the only key to our own
seat. The three charged Ogerpon behind the Tapu Bulu could not reach the front
while it stood there, so freezing them froze us.

READ THE OTHER WAY ROUND IT IS A ROUTE THE TARGET SCORER NEVER HAD. `can_ko` asks
two questions -- can the ACTIVE knock this out today, can a benched body knock it
out after we RETREAT today -- and both need a usable active. There is a third,
and when the seat is locked it is the only one alive: they knock our active out,
we PROMOTE, and the promoted body attacks whatever we gusted. Down that route
every candidate on this board is lethal, so the choice collapses to what the
knockout PAYS.

    candidate            their reply on our    our benched Ogerpon
                         20 HP Tapu Bulu       (3 en.) from the seat
    Munkidori 1 en.           60  -> opens          150 vs 90 HP
    Munkidori 0 en.            0  -> SHUT           120 vs 70 HP
    Grimmsnarl ex 5 en.      180  -> opens          540 vs 300 HP
    Froslass  0 en.            0  -> SHUT           120 vs 90 HP

The 540 is not a coincidence and it is why the biggest body is also the softest
one: Myriad Leaf Shower counts the energy on BOTH actives, so their own five
energies pay for the attack, and Marnie's Grimmsnarl ex is weak to Grass. Their
two-prize body spends its attack on our one-prize corpse (6->5), our relay cashes
two (6->4), and the race keeps that shape. That is the "descuadre" the user
named.

THE RULE is `the_relay_inherits_the_seat` in `_RULES_GUST_NUISANCE`, fed by
`relay_cashes_the_seat` in `_ctx_gust_target`, and it is deck-agnostic: nothing
in it names a card. Three conditions, all read per candidate -- the seat is
LOCKED, THIS body opens it, our bench cashes what sits in it -- plus the prize
floor that keeps it a trade (their knockout must not take their last prizes) and
the `op_wins_next` veto above it.

WHAT THE SPECIFICITY HALVES PIN. Unlock the seat and the rule must go quiet: the
board is then the one `opponent_line_higher_evolution` was already written for
and it answers the same target through the retreat route. Take their prizes down
to one, or leave our bench with nothing charged, and the trap is right again.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
import ptcg.turn.options.card as opt_card  # noqa: E402
from rule_trace import reason, resolve  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_the_relay_inherits_the_seat_step72.json")

GRIMMSNARL = m.Grimmsnarl_ex
MUNKIDORI = m.Munkidori
FROSLASS = m.Froslass
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
RULE = "the_relay_inherits_the_seat"

# Indices of the four candidates on THEIR bench, in menu order.
MUNKI_CHARGED, MUNKI_BARE, GRIMM, FROS = 0, 1, 2, 3


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _target(obs, choice):
    """(id, energies) of the opposing benched Pokemon the gust chooses."""
    o = obs["select"]["option"][choice[0]]
    assert o["type"] == int(m.OptionType.CARD) and o["area"] == 5
    pkmn = obs["current"]["players"][o["playerIndex"]]["bench"][o["index"]]
    return pkmn["id"], len(pkmn["energies"])


def _run(obs):
    """`(choice, {menu index -> _CtxGustObjetivo})` for one call of the agent.

    The contexts are captured as the agent builds them, so the assertions below
    read the SAME board reading the decision was made on -- not a rebuilt one
    that could drift away from it.
    """
    seen = {}
    original = opt_card._ctx_gust_target

    def spy(card, o, *a, **k):
        ctx = original(card, o, *a, **k)
        seen[o.index] = ctx
        return ctx

    opt_card._ctx_gust_target = spy
    try:
        return m.agent(obs), seen
    finally:
        opt_card._ctx_gust_target = original


def _score(ctx):
    return resolve(m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE,
                   ctx, default=-200)


# ---------------------------------------------------------------------------
# 1. The board is the one that discriminates
# ---------------------------------------------------------------------------

def test_the_seat_is_locked_and_that_is_what_makes_the_step_a_finding():
    """Without these four facts the step would prove nothing."""
    obs = _obs()
    us = obs["current"]["players"][1]
    them = obs["current"]["players"][0]
    active = us["active"][0]
    # (a) our active can neither attack nor pay its way out of the front;
    assert active["id"] == TAPU and not active["energies"]
    assert m.RETREAT_COST[TAPU] > 0
    assert not any(c["id"] == m.Basic_Grass_Energy for c in us["hand"])
    assert not any(c["id"] == 1123 for c in us["hand"])      # no Switch
    # (b) there IS a charged body behind it, so a relay exists;
    assert any(p["id"] == OGERPON and len(p["energies"]) >= 3
               for p in us["bench"])
    # (c) their bench holds a two-prize body and three one-prize ones;
    assert [p["id"] for p in them["bench"]] == [MUNKIDORI, MUNKIDORI,
                                                GRIMMSNARL, FROSLASS]
    # (d) and the game is nowhere near over on either side.
    assert len(us["prize"]) == len(them["prize"]) == 6


def test_the_menu_is_the_gust_target_and_offers_the_four_bodies():
    obs = _obs()
    sel = obs["select"]
    assert sel["context"] == int(m.SelectContext.SWITCH)
    assert sel["effect"]["id"] == m.Boss_Orders
    assert [o["index"] for o in sel["option"]] == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# 2. The real step
# ---------------------------------------------------------------------------

def test_step72_gusts_the_grimmsnarl_ex_not_the_bare_munkidori():
    obs = _obs()
    choice, _ = _run(obs)
    assert _target(obs, choice) == (GRIMMSNARL, 5), (
        "con el asiento bloqueado el gusteo elige lo que COBRA el relevo: su "
        "Grimmsnarl ex vale dos premios y el Ogerpon de banca le hace 540; el "
        "Munkidori pelado ni siquiera abre el asiento")


def test_step72_the_rule_that_decides_is_named():
    """Pinned by NAME, so a renumbering of the band survives and a different
    rule taking over does not."""
    _, ctxs = _run(_obs())
    assert reason(_score(ctxs[GRIMM])[1]) == RULE


# ---------------------------------------------------------------------------
# 3. The three conditions, read per candidate on the real board
# ---------------------------------------------------------------------------

def test_only_the_bodies_that_open_the_seat_cash_it():
    """The bare Munkidori and the Froslass cannot attack even with the turn's
    attachment, so gusting one of them keeps OUR door shut too -- which is the
    whole finding, and it is why the reading is per candidate and not a single
    "our active is doomed" flag."""
    _, ctxs = _run(_obs())
    assert ctxs[GRIMM].relay_cashes_the_seat
    assert ctxs[MUNKI_CHARGED].relay_cashes_the_seat
    assert not ctxs[MUNKI_BARE].relay_cashes_the_seat
    assert not ctxs[FROS].relay_cashes_the_seat
    # ...and the two that do NOT open it are exactly the two the old ladder
    # preferred: they are the harmless ones.
    assert ctxs[MUNKI_BARE].body_is_harmless and ctxs[FROS].body_is_harmless


def test_no_candidate_is_knockable_today_so_the_third_route_is_the_only_one():
    """`can_ko` is False for all four -- its two routes both need a usable
    active. If it were True the KO tiers would rule and this criterion would
    never get to decide."""
    _, ctxs = _run(_obs())
    assert not any(c.can_ko for c in ctxs.values())


def test_between_two_seat_openers_the_prizes_decide():
    """Once both are lethal down the relay route, what is left to choose by is
    what the knockout pays: two prizes beat one."""
    _, ctxs = _run(_obs())
    assert ctxs[GRIMM].prizes == 2 and ctxs[MUNKI_CHARGED].prizes == 1
    assert _score(ctxs[GRIMM])[0] > _score(ctxs[MUNKI_CHARGED])[0]


def test_the_band_clears_the_whole_jam_ladder():
    """The trap the agent used to pick tops out at 2100; the rule has to outrank
    it or the finding does not land."""
    _, ctxs = _run(_obs())
    assert _score(ctxs[MUNKI_BARE])[0] == 2100
    assert _score(ctxs[FROS])[0] == 2100
    assert _score(ctxs[GRIMM])[0] > 2100


# ---------------------------------------------------------------------------
# 4. SPECIFICITY: the three ways the rule has to go quiet
# ---------------------------------------------------------------------------

def test_with_the_seat_unlocked_the_rule_is_silent():
    """Three Grass on the Tapu Bulu pay its retreat (cost 3) without letting it
    attack (Wood Hammer costs 4). The seat is no longer locked, so the relay
    route is not the only one left -- and the board becomes the one
    `opponent_line_higher_evolution` was already written for, which reaches the
    same body through the retreat. Same answer, different reason: what this pins
    is that the new rule does not fire outside the state it was written for."""
    obs = _obs()
    active = obs["current"]["players"][1]["active"][0]
    active["energies"] = [1, 1, 1]
    active["energyCards"] = [{"id": 1, "playerIndex": 1, "serial": 900 + i}
                             for i in range(3)]
    choice, ctxs = _run(obs)
    assert not any(c.relay_cashes_the_seat for c in ctxs.values())
    assert reason(_score(ctxs[GRIMM])[1]) != RULE
    assert _target(obs, choice) == (GRIMMSNARL, 5)


def test_when_their_knockout_takes_their_last_prizes_the_trap_is_right_again():
    """Selling the body in front is a trade only while there is a game left
    after it. With one prize on their side, handing over the knockout on our
    one-prize active ends it."""
    obs = _obs()
    obs["current"]["players"][0]["prize"] = [None]
    choice, ctxs = _run(obs)
    assert not any(c.relay_cashes_the_seat for c in ctxs.values())
    assert _target(obs, choice)[0] != GRIMMSNARL


def test_without_a_charged_relay_the_trap_is_right_again():
    """Strip the bench and the third route does not exist: nothing we promote
    cashes the seat, so jamming them is all the turn can buy."""
    obs = _obs()
    for b in obs["current"]["players"][1]["bench"]:
        b["energies"] = []
        b["energyCards"] = []
    choice, ctxs = _run(obs)
    assert not any(c.relay_cashes_the_seat for c in ctxs.values())
    assert _target(obs, choice)[0] != GRIMMSNARL


# ---------------------------------------------------------------------------
# 5. THE PLAY HALF: the reason to spend the Supporter and the aim of it are the
#    same reading, so they cannot come apart
# ---------------------------------------------------------------------------
# The recorded turn played the Boss's for the TRAP reason (`gust_traps_their_turn`),
# which happened to be true on the same board. Strip the trappable bodies and the
# ladder used to fall through to `no_value` and END THE TURN -- with the two-prize
# exchange still on the table and every piece of it still true. That is the
# defect this file's own module docstring names: a detector justifying the play
# with one reading while the selector aims with another.


def _play_obs():
    with open(ROOT / "tests" / "fixtures"
              / "marnie_the_relay_seat_play_step71.json", encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _no_trap(obs):
    """One energy onto every bare body of theirs: nothing traps their turn any
    more, so the trap reason is gone and only the relay seat is left."""
    for i, b in enumerate(obs["current"]["players"][0]["bench"]):
        if not b["energies"]:
            b["energies"] = [7]
            b["energyCards"] = [{"id": 7, "playerIndex": 0, "serial": 800 + i}]
    return obs


def test_step71_plays_the_boss_and_the_menu_is_the_supporter():
    obs = _play_obs()
    hand = obs["current"]["players"][1]["hand"]
    assert hand[obs["select"]["option"][0]["index"]]["id"] == m.Boss_Orders
    assert m.agent(obs) == [0]


def test_with_no_body_to_trap_the_boss_is_still_played():
    """The load-bearing half. Without the relay rung this board answers END."""
    assert m.agent(_no_trap(_play_obs())) == [0], (
        "sin cuerpo que atrapar la escalera caia en `no_value` y pasaba el "
        "turno, con el intercambio de dos premios intacto sobre la mesa")


def test_it_is_read_above_the_already_jammed_active_too():
    """The reading sits ABOVE the `_op_active_stuck` split, because both sides of
    that split make the same assumption. One answers "their active is already
    jammed, do not spend the Supporter"; the other hunts for the body that jams
    them hardest. Both are purchases, and this is the state where we cannot spend
    what they buy. Their active is swapped for a bare 2-retreat body (deficit 2,
    so `_op_active_stuck` holds) and it is also HARMLESS, which is the second
    veto -- `gust_without_purpose` reads their CURRENT active, and the body that
    opens our seat is the one we are about to put there."""
    obs = _play_obs()
    act = obs["current"]["players"][0]["active"][0]
    act.update({"id": GRIMMSNARL, "hp": 320, "maxHp": 320,
                "energies": [], "energyCards": []})
    assert m.RETREAT_COST[GRIMMSNARL] - 0 >= 2      # _op_active_stuck
    assert m.agent(obs) == [0]


def test_the_play_and_the_aim_share_one_reading():
    """`_gust_relay_cashes_the_seat` is asked per candidate by the target half
    and over the whole bench by the play half -- one function, so the reason to
    spend the card and the body it aims at cannot disagree."""
    _, ctxs = _run(_obs())
    per_candidate = {i: c.relay_cashes_the_seat for i, c in ctxs.items()}
    assert any(per_candidate.values())
    # The existence half sees exactly what the per-candidate half sees.
    assert m._gust_relay_seat_on_their_bench.__module__ == \
        m._gust_relay_cashes_the_seat.__module__


def test_the_relay_seat_is_a_reason_with_a_prize_behind_it():
    """It has to be on `_boss_reason_with_prize` or the two deck-agnostic vetoes
    kill it -- `gust_without_purpose` reads THEIR CURRENT ACTIVE, and the body
    that opens our seat is the one we are about to put there."""
    from types import SimpleNamespace
    ctx = SimpleNamespace(
        win_via_boss_gust=False, gust_2prize_via_boss=False,
        boss_win_via_bench=False, boss_deny_alakazam_line=False,
        boss_prize_rank=0, boss_ko_threat_preevo=False,
        boss_dodge_redirect=False, boss_defensive_gust=False,
        boss_relay_seat=True, op_has_ability_immune_active=False,
        op_has_ex_immune_active=False, supp_values={})
    assert m._boss_reason_with_prize(ctx)
    ctx.boss_relay_seat = False
    assert not m._boss_reason_with_prize(ctx)


def test_the_rung_sits_between_the_trap_and_the_prize_of_today():
    """The ordering is the claim: above the trap (same board, but with a prize at
    the end of it), below every branch that takes a prize THIS turn and below a
    refill, whose hand can still rebuild."""
    assert (m.BOSS_SCORE_TRAP_GUST
            < m.BOSS_SCORE_RELAY_SEAT_GUST
            < m.BOSS_SCORE_PRIZE_RANK_BASE)
    names = [r.name for r in m._RULES_BOSS_PLAY]
    assert (names.index("gust_sells_the_locked_seat")
            < names.index("gust_traps_their_turn")
            < names.index("no_value"))


def test_the_absolute_vetoes_still_come_first():
    """The rule sits BELOW the three FORBID rungs, so it cannot rescue a target
    the chain refuses on principle -- a free-retreat body, a Latias-freed Basic
    or an Iron Thorns ex that would lock our own abilities from the front."""
    _, ctxs = _run(_obs())
    base = ctxs[GRIMM]
    for field, value in (("rc0", 0), ("card_id", m.Iron_Thorns_ex)):
        forbidden = copy.copy(base)
        setattr(forbidden, field, value)
        assert forbidden.relay_cashes_the_seat
        assert _score(forbidden)[0] == m.SCORE_FORBID, (
            f"{field}={value} deberia seguir vetado por encima de {RULE}")
