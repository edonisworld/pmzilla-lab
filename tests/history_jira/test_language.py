"""Tests de la langue des messages de history_jira.py (--language fr|en), sur le faux serveur de test_history_jira.py.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/history_jira -v

Le même parcours (connexion, collecte, contrôle, erreurs) est lancé en anglais et comparé à un instantané versionné
(reference_en.md) ; pour le régénérer après un changement voulu : PMZILLA_UPDATE_SNAPSHOTS=1. Aucune donnée réelle.
"""
import datetime as dt
import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base           # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from history_jira_messages import CATALOGS    # noqa: E402
from messages import check_catalogs           # noqa: E402

ICI = Path(__file__).resolve().parent
REFERENCE_EN = ICI / "reference_en.md"
MOTS_FRANCAIS = re.compile(r"\b(le|la|les|des|du|pour|dans|sur|avec|équipe|semaine|jours|tickets? lus|écartés|erreur|"
                           r"livrés|cache ignoré|réglages|aucun|aucune|seulement|selon)\b|[éèêàâçùôî]", re.IGNORECASE)


class Parcours(base.Base):
    """Un parcours complet, rejoué dans la langue demandée."""

    def parcours(self, *extra: str) -> str:
        with mock.patch.object(base.hj, "aujourd_hui", lambda: dt.date(2026, 10, 13)):
            return self._parcours(*extra)

    def _parcours(self, *extra: str) -> str:
        blocs: list[str] = []
        self.faux.__init__()                                    # état neuf : un parcours peut être rejoué dans le même test
        self.magasin.__init__()                                 # base fictive neuve (le faux flow_store est lié à cet objet)
        self.ecrire_reglages("scopes")

        def lancer(nom: str, *argv: str) -> tuple[int, str]:
            code, sortie = self.lancer(*argv, *extra)
            sortie = sortie.replace(str(self.ws), "<ws>").replace(self.url, "<url>")
            blocs.append(f"## {nom} (exit {code})\n\n```\n{sortie.rstrip()}\n```\n")
            return code, sortie

        lancer("test, connection", "test")
        attendu, self.faux.attendu = self.faux.attendu, "Basic autre"
        lancer("test, access denied", "test")
        self.faux.attendu = attendu
        reglages = (self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8")
        flux = self.ws / "Flux-Lab" / "flux.yaml"
        flux.write_text("jira_email: a@example.org\n", encoding="utf-8")
        lancer("missing settings", "test")
        flux.write_text("jira_site: http://exemple.atlassian.net\njira_email: a@example.org\njira_token_type: scoped\n"
                        f"jira_cloud_id: {base.CLOUD_ID}\n", encoding="utf-8")
        lancer("remote http", "test")
        flux.write_text(f"jira_site: {self.url}\njira_email: a@example.org\njira_token_type: autre\n", encoding="utf-8")
        lancer("token type", "test")
        self.ecrire_reglages("classique")
        jeton, base.hj.lire_jeton = base.hj.lire_jeton, lambda: self.fail("le Trousseau ne doit pas être lu")
        try:
            lancer("test, classic token", "test")
            lancer("collect, classic token", "collect", self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)]))
        finally:
            base.hj.lire_jeton = jeton
        self.ecrire_reglages("scopes", cloud=None)
        lancer("test, cloud id missing", "test")
        self.ecrire_reglages("scopes", cloud="a/b")
        lancer("test, cloud id with path characters", "test")
        self.ecrire_reglages("scopes")
        self.faux.cloud_site = "autre-identifiant"
        lancer("test, cloud id differs from the site's", "test")
        self.faux.cloud_site = base.CLOUD_ID
        self.faux.refus = {"history": 403}
        lancer("test, missing scope on history", "test")
        self.faux.refus = {"search": 403, "fields": 403}
        lancer("test, missing scopes on search and fields", "test")
        self.faux.refus = {}
        self.ecrire_reglages("scopes", expiration="2026-10-23")
        lancer("test, token expires soon", "test")
        self.ecrire_reglages("scopes", expiration="2026-10-01")
        lancer("test, token expiry passed", "test")
        self.faux.refus = {"fields": 403}
        lancer("test, token expiry passed and a refused call", "test")
        self.faux.refus = {}
        self.ecrire_reglages("scopes", expiration=None)
        lancer("test, no token expiry date", "test")
        self.ecrire_reglages("scopes")
        flux.write_text(reglages, encoding="utf-8")

        lignes = self.inventer(5, termines=("ABC-1", "ABC-2", "ABC-3", "ABC-4"))
        self.magasin.stock.clear()
        lancer("collect, empty database", "collect")
        export = self.ecrire_export(lignes)
        lancer("collect, bulk mode", "collect", export)
        lancer("collect, everything already collected", "collect", export)
        lancer("collect, --refresh", "collect", export, "--refresh")
        lancer("collect, --team", "collect", export, "--team", "Equipe Test")
        lancer("collect, unknown team", "collect", export, "--team", "Inconnue")
        resolu = self.magasin.stock["ABC-1"]["resolu"]
        self.magasin.stock["ABC-1"]["resolu"] = dt.datetime(2025, 1, 1, 10, 0, tzinfo=base.PARIS)
        lancer("collect, tickets past retention", "collect", "--refresh")
        self.magasin.stock["ABC-1"]["resolu"] = resolu
        self.faux.groupe = False
        self.faux.introuvables = {"ABC-2"}
        lancer("collect, ticket by ticket with one error", "collect", export, "--refresh")
        self.faux.groupe = True
        self.faux.introuvables = set()
        self.faux.attendu = "Basic autre"
        lancer("collect, access denied", "collect", export, "--refresh")
        self.faux.attendu = attendu
        lancer("collect, export file refused", "collect", str(self.ws / "export.csv"))
        for ticket in self.magasin.stock.values():
            ticket["equipes"] = []
        lancer("collect, --team without a team in the database", "collect", "--team", "x")

        def parcours_etats(*etats):
            return [(dt.datetime.fromisoformat(f"2026-03-0{n + 1}T10:00:00+02:00"), a, b)
                    for n, (a, b) in enumerate(zip(etats, etats[1:]))]
        for ticket in self.magasin.stock.values():
            ticket["equipes"] = ["Equipe Test"]
            ticket["cree"] = dt.datetime(2024, 1, 1, 9, 0, tzinfo=base.PARIS)
        self.magasin.transitions["ABC-1"] = parcours_etats("Open", "Definition", "Ready for Implementation", "Implementation", "Done")
        self.magasin.transitions["ABC-2"] = parcours_etats("Implementation", "Verification", "Done")
        self.magasin.transitions["ABC-3"] = []
        self.magasin.transitions["ABC-4"] = [(dt.datetime.fromisoformat("2026-03-01T10:00:00+02:00"), "Open", "Done")]
        self.magasin.transitions["ABC-5"] = parcours_etats("Open", "Closed")
        self.magasin.stock["ABC-6"] = {**self.magasin.stock["ABC-5"], "cle": "ABC-6", "a_historique": False}
        lancer("check", "check")
        lancer("check, --team", "check", "--team", "Equipe Test")
        lancer("check, --dormants removed", "check", "--dormants", "dormants.csv")
        lancer("check, --key", "check", "--key", "abc-2")
        lancer("check, unknown --key", "check", "--key", "ZZZ-9")
        lancer("check, export file refused", "check", str(self.ws / "export.csv"))
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            lancer("check, inside a Claude Code session", "check")
        for ticket in self.magasin.stock.values():
            ticket["a_historique"] = False
        lancer("check, no history in the database", "check")
        return "\n".join(["# history_jira.py, parcours de test\n"] + blocs)


class Langue(Parcours):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_sortie_anglaise_conforme_a_l_instantane(self):
        sortie = self.parcours("--language", "en")
        if os.environ.get("PMZILLA_UPDATE_SNAPSHOTS") == "1":
            REFERENCE_EN.write_text(sortie, encoding="utf-8")
        self.assertEqual(sortie, REFERENCE_EN.read_text(encoding="utf-8"))

    def test_pas_de_francais_dans_la_sortie_anglaise(self):
        for numero, ligne in enumerate(self.parcours("--language", "en").splitlines(), 1):
            self.assertIsNone(MOTS_FRANCAIS.search(ligne), f"ligne {numero} : {ligne}")

    def test_sans_option_la_sortie_est_francaise(self):
        defaut = self.parcours()
        self.assertIn("connexion OK", defaut)
        self.assertIn("Tickets lus :", defaut)
        self.assertNotIn("connection OK", defaut)

    def test_language_fr_explicite_donne_la_sortie_par_defaut(self):
        self.assertEqual(self.parcours("--language", "fr"), self.parcours())

    def test_ancienne_option_langue_refusee(self):
        code, sortie = self.lancer("test", "--langue", "en")
        self.assertEqual(code, 2, sortie)
        self.assertIn("« --langue » n'existe plus ; utiliser « --language »", sortie)

    def test_langue_inconnue_refusee(self):
        code, _ = self.lancer("test", "--language", "de")
        self.assertEqual(code, 2)

    def test_la_langue_ne_reste_pas_d_un_lancement_a_l_autre(self):
        self.assertIn("connection OK", self.lancer("test", "--language", "en")[1])
        self.assertIn("connexion OK", self.lancer("test")[1])


if __name__ == "__main__":
    unittest.main()
