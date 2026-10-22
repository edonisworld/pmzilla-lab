"""Fausses valeurs de secrets des tests, construites à l'exécution par concaténation : aucun fichier suivi ne contient une valeur d'une
famille de tools/secret_scan.py (la garde du dépôt réel, test_depot_reel.py, le vérifie). Pas de préfixe `test_` : non collecté seul."""

CORPS = "aB3dE5gH7jK9mN2pQ4rS6tU8vW1xY0zC"


def cle_privee(genre="RSA "):
    return "-----" + "BEGIN " + genre + "PRIVATE" + " KEY" + "-----"


def cle_cloud():
    return "AK" + "IA" + "QWERTY12" + "34567890"


def jeton_github():
    return "gh" + "p_" + CORPS + "AbCd"


def jeton_github_fin():
    return "github" + "_pat_" + CORPS + "_" + "AbCd"


def cle_anthropic():
    return "sk" + "-ant-" + "api03-" + CORPS


def jeton_atlassian():
    return "AT" + "ATT" + "3xFpAbCdEf" + CORPS


def jeton_slack():
    return "xo" + "xb-" + "1234567890-" + "AbCdEfGhIj"


def adresse(mot_de_passe="Zx9Qw2Er7"):
    return "postgres" + "ql://" + "role" + ":" + mot_de_passe + "@" + "localhost:5432/base"


def mot_de_passe_labo(valeur="Zx9Qw2Er7", suffixe="_PMZILLA_FLOW"):
    return "PMZILLA_LAB_DB" + "_PASSWORD" + suffixe + "=" + valeur
