"""Disrupting the opponent's hand: Xerosic's Machinations and Unfair Stamp.

They live TOGETHER on purpose: the ordering rule -- Xerosic BEFORE the Stamp,
because the Stamp leaves the opponent at 2 cards either way and the only thing
the order buys is the cards Xerosic sends to the discard FOREVER -- makes each
scorer consult the other. Separating them produces a circular import.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.calc.board import _active_of, _evolvable_counts
from ptcg.cards.ids import Abra, Alakazam_ex, Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Kadabra, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, Poke_Pad, SCORE_VETO, STAMP_MAX_HAND_SACRIFICED, STAMP_MIN_OP_HAND, STAMP_MIN_OP_HAND_VS_REFILL, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, XEROSIC_BIG_HAND, XEROSIC_SCORE_ALAKAZAM, XEROSIC_SCORE_GENERIC, XEROSIC_SCORE_LAST_RESORT, XEROSIC_SCORE_SOBRE_BOSS, XEROSIC_STAMP_ORDEN_MIN_OP_HAND, Xerosic_Machinations
from ptcg.state.zones import ZONE_DECK
from ptcg.engine.context import DecisionContext
from ptcg.engine.rules import _Adjustment, _FixedRule, _resolve_with_trace
from ptcg.turn.game_plan import plan_of


def _op_bodies(op_state):
    """Every Pokemon on THEIR board (active + bench).

    A pure board reading, and that is the point: the two predicates below are
    also consulted from the `agent()` scope, where the Stamp <-> Flip the Script
    chain is built LONG BEFORE the matchup flags (`op_is_alakazam_deck` and
    company) have been computed. What sits on the board is available everywhere.
    """
    if op_state is None:
        return []
    out = []
    act = _active_of(op_state)
    if act is not None:
        out.append(act)
    for p in (getattr(op_state, 'bench', None) or []):
        if p is not None:
            out.append(p)
    return out


def _op_refill_engine(op_state) -> bool:
    """Does their board REFUND the cards the Stamp denies?

    Fezandipiti ex: "Flip the Script" draws them 3 cards on a turn after one of
    their Pokemon was knocked out. The Stamp is played on the turn after one of
    OURS was -- i.e. on the turn we are answering with a KO of our own -- so the
    refund and the disruption land in the same window and cancel out. With that
    body on their board the Stamp has to deny FOUR cards
    (`STAMP_MIN_OP_HAND_VS_REFILL`) before it is worth its single copy.

    (registro_006 step 88 vs Alakazam, LOST: their Fezandipiti ex sat untouched
    on the bench, the Stamp denied one card, and the KO we took that same turn
    handed it back three.)
    """
    return any(getattr(p, 'id', 0) == Fezandipiti_ex for p in _op_bodies(op_state))


def _op_powerful_hand_line(op_state) -> bool:
    """Abra / Kadabra / Alakazam anywhere on their board, pre-evolutions of the
    stacks included. It is the board fact that makes OUR Xerosic irreplaceable:
    Powerful Hand does 20 per card in their hand, and capping that hand is the
    only answer the deck carries."""
    ids = set()
    for p in _op_bodies(op_state):
        ids.add(getattr(p, 'id', 0))
        for pre in (getattr(p, 'preEvolution', None) or []):
            ids.add(getattr(pre, 'id', 0))
    return bool(ids & {Abra, Kadabra, Alakazam_ex})


def _stamp_buries_the_last_xerosic(hand_counts, cards_in_deck,
                                   supporter_played, op_state) -> bool:
    """Would the Stamp shuffle away our LAST access to the Powerful Hand cap?

    The Stamp shuffles OUR WHOLE hand into the deck, and against the Alakazam
    line the Xerosic in that hand is not one more card: it is the answer to the
    attack that knocks our ex out (registro_006 step 75: Powerful Hand for 240
    on a 210 HP Ogerpon ex; the Xerosic capped their hand from 14 to 3 and left
    that same attack at 60).

    Three conditions, and all three have to hold:

      * a Xerosic in hand,
      * the turn's Supporter is ALREADY SPENT, so it cannot be played now and
        the only way to use it is to KEEP it for a later turn,
      * no other copy left in the deck -- with a drawable copy, shuffling the one
        in hand does not lose the access.

    It is the symmetric half of Lillie's `do_not_shuffle_the_last_xerosic`
    (main.py): Lillie's already refused to shuffle that card away, and the Stamp
    was the other card in the deck that shuffles our hand and did not.

    It only applies BELOW the disruption floor: with a big opposing hand the
    Stamp is worth the Xerosic, and the caller returns before reaching here.
    """
    if not _op_powerful_hand_line(op_state):
        return False
    if (hand_counts or {}).get(Xerosic_Machinations, 0) < 1:
        return False
    if not supporter_played:
        return False
    return (cards_in_deck or {}).get(
        Xerosic_Machinations, {}).get(ZONE_DECK, 0) == 0


def _our_cap_already_spent(c) -> bool:
    """Has OUR OWN Xerosic's Machinations already capped their hand THIS TURN?

    CARD RULE (user, `records/registro_006_pasos_074_hasta_087.json`, episode
    91690421, turn 6 vs Alakazam, LOST): once Xerosic has been played, the Unfair
    Stamp is NOT played -- not on that turn, not even with one of our bodies
    knocked out the turn before. It is KEPT for a later turn.

    The ORDER stays exactly as it was: with a giant opposing hand Xerosic goes
    first (`_xr_before_the_stamp`) because it DISCARDS and the Stamp only
    SHUFFLES. What changes is the second half of that sequence -- the Stamp no
    longer follows. After our own cap neither of its two halves pays:

      * DISRUPTION: Xerosic leaves them at `XEROSIC_HAND_CAP` = 3 and the Stamp
        leaves them at 2, so it denies ONE card and hands them two FRESH ones off
        the top of their deck. `STAMP_MIN_OP_HAND` = 4 already closed this half
        (that invariant is what registro_013 step 136 bought); it is stated here
        again because the rule is about the CARD, not about the floor.
      * REFILL: this is the half that was still open, and the one that lost this
        record. At step 81 our hand was three cards -- Lillie's Determination,
        Hydrapple ex and the Stamp -- so "we only sacrifice two" looked cheap and
        the Stamp went down: a Supporter for the next turn and the evolution of
        our Dipplin shuffled back into the deck to draw five random ones, and the
        single copy of the ACE SPEC burned for one denied card.

    The whole value of the Stamp is the resources it denies, and that value is
    measured against a FAT opposing hand. Our own Xerosic has just removed it:
    there is nothing left to deny today, and there will be on some later turn.
    Deck-agnostic on purpose -- it reads OUR play, not their archetype -- so it
    holds in every matchup, and it AUTO-EXPIRES: the flag is per-turn, so the
    Stamp is fully available again on the next one.

    `getattr` because the unit tests build stub contexts carrying only the fields
    their predicate reads.
    """
    return bool(getattr(c, 'our_xerosic_capped_this_turn', False))


def _stamp_worth_playing(op_hand_count, my_hand_len, *,
                         op_refill_engine=False,
                         buries_the_last_xerosic=False,
                         our_cap_already_spent=False) -> bool:
    """Card rule for Unfair Stamp (user, August 2026): the Stamp is only played
    if it DISRUPTS the opponent (opposing hand >= `STAMP_MIN_OP_HAND`, because
    it leaves them at 2) or if the REFILL is cheap (we sacrifice <=
    `STAMP_MAX_HAND_SACRIFICADA` cards, which is the hand WITHOUT the Stamp
    itself). See the constants block for the full reasoning.

    It holds for ANY opposing deck: the card behaves the same in every matchup,
    so no whitelist enters here. The two keyword-only clauses (August 2026) are
    not a whitelist either -- they are read off the BOARD by `_op_refill_engine`
    and `_stamp_buries_the_last_xerosic`, and they are optional so that a caller
    without a board at hand keeps the behaviour it had.

      * `op_refill_engine` RAISES the disruption floor: a board that draws three
        cards back the moment we take a KO refunds anything smaller.
      * `buries_the_last_xerosic` closes the REFILL clause: five new cards do not
        pay for the only copy of the card that answers Powerful Hand.
      * `our_cap_already_spent` closes BOTH clauses: after our own Xerosic the
        Stamp is kept for a later turn. See `_our_cap_already_spent`.

    With `None` (a caller without that datum at hand) it returns True: the rule
    only SUBTRACTS plays, it never invents one.
    """
    if our_cap_already_spent:
        return False
    if op_hand_count is None or my_hand_len is None:
        return True
    floor = (STAMP_MIN_OP_HAND_VS_REFILL if op_refill_engine
             else STAMP_MIN_OP_HAND)
    if op_hand_count >= floor:
        return True
    if buries_the_last_xerosic:
        return False
    return max(0, my_hand_len - 1) <= STAMP_MAX_HAND_SACRIFICED


def _stamp_worth_playing_ctx(c) -> bool:
    """`_stamp_worth_playing` with the three extra clauses filled in from the
    context. THE single entry point for every consumer that has a context: the
    scoring rule, `_stamp_pendiente` and the anti-Alakazam Lillie's veto all read
    the same answer, so a Stamp that is going to wait never collects the ordering
    yields of the turn (the paralysis documented in `_stamp_pendiente`).

    `getattr` throughout because the unit tests build stub contexts carrying only
    the fields their predicate reads.
    """
    state = getattr(c, 'state', None)
    op_state = getattr(c, 'op_state', None)
    return _stamp_worth_playing(
        getattr(c, 'op_hand_count', None),
        getattr(c, 'my_hand_len', None),
        op_refill_engine=_op_refill_engine(op_state),
        buries_the_last_xerosic=_stamp_buries_the_last_xerosic(
            getattr(c, 'hand_counts', None),
            getattr(c, 'cards_in_deck', None),
            bool(getattr(state, 'supporterPlayed', False)),
            op_state),
        our_cap_already_spent=_our_cap_already_spent(c))


def _stamp_pendiente(c) -> bool:
    """The Stamp is PLAYABLE and also DESERVES to be played this turn.

    The SINGLE source of the ordering vetoes that step aside for it (Boss's,
    Lillie's, Lana's, Dawn, Xerosic, the Meowth -> Last-Ditch chain and the
    Fezandipiti ability). It used to be enough that "we got knocked out + the
    Stamp is still in hand", but ever since `_stamp_worth_playing` can VETO the
    Stamp, that gate alone would have paralysed the turn: the way was given to a
    card that was no longer going to be played. By sharing the predicate, when
    the Stamp waits (opposing hand <= 2 and our own hand large) the Supporters
    carry on as normal -- and if our hand drops below 5 by playing items, the
    Stamp becomes available again in the same turn.

    IT DOES NOT WAIT FOR A TURN THAT ENDS THE GAME (user, registro_013 step 126
    vs the mirror, WON suboptimally). At mutual match point -- one prize each --
    our active Ogerpon ex already knocked out two different bodies on the
    opponent's bench, and Boss's Orders was in hand: gust + attack closed the game
    on the second action. This predicate returned True (we had been knocked out,
    the Stamp was in hand, their hand was large), so `yields_to_unfair_stamp`
    vetoed the Boss's down to -1 and the agent spent nineteen actions rebuilding a
    board for a game that was already over. The Stamp's whole value is the
    RESOURCES it denies for the turns to come; on a turn with a lethal route there
    are no turns to come, and its 5-card refill only feeds an opponent who is one
    prize from winning too. The plan answers that in one field, so every ordering
    veto that reads this predicate -- Boss's, Lillie's, Lana's, Dawn, Xerosic, the
    Meowth chain, Flip the Script -- steps back at once."""
    return (c.ko_last_turn
            and c.hand_counts.get(Unfair_Stamp, 0) >= 1
            and not plan_of(c).wins_this_turn
            and _stamp_worth_playing_ctx(c))


def _us_pokemon_jugable(c):
    if c.bench_count >= 5:
        return False
    h, f = c.hand_counts, c.field_counts
    if (h.get(Chikorita, 0) >= 1 and
            f.get(Chikorita, 0) + f.get(Bayleef, 0) + f.get(Meganium, 0) == 0):
        return True
    if (h.get(Applin, 0) >= 1 and
            f.get(Applin, 0) + f.get(Dipplin, 0) == 0):
        return True
    if (h.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
            f.get(Teal_Mask_Ogerpon_ex, 0) < 2):
        return True
    if h.get(Tapu_Bulu, 0) >= 1 and f.get(Tapu_Bulu, 0) == 0:
        return True
    if (h.get(Meowth_ex, 0) >= 1 and f.get(Meowth_ex, 0) == 0
            and not c.ko_last_turn):
        return True
    if h.get(Fezandipiti_ex, 0) >= 1 and f.get(Fezandipiti_ex, 0) == 0:
        return True
    return False


def _us_evo_jugable(c):
    """Is there an evolution the hand can really make THIS TURN?

    The pre-evolutions are counted through `_evolvable_counts`, not off the raw
    field: a body that came down (or evolved) during this turn cannot be evolved
    again, and the ladder this feeds is explicitly about what the hand can do
    TODAY (`_RULES_STAMP_PLAY`: Pokemon/evo 2000 < item 2500 < energy 3000 <
    nothing 7500). Without the filter the census counted a phantom evolution and
    pinned the Stamp to its lowest rung.

    (user, episode 90587542 step 150 vs Hop's: the Dipplin had evolved from an
    Applin on step 141 and the bench was full, so the menu offered NO evolution
    at all -- and the two Hydrapple ex in hand still priced the Stamp at 2000.
    It is the same shape as registro_006 step 84, the record that made
    `_evolvable_counts` exist.)

    MEASURED (`log/census_gate/`): the census disagreed on 31 of the 707 boards
    where the Stamp is priced (4.4%), and all 31 moved the rung. It buys ~2
    decisions in 1600 games -- 7 of 8 matchups bit-identical, `crustle_kangaskhan`
    among them, which is the matchup that punished this same cleanup at the four
    OTHER sites (see `_evolvable_counts`: do not unify those without measuring
    it again). Golden corpus 0 flips; winrate mean -0.23 with every cell inside
    the noise. A correctness fix, not a winrate one.
    """
    h = c.hand_counts
    f = _evolvable_counts(c.field_counts, c.field_at_turn_start,
                          c.forest_in_play)
    if h.get(Meganium, 0) >= 1 and f.get(Bayleef, 0) >= 1 and not c.meganium_in_play:
        return True
    if h.get(Bayleef, 0) >= 1 and f.get(Chikorita, 0) >= 1:
        return True
    if h.get(Hydrapple_ex, 0) >= 1 and f.get(Dipplin, 0) >= 1:
        return True
    if h.get(Dipplin, 0) >= 1 and f.get(Applin, 0) >= 1:
        return True
    return False


def _us_item_jugable(c):
    if c.itchy_pollen_active:
        return False
    h = c.hand_counts
    return (h.get(Bug_Catching_Set, 0) >= 1
            or (h.get(Ultra_Ball, 0) >= 1 and c.my_hand_len >= 3)
            or h.get(Night_Stretcher, 0) >= 1
            or h.get(Poke_Pad, 0) >= 1)


def _us_bonus_matchup(c):
    if c.op_is_alakazam_deck:
        return 400
    if c.op_is_control_deck or c.op_is_slowking_deck:
        return 350
    if c.op_is_gardevoir_deck:
        return 300
    if c.op_is_zoroark_deck:
        return 250
    return 0


def _xr_before_the_stamp(c):
    """Is Xerosic's Machinations played BEFORE Unfair Stamp?

    Both fit in the SAME turn -- the Stamp is an ITEM (ACE SPEC) and Xerosic a
    Supporter -- so no card is being chosen here: the ORDER is. And the two do
    different things to the opponent's hand:

      * Unfair Stamp **SHUFFLES it back into their deck** and gives them 2 cards.
      * Xerosic **DISCARDS** it down to 3.

    Playing Xerosic FIRST, the opponent loses `op_hand - 3` cards forever and the
    Stamp still leaves them at 2: the same board at the end of the turn, with
    half the opposing deck in the discard. The other way around, those cards go
    back to the deck and the Stamp also shuffles away OUR Xerosic (registro_008
    step 90 vs Alakazam: the Stamp took Boss's and Xerosic, and only one was
    recovered by luck).

    The cost is real -- the Supporter slot is spent BEFORE the Stamp's refill, so
    the 5 new cards can no longer pay for another Supporter -- hence the
    `XEROSIC_STAMP_ORDEN_MIN_OP_HAND` threshold: only when what gets burned is
    worth more than a whole hand.

    IT DOES NOT HAND THE TURN BACK (user, registro_006 step 81, episode 91690421
    vs Alakazam, LOST). This predicate used to revoke itself -- as soon as
    Xerosic was played `supporterPlayed` became True, and the Stamp was expected
    to recover its normal score and go down in the SAME turn. It no longer does:
    `_our_cap_already_spent` takes over the moment Xerosic resolves, and the
    Stamp is kept for a later turn. The two predicates hand off cleanly and there
    is no window between them -- this one holds while the Supporter slot is free,
    that one from the PLAY log onwards -- so the Stamp is vetoed for the whole
    turn either way, and by a rule that says which.
    """
    return (c.ko_last_turn
            and c.hand_counts.get(Unfair_Stamp, 0) >= 1
            and c.hand_counts.get(Xerosic_Machinations, 0) >= 1
            and not c.state.supporterPlayed
            and c.op_hand_count >= XEROSIC_STAMP_ORDEN_MIN_OP_HAND)


_RULES_STAMP_PLAY = [
    # CARD RULE (user, registro_006 step 81 vs Alakazam): our OWN Xerosic has
    # already capped their hand this turn -> the Stamp is KEPT for a later turn.
    # It is the first rule of the ladder so the trace names the real reason: the
    # value clause below would veto the same board, but reading
    # "no_disruption_no_refresh" hides that what closed it was a card WE played.
    # See `_our_cap_already_spent`.
    _FixedRule("our_xerosic_already_capped_them",
               _our_cap_already_spent,
               lambda c: SCORE_VETO),
    # CARD RULE (user, August 2026): without disruption (opposing hand <= 2) or a
    # cheap refill (we sacrifice > 4 cards) the Stamp is NOT played. It is not an
    # ordering veto: no other card of the turn revokes it, it only changes if the
    # board changes (e.g. our own hand drops by playing items). See
    # `_stamp_worth_playing`.
    # ...and BOTH halves are closed once our own Xerosic has capped their hand
    # this turn (`_our_cap_already_spent`): that one IS irrevocable for the rest
    # of the turn -- no later item can reopen it -- and the Stamp waits for a
    # turn where there is a hand left to deny.
    _FixedRule("no_disruption_no_refresh",
               lambda c: not _stamp_worth_playing_ctx(c),
               lambda c: SCORE_VETO),
    # ORDERING veto, not a value one (user, jul 2026): with a giant opposing hand,
    # Xerosic goes first and the Stamp waits -- for a LATER turn, ever since
    # `_our_cap_already_spent` picks it up where this rule leaves off. The Xerosic is
    # required to be REALLY going to be played (a score above last resort): if any
    # of its guards knocks it down to `XEROSIC_SCORE_LAST_RESORT` -- e.g.
    # `alakazam_yields_to_winning_gust`, where a Boss's decides the turn -- the
    # Stamp yields to nobody and is played normally. See `_xr_before_the_stamp`.
    _FixedRule("yields_the_order_to_xerosic",
               lambda c: (_xr_before_the_stamp(c)
                          and _score_xerosic_play(c)
                          > XEROSIC_SCORE_LAST_RESORT),
               lambda c: SCORE_VETO),
    # Rule (user): with Lillie's in hand and the opponent at <= 3 cards, do NOT
    # play the Stamp: its disruption adds little and refilling OUR hand pays
    # more (the Stamp would shuffle the Lillie's away; mutually exclusive plays).
    _FixedRule("yields_to_lillie_short_opponent_hand",
               lambda c: (c.hand_counts.get(Lillie_Determination, 0) >= 1
                          and c.op_hand_count <= 3
                          and not c.state.supporterPlayed),
               lambda c: SCORE_VETO),
    # The base value rises the LESS alternative use the hand has this turn
    # (Pokemon/evo < item < energy/stadium < nothing = 7500).
    _FixedRule("hand_with_a_pokemon_or_evo",
               lambda c: _us_pokemon_jugable(c) or _us_evo_jugable(c),
               lambda c: 2000),
    _FixedRule("hand_with_an_item",
               _us_item_jugable,
               lambda c: 2500),
    _FixedRule("hand_with_energy_or_stadium",
               lambda c: ((c.hand_counts[Basic_Grass_Energy] >= 1
                           and not c.state.energyAttached)
                          or (c.hand_counts.get(Forest_of_Vitality, 0) >= 1
                              and not c.forest_in_play)),
               lambda c: 3000),
]


# Every adjustment requires `s > 0`: they are bonuses to the value of a play that
# IS GOING TO HAPPEN, they must not resurrect a veto. Without the guard, a vetoed
# Stamp (SCORE_VETO = -1) came out of the resolver at +399 just from
# `bonus_matchup` vs Alakazam -- which is exactly the matchup where the ordering
# veto `yields_the_order_to_xerosic` lives.
_AJUSTES_STAMP_PLAY = [
    _Adjustment("early_turn",
            lambda c, s: s > 0 and c.state.turn <= 4,
            lambda c, s: s + 300),
    _Adjustment("we_are_losing_on_prizes",
            lambda c, s: s > 0 and c.my_prize > c.op_prize + 1,
            lambda c, s: s + 200),
    _Adjustment("bonus_matchup",
            lambda c, s: s > 0 and _us_bonus_matchup(c) != 0,
            lambda c, s: s + _us_bonus_matchup(c)),
    _Adjustment("aggro_and_losing",
            lambda c, s: (s > 0
                          and (c.op_is_aggro_deck or c.op_is_beedrill_deck)
                          and c.my_prize > c.op_prize),
            lambda c, s: s + 350),
]


def _score_unfair_stamp_play(ctx: DecisionContext) -> int:
    """Scores playing Unfair Stamp (hand refill). Body migrated to the RULES
    ENGINE (phase 4): rules and comments in _RULES_STAMP_PLAY."""
    return _resolve_with_trace("stamp->play", _RULES_STAMP_PLAY,
                               _AJUSTES_STAMP_PLAY, ctx, default=7500)


def _xr_below_the_alakazam_floor(c):
    """vs Alakazam, is the opposing hand still BELOW the six cards the cap
    needs? The floor of `_xr_gate_alakazam`, written on its own because it is
    also read as a hard veto (`alakazam_needs_six_cards`) and by the Last-Ditch
    fetch: the rule has to be answered BEFORE the card is searched for, not only
    when it is already in hand."""
    return c.op_is_alakazam_deck and c.op_hand_count < 6


def _xr_gate_alakazam(c):
    """vs Alakazam (the card's reason to exist): opposing hand >= 6, i.e.
    Powerful Hand already projecting 20 x (6 + 2) = 160.

    CARD RULE (user, august 2026, records/registro_003 step 17 -- episode
    91176376 vs Alakazam, LOST): SIX cards is a floor and it has no exceptions.
    On that turn the opponent held FOUR cards, the gate let the play through on
    its "a backup copy is left in the deck" branch, and the turn's Supporter was
    spent to discard ONE single card (4 -> 3): Powerful Hand went from 120 to
    100 while our hand kept a Xerosic that would have been worth 200+ damage of
    cap two turns later, when their hand was actually inflated. The two old
    escape hatches -- the early trigger with the Alakazam already active
    projecting lethal at 4-5 cards, and the backup copy that allowed spending
    the first copy from 4 -- are gone with it: both existed to play the cap
    BELOW the floor, which is exactly the mistake being fixed."""
    return c.op_is_alakazam_deck and not _xr_below_the_alakazam_floor(c)


def _xr_last_copy_locked_in_hand(c):
    """The Xerosic in hand is the LAST access to the Powerful Hand cap: no
    second copy in the deck and no Meowth ex left to re-search for it. Shared
    predicate: it is the condition of Lillie's `do_not_shuffle_the_last_xerosic`
    veto (Lillie's shuffles the hand into the deck and loses it forever), and
    the Xerosic side reads it so its own first-turn yield does not step aside
    for a Lillie's that is itself vetoed -- which would lose the Supporter slot
    entirely (the mutual-yield failure of Lillie's <-> Boss's)."""
    return (c.op_is_alakazam_deck
            and c.hand_counts.get(Xerosic_Machinations, 0) >= 1
            and c.op_hand_count >= 4
            and c.cards_in_deck.get(
                Xerosic_Machinations, {}).get(ZONE_DECK, 0) == 0
            and c.hand_counts.get(Meowth_ex, 0) == 0
            and (c.field_counts.get(Meowth_ex, 0) >= 2
                 or c.cards_in_deck.get(Meowth_ex, {}).get(ZONE_DECK, 0) == 0))


def _xr_ruta_a_lillie(c):
    """Is there a Lillie's Determination for THIS turn's Supporter slot -- in
    hand, or reachable by the fetch Meowth ex -> Last-Ditch Catch (the Meowth
    from hand, or dug out with an Ultra Ball)? It is the "no option to search
    for a Lillie's" of the first-turn rule, written as the routes the deck
    really has."""
    if c.hand_counts.get(Lillie_Determination, 0) >= 1:
        return True
    if c.cards_in_deck.get(Lillie_Determination, {}).get(ZONE_DECK, 0) < 1:
        return False
    if (c.meowth_ability_lock or not c.meowth_ld_free
            or c.bench_count >= 5 or c.field_counts.get(Meowth_ex, 0) >= 2):
        return False
    return (c.hand_counts.get(Meowth_ex, 0) >= 1
            or (c.hand_counts.get(Ultra_Ball, 0) >= 1
                and c.cards_in_deck.get(Meowth_ex, {}).get(ZONE_DECK, 0) >= 1))


def _xr_first_turn_yields_to_lillie(c):
    """OUR FIRST TURN GOING SECOND: Lillie's Determination takes the Supporter
    slot and Xerosic waits.

    On that turn the two cards are not comparable. With all six prizes untouched
    Lillie's draws EIGHT -- the largest refill in the deck, and the only turn on
    which the board is a lone active with nothing on the bench, so every card it
    draws has somewhere to go. Xerosic, by contrast, is capping a hand that has
    not been built yet: the opponent has just drawn their opening seven and
    played none of it, and Powerful Hand does not threaten anything until they
    have a board to attack from. Discarding those cards now only makes room for
    them to redraw; the cap is worth its Supporter later, when their hand is
    inflated AND an Alakazam is in play to punish it.

    Only going SECOND: the player going first may not play a Supporter on their
    first turn, so there is no slot to argue over.

    Exception, as stated by the user: Xerosic keeps the turn when it is the only
    Supporter we can reach -- no Lillie's in hand and no fetch that brings one
    (`_xr_ruta_a_lillie`). Second exception, structural: if the Lillie's would be
    vetoed anyway for being the card that shuffles our LAST Xerosic into the deck
    (`_xr_last_copy_locked_in_hand`), yielding would leave BOTH at -1 and the
    Supporter unplayed.

    (user, registro_002 step 11, episode 89633820 vs Alakazam -- WON in spite of
    this: hand {Ultra Ball, Xerosic, Lillie's, Lillie's, Meganium, Meganium},
    opponent on 5 cards, and the agent spent the turn's Supporter on Xerosic.)
    """
    # `getattr` for the same reason as `_alakazam_dig_xerosic_engine`: the unit
    # tests build stub contexts with only the fields their predicate reads, and
    # off the first turn this rule must not even look at the rest.
    if getattr(c, 'our_first_turn', False) is not True:
        return False
    return (not c.we_go_first
            and not c.state.supporterPlayed
            and _xr_ruta_a_lillie(c)
            and not _xr_last_copy_locked_in_hand(c))


_RULES_XEROSIC_PLAY = [
    # IT NEVER FIRES, AND IT IS KEPT ON PURPOSE (user, August 2026,
    # `utils/rule_census.py`: this veto and its two twins in the other Supporter
    # PLAY chains were evaluated ~222 000 times over the frozen corpus and 2 400
    # games and fired ZERO between them). The reason is not a wrong premise --
    # the failure mode of `_protect_last_supporter`, which was gated on a flag
    # that on a forced discard belongs to the OPPONENT -- it is that the ENGINE
    # already enforces one Supporter per turn and never offers a second one to
    # play. The guard is therefore redundant with a rule of the game, not with
    # another rule of ours, and it costs one comparison to keep saying so.
    _FixedRule("supporter_already_played",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # No effect if the opposing hand is already <= 3 (e.g. after an Unfair Stamp
    # this same turn): do not burn the Supporter for nothing.
    _FixedRule("opponent_hand_already_short",
               lambda c: c.op_hand_count <= 3,
               lambda c: SCORE_VETO),
    # THE FLOOR OF SIX CARDS vs ALAKAZAM (user, august 2026, records/registro_003
    # step 17 -- episode 91176376, LOST). Against the deck the card exists for,
    # the cap is NOT played until the opposing hand reaches six. See
    # `_xr_gate_alakazam` for the record.
    #
    # It is a VETO and not a fall-through to the last-resort band, and that is
    # the whole point of writing it as a rule of its own: below the floor the
    # ladder returned `XEROSIC_SCORE_LAST_RESORT` (20), and 20 is not "do not
    # play it", it is "play it if nothing else scores". On the record's turn the
    # menu was exactly {play Xerosic, end turn}, so the last-resort band would
    # have kept spending the Supporter on a one-card discard by elimination.
    # Below the floor the Xerosic is a card we are HOLDING for later, not a play
    # we are short of alternatives for.
    #
    # It goes ahead of every `_xr_gate_alakazam` branch below (which now cannot
    # fire under six anyway) and, deliberately, ahead of `generic_very_big_hand`
    # too: that branch needs >= 7 and is unreachable here, so the order costs
    # nothing and the floor reads as absolute. Only the Alakazam matchup is
    # touched; against every other deck the ladder is unchanged.
    _FixedRule("alakazam_needs_six_cards",
               _xr_below_the_alakazam_floor,
               lambda c: SCORE_VETO),
    # With a KO last turn and the Stamp in hand, the Stamp goes FIRST (it is an
    # Item and re-shuffles OUR hand). Same gate as Boss's/Lana's/Dawn.
    # EXCEPTION (user, jul 2026): with a GIANT opposing hand the order is
    # reversed -- the Stamp only returns those cards to the deck, Xerosic
    # DISCARDS them, and both fit in the same turn. See `_xr_before_the_stamp`;
    # the other side of the change is `yields_the_order_to_xerosic` in the Stamp.
    _FixedRule("yields_to_unfair_stamp",
               lambda c: (_stamp_pendiente(c)
                          and not _xr_before_the_stamp(c)),
               lambda c: SCORE_VETO),
    # Boss's Orders only takes priority when it WINS the game (user,
    # registro_006 step 85): there Xerosic yields and the Boss's (WIN_NOW 20000)
    # finishes. It used to yield to `boss_win_via_bench` too (a lethal gust that
    # only takes ONE prize), and with that the agent traded capping the opposing
    # hand for a single prize.
    _FixedRule("alakazam_yields_to_winning_gust",
               lambda c: (_xr_gate_alakazam(c) and c.win_via_boss_gust
                          and c.hand_counts.get(Boss_Orders, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # OUR FIRST TURN GOING SECOND: the slot belongs to Lillie's (draw EIGHT with
    # all six prizes up) -- see `_xr_first_turn_yields_to_lillie`. It is the
    # symmetric half of the Boss's `_boss_first_turn_yields` and of Lillie's own
    # `first_turn_always`, the two rules that already gave that turn to the
    # refill; Xerosic was the one Supporter that still took it. It goes ahead of
    # every yield gated on `_xr_gate_alakazam`, because its reason is the
    # calendar and not the matchup: on our first turn the cap is premature
    # against any deck.
    _FixedRule("first_turn_yields_to_lillie",
               _xr_first_turn_yields_to_lillie,
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # No attack and a short hand: development (Lillie's) is worth more than
    # disruption this turn.
    #
    # ...BUT ONLY WHILE THE CAP IS STILL CHEAP (user, `records/registro_006
    # _pasos_062_hasta_085.json`, episode 91851762, step 71, turn 6 vs Alakazam
    # -- LOST). Tapu Bulu promoted after a knockout with no energy on it, hand
    # of exactly three {Meganium, Lillie's Determination, Xerosic's
    # Machinations}, and the opponent holding TEN cards. This rule fired --
    # `active_cant_attack` and a hand of three, both true -- and dropped the cap
    # to `XEROSIC_SCORE_LAST_RESORT` (20), so the turn's Supporter went to
    # Lillie's (`refresh_short_hand`, 5000). Powerful Hand kept reading 20 x
    # (10 + 2) = 240 for the rest of the game.
    #
    # The premise was never wrong, it was UNBOUNDED: the sentence "development
    # is worth more than disruption" was said about the size of OUR hand and
    # never once asked how big THEIR hand was. Between the floor of six and an
    # opposing hand of twenty it answered the same thing, which is the same
    # blind spot `alakazam_yields_to_lillie_tiny_opponent_hand` was removed for,
    # read from the other end.
    #
    # The reading is `XEROSIC_BIG_HAND`, and deliberately no new number: it is
    # the ONE constant the play scorer (`generic_very_big_hand`) and the discard
    # scorer (`DISCARD_XEROSIC_CAPS_A_FAT_HAND`) already share to say "at this
    # size the cap is worth its Supporter". A card we would refuse to throw away
    # cannot be a card we refuse to play. With `_xr_gate_alakazam` imposing a
    # floor of six, the yield now lives in exactly one window -- an opposing
    # hand of six, where the cap discards three cards -- and above it the cap
    # takes the turn and the Lillie's waits.
    _FixedRule("alakazam_yields_to_lillie_short_hand",
               lambda c: (_xr_gate_alakazam(c) and c.active_cant_attack
                          and c.op_hand_count < XEROSIC_BIG_HAND
                          and sum(c.hand_counts.values()) <= 3
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # (REMOVED, august 2026: `alakazam_yields_to_lillie_tiny_opponent_hand`.
    # With a minimal opposing hand -- <= 4, where the cap discards ONE card --
    # it handed the Supporter to a Lillie's in hand (user, registro_002 step 17
    # vs Alakazam, LOST). The floor of six subsumes it and answers the same
    # board harder: under six the Xerosic is not played whether or not we hold a
    # Lillie's, so the rule could no longer fire -- `_xr_gate_alakazam` and
    # `op_hand_count <= 4` are now mutually exclusive.)
    # PRIORITY OVER BOSS'S (user, registro_006 step 85 vs Alakazam, LOST): with
    # Boss's Orders in hand and the opponent at 16 cards, the agent played Boss's
    # (a 2-prize gust, 6800) instead of Xerosic (6200) and left the opposing hand
    # untouched: their Powerful Hand (20 x card in their hand) kept hitting for
    # 320 and swept the board. Capping the hand is worth more than any gust that
    # does NOT win the game; the WINNING gust already returned above (rule
    # `alakazam_yields_to_winning_gust`). It is scored above
    # BOSS_SCORE_GUST_2PRIZE (6800), which was the band that used to win, and
    # below BOSS_SCORE_WIN_NOW (20000).
    _FixedRule("alakazam_priority_over_boss",
               lambda c: (_xr_gate_alakazam(c)
                          and c.hand_counts.get(Boss_Orders, 0) >= 1),
               lambda c: (XEROSIC_SCORE_SOBRE_BOSS
                          + min(300, 50 * (c.op_hand_count - 4))
                          + c.supporter_boost)),
    # Capping Powerful Hand: it scales with the opposing hand (5900-6200). It beats
    # a hydra-charged Lillie's (5800); below WIN_NOW/GUST_2PRIZE and the pivots.
    _FixedRule("alakazam_cap_the_hand",
               _xr_gate_alakazam,
               lambda c: (XEROSIC_SCORE_ALAKAZAM
                          + min(300, 50 * (c.op_hand_count - 4))
                          + c.supporter_boost)),
    # Generic: taking 4+ cards away is real value, but without Powerful Hand it goes
    # below a useful Lillie's/Lana's/Boss's. Only with an opposing hand >= 7.
    _FixedRule("generic_very_big_hand",
               lambda c: c.op_hand_count >= XEROSIC_BIG_HAND,
               lambda c: XEROSIC_SCORE_GENERIC + c.supporter_boost),
    # default: last resort (opposing hand 4-6 without the Alakazam matchup).
]


def _score_xerosic_play(ctx: DecisionContext) -> int:
    """Scores playing Xerosic's Machinations (id 1197): the opponent discards
    down to 3 cards. It is in the deck because of the Alakazam matchup (Powerful
    Hand does 20 per card in their hand). Body migrated to the RULES ENGINE
    (phase 4)."""
    return _resolve_with_trace("xerosic->play", _RULES_XEROSIC_PLAY, [],
                               ctx, default=XEROSIC_SCORE_LAST_RESORT)

__all__ = [
    '_xr_before_the_stamp',
    '_xr_below_the_alakazam_floor',
    '_xr_gate_alakazam',
    '_xr_last_copy_locked_in_hand',
    '_xr_ruta_a_lillie',
    '_xr_first_turn_yields_to_lillie',
    '_score_xerosic_play',
    '_RULES_XEROSIC_PLAY',
    '_op_bodies',
    '_op_refill_engine',
    '_op_powerful_hand_line',
    '_stamp_buries_the_last_xerosic',
    '_our_cap_already_spent',
    '_stamp_worth_playing',
    '_stamp_worth_playing_ctx',
    '_stamp_pendiente',
    '_us_pokemon_jugable',
    '_us_evo_jugable',
    '_us_item_jugable',
    '_us_bonus_matchup',
    '_score_unfair_stamp_play',
    '_RULES_STAMP_PLAY',
    '_AJUSTES_STAMP_PLAY',
]
