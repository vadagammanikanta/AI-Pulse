"""Tests for secret masking log filter."""
import logging
import io

from app.logging_config import SecretMaskingFilter, register_secret

def test_secret_masking_filter_masks_registered_secrets():
    secret_key = "gsk_secret_key_1234567890_super_secret"
    f = SecretMaskingFilter([secret_key])

    logger = logging.getLogger("test_masking_logger")
    logger.setLevel(logging.INFO)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(f)
    logger.addHandler(handler)

    logger.info("Calling provider with key=%s in request", secret_key)

    output = stream.getvalue()
    assert secret_key not in output
    assert "gsk_****" in output

def test_register_secret_global_masking():
    secret_val = "AIzaSy_test_secret_api_key_999"
    register_secret(secret_val)

    from app.logging_config import _global_filter

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Using key {secret_val}",
        args=(),
        exc_info=None
    )
    _global_filter.filter(record)
    assert secret_val not in record.msg
    assert "AIza****" in record.msg
