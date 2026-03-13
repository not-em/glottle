#!/usr/bin/env python3
"""
build_morpheme_data.py

Downloads Colin Goldberg's morphemes dataset, filters and transforms the raw
entries by origin, meaning quality, and form, then writes a clean
morpheme_data.json (split into prefixes, roots, and suffixes) for use in the
word builder app.

Run:    python build_morpheme_data.py
Output: morpheme_data.json  — filtered dataset (commit to repo)
        morphemes.json      — raw source download (gitignore)
"""

import json
import urllib.request
import re
import sys

MORPHEMES_URL = "https://raw.githubusercontent.com/colingoldberg/morphemes/master/data/morphemes.json"
RAW_FILE = "morphemes.json"
OUT_FILE = "morpheme_data.json"

# ---------------------------------------------------------------------------
# Quality filter constants
# ---------------------------------------------------------------------------

# Morphemes we know are ambiguous / roots masquerading as affixes / noise
BLOCKLIST = {
    "a",
    "e",
    "i",
    "o",
    "u",  # bare vowels
    "s",
    "er",
    "ed",
    "ing",  # inflectional suffixes
    "b",
    "c",
    "d",
    "f",
    "g",
    "h",  # single consonants
    "un",
    "in",
    "im",
    "il",
    "ir",  # real but very short & ambiguous
    "ab",
    "ad",
    "af",
    "ag",
    "ak",  # ambiguous short Latin prefixes
    "de",
    "di",
    "dis",  # keep only "dis" with a clear meaning — handled below
    "ex",
    "en",
    "em",  # too ambiguous without careful vetting
    "up",
    "out",
    "over",
    "under",  # English particle-prefixes, handled separately
    "fore",
    "mid",
    "non",
    "off",
}

# Origin strings from the dataset that indicate good classical sources
GOOD_ORIGINS = {
    "greek",
    "latin",
    "old english",
    "anglo-saxon",
    "french",
    "old french",
    "middle english",
    "anglo-french",
    "classical",
}

# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------


def origin_ok(origin_str: str) -> bool:
    """Return True if *origin_str* mentions at least one approved classical source."""
    if not origin_str:
        return False
    o = origin_str.lower()
    return any(g in o for g in GOOD_ORIGINS)


def meaning_ok(meaning: str) -> bool:
    """Return True if *meaning* is a substantive definition (not a cross-reference or stub)."""
    if not meaning:
        return False
    m = meaning.strip()
    if len(m) < 4:
        return False
    # reject meanings that are just "see X" or "variant of X"
    if re.match(r"^(see|variant|form of|alt\.)", m, re.I):
        return False
    return True


def form_ok(form: str, mtype: str) -> bool:
    """Return True if *form* passes length, blocklist, and character checks."""
    f = form.strip().lower()
    if f in BLOCKLIST:
        return False
    # prefixes/suffixes: at least 2 chars; roots: at least 3 chars
    if mtype in ("prefix", "suffix") and len(f) < 2:
        return False
    if mtype == "root" and len(f) < 3:
        return False
    # no digits or special chars
    if re.search(r"[^a-z]", f):
        return False
    return True


def dedup(lst: list) -> list:
    """Return *lst* with duplicate records removed, keeping the first occurrence of each form."""
    seen: set = set()
    out = []
    for item in lst:
        if item["form"] not in seen:
            seen.add(item["form"])
            out.append(item)
    return out


def truncate_meaning(meaning: str, max_len: int = 60) -> str:
    """Trim *meaning* to the first clause and hard-cap it at *max_len* characters."""
    m = meaning.split(";")[0].split(",")[0].strip()
    if len(m) > max_len:
        m = m[: max_len - 3].rsplit(" ", 1)[0] + "…"
    return m


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def download_raw(url: str, dest: str) -> dict:
    """Download the raw morphemes JSON from *url*, save it to *dest*, and return it parsed."""
    print(f"Downloading {dest}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"  saved to {dest}")
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    with open(dest, encoding="utf-8") as f:
        raw = json.load(f)

    print(f"  {len(raw)} entries in raw dataset")
    return raw


def parse_entries(raw: dict) -> tuple[list, list, list]:
    """
    Iterate over *raw* entries, apply quality filters, and sort records into
    three lists: prefixes, roots, suffixes.
    """
    prefixes: list = []
    roots: list = []
    suffixes: list = []

    for key, entry in raw.items():
        meaning_raw = (entry.get("meaning") or [""])[0] or entry.get("definition") or ""
        meaning_raw = meaning_raw.strip()
        origin = (entry.get("origin") or entry.get("language") or "").strip()
        examples = entry.get("examples") or entry.get("words") or []

        for f in entry.get("forms", []):
            mtype = f.get("loc")
            form = (f.get("form") or key).strip().lstrip("-").rstrip("-")
            root = f.get("root") or key

            if not form_ok(form, mtype):
                continue

            # Derive mtype from root punctuation when available
            if root.startswith("-") and root.endswith("-"):
                mtype = "root"
            elif root.startswith("-"):
                mtype = "suffix"
            elif root.endswith("-"):
                mtype = "prefix"

            record = {
                "form": form.lower(),
                "display": (
                    f"{form}-"
                    if mtype == "prefix"
                    else f"-{form}" if mtype == "suffix" else form
                ),
                "meaning": truncate_meaning(meaning_raw),
                "origin": origin.strip().title(),
                "examples": examples[:3] if isinstance(examples, list) else [],
            }

            if mtype == "prefix":
                prefixes.append(record)
            elif mtype == "suffix":
                suffixes.append(record)
            else:
                roots.append(record)

    return prefixes, roots, suffixes


def write_output(prefixes: list, roots: list, suffixes: list, dest: str) -> None:
    """De-duplicate, sort, and write the three morpheme lists to *dest* as JSON."""
    prefixes = dedup(sorted(prefixes, key=lambda x: x["form"]))
    roots = dedup(sorted(roots, key=lambda x: x["form"]))
    suffixes = dedup(sorted(suffixes, key=lambda x: x["form"]))

    result = {
        "prefixes": prefixes,
        "roots": roots,
        "suffixes": suffixes,
        "meta": {
            "source": "Colin Goldberg morphemes dataset (Apache 2.0)",
            "url": "https://github.com/colingoldberg/morphemes",
            "note": "Filtered for quality: classical origins, meaningful definitions, clean forms",
            "counts": {
                "prefixes": len(prefixes),
                "roots": len(roots),
                "suffixes": len(suffixes),
            },
        },
    }

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\nDone!")
    print(f"  prefixes : {len(prefixes)}")
    print(f"  roots    : {len(roots)}")
    print(f"  suffixes : {len(suffixes)}")
    print(f"  written  : {dest}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    raw = download_raw(MORPHEMES_URL, RAW_FILE)
    prefixes, roots, suffixes = parse_entries(raw)
    write_output(prefixes, roots, suffixes, OUT_FILE)


if __name__ == "__main__":
    main()
