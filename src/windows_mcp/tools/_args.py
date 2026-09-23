"""Argument coercion shared by the tool modules."""

_TRUE = {"true", "yes", "y", "1", "on"}
_FALSE = {"false", "no", "n", "0", "off"}


def as_bool(value: object, name: str) -> bool:
    """Parse a boolean tool argument.

    MCP clients sometimes send booleans as strings. Accept the common spellings and
    reject anything else: silently reading an unknown word as False made
    ``recursive="yes"`` quietly search only the top folder.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in _TRUE:
            return True
        if normalized in _FALSE:
            return False
    raise ValueError(f"{name} must be true or false (got {value!r})")


def as_whole_number(value: object, name: str) -> int | None:
    """Parse an optional non-negative whole number sent as a number or text ("0x1A2B" too)."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            number = int(value.strip(), 0)
        except ValueError:
            pass
        else:
            if number >= 0:
                return number
    raise ValueError(f"{name} must be a whole number (got {value!r})")
