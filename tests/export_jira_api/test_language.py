"""Tests de la langue des messages de export_jira_api.py (--language fr|en), sur le faux serveur de test_export_jira_api.py.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v

Le même parcours (export, diagnostic, champs, table des équipes écrite à la main, sous-commandes retirées, erreurs) est lancé en anglais et comparé à un
instantané versionné (reference_en.md) ; pour le régénérer après un changement voulu : PMZILLA_UPDATE_SNAPSHOTS=1.
Aucune donnée réelle.
"""
import copy
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_export_jira_api as base           # noqa: E402

from export_jira_api_messages import CATALOGS    # noqa: E402
from messages import check_catalogs              # noqa: E402

ex, hj = base.ex, base.hj
ICI = Path(__file__).resolve().parent
REFERENCE_EN = ICI / "reference_en.md"
CHAMP = base.CHAMP
VERIF = "customfield_10009"
MOTS_FRANCAIS = re.compile(r"\b(le|la|les|des|du|pour|dans|sur|avec|équipe|semaine|jours|écartés|erreur|livrés|"
                           r"réglages|aucun|aucune|seulement|selon|ticket\(s\) renseigné)\b|[éèêàâçùôî]", re.IGNORECASE)



class Parcours(base.Base):
    """Un parcours complet, rejoué dans la langue demandée."""

    def parcours(self, *extra: str) -> str:
        blocs: list[str] = []
        self.faux.__init__()                                       # état neuf : un parcours peut être rejoué dans le même test
        shutil.rmtree(self.ws / "Flux-Lab" / "exports", ignore_errors=True)
        (self.ws / "Flux-Lab" / "equipes-assets.yaml").unlink(missing_ok=True)
        self.ecrire_reglages()

        def lancer(nom: str, *argv: str) -> tuple[int, str]:
            code, sortie = self.lancer(*argv, *extra)
            sortie = sortie.replace(str(self.ws), "<ws>").replace(self.url, "<url>").replace(ex.dt.date.today().isoformat(), "<today>")
            blocs.append(f"## {nom} (exit {code})\n\n```\n{sortie.rstrip()}\n```\n")
            return code, sortie

        sortie_csv = lambda nom: str(self.ws / nom)
        lancer("export", "export", "--output", sortie_csv("api.csv"))
        self.ecrire_reglages("jql_export: project = ABC\n")
        lancer("export without a team field", "export", "--output", sortie_csv("b.csv"))
        tickets = copy.deepcopy(base.TICKETS)
        tickets["ABC-1"][VERIF] = {"value": "Yes"}
        tickets["ABC-2"][VERIF] = True
        self.faux.tickets = tickets
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_verification_field: {VERIF}\n")
        lancer("export with the verification column", "export", "--output", sortie_csv("c.csv"))
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        lancer("export, named queries", "export")
        lancer("export, one named query", "export", "--query", "a", "--output", sortie_csv("d.csv"))
        lancer("export, unknown query", "export", "--query", "c")
        lancer("export, --output with several queries", "export", "--output", sortie_csv("e.csv"))
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        lancer("export, --query without jql_exports", "export", "--query", "a")
        for nom, extra_reglages in (("missing query", ""), ("invalid query name", "jql_exports:\n  'a b': project = AAA\n"),
                                    ("empty query", "jql_exports:\n  a: ''\n"), ("query list", "jql_exports: [x]\n"),
                                    ("invalid team field", "jql_export: p\nexport_team_field: 'a b'\n"),
                                    ("invalid verification field", "jql_export: p\nexport_verification_field: 'a b'\n"),
                                    ("unknown time zone", "jql_export: p\nexport_timezone: Nulle/Part\n")):
            self.ecrire_reglages(extra_reglages)
            lancer(f"settings, {nom}", "export", "--output", sortie_csv("y.csv"))
        self.ecrire_reglages()
        attendu, self.faux.attendu = self.faux.attendu, "Basic autre"
        lancer("export, access denied", "export")
        lancer("fields, access denied", "fields", "--search", "a")
        self.faux.attendu = attendu

        lancer("diagnose", "diagnose")
        self.ecrire_reglages("jql_export: p\n")
        lancer("diagnose without a team field", "diagnose")
        self.ecrire_reglages("jql_export: project = ABC\nexport_team_field: customfield_99999\n")
        lancer("diagnose, field absent", "diagnose")
        self.ecrire_reglages()
        for cle, valeur in (("ABC-1", "texte"), ("ABC-2", None), ("ABC-3", []), ("ABC-9", 12.5)):
            self.faux.tickets[cle][CHAMP] = valeur
        lancer("diagnose, various shapes", "diagnose")
        self.faux.tickets["ABC-9"][CHAMP] = {"zz": 1, "aa": 2}
        self.faux.tickets["ABC-3"][CHAMP] = "12345"
        self.faux.tickets["ABC-2"][CHAMP] = [{"value": "x"}, "y"]
        lancer("diagnose, more shapes", "diagnose")
        for t in self.faux.tickets.values():
            t[CHAMP] = [{"workspaceId": "ws-secret", "id": "w:123", "objectId": "123"}]
        lancer("diagnose, Assets objects", "diagnose")
        lancer("export, Assets objects without a table", "export", "--output", sortie_csv("z.csv"))
        table = self.ws / "Flux-Lab" / "equipes-assets.yaml"
        table.write_text("equipes: {'123': 'Equipe Z'}\n", encoding="utf-8")
        for t in self.faux.tickets.values():
            t[CHAMP] = [{"objectId": "123"}, {"objectId": "999"}]
        lancer("diagnose, with a table", "diagnose")
        lancer("export, unknown teams", "export", "--output", sortie_csv("u.csv"))
        table.write_text("equipes: [pas, un", encoding="utf-8")
        lancer("export, unreadable table", "export", "--output", sortie_csv("v.csv"))
        table.unlink()
        self.faux.tickets = copy.deepcopy(base.TICKETS)
        self.faux.tickets["ABC-9"][CHAMP] = [{"value": "Equipe B"}]

        lancer("fields", "fields", "--search", "TEAM")
        lancer("fields, no match", "fields", "--search", "zzz")
        lancer("fields, empty text", "fields", "--search", "  ")
        champs, self.faux.champs = self.faux.champs, {"x": 1}
        lancer("fields, unexpected response", "fields", "--search", "a")
        self.faux.champs = champs

        self.faux.tickets = {}
        for cle, (objets, _) in base.TableEquipes.EQUIPES.items():
            ticket = base.champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200")
            ticket[CHAMP] = objets
            self.faux.tickets[cle] = ticket
        table.write_text("equipes: {'1': Equipe A, '2': Equipe B, '3': Equipe C}\n", encoding="utf-8")
        lancer("export, with the table", "export", "--output", sortie_csv("w.csv"))
        table.unlink()
        lancer("teams-table, retired", "teams-table", "m1.csv", "m2.csv")
        lancer("compare, retired", "compare", "m.csv", "a.csv", "--tolerance", "3.5")
        return "\n".join(["# export_jira_api.py, test run\n"] + blocs)


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
            # « (équipe inconnue) » est la valeur écrite dans le CSV (format de données) : elle reste française
            ligne = ligne.replace(ex.EQUIPE_INCONNUE, "")
            self.assertIsNone(MOTS_FRANCAIS.search(ligne), f"ligne {numero} : {ligne}")

    def test_sans_option_la_sortie_est_francaise(self):
        defaut = self.parcours()
        self.assertIn("Tickets : 4 ; pages : 1", defaut)
        self.assertIn("Fichier écrit", defaut)
        self.assertNotIn("File written", defaut)

    def test_language_fr_explicite_donne_la_sortie_par_defaut(self):
        self.assertEqual(self.parcours("--language", "fr"), self.parcours())

    def test_ancienne_option_langue_refusee(self):
        code, sortie = self.lancer("fields", "--search", "team", "--langue", "en")
        self.assertEqual(code, 2, sortie)
        self.assertIn("« --langue » n'existe plus ; utiliser « --language »", sortie)

    def test_langue_inconnue_refusee(self):
        code, _ = self.lancer("fields", "--search", "team", "--language", "de")
        self.assertEqual(code, 2)

    def test_la_langue_ne_reste_pas_d_un_lancement_a_l_autre(self):
        self.assertIn("field(s) out of", self.lancer("fields", "--search", "team", "--language", "en")[1])
        self.assertIn("champ(s) sur", self.lancer("fields", "--search", "team")[1])

    def test_l_equipe_inconnue_ecrite_dans_le_csv_ne_depend_pas_de_la_langue(self):
        (self.ws / "Flux-Lab" / "equipes-assets.yaml").write_text("equipes: {'123': 'Equipe Z'}\n", encoding="utf-8")
        for t in self.faux.tickets.values():
            t[CHAMP] = [{"objectId": "999"}]
        chemin = self.ws / "inconnues.csv"
        code, sortie = self.lancer("export", "--output", str(chemin), "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Unknown teams:", sortie)
        self.assertIn("(équipe inconnue)", chemin.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
