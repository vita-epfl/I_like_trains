import csv
import datetime
import importlib
import logging
import math
import multiprocessing as mp
import random
import traceback
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
import tqdm

from pydantic import BaseModel

from common.config import GradingConfig
from common.messages import Move
from common.state import GameState, Player, RoomChoice, RoomState, Slot
from server.game import Game
from server.room import Room

logger = logging.getLogger("grading")

# Grading works by sequentially loading each agent from the grading config
# and running it through the configured set of runs. Each run happens in its
# own subprocess via ProcessPoolExecutor so that a misbehaving agent cannot
# affect the rest of the grading session. The graded agent is never trusted:
# it only ever sees deep copies of RoomState and GameState and its get_move
# calls are bounded by a configurable timeout.


class RunResult(BaseModel):
    agent_to_grade: str
    map_name: str
    staff_agent_count: int
    seed: int
    # agent's score when running alone, agent's position otherwise
    score: int
    run_time_seconds: float
    # True if the graded agent ever failed to return a move in time and was
    # killed (it forfeits all remaining moves once this happens).
    timed_out: bool = False


# TODO(alok): copy-pasta
def _load_agent_module(base: str, agent_file: str):
    return importlib.import_module(f"{base}.{agent_file.removesuffix('.py')}")


def _run(
    config: GradingConfig, seed: int, n_agents: int, map_name: str, agent_to_grade: str
) -> RunResult:
    rng = random.Random(seed)
    if map_name not in config.maps:
        map_name = rng.choice(sorted(config.maps.keys()))
    map = Room.load_map(map_name, config.maps[map_name])

    total_players = 1 + n_agents
    room_choice = RoomChoice(
        total_players=total_players,
        min_staff_agents=n_agents,
    )
    bus_length = rng.randint(config.bus_min_length, config.bus_max_length)
    room_state = RoomState(
        players=set(),
        room_choice=room_choice,
        created_at=math.floor(datetime.datetime.now().timestamp()),
        room_max_wait_game_start_seconds=0,
        game_duration_ticks=config.game_duration_ticks * total_players,
        desired_passengers=config.desired_passengers,
        respawn_ticks=config.respawn_ticks * total_players,
        bus_length=bus_length,
        max_passengers=config.max_passengers,
        spawn_passenger_away_from_bus_distance=config.spawn_passenger_away_from_bus_distance,
        drop_passenger_from_bus_distance=config.drop_passenger_from_bus_distance,
        passenger_values=config.passenger_values,
        passenger_pickup_from_bus_distance=config.passenger_pickup_from_bus_distance,
        map=map,
    )

    # Assign slots randomly (mirrors Room.__init__)
    available_slots: list[Slot] = list(range(total_players))
    rng.shuffle(available_slots)
    grading_slot = available_slots.pop()
    room_state.players.add(
        Player(teamname=agent_to_grade, slot=grading_slot, is_staff_agent=False)
    )
    staff_names = sorted(config.staff_agents.keys())
    slot_to_module_name: dict[Slot, tuple[str, str]] = {
        grading_slot: ("grading.agents", config.agents_to_grade[agent_to_grade])
    }
    for slot in available_slots:
        staff_name = rng.choice(staff_names)
        staff_file = config.staff_agents[staff_name]
        slot_to_module_name[slot] = ("common.agents", staff_file)
        room_state.players.add(
            Player(teamname=staff_name, slot=slot, is_staff_agent=True)
        )

    # Construct agents only after the Player set is finalized so each agent
    # sees a complete snapshot of the room, including its own Player entry.
    # Each agent runs in its own subprocess so a get_move that never returns
    # can be hard-killed; the process boundary also isolates the agent from
    # the authoritative game state (it only ever sees a pickled copy).
    teamnames = {player.slot: player.teamname for player in room_state.players}
    agents: dict[Slot, AgentProcess] = {}
    for slot, (base, file) in slot_to_module_name.items():
        agents[slot] = AgentProcess(
            base, file, room_state, slot, teamnames[slot], _loggers
        )

    game = Game(rng, room_state, 1)

    start = datetime.datetime.now()
    try:
        while True:
            slot = game.tick()
            if slot is None:
                break
            if not game.bus_is_alive(slot):
                continue
            move = agents[slot].get_move(game.game_state, config.agent_timeout_seconds)
            game.move(slot, move)
        timed_out = agents[grading_slot].timed_out
    finally:
        for agent in agents.values():
            agent.close()
    end = datetime.datetime.now()

    scores = game.game_state.scores
    if n_agents == 0:
        metric = scores.get(grading_slot, 0)
    else:
        # Ties resolve in favor of the graded
        # agent (it shares the best reachable position).
        graded_score = scores.get(grading_slot, 0)
        metric = -1
        for slot in range(total_players):
            if scores.get(slot, 0) <= graded_score:
                metric += 1

    return RunResult(
        agent_to_grade=agent_to_grade,
        map_name=map_name,
        staff_agent_count=n_agents,
        seed=seed,
        score=metric,
        run_time_seconds=(end - start).total_seconds(),
        timed_out=timed_out,
    )


def _agent_worker(
    base: str,
    file: str,
    room_state: RoomState,
    slot: Slot,
    conn: Connection,
    loggers: dict[str, str],
) -> None:
    """Child-process entry point: build the agent once, then serve get_move
    requests over the pipe until the parent closes it (or kills us)."""
    # Wire this fresh process up to the grading log so the agent's own log
    # output is captured (with timestamps) instead of leaking to the console.
    _configure_logging(loggers)
    agent = None
    init_error: str | None = None
    try:
        module = _load_agent_module(base, file)
        agent = module.Agent(room_state, slot)
    except Exception:
        init_error = traceback.format_exc()

    # Signal readiness so the parent can pay interpreter-startup and agent
    # construction cost up front, keeping it out of the per-move timeout.
    conn.send(("ready", None))

    while True:
        try:
            game_state = conn.recv()
        except EOFError:
            return
        if init_error is not None:
            conn.send(("error", init_error))
            continue
        assert agent is not None
        try:
            conn.send(("move", agent.get_move(game_state)))
        except Exception:
            conn.send(("error", traceback.format_exc()))


class AgentProcess:
    """Runs a single agent in its own subprocess so a get_move that never
    returns can be hard-killed. The first time the agent fails to answer in
    time (or its process dies) we terminate it and mark it timed-out: every
    subsequent get_move short-circuits to an empty Move without touching the
    process. Agent exceptions come back over the pipe and are recoverable —
    they don't disqualify the agent. The agent only ever sees a pickled copy
    of the game state."""

    # How long to wait for a freshly spawned child to build its agent.
    _STARTUP_TIMEOUT = 30.0

    def __init__(
        self,
        base: str,
        file: str,
        room_state: RoomState,
        slot: Slot,
        teamname: str,
        loggers: dict[str, str],
    ) -> None:
        self.slot = slot
        self.teamname = teamname
        self.timed_out = False
        # Use a fresh context so we don't depend on the pool's start method.
        self._ctx = mp.get_context("spawn")
        parent_conn, child_conn = self._ctx.Pipe()
        self._proc: BaseProcess | None = self._ctx.Process(
            target=_agent_worker,
            args=(base, file, room_state, slot, child_conn, loggers),
            daemon=True,
        )
        self._conn: Connection | None = parent_conn
        self._proc.start()
        # Only the child needs its end; closing ours here lets recv raise
        # EOFError promptly if the child dies.
        child_conn.close()

        # Block until the agent is constructed so interpreter startup and
        # agent setup don't eat into the per-move timeout on the first tick.
        try:
            if parent_conn.poll(self._STARTUP_TIMEOUT):
                parent_conn.recv()  # ("ready", None)
            else:
                logger.warning(
                    f"slot {slot} ({teamname}) failed to start within "
                    f"{self._STARTUP_TIMEOUT}s"
                )
                self._kill()
        except EOFError, OSError:
            logger.warning(f"slot {slot} ({teamname}) died during startup")
            self._kill()

    def get_move(self, game_state: GameState, timeout_seconds: float) -> Move:
        # Once an agent has timed out (or its process is gone) it forfeits all
        # remaining moves; never spend time talking to a dead/runaway process.
        if self.timed_out or self._conn is None:
            return Move()
        try:
            self._conn.send(game_state)
            if not self._conn.poll(timeout_seconds):
                logger.warning(
                    f"slot {self.slot} ({self.teamname}) timed out on tick "
                    f"{game_state.tick}; forfeiting remaining moves"
                )
                self._kill()
                return Move()
            kind, payload = self._conn.recv()
        except EOFError, OSError:
            logger.warning(
                f"slot {self.slot} ({self.teamname}) process died on tick "
                f"{game_state.tick}; forfeiting remaining moves"
            )
            self._kill()
            return Move()

        if kind == "error":
            # The agent raised but its process is healthy; log and let it keep
            # playing (this tick is a no-op).
            logger.warning(f"slot {self.slot} ({self.teamname}) raised:\n{payload}")
            return Move()
        return payload

    def _kill(self) -> None:
        """Terminate the child and mark the agent as timed-out."""
        self.timed_out = True
        self.close()

    def close(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.join(timeout=1)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join()
            self._proc = None
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# Set by _worker_init in each pool worker so _run can forward the level map
# into the agent subprocesses it spawns.
_loggers: dict[str, str] = {}


def _configure_logging(loggers: dict[str, str]) -> None:
    # Spawn-based child processes don't inherit the parent's root logger
    # configuration, so every process that emits log records (pool workers and
    # the agent subprocesses they spawn) must reapply it here. Without this,
    # agent log lines escape to stderr via logging.lastResort, unformatted.
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("results/grading.log", mode="a")],
    )
    for logger_name, level in loggers.items():
        logging.getLogger(logger_name).setLevel(level)


def _worker_init(loggers: dict[str, str]) -> None:
    global _loggers
    _loggers = loggers
    _configure_logging(loggers)


def run_one(
    config: GradingConfig, seed: int, n_agents: int, map_name: str, agent_to_grade: str
) -> RunResult:
    """Entry point invoked by ProcessPoolExecutor workers."""
    return _run(config, seed, n_agents, map_name, agent_to_grade)


class Grade:
    def __init__(self, config: GradingConfig, loggers: dict[str, str]) -> None:
        self.config = config
        self.loggers = loggers

    def run(self) -> None:
        output_path = Path(self.config.output_file)
        new_file = not output_path.exists()

        with output_path.open("a", newline="") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(
                    [
                        "timestamp",
                        "room_seed",
                        "agent_to_grade",
                        "map_name",
                        "staff_agents",
                        "score",
                        "run_time_seconds",
                        "timed_out",
                    ]
                )
                f.flush()

            rng = random.Random(self.config.seed)
            n = len(self.config.agents_to_grade)
            n = n * len(self.config.maps)
            n = n * self.config.iterations
            n = n * (self.config.max_staff_agents - self.config.min_staff_agents + 1)
            logger.info(f"Grading {n} runs")

            with ProcessPoolExecutor(
                initializer=_worker_init, initargs=(self.loggers,)
            ) as pool:
                futures: list[Future[RunResult]] = []
                for _ in range(self.config.iterations):
                    for n_agents in range(
                        self.config.min_staff_agents, self.config.max_staff_agents + 1
                    ):
                        for map_name in sorted(self.config.maps.keys()):
                            seed = rng.randint(1, 999999)
                            for agent_to_grade in self.config.agents_to_grade.keys():
                                futures.append(
                                    pool.submit(
                                        run_one,
                                        self.config,
                                        seed,
                                        n_agents,
                                        map_name,
                                        agent_to_grade,
                                    )
                                )
                for future in tqdm.tqdm(
                    as_completed(futures),
                    total=len(futures),
                ):
                    result = future.result()
                    timestamp = math.floor(datetime.datetime.now().timestamp())
                    writer.writerow(
                        [
                            timestamp,
                            result.seed,
                            result.agent_to_grade,
                            result.map_name,
                            result.staff_agent_count,
                            result.score,
                            result.run_time_seconds,
                            result.timed_out,
                        ]
                    )
                    f.flush()
