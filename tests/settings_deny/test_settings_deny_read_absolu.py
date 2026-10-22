"""Règles `deny` de lecture en forme absolue (décision de l'auteur du 2026-10-21, point 2, option A+ ; constat A14 ; la pose est le geste de l'auteur).

Constat : quatre chemins protégés de Flux-Lab (exports/, historique/, la liste des noms sensibles, tableaux/) et versions-produit.txt ne sont
refusés à l'outil Read que sous la forme `./…` ; organisation.yaml, le catalogue des équipes et equipes-assets.yaml ont aussi `//**/…` et
`~/**/…`. Les dossiers de contenu (Bibliotheque-MD, Bibliotheque-Lab, Veille-Lab, Veille-Ecartes, Watch-Lab/watch, Watch-Lab/own-articles,
Watch-Excluded) n'ont que `./…` ; Bibliotheque-Images a `./…` et `**/…`, deux formes relatives : elle entre aussi dans le bloc. CLAUDE.md dit
« relatif ou absolu ». Le trou se voit depuis un worktree : `./Flux-Lab/…` y désigne le worktree, pas le Flux-Lab de la racine de contenu ; une
lecture par chemin absolu (`/Users/…/PMZilla-Lab/workspace/Flux-Lab/exports/x.csv`, `~/PMZilla-Lab/…`) n'y est pas refusée à l'outil Read.

Watch-Lab (décision de l'auteur du 2026-10-21) : le dossier entier est refusé, sous ses trois formes `./Watch-Lab/**`, `//**/Watch-Lab/**` et
`~/**/Watch-Lab/**` ; rien de Watch-Lab ne reste lisible (CLAUDE.md interdit de lire ses fichiers et sources.yaml). Les règles relatives
existantes de Watch-Lab/watch et Watch-Lab/own-articles restent ; leurs formes absolues sont couvertes par celles du dossier parent.

Le bloc REGLES_A_PLUS reprend exactement la syntaxe des règles d'organisation.yaml : `Read(//**/<chemin>)` et `Read(~/**/<chemin>)`, avec le
suffixe `/**` pour un dossier. organisation.yaml n'a aucune règle Edit en forme absolue (vérifié par ReglesExistantes) : le bloc n'en ajoute pas
(et jamais de Write : une règle Edit couvre tous les outils d'édition, garde partagée des listes déclarées).

Grep et Glob : aucune forme `Grep(...)` ni `Glob(...)` ; la documentation de Claude Code applique les règles `Read(...)` à ces outils, et c'est la
règle Read en forme absolue qui doit les couvrir depuis un worktree. Le comportement réel ne se teste pas par unittest : il se vérifie à la main
après la fusion (faux dossiers Flux-Lab/exports et Watch-Lab hors du dépôt, recherche par chemin absolu avec les outils Grep et Glob).

Ce fichier est écrit AVANT la pose : la classe BlocAPlus applique les cas au bloc seul et reste verte ; la classe DansLeFichierDeReglages ÉCHOUE
tant qu'aucune règle n'est posée, échoue en nommant les manquantes si la pose est partielle, et rejoue la matrice contre les règles réelles une
fois toutes posées. Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_read_absolu.py --json       (imprime le bloc à poser dans permissions.deny)
    python3 tests/settings_deny/test_settings_deny_read_absolu.py --familles   (le bloc par famille)

Complément (décision de l'auteur du 2026-10-21, constat 1 de l'audit du 2026-10-21 ; la pose est le geste de l'auteur) : copies des fichiers
protégés. Les règles Read de la liste des noms sensibles, du catalogue des équipes, d'organisation.yaml et d'equipes-assets.yaml visent le nom
exact ; une copie `<nom>.sauvegarde-…`, `<nom>.avant-…` ou `<nom>.bak-…` passe. Le complément ajoute `Read(./Flux-Lab/<nom>*)`,
`Read(//**/Flux-Lab/<nom>*)` et `Read(~/**/Flux-Lab/<nom>*)` (`*` ne franchit pas une barre : rapports/, flux.yaml et equipes-lisibles.yaml
restent lisibles). Le refus de `git merge` nu reste dans .claude/settings.local.json de l'espace de travail (décision D11, maintenue par
l'auteur le 2026-10-21 ; test_settings_deny_push_merge.py) : il n'entre pas dans le complément.
REGLES_COMPLEMENT n'est pas la liste --json (celle de regles_attendues(), contrôlée par la garde partagée) : BlocComplement la passe à la même
garde. BlocComplement est vert ; DansLeFichierComplement ÉCHOUE tant que l'auteur n'a pas posé le complément.

    python3 tests/settings_deny/test_settings_deny_read_absolu.py --json-complement       (le complément à poser dans permissions.deny)
    python3 tests/settings_deny/test_settings_deny_read_absolu.py --familles-complement   (le complément par famille)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny_offsite_backup import glob_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

# Chemins protégés de Flux-Lab refusés à l'outil Read sous la seule forme `./…` (un dossier finit par `/**`).
CHEMINS_FLUX = ("Flux-Lab/exports/**", "Flux-Lab/historique/**", "Flux-Lab/noms-sensibles.txt", "Flux-Lab/tableaux/**",
                "Flux-Lab/versions-produit.txt")
WATCH = "Watch-Lab/**"
# Dossiers de contenu des lignes 4 à 10 de .claude/settings.json (Watch-Lab entier à la place de ses deux sous-dossiers), plus
# Bibliotheque-Images (sa règle `**/…` est relative : elle ne couvre pas une lecture par chemin absolu depuis un worktree).
CHEMINS_CONTENU = ("Bibliotheque-MD/**", "Bibliotheque-Lab/**", "Veille-Lab/**", "Veille-Ecartes/**", WATCH, "Watch-Excluded/**",
                   "Bibliotheque-Images/**")
CHEMINS = CHEMINS_FLUX + CHEMINS_CONTENU
FORMES_ABSOLUES = ("//**/{c}", "~/**/{c}")
FORMES_WATCH = ("./{c}",) + FORMES_ABSOLUES          # Watch-Lab : la forme relative du dossier entier n'existe pas encore


def _formes(chemin: str) -> tuple:
    return FORMES_WATCH if chemin == WATCH else FORMES_ABSOLUES


# Le bloc que l'auteur pose dans permissions.deny de .claude/settings.json : une chaîne par règle, dans cet ordre.
REGLES_A_PLUS = tuple(f"Read({forme.format(c=chemin)})" for chemin in CHEMINS for forme in _formes(chemin))


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_A_PLUS)


# Racines d'où une lecture absolue peut viser le contenu : l'espace de travail, un worktree, sous `/` comme sous `~/`.
RACINES_ABSOLUES = ("/Users/quelquun/PMZilla-Lab/workspace", "/Users/quelquun/PMZilla-Lab/worktrees/wt-x",
                    "~/PMZilla-Lab/workspace", "~/PMZilla-Lab/worktrees/wt-x", "/Volumes/autre/PMZilla-Lab/workspace")
RACINES_RELATIVES = ("", "./")
SOURCES_WATCH = ("./Watch-Lab/sources.yaml", "Watch-Lab/sources.yaml", "/Users/quelquun/PMZilla-Lab/workspace/Watch-Lab/sources.yaml",
                 "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Watch-Lab/sources.yaml", "~/PMZilla-Lab/workspace/Watch-Lab/sources.yaml",
                 "~/PMZilla-Lab/worktrees/wt-x/Watch-Lab/sources.yaml")


def exemple(chemin: str) -> str:
    """Un fichier sous le chemin protégé : `dossier/**` -> `dossier/sous/x.csv`, un fichier -> lui-même."""
    return chemin[:-len("**")] + "sous/x.csv" if chemin.endswith("/**") else chemin


def chemins_absolus_refuses():
    for racine, chemin in itertools.product(RACINES_ABSOLUES, CHEMINS):
        yield f"{racine}/{exemple(chemin)}"
    yield "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/exports/x.csv"
    yield "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Flux-Lab/exports/x.csv"
    yield "~/PMZilla-Lab/workspace/Flux-Lab/historique/2026/x.json"
    for racine, sous in itertools.product(RACINES_ABSOLUES, ("watch/2026/article.md", "own-articles/article.md", "sources.yaml")):
        yield f"{racine}/Watch-Lab/{sous}"


def chemins_relatifs_refuses():
    for racine, chemin in itertools.product(RACINES_RELATIVES, CHEMINS):
        yield f"{racine}{exemple(chemin)}"
    yield "./Watch-Lab/sources.yaml"
    yield "Watch-Lab/watch/2026/article.md"


CHEMINS_PERMIS = tuple(
    f"{racine}/{fichier}" for racine, fichier in itertools.product(
        RACINES_ABSOLUES, ("Flux-Lab/rapports/flux-pilote-2026-10-21.md", "Flux-Lab/rapports/qualite-stories-x-2026-10-21.md",
                           "Flux-Lab/flux.yaml", "Flux-Lab/equipes-lisibles.yaml", "tools/flow_views.py"))
) + ("Flux-Lab/rapports/flux-pilote-2026-10-21.md", "./Flux-Lab/flux.yaml", "Flux-Lab/equipes-lisibles.yaml", "tools/flow_views.py",
     "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/exports-notes.md", "~/PMZilla-Lab/workspace/Flux-Lab/tableaux-notes.md",
     "tools/watch_lab.py", "tests/watch_lab/test_watch_lab.py")

# Grep et Glob : un chemin de Flux-Lab et un dossier de contenu, et la règle Read en forme absolue qui doit couvrir ces outils.
GREP_GLOB = {"Flux-Lab/exports/**": "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Flux-Lab/exports",
             WATCH: "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Watch-Lab"}


class Moteur:
    """Applique les règles `Read(...)` à des chemins (même lecture que les modules rgpd, offsite_backup et story_quality)."""

    def __init__(self, regles):
        self.lectures = [r[len("Read("):-1] for r in regles if r.startswith("Read(")]

    def lecture_interdite(self, chemin: str) -> bool:
        """Outil Read : « // » = chemin absolu depuis la racine du disque, « ~/ » = depuis le dossier personnel, sinon relatif au dossier."""
        for motif in self.lectures:
            if motif.startswith("//"):
                if chemin.startswith("/") and glob_en_regex(motif[1:]).fullmatch(chemin):
                    return True
            elif motif.startswith("~/"):
                if chemin.startswith("~/") and glob_en_regex(motif).fullmatch(chemin):
                    return True
            elif not chemin.startswith(("/", "~")) and glob_en_regex(motif.removeprefix("./")).fullmatch(chemin.removeprefix("./")):
                return True
        return False


def couverte(chemin: str, forme: str, regles) -> bool:
    """La forme `forme` du chemin relatif `chemin` est couverte par une règle Read de ce chemin ou d'un dossier parent (`P/**`)."""
    regles = set(regles)
    if f"Read({forme.format(c=chemin)})" in regles:
        return True
    morceaux = chemin.split("/")
    for i in range(1, len(morceaux)):
        parent = "/".join(morceaux[:i]) + "/**"
        if f"Read({forme.format(c=parent)})" in regles:
            return True
    return False


class Matrice:
    """Cas communs au bloc REGLES_A_PLUS et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_lectures_absolues_refusees(self):
        manquantes = [c for c in chemins_absolus_refuses() if not self.moteur.lecture_interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} lecture(s) par chemin absolu non refusée(s)")

    def verifier_lectures_permises(self):
        refusees = [c for c in CHEMINS_PERMIS if self.moteur.lecture_interdite(c)]
        self.assertEqual(refusees, [], "lecture(s) permise(s) refusée(s) : règle trop large")


class BlocAPlus(Matrice, unittest.TestCase):
    """Le moteur appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_A_PLUS)

    def test_le_bloc_compte_25_regles_read_sans_doublon_dans_l_ordre(self):
        self.assertEqual(len(REGLES_A_PLUS), 2 * len(CHEMINS) + 1)
        self.assertEqual(len(REGLES_A_PLUS), 25)
        self.assertEqual(len(REGLES_A_PLUS), len(set(REGLES_A_PLUS)))
        self.assertTrue(all(r.startswith(("Read(//**/", "Read(~/**/", "Read(./Watch-Lab/")) and r.endswith(")") for r in REGLES_A_PLUS))
        self.assertEqual(REGLES_A_PLUS[:2], ("Read(//**/Flux-Lab/exports/**)", "Read(~/**/Flux-Lab/exports/**)"))
        self.assertEqual([r for r in REGLES_A_PLUS if r.startswith("Read(./")], ["Read(./Watch-Lab/**)"])

    def test_watch_lab_entier_sous_ses_trois_formes_sans_les_sous_dossiers(self):
        for regle in ("Read(./Watch-Lab/**)", "Read(//**/Watch-Lab/**)", "Read(~/**/Watch-Lab/**)"):
            self.assertIn(regle, REGLES_A_PLUS)
        self.assertEqual([r for r in REGLES_A_PLUS if "Watch-Lab/watch" in r or "Watch-Lab/own-articles" in r], [])

    def test_meme_syntaxe_que_les_regles_d_organisation_yaml(self):
        modele = {f.format(c="Flux-Lab/organisation.yaml") for f in FORMES_ABSOLUES}
        self.assertEqual(modele, {"//**/Flux-Lab/organisation.yaml", "~/**/Flux-Lab/organisation.yaml"})
        for chemin in CHEMINS:
            self.assertIn(f"Read(//**/{chemin})", REGLES_A_PLUS)
            self.assertIn(f"Read(~/**/{chemin})", REGLES_A_PLUS)

    def test_lecture_par_chemin_absolu_refusee_depuis_l_espace_et_un_worktree(self):
        self.verifier_lectures_absolues_refusees()

    def test_rapports_flux_yaml_et_extrait_lisible_restent_permis(self):
        self.verifier_lectures_permises()

    def test_sources_yaml_de_watch_lab_refuse_sous_toutes_les_formes(self):
        for chemin in SOURCES_WATCH:
            self.assertTrue(self.moteur.lecture_interdite(chemin), chemin)

    def test_cas_nommes_de_la_decision(self):
        for chemin in ("/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/exports/x.csv", "~/PMZilla-Lab/workspace/Flux-Lab/exports/x.csv",
                       "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Flux-Lab/exports/x.csv",
                       "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/versions-produit.txt",
                       "/Users/quelquun/PMZilla-Lab/workspace/Watch-Lab/watch/2026/article.md",
                       "~/PMZilla-Lab/workspace/Bibliotheque-MD/livre.md",
                       "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Bibliotheque-Images/livre/figure-1.png",
                       "/Users/quelquun/PMZilla-Lab/workspace/Bibliotheque-Images/livre/figure-1.png",
                       "~/PMZilla-Lab/worktrees/wt-x/Bibliotheque-Images/livre/figure-1.png"):
            self.assertTrue(self.moteur.lecture_interdite(chemin), chemin)
        for chemin in ("/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/rapports/x.md",
                       "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/flux.yaml"):
            self.assertFalse(self.moteur.lecture_interdite(chemin), chemin)

    def test_la_regle_read_absolue_couvre_grep_et_glob(self):
        """Grep et Glob : la documentation de Claude Code applique les règles `Read(...)` à ces outils ; la règle absolue du bloc est celle
        qui couvre une recherche par chemin absolu depuis un worktree (dossier visé et tout fichier dessous). Comportement réel : à vérifier
        à la main après la fusion (faux dossiers, chemin absolu)."""
        for chemin, dossier in GREP_GLOB.items():
            self.assertIn(f"Read(//**/{chemin})", REGLES_A_PLUS)
            self.assertIn(f"Read(~/**/{chemin})", REGLES_A_PLUS)
            self.assertTrue(self.moteur.lecture_interdite(f"{dossier}/x.md"), dossier)
        self.assertEqual([r for r in REGLES_A_PLUS if r.startswith(("Grep(", "Glob("))], [])


class ReglesExistantes(unittest.TestCase):
    """Les règles réelles privées de REGLES_A_PLUS : même résultat avant et après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.avant = [r for r in cls.deny if r not in REGLES_A_PLUS and r not in REGLES_COMPLEMENT]
        cls.moteur = Moteur(cls.avant)

    def test_lectures_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in CHEMINS_PERMIS if self.moteur.lecture_interdite(c)], [])

    def test_la_forme_relative_est_deja_refusee(self):
        """Le bloc complète des chemins déjà refusés en `./…` ; pour Watch-Lab, ses deux sous-dossiers seulement."""
        for chemin in CHEMINS:
            if chemin != WATCH:
                self.assertIn(f"Read(./{chemin})", self.deny, chemin)
        for regle in ("Read(./Watch-Lab/watch/**)", "Read(./Watch-Lab/own-articles/**)"):
            self.assertIn(regle, self.deny)
        hors_watch = [c for c in chemins_relatifs_refuses() if "Watch-Lab/sous" not in c and "Watch-Lab/sources" not in c]
        self.assertEqual([c for c in hors_watch if not self.moteur.lecture_interdite(c)], [])

    def test_la_forme_absolue_n_est_pas_deja_couverte(self):
        """Garde le sens du bloc : sans lui, une lecture par chemin absolu de ces chemins n'est pas refusée, ni sources.yaml de Watch-Lab."""
        for chemin in CHEMINS:
            for racine in ("/Users/quelquun/PMZilla-Lab/workspace", "~/PMZilla-Lab/workspace"):
                cible = f"{racine}/{exemple(chemin)}"
                self.assertFalse(self.moteur.lecture_interdite(cible), cible)
        for chemin in SOURCES_WATCH:
            self.assertFalse(self.moteur.lecture_interdite(chemin), chemin)

    def test_le_modele_organisation_yaml_a_ses_deux_formes_absolues_en_read_seulement(self):
        for forme in FORMES_ABSOLUES:
            self.assertIn(f"Read({forme.format(c='Flux-Lab/organisation.yaml')})", self.deny)
        absolues = [r for r in self.deny if "organisation.yaml" in r and r.startswith(("Edit(", "Write(")) and ("//" in r or "~/" in r)]
        self.assertEqual(absolues, [], "organisation.yaml a des règles Edit ou Write en forme absolue : les reprendre dans REGLES_A_PLUS")

    def test_toute_regle_read_relative_de_flux_lab_et_du_contenu_a_ses_formes_absolues(self):
        """Garde contre la dérive : une règle `Read(./Flux-Lab/…)` ou d'un dossier de contenu est couverte si une règle absolue de son
        chemin ou d'un dossier parent existe, dans le fichier ou dans le bloc (Watch-Lab/** couvre watch/ et own-articles/) ; le dossier
        Watch-Lab entier a ses trois formes."""
        toutes = set(self.deny) | set(REGLES_A_PLUS)
        prefixes = ("Read(./Flux-Lab/", "Read(./Bibliotheque-", "Read(./Veille-", "Read(./Watch-")
        manquantes = []
        for regle in self.deny:
            if not regle.startswith(prefixes):
                continue
            chemin = regle[len("Read(./"):-1]
            manquantes += [f"{regle} : {forme}" for forme in FORMES_ABSOLUES if not couverte(chemin, forme, toutes)]
        self.assertEqual(manquantes, [], "règle(s) de lecture en forme absolue absente(s) du fichier et du bloc")
        for forme in FORMES_WATCH:
            self.assertIn(f"Read({forme.format(c=WATCH)})", toutes)

    def test_le_detecteur_de_couverture_par_un_parent(self):
        self.assertTrue(couverte("Watch-Lab/watch/**", "//**/{c}", ["Read(//**/Watch-Lab/**)"]))
        self.assertTrue(couverte("Flux-Lab/exports/**", "~/**/{c}", ["Read(~/**/Flux-Lab/exports/**)"]))
        self.assertFalse(couverte("Watch-Lab/watch/**", "~/**/{c}", ["Read(//**/Watch-Lab/**)"]))
        self.assertFalse(couverte("Flux-Lab/exports/**", "//**/{c}", ["Read(//**/Flux-Lab/tableaux/**)"]))

    def test_la_regle_relative_de_bibliotheque_images_ne_couvre_pas_un_worktree(self):
        """`Read(**/Bibliotheque-Images/**)` est relative : sans le bloc, une lecture absolue depuis un worktree passe."""
        self.assertIn("Read(**/Bibliotheque-Images/**)", self.deny)
        self.assertFalse(self.moteur.lecture_interdite("/Users/quelquun/PMZilla-Lab/worktrees/wt-x/Bibliotheque-Images/livre/figure-1.png"))

    def test_aucune_forme_grep_ni_glob_pour_ces_chemins(self):
        """Sur le modèle de test_settings_deny_equipes : aucune règle `Grep(...)` ni `Glob(...)` n'existe pour Flux-Lab/exports ni pour
        Watch-Lab ; ce sont les règles Read qui couvrent ces outils."""
        self.assertEqual([d for d in self.deny if d.startswith(("Grep(", "Glob(")) and ("Flux-Lab/exports" in d or "Watch-Lab" in d)], [])

    def test_aucune_regle_du_bloc_n_est_deja_dans_le_fichier_avant_la_pose_partielle(self):
        """Le bloc ne duplique aucune règle d'avant (toute présence vient de la pose de ce bloc)."""
        self.assertEqual(len(set(REGLES_A_PLUS) & set(self.avant)), 0)


class DansLeFichierDeReglages(unittest.TestCase):
    """L'auteur pose les règles. Rouge avant, échoue si la pose est partielle, passe si tout y est."""

    MESSAGE = "l'auteur n'a pas encore posé les règles de lecture en forme absolue"

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_A_PLUS if r in cls.deny]
        cls.manquantes = [r for r in REGLES_A_PLUS if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.fail(self.MESSAGE)
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_A_PLUS absente(s) de .claude/settings.json : "
                                              + " ; ".join(self.manquantes))

    def test_la_matrice_des_lectures_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail(self.MESSAGE)
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes))
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_lectures_absolues_refusees")
        matrice.verifier_lectures_absolues_refusees()
        matrice.verifier_lectures_permises()
        moteur = Moteur(self.deny)
        self.assertEqual([c for c in chemins_relatifs_refuses() if not moteur.lecture_interdite(c)], [])
        self.assertEqual([c for c in SOURCES_WATCH if not moteur.lecture_interdite(c)], [])

    def test_la_regle_couvrant_grep_et_glob_est_posee(self):
        """La règle Read en forme absolue de Flux-Lab/exports et de Watch-Lab, celle qui couvre Grep et Glob, est dans les réglages."""
        if not self.presentes:
            self.fail(self.MESSAGE)
        for chemin in GREP_GLOB:
            for forme in FORMES_ABSOLUES:
                self.assertIn(f"Read({forme.format(c=chemin)})", self.deny)


def familles() -> list:
    flux = sum(1 for r in REGLES_A_PLUS if "Flux-Lab/" in r)
    watch = sum(1 for r in REGLES_A_PLUS if "Watch-Lab/" in r)
    contenu = len(REGLES_A_PLUS) - flux - watch
    return [
        f"Flux-Lab (exports, historique, liste des noms sensibles, tableaux, versions-produit.txt) : {flux} règles Read (//**/ et ~/**/)",
        f"Watch-Lab entier : {watch} règles Read (./, //**/ et ~/**/)",
        f"autres dossiers de contenu (Bibliotheque-MD, Bibliotheque-Lab, Veille-Lab, Veille-Ecartes, Watch-Excluded, Bibliotheque-Images) : "
        f"{contenu} règles Read (//**/ et ~/**/)",
        f"total : {len(REGLES_A_PLUS)} règles",
    ]


# --- Complément : copies des fichiers protégés ----------------------------------------------------------------------------------------

# Les quatre fichiers protégés de Flux-Lab dont les règles Read visent le nom exact (lignes 13-14, 737-739, 926-928, 1004-1005, 2152-2153).
FICHIERS_PROTEGES = ("noms-sensibles.txt", "equipes-jira.yaml", "organisation.yaml", "equipes-assets.yaml")
FORMES_COMPLEMENT = ("./{c}",) + FORMES_ABSOLUES
# Le complément que l'auteur pose dans permissions.deny de .claude/settings.json : une chaîne par règle, dans cet ordre.
REGLES_COMPLEMENT = tuple(f"Read({forme.format(c=f'Flux-Lab/{nom}*')})" for nom in FICHIERS_PROTEGES for forme in FORMES_COMPLEMENT)

SUFFIXES_COPIE = ("", ".sauvegarde-2026-10-21", ".avant-r105", ".bak-1", ".bak")


def copies_refusees():
    """Chaque fichier protégé et ses copies, sous les trois formes, depuis l'espace de travail et depuis un worktree."""
    for nom, suffixe in itertools.product(FICHIERS_PROTEGES, SUFFIXES_COPIE):
        for racine in RACINES_ABSOLUES:
            yield f"{racine}/Flux-Lab/{nom}{suffixe}"
        for racine in RACINES_RELATIVES:
            yield f"{racine}Flux-Lab/{nom}{suffixe}"


CHEMINS_PERMIS_COMPLEMENT = CHEMINS_PERMIS + tuple(
    f"{racine}{fichier}" for racine, fichier in itertools.product(
        tuple(f"{r}/" for r in RACINES_ABSOLUES) + RACINES_RELATIVES,
        ("Flux-Lab/equipes-lisibles.yaml", "Flux-Lab/flux.yaml", "Flux-Lab/rapports/flux-pilote-2026-10-21.md",
         "Flux-Lab/rapports/equipes-jira.yaml.md", "Flux-Lab/rapports/organisation.yaml-notes.md"))
)

class MatriceComplement:
    """Cas communs au complément seul et aux règles réelles ; `self.moteur` est un Moteur."""

    def verifier_copies_refusees(self):
        manquantes = [c for c in copies_refusees() if not self.moteur.lecture_interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} copie(s) de fichier protégé non refusée(s)")

    def verifier_lectures_permises(self):
        refusees = [c for c in CHEMINS_PERMIS_COMPLEMENT if self.moteur.lecture_interdite(c)]
        self.assertEqual(refusees, [], "lecture(s) permise(s) refusée(s) : règle trop large")


class BlocComplement(MatriceComplement, unittest.TestCase):
    """Le moteur appliqué au complément seul : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_COMPLEMENT)

    def test_le_complement_compte_12_regles_read_sans_doublon_dans_l_ordre(self):
        self.assertEqual(len(REGLES_COMPLEMENT), 12)
        self.assertEqual(len(REGLES_COMPLEMENT), len(set(REGLES_COMPLEMENT)))
        self.assertEqual(REGLES_COMPLEMENT[:3], ("Read(./Flux-Lab/noms-sensibles.txt*)", "Read(//**/Flux-Lab/noms-sensibles.txt*)",
                                                 "Read(~/**/Flux-Lab/noms-sensibles.txt*)"))
        self.assertTrue(all(r.startswith("Read(") and r.endswith("*)") for r in REGLES_COMPLEMENT))

    def test_aucune_regle_de_fusion_dans_le_complement(self):
        """Décision D11 maintenue : le refus de la fusion nue reste dans le réglage local de l'espace de travail."""
        self.assertEqual([r for r in REGLES_COMPLEMENT if "merge" in r], [])

    def test_le_complement_passe_la_garde_partagee(self):
        import garde_regles
        self.assertEqual(garde_regles.constats(list(REGLES_COMPLEMENT)), [])

    def test_le_complement_est_disjoint_du_bloc_a_plus(self):
        self.assertEqual(set(REGLES_COMPLEMENT) & set(REGLES_A_PLUS), set())

    def test_copies_refusees_sous_les_trois_formes_depuis_l_espace_et_un_worktree(self):
        self.verifier_copies_refusees()

    def test_rapports_flux_yaml_et_extrait_lisible_restent_permis(self):
        self.verifier_lectures_permises()

    def test_le_catalogue_ne_touche_pas_l_extrait_lisible(self):
        for racine in ("/Users/quelquun/PMZilla-Lab/workspace/", "/Users/quelquun/PMZilla-Lab/worktrees/wt-x/", "~/PMZilla-Lab/workspace/",
                       "./", ""):
            self.assertFalse(self.moteur.lecture_interdite(f"{racine}Flux-Lab/equipes-lisibles.yaml"), racine)
            self.assertTrue(self.moteur.lecture_interdite(f"{racine}Flux-Lab/equipes-jira.yaml.sauvegarde-2026-10-21"), racine)


class DansLeFichierComplement(unittest.TestCase):
    """L'auteur pose le complément. Rouge avant, échoue si la pose est partielle, rejoue la matrice si tout y est."""

    MESSAGE = "l'auteur n'a pas encore posé le complément (copies des fichiers protégés)"

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_COMPLEMENT if r in cls.deny]
        cls.manquantes = [r for r in REGLES_COMPLEMENT if r not in cls.deny]

    def test_le_complement_est_dans_settings_json(self):
        if not self.presentes:
            self.fail(self.MESSAGE)
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_COMPLEMENT absente(s) de .claude/settings.json : "
                                              + " ; ".join(self.manquantes))

    def test_la_matrice_du_complement_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail(self.MESSAGE)
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes))
        matrice = type("MatriceComplementReelle", (MatriceComplement, unittest.TestCase),
                       {"moteur": Moteur(self.deny)})("verifier_copies_refusees")
        matrice.verifier_copies_refusees()
        matrice.verifier_lectures_permises()


def familles_complement() -> list:
    return [
        f"copies des fichiers protégés de Flux-Lab (liste des noms sensibles, catalogue des équipes, organisation.yaml, equipes-assets.yaml) : "
        f"{len(REGLES_COMPLEMENT)} règles Read (./, //**/ et ~/**/, suffixe *)",
        f"total : {len(REGLES_COMPLEMENT)} règles",
    ]


if __name__ == "__main__":
    if "--json-complement" in sys.argv:
        print(json.dumps(list(REGLES_COMPLEMENT), indent=2, ensure_ascii=False))
    elif "--familles-complement" in sys.argv:
        print("\n".join(familles_complement()))
    elif "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--familles" in sys.argv:
        print("\n".join(familles()))
    else:
        unittest.main()
