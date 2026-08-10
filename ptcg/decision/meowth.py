"""Meowth ex: Last-Ditch Catch and the value prediction.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.engine.rules import _FixedRule
from ptcg.cards.ids import Boss_Orders, Lillie_Determination, Xerosic_Machinations
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Boss_Orders, Dawn, Lillie_Determination
from ptcg.cards.ids import Basic_Grass_Energy, Boss_Orders, Dawn, Lanas_Aid, Lillie_Determination, Xerosic_Machinations
from ptcg.cards.tables import HAND_RESET_PLAY_IDS


_MEOWTH_FETCH_SUPPS = (Boss_Orders, Dawn, Lillie_Determination,
                       Lanas_Aid, Xerosic_Machinations)


class _CtxMeowthFetch:
    """Ctx of the Last-Ditch fetch: candidate card + flags of the turn."""

    def __init__(self, card_id, sv, hand_counts, supp_values, hand_size,
                 strong_attacker, op_hand_count, active_cant_attack,
                 win_via_boss, gust2_via_boss, deny_evo_via_boss,
                 devel_lillie, alakazam, first_turn=False,
                 lillie_alcanzable=False, gust_over_immune_active=False,
                 recovery_ko=False, hand_supp_val=0):
        # The best Supporter ALREADY IN HAND, on this same scale (`supp_values`).
        # It is the price of the turn's only Supporter slot: whatever the
        # Last-Ditch brings has to beat it to be played TODAY. See
        # `the_slot_is_taken_so_bring_what_survives`. Zero when the hand holds no
        # Supporter that the board values -- which includes the known blind spot
        # of `evaluate_supporters` (it never prices Xerosic's Machinations), and
        # zero is the conservative reading there: the rule simply does not fire.
        self.hand_supp_val = hand_supp_val
        # Does recovering Grass with Lana's Aid turn THIS turn -- a turn that
        # cannot attack at all -- into a knockout on their active? Computed once
        # in agent() as `_meowth_recovery_ko` over the shared arithmetic of
        # `ptcg/turn/game_plan.py::_recovery_creates_the_ko`, because the answer
        # needs the whole board (the discard, the attach routes still alive, the
        # damage formula) and this ctx only carries counts.
        self.recovery_ko = recovery_ko
        self.card_id = card_id
        # Is their active UNTOUCHABLE and their bench not? (`_boss_gust_immune_active`:
        # a dodge on heads, a Cornerstone, a Crustle, the Neutralization Zone --
        # whatever the reason, our attack on the body in front resolves for zero
        # and there is a body behind it that it would not). Then the ONLY
        # Supporter that turns this turn into damage is Boss's Orders, and the
        # fetch has to say so before the "no ready attacker" caps -- which are
        # true here, and for that very reason -- bury it under a refill.
        self.gust_over_immune_active = gust_over_immune_active
        # OUR FIRST turn: the anti-donk line benches Meowth ex even if the
        # Supporter is already in hand, and its fetch keeps the exception.
        self.first_turn = first_turn
        # Is there a Lillie's Determination REALLY reachable by this fetch?
        # (offered among the options of the prompt, or alive in the deck when the
        # fetch is PREDICTED before benching the Meowth). Without it, the
        # first-turn rule cannot degrade the other candidates.
        self.lillie_alcanzable = lillie_alcanzable
        self.alakazam = alakazam
        self.sv = sv
        self.hand = hand_counts
        self.supp_values = supp_values
        self.hand_size = hand_size
        self.strong_attacker = strong_attacker
        self.op_hand_count = op_hand_count
        self.active_cant_attack = active_cant_attack
        self.win_via_boss = win_via_boss
        self.gust2_via_boss = gust2_via_boss
        self.deny_evo_via_boss = deny_evo_via_boss
        self.devel_lillie = devel_lillie
        self.no_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) == 0)


def _v_meowth_fetch_value(c):
    score = c.sv
    if c.card_id == Boss_Orders and AGENT_STATE.op_is_crustle_deck:
        score += 100
    # Dawn (searches Basic+Stage1+Stage2 to assemble the evolution line) is
    # ONLY worth fetching with Meowth ex if we have Forest of Vitality (1261)
    # IN PLAY, which allows evolving the same turn (rush). WITHOUT Forest in
    # play we cannot accelerate the evolution: refilling the hand with
    # Lillie's Determination gives more immediate play/attack options. That is
    # why Dawn is pushed below the value of Lillie's, so Meowth ex fetches
    # Lillie's and not Dawn. WITH Forest in play Dawn keeps its value
    # (consistent with the Dawn/Lillie's tie-break around ~L6137). (user,
    # registro_004 step 53 vs Marnie's Grimmsnarl ex, LOST.)
    if (c.card_id == Dawn and not AGENT_STATE.forest_in_play
            and c.supp_values.get(Lillie_Determination, 0) > 0):
        score = min(score,
                    c.supp_values.get(Lillie_Determination, 0) - 50)
    return score


_RULES_MEOWTH_FETCH = [
    # FIRST TURN = ONLY LILLIE'S (user, log 88461779 step 16 vs Alakazam,
    # LOST). On OUR first turn the only reason to bench a Meowth ex is to
    # bring Lillie's Determination: turn 1 does not attack, does not evolve
    # and (going first) does not even offer playing Supporters, so the only
    # thing that decides the game is how much HAND we will have on turn 2.
    # Any other Supporter the Last-Ditch brings stays dead in hand -- and if on
    # turn 2 we play Lillie's itself, it also gets SHUFFLED away.
    # In that game the fetch brought a Xerosic's Machinations (branch
    # `xerosic_alakazam`: opposing hand >= 6 + strong attacker) while four
    # Lillie's sat in the deck: the Ultra Ball, the Meowth ex (a 2-prize body
    # on the bench) and the whole turn were spent to develop NOTHING.
    # It goes FIRST in the chain: no matchup branch (Xerosic, Boss's,
    # Dawn...) may hijack the first-turn fetch. Deck-agnostic: if the deck has
    # no reachable Lillie's (`lillie_alcanzable`), the rule degrades nobody and
    # the normal ladder decides.
    _FixedRule("first_turn_lillie_only",
               lambda c: (c.first_turn
                          and c.card_id == Lillie_Determination),
               lambda c: 1400),
    _FixedRule("first_turn_rest_yields_to_lillie",
               lambda c: c.first_turn and c.lillie_alcanzable,
               lambda c: min(c.sv, 40)),
    # REDUNDANT COPY (user, registro_010 step 118 vs Alakazam, WON with a
    # mistake): only ONE Supporter is played per turn, so bringing a 2nd copy
    # of one that is ALREADY in hand adds absolutely nothing -- the Meowth ex (a
    # 2-prize body on the bench) was spent to duplicate a card. On that turn
    # the fetch brought a second Xerosic's Machinations while holding one in
    # hand, instead of the Boss's Orders that was exactly what the engine that
    # benched the Meowth wanted. It goes FIRST in the chain: no other branch
    # may rescue a duplicate. 40 (not a veto) because the prompt requires
    # choosing a card: if ALL the candidates were duplicates we still have to
    # keep one. Deck-agnostic.
    _FixedRule("copy_already_in_hand",
               lambda c: (c.hand.get(c.card_id, 0) >= 1
                          and not c.first_turn),
               lambda c: 40),
    # THE FLOOR OF SIX CARDS, ASKED BEFORE THE SEARCH (user, august 2026,
    # records/registro_003 step 17 vs Alakazam, LOST). The play side now vetoes
    # the cap while the opposing hand is under six
    # (`alakazam_needs_six_cards`), and a Supporter we are not going to play is
    # not a Supporter worth spending the Last-Ditch Catch on: the Meowth ex is a
    # 2-prize body on the bench and the fetch only gets one card. The two
    # Xerosic branches below already ask for `op_hand_count >= 6`, so under the
    # floor they are silent -- what this rule closes is the ladder's TAIL, where
    # `supporter_value` would still let a Xerosic through on its raw value if
    # every other candidate scored lower.
    # 40 and not a veto, for the same reason as `copy_already_in_hand` above:
    # the prompt forces us to pick a card, so if every candidate were vetoed we
    # would still have to keep one. It fires only vs Alakazam; against any other
    # deck the generic branch (`xerosic_generico`, opposing hand >= 7) decides
    # as before.
    _FixedRule("alakazam_xerosic_needs_six_cards",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.alakazam
                          and c.op_hand_count < 6),
               lambda c: 40),
    # Winning finisher / 2 prizes via a Boss's Orders from the DECK.
    _FixedRule("winning_boss",
               lambda c: ((c.win_via_boss or c.gust2_via_boss)
                          and c.card_id == Boss_Orders),
               lambda c: 1300),
    # VALUE gust (deny-evo) via the Meowth engine (Meowth engine plan,
    # improvement A): the Boss's from the DECK cuts off the CHARGED
    # pre-evolution of the opposing ex attacker. 1280: below the winning
    # finisher (1300), above the refill/development Lillie's (1200-1250) --
    # with the threat on the bench, cutting the line beats refilling (user,
    # registro_006 step 82 vs Garchomp).
    _FixedRule("boss_deny_evo",
               lambda c: (c.deny_evo_via_boss
                          and c.card_id == Boss_Orders),
               lambda c: 1280),
    # THE FETCH THAT UNLOCKS THE ATTACK, NOT THE ONE THAT REFILLS THE HAND
    # (user, episode 90591443 step 84, turn 8 vs Marnie's Grimmsnarl ex, LOST).
    # A dead turn: our active Teal Mask Ogerpon ex at 2 of the 3 Myriad Leaf
    # Shower costs, a Meganium at 2 of 4, a second Ogerpon ex at 2 of 3, a bare
    # Tapu Bulu -- and NOT ONE GRASS IN HAND, so neither the turn's attachment
    # nor Teal Dance had anything to attach. The one place energy still existed
    # was the DISCARD, and the one card that reaches it is Lana's Aid.
    #
    # The ladder below reads that board correctly and answers it with the wrong
    # card: `stuck_without_energy` fires on exactly these boards ("the active
    # cannot attack and there is no Grass in hand") and hard-codes Lillie's
    # Determination as the answer, capping every other candidate -- Lana's Aid
    # included -- at 150. Refilling the hand is the right answer when it is a
    # CARD we are missing; here we were missing ENERGY, and it was already ours.
    #
    # What the recovery bought on the record's board: two Grass back, one on the
    # active (Meganium's Wild Growth makes each worth 2), Myriad Leaf Shower
    # 30 + 30 x (4 ours + 2 theirs) = 210, doubled by their Grass weakness = 420
    # on a 310 HP Marnie's Grimmsnarl ex -- their attacker and two prizes, from
    # a turn that was about to end having gusted a Froslass for nothing.
    #
    # It asks the SHARED arithmetic (`_recovery_creates_the_ko`), the same one
    # the winning route uses, so it is deck-agnostic: no card is named beyond
    # the two this deck recovers with, and the flag is false the moment the
    # discard, the attach routes or the damage do not add up. 1290: under the
    # gust that ends the game or takes two prizes without needing a charge chain
    # to hold together (`winning_boss` 1300), over the line cut
    # (`boss_deny_evo` 1280) -- a knockout on the body in front is worth more
    # than denying an evolution -- and over every cap further down.
    #
    # IT YIELDS TO A SHORT HAND, and that is not a hedge: with two cards or
    # fewer the refill is not competing with the recovery, it CONTAINS it.
    # Lillie's Determination draws eight, the deck is thirteen Basic Grass deep,
    # and shuffling a hand that small away costs nothing -- so the refill very
    # probably pays the same attack AND leaves a hand behind it. The recovery
    # only wins when there is a real hand to protect, which is the record's
    # board (seven cards: a Hydrapple ex, a second Meowth ex, a Boss's Orders)
    # and the reason a Lillie's there would have thrown the turn away twice.
    # `hand_size <= 2` is the ladder's own cut-off, the one `short_hand` below
    # already uses; this rule does not invent a second one.
    _FixedRule("recovery_creates_the_ko",
               lambda c: (c.recovery_ko and c.card_id == Lanas_Aid
                          and c.hand_size >= 3),
               lambda c: 1290),
    # THE BODY IN FRONT CANNOT BE TOUCHED, THE ONE BEHIND IT CAN (user, episode
    # 90325863, turn 8 vs a Dragapult / Azumarill deck). Their Marill hid
    # behind a Hide that came up heads: every attack of ours resolves for zero
    # against it, and the only card in the deck that turns the turn back into
    # damage is Boss's Orders -- gust an attackable body off their bench and
    # knock THAT one out.
    #
    # The fetch did not see it, and the reason it did not is worth writing
    # down: an untouchable active makes `strong_attacker` false, so the
    # `no_attacker*` rules further down fire and cap every candidate that is
    # not Lillie's at `min(sv, 200)`. The Boss's -- the answer -- was being
    # punished by the very fact that created the problem. In the record it
    # came out behind Dawn.
    #
    # 1270: under the winning finisher (1300) and the line cut (1280), over
    # the refill (1200-1250) and well over those caps. Deck-agnostic and
    # wall-agnostic: `gust_over_immune_active` is the same
    # `_boss_gust_immune_active` that already feeds the Meowth engine, so a
    # Cornerstone or a Crustle in front reads exactly like the coin.
    _FixedRule("boss_beats_the_untouchable_active",
               lambda c: (c.gust_over_immune_active
                          and c.card_id == Boss_Orders),
               lambda c: 1270),
    _FixedRule("lillie_development",
               lambda c: (c.devel_lillie
                          and c.card_id == Lillie_Determination),
               lambda c: 1250),
    # THE CAP OUTRANKS THE GUST (user, registro_006 step 62 vs Alakazam, LOST).
    # Same board, same turn and the same two cards as the play scorer's
    # `alakazam_priority_over_boss` -- only here they are still in the DECK and
    # the Last-Ditch Catch has to pick one. It picked the Boss's Orders: their
    # Fezandipiti ex was gusted up and knocked out for two prizes (5 -> 3), and
    # the opponent kept a hand of SIXTEEN. Their Powerful Hand hit back for 320,
    # which is more than anything we own, and took the Ogerpon ex that was
    # carrying six energies -- six turns of charging, for a two-prize trade they
    # matched immediately. The gust also SAVED the Alakazam: switching it out of
    # the active spot is what put it out of reach of the 240 our attack was
    # already doing to it that same turn.
    #
    # The two scales contradicted each other. Once the pair is IN HAND the play
    # scorer has said since registro_006 step 85 that capping the hand beats any
    # gust that does not WIN the game (XEROSIC_SCORE_SOBRE_BOSS 7000 over
    # BOSS_SCORE_GUST_2PRIZE 6800); the fetch, deciding which of the two ever
    # reaches the hand, still ranked the gust first. The fetch cannot be allowed
    # to hand-pick the card the play scorer would then refuse to play first.
    #
    # 1310 is the mirror of that band: above the two-prize gust (`winning_boss`
    # 1300) and the deny-evo gust (`boss_deny_evo` 1280), and it steps aside for
    # the gust that ENDS the game -- `not c.win_via_boss` is the same exemption
    # as the play scorer's `alakazam_yields_to_winning_gust`. It carries the
    # guards of `xerosic_alakazam` below unchanged, so it never fires anywhere
    # that rule would not: a fat opposing hand and either a hand to play or an
    # attacker already settled.
    _FixedRule("xerosic_priority_over_boss",
               lambda c: (c.card_id == Xerosic_Machinations
                          and not c.win_via_boss
                          and c.alakazam
                          and c.op_hand_count >= 6
                          and (c.hand_size >= 3 or c.strong_attacker)),
               lambda c: 1310),
    # Xerosic vs Alakazam (user): with a fat opposing hand (Powerful Hand =
    # 20 x card), Meowth ex fetches Xerosic to cap the damage. Refined
    # (user, registro_004 step 53 vs Alakazam, LOST): if we ALREADY have a
    # strong attacker in play (Hydrapple/Ogerpon), Xerosic rules EVEN IF our
    # hand ends up empty after benching the Meowth (an opposing hand of 13
    # cards = Powerful Hand 260, which knocks out everything of ours; capping
    # that is worth more than refilling with Lillie's when the attack is
    # already settled) -> 1260, above the development Lillie's (1250) and the
    # short-hand refill (1200), below the winning Boss's (1300). Without a
    # strong attacker the previous rule stands (only with hand >= 3, at 1200).
    _FixedRule("xerosic_alakazam",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.alakazam
                          and c.op_hand_count >= 6
                          and (c.hand_size >= 3 or c.strong_attacker)),
               lambda c: 1260 if c.strong_attacker else 1200),
    # GENERIC Xerosic in the Last-Ditch fetch (Meowth engine plan, improvement
    # B): against ANY deck with an opposing hand >= 7, taking 4+ cards away is
    # real value (the generic Xerosic scorer already plays it at 3380 if it is
    # in hand; before this it was not even a fetch candidate outside Alakazam).
    # 1100: below the refill/development Lillie's (1200-1250) and the Boss's
    # (1280/1300) -- only if there is no better option. Guards:
    # `strong_attacker` (with the attack already settled the disruption is
    # worth it; WITHOUT a strong attacker, digging with Lillie's -- ladders
    # 1000-1200 -- comes first) and an active-that-cannot-attack (so Xerosic
    # does not hijack the DEAD TURN fetch, whose whole point is to bring
    # Lana's/Lillie's to get out of the jam).
    _FixedRule("xerosic_generico",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.op_hand_count >= 7
                          and c.strong_attacker
                          and not c.active_cant_attack),
               lambda c: 1100),
    # THE SLOT IS ALREADY TAKEN, SO WHAT IS BROUGHT IS FOR TOMORROW (user,
    # august 2026, `records/registro_005_pasos_041_hasta_059.json` step 52 --
    # episode 91176376 vs Alakazam, LOST).
    #
    # The Last-Ditch Catch brought a **Dawn** while a **Boss's Orders** sat in
    # hand, and the ctx of that very prompt priced them on this same scale:
    #
    #     Boss's Orders (in hand) 970  >  Dawn 900  >  Lillie's Determination 800
    #
    # Only ONE Supporter is played per turn. With the Boss's above every
    # candidate, the card the fetch brings CANNOT be the Supporter of this turn
    # -- and the record played it out exactly so: the Boss's gusted a Kadabra for
    # the prize and the Dawn was still in hand when the turn ended.
    #
    # The ladder never asked the question. Every branch above compares the
    # candidates against EACH OTHER; none of them looks at what the hand already
    # holds, so a card is chosen for a slot that is not on offer.
    #
    # Once the slot is gone the fetch is choosing for a LATER turn, and that
    # changes which card is best. Dawn is above Lillie's here only because of the
    # SAME-TURN rush its premium is made of (`_v_meowth_fetch_value` lets it keep
    # its value when a Forest of Vitality is in play, which is what lets a body
    # played this turn evolve at once) -- and a rush needs the slot the Boss's is
    # taking. The refill does not: Lillie's draws eight whenever it is played.
    #
    # So the refills are EXEMPT and everything else is capped at 40, the same
    # "the prompt still forces a card" band as `copy_already_in_hand`. Deck-
    # agnostic on both halves: the refills are `HAND_RESET_PLAY_IDS`, read off
    # the PRINTED TEXT (any card that shuffles or discards the hand -- Lillie's,
    # Lacey, Judge, Carmine), and the comparison is a number the ctx already
    # carries.
    #
    # It goes LAST of the reasons and just above the caps, which is what keeps it
    # honest: every branch that names a REASON to bring a card -- the winning
    # gust, the line cut, the recovery that creates the KO, the Xerosic cap vs
    # Alakazam -- has already returned above it. Those say "this card is worth
    # more than the one in hand even if the scales disagree", and this rule must
    # not talk over them (`xerosic_priority_over_boss` is literally the case
    # where the fetch scale and the play scale rank the two cards the opposite
    # way round). What is left below is the tail, where nothing has a reason.
    _FixedRule("the_slot_is_taken_so_bring_what_survives",
               lambda c: (c.hand_supp_val > 0
                          and c.hand_supp_val >= c.sv
                          and c.card_id not in HAND_RESET_PLAY_IDS),
               lambda c: min(c.sv, 40)),
    _FixedRule("short_hand",
               lambda c: c.hand_size <= 2,
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 100))),
    _FixedRule("stuck_without_energy",
               lambda c: c.active_cant_attack and c.no_energy_in_hand,
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 150))),
    _FixedRule("stuck_without_lillie_in_hand",
               lambda c: (c.active_cant_attack and
                          c.hand.get(Lillie_Determination, 0) == 0),
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 150))),
    _FixedRule("no_attacker_medium_hand",
               lambda c: not c.strong_attacker and c.hand_size <= 5,
               lambda c: (1000 if c.card_id == Lillie_Determination
                          else min(c.sv, 200))),
    _FixedRule("no_attacker",
               lambda c: not c.strong_attacker,
               lambda c: (800 if c.card_id == Lillie_Determination
                          else min(c.sv, 400))),
    _FixedRule("supporter_value",
               lambda c: True,
               _v_meowth_fetch_value),
]

__all__ = [
    '_CtxMeowthFetch',
    '_MEOWTH_FETCH_SUPPS',
    '_v_meowth_fetch_value',
    '_RULES_MEOWTH_FETCH',
]
