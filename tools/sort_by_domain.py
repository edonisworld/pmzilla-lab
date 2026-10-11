"""
PMZilla Lab — ventilation de la bibliothèque par domaine, pour les agents BMAD.

Usage :
    python3 sort_by_domain.py <dossier_markdown> <dossier_collections>
    ex : python3 sort_by_domain.py ~/Bibliotheque-MD ~/Bibliotheque-Lab

- COPIE les fichiers (les originaux ne bougent pas). Écrit dans un dossier distinct
  de ~/Bibliotheque-Collections, qui reste tel quel pour Open WebUI.
- Un livre rattaché à plusieurs domaines est copié dans chacun ; le serveur de
  bibliothèque ne l'indexe qu'une fois, avec tous ses domaines.
- Les livres marqués "" (doublons de langue ou de format, livres à identifier) ne sont pas copiés.
- Signale les fichiers de la liste introuvables et les .md présents mais non classés.
- Avant toute copie, vérifie tous les codes de domaine de MAPPING : un code inconnu arrête le script
  (code de sortie 1) sans rien copier.
- Deux livres de même nom de fichier (dans deux sous-dossiers) ne peuvent pas coexister : le serveur de
  bibliothèque regroupe par nom de fichier. Le premier est copié, le suivant est signalé et n'est pas
  copié ; aucun fichier n'en écrase un autre.

Domaines (nom du dossier = nom de collection dans le serveur) et agents qui les lisent :

    produit       Discovery · BMAD Analyst, PM, UX Designer
    flow          Delivery, Scaling · BMAD PM, Scrum Master
    organisation  Scaling · BMAD Analyst
    facilitation  Facilitation · BMAD Scrum Master
    tech          Delivery · BMAD Architect, Dev, Test Architect
    (Critic cherche dans toute la bibliothèque)
"""
import shutil
import sys
from pathlib import Path

from mapping_lab import DOMAINS, MAPPING, R, norm  # noqa: E402,F401  (table commune, voir mapping_lab.py)


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1]).expanduser().resolve()
    dst = Path(sys.argv[2]).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"Not a folder: {src}")

    unknown = [(rel, code) for rel, codes in MAPPING.items() for code in codes if code not in DOMAINS]
    if unknown:  # tout est vérifié avant la première copie : jamais de copie partielle
        lines = [f"  - {rel} : code « {code} »" for rel, code in unknown]
        sys.exit(f"MAPPING invalide : {len(unknown)} code(s) de domaine inconnu(s) "
                 f"(codes valides : {', '.join(DOMAINS)}). Rien n'a été copié.\n" + "\n".join(lines))

    on_disk = {norm(p.relative_to(src).as_posix()): p for p in src.rglob("*.md")}
    counts = {name: 0 for name in DOMAINS.values()}
    missing, skipped, found = [], [], set()
    kept: dict[str, str] = {}     # nom de fichier (sans casse : APFS) -> livre déjà copié sous ce nom
    duplicates: list[tuple[str, str]] = []

    for rel, codes in MAPPING.items():
        f = on_disk.get(norm(rel))
        if f is None:
            missing.append(rel)
            continue
        found.add(norm(rel))
        if not codes:
            skipped.append(rel)
            continue
        first = kept.setdefault(norm(f.name).casefold(), rel)
        if first != rel:  # même nom de fichier qu'un livre déjà copié : on n'écrase rien
            duplicates.append((rel, first))
            continue
        for code in dict.fromkeys(codes):
            folder = dst / DOMAINS[code]
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, folder / f.name)
            counts[DOMAINS[code]] += 1

    unclassified = sorted(
        rel for rel, p in on_disk.items() if rel not in found and not p.name.startswith("_")
    )

    print("Livres copiés par domaine :")
    for name, count in counts.items():
        print(f"  {name} : {count}")
    if skipped:
        print(f"\nÉcartés (doublons, à identifier) : {len(skipped)}")
        for s in skipped:
            print(f"  - {s}")
    if duplicates:
        print(f"\nNoms de fichiers en double, non copiés (le premier est gardé) : {len(duplicates)}")
        for rel, first in duplicates:
            print(f"  - {rel}\n    même nom que {first} : renommer l'un des deux fichiers")
    if missing:
        print(f"\nIntrouvables (nom modifié ?) : {len(missing)}")
        for m in missing:
            print(f"  - {m}")
    if unclassified:
        print(f"\nPrésents mais non classés (nouveaux livres ?) : {len(unclassified)}")
        for u in unclassified:
            print(f"  - {u}")
    print(f"\nDomaines prêts dans : {dst}")


if __name__ == "__main__":
    main()
