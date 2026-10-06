import secrets


_TEMP_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_TEMP_LOWER = "abcdefghijkmnopqrstuvwxyz"
_TEMP_DIGITS = "23456789"
_TEMP_SYMBOLS = "!@#$%&*+-_"
_TEMP_ALPHABET = _TEMP_UPPER + _TEMP_LOWER + _TEMP_DIGITS + _TEMP_SYMBOLS


def generate_temporary_password(length: int = 14) -> str:
    """Generate a strong, human-transcribable temporary password.

    Ambiguous characters such as 0/O and 1/l are deliberately omitted because
    school administrators often communicate first-login credentials verbally or
    from a printed onboarding slip.
    """
    if length < 12:
        raise ValueError("Temporary passwords must be at least 12 characters long.")

    characters = [
        secrets.choice(_TEMP_UPPER),
        secrets.choice(_TEMP_LOWER),
        secrets.choice(_TEMP_DIGITS),
        secrets.choice(_TEMP_SYMBOLS),
    ]
    characters.extend(secrets.choice(_TEMP_ALPHABET) for _ in range(length - len(characters)))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)
