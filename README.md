# minesweeper

Prime/Verifiers environment for Minesweeper.

Prime needs this package to expose:

```python
load_environment(...) -> vf.Environment
```

The model gets one tool:

```text
play_minesweeper("reveal ROW COL")
```

The board is shown in the initial prompt and returned after every tool call.
Boards are generated in no-guess mode: random mine layouts are rejected until
the built-in logic solver can clear the board from the first reveal without
guessing.

The mine count is capped so the first revealed cell and its neighbors can
always be mine-free. For example, a `5x5` board can have at most `16` mines.

Run a quick local import smoke check from this folder:

```bash
PYTHONPATH=. python - <<'PY'
from minesweeper import load_environment

env = load_environment(num_examples=1, eval_examples=1)
print(type(env).__name__)
PY
```
