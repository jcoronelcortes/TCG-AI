"""vs Marnie (Froslass + Munkidori): do not feed doomed bodies (phase C) or
fill the bench with bodies that pay a toll (phase E).

Phases C and E of `docs/matchups.md`, which were left
unwritten when A, B and D were measured.

**Phase C — do not feed a DOOMED body** (defect D3 of the plan). Game 2
turn 10: *Teal Dance on the benched Ogerpon at 80/210 with 8 energies*, which
died that same turn with 5 Grass on it. Of the 13 Grass in the deck, 8 went
to the discard inside knocked-out bodies.

The plan asked for a cap of "attack cost + 1" while there was a Munkidori on
the field. **That cap is not implemented, and on purpose**: `_attacker_base_damage`
verifies -- against the REAL damage of six records -- that *Myriad Leaf Shower*
scales with the Ogerpon's own energy (30 + 30 × (its own + that of the opposing
active)) and *Syrup Storm* with the Grass on our WHOLE board. An Ogerpon with 8
energies is not overcharged: it hits for 270+. The premise "the surplus above 3 was
a pure gift" is false; what turns the energy into a gift is not the excess
but the **KO**, exactly as the plan's own diagnosis says ("while
the body LIVES the energy is not wasted; the waste happens at the KO").

So the rule is the other half: `_cuerpo_condenado` + the ceiling
`SCORE_CARGA_CONDENADA`. Two design decisions:

  * the window is measured **COMPLETE** (with Adrena-Brain's aimable damage), the
    opposite of Ripening Charge's healing, which uses the GUARANTEED one. There a
    false positive spends the whole ability; here it only diverts the Grass to another
    body of ours -- and for Syrup Storm it makes no difference where it lands.
  * the ceiling goes in a WRAPPER of `energy_score`, not at the end of its body:
    `_energy_score_base` has ~60 `return` statements scattered around (per-matchup caps,
    bench-at-0 bands, retreat pivots) and a ceiling at the end only reached
    the generic tail -- measured, it fired 0 times.

**Phase E — bench hygiene** (defect D5). With Froslass on the field, each body
of ours WITH AN ABILITY pays 20 per round per Froslass without the opponent spending
anything. Meowth ex was already protected; **Fezandipiti ex was not**: it joins the list
of matchups where it is only put down with *Flip the Script* alive or with the bench empty
(E1). And between two DEVELOPMENT plays the body that does not pay the toll is preferred
-- but E2 measured INERT (0 decisions changed) and is not implemented: see the
comment of the same name in `main.py`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
TAPU = m.Tapu_Bulu
APPLIN = m.Applin
DIPPLIN = m.Dipplin
FEZ = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
GRASS = m.Basic_Grass_Energy

FROSLASS = m.Froslass
MUNKIDORI = m.Munkidori
GRIMMSNARL = m.Grimmsnarl_ex
MORGREM = m.Marnies_Morgrem


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _energy_destination(obs, choice):
    """The id of the Pokemon that receives the Grass, or None if no ATTACH was chosen."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(m.OptionType.ATTACH):
        return None
    yo = obs["current"]["players"][obs["current"]["yourIndex"]]
    target_path = (yo["active"][0] if opt.get("inPlayArea") == int(m.AreaType.ACTIVE)
               else yo["bench"][opt["inPlayIndex"]])
    return target_path["id"]


def _play(obs, choice):
    """('PLAY', id) / ('ATTACH', id) / ('END',) ... of the chosen option."""
    opt = obs["select"]["option"][choice[0]]
    tipo = opt.get("type")
    yo = obs["current"]["players"][obs["current"]["yourIndex"]]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", yo["hand"][opt["index"]]["id"])
    if tipo == int(m.OptionType.ATTACH):
        return ("ATTACH", _energy_destination(obs, choice))
    if tipo == int(m.OptionType.END):
        return ("END",)
    return (tipo,)


# ---------------------------------------------------------------------------
# PHASE C — the Grass does not go to the body the opponent can cash in tonight
# ---------------------------------------------------------------------------

def _board_with_wounded_meganium(with_drip=True):
    """A benched Meganium at 30/160 (inside the window if there is drip) next to an
    INTACT benched Ogerpon ex. It reproduces the real flip of step 172 of
    `registros/marnie/partida_1`, where the Grass went to the dying Meganium.

    `con_goteo=False` is the CONTROL group: the same board with an opponent without
    Froslass or Munkidori, where the window is 0 and the rule does not exist.
    """
    opponent_bench = ([pk(FROSLASS, hp=90, max_hp=90),
                    pk(MUNKIDORI, hp=110, max_hp=110, energies=[G], fisicas=1)]
                   if with_drip else [pk(MORGREM, hp=100, max_hp=100)])
    return (Escenario(turn=12, step=172, tac=1)
            .my_active(pk(HYDRAPPLE, hp=110, max_hp=330, energies=[G, G],
                          fisicas=2, pre_evo=[APPLIN, DIPPLIN]))
            .my_bench(pk(MEGANIUM, hp=30, max_hp=160,
                         pre_evo=[CHIKORITA, BAYLEEF]),
                      pk(OGERPON, hp=210, max_hp=210, energies=[G, G],
                         fisicas=2))
            .my_hand(GRASS)
            .op_active(pk(GRIMMSNARL, hp=310, max_hp=320,
                          energies=[G, G], fisicas=2))
            .op_bench(*opponent_bench)
            .op_zonas(hand=5, deck=35, prizes=3)
            .menu_attach_energy()
            .build())


def test_the_grass_does_not_go_to_the_doomed_body():
    obs = _board_with_wounded_meganium(with_drip=True)
    target_path = _energy_destination(obs, m.agent(obs))
    assert target_path == OGERPON, (
        "con Froslass + Munkidori en mesa, el Meganium a 30 PV está DENTRO de "
        "la ventana de regalo (20 de goteo + 30 dirigibles): la Planta debe ir "
        f"al Ogerpon ex intacto, no al cuerpo que muere con ella encima "
        f"(fue a {m.card_table[target_path].name if target_path else target_path})")


def test_with_no_froslass_or_munkidori_the_split_does_not_change():
    # CONTROL: the same board with no drip. The window is 0, no body
    # enters it and the rule cannot fire -- the destination is decided by the
    # usual criterion (the wounded Meganium, which is the one that asks for the most energy).
    obs = _board_with_wounded_meganium(with_drip=False)
    target_path = _energy_destination(obs, m.agent(obs))
    assert target_path == MEGANIUM, (
        "sin Froslass ni Munkidori la Fase C no existe y el reparto debe ser "
        f"el de siempre; obtuvo "
        f"{m.card_table[target_path].name if target_path else target_path}")


def test_an_active_that_attacks_today_does_not_count_as_doomed():
    # The ACTIVE that is inside the window but ATTACKS this turn with that same Grass is
    # not doomed: the energy is cashed in before the opponent plays. An active Ogerpon
    # at 60 HP with 2 energies -> the 3rd pays for its Myriad Leaf Shower.
    obs = (Escenario(turn=12, step=1, tac=1)
           .my_active(pk(OGERPON, hp=60, max_hp=210, energies=[G, G], fisicas=2))
           .my_bench(pk(BAYLEEF, hp=100, max_hp=100, pre_evo=[CHIKORITA]))
           .my_hand(GRASS)
           .op_active(pk(GRIMMSNARL, hp=310, max_hp=320, energies=[G, G],
                         fisicas=2))
           .op_bench(pk(FROSLASS, hp=90, max_hp=90),
                     pk(MUNKIDORI, hp=110, max_hp=110, energies=[G], fisicas=1))
           .op_zonas(hand=5, deck=35, prizes=3)
           .menu_attach_energy()
           .build())
    assert _energy_destination(obs, m.agent(obs)) == OGERPON, (
        "el activo que ataca HOY con esa Planta cobra antes de morir: la Fase C "
        "no debe desviarla al Bayleef de banca")


# ---------------------------------------------------------------------------
# PHASE E — the bench pays a toll with Froslass on the field
# ---------------------------------------------------------------------------

def _board_to_play_fez(with_froslass=True, opponent_prizes=6):
    """A DEVELOPMENT turn with a Fezandipiti ex in hand and the bench in basics.

    The Fezandipiti ex development branch requires `bench_count <= 2` and that the
    bench be all Basics, so the bench is a Tapu Bulu (with a Bayleef the branch is
    not reached and the control would not distinguish anything).

    `premios_rival=5` means the opponent took a prize: the tracking deduces
    that we were knocked out and `ko_last_turn` switches Flip the Script on.
    """
    opponent_bench = ([pk(FROSLASS, hp=90, max_hp=90)] if with_froslass
                   else [pk(MORGREM, hp=100, max_hp=100)])
    return (Escenario(turn=6, step=1, tac=1)
            .my_active(pk(OGERPON, hp=210, max_hp=210, energies=[G, G, G],
                          fisicas=3))
            .my_bench(pk(TAPU, hp=140, max_hp=140))
            .my_hand(FEZ, GRASS)
            .op_active(pk(GRIMMSNARL, hp=320, max_hp=320, energies=[G],
                          fisicas=1))
            .op_bench(*opponent_bench)
            .op_zonas(hand=5, deck=40, prizes=opponent_prizes)
            .menu_hand(with_attachment=True)
            .build())


def test_fezandipiti_is_not_benched_with_froslass_on_the_table():
    obs = _board_to_play_fez(with_froslass=True)
    play = _play(obs, m.agent(obs))
    assert play != ("PLAY", FEZ), (
        "Fezandipiti ex son DOS premios con habilidad: con Froslass en mesa "
        "paga 20 por ronda sin que el rival gaste nada y Munkidori puede "
        f"rematarlo en la banca. No debe bajarse por desarrollo; jugó {play}")


def test_without_froslass_fezandipiti_is_played():
    # CONTROL: the SAME board without Froslass. Here the Fezandipiti ex development
    # branch is still alive (15000) and the body is put down -- which proves that
    # the veto of the previous test comes from phase E1 and not from another condition of
    # the board.
    obs = _board_to_play_fez(with_froslass=False)
    assert _play(obs, m.agent(obs)) == ("PLAY", FEZ), (
        "sin Froslass la ruta de desarrollo de Fezandipiti ex no cambia")


def _board_to_play_applin(with_munkidori=True, with_chain=False):
    """A development turn with an Applin in hand.

    `con_munkidori=True` puts the snipe (30) + one Adrena-Brain (30) on the board:
    the 40 HP of the freshly played Applin fall inside the window. `con_cadena`
    adds the Dipplin in hand and the Forest in play, so the Applin
    evolves the same turn and leaves the window.
    """
    opponent_bench = [pk(FROSLASS, hp=90, max_hp=90)]
    if with_munkidori:
        opponent_bench.append(pk(MUNKIDORI, hp=110, max_hp=110,
                              energies=[G], fisicas=1))
    hand = [APPLIN, GRASS] + ([DIPPLIN] if with_chain else [])
    esc = (Escenario(turn=6, step=1, tac=1)
           .my_active(pk(OGERPON, hp=210, max_hp=210, energies=[G, G, G],
                         fisicas=3))
           .my_bench(pk(TAPU, hp=140, max_hp=140))
           .my_hand(*hand)
           .op_active(pk(GRIMMSNARL, hp=320, max_hp=320, energies=[G],
                         fisicas=1))
           .op_bench(*opponent_bench)
           .op_zonas(hand=5, deck=40, prizes=6))
    if with_chain:
        esc = esc.stadium(m.Forest_of_Vitality)
    return esc.menu_hand(with_attachment=True).build()


def test_a_bare_applin_is_not_played_inside_the_window():
    obs = _board_to_play_applin(with_munkidori=True)
    play = _play(obs, m.agent(obs))
    assert play != ("PLAY", APPLIN), (
        "un Applin recién bajado tiene 40 PV: el snipe de 30 más UN contador "
        "movido por Adrena-Brain ya lo matan, y sin Dipplin en mano no "
        f"evoluciona este turno. Es un premio regalado; jugó {play}")


def test_without_munkidori_the_bare_snipe_does_not_reach():
    # CONTROL: Froslass only. The Applin has no ability, so it does not pay the
    # drip, and the bare snipe (30) does not reach its 40 HP: the rule does not
    # switch on and development goes on as usual.
    obs = _board_to_play_applin(with_munkidori=False)
    assert _play(obs, m.agent(obs)) == ("PLAY", APPLIN), (
        "sin daño dirigible el Applin sobrevive al snipe y se baja igual que "
        "siempre")


def test_with_the_chain_ready_the_applin_is_played():
    # EXCEPTION: with Forest in play and a Dipplin in hand, the Applin evolves the
    # same turn -- the evolution raises the maximum HP without erasing counters, so
    # it leaves the window. That is exactly what the plan asks for: KEEP the piece
    # until it can be chained, not give up the line.
    obs = _board_to_play_applin(with_munkidori=True, with_chain=True)
    assert _play(obs, m.agent(obs)) == ("PLAY", APPLIN), (
        "con Forest + Dipplin la cadena se monta en un turno y el Applin no "
        "queda expuesto")


def test_with_flip_the_script_alive_it_is_played():
    # EXCEPTION: if we were knocked out last turn, Flip the Script IS CASHED IN
    # this turn (it draws 3) and the toll stops mattering -- the same criterion
    # Lucario/Crustle/Cornerstone/Sylveon already used. The KO is declared through the
    # BOARD (the opponent went down to 5 prizes), not by touching the flag by hand.
    obs = _board_to_play_fez(with_froslass=True, opponent_prizes=5)
    assert _play(obs, m.agent(obs)) == ("PLAY", FEZ), (
        "con Flip the Script viva el Fezandipiti ex se cobra ESTE turno: la "
        "Fase E1 no debe vetarlo")
