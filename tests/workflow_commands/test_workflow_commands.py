"""Commandes de travail (.claude/commands/{implement,close,add-books,next,start}.md) : le fichier existe, son en-tête ne pré-approuve
aucun lancement interdit (design.md D5), son corps nomme les actions interdites. Les noms de personnes et d'équipes restent
l'affaire du hook pre-commit. Aucun accès extérieur.

    python3 -m unittest discover -s tests/workflow_commands -v
"""
import re
import unittest
from pathlib import Path

COMMANDES = Path(__file__).resolve().parents[2] / ".claude" / "commands"
NOMS = ("implement", "close", "add-books", "next", "start")
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
CORPS_COMMUNS = ("history_jira", "export_jira_api", "flow_import", "flow_compare", "knowledge_import", "psql", "finish_branch",
                 "PMZILLA_SKIP_GREEN_CHECK")
CORPS_PAR_COMMANDE = {
    "implement": ("--no-verify", "db.py", "--source db", "Push, merge"),
    "close": ("--no-verify", "db.py", "--source db", "Archive with an unticked task"),
    "add-books": ("convert_books", "sort_by_domain", "pmzilla_lab_library", "db.py", "--source db"),
    "next": ("db.py", "--source db"),
    "start": ("--no-verify", "db.py", "--source db", "Push, merge", "implement.md"),
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

    def test_close_et_implement_ne_pre_approuvent_pas_done(self):
        for nom in ("implement", "close", "start"):
            self.assertNotIn("roadmap.py done", pre_approbations(lire(nom)[0]), nom)

    def test_start_verifie_le_travail_avant_de_le_lancer(self):
        """R-18 : un travail est lancé seulement s'il est prêt, ses dépendances faites, sa date de début atteinte, ses conditions
        confirmées ; jamais sur main ; le travail est marqué fait sur la branche avant de donner la commande de fin de branche."""
        corps = lire("start")[1]
        for motif in ("`ready`", "`done`", "not_before", "conditions", "main", "roadmap.py done", "roadmap.py check",
                      "bash tools/finish_branch.sh", "`change`", "spec-writer"):
            with self.subTest(motif=motif):
                self.assertIn(motif, corps)

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

    def test_add_books_ne_pre_approuve_aucun_commit(self):
        approuve = pre_approbations(lire("add-books")[0])
        for motif in ("git commit", "git add", "git push", "git"):
            with self.subTest(motif=motif):
                self.assertNotIn(motif, approuve)

    def test_add_books_dit_de_ne_pas_commiter(self):
        corps = lire("add-books")[1]
        self.assertRegex(corps, r"Do not commit")

    def test_la_detection_attrape_une_pre_approbation_interdite(self):
        """Garde du test lui-même : un en-tête fautif serait refusé."""
        faute = "Bash(uv run tools/knowledge_import.py import:*), Bash(bash tools/finish_branch.sh:*), Bash(uv run:*)"
        self.assertTrue(any(m in faute for m in INTERDITS_COMMUNS))
        self.assertIsNotNone(LANCEURS_LARGES.search(faute))
        self.assertIsNotNone(BASH_NU.search("Read, Bash, Edit"))


if __name__ == "__main__":
    unittest.main()
