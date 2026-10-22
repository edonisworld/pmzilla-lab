"""Tests de la langue des messages de export_jira_api.py (--language fr|en), sur le faux serveur de test_export_jira_api.py.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v

Les refus de réglages (étiquette hors préfixe, durée de conservation) et du référentiel illisible viennent de flux_config.py et
de flow_organisation.py, en français seulement : ils ne sont pas dans ce parcours (testés dans test_referentiel_et_etiquettes.py).
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

from aide_couche_brute import MagasinMemoire     # noqa: E402
from export_jira_api_messages import CATALOGS    # noqa: E402
from messages import check_catalogs              # noqa: E402

ex, hj = base.ex, base.hj
ICI = Path(__file__).resolve().parent
REFERENCE_EN = ICI / "reference_en.md"
CHAMP = base.CHAMP
DECLAREES = ("declared_labels:\n  up_merge:\n    prefix: um-\n    labels: [um-legal, um-hotfix]\n"
             "  cycle:\n    prefix: cy-\n    labels: [cy-a, cy-b]\n")
REFERENTIEL = ("source_date: 2026-10-01\nsites: [Site 1]\ndepartments:\n  - name: Departement 1\n    site: Site 1\n    headcount: 9\n"
               "    teams: [Equipe A, Equipe B, Equipe D]\nteams:\n  - name: Equipe A\n    headcount: 3\n    jira_team_ids: ['1']\n"
               "  - name: Equipe B\n    headcount: 3\n    jira_team_ids: ['2']\n  - name: Equipe D\n    headcount: 3\n")
VERIF = "customfield_10009"
MOTS_FRANCAIS = re.compile(r"\b(le|la|les|des|du|pour|dans|sur|avec|équipe|semaine|jours|écartés|erreur|livrés|"
                           r"réglages|aucun|aucune|seulement|selon|ticket\(s\) renseigné)\b|[éèêàâçùôî]", re.IGNORECASE)



class Parcours(base.Base):
    """Un parcours complet, rejoué dans la langue demandée."""

    def parcours(self, *extra: str) -> str:
        blocs: list[str] = []
        self.faux.__init__()                                       # état neuf : un parcours peut être rejoué dans le même test
        self.magasin = MagasinMemoire()                            # couche brute neuve : les comptes de la base repartent de zéro
        shutil.rmtree(self.ws / "Flux-Lab" / "exports", ignore_errors=True)
        (self.ws / "Flux-Lab" / "equipes-assets.yaml").unlink(missing_ok=True)
        (self.ws / "Flux-Lab" / "organisation.yaml").unlink(missing_ok=True)
        (self.ws / "Flux-Lab" / "equipes-jira.yaml").unlink(missing_ok=True)
        self.ecrire_reglages()

        def lancer(nom: str, *argv: str) -> tuple[int, str]:
            code, sortie = self.lancer(*argv, *extra)
            sortie = sortie.replace(str(self.ws), "<ws>").replace(self.url, "<url>").replace(ex.dt.date.today().isoformat(), "<today>")
            blocs.append(f"## {nom} (exit {code})\n\n```\n{sortie.rstrip()}\n```\n")
            return code, sortie

        sortie_csv = lambda nom: str(self.ws / nom)
        lancer("export", "export")
        self.ecrire_reglages("jql_export: project = ABC\n")
        lancer("export without a team field", "export")
        tickets = copy.deepcopy(base.TICKETS)
        tickets["ABC-1"][VERIF] = {"value": "Yes"}
        tickets["ABC-2"][VERIF] = True
        self.faux.tickets = tickets
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_verification_field: {VERIF}\n")
        lancer("export with the retired verification setting", "export")
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        lancer("export, named queries", "export")
        lancer("export, one named query", "export", "--query", "a")
        lancer("export, full option", "export", "--full")
        lancer("export, unknown query", "export", "--query", "c")
        lancer("export, --output retired", "export", "--output", sortie_csv("e.csv"))
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        lancer("export, --query without jql_exports", "export", "--query", "a")
        for nom, extra_reglages in (("missing query", ""), ("invalid query name", "jql_exports:\n  'a b': project = AAA\n"),
                                    ("empty query", "jql_exports:\n  a: ''\n"), ("query list", "jql_exports: [x]\n"),
                                    ("invalid team field", "jql_export: p\nexport_team_field: 'a b'\n"),
                                    ("invalid points field", "jql_export: p\nexport_points_field: 'a b'\n"),
                                    ("unknown time zone", "jql_export: p\nexport_timezone: Nulle/Part\n")):
            self.ecrire_reglages(extra_reglages)
            lancer(f"settings, {nom}", "export")
        self.ecrire_reglages(jeton="classic")
        lancer("export, classic token", "export")
        lancer("fields, classic token", "fields", "--search", "a")
        self.ecrire_reglages(cloud=None)
        lancer("export, cloud id missing", "export")
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
        lancer("export, Assets objects without a source", "export")
        table = self.ws / "Flux-Lab" / "equipes-assets.yaml"
        catalogue = self.ws / "Flux-Lab" / "equipes-jira.yaml"
        catalogue.write_text("teams:\n  - name: Equipe Z\n    jira_team_ids: ['123']\n", encoding="utf-8")
        for t in self.faux.tickets.values():
            t[CHAMP] = [{"objectId": "123"}, {"objectId": "999"}]
        lancer("diagnose, with a catalogue", "diagnose")
        lancer("export, unknown teams", "export")
        catalogue.write_text("teams:\n  - name: Equipe Z\n    jira_team_ids: ['123']\n    obsolete: true\n", encoding="utf-8")
        lancer("export, obsolete team", "export")
        catalogue.unlink()
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
        catalogue.write_text("teams:\n  - name: Equipe A\n    jira_team_ids: ['1']\n  - name: Equipe B\n    jira_team_ids: ['2']\n"
                             "  - name: Equipe C\n    jira_team_ids: ['3']\n", encoding="utf-8")
        lancer("export, with the catalogue", "export")
        referentiel = self.ws / "Flux-Lab" / "organisation.yaml"
        referentiel.write_text(REFERENTIEL, encoding="utf-8")
        lancer("diagnose, with the referential and the catalogue", "diagnose")
        table.write_text("equipes: {'1': Equipe A, '2': Equipe B, '3': Equipe C}\n", encoding="utf-8")
        lancer("export, referential, catalogue and former table present", "export")
        table.unlink()
        catalogue.write_text("teams:\n  - name: Equipe Z\n    jira_team_ids: ['1', '9']\n", encoding="utf-8")
        lancer("export, referential and catalogue share an identifier", "export")
        lancer("export, strict teams", "export", "--strict-teams")
        catalogue.write_text("teams:\n  - name: Equipe A\n    jira_team_ids: ['1', '9']\n", encoding="utf-8")
        lancer("export, catalogue team named like a referential team", "export")
        catalogue.unlink()
        referentiel.unlink()
        table.write_text("equipes: {'1': Equipe A, '2': Equipe B, '3': Equipe C}\n", encoding="utf-8")
        lancer("diagnose, with the former table only", "diagnose")
        lancer("export, former table only", "export")
        table.unlink()

        self.faux.tickets = copy.deepcopy(base.TICKETS)
        self.faux.tickets["ABC-1"]["labels"] = ["cy-a", "um-legal", "um-hotfix", "cy-renamed", "other"]
        self.faux.tickets["ABC-1"]["fixVersions"] = [{"name": "v1"}]
        self.faux.tickets["ABC-2"]["labels"] = ["cy-renamed"]
        self.ecrire_reglages("jql_export: project = ABC\n" + DECLAREES)
        lancer("export, declared labels (not requested any more)", "export")
        self.ecrire_reglages("jql_export: project = ABC\nretention:\n  period_days: 30\n")
        lancer("export, rows past the retention rule", "export")
        self.ecrire_reglages()
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
        self.assertIn("couche brute :", defaut)
        self.assertNotIn("raw layer:", defaut)

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

    def test_l_equipe_inconnue_enregistree_ne_depend_pas_de_la_langue(self):
        (self.ws / "Flux-Lab" / "equipes-jira.yaml").write_text("teams:\n  - name: Equipe Z\n    jira_team_ids: ['123']\n", encoding="utf-8")
        for t in self.faux.tickets.values():
            t[CHAMP] = [{"objectId": "999"}]
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("team identifiers in neither the referential nor the catalogue", sortie)
        self.assertIn("(équipe inconnue)", repr(self.magasin.instantanes))


if __name__ == "__main__":
    unittest.main()
