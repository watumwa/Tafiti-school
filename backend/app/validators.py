import re

from django.core.exceptions import ValidationError


UGANDA_LIN_EXAMPLE = "U13F0921A44760"
UGANDA_LIN_PATTERN = re.compile(r"^U\d{2}[MF]\d{4}A\d{5}$")


def normalize_uganda_lin(value) -> str:
    """Normalize a Uganda EMIS learner identification number for storage."""
    return str(value or "").strip().upper()


def validate_uganda_lin(value):
    """Validate the structural LIN format while allowing the field to remain optional."""
    normalized = normalize_uganda_lin(value)
    if not normalized:
        return
    if not UGANDA_LIN_PATTERN.fullmatch(normalized):
        raise ValidationError(
            f"Enter the official 14-character Uganda LIN, e.g. {UGANDA_LIN_EXAMPLE}."
        )


def lin_gender_marker(value) -> str:
    """Return the M/F marker embedded in a structurally valid LIN, otherwise blank."""
    normalized = normalize_uganda_lin(value)
    if not UGANDA_LIN_PATTERN.fullmatch(normalized):
        return ""
    return normalized[3]
