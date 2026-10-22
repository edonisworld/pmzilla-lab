"""Garde partagée des listes de règles deny déclarées (change deny-rules-review, design D1 à D3).

Chaque module test_settings_deny_*.py qui imprime sa liste avec `--json` (test `"--json" in sys.argv`) est importé, sa liste
passe par garde_regles.constats() : aucune règle Write( ou NotebookEdit( (une règle Edit( couvre tous les outils d'édition),
aucune règle vide ou mal formée, aucun doublon, aucune liste vide. La liste est donc prouvée avant la pose dans
.claude/settings.json. Le fichier de réglages n'a pas besoin d'être modifié. Aucune commande n'est lancée.

Un module dont la sortie --json imprime une autre liste que regles_attendues() est nommé dans DECLARATIONS.
Une liste de retrait (règles que le change demande de retirer) n'est pas une liste --json et n'est pas contrôlée.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
RACINE = DOSSIER.parents[1]
sys.path.insert(0, str(DOSSIER))
import garde_regles  # noqa: E402

# Module -> nom de la fonction (sans argument) ou de la constante qui porte la liste imprimée par --json.
# Les modules qui s'appellent regles_attendues() n'ont pas besoin d'être déclarés.
DECLARATIONS = {
    "test_settings_deny_epics": "REGLES_EPICS",
    "test_settings_deny_github": "REGLES",
    "test_settings_deny_rgpd": "REGLES_D18",
    "test_settings_deny_story_quality": "REGLES_D13",
}

REGLAGES = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))


class ListesDeclarees(unittest.TestCase):
    def test_chaque_liste_json_passe_la_garde(self):
        lignes = garde_regles.constats_modules(DOSSIER, DECLARATIONS)
        self.assertEqual(lignes, [], "\n" + "\n".join(lignes))

    def test_les_modules_declares_existent_et_sortent_du_json(self):
        trouves = {p.stem for p in DOSSIER.glob("test_settings_deny_*.py")
                   if p.stem != Path(__file__).stem and garde_regles.imprime_json(p.read_text(encoding="utf-8"))}
        self.assertTrue(set(DECLARATIONS) <= trouves, sorted(set(DECLARATIONS) - trouves))
        self.assertIn("test_settings_deny_revue_equipes", trouves)

    def test_la_liste_json_de_etat_contexte_passe_la_garde(self):
        """etat_contexte.py imprime aussi une liste avec --json (REGLES_D10) sans être un module test_settings_deny_*."""
        import etat_contexte
        self.assertTrue(garde_regles.imprime_json((DOSSIER / "etat_contexte.py").read_text(encoding="utf-8")))
        lignes = [f"garde R-84 : etat_contexte : {c}" for c in garde_regles.constats(etat_contexte.REGLES_D10)]
        self.assertEqual(lignes, [], "\n" + "\n".join(lignes))


class Reglages(unittest.TestCase):
    def test_aucune_cle_de_permission_vide(self):
        lignes = garde_regles.constats_reglages(REGLAGES)
        self.assertEqual(lignes, [], "\n" + "\n".join(lignes))

    def test_aucun_doublon_dans_permissions_deny(self):
        deny = REGLAGES["permissions"]["deny"]
        doublons = sorted({r for r in deny if deny.count(r) > 1})
        self.assertEqual(doublons, [], [f"garde R-84 : règle en double dans .claude/settings.json : {r}" for r in doublons])


class Constats(unittest.TestCase):
    """Le garde sur des listes d'essai."""

    def test_liste_propre(self):
        self.assertEqual(garde_regles.constats(["Read(./a/**)", "Edit(./a/**)", "Bash(uv run x*)"]), [])

    def test_liste_vide(self):
        self.assertEqual(garde_regles.constats([]), ["liste vide"])

    def test_regle_write(self):
        self.assertEqual(garde_regles.constats(["Write(./a/**)"]),
                         ["règle Write(chemin) ou NotebookEdit(chemin) : Claude Code l'ignore ; utiliser Edit(chemin) : Write(./a/**)"])

    def test_regle_notebookedit(self):
        trouves = garde_regles.constats(["NotebookEdit(./a/**)"])
        self.assertEqual(len(trouves), 1)
        self.assertIn("Claude Code l'ignore", trouves[0])
        self.assertTrue(trouves[0].endswith(": NotebookEdit(./a/**)"))

    def test_regles_mal_formees(self):
        for mauvaise in ("", "Read()", "(chemin)", "Read(chemin", "Read chemin", "Read(a) ", None, 3):
            with self.subTest(regle=mauvaise):
                trouves = garde_regles.constats([mauvaise])
                self.assertEqual(len(trouves), 1)
                self.assertIn("règle mal formée (vide ou sans outil)", trouves[0])

    def test_doublon(self):
        self.assertEqual(garde_regles.constats(["Read(./a)", "Read(./b)", "Read(./a)"]), ["règle en double : Read(./a)"])

    def test_une_constat_par_regle_fautive_dans_l_ordre(self):
        trouves = garde_regles.constats(["Write(a)", "Read(b)", "", "Read(b)"])
        self.assertEqual(len(trouves), 3)
        self.assertIn("Write(a)", trouves[0])
        self.assertIn("mal formée", trouves[1])
        self.assertIn("en double", trouves[2])

    def test_reglages_cle_vide(self):
        faux = {"permissions": {"deny": ["Read(./a)"], "allow": []}}
        self.assertEqual(garde_regles.constats_reglages(faux),
                         ["garde R-84 : clé de permission vide dans .claude/settings.json : allow"])
        faux = {"permissions": {"deny": ["Read(./a)"], "defaultMode": ""}}
        self.assertEqual(garde_regles.constats_reglages(faux),
                         ["garde R-84 : clé de permission vide dans .claude/settings.json : defaultMode"])
        self.assertEqual(garde_regles.constats_reglages({"permissions": {"deny": ["Read(./a)"]}}), [])


class Modules(unittest.TestCase):
    """La découverte sur des modules d'essai, dans un dossier temporaire."""

    def _dossier(self, modules: dict) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for nom, texte in modules.items():
            (Path(tmp.name) / f"{nom}.py").write_text(texte, encoding="utf-8")
        return Path(tmp.name)

    SORTIE = '\nif __name__ == "__main__":\n    if "--json" in sys.argv:\n        print(1)\n'

    def test_regles_attendues_propre(self):
        d = self._dossier({"test_settings_deny_a": "import sys\ndef regles_attendues():\n    return ['Read(./a)']\n" + self.SORTIE})
        self.assertEqual(garde_regles.constats_modules(d, {}), [])

    def test_ligne_d_echec_avec_module_et_regle(self):
        d = self._dossier({"test_settings_deny_a": "import sys\ndef regles_attendues():\n    return ['Write(./a)']\n" + self.SORTIE})
        self.assertEqual(garde_regles.constats_modules(d, {}),
                         ["garde R-84 : test_settings_deny_a : règle Write(chemin) ou NotebookEdit(chemin) : "
                          "Claude Code l'ignore ; utiliser Edit(chemin) : Write(./a)"])

    def test_doublon_signale(self):
        d = self._dossier({"test_settings_deny_a": "import sys\nREGLES = ['Read(./a)', 'Read(./a)']\n" + self.SORTIE})
        self.assertEqual(garde_regles.constats_modules(d, {"test_settings_deny_a": "REGLES"}),
                         ["garde R-84 : test_settings_deny_a : règle en double : Read(./a)"])

    def test_sortie_json_sans_fonction_de_liste(self):
        d = self._dossier({"test_settings_deny_a": "import sys\ndef autre():\n    return []\n" + self.SORTIE})
        self.assertEqual(garde_regles.constats_modules(d, {}),
                         ["garde R-84 : test_settings_deny_a : sortie --json sans fonction de liste"])

    def test_liste_avant_la_pose(self):
        """Une liste propre passe même si ses règles ne sont pas dans le fichier de réglages."""
        d = self._dossier({"test_settings_deny_a": "import sys\ndef regles_attendues():\n    return ['Read(./inconnue-du-fichier/**)']\n" + self.SORTIE})
        self.assertEqual(garde_regles.constats_modules(d, {}), [])

    def test_liste_de_retrait_non_controlee(self):
        texte = ("import sys\nREGLES_A_RETIRER = ['Write(./a)', 'NotebookEdit(./a)']\n"
                 "def regles_attendues():\n    return ['Edit(./a)']\n" + self.SORTIE)
        d = self._dossier({"test_settings_deny_a": texte})
        self.assertEqual(garde_regles.constats_modules(d, {}), [])

    def test_module_sans_json_ignore(self):
        d = self._dossier({"test_settings_deny_a": "OPTIONS = ('--json',)\n"})
        self.assertEqual(garde_regles.constats_modules(d, {}), [])

    def test_fonction_declaree_dans_la_table(self):
        d = self._dossier({"test_settings_deny_a": "import sys\ndef ma_liste():\n    return ['Write(x)']\n" + self.SORTIE})
        self.assertEqual(len(garde_regles.constats_modules(d, {"test_settings_deny_a": "ma_liste"})), 1)
        self.assertEqual(garde_regles.constats_modules(d, {}),
                         ["garde R-84 : test_settings_deny_a : sortie --json sans fonction de liste"])


if __name__ == "__main__":
    unittest.main()
