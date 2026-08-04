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


_MEOWTH_FETCH_SUPPS = (Boss_Orders, Dawn, Lillie_Determination,
                       Lanas_Aid, Xerosic_Machinations)


class _CtxMeowthFetch:
    """Ctx of the Last-Ditch fetch: candidate card + flags of the turn."""

    def __init__(self, card_id, sv, hand_counts, supp_values, hand_size,
                 strong_attacker, op_hand_count, active_cant_attack,
                 win_via_boss, gust2_via_boss, deny_evo_via_boss,
                 devel_lillie, alakazam, first_turn=False,
                 lillie_alcanzable=False):
        self.card_id = card_id
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
    _FixedRule("lillie_development",
               lambda c: (c.devel_lillie
                          and c.card_id == Lillie_Determination),
               lambda c: 1250),
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
