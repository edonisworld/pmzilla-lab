#!/usr/bin/env python3
"""
PMZilla Lab : met à jour le sanctum des postures depuis les modèles de leurs skills.

    python3 tools/sanctum_refresh.py [--posture delivery|discovery|scaling|facilitation] [--racine DOSSIER] [--dry-run]

Le sanctum (_bmad/memory/pmzilla-<posture>-bmad/) n'est plus suivi par Git : il ne suit donc plus les modifications des
modèles. Ce script en génère une copie neuve avec init-sanctum.py dans un dossier temporaire, puis recopie dans le sanctum
existant ce qui vient des modèles : CREED.md, CAPABILITIES.md, references/ et scripts/. Il ne touche jamais au vécu
(MEMORY.md, BOND.md, PERSONA.md, INDEX.md, sessions/) ni à rien d'autre. INDEX.md n'est plus réécrit depuis le lot 6 :
c'est l'utilisateur qui décide de son contenu (il peut citer des fichiers que le sanctum a créés).
Les modèles ne contiennent plus de chemin absolu (lot 6, plan 6.1) : le CREED et le CAPABILITIES recopiés remplacent ceux
d'un ancien sanctum, qui en portaient. Si un modèle en contient de nouveau, le script s'arrête sans rien écrire. Un sanctum absent est créé par init-sanctum.py.
Un fichier du sanctum qui n'existe plus dans les modèles est supprimé de references/ et de scripts/ (le skill fait foi).
"""
from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

POSTURES = ("delivery", "discovery", "scaling", "facilitation")
FICHIERS = ("CREED.md", "CAPABILITIES.md")
DOSSIERS = ("references", "scripts")


def nom_skill(posture: str) -> str:
    return f"pmzilla-{posture}-bmad"


def regenerer(racine: Path, posture: str, dossier: Path) -> Path:
    """Sanctum neuf de la posture dans `dossier` (racine temporaire) ; renvoie son chemin."""
    skill = racine / ".claude" / "skills" / nom_skill(posture)
    fait = subprocess.run([sys.executable, str(skill / "scripts" / "init-sanctum.py"), str(dossier), str(skill)],
                          capture_output=True, text=True)
    if fait.returncode != 0:
        raise SystemExit(f"init-sanctum.py a échoué pour {posture} : {(fait.stderr or fait.stdout).strip()}")
    return dossier / "_bmad" / "memory" / nom_skill(posture)


CHEMIN_ABSOLU = re.compile(r"/(?:Users|home)/[^/\s]+/")


def verifier_sans_chemin_absolu(neuf: Path, temporaire: Path) -> None:
    """Les modèles ne portent aucun chemin absolu (ni celui du dossier temporaire, ni un dossier personnel) : sinon, rien n'est écrit."""
    anciens = {str(temporaire), str(temporaire.resolve())}
    sources = [neuf / nom for nom in FICHIERS] + [f for sous in DOSSIERS for f in sorted((neuf / sous).rglob("*"))]
    fautifs = []
    for fichier in sources:
        if fichier.is_file() and fichier.suffix in (".md", ".py", ".toml", ".yaml"):
            texte = fichier.read_text(encoding="utf-8")
            if CHEMIN_ABSOLU.search(texte) or any(ancien in texte for ancien in anciens):
                fautifs.append(str(fichier.relative_to(neuf)))
    if fautifs:
        raise SystemExit("Un modèle contient un chemin absolu (plan 6.1) : " + ", ".join(fautifs) + ". Rien n'a été écrit.")


def comparer(neuf: Path, existant: Path) -> tuple[list[str], list[str]]:
    """(fichiers à écrire, fichiers à supprimer), en chemins relatifs au sanctum."""
    a_ecrire, a_supprimer = [], []
    for nom in FICHIERS:
        if (neuf / nom).is_file() and (not (existant / nom).is_file() or not filecmp.cmp(neuf / nom, existant / nom, shallow=False)):
            a_ecrire.append(nom)
    for sous in DOSSIERS:
        for source in sorted((neuf / sous).rglob("*")) if (neuf / sous).is_dir() else []:
            if source.is_file():
                relatif = source.relative_to(neuf)
                cible = existant / relatif
                if not cible.is_file() or not filecmp.cmp(source, cible, shallow=False):
                    a_ecrire.append(str(relatif))
        for cible in sorted((existant / sous).rglob("*")) if (existant / sous).is_dir() else []:
            if cible.is_file() and not (neuf / cible.relative_to(existant)).is_file():
                a_supprimer.append(str(cible.relative_to(existant)))
    return a_ecrire, a_supprimer


def actualiser(racine: Path, posture: str, dry_run: bool = False) -> tuple[list[str], list[str]]:
    existant = racine / "_bmad" / "memory" / nom_skill(posture)
    with tempfile.TemporaryDirectory() as temp:
        neuf = regenerer(racine, posture, Path(temp))
        verifier_sans_chemin_absolu(neuf, Path(temp))
        if not existant.is_dir():
            if not dry_run:
                shutil.copytree(neuf, existant)
            return ["(sanctum créé)"], []
        a_ecrire, a_supprimer = comparer(neuf, existant)
        if not dry_run:
            for relatif in a_ecrire:
                (existant / relatif).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(neuf / relatif, existant / relatif)
            for relatif in a_supprimer:
                (existant / relatif).unlink()
        return a_ecrire, a_supprimer


def main() -> int:
    parser = argparse.ArgumentParser(description="Met à jour le sanctum des postures depuis les modèles de leurs skills")
    parser.add_argument("--posture", choices=POSTURES, help="une seule posture (défaut : les quatre)")
    parser.add_argument("--racine", default=str(Path(__file__).resolve().parent.parent), help="racine du workspace")
    parser.add_argument("--dry-run", action="store_true", help="dit ce qui changerait, sans rien écrire")
    args = parser.parse_args()
    racine = Path(args.racine).resolve()
    for posture in ([args.posture] if args.posture else POSTURES):
        ecrits, supprimes = actualiser(racine, posture, args.dry_run)
        verbe = "changerait" if args.dry_run else "mis à jour"
        if not ecrits and not supprimes:
            print(f"{posture} : à jour")
        else:
            print(f"{posture} : {verbe} : " + ", ".join(ecrits + [f"suppression de {s}" for s in supprimes]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
