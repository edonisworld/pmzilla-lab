"""
PMZilla Lab — table de classement des livres : domaines et MAPPING.

Module commun à sort_by_domain.py (copie des livres par domaine) et à convert_books.py (--redo-figures retrouve
par cette table un Markdown dont le nom diffère de sa source). Une seule table : jamais de copie.

MAPPING : « chemin du Markdown, relatif au dossier qui contient Bibliotheque-MD/Livres - Ressources » -> codes de
domaine (chaîne vide = livre écarté). Les commentaires de MAPPING sont lus par dashboard.py (livres absents).
"""
import unicodedata

DOMAINS = {
    "P": "produit",
    "D": "flow",
    "O": "organisation",
    "F": "facilitation",
    "T": "tech",
}

R = "Livres - Ressources/"

# Table neutre de l'édition : trois livres inventés, dont un écarté comme doublon. Remplacez-les par vos propres livres :
# la clé est le chemin du Markdown (R + « Dossier/Nom du livre.md »), la valeur ses codes de domaine ("" = écarté).
MAPPING = {
    R + "Exemple/Le Guide du Phare Imaginaire - A. Auteur.md": "O",
    R + "Exemple/Cartographie des Marées.md": "DP",
    R + "Exemple/Cartographie des Marées (copie).md": "",  # doublon : on garde l'original
}


# Correspondance explicite source -> Markdown, pour les livres que ni le nom de fichier ni MAPPING ne relient à leur Markdown.
# Clé : chemin du livre source relatif au dossier des livres, avec son extension. Valeur : une clé de MAPPING.
SOURCES = {
    "01 Exemple/Le Guide du Phare Imaginaire.epub": R + "Exemple/Le Guide du Phare Imaginaire - A. Auteur.md",
    "01 Exemple/Cartographie des Marées.pdf": R + "Exemple/Cartographie des Marées.md",
}

# Sources que la conversion normale ignore. Clé : chemin du livre source, avec son extension. Valeur : la raison.
EXCLUSIONS = {
    "01 Exemple/Cartographie des Marées (copie).pdf": "doublon de « Cartographie des Marées » (voir SOURCES)",
    "01 Exemple/Notes de la semaine.pdf": "pas un livre : notes courtes",
}


def norm(text: str) -> str:
    # macOS écrit les accents des noms de fichiers en Unicode NFD (é = e + ´) : on compare en NFC.
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Forme comparable d'un nom : sans accents ni casse (« Équipes » = « equipes »)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()
