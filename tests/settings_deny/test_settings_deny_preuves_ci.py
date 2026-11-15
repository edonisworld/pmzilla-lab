"""Règles `deny` du dossier des preuves de la CI locale et du nom de variable CI_LOCAL_PREUVES (R-20261104-58 Q2 (a), T2 de R-182).

La preuve de train (une ligne arbre, clé d'image, phases) est écrite par `ci_local.sh run` dans `~/.pmzilla-lab/ci/` ; une session qui l'écrirait
à la main, ou qui désignerait un autre fichier par la variable CI_LOCAL_PREUVES, fabriquerait une preuve. Trois règles :
  - `Edit(~/.pmzilla-lab/ci/**)` et `Edit(//**/.pmzilla-lab/ci/**)` (forme sous le dossier personnel et forme absolue, comme les fragments
    voisins) : une règle `Edit(chemin)` couvre aussi Write et NotebookEdit ; aucune règle `Write(chemin)`, que Claude Code ignore et que
    tools/settings_assemble.py refuse (garde R-84, tests/settings_deny/garde_regles.py). Le moteur de ce module applique donc chaque règle
    Edit aux deux outils, Edit et Write, comme Claude Code.
  - `Bash(*CI_LOCAL_PREUVES*)` : toute commande qui contient le nom de la variable est refusée, où qu'il soit (préfixe `VAR=x`, `export`, `env`).
Ce que les règles n'interdisent pas : lire ce dossier ; lancer `bash tools/ci_local.sh run <branche>` (qui écrit lui-même la preuve, hors des outils
Edit et Write) ; lancer une suite par `bash tests/run_all.sh <suite>` : aucune règle ne vise cette commande, qui ne contient pas le nom de la
variable. Les suites qui posent CI_LOCAL_PREUVES (tests/ci_local) le font dans un sous-processus du test, hors des règles de l'outil Bash ; le test
`SuitesQuiPosentLaVariable` le prouve en lisant tests/.

Remplace : rien (aucune règle ne visait ce dossier ni ce nom). Condition de retrait : les preuves sont écrites hors de portée de la session
(signées, ou par un processus que la session ne lance pas) (R-20261104-58 Q2 (a)).
Fragment : .claude/deny/40-preuves-ci.txt, nommé à la fin de .claude/deny/ORDRE. Les fragments n'admettent aucun commentaire (settings_assemble
refuse une ligne qui n'est pas Outil(motif)) : ce texte tient lieu de commentaire de tête de bloc. Les cas contre les vrais fichiers
(DansLesFichiers) restent rouges tant que l'auteur n'a pas régénéré .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_preuves_ci.py --json
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_story_quality import Moteur  # noqa: E402
import test_settings_deny_gardes  # noqa: E402
import test_settings_deny_run_worktree  # noqa: E402

# Édition publique : le test du bac à sable (liste N2) n'est pas publié ; la liste N2 est alors vide et les classes qui en dépendent sont sautées.
# Remplace : rien. Retrait : tombe quand test_settings_deny_bac_a_sable.py est publié (source : `edition/manifest.yaml` ; écart vu dans le dépôt privé par
# tests/build_edition/test_tests_publies_sans_fichier_exclu.py, ATTENDUS).
BAC_A_SABLE_LIVRE = test_settings_deny_gardes.bac_a_sable is not None   # le saut de classe plus bas
SANS_N2 = test_settings_deny_gardes.SANS_N2

REGLAGES = RACINE / ".claude" / "settings.json"
ORDRE = RACINE / ".claude" / "deny" / "ORDRE"
NOM_FRAGMENT = "40-preuves-ci.txt"
FRAGMENT = RACINE / ".claude" / "deny" / NOM_FRAGMENT
VARIABLE = "CI_LOCAL_PREUVES"

REGLES_PREUVES = [
    "Edit(~/.pmzilla-lab/ci/**)",
    "Edit(//**/.pmzilla-lab/ci/**)",
    f"Bash(*{VARIABLE}*)",
]

OUTILS = ("Edit", "Write")  # le moteur applique une règle Edit à Write, comme Claude Code (R-84)
CHEMINS_REFUSES = (
    "~/.pmzilla-lab/ci/preuves", "~/.pmzilla-lab/ci/verdicts", "~/.pmzilla-lab/ci/rapport-2026-11-04.txt", "~/.pmzilla-lab/ci/sous/dossier/preuves",
    "/Users/quelquun/.pmzilla-lab/ci/preuves", "/Users/quelquun/.pmzilla-lab/ci/sous/dossier/preuves", "/Users/autre/.pmzilla-lab/ci/verdicts",
)
CHEMINS_PERMIS = (
    "~/.pmzilla-lab/ciel/preuves", "~/.pmzilla-lab/sauvegardes/x", "~/.pmzilla-lab/offsite/statut", "~/.pmzilla-lab/preuves",
    "/Users/quelquun/.pmzilla-lab/ciel/preuves", "/Users/quelquun/.pmzilla-lab/preuves",
    "tools/ci_local.sh", "tests/ci_local/test_ci_local.sh", ".claude/deny/40-preuves-ci.txt", "docs/pmzilla/installation.md",
    "tests/settings_deny/test_settings_deny_preuves_ci.py",
)
COMMANDES_REFUSEES = (  # une forme de chaque famille : nom de la variable en préfixe, en export, derrière env, au milieu, collé
    f"{VARIABLE}=/x/preuves bash tools/ci_local.sh run feat/x",
    f"{VARIABLE}=/x/preuves bash tests/run_all.sh ci_local",
    f"export {VARIABLE}=/x/preuves",
    f"env {VARIABLE}=/x/preuves bash tools/ci_local.sh run main",
    f"cd /x && {VARIABLE}=/x/p bash tests/run_all.sh ci_local",
    f"echo {VARIABLE}",
    f"unset {VARIABLE}",
    f"bash -c 'export {VARIABLE}=/x/p; bash tools/ci_local.sh run main'",
)
COMMANDES_ADMISES = (  # aucune règle ne vise les lancements sans le nom de la variable
    "bash tests/run_all.sh ci_local", "bash tests/run_all.sh settings_deny", "bash tests/run_all.sh",
    "uv run tools/pilot.py freeze --check && bash tests/run_all.sh ci_local",
    "bash tools/ci_local.sh run feat/x", "bash tools/ci_local.sh places", "bash tools/ci_local.sh cle",
    "git log --oneline -- tools/ci_local.sh", "ls ~/.pmzilla-lab/ci",
)


def regles_attendues() -> list:
    """Les 3 règles du fragment 40."""
    return list(REGLES_PREUVES)


def ecarts_chemins_permis(deny, fragment=REGLES_PREUVES) -> list:
    """Les (outil, chemin) de CHEMINS_PERMIS que `fragment` fait refuser : refusés(deny) != refusés(deny moins fragment).

    Invariante de R-20261111-10 (même que P1-Q1) : un chemin « permis » n'est refusé par le fragment vérifié que s'il l'est déjà sans lui ;
    les refus qu'un autre fragment apporte (N2, bac à sable) sont couverts par les tests de ce fragment-là. Retrait exact par égalité de chaînes.
    Remplace : l'assertion « aucun chemin permis n'est refusé par le deny réel » (DansLesFichiers). Retrait : permanent, c'est la forme
    qui tient quand d'autres fragments refusent des chemins sous ~/.pmzilla-lab ou tools/."""
    avec = Moteur(list(deny))
    sans = Moteur([r for r in deny if r not in fragment])
    return [(o, c) for o in OUTILS for c in CHEMINS_PERMIS if avec.acces_interdit(o, c) != sans.acces_interdit(o, c)]


def ecarts_chemins_permis_stricts(deny) -> list:
    """Les (outil, chemin) de CHEMINS_PERMIS que `deny` moins les règles N2 fait refuser : refusés(deny moins N2) == [] est attendu.

    Contrôle strict de R-20261111-12 (P1-Q3 b), ajouté à ecarts_chemins_permis, qui reste : seules les règles N2 (bac à sable) peuvent refuser un
    chemin « permis » ; toute autre règle qui en refuse un rend ce contrôle rouge, même si elle est masquée par N2 dans la formule du fragment.
    Les règles exemptées sont lues à leur source, regles_attendues() du test du bac à sable (via liste_n2 de test_settings_deny_gardes), jamais recopiées.
    Remplace : rien. Retrait : quand les règles N2 quittent le deny (retour à la forme stricte sans exemption) ; source des règles exemptées :
    regles_attendues(), aucune copie."""
    n2 = test_settings_deny_gardes.liste_n2()
    moteur = Moteur([r for r in deny if r not in n2])
    return [(o, c) for o in OUTILS for c in CHEMINS_PERMIS if moteur.acces_interdit(o, c)]


class Bloc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_PREUVES)

    def test_trois_regles_sans_doublon(self):
        self.assertEqual(len(REGLES_PREUVES), 3)
        self.assertEqual(len(set(REGLES_PREUVES)), 3)
        self.assertEqual(regles_attendues(), REGLES_PREUVES)

    def test_la_garde_partagee_passe_sur_le_bloc(self):
        self.assertEqual(garde_regles.constats(regles_attendues()), [])
        self.assertTrue(garde_regles.imprime_json(Path(__file__).read_text(encoding="utf-8")))

    def test_aucune_regle_write_ni_notebookedit(self):
        self.assertEqual([r for r in REGLES_PREUVES if r.startswith(("Write(", "NotebookEdit("))], [])

    def test_chaque_chemin_est_refuse_en_edition_et_en_ecriture(self):
        manquants = [(o, c) for o in OUTILS for c in CHEMINS_REFUSES if not self.moteur.acces_interdit(o, c)]
        self.assertEqual(manquants, [])

    def test_une_forme_de_chaque_regle_edit_est_exigee(self):
        """Chaque règle Edit est la seule à refuser au moins un chemin : retirer l'une des deux fait échouer ce test."""
        for regle in REGLES_PREUVES[:2]:
            sans = Moteur([r for r in REGLES_PREUVES if r != regle])
            seuls = [c for c in CHEMINS_REFUSES if not sans.acces_interdit("Edit", c)]
            self.assertTrue(seuls, f"la règle {regle} ne refuse aucun chemin que l'autre ne refuse pas")

    def test_les_autres_chemins_restent_permis(self):
        self.assertEqual([(o, c) for o in OUTILS for c in CHEMINS_PERMIS if self.moteur.acces_interdit(o, c)], [])

    def test_le_bloc_ne_pose_aucune_regle_de_lecture(self):
        self.assertEqual([r for r in REGLES_PREUVES if r.startswith("Read(")], [])

    def test_chaque_commande_qui_contient_la_variable_est_refusee(self):
        self.assertEqual([c for c in COMMANDES_REFUSEES if not self.moteur.interdite(c)], [])

    def test_les_lancements_sans_la_variable_restent_admis(self):
        self.assertEqual([c for c in COMMANDES_ADMISES if self.moteur.interdite(c)], [])


class SuitesQuiPosentLaVariable(unittest.TestCase):
    """Aucune règle ne vise `bash tests/run_all.sh …` : une suite qui pose CI_LOCAL_PREUVES le fait dans un sous-processus de son test
    (export dans un script de test, variable d'environnement d'un sous-processus Python), jamais sur la ligne de commande que la session
    lance. Ce test lit tests/ et tests/run_all.sh ; il ne lance rien."""

    @classmethod
    def setUpClass(cls):
        moi = Path(__file__).resolve()
        cls.fichiers = [p for p in sorted((RACINE / "tests").rglob("*"))
                        if p.is_file() and p.suffix in (".sh", ".py") and "__pycache__" not in p.parts and p.resolve() != moi]
        cls.mentions = {}
        for p in cls.fichiers:
            lignes = [(i, l) for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1) if VARIABLE in l]
            if lignes:
                cls.mentions[p.relative_to(RACINE).as_posix()] = lignes

    def test_la_suite_ci_local_pose_la_variable_dans_son_test(self):
        self.assertIn("tests/ci_local/test_ci_local.sh", self.mentions)
        self.assertTrue(any(l.lstrip().startswith(f"export {VARIABLE}=") for _, l in self.mentions["tests/ci_local/test_ci_local.sh"]))

    def test_aucune_ligne_ne_pose_la_variable_en_lancant_run_all(self):
        mauvaises = [f"{f}:{i}" for f, lignes in self.mentions.items() for i, l in lignes if "run_all" in l]
        self.assertEqual(mauvaises, [], "une suite pose la variable sur une ligne qui lance run_all : la règle Bash la refuserait")

    def test_run_all_ne_nomme_pas_la_variable(self):
        self.assertNotIn(VARIABLE, (RACINE / "tests" / "run_all.sh").read_text(encoding="utf-8"))

    def test_aucune_suite_ne_pose_la_variable_en_prefixe_d_un_lancement(self):
        """`CI_LOCAL_PREUVES=… bash …` en tête de ligne (un lancement que la session ferait elle-même) : aucune ligne de tests/ n'en a la forme,
        hors export, affectation de test et sous-processus Python (liste de noms d'environnement)."""
        prefixes = [f"{f}:{i}" for f, lignes in self.mentions.items() for i, l in lignes
                    if l.lstrip().startswith(f"{VARIABLE}=") and any(m in l for m in ("bash ", "uv run", "python"))]
        self.assertEqual(prefixes, [])


class DansLesFichiers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur(cls.deny)

    def test_les_trois_regles_sont_dans_les_reglages(self):
        manquantes = [r for r in REGLES_PREUVES if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) absente(s) de .claude/settings.json (l'auteur régénère)")

    def test_le_fragment_40_est_nomme_une_fois_dans_ordre(self):
        noms = [n for n in ORDRE.read_text(encoding="utf-8").split("\n") if n]
        self.assertEqual(noms.count(NOM_FRAGMENT), 1)

    def test_le_fragment_40_contient_les_trois_regles_dans_l_ordre(self):
        lignes = [n for n in FRAGMENT.read_text(encoding="utf-8").split("\n") if n]
        self.assertEqual(lignes, REGLES_PREUVES)

    def test_les_vrais_reglages_refusent_chemins_et_commandes(self):
        self.assertEqual([(o, c) for o in OUTILS for c in CHEMINS_REFUSES if not self.moteur.acces_interdit(o, c)], [])
        self.assertEqual([c for c in COMMANDES_REFUSEES if not self.moteur.interdite(c)], [])

    def test_les_vrais_reglages_laissent_les_autres_chemins_et_les_lancements(self):
        self.assertEqual(ecarts_chemins_permis(self.deny), [])
        self.assertEqual(ecarts_chemins_permis_stricts(self.deny), [])  # R-20261111-12 : seules les règles N2 peuvent refuser ces chemins
        self.assertEqual([c for c in COMMANDES_ADMISES if self.moteur.interdite(c)], [])

    def test_les_vrais_reglages_laissent_lire_le_dossier_des_preuves(self):
        self.assertEqual([c for c in CHEMINS_REFUSES if self.moteur.lecture_interdite(c)], [])

    def test_aucune_regle_write_ni_notebookedit_ne_vise_le_dossier(self):
        self.assertEqual([d for d in self.deny if "pmzilla-lab/ci" in d and d.startswith(("Write(", "NotebookEdit("))], [])


@unittest.skipUnless(BAC_A_SABLE_LIVRE, SANS_N2)
class SurDenyN2Simule(unittest.TestCase):
    """Les trois vérifications de chemins « permis » rejouées sur un deny simulé : deny réel + fragment 41 + les 13 règles Edit de N2 (bac à
    sable), sans doublon. Vert dès aujourd'hui : prouve que la pose de N2 ne rend rouge ni les preuves CI ni le dossier d'exécution (R-20261111-10).

    Remplace : rien. Duplique, une fois N2 posé, les sources DansLesFichiers (ce fichier) et DansLeFichierDeReglages
    (test_settings_deny_run_worktree.py) : le deny simulé est alors égal au réel ; un écart entre eux ne peut venir que d'une différence entre
    REGLES_41 + règles N2 et le fragment 41 posé, que contenu_admis (test_le_fragment_contient_la_liste_et_rien_d_autre) voit.
    Retrait : à la première branche qui touche ce fichier après la fusion de la pose de N2."""

    @classmethod
    def setUpClass(cls):
        reel = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.n2 = test_settings_deny_gardes.liste_n2()
        cls.deny = list(dict.fromkeys(reel + list(test_settings_deny_gardes.REGLES_41) + cls.n2))
        cls.moteur = Moteur(cls.deny)

        class Cas(test_settings_deny_run_worktree.Verifications):  # le moteur de run_worktree, sur le deny simulé
            regles = cls.deny
        cls.cas = Cas()

    def test_chemins_permis_des_preuves_ci(self):
        self.assertEqual(ecarts_chemins_permis(self.deny), [])

    def test_formes_permises_du_dossier_d_execution(self):
        self.assertEqual(self.cas.ecarts_formes_permises(), [])

    def test_commandes_admises_des_preuves_ci(self):
        self.assertEqual([c for c in COMMANDES_ADMISES if self.moteur.interdite(c)], [])

    def test_commandes_permises_du_dossier_d_execution(self):
        self.assertEqual([c for c in test_settings_deny_run_worktree.COMMANDES_PERMISES if self.cas.commande_interdite(c)], [])

    def test_la_formule_n_ignore_pas_tout_n2_refuse_bien_ces_chemins(self):
        """Sur le deny simulé, N2 refuse bien ces deux chemins : l'invariante les laisse passer parce que N2 est hors du fragment vérifié."""
        self.assertTrue(self.cas.edition_interdite("Edit", "~/PMZilla-Lab/workspace/tools/x.py"))
        self.assertTrue(self.moteur.acces_interdit("Edit", "~/.pmzilla-lab/ciel/preuves"))
        self.assertIn("Edit(~/.pmzilla-lab/**)", self.n2)

    def test_temoin_preuves_ci_une_regle_fautive_dans_le_fragment_40_est_vue(self):
        # Ce témoin est vu parce que sa chaîne égale une règle N2 (le retrait par égalité enlève les deux copies) ; une règle distincte,
        # masquée par N2, ne le serait pas ici : pour le fragment 40, Bloc.test_les_autres_chemins_restent_permis (fragment seul) et
        # test_le_fragment_40_contient_les_trois_regles_dans_l_ordre la voient (relecture Opus de R-20261111-10).
        fautive = "Edit(~/.pmzilla-lab/**)"
        fragment = list(REGLES_PREUVES) + [fautive]
        self.assertNotEqual(ecarts_chemins_permis(list(dict.fromkeys(self.deny + [fautive])), fragment), [], fautive)
        # Sans N2 (N2 refuserait déjà ces chemins), une règle plus étroite est vue aussi.
        etroite = "Edit(~/.pmzilla-lab/ciel/**)"
        sans_n2 = [r for r in self.deny if r not in self.n2]
        self.assertNotEqual(ecarts_chemins_permis(sans_n2 + [etroite], list(REGLES_PREUVES) + [etroite]), [], etroite)

    def test_temoin_dossier_d_execution_une_regle_fautive_dans_r43_est_vue(self):
        # « Edit(~/PMZilla-Lab/workspace/tools/**) » est vu parce que sa chaîne égale une règle N2 ; seul « Edit(tools/**) » est un témoin
        # indépendant. Une règle distincte de R43, masquée par N2, est vue par ReglesProposees.test_aucun_chemin_permis_refuse_par_r43_seul.
        for fautive in ("Edit(~/PMZilla-Lab/workspace/tools/**)", "Edit(tools/**)"):
            fragment = list(test_settings_deny_run_worktree.REGLES_R43) + [fautive]

            class Cas(test_settings_deny_run_worktree.Verifications):
                regles = list(dict.fromkeys(self.deny + [fautive]))
            self.assertNotEqual(Cas().ecarts_formes_permises(fragment), [], fautive)


@unittest.skipUnless(BAC_A_SABLE_LIVRE, SANS_N2)
class TemoinsControleStrictHorsN2(unittest.TestCase):
    """Témoins du contrôle strict refusés(deny moins les règles N2) == [] (R-20261111-12), sur un deny simulé : deny réel + règles N2.

    Une règle hors N2 qui refuse un chemin « permis » rend le contrôle rouge ; une règle N2 ne le rend pas rouge.
    Remplace : rien. Retrait : quand les règles N2 quittent le deny (retour à la forme stricte sans exemption) ; source des règles exemptées :
    regles_attendues(), aucune copie."""

    @classmethod
    def setUpClass(cls):
        reel = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.n2 = test_settings_deny_gardes.liste_n2()
        cls.deny = list(dict.fromkeys(reel + cls.n2))

    def test_temoin_une_regle_hors_n2_qui_refuse_un_chemin_permis_rend_le_controle_rouge(self):
        fautive = "Edit(~/.pmzilla-lab/ciel/**)"
        self.assertNotIn(fautive, self.n2)
        self.assertEqual(ecarts_chemins_permis_stricts(self.deny), [])
        ecarts = ecarts_chemins_permis_stricts(self.deny + [fautive])
        self.assertIn(("Edit", "~/.pmzilla-lab/ciel/preuves"), ecarts)
        self.assertIn(("Write", "~/.pmzilla-lab/ciel/preuves"), ecarts)

    def test_temoin_une_regle_hors_n2_masquee_par_n2_rend_aussi_le_controle_rouge(self):
        """La formule du fragment (refusés(deny) != refusés(deny moins fragment)) ne voit pas une règle hors fragment que N2 masque ; le
        contrôle strict la voit, puisqu'il retire N2 avant de compter les refus."""
        fautive = "Edit(~/.pmzilla-lab/offsite/**)"
        self.assertNotIn(fautive, self.n2)
        self.assertEqual(ecarts_chemins_permis(self.deny + [fautive]), [])   # R-20261111-36 : le contrôle ordinaire est bien aveugle ici (la règle est masquée par N2)
        self.assertNotEqual(ecarts_chemins_permis_stricts(self.deny + [fautive]), [])

    def test_temoin_une_regle_n2_ne_rend_pas_le_controle_rouge(self):
        n2_visant_un_chemin_permis = "Edit(~/.pmzilla-lab/**)"
        self.assertIn(n2_visant_un_chemin_permis, self.n2)
        moteur = Moteur([n2_visant_un_chemin_permis])  # elle refuse bien un chemin permis, donc l'exemption est réellement exercée
        self.assertTrue(moteur.acces_interdit("Edit", "~/.pmzilla-lab/ciel/preuves"))
        self.assertEqual(ecarts_chemins_permis_stricts(self.deny + [n2_visant_un_chemin_permis]), [])
        self.assertEqual(ecarts_chemins_permis_stricts(self.n2), [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
