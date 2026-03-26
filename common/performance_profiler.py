import time
import logging
import threading
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import psutil


logger = logging.getLogger("performance_profiler")


class PerformanceProfiler:
    def __init__(
        self,
        enabled: bool = False,
        output_dir: str = "profiling_results",
        interval_seconds: float = 1.0,
        profile_name: str = "profile"
    ):
        self.enabled = enabled
        self.output_dir = output_dir
        self.interval_seconds = interval_seconds
        self.profile_name = profile_name
        
        self.metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.timers: Dict[str, float] = {}
        self.counters: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()
        
        self.start_time = time.time()
        self.process = psutil.Process()
        
        self.monitoring_thread: Optional[threading.Thread] = None
        self.running = False
        
        if self.enabled:
            os.makedirs(self.output_dir, exist_ok=True)
            logger.info(f"Performance profiling enabled. Output directory: {self.output_dir}")
            self.start_monitoring()
    
    def start_monitoring(self):
        if not self.enabled or self.running:
            return
        
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Performance monitoring thread started")
    
    def _monitor_loop(self):
        while self.running:
            try:
                self._collect_system_metrics()
                time.sleep(self.interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    def _collect_system_metrics(self):
        # Collect metrics OUTSIDE the lock to avoid blocking main thread
        # cpu_percent(interval=0.1) blocks for 100ms!
        try:
            timestamp = time.time() - self.start_time
            cpu_percent = self.process.cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            num_threads = self.process.num_threads()
            
            # Only hold lock briefly to append data
            with self.lock:
                self.metrics["system"].append({
                    "timestamp": timestamp,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "num_threads": num_threads
                })
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def start_timer(self, name: str):
        if not self.enabled:
            return
        self.timers[name] = time.time()
    
    def end_timer(self, name: str, category: str = "timers"):
        if not self.enabled or name not in self.timers:
            return
        
        elapsed = (time.time() - self.timers[name]) * 1000
        
        with self.lock:
            timestamp = time.time() - self.start_time
            self.metrics[category].append({
                "timestamp": timestamp,
                "name": name,
                "duration_ms": elapsed
            })
        
        del self.timers[name]
        return elapsed
    
    def record_metric(self, category: str, name: str, value: Any):
        if not self.enabled:
            return
        
        with self.lock:
            timestamp = time.time() - self.start_time
            self.metrics[category].append({
                "timestamp": timestamp,
                "name": name,
                "value": value
            })
    
    def increment_counter(self, name: str):
        if not self.enabled:
            return
        
        with self.lock:
            self.counters[name] += 1
    
    def get_counter(self, name: str) -> int:
        with self.lock:
            return self.counters.get(name, 0)
    
    def record_frame_time(self, frame_time_ms: float):
        if not self.enabled:
            return
        
        with self.lock:
            timestamp = time.time() - self.start_time
            self.metrics["frames"].append({
                "timestamp": timestamp,
                "frame_time_ms": frame_time_ms
            })
    
    def get_current_fps(self) -> float:
        """Get current FPS based on recent frame times (last 30 frames)"""
        with self.lock:
            if "frames" not in self.metrics or not self.metrics["frames"]:
                return 0.0
            
            recent_frames = self.metrics["frames"][-30:]
            if not recent_frames:
                return 0.0
            
            avg_frame_time = sum(f["frame_time_ms"] for f in recent_frames) / len(recent_frames)
            if avg_frame_time <= 0:
                return 0.0
            
            return 1000.0 / avg_frame_time
    
    def record_network_event(self, event_type: str, size_bytes: int = 0):
        if not self.enabled:
            return
        
        with self.lock:
            timestamp = time.time() - self.start_time
            self.metrics["network"].append({
                "timestamp": timestamp,
                "event_type": event_type,
                "size_bytes": size_bytes
            })
    
    def save_results(self):
        if not self.enabled:
            logger.debug(f"Profiler {self.profile_name} not enabled, skipping save")
            return
        
        logger.info(f"Saving profiling results for {self.profile_name}...")
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.profile_name}_{timestamp_str}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        logger.debug(f"Profiler output path: {filepath}")
        
        with self.lock:
            summary = self._generate_summary()
            
            output_data = {
                "profile_name": self.profile_name,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "duration_seconds": time.time() - self.start_time,
                "summary": summary,
                "counters": dict(self.counters),
                "metrics": {k: v for k, v in self.metrics.items()}
            }
        
        try:
            # Ensure directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(output_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            logger.info(f"Performance profiling results saved to: {filepath}")
            
            self._print_summary(summary)
            
            return filepath
        except Exception as e:
            logger.error(f"Error saving profiling results to {filepath}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _generate_summary(self) -> Dict[str, Any]:
        summary = {}
        
        if "frames" in self.metrics and self.metrics["frames"]:
            frame_times = [m["frame_time_ms"] for m in self.metrics["frames"]]
            summary["frames"] = {
                "count": len(frame_times),
                "avg_ms": sum(frame_times) / len(frame_times),
                "min_ms": min(frame_times),
                "max_ms": max(frame_times),
                "avg_fps": 1000 / (sum(frame_times) / len(frame_times)) if frame_times else 0
            }
        
        if "system" in self.metrics and self.metrics["system"]:
            cpu_values = [m["cpu_percent"] for m in self.metrics["system"]]
            memory_values = [m["memory_mb"] for m in self.metrics["system"]]
            thread_values = [m["num_threads"] for m in self.metrics["system"]]
            
            summary["system"] = {
                "avg_cpu_percent": sum(cpu_values) / len(cpu_values),
                "max_cpu_percent": max(cpu_values),
                "avg_memory_mb": sum(memory_values) / len(memory_values),
                "max_memory_mb": max(memory_values),
                "avg_threads": sum(thread_values) / len(thread_values),
                "max_threads": max(thread_values)
            }
        
        if "timers" in self.metrics and self.metrics["timers"]:
            timer_stats = defaultdict(list)
            for m in self.metrics["timers"]:
                timer_stats[m["name"]].append(m["duration_ms"])
            
            summary["timers"] = {}
            for name, durations in timer_stats.items():
                summary["timers"][name] = {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations)
                }
        
        if "network" in self.metrics and self.metrics["network"]:
            network_stats = defaultdict(lambda: {"count": 0, "total_bytes": 0})
            for m in self.metrics["network"]:
                event_type = m["event_type"]
                network_stats[event_type]["count"] += 1
                network_stats[event_type]["total_bytes"] += m.get("size_bytes", 0)
            
            summary["network"] = dict(network_stats)
        
        return summary
    
    def _print_summary(self, summary: Dict[str, Any]):
        logger.info("=" * 60)
        logger.info("PERFORMANCE PROFILING SUMMARY")
        logger.info("=" * 60)
        
        if "frames" in summary:
            logger.info(f"Frames: {summary['frames']['count']} total")
            logger.info(f"  Avg FPS: {summary['frames']['avg_fps']:.2f}")
            logger.info(f"  Avg frame time: {summary['frames']['avg_ms']:.2f}ms")
            logger.info(f"  Min/Max frame time: {summary['frames']['min_ms']:.2f}ms / {summary['frames']['max_ms']:.2f}ms")
        
        if "system" in summary:
            logger.info(f"System:")
            logger.info(f"  Avg CPU: {summary['system']['avg_cpu_percent']:.2f}%")
            logger.info(f"  Max CPU: {summary['system']['max_cpu_percent']:.2f}%")
            logger.info(f"  Avg Memory: {summary['system']['avg_memory_mb']:.2f}MB")
            logger.info(f"  Max Memory: {summary['system']['max_memory_mb']:.2f}MB")
            logger.info(f"  Avg Threads: {summary['system']['avg_threads']:.1f}")
        
        if "timers" in summary:
            logger.info("Timers:")
            for name, stats in summary["timers"].items():
                logger.info(f"  {name}: avg={stats['avg_ms']:.2f}ms, max={stats['max_ms']:.2f}ms, count={stats['count']}")
        
        if "network" in summary:
            logger.info("Network:")
            for event_type, stats in summary["network"].items():
                logger.info(f"  {event_type}: count={stats['count']}, total_bytes={stats['total_bytes']}")
        
        if self.counters:
            logger.info("Counters:")
            for name, count in self.counters.items():
                logger.info(f"  {name}: {count}")
        
        logger.info("=" * 60)
    
    def stop(self):
        if self.enabled:
            self.save_results()
