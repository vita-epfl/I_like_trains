from enum import Enum


class Move(Enum):
    UP = (0, -1)
    RIGHT = (1, 0)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    DROP = "drop"

    def turn_left(move):
        """
        Helper function you can call on the class. E.g.
        Move.turn_left(Move.UP)
        """
        match move:
            case Move.UP:
                return Move.LEFT
            case Move.RIGHT:
                return Move.UP
            case Move.DOWN:
                return Move.RIGHT
            case Move.LEFT:
                return Move.DOWN
            case _:
                return move

    def turn_right(move):
        """
        Helper function you can call on the class. E.g.
        Move.turn_right(Move.UP)
        """
        match move:
            case Move.UP:
                return Move.RIGHT
            case Move.RIGHT:
                return Move.DOWN
            case Move.DOWN:
                return Move.LEFT
            case Move.LEFT:
                return Move.UP
            case _:
                return move
