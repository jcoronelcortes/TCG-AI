"""Agent invariants with property-based testing (hypothesis).

Phase 5 of the strategy improvement architecture: instead of one fixture per
bug, hypothesis generates HUNDREDS of valid states (via the StateBuilder, which
guarantees consistency with deck.csv) and checks properties that must
hold in ALL of them:

  1. ROBUSTNESS: main.agent() never raises an exception or returns an invalid
     choice on arbitrary legal states (an exception in production
     is a forfeit: the game lost on the spot).
  2. APPLIN VETO: a 2nd energy is never attached to an Applin that already has
     one (the applin-max-una-energia memory), except for its documented
     exceptions (a complete evolution in hand / a Hydrapple ex in play),
     which the generators exclude on purpose.

`derandomize=True`: the examples are deterministic per code version
(the suite never "flakes"); if an invariant falls, hypothesis shrinks the
counterexample to the minimal state that violates it.

Requires `hypothesis` (pip install hypothesis).
"""

import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m
from golden_corpus import reset_agent
from state_builder import C, G, Scenario, InconsistentState, pk

KANGASKHAN = 756
CRUSTLE = 345
DWEBBLE = 344

# Our own roster WITHOUT Meganium (its Wild Growth doubles the effective energy and
# the synthetic specs with explicit arrays would become ambiguous) and WITHOUT
# Hydrapple ex (a documented exception to the Applin veto).
OWN_ROSTER = [m.Dipplin, m.Chikorita, m.Bayleef, m.Teal_Mask_Ogerpon_ex,
                 m.Tapu_Bulu, m.Meowth_ex]
OPPONENT_ROSTER = [
    pk(KANGASKHAN, hp=160, max_hp=400, energies=[C, G], fisicas=2),
    pk(CRUSTLE, pre_evo=[DWEBBLE]),
    pk(DWEBBLE),
]

AJUSTES = dict(
    max_examples=60, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.filter_too_much,
                           HealthCheck.too_slow])


def _valid_choice(obs, choice):
    sel = obs["select"]
    assert isinstance(choice, list), f"no es lista: {choice!r}"
    assert all(isinstance(i, int) for i in choice), f"indices no int: {choice!r}"
    assert sel["minCount"] <= len(choice) <= sel["maxCount"], (
        f"cantidad fuera de [{sel['minCount']},{sel['maxCount']}]: {choice}")
    assert all(0 <= i < len(sel["option"]) for i in choice), (
        f"indice fuera de rango: {choice} (n={len(sel['option'])})")
    assert len(set(choice)) == len(choice), f"indices repetidos: {choice}"


# ---------------------------------------------------------------------
# Invariant 1: robustness of the Ultra Ball fetch against arbitrary states
# ---------------------------------------------------------------------

@settings(**AJUSTES)
@given(
    active_id=st.sampled_from([m.Dipplin, m.Applin, m.Chikorita,
                               m.Teal_Mask_Ogerpon_ex, m.Tapu_Bulu]),
    active_energies=st.integers(min_value=0, max_value=2),
    bench=st.lists(st.sampled_from(OWN_ROSTER), max_size=3),
    hand=st.lists(st.sampled_from(
        [m.Basic_Grass_Energy, m.Lillie_Determination, m.Boss_Orders,
         m.Night_Stretcher, m.Dipplin]), max_size=3),
    extra_deck=st.lists(st.sampled_from(
        [m.Hydrapple_ex, m.Tapu_Bulu, m.Meganium, m.Chikorita,
         m.Basic_Grass_Energy, m.Lillie_Determination, m.Ultra_Ball,
         m.Forest_of_Vitality]), max_size=6),
    opponent=st.sampled_from(OPPONENT_ROSTER),
    turn=st.integers(min_value=2, max_value=10),
)
def test_invariante_fetch_ub_robusto(active_id, active_energies, bench,
                                     hand, extra_deck, opponent, turn):
    reset_agent(m)
    try:
        esc = (Scenario(turn=turn, step=1, tac=1)
               .my_active(pk(active_id, energies=active_energies))
               .my_bench(*bench)
               .my_hand(*hand)
               .op_active(opponent)
               .op_zonas(hand=5, deck=30, prizes=6)
               # the deck always carries a searchable Pokemon + random extras
               .deck(m.Teal_Mask_Ogerpon_ex, *extra_deck)
               .fetch_ultra_ball()
               .rest_to_discard())
        obs = esc.build()
    except InconsistentState:
        assume(False)  # an impossible composition: discard the example
        return
    choice = m.agent(obs)
    _valid_choice(obs, choice)


# ---------------------------------------------------------------------
# Invariant 2: the veto on the Applin's 2nd energy (and MAIN menu robustness)
# ---------------------------------------------------------------------

@settings(**AJUSTES)
@given(
    applin_active=st.booleans(),
    companiero=st.sampled_from(OWN_ROSTER),
    extra_bench=st.lists(st.sampled_from(OWN_ROSTER), max_size=2),
    energies_comp=st.integers(min_value=0, max_value=2),
    opponent=st.sampled_from(OPPONENT_ROSTER),
    turn=st.integers(min_value=2, max_value=10),
)
def test_invariant_applin_at_most_one_energy(applin_active, companiero,
                                           extra_bench, energies_comp,
                                           opponent, turn):
    reset_agent(m)
    applin = pk(m.Applin, energies=[G], fisicas=1)
    comp = pk(companiero, energies=energies_comp)
    try:
        esc = Scenario(turn=turn, step=1, tac=0)
        if applin_active:
            esc.my_active(applin).my_bench(comp, *extra_bench)
            pos_applin = ("activo", None)
        else:
            esc.my_active(comp).my_bench(applin, *extra_bench)
            pos_applin = ("banca", 0)
        obs = (esc
               .my_hand(m.Basic_Grass_Energy)  # without Dipplin+Hydrapple: no
               # the complete-evolution-this-turn exception applies
               .op_active(opponent)
               .op_zonas(hand=5, deck=30, prizes=6)
               .menu_attach_energy()
               .build())
    except InconsistentState:
        assume(False)
        return
    choice = m.agent(obs)
    _valid_choice(obs, choice)

    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != 8:  # nothing attached (END): the veto was respected
        return
    if pos_applin[0] == "activo":
        es_applin = (opt.get("inPlayArea") == 4)
    else:
        es_applin = (opt.get("inPlayArea") == 5
                     and opt.get("inPlayIndex") == pos_applin[1])
    assert not es_applin, (
        f"2a energia adjuntada a un Applin que ya tenia una (sin Hydrapple "
        f"ex en juego ni evolucion completa en mano): {choice} -> {opt}")
