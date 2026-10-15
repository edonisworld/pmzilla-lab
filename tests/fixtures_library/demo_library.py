"""Bibliothèque inventée, commune aux tests du lot 4 (import, recherche hybride, backend, parité).

Aucun texte de livre réel : titres, auteurs et phrases sont inventés. Les vecteurs ont 1024 dimensions comme bge-m3 ; seules les deux
premières ne sont pas nulles (cos θ, sin θ), donc la similarité de deux textes est le cosinus de l'écart de leurs angles et se calcule
de tête. `fake_embed` remplace `pmzilla_lab_library.embed` : il donne à une requête l'angle du premier mot-clé de KEYWORD_ANGLE qu'elle
contient (0,7 sinon), jamais d'appel à Ollama.

    sys.path.insert(0, ".../tests/fixtures_library"); import demo_library as demo
    demo.expected_counts()      -> dict des comptes attendus (livres, passages, figures, collections)
    demo.CHUNKS, demo.BOOKS     -> le contenu, pour calculer l'attendu d'une requête
    pg_demo.ThrowawayDatabase   -> (tests/library_backend/pg_demo.py) charge ce contenu par de simples INSERT dans une base jetable

Contenu : 5 documents, 14 passages dont 2 figures. Les collections sont celles du contenu (« veille » est l'ancien nom de « watch »). La date de publication des billets est relative à `today` pour que le bonus de fraîcheur soit testable.
"""
from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import watch_paths  # noqa: E402

DIMENSIONS = 1024
MODEL = "bge-m3"


def vector(angle: float) -> np.ndarray:
    v = np.zeros(DIMENSIONS, dtype=np.float32)
    v[0], v[1] = math.cos(angle), math.sin(angle)
    return v


def today_minus(days: int) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


# file_name -> (titre, collections « | », meta)
BOOKS: dict[str, tuple[str, str, dict]] = {
    "atelier-des-flux.md": ("L'atelier des flux", "flow|tech", {"author": "Auteur Fictif"}),
    "discovery-notes.md": ("Discovery Notes", "produit", {"author": "Another Author"}),
    "billet-recent.md": ("Un billet récent sur la prévisibilité", "watch",
                         {"url": "https://exemple.test/billet-recent", "author": "Blog Fictif", "published": today_minus(3),
                          "source": "exemple.test"}),
    "billet-ancien.md": ("An old post about experiments", "watch",
                         {"url": "https://exemple.test/billet-ancien", "author": "Blog Fictif", "published": "2020-01-15",
                          "source": "exemple.test"}),
    "article-propre.md": ("Un article de l'utilisateur", f"{watch_paths.OWN_COLLECTION}|watch",
                          {"url": "https://exemple.test/article-propre", "author": "Auteur Local",
                           "published": today_minus(10), "source": "exemple.test"}),
}

# (file_name, position, section, texte, angle, kind, ref)
CHUNKS: list[tuple[str, int, str, str, float, str, dict]] = [
    ("atelier-des-flux.md", 0, "Partie 1 > Chapitre 1", "Le flux de travail se mesure par le délai de bout en bout et l'âge des éléments en cours.", 0.20, "texte", {}),
    ("atelier-des-flux.md", 1, "Partie 1 > Chapitre 1", "Limiter le travail en cours réduit l'attente ; la prévisibilité d'une équipe dépend du débit observé.", 0.25, "texte", {}),
    ("atelier-des-flux.md", 2, "Partie 1 > Chapitre 2", "Une file d'attente qui grandit allonge le délai : c'est la loi de Little, pas une opinion.", 0.30, "texte", {}),
    ("atelier-des-flux.md", 3, "Partie 1 > Chapitre 2", "Figure 1.1 : le délai augmente avec le nombre d'éléments en cours.", 0.28, "figure",
     {"id": "fig-1-1", "label": "Figure 1.1", "page": 12, "section": "Partie 1 > Chapitre 2", "image": "images/atelier-fig-1-1.png",
      "legende": "Le délai augmente avec le travail en cours.", "texte_alternatif": "Courbe inventée du délai selon le travail en cours."}),
    ("atelier-des-flux.md", 4, "Partie 2 > Chapitre 3", "Les accents ne comptent pas : équipe, équipé et equipe se retrouvent par la même requête.", 0.40, "texte", {}),
    ("discovery-notes.md", 0, "Chapter 1", "A discovery hypothesis states the risk we want to reduce before building anything.", 1.00, "texte", {}),
    ("discovery-notes.md", 1, "Chapter 1", "Run the cheapest experiment that can prove the hypothesis wrong.", 1.05, "texte", {}),
    ("discovery-notes.md", 2, "Chapter 2", "Interviews reveal the user need; a prototype tests whether the solution is usable.", 1.10, "texte", {}),
    ("discovery-notes.md", 3, "Chapter 2", "Figure 2.1: the hypothesis loop from assumption to decision.", 1.02, "figure",
     {"id": "fig-2-1", "label": "Figure 2.1", "page": 30, "section": "Chapter 2", "image": "images/discovery-fig-2-1.png",
      "legende": "The hypothesis loop."}),
    ("billet-recent.md", 0, "Introduction", "Ce billet récent explique comment prévoir une date de livraison à partir du débit.", 0.22, "texte", {}),
    ("billet-recent.md", 1, "Introduction", "Une prévision honnête donne une fourchette et dit ce qu'elle ignore.", 0.35, "texte", {}),
    ("billet-ancien.md", 0, "Introduction", "An old post: run small experiments, learn, and write the result down.", 1.01, "texte", {}),
    ("billet-ancien.md", 1, "Introduction", "Experiments without a decision rule produce stories, not evidence.", 1.12, "texte", {}),
    ("article-propre.md", 0, "Introduction", "Mon point de vue sur le coaching d'équipe et la posture du Scrum Master.", 0.60, "texte", {}),
]

KEYWORD_ANGLE = {"flux": 0.22, "flow": 0.22, "débit": 0.24, "prévisibilité": 0.25, "délai": 0.28, "équipe": 0.40,
                 "discovery": 1.02, "hypothesis": 1.02, "hypothèse": 1.02, "experiment": 1.05, "expérience": 1.05,
                 "interview": 1.10, "coaching": 0.60}


def fake_embed(texts: list[str]) -> np.ndarray:
    rows = []
    for text in texts:
        low = text.lower()
        angle = next((a for word, a in KEYWORD_ANGLE.items() if word in low), 0.7)
        rows.append(vector(angle))
    return np.vstack(rows)


def chunk_blob(angle: float) -> bytes:
    return vector(angle).astype(np.float16).tobytes()


def expected_counts() -> dict:
    return {"books": len(BOOKS), "chunks": len(CHUNKS), "figures": sum(1 for c in CHUNKS if c[5] == "figure"),
            "collections": {"flow": 1, "tech": 1, "produit": 1, "watch": 3, watch_paths.OWN_COLLECTION: 1}}   # « veille » compté comme « watch »
