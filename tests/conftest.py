import sys
from unittest.mock import MagicMock

try:
    import sulguk
except ImportError:
    mock_sulguk = MagicMock()
    mock_sulguk.SULGUK_PARSE_MODE = "sulguk"
    mock_sulguk.AiogramSulgukMiddleware = MagicMock
    sys.modules["sulguk"] = mock_sulguk
