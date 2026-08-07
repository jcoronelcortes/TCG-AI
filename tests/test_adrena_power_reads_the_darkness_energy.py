"""Okidogi's Adrena-Power: the damage is ours to model, the HP is not.

Okidogi (**116**, a Fighting basic printed at 130 HP) has one ability and one
attack:

    Adrena-Power  If this Pokemon has any {D} Energy attached, it gets +100 HP,
                  and the attacks it uses do 100 more damage to your opponent's
                  Active Pokemon (before applying Weakness and Resistance).
    Good Punch    {F}{F}   70

So the attack that PRINTS 70 hits our active for **170** while a single Darkness
Energy sits on it, and for **340** against a body weak to Fighting -- the +100
lands before the doubling, which the card spells out.

`_op_active_attack_damage_to` is the projector everything defensive hangs off
(`active_ko_likely`, `active_doomed_real`, the promotion that has to survive, the
doomed-ex retreat, the turn plan). It read `attack.damage` and answered 70. That
is the same class of blind spot as Maximum Belt and Do the Wave: not an
approximation, a number the agent could read off the board and was not reading.

WHICH ENERGY COUNTS. Not only Basic {D}. **Prism Energy (16)** provides every
type of Energy while it is attached to a *Basic* Pokemon, and Okidogi is a
Basic -- so a Prism switches Adrena-Power on just as a Basic {D} does. That is
not a special case in our code, because `energies` carries the type the ENGINE
resolved. Probed directly:

    Prism on Applin  (BASIC)    -> energies reports **10** (RAINBOW, every type)
    Prism on Dipplin (STAGE 1)  -> energies reports  **0** (COLORLESS)

The engine applies the card's own "must be a Basic" condition and hands us the
answer. So the rule is one line -- RAINBOW satisfies any energy requirement --
and it covers Legacy Energy (12) for free, while a Prism on an evolved body
correctly counts for nothing.

WHY THE HP HALF IS DELIBERATELY NOT MODELLED. Same reason, the other way round:
the engine already applies it. Probed with two purpose-built decks (4 Okidogi
plus energy, 60 games each arm):

    deck WITH {D}        Okidogi reports maxHp = **230**
    deck with NO {D}     Okidogi reports maxHp = **130**, every single state

`hp` and `maxHp` are what the engine says they are. Adding the ability's +100 on
top of the observation would count it twice and invent a 330 HP body that never
existed.

THE RULE BOTH HALVES SHARE, for the next card of this family: **the observation
already carries every condition the engine resolved -- HP, and the type an
Energy provides. Only what the observation does NOT contain is ours to compute.**

VALIDATION AGAINST THE ENGINE. The projector was compared with the real HP drop,
in two arms:

    deck with Basic {D}   **101 of 103** hits predicted exactly, 0 underestimates
    deck with ONLY Prism  **257 of 268** hits predicted exactly, 0 underestimates

Not one of the misses is an underestimate: they are over-estimates by
construction, because a body with 50 HP left "only" drops 50 from a hit of 70.
The Prism arm carries no Basic {D} at all and still landed 42 hits of 170, which
is the whole point of this paragraph. Before the change every one of them was
projected at 70.

WHAT THE CORPUS CAN AND CANNOT SAY. Okidogi 116 lives in exactly ONE of the 569
opposing decks in the repo -- `competitor_decks/mazo_231.csv` -- and that list
carries **4 Prism Energy** and no Basic {D}. So the ability CAN switch on there,
and a model that only looked for energy type 7 would have been blind to the only
deck in the repo that can use it. One deck is too thin for a winrate signal; the
evidence is the engine probe above and these tests.

NOT the Okidogi of `test_op_scaling_attacks`. That one is **890**, a different
card whose *Settle the Score* scales with the prizes taken last turn; it is
unmodelled and its gate is still red. Same name, different card, different job.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402

OKIDOGI = m.Okidogi_Fighting
FIGHTING = 6
COLORLESS = 0
DARKNESS = m.DARKNESS_ENERGY_TYPE
RAINBOW = m.RAINBOW_ENERGY_TYPE
PRISM_ENERGY = 16
GOOD_PUNCH = 147


def _okidogi(energies, hp=230):
    """Their active as the ENGINE hands it over: hp/maxHp already boosted."""
    return SimpleNamespace(id=OKIDOGI, energies=list(energies),
                           hp=hp, maxHp=hp, tools=[])


def _body(card_id, hp):
    return SimpleNamespace(id=card_id, energies=[], hp=hp, maxHp=hp, tools=[])


# ---------------------------------------------------------------------------
# 1. The card: without these numbers the rest measures nothing
# ---------------------------------------------------------------------------

def test_the_card_is_the_one_we_think_it_is():
    card = m.card_table[OKIDOGI]
    assert card.name == "Okidogi"
    assert card.hp == 130, "the PRINTED 130; the 230 are put there by the engine"
    assert card.energyType == FIGHTING
    assert card.attacks == [GOOD_PUNCH]
    atk = m.attack_table[GOOD_PUNCH]
    assert atk.damage == 70 and atk.energies == [FIGHTING, FIGHTING]


def test_the_ability_is_registered_as_damage_only():
    """The table carries the damage half and nothing else, on purpose."""
    energy, bonus = m.OP_ACTIVE_ABILITY_DAMAGE[OKIDOGI]
    assert (energy, bonus) == (DARKNESS, 100)


def test_okidogi_is_basic_which_is_what_prism_requires():
    assert m.card_table[OKIDOGI].basic is True
    prism = m.card_table[PRISM_ENERGY]
    assert prism.name == "Prism Energy"
    assert "Basic" in prism.skills[0].text and "every type" in prism.skills[0].text


# ---------------------------------------------------------------------------
# 2. The projection
# ---------------------------------------------------------------------------

def test_without_darkness_it_is_the_printed_seventy():
    tapu = _body(m.Tapu_Bulu, 140)          # not weak to Fighting
    assert m._op_active_attack_damage_to(_okidogi([FIGHTING, FIGHTING]), tapu) == 70


def test_one_darkness_energy_turns_seventy_into_a_hundred_and_seventy():
    tapu = _body(m.Tapu_Bulu, 140)
    assert m._op_active_attack_damage_to(
        _okidogi([FIGHTING, FIGHTING, DARKNESS]), tapu) == 170, (
        "with one Darkness Energy attached, the Good Punch that prints 70 hits "
        "the active for 170")


def test_the_bonus_lands_before_the_weakness_doubling():
    """Meowth ex is weak to Fighting: 70x2 = 140 off, (70+100)x2 = 340 on."""
    meowth = _body(m.Meowth_ex, 170)
    assert m.card_table[m.Meowth_ex].weakness == FIGHTING
    assert m._op_active_attack_damage_to(
        _okidogi([FIGHTING, FIGHTING]), meowth) == 140
    assert m._op_active_attack_damage_to(
        _okidogi([FIGHTING, FIGHTING, DARKNESS]), meowth) == 340, (
        "the card says 'before applying Weakness': the +100 lands BEFORE the "
        "doubling")


def test_it_is_the_energy_that_switches_it_on_not_the_card():
    """Fighting energy alone -- the attack's own cost -- adds nothing."""
    tapu = _body(m.Tapu_Bulu, 140)
    plain = m._op_active_attack_damage_to(
        _okidogi([FIGHTING, FIGHTING, FIGHTING, FIGHTING]), tapu)
    assert plain == 70


# ---------------------------------------------------------------------------
# 2b. Prism Energy: the {D} that is not a {D}
# ---------------------------------------------------------------------------

def test_a_prism_on_a_basic_switches_the_ability_on():
    """The engine reports RAINBOW, and RAINBOW is every type -- {D} included.

    This is the ONLY way the ability can fire in the repo's decks:
    `competitor_decks/mazo_231.csv` runs Okidogi with 4 Prism Energy and no
    Basic {D} at all.
    """
    tapu = _body(m.Tapu_Bulu, 140)
    assert m._op_active_attack_damage_to(
        _okidogi([FIGHTING, FIGHTING, RAINBOW]), tapu) == 170, (
        "a Prism on a Basic provides ANY type, {D} included: the engine resolves "
        "that and reports it as RAINBOW")


def test_a_prism_alone_is_enough():
    """No Basic {D} anywhere on the body: one Prism carries the ability."""
    tapu = _body(m.Tapu_Bulu, 140)
    assert m._op_active_attack_damage_to(_okidogi([RAINBOW]), tapu) == 170


def test_a_prism_on_an_evolved_body_provides_only_colorless():
    """Probed: Prism on a Stage 1 reports COLORLESS, so nothing switches on.

    We do not re-check `card.basic` ourselves -- the engine already applied the
    card's condition, and this is what its answer looks like on the wire.
    """
    tapu = _body(m.Tapu_Bulu, 140)
    assert m._op_active_attack_damage_to(
        _okidogi([FIGHTING, FIGHTING, COLORLESS]), tapu) == 70


def test_the_rainbow_rule_lives_in_one_place():
    """`_has_energy_of_type` is the single reader, so Legacy Energy rides free."""
    assert m._has_energy_of_type(_okidogi([RAINBOW]), DARKNESS)
    assert m._has_energy_of_type(_okidogi([DARKNESS]), DARKNESS)
    assert not m._has_energy_of_type(_okidogi([COLORLESS, FIGHTING]), DARKNESS)
    # A rainbow satisfies ANY requirement, which is what "every type" means.
    assert m._has_energy_of_type(_okidogi([RAINBOW]), FIGHTING)


def test_no_other_opposing_active_picks_up_the_bonus():
    """The table is keyed by card, so a {D} attacker that is not Okidogi is untouched."""
    tapu = _body(m.Tapu_Bulu, 140)
    munkidori = SimpleNamespace(id=m.Munkidori_ex, energies=[DARKNESS, DARKNESS],
                                hp=200, maxHp=200, tools=[])
    before = m._op_active_attack_damage_to(munkidori, tapu)
    assert m.OP_ACTIVE_ABILITY_DAMAGE.get(m.Munkidori_ex) is None
    assert m._op_active_attack_damage_to(munkidori, tapu) == before


# ---------------------------------------------------------------------------
# 3. The half that is NOT ours: the HP comes from the observation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reported_hp", [130, 230])
def test_the_hp_is_read_from_the_observation_never_recomputed(reported_hp):
    """A hit equal to the reported HP is lethal, whatever that HP is.

    The engine sends 230 once Okidogi holds {D} and 130 when it does not. If
    anything ever added the ability's +100 on top, a body reported at 230 would
    need 330 to fall and every knockout on it would go silently missing.
    """
    theirs = _okidogi([FIGHTING, FIGHTING, DARKNESS], hp=reported_hp)
    ours = _body(m.Tapu_Bulu, 140)
    dealt = m._our_effective_damage(ours, theirs, reported_hp)
    assert dealt >= (theirs.hp or 0), (
        "the HP that counts is the one the engine reports, not the printed one "
        "plus the ability")
    assert m._our_effective_damage(ours, theirs, reported_hp - 10) < (theirs.hp or 0)
