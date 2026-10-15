"""Sous-commande `flux_jira.py cycles` (R-58, tâche 9.3) : lecture de la base seulement, rapports, refus, langue, chaînes distinctives.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Lancements dans le processus (aide_espace.py) avec un faux flow_store : aucune base, aucune connexion, aucun appel à Jira. La lecture SQL
est testée dans tests/flow_store (avec base, sautée sans elle). Specs jira-flow-reports (« Subcommands and former names »,
« Labels and versions absent from the flow report »), jira-flow-cycles (« Cycles report from the database »), jira-flow-labels
(« Jira labels only »).
"""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from aide_espace import AvecEspace, faux_store, fj  # noqa: E402

UTC = dt.timezone.utc
REGLAGES = """export_timezone: Etc/GMT-2
cycles:
  2026-C1:
    fix_version: ZZVERSION-alpha
    start: 2026-01-05
    end: 2026-02-27
    up_merge_provision: 0.1
  2026-C2:
    fix_version: ZZVERSION-beta
    start: 2026-03-02
    end: 2026-04-24
patches:
  2026-Q1: [ZZPATCH-alpha]
declared_labels:
  up_merge:
    prefix: ZZUM-
    labels: [ZZUM-legal, ZZUM-hotfix]
  cycle:
    prefix: ZZCY-
    labels: [ZZCY-sujet]
  epic_review:
    prefix: ZZER-
    labels: [ZZER-revue]
discovery_workflow:
  columns:
    A cadrer: [Draft]
    Valide: [Approved]
  start_column: A cadrer
  review_passed_columns: [Valide]
  validated_on: 2026-09-01
"""
CLE_DISTINCTIVE = "ZZKEY-77"


def element(resolu=None, versions=(), labels=(), type_="Story", transitions=()):
    ajout = dt.datetime(2026, 1, 1, tzinfo=UTC)
    return {"cle": CLE_DISTINCTIVE, "projet": "ZZKEY", "type": type_, "etat": "Done", "resolu": resolu, "motif": "Done",
            "labels": [(nom, ajout, None) for nom in labels], "versions": [(v, ajout, None) for v in versions],
            "transitions": list(transitions)}


def elements_du_jeu():
    livres = [element(dt.date(2026, 2, 10), ["ZZVERSION-alpha"]) for _ in range(20)]
    up = [element(dt.date(2026, 2, 12), ["ZZPATCH-alpha"], ["ZZUM-legal"]) for _ in range(5)]
    deux = [element(dt.date(2026, 2, 13), [], ["ZZUM-legal", "ZZUM-hotfix"])]
    etiquette = [element(None, [], ["ZZCY-sujet"])]
    inconnue = [element(None, ["ZZVERSION-gamma"])]
    return livres + up + deux + etiquette + inconnue


class Base(AvecEspace):
    def setUp(self):
        super().setUp()
        self.ecrire("flux.yaml", REGLAGES)
        self.appels = []
        self.store = faux_store(lire_donnees_cycles=self.lire)
        self.elements = elements_du_jeu()

    def lire(self, settings, etiquettes_revue):
        self.appels.append((settings, etiquettes_revue))
        return self.elements

    def cycles(self, *plus, store="defaut"):
        return self.lancer("cycles", "--name", "serie", "--today", "2026-05-04", *plus,
                           store=self.store if store == "defaut" else store)


class Rapports(Base):
    def test_ecrit_markdown_et_json_nommes_d_apres_la_serie_et_le_jour(self):
        code, console, _ = self.cycles()
        self.assertIsNone(code, console)
        self.assertEqual(sorted(p.name for p in self.rapports.iterdir()), ["cycles-serie-2026-05-04.json", "cycles-serie-2026-05-04.md"])
        r = json.loads(self.lire_rapport("cycles-serie-2026-05-04.json"))
        self.assertEqual([c["cle"] for c in r["cycles"]], ["2026-C1", "2026-C2"])
        c1 = r["cycles"][0]
        self.assertEqual((c1["livres"], c1["up_merge"]["resolus"], c1["up_merge"]["part"], c1["up_merge"]["par_patch"]),
                         (20, 5, 5 / 25, {"2026-Q1": 5}))
        self.assertEqual(c1["up_merge"]["provision"], 0.1)
        self.assertEqual(c1["up_merge"]["deux_etiquettes"], 1)
        self.assertEqual(r["etiquette_cycle_sans_cycle"], 1)
        self.assertEqual(r["versions_non_mappees"], {"versions": 1, "tickets": 1})

    def test_la_serie_absente_donne_un_nom_sans_serie(self):
        code, _, _ = self.lancer("cycles", "--today", "2026-05-04", store=self.store)
        self.assertIsNone(code)
        self.assertTrue((self.rapports / "cycles-2026-05-04.md").exists())

    def test_la_lecture_recoit_les_reglages_et_les_etiquettes_epic_review_declarees(self):
        self.cycles()
        self.assertEqual(len(self.appels), 1)
        settings, revue = self.appels[0]
        self.assertEqual(revue, ["ZZER-revue"])
        self.assertEqual(settings["export_fuseau"], "Etc/GMT-2")

    def test_console_deux_etiquettes_phrase_cle_sans_cle_de_ticket(self):
        """Scénario « Two labels » : la console imprime la phrase de la conception D19 avec le compte, aucune clé."""
        _, console, _ = self.cycles()
        self.assertIn("éléments d'up-merge à deux étiquettes : 1", console)
        _, console_en, _ = self.cycles("--language", "en")
        self.assertIn("up-merge items with two labels: 1", console_en)
        self.assertNotIn("ZZKEY", console + console_en)

    def test_perimetre_filtre_par_projet(self):
        self.elements = [{**e, "projet": "AUTRE"} for e in self.elements[:3]] + self.elements[3:]
        self.cycles("--scope", "ZZKEY")
        c1 = json.loads(self.lire_rapport("cycles-serie-2026-05-04.json"))["cycles"][0]
        self.assertEqual(c1["livres"], 17)


class SortiesSansValeurDistinctive(Base):
    """Exigence « Labels and versions absent from the flow report » (cycles) et « Version numbers never in outputs »."""

    def test_ni_cle_ni_version_ni_etiquette_en_sortie(self):
        for langue in ("fr", "en"):
            self.elements = elements_du_jeu() + [element(dt.date(2026, 2, 5), [], ["ZZER-revue"], "Epic",
                                                         [(dt.datetime(2026, 2, 4, tzinfo=UTC), "New", "Draft")])]
            _, console, erreur = self.cycles("--language", langue)
            sorties = console + erreur + self.lire_rapport("cycles-serie-2026-05-04.md") + self.lire_rapport("cycles-serie-2026-05-04.json")
            for chaine in ("ZZKEY", "ZZVERSION", "ZZPATCH", "ZZUM", "ZZCY", "ZZER", "Draft", "Approved"):
                self.assertNotIn(chaine, sorties, f"{chaine} {langue}")

    def test_le_rapport_ne_contient_aucun_numero_de_version_ni_cle_de_ticket(self):
        self.cycles()
        md = self.lire_rapport("cycles-serie-2026-05-04.md")
        self.assertIsNone(re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", re.sub(r"\b20\d\d-(C[1-6]|EOY|Q[1-4])\b", "", md)))


class Refus(Base):
    def test_fichier_csv_refuse_avant_toute_lecture(self):
        """Scénario « CSV files given » : arrêt avec « no CSV file may be given », code 1, la base n'est pas lue."""
        csv = self.flux / "export.csv"
        csv.write_text("Issue key\nPROJ-1\n", encoding="utf-8")
        for langue, attendu in (("fr", "aucun fichier CSV ne doit être donné"), ("en", "no CSV file may be given")):
            code, _, _ = self.lancer("cycles", str(csv), "--language", langue, store=faux_store(
                lire_donnees_cycles=mock.Mock(side_effect=AssertionError("la base ne doit pas être lue"))))
            self.assertIsInstance(code, str)                      # message dans l'exception : code de sortie 1
            self.assertIn(attendu, code)
        self.assertFalse(self.rapports.exists())

    def test_option_source_inexistante(self):
        code, _, erreur = self.cycles("--source", "csv")
        self.assertEqual(code, 2)

    def test_sans_cycle_dans_les_reglages_arret_avant_la_base(self):
        self.ecrire("flux.yaml", "export_timezone: Etc/GMT-2\n")
        code, _, _ = self.cycles(store=faux_store(lire_donnees_cycles=mock.Mock(side_effect=AssertionError("base"))))
        self.assertIsInstance(code, str)
        self.assertIn("Aucun cycle", code)
        self.assertFalse(self.rapports.exists())

    def test_reglage_de_cycles_invalide_arret_code_1_sans_la_valeur(self):
        self.ecrire("flux.yaml", REGLAGES.replace("start: 2026-03-02", "start: 2026-03-04"))      # un mercredi
        code, _, _ = self.cycles()
        self.assertIsInstance(code, str)
        self.assertIn("cycles.2026-C2.start", code)
        self.assertNotIn("2026-03-04", code)

    def test_base_injoignable_message_clair_code_1(self):
        class ErreurBase(Exception):
            pass
        code, _, _ = self.cycles(store=faux_store(lire_donnees_cycles=mock.Mock(side_effect=ErreurBase("refusée"))))
        self.assertEqual(code, "Base de données : lecture impossible. refusée")

    def test_fuseau_inconnu(self):
        self.ecrire("flux.yaml", REGLAGES.replace("Etc/GMT-2", "Nulle/Part"))
        code, _, _ = self.cycles()
        self.assertIsInstance(code, str)
        self.assertIn("export_timezone", code)


class Etiquettes(Base):
    def test_section_d_etiquettes_nommee_etiquettes_jira(self):
        """Scénario « Report wording » : la section d'étiquettes est intitulée « Jira labels » (« étiquettes Jira » en français)."""
        self.cycles("--language", "en")
        self.assertIn("## Up-merge and cycle (Jira labels)", self.lire_rapport("cycles-serie-2026-05-04.md"))
        self.cycles()
        self.assertIn("## Up-merge et cycle (étiquettes Jira)", self.lire_rapport("cycles-serie-2026-05-04.md"))

    def test_aucune_etiquette_non_jira_aucun_appel_confluence(self):
        source = (Path(fj.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("confluence", source.lower())


class VersionDeBase(Base):
    def test_entete_du_cycle_marque_et_pas_d_autre(self):
        """Scénarios « No flag » et « C1 flagged »."""
        self.cycles()
        self.assertNotIn("version de base", self.lire_rapport("cycles-serie-2026-05-04.md"))
        self.ecrire("flux.yaml", REGLAGES.replace("    fix_version: ZZVERSION-alpha\n", "    fix_version: ZZVERSION-alpha\n    base_version: true\n"))
        self.cycles()
        md = self.lire_rapport("cycles-serie-2026-05-04.md")
        self.assertIn("## 2026-C1 (version de base)", md)
        self.assertIn("## 2026-C2\n", md)
        self.cycles("--language", "en")
        self.assertIn("## 2026-C1 (base version)", self.lire_rapport("cycles-serie-2026-05-04.md"))


class Langue(Base):
    def test_rapport_anglais_sans_reste_de_francais_et_json_identique(self):
        self.cycles()
        fr_json = self.lire_rapport("cycles-serie-2026-05-04.json")
        self.cycles("--language", "en")
        md = self.lire_rapport("cycles-serie-2026-05-04.md")
        self.assertTrue(md.startswith("# Cycles: serie, as of 2026-05-04"))
        self.assertIsNone(re.search(r"[éèêàâùûôîç]|\b(les|des|dans|sans|pour|livrés|visés)\b", md), md)
        self.assertEqual(self.lire_rapport("cycles-serie-2026-05-04.json"), fr_json)


class Aide(unittest.TestCase):
    def test_cycles_est_liste_avec_les_autres_sous_commandes(self):
        """Scénario « Cycles listed »."""
        import contextlib
        import io
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), self.assertRaises(SystemExit) as arret:
            fj.main(["--help"])
        self.assertEqual(arret.exception.code, 0)
        aide = sortie.getvalue()
        for nom in ("statuses", "compute", "compare", "config", "cycles"):
            self.assertIn(nom, aide)


if __name__ == "__main__":
    unittest.main()
