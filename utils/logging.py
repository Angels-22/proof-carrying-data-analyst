"""
Logging module for VerifyAI.
Structured event-based logging that explicitly scrubs credentials and secrets.
"""

import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, Optional

def scrub_secrets(text: str) -> str:
    """Scrub potential API keys and secrets from logged strings."""
    if not isinstance(text, str):
        text = str(text)
    # Simple direct substitutions
    text = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "[REDACTED_KEY]", text, flags=re.IGNORECASE)
    text = re.sub(r"(api[_-]?key\s*[:=]\s*['\"]?)([^'\";\s]+)", r"\1[REDACTED_KEY]", text, flags=re.IGNORECASE)
    text = re.sub(r"(bearer\s+)([a-zA-Z0-9_\-\.]{10,})", r"\1[REDACTED_TOKEN]", text, flags=re.IGNORECASE)
    text = re.sub(r"(password\s*[:=]\s*['\"]?)([^'\";\s]+)", r"\1[REDACTED_PW]", text, flags=re.IGNORECASE)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: scrub_secrets(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(scrub_secrets(a) for a in record.args)
        return True


_LOGGER_INITIALIZED = False


def get_logger(name: str = "VerifyAI") -> logging.Logger:
    """Get or configure the VerifyAI logger."""
    global _LOGGER_INITIALIZED
    logger = logging.getLogger(name)

    if not _LOGGER_INITIALIZED:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        logger.propagate = False
        _LOGGER_INITIALIZED = True

    return logger


def log_event(event_type: str, details: Optional[Dict[str, Any]] = None, level: str = "INFO"):
    """
    Log a structured pipeline audit event.
    """
    logger = get_logger("VerifyAI.Audit")
    details = details or {}
    scrubbed_details = {k: scrub_secrets(str(v)) for k, v in details.items()}
    msg = f"EVENT={event_type} | " + " | ".join(f"{k}={v}" for k, v in scrubbed_details.items())
    
    if level.upper() == "WARNING":
        logger.warning(msg)
    elif level.upper() == "ERROR":
        logger.error(msg)
    elif level.upper() == "DEBUG":
        logger.debug(msg)
    else:
        logger.info(msg)
