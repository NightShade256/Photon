import enum
from itertools import chain
from math import ceil, inf
from typing import Union


WIN_PATTERNS = [
    [1, 4, 7],
    [2, 5, 8],
    [3, 6, 9],
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
    [1, 5, 9],
    [3, 5, 7]
]


class Player(enum.Enum):
    FIRST = -10
    NONE = 0
    SECOND = 10

class TicTacToe:

    def __init__(self):
        self._board = [[], [], []]
        for x in self._board:
            for _ in range(3):
                x.append(Player.NONE)

    def is_occupied(self, num: int) -> bool:
        """Checks if the cell is occupied already."""
        cell = self._board[ceil(num / 3) - 1][(num % 3) - 1]

        if cell != Player.NONE:
            return True
        
        return False

    def make_move(self, num: Union[int, list], player: Player) -> bool:
        """Makes a move on the baord."""
        if isinstance(num, list):
            self._board[num[0]][num[1]] = player
            return True
        if (num > 9 or num < 1) or self.is_occupied(num):
            return False

        self._board[ceil(num / 3) - 1][(num % 3) - 1] = player
        return True

    def check_full(self) -> bool:
        """Checks if the board is full."""
        flattened_board = list(chain.from_iterable(self._board))
        acc = [1 for x in flattened_board if x in (Player.FIRST, Player.SECOND)]

        if len(acc) == 9:
            return True

        return False

    def check_win(self, player: Player) -> bool:
        """Checks if the player has won the game."""

        flag = False

        for x in WIN_PATTERNS:
            first_cell = self._board[ceil(x[0] / 3) - 1][(x[0] % 3) - 1]
            second_cell = self._board[ceil(x[1] / 3) - 1][(x[1] % 3) - 1]
            third_cell = self._board[ceil(x[2] / 3) - 1][(x[2] % 3) - 1]
            cond = player == first_cell and first_cell == second_cell
            if cond and second_cell == third_cell:
                flag = True

        return flag

    def check_game_over(self) -> Union[Player, None]:
        """Returns whether a player has won a game."""

        if self.check_win(Player.FIRST):
            return Player.FIRST
        elif self.check_win(Player.SECOND):
            return Player.SECOND
        elif self.check_full():
            return Player.NONE
        
        return None

    def render_board(self) -> str:
        """Renders the board in emoji style."""
        rendered_board = "**__BOARD__**\n\n"

        counter = 0x31

        for row in self._board:
            for column in row:
                if column == Player.FIRST:
                    rendered_board += "\U0000274C"
                elif column == Player.SECOND:
                    rendered_board += "\U00002B55"
                else:
                    rendered_board += f"{chr(counter)}\U0000FE0F\U000020E3"
                counter += 1

            rendered_board += "\n"
        return rendered_board

    def make_move_AI(self):
        """Make a move using the Minimax algorithm."""
        best_moveset = [-inf, None]
        for rcount, row in enumerate(self._board):
            for ccount, col in enumerate(row):
                if col == Player.NONE:
                    self._board[rcount][ccount] = Player.SECOND
                    score = self.minimax(0, False, -inf, inf)
                    self._board[rcount][ccount] = Player.NONE
                    if score > best_moveset[0]:
                        best_moveset[0] = score
                        best_moveset[1] = [rcount, ccount]
        print(best_moveset)
        self.make_move(best_moveset[1], Player.SECOND)

    def minimax(self, depth, is_maximizing, alpha, beta):
        winner = self.check_game_over()
        if winner is not None:
            if winner != Player.NONE:
                return winner.value - depth
            return winner.value

        if is_maximizing:
            best_score = -inf
            for rcount, row in enumerate(self._board):
                for ccount, col in enumerate(row):
                    if col == Player.NONE:
                        self._board[rcount][ccount] = Player.SECOND
                        score = self.minimax(depth + 1, not is_maximizing, alpha, beta)
                        self._board[rcount][ccount] = Player.NONE
                        best_score = max(score, best_score)
                        alpha = max(alpha, score)
                        if beta <= alpha:
                            break
                if beta <= alpha:
                    break
            return best_score
        else:
            best_score = inf
            for rcount, row in enumerate(self._board):
                for ccount, col in enumerate(row):
                    if col == Player.NONE:
                        self._board[rcount][ccount] = Player.FIRST
                        score = self.minimax(depth + 1, not is_maximizing, alpha, beta)
                        self._board[rcount][ccount] = Player.NONE
                        best_score = min(score, best_score)
                        beta = min(beta, score)
                        if beta <= alpha:
                            break
                if beta <= alpha:
                    break
            return best_score
