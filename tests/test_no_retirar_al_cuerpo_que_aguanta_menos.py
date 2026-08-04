"""The one that SURVIVES goes in front: do not retreat a healthy ex for another ex at 50 HP.

Scenario (`registros/registro_012_pasos_163_hasta_180.json`, step 174, turn 12,
LOST vs Alakazam -- episode 88906640):

    US (2 prizes)                            RIVAL (2 prizes)
    active  Teal Mask Ogerpon ex             active  Alakazam 140/140, 1 energy
            **210/210**, 4 energies                  (Powerful Hand: 20 × hand)
    bench   Teal Mask Ogerpon ex **50/210**, 4 en.   bench  Fezandipiti ex (0 en.),
            Meganium 160, Fezandipiti ex,                   Kadabra, Dunsparce ×2
            Meowth ex, Hydrapple ex 330

The agent **retreated the 210 Ogerpon** (paying an energy) to promote the
**50 HP** one, and attacked with that one. The KO was identical -- *Myriad Leaf Shower* counts the
energy of BOTH actives: 30 + 30·(4+1) = 180 ≥ 140 -- so the swap gained
nothing and left in front a body that dies to anything, with the same 2
prizes at stake.

Cause: the **EX FALLBACK** of `_prize_denial_pivot`. That fallback looks for a bench
ex that (a) KNOCKS OUT the rival active and (b) SURVIVES the best projected blow from
the rival bench, and picks by life MARGIN. It met both: 180 ≥ 140, and 50 HP >
30 (Kadabra) → a margin of 20. But it **compared candidates against each other and never against the
ACTIVE**, which made the same KO with a margin of 210 − 30 = **180**.

Fix: `_pdx_act_margin`. The active's own KO and margin are computed (which is why
the active's damage is taken outside the "win now" gate) and the candidate is required to
improve on it **strictly** -- the swap also costs the retreat's energy. Both sides
are ex by construction (the loop only looks at `OUR_EX_IDS`),
so the prizes tie and the only thing that decides is how much each survives.

What does NOT change: the prize-denial pivot is still alive when it really
denies something. The case that created it (`registro_013` step 139: a Hydrapple ex at 10 HP
active, a healthy Ogerpon ex on the bench) improves on the active's margin and still fires.

Golden corpus: a single flip, this step's (RETREAT → play Xerosic).
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_retirada_al_cuerpo_de_50pv_step174.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
ALAKAZAM = m.Alakazam_ex
KADABRA = m.Kadabra


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
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _opcion(obs, tipo):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == tipo)


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_cambio_por_el_cuerpo_de_50pv():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    active = mio["active"][0]
    banca = [b for b in mio["bench"] if b]
    gemelo = next(b for b in banca if b["id"] == OGERPON)

    # The one in front is HEALTHY; the bench one is at 50 of 210.
    assert active["id"] == OGERPON and active["hp"] == 210
    assert gemelo["id"] == OGERPON and gemelo["hp"] == 50
    # Both have the same 4 effective energies: the same attack.
    assert len(active["energies"]) == len(gemelo["energies"]) == 4

    # Both are ex: the swap DENIES no prize (2 in both cases).
    assert m.prize_count_op(
        m.to_observation_class(o).current.players[yo].active[0]) == 2

    # Their Alakazam dies to Myriad: 30 + 30*(4 ours + 1 theirs) = 180 >= 140.
    assert riv["active"][0]["id"] == ALAKAZAM and riv["active"][0]["hp"] == 140
    assert 30 + 30 * (4 + len(riv["active"][0]["energies"])) >= 140

    # The only threat left after the KO is their bench: Kadabra hits for 30.
    assert any(b and b["id"] == KADABRA for b in riv["bench"])
    assert (m.attack_table[m.card_table[KADABRA].attacks[0]].damage or 0) == 30


def test_no_se_retira_el_ogerpon_sano():
    o = _obs()
    retirar = _opcion(o, int(m.OptionType.RETREAT))
    assert m.agent(o) != [retirar], (
        "el activo de 210 PV ya noquea al Alakazam; retirarlo para subir el "
        "gemelo de 50 PV cuesta una energía y deja delante el cuerpo que muere")


# ---------------------------------------------------------------------------
# 2. The margin: what decides, measured on the real board
# ---------------------------------------------------------------------------

def test_el_activo_aguanta_nueve_veces_mas_que_el_candidato():
    o = _obs()
    cur = m.to_observation_class(o).current
    yo = o["current"]["yourIndex"]
    mio = cur.players[yo]
    riv = cur.players[1 - yo]

    def margen(pkm):
        amenaza = max((m._op_active_attack_damage_to(b, pkm, riv.handCount)
                       for b in riv.bench if b is not None), default=0)
        return (pkm.hp or 0) - amenaza

    active = mio.active[0]
    gemelo = next(b for b in mio.bench if b is not None and b.id == OGERPON)
    assert margen(gemelo) == 20        # 50 - 30 (Kadabra)
    assert margen(active) == 180       # 210 - 30
    assert margen(active) > margen(gemelo)
