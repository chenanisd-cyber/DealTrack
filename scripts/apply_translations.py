#!/usr/bin/env python3
"""
Injecte le dictionnaire de traductions dans les catalogues .po, puis compile.

On passe par polib plutôt que par un éditeur .po : le catalogue est régénéré à
chaque `makemessages`, donc les traductions doivent vivre dans un fichier
versionné à part, réinjectable.
"""

import subprocess
import sys
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translations import CATALOGUES  # noqa: E402

BASE = Path(__file__).resolve().parent.parent


def normalise(text):
    """Aplatit les retours à la ligne pour comparer les msgid multilignes."""
    return " ".join(text.split())


def apply_language(code, mapping):
    path = BASE / "locale" / code / "LC_MESSAGES" / "django.po"
    catalogue = polib.pofile(str(path))

    lookup = {normalise(k): v for k, v in mapping.items()}
    translated = missing = 0

    for entry in catalogue:
        key = normalise(entry.msgid)
        if key in lookup:
            entry.msgstr = lookup[key]
            entry.flags = [f for f in entry.flags if f != "fuzzy"]
            translated += 1
        elif not entry.msgstr:
            missing += 1

    catalogue.metadata.update(
        {
            "Project-Id-Version": "DealTrack 1.0",
            "Language": code,
            "Language-Team": f"DealTrack {code}",
            "Content-Type": "text/plain; charset=UTF-8",
        }
    )
    catalogue.save(str(path))

    mo = path.with_suffix(".mo")
    subprocess.run(["msgfmt", "-o", str(mo), str(path)], check=True)

    total = len(catalogue)
    print(
        f"  {code} : {translated}/{total} traduites "
        f"({translated * 100 // total} %), {missing} sans traduction "
        f"→ repli sur le français"
    )
    return translated, total


def main():
    print("Injection des traductions :")
    for code, mapping in CATALOGUES.items():
        apply_language(code, mapping)
    print("\nCatalogues .mo compilés.")


if __name__ == "__main__":
    main()
