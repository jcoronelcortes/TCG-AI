"""COPIA VERBATIM del cargador de agentes de Kaggle. SIN EFECTOS SECUNDARIOS.

https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/agent.py

Vive en su propio archivo, y no en tests/test_submission.py, POR UNA RAZON:
el runner que ejecuta el agente en un interprete limpio importa este modulo, y
si al importarlo se anadiese la raiz del proyecto a `sys.path` (como hace
test_submission.py para alcanzar `utils/`), el subproceso dejaria de parecerse
al contenedor -- un paquete propio importado tarde SI se resolveria y el fallo
I1a nunca se reproduciria. Este archivo no toca sys.path ni importa nada del
proyecto: solo la biblioteca estandar.

Si Kaggle cambia su cargador, este es el unico sitio que hay que actualizar.
"""

import os
import sys
from io import StringIO


def get_last_callable(raw, fallback=None, path=None):
    orig_out = sys.stdout
    buffer = StringIO()
    sys.stdout = buffer

    try:
        path_str = path if path is not None else "<string>"
        code_object = compile(raw, path_str, "exec")
        env = {}

        # append exec_dir so that way python agents can import other files
        if path is not None:
            exec_dir = os.path.dirname(path)
            sys.path.append(exec_dir)
        else:
            exec_dir = None

        exec(code_object, env)
        if exec_dir is not None:
            sys.path.pop()
        sys.stdout = orig_out
        output = buffer.getvalue()
        if output:
            print(output)
        return [v for v in env.values() if callable(v)][-1]
    except Exception:
        sys.stdout = orig_out
        output = buffer.getvalue()
        if output:
            print(output)
        if fallback is not None:
            return fallback
        raise
