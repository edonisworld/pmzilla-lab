"""
Tests du journal d'accompagnement (tools/journal_lab.py) sur un faux journal.

    uv run --with pyyaml python -m unittest discover -s tests/journal_lab -v

Le journal vit dans un dossier temporaire : jamais Journal-Lab. Les entrées, rôles et périmètres sont inventés
(des rôles, jamais de noms de personnes). La date du jour est fixée par l'option cachée --today.
"""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import journal_lab as journal  # noqa: E402

AUJOURDHUI = "2026-10-06"

ENTREE = """\
date: 2026-10-01
type: rétro
perimetre: équipe Alpha
posture: facilitation
tente: Rétrospective en format 4L avec un vote à points.
constat: Plus de participation, mais les actions restent vagues.
suites:
  - quoi: Reformuler les trois actions avec un critère de fin
    pour: Scrum Master
    echeance: 2026-10-05
  - quoi: Partager le résultat à la direction produit
    pour: Product Owner
    echeance: 2026-10-20
experience:
  hypothese: Un critère de fin par action augmente la part d'actions terminées.
  signal: Au moins deux actions sur trois terminées à la rétro suivante.
  bilan_le: 2026-10-04
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for patch in (mock.patch.object(journal, "JOURNAL_DIR", self.tmp / "Journal-Lab"),
                      mock.patch.object(journal, "JOURNAL_FILE", self.tmp / "Journal-Lab" / "journal.yaml"),
                      # aucun auteur du module des cas : ni variable, ni .pmzilla/cases.yaml (jamais la base réelle)
                      mock.patch.object(journal, "WORKSPACE", self.tmp),
                      mock.patch.dict("os.environ", {"PMZILLA_LAB_CASES_AUTHOR": ""})):
            patch.start()
            self.addCleanup(patch.stop)

    def cli(self, *arguments, aujourdhui=AUJOURDHUI):
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["journal_lab.py", "--today", aujourdhui, *arguments]), \
                contextlib.redirect_stdout(sortie):
            journal.main()
        return sortie.getvalue()

    def refuse(self, *arguments) -> str:
        with self.assertRaises(SystemExit) as erreur:
            self.cli(*arguments)
        return str(erreur.exception.code)

    def fichier(self, texte: str, nom="entree.yaml") -> Path:
        chemin = self.tmp / nom
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def ajouter(self, texte: str = ENTREE, nom="entree.yaml") -> str:
        return self.cli("add", str(self.fichier(texte, nom)))

    def entrees(self) -> list[dict]:
        return yaml.safe_load(journal.JOURNAL_FILE.read_text(encoding="utf-8"))


class AnciensNoms(Base):
    """Lot 8 : anciens noms d'options et anciens noms de sous-commandes refusés avec le nom actuel."""

    def setUp(self):
        super().setUp()
        self.ajouter()

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        for ancien, actuel, arguments in (("--perimetre", "--scope", ("--perimetre", "équipe Alpha")),
                                          ("--toutes", "--all", ("--toutes",))):
            with self.subTest(ancien=ancien):
                erreur = io.StringIO()
                with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
                    self.cli("follow-ups", *arguments)
                self.assertEqual(stop.exception.code, 2)
                self.assertIn(f"« {ancien} »", erreur.getvalue())
                self.assertIn(f"« {actuel} »", erreur.getvalue())

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("ajouter", "suites", "maj", "bilan"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erreur:
                self.cli(ancien)
            self.assertEqual(erreur.exception.code, 2, ancien)


class Ajout(Base):
    def test_entree_valide(self):
        chemin = self.fichier(ENTREE)
        sortie = self.cli("add", str(chemin))
        self.assertIn("Séance notée : J-20261001-1 · rétro · équipe Alpha", sortie)
        self.assertIn("suite J-20261001-1.s1", sortie)
        self.assertIn("expérience J-20261001-1.x : bilan le 2026-10-04", sortie)
        self.assertFalse(chemin.exists())   # le fichier source est supprimé une fois noté
        entree = self.entrees()[0]
        self.assertEqual((entree["posture"], entree["suites"][0]["statut"], entree["experience"]["statut"]),
                         ("facilitation", "ouverte", "en cours"))
        self.assertEqual(sorted(p.name for p in journal.JOURNAL_DIR.iterdir()), ["journal.yaml"])   # pas de .tmp

    def test_identifiants_du_meme_jour_incrementes(self):
        self.ajouter()
        self.ajouter(nom="deux.yaml")
        self.assertEqual([e["id"] for e in self.entrees()], ["J-20261001-1", "J-20261001-2"])
        self.assertEqual(self.entrees()[1]["suites"][1]["id"], "J-20261001-2.s2")

    def test_champs_facultatifs_et_defauts(self):
        self.ajouter("type: atelier\nperimetre: domaine pilote\ntente: Atelier.\nconstat: Utile.\n")
        entree = self.entrees()[0]
        self.assertEqual((entree["date"], entree["posture"], entree["suites"]), (AUJOURDHUI, "aucune", []))
        self.assertNotIn("experience", entree)

    def test_refus_ne_ecrit_rien_et_garde_le_fichier(self):
        base = "type: rétro\nperimetre: équipe Alpha\ntente: A.\nconstat: B.\n"
        cas = {
            "champ manquant": ("type: rétro\nperimetre: équipe Alpha\ntente: A.\n", "« constat » manquant"),
            "champ inconnu": (base + "personne: X\n", "Champs inconnus : personne"),
            "type inconnu": (base.replace("rétro", "soirée"), "type : « soirée » inconnu"),
            "posture inconnue": (base + "posture: magie\n", "posture : « magie » inconnue"),
            "date future": (base + "date: 2026-12-01\n", "dans le futur"),
            "date illisible": (base + "date: hier\n", "AAAA-MM-JJ"),
            "trop long": (base.replace("A.", "x" * 601), "dépasse 600 caractères"),
            "pas un dictionnaire": ("- une\n- liste\n", "dictionnaire YAML"),
            "yaml cassé": ("type: [rétro\n", "Entrée refusée"),
            "échéance manquante": (base + "suites:\n  - quoi: Faire\n    pour: Scrum Master\n", "suites[1].echeance"),
            "suite mal formée": (base + "suites:\n  - juste du texte\n", "suites[1]"),
            "expérience sans bilan": (base + "experience:\n  hypothese: H\n  signal: S\n", "experience.bilan_le"),
            "type 1:1 lu comme nombre": (base.replace("rétro", "1:1"), "type : « 61 » inconnu"),
        }
        for nom, (texte, attendu) in cas.items():
            with self.subTest(nom):
                chemin = self.fichier(texte, "refuse.yaml")
                message = self.refuse("add", str(chemin))
                self.assertIn("Entrée refusée, rien n'est écrit", message)
                self.assertIn(attendu, message)
                self.assertTrue(chemin.exists())
                self.assertFalse(journal.JOURNAL_FILE.exists())

    def test_fichier_introuvable(self):
        self.assertIn("Fichier introuvable", self.refuse("add", str(self.tmp / "absent.yaml")))

    def test_suites_et_experience_sans_champ_obligatoire(self):
        base = "type: rétro\nperimetre: équipe Alpha\ntente: A.\nconstat: B.\n"
        message = self.refuse("add", str(self.fichier(base + "suites:\n  - quoi: Faire\n    echeance: 2026-10-10\n")))
        self.assertIn("« pour » manquant", message)


class Suites(Base):
    def setUp(self):
        super().setUp()
        self.ajouter()
        self.ajouter("type: coaching\nperimetre: rôle Product Owner\ntente: Échange.\nconstat: Clair.\ndate: 2026-09-20\n"
                     "suites:\n  - quoi: Clarifier le critère d'acceptation\n    pour: Product Owner\n"
                     "    echeance: 2026-10-30\n", "deux.yaml")

    def test_ordre_et_retard(self):
        sortie = self.cli("follow-ups")
        lignes = [l for l in sortie.splitlines() if "J-2026" in l and "pour le" in l]
        self.assertEqual([l.split(" · ")[0].strip().split()[-1] for l in lignes],
                         ["J-20261001-1.s1", "J-20261001-1.s2", "J-20260920-1.s1"])
        self.assertTrue(lignes[0].lstrip().startswith("EN RETARD J-20261001-1.s1"))
        self.assertFalse(lignes[1].lstrip().startswith("EN RETARD"))

    def test_filtre_perimetre_insensible_a_la_casse(self):
        sortie = self.cli("follow-ups", "--scope", "PRODUCT owner")
        self.assertIn("J-20260920-1.s1", sortie)
        self.assertNotIn("J-20261001-1.s1", sortie)
        self.assertIn("· PRODUCT owner (ouvertes)", sortie.splitlines()[0])   # l'en-tête reprend le filtre tel que saisi
        self.assertIn("aucune", self.cli("follow-ups", "--scope", "domaine inconnu"))

    def test_experience_due_listee_et_pas_avant_l_echeance(self):
        sortie = self.cli("follow-ups")
        self.assertIn("Expériences dont le bilan est dû :", sortie)
        self.assertIn("J-20261001-1.x · bilan prévu le 2026-10-04", sortie)
        self.assertNotIn("Expériences dont le bilan est dû", self.cli("follow-ups", aujourdhui="2026-10-03"))

    def test_toutes_ajoute_les_suites_closes(self):
        self.cli("update", "J-20261001-1.s1", "faite", "--note", "Fait en séance.")
        self.assertNotIn("J-20261001-1.s1", self.cli("follow-ups"))
        sortie = self.cli("follow-ups", "--all")
        self.assertIn("J-20261001-1.s1 [faite]", sortie)
        lignes = [l for l in sortie.splitlines() if "pour le" in l]
        self.assertIn("[faite]", lignes[-1])   # les closes passent après les ouvertes


class MiseAJour(Base):
    def setUp(self):
        super().setUp()
        self.ajouter()

    def test_suite_faite_abandonnee_rouverte(self):
        self.assertIn("Suite J-20261001-1.s1 : faite.", self.cli("update", "J-20261001-1.s1", "faite", "--note", " ok "))
        self.assertEqual(self.entrees()[0]["suites"][0]["note"], "ok")
        self.cli("update", "J-20261001-1.s2", "abandonnee")
        self.assertEqual(self.entrees()[0]["suites"][1]["statut"], "abandonnee")
        self.cli("update", "J-20261001-1.s1", "ouverte")
        self.assertEqual(self.entrees()[0]["suites"][0]["statut"], "ouverte")
        self.assertEqual(self.entrees()[0]["suites"][0]["note"], "ok")   # la note reste

    def test_conclure_une_experience_exige_un_resultat(self):
        self.assertIn("--note est obligatoire", self.refuse("update", "J-20261001-1.x", "conclue"))
        self.assertIn("--note est obligatoire", self.refuse("update", "J-20261001-1.x", "conclue", "--note", "  "))
        self.assertIn("Expérience J-20261001-1.x conclue.",
                      self.cli("update", "J-20261001-1.x", "conclue", "--note", "Deux actions sur trois terminées."))
        self.assertEqual(self.entrees()[0]["experience"]["statut"], "conclue")
        self.assertNotIn("bilan est dû", self.cli("follow-ups"))   # conclue : n'apparaît plus comme due

    def test_statuts_incoherents_et_identifiant_inconnu(self):
        self.assertIn("Une expérience se conclut", self.refuse("update", "J-20261001-1.x", "faite"))
        self.assertIn("Statut d'une suite", self.refuse("update", "J-20261001-1.s1", "conclue"))
        self.assertIn("Identifiant inconnu : J-1.s9", self.refuse("update", "J-1.s9", "faite"))
        with self.assertRaises(SystemExit):
            self.cli("update", "J-20261001-1.s1", "nimporte")   # refusé par argparse


class Bilan(Base):
    def setUp(self):
        super().setUp()
        self.ajouter()
        self.ajouter("type: coaching\nperimetre: rôle Product Owner\ntente: Échange.\nconstat: Clair.\ndate: 2026-08-01\n",
                     "ancienne.yaml")
        self.cli("update", "J-20261001-1.s2", "abandonnee")

    def test_periode_par_defaut_30_jours(self):
        sortie = self.cli("review")
        self.assertIn("du 2026-09-06 au 2026-10-06 : 1 séance(s)", sortie)
        self.assertIn("Suites : 2 promises · 0 faites · 1 abandonnées · 1 ouvertes, dont 1 en retard.", sortie)
        self.assertIn("Expériences : 1 · 0 conclues.", sortie)
        self.assertIn("## J-20261001-1 · 2026-10-01 · rétro · équipe Alpha · facilitation", sortie)
        self.assertNotIn("J-20260801-1", sortie)

    def test_depuis_et_perimetre(self):
        sortie = self.cli("review", "--since", "2026-07-01")
        self.assertIn("2 séance(s)", sortie)
        sortie = self.cli("review", "--since", "2026-07-01", "--scope", "product owner")
        self.assertIn("1 séance(s)", sortie)
        self.assertIn("· product owner :", sortie.splitlines()[0])
        self.assertNotIn("équipe Alpha", sortie.split("\n", 1)[1])

    def test_resultat_et_notes_affiches(self):
        self.cli("update", "J-20261001-1.x", "conclue", "--note", "Hypothèse confirmée.")
        self.cli("update", "J-20261001-1.s1", "faite", "--note", "Vu en séance.")
        sortie = self.cli("review")
        self.assertIn("Expériences : 1 · 1 conclues.", sortie)
        self.assertIn("résultat : Hypothèse confirmée.", sortie)
        self.assertIn("- Suite [faite]", sortie)
        self.assertIn("(Vu en séance.)", sortie)

    def test_journal_vide(self):
        shutil.rmtree(journal.JOURNAL_DIR)
        self.assertIn("0 séance(s)", self.cli("review"))
        self.assertIn("aucune", self.cli("follow-ups"))


if __name__ == "__main__":
    unittest.main()
