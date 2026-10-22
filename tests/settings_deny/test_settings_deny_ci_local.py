"""Règles `deny` de `tools/ci_local.sh` (change local-ci-container, design D12, tâche 9.1 ; l'ajout est la tâche 9.2 de l'auteur).

La session ne lance jamais `build` ni `up` (réseau, construction de l'image, démarrage de Colima : gestes de l'auteur), sous `bash`, `sh`, `zsh`
ou en lancement direct, par chemin relatif, absolu ou depuis le dossier personnel. Elle peut lancer `run` (avec ou sans branche), `--help`
et `-h`, lire le script et lancer sa suite (tests/ci_local) et le lanceur de tests.

Forme ancrée de regles_de_lancement (test_settings_deny_rgpd.py, outils Jira et flux), avec les lanceurs du shell : avec un lanceur, le script
précédé d'une barre (tout chemin), nu, ou précédé d'options ; en lancement direct, le chemin au début. Le joker ne se place jamais devant
« ci_local.sh » sans barre ni espace : `bash tests/ci_local/test_ci_local.sh` reste permis.

Ce fichier est écrit AVANT l'ajout de l'auteur : la classe BlocD12 applique les cas au bloc REGLES_D12 seul et reste verte ; la classe
DansLeFichierDeReglages ÉCHOUE tant qu'aucune règle n'est posée (rouge jusqu'à la tâche 9.2), échoue en nommant les manquantes si l'ajout
est partiel, et rejoue la matrice contre les règles réelles une fois toutes posées. Aucune commande n'est lancée ; le test ne lit que
.claude/settings.json et tools/ci_local.sh (classement des sous-commandes : toute sous-commande ajoutée sans être classée fait échouer le test).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_ci_local.py --json       (imprime le bloc à poser dans permissions.deny)
    python3 tests/settings_deny/test_settings_deny_ci_local.py --familles   (le bloc par famille)
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
OUTIL = RACINE / "tools" / "ci_local.sh"
SCRIPT = "ci_local.sh"

SOUS_COMMANDES_REFUSEES = ("build", "up")
SOUS_COMMANDES_PERMISES = ("run",)
LANCEURS_REGLES = ("bash", "sh", "zsh")
PREFIXES = ("tools/", "./tools/", "../*tools/", "~/*tools/", "$HOME/*tools/", "/*tools/", "", "./")


def regles_de_lancement(commande: str) -> list:
    """Règles qui refusent `commande` (script et sous-commande) sous chaque lanceur du shell et en lancement direct."""
    regles = []
    for lanceur in LANCEURS_REGLES:
        regles += [f"Bash({lanceur} */{commande}*)", f"Bash({lanceur} {commande}*)", f"Bash({lanceur} * {commande}*)"]
    regles += [f"Bash({prefixe}{commande}*)" for prefixe in PREFIXES]
    return regles


# Le bloc que l'auteur pose à la fin de permissions.deny de .claude/settings.json (tâche 9.2) : une chaîne par règle.
REGLES_D12 = tuple(r for sous in SOUS_COMMANDES_REFUSEES for r in regles_de_lancement(f"{SCRIPT} {sous}"))


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_D12)

LANCEURS = ("bash", "sh", "zsh", "bash -x", "bash --norc", "zsh -f", "sh -e")
CHEMINS = ("tools/{s}", "./tools/{s}", "../tools/{s}", "../workspace/tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "~/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
CHEMINS_DIRECTS = ("tools/{s}", "./tools/{s}", "../tools/{s}", "../workspace/tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}",
                   "/Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                   "~/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
# Un shell nommé par son chemin absolu n'est couvert que par la règle du chemin absolu des tools : seulement avec un chemin qui contient tools/.
LANCEURS_ABSOLUS = ("/bin/bash", "/bin/sh", "/bin/zsh")
CHEMINS_AVEC_TOOLS = tuple(c for c in CHEMINS if "tools/" in c)
OPTIONS_PAR_SOUS_COMMANDE = {
    "build": ("",),
    "up": ("", " main", " feat/local-ci-container", " feat/x"),
}

COMMANDES_PERMISES = (
    "bash tests/ci_local/test_ci_local.sh", "sh -n tests/ci_local/test_ci_local.sh", "bash tests/run_all.sh ci_local",
    "bash tests/run_all.sh --portable", "bash tests/run_all.sh --mac", "bash tests/run_all.sh --staged", "bash tests/run_all.sh settings_deny",
    "bash tests/run_all.sh run_all", "cat tools/ci_local.sh", "head -n 40 tools/ci_local.sh", "sed -n 1,60p tools/ci_local.sh",
    "grep -n build tools/ci_local.sh", "grep -n up tools/ci_local.sh", "git log --oneline -- tools/ci_local.sh", "git diff -- tools/ci_local.sh",
    "git grep ci_local.sh -- docs/", "grep -rn 'ci_local.sh up' docs/ openspec/", "ls tests/ci_local", "cat ci/Dockerfile",
    "uv run tools/pilot.py freeze --check",
)


def commandes_permises_du_script():
    """`run` (avec ou sans branche, une branche nommée build ou up comprise), `--help` et `-h`, sous chaque forme de lancement."""
    suites = ("run", "run main", "run feat/local-ci-container", "run build-fix", "run up-to-date", "--help", "-h")
    for lanceur, chemin, suite in itertools.product(LANCEURS, CHEMINS, suites):
        yield f"{lanceur} {chemin.format(s=SCRIPT)} {suite}"
    for chemin, suite in itertools.product(CHEMINS_DIRECTS, suites):
        yield f"{chemin.format(s=SCRIPT)} {suite}"


def commandes_refusees():
    """Toutes les formes de lancement de `build` et `up` que la session ne doit pas pouvoir exécuter."""
    for sous, options in OPTIONS_PAR_SOUS_COMMANDE.items():
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, options):
            yield f"{lanceur} {chemin.format(s=SCRIPT)} {sous}{option}"
        for lanceur, chemin, option in itertools.product(LANCEURS_ABSOLUS, CHEMINS_AVEC_TOOLS, options):
            yield f"{lanceur} {chemin.format(s=SCRIPT)} {sous}{option}"
        for chemin, option in itertools.product(CHEMINS_DIRECTS, options):
            yield f"{chemin.format(s=SCRIPT)} {sous}{option}"


def sous_commandes_declarees(texte: str) -> set:
    """Sous-commandes du premier `case "$SOUS" in` du script (bras `nom)` ou `a|b)`), options exclues."""
    debut = texte.find('case "$SOUS" in')
    if debut < 0:
        return set()
    bloc = texte[debut:texte.find("esac", debut)]
    noms = set()
    for bras in re.findall(r"^\s+([a-z|-]+)\)", bloc, re.MULTILINE):
        noms |= {n for n in bras.split("|") if n and not n.startswith("-")}
    return noms


def sous_commandes_non_classees(texte: str) -> list:
    return sorted(sous_commandes_declarees(texte) - set(SOUS_COMMANDES_REFUSEES) - set(SOUS_COMMANDES_PERMISES))


class Moteur:
    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


class Matrice:
    """Cas communs au bloc REGLES_D12 et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) de lancement de build ou up non refusée(s)")

    def verifier_formes_permises(self):
        refusees = [c for c in commandes_permises_du_script() if self.moteur.interdite(c)]
        self.assertEqual(refusees[:5], [], f"{len(refusees)} forme(s) de run ou --help refusée(s) : règle trop large")
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) permise(s) refusée(s) : règle trop large")


class BlocD12(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la tâche 9.2."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_D12)

    def test_le_bloc_compte_34_regles_bash_ancrees_sans_doublon(self):
        self.assertEqual(len(REGLES_D12), 34)
        self.assertEqual(len(REGLES_D12), len(set(REGLES_D12)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_D12))
        self.assertEqual([r for r in REGLES_D12 if r.startswith("Bash(*")], [], "règle à joker initial")

    def test_build_et_up_refuses_sous_chaque_lanceur_et_chaque_chemin(self):
        self.verifier_formes_refusees()

    def test_run_aide_lecture_et_suite_restent_permis(self):
        self.verifier_formes_permises()

    def test_le_joker_ne_touche_pas_le_script_de_test(self):
        for commande in ("bash tests/ci_local/test_ci_local.sh build", "bash tests/ci_local/test_ci_local.sh up"):
            self.assertFalse(self.moteur.interdite(commande), commande)


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de REGLES_D12 : même résultat avant et après la tâche 9.2."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_D12])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in commandes_permises_du_script() if self.moteur.interdite(c)][:5], [])
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])

    def test_build_et_up_ne_sont_pas_deja_couverts_par_une_regle_d_avant(self):
        """Garde le sens du bloc : sans lui, build et up ne sont pas refusés."""
        self.assertFalse(self.moteur.interdite("bash tools/ci_local.sh build"))
        self.assertFalse(self.moteur.interdite("bash tools/ci_local.sh up"))


class ClassementDesSousCommandes(unittest.TestCase):
    """Une sous-commande ajoutée au script sans être classée (refusée ou permise) fait échouer le test."""

    def test_le_detecteur_nomme_une_sous_commande_inconnue(self):
        texte = 'case "$SOUS" in\n  --help|-h) aide ;;\n  run|up) x ;;\n  build) y ;;\n  purge) z ;;\n  *) usage ;;\nesac\n'
        self.assertEqual(sous_commandes_non_classees(texte), ["purge"])
        self.assertEqual(sous_commandes_non_classees(texte.replace("  purge) z ;;\n", "")), [])

    def test_les_deux_listes_sont_disjointes(self):
        self.assertEqual(set(SOUS_COMMANDES_REFUSEES) & set(SOUS_COMMANDES_PERMISES), set())

    def test_le_script_ne_declare_que_des_sous_commandes_classees(self):
        self.assertTrue(OUTIL.is_file(), "tools/ci_local.sh absent")
        texte = OUTIL.read_text(encoding="utf-8")
        self.assertEqual(sous_commandes_declarees(texte), {"run", "build", "up"})
        self.assertEqual(sous_commandes_non_classees(texte), [])


class DansLeFichierDeReglages(unittest.TestCase):
    """Tâche 9.2 : l'auteur pose les règles. Rouge avant, échoue si l'ajout est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_D12 if r in cls.deny]
        cls.manquantes = [r for r in REGLES_D12 if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.fail("tâche 9.2 : l'auteur n'a pas encore posé les règles de ci_local.sh")
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_D12 absente(s) de .claude/settings.json")

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail("tâche 9.2 : l'auteur n'a pas encore posé les règles de ci_local.sh")
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes))
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


def familles() -> list:
    lignes = []
    for sous in SOUS_COMMANDES_REFUSEES:
        regles = [r for r in REGLES_D12 if f"{SCRIPT} {sous}*)" in r]
        avec = [r for r in regles if r.startswith(tuple(f"Bash({lanceur} " for lanceur in LANCEURS_REGLES))]
        lignes.append(f"{sous} : {len(regles)} règles ({len(avec)} avec bash, sh ou zsh ; {len(regles) - len(avec)} en lancement direct)")
    lignes.append(f"total : {len(REGLES_D12)} règles")
    return lignes


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--familles" in sys.argv:
        print("\n".join(familles()))
    else:
        unittest.main()
