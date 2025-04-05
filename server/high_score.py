import copy
import json
import logging
import threading

logger = logging.getLogger("server.highscore")


class HighScore:
    """
    Load and save each player's high score. This class is a singleton its methods
    are thread-safe.
    """

    FILE_PATH = "player_scores.json"
    _instance = None

    def __new__(cls):
        if HighScore._instance is None:
            HighScore._instance = super().__new__(cls)
        return HighScore._instance

    def __init__(self):
        self.lock = threading.Lock()
        self.scores = dict()

    def update(self, sciper, score):
        """
        Updates the sciper's high score.
        Returns True if the score is a new high score.
        """
        with self.lock:
            if sciper in self.scores:
                if score > self.scores[sciper]:
                    self.scores[sciper] = score
                    return True
            else:
                self.scores[sciper] = score
                return True
            return False

    def get(self):
        with self.lock:
            return copy.copy(self.scores)

    def dump(self, limit=10):
        """
        Dumps the top limit high scores to the logger.
        """

        with self.lock:
            # Sort scores in descending order
            sorted_scores = sorted(
                self.scores.items(), key=lambda x: x[1], reverse=True
            )
            logger.info("===== HIGH SCORES =====")
            for i, (player, score) in enumerate(sorted_scores[:limit], 1):
                logger.info(f"{i}. {player}: {score}")
            logger.info("======================")

    def save(self):
        """
        Save high scores to file.
        """
        with self.lock:
            try:
                with open(HighScore.FILE_PATH, "w") as f:
                    json.dump(self.scores, f, indent=4)
            except Exception as e:
                # TODO(Alok): exception shouldn't be swallowed here.
                logger.error(f"Error saving high scores to file: {e}")

    def load(self):
        with self.lock:
            try:
                with open(HighScore.FILE_PATH, "r") as f:
                    self.scores = json.load(f)
            except Exception as e:
                logger.error(
                    f"Error loading high score file. Will create a new one on save. {e}"
                )
