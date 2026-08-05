"""Damage: base damage of our attackers, unguaranteed KOs and sniping.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.calc.card import prize_count_op
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.tables import attack_table, card_table
from ptcg.cards.ids import ABILITY_IMMUNE_IDS, Alakazam_ex, Brave_Bangle, DO_THE_WAVE_ATTACK_ID, Dipplin, Drednaw, EX_IMMUNE_IDS, FULL_HP_SURVIVE_IDS, Farigiraf_ex, Fezandipiti_ex, Hydrapple_ex, Maximum_Belt, Meganium, OUR_ABILITY_IDS, OUR_BASIC_EX_IDS, OUR_EX_IDS, POWERFUL_HAND_ATTACK_ID, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calc.energy import _grass_mult
from ptcg.cards.lines import _direct_evolution_ids
from ptcg.cards.op_scaling import OP_SCALING_IGNORES_WEAKNESS, op_scaled_damage
from cg.api import EnergyType
from typing import NamedTuple
from ptcg.cards.ids import Mega_Hawlucha_ex, Survival_Brace


def _powerful_hand_proyectado(op_hand_count: int) -> int:
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


def _ventana_de_regalo(pokemon, is_active, golpe_proyectado, incluir_movible=True):
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
        else max(0, golpe_proyectado or 0)
    chip = AGENT_STATE._op_chip_per_round if pid in OUR_ABILITY_IDS else 0
    return golpe + chip + (AGENT_STATE._op_movable_dmg if incluir_movible else 0)


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


def _op_active_attack_damage_to(op_active, target, op_hand_count=None,
                                scaled=False):
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
            _dmg = max(_dmg, 20 * AGENT_STATE._op_bench_count)
        elif scaled:
            # THE ATTACKS THAT DO NOT DO THEIR PRINTED DAMAGE (ago 2026). See
            # `scaled` in the docstring for why this is opt-in and not the
            # default, and ptcg/cards/op_scaling.py for the table itself.
            _dmg = op_scaled_damage(_aid, _dmg, op_active, AGENT_STATE.op_scale)
            _ignores_weakness = _aid in OP_SCALING_IGNORES_WEAKNESS
        if _need <= avail and _dmg > best:
            best = _dmg
            best_ignores_weakness = _ignores_weakness
    if best <= 0:
        return 0
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


def _bench_attacker_best_damage(my_state, target, meganium_active, bench_count,
                                retreat_grass_after, neutral_zone,
                                min_body_hp=0):
    """Best EFFECTIVE damage a benched attacker would do to `target` today if we
    promote it (0 = none is ready). Non-lethal sibling of
    `_bench_attacker_can_ko`: it measures CHIP damage, not the KO.

    `min_body_hp` discards bodies that endure less than that threshold (mirror of
    the "do not swap an ex for a worse body" guard in the retreat scorer).
    """
    if target is None:
        return 0
    best = 0
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        if (bp.hp or 0) < min_body_hp:
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
    '_powerful_hand_proyectado',
    '_ProjTarget',
    '_ko_not_guaranteed',
    '_snipe_targets',
    '_our_effective_damage',
    '_tiene_rule_box',
    '_op_active_attack_damage_to',
    '_op_evolution_attack_damage_to',
    '_attacker_base_damage',
    '_bench_attacker_can_ko',
    '_bench_attacker_best_damage',
    '_snipe_target_score',
    '_ventana_de_regalo',
]
