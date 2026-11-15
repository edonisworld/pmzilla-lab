"""Règles du fragment 41 : protection en écriture des gardes, des crochets et de leurs modules (change session-guard-n1, design D7, Q1 (a), Q17 ; tâche 4.1 ;
spec tooling-permission-guards ; fichier d'étape P1 de l'auteur qui pose le fragment, nom : 41-protection-gardes.txt).

Constat (audit #629, classe C) : les gardes PreToolUse et les crochets Git tournent depuis des copies que la session peut écrire. Une fois le fragment 41 posé,
la session ne peut plus ÉDITER (un outil d'édition, Write et NotebookEdit compris : une règle Edit( les couvre tous, R-84) :
 - les crochets de `tools/hooks/`, les gardes (npm_guard, pipe_guard, garde_session) et chaque module qu'ils importent, ni `.claude/**`, dans l'espace de travail
   et dans l'arbre de run, par le chemin du dossier personnel (`~/PMZilla-Lab/workspace/…`) ou par le chemin absolu (`//**/PMZilla-Lab/workspace/…`) ;
 - `.claude/settings*.json` dans tout dossier (les worktrees compris) et `~/.claude/settings*.json`.
Aucune forme relative nue pour les fichiers de l'espace de travail : elle couvrirait aussi le worktree où la session travaille (Q1 (a) laisse les worktrees
modifiables). Le même chemin dans un worktree reste donc permis ; il n'est jamais exécuté par une garde ni par un crochet (lancement par chemin absolu de la copie de
l'espace de travail, correction 8 de commit-msg).

SOURCE UNIQUE des chemins : tools/garde_session.py (DOSSIERS_PROTEGES, FICHIERS_PROTEGES) ; la règle C de la garde et ce fragment lisent la même liste. Le fragment 41
recevra aussi les règles Edit du niveau 2 (bac à sable, R-20261107-26) par cette même fonction de liste.

Conception (même motif que test_settings_deny_garde_main_session.py) : ce module est écrit AVANT la pose :
 - la matrice des chemins s'applique au bloc déclaré, toujours : verte avant comme après ;
 - les tests du fichier réel sont SAUTÉS tant que rien n'est posé, ÉCHOUENT si la pose est partielle (ils nomment la règle absente) et rejouent la matrice contre les
   règles réelles quand tout est posé.
Aucune commande n'est lancée ; le test lit .claude/settings.json, .claude/deny/ORDRE et le fragment.

Remplace : rien (les fragments 16, 27 et 34 protègent d'autres chemins). Retrait : permanent ; l'outil d'édition tourne hors du bac à sable, sa protection repose sur
ces règles même après le niveau 2.

    bash tests/run_all.sh settings_deny
    python3 tests/settings_deny/test_settings_deny_gardes.py --json           (les règles Edit du fragment 41)
    python3 tests/settings_deny/test_settings_deny_gardes.py --lignes 41      (le fragment 41, une règle par ligne)
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(RACINE / "tools"))
import garde_regles  # noqa: E402
import garde_session  # noqa: E402
from test_settings_deny_story_quality import Moteur  # noqa: E402

# Édition publique : le test du bac à sable (liste N2) n'est pas publié ; la liste N2 est alors vide et les tests qui en dépendent sont sautés.
# Remplace : rien. Retrait : tombe quand test_settings_deny_bac_a_sable.py est publié par le manifeste `edition/manifest.yaml` (source), l'écart se voit
# par tests/build_edition/test_tests_publies_sans_fichier_exclu.py, qui vérifie dans le dépôt privé que ce fichier est exclu (ATTENDUS).
# La tolérance ne joue que dans l'arbre public (manifeste absent à la racine) ; dans le dépôt privé, l'absence du fichier fait échouer le chargement.
if not (Path(__file__).resolve().parent / "test_settings_deny_bac_a_sable.py").is_file():
    if (RACINE / "edition" / "manifest.yaml").is_file():
        raise AssertionError("le test du bac à sable est absent du dépôt privé (le manifeste de l'édition est présent) : la liste N2 est exigée")
    bac_a_sable = None
else:
    import test_settings_deny_bac_a_sable as bac_a_sable  # noqa: E402
SANS_N2 = "édition publique : liste N2 non livrée (R-20261108-03)"


def liste_n2() -> list:
    return list(bac_a_sable.regles_attendues()) if bac_a_sable is not None else []


REGLAGES = RACINE / ".claude" / "settings.json"
DENY = RACINE / ".claude" / "deny"
ORDRE = DENY / "ORDRE"
NOM_41 = "41-protection-gardes.txt"
NOM_40 = "40-preuves-ci.txt"
FRAGMENT_41 = DENY / NOM_41


def pose_declaree() -> bool:
    """Vrai dès que le fragment 41 ou son nom dans ORDRE est là (fichiers suivis, commités avec la pose) : les tests du fichier réel ne sont alors plus sautés."""
    return FRAGMENT_41.is_file() or NOM_41 in ORDRE.read_text(encoding="utf-8").split()


# Racines des fichiers exécutés : l'espace de travail et l'arbre de run, par le dossier personnel puis par le chemin absolu. Jamais la forme relative nue.
RACINES = ("~/PMZilla-Lab/workspace", "//**/PMZilla-Lab/workspace", "~/PMZilla-Lab/run", "//**/PMZilla-Lab/run")
CHEMINS = tuple(f"{d}/**" for d in garde_session.DOSSIERS_PROTEGES) + garde_session.FICHIERS_PROTEGES
# Les réglages de Claude Code, partout : le dossier courant, tout chemin absolu, tout chemin sous le dossier personnel, tout chemin relatif, et ceux du dossier personnel.
REGLAGES_PARTOUT = (
    "Edit(./.claude/settings*.json)", "Edit(//**/.claude/settings*.json)", "Edit(~/**/.claude/settings*.json)", "Edit(**/.claude/settings*.json)",
    "Edit(~/.claude/settings*.json)",
)


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees) : rien d'autre que des règles Edit(."""
    return [f"Edit({racine}/{chemin})" for racine in RACINES for chemin in CHEMINS] + list(REGLAGES_PARTOUT)


REGLES_41 = tuple(regles_attendues())


def contenu_admis(lignes: list) -> bool:
    """Contenu admis du fragment 41 (R-20261111-02, N1-Q4 a) : la liste N1 (REGLES_41) exactement, ou la liste N1 suivie exactement de
    test_settings_deny_bac_a_sable.regles_attendues() (liste N2, après sa pose), dans cet ordre. Tout autre contenu est refusé.
    Remplace : l'égalité stricte avec REGLES_41. Retrait : avec le fichier géré du niveau 2, quand les règles N2 passent ailleurs."""
    n1 = list(REGLES_41)
    return lignes == n1 or lignes == n1 + liste_n2()

# --- Matrice des chemins ------------------------------------------------------------------------------------------------------------------

ESPACE = "~/PMZilla-Lab/workspace"
ESPACE_ABS = "/Users/quelquun/PMZilla-Lab/workspace"
RUN = "~/PMZilla-Lab/run"
RUN_ABS = "/Users/quelquun/PMZilla-Lab/run"
WORKTREE = "~/PMZilla-Lab/worktrees/wt-feat-essai"
WORKTREE_ABS = "/Users/quelquun/PMZilla-Lab/worktrees/wt-feat-essai"

EXEMPLES = ("tools/hooks/pre-commit", "tools/hooks/reference-transaction", "tools/npm_guard.py", "tools/pipe_guard.py", "tools/garde_session.py",
            "tools/npm_ci_conditions.py", "tools/lab_paths.py", "tools/lab_paths.sh", "tools/finish_lock.py", "tools/sensitive_names.py", "tools/secret_scan.py",
            "tools/commit_names_scan.py", "tools/preuve_arbre.py", "tools/identifiants_personnels.py", "tools/gh_issue.py", "tools/roadmap_model.py",
            "tools/settings_assemble.py", ".claude/settings.json", ".claude/settings.base.json", ".claude/deny/26-git-push-merge.txt", ".claude/deny/41-protection-gardes.txt",
            ".claude/skills/bmad-help/SKILL.md", ".claude/quarantaine/bmad-eval-runner/SKILL.md.quarantaine")
HORS_LISTE = ("tools/db.py", "tools/doctor.py", "tools/roadmap.py", "tools/hooks_notes.txt", "tests/run_all.sh", "docs/pmzilla/x.md", "CLAUDE.md", "mothra/README.md")
OUTILS = ("Edit", "Write")


PERMIS = [".claude/deny/x.txt", f"{WORKTREE}/.claude/deny/x.txt", f"{WORKTREE_ABS}/.claude/skills/x/SKILL.md", "~/.claude/projects/x/memory.md",
          "~/.claude/keybindings.json", "~/.claude/settings.md"]
# Refusés par d'autres fragments que le 41 (34 pour CLAUDE.md, 16 pour le dossier d'exécution) : doivent le rester une fois le 41 posé (R-20261111-09, P1-Q1 a).
RESTENT_REFUSES = (f"{ESPACE}/CLAUDE.md", f"{ESPACE_ABS}/CLAUDE.md", f"{RUN}/tools/db.py", f"{RUN}/tools/doctor.py", f"{RUN}/tools/roadmap.py")


def sans_regles_41(deny: list) -> list:
    """Le deny sans les règles du fragment 41 : sert de référence pour dire ce que le 41 ajoute, et rien de plus."""
    return [r for r in deny if r not in REGLES_41]


class Matrice:
    """Cas communs au bloc REGLES_41 et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange.

    `moteur_sans_41` : None pour le bloc seul ; pour les règles réelles, le moteur du deny réel privé des règles de REGLES_41 (R-20261111-09, P1-Q1 a)."""

    moteur_sans_41 = None

    def verifier_workspace_et_run_refuses(self):
        manquants = [(o, f"{r}/{c}") for o in OUTILS for r in (ESPACE, ESPACE_ABS, RUN, RUN_ABS) for c in EXEMPLES
                     if not self.moteur.acces_interdit(o, f"{r}/{c}")]
        self.assertEqual(manquants[:5], [], f"{len(manquants)} chemin(s) non refusé(s)")

    def verifier_meme_chemin_dans_un_worktree_permis(self):
        refuses = [(o, f"{r}/{c}") for o in OUTILS for r in (WORKTREE, WORKTREE_ABS) for c in EXEMPLES
                   if not c.startswith(".claude/settings") and self.moteur.acces_interdit(o, f"{r}/{c}")]
        self.assertEqual(refuses[:5], [], "chemin(s) d'un worktree refusé(s) : règle trop large (Q1 (a))")
        refuses = [(o, c) for o in OUTILS for c in EXEMPLES if not c.startswith(".claude/settings") and self.moteur.acces_interdit(o, c)]
        self.assertEqual(refuses[:5], [], "forme relative nue refusée : elle couvrirait le worktree de la session")

    def verifier_reglages_partout(self):
        chemins = [f"{WORKTREE}/.claude/settings.json", f"{WORKTREE_ABS}/.claude/settings.local.json", f"{WORKTREE_ABS}/.claude/settings.base.json",
                   "~/.claude/settings.json", "~/.claude/settings.local.json", "/Users/quelquun/.claude/settings.json", "~/autre/.claude/settings.json",
                   "/Users/quelquun/autre/.claude/settings.local.json", ".claude/settings.json", ".claude/settings.local.json", "./.claude/settings.base.json",
                   "sous/dossier/.claude/settings.json", f"{ESPACE}/.claude/settings.json", f"{RUN_ABS}/.claude/settings.local.json"]
        manquants = [(o, c) for o in OUTILS for c in chemins if not self.moteur.acces_interdit(o, c)]
        self.assertEqual(manquants, [])

    def verifier_hors_liste_permis(self):
        chemins = [(o, f"{r}/{c}") for o in OUTILS for r in (ESPACE, ESPACE_ABS, RUN, RUN_ABS, WORKTREE) for c in HORS_LISTE]
        if self.moteur_sans_41 is None:
            refuses = [(o, c) for o, c in chemins if self.moteur.acces_interdit(o, c)]
            self.assertEqual(refuses[:5], [], "chemin hors liste refusé : règle trop large")
            self.assertEqual([c for c in PERMIS if self.moteur.acces_interdit("Edit", c)], [])
            return
        # Règles réelles : d'autres fragments refusent légitimement CLAUDE.md et run/tools/{db,doctor,roadmap}.py. Le 41 n'en refuse aucun de plus.
        refuses = [(o, c) for o, c in chemins if self.moteur.acces_interdit(o, c)]
        refuses_sans_41 = [(o, c) for o, c in chemins if self.moteur_sans_41.acces_interdit(o, c)]
        self.assertEqual(refuses, refuses_sans_41, "le fragment 41 refuse un chemin hors liste de plus : règle trop large")
        # PERMIS : aucun refusé, sur le réel comme sur le bloc (revue Opus de R-20261111-09 : la décision ne vise que les chemins hors liste).
        self.assertEqual([c for c in PERMIS if self.moteur.acces_interdit("Edit", c)], [])

    def verifier_claude_md_et_run_restent_refuses(self):
        """Sur le deny réel, Edit et Write de CLAUDE.md et de run/tools/{db,doctor,roadmap}.py restent refusés (fragments 34 et 16, pas le 41)."""
        ouverts = [(o, c) for o in OUTILS for c in RESTENT_REFUSES if not self.moteur.acces_interdit(o, c)]
        self.assertEqual(ouverts, [], "chemin(s) refusé(s) par d'autres fragments devenu(s) permis")


class BlocGardes(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_41)

    def test_le_bloc_est_fait_de_regles_edit_sans_doublon(self):
        self.assertTrue(REGLES_41, "bloc vide")
        self.assertEqual(len(REGLES_41), len(set(REGLES_41)))
        self.assertTrue(all(r.startswith("Edit(") and r.endswith(")") for r in REGLES_41))
        self.assertEqual(garde_regles.constats(REGLES_41), [])

    def test_aucune_regle_write_ni_notebookedit(self):
        self.assertEqual([r for r in REGLES_41 if r.startswith(("Write(", "NotebookEdit("))], [])

    def test_une_regle_autre_que_edit_est_refusee_par_la_garde_partagee(self):
        """La garde R-84 refuse Write( et NotebookEdit( dans une liste de ce module : le constat nomme la règle."""
        faute = list(REGLES_41) + ["Write(~/PMZilla-Lab/workspace/tools/npm_guard.py)", "NotebookEdit(~/PMZilla-Lab/workspace/x.ipynb)"]
        constats = garde_regles.constats(faute)
        self.assertEqual(len(constats), 2)
        self.assertTrue(all(garde_regles.ECRITURE_IGNOREE in c for c in constats))

    def test_les_comptes(self):
        self.assertEqual(len(garde_session.FICHIERS_PROTEGES), 15)
        self.assertEqual(len(CHEMINS), 17)
        self.assertEqual(len(REGLES_41), 4 * 17 + 5)

    def test_aucune_forme_relative_nue_pour_les_fichiers_de_l_espace(self):
        for regle in REGLES_41:
            corps = regle[len("Edit("):-1]
            if "settings*.json" in corps:
                continue
            self.assertTrue(corps.startswith(("~/PMZilla-Lab/workspace/", "//**/PMZilla-Lab/workspace/", "~/PMZilla-Lab/run/", "//**/PMZilla-Lab/run/")), regle)

    def test_la_garde_partagee_trouve_la_liste(self):
        texte = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(garde_regles.imprime_json(texte))
        self.assertEqual(garde_regles._liste_du_module(Path(__file__), garde_regles.CONVENTION), list(REGLES_41))

    def test_workspace_et_run_sont_refuses_par_chemin_personnel_et_absolu(self):
        self.verifier_workspace_et_run_refuses()

    def test_le_meme_chemin_dans_un_worktree_reste_permis(self):
        self.verifier_meme_chemin_dans_un_worktree_permis()

    def test_les_reglages_sont_refuses_partout(self):
        self.verifier_reglages_partout()

    def test_ce_qui_n_est_pas_dans_la_liste_reste_permis(self):
        self.verifier_hors_liste_permis()

    def test_la_garde_de_session_et_le_fragment_lisent_la_meme_liste(self):
        """Source unique : un chemin que la règle C de la garde protège est refusé par une règle Edit du bloc, et inversement pour l'espace de travail."""
        class Ctx:
            espace, run = "/Users/quelquun/PMZilla-Lab/workspace", "/Users/quelquun/PMZilla-Lab/run"
        for exemple in EXEMPLES:
            attendu_garde = garde_session.relatif_protege(exemple)
            self.assertEqual(garde_session.protege(f"{Ctx.espace}/{exemple}", Ctx), attendu_garde, exemple)
            self.assertEqual(self.moteur.acces_interdit("Edit", f"{ESPACE_ABS}/{exemple}"), attendu_garde, exemple)
        self.assertTrue(garde_session.relatif_protege(".claude/deny/x.txt"))
        for hors in HORS_LISTE:
            self.assertFalse(garde_session.relatif_protege(hors), hors)


class DansLeFichierDeReglages(unittest.TestCase):
    """La pose par l'auteur : sautée avant, échoue si elle est partielle, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.manquantes = [r for r in REGLES_41 if r not in cls.deny]

    def setUp(self):
        if not pose_declaree() and len(self.manquantes) == len(REGLES_41):
            self.skipTest("fragment 41 pas encore posé (fichier d'étape P1 de l'auteur)")

    def test_la_pose_declaree_est_complete(self):
        """Le fragment 41 absent d'un côté seulement (fichier sans ORDRE, ou ORDRE sans fichier) est une pose partielle."""
        self.assertTrue(FRAGMENT_41.is_file(), f"{NOM_41} absent de .claude/deny/ alors qu'ORDRE le nomme")
        noms = ORDRE.read_text(encoding="utf-8").split()
        self.assertIn(NOM_41, noms, f"{NOM_41} présent sans être dans .claude/deny/ORDRE")
        self.assertEqual(noms.index(NOM_41), noms.index(NOM_40) + 1, "le fragment 41 suit le fragment 40 dans ORDRE")

    def test_les_regles_edit_sont_dans_settings_json(self):
        self.assertEqual(self.manquantes, [], f"pose partielle : {len(self.manquantes)} règle(s) du fragment 41 absente(s) de .claude/settings.json : "
                         + " ; ".join(self.manquantes[:10]))

    def test_le_fragment_contient_la_liste_et_rien_d_autre(self):
        lignes = [ligne for ligne in FRAGMENT_41.read_text(encoding="utf-8").splitlines() if ligne.strip()]
        self.assertTrue(contenu_admis(lignes), "le fragment doit être la liste N1, seule ou suivie exactement de la liste N2, rien d'autre")

    def test_la_matrice_des_chemins_contre_les_regles_reelles(self):
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes[:10]))
        jouer_matrice(self, self.deny)

    def test_claude_md_et_run_restent_refuses_sur_le_deny_reel(self):
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes[:10]))
        jouer_verification(self, self.deny, "verifier_claude_md_et_run_restent_refuses")


SOUS_CAS = ("verifier_workspace_et_run_refuses", "verifier_meme_chemin_dans_un_worktree_permis", "verifier_reglages_partout", "verifier_hors_liste_permis")


def jouer_verification(test, deny: list, nom: str):
    """Joue une vérification de la matrice sur un deny complet, avec la référence « deny sans le fragment 41 »."""
    matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(deny), "moteur_sans_41": Moteur(sans_regles_41(deny))})
    with test.subTest(verification=nom):
        getattr(matrice(nom), nom)()


def jouer_matrice(test, deny: list):
    for nom in SOUS_CAS:
        jouer_verification(test, deny, nom)


@unittest.skipIf(bac_a_sable is None, SANS_N2)
class DecisionContenuAdmis(unittest.TestCase):
    """La fonction de décision appliquée à des listes construites : tourne toujours, sans dépendre de la pose (R-20261111-02, N1-Q4 a)."""

    N1 = list(REGLES_41)
    N2 = liste_n2()

    def test_n1_seul_est_admis(self):
        self.assertTrue(contenu_admis(self.N1))

    def test_n1_puis_n2_est_admis(self):
        self.assertTrue(contenu_admis(self.N1 + self.N2))

    def test_n2_puis_n1_est_refuse(self):
        self.assertFalse(contenu_admis(self.N2 + self.N1))

    def test_n1_n2_moins_une_ligne_est_refuse(self):
        for i in range(len(self.N2)):
            self.assertFalse(contenu_admis(self.N1 + self.N2[:i] + self.N2[i + 1:]), i)

    def test_n1_n2_plus_une_ligne_est_refuse(self):
        self.assertFalse(contenu_admis(self.N1 + self.N2 + ["Edit(~/PMZilla-Lab/workspace/x)"]))
        self.assertFalse(contenu_admis(self.N1 + self.N2 + [self.N2[0]]))

    def test_n1_moins_une_ligne_est_refuse(self):
        self.assertFalse(contenu_admis(self.N1[:-1]))
        self.assertFalse(contenu_admis(self.N1[1:]))

    def test_n1_plus_une_ligne_de_n2_est_refuse(self):
        for ligne in self.N2:
            self.assertFalse(contenu_admis(self.N1 + [ligne]), ligne)

    def test_n1_et_n2_sont_disjointes(self):
        self.assertEqual(set(self.N1) & set(self.N2), set())


class DenySimuleAvecLe41(unittest.TestCase):
    """Le deny réel de .claude/settings.json plus REGLES_41 (sans doublon), joué avec la matrice et l'assertion CLAUDE.md / run/ : tourne toujours, avant comme après la pose.

    Prouve, avant la pose, que la pose de P1 sera verte (R-20261111-09, P1-Q1 a). Remplace : rien. Duplique, une fois le 41 posé, la source
    DansLeFichierDeReglages (même matrice et même assertion sur le deny réel, qui contient alors REGLES_41 : le deny simulé lui est égal) ; un écart entre
    les deux ne peut venir que d'une différence entre REGLES_41 et le fragment posé, que test_le_fragment_contient_la_liste_et_rien_d_autre voit.
    Retrait : à la première branche qui touche ce fichier après la fusion de la pose de P1 (la pose est un fichier d'étape de l'auteur, elle ne retire rien
    du dépôt)."""

    @classmethod
    def setUpClass(cls):
        reel = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.deny = reel + [r for r in REGLES_41 if r not in reel]

    def test_pas_de_doublon_et_toutes_les_regles_du_41(self):
        self.assertEqual([r for r in REGLES_41 if self.deny.count(r) != 1], [])

    def test_la_matrice_sur_le_deny_simule(self):
        jouer_matrice(self, self.deny)

    def test_claude_md_et_run_restent_refuses_sur_le_deny_simule(self):
        jouer_verification(self, self.deny, "verifier_claude_md_et_run_restent_refuses")


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--lignes" in sys.argv:
        print("\n".join(regles_attendues()))
    else:
        unittest.main()
