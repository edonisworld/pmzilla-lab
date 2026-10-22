"""Règles `deny` du dossier de contexte (organisation-context, design D10 et D16, tâche 9.1, spec tooling-permission-guards).

La session ne lit, ne liste ni ne copie `originaux/` ; ne lit et n'écrit `notes/` que par la bibliothèque et l'outil de contexte ; ne touche pas
`regles/` (la surcouche de story-quality-audit, reposée sous le nouveau nom) ; ne parcourt pas le dossier entier avec `find`, `tree`, `rsync`,
`tar`, `ditto`, `zip`. Elle lit toujours le fichier local `.pmzilla/contexte.md` et les modèles neutres, lance l'outil de contexte, sa suite et le
lanceur de tests, et `story_quality.py grid`.

Conception (même motif que test_settings_deny_story_quality.py) : l'auteur remplace les règles de l'ancien dossier par celles de REGLES_D10 à la
tâche 9.3. La suite reste VERTE avant et après :
 - la matrice des formes s'applique au bloc REGLES_D10, pas au fichier de réglages ;
 - les tests « dans le fichier de réglages » sont SAUTÉS tant qu'aucune règle de D10 n'y est, ÉCHOUENT si l'état est partiel ou mélangé (ils nomment
   les règles en cause) et passent si tout y est ;
 - les commandes permises sont aussi vérifiées contre les règles réelles privées de celles de D10 : même résultat avant et après.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/etat_contexte.py --json     (imprime la liste à copier dans permissions.deny)
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etat_contexte import (ANCIEN_DOSSIER, ANCIENNE_REGLE_ALLOW, COMMANDES_DOSSIER_ENTIER, DOSSIER, FICHIER_SURCOUCHE, LECTEURS,  # noqa: E402
                           REGLES_D10, REGLES_DOSSIER_ENTIER, REGLES_NOTES, REGLES_ORIGINAUX, REGLES_SURCOUCHE, deny_reel, reglages,
                           reposee)
from test_settings_deny_story_quality import Moteur  # noqa: E402

DOSSIERS = (DOSSIER, f"./{DOSSIER}", f"/Users/quelquun/PMZilla-Lab/{DOSSIER}", f"~/PMZilla-Lab/{DOSSIER}", f"$HOME/PMZilla-Lab/{DOSSIER}")
OPTIONS = ("", "-n 5 ", "-r ")
CHEMINS_READ = {
    "originaux": (f"{DOSSIER}/originaux/a.pdf", f"./{DOSSIER}/originaux/a.pdf", f"/Users/quelquun/PMZilla-Lab/{DOSSIER}/originaux/a.pdf",
                  f"~/PMZilla-Lab/{DOSSIER}/originaux/sous/a.pdf", f"~/ailleurs/{DOSSIER}/originaux/a.pdf"),
    "notes": (f"{DOSSIER}/notes/2026-09-01-x.md", f"./{DOSSIER}/notes/2026-09-01-x.md", f"/Users/quelquun/PMZilla-Lab/{DOSSIER}/notes/x.md",
              f"~/PMZilla-Lab/{DOSSIER}/notes/x.md", f"~/ailleurs/{DOSSIER}/notes/x.md"),
    "regles": (f"{DOSSIER}/regles/{FICHIER_SURCOUCHE}", f"./{DOSSIER}/regles/{FICHIER_SURCOUCHE}",
               f"/Users/quelquun/PMZilla-Lab/{DOSSIER}/regles/{FICHIER_SURCOUCHE}", f"~/PMZilla-Lab/{DOSSIER}/regles/autre.yaml",
               f"~/ailleurs/{DOSSIER}/regles/x/y.yaml"),
}

COMMANDES_PERMISES = (
    "uv run tools/context_lab.py list", "uv run tools/context_lab.py check", "uv run tools/context_lab.py add",
    "uv run tools/context_lab.py review 2026-09-01-x.md 2027-01-01", "uv run tools/context_lab.py init",
    "python3 tools/context_lab.py check", "~/PMZilla-Lab/workspace/tools/context_lab.py list", "uv run tools/context_lab.py --help",
    "cat tools/context_lab.py", "head -40 tools/context_lab.py", "grep -n review tools/context_lab.py", "sed -n 1,40p tools/private_collections.py",
    "cat .claude/commands/context.md", "cat tests/context_lab/test_context_lab.py", "ls tests/context_lab", "ls tests/private_collections",
    "bash tests/run_all.sh context_lab", "bash tests/run_all.sh private_collections", "bash tests/run_all.sh --staged",
    "bash tests/run_all.sh settings_deny",
    "uv run --with numpy --with httpx --with pyyaml python -W ignore -m unittest discover -s tests/context_lab -q -f",
    "python3 -W ignore -m unittest discover -s tests/context_lab -q",
    "cat .pmzilla/contexte.md", "head -20 .pmzilla/contexte.md", "grep -n Mission .pmzilla/contexte.md",
    "cat ~/PMZilla-Lab/workspace/.pmzilla/contexte.md", "cat tests/postures/contexte-neutre.md", "cat tests/postures/contexte-neutre.en.md",
    "grep -n Qui tests/postures/contexte-neutre.md", "ls tests/postures",
    "find tests/postures -name contexte-neutre.md", "find . -name 'contexte-neutre*.md'", "git ls-files tests/postures",
    "uv run tools/story_quality.py grid", "uv run tools/story_quality.py grid --show", "python3 tools/story_quality.py grid --show",
    "grep -rn contexte docs/pmzilla", "git log --oneline -3 -- tools/context_lab.py",
)
CHEMINS_READ_PERMIS = (
    "tools/context_lab.py", "tools/private_collections.py", ".claude/commands/context.md", "tests/context_lab/test_context_lab.py",
    ".pmzilla/contexte.md", "./.pmzilla/contexte.md", "/Users/quelquun/PMZilla-Lab/workspace/.pmzilla/contexte.md",
    "~/PMZilla-Lab/workspace/.pmzilla/contexte.md", "tests/postures/contexte-neutre.md", "tests/postures/contexte-neutre.en.md",
    "docs/pmzilla/context-note-template.md",
)


def chemins_pour(outil, sous):
    """Les chemins d'essai d'un outil : Edit n'a que trois formes dans D10 (pas de forme « ~/**/ »), Read en a quatre."""
    return [c for c in CHEMINS_READ[sous] if outil == "Read" or not c.startswith("~/ailleurs")]


class Compte(unittest.TestCase):
    def test_107_regles_sans_doublon(self):
        self.assertEqual((len(REGLES_ORIGINAUX), len(REGLES_NOTES), len(REGLES_SURCOUCHE), len(REGLES_DOSSIER_ENTIER)), (33, 21, 35, 18))
        self.assertEqual(len(REGLES_D10), 107)
        self.assertEqual(len(set(REGLES_D10)), 107)

    def test_aucune_regle_ne_nomme_l_ancien_dossier(self):
        self.assertEqual([r for r in REGLES_D10 if ANCIEN_DOSSIER in r], [])
        self.assertTrue(all(r.startswith(("Bash(", "Read(", "Edit(")) and r.endswith(")") for r in REGLES_D10))

    def test_aucune_regle_write_pour_le_dossier(self):
        """Claude Code ignore Write(chemin) : seules des règles Edit(chemin) couvrent l'écriture (garde R-84)."""
        self.assertEqual([r for r in REGLES_D10 if r.startswith(("Write(", "NotebookEdit("))], [])

    def test_les_quatorze_lecteurs(self):
        self.assertEqual(len(LECTEURS), 14)
        self.assertEqual(LECTEURS, ("cat", "head", "tail", "less", "more", "grep", "rg", "awk", "sed", "cp", "strings", "bat", "xxd", "base64"))


class Bloc(unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à copier : vert avant comme après la tâche 9.3."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_D10)

    def test_originaux_lus_et_listes_sous_chaque_forme(self):
        for sous, outils in (("originaux", ("Read",)), ("notes", ("Read", "Edit")), ("regles", ("Read", "Edit"))):
            for outil in outils:
                for chemin in chemins_pour(outil, sous):
                    self.assertTrue(self.moteur.acces_interdit(outil, chemin), f"{outil}({chemin})")

    def test_les_quatorze_lecteurs_sur_chaque_sous_dossier(self):
        for lecteur, dossier, sous, option in itertools.product(LECTEURS, DOSSIERS, ("originaux", "notes", "regles"), OPTIONS):
            commande = f"{lecteur} {option}{dossier}/{sous}/x.md"
            self.assertTrue(self.moteur.interdite(commande), commande)
            commande = f"{lecteur} {option}{dossier}/{sous}"
            self.assertTrue(self.moteur.interdite(commande), commande)

    def test_la_surcouche_ou_qu_elle_soit_sous_le_dossier(self):
        for lecteur, dossier in itertools.product(LECTEURS, DOSSIERS):
            for sous in ("regles", "autre", "a/b"):
                commande = f"{lecteur} {dossier}/{sous}/{FICHIER_SURCOUCHE}"
                self.assertTrue(self.moteur.interdite(commande), commande)

    def test_listage_archive_metadonnees_et_ouverture_des_originaux(self):
        for commande in ("ls", "du", "zcat", "gzcat", "gunzip", "unzip", "textutil", "mdls", "xattr", "ditto", "zip", "ln", "open", "qlmanage", "mv"):
            for dossier in DOSSIERS:
                texte = f"{commande} {dossier}/originaux/a.pdf"
                self.assertTrue(self.moteur.interdite(texte), texte)
                texte = f"{commande} -la {dossier}/originaux"
                self.assertTrue(self.moteur.interdite(texte), texte)

    def test_dossier_entier_nomme_en_dernier_suivi_d_un_chemin_ou_d_options(self):
        for commande, dossier in itertools.product(COMMANDES_DOSSIER_ENTIER, DOSSIERS):
            for texte in (f"{commande} {dossier}", f"{commande} {dossier}/notes", f"{commande} {dossier} -name '*.md'",
                          f"{commande} -r {dossier} /tmp/copie", f"{commande} -a {dossier}/ ."):
                self.assertTrue(self.moteur.interdite(texte), texte)

    def test_ecriture_directe_d_une_note_refusee(self):
        for chemin in chemins_pour("Edit", "notes"):
            self.assertTrue(self.moteur.acces_interdit("Edit", chemin), f"Edit({chemin})")
        self.assertEqual([r for r in REGLES_NOTES if r.startswith("Write(")], [])

    def test_commandes_et_lectures_permises(self):
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])
        self.assertEqual([c for c in CHEMINS_READ_PERMIS if self.moteur.lecture_interdite(c)], [])

    def test_le_fichier_local_et_les_modeles_neutres_par_chaque_lecteur(self):
        for lecteur in LECTEURS:
            for chemin in (".pmzilla/contexte.md", "tests/postures/contexte-neutre.md", "tests/postures/contexte-neutre.en.md",
                           "~/PMZilla-Lab/workspace/.pmzilla/contexte.md"):
                commande = f"{lecteur} {chemin}"
                self.assertFalse(self.moteur.interdite(commande), commande)


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles de D10 : même résultat avant et après la tâche 9.3."""

    def test_aucune_regle_d_avant_ne_refuse_une_commande_permise(self):
        moteur = Moteur([r for r in deny_reel() if r not in REGLES_D10 and ANCIEN_DOSSIER not in r])
        self.assertEqual([c for c in COMMANDES_PERMISES if moteur.interdite(c)], [])
        self.assertEqual([c for c in CHEMINS_READ_PERMIS if moteur.lecture_interdite(c)], [])


class DansLeFichierDeReglages(unittest.TestCase):
    """Tâche 9.3 : l'auteur remplace les règles. Sauté avant, échoue si l'état est partiel ou mélangé, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.reglages = reglages()
        cls.deny = cls.reglages["permissions"]["deny"]
        cls.manquantes = [r for r in REGLES_D10 if r not in cls.deny]

    def avant(self):
        if not reposee():
            self.fail("tâche 9.3 : l'auteur n'a pas encore remplacé les règles de l'ancien dossier (utilisateur)")

    def test_les_107_regles_sont_dans_settings_json(self):
        self.avant()
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de D10 absente(s) de .claude/settings.json")

    def test_aucune_regle_ne_nomme_l_ancien_dossier(self):
        self.avant()
        self.assertEqual([r for r in self.deny if ANCIEN_DOSSIER in r], [], "règle(s) de l'ancien dossier encore dans .claude/settings.json")

    def test_l_ancienne_regle_allow_est_retiree(self):
        self.avant()
        # Seule allow admise après la reprise : celle de `story_quality.py grid` (décision du 2026-10-20, lot 7).
        self.assertEqual([r for r in self.reglages["permissions"].get("allow", []) if r != "Bash(uv run tools/story_quality.py grid*)"],
                         [], "la règle allow des notes de contexte est restée")
        self.assertNotIn(ANCIENNE_REGLE_ALLOW, self.reglages["permissions"].get("allow", []))

    def test_la_matrice_contre_les_regles_reelles(self):
        self.avant()
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_107_regles_sont_dans_settings_json")
        moteur = Moteur(self.deny)
        for sous, outils in (("originaux", ("Read",)), ("notes", ("Read", "Edit")), ("regles", ("Read", "Edit"))):
            for outil in outils:
                for chemin in chemins_pour(outil, sous):
                    self.assertTrue(moteur.acces_interdit(outil, chemin), f"{outil}({chemin})")
        self.assertEqual([c for c in COMMANDES_PERMISES if moteur.interdite(c)], [])
        self.assertEqual([c for c in CHEMINS_READ_PERMIS if moteur.lecture_interdite(c)], [])


if __name__ == "__main__":
    unittest.main()
