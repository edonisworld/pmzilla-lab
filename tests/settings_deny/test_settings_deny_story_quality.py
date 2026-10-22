"""Règles `deny` du change story-quality-audit (R-78, design D13, tâche 1.2, spec tooling-permission-guards).

La session ne lance jamais `tools/story_quality.py collect`, `review`, `analyse` ni `coach` (avec ou sans --show, --dry-run, --sample,
--team, --keys), ne lance aucune commande `security` qui cite le service Trousseau de la clé d'analyse, et ne lit, n'écrit ni ne modifie le
sous-dossier `regles/` du dossier de contexte (la surcouche de l'organisation). Elle peut lancer `report`, `grid` et `grid --show`, l'aide du
script, lire son code, lancer sa suite de tests et le lanceur de tests, lire le schéma de la surcouche et la surcouche d'exemple.

Conception (même motif que test_settings_deny_rgpd.py) : l'utilisateur ajoute les règles à .claude/settings.json à l'étape 1.7. La suite
reste donc VERTE avant et après :
 - la matrice des formes s'applique au bloc REGLES_D13 (celui que l'utilisateur copiera), pas au fichier de réglages ;
 - le test « les règles sont dans settings.json » est SAUTÉ tant qu'aucune règle n'y est, ÉCHOUE si certaines seulement y sont (il les
   nomme) et passe si toutes y sont ; la matrice est alors rejouée contre les règles RÉELLES ;
 - les commandes permises sont aussi vérifiées contre les règles réelles privées de celles de REGLES_D13 : même résultat avant et après 1.7.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json et, s'il existe, tools/story_quality.py (classement des
sous-commandes : toute sous-commande ajoutée sans être classée refusée ou permise fait échouer le test).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_story_quality.py --json     (imprime le bloc à copier dans permissions.deny)
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
from test_settings_deny_offsite_backup import glob_en_regex  # noqa: E402
from test_settings_deny_rgpd import (  # noqa: E402
    CHEMINS_TOOLS, CHEMINS_TOOLS_DIRECTS, LANCEURS, LECTEURS_TERMINAL, PREFIXES_TOOLS, regles_de_lancement,
)

from etat_contexte import REGLES_D10, nom_du_dossier  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
OUTIL = RACINE / "tools" / "story_quality.py"
# Organisation-context (design D10, D16) : le dossier de contexte change de nom avec la tâche 9.3 de l'auteur. Les règles de la surcouche portent
# le nom que le fichier de réglages porte (l'ancien avant, `contexte` après), donc cette suite reste verte dans les deux états ; les règles
# reposées de D10 sont un sur-ensemble de ce bloc pour la surcouche (voir test_settings_deny_contexte.py).
DOSSIER = nom_du_dossier()

SOUS_COMMANDES_REFUSEES = ("collect", "review", "analyse", "coach")
SOUS_COMMANDES_PERMISES = ("report", "grid")
SERVICE_CLE_ANALYSE = "pmzilla-story-analysis"          # service par défaut de la clé d'analyse dans le Trousseau (réglage engine)
FICHIER_SURCOUCHE = "surcouche-qualite-stories.yaml"
LECTEURS_SURCOUCHE = LECTEURS_TERMINAL + ("strings",)    # ceux des notes de contexte : cat head tail less more grep awk sed cp strings

# Le bloc que l'utilisateur copie dans permissions.deny de .claude/settings.json (étape 1.7) : une chaîne par règle.
REGLES_D13 = tuple(
    [r for sous in SOUS_COMMANDES_REFUSEES for r in regles_de_lancement(f"story_quality.py {sous}", PREFIXES_TOOLS)]
    + [f"Bash(security *{SERVICE_CLE_ANALYSE}*)"]
    # Read et Edit seulement : une règle Edit couvre aussi Write et NotebookEdit (R-84, aucune règle Write ne réapparaît).
    + [f"{outil}({chemin})" for outil in ("Read", "Edit")
       for chemin in (f"~/PMZilla-Lab/{DOSSIER}/regles/**", f"//**/{DOSSIER}/regles/**", f"**/{DOSSIER}/regles/**")]
    + [f"Bash({lecteur} *{DOSSIER}/regles*)" for lecteur in LECTEURS_SURCOUCHE]
    + [f"Bash({lecteur} *{DOSSIER}/*/{FICHIER_SURCOUCHE}*)" for lecteur in LECTEURS_SURCOUCHE]
)

OPTIONS_PAR_SOUS_COMMANDE = {
    "collect": ("", " --query q1", " --language en", " --query q1 --language fr"),
    "review": (" --team equipe-a --sample 5", " --team equipe-a --sample 5 --language en"),
    "analyse": ("", " --dry-run", " --sample 3", " --sample 3 --team equipe-a", " --sample 3 --dry-run", " --sample 3 --team equipe-a --dry-run",
                " --language en", " --dry-run --language en"),
    "coach": (" --team equipe-a", " --keys PROJ-1", " --keys PROJ-1 PROJ-2", " --team equipe-a --show", " --team equipe-a --dry-run",
              " --keys PROJ-1 --show", " --keys PROJ-1 --dry-run", " --team equipe-a --language en"),
}

DOSSIERS_CONTEXTE = (DOSSIER, f"./{DOSSIER}", f"/Users/quelquun/PMZilla-Lab/{DOSSIER}", f"~/PMZilla-Lab/{DOSSIER}",
                     f"$HOME/PMZilla-Lab/{DOSSIER}")
OPTIONS_LECTEUR = ("", "-n 5 ", "-r ")
CHEMINS_SURCOUCHE_READ = (
    f"{DOSSIER}/regles/surcouche-qualite-stories.yaml", f"./{DOSSIER}/regles/surcouche-qualite-stories.yaml",
    f"/Users/quelquun/PMZilla-Lab/{DOSSIER}/regles/surcouche-qualite-stories.yaml",
    f"~/PMZilla-Lab/{DOSSIER}/regles/surcouche-qualite-stories.yaml", f"~/PMZilla-Lab/{DOSSIER}/regles/autre.yaml",
    f"/Users/quelquun/PMZilla-Lab/{DOSSIER}/regles/sous-dossier/x.yaml",
)

# Commandes permises : aucune règle de REGLES_D13 ne doit les refuser.
COMMANDES_PERMISES = (
    "uv run tools/story_quality.py report --name serie-a", "uv run tools/story_quality.py report --name serie-a --language en",
    "uv run tools/story_quality.py report --name serie-a --json", "uv run tools/story_quality.py report --name serie-a --json --language en",
    "python3 tools/story_quality.py report --name serie-a --json", "~/PMZilla-Lab/workspace/tools/story_quality.py report --name x --json",
    "uv run --with pyyaml tools/story_quality.py report --name x --json", "uv run tools/story_quality.py grid --show --json",
    "python3 tools/story_quality.py report --name serie-a", "uv run --with pyyaml tools/story_quality.py report --name x",
    "~/PMZilla-Lab/workspace/tools/story_quality.py report --name x",
    "uv run tools/story_quality.py grid", "uv run tools/story_quality.py grid --show", "uv run tools/story_quality.py grid --language en",
    "uv run tools/story_quality.py grid --show --language en", "uv run --with jsonschema tools/story_quality.py grid --show",
    "python3 tools/story_quality.py grid --show", "~/PMZilla-Lab/workspace/tools/story_quality.py grid",
    "uv run tools/story_quality.py grid --show --json", "uv run tools/story_quality.py grid --show --json --language en",
    "uv run --with jsonschema tools/story_quality.py grid --show --json", "python3 tools/story_quality.py grid --show --json",
    "python tools/story_quality.py grid --show --json", "~/PMZilla-Lab/workspace/tools/story_quality.py grid --show --json",
    "./tools/story_quality.py grid --show --json", "/Users/quelquun/PMZilla-Lab/workspace/tools/story_quality.py grid --show --json",
    "$HOME/PMZilla-Lab/workspace/tools/story_quality.py grid --show --json",
    "uv run tools/story_quality.py --help", "python3 tools/story_quality.py --help", "uv run tools/story_quality.py -h",
    "cat tools/story_quality.py", "head -40 tools/story_quality.py", "grep -n collect tools/story_quality.py",
    "sed -n 1,40p tools/story_quality.py", "cat tools/story_quality_messages.py", "cat tools/story_quality_overlay.schema.json",
    "head -30 docs/pmzilla/surcouche-qualite-exemple.yaml", "cat docs/pmzilla/surcouche-qualite-exemple.yaml",
    "cat docs/pmzilla/grille-qualite-stories.md", "grep -n critere docs/pmzilla/grille-qualite-stories.md",
    "cat ~/PMZilla-Lab/workspace/.pmzilla/contexte.md", "ls tests/story_quality", "git log --oneline -3 -- tools/story_quality.py",
    "bash tests/run_all.sh story_quality", "bash tests/run_all.sh --staged", "bash tests/run_all.sh settings_deny",
    "uv run --with jsonschema python -W ignore -m unittest discover -s tests/story_quality -q -f",
    "uv run --with pyyaml --with jsonschema python -W ignore -m unittest discover -s tests/story_quality -q -f",
    "python3 -W ignore -m unittest discover -s tests/story_quality -q", "python3 tests/story_quality/test_grille.py",
    "uv run tools/flow_views.py show quality_by_team", "uv run tools/flow_views.py show quality_coverage_by_team",
    "uv run tools/flow_views.py show quality_by_product", "cat Flux-Lab/rapports/qualite-stories-serie-a-2026-10-20.md",
    "grep -n Chaîne Flux-Lab/rapports/qualite-stories-serie-a-2026-10-20.md", "ls Flux-Lab/rapports",
    "security list-keychains",
)
CHEMINS_READ_PERMIS = (
    "tools/story_quality.py", "tools/story_quality_overlay.schema.json", "docs/pmzilla/surcouche-qualite-exemple.yaml",
    "docs/pmzilla/grille-qualite-stories.md", "./docs/pmzilla/surcouche-qualite-exemple.yaml",
    "/Users/quelquun/PMZilla-Lab/workspace/docs/pmzilla/surcouche-qualite-exemple.yaml",
    "~/PMZilla-Lab/workspace/docs/pmzilla/surcouche-qualite-exemple.yaml",
    "/Users/quelquun/PMZilla-Lab/workspace/tools/story_quality_overlay.schema.json",
    "~/PMZilla-Lab/workspace/.pmzilla/contexte.md", "Flux-Lab/rapports/qualite-stories-serie-a-2026-10-20.md",
    "tests/story_quality/test_surcouche.py",
)

# Commandes permises que les règles EXISTANTES de settings.json refusent déjà : un défaut des règles d'avant, pas du bloc D13.
# Aucune pour l'instant ; toute entrée est documentée ici avec sa règle.
DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES: dict = {}


class Moteur:
    """Applique un ensemble de règles `Bash(...)`, `Read(...)`, `Write(...)` et `Edit(...)` à des commandes et à des chemins."""

    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]
        self.chemins = {outil: [r[len(outil) + 1:-1] for r in regles if r.startswith(outil + "(")] for outil in ("Read", "Edit")}
        self.chemins["Write"] = self.chemins["Edit"]      # une règle Edit s'applique à tous les outils qui modifient un fichier (R-84)

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def acces_interdit(self, outil: str, chemin: str) -> bool:
        """« // » = chemin absolu depuis la racine du disque, « ~/ » = depuis le dossier personnel, sinon relatif au dossier."""
        for motif in self.chemins[outil]:
            if motif.startswith("//"):
                if chemin.startswith("/") and glob_en_regex(motif[1:]).fullmatch(chemin):
                    return True
            elif motif.startswith("~/"):
                if chemin.startswith("~/") and glob_en_regex(motif).fullmatch(chemin):
                    return True
            elif not chemin.startswith(("/", "~")) and glob_en_regex(motif.removeprefix("./")).fullmatch(chemin.removeprefix("./")):
                return True
        return False

    def lecture_interdite(self, chemin: str) -> bool:
        return self.acces_interdit("Read", chemin)


def sous_commandes_declarees(texte: str) -> set:
    """Noms des sous-commandes qu'un script argparse déclare (add_parser("nom"...))."""
    return set(re.findall(r"""add_parser\(\s*["']([a-z][a-z-]*)["']""", texte))


def sous_commandes_non_classees(texte: str) -> list:
    return sorted(sous_commandes_declarees(texte) - set(SOUS_COMMANDES_REFUSEES) - set(SOUS_COMMANDES_PERMISES))


def commandes_json_permises():
    """`report --name <série> --json` (change story-quality-audit, tâche 3.24, M2 (a)) dans toutes les formes de lancement et de chemin :
    il ne lit que les vues, donc la session le lance comme `report`."""
    for suite in ("report --name serie-a --json", "report --name serie-a --json --language en", "report --name serie-a --language fr --json"):
        for lanceur, chemin in itertools.product(LANCEURS, CHEMINS_TOOLS):
            yield f"{lanceur} {chemin.format(s='story_quality.py')} {suite}"
        for chemin in CHEMINS_TOOLS_DIRECTS:
            yield f"{chemin.format(s='story_quality.py')} {suite}"


def commandes_refusees():
    """Toutes les formes de lancement et d'accès que la session ne doit pas pouvoir exécuter, par la voie du terminal."""
    for sous, options in OPTIONS_PAR_SOUS_COMMANDE.items():
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS_TOOLS, options):
            yield f"{lanceur} {chemin.format(s='story_quality.py')} {sous}{option}"
        for chemin, option in itertools.product(CHEMINS_TOOLS_DIRECTS, options):
            yield f"{chemin.format(s='story_quality.py')} {sous}{option}"
    for verbe in ("find-generic-password -w", "delete-generic-password", "add-generic-password -U", "find-generic-password -g"):
        yield f"security {verbe} -s {SERVICE_CLE_ANALYSE}"
        yield f"security {verbe} -a $USER -s {SERVICE_CLE_ANALYSE} -w"
    for lecteur, dossier, option in itertools.product(LECTEURS_SURCOUCHE, DOSSIERS_CONTEXTE, OPTIONS_LECTEUR):
        yield f"{lecteur} {option}{dossier}/regles/{FICHIER_SURCOUCHE}"
        yield f"{lecteur} {option}{dossier}/regles/*"
        yield f"{lecteur} {option}{dossier}/regles"
        yield f"{lecteur} {option}{dossier}/*/{FICHIER_SURCOUCHE}"


class Matrice:
    """Cas communs au bloc REGLES_D13 et aux règles réelles ; `self.moteur` est fourni par la sous-classe."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} formes de lancement ou de lecture non refusées")
        for outil in ("Read", "Write", "Edit"):
            for chemin in CHEMINS_SURCOUCHE_READ:
                self.assertTrue(self.moteur.acces_interdit(outil, chemin), f"{outil}({chemin})")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])
        refusees = [c for c in commandes_json_permises() if self.moteur.interdite(c)]
        self.assertEqual(refusees[:5], [], f"{len(refusees)} forme(s) de report --json refusée(s)")
        refusees = [c for c in CHEMINS_READ_PERMIS if self.moteur.lecture_interdite(c)]
        self.assertEqual(refusees, [])


class BlocD13(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à copier : vert avant comme après l'étape 1.7."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_D13)

    def test_le_bloc_n_a_pas_de_doublon_et_n_utilise_que_les_quatre_outils(self):
        self.assertTrue(REGLES_D13, "bloc vide")
        self.assertEqual(len(REGLES_D13), len(set(REGLES_D13)))
        self.assertTrue(all(r.startswith(("Bash(", "Read(", "Write(", "Edit(")) and r.endswith(")") for r in REGLES_D13))

    def test_chaque_sous_commande_chaque_lanceur_chaque_chemin_chaque_option(self):
        self.verifier_formes_refusees()

    def test_le_dry_run_et_l_echantillon_sont_refuses_comme_le_reste(self):
        for lanceur in LANCEURS:
            for suite in ("analyse --dry-run", "analyse --sample 3", "analyse --sample 3 --team x", "analyse --sample 3 --dry-run",
                          "coach --dry-run --team x", "coach --show --team x"):
                commande = f"{lanceur} tools/story_quality.py {suite}"
                self.assertTrue(self.moteur.interdite(commande), commande)

    def test_report_grid_et_aide_restent_permis(self):
        for lanceur in LANCEURS:
            for suite in ("report --name x", "report --name x --json", "grid", "grid --show", "grid --show --json", "--help"):
                commande = f"{lanceur} tools/story_quality.py {suite}"
                self.assertFalse(self.moteur.interdite(commande), commande)

    def test_la_cle_d_analyse_est_protegee_dans_le_trousseau(self):
        self.assertTrue(self.moteur.interdite(f"security delete-generic-password -s {SERVICE_CLE_ANALYSE}"))
        self.assertFalse(self.moteur.interdite("security list-keychains"))

    def test_la_surcouche_est_refusee_en_lecture_ecriture_et_modification(self):
        for outil, chemin in itertools.product(("Read", "Write", "Edit"), CHEMINS_SURCOUCHE_READ):
            self.assertTrue(self.moteur.acces_interdit(outil, chemin), f"{outil}({chemin})")

    def test_schema_exemple_et_notes_restent_lisibles(self):
        for chemin in CHEMINS_READ_PERMIS:
            self.assertFalse(self.moteur.lecture_interdite(chemin), chemin)
        for lecteur, dossier in itertools.product(LECTEURS_SURCOUCHE, DOSSIERS_CONTEXTE):
            commande = f"{lecteur} {dossier}/notes/organisation-2026-08.md"
            self.assertFalse(self.moteur.interdite(commande), commande)

    def test_ce_qui_reste_permis_autour_de_l_outil(self):
        self.verifier_formes_permises()


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles de REGLES_D13 : même résultat avant et après 1.7."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_D13 and r not in REGLES_D10])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        refusees = {c for c in COMMANDES_PERMISES if self.moteur.interdite(c)}
        self.assertEqual(sorted(refusees - set(DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES)), [])
        self.assertEqual(sorted(set(DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES) - refusees), [], "entrée périmée dans le dictionnaire")
        refusees = [c for c in CHEMINS_READ_PERMIS if self.moteur.lecture_interdite(c)]
        self.assertEqual(refusees, [])

    def test_la_surcouche_et_l_outil_ne_sont_pas_deja_couverts_par_une_regle_d_avant(self):
        """Garde le sens du bloc : si une règle existante couvrait déjà ces cas, REGLES_D13 serait redondant (sans lui, rien n'est refusé)."""
        for outil in ("Read", "Write", "Edit"):
            self.assertFalse(self.moteur.acces_interdit(outil, f"~/PMZilla-Lab/{DOSSIER}/regles/surcouche-qualite-stories.yaml"), outil)
        self.assertFalse(self.moteur.interdite("uv run tools/story_quality.py analyse --dry-run"))
        self.assertFalse(self.moteur.interdite(f"security delete-generic-password -s {SERVICE_CLE_ANALYSE}"))


class ClassementDesSousCommandes(unittest.TestCase):
    """Une sous-commande ou option ajoutée à l'outil sans être classée (refusée ou permise) fait échouer le test."""

    def test_le_detecteur_nomme_une_sous_commande_inconnue(self):
        texte = ('sous.add_parser("collect")\nsous.add_parser("review")\nsous.add_parser("analyse")\nsous.add_parser("coach")\n'
                 'sous.add_parser("report")\nsous.add_parser("grid")\nsous.add_parser("export")\n')
        self.assertEqual(sous_commandes_non_classees(texte), ["export"])
        self.assertEqual(sous_commandes_non_classees(texte.replace('sous.add_parser("export")\n', "")), [])

    def test_les_deux_listes_sont_disjointes(self):
        self.assertEqual(set(SOUS_COMMANDES_REFUSEES) & set(SOUS_COMMANDES_PERMISES), set())

    def test_l_outil_ne_declare_que_des_sous_commandes_classees(self):
        if not OUTIL.is_file():
            self.skipTest("tools/story_quality.py n'existe pas encore (groupe 3)")
        self.assertEqual(sous_commandes_non_classees(OUTIL.read_text(encoding="utf-8")), [],
                         "sous-commande de tools/story_quality.py non classée : l'ajouter à SOUS_COMMANDES_REFUSEES ou _PERMISES")


class DansLeFichierDeReglages(unittest.TestCase):
    """Étape 1.7 : l'utilisateur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_D13 if r in cls.deny]
        cls.manquantes = [r for r in REGLES_D13 if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.fail("étape 1.7 : l'utilisateur n'a pas encore ajouté les règles")
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_D13 absente(s) de .claude/settings.json")

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail("étape 1.7 : l'utilisateur n'a pas encore ajouté les règles")
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_regles_sont_dans_settings_json")
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(list(REGLES_D13), indent=2, ensure_ascii=False))
    else:
        unittest.main()
