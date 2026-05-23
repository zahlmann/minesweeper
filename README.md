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

Example rollout:

```text
status: playing
rows: 5 cols: 5 mines: 5 revealed_safe: 0/20
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: new game initialized

    0 1 2 3 4
0 | # # # # #
1 | # # # # #
2 | # # # # #
3 | # # # # #
4 | # # # # #

tool: play_minesweeper("reveal 0 0")

status: playing
rows: 5 cols: 5 mines: 5 revealed_safe: 14/20
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: revealed 14 safe cell(s) from (0, 0)

    0 1 2 3 4
0 | . . . . .
1 | . 1 1 2 1
2 | . 1 # # #
3 | 1 3 # # #
4 | # # # # #

tool: play_minesweeper("reveal 2 3")

status: playing
rows: 5 cols: 5 mines: 5 revealed_safe: 15/20
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: revealed 1 safe cell(s) from (2, 3)

    0 1 2 3 4
0 | . . . . .
1 | . 1 1 2 1
2 | . 1 # 2 #
3 | 1 3 # # #
4 | # # # # #

tool: play_minesweeper("reveal 3 2")

status: playing
rows: 5 cols: 5 mines: 5 revealed_safe: 16/20
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: revealed 1 safe cell(s) from (3, 2)

    0 1 2 3 4
0 | . . . . .
1 | . 1 1 2 1
2 | . 1 # 2 #
3 | 1 3 4 # #
4 | # # # # #
```
