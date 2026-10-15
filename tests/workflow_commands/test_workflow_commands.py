"""Commandes de travail (.claude/commands/{implement,close,add-books,next,start}.md) : le fichier existe, son en-tête ne pré-approuve
aucun lancement interdit (design.md D5), son corps nomme les actions interdites. Les noms de personnes et d'équipes restent
l'affaire du hook pre-commit. Aucun accès extérieur.

    python3 -m unittest discover -s tests/workflow_commands -v
"""
import re
import unittest
from pathlib import Path

COMMANDES = Path(__file__).resolve().parents[2] / ".claude" / "commands"
NOMS = ("implement", "close", "add-books", "next", "start", "batch", "doctor")
# Contrôles d'en-tête : /audit s'y ajoute (son corps a ses propres règles, vérifiées plus bas).
NOMS_EN_TETE = NOMS + ("audit",)

# Éléments qu'un en-tête ne doit jamais pré-approuver (nom de script, option ou variable), et que le corps doit nommer.
INTERDITS_COMMUNS = ("history_jira", "export_jira_api", "flow_import", "flow_compare", "knowledge_import", "db.py", "db_backup", "db_up",
                     "psql", "docker", "finish_branch", "PMZILLA_SKIP_GREEN_CHECK", "--source")
INTERDITS_LIVRES = ("convert_books", "sort_by_domain", "pmzilla_lab_library")
INTERDITS_EN_TETE_SEULEMENT = ("git push", "git merge", "--no-verify", "posture_evals")
# Lanceurs trop larges : pré-approuver « uv run » ou « bash » sans plus lance n'importe quel script.
LANCEURS_LARGES = re.compile(r"Bash\(\s*(uv run|uv|bash|sh|zsh|python3?|env)?\s*(:\*)?\s*\*?\)")
BASH_NU = re.compile(r"(^|[\s,])Bash(?![\w(])")

# Le corps doit nommer les actions interdites ; chaque commande en nomme au moins ces éléments.
CORPS_COMMUNS = ("history_jira", "export_jira_api", "flow_import", "flow_compare", "psql", "finish_branch",
                 "PMZILLA_SKIP_GREEN_CHECK")
CORPS_PAR_COMMANDE = {
    "implement": ("--no-verify", "db.py", "--source db", "Push, merge"),
    "close": ("--no-verify", "db.py", "--source db", "Archive with an unticked task"),
    "add-books": ("convert_books", "sort_by_domain", "pmzilla_lab_library", "db.py", "--source db"),
    "next": ("db.py", "--source db"),
    "start": ("--no-verify", "db.py", "--source db", "Push, merge", "implement.md"),
    "doctor": ("--record", "doctor.sh", "launchctl", "security", "docker", "db.py", "--source db"),
    "batch": ("--no-verify", "db.py", "--source db", "Merge, or push", "finish_worktree"),
}


def lire(nom: str) -> tuple[str, str]:
    """(en-tête, corps) du fichier de commande."""
    texte = (COMMANDES / f"{nom}.md").read_text(encoding="utf-8")
    morceaux = texte.split("---\n", 2)
    assert len(morceaux) == 3 and morceaux[0] == "", f"{nom}.md : en-tête YAML absent"
    return morceaux[1], morceaux[2]


def pre_approbations(en_tete: str) -> str:
    """La valeur de la ligne allowed-tools (tout le reste de l'en-tête n'approuve rien)."""
    for ligne in en_tete.splitlines():
        if ligne.startswith("allowed-tools:"):
            return ligne[len("allowed-tools:"):].strip()
    return ""


class Commandes(unittest.TestCase):
    def test_les_fichiers_existent_avec_un_en_tete(self):
        for nom in NOMS:
            with self.subTest(commande=nom):
                self.assertTrue((COMMANDES / f"{nom}.md").is_file(), f"{nom}.md absent")
                en_tete, corps = lire(nom)
                self.assertIn("description:", en_tete)
                self.assertTrue(corps.strip(), f"{nom}.md : corps vide")

    def test_aucun_en_tete_ne_pre_approuve_un_lancement_interdit(self):
        for nom in NOMS_EN_TETE:
            approuve = pre_approbations(lire(nom)[0])
            interdits = INTERDITS_COMMUNS + INTERDITS_LIVRES + INTERDITS_EN_TETE_SEULEMENT
            for motif in interdits:
                with self.subTest(commande=nom, motif=motif):
                    self.assertNotIn(motif, approuve, f"{nom}.md pré-approuve « {motif} »")

    def test_aucun_en_tete_ne_pre_approuve_un_lanceur_trop_large(self):
        for nom in NOMS_EN_TETE:
            approuve = pre_approbations(lire(nom)[0])
            with self.subTest(commande=nom):
                large = LANCEURS_LARGES.search(approuve)
                self.assertIsNone(large, f"{nom}.md : lanceur trop large {large and large.group(0)}")
                self.assertIsNone(BASH_NU.search(approuve), f"{nom}.md : Bash sans restriction")

    def test_le_corps_nomme_les_actions_interdites(self):
        for nom in NOMS:
            corps = lire(nom)[1]
            for motif in CORPS_COMMUNS + CORPS_PAR_COMMANDE[nom]:
                with self.subTest(commande=nom, motif=motif):
                    self.assertIn(motif, corps, f"{nom}.md ne nomme pas « {motif} »")

    def test_chaque_commande_est_ecrite_en_anglais_et_sert_la_langue_de_l_utilisateur(self):
        for nom in NOMS:
            with self.subTest(commande=nom):
                self.assertIn("THEIR language", lire(nom)[1])

    def test_next_ne_pre_approuve_que_la_sous_commande_next_du_lecteur(self):
        approuve = pre_approbations(lire("next")[0])
        self.assertEqual(approuve, "Bash(uv run --with pyyaml python tools/roadmap.py next:*)")

    def test_doctor_ne_pre_approuve_que_le_lancement_du_doctor_sans_record(self):
        approuve = pre_approbations(lire("doctor")[0])
        self.assertEqual(approuve, "Bash(uv run tools/doctor.py:*)")
        for motif in ("--record", "doctor.sh", "launchctl", "security"):
            with self.subTest(motif=motif):
                self.assertNotIn(motif, approuve)

    def test_close_et_implement_ne_pre_approuvent_pas_done(self):
        for nom in ("implement", "close", "start"):
            self.assertNotIn("roadmap.py done", pre_approbations(lire(nom)[0]), nom)

    def test_aucun_en_tete_ne_pre_approuve_l_outil_d_ecriture_ni_gh(self):
        """R-62 (D17) : chaque écriture sur GitHub passe par l'invite de permission de l'utilisateur."""
        for nom in NOMS_EN_TETE:
            approuve = pre_approbations(lire(nom)[0])
            for motif in ("gh_issue", r"(^|[\s(/])gh\s", "roadmap_import", r"roadmap\.py done", r"roadmap\.py archive"):
                with self.subTest(commande=nom, motif=motif):
                    self.assertIsNone(re.search(motif, approuve), f"{nom}.md pré-approuve « {motif} »")

    def test_implement_ne_mentionne_ni_le_document_ni_done(self):
        en_tete, corps = lire("implement")
        for motif in ("feuille-de-route", "roadmap.py", "`done`", "queue document"):
            with self.subTest(motif=motif):
                self.assertNotIn(motif, en_tete + corps)

    def test_aucune_commande_ne_lit_plus_le_document_de_la_file(self):
        for nom in ("start", "close", "next", "implement"):
            with self.subTest(commande=nom):
                texte = "".join(lire(nom))
                self.assertNotIn("feuille-de-route", texte)
                self.assertNotIn("roadmap.py archive", texte)
                self.assertNotIn("roadmap.py done", texte)

    def test_start_verifie_le_travail_avant_de_le_lancer(self):
        """R-62 (D17) : un travail est lancé seulement s'il est Ready, sans bloqueur ouvert, sa date de début atteinte, ses
        conditions confirmées ; jamais sur main ; l'état passe par l'outil d'écriture, la fin par close-feature."""
        corps = lire("start")[1]
        for motif in ("`Ready`", "blocker", "not_before", "conditions", "main", "roadmap.py check", "roadmap.py show",
                      "gh_issue.py status", "gh_issue.py sync-tasks", "gh_issue.py close-feature", "In progress",
                      "bash tools/finish_branch.sh", "`change`", "spec-writer"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

    def test_start_ne_pre_approuve_que_les_lectures_du_lecteur(self):
        approuve = pre_approbations(lire("start")[0])
        for motif in ("roadmap.py check", "roadmap.py show"):
            self.assertIn(motif, approuve)

    def test_close_nomme_la_synchronisation_et_la_cloture_de_la_feature(self):
        corps = lire("close")[1]
        for motif in ("gh_issue.py sync-tasks", "gh_issue.py close-feature", "In progress", "never invent"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

    def test_spec_writer_ecrit_les_balises_de_groupe(self):
        texte = (COMMANDES.parent / "agents" / "spec-writer.md").read_text(encoding="utf-8")
        for motif in ("[model: opus]", "[model: sonnet]", "[model: haiku]", "[user]", "[parallel]"):
            with self.subTest(motif=motif):
                self.assertIn(motif, texte)

    def test_start_ne_fixe_pas_le_modele(self):
        """Le modèle vient du travail : l'en-tête n'en impose pas, le corps demande de changer de modèle s'il diffère."""
        en_tete, corps = lire("start")
        self.assertNotIn("model:", en_tete)
        self.assertIn("/model", corps)

    def test_audit_compare_les_noms_de_livres_apres_normalisation_unicode(self):
        """Audit du 2026-10-10 (constat 3) : sans NFC, le contrôle des livres rapporte de faux « sans entrée »."""
        self.assertIn("NFC", lire("audit")[1])

    def test_audit_n_ecrit_que_dans_le_dossier_d_audit(self):
        """Audit : les seules écritures pré-approuvées visent .pmzilla/audit/ ; ni Edit, ni NotebookEdit, ni Write sans motif."""
        approuve = pre_approbations(lire("audit")[0])
        ecritures = re.findall(r"Write\(([^)]*)\)", approuve)
        self.assertTrue(ecritures, "audit.md ne pré-approuve aucune écriture")
        for cible in ecritures:
            with self.subTest(cible=cible):
                self.assertTrue(cible.startswith(".pmzilla/audit/"), f"écriture hors du dossier d'audit : {cible}")
                self.assertNotIn("..", cible)
        self.assertIsNone(re.search(r"(^|[\s,])Write(?![\w(])", approuve), "Write sans restriction")
        for outil in ("Edit", "NotebookEdit", "MultiEdit"):
            with self.subTest(outil=outil):
                self.assertIsNone(re.search(rf"(^|[\s,]){outil}\b", approuve), f"audit.md pré-approuve {outil}")

    def test_audit_ne_pre_approuve_ni_commit_ni_suite_de_tests_ni_evaluation(self):
        approuve = pre_approbations(lire("audit")[0])
        for motif in ("git commit", "git add", "git push", "git reset", "git checkout", "git rm", "rm ", "mv ", "unittest", "run_all",
                      "pytest", "posture_evals", "dbtest", "library_parity"):
            with self.subTest(motif=motif):
                self.assertNotIn(motif, approuve)

    def test_audit_dit_lecture_seule_et_nomme_ses_interdits(self):
        corps = lire("audit")[1]
        for motif in ("Read only", "make no commit", "psql", "docker exec", "no Jira tool", "no test suite", "posture evaluation set"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

    def test_audit_lit_l_etat_du_dossier_d_execution_sans_le_modifier(self):
        """R-43 : l'état pour la nuit lit `run_worktree.sh status` ; l'en-tête ne pré-approuve que status, ni create ni update."""
        en_tete, corps = lire("audit")
        approuve = pre_approbations(en_tete)
        self.assertIn("Bash(bash tools/run_worktree.sh status:*)", approuve)
        for sous_commande in ("create", "update"):
            with self.subTest(sous_commande=sous_commande):
                self.assertNotIn(f"run_worktree.sh {sous_commande}", approuve)
        self.assertIn("run_worktree.sh status", corps)
        self.assertIn("run_worktree.sh update", corps)  # l'action du constat, pour l'utilisateur
        self.assertNotIn("7:10 watch differ", corps)

    def test_add_books_ne_pre_approuve_aucun_commit(self):
        approuve = pre_approbations(lire("add-books")[0])
        for motif in ("git commit", "git add", "git push", "git"):
            with self.subTest(motif=motif):
                self.assertNotIn(motif, approuve)

    def test_add_books_dit_de_ne_pas_commiter(self):
        corps = lire("add-books")[1]
        self.assertRegex(corps, r"Do not commit")

    # R-65 (D14, D15) : release en cours, code 8, close-step avec raison, commit sans préfixe.

    def test_start_rapporte_la_ligne_de_release_et_n_edite_pas_le_reglage(self):
        corps = lire("start")[1]
        for motif in ("moved R-", "no current release; milestone unchanged", "is not an open milestone",
                      "tools/roadmap_settings.yaml"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)
        self.assertRegex(corps, r"(?i)never move a milestone")

    def test_start_et_close_nomment_le_code_8_et_l_arret_avant_toute_ecriture(self):
        for nom in ("start", "close"):
            corps = lire(nom)[1]
            for motif in ("exit code 8", "check command", "no further GitHub write", "not sent"):
                with self.subTest(commande=nom, motif=motif):
                    self.assertIn(motif, corps)

    def test_close_propose_close_step_avec_raison_apres_le_oui_de_l_utilisateur(self):
        corps = lire("close")[1]
        for motif in ("close-step", "--reason", "user's yes"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)
        self.assertRegex(corps, r"(?i)every unticked task[^.]*reason")

    def test_close_feature_commente_la_branche(self):
        self.assertIn("naming the branch", lire("start")[1])

    # edition-publish-tooling (D19) : /close et /start vérifient le manifeste et proposent l'étiquette de l'édition publique.

    def test_close_et_start_verifient_le_manifeste_et_proposent_l_etiquette_publique(self):
        for nom in ("close", "start"):
            corps = lire(nom)[1]
            for motif in ("edition/manifest.yaml", "edition:public", "--edition-public", "merge base", "user's yes"):
                with self.subTest(commande=nom, motif=motif):
                    self.assertIn(motif, corps)

    def test_close_et_start_passent_l_option_publique_seulement_apres_le_oui(self):
        for nom in ("close", "start"):
            corps = lire(nom)[1]
            with self.subTest(commande=nom):
                self.assertRegex(corps, r"(?is)--edition-public.{0,400}user's yes|user's yes.{0,400}--edition-public")
                self.assertRegex(corps, r"(?i)no path of the edition")

    # R-61 (batch-milestone, D4, D5) : /start reprend une feature lancée par /batch.

    def test_start_nomme_la_regle_de_reprise_d_une_feature_du_batch(self):
        corps = lire("start")[1]
        for motif in ("In progress", "resume", "chore/spec-r", "chore/r", "feat/<change>",
                      "does not set the Status again", "tools/finish_worktree.sh"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)
        self.assertRegex(corps, r"(?i)never run it")

    # R-61 (batch-milestone, D9, D11, D12) : /batch est une commande contrôlée.

    EN_TETE_BATCH = ("Bash(uv run --with pyyaml python tools/roadmap.py check:*), "
                     "Bash(uv run --with pyyaml python tools/roadmap.py batch:*), Bash(bash tools/worktree.sh:*), "
                     "Bash(git status:*), Bash(git rev-parse:*)")

    def test_batch_fichier_en_tete_et_langue(self):
        en_tete, corps = lire("batch")
        self.assertIn("description:", en_tete)
        self.assertTrue(corps.strip())
        self.assertIn("THEIR language", corps)
        self.assertNotIn("model:", en_tete)

    def test_batch_en_tete_egal_a_l_ensemble_de_d11(self):
        self.assertEqual(pre_approbations(lire("batch")[0]), self.EN_TETE_BATCH)

    def test_batch_en_tete_sans_lancement_interdit_ni_lanceur_large_ni_ecriture(self):
        approuve = pre_approbations(lire("batch")[0])
        interdits = INTERDITS_COMMUNS + INTERDITS_LIVRES + INTERDITS_EN_TETE_SEULEMENT + ("finish_worktree",)
        for motif in interdits:
            with self.subTest(motif=motif):
                self.assertNotIn(motif, approuve)
        self.assertIsNone(LANCEURS_LARGES.search(approuve))
        self.assertIsNone(BASH_NU.search(approuve))
        for motif in ("gh_issue", r"(^|[\s(/])gh\s", "roadmap_import", r"roadmap\.py done", r"roadmap\.py archive"):
            with self.subTest(motif=motif):
                self.assertIsNone(re.search(motif, approuve))

    def test_aucun_en_tete_ne_pre_approuve_le_script_de_fin_de_worktree(self):
        for nom in NOMS_EN_TETE:
            with self.subTest(commande=nom):
                self.assertNotIn("finish_worktree", pre_approbations(lire(nom)[0]))

    def test_batch_corps_nomme_les_actions_interdites(self):
        corps = lire("batch")[1]
        for motif in CORPS_COMMUNS + ("--no-verify", "db.py", "--source db", "finish_worktree", "claude", "gh_issue.py", "gh",
                                      "tools/roadmap_settings.yaml", "Terminal", "worktree", "branch"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

    def test_batch_corps_nomme_la_sequence_et_les_arrets(self):
        corps = lire("batch")[1]
        for motif in ("roadmap.py check", "roadmap.py batch", "tools/worktree.sh", "gh_issue.py status", "In progress", "main",
                      "exit code 8", "check command", "no further GitHub write", "not sent",
                      "git rev-parse --abbrev-ref HEAD", "conditions"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

    def test_batch_bloc_de_lancement_donne_la_commande_de_fin(self):
        corps = lire("batch")[1]
        self.assertIn("bash tools/finish_worktree.sh <branch>", corps)
        self.assertIn('cd <folder> && claude --model <alias> "<prompt>"', corps)
        self.assertRegex(corps, r"(?i)never run")

    def test_batch_nomme_chaque_action_de_d9(self):
        corps = lire("batch")[1]
        for motif in ("Launch a session", "Open a Terminal", "Merge", "push", "tools/finish_branch.sh", "tools/finish_worktree.sh",
                      "Remove a worktree", "other than through `tools/gh_issue.py`", "Status other than `In progress`",
                      "`Ready`", "rank", "estimate", "model", "dependency", "condition", "milestone",
                      "tools/roadmap_settings.yaml", "did not retain", "--no-verify", "PMZILLA_SKIP_GREEN_CHECK"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

    def test_aucune_affectation_avant_git_commit_dans_batch(self):
        prefixe = re.compile(r"\b[A-Z][A-Z0-9_]*=\S*\s+git\s+commit\b")
        self.assertIsNone(prefixe.search((COMMANDES / "batch.md").read_text(encoding="utf-8")))

    def test_aucun_fichier_ne_met_une_affectation_avant_git_commit(self):
        """D15 : `NAME=value git commit` est refusé par le classificateur de permissions."""
        prefixe = re.compile(r"\b[A-Z][A-Z0-9_]*=\S*\s+git\s+commit\b")
        racine = COMMANDES.parents[1]
        fichiers = [COMMANDES / f"{n}.md" for n in NOMS_EN_TETE] + [racine / "CLAUDE.md"]
        for f in fichiers:
            with self.subTest(fichier=f.name):
                self.assertIsNone(prefixe.search(f.read_text(encoding="utf-8")), f"{f.name} : affectation avant git commit")
        self.assertIsNotNone(prefixe.search("PMZILLA_NO_EVALS=1 git commit -m x"))

    def test_les_commandes_de_commit_disent_git_commit_seul_sans_le_mode_apres_commit(self):
        for nom in ("start", "close", "implement"):
            corps = lire(nom)[1]
            with self.subTest(commande=nom):
                self.assertNotIn("PMZILLA_NO_EVALS", corps)
                self.assertIn("`git commit`", corps)
                self.assertIn("PMZILLA_AFTER_COMMIT", corps)
                self.assertRegex(corps, r"(?i)never set `PMZILLA_AFTER_COMMIT`")
                self.assertIn("session's environment", corps)

    def test_la_detection_attrape_une_pre_approbation_interdite(self):
        """Garde du test lui-même : un en-tête fautif serait refusé."""
        faute = "Bash(uv run tools/knowledge_import.py import:*), Bash(bash tools/finish_branch.sh:*), Bash(uv run:*)"
        self.assertTrue(any(m in faute for m in INTERDITS_COMMUNS))
        self.assertIsNotNone(LANCEURS_LARGES.search(faute))
        self.assertIsNotNone(BASH_NU.search("Read, Bash, Edit"))


if __name__ == "__main__":
    unittest.main()
