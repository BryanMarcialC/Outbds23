"""
Optimized Utility Functions
High-performance utilities for JSON processing, HTTP requests, caching, and DataFrame operations
"""
import time
import json
import logging
import functools
from typing import Any, Dict, List, Optional, Union, Callable
from functools import lru_cache
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Try to import orjson for faster JSON processing
try:
    import orjson
    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

# Try to import aiohttp for async HTTP requests
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from performance_config import config
from performance_monitor import performance_monitor, profile_critical, TimeBlock, log_slow_query

class FastJSON:
    """Optimized JSON processing with orjson fallback"""
    
    @staticmethod
    def dumps(obj: Any, **kwargs) -> str:
        """Fast JSON serialization with orjson fallback"""
        if ORJSON_AVAILABLE:
            try:
                # orjson returns bytes, need to decode to string
                return orjson.dumps(obj).decode('utf-8')
            except Exception:
                pass
        
        # Fallback to standard json
        return json.dumps(obj, **kwargs)
    
    @staticmethod
    def loads(s: Union[str, bytes]) -> Any:
        """Fast JSON deserialization with orjson fallback"""
        if ORJSON_AVAILABLE:
            try:
                return orjson.loads(s)
            except Exception:
                pass
        
        # Fallback to standard json
        return json.loads(s)

class OptimizedHTTPClient:
    """Enhanced HTTP client with connection pooling and performance optimizations"""
    
    def __init__(self):
        self.session = requests.Session()
        self._setup_session()
        self.logger = logging.getLogger(__name__)
    
    def _setup_session(self):
        """Configure session with optimal settings"""
        # Connection pooling configuration
        adapter = HTTPAdapter(
            pool_connections=config.HTTP_MAX_CONNECTIONS,
            pool_maxsize=config.HTTP_MAX_CONNECTIONS_PER_HOST,
            max_retries=Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Set keep-alive
        if config.HTTP_KEEP_ALIVE:
            self.session.headers.update({'Connection': 'keep-alive'})
    
    @profile_critical
    def get(self, url: str, **kwargs) -> requests.Response:
        """Optimized GET request with performance monitoring"""
        start_time = time.time()
        try:
            kwargs.setdefault('timeout', config.HTTP_TIMEOUT)
            response = self.session.get(url, **kwargs)
            execution_time = time.time() - start_time
            
            log_slow_query(f"GET_{url}", execution_time, threshold=2.0)
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"GET request failed for {url}: {e} (took {execution_time:.2f}s)")
            raise
    
    @profile_critical
    def put(self, url: str, **kwargs) -> requests.Response:
        """Optimized PUT request with performance monitoring"""
        start_time = time.time()
        try:
            kwargs.setdefault('timeout', config.HTTP_TIMEOUT)
            
            # Use optimized JSON if data is provided
            if 'json' in kwargs:
                json_data = FastJSON.dumps(kwargs['json'])
                kwargs['data'] = json_data
                kwargs['headers'] = kwargs.get('headers', {})
                kwargs['headers']['Content-Type'] = 'application/json'
                del kwargs['json']
            
            response = self.session.put(url, **kwargs)
            execution_time = time.time() - start_time
            
            log_slow_query(f"PUT_{url}", execution_time, threshold=2.0)
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"PUT request failed for {url}: {e} (took {execution_time:.2f}s)")
            raise
    
    def close(self):
        """Close the session"""
        self.session.close()

class TTLCache:
    """Time-based LRU cache with automatic expiration"""
    
    def __init__(self, maxsize: int = 128, ttl_seconds: int = 600):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.timestamps = {}
        self.access_order = []
        self.logger = logging.getLogger(__name__)
    
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired"""
        if key not in self.timestamps:
            return True
        return time.time() - self.timestamps[key] > self.ttl_seconds
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.timestamps.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        
        for key in expired_keys:
            self._remove_key(key)
    
    def _remove_key(self, key: str):
        """Remove key from all data structures"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]
        if key in self.access_order:
            self.access_order.remove(key)
    
    def _enforce_size_limit(self):
        """Enforce cache size limit using LRU eviction"""
        while len(self.cache) > self.maxsize:
            if self.access_order:
                oldest_key = self.access_order.pop(0)
                self._remove_key(oldest_key)
            else:
                break
    
    def get(self, key: str, default=None):
        """Get value from cache"""
        self._cleanup_expired()
        
        if key in self.cache and not self._is_expired(key):
            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        
        return default
    
    def set(self, key: str, value: Any):
        """Set value in cache"""
        self._cleanup_expired()
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
        
        # Update access order
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        
        self._enforce_size_limit()
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.timestamps.clear()
        self.access_order.clear()
        self.logger.info("Cache cleared")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self._cleanup_expired()
        return {
            'size': len(self.cache),
            'maxsize': self.maxsize,
            'ttl_seconds': self.ttl_seconds,
            'hit_ratio': getattr(self, '_hits', 0) / max(getattr(self, '_requests', 1), 1)
        }

class DataFrameOptimizer:
    """DataFrame memory and performance optimization utilities"""
    
    @staticmethod
    @profile_critical
    def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame data types for memory efficiency"""
        if not config.OPTIMIZE_DTYPES or df.empty:
            return df
        
        with TimeBlock("dataframe_dtype_optimization"):
            optimized_df = df.copy()
            
            for col in optimized_df.columns:
                col_type = optimized_df[col].dtype
                
                # Optimize numeric columns
                if pd.api.types.is_numeric_dtype(col_type):
                    if pd.api.types.is_integer_dtype(col_type):
                        # Try to downcast integers
                        optimized_df[col] = pd.to_numeric(optimized_df[col], downcast='integer')
                    elif pd.api.types.is_float_dtype(col_type):
                        # Try to downcast floats
                        optimized_df[col] = pd.to_numeric(optimized_df[col], downcast='float')
                
                # Optimize object columns
                elif col_type == 'object':
                    # Try to convert to category if it has few unique values
                    unique_ratio = optimized_df[col].nunique() / len(optimized_df[col])
                    if unique_ratio < 0.5:  # Less than 50% unique values
                        try:
                            optimized_df[col] = optimized_df[col].astype('category')
                        except:
                            pass  # Keep as object if conversion fails
            
            memory_before = df.memory_usage(deep=True).sum()
            memory_after = optimized_df.memory_usage(deep=True).sum()
            reduction = (memory_before - memory_after) / memory_before * 100
            
            logging.getLogger(__name__).info(
                f"DataFrame memory optimized: {memory_before/1024/1024:.1f}MB -> "
                f"{memory_after/1024/1024:.1f}MB ({reduction:.1f}% reduction)"
            )
            
            return optimized_df
    
    @staticmethod
    @profile_critical
    def process_in_chunks(df: pd.DataFrame, func: Callable, chunk_size: Optional[int] = None) -> pd.DataFrame:
        """Process large DataFrame in chunks to reduce memory usage"""
        if df.empty:
            return df
        
        chunk_size = chunk_size or config.DATAFRAME_CHUNK_SIZE
        
        if len(df) <= chunk_size:
            return func(df)
        
        with TimeBlock("chunked_dataframe_processing"):
            results = []
            
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i + chunk_size]
                processed_chunk = func(chunk)
                results.append(processed_chunk)
            
            return pd.concat(results, ignore_index=True)
    
    @staticmethod
    def vectorize_operations(df: pd.DataFrame) -> pd.DataFrame:
        """Replace lambda functions with vectorized operations where possible"""
        # This is a template - specific optimizations should be implemented per use case
        optimized_df = df.copy()
        
        # Example: Replace lambda x: str(x) with .astype(str)
        for col in optimized_df.select_dtypes(include=['object']).columns:
            if optimized_df[col].dtype != 'string':
                try:
                    optimized_df[col] = optimized_df[col].astype('string')
                except:
                    pass
        
        return optimized_df

class BarcodeCache:
    """Optimized barcode generation with caching"""
    
    def __init__(self):
        self.cache = TTLCache(maxsize=config.BARCODE_CACHE_SIZE, ttl_seconds=3600)  # 1 hour TTL
        self.logger = logging.getLogger(__name__)
    
    @profile_critical
    def generate_barcode(self, valor: str, carpeta: str, nombre: str) -> str:
        """Generate barcode with caching and file existence check"""
        import barcode
        from barcode.writer import ImageWriter
        import os
        
        cache_key = f"{valor}_{carpeta}_{nombre}"
        ruta = os.path.join(carpeta, f"{nombre}.png")
        
        # Check cache first
        cached_path = self.cache.get(cache_key)
        if cached_path and os.path.exists(cached_path):
            return cached_path
        
        # Check if file already exists
        if os.path.exists(ruta):
            self.cache.set(cache_key, ruta)
            return ruta
        
        # Generate new barcode
        try:
            with TimeBlock("barcode_generation"):
                code128 = barcode.get('code128', valor, writer=ImageWriter())
                code128.save(ruta)
                self.cache.set(cache_key, ruta)
                return ruta
        except Exception as e:
            self.logger.error(f"Failed to generate barcode for {valor}: {e}")
            raise

# Global instances
http_client = OptimizedHTTPClient()
api_cache = TTLCache(maxsize=config.API_CACHE_SIZE, ttl_seconds=config.get_cache_ttl_seconds())
barcode_cache = BarcodeCache()
df_optimizer = DataFrameOptimizer()

def cached_api_call(cache_key: str, api_func: Callable, *args, **kwargs) -> Any:
    """Wrapper for API calls with caching"""
    # Check cache first
    cached_result = api_cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Make API call
    result = api_func(*args, **kwargs)
    
    # Cache the result
    api_cache.set(cache_key, result)
    return result

def optimize_html_generation(html_content: str, filename: str) -> str:
    """Optimized HTML file writing with buffering"""
    try:
        with open(filename, "w", encoding="utf-8", buffering=config.FILE_BUFFER_SIZE) as f:
            f.write(html_content)
        return filename
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to write HTML file {filename}: {e}")
        raise