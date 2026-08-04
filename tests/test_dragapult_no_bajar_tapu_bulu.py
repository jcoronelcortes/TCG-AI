"""vs Dragapult: Tapu Bulu is NOT put down with the board already developed.

Scenario (`registros/registro_003_pasos_018_hasta_056.json`, step 43, turn 3,
LOST vs Dragapult -- episode 88912610):

    US                                         RIVAL (Dragapult)
    active  Meganium 160, 2 energies           active  Dreepy 70 (+ a tool)
    bench   Dipplin 80                         bench   Dreepy, Dreepy
            Teal Mask Ogerpon ex x3 (2 en. each)
    hand    Ultra Ball, Chikorita, Dawn,
            Grass x3, **Tapu Bulu**

With **five Pokémon already in play** the agent put Tapu Bulu down and left the bench
FULL. Two steps earlier the Bug Catching Set had already chosen it (over
Bayleef) to bring it to hand, so the mistake came in a pair: searching for the
card and playing it.

Why it is wrong in THIS matchup. Tapu Bulu is the deck's **manual** attacker:
its job is to hit when the rival switches off our abilities (Iron Thorns,
Cornerstone) or makes our ex immune (Crustle, Sylveon). Dragapult does neither
the one nor the other -- Teal Mask Ogerpon ex and Hydrapple ex attack normally
--, so there it is a filler body with no energy. And every extra body PAYS
the rival:

  * *Phantom Dive* spreads 6 counters around the bench (`op_bench_snipe_threat` already
    switches on in this matchup); with the bench full the spread always
    finds somewhere to hurt;
  * it is one more prize to give away, and it takes the slot the lines that
    do attack need (Applin/Dipplin/Hydrapple ex and Chikorita/Bayleef/Meganium).

Rule (user): **vs Dragapult, Tapu Bulu only goes down with <=2 Pokémon in play**
-- there survival rules, because a KO would leave us with no bench
([[nunca-terminar-turno-banca-vacia]]).

Cause: Tapu Bulu's PLAY branch decided by board, not by matchup. The
condition that fired here (`_tapu_in_play_count >= 4 and meganium_in_play and
not _op_is_crustle_like`) scores 16000 precisely when there are MANY bodies in
play -- exactly the opposite of what this matchup asks for. And it came EARLIER in
the chain than the generic crowding veto (`_tapu_in_play_count > 2`).

Fix: `_dragapult_no_tapu`, computed just once and applied in the four
places that decide the same thing, so that searching and playing cannot contradict
each other ([[state-builder-escenarios-sinteticos]] documents the same pattern in
`_matchup_permite_bajar`):

  * the PLAY branch (first of the chain),
  * the Bug Catching Set / Night Stretcher / Dawn fetches,
  * `_matchup_permite_bajar`, used by the sterile-turn rescue net.

The veto **yields to the wall** (`_op_is_crustle_like`): if on top of that there is something
on the table that cancels abilities or makes our ex immune, Tapu Bulu is again the only
attacker and the matchup collision rules
([[colision-cubchoo-muro-inmune-pivote]]).

Golden corpus: exactly two flips, both from this turn -- the Bug
Catching Set fetch (Tapu Bulu -> Bayleef) and this step (playing Tapu Bulu -> Ultra Ball,
which is what brought the Hydrapple ex).
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
            / "dragapult_no_bajar_tapu_bulu_step43.json")
_REGISTRO = (ROOT / "registros"
             / "registro_003_pasos_018_hasta_056.json")

TAPU = m.Tapu_Bulu
DREEPY = m.Dreepy
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
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
    m._init_cartas_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _idx_tapu(obs):
    """Index of the 'PLAY Tapu Bulu' option in the main menu."""
    mano = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == TAPU:
            return i
    raise AssertionError("el fixture no ofrece bajar Tapu Bulu")


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_banca_llena_vs_dragapult():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    # Five Pokémon in play: the active Meganium + four on the bench.
    banca = [b for b in mio["bench"] if b]
    assert mio["active"][0]["id"] == MEGANIUM
    assert len(banca) == 4
    assert sum(1 for b in banca if b["id"] == OGERPON) == 3
    assert 1 + len(banca) > 2, "con <=2 cuerpos la regla NO aplica"

    # Tapu Bulu is in hand and the menu offers to play it.
    assert any(c["id"] == TAPU for c in mio["hand"])
    assert _idx_tapu(o) == 2

    # The rival is Dragapult (a Dreepy line) and is NOT a wall deck: it neither cancels
    # abilities nor makes our ex immune, so Tapu Bulu is not needed.
    assert riv["active"][0]["id"] == DREEPY
    assert any(b and b["id"] == DREEPY for b in riv["bench"])

    # And the record confirms it was played there (the play this test vetoes).
    fx = json.load(open(_FIXTURE, encoding="utf-8"))
    assert fx["accion_registrada"] == [2]


def test_no_se_baja_tapu_bulu():
    o = _obs()
    m.meganium_in_play = True
    assert m.agent(o) != [_idx_tapu(o)], (
        "vs Dragapult, con 5 Pokémon ya en juego, Tapu Bulu no aporta ataque "
        "y sólo suma un cuerpo al reparto de Phantom Dive")


# ---------------------------------------------------------------------------
# 2. The faithful replay: the same turn reproduced from cold
# ---------------------------------------------------------------------------

def _replay_hasta(paso_final):
    """Replays the record from its first step and returns the decisions."""
    datos = json.load(open(_REGISTRO, encoding="utf-8"))
    pasos = datos["source_step_numbers"]
    decisiones = {}
    for i, par in enumerate(datos["steps"]):
        if pasos[i] > paso_final:
            break
        for item in par:
            obs = item.get("observation") or {}
            if (item.get("status") != "ACTIVE" or not obs.get("select")
                    or obs["current"].get("yourIndex") != 1):
                continue
            decisiones[pasos[i]] = (copy.deepcopy(obs), m.agent(copy.deepcopy(obs)))
    return decisiones


@pytest.mark.skipif(
    not _REGISTRO.exists(),
    reason="registro local rotado (registros/ es transitorio)")
def test_replay_fiel_ni_lo_busca_ni_lo_baja():
    dec = _replay_hasta(43)

    # Step 42: the Bug Catching Set looks at 7 cards and picks 2. Tapu Bulu is
    # no longer one of them (before it came out Grass + Tapu Bulu).
    obs42, eleccion42 = dec[42]
    vistas = obs42["select"]["deck"] or obs42["current"]["looking"]
    elegidas = [vistas[obs42["select"]["option"][i]["index"]]["id"]
                for i in eleccion42]
    assert TAPU in [c["id"] for c in vistas], "el BCS SÍ veía a Tapu Bulu"
    assert TAPU not in elegidas, (
        "no se busca lo que después no se va a poder bajar")

    # Step 43: and the turn goes on through the Ultra Ball (the one that brought Hydrapple ex).
    obs43, eleccion43 = dec[43]
    assert eleccion43 != [_idx_tapu(obs43)]


# ---------------------------------------------------------------------------
# 3. The limits of the rule
# ---------------------------------------------------------------------------

def test_con_dos_cuerpos_en_juego_si_se_baja():
    """<=2 Pokémon in play: survival rules, not the damage spread."""
    o = _obs()
    mio = o["current"]["players"][o["current"]["yourIndex"]]
    mio["bench"] = mio["bench"][:1]          # active + 1 = 2 in play
    m.meganium_in_play = True
    assert m.agent(o) == [_idx_tapu(o)]


def _sin_items_en_mano(obs):
    """Removes the Ultra Ball and rebuilds the menu.

    Tapu Bulu has a ceiling of its own that comes before all this
    (`TAPU_WAIT_FOR_ITEMS_SCORE`: it is not played while there are items left to play,
    [[bug-catching-set-antes-de-bajar-pokemon]]). To measure the matchup
    veto that ceiling has to be taken out of the way.
    """
    yo = obs["current"]["yourIndex"]
    mio = obs["current"]["players"][yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != m.Ultra_Ball]
    mio["handCount"] = len(mio["hand"])
    jugables = {m.Tapu_Bulu, m.Chikorita}
    obs["select"]["option"] = (
        [{"index": i, "type": int(m.OptionType.PLAY)}
         for i, c in enumerate(mio["hand"]) if c["id"] in jugables]
        + [{"type": int(m.OptionType.RETREAT)}, {"type": int(m.OptionType.END)}])


def test_el_veto_cede_ante_un_muro_inmune():
    """A matchup collision: with a Cornerstone on the table Tapu is THE
    attacker again (our ex with an ability do 0), and the veto is lifted."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    riv["active"][0]["id"] = m.Cornerstone_Mask_Ogerpon_ex
    riv["active"][0]["hp"] = riv["active"][0]["maxHp"] = 220
    _sin_items_en_mano(o)
    m.meganium_in_play = True
    assert m.agent(o) == [_idx_tapu(o)]


def test_con_el_muro_fuera_el_veto_vuelve():
    """Control for the previous test: the same board WITHOUT the wall -> still vetoed."""
    o = _obs()
    _sin_items_en_mano(o)
    m.meganium_in_play = True
    assert m.agent(o) != [_idx_tapu(o)]


def test_el_veto_no_toca_otros_matchups():
    """With no Dragapult across the table, the same board still plays Tapu Bulu."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    for pk in riv["active"] + [b for b in riv["bench"] if b]:
        pk["id"] = m.Chikorita                 # any basic, non-Dragapult
        pk["hp"] = pk["maxHp"] = 70
    m.meganium_in_play = True
    assert m.agent(o) == [_idx_tapu(o)]


# ---------------------------------------------------------------------------
# 4. The shared predicate: searching and playing cannot contradict each other
# ---------------------------------------------------------------------------

def test_matchup_permite_bajar_veta_tapu_vs_dragapult():
    campo = {}
    assert m._matchup_permite_bajar(TAPU, campo, False, False,
                                    dragapult_no_tapu=True) is False
    # Without the veto (<=2 bodies, or another rival) it is still allowed...
    assert m._matchup_permite_bajar(TAPU, campo, False, False) is True
    # ...and it only affects Tapu Bulu.
    assert m._matchup_permite_bajar(OGERPON, campo, False, False,
                                    dragapult_no_tapu=True) is True
