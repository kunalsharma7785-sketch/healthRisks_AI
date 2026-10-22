import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

audit_logger = logging.getLogger("healthrisk.audit")
audit_logger.setLevel(logging.INFO)

# Structured JSON log format
class AuditLogger:
    @staticmethod
    def log_event(
        event_type: str,
        status: str,
        ip_address: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Record a compliance security audit entry.
        Never logs sensitive health data, plaintext passwords, or auth tokens.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "status": status,
            "ip_address": ip_address,
            "user_id": str(user_id) if user_id else "anonymous",
            "details": details or {}
        }
        audit_logger.info(json.dumps(log_entry))
