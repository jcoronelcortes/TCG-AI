"""Damage: base damage of our attackers, unguaranteed KOs and sniping.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.calc.card import prize_count, prize_count_op
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.tables import attack_table, card_table
from ptcg.cards.ids import ABILITY_IMMUNE_IDS, Alakazam_ex, EVO_BODY_DAMAGE, EVO_BODY_EXPOSURE, EVO_BODY_RESCUE, OP_ACTIVE_ABILITY_DAMAGE, OP_BENCH_SNIPE_DAMAGE, RAINBOW_ENERGY_TYPE, Brave_Bangle, DO_THE_WAVE_ATTACK_ID, Dipplin, Drednaw, EX_IMMUNE_IDS, FULL_HP_SURVIVE_IDS, Farigiraf_ex, Fezandipiti_ex, Hydrapple_ex, Maximum_Belt, Meganium, OUR_ABILITY_IDS, OUR_BASIC_EX_IDS, OUR_EX_IDS, POWERFUL_HAND_ATTACK_ID, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calc.energy import _grass_mult
from ptcg.cards.lines import _direct_evolution_ids
from ptcg.cards.op_scaling import OP_SCALING_IGNORES_WEAKNESS, op_scaled_damage
from cg.api import EnergyType
from typing import NamedTuple
from ptcg.cards.ids import Mega_Hawlucha_ex, Survival_Brace


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
                          meganium_active=False, neutralization_zone=False):
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
                                scaled=False, scale=None):
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


def _op_evolution_attack_damage_to(op_active, target, op_hand_count=None):
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
        _proj = _ProjTarget(_evo_id,
                            tuple(getattr(op_active, 'tools', None) or ()),
                            tuple(getattr(op_active, 'energies', None) or ()))
        best = max(best, _op_active_attack_damage_to(_proj, target,
                                                     op_hand_count))
    return best


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
    if target is None:
        return False
    _thp = target.hp or 0
    if _thp <= 0:
        return False
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


def _bench_finisher_that_survives(my_state, target, meganium_active, bench_count,
                                  retreat_grass_after, neutral_zone,
                                  incoming_damage, max_prizes):
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
    _thp = target.hp or 0
    if _thp <= 0:
        return False
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        if (bp.hp or 0) <= incoming_damage:
            continue          # it dies to the same reply: the swap buys nothing
        if prize_count(bp) > max_prizes:
            continue          # it hands over more than the body it replaces
        e = len(bp.energies)
        base = _attacker_base_damage(bp.id, target, e * _grass_mult(),
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
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
                            incoming_damage):
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
    _thp = target.hp or 0
    if _thp <= 0:
        return ''
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
        e = len(bp.energies)
        base = _attacker_base_damage(bp.id, target, e * _grass_mult(),
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
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
    if damage >= _hp:
        return (10000 + 1000 * prize_count_op(target)
                + 10 * len(getattr(target, 'energies', []) or [])
                + _hp // 10)
    return 100 + int(100 * damage / max(1, _hp))

__all__ = [
    '_powerful_hand_projected',
    '_ProjTarget',
    '_ko_not_guaranteed',
    '_snipe_targets',
    '_our_effective_damage',
    '_tiene_rule_box',
    '_has_energy_of_type',
    '_op_active_attack_damage_to',
    '_op_evolution_attack_damage_to',
    '_attacker_base_damage',
    '_bench_attacker_can_ko',
    '_bench_finisher_that_survives',
    '_bench_finisher_upgrade',
    'UPGRADE_PRIZE',
    'UPGRADE_BODY',
    '_hand_revealed_lethal_reply',
    '_reply_reaches_match_point',
    '_bench_attacker_best_damage',
    '_ex_active_is_a_wall',
    '_snipe_target_score',
    '_ventana_de_regalo',
    'evolution_body_bias',
    '_movable_dmg_after_our_hit',
    '_bench_cashable_after_retreat',
]
