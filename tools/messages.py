"""PMZilla Lab : catalogues de messages par langue, communs aux scripts du lot 3 (plan de la version anglaise, 3 et 6).

Chaque script garde ses messages dans un catalogue `{langue: {clé: texte}}` (module `<script>_messages.py`). Le français
est la langue de référence : ses textes sont ceux que les rapports et les tests actuels produisent, à l'octet près. Un
texte porte des champs `{nom}` remplis par `str.format`. Une clé absente de l'anglais retombe sur le français (jamais
d'erreur en cours de rapport) ; le test `check_catalogs` du module de chaque script signale l'écart avant.

    from messages import Messages, add_language_option
    t = Messages(CATALOGS, args.language)
    t("coverage", with_=3, total=4)

Aucune dépendance, aucun accès à Flux-Lab/ ni à Jira.
"""
from __future__ import annotations

import argparse
import string

LANGUAGES = ("fr", "en")
DEFAULT_LANGUAGE = "fr"


class Messages:
    """Messages d'une langue, avec repli sur le français."""

    def __init__(self, catalogs: dict[str, dict[str, str]], language: str = DEFAULT_LANGUAGE):
        if language not in catalogs:
            raise ValueError(f"langue inconnue : {language!r} (attendu : {', '.join(sorted(catalogs))})")
        self.language = language
        self.catalogs = catalogs

    def __call__(self, key: str, **values) -> str:
        texte = self.catalogs[self.language].get(key)
        if texte is None:
            texte = self.catalogs[DEFAULT_LANGUAGE][key]          # KeyError si la clé n'existe même pas en français
        return texte.format(**values) if values or "{" in texte else texte

    def other(self, language: str) -> "Messages":
        return Messages(self.catalogs, language)


def fields(text: str) -> set[str]:
    """Noms des champs `{nom}` d'un texte de catalogue."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def check_catalogs(catalogs: dict[str, dict[str, str]]) -> list[str]:
    """Écarts entre les langues : clé manquante ou en trop, champs différents. Liste vide = catalogues cohérents."""
    problemes: list[str] = []
    reference = catalogs[DEFAULT_LANGUAGE]
    for language, catalog in catalogs.items():
        if language == DEFAULT_LANGUAGE:
            continue
        for key in sorted(set(reference) - set(catalog)):
            problemes.append(f"{language} : clé « {key} » absente")
        for key in sorted(set(catalog) - set(reference)):
            problemes.append(f"{language} : clé « {key} » absente du français")
        for key in sorted(set(reference) & set(catalog)):
            if fields(reference[key]) != fields(catalog[key]):
                problemes.append(f"{language} : champs de « {key} » différents du français "
                                 f"({sorted(fields(catalog[key]))} au lieu de {sorted(fields(reference[key]))})")
    return problemes


def add_language_option(parser: argparse.ArgumentParser) -> None:
    """`--language fr|en` (français par défaut). L'ancien `--langue` est refusé par flux_config.refuse_old_options."""
    parser.add_argument("--language", choices=LANGUAGES, default=DEFAULT_LANGUAGE,
                        help="langue du rapport et des messages (fr par défaut)")
