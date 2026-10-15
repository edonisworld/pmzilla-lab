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
        if not self.journal.exists():
            return []
        return [json.loads(l) for l in self.journal.read_text(encoding="utf-8").splitlines() if l]

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

    def test_jalon_absent(self):
        self.depot(feature(1, milestone=None))
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
        _, sortie, _ = self.next("8h", feature(1, status="Todo"), feature(2, status="In progress"),
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


class TestShowStatusBoard(Base):
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

    def test_board_ecrit_dans_le_dossier_de_donnees(self):
        code, sortie, _ = self.lance("board", "--today", "2026-10-12")
        self.assertEqual(code, 0, sortie)
        page = self.dir / "data" / "feuille-de-route.html"
        self.assertTrue(page.is_file())
        texte = page.read_text(encoding="utf-8")
        self.assertIn("R-2", texte)
        self.assertIn("2026-10-05", texte)

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
        for cmd in (["check"], ["status"], ["board"], ["show", "R-1"], ["next", "--budget", "1h"]):
            with self.subTest(cmd=cmd):
                code, sortie, _ = self.lance(*cmd)
                self.assertEqual(code, 0, sortie)
                self.assertEqual(sortie.splitlines()[0], "GitHub unreachable; read from the cache of 2026-10-11")

    def test_hors_ligne_sans_cache(self):
        os.environ["FAKE_GH_MODE"] = "offline"
        for cmd in (["check"], ["status"], ["board"], ["show", "R-1"], ["next", "--budget", "1h"]):
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

    def test_board_n_imprime_pas_de_chemin_absolu(self):
        self.depot(feature(1))
        _, sortie, _ = self.lance("board")
        self.assertNotIn(str(self.dir), sortie)
        self.assertNotIn(str(Path.home()), sortie)
        self.assertIn("feuille-de-route.html", sortie)


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
            for cmd in (["check"], ["status"], ["board"], ["show", "R-1"], ["next", "--budget", "1h"]):
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
        self.depot(feature(1, milestone="Namazu"), feature(2, status="Todo"), feature(3, status="Todo"),
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
