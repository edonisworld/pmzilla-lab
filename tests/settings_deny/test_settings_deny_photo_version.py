"""Règles `deny` de tools/version_photo.py (change version-quality-photo, design D12, tâche 1.4 ; spec tooling-permission-guards).

La session ne lance jamais l'outil des photos de qualité par version (`reconstruct`, `take`, `adopt-n`, ni aucune option, `--help` compris : une
règle ne distingue pas les options) : il écrit dans la base sous le rôle d'import. Chaque façon de le lancer est refusée, avec chaque lanceur et
chaque façon d'écrire le chemin. Elle peut lire le code de l'outil, lancer sa suite (tests/version_photo, sans base), lire la vue de la photo avec le
lecteur des vues (`uv run tools/flow_views.py show v_version_quality_photo`) et lancer le lanceur de tests.

Forme ancrée de regles_de_lancement (test_settings_deny_rgpd.py, outil de conservation), les seize règles de D12 : avec un lanceur (`uv run`,
`python`, `python3`), le script précédé d'une barre (tout chemin), nu, ou précédé d'options ; en lancement direct, le chemin au début. Le joker
ne se place jamais devant « version_photo.py » sans barre ni espace : `python3 tests/version_photo/test_version_photo.py` reste permis.
Aucune règle `Write(` ni `NotebookEdit(`, aucune clé de permission vide : la garde partagée (test_settings_deny_listes_declarees.py) le contrôle sur
la liste imprimée par --json.

Conception : l'auteur pose le fragment `.claude/deny/35-photo-version.txt` depuis sa fiche d'étape (liste imprimée par --json, ajoutée à ORDRE, puis
`tools/settings_assemble.py --write`) ; la session n'écrit jamais dans .claude/. Ce module est donc écrit AVANT la pose :
 - les tests de correspondance appliquent le moteur de motifs au bloc REGLES_PHOTO (le bloc à poser), pas au fichier de réglages : verts avant comme après ;
 - les tests du fichier réel sont SAUTÉS tant qu'aucune règle n'y est, ÉCHOUENT si certaines seulement y sont (ils nomment les manquantes : une pose
   partielle) et rejouent la matrice contre les règles réelles quand toutes y sont ;
 - les commandes permises sont aussi vérifiées contre les règles réelles privées de celles du bloc : le résultat est le même avant et après la pose.
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json et tools/version_photo.py (classement des sous-commandes : toute sous-commande
ajoutée sans être classée fait échouer le test).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_photo_version.py --json     (imprime le bloc à poser dans le fragment 35)
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
OUTIL = RACINE / "tools" / "version_photo.py"
SCRIPT = "version_photo.py"

SOUS_COMMANDES = ("reconstruct", "take", "adopt-n")           # toutes refusées : chacune écrit dans la base
LANCEURS_REGLES = ("uv run", "python", "python3")
PREFIXES_TOOLS = ("tools/", "./tools/", "~/*tools/", "$HOME/*tools/", "/*tools/", "", "./")


def regles_de_lancement(commande: str, prefixes: tuple) -> list:
    """Règles qui refusent `commande` sous chaque lanceur et chaque forme de chemin (voir test_settings_deny_rgpd.regles_de_lancement)."""
    regles = []
    for lanceur in LANCEURS_REGLES:
        regles += [f"Bash({lanceur} */{commande}*)", f"Bash({lanceur} {commande}*)", f"Bash({lanceur} * {commande}*)"]
    regles += [f"Bash({prefixe}{commande}*)" for prefixe in prefixes]
    return regles


# Le bloc que l'auteur pose dans le fragment 35 : une règle par ligne, les seize règles de D12.
REGLES_PHOTO = tuple(regles_de_lancement(SCRIPT, PREFIXES_TOOLS))


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_PHOTO)


LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run python3", "uv run --with pyyaml", "uv run -q",
            "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "~/PMZilla-Lab/{s}",
           "/Users/quelquun/PMZilla-Lab/{s}", "{s}")
CHEMINS_DIRECTS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                   "$HOME/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
OPTIONS = ("", " reconstruct", " reconstruct --replace", " take", " take --replace", " take --language en",
           " adopt-n --weeks 6 --adopted-on 2026-11-20", " adopt-n --weeks 8 --adopted-on 2026-12-01 --reason r --language en",
           " --language en take", " --help", " -h")

COMMANDES_PERMISES = (
    "cat tools/version_photo.py", "head -40 tools/version_photo.py", "sed -n 1,60p tools/version_photo.py", "grep -n take tools/version_photo.py",
    "cat tools/version_photo_messages.py", "git log --oneline -3 -- tools/version_photo.py", "git diff -- tools/version_photo.py",
    "ls tests/version_photo", "cat tests/version_photo/test_take.py", "bash tests/run_all.sh version_photo", "bash tests/run_all.sh --staged",
    "bash tests/run_all.sh settings_deny", "bash tests/run_all.sh db",
    "uv run --with pyyaml --with \"psycopg[binary]\" python -W ignore -m unittest discover -s tests/version_photo -q -f",
    "python3 -W ignore -m unittest discover -s tests/version_photo -q",
    "python3 tests/version_photo/test_semaine.py", "python3 tests/version_photo/test_take.py",
    "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_photo_version.py -q",
    "python3 tests/settings_deny/test_settings_deny_photo_version.py --json",
    "uv run tools/flow_views.py show v_version_quality_photo", "uv run tools/flow_views.py show v_team_fix_version_lag",
    "uv run tools/flow_views.py list", "cat db/migrations/0019_flow_version_photo.sql",
    "uv run tools/pilot.py freeze --check", "git grep -n version_photo -- tools tests",
)


def commandes_refusees():
    """Toutes les formes de lancement de l'outil que la session ne doit pas pouvoir exécuter."""
    for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
        yield f"{lanceur} {chemin.format(s=SCRIPT)}{option}"
    for chemin, option in itertools.product(CHEMINS_DIRECTS, OPTIONS):
        yield f"{chemin.format(s=SCRIPT)}{option}"


def sous_commandes_declarees(texte: str) -> set:
    """Sous-commandes de l'analyseur : les `add_parser("nom")` et les noms des `for nom in (...)` qui ajoutent des analyseurs."""
    noms = set(re.findall(r'sous\.add_parser\("([a-z-]+)"', texte))
    for groupe in re.findall(r"for nom in \(([^)]*)\):\s*\n\s+commande = sous\.add_parser\(nom", texte):
        noms |= set(re.findall(r'"([a-z-]+)"', groupe))
    return noms


def sous_commandes_non_classees(texte: str) -> list:
    return sorted(sous_commandes_declarees(texte) - set(SOUS_COMMANDES))


class Moteur:
    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


class Matrice:
    """Cas communs au bloc REGLES_PHOTO et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) de lancement non refusée(s)")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) permise(s) refusée(s) : règle trop large")


class BlocPhoto(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_PHOTO)

    def test_le_bloc_compte_seize_regles_bash_ancrees_sans_doublon(self):
        self.assertEqual(len(REGLES_PHOTO), 16)
        self.assertEqual(len(REGLES_PHOTO), len(set(REGLES_PHOTO)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_PHOTO))
        self.assertEqual([r for r in REGLES_PHOTO if r.startswith("Bash(*")], [], "règle à joker initial")
        self.assertEqual([r for r in REGLES_PHOTO if r.startswith(("Write(", "NotebookEdit("))], [])

    def test_les_seize_regles_de_la_decision_d12(self):
        attendues = [
            "Bash(uv run */version_photo.py*)", "Bash(uv run version_photo.py*)", "Bash(uv run * version_photo.py*)",
            "Bash(python */version_photo.py*)", "Bash(python version_photo.py*)", "Bash(python * version_photo.py*)",
            "Bash(python3 */version_photo.py*)", "Bash(python3 version_photo.py*)", "Bash(python3 * version_photo.py*)",
            "Bash(tools/version_photo.py*)", "Bash(./tools/version_photo.py*)", "Bash(~/*tools/version_photo.py*)",
            "Bash($HOME/*tools/version_photo.py*)", "Bash(/*tools/version_photo.py*)", "Bash(version_photo.py*)", "Bash(./version_photo.py*)"]
        self.assertEqual(sorted(REGLES_PHOTO), sorted(attendues))

    def test_chaque_sous_commande_et_chaque_option_sont_refusees_sous_chaque_lanceur_et_chaque_chemin(self):
        self.verifier_formes_refusees()

    def test_lecture_suite_et_vue_restent_permises(self):
        self.verifier_formes_permises()

    def test_le_joker_ne_touche_pas_les_scripts_de_test(self):
        for commande in ("python3 tests/version_photo/test_version_photo.py", "uv run tests/version_photo/aide_version_photo.py",
                         "python3 tests/db/test_flow_version_photo_outil.py", "bash tests/version_photo/test_x.sh take"):
            self.assertFalse(self.moteur.interdite(commande), commande)

    def test_une_autre_option_de_l_interpreteur_est_refusee(self):
        for commande in ("uv run --with pyyaml python tools/version_photo.py take", "python3 -W ignore tools/version_photo.py reconstruct",
                         "python -I ~/PMZilla-Lab/workspace/tools/version_photo.py adopt-n --weeks 6 --adopted-on 2026-11-20",
                         "uv run -q $HOME/PMZilla-Lab/workspace/tools/version_photo.py take --replace"):
            self.assertTrue(self.moteur.interdite(commande), commande)


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles du bloc : même résultat avant et après la pose."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_PHOTO])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])

    def test_le_lancement_n_est_pas_deja_couvert_par_une_regle_d_avant(self):
        """Garde le sens du bloc : sans lui, l'outil n'est pas refusé."""
        for commande in ("uv run tools/version_photo.py take", "python3 tools/version_photo.py reconstruct"):
            self.assertFalse(self.moteur.interdite(commande), commande)


class ClassementDesSousCommandes(unittest.TestCase):
    """Une sous-commande ajoutée à l'outil sans être classée fait échouer le test."""

    def test_le_detecteur_nomme_une_sous_commande_inconnue(self):
        texte = ('    sous = analyseur.add_subparsers(dest="commande")\n    for nom in ("reconstruct", "take"):\n'
                 '        commande = sous.add_parser(nom, add_help=False)\n    adoption = sous.add_parser("adopt-n", add_help=False)\n'
                 '    autre = sous.add_parser("purge", add_help=False)\n')
        self.assertEqual(sous_commandes_non_classees(texte), ["purge"])
        self.assertEqual(sous_commandes_non_classees(texte.replace('    autre = sous.add_parser("purge", add_help=False)\n', "")), [])

    def test_l_outil_ne_declare_que_des_sous_commandes_classees(self):
        self.assertTrue(OUTIL.is_file(), "tools/version_photo.py absent")
        texte = OUTIL.read_text(encoding="utf-8")
        self.assertEqual(sous_commandes_declarees(texte), set(SOUS_COMMANDES))
        self.assertEqual(sous_commandes_non_classees(texte), [])


class DansLeFichierDeReglages(unittest.TestCase):
    """La pose par l'auteur : sautée avant, échoue si elle est partielle, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_PHOTO if r in cls.deny]
        cls.manquantes = [r for r in REGLES_PHOTO if r not in cls.deny]

    # Désherbage du 2026-10-28 (D79) : les branches de saut « fragment 35 pas encore posé » sont retirées (le fragment 35 est dans settings.json) ;
    # sans règle posée, `manquantes` les nomme toutes et le test échoue.

    def test_les_regles_sont_dans_settings_json(self):
        self.assertEqual(self.manquantes, [], f"pose partielle : {len(self.manquantes)} règle(s) de REGLES_PHOTO absente(s) de .claude/settings.json")

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes))
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
