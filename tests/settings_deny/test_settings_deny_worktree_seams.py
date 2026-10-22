"""Règles `deny` des coutures de test de `tools/worktree.sh` (change mothra-npm-ready, revue 6.1, constat E2 ; la pose est le geste de l'auteur).

`tools/worktree.sh` honore deux variables prévues pour ses tests : WORKTREE_TERMINAL (1 ou 0 : force l'entrée standard à valoir terminal ou non)
et WORKTREE_NPM (remplace la commande npm). Hors des tests, une session pourrait lancer
`printf 'o\\n' | WORKTREE_TERMINAL=1 bash tools/worktree.sh <b>` et faire partir `npm ci --offline` sans le oui de l'auteur ; avec WORKTREE_NPM,
une commande quelconque. Les règles ci-dessous refusent toute commande qui pose l'une des deux variables (`WORKTREE_TERMINAL=` ou `WORKTREE_NPM=`
n'importe où dans la commande) et tout `export WORKTREE_*`.

Joker initial voulu (précédent des règles `*=* uv run */library_parity.py*`) : la variable peut se trouver derrière `printf ... |`, `env`, `cd x &&`,
un chemin relatif, absolu, `~` ou `$HOME`, sous bash, sh, zsh ou en lancement direct.

Limite connue : une commande qui contient « WORKTREE_NPM= » ou « WORKTREE_TERMINAL= » (avec le signe égal) est refusée aussi, une recherche comprise
(`git grep WORKTREE_NPM=`) ; chercher sans le signe égal (`git grep WORKTREE_NPM`). Les suites (`bash tests/worktree/test_worktree.sh`,
`bash tests/run_all.sh worktree`) posent ces variables à l'intérieur du script de test, pas dans la commande de la session : elles restent permises.

Ce fichier est écrit AVANT la pose : la classe BlocE2 applique les cas au bloc REGLES_E2 seul et reste verte ; la classe DansLeFichierDeReglages
ÉCHOUE tant qu'aucune règle n'est posée, échoue en nommant les manquantes si la pose est partielle, et rejoue la matrice contre les règles réelles
une fois toutes posées. Aucune commande n'est lancée ; le test ne lit que .claude/settings.json et tools/worktree.sh (toute nouvelle variable de
couture WORKTREE_* lue par le script sans être couverte fait échouer le test).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_worktree_seams.py --json       (imprime le bloc à poser dans permissions.deny)
    python3 tests/settings_deny/test_settings_deny_worktree_seams.py --familles   (le bloc par famille)
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
OUTIL = RACINE / "tools" / "worktree.sh"
SCRIPT = "worktree.sh"

COUTURES = ("WORKTREE_TERMINAL", "WORKTREE_NPM")

# Le bloc que l'auteur pose à la fin de permissions.deny de .claude/settings.json : une chaîne par règle, dans cet ordre.
REGLES_E2 = (
    "Bash(*WORKTREE_TERMINAL=*)",
    "Bash(*WORKTREE_NPM=*)",
    "Bash(export WORKTREE_*)",
)


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_E2)


LANCEURS = ("bash", "sh", "zsh")
CHEMINS = ("tools/{s}", "./tools/{s}", "../tools/{s}", "../workspace/tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "~/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
CHEMINS_DIRECTS = CHEMINS
VARIABLES_POSEES = ("WORKTREE_TERMINAL=1", "WORKTREE_TERMINAL=0", "WORKTREE_TERMINAL=", "WORKTREE_NPM=/bin/echo", "WORKTREE_NPM=x",
                    "WORKTREE_NPM=", "WORKTREE_NPM='/bin/echo ok'", 'WORKTREE_NPM="$HOME/faux-npm"')
DEVANTS = ("", "printf 'o\\n' | ", "printf 'o\\n' | env ", "env ", "cd x && ", "cd x && printf 'o\\n' | ", "yes o | ", "echo o | ")

COMMANDES_PERMISES = (
    "bash tests/worktree/test_worktree.sh", "sh -n tests/worktree/test_worktree.sh", "bash tests/run_all.sh worktree",
    "bash tests/run_all.sh --staged", "bash tests/run_all.sh --portable", "bash tests/run_all.sh settings_deny",
    "git grep WORKTREE_NPM", "git grep WORKTREE_TERMINAL", "git grep -n WORKTREE_ -- tools/ tests/",
    "grep -n WORKTREE_TERMINAL tools/worktree.sh", "grep -n WORKTREE_NPM tools/worktree.sh", "grep -n WORKTREE tools/worktree.sh",
    "git diff -- tools/worktree.sh", "git log --oneline -- tools/worktree.sh", "cat tools/worktree.sh", "uv run tools/doctor.py",
    "uv run tools/pilot.py freeze --check", "ls tests/worktree",
)


def commandes_permises_du_script():
    """Le script lancé sans variable de couture, sous chaque lanceur et chaque chemin, avec ou sans entrée redirigée."""
    suites = ("feat/x", "feat/x ../wt-x", "main")
    for devant, lanceur, chemin, suite in itertools.product(("", "cd x && ", "printf 'o\\n' | "), LANCEURS, CHEMINS, suites):
        yield f"{devant}{lanceur} {chemin.format(s=SCRIPT)} {suite}"
    for chemin, suite in itertools.product(CHEMINS_DIRECTS, suites):
        yield f"{chemin.format(s=SCRIPT)} {suite}"


def commandes_refusees():
    """Toutes les formes qui posent une variable de couture devant (ou avant) le script, et les `export`."""
    for devant, variable, lanceur, chemin in itertools.product(DEVANTS, VARIABLES_POSEES, LANCEURS, CHEMINS):
        yield f"{devant}{variable} {lanceur} {chemin.format(s=SCRIPT)} feat/x"
    for devant, variable, chemin in itertools.product(DEVANTS, VARIABLES_POSEES, CHEMINS_DIRECTS):
        yield f"{devant}{variable} {chemin.format(s=SCRIPT)} feat/x"
    for variable in VARIABLES_POSEES:
        yield f"export {variable}"
        yield f"export {variable}; bash tools/worktree.sh feat/x"
        yield f"export {variable} && bash tools/worktree.sh feat/x"
    for nom in COUTURES:
        yield f"export {nom}"
        yield f"export {nom}; bash tools/worktree.sh feat/x"
        yield "export WORKTREE_AUTRE=1"


def variables_de_couture_lues(texte: str) -> set:
    """Variables WORKTREE_* lues par le script, commentaires exclus : `$WORKTREE_X`, `${WORKTREE_X...}` ou `WORKTREE_X=` en code."""
    lues = set()
    for ligne in texte.splitlines():
        code = ligne.split("#", 1)[0] if ligne.lstrip().startswith("#") else re.sub(r"(^|\s)#.*$", "", ligne)
        lues |= set(re.findall(r"\bWORKTREE_[A-Z0-9_]+", code))
    return lues


class Moteur:
    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


class Matrice:
    """Cas communs au bloc REGLES_E2 et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) posant une couture de worktree.sh non refusée(s)")

    def verifier_formes_permises(self):
        refusees = [c for c in commandes_permises_du_script() if self.moteur.interdite(c)]
        self.assertEqual(refusees[:5], [], f"{len(refusees)} lancement(s) de worktree.sh sans couture refusé(s) : règle trop large")
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) permise(s) refusée(s) : règle trop large")


class BlocE2(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_E2)

    def test_le_bloc_compte_3_regles_bash_sans_doublon_dans_l_ordre(self):
        self.assertEqual(len(REGLES_E2), 3)
        self.assertEqual(len(REGLES_E2), len(set(REGLES_E2)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_E2))
        self.assertEqual(list(REGLES_E2), ["Bash(*WORKTREE_TERMINAL=*)", "Bash(*WORKTREE_NPM=*)", "Bash(export WORKTREE_*)"])

    def test_chaque_couture_posee_devant_la_commande_est_refusee(self):
        self.verifier_formes_refusees()

    def test_le_script_sans_couture_la_lecture_et_les_suites_restent_permis(self):
        self.verifier_formes_permises()

    def test_la_limite_connue_une_recherche_avec_le_signe_egal_est_refusee(self):
        self.assertTrue(self.moteur.interdite("git grep WORKTREE_NPM="))
        self.assertFalse(self.moteur.interdite("git grep WORKTREE_NPM"))


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de REGLES_E2 : même résultat avant et après la pose."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_E2])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in commandes_permises_du_script() if self.moteur.interdite(c)][:5], [])
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])

    def test_les_coutures_ne_sont_pas_deja_couvertes_par_une_regle_d_avant(self):
        """Garde le sens du bloc : sans lui, poser une couture n'est pas refusé."""
        self.assertFalse(self.moteur.interdite("WORKTREE_TERMINAL=1 bash tools/worktree.sh feat/x"))
        self.assertFalse(self.moteur.interdite("printf 'o\\n' | WORKTREE_TERMINAL=1 bash tools/worktree.sh feat/x"))
        self.assertFalse(self.moteur.interdite("WORKTREE_NPM=/bin/echo bash tools/worktree.sh feat/x"))
        self.assertFalse(self.moteur.interdite("export WORKTREE_TERMINAL=1"))


class CouverturesDuScript(unittest.TestCase):
    """Une nouvelle variable de couture WORKTREE_* lue par le script sans être couverte fait échouer le test."""

    def test_le_detecteur_nomme_une_variable_inconnue(self):
        texte = '# WORKTREE_COMMENTAIRE n\'est pas lue\nnpm=${WORKTREE_NPM:-npm}\ncase "${WORKTREE_TERMINAL:-}" in\n  x=$WORKTREE_NOUVELLE\n'
        self.assertEqual(variables_de_couture_lues(texte), {"WORKTREE_NPM", "WORKTREE_TERMINAL", "WORKTREE_NOUVELLE"})
        self.assertEqual(variables_de_couture_lues("PMZILLA_LAB_WORKTREES=x\nWORKTREE_NPM=y"), {"WORKTREE_NPM"})

    def test_les_coutures_declarees_sont_couvertes_par_le_bloc(self):
        for nom in COUTURES:
            self.assertTrue(any(f"{nom}=" in r for r in REGLES_E2), nom)

    def test_le_script_ne_lit_que_les_deux_coutures_couvertes(self):
        self.assertTrue(OUTIL.is_file(), "tools/worktree.sh absent")
        lues = variables_de_couture_lues(OUTIL.read_text(encoding="utf-8"))
        self.assertEqual(sorted(lues), sorted(COUTURES),
                         "tools/worktree.sh lit une variable de couture WORKTREE_* sans règle deny dans REGLES_E2")


class DansLeFichierDeReglages(unittest.TestCase):
    """L'auteur pose les règles. Rouge avant, échoue si la pose est partielle, passe si tout y est."""

    MESSAGE = "l'auteur n'a pas encore posé les règles des coutures de worktree.sh"

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_E2 if r in cls.deny]
        cls.manquantes = [r for r in REGLES_E2 if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.fail(self.MESSAGE)
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_E2 absente(s) de .claude/settings.json : "
                                              + " ; ".join(self.manquantes))

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail(self.MESSAGE)
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes))
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


def familles() -> list:
    return [
        f"variable posée devant la commande : {sum(1 for r in REGLES_E2 if r.startswith('Bash(*'))} règles (WORKTREE_TERMINAL=, WORKTREE_NPM=)",
        f"export : {sum(1 for r in REGLES_E2 if r.startswith('Bash(export '))} règle (export WORKTREE_*)",
        f"total : {len(REGLES_E2)} règles",
    ]


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--familles" in sys.argv:
        print("\n".join(familles()))
    else:
        unittest.main()
