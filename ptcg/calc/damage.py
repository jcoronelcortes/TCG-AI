"""The DAMAGE MODEL: how hard a hit lands, ours and theirs.

The single most consequential module in the package. Nearly every decision the
agent makes reduces to a damage question -- does this attack knock out, do we
survive the reply, is that body worth gusting -- and all of them are answered
here. An error in this file does not fail a test; it loses a game while every
test stays green (see `_our_effective_damage`, whose docstring carries exactly
such a loss).

THE CANONICAL MODEL, AND WHY IT MATTERS. There is one implementation of the
arithmetic and every consumer goes through it. That is a rule with a price
attached: the last time a correction was added with a default that let existing
callers ignore it, all 69 of them ignored it, four inline copies of the
arithmetic quietly carried the fix, and the finishers over-read by 30 for a
month. When something new modifies damage, it belongs INSIDE the functions
here, not beside them.

THE TWO HALVES

  * OUR damage. `_attacker_base_damage` gives what the attack prints given the
    energy on it; `_our_effective_damage` then RESOLVES that number against the
    body receiving it. The order inside the resolver is the card rules' order
    and is load-bearing: immunities first (they return 0 outright), then
    weakness and resistance, then the stadium, then the survive-at-10 caps.
    Anything inserted at the wrong rung comes out wrong by 30.

  * THEIR damage. `_op_active_attack_damage_to` and its evolution counterpart
    project what the opponent hits us for. Harder, because their board scales
    their attacks in ways the printed number does not show -- their bench, our
    hand, the prizes taken -- which is what `ptcg/cards/op_scaling.py` and the
    `op_scale` on `AGENT_STATE` carry. A projector that reads only the attacker
    silently reverts to the placeholder printed on the card.

THE VOCABULARY the rest of the agent borrows from here:

  * a GUARANTEED knockout is not simply "damage >= HP" -- `_ko_not_guaranteed`
    is the veto for bodies that survive on a coin flip or a Tenacious Body, and
    a route that closes the game may not be built on an unguaranteed one.
  * the GIFT WINDOW (`_ventana_de_regalo`) is the damage a body will have taken
    by the time the opponent next acts -- their attack plus the chip and the
    movable damage they can aim. It is what "will this body still be alive"
    means anywhere in the agent.
  * the REPLY is their answer to our turn (`_promoted_reply_damage`,
    `_promoted_lethal_reply`), which is the defensive half of the turn plan.
  * a FINISHER is a body that closes a route; the `_bench_finisher_*` family
    finds the one on our bench, including whether it survives long enough to
    matter.
  * SNIPE is damage aimed past the active at the bench, and it has its own
    target-selection family because the best snipe target is rarely the
    biggest body.

WHAT THIS MODULE MAY NOT DO. It is pure: it reads cards, tables and the board
passed to it, and writes nothing. Turn-scoped facts it cannot see -- the
stadium, the opposing board scale -- reach it either as a parameter or as a
read of the refreshed flags on `AGENT_STATE`. The `full_metal_lab=None`
three-state switch in `_our_effective_damage` is the pattern for that, and the
reason it is a three-state rather than a boolean is documented there.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from dataclasses import replace

from ptcg.calc.card import prize_count, prize_count_op
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.tables import attack_table, card_table
from ptcg.cards.ids import ABILITY_IMMUNE_IDS, Alakazam_ex, EVO_BODY_DAMAGE, EVO_BODY_EXPOSURE, EVO_BODY_RESCUE, OP_ACTIVE_ABILITY_DAMAGE, OP_BENCH_SNIPE_DAMAGE, RAINBOW_ENERGY_TYPE, Brave_Bangle, DO_THE_WAVE_ATTACK_ID, Dipplin, Drednaw, EX_IMMUNE_IDS, FULL_HP_SURVIVE_IDS, Farigiraf_ex, Fezandipiti_ex, Hydrapple_ex, Maximum_Belt, Meganium, OUR_ABILITY_IDS, OUR_BASIC_EX_IDS, OUR_EX_IDS, POWERFUL_HAND_ATTACK_ID, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex, WAVE_BENCH_BODY_IDS
from ptcg.calc.energy import _grass_attach_slots_for, _grass_attach_unit, _grass_mult, _retreat_grass_units
from ptcg.cards.lines import _direct_evolution_ids
from ptcg.cards.op_scaling import OP_SCALING_IGNORES_WEAKNESS, op_scaled_damage
from cg.api import CardType, EnergyType
from typing import NamedTuple
from ptcg.cards.ids import ADRENA_BRAIN_MOVE, ATTACKER_PUNISH_DAMAGE, ATTACKER_PUNISH_NEEDS_DARK, Basic_Grass_Energy, FREEZING_SHROUD_COUNTER, Froslass, GRASS_DIGGER_REACH, GRASS_DIGGER_SUPPORTERS, Mega_Hawlucha_ex, OP_EVO_ENERGY_ON_PLAY, RETREAT_COST, SNIPE_ANY_TARGET_IDS, Survival_Brace
from ptcg.state.zones import ZONE_DECK, ZONE_DISCARD


def _powerful_hand_projected(op_hand_count: int) -> int:
    """Powerful Hand damage projected onto the opponent's NEXT turn.

    Same model as `_op_active_attack_damage_to`: 20 x (hand + 2), where the +2
    is the draw for the turn + the Psychic Draw from evolving. It lives on its
    own (and not behind "their active is an Alakazam") because the Alakazam that
    will finish us off may still be on the opposing BENCH: on their turn they
    promote, evolve and attack. Inside the `op_is_alakazam_deck` matchup it is
    the deck's only attacking line (Abra -> Kadabra -> Alakazam), so projecting
    it always is correct.
    """
    return 20 * (max(0, op_hand_count) + 2)


def _ko_not_guaranteed(op_pokemon):
    """True if the defender's KO is NOT guaranteed even though the projected
    damage is lethal: Mega Hawlucha ex (Tenacious Body: coin flip, on heads it
    survives at 10 HP) or Survival Brace (tool 1155: at full HP it survives at
    10 HP).

    It is consulted ONLY by the FINISHER evaluators that declare a certain win
    (`wins_now`, SCORE_WIN_GAME, `_active_attack_wins_now`): against these
    bodies "winning this turn" can fail and hand the turn back. Normal
    damage/can_ko is NOT touched (attacking them is still the best play most of
    the time). The ones that survive at full HP via Sturdy/Resolute Heart
    (FULL_HP_SURVIVE_IDS) do not need this predicate, because
    `_our_effective_damage` already caps their damage at hp-10 and can_ko comes
    out False."""
    if op_pokemon is None:
        return False
    if op_pokemon.id == Mega_Hawlucha_ex:
        return True
    if (op_pokemon.hp == op_pokemon.maxHp
            and any(getattr(_t, 'id', 0) == Survival_Brace
                    for _t in (getattr(op_pokemon, 'tools', None) or []))):
        return True
    return False


def _festival_double_wave(attacker_id) -> bool:
    """FESTIVAL LEAD IS OURS TOO: with Festival Grounds on the field, OUR Dipplin
    uses its attack TWICE in the same turn.

    The card (dataset/EN_Card_Data.csv, id 93): *"If Festival Grounds is in play,
    this Pokemon may use an attack it has twice. If the first attack Knocks Out
    your opponent's Active Pokemon, you may attack again after your opponent
    chooses a new Active Pokemon."* The second wave is NOT conditional on the
    knockout -- the knockout sentence only says WHEN it resolves. Verified in the
    record this reading comes from (user, registro_006 turn 5, episode 91522323):
    the opposing Dipplin threw Do the Wave twice into the SAME body, 210 -> 110 ->
    10, with no knockout in between.

    Festival Grounds is a SHARED stadium and we do not carry it in deck.csv, so
    the copy on the field is always theirs -- and it arms our Dipplin exactly as
    it arms theirs. Until this predicate existed the flag
    `_festival_grounds_in_play` was read only DEFENSIVELY (their double attack,
    and the counter-stadium that switches it off), and the whole offensive half
    of the same card was invisible: see [[el-doble-ataque-del-estadio-tambien-es-nuestro]].
    """
    return bool(attacker_id == Dipplin and AGENT_STATE._festival_grounds_in_play)


def _festival_wave_bench(my_state, hand_counts=None) -> int:
    """How many benched bodies *Do the Wave* counts THIS TURN: the bench as it
    stands, PLUS the 1-prize Basics still in hand that have a free seat waiting.

    THE ONE NUMBER (user, registro_004 step 61 vs Festival Lead, episode
    92669047). Do the Wave is 20 x our bench, so on the turn the stadium is ours
    the bench is not the board, it is the ATTACK -- and a body in hand with a
    seat free is twenty damage on each of the two waves. Reading the wave off
    `bench_count` prices it as if the hand were empty, which is the same
    blindness `_win_via_field_ability` was written for on the other line: a card
    in hand that changes how hard WE hit is damage, not development.

    It has to be ONE function because two decisions read it and they must not be
    able to disagree: `_festival_lead_pays_us_now` (which forbids replacing the
    stadium and evolving the body) and `_festival_sac_pivot` (which commits the
    retreat). If the detector counted the body and the pivot did not, the pivot
    would decline a knockout that is there; the other way round it would retreat
    into a wave that never grew.

    THE COUNT IS ONLY HONEST BECAUSE THE PLAY IS GUARANTEED. `WAVE_BENCH_BODY_IDS`
    is exactly the set the envelope at the end of `ptcg/turn/options/play.py`
    lifts to `SCORE_WAVE_BODY_IS_DAMAGE` on this same flag, and a Pokemon drop
    sits in `_TIER_DEVELOP` (40) while the retreat sits in tier 0 -- so the body
    is on the bench before the wave is thrown. Widening this set without
    widening that one puts back the disagreement.

    With no hand (`hand_counts` empty or None) it degrades to the bench as it
    stands, which is what every caller read before this existed.
    """
    bench = [b for b in (getattr(my_state, 'bench', None) or []) if b is not None]
    if not hand_counts:
        return len(bench)
    free = max(0, (getattr(my_state, 'benchMax', 5) or 5) - len(bench))
    if free <= 0:
        return len(bench)
    in_hand = sum(hand_counts.get(_id, 0) for _id in WAVE_BENCH_BODY_IDS)
    return len(bench) + min(free, in_hand)


def _festival_second_wave_prizes(op_state, damage, knocked_out=None) -> int:
    """Prizes the SECOND Do the Wave cashes, once the first one has knocked
    `knocked_out` out of the Active spot. 0 when the wave does not close a
    second body.

    THE OPPONENT CHOOSES WHO COMES UP, so this counts a prize only when EVERY
    body they can promote dies to the same `damage` -- the same conservative
    reading `_promoted_reply_damage` uses from the other side of the table. A
    bench with one survivor in it (a 100 HP Thwackey against a wave of 80) is
    worth ZERO here, not "sometimes one": a projection that assumes the opponent
    promotes badly is how a turn gets spent on a prize that never arrives.

    THE CANDIDATES ARE EVERY BODY THEY HAVE LEFT, not their bench: when the wave
    is aimed at a gusted body, the Active it displaced goes back to the bench and
    is promotable again. Hence `knocked_out` rather than "their active".

    `damage` is the EFFECTIVE damage of the first wave, already through
    `_our_effective_damage`. Do the Wave scales with OUR bench, which the second
    wave does not change, so the same number lands twice -- and it is compared
    here against HP only, which is why a body that RESISTS or is weak to Grass
    would need its own reading before this could claim its prize.
    """
    if damage <= 0:
        return 0
    _koed = getattr(knocked_out, 'serial', None)
    _in_play = (list(getattr(op_state, 'active', None) or [])
                + list(getattr(op_state, 'bench', None) or []))
    candidates = [p for p in _in_play
                  if p is not None and p is not knocked_out
                  and (_koed is None or getattr(p, 'serial', None) != _koed)]
    if not candidates:
        return 0            # no body comes up: the game already ended with the KO
    worst = None
    for body in candidates:
        if _ko_not_guaranteed(body) or damage < _op_hp_for_our_ko(body, 1):
            return 0        # they promote this one and the second wave takes nothing
        # THE CHEAPEST CORPSE, not the dearest. Every body dies to the wave, so
        # what the second one is WORTH is still their choice, and they make it
        # against us: a bench of one Thwackey and one ex pays ONE prize, because
        # the Thwackey is what comes up. The line above already refuses the whole
        # prize when a single body survives; this line refuses to invent the
        # difference between two that do not. Reading the maximum here is how a
        # route that takes one prize gets to call itself lethal for two.
        _p = prize_count_op(body)
        worst = _p if worst is None else min(worst, _p)
    return worst or 0


class _ProjTarget(NamedTuple):
    """Lightweight target used to project the opponent's damage against a body
    that is not in play yet (e.g. the EVOLUTION of a benched pre-evolution). It
    only needs `id` (for weakness/resistance via card_table); `tools`/`energies`
    are empty."""
    id: int
    tools: tuple = ()
    energies: tuple = ()


def _snipe_targets(op_state):
    """Opposing Pokemon reachable by a snipe attack: active + bench."""
    out = []
    if op_state is None:
        return out
    for _p in (list(getattr(op_state, 'active', None) or [])
               + list(getattr(op_state, 'bench', None) or [])):
        if _p is not None:
            out.append(_p)
    return out


def _ventana_de_regalo(pokemon, is_active, projected_hit, include_movable=True):
    """Damage the opponent can concentrate on `pokemon` before our next turn.
    A body with `hp <= _ventana_de_regalo(...)` is a prize the opponent can cash
    in whenever they want.

    `golpe_proyectado` is the attack that reaches it: `estimated_op_damage` for
    the ACTIVE, `_op_bench_snipe_dmg` for the bench. On top of that, the two
    sources that are not attacks are added (see "THE GIFT WINDOW"):

      * the Freezing Shroud drip, which only bodies with an ABILITY pay;
      * the AIMABLE damage of Adrena-Brain, which reaches any body.

    `incluir_movible=False` returns the **GUARANTEED** window: only what
    arrives no matter what. The distinction matters because movable damage is
    ELASTIC -- the opponent aims it wherever they like, but it only kills ONE
    body per turn. Always measuring with the ceiling would leave half the board
    "doomed" and switch healing off exactly like measuring with the snipe alone.

    Without Froslass or Munkidori on the field both terms are 0 and the two
    windows are the usual projected hit."""
    pid = getattr(pokemon, 'id', 0)
    # The Tera of Teal Mask Ogerpon ex: ON THE BENCH it prevents damage from
    # ATTACKS (and therefore automatic sniping), never counters that are placed or
    # moved.
    golpe = 0 if (not is_active and pid == Teal_Mask_Ogerpon_ex) \
        else max(0, projected_hit or 0)
    chip = AGENT_STATE._op_chip_per_round if pid in OUR_ABILITY_IDS else 0
    return golpe + chip + (AGENT_STATE._op_movable_dmg if include_movable else 0)


# --- THE OTHER HALF OF THE DRIP: IT ALSO FALLS ON THEIR BOARD ----------------
# (user, registro_006 step 90 vs Marnie's Grimmsnarl ex, episode 92871474, LOST.)
#
# `_ventana_de_regalo` above prices Freezing Shroud as a THREAT, because that is
# the half that kills us. The card does not say "your opponent's Pokemon": it
# says "each Pokemon in play that has an Ability", and their Grimmsnarl ex has
# one (Punk Up). The whole estate knew it -- the note next to
# FREEZING_SHROUD_COUNTER says the counters reload "onto each Munkidori AND onto
# the Grimmsnarl ex (they all have an ability)" -- and used it only to work out
# how much ammunition Adrena-Brain has.
#
# WHAT IT COST. Their Grimmsnarl ex at 320/320, our Meganium on the bench with
# four effective Grass: Solar Beam is 140, doubled by their Darkness weakness =
# 280. Read against the printed 320 that is not a knockout, so the veto "the
# Meganium line does not go active" stood and a mute Meowth ex took the front.
# Read against the HP their own two Froslass leave -- one checkup before our
# turn, one after our attack, 40 in all -- it is 280 against 280: EXACTLY
# lethal, two prizes, cashed at the checkup before they could answer.
#
# WHY THE PRIZE IS SAFE. The counters land BETWEEN turns, so the body is gone
# before their turn starts: they cannot heal it, retreat it, or move the damage
# off it with Adrena-Brain (which they only get to use on their own turn). The
# one thing that can take it away is the Froslass leaving the field, which is
# not something they do to themselves.
#
# THE UNIT IS THE CHECKUP, and how many of them there are depends on WHEN the
# question is asked -- this is the whole subtlety:
#
#   * on OUR turn (the attack we are about to make): the checkup that opened
#     this turn has already happened and is inside the HP we can see, so ONE
#     checkup remains between our attack and their turn;
#   * at the FORCED PROMOTION after a knockout, which resolves at the end of
#     THEIR turn: TWO, the one that opens our turn and the one that follows our
#     attack -- `CHECKUPS_PER_ROUND`.
#
# IT IS A NO-OP WITHOUT FROSLASS. `_op_chip_per_checkup` is 0 unless one is in
# play, so `_op_hp_for_our_ko` returns the printed HP and every threshold
# downstream reads exactly the number it was calibrated on. That is what lets
# this be wired into the knockout tests themselves instead of being asked as a
# second question beside them.
def _has_ability(card_id) -> bool:
    """The card PRINTS an Ability, which is the condition Freezing Shroud names.

    Read off the card database (`skills`) rather than a hand-kept list: the
    counters have to be projected onto THEIR board, and their board is whatever
    deck we drew. The one list we do keep, `OUR_ABILITY_IDS`, agrees with this
    reading on all six of its entries, and the record agrees on theirs -- the
    checkups of registro_006 put counters on Munkidori and on nothing else of
    theirs (Marnie's Impidimp, with no Ability, was untouched).
    """
    _d = card_table.get(card_id)
    return bool(getattr(_d, 'skills', None))


# THE GATE'S HANDLE. Rebinding this to False in THIS module's globals switches
# the whole reading off, everywhere, in one assignment: `_op_hp_for_our_ko` is
# the same function object main.py imported with its star import, so both arms
# of `utils/gate_their_own_drip_finishes_the_body.py` stay structurally
# identical -- same code, same order, one flag.
SHROUD_KO_READING = True


def _shroud_damage_to(pokemon, checkups=1) -> int:
    """Damage their own Freezing Shroud puts on `pokemon` over `checkups`.

    0 when there is no Froslass in play, when the body prints no Ability, and
    on Froslass itself -- the card excludes its own kind, which the record
    confirms: two of them stood at 90/90 through every checkup of the game.
    """
    if pokemon is None or checkups <= 0 or not SHROUD_KO_READING:
        return 0
    per = AGENT_STATE._op_chip_per_checkup
    if per <= 0:
        return 0
    cid = getattr(pokemon, 'id', 0)
    if cid == Froslass or not _has_ability(cid):
        return 0
    return per * checkups


def _op_hp_for_our_ko(target, checkups=1) -> int:
    """The HP OUR attack actually has to cover to knock `target` out.

    The printed HP minus what their own drip takes off it before they can
    answer. Floored at 1: a body their Froslass would finish on its own is
    still not knocked out by an attack that does nothing to it, and every
    knockout test downstream is `damage >= this`.

    Returns the printed HP untouched whenever there is no drip on that body,
    which is every board without a Froslass on it.
    """
    hp = getattr(target, 'hp', 0) or 0
    if hp <= 0:
        return hp
    return max(1, hp - _shroud_damage_to(target, checkups))


def _prizes_of_id(card_id):
    """Prizes a card hands over when knocked out, WITHOUT the denial that
    depends on what it carries. It compares a body against what it will become,
    and the evolution is still in hand: it carries nothing yet."""
    data = card_table.get(card_id)
    if data is None:
        return 1
    return 3 if data.megaEx else 2 if data.ex else 1


def evolution_body_bias(pokemon, evo_card_id, is_active, projected_hit):
    """How much better this BODY is than another one for the SAME evolution
    card. Deck-agnostic: it only reads life, the projected window and prizes.

    Evolving does not heal -- the damage carries over and only the maximum goes
    up (Applin 10/40 -> Hydrapple ex 300/330) -- so the copy worth evolving is
    the DAMAGED one: the counters it already has stop being lethal inside a
    bigger pool and the intact copy is the one that can wait on the bench.
    Evolving the healthy one instead leaves the wounded copy there as a prize
    anyone with a snipe cashes in for free.

    Three terms, all bounded (see EVO_BODY_* in cards/ids.py) so that this
    orders bodies and never decides which CARD is played:

      * the body leaves the gift window -> EVO_BODY_RESCUE (the real rescue);
      * it stays inside it AND the evolution is worth more prizes -> the
        evolution is not saving anything, it is raising the opponent's prize:
        -EVO_BODY_EXPOSURE;
      * otherwise, a gradient proportional to the damage already taken.

    `projected_hit` is what reaches that slot: `estimated_op_damage` for the
    ACTIVE, `_op_bench_snipe_dmg` for the bench (the same convention as
    `_ventana_de_regalo`). With no threat on the board both windows are 0, only
    the gradient survives and the damaged body still wins.
    """
    if pokemon is None:
        return 0
    data = card_table.get(evo_card_id)
    evo_max_hp = (getattr(data, 'hp', 0) or 0) if data is not None else 0
    max_hp = getattr(pokemon, 'maxHp', 0) or 0
    hp = getattr(pokemon, 'hp', 0) or 0
    if evo_max_hp <= 0 or max_hp <= 0:
        return 0

    damage = max(0, max_hp - hp)
    hit = max(0, projected_hit or 0)
    hp_after = max(0, evo_max_hp - damage)
    # `_ProjTarget` is the body it is ABOUT to become: `_ventana_de_regalo`
    # only reads `.id`, and the window can GROW while evolving (an Applin has no
    # ability and pays no Freezing Shroud drip; a Dipplin does).
    window_after = _ventana_de_regalo(_ProjTarget(evo_card_id), is_active, hit)

    if hp_after <= window_after:
        # The evolution does not take it out of the window: the body dies
        # anyway and the card dies underneath it.
        if _prizes_of_id(evo_card_id) > _prizes_of_id(getattr(pokemon, 'id', 0)):
            return -EVO_BODY_EXPOSURE
        return 0

    bias = min(EVO_BODY_DAMAGE, (damage * EVO_BODY_DAMAGE) // max_hp)
    if hp <= _ventana_de_regalo(pokemon, is_active, hit):
        bias += EVO_BODY_RESCUE
    return bias


def _movable_dmg_after_our_hit(our_damage):
    """`_op_movable_dmg` recomputed with the counters OUR OWN attack is about
    to leave on their board.

    Adrena-Brain only moves counters that ALREADY exist, so on a healthy
    opposing board the window reads 0 -- and it stops reading 0 the instant we
    attack. Projecting what reaches our bench BEFORE our attack lands therefore
    measures a board that will not exist by the time the opponent plays: our
    own damage is their ammunition.

    User, registro_012 step 112 vs Marnie's Grimmsnarl ex. Their four benched
    bodies were at full HP (0 counters, movable window 0) and we hid a Teal Mask
    Ogerpon ex at 30 HP behind the Hydrapple ex wall. Then Syrup Storm put 360
    on their active, and with two charged Munkidori they moved 30 of those
    counters onto the hidden ex: two prizes without attacking, and their
    attacker healed 30 in the same motion.
    """
    return min(AGENT_STATE._op_movable_cap,
               AGENT_STATE._op_movable_ammo + max(0, our_damage or 0))


class OpHarvest(NamedTuple):
    """What `_op_prize_harvest` answers. See that function."""
    # Prizes they collect before we act again, from every source together.
    prizes: int
    # ... of those, the ones taken WITHOUT an attack: the Freezing Shroud drip
    # and the counters Adrena-Brain aims. They survive our own knockout, which
    # is the whole reason the field exists apart from `prizes`.
    off_board: int
    # Their attack finishes our ACTIVE.
    kills_active: bool
    # Serials of our bodies in the harvest, so a test or the debug dump can say
    # WHICH ones rather than how many.
    victims: tuple


def _op_prize_harvest(my_state, op_state, op_hand_count, our_damage=0):
    """Prizes the opponent can collect before our next turn -- ALL of them, and
    off ALL of our bodies.

    THE HOLE IT FILLS (user, registro_009 step 150 vs Marnie's Grimmsnarl ex,
    episode 92844329, LOST). `_opponent_reply` projects exactly one thing: their
    ACTIVE hitting OUR ACTIVE. On that board it answered 2 prizes and
    `op_wins_next=False`, so the agent believed it had a tomorrow, pivoted into
    a wall and spent the turn developing. The truth was that it had no tomorrow
    at all: our benched Meowth ex stood at 40 HP with two Froslass on the field,
    so it died to the drip alone -- two prizes with no attack, on top of the two
    their Grimmsnarl ex was about to take from the active. Four prizes against
    the three they needed. The only correct play was the one that ended the game
    that turn, and the plan had no way to say so.

    The three sources of `THE GIFT WINDOW`, put together and aimed the way an
    opponent aims them:

      * the FREEZING SHROUD drip, which every body in `OUR_ABILITY_IDS` pays
        twice a round and which nothing can be done about;
      * their ATTACK on our active, and the automatic SNIPE it carries to ONE
        benched body (the opponent picks which, so every seat is tried);
      * ADRENA-BRAIN, which is neither of those two: a POOL of moves (up to 3
        counters each, one body per move) that they spend wherever it buys the
        most. `_ventana_de_regalo` prices it as if it could only ever finish one
        body, which is the honest reading for "is THIS body doomed" and the
        wrong one for "how many prizes is the board worth": two charged
        Munkidori finish two different bodies in the same turn.

    THE OPPONENT MAXIMISES PRIZES, which is why the allocation is searched and
    not greedy. Our board is at most six bodies, so every subset is tried
    against the two budgets (moves, and the counters their board can actually
    supply) and the best one wins -- ties going to the cheaper allocation. That
    is what "they concentrate on the lowest HP, or on whatever hands over two
    prizes" means once it is written down as arithmetic rather than as a
    preference.

    `our_damage` is the damage OUR attack is about to leave on their board,
    because that is Adrena-Brain's ammunition -- the same correction
    `_movable_dmg_after_our_hit` exists for. It defaults to 0, which reads the
    board as it stands.

    IT IS A PROJECTION AND IT REFUSES TO INVENT. Their gusts, their bench swaps
    and whatever their hand holds are not modelled here for the reason
    `_opponent_reply` states: a projection that assumes the hand we cannot see
    makes every turn look lost.
    """
    ours = ([p for p in (getattr(my_state, 'active', None) or []) if p is not None]
            + [p for p in (getattr(my_state, 'bench', None) or []) if p is not None])
    if not ours:
        return OpHarvest(0, 0, False, ())
    op_active = (op_state.active[0]
                 if op_state is not None and getattr(op_state, 'active', None)
                 else None)
    my_active = (my_state.active[0]
                 if getattr(my_state, 'active', None) else None)

    chip = AGENT_STATE._op_chip_per_round
    attack = 0
    if op_active is not None and my_active is not None:
        attack = _op_active_attack_damage_to(op_active, my_active, op_hand_count,
                                             scaled=True)
    snipe = AGENT_STATE._op_bench_snipe_dmg

    # The pool, in the two units it is spent in: MOVES (one body each, up to
    # three counters) and the COUNTERS those moves have to carry, which their
    # own board has to be holding.
    per_move = ADRENA_BRAIN_MOVE // FREEZING_SHROUD_COUNTER
    moves = AGENT_STATE._op_movable_cap // ADRENA_BRAIN_MOVE
    ammo = min(AGENT_STATE._op_movable_cap,
               _movable_dmg_after_our_hit(our_damage)) // FREEZING_SHROUD_COUNTER
    bench = [b for b in ours if b is not my_active]

    def _reap(with_attack):
        """(prizes, victims) for the best way they can spend the turn.

        `with_attack=False` is the same board with their attack and its snipe
        switched off: what the drip and the moved counters take on their own.
        """
        best_prizes, best_victims = 0, ()
        for aimed in ([None] + bench if (with_attack and snipe > 0) else [None]):
            free, pending = [], []
            for body in ours:
                taken = chip if getattr(body, 'id', 0) in OUR_ABILITY_IDS else 0
                if with_attack:
                    if body is my_active:
                        taken += attack
                    elif body is aimed and getattr(body, 'id', 0) != Teal_Mask_Ogerpon_ex:
                        # The Tera of a benched Teal Mask Ogerpon ex stops damage
                        # from ATTACKS, which is what a snipe is -- and nothing else.
                        taken += snipe
                left = (getattr(body, 'hp', 0) or 0) - taken
                if left <= 0:
                    free.append(body)
                    continue
                need = -(-left // FREEZING_SHROUD_COUNTER)   # ceil, in counters
                if moves > 0 and need <= moves * per_move:
                    pending.append((body, need, -(-need // per_move)))
            # THE OPPONENT MAXIMISES: every subset of what the pool can still
            # finish is tried against both budgets. At most six bodies.
            take_prizes, take_cost, taken_bodies = 0, 0, ()
            for mask in range(1 << len(pending)):
                counters = spent = gained = 0
                picked = []
                for i, (body, need, cost) in enumerate(pending):
                    if mask & (1 << i):
                        counters += need
                        spent += cost
                        gained += prize_count(body)
                        picked.append(body)
                if spent > moves or counters > ammo:
                    continue
                if gained > take_prizes or (gained == take_prizes
                                            and counters < take_cost):
                    take_prizes, take_cost = gained, counters
                    taken_bodies = tuple(picked)
            total = sum(prize_count(b) for b in free) + take_prizes
            if total > best_prizes:
                best_prizes = total
                best_victims = tuple(getattr(b, 'serial', None)
                                     for b in list(free) + list(taken_bodies))
        return best_prizes, best_victims

    prizes, victims = _reap(True)
    off_board, _ = _reap(False)
    return OpHarvest(
        prizes=prizes,
        off_board=off_board,
        kills_active=(my_active is not None and attack >= (my_active.hp or 0)),
        victims=victims)


def _active_closes_with_one_charge(my_state, op_state, state, hand_counts,
                                   field_counts, my_prize, total_grass,
                                   bench_count, meganium_active, neutral_zone,
                                   grass_left_in_deck, abilities_off=False):
    """The body standing in FRONT is one Basic Grass away from the knockout that
    ENDS the game, and the turn can still find that Grass.

    THE RETREAT THAT THREW THE GAME AWAY (user, registro_009 step 150 vs
    Marnie's Grimmsnarl ex, episode 92844329, LOST). Two prizes left, their
    Grimmsnarl ex at 300 of 320 -- and weak to Grass, so our active Teal Mask
    Ogerpon ex at two Grass needed exactly one more to hit for 360 and win on
    the spot. The Grass was not in hand, so `_doomed_mute_pivot` read the active
    as MUTE, retreated it, PAID one of its two Grass for the retreat, and put a
    fresh Fezandipiti ex in front. Four actions later the turn drew the Grass it
    had just declared unreachable -- and attached it to a benched body, because
    by then the attacker was on the bench and could not come back.

    WHY "ONE CHARGE" AND NOT "IT CAN ATTACK". The mute reading is not wrong
    about the board it can see: the Grass really is not in hand. What it is
    wrong about is the PRICE of being wrong. On any other turn a pivot that
    guesses badly costs a little tempo; on the turn where the body in front is
    the win condition it costs the game, and the retreat also burns the very
    energy the attack was going to count. So the veto is written where that
    asymmetry lives -- the knockout has to CLOSE the game (`my_prize <=` the
    prizes their active hands over), not merely be available.

    THE TURN HAS TO BE ABLE TO FIND IT, which is the other half and the reason
    this is not simply "the active is one energy short". Two things have to be
    true: a ROUTE that can still put a Grass on that body
    (`_grass_attach_slots_for` -- the turn's attachment, Teal Dance, Ripening
    Charge), and a Grass we can still get into HAND -- already there, or
    reachable by a card that digs for one. `GRASS_FROM_DECK_IDS` and
    `GRASS_FROM_DISCARD_IDS` name those cards and where each reaches; the
    Supporters among them only count while the Supporter slot is still free.

    Deck-agnostic: it reads our own attack costs, our own dig cards and the two
    prize counts. Against a deck whose active is a 1-prize body it needs us at
    exactly one prize, which is as rare as it sounds -- that rarity is the
    licence, the same one `do_or_die` carries.
    """
    active = (my_state.active[0]
              if getattr(my_state, 'active', None) else None)
    op_active = (op_state.active[0]
                 if op_state is not None and getattr(op_state, 'active', None)
                 else None)
    if active is None or op_active is None:
        return False
    if my_prize > prize_count_op(op_active):
        return False            # the knockout does not close the game
    if _ko_not_guaranteed(op_active):
        return False            # a route that ends the game may not be a coin flip
    if _grass_attach_slots_for(active, state, field_counts, abilities_off) < 1:
        return False            # no route left to put it on that body

    eff_after = len(getattr(active, 'energies', []) or []) + _grass_attach_unit()
    base = _attacker_base_damage(active.id, op_active, eff_after,
                                 grass_scale=total_grass + 1,
                                 teal_self_energy=eff_after,
                                 bench_count=bench_count)
    if base <= 0:
        return False
    damage = _our_effective_damage(active, op_active, base, meganium_active,
                                   neutral_zone)
    if damage < _op_hp_for_our_ko(op_active, 1):
        return False

    if (hand_counts or {}).get(Basic_Grass_Energy, 0) >= 1:
        return True
    supporter_free = not getattr(state, 'supporterPlayed', False)
    grass_in_discard = sum(1 for c in (getattr(my_state, 'discard', None) or [])
                           if getattr(c, 'id', 0) == Basic_Grass_Energy)
    for _cid, _reach in GRASS_DIGGER_REACH.items():
        if (hand_counts or {}).get(_cid, 0) < 1:
            continue
        if _cid in GRASS_DIGGER_SUPPORTERS and not supporter_free:
            continue
        if _reach == ZONE_DISCARD and grass_in_discard > 0:
            return True
        if _reach == ZONE_DECK and max(0, grass_left_in_deck) > 0:
            return True
    return False


def _bench_cashable_after_retreat(pokemon, op_active, our_damage=0):
    """Would the body we are about to hide on the bench die there anyway?

    The retreat of a doomed ex only denies prizes if the ex SURVIVES down
    there ([[repliegue-del-ex-condenado-vs-sniper]]). Three things reach it:
    the snipe of the attacker IN FRONT (the narrow reading -- the table flag
    `_op_bench_snipe_dmg` falls to a default 30 with any drip threat in play
    and switching pivots off with it measured -3.1 points vs
    crustle/Kangaskhan), the Freezing Shroud drip, and the counters
    Adrena-Brain can aim once our attack has loaded their board.

    The Tera of a benched Teal Mask Ogerpon ex is already handled by
    `_ventana_de_regalo`: it cuts the snipe (damage from an ATTACK) and does
    nothing against moved counters -- which is exactly how the record died.
    """
    if pokemon is None:
        return False
    snipe = OP_BENCH_SNIPE_DAMAGE.get(getattr(op_active, 'id', 0), 0)
    window = (_ventana_de_regalo(pokemon, False, snipe, include_movable=False)
              + _movable_dmg_after_our_hit(our_damage))
    return (getattr(pokemon, 'hp', 0) or 0) <= window


def _our_effective_damage(my_pokemon, op_pokemon, base_damage,
                          meganium_active=False, neutralization_zone=False,
                          full_metal_lab=None):
    """Our base damage, resolved against the body that receives it.

    `full_metal_lab` is a THREE-state switch, and the third state is the one
    that matters: `None` (the default) means "ask the board", i.e. read
    `AGENT_STATE.full_metal_lab_in_play`. True/False force the answer and exist
    for the tests and for any caller projecting a board where the stadium is
    about to change.

    It was NOT always so. The morning the stadium was taught to the model it
    arrived as `full_metal_lab=False`, expressly so that the ~70 call sites
    "did not have to change at once" -- and none of them ever did. Zero of 69
    passed it, so the canonical model knew the card and was never asked about
    it: the four inline copies of the arithmetic (the turn plan, Syrup Storm's
    can-KO, the gust's price and Do the Wave) carried the whole fix while every
    finisher kept over-reading by 30.

    That is what a lost game looks like (episode 91627381, record
    registro_007 step 63, turn 7 vs Archaludon). Their Duraludon, 130/130 and
    ALONE -- an empty bench, so the knockout ends the game. Syrup Storm with
    five Grass on our side is 180, minus 30 Grass resistance = 150, and
    `_active_already_kos` read 150 >= 130 and set `_active_attack_wins_now`.
    That flag is absolute priority (`_TIER_WIN_ATTACK`, 99000): it empties the
    menu. So the agent attacked at once, playing nothing -- and the engine
    logged `value: -120`, because the stadium takes its 30 after the
    resistance. Duraludon survived at 10 and the game was lost from there.

    Two cards in that hand won on the spot, and the over-read hid both: our own
    Forest of Vitality (replace the stadium and 180-30 = 150 is lethal) and the
    Night Stretcher (recover one of the three Grass in the discard, attach it,
    and 210-30-30 = 150 is lethal WITH the stadium still up). One wrong number,
    three plays not made.
    """
    if full_metal_lab is None:
        full_metal_lab = AGENT_STATE.full_metal_lab_in_play
    if op_pokemon is None or base_damage is None:
        return 0
    data = card_table.get(op_pokemon.id)
    if data is None:
        return max(0, base_damage)
    my_is_ex = my_pokemon.id in OUR_EX_IDS
    my_has_ability = my_pokemon.id in OUR_ABILITY_IDS
    is_fez = (my_pokemon.id == Fezandipiti_ex)
    damage = base_damage

    if op_pokemon.id in EX_IMMUNE_IDS and my_is_ex:
        return 0

    _op_has_rule_box = bool(getattr(data, 'ex', False) or getattr(data, 'megaEx', False))
    if neutralization_zone and my_is_ex and not _op_has_rule_box:
        return 0

    # ...and the same zero bought out of their hand for one turn, on one body.
    # It sits on this line because it IS the line above with a different source:
    # `neutralization_zone` is a stadium anyone can read off the observation and
    # this one is a Supporter that left no trace on the board. See
    # `_shield_mutes_our_ex`.
    if my_is_ex and _shield_mutes_our_ex(op_pokemon):
        return 0

    if op_pokemon.id in ABILITY_IMMUNE_IDS and my_has_ability:
        return 0

    # Farigiraf ex ("Armor Tail"): immune to attack damage from BASIC ex. Only
    # Hydrapple ex (Stage 2) and the non-ex damage it (jul 2026 plan, P1.6).
    if op_pokemon.id == Farigiraf_ex and my_pokemon.id in OUR_BASIC_EX_IDS:
        return 0

    if not is_fez:
        if data.weakness == EnergyType.GRASS:
            damage *= 2
        elif data.resistance == EnergyType.GRASS:
            damage -= 30

    # Full Metal Lab: 30 less onto {M} bodies, and the card says AFTER weakness
    # and resistance, which is why it sits on this line and not above. Against
    # the Archaludon line the two stack (-30 resistance, then -30 stadium) and
    # that second 30 is what turns a projected knockout into a body left at 30.
    # Unlike the resistance this is NOT conditioned on `is_fez`: the stadium
    # reduces damage from any attack, and the Fezandipiti exception above is
    # about weakness and resistance only.
    if full_metal_lab and getattr(data, 'energyType', None) == EnergyType.METAL:
        damage -= 30

    if op_pokemon.id == Drednaw and damage >= 200:
        return 0

    # Sturdy (Crustle 533) / Resolute Heart (Pikachu ex 210): at FULL HP they
    # survive the lethal hit staying at 10 HP -> cap at hp-10 (P0.1).
    if (op_pokemon.id in FULL_HP_SURVIVE_IDS and
            op_pokemon.hp == op_pokemon.maxHp and damage >= op_pokemon.hp):
        damage = op_pokemon.hp - 10

    return max(0, int(damage))


def _tiene_rule_box(card_id) -> bool:
    """Does the card have a Rule Box (Pokemon ex / Mega ex / V ...)?

    It is consulted by tools conditioned on "if the holder does NOT have a Rule
    Box" (Brave Bangle). For an unknown card it returns True -> the bonus is NOT
    added: we prefer not to invent damage on data we cannot read.
    """
    _d = card_table.get(card_id)
    if _d is None:
        return True
    return bool(getattr(_d, 'ex', False) or getattr(_d, 'megaEx', False))


# The switch the two-arm gate flips (`utils/gate_the_stadium_that_mutes_our_ex.py`),
# and it governs the ROUTING only: `_our_effective_damage` reads the stadium
# straight from its own argument and is never switched off, so with this False
# the agent still projects the zero correctly and merely goes back to charging
# as if the stadium were not there -- which is exactly the behaviour the gate's
# baseline arm has to reproduce.
NZ_MUTE_ROUTING = True


def _nz_mutes_our_ex(op_active, neutralization_zone) -> bool:
    """Neutralization Zone with a Rule-Box-less body in front: every ex of ours
    does ZERO to it.

    The same sentence `_our_effective_damage` already enforces two rungs above
    the weakness (`neutralization_zone and my_is_ex and not _op_has_rule_box ->
    0`), lifted out so the ROUTING can ask it before it spends a card. The
    damage model knew the stadium and the energy routing did not, which is a
    whole class of wasted turn: the agent kept charging bodies that could not
    reach the board in front (user, `records/registro_010_pasos_070_hasta_080`
    step 70, vs a Mesprit/Uxie/Azelf deck -- their five bodies all 70 HP and
    none with a Rule Box, our Hydrapple ex and both Ogerpon ex mute, and the
    turn's only Grass went to a benched Ogerpon via Teal Dance while Meganium,
    the one body of ours that could still knock anything out, sat at zero).

    It is the THIRD shape of the same wall the agent already knows -- Crustle
    (`EX_IMMUNE_IDS`) and Cornerstone (`ABILITY_IMMUNE_IDS`) -- and the one that
    reads backwards: here the wall is not a body of theirs, it is the ABSENCE
    of a Rule Box on the body in front. Which is why it also comes and goes with
    THEIR promotion, and has to be asked of the current active rather than of
    the matchup.

    Unknown card -> `_tiene_rule_box` answers True -> this answers False: on
    data we cannot read we do not switch off our own attackers.
    """
    if not NZ_MUTE_ROUTING:
        return False
    if not neutralization_zone or op_active is None:
        return False
    return not _tiene_rule_box(op_active.id)


# The switch the two-arm gate flips (`utils/gate_the_shield_they_buy_for_one_turn.py`),
# sibling of `NZ_MUTE_ROUTING` above and with the same scope: it governs the
# WHOLE reading, model included, because unlike the stadium there is no board to
# fall back on -- with this False the agent simply does not know the card, which
# is exactly the behaviour the gate's baseline arm has to reproduce.
OP_EX_SHIELD_ROUTING = True


def _shield_mutes_our_ex(op_pokemon) -> bool:
    """Is `op_pokemon` the body their Acerola's Mischief is protecting from our
    ex THIS turn?

    Why it exists (user, episode 93163758, `records/registro_013_pasos_107_...`
    step 107 onward, vs a Comfey/Chandelure deck -- LOST at ONE prize). Their
    board was a 70 HP Comfey in front and two Chandelure on the bench; our
    active Teal Mask Ogerpon ex carried three Grass, its twin on the bench
    carried seven, and Boss's Orders sat in hand. Myriad Leaf Shower reads
    30 + 30 x energy, so every projection in this agent said the Comfey died and
    `prizes_today` said 1. The engine logged `value: 0`, turn after turn:

        turn 13  attack -> 0     turn 15  attack -> 0     turn 19  attack -> 0

    Seven turns of a stalled prize pile against an opponent who never left six,
    because the ONE number the whole turn hangs on was wrong and nothing on the
    board said so. The line was in hand the entire time: Boss's Orders on a
    Chandelure (130 HP, and the shield stays on the Comfey it was pinned to) is
    one prize with the active as it stood, the game with the twin promoted.

    THE READING IS A SERIAL AND A TURN, AND BOTH COME FROM THE LOGS. main.py
    pins them when it sees their PLAY (`_op_ex_shield_serial`), and publishes
    the resolved answer for the observation being answered
    (`AGENT_STATE.op_ex_shield_serial`) because this module cannot see
    `state.turn`. A body with no serial -- the synthetic Pokemon of a unit test
    -- answers False: on data we cannot read we do not switch off our own
    attackers, the same direction `_nz_mutes_our_ex` takes.

    It says nothing about our NON-ex bodies, and that is the whole point of the
    card: Dipplin, Meganium, Tapu Bulu and Pinsir go through it untouched.
    """
    if not OP_EX_SHIELD_ROUTING:
        return False
    if op_pokemon is None:
        return False
    _shielded = AGENT_STATE.op_ex_shield_serial
    if _shielded is None:
        return False
    _serial = getattr(op_pokemon, 'serial', None)
    return _serial is not None and _serial == _shielded


def _wall_mutes_our_ex(op_active, neutralization_zone) -> bool:
    """Do our ex do ZERO to the body in front, by stadium or by their Supporter?

    The one question the ENERGY ROUTING asks, and it has two answers that mean
    the same thing to it: under Neutralization Zone with a Rule-Box-less body in
    front (`_nz_mutes_our_ex`), and under the shield their Acerola's Mischief
    pinned on that same body (`_shield_mutes_our_ex`). What follows from either
    is identical -- the turn's Grass belongs to a body of ours that is not an ex
    -- so the routing reads them through one name and the two predicates keep
    their own, each with its own switch and its own gate.
    """
    return (_nz_mutes_our_ex(op_active, neutralization_zone)
            or _shield_mutes_our_ex(op_active))


def _defender_punish_damage(op_active):
    """Damage the DEFENDER's own attachments put on OUR attacker when we hit it.

    Every other projector in this file answers "what does this attack do to that
    body". This one answers the question none of them ask: WHAT DOES ATTACKING
    COST US. Four cards print the same sentence -- "if the Pokemon this card is
    attached to is in the Active Spot and is damaged by an attack from your
    opponent's Pokemon (even if this Pokemon is Knocked Out), put N damage
    counters on the Attacking Pokemon" -- and until 12 August 2026 not one of
    them existed anywhere in this tree.

    It is read off the board, never guessed: the tools and the energy cards of
    their active are in the observation. Three conditions come from the text and
    all three are load-bearing:

      * ACTIVE SPOT ONLY. The same tool on a benched body charges nothing, so
        this takes the opposing ACTIVE and refuses to walk their bench.
      * "IS DAMAGED BY AN ATTACK". An attack that deals zero -- a wall, an
        immunity -- pays nothing either. The caller owns that condition, because
        this function does not know what we are about to swing.
      * THE TYPE QUALIFIER. Punk Helmet prints "{D} Pokemon"; a tool on a body
        of the wrong type is cardboard. Spiky Energy and Deluxe Bomb name no
        type.

    They ADD UP: nothing in the text makes them exclusive, and two of them on
    one body is a legal board. Summing is also the safe direction -- the number
    only ever stops us from claiming a victory we do not have.

    Handheld Fan (1161) is deliberately absent: it moves an ENERGY off the
    attacker instead of damaging it. That is a real cost and for this deck
    possibly the worst of the four -- Myriad Leaf Shower scales with energy --
    but it is a different reading and inventing HP for it would be a lie.
    """
    if op_active is None:
        return 0
    total = 0
    _is_dark = _has_energy_of_type(op_active, EnergyType.DARKNESS)
    _data = card_table.get(op_active.id)
    _type_ok = (getattr(_data, 'energyType', None) == EnergyType.DARKNESS
                or _is_dark)
    for _card in list(getattr(op_active, 'tools', None) or []) + \
            list(getattr(op_active, 'energyCards', None) or []):
        _punish = ATTACKER_PUNISH_DAMAGE.get(getattr(_card, 'id', None))
        if _punish is None:
            continue
        if _card.id in ATTACKER_PUNISH_NEEDS_DARK and not _type_ok:
            continue
        total += _punish
    return total


def _has_energy_of_type(pokemon, energy_type):
    """Does `pokemon` hold an Energy that PROVIDES `energy_type`?

    `energies` carries EnergyType already resolved by the engine, so a special
    Energy appears as what it really provides on the body it sits on. RAINBOW is
    the engine's way of saying "every type", so it satisfies any requirement.

    That one line is what makes Prism Energy (16) work without a special case.
    Its text is conditional -- "provides {C}; if attached to a Basic Pokemon it
    provides every type" -- and the engine resolves the condition for us: probed
    directly, a Prism reports RAINBOW on Applin (Basic) and COLORLESS on Dipplin
    (Stage 1). Re-deriving `card.basic` here would duplicate a rule the engine
    already applies, and duplicated rules drift. Legacy Energy (12) is rainbow
    unconditionally and rides the same path.
    """
    return any(_e in (energy_type, RAINBOW_ENERGY_TYPE)
               for _e in (getattr(pokemon, 'energies', None) or []))


def _op_active_attack_damage_to(op_active, target, op_hand_count=None,
                                scaled=False, scale=None, team_buff=False):
    """Maximum PRINTED damage the opposing active can deal to `target`.

    It resolves the attack IDs via `attack_table` (the `card.attacks` entries
    are ints, not objects, which is why `_op_best_damage_vs` -- which does
    getattr(id,'damage') -- always returns 0). It only considers attacks whose
    cost (number of energies) the opposing active can pay, assuming 1 energy
    attached next turn. It applies the TARGET's weakness/resistance against the
    energy type of the opposing attacker. It returns 0 if the attack cannot be
    read (damage None, e.g. attacks that place counters) -> the caller stays
    conservative.

    EXCEPTION (anti-Alakazam suggestion 1): Powerful Hand (Alakazam 743,
    attackId 1072) has printed damage 0 but real damage = 20 x card in the
    opponent's hand. Without modelling it, ALL the defensive pivots (Hydrapple
    wall, fragile-ex sacrifice, promotions) believed Alakazam hits for 0 and
    never fired in the matchup where we need them most. If the caller passes
    `op_hand_count`, `20 x (hand + 2)` is projected (+2 = draw for the turn +
    Psychic Draw when evolving); without the parameter the usual conservative 0
    is kept.

    EXCEPTION 2 (log 88971843 step 117, vs Festival Lead, LOST): Do the Wave
    (Dipplin 93, attackId 115) also has printed damage 0 and real damage = 20 x
    the opposing BENCH. The scale is read from the per-turn flag
    `_op_bench_count` (see DO_THE_WAVE_ATTACK_ID): that way ALL callers see it,
    without depending on each one remembering to pass an extra parameter.

    `scaled=True` -- THE REST OF THAT FAMILY, OPT-IN (ago 2026, registro_013).
    Those two "exceptions" were the whole of the model. A census of the 406
    opposing decks in the repo found FIFTEEN attacks whose damage is a count of
    something on the board, and the other thirteen were being projected as the
    placeholder printed on the card: 30 for a Syrup Storm that the engine
    resolved at 270 in that very game. They live in `ptcg/cards/op_scaling.py`
    and read the per-turn snapshot `AGENT_STATE.op_scale`.

    WHY IT IS OPT-IN, AND NOT SIMPLY THE TRUTH FOR EVERYONE. Because the number
    is right and the rules that read it are not calibrated for it. Turning it on
    for all 42 call sites measured, against HEAD, three independent samples of
    4000 self-play games:

        turn plan only        51.1% / 49.2% / 50.4%   premios +0.08 / -0.03 / +0.00
        + scale everywhere    49.2% / 48.9% / 49.8%   premios -0.10 / -0.08 / -0.05

    Three negative prize differentials out of three is not shuffle noise. The
    flips say what happened: the defensive machinery downstream of this function
    (`active_ko_likely`, `active_doomed_real`, the doomed-ex sacrifice pivot, the
    promotion that has to survive) was tuned to fire rarely BECAUSE the
    projection was low, and a projection three times larger turns the agent
    passive from turn 4 -- ATTACK becoming RETREAT with five prizes still on the
    table.

    So the accurate number ships where nothing was ever calibrated against the
    blind one: the turn plan's `op_prizes_next` (ptcg/turn/game_plan.py), which
    is new. Migrating the other call sites is a per-site job with its own
    measurement, not a flag flip -- each of them encodes a threshold that was
    fitted to the old reading.

    `scale` -- THE BOARD THIS PROJECTION HAPPENS ON. Default None means "the
    board as it stands", `AGENT_STATE.op_scale`, which is right for every
    question about their NEXT turn asked from the board of this one. It is not
    right for a projection over a board our own turn is about to change: after
    we knock their active out, the body that replies comes off their bench, and
    their bench is one body smaller than the snapshot says. Do the Wave counts
    exactly that, so the caller passes a corrected snapshot rather than
    overstating their damage by 20 -- the same arithmetic as `_promo_bench_after`
    on our side of the table, and the same direction of error if it is skipped.
    """
    if op_active is None or target is None:
        return 0
    opd = card_table.get(op_active.id)
    if not opd or not getattr(opd, 'attacks', None):
        return 0
    avail = len(op_active.energies) + 1
    best = 0
    best_ignores_weakness = False
    for _aid in opd.attacks:
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        _dmg = getattr(_atk, 'damage', 0) or 0
        _need = len(getattr(_atk, 'energies', []) or [])
        _ignores_weakness = False
        if (op_active.id == Alakazam_ex and _aid == POWERFUL_HAND_ATTACK_ID
                and op_hand_count is not None and _need <= avail):
            _dmg = 20 * (op_hand_count + 2)
        elif _aid == DO_THE_WAVE_ATTACK_ID:
            # The bench this attack counts is THEIRS, and `scale` is how a
            # caller says which board it is asking about. None -- every caller
            # that existed before -- keeps reading the per-turn flag, byte for
            # byte. A caller projecting the body they PROMOTE passes a snapshot
            # with that bench already one smaller, because the body doing the
            # counting is the one standing up.
            #
            # This branch sits ABOVE the `scaled` one, so entry 115 of
            # OP_SCALING_DAMAGE is never reached from here: Do the Wave was
            # modelled before the table existed and is not opt-in. The two
            # formulas are pinned against each other in
            # tests/test_the_reply_comes_from_their_bench.py so they cannot
            # drift apart while both exist.
            _bench = (AGENT_STATE._op_bench_count if scale is None
                      else scale.op_bench)
            _dmg = max(_dmg, 20 * _bench)
        elif scaled:
            # THE ATTACKS THAT DO NOT DO THEIR PRINTED DAMAGE (ago 2026). See
            # `scaled` in the docstring for why this is opt-in and not the
            # default, and ptcg/cards/op_scaling.py for the table itself.
            _dmg = op_scaled_damage(
                _aid, _dmg, op_active,
                AGENT_STATE.op_scale if scale is None else scale)
            _ignores_weakness = _aid in OP_SCALING_IGNORES_WEAKNESS
        if _need <= avail and _dmg > best:
            best = _dmg
            best_ignores_weakness = _ignores_weakness
    if best <= 0:
        return 0
    # An ABILITY on the opposing attacker that boosts EVERY attack it uses
    # against our active, before weakness/resistance: Adrena-Power (Okidogi 116)
    # adds 100 while it holds any {D} Energy. Unlike the tools below it does not
    # care whether the target is an ex -- the card says "your opponent's Active
    # Pokemon", full stop -- and this projector is exactly that question: what
    # their active does to the body standing in front of it.
    #
    # Read off the board, not guessed: the condition is the energies attached,
    # which are in the observation. Verified against the engine -- with {D} the
    # Good Punch that PRINTS 70 takes 170 off our active, and 140 off a
    # Fighting-weak body without it, so the bonus really does land before the
    # doubling. See OP_ACTIVE_ABILITY_DAMAGE in ptcg/cards/ids.py for why the
    # +100 HP half of the same ability is deliberately NOT modelled.
    _ability = OP_ACTIVE_ABILITY_DAMAGE.get(op_active.id)
    if _ability is not None:
        _energy_needed, _bonus = _ability
        if _has_energy_of_type(op_active, _energy_needed):
            best += _bonus
    # ...and the same shape of bonus granted by a body on THEIR BENCH to their
    # whole team (Cheer On to Glory, Extra Helpings). It rides on the per-turn
    # flag for the reason the flag exists -- the buff body is not the attacker,
    # so it does not travel in this signature -- and it lands here, before
    # weakness, because that is what the cards print.
    #
    # OPT-IN, exactly like `scaled` and for the same measured reason: this
    # function has 94 call sites and every defensive threshold downstream of it
    # was fitted to a projection that did not include the buff. The reading is
    # correct for all of them; switching them over is a per-site job with its own
    # measurement. Today it ships at the site whose whole job is to answer "can
    # they cash this body before we use it".
    if team_buff:
        best += AGENT_STATE._op_team_dmg_buff
    # Tools on the opposing attacker that add damage against our ACTIVE ex, before
    # weakness/resistance. Maximum Belt (1158, +50) is unconditional; Brave Bangle
    # (1175, +30) only counts if the HOLDER has no Rule Box (Dipplin does not have
    # one; an opposing ex with the Bangle would not get the bonus).
    if target.id in OUR_EX_IDS:
        _op_tool_ids = {getattr(_t, 'id', 0)
                        for _t in (getattr(op_active, 'tools', None) or [])}
        if Maximum_Belt in _op_tool_ids:
            best += 50
        if Brave_Bangle in _op_tool_ids and not _tiene_rule_box(op_active.id):
            best += 30
    tgt = card_table.get(target.id)
    _op_type = getattr(opd, 'energyType', None)
    if best_ignores_weakness:
        # The attack's own text says so (Raging Curse). Without this the
        # projector would double a number the engine never doubles.
        return max(0, int(best))
    if tgt is not None and _op_type is not None:
        if getattr(tgt, 'weakness', None) == _op_type:
            best *= 2
        elif getattr(tgt, 'resistance', None) == _op_type:
            best = max(0, best - 30)
    return max(0, int(best))


def _op_basic_energy_in(cards, energy_type):
    """Basic energy cards of `energy_type` in a zone (their discard pile).

    The resource half of `OP_EVO_ENERGY_ON_PLAY`: an ability that attaches
    "from your discard pile" can only attach what is IN that pile, and on their
    first turns it is empty. Reading it is what keeps the projection from
    inventing a finisher two turns before its fuel exists.
    """
    if not cards or energy_type is None:
        return 0
    n = 0
    for _c in cards:
        _d = card_table.get(getattr(_c, 'id', 0))
        if (_d is not None
                and getattr(_d, 'cardType', None) == CardType.BASIC_ENERGY
                and getattr(_d, 'energyType', None) == energy_type):
            n += 1
    return n


def _op_evolution_attack_damage_to(op_active, target, op_hand_count=None,
                                   team_buff=False, op_discard=None):
    """Damage the EVOLUTION of the opposing active would deal to `target`.

    THE THREAT THAT IS NOT ON THE BOARD YET (user, registro_002 step 25 vs Mega
    Lucario ex, LOST). Every defensive reading of the agent asks
    `_op_active_attack_damage_to`, and that function reads the body that is in
    front of us TODAY. Against an evolution deck the body in front is not the
    one that kills us: on turn 2 the opposing active was a Riolu with one energy
    -- Accelerating Stab, 30 -- and the projector answered 60 against our 170 HP
    Meowth ex. Their next turn it evolved into Mega Lucario ex and hit for 320.

    So this is the same projection run against each card the opposing active can
    become in ONE step, with the energies and tools it already carries (both
    survive an evolution) -- and the projector's own "+1 energy for next turn"
    on top. It answers 0 when the active is a final stage, which is why every
    caller can take `max()` of the two readings without a special case.

    IT ASSUMES THEY HOLD THE EVOLUTION, and that is the deliberate part. Their
    hand is invisible; what is visible is that a pre-evolution is in play, and a
    deck does not play the Basic without the card it evolves into. The agent
    already reasons that way on the offensive side, where cutting the line of an
    opposing pre-evolution with Boss's Orders is worth a Supporter
    (`_preevo_of_ex_line`).

    IT IS OPT-IN, exactly like `scaled=True` above and for the same measured
    reason: the defensive machinery downstream was calibrated against the blind
    reading, and turning a bigger number on for all of it makes the agent
    passive. Its only consumer is the doomed-ex sacrifice pivot
    (`ptcg/turn/options/retreat.py`), whose remaining gates -- three prizes
    still to take, no ready attacker on the bench, a 1-prize body to put in
    front -- keep it to the turns where the alternative is handing over two
    prizes for nothing.
    """
    if op_active is None or target is None:
        return 0
    best = 0
    for _evo_id in _direct_evolution_ids(op_active.id):
        _energies = tuple(getattr(op_active, 'energies', None) or ())
        # ...AND THE EVOLUTION THAT PAYS ITS OWN COST ON THE WAY IN (episode
        # 91522306, step 37 vs Archaludon ex, LOST). Inheriting the energies of
        # the body in front is right for an evolution that has to be charged by
        # hand; against one whose ability attaches on evolution it under-reads
        # by exactly what that ability brings. Their Duraludon carried ONE Metal
        # -- 1 + the attachment of their turn = 2 against a Metal Defender that
        # costs three -- so the projection answered 0 while the real turn was
        # evolve, Assemble Alloy for two Metals out of the discard, 220 and two
        # prizes. The table (OP_EVO_ENERGY_ON_PLAY) is keyed by the card that
        # prints the ability and the energies are of the evolution's own type,
        # which is what those abilities attach.
        #
        # AND IT IS CAPPED BY THE FUEL THAT IS ACTUALLY THERE. Assemble Alloy
        # attaches "from your DISCARD PILE", so on their first turns -- an
        # empty discard -- it brings nothing, and a projection that credited it
        # anyway would condemn our active from turn 1 against a board that
        # cannot yet do anything. `op_discard=None` means the caller did not
        # say, and then nothing is credited: this reading only ever fires where
        # somebody looked.
        _accel = OP_EVO_ENERGY_ON_PLAY.get(_evo_id, 0)
        if _accel:
            _evo_data = card_table.get(_evo_id)
            _evo_type = getattr(_evo_data, 'energyType', None)
            _accel = min(_accel, _op_basic_energy_in(op_discard, _evo_type))
            if _accel and _evo_type is not None:
                _energies = _energies + (int(_evo_type),) * _accel
        _proj = _ProjTarget(_evo_id,
                            tuple(getattr(op_active, 'tools', None) or ()),
                            _energies)
        best = max(best, _op_active_attack_damage_to(_proj, target,
                                                     op_hand_count,
                                                     team_buff=team_buff))
    return best


def _op_window_against_evolution(op_active, evo_card_id, op_hand_count=None):
    """Damage that reaches the ACTIVE spot before our next turn, measured
    against the body an evolution is ABOUT to create.

    It is `_ventana_de_regalo` asked about a body that is not in play yet, and
    it takes the two readings of the opposing threat at their maximum: the one
    in front of us TODAY (`_op_active_attack_damage_to`) and the one they are a
    single evolution away from (`_op_evolution_attack_damage_to`). Both are
    needed because the question this answers spans exactly one opposing turn,
    which is the turn where their pre-evolution stops being a pre-evolution.

    The record that asks for it (registro_004 step 44 vs Abra/Kadabra/Alakazam,
    WON): their active was a Kadabra with one Psychic -- Super Psy Bolt, 30 --
    and our Bayleef at 80/110 became a 130 HP Meganium, which survives 30 with
    room to spare. Their next turn that Kadabra was an Alakazam and Powerful
    Hand hit for 20 x their hand. Reading only the body in front prices the
    front spot off the one threat that will not be there.

    THIS FUNCTION IS THE OPT-IN OF `_op_evolution_attack_damage_to` AT ONE MORE
    SITE, with the same caveat written on it: it ships where the question is
    "can this body do its job in front", never as a global upgrade of
    `estimated_op_damage`, which the defensive machinery was calibrated blind
    against.
    """
    proj = _ProjTarget(evo_card_id)
    hit = max(_op_active_attack_damage_to(op_active, proj, op_hand_count),
              _op_evolution_attack_damage_to(op_active, proj, op_hand_count))
    return _ventana_de_regalo(proj, True, hit)


def _attacker_base_damage(attacker_id, target, effective_energy,
                          grass_scale, teal_self_energy, bench_count):
    """Base damage of one of our attackers against `target`, BEFORE applying
    weakness/resistance/immunity (that is _our_effective_damage's job).

    - effective_energy: EFFECTIVE energy available to attack (len(energies) is
      already effective; include the energy about to be attached if relevant).
    - grass_scale: number of Grass energies used to scale Hydrapple's attack.
    - teal_self_energy: our own energy used to scale Teal Mask's attack
      (internally the target's energy is added to it).
    - bench_count: number of Pokemon on our bench (scales Dipplin's attack).

    Returns 0 if the attacker does not reach its energy requirement
    (ATTACK_ENERGY_REQ, the single source of truth).
    """
    req = AGENT_STATE.ATTACK_ENERGY_REQ
    if attacker_id == Hydrapple_ex and effective_energy >= req[Hydrapple_ex]:
        return 30 + 30 * grass_scale
    if attacker_id == Teal_Mask_Ogerpon_ex and effective_energy >= req[Teal_Mask_Ogerpon_ex]:
        # Myriad Leaf Shower (attack 120): "30 more damage for each Energy attached to
        # BOTH Active Pokemon" -> it counts the energy on OUR active Ogerpon PLUS the
        # energy on the opposing active. Verified against the REAL damage of 6 records
        # (own 3 + opp 2 -> 180; own 4 + opp 2 -> 210; own 4 + opp 0 -> 150;
        # own 3 + opp 1 -> 150): with the same own energy the damage changes with the
        # opponent's energy, so it is NOT only ours. `teal_self_energy` is already our
        # EFFECTIVE energy (Meganium's Wild Growth doubles it); `len(target.energies)`
        # is the energy on the opposing active, or on the target we gust with Boss's
        # (which becomes the active and therefore counts).
        _opp_active_e = len(getattr(target, 'energies', []) or []) if target is not None else 0
        return 30 + 30 * (teal_self_energy + _opp_active_e)
    if attacker_id == Tapu_Bulu and effective_energy >= req[Tapu_Bulu]:
        return 220
    if attacker_id == Fezandipiti_ex and effective_energy >= req[Fezandipiti_ex]:
        return 100
    if attacker_id == Meganium and effective_energy >= req[Meganium]:
        return 140
    if attacker_id == Dipplin and effective_energy >= req[Dipplin]:
        return 20 * bench_count
    if attacker_id == Pinsir and effective_energy >= req[Pinsir]:
        return 100
    return 0


def _bench_attacker_can_ko(my_state, target, meganium_active, total_grass_field,
                           bench_count, retreat_grass_after, neutral_zone):
    """Can ANY body on our bench knock `target` out, as things stand?

    The existence question behind every promote route: before paying a retreat
    to bring a body forward, something has to establish that the body it brings
    up actually finishes the job. Walks the bench and stops at the first one
    that does.

    It reads each candidate with the energy ALREADY on it -- no projected
    attachment -- so it answers "is the finisher ready", not "could one be made
    ready". `retreat_grass_after` is the Grass still on the field once the
    retreat is paid, which matters because our scaling attacks count the whole
    field and paying a retreat can shrink the very number they scale on.
    """
    if target is None:
        return False
    if (target.hp or 0) <= 0:
        return False
    _thp = _op_hp_for_our_ko(target, 1)
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        e = len(bp.energies)
        eff = e * _grass_mult()
        base = _attacker_base_damage(bp.id, target, eff,
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
        if base <= 0:
            continue
        if _our_effective_damage(bp, target, base, meganium_active, neutral_zone) >= _thp:
            return True
    return False


def _festival_active_wave_prizes(my_state, op_state, bench_count,
                                 meganium_active, neutral_zone):
    """Prizes the double *Do the Wave* takes with the Dipplin **already in the
    Active spot**: the body in front plus the one that replaces it. 0 otherwise.

    The same law as `_festival_promote_wave_prizes` read from the other route,
    and it needs its own function for a reason the record makes plain. The
    inline damage copy that feeds `_active_already_kos` knows Ogerpon, Hydrapple,
    Tapu Bulu, Meganium and Fezandipiti -- and not Dipplin -- so from the front
    our own wave reads as ZERO and no "does the active already finish it?" rule
    can see it at all. Rather than widen that copy (`_active_already_kos` is read
    by a dozen rules that were measured without it), this answers the one
    question the stadium changes, through the canonical model, and its only
    consumer is `_active_attack_wins_now`.

    What it claims is not new damage, it is a PRIORITY: the turn where our
    charged Dipplin's two waves close our prize count is a turn no gust, no
    Supporter and no defensive pivot may divert. See
    [[el-doble-ataque-del-estadio-tambien-es-nuestro]].
    """
    act = (my_state.active or [None])[0] if my_state.active else None
    if act is None or op_state is None or not _festival_double_wave(act.id):
        return 0
    target = (op_state.active or [None])[0] if op_state.active else None
    if target is None or (target.hp or 0) <= 0 or _ko_not_guaranteed(target):
        return 0
    _e = len(act.energies)
    _eff = _e * _grass_mult()
    _base = _attacker_base_damage(act.id, target, _eff, grass_scale=0,
                                  teal_self_energy=_e, bench_count=bench_count)
    if _base <= 0:
        return 0
    _dmg = _our_effective_damage(act, target, _base, meganium_active,
                                 neutral_zone)
    if _dmg <= 0 or _dmg < _op_hp_for_our_ko(target, 1):
        return 0
    return prize_count_op(target) + _festival_second_wave_prizes(
        op_state, _dmg, target)


def _festival_promote_wave_prizes(my_state, op_state, op_active, bench_count,
                                  can_attach_grass, retreat_grass_after,
                                  meganium_active, neutral_zone):
    """Prizes the PROMOTE route takes when the body it brings up is a **Dipplin
    under Festival Grounds**: the first Do the Wave on their Active plus the
    second one on whatever they promote. 0 when that route does not exist.

    THE ONE ROUTE WHOSE PRIZE COUNT IS NOT THE TARGET'S (user, registro_020
    step 146 vs Festival Lead, episode 92849968 -- WON, and won late). At two
    prizes, with their Applin (40 HP) in front and two Thwackey (100 HP) behind
    it, our bench held an Applin and our hand two Grass. Evolving it, charging
    it and retreating the Teal Mask Ogerpon ex into it is Do the Wave for
    20 x 5 = 100: the Applin dies, they promote a Thwackey, the stadium throws
    the SAME wave again and the Thwackey dies too. Two prizes, two of two,
    game over on turn 20. The agent evolved the Applin, spent both Grass on
    Teal Dance and finished the 40 HP Applin with a 210-damage Myriad -- one
    prize for a turn that had two in it.

    **Why nothing saw it.** Everything this agent had learned about the shared
    stadium was written for a different question. `_festival_sac_pivot` is this
    exact swap, but it is DEFENSIVE: it only fires when the ex in front is
    already doomed (`active_ko_likely`), and here the ex sat at 150/210 in front
    of a 40 HP Applin with nothing to fear. `festival_lead_pays_us_now` only
    stops us discarding the stadium that is paying us. And `prizes_today` in the
    turn plan DID count the second wave -- it read 2 on this very board -- but
    `prizes_today` labels a turn, it does not execute one. The flag that
    executes is `_win_ko_active_via_promote`, and it is fed by
    `_promote_ko_active_prizes`, which answered `prize_count_op(op_active)`:
    ONE. So the plan said RACE, and a RACE turn takes the prize it can see.

    Two readings the generic promote route cannot make, which is why this is a
    function and not a branch:

      * THE PRIZES ARE NOT THE TARGET'S. Every other promote route cashes the
        body it knocks out; this one cashes that body **and** the one that
        replaces it, and only `_festival_second_wave_prizes` knows when the
        second one is real.
      * THE FINISHER MAY STILL BE EMPTY. `_bench_attacker_can_ko` reads each
        candidate with the energy ALREADY on it, on purpose -- it answers "is
        the finisher ready", not "could one be made ready". Do the Wave costs
        ONE Grass and its damage does not scale with energy, so for this body
        alone the distinction collapses: the turn's attachment is the whole
        difference between a route and no route, and the record's Dipplin was
        sitting on zero.

    The bench the wave counts is the one the RETREAT leaves behind, and a
    retreat SWAPS bodies -- the ex goes down as the Dipplin comes up -- so
    `bench_count` is the same number before and after
    ([[la-retirada-intercambia-cuerpos-la-banca-no-encoge]]). The retreat fee is
    paid by the ACTIVE and cannot charge the relay, which is why the attachment
    is spent here without discount.
    """
    if op_active is None or op_state is None:
        return 0
    if (op_active.hp or 0) <= 0 or _ko_not_guaranteed(op_active):
        return 0
    _thp = _op_hp_for_our_ko(op_active, 1)
    req = AGENT_STATE.ATTACK_ENERGY_REQ
    best = 0
    for bp in (my_state.bench or []):
        if bp is None or not _festival_double_wave(bp.id):
            continue
        _e = len(bp.energies)
        _eff = _e * _grass_mult()
        if _eff < req.get(bp.id, 1):
            if not can_attach_grass:
                continue
            _eff += _grass_attach_unit()
            if _eff < req.get(bp.id, 1):
                continue
        _base = _attacker_base_damage(bp.id, op_active, _eff,
                                      grass_scale=retreat_grass_after,
                                      teal_self_energy=_e,
                                      bench_count=bench_count)
        if _base <= 0:
            continue
        _dmg = _our_effective_damage(bp, op_active, _base, meganium_active,
                                     neutral_zone)
        if _dmg <= 0 or _dmg < _thp:
            continue
        best = max(best, prize_count_op(op_active)
                   + _festival_second_wave_prizes(op_state, _dmg, op_active))
    return best


def _promote_ko_active_prizes(my_state, op_active, can_switch, has_switch_card,
                              can_attach_grass, total_grass, bench_count,
                              meganium_active, neutral_zone, op_state=None):
    """Prizes the KO on the opposing ACTIVE is worth **through the retreat**;
    0 when that route does not exist.

    Every other reading of "can I knock out what is in front?" is taken with the
    body standing in the active spot TODAY (`_boss_dmg_to` -> `_bo_can_ko_active`,
    `_bpr_active_can_ko`). For the BENCH targets of a gust the very same blocks DO
    look through the retreat (`_bench_attacker_can_ko`), and that asymmetry is a
    bug: with our active stuck the opposing active is read at 0 prizes and ANY
    1-prize gust beats that 0 -- so the Boss's swaps a 2-prize ex in front for a
    pre-evolution on the bench and the turn cashes half of what it could.
    This answers the same question with the same route the gust is allowed to
    use: retreat, promote, attack.

    It returns 0 -- "the route does not exist" -- when:
      * the CURRENT active already knocks it out (then the play is to ATTACK, and
        `_bo_can_ko_active` is already reading that);
      * the retreat cannot be paid (no switch card and not enough energy);
      * no benched body finishes it after paying that retreat.

    The immunity guards (an ex-immune / ability-immune wall in the active spot)
    belong to the CALLER: against those walls the gust is preferred on purpose
    (`_wall_ko_promote`, [[boss-el-chip-al-activo-no-es-un-premio]]).
    """
    if op_active is None or not can_switch:
        return 0
    if (op_active.hp or 0) <= 0:
        return 0
    act = (my_state.active or [None])[0] if my_state.active else None
    if act is None:
        return 0

    _e = len(act.energies)
    _eff = _e * _grass_mult() + (_grass_attach_unit() if can_attach_grass else 0)
    _base = _attacker_base_damage(act.id, op_active, _eff,
                                  grass_scale=total_grass,
                                  teal_self_energy=_e + (1 if can_attach_grass else 0),
                                  bench_count=bench_count)
    _active_already_kos = (
        _base > 0
        and _our_effective_damage(act, op_active, _base, meganium_active,
                                  neutral_zone) >= _op_hp_for_our_ko(op_active, 1))

    _cost = 0 if has_switch_card else RETREAT_COST.get(act.id, 1)
    if not has_switch_card and len(act.energies) < _cost:
        return 0
    # The retreat DISCARDS whole cards: the Grass on the field that scales
    # Hydrapple is measured AFTER paying it.
    _grass_after = max(0, total_grass - (0 if has_switch_card
                                         else _retreat_grass_units(_cost)))
    # THE SHARED STADIUM PAYS THIS ROUTE TWICE. Asked BEFORE the "the active
    # already knocks it out" guard below, because that guard's premise is that
    # the two routes cash the same prize and the front one is free -- true of
    # every route but this one. Under Festival Grounds the promotion cashes the
    # body it kills AND the body that replaces it, so an active that finishes
    # the same target for ONE prize is not an answer to a swap that takes TWO.
    # See `_festival_promote_wave_prizes` for the record this comes from.
    _fest = _festival_promote_wave_prizes(
        my_state, op_state, op_active, bench_count, can_attach_grass,
        _grass_after, meganium_active, neutral_zone)
    if _active_already_kos and _fest <= prize_count_op(op_active):
        return 0            # attacking is the play, and `_bo_can_ko_active` reads it
    if not _bench_attacker_can_ko(my_state, op_active, meganium_active,
                                  total_grass, bench_count, _grass_after,
                                  neutral_zone):
        return _fest
    return max(_fest, prize_count_op(op_active))


def _hand_revealed_lethal_reply(op_active, target, op_hand_count):
    """The opponent's lethal reply on `target` -- but only when their HAND SIZE
    is what makes it lethal. 0 otherwise.

    Some attacks print no damage at all: Powerful Hand places counters, so the
    table reads 0 and the whole defensive model sees a harmless attacker. That
    is the one seam where the pivots are blind, and it is the seam this answers.
    It reads the opposing attack twice -- the way every other rule already reads
    it, and again counting their hand -- and only speaks when the second is
    lethal and the first is not.

    Everywhere else the ordinary reading is already right, and the machinery
    built and measured against those boards keeps its say.
    """
    hp = getattr(target, 'hp', 0) or 0
    if hp <= 0:
        return 0
    if _op_active_attack_damage_to(op_active, target) >= hp:
        return 0
    seen = _op_active_attack_damage_to(op_active, target,
                                       op_hand_count=op_hand_count)
    return seen if seen >= hp else 0


def _promoted_reply_damage(my_state, op_state, op_hand_count):
    """Damage the body they PROMOTE deals to our ACTIVE, once our own attack
    knocks their active out this turn.

    THE BODY THAT REPLIES IS NOT THE ONE IN FRONT. Every defensive projection in
    this file reads the opposing ACTIVE, and on the boards where we take the
    knockout that body is on its way to the discard. A knockout does not end
    their turn, it forces a PROMOTION -- and unlike a bench swap or a gust,
    which need a hand nobody can see, the bench they promote from is entirely in
    the observation. So the one number a "should I take this prize from the
    front?" rule depends on was being read off a corpse.

    Founding board (user, registro_006 step 54 vs Mega Starmie ex, LOST --
    episode 91693960). Their active was a Cinderace, 160 HP and one energy, whose
    Turbo Flare reads 50; one slot behind it stood a Mega Starmie ex with three
    energies, whose Nebula Beam reads 210. Our Teal Mask Ogerpon ex finished the
    Cinderace from the front for one prize and was then removed by exactly 210 for
    two, with four Grass going to the discard with it. Read off their active the
    reply was 50 and nothing was in danger; read off the body that actually stood
    up it was the game.

    WHAT IT PROJECTS, AND WHAT IT REFUSES TO. The best of their benched bodies
    against our active, read exactly the way their active is read -- the same
    projector, `scaled=True`, the same "one energy attached next turn". It does
    NOT model which one they would choose (that is their decision, not a
    reading), so it takes the worst case for us, the only assumption a defensive
    projection can make honestly.

    THE BENCH IS ONE BODY SMALLER once one of them is standing in front. Do the
    Wave counts their bench, so the projection runs on a corrected snapshot;
    without it their damage reads 20 too high, which is the direction that makes
    a defensive rule fire when it should not.

    0 when their bench is empty: there the knockout wins by bench-out and there
    is no reply to project at all.

    This is the number `_reply_after_promotion` (ptcg/turn/game_plan.py) already
    turned into prizes for the turn plan; both read it from here so the plan's
    data and the retreat's rules cannot drift apart.
    """
    my_active = my_state.active[0] if my_state.active else None
    if my_active is None:
        return 0
    bench = [p for p in (op_state.bench or []) if p is not None]
    if not bench:
        return 0
    scale = replace(AGENT_STATE.op_scale,
                    op_bench=max(0, AGENT_STATE.op_scale.op_bench - 1))
    worst = 0
    for body in bench:
        worst = max(worst, _op_active_attack_damage_to(
            body, my_active, op_hand_count, scaled=True, scale=scale))
    return worst


def _promoted_lethal_reply(my_state, op_state, op_hand_count):
    """The reply that only the body they PROMOTE makes lethal. 0 otherwise.

    The same discipline as `_hand_revealed_lethal_reply`, and for the same
    reason: a correction to a projection is only allowed to speak where the
    ordinary reading is BLIND. It reads the blow twice -- off their active, the
    way every pivot already reads it, and off the bench they are about to
    promote from -- and answers only when the second is lethal and the first is
    not.

    That is the whole seam. Where their active already kills our active, the
    machinery written on a doomed body (the sacrifice pivots, the doomed-ex
    promotions, `_hand_revealed_lethal_reply` itself) has been measured on those
    boards and keeps its say; adding a second lethal reading there changes
    nothing about the board and everything about which rule answers for it --
    measured, and it costs the Marnie step 107 Meowth and two Boss's Orders
    gusts the project already paid for.

    Where their active does NOT kill it, nothing spoke at all. That is the board
    of registro_006 step 54: a Cinderace in front reading 50 against our 210 HP
    ex, and a Mega Starmie ex one slot behind it reading 210. Every defensive
    rule saw the 50.

    NOT symmetric with the hand-revealed reading in one respect: this one is
    only meaningful when our own attack is about to knock their active out --
    otherwise the body that replies is the one standing there. The CALLER owns
    that condition; every call site in ptcg/turn/options/retreat.py is already
    gated on `_active_kos_op_active`.
    """
    my_active = my_state.active[0] if my_state.active else None
    hp = (getattr(my_active, 'hp', 0) or 0) if my_active is not None else 0
    if hp <= 0:
        return 0
    op_active = op_state.active[0] if op_state.active else None
    if _op_active_attack_damage_to(op_active, my_active, op_hand_count) >= hp:
        return 0
    promoted = _promoted_reply_damage(my_state, op_state, op_hand_count)
    return promoted if promoted >= hp else 0


def _reply_reaches_match_point(my_active, op_state, op_active):
    """Would their reply on our ACTIVE leave them one knockout from winning?

    True when the prizes our active hands over take them to their last prize or
    past it -- either their reply wins outright, or it leaves them needing one
    more knockout and nothing else. That is the line between "the body standing
    in front is a trade" and "the body standing in front is the game", and it is
    what tells a defensive pivot apart from a preference.

    WHICH PILE IS WHICH. Prizes cashed for knocking a body out come from the
    pile of the player who cashes them: `prize_count(our body)` comes off
    THEIRS, `prize_count_op(their body)` comes off OURS. This predicate used to
    subtract our own winnings from their pile before comparing -- the one place
    in the codebase that mixed the two sides. Verified on the board of record
    90350002: finishing their Alakazam moved OUR prizes from 4 to 3 and left
    theirs at 1. Everywhere else already reads it correctly (`my_prize <=
    prize_count_op(op_act)` is us winning, `op_prize <= prize_count(card)` is
    them winning).

    The subtraction cost it at both ends. It silenced the rule at THEIR match
    point -- one prize left, where any knockout wins and the pivot matters most
    -- and it fired on boards where their reply is a plain trade, because a pile
    of three minus a two-prize ex reads like a pile of one.

    WHY MATCH POINT AND NOT THE WIN ITSELF. Because that is the boundary the
    rule was measured on. Its founding board (record 90099795, registro_012 step
    120) has them on three prizes against our two-prize ex: their reply leaves
    them on one, not zero. Reading it as "their reply must WIN" would switch the
    whole line off there -- including the Grass spent on the active to pay the
    retreat -- and that line was kept because it was the difference in a game we
    lost. A body that puts them one knockout from the game is already worth a
    retreat; one that merely trades is not.
    """
    if my_active is None or op_active is None:
        return False
    op_left = len(getattr(op_state, 'prize', None) or [])
    return op_left >= 1 and prize_count(my_active) >= op_left - 1


def _relay_reading(bp, target, bench_count, retreat_grass_after,
                   reachable_grass=None):
    """(base damage, effective energy) of a benched body used as a RELAY, with
    the charge the turn can still put on it.

    THE RELAY ARRIVES CHARGED, or it does not arrive at all. Both finisher
    predicates below used to read `len(bp.energies)` and stop there, which asks
    "does this body attack with what is already on it" -- a question about the
    board as it stands, on a rule about a board our own turn is about to change.
    A Hydrapple ex one energy short of Syrup Storm reads as MUTE, and the Night
    Stretcher in hand that recovers the Grass, plus the attachment nobody has
    spent yet, are simply not part of the reading. Every other promote pivot in
    `ptcg/turn/options/retreat.py` already counts that charge
    (`_ogerpon_lethal_promote` names the Night Stretcher route explicitly); these
    two were the ones that did not.

    `reachable_grass` is a callable `(bp) -> physical Grass cards we can still
    attach to bp this turn`, which is `_reachable_grass_for`'s job -- it knows
    both ceilings, the CARDS (hand + Night Stretcher over the discard, the
    retreat's own payment included) and the ROUTES (a free attachment, a
    Ripening Charge, a Teal Dance). None means "read the board as it stands",
    which is what every caller did before and is still the default.

    The recovered Grass counts TWICE and both are real: once as energy on the
    relay, so it reaches its attack cost, and once in `retreat_grass_after`,
    because a Syrup Storm scales with the Grass on the whole field and that card
    lands on the field. Founding board: registro_006 step 54, where the
    Hydrapple ex needed the first to attack at all and the second to reach 180
    over a 160 HP body -- without either number the relay is invisible.
    """
    extra = 0
    if reachable_grass is not None:
        extra = max(0, reachable_grass(bp)) * _grass_attach_unit()
    e = len(bp.energies) + extra
    base = _attacker_base_damage(bp.id, target, e * _grass_mult(),
                                 grass_scale=retreat_grass_after + extra,
                                 teal_self_energy=e, bench_count=bench_count)
    return base, e


def _bench_finisher_that_survives(my_state, target, meganium_active, bench_count,
                                  retreat_grass_after, neutral_zone,
                                  incoming_damage, max_prizes,
                                  reachable_grass=None):
    """Is there a benched body that FINISHES `target` after we retreat AND is
    still standing when their reply lands?

    The lethal sibling of `_bench_attacker_can_ko`, with the two conditions the
    plain one cannot express. The body must outlast `incoming_damage` -- the
    reply we project onto whatever we leave in the active spot -- and it must
    not hand over more prizes than the body it replaces (`max_prizes`). Both
    numbers come from the caller, because only the caller knows which body is
    being replaced and how their attack was projected.

    It answers the question that decides a turn where the knockout is available
    either way: not "can I finish from the front", but "which of the two bodies
    that finish is the one I want standing there afterwards".
    """
    if target is None:
        return False
    if (target.hp or 0) <= 0:
        return False
    _thp = _op_hp_for_our_ko(target, 1)
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        if (bp.hp or 0) <= incoming_damage:
            continue          # it dies to the same reply: the swap buys nothing
        if prize_count(bp) > max_prizes:
            continue          # it hands over more than the body it replaces
        base, _ = _relay_reading(bp, target, bench_count, retreat_grass_after,
                                 reachable_grass)
        if base <= 0:
            continue
        if _our_effective_damage(bp, target, base, meganium_active,
                                 neutral_zone) >= _thp:
            return True
    return False


UPGRADE_PRIZE = 'PRIZE'
UPGRADE_BODY = 'BODY'


def _bench_finisher_upgrade(my_state, active, target, meganium_active,
                            bench_count, retreat_grass_after, neutral_zone,
                            incoming_damage, reachable_grass=None):
    """Among the bodies that take the SAME knockout, which one should be
    STANDING there when the prize is collected?

    The knockout is not in question here: the caller only asks when the active
    already finishes `target`. What is in question is the bill for the body left
    in the active spot afterwards, and it is paid in two currencies:

      * `UPGRADE_PRIZE` -- a benched finisher handing over FEWER prizes than the
        active. The same prize, and half the corpse when it is collected.
      * `UPGRADE_BODY`  -- with the prizes TIED, a benched finisher that
        OUTLASTS the blow the active does not, so the same removal costs the
        opponent another turn and another handful of cards.

    Both are scoped by `incoming_damage`, the projected lethal reply on the
    ACTIVE (0 when their attack does not knock it out): the question is which
    body we are about to TRADE, and where nothing is being traded there is
    nothing to choose. That is also what keeps the rule from talking over the
    plays that are about the prize itself -- a Boss's Orders onto a 2-prize
    bench body is worth more than swapping who takes a 1-prize knockout, and it
    only gets to say so if this rule stays quiet on boards where our active is
    in no danger.

    `''` when the active is already the right body. Prize beats HP, and both
    comparisons are STRICT: a tie is not worth the retreat cost.

    Note what the second tier compares WITHOUT naming it: surviving a blow that
    the active does not means CURRENT HP above it, which is the reading
    `_pdx_act_margin` makes from the other side -- an ex at 50 of its 210 is the
    fragile body, whatever the card prints. The two together are one symmetric
    rule: the healthy twin goes in front and the wounded one waits on the bench,
    whichever of them happens to be standing there now.
    """
    if active is None or target is None:
        return ''
    if (target.hp or 0) <= 0:
        return ''
    _thp = _op_hp_for_our_ko(target, 1)
    if incoming_damage <= 0 or incoming_damage < (active.hp or 0):
        return ''             # nothing is being traded: nothing to choose
    _act_prizes = prize_count(active)
    best = ''
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        _bp_prizes = prize_count(bp)
        if _bp_prizes < _act_prizes:
            tier = UPGRADE_PRIZE
        elif (_bp_prizes == _act_prizes
                and (bp.hp or 0) > incoming_damage):
            tier = UPGRADE_BODY
        else:
            continue          # it pays more, or it does not outlast the reply
        if tier == UPGRADE_BODY and best == UPGRADE_PRIZE:
            continue          # a cheaper corpse was already found
        base, _ = _relay_reading(bp, target, bench_count, retreat_grass_after,
                                 reachable_grass)
        if base <= 0:
            continue          # it does not attack today: it is no relay
        if _our_effective_damage(bp, target, base, meganium_active,
                                 neutral_zone) < _thp:
            continue          # it does not finish: the prize would be lost
        if tier == UPGRADE_PRIZE:
            return UPGRADE_PRIZE
        best = UPGRADE_BODY
    return best


def _ex_active_is_a_wall(act):
    """Is our active ex a body the "do not swap it for a worse body" guard
    should be defending?

    That guard protects a WALL: a big body that costs the opponent a whole turn
    to remove and that pays for itself by attacking once it is charged. Meowth
    ex is not one. It has no entry in `ATTACK_ENERGY_REQ` -- the CURATED list of
    bodies we really attack with, which leaves it out on purpose (see
    `_can_attack_eff`) -- so no amount of energy ever turns it into damage. It
    is a draw engine that got stuck in the active spot, and while it stands
    there the turn cannot attack at all.

    Defending its HP therefore defends nothing, and its two prizes are exactly
    what the opponent is collecting meanwhile. The same reading the promotion
    menu already makes: in front of a body we cannot hurt, ENDURING is not a
    virtue if the survivor takes no HP off it.

    False for anything that is not one of our ex: there the guard never applied.
    """
    if act is None or act.id not in OUR_EX_IDS:
        return False
    return AGENT_STATE.ATTACK_ENERGY_REQ.get(act.id) is not None


def _bench_attacker_best_damage(my_state, target, meganium_active, bench_count,
                                retreat_grass_after, neutral_zone,
                                min_body_hp=0, max_prizes=None):
    """Best EFFECTIVE damage a benched attacker would do to `target` today if we
    promote it (0 = none is ready). Non-lethal sibling of
    `_bench_attacker_can_ko`: it measures CHIP damage, not the KO.

    `min_body_hp` discards bodies that endure less than that threshold (mirror of
    the "do not swap an ex for a worse body" guard in the retreat scorer).
    `max_prizes` discards bodies that hand over more prizes than that -- the
    other half of the same guard, and the only half left when the body going
    down is not a wall (`_ex_active_is_a_wall`).
    """
    if target is None:
        return 0
    best = 0
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        if (bp.hp or 0) < min_body_hp:
            continue
        if max_prizes is not None and prize_count(bp) > max_prizes:
            continue
        e = len(bp.energies)
        base = _attacker_base_damage(bp.id, target, e * _grass_mult(),
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
        if base <= 0:
            continue
        best = max(best, _our_effective_damage(
            bp, target, base, meganium_active, neutral_zone))
    return best


def _snipe_best_target(attacker, op_state, effective_energy, meganium_active,
                       neutral_zone, bench_count=0, grass_scale=0):
    """(target, effective_damage, is_ko) of the BEST opposing Pokemon for the
    `attacker`'s attack, when that attack can also aim at the bench.

    It returns (None, 0, False) if the attacker is not a sniper or does not
    reach the cost of its attack. The damage comes from `_our_effective_damage`,
    which already applies ex immunity (Crustle), the Neutralization Zone,
    Sturdy/Resolute Heart and the weakness/resistance skip specific to
    Fezandipiti (fixed damage)."""
    if attacker is None or attacker.id not in SNIPE_ANY_TARGET_IDS:
        return None, 0, False
    best, best_dmg, best_score = None, 0, 0
    for tgt in _snipe_targets(op_state):
        base = _attacker_base_damage(
            attacker.id, tgt, effective_energy,
            grass_scale=grass_scale, teal_self_energy=effective_energy,
            bench_count=bench_count)
        if base <= 0:
            continue  # the attacker does not reach the cost of its attack
        dmg = _our_effective_damage(attacker, tgt, base, meganium_active,
                                    neutral_zone)
        sc = _snipe_target_score(dmg, tgt)
        if best is None or sc > best_score:
            best, best_dmg, best_score = tgt, dmg, sc
    if best is None:
        return None, 0, False
    return best, best_dmg, (best_dmg > 0
                            and best_dmg >= _op_hp_for_our_ko(best, 1))


def _bench_snipe_best(my_state, op_state, meganium_active, bench_count,
                      retreat_grass_after, neutral_zone):
    """(attacker, target, damage, is_ko) of the best snipe a body ON OUR BENCH
    would fire if a retreat promoted it -- measured against the WHOLE opposing
    field, not only against what is standing in front.

    THE SAME QUESTION AS `_snipe_best_target`, ASKED FROM THE OTHER SIDE OF THE
    RETREAT (user, registro_014 step 129 vs Cornerstone/Ceruledge ex, WON with
    the win thrown away). Our active Hydrapple ex had two energies and a retreat
    cost of three; their active was a Cornerstone Mask Ogerpon ex, whose stance
    cancels every attacker of ours that carries an Ability -- Syrup Storm for a
    literal zero. On our bench sat a Fezandipiti ex at eight energies and on
    theirs two 70 HP bodies, with ONE prize left on our side: Cruel Arrow closed
    the game. One Grass from hand paid the retreat.

    Nothing in the agent saw it. The snipe was only ever read for the body
    ALREADY in the active spot, and the whole retreat/promote family
    (`_bench_attacker_can_ko`, `_bench_attacker_best_damage`,
    `_prizes_via_promote`) prices the promoted body against the opposing ACTIVE
    -- so the sniper's 100 was read as 0 against the wall, no route existed, and
    the energy went to the bench by the generic development band (7700). The
    turn ended attacking the wall for nothing.

    This is a SECOND reading, never a substitute: `_bench_attacker_can_ko`
    answers "does a benched body knock out THIS target" and its callers (the
    gust) mean that literally. Widening it there would answer a question nobody
    asked. Callers that mean "does a benched body knock out ANYTHING" ask both.

    `retreat_grass_after` is the Grass left on the field once the retreat is
    paid (whole cards leave, `_retreat_grass_units`): the same correction every
    other relay reading applies before scaling damage.
    """
    best = (None, None, 0, False)
    best_score = 0
    for bp in (my_state.bench or []):
        if bp is None or bp.id not in SNIPE_ANY_TARGET_IDS:
            continue
        tgt, dmg, is_ko = _snipe_best_target(
            bp, op_state, len(bp.energies) * _grass_mult(), meganium_active,
            neutral_zone, bench_count=bench_count,
            grass_scale=retreat_grass_after)
        if tgt is None or dmg <= 0:
            continue
        score = _snipe_target_score(dmg, tgt)
        if score > best_score:
            best, best_score = (bp, tgt, dmg, is_ko), score
    return best


def _bench_snipe_can_ko(my_state, op_state, meganium_active, bench_count,
                        retreat_grass_after, neutral_zone):
    """Does a benched SNIPER knock something out through the retreat? The
    predicate half of `_bench_snipe_best`, shaped like `_bench_attacker_can_ko`
    so the relay call sites can simply ask both."""
    return _bench_snipe_best(my_state, op_state, meganium_active, bench_count,
                             retreat_grass_after, neutral_zone)[3]


def _snipe_target_score(damage, target):
    """Ranking of a snipe target with the damage ALREADY made effective:
      1) KO (more prizes > more charged > more HP = more developed),
      2) if nothing dies, the chip damage that leaves it CLOSEST to a KO,
      3) immune bodies (damage 0) as a last resort -- the selection is mandatory."""
    if target is None:
        return 0
    _hp = target.hp or 0
    if damage <= 0:
        return 1
    if damage >= _op_hp_for_our_ko(target, 1):
        return (10000 + 1000 * prize_count_op(target)
                + 10 * len(getattr(target, 'energies', []) or [])
                + _hp // 10)
    return 100 + int(100 * damage / max(1, _hp))

__all__ = [
    '_powerful_hand_projected',
    '_ProjTarget',
    '_ko_not_guaranteed',
    '_festival_double_wave',
    '_festival_wave_bench',
    '_festival_second_wave_prizes',
    '_festival_active_wave_prizes',
    '_festival_promote_wave_prizes',
    '_snipe_targets',
    '_our_effective_damage',
    '_tiene_rule_box',
    '_shield_mutes_our_ex',
    '_wall_mutes_our_ex',
    '_defender_punish_damage',
    '_has_energy_of_type',
    '_op_active_attack_damage_to',
    '_op_evolution_attack_damage_to',
    '_op_window_against_evolution',
    '_attacker_base_damage',
    '_bench_attacker_can_ko',
    '_promote_ko_active_prizes',
    '_bench_finisher_that_survives',
    '_bench_finisher_upgrade',
    'UPGRADE_PRIZE',
    'UPGRADE_BODY',
    '_hand_revealed_lethal_reply',
    '_promoted_reply_damage',
    '_promoted_lethal_reply',
    '_reply_reaches_match_point',
    '_bench_attacker_best_damage',
    '_ex_active_is_a_wall',
    '_snipe_best_target',
    '_bench_snipe_best',
    '_bench_snipe_can_ko',
    '_snipe_target_score',
    '_ventana_de_regalo',
    'SHROUD_KO_READING',
    '_has_ability',
    '_shroud_damage_to',
    '_op_hp_for_our_ko',
    'OpHarvest',
    '_op_prize_harvest',
    '_active_closes_with_one_charge',
    'evolution_body_bias',
    '_movable_dmg_after_our_hit',
    '_bench_cashable_after_retreat',
]
