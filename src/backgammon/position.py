# Copyright 2020 Softwerks LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import dataclasses

# Position ID
# https://www.gnu.org/software/gnubg/manual/html_node/A-technical-description-of-the-Position-ID.html
# Official documentation is inaccurate. Position key (binary string) starts from the opponent's ace point. See:
# https://lists.gnu.org/archive/html/bug-gnubg/2005-01/msg00081.html
# https://lists.gnu.org/archive/html/bug-gnubg/2013-01/msg00010.html
import os
import struct
from typing import List, Optional, Tuple


basename = os.path.basename(__file__)
dirname = os.path.dirname(__file__)

POINTS = 24
POINTS_PER_QUADRANT = int(POINTS / 4)


@dataclasses.dataclass(frozen=True)
class Position:
    board_points: Tuple[int, ...]
    player_bar: int
    player_off: int
    opponent_bar: int
    opponent_off: int

    def enter(self, pips: int) -> Tuple[Optional["Position"], Optional[int]]:
        """
        Try to enter from the bar and return the new position and destination.
        """
        destination: int = POINTS - pips
        if self.board_points[destination] >= -1:
            return self.apply_move(-1, destination), destination
        return None, None

    def player_home(self) -> Tuple[int, ...]:
        """
        Return the players checkers in the player's home board.
        """
        # The players home board can be found by slicing the board by the quadrant size i.e. the first 6 points.
        home_board: Tuple[int, ...] = self.board_points[:POINTS_PER_QUADRANT]
        # Then return a tuple with all the players, but not the opponents points.
        return tuple(point if point > 0 else 0 for point in home_board)

    def opponent_home(self) -> Tuple[int, ...]:
        """
        Return the opponents checkers in the player's home board.
        """
        # The players home board can be found by slicing the board by the quadrant size i.e. the first 6 points.
        home_board: Tuple[int, ...] = self.board_points[:POINTS_PER_QUADRANT]
        # Then return a tuple with all the players, but not the opponents points.
        return tuple(point if point < 0 else 0 for point in home_board)

    def off(self, point: int, pips: int) -> Tuple[Optional["Position"], Optional[int]]:
        """
        Try to move a checker in the player's home board and return the new position and destination."
        """
        if self.board_points[point] > 0:
            destination: int = point - pips
            if destination < 0:
                checkers_on_higher_points: int = sum(
                    self.player_home()[point + 1 : POINTS_PER_QUADRANT]
                )
                if destination == -1 or checkers_on_higher_points == 0:
                    return self.apply_move(point, -1), -1
            elif self.board_points[destination] >= -1:
                return self.apply_move(point, destination), destination
        return None, None

    def move(self, point: int, pips: int) -> Tuple[Optional["Position"], Optional[int]]:
        """
        Try to move a checker and return the new position and destination.
        """
        if self.board_points[point] > 0:
            destination: int = point - pips
            if destination >= 0 and self.board_points[destination] >= -1:
                return self.apply_move(point, destination), destination
        return None, None

    def apply_move(
        self, source: Optional[int], destination: Optional[int]
    ) -> "Position":
        """
        Apply a move and return a new position.
        """
        board_points: List[int] = list(self.board_points)
        player_bar: int = self.player_bar
        player_off: int = self.player_off
        opponent_bar: int = self.opponent_bar
        opponent_off: int = self.opponent_off

        if source == -1:
            player_bar -= 1
        else:
            board_points[source] -= 1

        if destination == -1:
            player_off += 1
        else:
            hit: bool = True if board_points[destination] == -1 else False
            if hit:
                board_points[destination] = 1
                opponent_bar += 1
            else:
                board_points[destination] += 1

        return Position(
            tuple(board_points), player_bar, player_off, opponent_bar, opponent_off
        )

    def swap_players(self) -> "Position":
        """
        Swap the players; essentially mirroring the board for an alternate view.
        """

        return Position(
            board_points=tuple(map(lambda n: -n, self.board_points[::-1])),
            player_bar=self.opponent_bar,
            player_off=self.opponent_off,
            opponent_bar=self.player_bar,
            opponent_off=self.player_off,
        )

    def pip_count(self) -> tuple:
        """
        Counts the number of pips for each player
        """
        player_count: int = 0
        opponent_count: int = 0
        length: int = len(self.board_points)
        # Iterate through the board to sum all the checkers left into a total
        for i in range(0, length):
            point = self.board_points[i]
            # The negative/positivity of the point determines the bias
            # Positive is this player
            if point > 0:
                player_count += point * (i + 1)
            # negative is the opponent
            elif point < 0:
                opponent_count += abs(point) * (length - i)
        # Add any checkers on the bar.
        # Bar is 25 points for a human or 24 when 0 indexing.
        player_count += self.player_bar * 25 if self.player_bar > 0 else 0
        opponent_count += (
            abs(self.opponent_bar) * 25 if abs(self.opponent_bar) > 0 else 0
        )
        return player_count, opponent_count

    @staticmethod
    def decode(position_id: str) -> "Position":
        """
        Decode a position ID and return a Position.

        Position.decode('4HPwATDgc/ABMA')
            Position(
            board_points=(-2, 0, 0, 0, 0, 5, 0, 3, 0, 0, 0, -5, 5, 0, 0, 0, -3, 0, -5, 0, 0, 0, 0, 2),
            player_bar=0,
            player_off=0,
            opponent_bar=0,
            opponent_off=0
            )
        """

        def key_from_id(position_id: str) -> str:
            """Decode the the position ID and return the key (bit string)."""
            position_bytes: bytes = base64.b64decode(position_id + "==")
            position_key: str = "".join(
                [format(b, "08b")[::-1] for b in position_bytes]
            )
            return position_key

        def checkers_from_key(position_key: str) -> Tuple[int, ...]:
            """
            Return a list of checkers.
            """
            return tuple(
                sum(int(n) for n in pos) for pos in position_key.split("0")[:50]
            )

        def merge_points(
            player: Tuple[int, ...], opponent: Tuple[int, ...]
        ) -> Tuple[int, ...]:
            """
            Merge player and opponent board positions and return the combined points.
            """
            return tuple(
                i + j for i, j in zip(player, tuple(map(lambda n: -n, opponent[::-1])))
            )

        position_key: str = key_from_id(position_id)

        checkers: Tuple[int, ...] = checkers_from_key(position_key)

        player_points: Tuple[int, ...] = checkers[25:49]
        opponent_points: Tuple[int, ...] = checkers[:24]
        board_points: Tuple[int, ...] = merge_points(player_points, opponent_points)

        player_bar: int = checkers[49]
        player_off: int = abs(15 - sum(player_points) - player_bar)

        opponent_bar: int = checkers[24]
        opponent_off: int = abs(15 - sum(opponent_points) - abs(opponent_bar))

        return Position(
            board_points=board_points,
            player_bar=player_bar,
            player_off=player_off,
            opponent_bar=opponent_bar,
            opponent_off=opponent_off,
        )

    def encode(self) -> str:
        """
        Encode the position and return a position ID.

        position = Position(
            board_points=(-2, 0, 0, 0, 0, 5, 0, 3, 0, 0, 0, -5, 5, 0, 0, 0, -3, 0, -5, 0, 0, 0, 0, 2),
            player_bar=0,
            player_off=0,
            opponent_bar=0,
            opponent_off=0
        )
         position.encode()
        '4HPwATDgc/ABMA'

        """

        def unmerge_points(
            board_points: Tuple[int, ...],
        ) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
            """
            Return player and opponent board positions starting from their respective ace points.
            """
            player: Tuple[int, ...] = tuple(
                map(
                    lambda n: 0 if n < 0 else n,
                    board_points,
                )
            )
            opponent: Tuple[int, ...] = tuple(
                map(
                    lambda n: 0 if n > 0 else -n,
                    board_points[::-1],
                )
            )
            return player, opponent

        def key_from_checkers(checkers: Tuple[int, ...]) -> str:
            """
            Return a position key (bit string).
            """
            return "".join("1" * n + "0" for n in checkers).ljust(80, "0")

        def id_from_key(position_key: str) -> str:
            """
            Encode the position key and return the ID.
            """
            byte_strings: Tuple[str, ...] = tuple(
                position_key[i : i + 8][::-1] for i in range(0, len(position_key), 8)
            )
            position_bytes: bytes = struct.pack(
                "10B", *(int(b, 2) for b in byte_strings)
            )
            return base64.b64encode(position_bytes).decode()[:-2]

        player_points, opponent_points = unmerge_points(self.board_points)
        checkers: Tuple[int, ...] = (
            opponent_points + (self.opponent_bar,) + player_points + (self.player_bar,)
        )

        position_key: str = key_from_checkers(checkers)

        position_id: str = id_from_key(position_key)

        return position_id
