import asyncio
import csv
import datetime
import importlib
import logging
import math
import random
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path
import tqdm

from pydantic import BaseModel

from common.base_agent import BaseAgent
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


# TODO(alok): copy-pasta
def _load_agent_module(base: str, agent_file: str):
    return importlib.import_module(f"{base}.{agent_file.removesuffix('.py')}")


async def _run_async(
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
    agents: dict[Slot, BaseAgent] = {}
    for slot, (base, file) in slot_to_module_name.items():
        module = _load_agent_module(base, file)
        agents[slot] = module.Agent(room_state.model_copy(deep=True), slot)

    game = Game(rng, room_state, 1)

    start = datetime.datetime.now()
    while True:
        slot = game.tick()
        if slot is None:
            break
        if not game.bus_is_alive(slot):
            continue
        agent = agents[slot]
        move = await _get_move(agent, game.game_state, config.agent_timeout_seconds)
        game.move(slot, move)
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
    )


async def _get_move(
    agent: BaseAgent, game_state: GameState, timeout_seconds: float
) -> Move:
    # The agent is given a deep copy of GameState so that mutations inside
    # get_move can't corrupt the authoritative state held by the Game.
    game_state_copy = game_state.model_copy(deep=True)
    move = Move()

    # TODO(alok): it would be nice to disable the gc, but I'm not too
    # sure about disabling the gc.disable() before awaiting.
    # It's likely to be ok, but we can disable() the gc if it becomes
    # an issue.
    # gc.disable()
    try:
        move = await asyncio.wait_for(
            agent.async_get_move(game_state_copy), timeout_seconds
        )
    except TimeoutError:
        logger.warning(f"slot {agent.slot} timed out on tick {game_state.tick}")
    except Exception as e:
        logger.warning(f"slot {agent.slot} raised: {e}")
    # gc.enable()
    return move


def _worker_init(loggers: dict[str, str]) -> None:
    # With spawn-based pools the worker does not inherit the parent's root
    # logger configuration, so we reapply the same format here. Without this
    # agent log lines come out unformatted (no timestamp, no level).
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    for logger_name, level in loggers.items():
        log = logging.getLogger(logger_name)
        log.setLevel(level)


def run_one(
    config: GradingConfig, seed: int, n_agents: int, map_name: str, agent_to_grade: str
) -> RunResult:
    """Entry point invoked by ProcessPoolExecutor workers."""
    return asyncio.run(_run_async(config, seed, n_agents, map_name, agent_to_grade))


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
                        ]
                    )
                    f.flush()
