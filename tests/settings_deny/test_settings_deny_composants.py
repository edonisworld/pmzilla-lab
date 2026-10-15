"""Règles `deny` pour `tools/composants.py check` (change components-watch, design D14, tâche 6.1 ; fiche C18).

La session ne lance jamais `composants.py check` : il interroge les sources amont (réseau), ce que font seuls la veille quotidienne et
l'utilisateur. Elle lance `composants.py inventory` (avec ou sans `--verify`, hors réseau), le lanceur de tests et les suites.

Ce fichier est écrit AVANT l'ajout de l'auteur (tâche 8.1) : REGLES_A_AJOUTER est la liste exacte des règles à coller dans
permissions.deny de .claude/settings.json. Tant qu'aucune n'y figure, les cas contre les vrais réglages sont SAUTÉS ; si l'ajout est
partiel, ils échouent en nommant les règles manquantes ; une fois toutes présentes, ils vérifient chaque forme contre la vraie liste.
La classe ReglesProposees évalue les mêmes cas, avec le même moteur, sur REGLES_A_AJOUTER seule : elle est toujours verte.
Les formes autorisées (inventory, lanceur de tests, lecture du fichier) sont vérifiées contre les vrais réglages dans tous les cas.
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base, motif_en_regex  # noqa: E402

# Règles à ajouter à permissions.deny, sur le modèle de celles de tools/flow_retention.py. Le motif « composants.py*check* » couvre
# aussi une option placée avant la sous-commande (« --root X check ») ; « inventory » n'y contient pas « check ».
REGLES_A_AJOUTER = [
    "Bash(uv run */composants.py*check*)", "Bash(uv run composants.py*check*)", "Bash(uv run * composants.py*check*)",
    "Bash(python */composants.py*check*)", "Bash(python composants.py*check*)", "Bash(python * composants.py*check*)",
    "Bash(python3 */composants.py*check*)", "Bash(python3 composants.py*check*)", "Bash(python3 * composants.py*check*)",
    "Bash(tools/composants.py*check*)", "Bash(./tools/composants.py*check*)", "Bash(~/*tools/composants.py*check*)",
    "Bash($HOME/*tools/composants.py*check*)", "Bash(/*tools/composants.py*check*)",
    "Bash(composants.py*check*)", "Bash(./composants.py*check*)",
]

LANCEURS_PY = ("uv run", "uv run -q", "uv run --with pyyaml python", "python", "python3", "python3 -I")
CHEMINS_AVEC_LANCEUR = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                        "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}")
LANCEURS_DIRECTS = ("",)
CHEMINS_DIRECTS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                   "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
SUITES_CHECK = ("check", "check --if-due", "check --only numpy", "check --timeout 3", "check --if-due --timeout 3 --only numpy",
                "check --root /tmp/x", "--root /tmp/x check", "--root /tmp/x check --if-due")

COMMANDES_PERMISES = (
    "uv run tools/composants.py inventory", "uv run tools/composants.py inventory --verify",
    "uv run --with pyyaml python tools/composants.py inventory --verify", "python3 tools/composants.py inventory",
    "./tools/composants.py inventory --verify", "python3 composants.py inventory --verify",
    "uv run tools/composants.py inventory --root /tmp/x",
    "bash tests/run_all.sh", "bash tests/run_all.sh composants", "bash tests/run_all.sh --staged",
    "uv run --with pyyaml python -m unittest discover -s tests/composants",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/composants -q -f",
    "cat tools/composants.py", "grep -n check tools/composants.py", "head -n 40 tools/composants.py",
    "sed -n 1,20p tools/composants.py", "ls tests/composants",
)


def commandes_check():
    for lanceur, chemin, suite in itertools.product(LANCEURS_PY, CHEMINS_AVEC_LANCEUR, SUITES_CHECK):
        yield f"{lanceur} {chemin.format(s='composants.py')} {suite}"
    for chemin, suite in itertools.product(CHEMINS_DIRECTS, SUITES_CHECK):
        yield f"{chemin.format(s='composants.py')} {suite}"


class Verifications:
    """Cas communs : `interdite` vient du moteur de la classe qui les mélange."""

    def verifier_formes_interdites(self):
        manquantes = [c for c in commandes_check() if not self.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) de composants.py check non interdite(s)")

    def verifier_formes_permises(self):
        interdites = [c for c in COMMANDES_PERMISES if self.interdite(c)]
        self.assertEqual(interdites, [], "commande(s) permise(s) interdite(s)")


class ReglesProposees(Verifications, unittest.TestCase):
    """REGLES_A_AJOUTER seule, avec le moteur de Base : toujours verte."""

    @classmethod
    def setUpClass(cls):
        cls.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in REGLES_A_AJOUTER]

    def interdite(self, commande):
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_toute_forme_de_check_est_interdite(self):
        self.verifier_formes_interdites()

    def test_inventory_lanceur_de_tests_et_lecture_restent_permis(self):
        self.verifier_formes_permises()

    def test_pas_de_regle_en_double(self):
        self.assertEqual(len(REGLES_A_AJOUTER), len(set(REGLES_A_AJOUTER)))


class DansLeFichierDeReglages(Verifications, Base):
    """Tâche 8.1 : l'auteur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    def presentes(self):
        return [r for r in REGLES_A_AJOUTER if r in self.deny], [r for r in REGLES_A_AJOUTER if r not in self.deny]

    def test_les_regles_sont_dans_settings_json(self):
        presentes, manquantes = self.presentes()
        if not presentes:
            self.skipTest("tâche 8.1 : l'auteur n'a pas encore ajouté les règles de composants.py check")
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) de REGLES_A_AJOUTER absente(s) de .claude/settings.json")

    def test_toute_forme_de_check_est_interdite_par_les_regles_reelles(self):
        presentes, manquantes = self.presentes()
        if not presentes:
            self.skipTest("tâche 8.1 : l'auteur n'a pas encore ajouté les règles de composants.py check")
        if manquantes:
            self.fail("règles manquantes : " + " ; ".join(manquantes))
        self.verifier_formes_interdites()

    def test_inventory_lanceur_de_tests_et_lecture_sont_permis_dans_tous_les_cas(self):
        self.verifier_formes_permises()


if __name__ == "__main__":
    unittest.main()
