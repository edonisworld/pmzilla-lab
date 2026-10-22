"""
Tests de tools/gh_issue.py (outil d'écriture vers GitHub, change github-roadmap, design D7 à D9, spec workflow-github-issues).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f

Tout appel à gh passe par le faux gh de ce dossier (variable PMZILLA_GH) : un GitHub simulé dans un fichier JSON, qui note
chaque appel. Aucun test n'appelle le réseau. Liste de noms sensibles et identifiants fictifs (fixtures) : la vraie liste et
les vrais identifiants ne sont jamais lus. Les commandes tournent dans le processus (gh_issue.main), gh est le faux.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
sys.path.insert(0, str(HERE))
import fake_gh_core  # noqa: E402
import gh_issue as g  # noqa: E402
import roadmap_model as rm  # noqa: E402

NAME = "Zorglubian"          # nom fictif de la liste de noms sensibles
IDENT = "ident-fictif-zz"    # identifiant personnel fictif
FAKE_KEY = "ZQ-4321"         # clé de ticket inventée

TASKS = """# Tasks

## 1. Inputs [model: haiku]

- [x] 1.1 First.
- [x] 1.2 Second.

## 2. Build [model: sonnet] [parallel]

- [x] 2.1 Tests first.
- [ ] 2.2 [user] Check by hand.

## 3. User run [user]

- [ ] 3.1 Run it.
"""

OPTIONS = [{"id": "o1", "name": "Todo"}, {"id": "o2", "name": "Ready"}, {"id": "o3", "name": "In progress"}, {"id": "o4", "name": "Done"}]


def new_state():
    return {"repo": "owner-x/repo-y", "issues": [], "labels": [], "comments": [],
            "milestones": [{"number": 1, "title": "Hydra", "state": "open"}, {"number": 2, "title": "Namazu", "state": "open"},
                           {"number": 3, "title": "Tarasque", "state": "closed"}],
            "project": {"id": "PVT_1", "title": g.PROJECT_TITLE, "field_id": "F_1", "options": OPTIONS, "items": []}, "mode": {}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "root"
        (self.root / ".pmzilla").mkdir(parents=True)
        (self.root / ".pmzilla" / "identifiants.txt").write_text(IDENT + "\n", encoding="utf-8")
        (self.root / "openspec" / "changes" / "demo").mkdir(parents=True)
        (self.root / "openspec" / "changes" / "demo" / "tasks.md").write_text(TASKS, encoding="utf-8")
        self.names = Path(self.tmp.name) / "noms.txt"
        self.names.write_text(f"# fixture\n{NAME}\n", encoding="utf-8")
        self.state_path = Path(self.tmp.name) / "state.json"
        self.log_path = Path(self.tmp.name) / "log.jsonl"
        self.log_path.write_text("", encoding="utf-8")
        self.st = new_state()
        self.save()
        env = {"PMZILLA_GH": str(HERE / "fake_gh"), "FAKE_GH_STATE": str(self.state_path), "FAKE_GH_LOG": str(self.log_path),
               "PMZILLA_LAB_SENSITIVE_NAMES": str(self.names), "PMZILLA_LAB_WORKSPACE": str(self.root), "PMZILLA_GH_PAUSE": "0", "ROADMAP_TODAY": "2026-10-12"}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        for target, value in ((g, "RACINE"), ):
            q = mock.patch.object(target, value, self.root)
            q.start()
            self.addCleanup(q.stop)
        self.sleeps = []
        q = mock.patch.object(g, "sleep", lambda s: self.sleeps.append(s))
        q.start()
        self.addCleanup(q.stop)
        q = mock.patch.object(g, "git_origin_url", lambda: "git@github.com:owner-x/repo-y.git")
        q.start()
        self.addCleanup(q.stop)
        self.head = ("chore/r65-fixes", "abc1234")      # (branche ou None en tête détachée, commit court)
        q = mock.patch.object(g, "git_head", lambda: self.head)
        q.start()
        self.addCleanup(q.stop)
        if not self.REEL:
            self.faux_gh_dans_le_processus()

    REEL = False        # True : le faux gh tourne toujours dans un vrai processus (tests du lancement)

    def faux_gh_dans_le_processus(self):
        """Remplace le lanceur de processus pour l'exécutable du faux gh : l'appel va au cœur du faux gh, dans le processus.
        Un mode de blocage (hang_*) garde le vrai processus : seul lui montre qu'un enfant bloqué est tué par la limite."""
        vrai = subprocess.run
        faux = str(HERE / "fake_gh")

        def lance(cmd, *args, **kwargs):
            if cmd[0] != faux:
                return vrai(cmd, *args, **kwargs)
            mode = json.loads(self.state_path.read_text(encoding="utf-8")).get("mode", {})
            if mode.get("hang_reads") or mode.get("hang_writes_after") is not None:
                return vrai(cmd, *args, **kwargs)
            stdin = kwargs["input"] if "input" in kwargs else ""
            devnull = kwargs.get("stdin") is subprocess.DEVNULL
            code, out, err = fake_gh_core.handle(cmd[1:], stdin, kwargs["env"], devnull)
            return subprocess.CompletedProcess(cmd, code, out, err)

        q = mock.patch.object(g.subprocess, "run", lance)
        q.start()
        self.addCleanup(q.stop)

    # état
    def save(self):
        self.state_path.write_text(json.dumps(self.st), encoding="utf-8")

    def load(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def calls(self, writes_only=False):
        lignes = [json.loads(l) for l in self.log_path.read_text(encoding="utf-8").splitlines() if l]
        return [c for c in lignes if c["write"]] if writes_only else lignes

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = g.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    # graines
    def add_issue(self, key, title, labels, body=None, state="open", milestone=None, block=None):
        st = self.st
        n = len(st["issues"]) + 1
        if body is None:
            body = rm.marker(key)
            if block is not None:
                body += "\n\n" + rm.render_block(block)
        issue = {"number": n, "id": 9000 + n, "node_id": f"I_{n}", "title": title, "body": body, "state": state,
                 "state_reason": "completed" if state == "closed" else None, "labels": [{"name": l} for l in labels],
                 "milestone": {"title": milestone, "number": {"Hydra": 1, "Namazu": 2, "Tarasque": 3}[milestone]} if milestone else None}
        st["issues"].append(issue)
        self.save()
        return issue

    def add_feature(self, n, state="open", status=None, milestone="Hydra", change=None, rank=None, blocked_by=(), **over):
        block = {"id": f"R-{n}", "theme": "outillage", "estimate": "1h", "method": "openspec", "model": "sonnet", "conditions": ""}
        if state == "open":
            block["rank"] = rank or n * 10
        if change:
            block["change"] = change
        block.update(over)
        issue = self.add_issue(f"R-{n}", f"R-{n} · Feature {n}", ["type:feature", "theme:outillage"], state=state,
                               milestone=milestone, block=block)
        self.st = self.load()
        if status:
            self.st["project"]["items"].append({"id": f"PVTI_{issue['number']}", "number": issue["number"], "status": status})
        if blocked_by:
            self.st.setdefault("blocked", {})[str(issue["number"])] = [self.number_of(f"R-{b}") for b in blocked_by]
        self.save()
        return issue

    def set_release(self, name):
        """Écrit le réglage de la release en cours dans la racine factice (le fichier est lu par l'outil)."""
        path = self.root / rm.SETTINGS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"current_release: {name}\n" if name else "current_release:\n", encoding="utf-8")

    def milestone_writes(self):
        """Écritures PATCH qui portent un jalon : [(numéro d'issue, numéro de jalon)]."""
        out = []
        for c in self.calls(writes_only=True):
            if "PATCH" in c["args"]:
                body = json.loads(c["stdin"])
                if "milestone" in body:
                    out.append((int(next(a for a in c["args"] if a.startswith("repos/")).rsplit("/", 1)[1]), body["milestone"]))
        return out

    def milestone_of(self, key):
        m = self.issue(key)["milestone"]
        return m["title"] if m else None

    def number_of(self, key):
        st = self.load()
        for i in st["issues"]:
            if i["body"].startswith(f"<!-- roadmap-id: {key} -->"):
                return i["number"]
        raise KeyError(key)

    def issue(self, key):
        st = self.load()
        return next(i for i in st["issues"] if i["body"].startswith(f"<!-- roadmap-id: {key} -->"))

    def status_of(self, key):
        n = self.number_of(key)
        return next((i["status"] for i in self.load()["project"]["items"] if i["number"] == n), None)

    def no_leak(self, *texts, words=(NAME, IDENT, FAKE_KEY)):
        for t in texts:
            for w in words:
                self.assertNotIn(w.lower(), t.lower())


# --- Garde-fou ----------------------------------------------------------------------------------------------------

class Garde(Base):
    def new(self, **sets):
        argv = ["new-feature", "--title", "Titre", "--theme", "outillage", "--milestone", "Hydra"]
        for k, v in sets.items():
            argv += ["--set", f"{k}={v}"]
        return self.run_cli(*argv)

    def test_nom_dans_le_corps(self):
        code, out, err = self.new(conditions=f"voir avec {NAME} demain")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"gh_issue: refused: sensitive name in body, line \d+; nothing was sent")
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.load()["issues"], [])

    def test_nom_dans_le_titre_casse_ignoree(self):
        code, out, err = self.run_cli("new-feature", "--title", NAME.upper() + " plan", "--theme", "outillage", "--milestone", "Hydra")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name in title, line 1", err)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_nom_colle_a_une_lettre_ne_correspond_pas(self):
        code, _, err = self.new(conditions=f"x{NAME}y")
        self.assertEqual(code, 0, err)

    def test_identifiant_dans_une_etiquette_toutes_casses(self):
        client = g.Client(g.Guard.load())
        with self.assertRaises(g.Stop) as c:
            g.ensure_label(client, "owner:" + IDENT.upper())
        self.assertEqual(c.exception.code, 3)
        self.assertIn("personal identifier in label, line 1", c.exception.lines[0])
        self.assertNotIn(IDENT, " ".join(c.exception.lines).lower())
        self.assertEqual(self.calls(writes_only=True), [])

    def test_identifiant_dans_un_commentaire(self):
        self.add_feature(1)
        f = Path(self.tmp.name) / "c.txt"
        f.write_text(f"ligne un\nmerci {IDENT.title()}\n", encoding="utf-8")
        code, out, err = self.run_cli("comment", "R-1", "--body-file", str(f))
        self.assertEqual(code, 3)
        self.assertIn("refused: personal identifier in comment, line 2; nothing was sent", err)
        self.no_leak(out, err)
        self.assertEqual(self.load()["comments"], [])

    def test_cle_de_ticket_inventee_dans_le_corps(self):
        code, out, err = self.new(conditions=f"attend {FAKE_KEY}")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"refused: ticket key in body, line \d+; nothing was sent")
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_cle_de_ticket_dans_un_commentaire_et_un_titre(self):
        self.add_feature(1)
        f = Path(self.tmp.name) / "c.txt"
        f.write_text(f"{FAKE_KEY}\n", encoding="utf-8")
        code, _, err = self.run_cli("comment", "R-1", "--body-file", str(f))
        self.assertEqual((code, "ticket key in comment, line 1" in err), (3, True))
        code, _, err = self.run_cli("edit", "R-1", "--title", f"suite de {FAKE_KEY.lower().upper()}")
        self.assertEqual((code, "ticket key in title" in err), (3, True))

    def test_les_identifiants_de_la_file_ne_sont_pas_refuses(self):
        code, out, err = self.new(conditions="après R-62 et R-7/g3, voir R-64")
        self.assertEqual(code, 0, err)
        self.assertIn("created R-1 (#1)", out)

    def test_motif_de_cle_exact(self):
        guard = g.Guard.load()
        for ok in ("R-62", "R-62/g1", "R2-12", "a-12", "AB12", "AB-x", "<!-- roadmap-id: R-3 -->"):
            guard.scan({"body": ok})
        for bad in ("AB-1", "xx AB-12 yy", "CODE-9999", "AB-12/g1"):
            with self.assertRaises(g.Stop) as c:
                guard.scan({"body": bad})
            self.assertEqual(c.exception.code, 3)

    def test_liste_absente(self):
        self.names.unlink()
        code, out, err = self.new()
        self.assertEqual(code, 4)
        self.assertIn("gh_issue: guard could not run: sensitive-names list absent", err)
        self.assertEqual(self.calls(), [])

    def test_liste_vide_ou_de_commentaires(self):
        self.names.write_text("# seulement un commentaire\n\n", encoding="utf-8")
        code, _, err = self.new()
        self.assertEqual(code, 4)
        self.assertIn("guard could not run: sensitive-names list empty", err)
        self.assertEqual(self.calls(), [])

    def test_echec_du_scanner(self):
        with mock.patch.object(g.identifiants_personnels, "identifiants", side_effect=SystemExit(2)):
            code, _, err = self.new()
        self.assertEqual(code, 4)
        self.assertIn("guard could not run: identifier scanner failed", err)
        self.assertEqual(self.calls(), [])

    def test_aucune_option_pour_passer_le_garde_fou(self):
        for opt in ("--no-guard", "--skip-guard", "--force"):
            code, _, err = self.run_cli("ensure-labels", opt)
            self.assertEqual(code, 2)
            self.assertIn("gh_issue: usage:", err)

    def test_une_trouvaille_refuse_toute_la_commande(self):
        self.add_feature(1, change="demo")
        tasks = (self.root / "openspec" / "changes" / "demo" / "tasks.md")
        tasks.write_text(TASKS.replace("## 3. User run [user]", f"## 3. Avec {NAME} [user]"), encoding="utf-8")
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name in R-1/g3 title, line 1", err)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])     # les groupes 1 et 2 n'ont pas été créés non plus
        self.assertEqual(len(self.load()["issues"]), 1)

    def test_la_sortie_ne_contient_jamais_le_texte_de_la_ligne(self):
        code, out, err = self.new(conditions=f"secret-bleu {NAME} secret-rouge")
        self.assertEqual(code, 3)
        self.no_leak(out, err, words=("secret-bleu", "secret-rouge", NAME))


# --- Dépôt et absence de suppression ------------------------------------------------------------------------------

class Depot(Base):
    def test_autre_depot_refuse_code_2(self):
        code, _, err = self.run_cli("ensure-labels", "--repo", "someone-else/other")
        self.assertEqual(code, 2)
        self.assertIn("gh_issue: usage:", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_depot_confirme_accepte(self):
        code, _, err = self.run_cli("ensure-labels", "--repo", "owner-x/repo-y")
        self.assertEqual(code, 0, err)

    def test_depot_resolu_depuis_origin_sans_repo_view(self):
        self.run_cli("ensure-labels")
        self.assertFalse(any(c["args"][:2] == ["repo", "view"] for c in self.calls()))
        self.assertTrue(all(any(a.startswith("repos/owner-x/repo-y/") for a in c["args"]) for c in self.calls()))

    def test_formes_d_url_de_origin(self):
        for url in ("git@github.com:owner-x/repo-y.git", "https://github.com/owner-x/repo-y.git", "https://github.com/owner-x/repo-y",
                    "ssh://git@github.com/owner-x/repo-y.git"):
            self.assertEqual(rm.repo_from_url(url), "owner-x/repo-y", url)
        for url in ("", "https://example.org/a/b", "nonsense"):
            self.assertIsNone(rm.repo_from_url(url), url)

    def test_pas_de_copie_locale_de_repo_from_url(self):
        src = (HERE.parents[1] / "tools" / "gh_issue.py").read_text(encoding="utf-8")
        self.assertNotIn("def repo_from_url", src)
        self.assertIn("rm.repo_from_url", src)

    def test_origin_introuvable_code_2(self):
        with mock.patch.object(g, "git_origin_url", lambda: ""):
            code, _, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 2)
        self.assertIn("origin", err)
        self.assertEqual(self.calls(), [])

    def test_texte_de_l_outil_sans_suppression(self):
        import io as _io
        import tokenize
        src = (HERE.parents[1] / "tools" / "gh_issue.py").read_text(encoding="utf-8")
        gardes = []
        for tok in tokenize.generate_tokens(_io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT,):
                continue
            gardes.append(tok.string)
        texte = " ".join(gardes)
        # les docstrings d'en-tête sont des chaînes : on les retire avant de chercher les verbes interdits
        corps = texte.split('"""', 2)[-1] if '"""' in texte else texte
        for interdit in ("/transfer", "releases", "git/refs", "git/tags", "deleteIssue", "deleteLabel", "deleteProject",
                         "/lock", "/pin", "lockLockable", "pinIssue", "transferIssue"):
            self.assertNotIn(interdit, corps, interdit)
        for ligne in src.splitlines():
            if '"DELETE"' in ligne:
                self.assertIn("blocked_by", ligne)     # seule suppression : une relation « blocked by »
        self.assertEqual(src.count('"DELETE"'), 1)
        self.assertNotIn("labels/", src.replace("issues/", ""))      # aucun chemin d'étiquette individuelle
        self.assertNotIn("milestones/{m['number']}\", {\"state\": \"open\"", src)
        # aucun code qui change un jalon existant : ni fonction de fermeture, ni requête PATCH sur milestones/
        self.assertNotIn("close_milestone", src)
        self.assertIsNone(re.search(r"PATCH[\"']\s*,\s*f?[\"']milestones/", src))
        self.assertNotIn("milestones/{", src)


# --- Création et édition des features -----------------------------------------------------------------------------

class Features(Base):
    def new(self, title="Une feature", **kw):
        argv = ["new-feature", "--title", title, "--theme", kw.pop("theme", "outillage"), "--milestone", kw.pop("milestone", "Hydra")]
        if "blocked_by" in kw:
            argv += ["--blocked-by", kw.pop("blocked_by")]
        for k, v in kw.items():
            argv += ["--set", f"{k}={v}"]
        return self.run_cli(*argv)

    def test_prochain_identifiant_parmi_toutes_les_issues(self):
        self.add_feature(60, state="closed", milestone="Tarasque")
        self.add_feature(64)
        self.add_issue("R-70/g1", "R-70 · 1. Groupe", ["type:task"])
        code, out, err = self.new()
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: created R-71 (#4)", out)

    def test_feature_creee_avec_tout(self):
        self.add_feature(5, rank=50)
        self.add_feature(6, rank=60)
        code, out, err = self.new("Titre neuf", theme="cas", estimate="2h", method="openspec", model="opus", conditions="à voir")
        self.assertEqual(code, 0, err)
        issue = self.issue("R-7")
        self.assertEqual(issue["title"], "R-7 · Titre neuf")
        self.assertEqual(sorted(l["name"] for l in issue["labels"]), ["theme:cas", "type:feature"])
        self.assertEqual(issue["milestone"]["title"], "Hydra")
        block = rm.parse_block(issue["body"])
        self.assertEqual((block["id"], block["theme"], block["estimate"], block["model"], block["rank"]), ("R-7", "cas", "2h", "opus", 70))
        self.assertEqual(rm.validate_block(block, marker_key="R-7"), [])
        self.assertEqual(rm.parse_marker(issue["body"]), "R-7")
        self.assertEqual(self.status_of("R-7"), "Todo")
        self.assertTrue({"type:feature", "theme:cas"} <= {l["name"] for l in self.load()["labels"]})

    def test_nouvelle_feature_apres_r64(self):
        self.add_feature(64, state="closed", milestone="Tarasque")
        code, out, _ = self.new("Suite")
        self.assertEqual(code, 0)
        self.assertEqual(self.issue("R-65")["title"], "R-65 · Suite")
        self.assertEqual(self.status_of("R-65"), "Todo")

    def test_blocked_by_a_la_creation(self):
        self.add_feature(1)
        self.new("Dépendante", blocked_by="R-1")
        self.assertEqual(self.load()["blocked"][str(self.number_of("R-2"))], [self.number_of("R-1")])

    def test_usage_theme_inconnu_et_jalon_inconnu(self):
        code, _, err = self.new(theme="nimporte")
        self.assertEqual(code, 2)
        code, _, err = self.new(milestone="Inconnu")
        self.assertEqual(code, 7)
        self.assertIn("unknown milestone", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_rang_deja_pris(self):
        self.add_feature(1, rank=10)
        code, _, err = self.new(rank=10)
        self.assertEqual(code, 7)
        self.assertIn("rank already used by R-1", err)

    def test_edit_titre_jalon_et_bloc(self):
        self.add_feature(1)
        code, out, err = self.run_cli("edit", "R-1", "--title", "Nouveau titre", "--milestone", "Namazu", "--set", "estimate=2h")
        self.assertEqual(code, 0, err)
        i = self.issue("R-1")
        self.assertEqual(i["title"], "R-1 · Nouveau titre")
        self.assertEqual(i["milestone"]["title"], "Namazu")
        self.assertEqual(rm.parse_block(i["body"])["estimate"], "2h")
        self.assertTrue(i["body"].startswith("<!-- roadmap-id: R-1 -->"))
        code, out, _ = self.run_cli("edit", "R-1", "--set", "estimate=2h")
        self.assertIn("nothing to do", out)

    def test_edit_vers_un_jalon_ferme_refuse_sur_une_feature_ouverte(self):
        self.add_feature(1)
        code, _, err = self.run_cli("edit", "R-1", "--milestone", "Tarasque")
        self.assertEqual(code, 7)
        self.assertIn("closed milestone", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_edit_theme_change_l_etiquette(self):
        self.add_feature(1)
        self.run_cli("edit", "R-1", "--set", "theme=cas")
        self.assertEqual(sorted(l["name"] for l in self.issue("R-1")["labels"]), ["theme:cas", "type:feature"])

    def test_edit_identifiant_inconnu_ou_bloc_invalide(self):
        code, _, err = self.run_cli("edit", "R-99", "--title", "x")
        self.assertEqual((code, "unknown identifier R-99" in err), (7, True))
        self.add_feature(1)
        code, _, err = self.run_cli("edit", "R-1", "--set", "estimate=bientôt")
        self.assertEqual((code, "invalid block: estimate" in err), (7, True))

    def test_status_en_cours_ecrit_started_on_une_fois(self):
        self.add_feature(1, status="Ready")
        code, out, _ = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 0)
        self.assertEqual(self.status_of("R-1"), "In progress")
        self.assertEqual(rm.parse_block(self.issue("R-1")["body"])["started_on"], "2026-10-12")
        with mock.patch.dict(os.environ, {"ROADMAP_TODAY": "2026-10-20"}):
            self.run_cli("status", "R-1", "Ready")
            self.run_cli("status", "R-1", "In progress")
        self.assertEqual(rm.parse_block(self.issue("R-1")["body"])["started_on"], "2026-10-12")
        code, out, _ = self.run_cli("status", "R-1", "In progress")
        self.assertIn("nothing to do", out)

    def test_estimation_nulle_refusee(self):
        self.add_feature(1)
        for est in ("0min", "0h"):
            code, _, err = self.run_cli("edit", "R-1", "--set", f"estimate={est}")
            self.assertEqual(code, 7, est)
            self.assertIn("estimate", err)

    def test_status_invalide(self):
        self.add_feature(1)
        code, _, err = self.run_cli("status", "R-1", "Blocked")
        self.assertEqual(code, 2)

    def test_commentaire(self):
        self.add_feature(1)
        f = Path(self.tmp.name) / "c.txt"
        f.write_text("branche feat/x, voir R-1\n", encoding="utf-8")
        code, out, _ = self.run_cli("comment", "R-1", "--body-file", str(f))
        self.assertEqual(code, 0)
        self.assertEqual(self.load()["comments"], [{"issue": self.number_of("R-1"), "body": "branche feat/x, voir R-1\n"}])


# --- Relations ----------------------------------------------------------------------------------------------------

class Relations(Base):
    def test_block_et_unblock(self):
        self.add_feature(1)
        self.add_feature(2)
        code, out, _ = self.run_cli("block", "R-2", "--by", "R-1")
        self.assertEqual(code, 0)
        self.assertEqual(self.load()["blocked"][str(self.number_of("R-2"))], [self.number_of("R-1")])
        self.assertIn("nothing to do", self.run_cli("block", "R-2", "--by", "R-1")[1])
        self.assertEqual(self.run_cli("unblock", "R-2", "--by", "R-1")[0], 0)
        self.assertEqual(self.load()["blocked"][str(self.number_of("R-2"))], [])
        self.assertIn("nothing to do", self.run_cli("unblock", "R-2", "--by", "R-1")[1])

    def test_cycle_refuse(self):
        self.add_feature(1)
        self.add_feature(2, blocked_by=[1])
        before = self.load()["blocked"]
        code, _, err = self.run_cli("block", "R-1", "--by", "R-2")
        self.assertEqual(code, 7)
        self.assertIn("dependency cycle: R-1 -> R-2 -> R-1", err)
        self.assertEqual(self.load()["blocked"], before)

    def test_cycle_indirect(self):
        self.add_feature(1)
        self.add_feature(2, blocked_by=[1])
        self.add_feature(3, blocked_by=[2])
        code, _, err = self.run_cli("block", "R-1", "--by", "R-3")
        self.assertEqual(code, 7)
        self.assertIn("dependency cycle: R-1 -> R-3 -> R-2 -> R-1", err)

    def test_relation_sur_soi_ou_cible_inconnue(self):
        self.add_feature(1)
        code, _, err = self.run_cli("block", "R-1", "--by", "R-1")
        self.assertEqual((code, "dependency cycle:" in err), (7, True))
        code, _, err = self.run_cli("block", "R-1", "--by", "R-9")
        self.assertEqual((code, "unknown identifier R-9" in err), (7, True))
        self.assertEqual(self.calls(writes_only=True), [])

    def test_une_sous_issue_n_est_pas_une_cible(self):
        self.add_feature(1)
        self.add_issue("R-1/g1", "R-1 · 1. Groupe", ["type:task"])
        code, _, err = self.run_cli("block", "R-1", "--by", "R-1/g1")
        self.assertEqual(code, 2)


# --- Synchronisation des tâches -----------------------------------------------------------------------------------

class Sync(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1, change="demo")

    def test_groupe_mixte_et_etiquettes(self):
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0, err)
        g1, g2, t22, g3 = (self.issue(k) for k in ("R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3"))
        labels = lambda i: sorted(l["name"] for l in i["labels"])
        self.assertEqual(labels(g1), ["model:haiku", "type:task"])
        self.assertEqual(labels(g2), ["model:sonnet", "parallel", "type:task"])
        self.assertEqual(labels(t22), ["owner:user", "type:task"])
        self.assertEqual(labels(g3), ["owner:user", "type:task"])
        self.assertEqual(g1["title"], "R-1 · 1. Inputs")
        self.assertEqual(t22["title"], "R-1 · 2.2 (user step)")
        self.assertEqual(self.load()["sub"][str(self.number_of("R-1"))], [g1["number"], g2["number"], t22["number"], g3["number"]])

    def test_corps_sans_texte_des_taches(self):
        self.run_cli("sync-tasks", "R-1")
        for k in ("R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3"):
            body = self.issue(k)["body"]
            for texte in ("Tests first", "Check by hand", "Run it", "First."):
                self.assertNotIn(texte, body)
            self.assertIn("Change: demo", body)

    def test_groupe_coche_ferme_seulement_lui(self):
        self.run_cli("sync-tasks", "R-1")
        self.assertEqual(self.issue("R-1/g1")["state"], "closed")
        self.assertEqual(self.issue("R-1/g1")["state_reason"], "completed")
        for k in ("R-1/g2", "R-1/t2.2", "R-1/g3"):
            self.assertEqual(self.issue(k)["state"], "open")

    def test_deuxieme_passage_ne_fait_rien(self):
        self.run_cli("sync-tasks", "R-1")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_tache_utilisateur_cochee_ferme_sa_sous_issue_puis_decochee_la_rouvre(self):
        self.run_cli("sync-tasks", "R-1")
        path = self.root / "openspec" / "changes" / "demo" / "tasks.md"
        path.write_text(TASKS.replace("- [ ] 2.2", "- [x] 2.2"), encoding="utf-8")
        self.run_cli("sync-tasks", "R-1")
        self.assertEqual(self.issue("R-1/t2.2")["state"], "closed")
        self.assertEqual(self.issue("R-1/g2")["state"], "closed")
        path.write_text(TASKS, encoding="utf-8")
        code, out, _ = self.run_cli("sync-tasks", "R-1")
        self.assertIn("reopened R-1/t2.2", out)
        self.assertEqual(self.issue("R-1/t2.2")["state"], "open")
        self.assertEqual(self.issue("R-1/g2")["state"], "open")

    def test_groupe_utilisateur_ne_se_ferme_pas_par_la_synchronisation(self):
        path = self.root / "openspec" / "changes" / "demo" / "tasks.md"
        path.write_text(TASKS.replace("- [ ] 3.1", "- [x] 3.1"), encoding="utf-8")
        code, out, _ = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(self.issue("R-1/g3")["state"], "open")
        self.assertIn("ready to close after your confirmation: R-1/g3", out)

    def test_groupe_sans_tag(self):
        path = self.root / "openspec" / "changes" / "demo" / "tasks.md"
        path.write_text(TASKS + "\n## 4. Sans tag\n\n- [ ] 4.1 x\n\n## 5. Autre\n\n- [ ] 5.1 y\n", encoding="utf-8")
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 7)
        self.assertIn("tasks.md groups untagged: 4, 5", err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(len(self.load()["issues"]), 1)

    def test_feature_sans_change_ou_change_introuvable(self):
        self.add_feature(2)
        code, _, err = self.run_cli("sync-tasks", "R-2")
        self.assertEqual(code, 7)
        self.add_feature(3, change="absent")
        code, _, err = self.run_cli("sync-tasks", "R-3")
        self.assertEqual((code, "tasks.md not found" in err), (7, True))

    def test_close_step(self):
        self.run_cli("sync-tasks", "R-1")
        code, out, _ = self.run_cli("close-step", "R-1/g3")
        self.assertEqual((code, self.issue("R-1/g3")["state"]), (0, "closed"))
        self.assertIn("nothing to do", self.run_cli("close-step", "R-1/g3")[1])
        self.assertEqual(self.run_cli("close-step", "R-1")[0], 2)
        self.assertEqual(self.run_cli("close-step", "R-1/g9")[0], 7)

    def test_close_step_refuse_une_sous_issue_sans_owner_user(self):
        self.run_cli("sync-tasks", "R-1")
        n = len(self.calls(writes_only=True))
        code, _, err = self.run_cli("close-step", "R-1/g2")
        self.assertEqual(code, 7)
        self.assertIn("gh_issue: R-1/g2 is an agent sub-issue; close it with --reason after the user's confirmation", err)
        self.assertEqual(self.issue("R-1/g2")["state"], "open")
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_sync_refuse_un_change_archive(self):
        arch = self.root / "openspec" / "changes" / "archive" / "2026-10-11-old"
        arch.mkdir(parents=True)
        (arch / "tasks.md").write_text(TASKS, encoding="utf-8")
        self.add_feature(2, change="old")
        code, _, err = self.run_cli("sync-tasks", "R-2")
        self.assertEqual(code, 7)
        self.assertIn("change archived", err)
        self.assertEqual(self.calls(writes_only=True), [])


# --- Fermeture d'une feature --------------------------------------------------------------------------------------

class Fermeture(Base):
    def test_refus_tant_qu_une_sous_issue_est_ouverte(self):
        self.add_feature(1, change="demo", status="In progress")
        self.run_cli("sync-tasks", "R-1")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 7)
        self.assertIn("open sub-issues remain: R-1/g2, R-1/g3, R-1/t2.2", err)
        self.assertEqual(self.issue("R-1")["state"], "open")
        self.assertEqual(self.status_of("R-1"), "In progress")

    def test_fermeture_complete_et_debloquees(self):
        self.add_feature(1, change="demo", status="In progress")
        self.add_feature(2, status="Todo", blocked_by=[1])
        self.add_feature(3, status="Todo", blocked_by=[1, 2])
        self.run_cli("sync-tasks", "R-1")
        path = self.root / "openspec" / "changes" / "demo" / "tasks.md"
        path.write_text(TASKS.replace("- [ ]", "- [x]"), encoding="utf-8")
        self.run_cli("sync-tasks", "R-1")
        self.run_cli("close-step", "R-1/g3")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        i = self.issue("R-1")
        self.assertEqual((i["state"], i["state_reason"]), ("closed", "completed"))
        self.assertEqual(rm.parse_block(i["body"])["done_on"], "2026-10-12")
        self.assertEqual(self.status_of("R-1"), "Done")
        self.assertIn("unblocked: R-2", out)
        self.assertNotIn("R-3", out)
        self.assertEqual(self.status_of("R-2"), "Todo")
        self.assertEqual(self.issue("R-2")["state"], "open")

    def test_feature_sans_sous_issue_se_ferme(self):
        self.add_feature(1, status="Ready")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        self.assertIn("unblocked: none", out)
        self.assertIn("nothing to do", self.run_cli("close-feature", "R-1")[1])

    def test_refus_du_garde_avant_toute_ecriture(self):
        self.add_feature(1, change="demo", status="In progress", conditions=f"{NAME} attend")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 3)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(len(self.load()["issues"]), 1)        # aucune sous-issue créée par la synchronisation
        self.no_leak(out, err)

    def test_change_archive_ne_bloque_pas(self):
        arch = self.root / "openspec" / "changes" / "archive" / "2026-10-11-old"
        arch.mkdir(parents=True)
        (arch / "tasks.md").write_text("# Tasks\n\n## 1. Sans tag\n\n- [x] 1.1 a\n", encoding="utf-8")
        self.add_feature(1, change="old", status="In progress")
        code, _, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)


# --- Idempotence --------------------------------------------------------------------------------------------------

class Idempotence(Base):
    def test_etiquettes_et_jalons_deja_la(self):
        code, out, _ = self.run_cli("ensure-labels")
        self.assertIn("created 18 label(s)", out)
        n = len(self.calls(writes_only=True))
        self.assertIn("nothing to do", self.run_cli("ensure-labels")[1])
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertIn("created milestone Kraken", self.run_cli("ensure-milestone", "Kraken")[1])
        self.assertIn("nothing to do", self.run_cli("ensure-milestone", "Kraken")[1])
        self.assertIn("nothing to do", self.run_cli("ensure-milestone", "Tarasque", "--closed")[1])

    def test_jalon_ferme_a_la_creation(self):
        self.run_cli("ensure-milestone", "Vieux", "--closed")
        self.assertEqual(next(m for m in self.load()["milestones"] if m["title"] == "Vieux")["state"], "closed")

    def test_issue_existante_non_recreee(self):
        self.add_feature(1)
        client = g.Client(g.Guard.load())
        snap = g.load_snapshot(client)
        issue, created = g.create_issue(client, snap, "R-1", "R-1 · x", rm.marker("R-1"), ["type:feature"])
        self.assertFalse(created)
        self.assertEqual(issue["number"], 1)
        self.assertEqual(self.calls(writes_only=True), [])


# --- Idées (change single-tracking-github, design D7) -------------------------------------------------------------

class Idees(Base):
    def idea(self, title="Une idée à suivre", body="Résumé court."):
        return self.run_cli("new-idea", "--title", title, "--body", body)

    def ideas(self):
        return [i for i in self.load()["issues"] if "<!-- roadmap-idea:" in i["body"]]

    def test_creation(self):
        code, out, err = self.idea("Éviter les Listes Vides !", "Un résumé.")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: created idea eviter-les-listes-vides (#1)", out)
        (issue,) = self.ideas()
        self.assertEqual(issue["title"], "Éviter les Listes Vides !")
        self.assertEqual([l["name"] for l in issue["labels"]], ["type:idea"])
        self.assertEqual(issue["body"], "<!-- roadmap-idea: eviter-les-listes-vides -->\n\nUn résumé.")
        self.assertIsNone(issue["milestone"])
        self.assertEqual(issue["state"], "open")

    def test_etiquette_creee_quand_elle_manque_sinon_non(self):
        self.idea()
        self.assertIn("type:idea", {l["name"] for l in self.load()["labels"]})
        posts = [c for c in self.calls(writes_only=True) if c["args"][-3].endswith("/labels")]
        self.assertEqual([json.loads(c["stdin"])["name"] for c in posts], ["type:idea"])
        self.idea("Une autre idée")
        posts = [c for c in self.calls(writes_only=True) if c["args"][-3].endswith("/labels")]
        self.assertEqual(len(posts), 1)

    def test_ni_jalon_ni_project_ni_statut(self):
        self.idea()
        for c in self.calls():
            self.assertNotIn("graphql", c["args"])
            self.assertFalse(any("/milestones" in a for a in c["args"]))
        issue_posts = [json.loads(c["stdin"]) for c in self.calls(writes_only=True) if c["args"][-3].endswith("/issues")]
        self.assertEqual(len(issue_posts), 1)
        self.assertNotIn("milestone", issue_posts[0])
        self.assertEqual(self.load()["project"]["items"], [])
        self.assertNotIn("```roadmap", self.ideas()[0]["body"])
        self.assertNotIn("roadmap-id:", self.ideas()[0]["body"])
        self.assertEqual(self.load().get("sub", {}), {})

    def test_regle_du_slug(self):
        cas = {"Ça marche  très bien": "ca-marche-tres-bien", "(A/B_c)": "a-b-c", "Déjà 2 fois": "deja-2-fois"}
        for titre, slug in cas.items():
            code, out, err = self.idea(titre)
            self.assertEqual(code, 0, err)
            self.assertIn(f"created idea {slug} (#", out)
            self.assertIn(f"<!-- roadmap-idea: {slug} -->", [i for i in self.ideas() if i["title"] == titre][0]["body"])

    def test_idempotence_ouverte_ou_fermee(self):
        self.idea("Même idée")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.idea("même  IDÉE", "Autre résumé.")
        self.assertEqual(code, 0)
        self.assertIn("gh_issue: already exists: idea meme-idee (#1)", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.st = self.load()
        self.st["issues"][0]["state"] = "closed"
        self.save()
        code, out, _ = self.idea("Même idée")
        self.assertEqual(code, 0)
        self.assertIn("already exists: idea meme-idee (#1)", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertEqual(len(self.ideas()), 1)

    def test_refus_du_garde_rien_n_est_envoye(self):
        for titre, corps, champ in ((f"Idée {NAME}", "ok", "title"), ("Idée", f"voir {NAME}", "body"),
                                    ("Idée", f"clé {FAKE_KEY}", "body"), (f"Idée {IDENT}", "ok", "title")):
            code, out, err = self.idea(titre, corps)
            self.assertEqual(code, 3, err)
            self.assertRegex(err, rf"gh_issue: refused: .* in {champ}, line \d+; nothing was sent")
            self.no_leak(out, err)
        self.assertEqual(self.calls(), [])

    def test_garde_impossible_code_4(self):
        self.names.unlink()
        code, _, err = self.idea()
        self.assertEqual(code, 4)
        self.assertIn("guard could not run", err)
        self.assertEqual(self.calls(), [])

    def test_usage_code_2(self):
        for argv in (["new-idea", "--body", "x"], ["new-idea", "--title", "x"], ["new-idea", "--title", "x", "--body", "  "],
                     ["new-idea", "--title", "!!! ???", "--body", "x"], ["new-idea", "--title", "", "--body", "x"]):
            code, out, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("gh_issue: usage:", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_les_idees_ne_changent_pas_le_prochain_identifiant(self):
        self.add_feature(64)
        self.idea("Une idée")
        self.idea("R-90 : une idée au titre trompeur")
        code, out, err = self.run_cli("new-feature", "--title", "Suite", "--theme", "outillage", "--milestone", "Hydra")
        self.assertEqual(code, 0, err)
        self.assertIn("created R-65 (#4)", out)

    def test_ensure_labels_cree_l_etiquette_des_idees(self):
        self.run_cli("ensure-labels")
        self.assertIn("type:idea", {l["name"] for l in self.load()["labels"]})


# --- Valeur et jalon des idées (#184) -----------------------------------------------------------------------------

class ValeurEtJalonDesIdees(Base):
    def idea(self, title="Une idée à suivre", body="Résumé court."):
        return self.run_cli("new-idea", "--title", title, "--body", body)

    def ideas(self):
        return [i for i in self.load()["issues"] if "<!-- roadmap-idea:" in i["body"]]

    def labels_of(self, n):
        return [l["name"] for l in self.load()["issues"][n - 1]["labels"]]

    def test_new_idea_avec_jalon_et_valeur(self):
        code, out, err = self.run_cli("new-idea", "--title", "Idée chiffrée", "--body", "Résumé.", "--milestone", "Hydra", "--value", "2")
        self.assertEqual(code, 0, err)
        (issue,) = self.ideas()
        self.assertEqual(issue["milestone"]["title"], "Hydra")
        self.assertEqual(sorted(l["name"] for l in issue["labels"]), ["type:idea", "value:2"])
        self.assertIn("value:2", {l["name"] for l in self.load()["labels"]})

    def test_new_idea_jalon_inconnu_ou_valeur_invalide(self):
        code, _, err = self.run_cli("new-idea", "--title", "A", "--body", "x", "--milestone", "Inconnu")
        self.assertEqual(code, 7)
        self.assertIn("unknown milestone", err)
        code, _, err = self.run_cli("new-idea", "--title", "A", "--body", "x", "--value", "4")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_edit_idea_change_jalon_et_valeur(self):
        self.idea()
        code, out, err = self.run_cli("edit-idea", "1", "--milestone", "Namazu", "--value", "1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.load()["issues"][0]["milestone"]["title"], "Namazu")
        self.assertEqual(sorted(self.labels_of(1)), ["type:idea", "value:1"])
        code, out, err = self.run_cli("edit-idea", "#1", "--value", "3")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(self.labels_of(1)), ["type:idea", "value:3"])
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit-idea", "1", "--value", "3", "--milestone", "Namazu")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_edit_idea_sans_option_ou_jalon_inconnu(self):
        self.idea()
        self.assertEqual(self.run_cli("edit-idea", "1")[0], 2)
        self.assertEqual(self.run_cli("edit-idea", "1", "--milestone", "Inconnu")[0], 7)

    def test_edit_idea_refuse_une_feature(self):
        self.add_feature(5)
        self.assertEqual(self.run_cli("edit-idea", "1", "--value", "1")[0], 7)
        self.assertEqual(self.calls(writes_only=True), [])


# --- Hors ligne, scope, refus de GitHub ---------------------------------------------------------------------------

class Reseau(Base):
    def mode(self, **m):
        self.st["mode"] = m
        self.save()

    def new(self):
        return self.run_cli("new-feature", "--title", "T", "--theme", "outillage", "--milestone", "Hydra")

    def test_injoignable_code_5_sans_file_d_attente(self):
        self.mode(offline=True)
        avant = sorted(p.name for p in Path(self.tmp.name).rglob("*"))
        code, out, err = self.new()
        self.assertEqual(code, 5)
        self.assertIn("gh_issue: GitHub unreachable; nothing was sent", err)
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).rglob("*")), avant)
        self.assertEqual(self.load()["issues"], [])

    def test_non_authentifie_code_5(self):
        self.mode(unauth=True)
        code, _, err = self.new()
        self.assertEqual(code, 5)
        self.assertIn("not authenticated; run gh auth login in the Terminal", err)

    def test_scope_project_manquant_code_6(self):
        self.mode(scope_missing=True)
        code, _, err = self.new()
        self.assertEqual(code, 6)
        self.assertIn("gh auth refresh -s project", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_project_absent_ou_option_manquante_code_6(self):
        self.st["project"]["options"] = [o for o in OPTIONS if o["name"] != "Ready"]
        self.save()
        code, _, err = self.new()
        self.assertEqual(code, 6)
        self.assertIn("Project not found or Status options incomplete", err)
        self.st["project"] = None
        self.save()
        self.assertEqual(self.new()[0], 6)
        self.assertEqual(self.load()["issues"], [])

    def test_refus_de_github_code_1_sans_texte_envoye(self):
        self.mode(reject_writes=True)
        code, out, err = self.run_cli("new-feature", "--title", "secret-bleu", "--theme", "outillage", "--milestone", "Hydra")
        self.assertEqual(code, 1)
        self.assertIn("gh_issue: GitHub refused: gh: Validation Failed (HTTP 422)", err)
        self.no_leak(out, err, words=("secret-bleu",))

    def test_limite_secondaire_attente_d_au_moins_60_s(self):
        self.mode(rate_limit_once=True)            # Retry-After: 1
        code, out, err = self.run_cli("ensure-milestone", "Kraken")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sleeps, [60])

    def test_limite_secondaire_sans_en_tete(self):
        self.mode(rate_limit_once={"bare": True})
        self.assertEqual(self.run_cli("ensure-milestone", "Kraken")[0], 0)
        self.assertEqual(self.sleeps, [60])

    def test_limite_primaire_lit_x_ratelimit_reset(self):
        self.mode(rate_limit_once={"reset": 1030})
        with mock.patch.object(g, "now", lambda: 1000):
            code, out, err = self.run_cli("ensure-milestone", "Kraken")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sleeps, [31])

    def test_pause_apres_toute_ecriture(self):
        self.add_feature(1, change="demo")
        self.run_cli("sync-tasks", "R-1")
        self.sleeps.clear()
        with mock.patch.dict(os.environ, {"PMZILLA_GH_PAUSE": "0.5"}):
            self.assertEqual(self.run_cli("close-step", "R-1/g3")[0], 0)      # une seule écriture : fermeture
            self.assertEqual(self.sleeps, [0.5])
            self.sleeps.clear()
            self.assertEqual(self.run_cli("comment", "R-1", "--body-file", str(self.root / "openspec" / "changes" / "demo" / "tasks.md"))[0], 0)
            self.assertEqual(self.sleeps, [0.5])

    def test_message_de_gh_avec_identifiant_retenu(self):
        for secret in (IDENT, NAME):
            self.mode(reject_writes=True, reject_message=f"gh: {secret}/depot Validation Failed (HTTP 422)")
            code, out, err = self.new()
            self.assertEqual(code, 1)
            self.assertIn("gh_issue: GitHub refused: HTTP 422 (message withheld)", err)
            self.no_leak(out, err)

    def test_message_de_gh_propre_conserve(self):
        self.mode(reject_writes=True, reject_message="gh: Validation Failed (HTTP 422)")
        self.assertIn("GitHub refused: gh: Validation Failed (HTTP 422)", self.new()[2])

    def test_usage(self):
        for argv in ([], ["inconnue"], ["edit"], ["status", "R-1"], ["new-feature", "--title", "x"]):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertTrue(err.startswith("gh_issue: usage:"), (argv, err))


# --- Appels bornés, classement des échecs, état inconnu, visibilité ---------------------------------------------------

class Bornes(Base):
    SHOW = "uv run --with pyyaml python tools/roadmap.py show"

    def setUp(self):
        super().setUp()
        p = mock.patch.dict(os.environ, {"PMZILLA_GH_TIMEOUT": "1"})
        p.start()
        self.addCleanup(p.stop)

    def mode(self, **m):
        self.st = self.load()
        self.st["mode"] = m
        self.save()

    def seed_labels(self):
        self.st = self.load()
        self.st["labels"] = [{"name": l} for l in rm.all_labels()]
        self.save()

    def new(self):
        return self.run_cli("new-feature", "--title", "T", "--theme", "outillage", "--milestone", "Hydra")

    # --- délais, entrée standard

    def test_lecture_sans_reponse_code_5_avant_toute_ecriture(self):
        self.add_feature(1, change="demo")
        self.mode(hang_reads=True)
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 5)
        self.assertIn("gh_issue: GitHub unreachable (no answer within 1 s); nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_ecriture_sans_reponse_code_8_sans_nouvel_envoi(self):
        self.add_feature(1, change="demo")
        self.assertEqual(self.run_cli("sync-tasks", "R-1")[0], 0)
        avant = len(self.calls(writes_only=True))
        self.mode(hang_writes_after=0)
        code, out, err = self.run_cli("close-step", "R-1/g3")
        self.assertEqual(code, 8)
        self.assertIn("gh_issue: state unknown: 0 write(s) confirmed, the last write got no answer; "
                      f"check with {self.SHOW} R-1 before running the command again", err)
        self.assertNotIn("nothing was sent", out + err)
        self.assertEqual(len(self.calls(writes_only=True)), avant + 1)       # la demande sans réponse, jamais renvoyée
        self.assertEqual(self.issue("R-1/g3")["state"], "open")

    def test_ecriture_sans_reponse_apres_ecritures_confirmees(self):
        self.seed_labels()
        client = g.Client(g.Guard.load())
        client.target = "R-1"
        client.send("POST", "labels", {"name": "x1"}, {})
        client.send("POST", "labels", {"name": "x2"}, {})
        self.mode(hang_writes_after=0)
        with self.assertRaises(g.Stop) as c:
            client.send("POST", "labels", {"name": "x3"}, {})
        self.assertEqual(c.exception.code, 8)
        self.assertIn("state unknown: 2 write(s) confirmed, the last write got no answer", c.exception.lines[0])

    def test_une_seule_demande_d_ecriture_apres_un_delai(self):
        self.seed_labels()
        self.mode(hang_writes_after=0)
        code, _, _ = self.run_cli("ensure-milestone", "Kraken")
        self.assertEqual(code, 8)
        self.assertEqual(len(self.calls(writes_only=True)), 1)

    def test_commande_sans_feature_conseille_de_rejouer(self):
        self.mode(hang_writes_after=0)
        code, _, err = self.run_cli("ensure-milestone", "Kraken")
        self.assertEqual(code, 8)
        self.assertIn("run the same command again, it is idempotent", err)
        self.assertNotIn("roadmap.py", err)

    def test_limite_de_debit_au_dessus_du_plafond(self):
        self.mode(rate_limit_always=500)
        code, out, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 5)
        self.assertIn("gh_issue: GitHub rate limit: 500 s to wait is over the allowed wait; nothing was sent", err)
        self.assertEqual(self.sleeps, [])

    def test_attentes_cumulees_bornees_par_commande(self):
        self.mode(rate_limit_always=70)
        code, _, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 5)
        self.assertEqual(self.sleeps, [70])            # 70 + 70 depasse 120 : pas de seconde attente
        self.assertIn("nothing was sent", err)

    def test_plafond_configurable(self):
        self.mode(rate_limit_always=70)
        with mock.patch.dict(os.environ, {"PMZILLA_GH_MAX_WAIT": "10"}):
            code, _, err = self.run_cli("ensure-labels")
        self.assertEqual((code, self.sleeps), (5, []))

    def test_limite_de_debit_apres_une_ecriture_code_8(self):
        self.seed_labels()
        self.mode(rate_limit_after_writes=[1, 500])
        code, out, err = self.new()
        self.assertEqual(code, 8)
        self.assertIn("state unknown: GitHub unreachable after 1 confirmed write(s); "
                      f"check with {self.SHOW} R-1, then run the same command again", err)
        self.assertNotIn("nothing was sent", out + err)

    # --- classement sans en-têtes

    def test_en_tetes_avec_scope_project_sur_un_404_reste_code_1(self):
        self.add_feature(1, status="In progress")
        self.mode(refuse_after_writes=0)
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 1)
        self.assertIn("gh_issue: GitHub refused:", err)
        self.assertNotIn("missing token scope project", err)
        self.assertNotIn("auth refresh", err)

    def test_refus_apres_ecritures_confirmees_ajoute_une_ligne(self):
        self.add_feature(1, status="In progress")
        self.mode(refuse_after_writes=1)
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 1)
        lignes = err.splitlines()
        self.assertTrue(lignes[0].startswith("gh_issue: GitHub refused:"), err)
        self.assertEqual(lignes[1], f"gh_issue: 1 write(s) were confirmed before this failure; check with {self.SHOW} R-1")
        self.assertEqual(len(lignes), 2)

    def test_pas_de_seconde_ligne_sans_ecriture_confirmee(self):
        self.mode(reject_writes=True)
        code, _, err = self.new()
        self.assertEqual(code, 1)
        self.assertEqual(len(err.splitlines()), 1)

    def test_vraie_erreur_de_scope_graphql_code_6(self):
        self.mode(graphql_insufficient=True)
        code, _, err = self.new()
        self.assertEqual(code, 6)
        self.assertIn("gh auth refresh -s project", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_erreur_de_scope_apres_ecritures_ajoute_une_ligne(self):
        self.seed_labels()
        client = g.Client(g.Guard.load())
        client.target = "R-1"
        client.send("POST", "labels", {"name": "x1"}, {})
        self.mode(graphql_insufficient=True)
        with mock.patch.object(g, "Client", lambda guard: client):
            code, _, err = self.new()
        self.assertEqual(code, 6)
        self.assertIn("1 write(s) were confirmed before this failure", err.splitlines()[-1])

    def test_reseau_perdu_avant_toute_ecriture_reste_code_5(self):
        self.mode(offline=True)
        code, _, err = self.new()
        self.assertEqual(code, 5)
        self.assertIn("GitHub unreachable; nothing was sent", err)

    def test_reseau_perdu_apres_une_ecriture_code_8(self):
        self.seed_labels()
        self.mode(offline_after_writes=1)
        code, out, err = self.new()
        self.assertEqual(code, 8)
        self.assertIn(f"gh_issue: state unknown: GitHub unreachable after 1 confirmed write(s); check with {self.SHOW} R-1", err)
        self.assertNotIn("nothing was sent", out + err)

    def test_reseau_perdu_apres_deux_ecritures(self):
        self.seed_labels()
        client = g.Client(g.Guard.load())
        client.target = "R-4"
        client.send("POST", "labels", {"name": "x1"}, {})
        client.send("POST", "labels", {"name": "x2"}, {})
        self.mode(offline=True)
        with self.assertRaises(g.Stop) as c:
            client.get("issues")
        self.assertEqual(c.exception.code, 8)
        self.assertIn("state unknown: GitHub unreachable after 2 confirmed write(s)", c.exception.lines[0])
        self.assertIn(f"{self.SHOW} R-4", c.exception.lines[0])

    # --- visibilité d'une feature créée

    def test_liste_en_retard_la_feature_est_vue_a_la_troisieme_lecture(self):
        self.seed_labels()
        self.mode(hide_new_reads=2)
        code, out, err = self.new()
        self.assertEqual(code, 0, err)
        self.assertIn("created R-1 (#1)", out)
        self.assertEqual(self.sleeps, [1, 2])
        self.assertEqual(self.status_of("R-1"), "Todo")
        self.assertEqual(len([i for i in self.load()["issues"]]), 1)

    def test_feature_jamais_listee_code_8_sans_seconde_creation(self):
        self.seed_labels()
        self.mode(hide_new_reads=50)
        code, out, err = self.new()
        self.assertEqual(code, 8)
        self.assertIn(f"gh_issue: state unknown: created R-1 (#1) but GitHub does not list it yet; wait before the next "
                      f"new-feature, then check with {self.SHOW} R-1", err)
        self.assertEqual(self.sleeps, [1, 2, 4, 8])
        self.assertEqual(len(self.load()["issues"]), 1)
        self.assertNotIn("nothing was sent", out + err)

    def test_ajout_au_project_rejoue_sur_noeud_non_resolu(self):
        self.seed_labels()
        self.mode(node_unresolved_adds=2)
        code, out, err = self.new()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sleeps, [1, 2])
        self.assertEqual(self.status_of("R-1"), "Todo")

    def test_ajout_au_project_jamais_resolu_code_1(self):
        self.seed_labels()
        self.mode(node_unresolved_adds=10)
        code, _, err = self.new()
        self.assertEqual(code, 1)
        self.assertEqual(self.sleeps, [1, 2, 4, 8])
        self.assertIn("write(s) were confirmed before this failure", err)

    def test_identifiant_au_dessus_du_plus_haut_connu_vu_a_la_deuxieme_lecture(self):
        self.add_feature(1)
        self.st = self.load()
        self.st["issues"][0]["hidden_reads"] = 1
        self.save()
        code, out, err = self.run_cli("edit", "R-1", "--title", "Nouveau")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.sleeps, [1])
        self.assertEqual(self.issue("R-1")["title"], "R-1 · Nouveau")

    def test_identifiant_au_dessus_jamais_liste_est_inconnu_apres_les_essais(self):
        self.add_feature(5)
        code, _, err = self.run_cli("edit", "R-9", "--title", "x")
        self.assertEqual(code, 7)
        self.assertIn("unknown identifier R-9", err)
        self.assertEqual(self.sleeps, [1, 2, 4, 8])

    def test_identifiant_sous_le_plus_haut_echoue_aussitot(self):
        self.add_feature(5)
        code, _, err = self.run_cli("edit", "R-3", "--title", "x")
        self.assertEqual(code, 7)
        self.assertIn("unknown identifier R-3", err)
        self.assertEqual(self.sleeps, [])


# --- Jalon des sous-issues (D11) ----------------------------------------------------------------------------------

class JalonDesSousIssues(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1, change="demo")
        self.keys = ["R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3"]

    def test_creees_avec_le_jalon_de_la_feature(self):
        self.assertEqual(self.run_cli("sync-tasks", "R-1")[0], 0)
        self.assertEqual([self.milestone_of(k) for k in self.keys], ["Hydra"] * 4)
        creations = [json.loads(c["stdin"]) for c in self.calls(writes_only=True) if "POST" in c["args"]
                     and c["args"][-3].endswith("/issues")]
        self.assertTrue(creations and all(c["milestone"] == 1 for c in creations))

    def test_ancienne_sous_issue_sans_jalon_realignee_puis_rien_a_faire(self):
        self.run_cli("sync-tasks", "R-1")
        st = self.load()
        for i in st["issues"]:
            if "/" in i["body"].split("-->")[0]:
                i["milestone"] = None
        self.st = st
        self.save()
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual([self.milestone_of(k) for k in self.keys], ["Hydra"] * 4)     # la sous-issue fermée comprise
        self.assertEqual(self.issue("R-1/g1")["state"], "closed")
        self.assertNotIn("nothing to do", out)
        code, out, _ = self.run_cli("sync-tasks", "R-1")
        self.assertIn("nothing to do", out)

    def test_jalon_different_realigne(self):
        self.run_cli("sync-tasks", "R-1")
        st = self.load()
        next(i for i in st["issues"] if i["body"].startswith("<!-- roadmap-id: R-1/g2")).update(milestone={"title": "Namazu", "number": 2})
        self.st = st
        self.save()
        self.run_cli("sync-tasks", "R-1")
        self.assertEqual(self.milestone_of("R-1/g2"), "Hydra")

    def test_edit_jalon_deplace_aussi_les_sous_issues(self):
        self.run_cli("sync-tasks", "R-1")
        code, out, err = self.run_cli("edit", "R-1", "--milestone", "Namazu")
        self.assertEqual(code, 0, err)
        self.assertEqual([self.milestone_of(k) for k in ["R-1", *self.keys]], ["Namazu"] * 5)
        self.assertIn("moved 4 sub-issue(s) to Namazu", out)

    def test_edit_vers_un_jalon_ferme_ne_deplace_rien(self):
        self.run_cli("sync-tasks", "R-1")
        n = len(self.calls(writes_only=True))
        code, _, err = self.run_cli("edit", "R-1", "--milestone", "Tarasque")
        self.assertEqual(code, 7)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_edit_refus_du_garde_avant_toute_ecriture(self):
        self.run_cli("sync-tasks", "R-1")
        n = len(self.calls(writes_only=True))
        code, _, _ = self.run_cli("edit", "R-1", "--milestone", "Namazu", "--set", f"conditions=voir {NAME}")
        self.assertEqual(code, 3)
        self.assertEqual(len(self.calls(writes_only=True)), n)


# --- Release en cours (D12) ---------------------------------------------------------------------------------------

class ReleaseEnCours(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1, change="demo", status="Ready")
        self.run_cli("sync-tasks", "R-1")

    def test_release_configuree_deplace_la_feature_et_ses_sous_issues(self):
        self.set_release("Namazu")
        code, out, err = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: moved R-1 and 4 sub-issue(s) to Namazu", out)
        self.assertEqual([self.milestone_of(k) for k in ("R-1", "R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3")], ["Namazu"] * 5)
        self.assertEqual(self.status_of("R-1"), "In progress")

    def test_le_deplacement_precede_le_statut(self):
        self.set_release("Namazu")
        self.run_cli("status", "R-1", "In progress")
        ecritures = self.calls(writes_only=True)
        dernier_jalon = max(k for k, c in enumerate(ecritures) if "PATCH" in c["args"] and "milestone" in c["stdin"])
        statut = next(k for k, c in enumerate(ecritures) if "graphql" in c["args"] and "updateProjectV2ItemFieldValue" in c["stdin"])
        self.assertLess(dernier_jalon, statut)

    def test_deja_dans_la_release_aucune_demande_de_deplacement(self):
        self.set_release("Hydra")
        n = len(self.milestone_writes())
        code, out, _ = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.milestone_writes()), n)
        self.assertNotIn("moved", out)
        self.assertEqual(self.status_of("R-1"), "In progress")

    def test_seules_les_sous_issues_en_retard_bougent(self):
        self.set_release("Hydra")
        st = self.load()
        next(i for i in st["issues"] if i["body"].startswith("<!-- roadmap-id: R-1/g2")).update(milestone=None)
        self.st = st
        self.save()
        n = len(self.milestone_writes())
        code, out, _ = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(len(self.milestone_writes()), n + 1)
        self.assertIn("moved 1 sub-issue(s) of R-1 to Hydra", out)
        self.assertEqual(self.milestone_of("R-1/g2"), "Hydra")

    def test_aucune_release_message_et_statut(self):
        self.set_release("")
        code, out, _ = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 0)
        self.assertIn("gh_issue: no current release; milestone unchanged", out)
        self.assertEqual(self.status_of("R-1"), "In progress")
        self.assertEqual(self.milestone_of("R-1"), "Hydra")

    def test_fichier_de_reglages_absent_vaut_aucune_release(self):
        code, out, _ = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 0)
        self.assertIn("no current release; milestone unchanged", out)

    def test_release_fermee_code_7_sans_ecriture(self):
        self.set_release("Tarasque")
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 7)
        self.assertIn("gh_issue: current release Tarasque is not an open milestone; nothing was sent", err)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertEqual(self.status_of("R-1"), "Ready")

    def test_release_inconnue_code_7_sans_ecriture(self):
        self.set_release("Absente")
        n = len(self.calls(writes_only=True))
        code, _, err = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 7)
        self.assertIn("current release Absente is not an open milestone; nothing was sent", err)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_reglages_illisibles_code_7_sans_ecriture(self):
        path = self.root / rm.SETTINGS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("autre: 1\n", encoding="utf-8")
        n = len(self.calls(writes_only=True))
        code, _, err = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 7)
        self.assertIn("is invalid; nothing was sent", err)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_les_autres_statuts_ne_lisent_pas_la_release(self):
        self.set_release("Tarasque")
        code, _, err = self.run_cli("status", "R-1", "Todo")
        self.assertEqual(code, 0, err)


# --- Fermeture : commentaire de clôture (D9) et close-step avec raison (D10) -------------------------------------

class CommentaireDeCloture(Base):
    def comments(self):
        return self.load()["comments"]

    def test_commentaire_nomme_la_branche_avant_la_fermeture(self):
        self.add_feature(1, status="In progress")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        cs = self.comments()
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]["body"], "<!-- roadmap-close -->\nClosed on branch chore/r65-fixes, before the merge; "
                                       "the user merges with bash tools/finish_branch.sh.")
        ecritures = self.calls(writes_only=True)
        idx = lambda pred: next(k for k, c in enumerate(ecritures) if pred(c))
        statut = idx(lambda c: "updateProjectV2ItemFieldValue" in (c["stdin"] or ""))
        commentaire = idx(lambda c: c["args"][-3].endswith("/comments"))
        fermeture = idx(lambda c: "PATCH" in c["args"] and '"state": "closed"' in c["stdin"])
        self.assertLess(statut, commentaire)
        self.assertLess(commentaire, fermeture)
        self.assertEqual((self.issue("R-1")["state"], self.issue("R-1")["state_reason"]), ("closed", "completed"))

    def test_deuxieme_passage_rien_a_faire_pas_de_commentaire(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("close-feature", "R-1")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_rejeu_poste_le_commentaire_manquant_sur_une_feature_deja_fermee(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1")
        self.st = self.load()
        self.st["comments"] = []          # première exécution interrompue entre la fermeture et le commentaire
        self.save()
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        self.assertNotIn("nothing to do", out)
        self.assertEqual([c["body"].splitlines()[0] for c in self.comments()], ["<!-- roadmap-close -->"])
        self.assertEqual((self.issue("R-1")["state"], self.issue("R-1")["state_reason"]), ("closed", "completed"))
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("close-feature", "R-1")      # troisième passage : plus rien à faire, aucun doublon
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_tete_detachee(self):
        self.head = (None, "abc1234")
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1")
        self.assertEqual(self.comments()[0]["body"], "<!-- roadmap-close -->\nClosed outside a branch (detached HEAD at abc1234), before the merge.")

    def test_commentaire_deja_present_n_est_pas_reposte(self):
        issue = self.add_feature(1, status="In progress")
        self.st = self.load()
        self.st["comments"].append({"issue": issue["number"], "body": "<!-- roadmap-close -->\nClosed on branch autre, before the merge."})
        self.save()
        code, _, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(self.issue("R-1")["state"], "closed")

    def test_garde_sur_le_commentaire_avant_toute_ecriture(self):
        self.head = (f"feat/{NAME.lower()}-x", "abc1234")
        self.add_feature(1, change="demo", status="In progress")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 3)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(len(self.load()["issues"]), 1)
        self.no_leak(out, err)

    def test_pas_de_commentaire_quand_une_sous_issue_reste_ouverte(self):
        self.add_feature(1, change="demo", status="In progress")
        self.run_cli("sync-tasks", "R-1")
        code, _, _ = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 7)
        self.assertEqual(self.comments(), [])


class CloseStepAvecRaison(Base):
    MARQUEUR = "<!-- roadmap-closed-with-reason -->"

    def setUp(self):
        super().setUp()
        self.add_feature(1, change="demo")
        (self.root / "openspec" / "changes" / "demo" / "tasks.md").write_text(TASKS.replace("- [x] 1.2", "- [ ] 1.2"), encoding="utf-8")
        self.run_cli("sync-tasks", "R-1")

    def test_sous_issue_agent_avec_raison(self):
        code, out, err = self.run_cli("close-step", "R-1/g1", "--reason", "user step, no test")
        self.assertEqual(code, 0, err)
        self.assertIn("closed R-1/g1", out)
        cs = self.load()["comments"]
        self.assertEqual(cs, [{"issue": self.number_of("R-1/g1"), "body": self.MARQUEUR + "\nClosed with a reason: user step, no test"}])
        self.assertEqual((self.issue("R-1/g1")["state"], self.issue("R-1/g1")["state_reason"]), ("closed", "completed"))

    def test_la_synchronisation_ne_rouvre_pas(self):
        self.run_cli("close-step", "R-1/g1", "--reason", "raison")
        code, out, _ = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0)
        self.assertNotIn("reopened", out)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.issue("R-1/g1")["state"], "closed")

    def test_sans_raison_la_synchronisation_rouvre_toujours(self):
        # une sous-issue fermée à la main, sans marqueur, puis une tâche décochée : elle est rouverte
        self.run_cli("close-step", "R-1/g1", "--reason", "raison")
        st = self.load()
        st["comments"] = []
        self.st = st
        self.save()
        code, out, _ = self.run_cli("sync-tasks", "R-1")
        self.assertIn("reopened R-1/g1", out)

    def test_sans_raison_code_7_rien_envoye(self):
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("close-step", "R-1/g1")
        self.assertEqual(code, 7)
        self.assertIn("gh_issue: R-1/g1 is an agent sub-issue; close it with --reason after the user's confirmation", err)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertEqual(self.issue("R-1/g1")["state"], "open")
        code, _, _ = self.run_cli("close-step", "R-1/g1", "--reason", "   ")
        self.assertEqual(code, 7)

    def test_raison_avec_un_nom_sensible_code_3(self):
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("close-step", "R-1/g1", "--reason", f"voir {NAME}")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name in comment", err)
        self.no_leak(out, err)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertEqual(self.issue("R-1/g1")["state"], "open")

    def test_etape_utilisateur_sans_raison_comme_avant(self):
        code, _, err = self.run_cli("close-step", "R-1/g3")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.load()["comments"], [])

    def test_etape_utilisateur_avec_raison_facultative(self):
        code, _, err = self.run_cli("close-step", "R-1/t2.2", "--reason", "fait hors outil")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.load()["comments"][0]["body"], self.MARQUEUR + "\nClosed with a reason: fait hors outil")
        self.assertEqual(self.issue("R-1/t2.2")["state"], "closed")

    def test_raison_deja_postee_n_est_pas_repostee(self):
        self.run_cli("close-step", "R-1/g1", "--reason", "raison")
        code, out, _ = self.run_cli("close-step", "R-1/g1", "--reason", "raison")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.load()["comments"]), 1)


# --- Étiquette de l'édition publique (edition-publish-tooling, D19) ----------------------------------------------

class EtiquetteEditionPublique(Base):
    """`close-feature --edition-public` ajoute edition:public ; ensure-labels la crée ; l'outil ne la retire jamais."""
    ETIQUETTE = "edition:public"

    def etiquettes(self, key):
        return sorted(l["name"] for l in self.issue(key)["labels"])

    def requetes_etiquette(self):
        """Écritures qui portent la liste d'étiquettes d'une issue (PATCH issues/<n> avec `labels`), hors création d'étiquette."""
        return [c for c in self.calls(writes_only=True)
                if c["stdin"] and "labels" in json.loads(c["stdin"]) and not c["args"][-3].endswith("/labels")]

    def sous_issues_fermees(self):
        self.add_feature(1, change="demo", status="In progress")
        self.run_cli("sync-tasks", "R-1")
        (self.root / "openspec" / "changes" / "demo" / "tasks.md").write_text(TASKS.replace("- [ ]", "- [x]"), encoding="utf-8")
        self.run_cli("sync-tasks", "R-1")
        self.run_cli("close-step", "R-1/g3")

    def test_ensure_labels_cree_l_etiquette(self):
        code, out, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 0, err)
        self.assertIn(self.ETIQUETTE, {l["name"] for l in self.load()["labels"]})

    def test_ensure_labels_ne_la_recree_pas_si_elle_existe(self):
        self.st["labels"] = [{"name": self.ETIQUETTE}]
        self.save()
        self.run_cli("ensure-labels")
        creees = [json.loads(c["stdin"])["name"] for c in self.calls(writes_only=True) if c["args"][-3].endswith("/labels")]
        self.assertNotIn(self.ETIQUETTE, creees)

    def test_feature_ouverte_etiquetee_avant_les_ecritures_de_fermeture(self):
        self.sous_issues_fermees()
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("close-feature", "R-1", "--edition-public")
        self.assertEqual(code, 0, err)
        self.assertIn(self.ETIQUETTE, self.etiquettes("R-1"))
        self.assertIn("type:feature", self.etiquettes("R-1"))          # les étiquettes existantes sont conservées
        i = self.issue("R-1")
        self.assertEqual((i["state"], i["state_reason"]), ("closed", "completed"))
        self.assertEqual(self.status_of("R-1"), "Done")
        ecritures = self.calls(writes_only=True)[avant:]
        etiquette = next(k for k, c in enumerate(ecritures) if c in self.requetes_etiquette())
        fermeture = next(k for k, c in enumerate(ecritures)
                         if "updateProjectV2ItemFieldValue" in (c["stdin"] or "") or c["args"][-3].endswith("/comments")
                         or ("PATCH" in c["args"] and '"state": "closed"' in (c["stdin"] or "")))
        self.assertLess(etiquette, fermeture)
        self.assertEqual(len([c for c in ecritures if c in self.requetes_etiquette()]), 1)

    def test_feature_deja_fermee_sans_etiquette_n_ajoute_que_l_etiquette(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1")
        avant = self.issue("R-1")
        commentaires = list(self.load()["comments"])
        statut = self.status_of("R-1")
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("close-feature", "R-1", "--edition-public")
        self.assertEqual(code, 0, err)
        nouvelles = self.calls(writes_only=True)[n:]
        self.assertEqual(len(nouvelles), 1)
        self.assertEqual(nouvelles, self.requetes_etiquette()[-1:])
        i = self.issue("R-1")
        self.assertIn(self.ETIQUETTE, self.etiquettes("R-1"))
        for champ in ("state", "state_reason", "body", "milestone"):
            self.assertEqual(i[champ], avant[champ], champ)
        self.assertEqual(self.status_of("R-1"), statut)
        self.assertEqual(self.load()["comments"], commentaires)

    def test_etiquette_deja_presente_aucune_requete_et_rien_a_faire(self):
        self.add_feature(1, status="In progress")
        self.run_cli("close-feature", "R-1", "--edition-public")
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("close-feature", "R-1", "--edition-public")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertEqual(self.etiquettes("R-1").count(self.ETIQUETTE), 1)

    def test_etiquette_presente_sur_une_feature_ouverte_aucune_requete_d_etiquette(self):
        self.add_feature(1, status="In progress")
        self.st = self.load()
        self.st["issues"][0]["labels"].append({"name": self.ETIQUETTE})
        self.save()
        code, out, err = self.run_cli("close-feature", "R-1", "--edition-public")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.requetes_etiquette(), [])
        self.assertEqual(self.issue("R-1")["state"], "closed")

    def test_sans_l_option_aucune_requete_d_etiquette(self):
        self.add_feature(1, status="In progress")
        code, out, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.requetes_etiquette(), [])
        self.assertNotIn(self.ETIQUETTE, self.etiquettes("R-1"))
        self.assertEqual(self.issue("R-1")["state"], "closed")

    def test_le_nom_de_l_etiquette_passe_le_garde(self):
        self.add_feature(1, status="In progress")
        code, out, err = self.run_cli("close-feature", "R-1", "--edition-public")
        self.assertEqual(code, 0, err)
        self.assertNotIn("refused", err)

    def test_le_garde_refuse_avant_toute_ecriture_meme_avec_l_option(self):
        self.add_feature(1, change="demo", status="In progress", conditions=f"{NAME} attend")
        code, out, err = self.run_cli("close-feature", "R-1", "--edition-public")
        self.assertEqual(code, 3)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertNotIn(self.ETIQUETTE, self.etiquettes("R-1"))
        self.no_leak(out, err)


# --- Le faux gh : dans le processus par défaut, en vrai processus pour ce qui vise le lancement -------------------------

class FauxGhDansLeProcessus(Base):
    def test_aucun_processus_pour_une_commande_ordinaire(self):
        with mock.patch.object(fake_gh_core, "handle", wraps=fake_gh_core.handle) as handle:
            code, _, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 0, err)
        self.assertTrue(handle.call_args_list)
        self.assertTrue(self.calls())

    def test_un_blocage_reste_en_vrai_processus(self):
        self.st["mode"] = {"hang_reads": True}
        self.save()
        with mock.patch.object(fake_gh_core, "handle", wraps=fake_gh_core.handle) as handle:
            with mock.patch.dict(os.environ, {"PMZILLA_GH_TIMEOUT": "0.5"}):
                code, _, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 5)
        self.assertEqual(handle.call_args_list, [])


class ProcessusReel(Base):
    """Les tests qui visent le lancement lui-même : le faux gh tourne dans un vrai processus (REEL)."""
    REEL = True

    def setUp(self):
        super().setUp()
        p = mock.patch.dict(os.environ, {"PMZILLA_GH_TIMEOUT": "1"})
        p.start()
        self.addCleanup(p.stop)

    def test_entree_standard_fermee_et_invites_desactivees(self):
        with mock.patch.object(g.subprocess, "run", wraps=g.subprocess.run) as run:
            code, _, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 0, err)
        reads = [c for c in run.call_args_list if "input" not in c.kwargs]
        sends = [c for c in run.call_args_list if "input" in c.kwargs]
        self.assertTrue(reads and sends)
        for c in reads:
            self.assertIs(c.kwargs["stdin"], subprocess.DEVNULL)
        for c in run.call_args_list:
            self.assertEqual(c.kwargs["env"]["GH_PROMPT_DISABLED"], "1")
            self.assertEqual(c.kwargs["timeout"], 1.0)
        for c in self.calls():
            self.assertEqual(c["prompt_disabled"], "1")
            if not c["write"]:
                self.assertTrue(c["stdin_devnull"])
                self.assertEqual(c["stdin"], "")

    def test_delai_par_defaut(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("PMZILLA_GH_TIMEOUT")
            with mock.patch.object(g.subprocess, "run", wraps=g.subprocess.run) as run:
                self.run_cli("ensure-milestone", "Hydra")
        self.assertEqual(run.call_args_list[0].kwargs["timeout"], 60.0)

    def test_gh_tourne_dans_la_racine_du_depot(self):
        with mock.patch.dict(os.environ, {"PMZILLA_GH_TIMEOUT": "60"}), mock.patch.object(g.subprocess, "run", wraps=g.subprocess.run) as run:
            self.run_cli("ensure-labels")
        self.assertTrue(run.call_args_list)
        for c in run.call_args_list:
            self.assertEqual(c.kwargs.get("cwd"), self.root)
            self.assertEqual(c.kwargs["timeout"], 60.0)   # la limite d'origine de ce test (classe Depot), pas la seconde de la classe

    def test_variable_d_environnement_respectee(self):
        with mock.patch.dict(os.environ, {"PMZILLA_GH": str(Path(self.tmp.name) / "absent"), "PMZILLA_GH_TIMEOUT": "60"}):
            code, _, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 5)
        self.assertIn("gh not found", err)


if __name__ == "__main__":
    unittest.main()
