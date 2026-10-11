"""
PMZilla Lab — tableau des livres que sort_by_domain.py écarte (lignes de MAPPING à "").

    python3 tools/sorting_exclusions.py [<dossier_markdown>]     (par défaut Bibliotheque-MD du workspace)

Pour chaque livre écarté : le livre gardé à sa place (s'il y en a un), la raison (le commentaire de MAPPING), puis,
pour les deux fichiers, la taille du Markdown, le format de la source et le nombre de figures. Taille, format et
figures viennent du fichier lui-même (taille du fichier, et seulement les premières lignes de son en-tête :
source:, figures:) ; aucun texte de livre n'est lu ni affiché. Lecture seule : rien n'est déplacé ni supprimé.

Un livre écarté qui ne figure pas dans GARDES (une nouvelle ligne à "" de MAPPING) apparaît « à identifier ».
Un écarté « hors sujet » n'est pas un doublon : il n'a pas de livre gardé.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapping_lab import MAPPING, R, norm  # noqa: E402

# écarté -> livre gardé à sa place (clés de MAPPING) ; None : écarté sans doublon (hors sujet, version concise)
GARDES: dict[str, str | None] = {
    R + "Agile & Scrum/agile-fluency-french-version.md": R + "Agile & Scrum/agile-fluency-project-ebook-rtw-1.md",
    R + "Agile & Scrum/un_guide_de_survie_à_l_adoption_ou_transformation_agile___travailler_avec_la_culture_d_une_organisation.md":
        R + "UX & Design/Michael Sahota - An Agile Adoption and Transformation Survival Guide.md",
    R + "Organizational Change & Transformation/OCTO_CULTURE_SCALING_KAIZEN_WEB.md":
        R + "Organizational Change & Transformation/culture-scaling-kaizen-version-epub.md",
    R + "Product Management & Discovery/Jeff Patton - Le story mapping (2015).md":
        R + "Product Management & Discovery/User Story Mapping Jeffe Patton O reilly 2014.md",
    R + "UX & Design/Lean UX_ Applying Lean Principles to Improve User Experience.md":
        R + "UX & Design/Lean UX_ Applying Lean Principles to Improve User Experience .md",
    R + "Agile & Scrum/Malcolm Gladwell - Blink.md": None,
    R + "Communication & Social Skills/BookHabits - Summary of Principles by Ray Dalio.md":
        R + "Organizational Change & Transformation/Ray Dalio - Principles.md",
    R + "Personal Development & Mindset/Joe Navarro - Narcissists Among Us.md": None,
    R + "Personal Development & Mindset/Robert Greene - Mastery (concise).md": None,
    R + "Lean & Continuous Improvement/Kaizen.md": None,
    R + "Books/Kanban PDF.md":
        R + "Books/Kanban Successful Evolutionary Change for Your Technology Business by David J. Anderson.md",
}

LINE = re.compile(r'^\s*R \+ "(?P<key>.+?)":\s*"(?P<codes>[A-Z]*)",?\s*(?:#\s*(?P<comment>.*))?$')


def comments(source_text: str) -> dict[str, str]:
    """Commentaire de chaque ligne de MAPPING, lu dans le texte de mapping_lab.py (clé complète, avec R)."""
    found: dict[str, str] = {}
    for line in source_text.splitlines():
        match = LINE.match(line)
        if match:
            found[R + match.group("key")] = (match.group("comment") or "").strip()
    return found


def facts(root: Path, key: str, on_disk: dict[str, Path]) -> dict:
    """Taille du Markdown, format de la source et figures, d'après le fichier (en-tête seulement)."""
    path = on_disk.get(norm(key))
    if path is None:
        return {"present": False}
    size, source, figures = path.stat().st_size, "?", "?"
    with path.open(encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle):
            if number >= 12:
                break
            if line.startswith("source:"):
                source = (Path(line.split(":", 1)[1].strip().strip('"')).suffix.lstrip(".").upper()) or "?"
            elif line.startswith("figures:"):
                figures = line.split(":", 1)[1].strip()
    return {"present": True, "size": size, "format": source, "figures": figures}


def kib(size: int) -> str:
    return f"{size / 1024:.0f} Ko"


def table(root: Path, mapping: dict | None = None, gardes: dict | None = None,
          comment_of: dict | None = None) -> str:
    mapping = MAPPING if mapping is None else mapping
    gardes = GARDES if gardes is None else gardes
    comment_of = comments((Path(__file__).resolve().parent / "mapping_lab.py").read_text(encoding="utf-8")) \
        if comment_of is None else comment_of
    on_disk = {norm(p.relative_to(root).as_posix()): p for p in root.rglob("*.md")}
    discarded = [key for key, codes in mapping.items() if not codes]
    rows = ["| Écarté | Gardé à sa place | Raison (commentaire de MAPPING) | Taille (écarté / gardé) | "
            "Format source (écarté / gardé) | Figures (écarté / gardé) |", "|---|---|---|---|---|---|"]
    no_duplicate = to_identify = 0
    for key in discarded:
        short = key[len(R):] if key.startswith(R) else key
        kept = gardes.get(key, "?")
        reason = comment_of.get(key) or "(aucun commentaire)"
        out = facts(root, key, on_disk)
        if kept is None:
            no_duplicate += 1
            kept_label, kept_facts = "aucun (écarté, pas un doublon)", None
        elif kept == "?":
            to_identify += 1
            kept_label, kept_facts = "à identifier", None
        else:
            kept_facts = facts(root, kept, on_disk)
            kept_label = (kept[len(R):] if kept.startswith(R) else kept) + f" ({mapping.get(kept) or 'écarté'})"

        def pair(field: str, show=str) -> str:
            left = show(out[field]) if out["present"] else "absent"
            right = "—" if kept_facts is None else (show(kept_facts[field]) if kept_facts["present"] else "absent")
            return f"{left} / {right}"
        rows.append(f"| {short} | {kept_label} | {reason} | {pair('size', kib)} | {pair('format')} | {pair('figures')} |")
    summary = (f"{len(discarded)} livres écartés par sort_by_domain.py : "
               f"{len(discarded) - no_duplicate - to_identify} doublons, {no_duplicate} écartés sans doublon "
               f"(hors sujet, version concise), {to_identify} à identifier.")
    return summary + "\n\n" + "\n".join(rows) + "\n"


def main() -> None:
    if len(sys.argv) > 2:
        print(__doc__)
        sys.exit(1)
    root = Path(sys.argv[1] if len(sys.argv) == 2 else Path(__file__).resolve().parents[1] / "Bibliotheque-MD")
    root = root.expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Not a folder: {root}")
    print(table(root), end="")


if __name__ == "__main__":
    main()
