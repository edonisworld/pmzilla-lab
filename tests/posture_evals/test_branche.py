"""
Jeu d'essai sur le sommet d'une branche et empreinte des fichiers évalués (change posture-evals-on-branch-tip, groupes 3 et 4) :
option --branch, empreinte `v1:` du run, liste partagée tests/postures/fichiers-evalues.txt.

    bash tests/run_all.sh posture_evals

Un dépôt Git temporaire réel (branche, worktree, modifications en cours), une fausse séance (`run_session` remplacé) : aucun
appel au modèle, aucun coût, aucune base. Le jeu d'essai réel n'est jamais lancé.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import posture_evals as essai  # noqa: E402
import posture_eval_fingerprint as empreinte  # noqa: E402

RACINE_DEPOT = Path(__file__).resolve().parents[2]
LISTE = Path("tests/postures/fichiers-evalues.txt")
VOCABULAIRE = (RACINE_DEPOT / "tests/postures/vocabulaire.yaml").read_text(encoding="utf-8")
PREPARE_MEMOIRE_REEL = essai.prepare_memory      # l'original, avant que Depot ne le remplace
CAS = [{"id": "c1", "question": "Question un ?", "posture": "Delivery"}]
SEANCE = [
    {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [{"type": "text", "text": "[Posture : Delivery] réponse"}]}},
    {"type": "result", "result": "[Posture : Delivery] réponse", "total_cost_usd": 0.0, "num_turns": 1, "is_error": False,
     "permission_denials": []},
]


def git(cwd: Path, *args: str) -> str:
    sortie = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if sortie.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} : {sortie.stderr}")
    return sortie.stdout.strip()


def ecrire(racine: Path, chemin: str, texte: str) -> None:
    (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
    (racine / chemin).write_text(texte, encoding="utf-8")


class Depot(unittest.TestCase):
    """Un dépôt temporaire : main porte la liste et les cinq familles ; feat/x en diffère ; le workspace est sur main, modifié."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = self.tmp / "workspace"
        self.ws.mkdir()
        env = {"GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"), "GIT_CONFIG_SYSTEM": "/dev/null"}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        git(self.ws, "init", "-q", "-b", "main")
        git(self.ws, "config", "user.email", "t@example.org")
        git(self.ws, "config", "user.name", "test")
        ecrire(self.ws, "CLAUDE.md", "instructions main")
        ecrire(self.ws, ".claude/skills/pmzilla-x/SKILL.md", "posture main")
        ecrire(self.ws, ".claude/agents/pmzilla-critic.md", "critic")
        ecrire(self.ws, "tests/postures/vocabulaire.yaml", VOCABULAIRE)
        ecrire(self.ws, "tests/postures/memoire/m.md", "m")
        ecrire(self.ws, "autre.txt", "autre")
        shutil.copy2(RACINE_DEPOT / LISTE, self.ws / LISTE) if (RACINE_DEPOT / LISTE).exists() else None
        git(self.ws, "add", "-A")
        git(self.ws, "commit", "-q", "-m", "initial")
        git(self.ws, "checkout", "-q", "-b", "feat/x")
        ecrire(self.ws, "CLAUDE.md", "instructions du sommet")
        git(self.ws, "commit", "-q", "-am", "sommet")
        self.tip = git(self.ws, "rev-parse", "HEAD")
        git(self.ws, "checkout", "-q", "main")
        ecrire(self.ws, "CLAUDE.md", "instructions en cours, non commitées")   # état du workspace, différent du sommet
        ecrire(self.ws, "non-suivi.txt", "jamais copié avec --branch")
        self.copies: list[dict] = []
        self.cas_file = self.tmp / "cas.yaml"
        self.cas_file.write_text(yaml.safe_dump(CAS, allow_unicode=True), encoding="utf-8")

        def fausse_seance(question, copie, mcp, model, trace, *a, **k):
            self.copies.append({"claude": (copie / "CLAUDE.md").read_text(encoding="utf-8"),
                                "non_suivi": (copie / "non-suivi.txt").exists(),
                                "memoire": (copie / "tests/postures/memoire/m.md").exists()})
            return SEANCE

        for patch in (mock.patch.object(essai, "WORKSPACE", self.ws),
                      mock.patch.object(essai, "DATA", self.tmp / "essais"),
                      mock.patch.object(essai, "REPORT_DIR", self.tmp / "rapports"),
                      mock.patch.object(essai, "CASES_FILE", self.cas_file),
                      mock.patch.object(essai, "create_cases_database", lambda: None),
                      mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}),
                      mock.patch.object(essai, "run_session", fausse_seance)):
            patch.start()
            self.addCleanup(patch.stop)

    def lancer(self, *arguments):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", "--retries", "0", *arguments]), \
             contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            essai.main()
        return sortie.getvalue(), erreur.getvalue()

    def refus(self, *arguments):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", "--retries", "0", *arguments]), \
             contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as arret:
            essai.main()
        return arret.exception.code, sortie.getvalue() + erreur.getvalue()

    def dernier_resultat(self) -> dict:
        return json.loads(max((self.tmp / "essais").glob("*/resultats.json")).read_text(encoding="utf-8"))

    def aucune_copie_ni_passage(self):
        self.assertEqual(self.copies, [])
        self.assertEqual(list((self.tmp / "essais").glob("*/resultats.json")), [])
        self.assertNotIn("copie-", git(self.ws, "worktree", "list"))


class ListePartagee(unittest.TestCase):
    def test_la_liste_couvre_les_cinq_familles(self):
        chemin = RACINE_DEPOT / LISTE
        self.assertTrue(chemin.is_file(), "tests/postures/fichiers-evalues.txt est absent")
        entrees = [ligne.strip() for ligne in chemin.read_text(encoding="utf-8").splitlines()
                   if ligne.strip() and not ligne.lstrip().startswith("#")]
        for attendu in ("CLAUDE.md", ".claude/skills/pmzilla-*", ".claude/agents/pmzilla-critic.md",
                        "tests/postures/vocabulaire.yaml", "tests/postures/memoire"):
            self.assertIn(attendu, entrees)

    def test_l_en_tete_dit_la_semantique_des_chemins(self):
        premieres = [ligne for ligne in (RACINE_DEPOT / LISTE).read_text(encoding="utf-8").splitlines() if ligne.startswith("#")]
        self.assertTrue(any("racine du dépôt" in ligne for ligne in premieres))

    def test_chaque_entree_de_la_fin_est_surveillee_par_le_post_commit(self):
        """Inclusion (décision du 2026-10-21, point 5) : la liste de la fin fait foi pour le jeu payant, le post-commit
        surveille plus large ; chaque fichier suivi que vise une entrée doit aussi déclencher le post-commit."""
        motif = motif_du_post_commit()
        self.assertEqual(entrees_non_surveillees(entrees_de_la_liste(), motif), [])

    def test_une_entree_non_surveillee_est_signalee(self):
        motif = motif_du_post_commit()
        self.assertEqual(entrees_non_surveillees(["docs/pmzilla/installation.md", "CLAUDE.md"], motif),
                         ["docs/pmzilla/installation.md"])

    def test_une_entree_qui_ne_vise_aucun_fichier_suivi_est_signalee(self):
        self.assertEqual(entrees_non_surveillees(["tests/postures/absent-*.yaml"], motif_du_post_commit()),
                         ["tests/postures/absent-*.yaml"])


def entrees_de_la_liste() -> list[str]:
    return [ligne.strip() for ligne in (RACINE_DEPOT / LISTE).read_text(encoding="utf-8").splitlines()
            if ligne.strip() and not ligne.lstrip().startswith("#")]


def motif_du_post_commit() -> "re.Pattern[str]":
    """Le motif `grep -E '…'` de la ligne WATCHED= du crochet, lu sans le lancer."""
    texte = (RACINE_DEPOT / "tools/hooks/post-commit").read_text(encoding="utf-8")
    trouve = re.search(r"^WATCHED=.*grep -E '([^']+)'", texte, re.MULTILINE)
    if not trouve:
        raise AssertionError("ligne WATCHED= introuvable dans tools/hooks/post-commit")
    return re.compile(trouve.group(1))


def entrees_non_surveillees(entrees: list[str], motif: "re.Pattern[str]") -> list[str]:
    """Les entrées dont un fichier suivi (git ls-files, même lecture de la spécification de chemin) échappe au motif,
    ou qui ne visent aucun fichier suivi (inclusion invérifiable)."""
    env = {k: v for k, v in os.environ.items() if k != "GIT_LITERAL_PATHSPECS"}   # comme l'empreinte : « * » reste un motif
    manquantes = []
    for entree in entrees:
        fichiers = subprocess.run(["git", "ls-files", "--", entree], cwd=RACINE_DEPOT, env=env,
                                  capture_output=True, text=True, check=True).stdout.splitlines()
        if not fichiers or any(not motif.search(f) for f in fichiers):
            manquantes.append(entree)
    return manquantes


class Branche(Depot):
    def test_copie_faite_du_sommet_et_non_de_l_etat_du_workspace(self):
        git(self.ws, "worktree", "add", "-q", str(self.tmp / "wt"), "feat/x")   # branche reprise dans un autre worktree
        sortie, _ = self.lancer("--branch", "feat/x")
        self.assertEqual(self.copies, [{"claude": "instructions du sommet", "non_suivi": False, "memoire": True}])
        court = git(self.ws, "rev-parse", "--short", self.tip)
        ligne = f"état testé : sommet de feat/x ({court})"
        self.assertIn(ligne, sortie)
        self.assertLess(sortie.index(ligne), sortie.index("[1/1]"))
        self.assertEqual(self.dernier_resultat()["base"], self.tip)
        rapport = next((self.tmp / "rapports").glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertIn(ligne, rapport)

    def test_sommet_sans_worktree_ni_extraction(self):
        self.lancer("--branch", "feat/x")      # feat/x n'est extraite nulle part
        self.assertEqual(self.copies[0]["claude"], "instructions du sommet")

    def test_sans_l_option_l_etat_du_workspace_est_copie(self):
        self.lancer()
        self.assertEqual(self.copies[0]["claude"], "instructions en cours, non commitées")
        self.assertTrue(self.copies[0]["non_suivi"])

    def test_branche_inconnue(self):
        code, texte = self.refus("--branch", "feat/absente")
        self.assertEqual(code, 2)
        self.assertIn("branche inconnue : feat/absente", texte)
        self.aucune_copie_ni_passage()

    def test_option_combinee_avec_l_etat_commite(self):
        code, texte = self.refus("--branch", "feat/x", "--committed-state")
        self.assertEqual(code, 2)
        self.assertIn("--branch ne se combine pas avec --committed-state", texte)
        self.aucune_copie_ni_passage()

    def test_worktree_de_la_branche_avec_un_fichier_evalue_modifie(self):
        wt = self.tmp / "wt"
        git(self.ws, "worktree", "add", "-q", str(wt), "feat/x")
        ecrire(wt, ".claude/skills/pmzilla-x/SKILL.md", "brouillon non commité")
        code, texte = self.refus("--branch", "feat/x")
        self.assertEqual(code, 2)
        self.assertIn("le worktree de feat/x a des modifications non commitées des fichiers évalués : "
                      "commite-les ou retire-les, puis relance", texte)
        self.aucune_copie_ni_passage()

    def test_worktree_de_la_branche_avec_un_fichier_evalue_nouveau_non_suivi(self):
        wt = self.tmp / "wt"
        git(self.ws, "worktree", "add", "-q", str(wt), "feat/x")
        ecrire(wt, ".claude/skills/pmzilla-neuve/SKILL.md", "posture en cours d'écriture")
        code, texte = self.refus("--branch", "feat/x")
        self.assertEqual(code, 2)
        self.assertIn("modifications non commitées des fichiers évalués", texte)

    def test_worktree_de_la_branche_avec_un_fichier_non_evalue_modifie(self):
        wt = self.tmp / "wt"
        git(self.ws, "worktree", "add", "-q", str(wt), "feat/x")
        ecrire(wt, "autre.txt", "modifié")
        self.lancer("--branch", "feat/x")
        self.assertEqual(len(self.copies), 1)

    def test_la_branche_extraite_dans_le_workspace_modifie_est_refusee(self):
        git(self.ws, "stash", "-q", "-u")
        git(self.ws, "checkout", "-q", "feat/x")
        ecrire(self.ws, "CLAUDE.md", "brouillon")
        code, texte = self.refus("--branch", "feat/x")
        self.assertEqual(code, 2)
        self.assertIn("le worktree de feat/x a des modifications non commitées des fichiers évalués", texte)

    def test_ou_le_passage_lit_et_ecrit(self):
        self.lancer("--branch", "feat/x")
        self.assertEqual(len(list((self.tmp / "essais").glob("*/resultats.json"))), 1)   # enregistrement : dossier des données
        self.assertEqual(len(list((self.tmp / "rapports").glob("essai-*.md"))), 1)      # rapport : dossier des rapports du workspace
        self.assertNotIn("copie-", git(self.ws, "worktree", "list"))                    # copies effacées


class Empreinte(Depot):
    def test_empreinte_ecrite_dans_l_enregistrement(self):
        self.lancer("--branch", "feat/x")
        enregistre = self.dernier_resultat()["evaluated_fingerprint"]
        self.assertTrue(enregistre.startswith("v1:"))
        paires = [ligne.strip() for ligne in (self.ws / LISTE).read_text(encoding="utf-8").splitlines()
                  if ligne.strip() and not ligne.lstrip().startswith("#")]
        self.assertEqual(enregistre, empreinte.fingerprint(self.ws, self.tip, paires))

    def test_sans_l_option_l_empreinte_est_celle_de_l_arbre_teste(self):
        self.lancer("--committed-state")
        paires = [ligne.strip() for ligne in (self.ws / LISTE).read_text(encoding="utf-8").splitlines()
                  if ligne.strip() and not ligne.lstrip().startswith("#")]
        self.assertEqual(self.dernier_resultat()["evaluated_fingerprint"],
                         empreinte.fingerprint(self.ws, git(self.ws, "rev-parse", "HEAD"), paires))

    def specs(self):
        return ["CLAUDE.md", ".claude/skills/pmzilla-*", ".claude/agents/pmzilla-critic.md",
                "tests/postures/vocabulaire.yaml", "tests/postures/memoire"]

    def test_stable_changee_par_un_fichier_evalue_pas_par_un_autre(self):
        avant = empreinte.fingerprint(self.ws, "main", self.specs())
        self.assertEqual(avant, empreinte.fingerprint(self.ws, "main", self.specs()))
        self.assertRegex(avant, r"^v1:[0-9a-f]{64}$")
        git(self.ws, "stash", "-q", "-u")
        ecrire(self.ws, "autre.txt", "changé")
        git(self.ws, "commit", "-q", "-am", "autre fichier")
        self.assertEqual(avant, empreinte.fingerprint(self.ws, "main", self.specs()))
        ecrire(self.ws, ".claude/skills/pmzilla-x/SKILL.md", "posture changée")
        git(self.ws, "commit", "-q", "-am", "posture")
        self.assertNotEqual(avant, empreinte.fingerprint(self.ws, "main", self.specs()))

    def test_cas_vide_prefixe(self):
        vide = empreinte.fingerprint(self.ws, "main", ["rien/du/tout"])
        self.assertEqual(vide, "v1:" + hashlib.sha256(b"").hexdigest())

    def test_format_des_lignes_et_tri_par_chemin(self):
        arbre = git(self.ws, "rev-parse", "main^{tree}")
        lignes = []
        for chemin in sorted(["CLAUDE.md", ".claude/agents/pmzilla-critic.md"]):
            entete, nom = git(self.ws, "ls-tree", "-r", arbre, "--", chemin).split("\t")
            mode, _, identifiant = entete.split(" ")
            lignes.append(f"{mode} {identifiant} {nom}")
        attendu = "v1:" + hashlib.sha256("\n".join(lignes).encode()).hexdigest()
        self.assertEqual(empreinte.fingerprint(self.ws, "main", ["CLAUDE.md", ".claude/agents/pmzilla-critic.md"]), attendu)

    def test_claude_md_d_un_sous_dossier_n_est_pas_evalue(self):
        avant = empreinte.fingerprint(self.ws, "main", self.specs())
        git(self.ws, "stash", "-q", "-u")
        ecrire(self.ws, "mothra/CLAUDE.md", "instructions d'un sous-dossier")
        git(self.ws, "add", "-A")
        git(self.ws, "commit", "-q", "-m", "sous-dossier")
        self.assertEqual(avant, empreinte.fingerprint(self.ws, "main", self.specs()))

    def test_le_rejugement_garde_l_empreinte_du_passage_rejuge(self):
        passage = self.tmp / "essais" / "2026-10-01-090000"
        passage.mkdir(parents=True)
        (passage / "resultats.json").write_text(json.dumps(
            {"base": "abc", "memoire": "figée", "evaluated_fingerprint": "v1:" + "a" * 64,
             "cas": [{"id": "c1", "verifications": []}]}), encoding="utf-8")
        (passage / "c1.jsonl").write_text("\n".join(json.dumps(e) for e in SEANCE), encoding="utf-8")
        self.lancer("--rejudge", "2026-10-01-090000")
        nouveaux = [p for p in (self.tmp / "essais").glob("*/resultats.json") if p.parent != passage]
        self.assertEqual(json.loads(nouveaux[0].read_text(encoding="utf-8"))["evaluated_fingerprint"], "v1:" + "a" * 64)

    def test_le_rejugement_d_un_ancien_passage_n_invente_pas_d_empreinte(self):
        passage = self.tmp / "essais" / "2026-10-01-090000"
        passage.mkdir(parents=True)
        (passage / "resultats.json").write_text(json.dumps({"base": "abc", "cas": [{"id": "c1", "verifications": []}]}),
                                                encoding="utf-8")
        (passage / "c1.jsonl").write_text("\n".join(json.dumps(e) for e in SEANCE), encoding="utf-8")
        self.lancer("--rejudge", "2026-10-01-090000")
        nouveaux = [p for p in (self.tmp / "essais").glob("*/resultats.json") if p.parent != passage]
        self.assertNotIn("evaluated_fingerprint", json.loads(nouveaux[0].read_text(encoding="utf-8")))


class VocabulaireEtMemoireDuSommet(Depot):
    """feat/x change le vocabulaire (balise « [Cap : … » au lieu de « [Posture : … ») et la mémoire figée ; le vrai
    prepare_memory tourne. Avec --branch, les contrôles lisent le vocabulaire de la copie, la copie porte la mémoire du sommet."""

    def setUp(self):
        super().setUp()
        wt = self.tmp / "wt-sommet"
        git(self.ws, "worktree", "add", "-q", str(wt), "feat/x")
        vocabulaire = VOCABULAIRE.replace("\\s*Posture[", "\\s*Cap[").replace('posture_tag: "[Posture : {posture}]"',
                                                                             'posture_tag: "[Cap : {posture}]"')
        self.assertNotEqual(vocabulaire, VOCABULAIRE)
        ecrire(wt, "tests/postures/vocabulaire.yaml", vocabulaire)
        ecrire(wt, "tests/postures/memoire/delivery/MEMORY.md", "mémoire figée du sommet")
        ecrire(wt, "_bmad/memory/pmzilla-delivery-bmad/MEMORY.md", "vécu")
        git(wt, "add", "-A")
        git(wt, "commit", "-q", "-m", "vocabulaire et mémoire du sommet")
        self.tip = git(wt, "rev-parse", "HEAD")
        git(self.ws, "worktree", "remove", "--force", str(wt))
        ecrire(self.ws, "tests/postures/contexte-neutre.md", "contexte neutre")
        self.memoires: list[str] = []
        texte = "[Cap : Delivery] réponse"
        seance = [
            {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [{"type": "text", "text": texte}]}},
            {"type": "result", "result": texte, "total_cost_usd": 0.0, "num_turns": 1, "is_error": False,
             "permission_denials": []},
        ]

        def seance_cap(question, copie, mcp, model, trace, *a, **k):
            self.memoires.append((copie / "_bmad/memory/pmzilla-delivery-bmad/MEMORY.md").read_text(encoding="utf-8"))
            return seance

        for patch in (mock.patch.object(essai, "prepare_memory", PREPARE_MEMOIRE_REEL),
                      mock.patch.object(essai, "run_session", seance_cap)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_les_controles_lisent_le_vocabulaire_du_sommet_et_la_copie_la_memoire_du_sommet(self):
        self.lancer("--branch", "feat/x")
        self.assertEqual(self.memoires, ["mémoire figée du sommet"])
        verifications = self.dernier_resultat()["cas"][0]["verifications"]
        self.assertTrue(verifications)
        echecs = [v for v in verifications if not v["ok"]]
        self.assertEqual(echecs, [])


class BrancheAvecRejugement(Depot):
    def test_refus_de_branch_avec_rejudge(self):
        code, texte = self.refus("--branch", "feat/x", "--rejudge", "2026-10-01-090000")
        self.assertEqual(code, 2)
        self.assertIn("--branch ne se combine pas avec --rejudge", texte)
        self.aucune_copie_ni_passage()


class ListeAbsenteOuVide(Depot):
    PHRASE = "liste des fichiers évalués absente ou vide"

    def remplace_la_liste(self, contenu=None):
        """La liste est lue dans le dépôt où tourne l'outil (le workspace) : absente si `contenu` est None."""
        if contenu is None:
            (self.ws / LISTE).unlink()
        else:
            ecrire(self.ws, str(LISTE), contenu)

    def test_liste_absente(self):
        self.remplace_la_liste()
        code, texte = self.refus("--branch", "feat/x")
        self.assertEqual(code, 2)
        self.assertIn(self.PHRASE, texte)
        self.aucune_copie_ni_passage()

    def test_liste_vide_ou_de_commentaires_seulement(self):
        self.remplace_la_liste("# rien\n\n")
        code, texte = self.refus("--branch", "feat/x")
        self.assertEqual(code, 2)
        self.assertIn(self.PHRASE, texte)
        self.aucune_copie_ni_passage()

    def test_pas_de_repli_sur_des_chemins_internes(self):
        self.remplace_la_liste()
        code, texte = self.refus("--committed-state")
        self.assertEqual(code, 2)
        self.assertIn(self.PHRASE, texte)
        self.aucune_copie_ni_passage()


if __name__ == "__main__":
    unittest.main()
