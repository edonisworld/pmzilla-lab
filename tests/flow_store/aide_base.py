"""Base jetable des tests de flow_store : création, migrations, insertion du jeu inventé sous le rôle pmzilla_flow.

La base jetable (port 55432) est celle de bash tools/dbtest.sh (installation.md, 14.5). La règle qui décide de l'utiliser est celle de tests/db/test_db.py
(base_jetable_disponible, test-speed-2 D1) : sans le repère DBTEST_PORT posé par ce script, les tests qui en ont besoin sont sautés. Le vrai
Trousseau n'est jamais interrogé : PMZILLA_LAB_DB_SECURITY_BIN pointe un faux binaire.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import stat
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

RACINE = Path(__file__).resolve().parents[2]
TOOLS = RACINE / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import db  # noqa: E402
import test_db  # noqa: E402  (la garde des tests avec base : une seule règle)

MESSAGE_SAUT = test_db.MESSAGE_SAUT
_DOSSIER = tempfile.TemporaryDirectory()
FAUX_SECURITY = Path(_DOSSIER.name) / "security_absent"
FAUX_SECURITY.write_text("#!/bin/sh\nexit 44\n")
FAUX_SECURITY.chmod(FAUX_SECURITY.stat().st_mode | stat.S_IXUSR)

URL_BASE = os.environ.get(db.VARIABLE_URL) or db.url_par_defaut()
MOT_DE_PASSE = os.environ.get(db.VARIABLE_MOT_DE_PASSE)


BASE_DISPONIBLE = test_db.base_jetable_disponible()


def url_vers(nom_base: str) -> str:
    return urlunsplit(urlsplit(URL_BASE)._replace(path="/" + nom_base))


class AvecBase(unittest.TestCase):
    """Chaque test a sa base pmzilla_test_<hex>, migrée, supprimée à la fin. self.env : environnement des sous-processus."""

    def setUp(self):
        if not BASE_DISPONIBLE:
            self.skipTest(MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(URL_BASE, password=MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = url_vers(self.nom_base)
        self.conn = db.connect(self.url, password=MOT_DE_PASSE)
        db.migrer(self.conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.conn.commit()
        self.env = {db.VARIABLE_URL: self.url, db.VARIABLE_MOT_DE_PASSE: MOT_DE_PASSE, db.VARIABLE_SECURITY: str(FAUX_SECURITY)}
        patch = unittest.mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)

    def _supprimer(self):
        with contextlib.suppress(Exception):
            self.conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def inserer(self, liste: list[dict], liens_base: list, transitions: list, fuseau: str = "Europe/Paris",
                avec_historique: bool | list[str] = True) -> None:
        """Lignes SQL du jeu, sous le rôle pmzilla_flow : heures locales naïves converties dans le fuseau d'export."""
        c = self.conn
        c.execute("SET ROLE pmzilla_flow")
        ids: dict[str, int] = {}
        for t in liste:
            for nom in t["equipes"]:
                if nom not in ids:
                    ids[nom] = c.execute("INSERT INTO flow.teams (name) VALUES (%s) RETURNING id", (nom,)).fetchone()[0]
        for t in liste:
            cle = t["cle"]
            c.execute(
                "INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, resolution, "
                "status_category_changed_at, story_points, updated_at, team_id, parent_key) VALUES "
                "(%s, %s, %s, %s, %s, %s::timestamp AT TIME ZONE %s, %s::timestamp AT TIME ZONE %s, %s, "
                "%s::timestamp AT TIME ZONE %s, %s, now(), %s, %s)",
                (cle, cle.rsplit("-", 1)[0], t["type"], t["etat"], t["categorie"], t["cree"], fuseau, t["resolu"], fuseau,
                 t["motif"] or None, t["debut"], fuseau, t["points"], ids[t["equipes"][0]] if t["equipes"] else None,
                 t["parent"] or None))
            for position, nom in enumerate(dict.fromkeys(t["equipes"]), start=1):
                c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES (%s, %s, %s)",
                          (cle, ids[nom], position))
        for source, cible, typ, direction in liens_base:
            c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, %s, %s)",
                      (source, cible, typ, direction))
        for cle, instant, depart, arrivee in transitions:
            c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) VALUES (%s, %s, %s, %s)",
                      (cle, instant, depart, arrivee))
        if avec_historique:       # tous les tickets du jeu ont une entrée dans le cache de test (avec ou sans transition)
            cles = [t["cle"] for t in liste] if avec_historique is True else list(avec_historique)
            c.execute("UPDATE flow.issues SET has_history = true WHERE key = ANY(%s)", (cles,))
        c.execute("RESET ROLE")
        c.commit()
