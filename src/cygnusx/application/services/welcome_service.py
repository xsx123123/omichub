"""Legacy import compatibility. Runtime welcome content lives in PostgreSQL."""
from cygnusx.application.services.welcome.distribution import claim, impression
from cygnusx.application.services.welcome.validation import FALLBACK_TEXT

DEFAULT_WELCOME_TEXT = FALLBACK_TEXT
__all__ = ["DEFAULT_WELCOME_TEXT", "claim", "impression"]
