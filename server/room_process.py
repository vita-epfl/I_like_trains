"""
Room Process Module - Runs rooms in separate processes to bypass Python GIL

This module provides a multiprocessing wrapper for Room objects, allowing
each room to run in its own process for better CPU utilization with many clients.
"""

import logging
import multiprocessing as mp
import socket
import json
import time
import queue
import zlib
import base64
from typing import Dict, Any, Optional

# Compression threshold in bytes - messages larger than this will be compressed
COMPRESSION_THRESHOLD = 1024  # 1KB

logger = logging.getLogger(__name__)


class RoomProcessManager:
    """
    Manages room processes for the server.
    
    Each room runs in a separate process, communicating with the main
    server process via queues. This bypasses the Python GIL, allowing
    true parallelism for CPU-bound game logic.
    """
    
    def __init__(self, server_socket: socket.socket, config):
        self.server_socket = server_socket
        self.config = config
        self.room_processes: Dict[str, 'RoomProcessHandle'] = {}
        self.running = True
        
        # Queue for receiving messages from room processes
        self.outbound_queue = mp.Queue()
        
        # Start the outbound message handler thread
        import threading
        self.outbound_thread = threading.Thread(target=self._handle_outbound_messages, daemon=True)
        self.outbound_thread.start()
        
        logger.info("RoomProcessManager initialized")
    
    def create_room_process(
        self,
        room_id: str,
        nb_players_max: int,
        bot_seed: Optional[int] = None,
        grading_mode: bool = False,
        **kwargs
    ) -> 'RoomProcessHandle':
        """Create a new room process"""
        
        # Create queues for communication
        inbound_queue = mp.Queue()  # Messages TO the room
        
        # Create the process
        process = mp.Process(
            target=_room_process_entry,
            args=(
                room_id,
                nb_players_max,
                self.config,
                inbound_queue,
                self.outbound_queue,
                bot_seed,
                grading_mode,
            ),
            daemon=True
        )
        
        handle = RoomProcessHandle(
            room_id=room_id,
            process=process,
            inbound_queue=inbound_queue,
            nb_players_max=nb_players_max,
        )
        
        self.room_processes[room_id] = handle
        process.start()
        
        logger.info(f"Started room process {room_id} (PID: {process.pid})")
        return handle
    
    def send_to_room(self, room_id: str, message: Dict[str, Any], client_addr: tuple):
        """Send a message to a specific room process"""
        if room_id not in self.room_processes:
            logger.warning(f"Room {room_id} not found")
            return False
        
        handle = self.room_processes[room_id]
        try:
            handle.inbound_queue.put_nowait({
                'type': 'client_message',
                'addr': client_addr,
                'message': message,
            })
            return True
        except queue.Full:
            logger.warning(f"Inbound queue full for room {room_id}")
            return False
    
    def add_client_to_room(self, room_id: str, client_addr: tuple, nickname: str, game_mode: str):
        """Notify room process of a new client"""
        if room_id not in self.room_processes:
            return False
        
        handle = self.room_processes[room_id]
        handle.inbound_queue.put({
            'type': 'add_client',
            'addr': client_addr,
            'nickname': nickname,
            'game_mode': game_mode,
        })
        handle.client_count += 1
        handle.clients[client_addr] = nickname  # Track for ping mechanism
        return True
    
    def remove_client_from_room(self, room_id: str, client_addr: tuple):
        """Notify room process of client disconnection"""
        if room_id not in self.room_processes:
            return False
        
        handle = self.room_processes[room_id]
        handle.inbound_queue.put({
            'type': 'remove_client',
            'addr': client_addr,
        })
        handle.client_count = max(0, handle.client_count - 1)
        if client_addr in handle.clients:
            del handle.clients[client_addr]
        return True
    
    def get_available_room(self) -> Optional['RoomProcessHandle']:
        """Find a room with space or return None"""
        for handle in self.room_processes.values():
            if handle.client_count < handle.nb_players_max and not handle.game_started:
                return handle
        return None
    
    def remove_room(self, room_id: str):
        """Stop and remove a room process"""
        if room_id not in self.room_processes:
            return
        
        handle = self.room_processes[room_id]
        
        # Send shutdown signal
        try:
            handle.inbound_queue.put({'type': 'shutdown'}, timeout=1)
        except Exception:
            pass
        
        # Wait for process to finish
        handle.process.join(timeout=2)
        
        if handle.process.is_alive():
            logger.warning(f"Force terminating room process {room_id}")
            handle.process.terminate()
        
        del self.room_processes[room_id]
        logger.info(f"Removed room process {room_id}")
    
    def _handle_outbound_messages(self):
        """Thread that sends messages from room processes to clients"""
        while self.running:
            try:
                msg = self.outbound_queue.get(timeout=0.1)
                
                if msg['type'] == 'send_to_client':
                    addr = tuple(msg['addr'])  # Convert list back to tuple
                    data = msg['data']
                    try:
                        self.server_socket.sendto(data.encode(), addr)
                    except Exception as e:
                        logger.debug(f"Error sending to client {addr}: {e}")
                
                elif msg['type'] == 'room_closed':
                    room_id = msg['room_id']
                    if room_id in self.room_processes:
                        del self.room_processes[room_id]
                        logger.info(f"Room {room_id} closed")
                
                elif msg['type'] == 'game_started':
                    room_id = msg['room_id']
                    if room_id in self.room_processes:
                        self.room_processes[room_id].game_started = True
                        
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in outbound handler: {e}")
    
    def shutdown(self):
        """Shutdown all room processes"""
        self.running = False
        
        for room_id in list(self.room_processes.keys()):
            self.remove_room(room_id)
        
        logger.info("RoomProcessManager shutdown complete")


class RoomProcessHandle:
    """Handle for tracking a room process from the main server"""
    
    def __init__(
        self,
        room_id: str,
        process: mp.Process,
        inbound_queue: mp.Queue,
        nb_players_max: int,
    ):
        self.room_id = room_id
        self.process = process
        self.inbound_queue = inbound_queue
        self.nb_players_max = nb_players_max
        self.client_count = 0
        self.game_started = False
        self.first_client_join_time: Optional[float] = None
        self.clients: Dict[tuple, str] = {}  # Track clients for ping mechanism


def _room_process_entry(
    room_id: str,
    nb_players_max: int,
    config,
    inbound_queue: mp.Queue,
    outbound_queue: mp.Queue,
    bot_seed: Optional[int],
    grading_mode: bool,
):
    """Entry point for room process - runs in a separate process"""
    
    # Set up logging for this process
    import logging
    logging.basicConfig(
        level=logging.DEBUG if not grading_mode else logging.INFO,
        format=f'%(asctime)s - room_{room_id} - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(f'room_{room_id}')
    
    logger.info(f"Room process {room_id} started (PID: {mp.current_process().pid})")
    
    try:
        runner = RoomProcessRunner(
            room_id=room_id,
            nb_players_max=nb_players_max,
            config=config,
            inbound_queue=inbound_queue,
            outbound_queue=outbound_queue,
            bot_seed=bot_seed,
            grading_mode=grading_mode,
            logger=logger,
        )
        runner.run()
    except Exception as e:
        logger.error(f"Room process {room_id} crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        outbound_queue.put({
            'type': 'room_closed',
            'room_id': room_id,
        })
        logger.info(f"Room process {room_id} exiting")


class RoomProcessRunner:
    """
    Runs the game loop for a single room in its own process.
    
    This is a simplified version of Room that handles the game logic
    and communicates with the main server process via queues.
    """
    
    def __init__(
        self,
        room_id: str,
        nb_players_max: int,
        config,
        inbound_queue: mp.Queue,
        outbound_queue: mp.Queue,
        bot_seed: Optional[int],
        grading_mode: bool,
        logger,
    ):
        self.room_id = room_id
        self.nb_players_max = nb_players_max
        self.config = config
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self.bot_seed = bot_seed
        self.grading_mode = grading_mode
        self.logger = logger
        
        self.clients: Dict[tuple, str] = {}  # addr -> nickname
        self.client_game_modes: Dict[tuple, str] = {}
        self.running = True
        self.game_started = False
        self.game_over = False
        self.first_client_join_time: Optional[float] = None
        self.room_creation_time = time.time()
        
        # Import game components here to avoid issues with multiprocessing
        from server.game import Game
        import random
        
        self.random = random.Random(bot_seed)
        self.game = Game(
            config,
            self._send_cooldown_notification,
            nb_players_max,
            room_id,
            bot_seed,
            self.random,
        )
        
        self.ai_clients = {}
        self.used_ai_names = set()
        self.used_nicknames = set()
        
        self.logger.info(f"RoomProcessRunner initialized for room {room_id}")
    
    def _send_to_client(self, addr: tuple, data: str, compress: bool = True):
        """Send data to a client via the outbound queue.
        
        Args:
            addr: Client address tuple
            data: JSON string data to send
            compress: If True, compress large messages (> COMPRESSION_THRESHOLD)
        """
        # Optionally compress large messages
        if compress and len(data) > COMPRESSION_THRESHOLD:
            try:
                compressed = zlib.compress(data.encode(), level=6)
                # Only use compression if it actually reduces size
                if len(compressed) < len(data) * 0.8:  # At least 20% reduction
                    # Wrap compressed data with marker
                    compressed_b64 = base64.b64encode(compressed).decode()
                    data = json.dumps({"_compressed": True, "data": compressed_b64}) + "\n"
            except Exception as e:
                self.logger.debug(f"Compression failed, sending uncompressed: {e}")
        
        self.outbound_queue.put({
            'type': 'send_to_client',
            'addr': list(addr),  # Convert tuple to list for JSON serialization
            'data': data,
        })
    
    def _send_cooldown_notification(self, nickname: str, cooldown: int, death_reason: str):
        """Send death/cooldown notification to a client"""
        for addr, name in self.clients.items():
            if name == nickname:
                response = {"type": "death", "remaining": cooldown, "reason": death_reason}
                self._send_to_client(addr, json.dumps(response) + "\n")
                return
    
    def run(self):
        """Main loop for the room process"""
        self.logger.info("Starting room process main loop")
        
        # Wait for clients and handle the waiting room phase
        last_broadcast = time.time()
        broadcast_interval = 0.5  # Send waiting room updates every 0.5s
        
        while self.running and not self.game_started:
            self._process_messages(timeout=0.1)
            
            # Broadcast waiting room status periodically
            if time.time() - last_broadcast >= broadcast_interval:
                self._check_waiting_room()
                last_broadcast = time.time()
            
            time.sleep(0.05)  # Small sleep to avoid busy-waiting
        
        # Run the game if it started
        if self.game_started and self.running:
            self._run_game()
        
        self.logger.info("Room process main loop finished")
    
    def _process_messages(self, timeout: float = 0.01):
        """Process incoming messages from the main server"""
        try:
            msg = self.inbound_queue.get(timeout=timeout)
            
            if msg['type'] == 'shutdown':
                self.running = False
                
            elif msg['type'] == 'add_client':
                addr = tuple(msg['addr'])
                nickname = msg['nickname']
                game_mode = msg['game_mode']
                
                self.clients[addr] = nickname
                self.client_game_modes[addr] = game_mode
                self.used_nicknames.add(nickname)
                
                if self.first_client_join_time is None:
                    self.first_client_join_time = time.time()
                
                self.logger.info(f"Client {nickname} joined room")
                
            elif msg['type'] == 'remove_client':
                addr = tuple(msg['addr'])
                if addr in self.clients:
                    nickname = self.clients[addr]
                    del self.clients[addr]
                    if addr in self.client_game_modes:
                        del self.client_game_modes[addr]
                    self.logger.info(f"Client {nickname} left room")
                    
                    # If no clients left, stop the room
                    if not self._has_human_clients():
                        self.running = False
                        
            elif msg['type'] == 'client_message':
                addr = tuple(msg['addr'])
                message = msg['message']
                self._handle_client_message(addr, message)
                
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    def _has_human_clients(self) -> bool:
        """Check if there are any human clients"""
        for addr in self.clients:
            if not (isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI"):
                return True
        return False
    
    def _check_waiting_room(self):
        """Check if it's time to start the game"""
        if self.game_started:
            return
        
        # Check if room is full
        if len(self.clients) >= self.nb_players_max:
            self.logger.info("Room is full, starting game")
            self._start_game()
            return
        
        # Check if waiting time expired
        if self.first_client_join_time:
            elapsed = time.time() - self.first_client_join_time
            if elapsed >= self.config.waiting_time_before_bots_seconds:
                self.logger.info("Waiting time expired, starting game with bots")
                self._start_game()
                return
        
        # Broadcast waiting room status
        self._broadcast_waiting_room()
    
    def _broadcast_waiting_room(self):
        """Send waiting room status to all clients"""
        remaining_time = 0
        if self.first_client_join_time:
            elapsed = time.time() - self.first_client_join_time
            remaining_time = max(0, int(self.config.waiting_time_before_bots_seconds - elapsed))
        
        data = {
            "type": "waiting_room",
            "data": {
                "room_id": self.room_id,
                "players": list(self.clients.values()),
                "nb_players": self.nb_players_max,
                "game_started": self.game_started,
                "waiting_time": remaining_time,
            },
        }
        
        msg = json.dumps(data) + "\n"
        for addr in self.clients:
            if not (isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI"):
                self._send_to_client(addr, msg)
    
    def _start_game(self):
        """Start the game"""
        self.game_started = True
        self.game.game_started = True
        self.game.start_time = time.time()
        
        # Notify main server that game has started
        self.outbound_queue.put({
            'type': 'game_started',
            'room_id': self.room_id,
        })
        
        # Send game_started_success to all clients
        response = {"type": "game_started_success"}
        msg = json.dumps(response) + "\n"
        for addr in list(self.clients.keys()):
            if not (isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI"):
                self._send_to_client(addr, msg)
        
        # Add trains for all players
        self._add_all_trains()
        
        # Fill with bots if needed
        current_players = len(self.clients)
        bots_needed = self.nb_players_max - current_players
        if bots_needed > 0:
            self._fill_with_bots(bots_needed)
        
        self.logger.info(f"Game started with {len(self.clients)} players")
    
    def _add_all_trains(self):
        """Add trains for all human players"""
        for addr, nickname in list(self.clients.items()):
            if self.game.add_train(nickname):
                response = {"type": "spawn_success", "nickname": nickname}
                self._send_to_client(addr, json.dumps(response) + "\n")
            else:
                self.logger.warning(f"Failed to spawn train for {nickname}")
    
    def _fill_with_bots(self, nb_bots: int):
        """Fill room with AI bots"""
        if not hasattr(self.config, 'agents') or not self.config.agents:
            self.logger.warning("No agents configured")
            return
        
        from server.ai_client import AIClient
        
        agents = self.config.agents[:]
        self.random.shuffle(agents)
        while len(agents) < nb_bots:
            agents.append(self.random.choice(self.config.agents))
        agents = agents[:nb_bots]
        
        for agent in agents:
            ai_nickname = self._get_available_ai_name(agent)
            
            if self.game.add_train(ai_nickname):
                # Create a minimal room-like object for AIClient
                ai_client = AIClient(
                    room=self,
                    nickname=ai_nickname,
                    ai_agent_file_name=agent.agent_file_name,
                    agent_dir="common.agents",
                )
                self.ai_clients[ai_nickname] = ai_client
                self.game.ai_clients[ai_nickname] = ai_client
                
                # Add to clients dict with AI marker
                ai_addr = ("AI", ai_nickname)
                self.clients[ai_addr] = ai_nickname
                
                self.logger.debug(f"Added bot {ai_nickname}")
    
    def _get_available_ai_name(self, agent) -> str:
        """Get an available AI name"""
        from server.room import AI_NAMES
        import random
        
        ai_nickname = agent.nickname if agent.nickname else None
        
        if not ai_nickname:
            for name in AI_NAMES:
                if name not in self.used_ai_names:
                    self.used_ai_names.add(name)
                    return name
            ai_nickname = f"Bot_{random.randint(1000, 9999)}"
        
        while ai_nickname in self.used_nicknames:
            ai_nickname = f"{ai_nickname}_{random.randint(1, 999)}"
        
        self.used_ai_names.add(ai_nickname)
        self.used_nicknames.add(ai_nickname)
        return ai_nickname
    
    def _handle_client_message(self, addr: tuple, message: dict):
        """Handle a message from a client"""
        nickname = self.clients.get(addr)
        if not nickname:
            return
        
        action = message.get('action')
        
        if action == 'direction':
            if nickname in self.game.trains and self.game.contains_train(nickname):
                self.game.trains[nickname].change_direction(message['direction'])
                
        elif action == 'respawn':
            if self.game_over:
                response = {"type": "respawn_failed", "message": "Game is over"}
                self._send_to_client(addr, json.dumps(response) + "\n")
                return
            
            cooldown = self.game.get_train_respawn_cooldown(nickname)
            if cooldown > 0:
                response = {"type": "death", "remaining": cooldown}
                self._send_to_client(addr, json.dumps(response) + "\n")
                return
            
            if self.game.add_train(nickname):
                response = {"type": "spawn_success", "nickname": nickname}
                self._send_to_client(addr, json.dumps(response) + "\n")
                
        elif action == 'drop_wagon':
            if nickname in self.game.trains and self.game.contains_train(nickname):
                from server.passenger import Passenger
                from common.constants import BOOST_COOLDOWN_DURATION
                
                last_wagon_position = self.game.trains[nickname].drop_wagon()
                if last_wagon_position:
                    new_passenger = Passenger(self.game)
                    new_passenger.position = last_wagon_position
                    new_passenger.value = 1
                    self.game.passengers.append(new_passenger)
                    self.game._dirty["passengers"] = True
                    
                    response = {
                        "type": "drop_wagon_success",
                        "cooldown": BOOST_COOLDOWN_DURATION
                    }
                    self._send_to_client(addr, json.dumps(response) + "\n")
    
    def _run_game(self):
        """Run the game loop"""
        from common.constants import REFERENCE_TICK_RATE
        
        reference_tickrate = REFERENCE_TICK_RATE
        total_updates = int(self.config.game_duration_seconds * reference_tickrate)
        game_seconds_per_tick = 1.0 / reference_tickrate
        real_seconds_per_tick = 1.0 / self.config.tick_rate
        
        game_start_time = time.time()
        game_time_elapsed = 0.0
        
        self.logger.info(f"Starting game loop: {total_updates} ticks, {real_seconds_per_tick*1000:.2f}ms/tick")
        
        for update_count in range(total_updates):
            if not self.running or self.game_over:
                break
            
            # Process any pending messages (non-blocking)
            self._process_messages(timeout=0)
            
            # Update game state
            self.game.current_tick = update_count + 1
            game_time_elapsed += game_seconds_per_tick
            
            self.game.update()
            
            # Get dirty state and broadcast
            state = self.game.get_dirty_state()
            if state:
                remaining_time = self.config.game_duration_seconds - game_time_elapsed
                if self.game.last_remaining_time is None or round(remaining_time) != round(self.game.last_remaining_time):
                    state["remaining_time"] = round(remaining_time)
                    self.game.last_remaining_time = remaining_time
                
                state_data = {"type": "state", "data": state}
                
                # Update AI clients
                for ai_client in self.ai_clients.values():
                    ai_client.update_state(state_data)
                
                # Send to human clients
                state_json = json.dumps(state_data) + "\n"
                for addr in list(self.clients.keys()):
                    if not (isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI"):
                        self._send_to_client(addr, state_json)
            
            # Sleep to maintain tick rate (skip in grading mode)
            if not self.grading_mode and real_seconds_per_tick > 0:
                elapsed = time.time() - game_start_time
                target_time = (update_count + 1) * real_seconds_per_tick
                sleep_time = max(0, target_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        # Game finished
        total_real_time = time.time() - game_start_time
        self.logger.info(f"Game completed: {update_count + 1} ticks in {total_real_time:.2f}s")
        
        self._end_game()
    
    def _end_game(self):
        """End the game and send final scores"""
        if self.game_over:
            return
        
        self.game_over = True
        self.running = False
        
        # Collect and send final scores
        final_scores = []
        for nickname, score in self.game.best_scores.items():
            final_scores.append({"name": nickname, "best_score": score})
        
        final_scores.sort(key=lambda x: x['best_score'], reverse=True)
        
        response = {"type": "game_over", "scores": final_scores}
        msg = json.dumps(response) + "\n"
        
        for addr in list(self.clients.keys()):
            if not (isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI"):
                self._send_to_client(addr, msg)
        
        self.logger.info(f"Game over. Final scores: {final_scores}")
