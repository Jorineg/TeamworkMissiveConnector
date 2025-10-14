"""Webhook security verification."""
import hmac
import hashlib
from typing import Optional

from src import settings
from src.logging_conf import logger


def verify_teamwork_webhook(payload: bytes, signature: Optional[str]) -> bool:
    """
    Verify Teamwork webhook signature.
    
    Args:
        payload: Raw request payload
        signature: Signature from request header
    
    Returns:
        True if signature is valid or verification is disabled
    """
    if not settings.TEAMWORK_WEBHOOK_SECRET:
        # No secret configured, skip verification
        return True
    
    if not signature:
        logger.warning("Teamwork webhook signature missing")
        return False
    
    try:
        expected_signature = hmac.new(
            settings.TEAMWORK_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Error verifying Teamwork webhook: {e}")
        return False


def verify_missive_webhook(payload: bytes, signature: Optional[str]) -> bool:
    """
    Verify Missive webhook signature.
    
    Args:
        payload: Raw request payload
        signature: Signature from request header
    
    Returns:
        True if signature is valid or verification is disabled
    """
    if not settings.MISSIVE_WEBHOOK_SECRET:
        # No secret configured, skip verification
        return True
    
    if not signature:
        logger.warning("Missive webhook signature missing")
        return False
    
    try:
        expected_signature = hmac.new(
            settings.MISSIVE_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Error verifying Missive webhook: {e}")
        return False

