import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


HOOK_PATH = Path(__file__).resolve().parents[1] / "audit_log.py"
SPEC = importlib.util.spec_from_file_location("audit_log", HOOK_PATH)
AUDIT_LOG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT_LOG)


class _RecordingPattern:
    def __init__(self):
        self.max_seen = 0

    def sub(self, replacement, value):
        self.max_seen = max(self.max_seen, len(value))
        return value


class AuditLogRedactionTests(unittest.TestCase):
    def test_large_string_is_bounded_before_redaction_patterns_scan_it(self):
        patterns = {
            name: _RecordingPattern()
            for name in (
                "KEY_VALUE_SECRET_PATTERN",
                "BEARER_PATTERN",
                "API_KEY_PATTERN",
                "JWT_PATTERN",
            )
        }
        large_value = "x" * (AUDIT_LOG.MAX_VALUE_LEN * 100)

        with patch.multiple(AUDIT_LOG, **patterns):
            result = AUDIT_LOG._redact(large_value)

        self.assertLessEqual(len(result), AUDIT_LOG.MAX_VALUE_LEN + 100)
        for pattern in patterns.values():
            self.assertLessEqual(pattern.max_seen, AUDIT_LOG.MAX_VALUE_LEN)


if __name__ == "__main__":
    unittest.main()
