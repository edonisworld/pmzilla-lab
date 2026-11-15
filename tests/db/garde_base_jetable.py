"""Garde des tests avec base (test-speed-2, D1), seule : aucune création de fichier, aucune variable d'environnement posée, aucune
connexion à l'import. tests/db/test_db.py et le chargeur du jeu synthétique de Mothra (tests/mothra_donnees/) l'importent tous deux :
une seule règle pour décider qu'une base jetable peut être utilisée.

Seul effet à l'import : tools/ est ajouté au chemin des modules (pour importer db), une fois.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "tools") not in sys.path:
    sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402

VARIABLE_REPERE = "DBTEST_PORT"   # posée par tools/dbtest.sh : le port de son conteneur jetable (test-speed-2, D1)
PORT_STANDARD = 5432


def _port_valide(texte: str | None) -> int | None:
    """Une seule règle de port (test-db-guards, D1) : forme décimale simple seulement (chiffres ASCII, sans signe, sans espace, sans
    zéro en tête, de 1 à 65535), rendue comme nombre ; toute autre forme rend None. Même règle que tools/dbtest.sh."""
    if texte is None or re.fullmatch(r"[1-9][0-9]{0,4}", texte, re.ASCII) is None:
        return None
    nombre = int(texte)
    return nombre if nombre <= 65535 else None


def base_jetable_disponible(env=None, connecter=None) -> bool:
    """Garde des tests avec base (test-speed-2, D1) : vrai seulement si toutes les conditions tiennent, dans cet ordre, et sans
    aucune connexion avant la dernière : psycopg importable ; DBTEST_PORT et le port de connexion (PMZILLA_LAB_DB_PORT) sont tous deux
    de forme décimale simple (chiffres ASCII, sans signe, sans espace, sans zéro en tête, de 1 à 65535, test-db-guards D1) ; le repère
    n'est pas 5432 ; le port de connexion lui est égal en nombre ; l'adresse (PMZILLA_LAB_DB_URL), si elle existe, vise ce port en
    nombre ; le mot de passe est non vide ; la connexion (délai de deux secondes) réussit. La vraie base, sur 5432 ou sur son port
    configuré, n'est donc jamais utilisée."""
    env = os.environ if env is None else env
    connecter = db.connect if connecter is None else connecter
    if db.psycopg is None:
        return False
    repere = _port_valide(env.get(VARIABLE_REPERE))
    if repere is None or repere == PORT_STANDARD or _port_valide(env.get("PMZILLA_LAB_DB_PORT")) != repere:
        return False
    adresse = env.get(db.VARIABLE_URL)
    if adresse:
        try:
            port_adresse = urlsplit(adresse).port
        except ValueError:
            return False
        if port_adresse is None or port_adresse != repere:
            return False
    mot_de_passe = env.get(db.VARIABLE_MOT_DE_PASSE)
    if not mot_de_passe:
        return False
    try:
        connecter(adresse or db.url_par_defaut(), password=mot_de_passe, timeout=2, autocommit=True).close()
        return True
    except db.ErreurBase:
        return False
