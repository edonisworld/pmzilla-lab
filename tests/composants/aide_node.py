"""Aide des tests de Node de Mothra (change mothra-node-lts) : faux fichier de version, entrée d'inventaire, titre de procédure et
définition d'image de la forme réelle du lot 6 (local-ci-container D4).

Les numéros de version des tests sont fictifs ; aucun n'est le Node réel de Mothra.
"""
from aide_composants import DIGEST_BASE_CI, DOCKERFILE_CI, GUIDE, entree, entrees_ci, inventaire_complet

FICHIER = "mothra/.node-version"
IMAGE = "ci/Dockerfile"
PROCEDURE = "Update the Node of Mothra"
DIGEST = DIGEST_BASE_CI
BASE_LOT_6 = f"FROM node:26-slim@{DIGEST_BASE_CI}"   # ligne de base de la définition inventée de aide_composants


def entree_mothra() -> dict:
    return entree("node-mothra", "node-runtime", FICHIER, "Node.js releases", PROCEDURE, flags=["major-watch-only"])


def definition_image(etiquette: str, prefixe: str = "", empreinte: str | None = DIGEST) -> str:
    """Définition de l'image de la CI de la forme du lot 6 (base, uv copié, Python de .python-version, CLI OpenSpec épinglée), dont
    seule la base change : `FROM <prefixe>node:<etiquette>-slim@<empreinte>` (sans empreinte : `FROM <prefixe>node:<etiquette>`)."""
    base = f"FROM {prefixe}node:{etiquette}-slim" + (f"@{empreinte}" if empreinte else "")
    assert BASE_LOT_6 in DOCKERFILE_CI, BASE_LOT_6
    return DOCKERFILE_CI.replace(BASE_LOT_6, base)


def avec_mothra(depot, version: str | None = "90.1.0", entree_presente: bool = True, image: str | None = None):
    """Ajoute au faux dépôt le fichier de version (si version), l'entrée d'inventaire (si demandée), le titre de procédure du guide
    et, si image (texte de ci/Dockerfile), la définition de l'image avec les trois entrées de la CI du lot 6."""
    depot.ecrire("docs/pmzilla/installation.md", GUIDE + f"### {PROCEDURE}\n")
    if version is not None:
        depot.ecrire(FICHIER, version)
    entrees = inventaire_complet()
    if image is not None:
        depot.avec_ci = True
        depot.ecrire(IMAGE, image)
        entrees += entrees_ci()
    depot.ecrire_inventaire(entrees + ([entree_mothra()] if entree_presente else []))


def publications(*lignes) -> list[dict]:
    """Liste de publications au format de l'index de la distribution : (version, lts) ; lts False ou nom de code."""
    return [{"version": f"v{v}", "lts": lts} for v, lts in lignes]
