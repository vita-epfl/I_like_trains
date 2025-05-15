import threading
import time
import logging
import sys
import pygame
import concurrent.futures


logger = logging.getLogger("client.agent_thread")

class AgentThread(threading.Thread):
    """Thread responsible for calling update_agent() at regular intervals"""
    
    def __init__(self, client):
        """Initialize the agent thread"""
        super().__init__(daemon=True)  # Set as daemon so it exits when the main thread exits
        self.client = client
        self.running = True
    
    def run(self):
        """Main thread loop to update the agent at appropriate intervals"""
        logger.info("Starting agent thread")
        
        while self.running:
            # Only update if the client is initialized, not dead, and has a train
            if (self.client.is_initialized and 
                not self.client.is_dead and 
                self.client.nickname in self.client.trains):
                
                # Calculate the appropriate timing based on train speed
                if len(self.client.trains) > 0 and self.client.nickname in self.client.trains:
                    # Use the same formula as in GameState.handle_state_data
                    from client.game_state import INITIAL_SPEED, SPEED_DECREMENT_COEFFICIENT
                    train_speed = INITIAL_SPEED * SPEED_DECREMENT_COEFFICIENT ** len(self.client.trains[self.client.nickname]["wagons"])
                    theoretical_time = 1.0 / train_speed
                    
                    # Check if agent is taking too long to respond
                    current_time = time.time()
                    if self.client.last_update is not None:
                        elapsed_time = round(current_time - self.client.last_update, 3)
                        max_response_time = round(theoretical_time, 3)
                        
                        if elapsed_time > max_response_time:
                            logger.warning(f"Agent has not answered in time. Update took {elapsed_time} instead of max {max_response_time}")

                        else:
                            logger.debug(f"Agent answered in time. Update took {elapsed_time} instead of max {max_response_time}")
                    
                    # Update the last update time and call update_agent with timeout monitoring
                    if hasattr(self.client, "agent") and self.client.agent is not None:
                        timeout_seconds = self.client.config.server_timeout_seconds
                        self.client.last_update = current_time
                        
                        # Run agent update in a separate thread with timeout
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            # Submit update_agent task
                            self.client.has_answered = False
                            future = executor.submit(self.client.agent.update_agent)
                            
                            try:
                                # Wait for the result with timeout
                                future.result(timeout=timeout_seconds)
                            except concurrent.futures.TimeoutError:
                                # The agent took too long to respond
                                error_msg = f"Agent too slow! Execution exceeded timeout limit of {timeout_seconds}s"
                                logger.error(error_msg)
                                self.display_error_and_exit(error_msg)
                            except Exception as e:
                                # Other errors in the agent
                                error_msg = f"Error in agent: {str(e)}"
                                logger.error(error_msg)
                                self.display_error_and_exit(error_msg)
                    
                    # Sleep for slightly less than theoretical_time to ensure we don't miss updates
                    sleep_duration = 1 / self.client.REFERENCE_TICK_RATE
                    time.sleep(sleep_duration)
                else:
                    # Default sleep if we can't calculate based on train
                    time.sleep(0.05)
            else:
                # Sleep a bit longer if conditions aren't met
                time.sleep(0.1)
    
    def stop(self):
        """Stop the thread"""
        self.running = False
        
    def display_error_and_exit(self, error_message):
        """Display an error message and exit the game"""
        logger.error(f"Forced game termination: {error_message}")
        
        self.client.network.disconnect(stop_client=True)
        
        # Stop the thread
        self.stop()
