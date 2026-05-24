# minesweeper

Prime/Verifiers environment for Minesweeper.

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
rows: 5 cols: 5 mines: 8 revealed_safe: 0/17
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: new game initialized

cols:  0 1 2 3 4
row 0: # # # # #
row 1: # # # # #
row 2: # # # # #
row 3: # # # # #
row 4: # # # # #

tool: play_minesweeper("reveal 0 0")

status: playing
rows: 5 cols: 5 mines: 8 revealed_safe: 6/17
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: revealed 6 safe cell(s) from (0, 0)

cols:  0 1 2 3 4
row 0: . . 2 # #
row 1: 2 2 3 # #
row 2: # # # # #
row 3: # # # # #
row 4: # # # # #

tool: play_minesweeper("reveal 2 2")

status: playing
rows: 5 cols: 5 mines: 8 revealed_safe: 7/17
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: revealed 1 safe cell(s) from (2, 2)

cols:  0 1 2 3 4
row 0: . . 2 # #
row 1: 2 2 3 # #
row 2: # # 2 # #
row 3: # # # # #
row 4: # # # # #

tool: play_minesweeper("reveal 3 0")

status: playing
rows: 5 cols: 5 mines: 8 revealed_safe: 8/17
coords: zero-based row col
legend: # hidden, . clear, 1-8 adjacent mines
last: revealed 1 safe cell(s) from (3, 0)

cols:  0 1 2 3 4
row 0: . . 2 # #
row 1: 2 2 3 # #
row 2: # # 2 # #
row 3: 2 # # # #
row 4: # # # # #
```
