"""
Authentication and authorization utilities for MSA.

Provides API key validation, tenant extraction, and rate limiting.
"""

import hashlib
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


# Simple in-memory API key store (replace with database in production)
API_KEYS = {
    "test-api-key": {
        "tenant_id": "default",
        "name": "Test API Key",
        "rate_limit": 1000,  # requests per minute
        "active": True
    }
}


# Rate limiting state (in-memory, use Redis in production)
rate_limit_state = defaultdict(list)


def validate_api_key(
    x_api_key: str = Header(..., alias="X-API-Key")
) -> Tuple[str, dict]:
    """
    Validate API key and return tenant info.
    
    Args:
        x_api_key: API key from header
        
    Returns:
        Tuple of (tenant_id, api_key_info)
        
    Raises:
        HTTPException: If API key is invalid
    """
    api_key_info = API_KEYS.get(x_api_key)
    
    if not api_key_info:
        logger.warning(f"Invalid API key attempted: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    if not api_key_info.get("active", False):
        logger.warning(f"Inactive API key attempted: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive"
        )
    
    tenant_id = api_key_info["tenant_id"]
    
    logger.debug(f"API key validated for tenant: {tenant_id}")
    return tenant_id, api_key_info


def check_rate_limit(tenant_id: str, rate_limit: int) -> bool:
    """
    Check if tenant has exceeded rate limit.
    
    Args:
        tenant_id: Tenant ID
        rate_limit: Max requests per minute
        
    Returns:
        True if within limit, False if exceeded
    """
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # Clean old entries
    rate_limit_state[tenant_id] = [
        timestamp for timestamp in rate_limit_state[tenant_id]
        if timestamp > minute_ago
    ]
    
    # Check limit
    current_count = len(rate_limit_state[tenant_id])
    
    if current_count >= rate_limit:
        logger.warning(
            f"Rate limit exceeded for tenant {tenant_id}: "
            f"{current_count}/{rate_limit}"
        )
        return False
    
    # Record this request
    rate_limit_state[tenant_id].append(now)
    return True


def rate_limit_dependency(
    x_api_key: str = Header(..., alias="X-API-Key")
) -> str:
    """
    FastAPI dependency for rate limiting.
    
    Args:
        x_api_key: API key from header
        
    Returns:
        Tenant ID
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    tenant_id, api_key_info = validate_api_key(x_api_key)
    rate_limit = api_key_info.get("rate_limit", 1000)
    
    if not check_rate_limit(tenant_id, rate_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {rate_limit} requests per minute"
        )
    
    return tenant_id


def get_tenant_from_api_key(api_key: str) -> Optional[str]:
    """
    Extract tenant ID from API key without validation.
    
    Args:
        api_key: API key
        
    Returns:
        Tenant ID or None
    """
    api_key_info = API_KEYS.get(api_key)
    return api_key_info.get("tenant_id") if api_key_info else None


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for secure storage.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key(tenant_id: str) -> str:
    """
    Generate a new API key for a tenant.
    
    Args:
        tenant_id: Tenant ID
        
    Returns:
        New API key
    """
    import secrets
    api_key = f"msa_{secrets.token_urlsafe(32)}"
    return api_key
