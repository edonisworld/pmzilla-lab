"""Règles `deny` de la sous-commande `flux_jira.py epics` (R-89, conception D1, tâche 2.9, étape utilisateur 10.1).

La session ne lance jamais le rapport de flux des épics (il lit la base) : ni par `uv run`, ni par `python`, ni par `python3`, ni en
exécution directe, quel que soit le chemin du script. Un `grep` du même texte dans la documentation reste permis, comme la lecture du
code, du rapport (Flux-Lab/rapports/) et les autres sous-commandes (`compute`, `statuses`, `compare`). Aucune règle ne commence par un
joker (forme de R-69, D12) : chacune commence par le lanceur ou par le chemin du script.

Même conception que test_settings_deny_rgpd.py : la suite reste VERTE avant et après l'étape 10.1.
 - le moteur de motifs est appliqué au bloc REGLES_EPICS (celui que l'utilisateur copie), pas au fichier de réglages ;
 - le test « les règles sont dans settings.json » est SAUTÉ tant qu'aucune règle n'y est (rouge à la place d'un saut : impossible, le crochet
   de commit exige des suites vertes), ÉCHOUE si certaines seulement y sont (il les nomme) et passe si toutes y sont ; la matrice des formes
   est alors rejouée contre les règles RÉELLES.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    python3 tests/settings_deny/test_settings_deny_epics.py --json     (imprime le bloc à copier dans permissions.deny)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny_rgpd import (CHEMINS_TOOLS, CHEMINS_TOOLS_DIRECTS, LANCEURS, PREFIXES_TOOLS, REGLAGES,  # noqa: E402
                                     Moteur, regles_de_lancement)

REGLES_EPICS = regles_de_lancement("flux_jira.py epics", PREFIXES_TOOLS)
OPTIONS_EPICS = (" epics", " epics --name serie-a", " epics --name x --language en", " epics --language fr --name x",
                 " epics --name x --today 2026-10-18", " epics --help")

# Commandes permises : aucune règle de REGLES_EPICS ne doit les refuser.
COMMANDES_PERMISES = (
    'grep -n "uv run tools/flux_jira.py epics" docs/pmzilla/manuel.md', 'grep -rn "flux_jira.py epics" docs/',
    'git grep -n "python3 tools/flux_jira.py epics --name x" -- docs/', "cat tools/flux_jira.py", "head -40 tools/flux_jira.py",
    "grep -n epics tools/flux_jira.py", "cat Flux-Lab/rapports/epics-serie-a-2026-10-18.md",
    "head -20 ./Flux-Lab/rapports/epics-serie-a-2026-10-18.md", "ls Flux-Lab/rapports",
    "uv run tools/flux_jira.py compare --name epics-serie-a", "python3 tools/flux_jira.py config migrate --dry-run",
    "bash tests/run_all.sh flux_jira", "bash tests/run_all.sh settings_deny",
    "uv run --with numpy --with pyyaml python -W ignore -m unittest discover -s tests/flux_jira -q -f",
    "python3 tests/flux_jira/test_epics_calcul.py", "git log --oneline -3 -- tools/flux_jira.py",
)


def commandes_refusees():
    for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS_TOOLS, OPTIONS_EPICS):
        yield f"{lanceur} {chemin.format(s='flux_jira.py')}{option}"
    for chemin, option in itertools.product(CHEMINS_TOOLS_DIRECTS, OPTIONS_EPICS):
        yield f"{chemin.format(s='flux_jira.py')}{option}"
    for lanceur in ("uv run", "python", "python3"):          # les trois façons de lancer nommées par la tâche 2.9
        yield f"{lanceur} tools/flux_jira.py epics --name serie-a"


class Matrice:
    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} formes de lancement non refusées")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])


class BlocEpics(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à copier : vert avant comme après l'étape 10.1."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_EPICS)

    def test_aucune_regle_ne_commence_par_un_joker(self):
        for regle in REGLES_EPICS:
            self.assertTrue(regle.startswith("Bash(") and regle.endswith(")"), regle)
            self.assertNotEqual(regle[len("Bash("):][:1], "*", regle)

    def test_le_bloc_n_a_pas_de_doublon(self):
        self.assertEqual(len(REGLES_EPICS), len(set(REGLES_EPICS)))

    def test_uv_run_python_et_python3_refuses(self):
        for commande in ("uv run tools/flux_jira.py epics --name x", "python tools/flux_jira.py epics --name x",
                         "python3 tools/flux_jira.py epics --name x"):
            self.assertTrue(self.moteur.interdite(commande), commande)

    def test_chaque_lanceur_chaque_chemin_chaque_option(self):
        self.verifier_formes_refusees()

    def test_un_grep_du_meme_texte_dans_la_documentation_reste_permis(self):
        for commande in COMMANDES_PERMISES[:3]:
            self.assertFalse(self.moteur.interdite(commande), commande)

    def test_ce_qui_reste_permis_autour_de_l_outil(self):
        self.verifier_formes_permises()


class DansLeFichierDeReglages(unittest.TestCase):
    """Étape 10.1 : l'utilisateur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_EPICS if r in cls.deny]
        cls.manquantes = [r for r in REGLES_EPICS if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.fail("étape 10.1 : l'utilisateur n'a pas encore ajouté les règles de flux_jira.py epics")
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_EPICS absente(s) de .claude/settings.json")

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail("étape 10.1 : l'utilisateur n'a pas encore ajouté les règles de flux_jira.py epics")
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_regles_sont_dans_settings_json")
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(REGLES_EPICS, indent=2, ensure_ascii=False))
    else:
        unittest.main()
