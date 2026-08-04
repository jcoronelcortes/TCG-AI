"""The "evolvable" snapshot was not decremented when EVOLVING during the turn.

Scenario (user, episode 88909907, registro_006 steps 76-87, turn 6 vs
Marnie's Grimmsnarl ex, WON):

    US (start of turn 6)                         RIVAL
    active  Teal Mask Ogerpon ex 180/210 3 {G}   active  Grimmsnarl ex 310/320
    bench   Meowth ex, Dipplin(709), Applin 40,          bench  Morgrem, 2x Impidimp,
            Teal Mask Ogerpon ex 190/210                        Impidimp
    hand    Unfair Stamp, Night Stretcher, ...
    discard  Dipplin(93 s16), Applin(92 s13), 2 basic Grass

Within THAT SAME turn the agent evolved its bench Applin into Dipplin
(step 79). By step 84 there was no Applin left in play... and even so it
played the **Night Stretcher to recover a Dipplin**: a Stage 1 with nothing
to go on top of and that cannot be put on the bench. A dead card in hand.
Worse still, in step 86 it played the **Unfair Stamp**, which shuffled that Dipplin
back into the deck: two cards spent to change nothing on the board.

Root cause -- a single one, shared by six different decisions. The
`evolvable` snapshot was computed like this in five places in main.py:

    evolvable = field_at_turn_start if (not forest and field_at_turn_start)
                else field_counts

The intention is right: without Forest of Vitality a pre-evolution can only
evolve if it was ALREADY in play at the start of the turn (it did not come out this turn).
But the start-of-turn snapshot is a frozen counter that **is never decremented**
when that same pre-evo is consumed by evolving. After step 79 it said
"Applin: 1" with zero Applin on the table, and with that the two branches
that produced the play fired:

  * `ns->play  dipplin_applin_evolucionable` = 750 -> base 10400 (playing the NS);
  * `ns->dipplin applin_evolucionable`       = 850 (recovering the Dipplin),
    above `ns->grass sin_planta_en_mano` = 750 (the Grass, useful).

Fix (`_evolvable_counts`): the snapshot becomes the INTERSECTION by species
-- present NOW (`field_counts`) **and** present at the start of the turn --, which
is exactly the criterion `_ub_evolve_now_search` and `_lillie_evolve_now`
already used by hand. With a Forest on the table the current snapshot still rules.

With the fix the NS is vetoed (SCORE_VETO) and the turn plays the Unfair
Stamp with ONE CARD MORE in hand; if something forces the recovery menu
anyway, it brings the basic Grass instead of the dead evolution.

SCOPE (measured, not aesthetic): the cleaned-up snapshot is applied ONLY to the two faces
of the Night Stretcher. Applying it also to the other four places with the same
idiom (Ultra Ball x2, Poke Pad, Lillie's) cost **-4.7 points vs
Crustle/Kangaskhan** (68.6% vs 73.3%, n=1000, outside the 95% CI), so those
keep the original idiom. See the note in `_evolvable_counts`.

Measurement of the change that DOES go in (a delta within the SAME run, which is the
only paired one: the bot's absolute level moves ~3 points between runs):
vs Crustle/Kangaskhan **+2.4** (72.5% vs 70.1%), vs Marnie +0.9 (94.7% vs
93.8%), vs Alakazam -0.4 (99.3% vs 99.7%, saturated at 99%). n=1000 each.
Golden corpus: 0 flips (the snapshot already had the right play; this bug
flipped it).
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
            / "marnie_ns_no_recupera_evolucion_sin_preevo_step84.json")

APPLIN, DIPPLIN, HYDRAPPLE = m.Applin, m.Dipplin, m.Hydrapple_ex
CHIKORITA, BAYLEEF = m.Chikorita, m.Bayleef
GRASS = m.Basic_Grass_Energy
NIGHT_STRETCHER = m.Night_Stretcher
UNFAIR_STAMP = m.Unfair_Stamp


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
    m._ub_engine_pivot_turn = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _observaciones():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observaciones"])


def _by_step(obs_list):
    return {o["step"]: o for o in obs_list}


def _card_from_hand(obs, choice):
    o = obs["select"]["option"][choice[0]]
    assert o["type"] == int(m.OptionType.PLAY), o
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["hand"][o["index"]]["id"]


def _card_from_discard(obs, choice):
    o = obs["select"]["option"][choice[0]]
    assert o["type"] == int(m.OptionType.CARD), o
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["discard"][o["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The unit: the evolvable snapshot
# ---------------------------------------------------------------------------

def test_la_preevo_consumida_por_una_evolucion_deja_de_ser_evolucionable():
    """The Applin from the start of the turn is already a Dipplin: there is nothing left to go on top of."""
    inicio = {APPLIN: 1, CHIKORITA: 1}
    ahora = {DIPPLIN: 1, CHIKORITA: 1}  # the Applin evolved this turn
    evolvable = m._evolvable_counts(ahora, inicio, False)
    assert evolvable.get(APPLIN, 0) == 0
    assert evolvable.get(CHIKORITA, 0) == 1


def test_la_preevo_bajada_este_turno_sigue_sin_ser_evolucionable():
    """The other direction of the filter (the one that already worked) is not broken."""
    evolvable = m._evolvable_counts({APPLIN: 1, CHIKORITA: 1},
                                    {CHIKORITA: 1}, False)
    assert evolvable.get(APPLIN, 0) == 0


def test_sin_foto_de_inicio_manda_la_actual():
    """Semantics preserved: an empty snapshot = no data, the current field is used.

    That is how the original idiom behaved (`{}` is falsy) and the first menu of
    each turn depends on it, before the snapshot is filled in."""
    evolvable = m._evolvable_counts({APPLIN: 1}, {}, False)
    assert evolvable.get(APPLIN, 0) == 1


def test_con_forest_manda_la_foto_actual():
    """Forest of Vitality lifts the restriction: what is there NOW counts."""
    evolvable = m._evolvable_counts({APPLIN: 2}, {APPLIN: 1}, True)
    assert evolvable.get(APPLIN, 0) == 2


def test_varias_copias_solo_pierde_la_que_evoluciono():
    """With two Applin at the start and one evolved, ONE evolvable is left."""
    evolvable = m._evolvable_counts({APPLIN: 1, DIPPLIN: 1}, {APPLIN: 2}, False)
    assert evolvable.get(APPLIN, 0) == 1


# ---------------------------------------------------------------------------
# 2. The real turn
# ---------------------------------------------------------------------------

def test_paso84_no_se_juega_la_night_stretcher_por_una_preevo_fantasma():
    obs = _by_step(_observaciones())
    m.agent(obs[76])                       # it sets the start-of-turn snapshot (with the Applin)
    choice = m.agent(obs[84])            # the main menu after evolving
    play = _card_from_hand(obs[84], choice)
    assert play != NIGHT_STRETCHER, (
        "la Night Stretcher recupera un Dipplin sin Applin sobre el que subir")
    assert play == UNFAIR_STAMP


def test_paso84_el_unfair_stamp_se_juega_con_la_mano_entera():
    """The NS no longer slips in AHEAD of the Stamp, which remakes 4 cards and not 3."""
    obs = _by_step(_observaciones())
    m.agent(obs[76])
    yo = obs[84]["current"]["yourIndex"]
    assert len(obs[84]["current"]["players"][yo]["hand"]) == 4
    choice = m.agent(obs[84])
    assert _card_from_hand(obs[84], choice) == UNFAIR_STAMP


def test_paso85_si_se_llega_al_menu_se_recupera_la_planta_no_el_dipplin():
    """A second line of defence: the FETCH does not pick the dead evolution either."""
    obs = _by_step(_observaciones())
    m.agent(obs[76])
    m.agent(obs[84])
    choice = m.agent(obs[85])
    recuperada = _card_from_discard(obs[85], choice)
    assert recuperada != DIPPLIN
    assert recuperada == GRASS


def test_paso84_el_veto_no_depende_del_descarte_sino_del_campo():
    """The Applin in the DISCARD rehabilitates nothing: it is not in play."""
    obs = _by_step(_observaciones())
    yo = obs[85]["current"]["yourIndex"]
    discard = [c["id"] for c in obs[85]["current"]["players"][yo]["discard"]]
    assert APPLIN in discard and DIPPLIN in discard
    campo = obs[84]["current"]["players"][yo]
    in_play = [c["id"] for c in campo["active"] + campo["bench"] if c]
    assert APPLIN not in in_play
    m.agent(obs[76])
    assert _card_from_hand(obs[84], m.agent(obs[84])) != NIGHT_STRETCHER
