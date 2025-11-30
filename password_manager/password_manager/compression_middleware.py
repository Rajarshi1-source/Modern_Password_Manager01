"""
Compression Middleware for Password Manager

ASGI-Compatible middleware that provides response compression for API endpoints:
- Gzip compression for large responses
- Brotli compression (if available)
- Selective compression based on content type
- Size threshold for compression

This middleware complements Django's GZipMiddleware with:
- Better control over compression
- Content-type filtering
- Size-based decisions
- Compression statistics

Author: SecureVault Password Manager
Version: 2.0.0 (ASGI-compatible)
"""

import gzip
import logging
from io import BytesIO
from typing import Optional

from django.conf import settings
from asgiref.sync import iscoroutinefunction, markcoroutinefunction

logger = logging.getLogger(__name__)

# Try to import brotli for better compression
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False


class VaultCompressionMiddleware:
    """
    Intelligent compression middleware for vault API responses.
    
    Features:
    - Compresses responses above threshold
    - Supports Gzip and Brotli
    - Skips already-compressed content
    - Skips binary/streaming content
    - Tracks compression statistics
    - ASGI/async compatible
    """
    
    async_capable = True
    sync_capable = True
    
    # Configuration
    MIN_SIZE_FOR_COMPRESSION = 1024  # 1KB minimum
    COMPRESSIBLE_CONTENT_TYPES = [
        'application/json',
        'text/html',
        'text/plain',
        'text/css',
        'text/javascript',
        'application/javascript',
        'application/xml',
        'text/xml'
    ]
    
    # Paths to always compress (API endpoints)
    COMPRESS_PATHS = [
        '/api/vault/',
        '/api/auth/',
        '/api/kyber/',
    ]
    
    # Paths to skip compression
    SKIP_PATHS = [
        '/static/',
        '/media/',
        '/admin/',
    ]
    
    # Statistics tracking
    _stats = {
        'compressed': 0,
        'skipped': 0,
        'total_original': 0,
        'total_compressed': 0
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        response = await self.get_response(request)
        return self._process_response(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        response = self.get_response(request)
        return self._process_response(request, response)
    
    def _process_response(self, request, response):
        """
        Process response and apply compression if appropriate.
        """
        # Skip if compression disabled
        if not getattr(settings, 'ENABLE_RESPONSE_COMPRESSION', True):
            return response
        
        # Check if we should compress this response
        if not self._should_compress(request, response):
            self._stats['skipped'] += 1
            return response
        
        # Get content
        content = response.content
        original_size = len(content)
        
        # Skip if below threshold
        if original_size < self.MIN_SIZE_FOR_COMPRESSION:
            return response
        
        # Check client's accepted encodings
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        
        # Try Brotli first (better compression)
        if BROTLI_AVAILABLE and 'br' in accept_encoding:
            compressed = self._compress_brotli(content)
            if compressed and len(compressed) < original_size * 0.9:
                return self._create_compressed_response(
                    response, compressed, 'br', original_size
                )
        
        # Fall back to Gzip
        if 'gzip' in accept_encoding:
            compressed = self._compress_gzip(content)
            if compressed and len(compressed) < original_size * 0.9:
                return self._create_compressed_response(
                    response, compressed, 'gzip', original_size
                )
        
        return response
    
    def _should_compress(self, request, response) -> bool:
        """
        Determine if response should be compressed.
        """
        # Skip if response already has content-encoding
        if response.get('Content-Encoding'):
            return False
        
        # Skip streaming responses
        if response.streaming:
            return False
        
        # Skip certain status codes
        if response.status_code < 200 or response.status_code >= 300:
            return False
        
        # Check path
        path = request.path
        
        # Skip excluded paths
        for skip_path in self.SKIP_PATHS:
            if path.startswith(skip_path):
                return False
        
        # Check content type
        content_type = response.get('Content-Type', '').split(';')[0].strip()
        if content_type not in self.COMPRESSIBLE_CONTENT_TYPES:
            return False
        
        return True
    
    def _compress_gzip(self, content: bytes) -> Optional[bytes]:
        """
        Compress content using Gzip.
        """
        try:
            buffer = BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=6) as f:
                f.write(content)
            return buffer.getvalue()
        except Exception as e:
            logger.warning(f"Gzip compression failed: {e}")
            return None
    
    def _compress_brotli(self, content: bytes) -> Optional[bytes]:
        """
        Compress content using Brotli.
        """
        if not BROTLI_AVAILABLE:
            return None
        
        try:
            return brotli.compress(content, quality=4)
        except Exception as e:
            logger.warning(f"Brotli compression failed: {e}")
            return None
    
    def _create_compressed_response(
        self, 
        response, 
        compressed: bytes, 
        encoding: str,
        original_size: int
    ):
        """
        Create compressed response with appropriate headers.
        """
        response.content = compressed
        response['Content-Encoding'] = encoding
        response['Content-Length'] = len(compressed)
        
        # Add Vary header for proper caching
        vary = response.get('Vary', '')
        if 'Accept-Encoding' not in vary:
            response['Vary'] = f"{vary}, Accept-Encoding" if vary else 'Accept-Encoding'
        
        # Update statistics
        self._stats['compressed'] += 1
        self._stats['total_original'] += original_size
        self._stats['total_compressed'] += len(compressed)
        
        # Log compression ratio for debugging
        ratio = (1 - len(compressed) / original_size) * 100
        logger.debug(
            f"Compressed response: {original_size} -> {len(compressed)} "
            f"({ratio:.1f}% reduction, {encoding})"
        )
        
        return response
    
    @classmethod
    def get_stats(cls) -> dict:
        """
        Get compression statistics.
        """
        total_saved = cls._stats['total_original'] - cls._stats['total_compressed']
        avg_ratio = 0
        if cls._stats['total_original'] > 0:
            avg_ratio = (1 - cls._stats['total_compressed'] / cls._stats['total_original']) * 100
        
        return {
            **cls._stats,
            'total_saved_bytes': total_saved,
            'average_compression_ratio': f'{avg_ratio:.1f}%',
            'brotli_available': BROTLI_AVAILABLE
        }
    
    @classmethod
    def reset_stats(cls):
        """Reset compression statistics."""
        cls._stats = {
            'compressed': 0,
            'skipped': 0,
            'total_original': 0,
            'total_compressed': 0
        }


class CacheControlMiddleware:
    """
    Set appropriate cache control headers for vault API responses.
    
    - No-cache for sensitive vault data
    - Cache for static assets
    - ETag support for conditional requests
    - ASGI/async compatible
    """
    
    async_capable = True
    sync_capable = True
    
    NO_CACHE_PATHS = [
        '/api/vault/',
        '/api/auth/',
        '/api/kyber/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        response = await self.get_response(request)
        return self._process_response(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        response = self.get_response(request)
        return self._process_response(request, response)
    
    def _process_response(self, request, response):
        path = request.path
        
        # Set no-cache for sensitive endpoints
        for no_cache_path in self.NO_CACHE_PATHS:
            if path.startswith(no_cache_path):
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                return response
        
        # Allow caching for static files
        if path.startswith('/static/'):
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
        
        return response
