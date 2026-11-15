"""
Tests du mode GitHub du lecteur de la file (tools/roadmap.py), sur un faux `gh` (tests/roadmap/fake_gh) : aucun réseau.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import contextlib
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import roadmap  # noqa: E402
import roadmap_model as rm  # noqa: E402

roadmap_git_origin_url_reel = roadmap.git_origin_url

FAUX_GH = Path(__file__).resolve().parent / "fake_gh"


def feature(n, titre="Travail", *, state="OPEN", status="Ready", milestone="Hydra", milestone_state="OPEN", theme="outillage",
            bloc=None, blocked_by=(), labels=None, texte="Description libre.", number=None, parent=None):
    """Noeud d'issue au format GraphQL de la requête du lecteur."""
    b = {"id": f"R-{n}", "theme": theme, "estimate": "1h", "method": "direct-prompt", "model": "sonnet", "conditions": ""}
    if state == "OPEN":
        b["rank"] = n * 10
    b.update(bloc or {})
    etiquettes = labels if labels is not None else [rm.LABEL_FEATURE, rm.label_theme(theme)]
    return {
        "number": number or 100 + n, "title": rm.feature_title(n, titre), "state": state,
        "body": rm.marker(f"R-{n}") + "\n" + rm.render_block(b) + "\n\n" + texte,
        "labels": {"nodes": [{"name": x} for x in etiquettes]},
        "milestone": {"title": milestone, "state": milestone_state} if milestone else None,
        "parent": {"number": parent} if parent else None,
        "blockedBy": {"nodes": [{"number": x} for x in blocked_by]},
        "projectItems": {"nodes": [{"fieldValueByName": {"name": status}, "project": {"title": roadmap.PROJECT_TITLE}}] if status else []},
    }


def sous_issue(n, groupe, parent, *, state="OPEN", labels=None, titre="Groupe", number=None):
    return {
        "number": number or 500 + groupe, "title": rm.group_title(n, groupe, titre), "state": state,
        "body": rm.marker(rm.group_key(n, groupe)) + "\nchange: x, group 1",
        "labels": {"nodes": [{"name": x} for x in (labels if labels is not None else [rm.LABEL_TASK, "model:sonnet"])]},
        "milestone": None, "parent": {"number": parent}, "blockedBy": {"nodes": []}, "projectItems": {"nodes": []},
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.journal = self.dir / "appels.log"
        env = {"PMZILLA_GH": str(FAUX_GH), "FAKE_GH_DATA": str(self.dir / "issues.json"), "FAKE_GH_LOG": str(self.journal),
               "PMZILLA_LAB_DATA": str(self.dir / "data"), "FAKE_GH_MODE": ""}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("ROADMAP_TODAY", None)
        for nom in ("PMZILLA_GH_TIMEOUT", "FAKE_GH_MILESTONES"):
            os.environ.pop(nom, None)
        self.origin = "git@github.com:owner-x/repo-y.git"
        q = mock.patch.object(roadmap, "git_origin_url", lambda: self.origin)
        q.start()
        self.addCleanup(q.stop)
        self.reglages = self.dir / "reglages.yaml"       # absent : aucune release
        q = mock.patch.object(roadmap, "CHEMIN_REGLAGES", self.reglages)
        q.start()
        self.addCleanup(q.stop)
        self.reel = datetime.date(2026, 10, 11)   # date réelle simulée (date du cache)
        q = mock.patch.object(roadmap, "jour_reel", lambda: self.reel)
        q.start()
        self.addCleanup(q.stop)

    def depot(self, *noeuds):
        (self.dir / "issues.json").write_text(json.dumps(list(noeuds)), encoding="utf-8")

    def lance(self, *args):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                code = roadmap.main(list(args))
            except SystemExit as e:
                code = e.code
        return code, sortie.getvalue(), erreur.getvalue()

    def appels(self):
        return [json.loads(l) for l in self.journal.read_text(encoding="utf-8").splitlines()] if self.journal.exists() else []

    def cache(self):
        return self.dir / "data" / "roadmap-cache.json"


class TestCheck(Base):
    def test_file_valide(self):
        self.depot(feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED"),
                   feature(2, blocked_by=[101]), feature(3, status="Todo"))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 0, sortie)

    def test_cle_de_bloc_inconnue(self):
        self.depot(feature(1, bloc={"zzz": 1}))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1", sortie)
        self.assertIn("zzz", sortie)

    def test_valeurs_interdites(self):
        for champ, valeur in (("method", "x"), ("model", "gpt"), ("estimate", "0min"), ("due", "2026-02-30")):
            with self.subTest(champ=champ):
                self.depot(feature(1, bloc={champ: valeur}))
                code, sortie, _ = self.lance("check")
                self.assertEqual(code, 1)
                self.assertIn(f"R-1 : {champ}", sortie)

    def test_theme_different_du_label(self):
        self.depot(feature(1, theme="veille", labels=[rm.LABEL_FEATURE, "theme:base"]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : theme", sortie)

    def test_deux_labels_de_theme(self):
        self.depot(feature(1, labels=[rm.LABEL_FEATURE, "theme:base", "theme:veille"]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : labels", sortie)

    def test_titre_hors_motif_et_marqueur_different(self):
        n = feature(1)
        n["title"] = "Sans identifiant"
        m = feature(2)
        m["body"] = m["body"].replace("roadmap-id: R-2", "roadmap-id: R-9")
        self.depot(n, m)
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("title", sortie)
        self.assertIn("R-2 : marker", sortie)

    def test_feature_ouverte_sans_jalon_est_valide(self):
        # gh-issue-autonomy (D5, R-20261103-22 Q2) : une feature d'un horizon lointain n'a pas de jalon ; le contrôle ne le lui reproche pas
        self.depot(feature(1, milestone=None))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("milestone", sortie)

    def test_show_feature_sans_jalon_dit_aucun(self):
        self.depot(feature(1, milestone=None))
        code, sortie, _ = self.lance("show", "R-1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("jalon : aucun", sortie)
        self.assertNotIn("None", sortie)

    def test_feature_fermee_sans_jalon_reste_signalee(self):
        self.depot(feature(1, state="CLOSED", status="Done", milestone=None, bloc={"done_on": "2026-10-01"}))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : milestone", sortie)

    def test_identifiant_en_double(self):
        self.depot(feature(1, number=101), feature(1, number=102, bloc={"rank": 99}))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : id", sortie)

    def test_rang_en_double(self):
        self.depot(feature(1, bloc={"rank": 5}), feature(2, bloc={"rank": 5}))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : rank", sortie)
        self.assertIn("R-2 : rank", sortie)

    def test_dependance_inconnue(self):
        self.depot(feature(1, blocked_by=[999]), feature(2, blocked_by=[100 + 3]),
                   sous_issue(3, 1, parent=102, number=103))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : blocked_by", sortie)
        self.assertIn("R-2 : blocked_by", sortie)

    def test_bloquee_par_elle_meme(self):
        self.depot(feature(1, blocked_by=[101]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : blocked_by", sortie)

    def test_cycle(self):
        self.depot(feature(1, status="Todo", blocked_by=[102]), feature(2, status="Todo", blocked_by=[101]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        ligne = next(l for l in sortie.splitlines() if "cycle" in l)
        self.assertIn("R-1", ligne)
        self.assertIn("R-2", ligne)

    def test_ready_avec_bloqueur_ouvert(self):
        self.depot(feature(1, status="Todo"), feature(2, blocked_by=[101]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-2 : Status", sortie)

    def test_en_cours_avec_bloqueur_ouvert(self):
        self.depot(feature(1, status="Todo"), feature(2, status="In progress", blocked_by=[101]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-2 : Status", sortie)

    def test_todo_avec_bloqueur_ouvert_est_valide(self):
        self.depot(feature(1), feature(2, status="Todo", blocked_by=[101]))
        self.assertEqual(self.lance("check")[0], 0)

    def test_fermee_avec_bloqueur_ouvert(self):
        self.depot(feature(1), feature(2, state="CLOSED", status="Done", milestone="Hydra", blocked_by=[101]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-2 : state", sortie)

    def test_status_et_ouverture_incoherents(self):
        self.depot(feature(1, state="CLOSED", status="Ready"), feature(2, status="Done"), feature(3, status=None))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        for i in (1, 2, 3):
            self.assertIn(f"R-{i} : Status", sortie)

    def test_feature_ouverte_dans_tarasque(self):
        self.depot(feature(1, milestone="Tarasque"))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : milestone", sortie)

    def test_jalon_ferme_avec_issue_ouverte(self):
        self.depot(feature(1, milestone="Golem", milestone_state="CLOSED"))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : milestone", sortie)

    def test_sous_issues(self):
        self.depot(feature(1),
                   sous_issue(1, 1, 101),                                                   # valide
                   sous_issue(1, 2, 101, labels=[rm.LABEL_TASK, rm.LABEL_USER]),            # valide : étape de l'utilisateur
                   sous_issue(1, 3, 101, labels=[rm.LABEL_TASK, "model:sonnet", rm.LABEL_USER]),   # les deux
                   sous_issue(1, 4, 101, labels=[rm.LABEL_TASK]),                           # aucun
                   sous_issue(1, 5, 101, labels=["model:sonnet"]),                          # sans type:task
                   sous_issue(1, 6, 777))                                                   # parent inconnu
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        lignes = sortie.splitlines()
        for g in (3, 4, 5, 6):
            self.assertTrue(any(f"R-1/g{g} :" in l for l in lignes), g)
        for g in (1, 2):
            self.assertFalse(any(f"R-1/g{g} :" in l for l in lignes), g)

    def test_tache_utilisateur_autonome_cle_u(self):
        """Une tâche R-<n>/u<k> (gh_issue new-task) est une sous-issue valide : type:task + owner:user, parent feature."""
        tache = sous_issue(1, 1, 101, labels=[rm.LABEL_TASK, rm.LABEL_USER], number=601)
        tache["title"] = rm.feature_title(1, "Valider le brouillon")
        tache["body"] = rm.marker(rm.user_task_key(1, 1)) + "\n\nTexte."
        self.depot(feature(1), tache)
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 0, sortie)

    def test_sous_issue_dont_le_parent_n_est_pas_une_feature(self):
        self.depot(feature(1), sous_issue(1, 1, 101, number=601), sous_issue(1, 2, 601, number=602))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1/g2 : parent", sortie)

    def test_ne_fait_aucune_ecriture(self):
        self.depot(feature(1), feature(2, status="Todo"))
        self.lance("check")
        self.assertTrue(self.appels())
        for a in self.appels():
            self.assertEqual(a[:2], ["api", "graphql"])
            self.assertFalse(any("mutation" in x.lower() or x in ("-X", "--method", "POST", "PATCH") for x in a), a)

    def test_pagination(self):
        self.depot(*[feature(i, bloc={"rank": i}) for i in range(1, 8)])
        os.environ["FAKE_GH_PAGE"] = "3"
        self.addCleanup(os.environ.pop, "FAKE_GH_PAGE", None)
        self.assertEqual(self.lance("check")[0], 0)
        self.assertEqual(len(self.appels()), 3)

    def test_erreur_graphql_n_est_pas_hors_ligne(self):
        self.depot(feature(1))
        self.assertEqual(self.lance("check")[0], 0)
        os.environ["FAKE_GH_MODE"] = "graphql_error"
        code, sortie, erreur = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("GitHub refused", erreur)
        self.assertNotIn("cache of", sortie)


class TestSignauxCycle(Base):
    """Signaux de cycle de vie du check (change github-status-lifecycle, design D3 à D5) : lecteurs Git remplacés, jamais d'écriture."""

    SIG_SANS_BRANCHE = "roadmap : signalement : R-1 : Status : In progress sans branche ouverte"

    def git(self, branches=frozenset(), sur_main=frozenset()):
        for nom, valeur in (("branches_locales", branches), ("changes_sur_main", sur_main)):
            q = mock.patch.object(roadmap, nom, (lambda v: (lambda: None if v is None else set(v)))(valeur))
            q.start()
            self.addCleanup(q.stop)

    def check(self, *noeuds):
        self.depot(*noeuds)
        return self.lance("check")

    def test_en_cours_sans_branche_file_valide_et_code_0(self):
        self.git({"main", "feat/autre"})
        code, sortie, _ = self.check(feature(1, status="In progress"))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines(), [self.SIG_SANS_BRANCHE, "roadmap : file valide"])

    def test_ready_change_absent_de_main(self):
        self.git({"main"}, set())
        code, sortie, _ = self.check(feature(2, bloc={"method": "openspec", "change": "mon-change"}))
        self.assertEqual(code, 0, sortie)
        self.assertIn("roadmap : signalement : R-2 : Status : Ready alors que le change mon-change n'est pas sur main", sortie.splitlines())

    def test_ready_openspec_sans_change(self):
        self.git({"main"}, set())
        code, sortie, _ = self.check(feature(2, bloc={"method": "openspec"}))
        self.assertEqual(code, 0, sortie)
        self.assertIn("roadmap : signalement : R-2 : Status : Ready sans change sur main", sortie.splitlines())

    def test_ready_direct_prompt_sans_change_sans_signal(self):
        self.git({"main"}, set())
        code, sortie, _ = self.check(feature(2))
        self.assertEqual((code, sortie), (0, "roadmap : file valide\n"))

    def test_branche_nommee_d_apres_le_change(self):
        self.git({"main", "feat/c"})
        code, sortie, _ = self.check(feature(1, status="In progress", bloc={"method": "openspec", "change": "c"}))
        self.assertEqual((code, sortie), (0, "roadmap : file valide\n"))

    def test_jeton_d_identifiant(self):
        self.git({"main", "chore/r650-x"})
        _, sortie, _ = self.check(feature(65, status="In progress"))
        self.assertIn("roadmap : signalement : R-65 : Status : In progress sans branche ouverte", sortie.splitlines())
        self.git({"main", "chore/r65-fixes"})
        _, sortie, _ = self.check(feature(65, status="In progress"))
        self.assertEqual(sortie, "roadmap : file valide\n")

    def test_change_sur_une_branche_de_spec_seulement(self):
        # le change existe dans l'arbre de travail (cas d'un check lancé sur la branche de spec) mais pas dans l'arbre de main
        (self.dir / "openspec" / "changes" / "c").mkdir(parents=True)
        q = mock.patch.object(roadmap, "ARBRE", self.dir)
        q.start()
        self.addCleanup(q.stop)
        self.git({"main", "spec/c"}, set())
        _, sortie, _ = self.check(feature(2, bloc={"method": "openspec", "change": "c"}))
        self.assertIn("Ready alors que le change c n'est pas sur main", sortie)

    def test_change_archive_sur_main(self):
        self.git({"main"}, {"c"})       # le lecteur range les dossiers d'archive sous leur nom de change (voir TestLecteursGit)
        code, sortie, _ = self.check(feature(2, bloc={"method": "openspec", "change": "c"}))
        self.assertEqual((code, sortie), (0, "roadmap : file valide\n"))

    def test_git_illisible(self):
        self.git(None, None)
        code, sortie, _ = self.check(feature(1, status="In progress"), feature(2, bloc={"method": "openspec"}))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines(), ["roadmap : signalement : branches et main illisibles ; aucun signalement de cycle",
                                               "roadmap : file valide"])

    def test_rien_a_verifier_git_n_est_pas_lu(self):
        def interdit():
            raise AssertionError("Git lu sans feature à vérifier")
        for nom in ("branches_locales", "changes_sur_main"):
            q = mock.patch.object(roadmap, nom, interdit)
            q.start()
            self.addCleanup(q.stop)
        code, sortie, _ = self.check(feature(1), feature(2, status="Todo", bloc={"method": "openspec"}))
        self.assertEqual((code, sortie), (0, "roadmap : file valide\n"))

    def test_un_signal_ne_change_pas_le_code_d_un_probleme(self):
        self.git({"main"})
        code, sortie, _ = self.check(feature(1, status="In progress"), feature(2, bloc={"zzz": 1}))
        self.assertEqual(code, 1)
        lignes = sortie.splitlines()
        self.assertTrue(any("R-2 : zzz" in l for l in lignes), sortie)
        self.assertLess(max(i for i, l in enumerate(lignes) if "R-2 : zzz" in l), lignes.index(self.SIG_SANS_BRANCHE))
        self.assertNotIn("roadmap : file valide", sortie)

    def test_signaux_dans_l_ordre_du_rang(self):
        self.git({"main"})
        _, sortie, _ = self.check(feature(1, status="In progress", bloc={"rank": 20}), feature(2, status="In progress", bloc={"rank": 10}))
        signaux = [l for l in sortie.splitlines() if "signalement" in l]
        self.assertEqual([l.split(" : ")[2] for l in signaux], ["R-2", "R-1"])

    def test_features_fermees_et_idees_ignorees(self):
        self.git({"main"})
        _, sortie, _ = self.check(feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED"))
        self.assertEqual(sortie, "roadmap : file valide\n")

    def test_hors_ligne_signaux_apres_la_banniere(self):
        self.git({"main"})
        self.depot(feature(1, status="In progress"))
        self.lance("check")
        os.environ["FAKE_GH_MODE"] = "offline"
        code, sortie, _ = self.lance("check")
        lignes = sortie.splitlines()
        self.assertEqual(code, 0, sortie)
        self.assertTrue(lignes[0].startswith("GitHub unreachable; read from the cache of"))
        self.assertEqual(lignes[1:], [self.SIG_SANS_BRANCHE, "roadmap : file valide"])

    def test_aucun_nom_de_branche_titre_ni_corps_imprime(self):
        self.git({"main", "secret/branche-privee"})
        _, sortie, _ = self.check(feature(1, titre="TITRE-PRIVE", status="In progress", texte="CORPS-PRIVE"))
        for interdit in ("secret/branche-privee", "TITRE-PRIVE", "CORPS-PRIVE"):
            self.assertNotIn(interdit, sortie)

    def test_lecture_seule_gh_et_git(self):
        vus = []
        reel = subprocess.run

        def faux(cmd, *a, **kw):
            if cmd[0] == "git":
                vus.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return reel(cmd, *a, **kw)
        self.depot(feature(1, status="In progress"), feature(2, bloc={"method": "openspec", "change": "c"}))
        with mock.patch.object(subprocess, "run", faux):
            code, sortie, _ = self.lance("check")
        self.assertEqual(code, 0, sortie)
        self.assertTrue(vus)
        for cmd in vus:
            self.assertIn(cmd[3], ("for-each-ref", "ls-tree"), cmd)
        for a in self.appels():
            self.assertEqual(a[:2], ["api", "graphql"])
            self.assertFalse(any("mutation" in x.lower() for x in a), a)


class TestLecteursGit(Base):
    """`branches_locales` et `changes_sur_main` (design D3) : Git en lecture seule, entrée fermée, délai borné."""

    def faux_git(self, reponses):
        """Remplace subprocess.run : `reponses` associe la sous-commande (et le dernier argument) à (code, sortie)."""
        vus = []

        def faux(cmd, *a, **kw):
            vus.append((cmd, kw))
            code, sortie = reponses(cmd)
            return subprocess.CompletedProcess(cmd, code, sortie, "")
        return vus, mock.patch.object(subprocess, "run", faux)

    def test_branches_locales(self):
        vus, p = self.faux_git(lambda cmd: (0, "refs/heads/main\nrefs/heads/feat/c\nrefs/heads/chore/r65-x\n"))
        with p:
            self.assertEqual(roadmap.branches_locales(), {"main", "feat/c", "chore/r65-x"})
        cmd, kw = vus[0]
        self.assertEqual((cmd[0], cmd[3]), ("git", "for-each-ref"))
        self.assertEqual(kw.get("stdin"), subprocess.DEVNULL)
        self.assertEqual(kw.get("timeout"), roadmap.DELAI_GIT)

    def test_branches_locales_illisibles(self):
        _, p = self.faux_git(lambda cmd: (128, ""))
        with p:
            self.assertIsNone(roadmap.branches_locales())
        with mock.patch.object(subprocess, "run", mock.Mock(side_effect=subprocess.TimeoutExpired("git", 1))):
            self.assertIsNone(roadmap.branches_locales())
        with mock.patch.object(subprocess, "run", mock.Mock(side_effect=OSError("pas de git"))):
            self.assertIsNone(roadmap.branches_locales())

    def reponses_main(self, cmd):
        assert cmd[3] == "ls-tree" and "refs/heads/main" in cmd, cmd
        if cmd[-1] == "openspec/changes/":
            return 0, "openspec/changes/archive\nopenspec/changes/mon-change\nopenspec/changes/autre\n"
        if cmd[-1] == "openspec/changes/archive/":
            return 0, "openspec/changes/archive/2026-01-01-vieux-change\n"
        raise AssertionError(cmd)

    def test_changes_sur_main_non_archives_et_archives(self):
        vus, p = self.faux_git(self.reponses_main)
        with p:
            noms = roadmap.changes_sur_main()
        self.assertTrue({"mon-change", "autre", "vieux-change"} <= noms, noms)
        self.assertNotIn("change", noms)        # seul le nom après la date d'archive, jamais un suffixe
        self.assertNotIn("archive", noms)
        self.assertNotIn("not-a-change", noms)
        for cmd, kw in vus:
            self.assertEqual(kw.get("stdin"), subprocess.DEVNULL)
            self.assertEqual(kw.get("timeout"), roadmap.DELAI_GIT)

    def test_changes_sur_main_illisible_sans_ref_main(self):
        _, p = self.faux_git(lambda cmd: (128, ""))
        with p:
            self.assertIsNone(roadmap.changes_sur_main())

    def test_changes_sur_main_sans_dossier_d_archive(self):
        _, p = self.faux_git(lambda cmd: (0, "openspec/changes/mon-change\n" if cmd[-1] == "openspec/changes/" else ""))
        with p:
            self.assertEqual(roadmap.changes_sur_main(), {"mon-change"})

    def test_lecture_reelle_du_depot(self):
        """Sans remplacement : le lecteur lit le vrai dépôt, en lecture seule (ses refs locales contiennent au moins la branche courante)."""
        branches = roadmap.branches_locales()
        self.assertTrue(branches is None or isinstance(branches, set))
        noms = roadmap.changes_sur_main()
        self.assertTrue(noms is None or isinstance(noms, set))


class TestNext(Base):
    def next(self, budget, *noeuds, extra=()):
        self.depot(*noeuds)
        return self.lance("next", "--budget", budget, "--today", "2026-10-12", *extra)

    def test_budget_rempli_par_rang(self):
        code, sortie, _ = self.next("2h", feature(1, bloc={"estimate": "1h"}), feature(2, bloc={"estimate": "1h30"}),
                                    feature(3, bloc={"estimate": "30min"}))
        self.assertEqual(code, 0, sortie)
        self.assertIn("R-1 |", sortie)
        self.assertIn("R-3 |", sortie)
        self.assertIn("trop long pour le temps restant :\n  R-2 |", sortie)
        self.assertIn("total 1h30", sortie)

    def test_le_rang_prime_sur_le_numero(self):
        _, sortie, _ = self.next("1h", feature(1, bloc={"rank": 50}), feature(2, bloc={"rank": 5}))
        self.assertIn("proposés :\n  R-2 |", sortie)
        self.assertIn("trop long pour le temps restant :\n  R-1 |", sortie)

    def test_estimation_tbd_a_part(self):
        _, sortie, _ = self.next("2h", feature(1, bloc={"estimate": "tbd"}), feature(2, bloc={"estimate": "1h"}))
        self.assertIn("sans estimation (non comptés) :\n  R-1 |", sortie)
        self.assertIn("total 1h", sortie)

    def test_not_before(self):
        _, sortie, _ = self.next("2h", feature(1, bloc={"not_before": "2026-10-13"}), feature(2, bloc={"not_before": "2026-10-12"}))
        self.assertNotIn("R-1 |", sortie)
        self.assertIn("R-2 |", sortie)

    def test_jamais_un_travail_non_ready_ou_bloque(self):
        # R-20261104-23 : un Todo direct-prompt est maintenant proposé ; seul un Todo openspec ne l'est pas (scénario « Not ready or blocked »)
        _, sortie, _ = self.next("8h", feature(1, status="Todo", bloc={"method": "openspec"}), feature(2, status="In progress"),
                                 feature(3, status="Todo", blocked_by=[101]), feature(4, status="Done", state="CLOSED", milestone="Tarasque"))
        self.assertIn("jobs proposés : aucun", sortie)
        self.assertIn("total 0min", sortie)

    def test_bloqueur_ferme_ne_bloque_pas(self):
        _, sortie, _ = self.next("2h", feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED"),
                                 feature(2, blocked_by=[101]))
        self.assertIn("R-2 |", sortie)

    def test_milestone(self):
        _, sortie, _ = self.next("8h", feature(1, milestone="Hydra"), feature(2, milestone="Namazu"), extra=("--milestone", "Namazu"))
        self.assertIn("R-2 |", sortie)
        self.assertNotIn("R-1 |", sortie)

    def test_affichage_complet(self):
        _, sortie, _ = self.next("2h", feature(1, titre="Mon travail", bloc={"conditions": "valider X", "due": "2026-11-01"}))
        ligne = next(l for l in sortie.splitlines() if "R-1 |" in l)
        for morceau in ("Mon travail", "estimation 1h", "méthode direct-prompt", "modèle sonnet", "à confirmer : valider X",
                        "échéance 2026-11-01"):
            self.assertIn(morceau, ligne)

    def test_budget_mal_forme(self):
        self.depot(feature(1))
        code, sortie, _ = self.lance("next", "--budget", "demain")
        self.assertEqual(code, 2)
        self.assertNotIn("R-1", sortie)

    def test_file_invalide(self):
        code, _, _ = self.next("2h", feature(1, bloc={"method": "x"}))
        self.assertEqual(code, 1)

    def test_date_du_jour_par_environnement(self):
        self.depot(feature(1, bloc={"not_before": "2026-10-13"}))
        os.environ["ROADMAP_TODAY"] = "2026-10-14"
        self.addCleanup(os.environ.pop, "ROADMAP_TODAY", None)
        self.assertIn("R-1 |", self.lance("next", "--budget", "2h")[1])

    # change github-status-lifecycle, design D11 (R-20261104-23, O3)
    def test_todo_direct_prompt_propose(self):
        code, sortie, _ = self.next("2h", feature(1, status="Todo"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("proposés :\n  R-1 |", sortie)
        self.assertIn("total 1h", sortie)
        for a in self.appels():
            self.assertEqual(a[:2], ["api", "graphql"])

    def test_todo_openspec_jamais_propose(self):
        _, sortie, _ = self.next("8h", feature(1, status="Todo", bloc={"method": "openspec"}),
                                 feature(2, status="Todo", bloc={"method": "openspec", "change": "c"}))
        self.assertIn("jobs proposés : aucun", sortie)
        self.assertIn("total 0min", sortie)

    def test_todo_direct_prompt_bloque_ou_pas_encore_jamais_propose(self):
        _, sortie, _ = self.next("8h", feature(1, status="Todo"), feature(2, status="Todo", blocked_by=[101]),
                                 feature(3, status="Todo", bloc={"not_before": "2026-10-13"}))
        self.assertIn("proposés :\n  R-1 |", sortie)
        self.assertNotIn("R-2 |", sortie)
        self.assertNotIn("R-3 |", sortie)

    def test_todo_direct_prompt_suit_le_budget_et_le_jalon(self):
        _, sortie, _ = self.next("1h", feature(1, status="Todo", bloc={"estimate": "2h"}), feature(2, status="Todo", milestone="Namazu"),
                                 extra=("--milestone", "Hydra"))
        self.assertIn("trop long pour le temps restant :\n  R-1 |", sortie)
        self.assertNotIn("R-2 |", sortie)


class TestShowStatus(Base):
    def setUp(self):
        super().setUp()
        self.depot(feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED",
                           bloc={"done_on": "2026-10-05"}, theme="base", labels=[rm.LABEL_FEATURE, "theme:base"]),
                   feature(2, titre="Deuxième", status="In progress", bloc={"started_on": "2026-10-10", "conditions": "confirmer"},
                           blocked_by=[101], texte="Paragraphe du travail."),
                   feature(3, status="Todo", blocked_by=[102]), feature(4),
                   sous_issue(2, 1, 102), sous_issue(2, 2, 102, state="CLOSED", labels=[rm.LABEL_TASK, rm.LABEL_USER]))

    def test_show(self):
        code, sortie, _ = self.lance("show", "R-2")
        self.assertEqual(code, 0, sortie)
        for morceau in ("Deuxième", "In progress", "Hydra", "confirmer", "started_on : 2026-10-10", "R-1 (fermée)",
                        "R-2/g1 | ", "ouverte", "R-2/g2 | ", "fermée", "Paragraphe du travail."):
            self.assertIn(morceau, sortie)

    def test_show_identifiant_inconnu(self):
        code, sortie, _ = self.lance("show", "R-99")
        self.assertEqual(code, 1)
        self.assertIn("R-99", sortie)

    def test_status(self):
        code, sortie, _ = self.lance("status")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ready 1", sortie)
        self.assertIn("in-progress 1", sortie)
        self.assertIn("blocked 1", sortie)
        self.assertIn("done 1", sortie)
        self.assertIn("R-2 | Deuxième | depuis 2026-10-10", sortie)
        self.assertIn("R-3 | Travail | attend R-2", sortie)
        self.assertIn("R-4 | Travail | estimation 1h", sortie)

    def test_status_file_invalide(self):
        self.depot(feature(1, bloc={"method": "x"}))
        self.assertEqual(self.lance("status")[0], 1)


class TestHorsLigne(Base):
    def test_cache_ecrit_apres_une_lecture_reussie_hors_du_depot(self):
        self.depot(feature(1))
        self.lance("check", "--today", "2026-10-11")
        self.assertTrue(self.cache().is_file())
        self.assertNotIn(str(RACINE), str(self.cache()))
        self.assertEqual(json.loads(self.cache().read_text(encoding="utf-8"))["date"], "2026-10-11")

    def test_hors_ligne_avec_cache(self):
        self.depot(feature(1, bloc={"estimate": "1h"}))
        self.lance("check", "--today", "2026-10-11")
        os.environ["FAKE_GH_MODE"] = "offline"
        code, sortie, _ = self.lance("next", "--budget", "2h", "--today", "2026-10-12")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines()[0], "GitHub unreachable; read from the cache of 2026-10-11")
        self.assertIn("R-1 |", sortie)

    def test_hors_ligne_toutes_les_lectures(self):
        self.depot(feature(1))
        self.lance("check", "--today", "2026-10-11")
        os.environ["FAKE_GH_MODE"] = "offline"
        for cmd in (["check"], ["status"], ["show", "R-1"], ["next", "--budget", "1h"]):
            with self.subTest(cmd=cmd):
                code, sortie, _ = self.lance(*cmd)
                self.assertEqual(code, 0, sortie)
                self.assertEqual(sortie.splitlines()[0], "GitHub unreachable; read from the cache of 2026-10-11")

    def test_hors_ligne_sans_cache(self):
        os.environ["FAKE_GH_MODE"] = "offline"
        for cmd in (["check"], ["status"], ["show", "R-1"], ["next", "--budget", "1h"]):
            with self.subTest(cmd=cmd):
                code, sortie, erreur = self.lance(*cmd)
                self.assertEqual(code, 5)
                self.assertIn("GitHub unreachable and no cache", erreur)

    def test_non_authentifie_est_traite_comme_injoignable(self):
        os.environ["FAKE_GH_MODE"] = "auth"
        self.assertEqual(self.lance("check")[0], 5)

    def test_gh_absent(self):
        os.environ["PMZILLA_GH"] = str(self.dir / "inexistant")
        self.assertEqual(self.lance("check")[0], 5)

    def test_le_cache_n_est_pas_ecrit_hors_ligne(self):
        self.depot(feature(1))
        self.lance("check", "--today", "2026-10-11")
        avant = self.cache().read_text(encoding="utf-8")
        os.environ["FAKE_GH_MODE"] = "offline"
        self.lance("check", "--today", "2026-10-20")
        self.assertEqual(self.cache().read_text(encoding="utf-8"), avant)

    def test_cache_remplace_a_chaque_lecture(self):
        self.depot(feature(1))
        self.lance("check", "--today", "2026-10-11")
        self.depot(feature(1), feature(2))
        self.reel = datetime.date(2026, 10, 12)
        self.lance("check", "--today", "2026-10-12")
        d = json.loads(self.cache().read_text(encoding="utf-8"))
        self.assertEqual((d["date"], len(d["issues"])), ("2026-10-12", 2))


class TestCorrectionsRevue(Base):
    def test_date_du_cache_est_la_date_reelle_pas_today(self):
        self.depot(feature(1))
        self.lance("check", "--today", "2030-01-01")
        self.assertEqual(json.loads(self.cache().read_text(encoding="utf-8"))["date"], "2026-10-11")
        os.environ["ROADMAP_TODAY"] = "2031-01-01"
        self.lance("check")
        self.assertEqual(json.loads(self.cache().read_text(encoding="utf-8"))["date"], "2026-10-11")

    def test_erreur_graphql_avec_identifiant_personnel_retenue(self):
        self.depot(feature(1))
        os.environ["FAKE_GH_MODE"] = "graphql_error_perso"
        os.environ["FAKE_GH_SECRET"] = "zorglub-fictif"
        with mock.patch.object(roadmap.identifiants_personnels, "identifiants", lambda racine: ["zorglub-fictif"]):
            code, sortie, erreur = self.lance("check")
        self.assertEqual(code, 1)
        self.assertNotIn("zorglub-fictif", erreur + sortie)
        self.assertIn("GitHub refused: HTTP 403 (message withheld)", erreur)

    def test_erreur_graphql_sans_identifiant_gardee(self):
        self.depot(feature(1))
        os.environ["FAKE_GH_MODE"] = "graphql_error"
        with mock.patch.object(roadmap.identifiants_personnels, "identifiants", lambda racine: ["zorglub-fictif"]):
            _, _, erreur = self.lance("check")
        self.assertIn("doesn't exist", erreur)

    def test_erreurs_dans_la_reponse_json_avec_identifiant_retenues(self):
        self.depot(feature(1))
        os.environ["FAKE_GH_MODE"] = "json_errors_perso"
        os.environ["FAKE_GH_SECRET"] = "zorglub-fictif"
        with mock.patch.object(roadmap.identifiants_personnels, "identifiants", lambda racine: ["zorglub-fictif"]):
            code, sortie, erreur = self.lance("check")
        self.assertEqual(code, 1)
        self.assertNotIn("zorglub-fictif", erreur + sortie)
        self.assertIn("(message withheld)", erreur)

    def test_status_d_un_autre_project_ignore(self):
        n = feature(1, status=None)
        n["projectItems"] = {"nodes": [
            {"fieldValueByName": {"name": "Done"}, "project": {"title": "Autre projet"}},
            {"fieldValueByName": {"name": "Ready"}, "project": {"title": roadmap.PROJECT_TITLE}}]}
        self.depot(n)
        code, sortie, _ = self.lance("show", "R-1")
        self.assertIn("Status : Ready", sortie)
        n["projectItems"] = {"nodes": [{"fieldValueByName": {"name": "Ready"}, "project": {"title": "Autre projet"}}]}
        self.depot(n)
        _, sortie, _ = self.lance("check")
        self.assertIn("absent du Project", sortie)

    def test_la_requete_demande_le_titre_du_project(self):
        self.depot(feature(1))
        self.lance("check")
        self.assertIn("project{title}", " ".join(self.appels()[0]))


class TestRappel(Base):
    def test_ligne_de_comptes_sans_reseau(self):
        self.depot(feature(1), feature(2), feature(3, status="In progress"), feature(4, status="Todo"),
                   feature(5, state="CLOSED", status="Done", milestone="Tarasque", milestone_state="CLOSED"))
        self.reel = datetime.date(2026, 10, 12)
        self.lance("check", "--today", "2026-10-12")
        self.journal.unlink()
        os.environ["FAKE_GH_MODE"] = "offline"
        code, sortie, _ = self.lance("reminder", "--session-hook")
        self.assertEqual(code, 0)
        self.assertEqual(sortie, "roadmap: 2 ready, 1 in progress (cache of 2026-10-12)\n")
        self.assertFalse(self.journal.exists(), "le rappel ne doit pas lancer gh")

    def test_l_option_session_hook_ne_change_rien(self):
        self.depot(feature(1), feature(2, status="In progress"))
        self.lance("check", "--today", "2026-10-12")
        avec = self.lance("reminder", "--session-hook")
        sans = self.lance("reminder")
        self.assertEqual(avec[:2], sans[:2])
        self.assertEqual(avec[0], 0)
        self.assertEqual(len(avec[1].splitlines()), 1)

    def test_sans_cache_rien_et_code_0(self):
        code, sortie, erreur = self.lance("reminder", "--session-hook")
        self.assertEqual((code, sortie, erreur), (0, "", ""))
        self.assertFalse(self.journal.exists())

    def test_cache_illisible_rien_et_code_0(self):
        self.cache().parent.mkdir(parents=True)
        self.cache().write_text("pas du json", encoding="utf-8")
        self.assertEqual(self.lance("reminder", "--session-hook")[:2], (0, ""))

    def test_aucun_titre_ni_corps(self):
        self.depot(feature(1, titre="Titre secret", texte="Corps secret"))
        self.lance("check", "--today", "2026-10-12")
        _, sortie, _ = self.lance("reminder", "--session-hook")
        self.assertNotIn("secret", sortie)
        self.assertEqual(len(sortie.splitlines()), 1)


class TestBoardRetire(Base):
    """`board` n'existe plus (R-145) : erreur d'usage d'argparse, aucun appel gh, aucune page écrite."""

    def test_board_refuse_avec_ou_sans_options(self):
        self.depot(feature(1))
        for cmd in (["board"], ["board", "--open"], ["board", "--product", "mothra"]):
            with self.subTest(cmd=cmd):
                code, sortie, erreur = self.lance(*cmd)
                self.assertEqual(code, 2)
                self.assertIn("invalid choice", erreur)
                self.assertIn("board", erreur)
                self.assertEqual(self.appels(), [], "aucun appel de gh")
                self.assertFalse((self.dir / "data" / "feuille-de-route.html").exists())


class TestModeFichierRetire(Base):
    def test_option_file_et_sous_commandes_done_archive_refusees(self):
        for cmd in (["check", "--file", "f.md"], ["done", "R-1"], ["archive"]):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.lance(*cmd)[0], 2)
        self.assertFalse(self.journal.exists())


if __name__ == "__main__":
    unittest.main()


class TestDepotDOrigine(Base):
    def test_lectures_nomment_le_depot_d_origin(self):
        self.depot(feature(1))
        self.lance("check")
        appels = self.appels()
        self.assertTrue(appels)
        for a in appels:
            self.assertIn("owner=owner-x", a)
            self.assertIn("name=repo-y", a)
            self.assertFalse(any("{owner}" in x or "{repo}" in x for x in a), a)

    def test_chaque_forme_d_url(self):
        self.depot(feature(1))
        for url in ("git@github.com:owner-x/repo-y.git", "https://github.com/owner-x/repo-y.git", "https://github.com/owner-x/repo-y",
                    "ssh://git@github.com/owner-x/repo-y.git"):
            with self.subTest(url=url):
                self.origin = url
                self.journal.unlink(missing_ok=True)
                self.assertEqual(self.lance("check")[0], 0)
                self.assertIn("owner=owner-x", self.appels()[0])
                self.assertIn("name=repo-y", self.appels()[0])

    def test_origin_absent_code_2_sans_lecture(self):
        self.depot(feature(1))
        self.lance("check")                      # écrit un instantané
        self.journal.unlink()
        for origin in ("", "https://example.org/a/b"):
            for cmd in (["check"], ["status"], ["show", "R-1"], ["next", "--budget", "1h"]):
                with self.subTest(origin=origin, cmd=cmd):
                    self.origin = origin
                    code, sortie, erreur = self.lance(*cmd)
                    self.assertEqual(code, 2)
                    self.assertEqual(sortie, "")
                    self.assertIn("usage: the origin remote is missing or is not a GitHub repository", erreur)
                    self.assertEqual(self.appels(), [], "aucune lecture de GitHub")

    def test_origin_lu_sans_entree_et_avec_delai(self):
        vus = []
        reel = subprocess.run

        def espion(cmd, *a, **kw):
            vus.append((cmd, kw))
            return reel(cmd, *a, **kw)
        # git_origin_url réel : on le rappelle sans le patch de Base
        q = mock.patch.object(roadmap, "git_origin_url", roadmap_git_origin_url_reel)
        with q, mock.patch.object(subprocess, "run", espion):
            roadmap.git_origin_url()
        cmd, kw = vus[0]
        self.assertEqual(cmd[:2], ["git", "-C"])
        self.assertIn("get-url", cmd)
        self.assertEqual(kw.get("stdin"), subprocess.DEVNULL)
        self.assertIsNotNone(kw.get("timeout"))


class TestAppelsBornes(Base):
    def espionne(self):
        vus = []
        reel = subprocess.run

        def espion(cmd, *a, **kw):
            vus.append((cmd, kw))
            return reel(cmd, *a, **kw)
        return vus, mock.patch.object(subprocess, "run", espion)

    def test_entree_fermee_invites_coupees_et_delai_par_defaut(self):
        self.depot(feature(1))
        vus, p = self.espionne()
        with p:
            self.assertEqual(self.lance("check")[0], 0)
        gh = [kw for cmd, kw in vus if cmd[0] == str(FAUX_GH)]
        self.assertTrue(gh)
        for kw in gh:
            self.assertEqual(kw.get("stdin"), subprocess.DEVNULL)
            self.assertEqual(kw["env"]["GH_PROMPT_DISABLED"], "1")
            self.assertEqual(kw["timeout"], 60)

    def test_delai_par_variable(self):
        os.environ["PMZILLA_GH_TIMEOUT"] = "7"
        self.depot(feature(1))
        vus, p = self.espionne()
        with p:
            self.lance("check")
        self.assertEqual([kw["timeout"] for cmd, kw in vus if cmd[0] == str(FAUX_GH)], [7] * len([1 for cmd, _ in vus if cmd[0] == str(FAUX_GH)]))

    def test_delai_invalide_retombe_sur_le_defaut(self):
        self.depot(feature(1))
        for v in ("abc", "0", "-3", ""):
            os.environ["PMZILLA_GH_TIMEOUT"] = v
            vus, p = self.espionne()
            with self.subTest(v=v), p:
                self.lance("check")
                self.assertEqual({kw["timeout"] for cmd, kw in vus if cmd[0] == str(FAUX_GH)}, {60})

    def test_sans_reponse_avec_instantane(self):
        self.depot(feature(1))
        self.lance("check", "--today", "2026-10-11")
        os.environ["FAKE_GH_MODE"] = "hang"
        os.environ["PMZILLA_GH_TIMEOUT"] = "0.5"
        code, sortie, _ = self.lance("status")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines()[0], "GitHub unreachable; read from the cache of 2026-10-11")

    def test_sans_reponse_sans_instantane(self):
        os.environ["FAKE_GH_MODE"] = "hang"
        os.environ["PMZILLA_GH_TIMEOUT"] = "0.5"
        code, _, erreur = self.lance("check")
        self.assertEqual(code, 5)
        self.assertIn("GitHub unreachable and no cache", erreur)


class TestReleaseCourante(Base):
    def regle(self, texte):
        self.reglages.write_text(texte, encoding="utf-8")

    def lignes(self, *args):
        code, sortie, _ = self.lance("check", *args)
        return code, [l for l in sortie.splitlines() if "current_release" in l]

    def base(self):
        self.depot(feature(1))
        os.environ["FAKE_GH_MILESTONES"] = json.dumps([{"title": "Hydra", "state": "OPEN"}, {"title": "Griffon", "state": "CLOSED"},
                                                       {"title": "Tarasque", "state": "OPEN"}])

    def test_jalon_ouvert(self):
        self.base()
        self.regle("current_release: Hydra\n")
        self.assertEqual(self.lignes(), (0, []))

    def test_jalon_ferme(self):
        self.base()
        self.regle("current_release: Griffon\n")
        code, l = self.lignes()
        self.assertEqual(code, 1)
        self.assertEqual(len(l), 1)
        self.assertTrue(l[0].startswith(roadmap.PREFIXE + "current_release : "), l)
        self.assertIn("Griffon", l[0])

    def test_tarasque(self):
        self.base()
        self.regle("current_release: Tarasque\n")
        code, l = self.lignes()
        self.assertEqual((code, len(l)), (1, 1))
        self.assertIn("Tarasque", l[0])

    def test_jalon_inconnu(self):
        self.base()
        self.regle("current_release: Chimere\n")
        code, l = self.lignes()
        self.assertEqual((code, len(l)), (1, 1))
        self.assertIn("Chimere", l[0])

    def test_vide_ou_fichier_absent(self):
        self.base()
        self.assertEqual(self.lignes(), (0, []))                  # fichier absent
        self.regle("current_release:\n")
        self.assertEqual(self.lignes(), (0, []))

    def test_fichier_illisible(self):
        self.base()
        self.regle("current_release: [a]\n")
        code, l = self.lignes()
        self.assertEqual((code, len(l)), (1, 1))

    def test_les_autres_commandes_ne_sont_pas_refusees(self):
        self.base()
        self.regle("current_release: Chimere\n")
        self.assertEqual(self.lance("status")[0], 0)

    def test_hors_ligne_lit_les_jalons_de_l_instantane(self):
        self.base()
        self.regle("current_release: Griffon\n")
        self.lance("check")
        os.environ["FAKE_GH_MODE"] = "offline"
        code, l = self.lignes()
        self.assertEqual((code, len(l)), (1, 1))
        self.regle("current_release: Hydra\n")
        self.assertEqual(self.lignes(), (0, []))

    def test_le_lecteur_n_ecrit_pas_le_reglage(self):
        self.base()
        self.regle("current_release: Hydra\n")
        avant = self.reglages.read_text(encoding="utf-8")
        self.lance("check")
        self.assertEqual(self.reglages.read_text(encoding="utf-8"), avant)

    def test_fichier_suivi_valide(self):
        """La valeur change à chaque publication de l'édition : le test exige un fichier lisible, pas une valeur."""
        texte = (RACINE / rm.SETTINGS_FILE).read_text(encoding="utf-8")
        self.assertIsInstance(rm.parse_settings(texte)["current_release"], str)
        self.assertEqual(Path(roadmap.RACINE / rm.SETTINGS_FILE), RACINE / "tools" / "roadmap_settings.yaml")


class TestBatch(Base):
    """`roadmap.py batch --milestone` : lot d'un jalon (change batch-milestone, design D2, D3, D5)."""

    def setUp(self):
        super().setUp()
        self.arbre = self.dir / "arbre"
        for chemin in ("tools/a.py", "tools/b.py", "docs/pmzilla/installation.md", "README.md", "tests/x/t.py"):
            (self.arbre / chemin).parent.mkdir(parents=True, exist_ok=True)
            (self.arbre / chemin).write_text("x", encoding="utf-8")
        q = mock.patch.object(roadmap, "ARBRE", self.arbre)
        q.start()
        self.addCleanup(q.stop)

    def change(self, nom, tasks="", design=""):
        d = self.arbre / "openspec" / "changes" / nom
        d.mkdir(parents=True, exist_ok=True)
        (d / "tasks.md").write_text(tasks, encoding="utf-8")
        (d / "design.md").write_text(design, encoding="utf-8")

    def os_feature(self, n, nom, tasks="", **kw):
        bloc = {"method": "openspec", "change": nom, **kw.pop("bloc", {})}
        self.change(nom, tasks)
        return feature(n, bloc=bloc, **kw)

    def batch(self, *noeuds, milestone="Hydra", extra=()):
        self.depot(*noeuds)
        return self.lance("batch", "--milestone", milestone, "--today", "2026-10-13", *extra)

    def lignes(self, sortie):
        return sortie.splitlines()

    def test_independantes_dans_l_ordre_du_rang(self):
        code, sortie, _ = self.batch(self.os_feature(2, "c2", "`tools/b.py`"), self.os_feature(1, "c1", "`tools/a.py`"))
        self.assertEqual(code, 0, sortie)
        l = self.lignes(sortie)
        self.assertEqual(l[0], "roadmap : lot du jalon Hydra")
        self.assertEqual(l[1], "roadmap : release courante : aucune")
        self.assertEqual(l[2], "roadmap : retenues :")
        self.assertTrue(l[3].startswith("  R-1 | Travail | méthode openspec | modèle sonnet | branche feat/c1 | session sonnet | exécution | fichiers 1"), l[3])
        self.assertTrue(l[4].startswith("  R-2 |"), l[4])
        self.assertNotIn("écartées", sortie)

    def test_fichier_commun_avec_mieux_classee(self):
        code, sortie, _ = self.batch(self.os_feature(1, "c1", "`tools/`"), self.os_feature(2, "c2", "`tools/b.py`"))
        self.assertEqual(code, 0)
        self.assertIn("roadmap : écartées :\n  R-2 | Travail | fichiers communs avec R-1\n", sortie)
        self.assertNotIn("  R-2 | Travail | méthode", sortie)

    def test_fichier_commun_avec_un_job_en_cours_d_un_autre_jalon(self):
        code, sortie, _ = self.batch(self.os_feature(1, "c1", "`tools/a.py`", status="In progress", milestone="Namazu"),
                                     self.os_feature(2, "c2", "`tools/`"))
        self.assertEqual(code, 0)
        self.assertIn("  R-2 | Travail | fichiers communs avec R-1 (en cours)", sortie)
        self.assertIn("retenues : aucune", sortie)

    def test_fichiers_inconnus_ne_ecartent_personne(self):
        code, sortie, _ = self.batch(feature(1), self.os_feature(2, "c2", "`tools/a.py`"), self.os_feature(3, "c3", "`tools/a.py`"))
        self.assertEqual(code, 0)
        self.assertIn("  R-1 | Travail | méthode direct-prompt | modèle sonnet | branche chore/r1-travail | session sonnet | exécution | fichiers inconnus", sortie)
        self.assertIn("  R-2 | Travail | méthode openspec", sortie)
        self.assertIn("  R-3 | Travail | fichiers communs avec R-2", sortie)

    def test_change_introuvable(self):
        code, sortie, _ = self.batch(feature(1, bloc={"method": "openspec", "change": "absent"}))
        self.assertEqual(code, 0)
        self.assertIn("  R-1 | Travail | change absent introuvable", sortie)
        self.assertIn("retenues : aucune", sortie)

    def test_change_archive_introuvable(self):
        (self.arbre / "openspec" / "changes" / "archive" / "2026-01-01-vieux").mkdir(parents=True)
        code, sortie, _ = self.batch(feature(1, bloc={"method": "openspec", "change": "2026-01-01-vieux"}))
        self.assertIn("change 2026-01-01-vieux introuvable", sortie)

    def test_openspec_sans_change_cadrage(self):
        code, sortie, _ = self.batch(feature(1, bloc={"method": "openspec"}))
        self.assertIn("branche chore/spec-r1 | session opus | cadrage | fichiers inconnus", sortie)

    def test_fichiers_partages_listes_sans_ecarter(self):
        code, sortie, _ = self.batch(self.os_feature(1, "c1", "`README.md` `docs/pmzilla/installation.md` `tools/a.py`"),
                                     self.os_feature(2, "c2", "`README.md` `tools/b.py`"))
        self.assertEqual(code, 0)
        self.assertNotIn("écartées", sortie)
        self.assertIn("roadmap : fichiers partagés :\n  README.md | R-1, R-2\n", sortie)
        self.assertNotIn("installation.md | ", sortie)

    def test_hors_lot(self):
        # R-20261104-23 : un Todo direct-prompt est maintenant retenu ; un Todo dont le change est nommé ne l'est pas (scénario « Feature not proposable »)
        self.depot(feature(1, milestone="Namazu"), feature(2, status="Todo", bloc={"method": "openspec", "change": "c2"}),
                   feature(3, status="Todo", bloc={"method": "openspec", "change": "c3"}),
                   feature(4, status="Todo", blocked_by=[103]), feature(5, bloc={"not_before": "2026-12-01"}),
                   feature(6, status="Done", state="CLOSED", milestone="Hydra"))
        code, sortie, _ = self.lance("batch", "--milestone", "Hydra", "--today", "2026-10-13")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("R-", "\n".join(l for l in sortie.splitlines() if l.startswith("  ")))
        self.assertIn("retenues : aucune", sortie)
        self.assertNotIn("écartées", sortie)

    def test_conditions_et_echeance(self):
        code, sortie, _ = self.batch(feature(1, bloc={"conditions": "accord du métier", "due": "2026-11-01"}))
        self.assertIn("| à confirmer : accord du métier | échéance 2026-11-01", sortie)

    def test_pas_de_description(self):
        code, sortie, _ = self.batch(feature(1, texte="SECRET-LIBRE"))
        self.assertNotIn("SECRET-LIBRE", sortie)

    def test_release_courante(self):
        self.reglages.write_text("current_release: Hydra\n", encoding="utf-8")
        _, sortie, _ = self.batch(feature(1))
        self.assertIn("roadmap : release courante : Hydra", sortie)

    def test_file_invalide(self):
        code, sortie, _ = self.batch(feature(1, bloc={"zzz": 1}))
        self.assertEqual(code, 1)
        self.assertIn("R-1", sortie)

    def test_jalon_manquant_inconnu_ferme(self):
        code, _, erreur = self.lance("batch")
        self.assertEqual(code, 2)
        self.assertIn("--milestone", erreur)
        code, sortie, erreur = self.batch(feature(1), milestone="Inconnu")
        self.assertEqual((code, erreur.strip(), sortie), (2, "usage: unknown milestone Inconnu", ""))
        code, sortie, erreur = self.batch(feature(1, milestone="Golem", milestone_state="CLOSED", state="CLOSED", status="Done"), milestone="Golem")
        self.assertEqual((code, erreur.strip(), sortie), (2, "usage: closed milestone Golem", ""))

    def test_hors_ligne_avec_et_sans_instantane(self):
        self.depot(feature(1))
        self.assertEqual(self.lance("batch", "--milestone", "Hydra")[0], 0)
        self.assertTrue(self.cache().exists())
        os.environ["FAKE_GH_MODE"] = "offline"
        code, sortie, erreur = self.lance("batch", "--milestone", "Hydra")
        self.assertEqual((code, sortie, erreur.strip()), (5, "", "GitHub unreachable; a batch needs a live read"))
        self.cache().unlink()
        code, sortie, erreur = self.lance("batch", "--milestone", "Hydra")
        self.assertEqual((code, sortie, erreur.strip()), (5, "", "GitHub unreachable; a batch needs a live read"))

    def test_lecture_seule(self):
        self.batch(feature(1), feature(2))
        appels = self.appels()
        self.assertTrue(appels)
        for a in appels:
            self.assertEqual(a[:2], ["api", "graphql"])
            self.assertFalse(any("mutation" in x.lower() for x in a), a)

    # change github-status-lifecycle, design D11 (R-20261104-23, O3 (a) avec (c))
    def test_todo_direct_prompt_retenue_en_execution_sans_ecriture(self):
        code, sortie, _ = self.batch(feature(1, status="Todo"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("  R-1 | Travail | méthode direct-prompt | modèle sonnet | branche chore/r1-travail | session sonnet | exécution | fichiers inconnus", sortie)
        for a in self.appels():
            self.assertEqual(a[:2], ["api", "graphql"])
            self.assertFalse(any("mutation" in x.lower() for x in a), a)

    def test_todo_openspec_sans_change_retenue_en_cadrage(self):
        code, sortie, _ = self.batch(feature(1, status="Todo", bloc={"method": "openspec"}))
        self.assertEqual(code, 0, sortie)
        self.assertIn("  R-1 | Travail | méthode openspec | modèle sonnet | branche chore/spec-r1 | session opus | cadrage | fichiers inconnus", sortie)

    def test_todo_openspec_avec_change_ni_retenue_ni_ecartee(self):
        code, sortie, _ = self.batch(self.os_feature(1, "c1", "`tools/a.py`", status="Todo"),
                                     feature(2, status="Todo", bloc={"method": "openspec", "change": "absent"}))
        self.assertEqual(code, 0, sortie)
        self.assertIn("retenues : aucune", sortie)
        self.assertNotIn("écartées", sortie)
        self.assertNotIn("R-1 |", sortie)
        self.assertNotIn("R-2 |", sortie)

    def test_todo_non_proposable_ni_retenue_ni_ecartee(self):
        _, sortie, _ = self.batch(feature(1, status="Todo", blocked_by=[102]), feature(2, status="Todo"),
                                  feature(3, status="Todo", bloc={"not_before": "2026-12-01"}),
                                  feature(4, status="Todo", bloc={"method": "openspec"}, milestone="Namazu"))
        self.assertIn("  R-2 | Travail | méthode direct-prompt", sortie)
        for x in ("R-1 |", "R-3 |", "R-4 |"):
            self.assertNotIn(x, sortie)
        self.assertNotIn("écartées", sortie)
