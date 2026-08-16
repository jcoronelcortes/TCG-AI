"""The gust that ends the game is not a jam.

Origin (user, `records/registro_010_pasos_129_hasta_137.json`, step 131, episode
93517174 vs **Dragapult** -- WON, but with one prize where two were on offer):

    US (2 prizes)                          RIVAL (5 prizes)
    active  Meganium, 2 of 4 {G}           active  Drakloak 90/90
    bench   Teal Mask Ogerpon ex  8 {G}    bench   Drakloak 90/90, 1 {G}
            Teal Mask Ogerpon ex  4 {G}            **Fezandipiti ex** 210/210, 0 {G}
            Teal Mask Ogerpon ex  2 {G}            Dreepy 70/70
            Fezandipiti ex, Munkidori
    hand    Boss's Orders, ...             stadium their Artazon

        [0] their bench #0  Drakloak        <-- gusted
        [1] their bench #1  Fezandipiti ex
        [2] their bench #2  Dreepy

Our Meganium sat at two of the four energies *Petal Dance* costs, so it did not
attack -- but its retreat cost is two, and it could pay it. Behind it, a Teal
Mask Ogerpon ex at EIGHT effective energies (four Grass cards doubled by Wild
Growth). *Myriad Leaf Shower* counts the energy on BOTH actives, so against the
bare Fezandipiti ex it reads 30 + 30 x 8 = **270** on a 210 HP body worth **two
prizes** -- our last two.

Retreat, promote, attack, game. The agent gusted the Drakloak instead, took one
prize with 300 damage, and played on.

BOTH HALVES OF THE CARD HAD THE ANSWER AND NEITHER SPENT IT, which is the shape
this file exists to pin. The PLAY half priced the Supporter at `win_via_bench`
(`ptcg/turn/supporters.py`): its retreat-and-promote detector walked their bench
with `_bench_attacker_can_ko`, found the body whose knockout wins... and
`break`s without recording which body it was. The TARGET half built the reading
again, correctly -- `_ctx_gust_target` came out of that board with
`can_ko=True, prizes=2, wins_now=True` on the Fezandipiti ex -- and then handed
it to a ladder with no rung for winning.

WHICH LADDER RUNS IS DECIDED BY OUR ACTIVE, AND THAT IS THE DEFECT.
`ptcg/turn/options/card.py` routes the candidates to `_RULES_GUST_NUISANCE` when
our active cannot attack this turn. That is a sound proxy for "no knockout is on
offer" only while the knockout has to come from the front, and it does not:
`can_ko` has always had a second route -- retreat, promote, attack -- and that
route is at its strongest precisely when the active is stuck, because a stuck
active is what makes retreating free.

So the jam ladder priced three bodies by what escaping them would cost the
opponent, and it is prize-blind by construction: its only knockout-aware rung,
`opponent_line_higher_evolution`, is gated on `line_rank >= 1` and therefore
cannot see a BASIC at all. The Drakloak -- a Stage 1 of their line we could also
knock out -- took 6000 + 3000 + 50 = **9050**; the Fezandipiti ex fell through to
`net_stuck` for 500 + 100 = **600**. One prize outranked the game by 8450.

THE CORRECTION is `gust_wins_the_game` in `_ADJUST_GUST_NUISANCE`: the sentence
the offensive chain already carries, written in the other ladder. `max()` and
not `+`, because the rules above hand out SCORE_FORBID for a free retreat, for
Latias freeing the basics and for the Iron Thorns lock -- and every one of those
is an argument about the board we get to keep after the gust. There is no such
board.

DECK-AGNOSTIC BY CONSTRUCTION. It reads our bench's damage, their body's HP,
`prize_count_op` and our own prize count. No card id, no matchup, no evolution
line: any deck whose active is stuck with a charged finisher behind it gets the
same answer, and the last test here shows it on a line the rule was never
written against.
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
from rule_trace import adjustments, resolve  # noqa: E402
from state_builder import G, Scenario, pk  # noqa: E402

BOSS = m.Boss_Orders
DRAKLOAK = m.Drakloak
DREEPY = m.Dreepy
FEZANDIPITI = m.Fezandipiti_ex
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
MUNKIDORI = m.Munkidori
GRASS = m.Basic_Grass_Energy

# The record it came from is transient working data (`records/` is git-ignored
# and a fresh harvest renumbers every file), so the observation is pinned here
# instead -- the same thing every other record-derived test in this suite does.
_FIXTURE = ROOT / "tests" / "fixtures" / "the_gust_that_ends_the_game_step131.json"


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


def _observation():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


# ---------------------------------------------------------------------------
# 1. The record: the board, and the choice it now makes
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_the_finding_describes():
    """Two prizes left, a stuck active that can still retreat, a charged
    finisher on the bench and a two-prize ex on theirs."""
    obs = _observation()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert len(mine["prize"]) == 2                    # the game is two prizes away
    active = mine["active"][0]
    assert active["id"] == MEGANIUM
    # It cannot attack (Petal Dance costs 4) but it CAN pay its way out (2).
    assert len(active["energies"]) == 2
    assert m.RETREAT_COST[MEGANIUM] == 2

    # The finisher, already charged, on our bench.
    assert max(len(b["energies"]) for b in mine["bench"]
               if b["id"] == OGERPON) == 8

    # Their bench: the Stage 1 of their line, the two-prize ex, the basic.
    assert [b["id"] for b in theirs["bench"]] == [DRAKLOAK, FEZANDIPITI, DREEPY]
    assert theirs["bench"][1]["hp"] == 210
    assert not theirs["bench"][1]["energies"]

    # ...and the menu is the gust target select, with one option per body.
    assert obs["select"]["effect"]["id"] == BOSS
    assert len(obs["select"]["option"]) == 3


def test_the_agent_now_gusts_the_body_whose_knockout_ends_the_game():
    """The whole finding in one assertion: index 1, the Fezandipiti ex."""
    assert m.agent(_observation()) == [1]


def test_without_the_rule_the_same_board_gusts_the_stage_one(monkeypatch):
    """The control. Take `gust_wins_the_game` out of the jam ladder and the
    board reproduces the recorded mistake exactly -- so the fixture is a real
    witness and not a board that would have been answered right anyway."""
    import ptcg.turn.options.card as card_options
    monkeypatch.setattr(
        card_options, "_ADJUST_GUST_NUISANCE",
        [a for a in card_options._ADJUST_GUST_NUISANCE
         if a.name != "gust_wins_the_game"])
    assert m.agent(_observation()) == [0]


# ---------------------------------------------------------------------------
# 2. The reading was never wrong -- only the ladder that consumed it
# ---------------------------------------------------------------------------

def _contexts_of_the_record(monkeypatch):
    """The three `_CtxGustObjetivo` the live turn built, keyed by card id."""
    import ptcg.turn.options.card as card_options
    seen = {}
    real = card_options._ctx_gust_target

    def _spy(card, o, *a, **k):
        ctx = real(card, o, *a, **k)
        seen[card.id] = ctx
        return ctx

    monkeypatch.setattr(card_options, "_ctx_gust_target", _spy)
    m.agent(_observation())
    assert len(seen) == 3, seen
    return seen


def test_the_target_reading_already_knew_the_gust_won(monkeypatch):
    """`can_ko` found the retreat-and-promote route, `prize_count_op` priced it
    at two and `wins_now` compared it with our two prizes. Nothing here was
    missing on the day the game was played."""
    ctxs = _contexts_of_the_record(monkeypatch)
    fez = ctxs[FEZANDIPITI]
    assert fez.can_ko and fez.prizes == 2 and fez.wins_now

    # And the two bodies that do NOT end the game are read as such.
    assert ctxs[DRAKLOAK].can_ko and not ctxs[DRAKLOAK].wins_now
    assert ctxs[DREEPY].can_ko and not ctxs[DREEPY].wins_now


def test_the_jam_ladder_cannot_see_a_basic_at_all(monkeypatch):
    """The prize blindness that produced the inversion: the only
    knockout-aware rung of the jam ladder is gated on `line_rank >= 1`, so a
    two-prize BASIC never reaches it -- however lethal it is."""
    ctxs = _contexts_of_the_record(monkeypatch)
    assert ctxs[DRAKLOAK].line_rank == 1 and ctxs[DRAKLOAK].line_can_ko
    assert ctxs[FEZANDIPITI].line_rank == 0 and not ctxs[FEZANDIPITI].line_can_ko


def _jam(ctx):
    return resolve(m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE, ctx,
                   default=-200)


def test_the_winning_gust_outranks_the_jam_it_used_to_lose_to(monkeypatch):
    """9050 for the Stage 1 against 600 for the game. Now the order is the
    other way round, and by a margin no jam rung can reach."""
    ctxs = _contexts_of_the_record(monkeypatch)
    fez, why = _jam(ctxs[FEZANDIPITI])
    drak, _ = _jam(ctxs[DRAKLOAK])

    assert "gust_wins_the_game" in adjustments(why)
    assert fez > drak
    # The ceiling of the whole jam ladder is the relay band, 20000 + 2000/prize.
    assert fez >= 100000


# ---------------------------------------------------------------------------
# 3. The scope: it fires on the winning turn and on no other
# ---------------------------------------------------------------------------

def _synthetic(my_prizes=2, op_bench=None, ogerpon_cards=4, meganium_cards=1):
    """The record's shape, rebuilt so the prize count and their bench move.

    Our active is a Meganium short of its attack cost and able to pay its
    retreat; the finisher waits on the bench. Energy is counted in CARDS,
    because Wild Growth makes each Grass worth two symbols and the whole board
    turns on that: four cards on the Ogerpon are the eight effective energies
    that read 270 on a bare 210 HP body.
    """
    if op_bench is None:
        op_bench = [pk(DRAKLOAK, pre_evo=[DREEPY]),
                    pk(FEZANDIPITI),
                    pk(DREEPY)]
    return (Scenario(turn=10, step=131, tac=3, first_player=0,
                     energy_played=True, supporter_played=False,
                     own_prizes=my_prizes)
            .my_active(pk(MEGANIUM, energies=[G] * (2 * meganium_cards),
                          fisicas=meganium_cards,
                          pre_evo=[CHIKORITA, BAYLEEF]))
            .my_bench(pk(OGERPON, energies=[G] * (2 * ogerpon_cards),
                         fisicas=ogerpon_cards),
                      pk(OGERPON, energies=[G, G], fisicas=1))
            .my_hand(BOSS)
            .op_active(pk(DRAKLOAK, pre_evo=[DREEPY]))
            .op_bench(*op_bench)
            .op_zones(hand=4, deck=20, prizes=5)
            .menu_gust()
            .build())


def _winners_of(obs, monkeypatch):
    """The candidates the live turn read as `wins_now`, by card id."""
    import ptcg.turn.options.card as card_options
    seen = {}
    real = card_options._ctx_gust_target

    def _spy(card, o, *a, **k):
        ctx = real(card, o, *a, **k)
        seen[card.id] = ctx.wins_now
        return ctx

    monkeypatch.setattr(card_options, "_ctx_gust_target", _spy)
    m.agent(obs)
    return {cid for cid, won in seen.items() if won}


def test_the_synthetic_board_reproduces_the_record():
    """Same answer on a board built from scratch: the reading does not depend
    on anything the fixture happens to carry."""
    assert m.agent(_synthetic(my_prizes=2)) == [1]


def test_with_prizes_left_over_the_jam_reading_is_untouched():
    """Three prizes: the same knockout no longer ends the game, `wins_now` is
    False and the ladder answers exactly what it answered before -- the Stage 1
    of their line. The rule is scoped to the turn that closes, so it cannot be
    what a broad measurement moves."""
    assert m.agent(_synthetic(my_prizes=3)) == [0]


def test_a_finisher_that_falls_short_does_not_promise_a_win(monkeypatch):
    """Two prizes still on the table, but three Grass cards on the Ogerpon are
    six effective energies: 30 + 30 x 6 = 210 reaches the ex, 30 + 30 x 5 = 180
    does not. At two cards nothing on their bench is `wins_now` and the jam
    reading comes straight back. The rule rides on the damage model, not on the
    prize count alone."""
    assert _winners_of(_synthetic(my_prizes=2, ogerpon_cards=3), monkeypatch) \
        == {FEZANDIPITI}
    assert _winners_of(_synthetic(my_prizes=2, ogerpon_cards=2), monkeypatch) \
        == set()
    assert m.agent(_synthetic(my_prizes=2, ogerpon_cards=2)) == [0]


def test_an_active_that_cannot_pay_its_retreat_has_no_route_to_promise(monkeypatch):
    """The seat never opens: with no energy on the Meganium the promote route
    does not exist, so `can_ko` is False on every body and the winning gust is
    never claimed.

    It is asserted on the READING and not on the index the turn returns,
    because on that board another rung answers -- and answers well:
    `without_a_ko_prefer_the_dead_body` prefers the bare ex as a TRAP. Same
    target, a different sentence, and pinning the index would hide which of the
    two was speaking."""
    assert _winners_of(_synthetic(my_prizes=2, meganium_cards=0), monkeypatch) \
        == set()


def test_between_two_winners_the_prizes_break_the_tie():
    """Two bodies that both end the game: the tie-break is what the knockout
    PAYS, which is the only thing left to choose by once both are lethal."""
    obs = _synthetic(my_prizes=1,
                     op_bench=[pk(DREEPY), pk(FEZANDIPITI)])
    assert m.agent(obs) == [1]


# ---------------------------------------------------------------------------
# 4. The rest of the turn: the gust is only worth what the turn then cashes
# ---------------------------------------------------------------------------
#
# Aiming the gust is one decision of three, and a target that the turn does not
# then convert is not a fix -- it is a worse board. The record proves the other
# two against a Drakloak (it retreated, promoted the charged Ogerpon and
# attacked), but the body in front is different now and 210 HP is not 90, so the
# route is asserted rather than argued.

def _after_the_gust(menu):
    """The board one action later: their Fezandipiti ex dragged into the active
    spot, our Meganium still stuck in front of it."""
    sc = (Scenario(turn=10, step=133, tac=4, first_player=0,
                   energy_played=True, supporter_played=True, own_prizes=2)
          .my_active(pk(MEGANIUM, energies=[G, G], fisicas=1,
                        pre_evo=[CHIKORITA, BAYLEEF]))
          .my_bench(pk(OGERPON, energies=[G] * 8, fisicas=4),
                    pk(OGERPON, energies=[G, G], fisicas=1))
          .my_hand(GRASS)
          .op_active(pk(FEZANDIPITI))
          .op_bench(pk(DRAKLOAK, pre_evo=[DREEPY]), pk(DREEPY))
          .op_zones(hand=4, deck=20, prizes=5))
    return menu(sc).build()


def test_the_turn_steps_aside_for_the_finisher():
    """Our Meganium does not attack, so the only thing worth doing with the
    front seat is vacating it. The menu offers the retreat and every card in
    hand; the answer is the retreat."""
    obs = _after_the_gust(lambda sc: sc.menu_hand(with_retreat=True,
                                                  with_attack=True))
    chosen = m.agent(obs)[0]
    assert obs["select"]["option"][chosen]["type"] == int(m.OptionType.RETREAT)


def test_the_seat_goes_to_the_body_that_reaches_270():
    """Both benched bodies are Teal Mask Ogerpon ex; only one of them finishes.
    Myriad Leaf Shower reads 30 + 30 x 8 = 270 off the eight effective energies
    on bench slot 0 and 30 + 30 x 2 = 90 off slot 1."""
    obs = _after_the_gust(lambda sc: sc.promote_after_retreat())
    assert m.agent(obs) == [0]


def test_and_then_it_attacks():
    """The promoted finisher in front of the 210 HP body, with the attack and
    END both on the menu."""
    sc = (Scenario(turn=10, step=136, tac=7, first_player=0,
                   energy_played=True, supporter_played=True,
                   retirado=True, own_prizes=2)
          .my_active(pk(OGERPON, energies=[G] * 8, fisicas=4))
          .my_bench(pk(OGERPON, energies=[G, G], fisicas=1),
                    pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]))
          .my_hand(GRASS)
          .op_active(pk(FEZANDIPITI))
          .op_bench(pk(DRAKLOAK, pre_evo=[DREEPY]), pk(DREEPY))
          .op_zones(hand=4, deck=20, prizes=5)
          .menu_hand(with_attack=True)
          .build())
    chosen = m.agent(sc)[0]
    assert sc["select"]["option"][chosen]["type"] == int(m.OptionType.ATTACK)


# ---------------------------------------------------------------------------
# 5. Nothing in it names a card
# ---------------------------------------------------------------------------

def test_the_rule_reads_the_board_and_not_the_matchup():
    """The same board with their evolution line replaced by bodies the rule was
    never written against: a bare Munkidori standing in for the Stage 1 the jam
    ladder used to prefer. The two-prize ex is still the answer."""
    obs = _synthetic(my_prizes=2,
                     op_bench=[pk(MUNKIDORI), pk(FEZANDIPITI), pk(MUNKIDORI)])
    assert m.agent(obs) == [1]


def test_the_rule_is_written_without_an_id():
    """A guard against the correction drifting back into a matchup: the rung's
    source may not mention a card, a deck or an evolution line."""
    import inspect

    from ptcg.decision import boss_orders

    rung = next(a for a in boss_orders._ADJUST_GUST_NUISANCE
                if a.name == "gust_wins_the_game")
    source = inspect.getsource(rung.when) + inspect.getsource(rung.apply)
    for forbidden in ("Drakloak", "Fezandipiti", "Dragapult", "op_alakazam",
                      "op_dragapult_line", "card_id"):
        assert forbidden not in source, forbidden
