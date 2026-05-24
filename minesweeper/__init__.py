import json
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from datasets import Dataset
import verifiers as vf

Cell = tuple[int, int]

PLAYING = "playing"
WON = "won"
LOST = "lost"
NO_GUESS_ATTEMPTS = 1000

SYSTEM_PROMPT = """Play Minesweeper by calling play_minesweeper.

Use one command per tool call:
- reveal ROW COL

Coordinates are zero-based. The first reveal is safe.
Reveal all safe cells without revealing a mine. The board is returned after every command.
The mines are placed so the board can be solved by logic without guessing.
Bad command syntax or unrelated tools end the rollout with minimum reward.
"""


class InvalidToolCommandError(ValueError):
    """Raised when the tool command is not reveal ROW COL."""


@dataclass(frozen=True)
class GameConfig:
    rows: int
    cols: int
    mines: int
    seed: int

    def __post_init__(self) -> None:
        if self.rows < 1:
            raise ValueError("rows must be at least 1")
        if self.cols < 1:
            raise ValueError("cols must be at least 1")
        if self.mines < 1:
            raise ValueError("mines must be at least 1")
        if self.mines > self.max_mines:
            message = (
                f"mines must be at most {self.max_mines} "
                f"for a {self.rows}x{self.cols} board"
            )
            raise ValueError(message)

    @property
    def cells(self) -> int:
        return self.rows * self.cols

    @property
    def safe_cells(self) -> int:
        return self.cells - self.mines

    @property
    def first_reveal_safe_cells(self) -> int:
        return min(self.rows, 3) * min(self.cols, 3)

    @property
    def max_mines(self) -> int:
        return self.cells - self.first_reveal_safe_cells


@dataclass
class Game:
    config: GameConfig
    mines: set[Cell] = field(default_factory=set)
    revealed: set[Cell] = field(default_factory=set)
    status: str = PLAYING
    commands: int = 0
    invalid_commands: int = 0
    last_message: str = "new game initialized"

    @classmethod
    def new(cls, config: GameConfig) -> "Game":
        return cls(config=config)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Game":
        return cls(
            config=GameConfig(
                rows=data["rows"],
                cols=data["cols"],
                mines=data["mines"],
                seed=data["seed"],
            ),
            mines=to_cells(data["mine_cells"]),
            revealed=to_cells(data["revealed"]),
            status=data["status"],
            commands=data["commands"],
            invalid_commands=data["invalid_commands"],
            last_message=data["last_message"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.config.rows,
            "cols": self.config.cols,
            "mines": self.config.mines,
            "seed": self.config.seed,
            "mine_cells": from_cells(self.mines),
            "revealed": from_cells(self.revealed),
            "status": self.status,
            "commands": self.commands,
            "invalid_commands": self.invalid_commands,
            "last_message": self.last_message,
        }

    @property
    def total_safe_cells(self) -> int:
        return self.config.safe_cells

    @property
    def revealed_safe_cells(self) -> int:
        return len(self.revealed - self.mines)

    def reveal(self, cell: Cell) -> str:
        self.commands += 1

        if not self.in_bounds(cell):
            return self.invalid(f"{cell} is outside the board")
        if cell in self.revealed:
            return self.invalid(f"{cell} is already revealed")
        if not self.mines:
            self.place_mines(first_cell=cell)
        if cell in self.mines:
            return self.lose(cell)

        opened = self.open_area(cell)
        if self.revealed_safe_cells == self.total_safe_cells:
            self.status = WON
            self.last_message = f"won: revealed the final {opened} safe cell(s)"
        else:
            self.last_message = f"revealed {opened} safe cell(s) from {cell}"
        return self.render()

    def render(self) -> str:
        lines = [
            f"status: {self.status}",
            (
                f"rows: {self.config.rows} cols: {self.config.cols} mines: {self.config.mines} "
                f"revealed_safe: {self.revealed_safe_cells}/{self.total_safe_cells}"
            ),
            "coords: zero-based row col",
            "legend: # hidden, . clear, 1-8 adjacent mines",
            f"last: {self.last_message}",
            "",
        ]
        row_width = len(str(self.config.rows - 1))
        cell_width = len(str(self.config.cols - 1))
        row_label_width = len(f"row {self.config.rows - 1}:")
        header_gap = " " * (row_label_width - len("cols:") + 1)
        header_cells = " ".join(
            f"{col:>{cell_width}}" for col in range(self.config.cols)
        )
        lines.append(f"cols:{header_gap}{header_cells}")

        for row in range(self.config.rows):
            cells = [
                f"{self.visible((row, col)):>{cell_width}}"
                for col in range(self.config.cols)
            ]
            lines.append(f"row {row:>{row_width}}: " + " ".join(cells))

        return "\n".join(lines)

    def visible(self, cell: Cell) -> str:
        if cell in self.revealed:
            count = self.adjacent_mines(cell)
            return "." if count == 0 else str(count)
        return "#"

    def place_mines(self, first_cell: Cell) -> None:
        for attempt in range(NO_GUESS_ATTEMPTS):
            mines = self.sample_mines(first_cell, attempt)
            if self.can_solve_without_guessing(first_cell, mines):
                self.mines = mines
                return

        raise ValueError("could not generate a no-guess board")

    def sample_mines(self, first_cell: Cell, attempt: int) -> set[Cell]:
        all_cells = [
            (row, col)
            for row in range(self.config.rows)
            for col in range(self.config.cols)
        ]
        blocked = {first_cell, *self.neighbors(first_cell)}
        candidates = [cell for cell in all_cells if cell not in blocked]

        seed = f"{self.config.seed}:{first_cell[0]}:{first_cell[1]}:{attempt}"
        rng = random.Random(seed)
        return set(rng.sample(candidates, self.config.mines))

    def can_solve_without_guessing(self, first_cell: Cell, mines: set[Cell]) -> bool:
        revealed: set[Cell] = set()
        known_mines: set[Cell] = set()
        self.open_area_for_solver(first_cell, mines, revealed)

        while len(revealed) < self.total_safe_cells:
            made_progress = False

            for cell in list(revealed):
                hidden_neighbors = [
                    neighbor
                    for neighbor in self.neighbors(cell)
                    if neighbor not in revealed and neighbor not in known_mines
                ]
                if not hidden_neighbors:
                    continue

                known_neighbor_mines = len(
                    [
                        neighbor
                        for neighbor in self.neighbors(cell)
                        if neighbor in known_mines
                    ]
                )
                remaining_mines = (
                    self.adjacent_mines(cell, mines)
                    - known_neighbor_mines
                )

                if remaining_mines == 0:
                    for safe_cell in hidden_neighbors:
                        self.open_area_for_solver(safe_cell, mines, revealed)
                    made_progress = True
                    continue

                if remaining_mines == len(hidden_neighbors):
                    known_mines.update(hidden_neighbors)
                    made_progress = True

            if not made_progress:
                return False

        return True

    def open_area_for_solver(
        self,
        start: Cell,
        mines: set[Cell],
        revealed: set[Cell],
    ) -> None:
        queue: deque[Cell] = deque([start])

        while queue:
            cell = queue.popleft()
            if cell in revealed or cell in mines:
                continue

            revealed.add(cell)
            if self.adjacent_mines(cell, mines) == 0:
                queue.extend(
                    neighbor
                    for neighbor in self.neighbors(cell)
                    if neighbor not in revealed
                )

    def open_area(self, start: Cell) -> int:
        before = len(self.revealed)
        queue: deque[Cell] = deque([start])

        while queue:
            cell = queue.popleft()
            if cell in self.revealed or cell in self.mines:
                continue

            self.revealed.add(cell)
            if self.adjacent_mines(cell) == 0:
                queue.extend(
                    neighbor
                    for neighbor in self.neighbors(cell)
                    if neighbor not in self.revealed
                )

        return len(self.revealed) - before

    def lose(self, cell: Cell) -> str:
        self.revealed.add(cell)
        self.status = LOST
        self.last_message = f"BOOM: revealed a mine at {cell}"
        return self.render()

    def invalid(self, message: str) -> str:
        self.invalid_commands += 1
        self.last_message = f"INVALID: {message}"
        return self.render()

    def adjacent_mines(self, cell: Cell, mines: set[Cell] | None = None) -> int:
        mine_cells = self.mines if mines is None else mines
        return len(
            [
                neighbor
                for neighbor in self.neighbors(cell)
                if neighbor in mine_cells
            ]
        )

    def neighbors(self, cell: Cell) -> list[Cell]:
        row, col = cell
        cells = []
        for next_row in range(row - 1, row + 2):
            for next_col in range(col - 1, col + 2):
                neighbor = (next_row, next_col)
                if neighbor != cell and self.in_bounds(neighbor):
                    cells.append(neighbor)
        return cells

    def in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.config.rows and 0 <= col < self.config.cols


def play_minesweeper(command: str, game_state: dict[str, Any]) -> str:
    """Play one Minesweeper command and return the updated board."""
    game = Game.from_dict(game_state)

    if not isinstance(command, str):
        raise InvalidToolCommandError("command must be a string")

    parts = command.split()

    if len(parts) != 3 or parts[0] != "reveal":
        raise InvalidToolCommandError("command must be: reveal ROW COL")

    try:
        cell = (int(parts[1]), int(parts[2]))
    except ValueError:
        raise InvalidToolCommandError("row and col must be integers")

    output = game.reveal(cell)

    game_state.clear()
    game_state.update(game.to_dict())
    return output


class MinesweeperEnv(vf.StatefulToolEnv):
    def __init__(
        self,
        dataset: Dataset,
        eval_dataset: Dataset,
        max_turns: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            eval_dataset=eval_dataset,
            system_prompt=SYSTEM_PROMPT,
            rubric=vf.Rubric(funcs=[game_reward]),
            max_turns=max_turns,
            stop_errors=[
                InvalidToolCommandError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ],
            **kwargs,
        )
        self.add_tool(play_minesweeper, args_to_skip=["game_state"])

    async def env_response(
        self,
        messages: vf.Messages,
        state: vf.State,
        **kwargs: Any,
    ) -> vf.Messages:
        try:
            tool_messages = []
            last_msg = messages[-1]

            for tool_call in last_msg.tool_calls:
                tool_call_id = tool_call.id

                try:
                    tool_name = tool_call.name
                    parsed_args = json.loads(tool_call.arguments)
                    if not isinstance(parsed_args, dict):
                        message = (
                            "Expected tool arguments to be a dict, got "
                            f"{type(parsed_args).__name__}: {parsed_args}"
                        )
                        raise ValueError(message)
                    tool_args = parsed_args
                except Exception as exc:
                    if self._should_stop_for_error(exc):
                        raise vf.ToolParseError from exc
                    tool_messages.append(
                        vf.ToolMessage(
                            role="tool",
                            content=self.error_formatter(exc),
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                tool_args = self.update_tool_args(
                    tool_name,
                    tool_args,
                    messages,
                    state,
                    **kwargs,
                )
                try:
                    tool_message = await self.call_tool(
                        tool_name,
                        tool_args,
                        tool_call_id,
                    )
                except Exception as exc:
                    if self._should_stop_for_error(exc):
                        raise vf.ToolCallError from exc
                    tool_message = vf.ToolMessage(
                        role="tool",
                        content=self.error_formatter(exc),
                        tool_call_id=tool_call_id,
                    )

                tool_messages.append(tool_message)
                if game_from_state(state).status in {WON, LOST}:
                    state["final_env_response"] = tool_messages
                    break
        except vf.ToolError as exc:
            state["invalid_tool_call"] = str(exc.__cause__ or exc)
            raise
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            state["invalid_tool_call"] = str(exc)
            raise vf.ToolCallError(str(exc)) from exc

        return tool_messages

    async def setup_state(self, state: vf.State) -> None:
        game = Game.new(config_from_state(state))
        state["game"] = game.to_dict()
        await super().setup_state(state)

    def update_tool_args(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        messages: vf.Messages,
        state: vf.State,
        **kwargs: Any,
    ) -> dict[str, Any]:
        tool_args["game_state"] = state["game"]
        return tool_args


def load_environment(
    num_examples: int = 50,
    eval_examples: int = 25,
    rows: int = 5,
    cols: int = 5,
    mines: int = 8,
    base_seed: int = 1000,
    eval_base_seed: int = 2000,
    max_turns: int = 35,
    **kwargs: Any,
) -> vf.Environment:
    train_config = GameConfig(rows=rows, cols=cols, mines=mines, seed=base_seed)
    eval_config = GameConfig(rows=rows, cols=cols, mines=mines, seed=eval_base_seed)
    return MinesweeperEnv(
        dataset=build_dataset(num_examples, train_config),
        eval_dataset=build_dataset(eval_examples, eval_config),
        max_turns=max_turns,
        **kwargs,
    )


def build_dataset(count: int, base: GameConfig) -> Dataset:
    rows = []
    for index in range(count):
        config = GameConfig(
            rows=base.rows,
            cols=base.cols,
            mines=base.mines,
            seed=base.seed + index,
        )
        game = Game.new(config)
        rows.append(
            {
                "question": "\n".join(
                    [
                        (
                            f"rows={config.rows} cols={config.cols} "
                            f"mines={config.mines} seed={config.seed}"
                        ),
                        "",
                        game.render(),
                    ]
                ),
                "info": config.__dict__,
            }
        )
    return Dataset.from_list(rows)


async def game_reward(state: vf.State) -> float:
    game = game_from_state(state)
    if state.get("error") is not None:
        return -1.0
    if state.get("stop_condition") == "no_tools_called":
        return -1.0

    invalid_penalty = 0.1 * game.invalid_commands
    if game.status == WON:
        return max(-1.0, 1.0 - invalid_penalty)

    return -1.0


def config_from_state(state: vf.State) -> GameConfig:
    info = state["info"]
    return GameConfig(
        rows=info["rows"],
        cols=info["cols"],
        mines=info["mines"],
        seed=info["seed"],
    )


def game_from_state(state: vf.State) -> Game:
    return Game.from_dict(state["game"])


def to_cell(value: Any) -> Cell:
    return value[0], value[1]


def to_cells(values: Any) -> set[Cell]:
    return {to_cell(value) for value in values}


def from_cells(cells: set[Cell]) -> list[list[int]]:
    return [[row, col] for row, col in sorted(cells)]
