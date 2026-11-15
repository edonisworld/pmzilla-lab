"""Garde de session, niveau 1 (change session-guard-n1, tâche 9.3, design D8) : matrice des fragments doublons.

Les fragments 02 (`security`), 12 (`gh`), 26 (push, `--force`, `--no-verify`) et 39 (garde de main de la session) restent posés ; la garde est leur source. La matrice
fait passer par `decider` chaque forme que les tests des fragments disent refusée : elle échoue, en nommant la forme, quand une forme refusée par un fragment est
admise par la garde, sauf si l'écart est déclaré ci-dessous avec sa raison. Elle compare aussi la liste des scripts de la règle A5 à celle du fragment 07.

Écarts déclarés (formes que le fragment refuse et que la garde ne refuse pas) : chaque famille est décrite par un prédicat, doit contenir au moins une forme admise
(sinon elle est périmée) et toute forme admise doit appartenir à une famille. Depuis R-20261108-01 (question 15 a), la garde reprend `--force`, `git merge`, `git pull`,
`git branch -M|-C … main` et le texte nommé : il ne reste que deux écarts étroits (voir ECARTS). Le désherbage des fragments (tâche 16.1) reste BLOQUÉ pour ces deux familles.

Remplace : rien. Retrait : les lignes de la matrice qui lisent un fragment tombent avec ce fragment, au désherbage du niveau 1 (le bac à sable posé, sa sonde verte
deux semaines ; R-20261107-26, Q15).

    bash tests/run_all.sh garde_session
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, RACINE, g  # noqa: E402

sys.path.insert(0, str(RACINE / "tests" / "settings_deny"))
from test_settings_deny_garde_main_session import (  # noqa: E402
    BRANCH_CHAINAGES, BRANCH_CD, BRANCH_C_WORKTREE, BRANCH_ENV, BRANCH_NUE, BRANCH_OPTIONS_APRES, BRANCH_OPTIONS_AVANT, BRANCH_CHEMIN_ABSOLU,
    EFFETS_COMMANDES, HOOKS_REFUSEES,
)
from test_settings_deny_github import GH_REFUSE, PREFIXES_GH  # noqa: E402
from test_settings_deny_push_merge import (  # noqa: E402
    COMMANDES_FORCE, COMMANDES_SANS_CROCHETS, EFFETS_PARTAGE, ENVELOPPES, FUSIONS_ESPACE, FUSIONS_NUES, STEMS_PR, STEMS_PUSH, SUITES_PUSH,
)

DENY = RACINE / ".claude" / "deny"
FRAGMENTS = {"02": "02-jira-commandes.txt", "12": "12-github-ecriture.txt", "26": "26-git-push-merge.txt", "39": "39-garde-main-session.txt",
             "07": "07-scripts-sauvegarde-fin.txt"}

FORMES_DENIES = {
    # Les tests de ces fragments disent ces formes refusées (modules importés ci-dessus) ou, pour `security`, la règle du fragment 02 nomme le service.
    "02": ["security find-generic-password -s pmzilla-jira -w", "security find-generic-password", "security add-pmzilla-jira x", "security dump-pmzilla-jira"],
    "12": [f"{prefixe} {commande}{suite}" for prefixe, commande, suite in itertools.product(PREFIXES_GH, GH_REFUSE, ("", " 12", " --repo o/r"))],
    "26-push": [f"{stem}{suite}" for stem, suite in itertools.product(STEMS_PUSH, SUITES_PUSH)],
    "26-crochets": [enveloppe.format(commande) for enveloppe, commande in itertools.product(ENVELOPPES, COMMANDES_SANS_CROCHETS)],
    "26-pr": list(STEMS_PR),
    "26-force": [enveloppe.format(commande) for enveloppe, commande in itertools.product(ENVELOPPES, COMMANDES_FORCE)],
    "26-fusion": list(FUSIONS_ESPACE) + list(FUSIONS_NUES),
    "26-texte": list(EFFETS_PARTAGE),
    "39-hooks": list(HOOKS_REFUSEES),
    "39-branch": [c for famille in (BRANCH_NUE, BRANCH_C_WORKTREE, BRANCH_CHEMIN_ABSOLU, BRANCH_ENV, BRANCH_CD, BRANCH_CHAINAGES, BRANCH_OPTIONS_APRES,
                                    BRANCH_OPTIONS_AVANT) for c in famille],
    "39-texte": list(EFFETS_COMMANDES),
}

# Familles d'écarts déclarés : (fragment, prédicat sur la forme, raison).
# R-20261108-01, question 15 a : la garde reprend `--force` hors de push, `git merge` et `git pull` (toutes formes), `git branch -M|-C … main` et les commandes qui
# ne font que nommer le texte (hooksPath, GIT_CONFIG_, push après -C, --force, `git branch -M x main` dans un message) : les familles 26-force, 26-fusion, 39-branch
# ne sont plus des écarts. Restent deux écarts étroits, déclarés avec leur raison ; ils tombent avec le fragment concerné ou sur décision de l'auteur.
ECARTS = {
    "26-texte": ("faux positif du fragment 26 : dans `git commit -m 'note --no-verify'`, --no-verify est le texte du message, pas une option ; "
                 "la garde l'admet (test_commits_ordinaires) et ce refus tombe avec le fragment au désherbage (R-20261108-03, question 1)",
                 lambda c: "--no-verify" in c),
    "39-texte": ("formes que le fragment 39 refuse par accident de motif (sous-chaîne `-f` ou `-m` d'un nom de branche ou de `--format`, `main` en fin de chaîne "
                 "d'une autre commande git) sans être une écriture forcée de main : la garde les admet, la reprise exacte du glob n'est pas voulue",
                 lambda c: any(k in c for k in ("--format", "fix-flaky-ci", "fix-merge-x", "rebase main"))),
}


class MatriceDesDoublons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()
        cls.admises = {}
        for famille, formes in FORMES_DENIES.items():
            cls.admises[famille] = sorted({f for f in formes if g.decider(f, cls.a.contexte()) is None})

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def test_les_fragments_sont_poses(self):
        ordre = (DENY / "ORDRE").read_text(encoding="utf-8").split()
        reglages = set(json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"])
        for nom in FRAGMENTS.values():
            self.assertIn(nom, ordre, nom)
            lignes = [ligne for ligne in (DENY / nom).read_text(encoding="utf-8").splitlines() if ligne.strip()]
            self.assertTrue(lignes, nom)
            self.assertEqual([ligne for ligne in lignes if ligne not in reglages], [], f"{nom} : règle(s) absente(s) des réglages assemblés")

    def test_chaque_famille_a_des_formes(self):
        for famille, formes in FORMES_DENIES.items():
            self.assertTrue(formes, famille)

    def test_toute_forme_refusee_par_un_fragment_l_est_par_la_garde_sauf_ecart_declare(self):
        for famille, admises in self.admises.items():
            if famille in ECARTS:
                continue
            with self.subTest(famille=famille):
                self.assertEqual(admises[:5], [], f"{len(admises)} forme(s) refusée(s) par un fragment et admise(s) par la garde (famille {famille})")

    def test_tout_ecart_admis_appartient_a_une_famille_declaree(self):
        for famille, (raison, predicat) in ECARTS.items():
            admises = self.admises[famille]
            with self.subTest(famille=famille):
                self.assertTrue(raison.strip())
                self.assertTrue(admises, f"écart déclaré périmé : la garde refuse maintenant toutes les formes de {famille}, le retirer de ECARTS")
                hors = [f for f in admises if not predicat(f)]
                self.assertEqual(hors[:5], [], f"forme(s) admise(s) hors de la famille déclarée {famille}")

    def test_les_ecarts_declares_ne_cachent_pas_les_lancements(self):
        """Les formes de push, de crochets sautés, de `gh` et de hooksPath ne sont jamais dans un écart déclaré."""
        for famille in ("02", "12", "26-push", "26-crochets", "26-pr", "39-hooks"):
            self.assertNotIn(famille, ECARTS)
            self.assertEqual(self.admises[famille][:5], [], famille)

    def test_les_formes_de_force_et_de_fusion_sont_refusees_par_la_garde(self):
        """R-20261108-01, question 15 a : `--force` hors de push et `git merge` ne sont plus des écarts, la garde les refuse seule."""
        self.assertIsNotNone(g.decider("env GIT_TRACE=1 git checkout --force main", self.a.contexte()))
        self.assertIsNotNone(g.decider("git push --force", self.a.contexte()))
        self.assertIsNotNone(g.decider("git checkout --force main", self.a.contexte()))
        self.assertIsNotNone(g.decider("git merge main", self.a.contexte()))


class ListeDesScripts(unittest.TestCase):
    def test_les_scripts_de_la_regle_a5_sont_ceux_du_fragment_07(self):
        texte = (DENY / FRAGMENTS["07"]).read_text(encoding="utf-8")
        du_fragment = set(re.findall(r"tools/([A-Za-z0-9_]+\.sh)", texte))
        self.assertEqual(du_fragment, set(g.SCRIPTS_RESERVES))

    def test_les_etiquettes_launchctl_sont_celles_du_fragment_07(self):
        texte = (DENY / FRAGMENTS["07"]).read_text(encoding="utf-8")
        for etiquette in g.ETIQUETTES_LAUNCHCTL:
            self.assertIn(etiquette, texte)
        self.assertIn("DB_BACKUP_", texte)
        self.assertTrue(any(p == "DB_BACKUP_" for p in g.PREFIXES_REGLAGE))

    def test_chaque_forme_de_lancement_du_fragment_07_est_refusee_par_la_garde(self):
        a = Arbre()
        try:
            manquantes = []
            for ligne in (DENY / FRAGMENTS["07"]).read_text(encoding="utf-8").splitlines():
                m = re.fullmatch(r"Bash\((.*)\)", ligne.strip())
                if not m or "tools/" not in m.group(1) or ".sh" not in m.group(1):
                    continue
                forme = m.group(1).replace("*", "")   # `bash *tools/x.sh*` donne `bash tools/x.sh`
                if g.decider(forme, a.contexte()) is None:
                    manquantes.append(forme)
            self.assertEqual(manquantes, [])
        finally:
            a.fermer()


if __name__ == "__main__":
    unittest.main()
