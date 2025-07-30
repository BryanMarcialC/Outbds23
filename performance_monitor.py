"""
Performance Monitoring and Profiling System
Provides comprehensive performance tracking, profiling, and system monitoring
"""
import time
import json
import logging
import functools
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    
try:
    import memory_profiler
    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False

from performance_config import config

@dataclass
class FunctionStats:
    """Statistics for a function"""
    name: str
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    success_count: int = 0
    error_count: int = 0
    memory_usage_mb: float = 0.0
    last_called: Optional[datetime] = None

@dataclass
class SystemStats:
    """System resource statistics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_threads: int

class PerformanceMonitor:
    """Comprehensive performance monitoring system"""
    
    def __init__(self):
        self.function_stats: Dict[str, FunctionStats] = {}
        self.system_stats: deque = deque(maxlen=100)  # Keep last 100 system snapshots
        self.slow_functions: List[tuple] = []  # (function_name, execution_time)
        self.logger = logging.getLogger(__name__)
        self._last_system_check = time.time()
        
    def profile_function(self, func_name: str, execution_time: float, 
                        success: bool = True, memory_usage: float = 0.0):
        """Record function execution statistics"""
        if func_name not in self.function_stats:
            self.function_stats[func_name] = FunctionStats(name=func_name)
        
        stats = self.function_stats[func_name]
        stats.call_count += 1
        stats.total_time += execution_time
        stats.avg_time = stats.total_time / stats.call_count
        stats.min_time = min(stats.min_time, execution_time)
        stats.max_time = max(stats.max_time, execution_time)
        stats.last_called = datetime.now()
        
        if success:
            stats.success_count += 1
        else:
            stats.error_count += 1
            
        if memory_usage > 0:
            stats.memory_usage_mb = memory_usage
        
        # Track slow functions
        if execution_time > config.SLOW_FUNCTION_THRESHOLD:
            self.slow_functions.append((func_name, execution_time, datetime.now()))
            # Keep only last 50 slow function calls
            if len(self.slow_functions) > 50:
                self.slow_functions = self.slow_functions[-50:]
    
    def record_system_stats(self):
        """Record current system resource usage"""
        if not PSUTIL_AVAILABLE or not config.MONITOR_SYSTEM_RESOURCES:
            return
            
        current_time = time.time()
        if current_time - self._last_system_check < config.RESOURCE_CHECK_INTERVAL:
            return
            
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            stats = SystemStats(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                active_threads=len(psutil.Process().threads())
            )
            
            self.system_stats.append(stats)
            self._last_system_check = current_time
            
        except Exception as e:
            self.logger.warning(f"Failed to collect system stats: {e}")
    
    def get_function_stats(self, sort_by: str = 'total_time') -> List[Dict[str, Any]]:
        """Get function statistics sorted by specified metric"""
        stats_list = [asdict(stats) for stats in self.function_stats.values()]
        
        # Convert datetime to string for JSON serialization
        for stats in stats_list:
            if stats['last_called']:
                stats['last_called'] = stats['last_called'].isoformat()
        
        return sorted(stats_list, key=lambda x: x.get(sort_by, 0), reverse=True)
    
    def get_slow_functions(self, threshold_seconds: Optional[float] = None) -> List[Dict[str, Any]]:
        """Get functions that exceeded the slow threshold"""
        threshold = threshold_seconds or config.SLOW_FUNCTION_THRESHOLD
        
        slow_funcs = [
            {
                'function_name': name,
                'execution_time': exec_time,
                'timestamp': timestamp.isoformat()
            }
            for name, exec_time, timestamp in self.slow_functions
            if exec_time > threshold
        ]
        
        return sorted(slow_funcs, key=lambda x: x['execution_time'], reverse=True)
    
    def get_system_stats_summary(self) -> Dict[str, Any]:
        """Get summary of system resource usage"""
        if not self.system_stats:
            return {}
        
        recent_stats = list(self.system_stats)[-10:]  # Last 10 measurements
        
        return {
            'avg_cpu_percent': sum(s.cpu_percent for s in recent_stats) / len(recent_stats),
            'avg_memory_percent': sum(s.memory_percent for s in recent_stats) / len(recent_stats),
            'avg_memory_used_mb': sum(s.memory_used_mb for s in recent_stats) / len(recent_stats),
            'max_cpu_percent': max(s.cpu_percent for s in recent_stats),
            'max_memory_percent': max(s.memory_percent for s in recent_stats),
            'current_active_threads': recent_stats[-1].active_threads if recent_stats else 0,
            'measurement_count': len(recent_stats),
            'time_range_minutes': (recent_stats[-1].timestamp - recent_stats[0].timestamp).total_seconds() / 60 if len(recent_stats) > 1 else 0
        }
    
    def export_metrics(self, filename: str):
        """Export all performance metrics to JSON file"""
        metrics = {
            'export_timestamp': datetime.now().isoformat(),
            'function_stats': self.get_function_stats(),
            'slow_functions': self.get_slow_functions(),
            'system_stats_summary': self.get_system_stats_summary(),
            'configuration': {
                'slow_function_threshold': config.SLOW_FUNCTION_THRESHOLD,
                'api_cache_size': config.API_CACHE_SIZE,
                'max_workers': config.MAX_WORKERS,
                'profiling_enabled': config.ENABLE_PROFILING
            }
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Performance metrics exported to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
    
    def log_performance_summary(self):
        """Log a summary of performance metrics"""
        if not self.function_stats:
            self.logger.info("No performance data available")
            return
        
        # Top 5 slowest functions by total time
        top_functions = self.get_function_stats('total_time')[:5]
        
        self.logger.info("=== Performance Summary ===")
        self.logger.info(f"Total functions monitored: {len(self.function_stats)}")
        self.logger.info(f"Slow function calls detected: {len(self.slow_functions)}")
        
        self.logger.info("Top 5 functions by total execution time:")
        for i, func in enumerate(top_functions, 1):
            self.logger.info(f"  {i}. {func['name']}: {func['total_time']:.2f}s total, "
                           f"{func['call_count']} calls, {func['avg_time']:.3f}s avg")
        
        # System stats summary
        sys_summary = self.get_system_stats_summary()
        if sys_summary:
            self.logger.info(f"System - Avg CPU: {sys_summary['avg_cpu_percent']:.1f}%, "
                           f"Avg Memory: {sys_summary['avg_memory_percent']:.1f}%, "
                           f"Active Threads: {sys_summary['current_active_threads']}")
        
        self.logger.info("==========================")
    
    def reset_stats(self):
        """Reset all performance statistics"""
        self.function_stats.clear()
        self.system_stats.clear()
        self.slow_functions.clear()
        self.logger.info("Performance statistics reset")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def profile_critical(func: Callable) -> Callable:
    """Decorator to profile critical functions"""
    if not config.ENABLE_PROFILING:
        return func
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        memory_before = 0
        
        if MEMORY_PROFILER_AVAILABLE:
            try:
                memory_before = memory_profiler.memory_usage()[0]
            except:
                pass
        
        # Record system stats periodically
        performance_monitor.record_system_stats()
        
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            success = False
            raise
        finally:
            execution_time = time.time() - start_time
            memory_after = 0
            
            if MEMORY_PROFILER_AVAILABLE:
                try:
                    memory_after = memory_profiler.memory_usage()[0]
                except:
                    pass
            
            memory_usage = max(0, memory_after - memory_before)
            
            performance_monitor.profile_function(
                func.__name__,
                execution_time,
                success,
                memory_usage
            )
        
        return result
    
    return wrapper

@contextmanager
def TimeBlock(block_name: str):
    """Context manager to time code blocks"""
    start_time = time.time()
    try:
        yield
        success = True
    except Exception:
        success = False
        raise
    finally:
        execution_time = time.time() - start_time
        if config.ENABLE_PROFILING:
            performance_monitor.profile_function(
                f"block_{block_name}",
                execution_time,
                success
            )

def log_slow_query(query_name: str, execution_time: float, threshold: float = 1.0):
    """Log slow database/API queries"""
    if execution_time > threshold:
        logging.getLogger(__name__).warning(
            f"Slow query detected: {query_name} took {execution_time:.2f}s "
            f"(threshold: {threshold}s)"
        )
        
        if config.ENABLE_PROFILING:
            performance_monitor.profile_function(
                f"slow_query_{query_name}",
                execution_time,
                True
            )