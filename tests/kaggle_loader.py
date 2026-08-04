"""A VERBATIM COPY of Kaggle's agent loader. NO SIDE EFFECTS.

https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/agent.py

It lives in its own file, and not in tests/test_submission.py, FOR A REASON:
the runner that executes the agent in a clean interpreter imports this module, and
if importing it added the project root to `sys.path` (as
test_submission.py does to reach `utils/`), the subprocess would stop resembling
the container -- one of our own packages imported late WOULD resolve and the I1a
failure would never reproduce. This file touches neither sys.path nor imports anything from the
project: only the standard library.

If Kaggle changes its loader, this is the only place that has to be updated.
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
