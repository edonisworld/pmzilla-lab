"""Sous-commande `flux_jira.py epics` (R-89, conception D1, D2, D11, D14, tâche 2.8) : codes de sortie et phrases clés dans les deux langues,
lignes de source Ready, rapport réduit sans correspondance validée, refus en session, fichiers CSV refusés, chaînes distinctives.

    bash tests/run_all.sh flux_jira

Lancements dans le processus (aide_espace.py) avec un faux flow_store : aucune base, aucune connexion, aucun appel à Jira. La lecture SQL
est testée dans tests/flow_store. Données et noms inventés.
"""
import contextlib
import io
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from aide_epics import epic, periode  # noqa: E402
from aide_espace import AvecEspace, faux_store, fj  # noqa: E402

EQUIPE = "Equipe Distinctive"
ETIQUETTES_DISTINCTIVES = ("zz-dom", "zc-un", "zc-deux", "zr-pret", "ze-revue", "zf-pris", "zf-non")
REGLAGES = """export_timezone: Etc/GMT+5
epic_types: [Epic]
excluded_resolutions: [Won't Do]
declared_labels:
  pilot_domain: {prefix: "zz-", labels: ["zz-dom"]}
  cycle: {prefix: "zc-", labels: ["zc-un", "zc-deux"], cycle_keys: {zc-un: 2026-C1, zc-deux: 2026-C2}}
  ready: {prefix: "zr-", labels: ["zr-pret"]}
  epic_review: {prefix: "ze-", labels: ["ze-revue"]}
  confirmation: {prefix: "zf-", labels: ["zf-pris", "zf-non"], meanings: {zf-pris: taken_in, zf-non: not_taken_in}}
cycles:
  2026-C1: {fix_version: ZZVERSION-alpha, start: 2026-01-05, end: 2026-02-27}
  2026-C2: {fix_version: ZZVERSION-beta, start: 2026-03-02, end: 2026-04-24}
discovery_workflow:
  columns:
    Idee: [s-idee]
    Revue: [s-revue]
    Pret: [s-pret]
  start_column: Idee
  review_passed_columns: [Pret]
  ready_column: Pret
  active_columns: [Idee, Revue]
  validated_on: 2026-01-02
"""
SORTIE = "epics-serie-2026-07-01"


def epics_du_jeu(n: int = 6, historique: bool = True, domaine: bool = True) -> list:
    liste = []
    for _ in range(n):
        e = epic("2026-01-12", etat="s-pret", equipes=(EQUIPE,), a_historique=historique,
                 transitions=[("2026-02-01", "s-idee", "s-pret")],
                 periodes=[periode("cycle", "2026-01-02", cycle="2026-C1"), periode("epic_review", "2026-01-20", "2026-01-25"),
                           periode("ready", "2026-02-01")])
        if not domaine:
            e["periodes"] = e["periodes"][1:]
        liste.append(e)
    return liste


class Base(AvecEspace):
    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("CLAUDECODE", None)
        self.ecrire("flux.yaml", REGLAGES)
        self.appels = []
        self.epics = epics_du_jeu()
        self.store = faux_store(lire_epics=self.lire)

    def lire(self, settings, motifs_exclus):
        self.appels.append((settings, motifs_exclus))
        return self.epics

    def epics_cmd(self, *plus, store="defaut"):
        return self.lancer("epics", "--name", "serie", "--today", "2026-07-01", *plus,
                           store=self.store if store == "defaut" else store)

    def json(self) -> dict:
        return json.loads(self.lire_rapport(SORTIE + ".json"))

    def md(self) -> str:
        return self.lire_rapport(SORTIE + ".md")


class Rapport(Base):
    def test_ecrit_markdown_et_json_et_le_dit(self):
        code, console, _ = self.epics_cmd()
        self.assertIsNone(code, console)
        self.assertEqual(sorted(p.name for p in self.rapports.iterdir()), [SORTIE + ".json", SORTIE + ".md"])
        self.assertIn("rapport de flux des épics écrit", console)
        _, console_en, _ = self.epics_cmd("--language", "en")
        self.assertIn("epic flow report written", console_en)

    def test_la_lecture_recoit_les_reglages_et_la_liste_des_resolutions_exclues(self):
        self.epics_cmd()
        self.assertEqual(len(self.appels), 1)
        settings, motifs = self.appels[0]
        self.assertEqual(settings["export_fuseau"], "Etc/GMT+5")
        self.assertEqual({m.casefold() for m in motifs}, {"won't do"})

    def test_la_serie_est_facultative(self):
        code, _, _ = self.lancer("epics", "--today", "2026-07-01", store=self.store)
        self.assertIsNone(code)
        self.assertTrue((self.rapports / "epics-2026-07-01.md").exists())

    def test_sections_et_lignes_du_json(self):
        self.epics_cmd()
        r = self.json()
        self.assertEqual(set(r["sections"]), {"idea_to_ready", "epic_review_passages", "planned_cycle", "epics_per_column", "age"})
        ligne = r["sections"]["idea_to_ready"]["rows"][0]
        self.assertEqual(ligne["row"], "pilot_domain")
        self.assertEqual(ligne["cells"]["total.atteints"], {"value": 6, "state": "ok"})
        self.assertEqual(ligne["cells"]["total.p50"], {"value": 20.0, "state": "ok"})
        self.assertEqual(r["sections"]["idea_to_ready"]["rows"][1]["team"], EQUIPE)
        self.assertEqual(r["coverage"], {"with_history": {"value": 6, "state": "ok"}, "epics": {"value": 6, "state": "ok"}})

    def test_la_console_ne_porte_que_des_comptes_du_domaine_et_les_phrases_cles(self):
        _, console, erreur = self.epics_cmd()
        self.assertIn("épics avec historique : 6 sur 6", console)
        self.assertNotIn(EQUIPE, console + erreur)
        self.assertIn(EQUIPE, self.md())
        self.assertIn(EQUIPE, self.lire_rapport(SORTIE + ".json"))

    def test_couverture_masquee_sous_cinq(self):
        self.epics = epics_du_jeu(3)
        _, console, _ = self.epics_cmd("--language", "en")
        self.assertIn("epics with history: masked of masked", console)
        self.assertIn("epics with history: masked of masked", self.md())
        self.assertIn("A count under five is written \"masked\"", self.md())       # le seuil reste dans l'introduction

    def test_couverture_partielle(self):
        self.epics = epics_du_jeu(7) + epics_du_jeu(5, historique=False)
        _, console, _ = self.epics_cmd("--language", "en")
        self.assertIn("epics with history: 7 of 12", console)

    def test_les_epics_hors_domaine_ne_sont_comptes_nulle_part(self):
        self.epics = epics_du_jeu(6) + epics_du_jeu(4, domaine=False)
        _, console, _ = self.epics_cmd("--language", "en")
        self.assertIn("epics with history: 6 of 6", console)


class SourceReady(Base):
    def test_etiquette_ready_configuree(self):
        _, console, _ = self.epics_cmd("--language", "en")
        self.assertIn("Ready source: Ready label", self.md())
        self.assertEqual(self.json()["ready_source"], "label")
        self.assertNotIn("Ready label not configured", console + self.md())

    def test_etiquette_ready_vide(self):
        self.ecrire("flux.yaml", REGLAGES.replace('ready: {prefix: "zr-", labels: ["zr-pret"]}', 'ready: {prefix: "zr-", labels: []}'))
        code, console, _ = self.epics_cmd("--language", "en")
        self.assertIsNone(code)
        md = self.md()
        for sortie in (console, md):
            self.assertIn("Ready label not configured: Ready column used", sortie)
        self.assertIn("Ready source: Ready column", md)
        self.assertEqual(self.json()["ready_source"], "column")
        _, console_fr, _ = self.epics_cmd()
        self.assertIn("étiquette Ready non configurée : colonne Ready utilisée", console_fr)
        self.assertIn("source de Ready : colonne Ready", self.md())

    def test_francais_etiquette_configuree(self):
        self.epics_cmd()
        self.assertIn("source de Ready : étiquette Ready", self.md())

    def test_role_ready_absent_meme_chose_qu_une_etiquette_vide(self):
        self.ecrire("flux.yaml", REGLAGES.replace('  ready: {prefix: "zr-", labels: ["zr-pret"]}\n', ""))
        code, console, _ = self.epics_cmd("--language", "en")
        self.assertIsNone(code)
        self.assertIn("Ready label not configured: Ready column used", console)


class ErreursEtRefus(Base):
    def test_fichier_csv_refuse_avant_toute_lecture(self):
        csv = self.flux / "export.csv"
        csv.write_text("Issue key\nPROJ-1\n", encoding="utf-8")
        boum = faux_store(lire_epics=mock.Mock(side_effect=AssertionError("la base ne doit pas être lue")))
        for langue, attendu in (("fr", "aucun fichier CSV ne doit être donné"), ("en", "no CSV file may be given")):
            code, _, _ = self.lancer("epics", str(csv), "--language", langue, store=boum)
            self.assertIsInstance(code, str)                      # message dans l'exception : code de sortie 1
            self.assertIn(attendu, code)
        self.assertFalse(self.rapports.exists())

    def test_refus_en_session_avant_toute_lecture_de_reglage(self):
        (self.flux / "flux.yaml").unlink()                       # aucun réglage à lire : le refus passe avant
        os.environ["CLAUDECODE"] = "1"
        boum = faux_store(lire_epics=mock.Mock(side_effect=AssertionError("la base ne doit pas être lue")))
        for langue, phrase in (("fr", "Refusé dans une session Claude Code"), ("en", "Refused inside a Claude Code session")):
            code, console, erreur = self.lancer("epics", "--language", langue, store=boum)
            self.assertEqual(code, 3)
            self.assertIn(phrase, console + erreur)
        self.assertFalse(self.rapports.exists())
        self.assertFalse((self.flux / "flux.yaml").exists())      # aucun fichier de réglages créé non plus

    def test_sans_cycle_arret_avant_la_base(self):
        self.ecrire("flux.yaml", "export_timezone: Etc/GMT+5\ndeclared_labels:\n  pilot_domain: {prefix: \"zz-\", labels: [\"zz-dom\"]}\n")
        code, _, _ = self.epics_cmd(store=faux_store(lire_epics=mock.Mock(side_effect=AssertionError("base"))))
        self.assertIsInstance(code, str)
        self.assertIn("Aucun cycle", code)
        self.assertFalse(self.rapports.exists())

    def test_reglages_invalides_cle_et_ligne_sans_valeur(self):
        self.ecrire("flux.yaml", REGLAGES.replace("active_columns: [Idee, Revue]", "active_columns: [Idee, ZZInconnue]"))
        code, _, _ = self.epics_cmd()
        self.assertIsInstance(code, str)
        self.assertIn("discovery_workflow.active_columns", code)
        self.assertNotIn("ZZInconnue", code)
        self.assertEqual(self.appels, [])

    def test_aucune_etiquette_de_domaine(self):
        self.ecrire("flux.yaml", REGLAGES.replace('  pilot_domain: {prefix: "zz-", labels: ["zz-dom"]}\n', ""))
        for langue, phrase in (("fr", "domaine pilote non configuré : aucune étiquette de domaine déclarée"),
                               ("en", "pilot domain not configured: no domain label declared")):
            code, _, _ = self.epics_cmd("--language", langue, store=faux_store(lire_epics=mock.Mock(side_effect=AssertionError("base"))))
            self.assertEqual(code, phrase)
        self.assertFalse(self.rapports.exists())

    def test_aucun_epic_dans_le_pilote(self):
        self.epics = epics_du_jeu(5, domaine=False)
        for langue, phrase in (("fr", "aucun épic dans le domaine pilote"), ("en", "no epic in the pilot domain")):
            code, _, _ = self.epics_cmd("--language", langue)
            self.assertEqual(code, phrase)
        self.assertFalse(self.rapports.exists())

    def test_domaine_retire_ne_compte_pas(self):
        self.epics = epics_du_jeu(5)
        for e in self.epics:
            e["periodes"][0] = {**e["periodes"][0], "retrait": e["periodes"][0]["ajout"].replace(month=2)}
        code, _, _ = self.epics_cmd("--language", "en")
        self.assertEqual(code, "no epic in the pilot domain")

    def test_epics_du_pilote_sans_aucun_historique(self):
        self.epics = epics_du_jeu(12, historique=False)
        for langue, phrase in (("fr", "aucun historique d'épic dans la base : lancez d'abord la collecte de l'historique"),
                               ("en", "no epic history in the database: run the history collection first")):
            code, _, _ = self.epics_cmd("--language", langue)
            self.assertEqual(code, phrase)
        self.assertFalse(self.rapports.exists())

    def test_base_injoignable_message_clair_code_1(self):
        class ErreurBase(Exception):
            pass
        code, _, _ = self.epics_cmd(store=faux_store(lire_epics=mock.Mock(side_effect=ErreurBase("refusée"))))
        self.assertEqual(code, "Base de données : lecture impossible. refusée")

    def test_langue_inconnue_erreur_d_usage(self):
        code, _, _ = self.epics_cmd("--language", "de")
        self.assertEqual(code, 2)

    def test_option_source_inexistante(self):
        code, _, _ = self.epics_cmd("--source", "csv")
        self.assertEqual(code, 2)


class RapportReduit(Base):
    PHRASE_EN = "Discovery Workflow mapping not validated: columns, delays and ages not computed"
    PHRASE_FR = "correspondance du Discovery Workflow non validée : colonnes, délais et âges non calculés"

    def test_sans_date_de_validation(self):
        self.ecrire("flux.yaml", REGLAGES.replace("  validated_on: 2026-01-02\n", ""))
        code, console, _ = self.epics_cmd("--language", "en")
        self.assertIsNone(code)
        md = self.md()
        for sortie in (md, console):
            self.assertIn(self.PHRASE_EN, sortie)
        self.assertIn("## Passages in Epic Review", md)
        self.assertIn("## Planned cycle and carry-over", md)
        self.assertIn("## Epics per status", md)
        for titre in ("## Idea to Ready", "## Epics per board column", "## Age of epics in progress"):
            self.assertNotIn(titre, md)
        r = self.json()
        self.assertFalse(r["mapping_validated"])
        for section in ("idea_to_ready", "epics_per_column", "age"):
            cellules = [c for ligne in r["sections"][section]["rows"] for c in ligne["cells"].values()]
            self.assertTrue(cellules and all(c == {"value": None, "state": "not_computed"} for c in cellules), section)
        self.assertEqual(r["sections"]["epics_per_status"]["status"], "ok")
        self.assertEqual(r["sections"]["planned_cycle"]["status"], "ok")
        self.epics_cmd()
        self.assertIn(self.PHRASE_FR, self.md())

    def test_sans_colonnes_actives(self):
        self.ecrire("flux.yaml", REGLAGES.replace("  active_columns: [Idee, Revue]\n", ""))
        self.epics_cmd("--language", "en")
        self.assertIn(self.PHRASE_EN, self.md())

    def test_sans_colonne_ready_et_sans_etiquette_ready(self):
        reglages = REGLAGES.replace("  ready_column: Pret\n", "").replace('ready: {prefix: "zr-", labels: ["zr-pret"]}', 'ready: {prefix: "zr-", labels: []}')
        self.ecrire("flux.yaml", reglages)
        self.epics_cmd("--language", "en")
        self.assertIn(self.PHRASE_EN, self.md())

    def test_sans_colonne_ready_mais_avec_l_etiquette_ready_rapport_complet(self):
        self.ecrire("flux.yaml", REGLAGES.replace("  ready_column: Pret\n", ""))
        self.epics_cmd("--language", "en")
        self.assertNotIn(self.PHRASE_EN, self.md())
        self.assertIn("## Idea to Ready", self.md())

    def test_rapport_complet_ne_porte_pas_la_phrase(self):
        self.epics_cmd("--language", "en")
        self.assertNotIn(self.PHRASE_EN, self.md())
        self.assertNotIn("epics_per_status", self.json()["sections"])


class SectionsAbsentes(Base):
    def test_aucun_role_epic_review(self):
        self.ecrire("flux.yaml", REGLAGES.replace('  epic_review: {prefix: "ze-", labels: ["ze-revue"]}\n', ""))
        code, _, _ = self.epics_cmd("--language", "en")
        self.assertIsNone(code)
        self.assertIn("no Epic Review label declared", self.md())
        self.assertEqual(self.json()["sections"]["epic_review_passages"]["status"], "no_epic_review_label")
        self.assertIn("## Idea to Ready", self.md())
        self.epics_cmd()
        self.assertIn("aucune étiquette Epic Review déclarée", self.md())

    def test_aucune_etiquette_de_cycle_liee_a_un_cycle(self):
        self.ecrire("flux.yaml", REGLAGES.replace(", cycle_keys: {zc-un: 2026-C1, zc-deux: 2026-C2}", ""))
        code, _, _ = self.epics_cmd("--language", "en")
        self.assertIsNone(code)
        self.assertIn("no cycle label linked to a cycle", self.md())
        self.assertEqual(self.json()["sections"]["planned_cycle"]["status"], "no_cycle_label")
        self.epics_cmd()
        self.assertIn("aucune étiquette de cycle liée à un cycle", self.md())


class SortiesSansValeurDistinctive(Base):
    def test_ni_cle_ni_etiquette_ni_version_en_sortie(self):
        for langue in ("fr", "en"):
            _, console, erreur = self.epics_cmd("--language", langue)
            sorties = console + erreur + self.md() + self.lire_rapport(SORTIE + ".json")
            for chaine in ETIQUETTES_DISTINCTIVES + ("ZZVERSION", "ZZE-", "Won't Do"):
                self.assertNotIn(chaine, sorties, f"{chaine} {langue}")
            self.assertIsNone(re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", re.sub(r"\b20\d\d-(C[1-6]|EOY|Q[1-4])\b", "", sorties)))

    def test_le_nom_d_equipe_n_est_que_dans_les_fichiers(self):
        _, console, erreur = self.epics_cmd()
        self.assertNotIn(EQUIPE, console + erreur)
        self.assertIn(EQUIPE, self.md())


class Langue(Base):
    def test_json_identique_et_rapport_anglais_sans_francais(self):
        self.epics_cmd()
        fr_json = self.lire_rapport(SORTIE + ".json")
        self.epics_cmd("--language", "en")
        md = self.md()
        self.assertEqual(self.lire_rapport(SORTIE + ".json"), fr_json)
        self.assertIsNone(re.search(r"[éèêàâùûôîç]|\b(les|des|dans|sans|pour|épics|cycle planifié)\b", md), md)
        self.assertIn("## Idea to Ready", md)
        self.epics_cmd()
        self.assertIn("## De l'idée à Ready", self.md())


class Aide(unittest.TestCase):
    def test_epics_est_liste_et_l_aide_ne_lit_rien(self):
        sortie = io.StringIO()
        store = mock.Mock(side_effect=AssertionError("aucune lecture"))
        with contextlib.redirect_stdout(sortie), mock.patch.object(fj, "config", store), self.assertRaises(SystemExit) as arret:
            fj.main(["--help"])
        self.assertEqual(arret.exception.code, 0)
        for nom in ("statuses", "compute", "compare", "config", "cycles", "epics"):
            self.assertIn(nom, sortie.getvalue())
        store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
