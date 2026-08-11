"""The same misattribution as the target guard, on the other side of the attack.

`51dc87d` fixed one half: the plan carries `target` -- 0 their active, 1 and up
their bench -- and `judge()` was comparing its prediction against whichever
single opposing body happened to lose hp. 545 of 611 PHANTOM_KO were the agent
correctly predicting a gust it then did not play.

The plan carries `attacker` in exactly the same shape, over OUR bodies, and only
the ACTIVE can attack. A plan whose attacker is a BENCHED body is a plan about a
body we meant to promote or retreat into; if the turn then attacks with whoever
is already standing in front, the prediction and the damage belong to two
different Pokemon. Nothing read that field either.

WHAT IT WAS WORTH, measured on `crustle_wall_9` at 800 games and only after the
mirror-seat artefact had already been removed:

    56 findings -> 19, with 146 decisions counted as "otro atacante"
    of the 45 DAMAGE_DRIFT, 37 had `plan.attacker` on the bench

and the signature was a giveaway once the numbers were put side by side: the
projection sat at a CONSTANT 140 while the engine resolved 20, 60, 80 and 100 --
exactly `20 x bench` for the Dipplin that did attack. The engine was right about
the bench every single time. The two numbers were simply about different
attackers.

The residue that survives is the one worth reading: 7 phantom knockouts and 12
drifts where we predict MORE damage than the engine deals.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from differential_oracle import planned_attacker_is_the_one_attacking as comparable


def _obs(bench=2):
    return {"current": {"players": [
        {"active": [{"serial": 10, "id": 93}],
         "bench": [{"serial": 20 + i, "id": 96} for i in range(bench)]},
        {"active": [{"serial": 90, "id": 345}], "bench": []},
    ]}}


def test_un_plan_sobre_el_ACTIVO_es_comparable():
    # The only body that can attack is the one standing in front, so a plan
    # about it is a prediction about the attack that just happened.
    assert comparable(_obs(), 0, 0) is True


def test_un_plan_sobre_un_cuerpo_de_la_BANCA_no_lo_es():
    # This is the whole finding: index 1 and up is a body we intended to bring
    # up. If the turn attacked anyway, it attacked with somebody else.
    assert comparable(_obs(), 0, 1) is False
    assert comparable(_obs(bench=4), 0, 4) is False


def test_sin_atacante_apuntado_se_juzga_como_siempre():
    # `None` is "the turn wrote no attacker". Skipping those would silence the
    # detector on every path that predicts without naming a body, which is the
    # opposite of what this guard is for.
    assert comparable(_obs(), 0, None) is True
    assert comparable(_obs(), 0, -1) is True


def test_no_depende_del_tablero_que_se_le_pase():
    # Only the ACTIVE can attack -- that is a rule of the game, not a fact about
    # this board -- so the answer must not change with the bench, and an
    # unreadable observation must not turn a skip into a judgement.
    for tablero in (_obs(bench=0), _obs(bench=5), {}, {"current": {}}, None):
        assert comparable(tablero, 0, 0) is True
        assert comparable(tablero, 0, 2) is False


def test_el_guard_es_el_gemelo_del_de_objetivo_no_su_sustituto():
    """Both have to hold: a plan can name the wrong attacker AND the wrong
    target, and either one on its own makes the comparison meaningless."""
    from differential_oracle import planned_serial

    obs = _obs()
    # The target guard still resolves opponent serials independently of this one.
    assert planned_serial(obs, 1, 0) == 90
    assert planned_serial(obs, 1, 5) is None
    # And the attacker guard says nothing about the target.
    assert comparable(obs, 0, 0) is True
