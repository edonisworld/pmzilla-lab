"""tools/epic_statuses.py : relevé des statuts des épics (change jira-gdpr-alignment, groupe 10 ; spec jira-flow-epic-statuses).

Un espace de travail temporaire (PMZILLA_LAB_WORKSPACE) avec un flux.yaml, des exports et un cache inventés ; l'outil RÉEL est appelé dans
le processus (main(argv, environ)) sans la variable de session Claude Code (sauf pour le test du refus). Les chaînes distinctives (clé,
équipe, étiquette, version, nom de fichier) ne doivent apparaître ni dans la console ni dans le rapport. Aucune donnée réelle."""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.append(str(RACINE / "tests" / "flux_jira"))
import chargeur_csv as chargeur  # noqa: E402  (chargeur de fixtures, réservé aux tests : D11)
import epic_statuses as outil  # noqa: E402
import epic_statuses_messages  # noqa: E402
import messages  # noqa: E402

CLE = "ZQXKEY"                     # préfixe de clé distinctif
EQUIPE = "EquipeVorblaxQQ"
ETIQUETTE = "etiquette-distinctive-qq"
VERSION = "versionqq-9-9"
NOM_FICHIER = "export-nomdistinctifqq"
DISTINCTIVES = (CLE, EQUIPE, ETIQUETTE, VERSION, NOM_FICHIER, "Titre")
ENTETE = ["Issue key", "Issue Type", "Status", "Created", "Updated", "Team", "Summary", "Labels", "Fix Version"]
JOUR = "05/Mar/2026 09:00"
DATE_TRANSITION = "2026-03-05T09:00:00.000+0100"


class Decor(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name).resolve()
        self.flux = self.racine / "Flux-Lab"
        self.rapports = self.flux / "rapports"
        (self.flux / "exports").mkdir(parents=True)
        (self.flux / "historique").mkdir()
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        self.env["PMZILLA_LAB_WORKSPACE"] = str(self.racine)
        self.export = self.flux / "exports" / f"{NOM_FICHIER}.csv"
        self.cache = self.flux / "historique" / "transitions.json"

    def ecrire_export(self, lignes, chemin=None):
        with (chemin or self.export).open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(ENTETE)
            for cle, type_, etat in lignes:
                w.writerow([cle, type_, etat, JOUR, JOUR, EQUIPE, "Titre secret", ETIQUETTE, VERSION])

    def ecrire_cache(self, transitions_par_cle):
        self.cache.write_text(json.dumps({cle: {"termine": False, "transitions": [[DATE_TRANSITION, d, v] for d, v in trs]}
                                          for cle, trs in transitions_par_cle.items()}), encoding="utf-8")

    def ecrire_reglages(self, texte):
        (self.flux / "flux.yaml").write_text(texte, encoding="utf-8")

    def faux_store(self, csv_donnes):
        """Faux flow_store : les tickets des fixtures CSV (ceux de la ligne, sinon l'export du décor) et le cache d'historique du
        décor, rendus comme la base les rend. Sans cache : aucun historique."""
        chemins = csv_donnes or [str(self.export)]
        faux = types.ModuleType("flow_store")
        faux.lire_tickets_flux = lambda settings: chargeur.lire_tickets_flux(settings, [c for c in chemins if Path(c).exists()])
        faux.lire_historique = lambda settings: (chargeur.lire_historique(settings, str(self.cache))
                                                 if self.cache.exists() else {})
        return faux

    def lancer(self, *argv, env=None, brut=False):
        """Lance l'outil dans le processus. Par défaut, les chemins .csv et la valeur de --history sont retirés de la ligne (la base
        est remplacée par les fixtures) ; avec brut=True, la ligne est donnée telle quelle (tests de refus)."""
        argv, csv_donnes = list(argv), []
        if not brut:
            ligne, i = [], 0
            while i < len(argv):
                if argv[i].endswith(".csv"):
                    csv_donnes.append(argv[i])
                elif argv[i] == "--history" and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                    i += 1
                    ligne.append("--history")
                else:
                    ligne.append(argv[i])
                i += 1
            argv = ligne
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie), \
                mock.patch.dict(sys.modules, {"flow_store": self.faux_store(csv_donnes)}):
            try:
                code = outil.main(argv, self.env if env is None else env)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, sortie.getvalue()

    def rapport(self):
        fichiers = list(self.rapports.glob("statuts-epics-*.md"))
        self.assertEqual(len(fichiers), 1)
        return fichiers[0].read_text(encoding="utf-8")

    def aucun_rapport(self):
        self.assertFalse(self.rapports.exists() and list(self.rapports.glob("*")))

    def jeu_standard(self):
        """6 épics Draft, 5 Ready, 2 Review, 7 Done (+ une story Draft ignorée) ; historique : 6 passages Draft -> Review,
        un seul Draft -> Ready."""
        lignes, histoire, n = [], {}, 0
        for etat, nombre in (("Draft", 6), ("Ready", 5), ("Review", 2), ("Done", 7)):
            for _ in range(nombre):
                n += 1
                lignes.append((f"{CLE}-{n}", "Epic", etat))
        lignes.append((f"{CLE}-900", "Story", "Draft"))
        self.ecrire_export(lignes)
        for i in range(1, 7):
            histoire[f"{CLE}-{i}"] = [("Open", "Draft"), ("Draft", "Review")]
        histoire[f"{CLE}-7"] = [("Draft", "Ready")]
        histoire[f"{CLE}-900"] = [("Open", "Zzstory")]
        self.ecrire_cache(histoire)


class TestRapport(Decor):
    def test_contenu_quatre_statuts(self):
        self.jeu_standard()
        code, console = self.lancer(str(self.export))
        self.assertEqual(code, 0)
        texte = self.rapport()
        lignes = {l.split("|")[1].strip(): [c.strip() for c in l.split("|")[2:-1]] for l in texte.splitlines()
                  if l.startswith("| ") and not l.startswith("| Statut")}
        self.assertEqual(set(lignes), {"Draft", "Ready", "Review", "Done", "Open"})   # Open : départ vu dans l'historique
        self.assertEqual(lignes["Draft"][0], "6")
        self.assertEqual(lignes["Ready"][0], "5")
        self.assertEqual(lignes["Done"][0], "7")
        self.assertEqual(lignes["Draft"][1], "6")                 # arrivées en Draft : 6 épics
        self.assertIn("Review : 6", lignes["Draft"][2])
        self.assertIn("Ready : masqué", lignes["Draft"][2])
        self.assertIn("Tout compte inférieur à cinq est écrit « masqué ».", texte)    # le seuil reste dans l'introduction
        self.assertNotIn("Zzstory", texte)                         # la story n'est pas un épic
        for marque in DISTINCTIVES:
            self.assertNotIn(marque, texte)

    def test_nom_du_rapport_date(self):
        self.jeu_standard()
        self.lancer(str(self.export))
        self.assertEqual([p.name for p in self.rapports.glob("*")], [f"statuts-epics-{dt.date.today().isoformat()}.md"])

    def test_petite_cellule(self):
        self.jeu_standard()
        self.lancer(str(self.export))
        review = next(l for l in self.rapport().splitlines() if l.startswith("| Review "))
        self.assertEqual(review.split("|")[2].strip(), "masqué")  # 2 épics actuellement

    def test_aucun_epic(self):
        self.ecrire_export([(f"{CLE}-1", "Story", "Draft")])
        code, console = self.lancer(str(self.export))
        self.assertEqual(code, 1)
        self.assertIn("aucun épic trouvé", console)
        self.aucun_rapport()

    def test_aucun_epic_anglais(self):
        self.ecrire_export([(f"{CLE}-1", "Story", "Draft")])
        code, console = self.lancer(str(self.export), "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("no epic found", console)
        self.aucun_rapport()

    def test_types_d_epics_du_reglage(self):
        self.ecrire_reglages("epic_types: [Initiative]\n")
        self.ecrire_export([(f"{CLE}-{i}", "Initiative", "Draft") for i in range(1, 7)] + [(f"{CLE}-99", "Epic", "Zzepic")])
        self.ecrire_cache({f"{CLE}-1": [("Open", "Draft")]})
        code, _ = self.lancer(str(self.export))
        self.assertEqual(code, 0)
        texte = self.rapport()
        self.assertIn("| Draft | 6 |", texte)
        self.assertNotIn("Zzepic", texte)

    def test_aucun_historique_dans_la_base(self):
        self.ecrire_export([(f"{CLE}-{i}", "Epic", "Draft") for i in range(1, 7)])
        code, console = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("aucun historique dans la base : lancez d'abord la collecte de l'historique", console)
        self.aucun_rapport()

    def test_aucun_historique_dans_la_base_anglais(self):
        self.ecrire_export([(f"{CLE}-{i}", "Epic", "Draft") for i in range(1, 7)])
        code, console = self.lancer("--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("no history in the database: run the history collection first", console)

    def test_history_sans_valeur_accepte(self):
        self.jeu_standard()
        code, _ = self.lancer("--history")
        self.assertEqual(code, 0)
        self.assertIn("Review : 6", self.rapport())

    def test_chemin_donne_a_history_refuse(self):
        self.jeu_standard()
        autre = self.racine / "autre.json"
        autre.write_text(self.cache.read_text(encoding="utf-8"), encoding="utf-8")
        code, console = self.lancer("--history", str(autre), brut=True)
        self.assertEqual(code, 2)
        self.assertIn("--history ne prend aucun fichier : l'historique est lu dans la base", console)
        self.assertNotIn("autre.json", console)
        self.aucun_rapport()

    def test_fichier_d_export_refuse(self):
        self.jeu_standard()
        code, console = self.lancer(str(self.export), brut=True)
        self.assertEqual(code, 2)
        self.assertIn("les fichiers d'export ne sont plus lus : la base est la seule source", console)
        self.assertNotIn(NOM_FICHIER, console)
        self.aucun_rapport()

    def test_refus_en_anglais_des_fichiers(self):
        code, console = self.lancer(str(self.export), "--language", "en", brut=True)
        self.assertEqual(code, 2)
        self.assertIn("export files are no longer read: the database is the only source", console)

    def test_plusieurs_exports(self):
        self.ecrire_export([(f"{CLE}-{i}", "Epic", "Draft") for i in range(1, 4)])
        deuxieme = self.flux / "exports" / f"{NOM_FICHIER}-2.csv"
        self.ecrire_export([(f"{CLE}-{i}", "Epic", "Draft") for i in range(4, 8)], deuxieme)
        self.ecrire_cache({f"{CLE}-1": [("Open", "Draft")]})
        self.lancer(str(self.export), str(deuxieme))
        self.assertIn("| Draft | 7 |", self.rapport())


class TestConsole(Decor):
    def test_console_comptes_et_phrase_cle(self):
        self.jeu_standard()
        code, console = self.lancer(str(self.export))
        self.assertEqual(code, 0)
        self.assertIn("relevé des statuts des épics écrit", console)
        for ligne in console.strip().splitlines():
            self.assertRegex(ligne, r"^(épics : \S+|statuts : \S+|relevé des statuts des épics écrit)$")
        for marque in DISTINCTIVES + ("Draft", "Review", "Done"):
            self.assertNotIn(marque, console)

    def test_console_anglais(self):
        self.jeu_standard()
        code, console = self.lancer(str(self.export), "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("epic statuses report written", console)
        self.assertNotIn("relevé", console)
        self.assertIn("Epic statuses on", self.rapport())

    def test_rapport_en_anglais_sans_francais(self):
        self.jeu_standard()
        self.lancer(str(self.export), "--language", "en")
        self.assertNotIn("Statut", self.rapport())

    def test_langue_inconnue_code_2(self):
        self.jeu_standard()
        code, console = self.lancer(str(self.export), "--language", "de")
        self.assertEqual(code, 2)
        self.aucun_rapport()

    def test_option_inconnue_code_2_et_pas_de_contournement(self):
        self.jeu_standard()
        for option in ("--force", "--allow-session", "--bypass"):
            code, _ = self.lancer(str(self.export), option, env={**self.env, "CLAUDECODE": "1"})
            self.assertEqual(code, 2)


class TestSession(Decor):
    def test_refus_dans_une_session_sans_lire_de_fichier(self):
        self.jeu_standard()
        with mock.patch.object(outil, "reglages", side_effect=AssertionError("réglage lu")), \
                mock.patch.object(chargeur, "lire_tickets_flux", side_effect=AssertionError("base lue")), \
                mock.patch.object(chargeur, "lire_historique", side_effect=AssertionError("base lue")):
            code, console = self.lancer(str(self.export), env={**self.env, "CLAUDECODE": "1"})
        self.assertEqual(code, 3)
        self.assertIn("Refusé dans une session Claude Code", console)
        self.aucun_rapport()

    def test_refus_en_anglais(self):
        code, console = self.lancer(str(self.export), "--language", "en", env={**self.env, "CLAUDECODE": "1"})
        self.assertEqual(code, 3)
        self.assertIn("Refused inside a Claude Code session", console)

    def test_variable_vide_refuse_aussi(self):
        code, _ = self.lancer(str(self.export), env={**self.env, "CLAUDECODE": ""})
        self.assertEqual(code, 3)


DISCOVERY = """discovery_workflow:
  columns:
    Backlog: [Draft, Zzabsentun]
    Analyse: [Review]
    Fait: [Done, Zzabsentdeux]
  start_column: Backlog
  review_passed_columns: [Fait]
"""


class TestDiscoveryWorkflow(Decor):
    def test_non_validee_le_dit(self):
        self.ecrire_reglages(DISCOVERY)
        self.jeu_standard()
        self.assertEqual(self.lancer(str(self.export))[0], 0)
        self.assertIn("Correspondance non validée", self.rapport())

    def test_non_validee_en_anglais(self):
        self.ecrire_reglages(DISCOVERY)
        self.jeu_standard()
        self.lancer(str(self.export), "--language", "en")
        self.assertIn("Mapping not validated", self.rapport())

    def test_validee_sans_avertissement(self):
        self.ecrire_reglages(DISCOVERY + "  validated_on: 2026-10-01\n")
        self.jeu_standard()
        self.lancer(str(self.export))
        self.assertNotIn("non validée", self.rapport())

    def test_sans_bloc_ni_avertissement_ni_liste(self):
        self.jeu_standard()
        self.lancer(str(self.export))
        texte = self.rapport()
        self.assertNotIn("non validée", texte)
        self.assertNotIn("Mappés mais non observés", texte)

    def test_mappes_mais_non_observes(self):
        self.ecrire_reglages(DISCOVERY + "  validated_on: 2026-10-01\n")
        self.jeu_standard()
        self.lancer(str(self.export))
        texte = self.rapport()
        section = texte.split("## Mappés mais non observés")[1]
        self.assertIn("- Zzabsentun", section)
        self.assertIn("- Zzabsentdeux", section)
        self.assertNotIn("Draft", section)                         # observé : pas dans la liste
        self.assertNotRegex(section, r"\d")                        # noms seulement, aucun compte

    def test_mappes_mais_non_observes_anglais(self):
        self.ecrire_reglages(DISCOVERY)
        self.jeu_standard()
        self.lancer(str(self.export), "--language", "en")
        self.assertIn("## Mapped but not observed", self.rapport())

    def test_un_statut_observe_par_l_historique_seul_est_observe(self):
        self.ecrire_reglages(DISCOVERY.replace("Zzabsentun", "Open") + "  validated_on: 2026-10-01\n")
        self.jeu_standard()                                         # « Open » n'est que le départ de transitions
        self.lancer(str(self.export))
        self.assertNotIn("- Open", self.rapport())

    def test_statut_a_deux_colonnes_refuse_code_1(self):
        self.ecrire_reglages("discovery_workflow:\n  columns:\n    A: [Zzdouble]\n    B: [Zzdouble]\n")
        self.jeu_standard()
        code, console = self.lancer(str(self.export))
        self.assertEqual(code, 1)
        self.assertIn("discovery_workflow.columns", console)
        self.assertRegex(console, r"L\d+")
        self.aucun_rapport()

    def test_colonne_de_depart_non_declaree_refusee(self):
        self.ecrire_reglages("discovery_workflow:\n  columns:\n    A: [S1]\n  start_column: Zzinconnue\n")
        self.jeu_standard()
        code, console = self.lancer(str(self.export))
        self.assertEqual(code, 1)
        self.assertIn("discovery_workflow.start_column", console)
        self.assertNotIn("Zzinconnue", console)

    def test_colonne_revue_passee_non_declaree_refusee(self):
        self.ecrire_reglages("discovery_workflow:\n  columns:\n    A: [S1]\n  review_passed_columns: [Zzinconnue]\n")
        self.jeu_standard()
        code, console = self.lancer(str(self.export))
        self.assertEqual(code, 1)
        self.assertIn("discovery_workflow.review_passed_columns", console)
        self.assertNotIn("Zzinconnue", console)


class TestMessages(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(messages.check_catalogs(epic_statuses_messages.CATALOGS), [])


class TestCompteMasque(unittest.TestCase):
    """masking-mutation-tests 6.2 : la limite du masquage de `compte` (SEUIL ±1, comparaison inversée, négation, retour None)."""

    def test_limite_du_seuil(self):
        fr = messages.Messages(epic_statuses_messages.CATALOGS, "fr")
        self.assertEqual(outil.SEUIL, 5)
        self.assertEqual(outil.compte(0, fr), "masqué")                 # idée #417 : le mot, jamais « <5 »
        self.assertEqual(outil.compte(4, fr), "masqué")
        self.assertEqual(outil.compte(5, fr), "5")
        self.assertEqual(outil.compte(12, fr), "12")

    def test_le_mot_suit_la_langue(self):
        en = messages.Messages(epic_statuses_messages.CATALOGS, "en")
        self.assertEqual(outil.compte(4, en), "masked")
        self.assertEqual(outil.compte(5, en), "5")


if __name__ == "__main__":
    unittest.main()
