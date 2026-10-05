import re
import unicodedata

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_name(name: str) -> str:
    """'D.J. Moore Jr.' -> 'dj moore'. Used for exact and fuzzy matching and search."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    folded = folded.replace("-", " ")
    folded = _NON_ALNUM.sub("", folded)
    parts = [p for p in folded.split() if p not in _SUFFIXES]
    return " ".join(parts)
