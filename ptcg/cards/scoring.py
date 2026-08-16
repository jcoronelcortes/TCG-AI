"""Scoring constants shared by several phases -- and the BANDS they live in.

Every decision the agent makes is a number, and the numbers are not arbitrary:
they are arranged in BANDS, so that what matters more can never be outbid by
what matters less. Read this before adding a constant anywhere, because the
value you pick is a claim about priority, and picking it by eye is how a sound
rule ends up vetoing a decisive one.

THE GLOBAL SCALE (defined in `ptcg/cards/ids.py`, listed here because that is
where the reasoning belongs):

    50000   SCORE_WIN_GAME       ending the game beats everything
    20000   SCORE_DEVELOP_BASE   base for benching a Pokemon
    10000   SCORE_ITEM_BASE      base for playing a non-Pokemon card
        -1  SCORE_VETO           do not play this
      -100  SCORE_CANCEL         below the veto, so an index tie cannot pick it
     -5000  SCORE_USELESS_ATTACK attacking into an immunity
    -10000  SCORE_NEVER          never
   -100000  SCORE_FORBID         illegal or self-harming; absolutely not

Two properties of that scale carry most of the weight. The negatives are
ORDERED rather than a single "no", so that vetoes of different strength do not
collapse into a tie. And a tie is genuinely dangerous: when two options share a
score the MENU ORDER decides, which is the engine's order and not ours -- the
reason several constants below exist purely to keep two rungs apart.

THE PROMOTION BAND, which is what most of this file defines. Choosing who takes
the front seat after a knockout is the decision with the most competing
opinions, so it has its own layered structure:

    +20000  PROMO_KO_BONUS       whoever knocks their active out goes first
     +1200  PROMO_KO_FRONT       ...and among knockers, who outlives whom
      9450  PROMO_LAST_STAND     at their match point, who absorbs the reply
     -6000  PROMO_DOOMED_PENALTY a body that dies anyway yields to a survivor
     -1500  PROMO_PRIZE_PENALTY  per extra prize handed over
    -30000  PROMO_MATCH_POINT_VETO   this promotion LOSES the game

Each constant's own comment carries the game that set its value and, more
usefully, the neighbouring numbers it had to clear or stay under. That
arithmetic is the real specification: `PROMO_KO_FRONT` is 1200 because it must
sit above every incidental adjustment in its branch and below every deliberate
one, and the comment enumerates both sides.

WHY A TIE-BREAK MUST STAY SMALL. A generic tie-break exists to order options
that measured rules do not distinguish. Make it large and it starts overruling
rules that were each written from a specific lost game -- which is exactly what
happened when `PROMO_KO_FRONT` was first tried wider, and it moved corpus
decisions onto bodies those matchups deliberately keep back.

The two helpers here, `_SUPP_PLAY_IDS` and `_purchase_of_this_turn`, share one
doctrine: the decision that SPENDS a resource and the decision that prices the
result afterwards must not be able to contradict each other, so both consult
the same source.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cards.ids import Boss_Orders, Dawn, Lanas_Aid, Lillie_Determination, Xerosic_Machinations


# Floor of the commitment: above the maximum of any other Supporter in hand
# (Xerosic ~7300 is the highest) so the tie-break does not depend on the deck.
SCORE_LD_SUPP_COMPROMETIDO = 8000


# --- WHICH Supporter will be PLAYED this turn? ------------------------------
# Only ONE Supporter is played per turn, so any decision that SPENDS a resource
# to SEARCH for a Supporter (Meowth ex / Last-Ditch Catch, Poke Pad...) needs to
# know BEFOREHAND who is going to take that single slot. These two helpers are
# the single source of that answer: they dispatch to the SAME `_score_*` the
# scoring loop uses, so the decision to spend the resource and the decision of
# which Supporter ends up being played cannot contradict each other.
_SUPP_PLAY_IDS = (Boss_Orders, Xerosic_Machinations, Lillie_Determination,
                  Dawn, Lanas_Aid)


# Main attackers evaluated in the ready-to-attack blocks.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)


# WHO GOES IN FRONT OF THE MEGA STARMIE LINE. The top of the user's order and
# the gap between its rungs. The band sits ABOVE the sacrifice menu's own top
# rung (6000, the Chikorita of `_doomed_sac_context`) because it is a different
# question with a different answer: that order asks which of two evolution
# lines we would rather spend, this one asks which body pays ONE prize instead
# of two against a deck that one-shots any ex we leave in front. Seven rungs
# 100 apart -- Tapu Bulu, Applin without energy, Applin with energy, Chikorita,
# Dipplin, Bayleef, Meowth ex -- so no two of them can ever tie and have the
# menu order decide. See STARMIE_SAC_PROMOTE_ORDER in ptcg/cards/ids.py.
OPENING_SAC_PROMOTE_TOP = 7000
OPENING_SAC_PROMOTE_STEP = 100


# Terminal PROMOTION adjustment (see "SURVIVAL WHEN PROMOTING"). The doomed body
# drops far enough to yield to any real survivor (the measured case: a charged
# Ogerpon 4557 -> -1443, below the Hydrapple ex at 259).
PROMO_DOOMED_PENALTY = 6000


# With no survivors, each extra prize we hand over costs this much.
PROMO_PRIZE_PENALTY = 1500


# Whoever KNOCKS OUT the opposing active is promoted above anyone who does not,
# tank included (user). Above the maximum score of the promotion branches
# (9500 = `_promote_setup_ko_attacker`) so that it is a GUARANTEE and does not
# depend on the knocker scoring higher base than the tank:
# `_ko_prefer_basic_general` gives 8500+ to a 1-prize basic and the sturdy wall
# 6100, so a knocker at ~4500 could lose. Among several knockers the base score
# decides -- EXCEPT where `PROMO_KO_FRONT` speaks (see below).
PROMO_KO_BONUS = 20000


# THE FRONT SPOT AMONG THE ONES THAT KNOCK OUT (user, registro_012 step 172 vs
# Alakazam). "Among several knockers the base score decides" was measured false:
# that base score is 500 + `hp // 10` + energies + a flavour bonus per species,
# so between a Teal Mask Ogerpon ex at 210 HP and a Hydrapple ex at 140 -- both
# finishing the same Alakazam -- HP was worth SEVEN points and the flavour
# ninety. This demotes a knocker that an EQUALLY PRICED knocker outlives: the
# knockers are grouped by price (`ko_front_price_rung`) and ordered by current HP
# INSIDE each group. Across prices it says nothing -- which price we would rather
# pay is already decided by rules measured one board at a time.
#
# 1200 sits ABOVE every incidental adjustment of that branch -- the 150 between
# "attacks now" and "attacks after attaching", `hp // 10` (<= 33), the energy
# count, the +-100 per species, the 120/40 of the promotion lookahead, the -250
# for weakness, the -300 of anti-Cubchoo and the +-280 of the Drednaw / Sylveon
# / Neutralization Zone blocks -- and BELOW every deliberate one, which is where
# this generic tie-break has to yield: the +2000 of the matchup attacker when
# confused, the +2500 of the prize mismatch, the +3000 of prize denial, the
# +4000 of the best attacker, the +5000 / +6000 of the anti-wall rules.
#
# It stays inside the knocker band by construction: 20000 - 1200 = 18800, and
# even stacked with the match-point penalty of the sibling rule
# (20000 - 6000 - 1200 = 12800) it is still far above the 9500 of the highest
# body that takes no prize.
PROMO_KO_FRONT = 1200


# THE FRONT SPOT UNDER A LOCK THAT MUTES IT (user, registro_010 step 81 vs a
# Cubchoo stall deck). The tie-break above orders knockers by who OUTLIVES whom,
# and against Cubchoo that question has no content: *Snotted Up* does 10 damage,
# every candidate outlives it, and HP decided the seat. What decides it there is
# MOBILITY -- the lock mutes whatever we put in front, so the body promoted today
# has to buy its way out again tomorrow, and Hydrapple ex pays 3 (two whole Grass
# cards under Wild Growth) where Teal Mask Ogerpon ex pays 1. On the board that
# produced this the two of them knocked out the same 70 HP Cubchoo and the HP
# tie-break handed the seat to the Hydrapple by 1272 points.
#
# 1800 is set by the two numbers it sits between: ABOVE `PROMO_KO_FRONT` (1200)
# plus the -300 of the anti-Cubchoo nail penalty it completes, because those two
# are exactly what it has to overrule; and BELOW the +2000 of the matchup
# attacker when confused, the first of the deliberate rules this must still yield
# to. Like its neighbour it is a penalty on the dominated knocker and never a
# bonus, so it only ever reorders INSIDE the +20000 band: stacked with everything
# that can hit the same body (20000 - 1800 - 1200 - 6000 = 11000) it is still
# above the 9500 of the highest body that takes no prize.
PROMO_KO_ROTATION = 1800


# MATCH POINT: the opponent only needs to knock this body out to take the last
# prize. That is not a bad trade, it is losing the game -> veto, not a penalty.
# It goes BELOW SCORE_NEVER (-10000) on purpose: other promotion vetoes use that
# exact value (e.g. "the Meganium line does not go active") and a tie at -10000
# would leave the tie-break to the random order of the options, exactly between
# the body that endures and the one that makes us lose.
PROMO_MATCH_POINT_VETO = -30000


# THE LAST STAND: at their match point every body on our bench pays at least
# their remaining pile, so the price tag stops separating the candidates and
# what is left is who absorbs their reply best (`_mp_last_stand`).
#
# 9450 places it just BELOW the two branches that are about acting FIRST -- the
# guaranteed finisher (9500) and, above everything, the body that knocks out
# (+`PROMO_KO_BONUS`) -- and above the whole cheap-wall family (8500 + hp/10 of
# `_ko_prefer_basic_general`, 9000 for an Applin, 6100 for the sturdy basic):
# when their next knockout ends the game, taking a prize or removing their
# attacker still comes first, and handing over a cheaper corpse no longer does.
PROMO_LAST_STAND = 9450


# THE ATTACKER THAT CAN STILL WALK BACK (`_promo_deferred_attacker`). The front
# spot goes to the body that attacks -- today, or after this coming turn's
# attachment -- instead of to a cheap corpse, because the promotion resolves at
# the END of their turn and a body that can pay its own retreat is not obliged
# to be standing there when their reply lands.
#
# 9200 is fixed from both sides. ABOVE the whole cheap-wall family (9000 for an
# Applin, 8500 + hp/10 for a sturdy basic, 6100 for the refill wall), which is
# the family this rule exists to outrank: those hand over the slot to a body
# chosen for how little it costs when it dies, and this one says the dying is
# not settled yet. BELOW the two branches that promise something this one does
# not -- the last stand (9450), where nothing cheaper is left to defer to, and
# the guaranteed finisher (9500), which is this same sentence with a knockout
# attached -- and far below the body that knocks out today (+PROMO_KO_BONUS).
PROMO_DEFERRED_ATTACKER = 9200


def _purchase_of_this_turn(card_id, hand, bought_serials):
    """How many copies of `card_id` in `hand` OUR OWN searches bought today.

    The other side of `_SUPP_PLAY_IDS` above, and the same doctrine: the
    decision that SPENDS a resource and the decision that PRICES the hand
    afterwards cannot contradict each other. Here the resource has already been
    spent -- an Ultra Ball, a Meowth ex ability, a Bug Catching Set went and got
    this card -- and the discard ladders, which know only what a card IS, are
    about to price it as if it had always been sitting there.

    A COUNT, not a list of serials, because copies of one card are
    interchangeable: what has to survive the next cost is as many copies as the
    search brought, not the physical ones it brought. `bought_serials` is
    `AGENT_STATE._bought_this_turn` (taken off the MOVE_CARD logs; a DRAW is not
    a purchase). It names no card and no deck.
    """
    if not bought_serials:
        return 0
    return sum(1 for c in hand
               if getattr(c, 'id', None) == card_id
               and getattr(c, 'serial', None) in bought_serials)


__all__ = [
    'SCORE_LD_SUPP_COMPROMETIDO',
    '_SUPP_PLAY_IDS',
    '_purchase_of_this_turn',
    'MAIN_ATTACKERS',
    'PROMO_DEFERRED_ATTACKER',
    'PROMO_DOOMED_PENALTY',
    'PROMO_KO_BONUS',
    'PROMO_KO_FRONT',
    'PROMO_KO_ROTATION',
    'PROMO_LAST_STAND',
    'PROMO_MATCH_POINT_VETO',
    'PROMO_PRIZE_PENALTY',
    'OPENING_SAC_PROMOTE_TOP',
    'OPENING_SAC_PROMOTE_STEP',
]
