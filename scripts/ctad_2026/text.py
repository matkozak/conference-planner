"""Text normalisation shared by the two CTAD source documents."""

import re
import unicodedata
from html import escape

#: Tokens kept upper-case when title-casing an all-caps heading.
ACRONYMS = frozenset(
    {
        "AD",
        "ADNI",
        "AI",
        "APOE",
        "CSF",
        "CTAD",
        "EEG",
        "FDA",
        "II",
        "IIA",
        "IIB",
        "III",
        "MCI",
        "MRI",
        "PET",
        "TMS",
        "US",
        "VCID",
    }
)

#: Credential tokens that follow a name and are not part of it.
POST_NOMINALS = frozenset(
    {
        "bsc",
        "do",
        "drph",
        "facp",
        "frcp",
        "mba",
        "mbbs",
        "md",
        "mph",
        "ms",
        "msc",
        "pharmd",
        "phd",
        "rn",
    }
)

_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_POSSESSIVE = re.compile(r"(?<=[^\W\d_])(['’])S\b", re.UNICODE)


def collapse(text: str) -> str:
    """Collapse runs of whitespace and trim."""
    return _WHITESPACE.sub(" ", text).strip()


def titleize(text: str) -> str:
    """Title-case an all-caps heading, preserving known acronyms.

    Mixed-case input is returned unchanged; the source only shouts in headings.
    """
    letters = [character for character in text if character.isalpha()]
    if not letters or not all(character.isupper() for character in letters):
        return collapse(text)

    def convert(match: re.Match[str]) -> str:
        word = match.group(0)
        if word.upper() in ACRONYMS:
            return word.upper()
        return word[0] + word[1:].lower()

    converted = _WORD.sub(convert, collapse(text))
    return _POSSESSIVE.sub(lambda match: f"{match.group(1)}s", converted)


def _recase_word(word: str) -> str:
    """``MCGINNIS`` -> ``McGinnis``; ``GUERRA`` -> ``Guerra``.

    ``Mac`` is deliberately not treated as a prefix: the sources contain both
    ``MACDONALD`` and ``MACHIZAWA``, and only one of them wants a capital.
    """
    if not word:
        return word
    if word.lower().startswith("mc") and len(word) > 2:
        return f"Mc{word[2].upper()}{word[3:].lower()}"
    return word[0].upper() + word[1:].lower()


def _recase_token(token: str) -> str:
    """Recase one whitespace-delimited token, respecting hyphenated surnames."""
    return "-".join(_recase_word(part) for part in token.split("-"))


def normalize_name(name: str) -> str:
    """Normalise a person name to display casing.

    The posters document upper-cases surnames (``Nemil BHATT``); the program
    document already uses display casing. Post-nominal credentials are dropped,
    and a hyphen the source broke across a line (``Rosa- Neto``) is rejoined.
    """
    joined = re.sub(r"(?<=\w)-\s+(?=\w)", "-", collapse(name))
    tokens = [token for token in joined.replace(",", " ").split() if token]
    kept: list[str] = []
    for token in tokens:
        if token.strip(".").lower() in POST_NOMINALS:
            continue
        if token.isupper() and len(token) > 1:
            token = _recase_token(token)
        kept.append(token)
    return " ".join(kept)


def is_post_nominal(name: str) -> bool:
    """True when a comma-separated fragment is only credentials, not a name."""
    tokens = [token.strip(".").lower() for token in collapse(name).split() if token]
    return bool(tokens) and all(token in POST_NOMINALS for token in tokens)


def normalize_org(text: str) -> str:
    """Tidy an affiliation string for display.

    The posters document runs country names together (``Durham,United-States``)
    and both documents wrap affiliations mid-phrase.
    """
    tidied = collapse(text).replace("United-States", "United States")
    tidied = re.sub(r",(?=\S)", ", ", tidied)
    return tidied.strip(" ,-")


def fold(text: str) -> str:
    """Fold a string to an accent-free, lower-case identity key."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return collapse(re.sub(r"[^\w\s]", " ", stripped)).lower()


def paragraphs_html(parts: list[str]) -> str:
    """Render text fragments as sanitized ``description_html`` paragraphs."""
    return "".join(f"<p>{escape(collapse(part))}</p>" for part in parts if part.strip())
