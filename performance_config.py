"""
Performance Configuration System
Centralized configuration for all performance-related settings
"""
import os
from typing import Optional

class PerformanceConfig:
    """Centralized performance configuration with environment variable support"""
    
    # HTTP Client Settings
    HTTP_TIMEOUT: int = int(os.getenv('HTTP_TIMEOUT', '30'))
    HTTP_MAX_CONNECTIONS: int = int(os.getenv('HTTP_MAX_CONNECTIONS', '20'))
    HTTP_MAX_CONNECTIONS_PER_HOST: int = int(os.getenv('HTTP_MAX_CONNECTIONS_PER_HOST', '10'))
    HTTP_DNS_CACHE_TTL: int = int(os.getenv('HTTP_DNS_CACHE_TTL', '300'))  # 5 minutes
    HTTP_KEEP_ALIVE: bool = os.getenv('HTTP_KEEP_ALIVE', 'true').lower() == 'true'
    
    # Caching Settings
    API_CACHE_SIZE: int = int(os.getenv('API_CACHE_SIZE', '256'))
    API_CACHE_TTL_MINUTES: int = int(os.getenv('API_CACHE_TTL_MINUTES', '10'))
    STREAMLIT_CACHE_TTL_SECONDS: int = int(os.getenv('STREAMLIT_CACHE_TTL_SECONDS', '600'))
    BARCODE_CACHE_SIZE: int = int(os.getenv('BARCODE_CACHE_SIZE', '64'))
    
    # DataFrame Processing
    DATAFRAME_CHUNK_SIZE: int = int(os.getenv('DATAFRAME_CHUNK_SIZE', '500'))
    DATAFRAME_LARGE_THRESHOLD: int = int(os.getenv('DATAFRAME_LARGE_THRESHOLD', '1000'))
    OPTIMIZE_DTYPES: bool = os.getenv('OPTIMIZE_DTYPES', 'true').lower() == 'true'
    
    # Thread Pool Settings
    MAX_WORKERS_MULTIPLIER: float = float(os.getenv('MAX_WORKERS_MULTIPLIER', '1.0'))
    MIN_WORKERS: int = int(os.getenv('MIN_WORKERS', '2'))
    MAX_WORKERS: int = int(os.getenv('MAX_WORKERS', '16'))
    
    # File I/O Settings
    FILE_BUFFER_SIZE: int = int(os.getenv('FILE_BUFFER_SIZE', '8192'))  # 8KB
    
    # Performance Monitoring
    ENABLE_PROFILING: bool = os.getenv('ENABLE_PROFILING', 'true').lower() == 'true'
    SLOW_FUNCTION_THRESHOLD: float = float(os.getenv('SLOW_FUNCTION_THRESHOLD', '1.0'))
    PERFORMANCE_LOG_LEVEL: str = os.getenv('PERFORMANCE_LOG_LEVEL', 'INFO')
    
    # System Resource Monitoring
    MONITOR_SYSTEM_RESOURCES: bool = os.getenv('MONITOR_SYSTEM_RESOURCES', 'true').lower() == 'true'
    RESOURCE_CHECK_INTERVAL: int = int(os.getenv('RESOURCE_CHECK_INTERVAL', '60'))  # seconds
    
    @classmethod
    def get_optimal_workers(cls, data_size: Optional[int] = None) -> int:
        """Calculate optimal number of workers based on CPU cores and data size"""
        import os
        cpu_count = os.cpu_count() or 2
        base_workers = max(cls.MIN_WORKERS, min(int(cpu_count * cls.MAX_WORKERS_MULTIPLIER), cls.MAX_WORKERS))
        
        if data_size:
            # Adjust based on data size
            if data_size > cls.DATAFRAME_LARGE_THRESHOLD:
                return min(base_workers + 2, cls.MAX_WORKERS)
            elif data_size < 100:
                return max(cls.MIN_WORKERS, base_workers - 2)
        
        return base_workers
    
    @classmethod
    def is_large_dataset(cls, size: int) -> bool:
        """Check if dataset is considered large"""
        return size > cls.DATAFRAME_LARGE_THRESHOLD
    
    @classmethod
    def get_cache_ttl_seconds(cls) -> int:
        """Get API cache TTL in seconds"""
        return cls.API_CACHE_TTL_MINUTES * 60
    
    @classmethod
    def log_configuration(cls):
        """Log current configuration settings"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=== Performance Configuration ===")
        logger.info(f"HTTP Timeout: {cls.HTTP_TIMEOUT}s")
        logger.info(f"HTTP Max Connections: {cls.HTTP_MAX_CONNECTIONS}")
        logger.info(f"API Cache Size: {cls.API_CACHE_SIZE}")
        logger.info(f"API Cache TTL: {cls.API_CACHE_TTL_MINUTES} minutes")
        logger.info(f"DataFrame Chunk Size: {cls.DATAFRAME_CHUNK_SIZE}")
        logger.info(f"Max Workers: {cls.MAX_WORKERS}")
        logger.info(f"Profiling Enabled: {cls.ENABLE_PROFILING}")
        logger.info("================================")

# Global configuration instance
config = PerformanceConfig()