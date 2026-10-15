# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : liste « hors bibliothèque » d'une posture, calculée depuis le catalogue de chacun.

    uv run tools/outside_library.py <delivery|discovery|scaling|facilitation|toutes> [--catalog CHEMIN]

`references_postures.yaml` liste les ouvrages que les règles de chaque posture citent. Ce script les compare au
catalogue de la personne (tools/book_catalog.yaml, ou PMZILLA_LAB_CATALOGUE, ou --catalog) : un ouvrage est « dans
la bibliothèque » si un livre du catalogue porte le même titre (ou un alias) et un auteur commun. Tout le reste est
« hors bibliothèque ». Les documents officiels et boîtes à outils (`document: true`) se cherchent comme des livres : hors bibliothèque tant qu'ils ne sont pas indexés. Le champ `relations` donne les liens à ne pas confondre.
wake.py (réveil des postures) imprime ce résultat : la liste n'est plus écrite à la main dans les textes.
Sans catalogue lisible, le script le dit et ne classe rien (aucune supposition).

Exemple :
    uv run tools/outside_library.py delivery
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ICI = Path(__file__).resolve().parent
POSTURES = ("delivery", "discovery", "scaling", "facilitation")
REFERENCES = ICI / "references_postures.yaml"


def catalogue_par_defaut() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_CATALOGUE") or ICI / "book_catalog.yaml").expanduser()


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples."""
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte).split())


def titres_concordent(voulu: str, present: str) -> bool:
    """Même titre, ou le titre voulu contenu comme mots entiers dans le titre du catalogue (« Kanban » dans
    « Kanban : Successful Evolutionary Change… »), ou l'inverse pour un titre de catalogue assez long."""
    if not voulu or not present:
        return False
    if voulu == present:
        return True
    if len(voulu) >= 5 and f" {voulu} " in f" {present} ":
        return True
    return len(present) >= 8 and f" {present} " in f" {voulu} "


def charger_catalogue(chemin: Path | None = None) -> list[dict] | None:
    """Entrées du catalogue (titre normalisé, auteurs normalisés), ou None si le fichier est absent ou illisible."""
    chemin = Path(chemin).expanduser() if chemin else catalogue_par_defaut()
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(donnees, dict):
        return None
    return [{"titre": normaliser(e.get("titre", "")), "auteurs": normaliser(" ".join(map(str, e.get("auteurs") or [])))}
            for e in donnees.values() if isinstance(e, dict)]


def dans_le_catalogue(ouvrage: dict, catalogue: list[dict]) -> bool:
    """Un document (documentation officielle, Scrum Guide, toolbox) se cherche comme un livre, par son titre :
    hors bibliothèque tant qu'aucune entrée du catalogue ne le porte, donc dès qu'il est indexé il n'y est plus."""
    titres = [normaliser(t) for t in [ouvrage["titre"], *(ouvrage.get("alias") or [])]]
    auteurs = [normaliser(a) for a in ouvrage.get("auteurs") or []]
    for entree in catalogue:
        if not any(titres_concordent(t, entree["titre"]) for t in titres):
            continue
        if not auteurs or not entree["auteurs"] or any(a and a in entree["auteurs"] for a in auteurs):
            return True
    return False


def references(posture: str, fichier: Path | None = None) -> list[dict]:
    donnees = yaml.safe_load((fichier or REFERENCES).read_text(encoding="utf-8")) or {}
    if posture not in donnees:
        raise KeyError(f"posture inconnue : {posture} (connues : {', '.join(donnees)})")
    return donnees[posture]


def hors_bibliotheque(posture: str, catalogue: Path | None = None, fichier: Path | None = None) -> list[dict] | None:
    """Ouvrages cités par la posture et absents du catalogue ; None si le catalogue est illisible."""
    entrees = charger_catalogue(catalogue)
    if entrees is None:
        return None
    return [o for o in references(posture, fichier) if not dans_le_catalogue(o, entrees)]


def libelle(ouvrage: dict) -> str:
    if ouvrage.get("document"):
        return f"{ouvrage['titre']} (document, non indexé)"
    auteurs = " & ".join(ouvrage.get("auteurs") or [])
    return f"{auteurs}, {ouvrage['titre']}" if auteurs else ouvrage["titre"]


def rendre(posture: str, catalogue: Path | None = None, fichier: Path | None = None) -> list[str]:
    """Lignes de texte de la liste d'une posture (utilisées par wake.py et par la ligne de commande)."""
    try:
        absents = hors_bibliotheque(posture, catalogue, fichier)
    except KeyError as erreur:
        return [str(erreur)]
    if absents is None:
        return ["Catalogue introuvable ou illisible : la liste n'est pas calculée. Ne suppose rien : seul ce que "
                "renvoie la recherche vient de la bibliothèque ; pour le reste, écris la formule de ta langue de "
                "réponse pour une source absente (table de CLAUDE.md)."]
    if not absents:
        return ["Aucun des ouvrages cités par tes règles n'est absent du catalogue de l'utilisateur."]
    return [f"- {libelle(o)}" for o in absents]


RELATIONS = {
    "commente": "commente {avec} : cite-le comme un commentaire, par sa section, et ne lui fais pas dire ce que dit {avec}, ni l'inverse",
    "ne_pas_confondre": "ne pas confondre avec {avec} : ne fais pas dire à l'un ce que dit l'autre",
    "supplee_par": "à défaut, appuie-toi sur {avec}",
}


def rendre_relations(posture: str, fichier: Path | None = None) -> list[str]:
    """Liens entre ouvrages (champ `relations`) de la posture, à imprimer sous la liste hors bibliothèque."""
    lignes = []
    try:
        ouvrages = references(posture, fichier)
    except KeyError:
        return []
    for o in ouvrages:
        for lien in o.get("relations") or []:
            modele = RELATIONS.get(lien.get("type"), "lié à {avec}")
            texte = f"- {o['titre']} : " + modele.format(avec=lien.get("avec", "?"))
            lignes.append(texte + (f" ({lien['note']})" if lien.get("note") else ""))
    return lignes


def main() -> int:
    parser = argparse.ArgumentParser(description="Liste « hors bibliothèque » d'une posture, calculée depuis le catalogue")
    parser.add_argument("posture", help="delivery, discovery, scaling, facilitation ou toutes")
    parser.add_argument("--catalog", help="catalogue de livres (défaut : PMZILLA_LAB_CATALOGUE ou tools/book_catalog.yaml)")
    import flux_config
    flux_config.refuse_old_options(sys.argv[1:], {"--catalogue": "--catalog"})
    args = parser.parse_args()
    voulues = POSTURES if args.posture == "toutes" else (args.posture,)
    for posture in voulues:
        if len(voulues) > 1:
            print(f"## {posture}")
        print("\n".join(rendre(posture, Path(args.catalog) if args.catalog else None)))
        relations = rendre_relations(posture)
        if relations:
            print("Relations entre ouvrages :\n" + "\n".join(relations))
    return 0


if __name__ == "__main__":
    sys.exit(main())
