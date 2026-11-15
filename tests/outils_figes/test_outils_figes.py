"""
Tests des enveloppes figées du bac à sable de Bash (niveau 2 du bac à sable, tâches 7.2, 7.3, 7.5, 7.7 ; design D4, D5, D12 ; R-20261109-09, -12).

Chaque test bâtit un dossier jetable (tempfile) qui joue le dossier des outils figés : les enveloppes réelles du dépôt y sont copiées, les outils
figés sont des doublures qui notent leur dossier de travail, leurs arguments et leur environnement dans un dossier voisin, le relevé des
empreintes est écrit comme le fait le script de copie, et dossiers.conf nomme des dossiers jetables. Rien ne touche le vrai dossier des outils
figés, ni la vraie base, ni GitHub, ni Docker. Les enveloppes sont lancées par /bin/bash, comme le fait la session.

    bash tests/run_all.sh outils_figes
"""
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "tools" / "outils_figes"
sys.path.insert(0, str(RACINE / "tools"))
import sandbox_config  # noqa: E402

ENVELOPPES = ("ci_local.sh", "gh_issue.sh", "flow_views.sh", "worktree.sh", "npm_ci.sh")
# La source du fichier géré (config/gere/) est exclue de l'édition publique (manifeste, R-20261108-03) : les cas qui la lisent sautent quand elle est absente,
# avec ce message ; dans le dépôt privé elle existe et ces cas tournent comme avant. Un test statique de tests/build_edition le garde (R-20261114-107).
SOURCE_GEREE_ABSENTE = f"{sandbox_config.SOURCE_RELATIVE} absent (exclu de l'édition publique)"
SANS_SOURCE_GEREE = unittest.skipUnless((RACINE / sandbox_config.SOURCE_RELATIVE).is_file(), SOURCE_GEREE_ABSENTE)
L97 = "outil figé : empreinte différente de son relevé, rien n'est lancé : {}"
L96_SOUS = "outil figé : sous-commande refusée : {}"
L96_ARG = "outil figé : argument refusé : {}"
ENV_FERME = {"PATH", "HOME", "LANG", "UV_OFFLINE", "UV_NO_CONFIG", "UV_CACHE_DIR", "UV_PYTHON", "GH_PROMPT_DISABLED", "GIT_TERMINAL_PROMPT",
             "PMZILLA_LAB_WORKSPACE", "PMZILLA_LAB_DATA", "PMZILLA_LAB_SENSITIVE_NAMES", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0",
             "GIT_CONFIG_KEY_1", "GIT_CONFIG_VALUE_1"}
ENV_GH_EN_PLUS = {"PMZILLA_GH_ISSUE_RACINE", "PMZILLA_GH_ISSUE_BASES_LECTURE", "PMZILLA_GH_ISSUE_BASES_SORTIE"}   # posées par l'enveloppe de l'outil de file seulement
CLES_CONF = ("maison", "workspace", "worktrees", "etapes", "scratchpad", "donnees", "noms", "crochets", "cache_uv", "python")
AJOUTES_PAR_LES_INTERPRETEURS = {"PWD", "SHLVL", "_", "OLDPWD", "LC_CTYPE"} | ({"__CF_USER_TEXT_ENCODING"} if sys.platform == "darwin" else set())   # R-20261111-13 : posée par CoreFoundation sous macOS

FAUX_CI = """#!/bin/bash
aux="{aux}"
{{ pwd -P; printf '%s\\n' "$@"; }} > "$aux/trace-ci-args.txt"
env > "$aux/trace-ci-env.txt"
if [ -f "$aux/verrou-liste.txt" ] && grep -qxF "$(pwd -P)" "$aux/verrou-liste.txt"; then echo "ci_local : fin de branche en cours" >&2; exit 7; fi
[ -f "$aux/code-ci.txt" ] && exit "$(cat "$aux/code-ci.txt")"
exit 0
"""
FAUX_PYTHON = """import json, os, sys
aux = "{aux}"
trace = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "env": dict(os.environ)}}
open(aux + "/trace-{nom}.json", "w", encoding="utf-8").write(json.dumps(trace))
if "--sortie" in sys.argv:
    open(sys.argv[sys.argv.index("--sortie") + 1], "w", encoding="utf-8").write("{{}}")
fichier = aux + "/code-{nom}.txt"
sys.exit(int(open(fichier).read()) if os.path.exists(fichier) else 0)
"""
FAUX_UV = """#!/bin/sh
# uv run --script <chemin> <arguments> : lance le script avec l'interpréteur du test
shift 2
script=$1
shift
exec "{python}" "$script" "$@"
"""


def sha(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def liste_figee():
    """[(genre, chemin)] de la liste fermée du dépôt."""
    sortie = []
    for ligne in (SOURCE / "liste.txt").read_text(encoding="utf-8").splitlines():
        if ligne.strip() and not ligne.startswith("#"):
            genre, chemin = ligne.split(" ", 1)
            sortie.append((genre, chemin))
    return sortie


class Dossier(unittest.TestCase):
    """Le dossier des outils figés jetable, ses voisins et les lanceurs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.maison = self.base / "maison"
        self.figes = self.base / "outils-figes"
        self.aux = self.base / "aux"
        self.worktrees = self.base / "worktrees"
        self.etapes = self.base / "etapes"
        self.sessions = self.base / "sessions"
        self.scratch = self.sessions / "s1" / "scratchpad"
        self.workspace = self.base / "workspace"
        self.donnees = self.base / "donnees"
        self.noms = self.base / "noms.txt"
        self.hors = self.base / "ailleurs"
        self.crochets = self.base / "crochets"
        self.cache_uv = self.base / "cache-uv"
        for d in (self.maison / ".local" / "bin", self.figes, self.aux, self.worktrees, self.etapes, self.scratch, self.workspace, self.donnees,
                  self.hors, self.crochets, self.cache_uv):
            d.mkdir(parents=True, exist_ok=True)
        self.noms.write_text("fictif\n", encoding="utf-8")
        for nom in ENVELOPPES + ("enveloppe.sh",):
            (self.figes / nom).write_text((SOURCE / nom).read_text(encoding="utf-8"), encoding="utf-8")
        for genre, chemin in liste_figee():
            if genre == "C":
                self.ecrire(self.figes / "copie" / chemin, "# doublure\n")
        self.ecrire(self.figes / "copie" / "tools" / "ci_local.sh", FAUX_CI.format(aux=self.aux))
        for nom, chemin in (("gh", "gh_issue.py"), ("flow", "flow_views.py")):
            self.ecrire(self.figes / "copie" / "tools" / chemin, FAUX_PYTHON.format(aux=self.aux, nom=nom))
        uv = self.maison / ".local" / "bin" / "uv"
        self.ecrire(uv, FAUX_UV.format(python=sys.executable))
        uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
        self.ecrire_conf()
        self.releve()

    # --- construction ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def ecrire(chemin: Path, texte: str):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def ecrire_conf(self, **remplace):
        valeurs = {"maison": self.maison, "workspace": self.workspace, "worktrees": self.worktrees, "etapes": self.etapes,
                   "scratchpad": self.sessions, "donnees": self.donnees, "noms": self.noms, "crochets": self.crochets, "cache_uv": self.cache_uv,
                   "python": sys.executable}
        valeurs.update(remplace)
        self.ecrire(self.figes / "dossiers.conf", "".join(f"{k}={v}\n" for k, v in valeurs.items() if v is not None))

    def releve(self):
        """Écrit empreintes.sha256 comme le script de copie : un « <sha256>  <nom> » par fichier du dossier, sauf le relevé."""
        lignes = []
        for chemin in sorted(self.figes.rglob("*")):
            if chemin.is_file() and chemin.name != "empreintes.sha256":
                lignes.append(f"{sha(chemin)}  {chemin.relative_to(self.figes).as_posix()}")
        self.ecrire(self.figes / "empreintes.sha256", "\n".join(lignes) + "\n")

    def worktree(self, nom="wt-a", inscrit=True):
        """Un worktree sous le dossier des worktrees ; inscrit, comme git le fait, par un fichier gitdir sous <workspace>/.git/worktrees/<nom>/."""
        chemin = self.worktrees / nom
        self.ecrire(chemin / ".git", "gitdir: ailleurs\n")
        if inscrit:
            self.ecrire(self.workspace / ".git" / "worktrees" / nom / "gitdir", f"{chemin.resolve()}/.git\n")
        return chemin

    def lance(self, enveloppe, *args, env=None, cwd=None):
        environ = {"PATH": "/usr/bin:/bin", "HOME": str(self.base)}
        environ.update(env or {})
        return subprocess.run(["/bin/bash", str(self.figes / enveloppe), *args], capture_output=True, text=True,
                              cwd=str(cwd or self.base), env=environ)

    def trace(self, nom):
        return json.loads((self.aux / f"trace-{nom}.json").read_text(encoding="utf-8"))

    def args_ci(self):
        return (self.aux / "trace-ci-args.txt").read_text(encoding="utf-8").splitlines()

    def rien_lance(self):
        self.assertEqual([p.name for p in self.aux.glob("trace-*")], [])

    def refuse(self, r, code, ligne, secrets=()):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertEqual(r.stderr.strip(), ligne)
        for secret in secrets:
            self.assertNotIn(str(secret), r.stdout + r.stderr)
        self.rien_lance()


class Empreintes(Dossier):
    def test_relevé_egal_l_outil_est_lance(self):
        r = self.lance("ci_local.sh", "places", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.args_ci()[1:], ["places", "--json"])

    def test_chaque_enveloppe_refuse_un_fichier_different(self):
        casse = {"ci_local.sh": ("copie/tools/finish_lock.py", ("run",)),
                 "gh_issue.sh": ("copie/tools/gh_issue.py", ("list",)),
                 "flow_views.sh": ("copie/tools/db.py", ("show", "v_team_status")),
                 "worktree.sh": ("dossiers.conf", ("add", "feat/x", "main"))}
        for enveloppe, (nom, args) in casse.items():
            with self.subTest(enveloppe=enveloppe):
                chemin = self.figes / nom
                avant = chemin.read_text(encoding="utf-8")
                chemin.write_text(avant + "# modifié\n", encoding="utf-8")
                r = self.lance(enveloppe, *args)
                self.refuse(r, 97, L97.format(nom))
                chemin.write_text(avant, encoding="utf-8")

    def test_la_bibliotheque_commune_est_aussi_relevee(self):
        for enveloppe, args in (("ci_local.sh", ("places",)), ("gh_issue.sh", ("list",)), ("flow_views.sh", ("show", "v")),
                                ("worktree.sh", ("add", "x", "main"))):
            with self.subTest(enveloppe=enveloppe):
                chemin = self.figes / "enveloppe.sh"
                avant = chemin.read_text(encoding="utf-8")
                chemin.write_text(avant + "\n# modifié\n", encoding="utf-8")
                self.refuse(self.lance(enveloppe, *args), 97, L97.format("enveloppe.sh"))
                chemin.write_text(avant, encoding="utf-8")

    def test_relevé_absent_code_97(self):
        (self.figes / "empreintes.sha256").unlink()
        self.refuse(self.lance("gh_issue.sh", "list"), 97, L97.format("empreintes.sha256"))

    def test_relevé_mal_forme_code_97(self):
        for contenu in ("pas un relevé\n", "abc  ci_local.sh\n", f"{'0' * 64} ci_local.sh\n", f"{'0' * 64}  ../x\n"):
            with self.subTest(contenu=contenu):
                self.ecrire(self.figes / "empreintes.sha256", contenu)
                self.refuse(self.lance("ci_local.sh", "places"), 97, L97.format("empreintes.sha256"))

    def test_fichier_figé_absent_du_dossier_code_97(self):
        (self.figes / "copie" / "tools" / "db.py").unlink()
        self.refuse(self.lance("flow_views.sh", "show", "v"), 97, L97.format("copie/tools/db.py"))

    def test_fichier_figé_qui_est_un_lien_code_97(self):
        cible = self.hors / "db.py"
        self.ecrire(cible, "# doublure\n")
        chemin = self.figes / "copie" / "tools" / "db.py"
        chemin.unlink()
        chemin.symlink_to(cible)
        self.refuse(self.lance("flow_views.sh", "show", "v"), 97, L97.format("copie/tools/db.py"))

    def test_un_fichier_necessaire_absent_du_relevé_code_97(self):
        lignes = (self.figes / "empreintes.sha256").read_text(encoding="utf-8").splitlines()
        self.ecrire(self.figes / "empreintes.sha256", "\n".join(l for l in lignes if not l.endswith("copie/tools/messages.py")) + "\n")
        self.refuse(self.lance("flow_views.sh", "show", "v"), 97, L97.format("copie/tools/messages.py"))

    def test_dossiers_conf_modifie_ou_absent_code_97(self):
        self.ecrire_conf(worktrees="/ailleurs")        # modifié sans réécrire le relevé
        self.refuse(self.lance("ci_local.sh", "places"), 97, L97.format("dossiers.conf"))
        self.releve()
        self.ecrire_conf(worktrees="relatif")           # relevé à jour, mais valeur non absolue : refus à la lecture de la clé
        self.releve()
        r = self.lance("ci_local.sh", "run", "--travail", "--worktree", str(self.worktree()))
        self.assertEqual((r.returncode, r.stderr.strip()), (97, L97.format("dossiers.conf")))

    def test_le_calcul_de_l_empreinte_ignore_l_environnement_de_la_session(self):
        """B6 : un vrai fichier BASH_ENV, PERL5OPT (un module qui note son passage) et une fonction exportée qui remplace shasum. Rien ne doit passer par le
        calcul de l'empreinte : aucun marqueur de Perl ni de la fonction, et le fichier BASH_ENV n'est lu que par l'interpréteur de l'enveloppe elle-même
        (son marqueur porte le nom du script qui le charge : aucun autre script, donc aucun programme lancé par l'enveloppe, ne l'a chargé)."""
        marques = self.base / "marqueurs"
        marques.mkdir()
        bash_env = self.base / "bash_env.sh"
        bash_env.write_text(f'echo "bash_env:$PPID" >> "{marques}/bash_env.txt"\n', encoding="utf-8")   # R-20261111-13 : lecteur reconnu par $PPID (ce test), pas par $0 (fixé après la lecture, variable selon la version de bash)
        modules = self.base / "perl"
        modules.mkdir()
        (modules / "marqueur.pm").write_text(f'package marqueur;\nopen(my $f, ">>", "{marques}/perl.txt");\nprint $f "perl\\n";\nclose($f);\n1;\n', encoding="utf-8")
        fonction = f'() {{ echo fonction >> "{marques}/fonction.txt"; command shasum "$@"; }}'
        session = {"BASH_ENV": str(bash_env), "PERL5OPT": f"-I{modules} -Mmarqueur", "BASH_FUNC_shasum%%": fonction, "shasum": fonction}
        for enveloppe, args in (("ci_local.sh", ("places",)), ("gh_issue.sh", ("list",)), ("flow_views.sh", ("show", "v")), ("worktree.sh", ("remove",))):
            with self.subTest(enveloppe=enveloppe):
                r = self.lance(enveloppe, *args, env=session)
                self.assertIn(r.returncode, (0, 96), r.stderr)                    # le relevé est passé (sinon 97)
                self.assertFalse((marques / "perl.txt").exists(), "PERL5OPT a atteint le calcul de l'empreinte")
                self.assertFalse((marques / "fonction.txt").exists(), "la fonction exportée a remplacé shasum")
                propre = marques / "bash_env.txt"
                lignes = set(propre.read_text(encoding="utf-8").splitlines()) if propre.exists() else set()
                self.assertLessEqual(lignes, {f"bash_env:{os.getpid()}"})
                lecteurs = propre.read_text(encoding="utf-8").splitlines() if propre.exists() else []
                self.assertEqual(lecteurs, [f"bash_env:{os.getpid()}"], "R-20261111-23 : BASH_ENV lu exactement une fois par lancement")
                propre.unlink(missing_ok=True)

    def test_apres_la_relance_videe_aucun_enfant_ne_voit_bash_env_env_ni_fonction_exportee(self):
        """R-20261111-15 (2) : l'enveloppe se relance sous `env -i` avec --noprofile --norc. Le fichier BASH_ENV n'est lu que par le premier bash (son
        parent est ce test : $PPID) ; aucun enfant n'en reçoit ni la variable, ni ENV, ni une fonction exportée."""
        marques = self.base / "marqueurs"
        marques.mkdir()
        bash_env = self.base / "bash_env.sh"
        bash_env.write_text(f'echo "$PPID" >> "{marques}/bash_env.txt"\n', encoding="utf-8")
        fonction = '() { echo fonction; }'
        session = {"BASH_ENV": str(bash_env), "ENV": str(bash_env), "BASH_FUNC_cut%%": fonction, "BASH_FUNC_dirname%%": fonction, "cut": fonction}
        suivi = marques / "bash_env.txt"
        for enveloppe, args in (("gh_issue.sh", ("list",)), ("flow_views.sh", ("show", "v")), ("ci_local.sh", ("places",))):
            suivi.unlink(missing_ok=True)   # R-20261111-23 : remis à zéro entre deux lancements, exactement une ligne par lancement
            self.assertEqual(self.lance(enveloppe, *args, env=session).returncode, 0)
            self.assertEqual(suivi.read_text(encoding="utf-8").splitlines() if suivi.exists() else [], [str(os.getpid())], enveloppe)
        env_ci = dict(l.split("=", 1) for l in (self.aux / "trace-ci-env.txt").read_text(encoding="utf-8").splitlines() if "=" in l)
        for nom, env in (("gh", self.trace("gh")["env"]), ("flow", self.trace("flow")["env"]), ("ci", env_ci)):
            with self.subTest(outil=nom):
                self.assertEqual([c for c in env if c in ("BASH_ENV", "ENV") or c.startswith("BASH_FUNC_")], [])
        lignes = set((marques / "bash_env.txt").read_text(encoding="utf-8").splitlines()) if (marques / "bash_env.txt").exists() else set()
        self.assertLessEqual(lignes, {str(os.getpid())})

    def test_une_fonction_exportee_dirname_n_atteint_pas_l_enveloppe_relancee(self):
        """R-20261111-23 : `dirname` remplacé par une fonction exportée qui note son passage et rendrait un faux chemin : le code de retour est celui d'un
        lancement sans fonction, et la fonction n'a jamais tourné (elle n'atteint pas l'enveloppe relancée)."""
        marques = self.base / "marqueurs"
        marques.mkdir()
        sortie = self.scratch / "lecture-dirname.json"   # `list --sortie <fichier sous le scratchpad>` : le cas où l'enveloppe appelle fige_sous, donc dirname
        sans = self.lance("gh_issue.sh", "list", "--sortie", str(sortie)).returncode
        self.assertEqual(sans, 0)
        self.assertTrue(sortie.exists(), "le lancement sans fonction a tourné jusqu'à fige_sous")
        sortie.unlink()
        fonction = f'() {{ echo fonction >> "{marques}/dirname.txt"; echo /inexistant; }}'
        r = self.lance("gh_issue.sh", "list", "--sortie", str(sortie), env={"BASH_FUNC_dirname%%": fonction, "dirname": fonction})
        self.assertEqual(r.returncode, sans, r.stderr)
        self.assertTrue(sortie.exists(), "fige_sous a tourné avec le vrai dirname : la doublure a écrit le fichier de --sortie")
        self.assertFalse((marques / "dirname.txt").exists(), "la fonction exportée a remplacé dirname")

    def test_une_fonction_exportee_cut_ne_masque_pas_un_fichier_modifie_code_97(self):
        """R-20261111-15 (3) : un fichier figé modifié et une fonction exportée `cut` qui rend l'empreinte attendue (celle du fichier d'origine) : le code
        reste 97. Sans la relance vidée, la fonction remplace `cut` dans le tube du calcul de l'empreinte et le contournement réussit."""
        hashes = self.base / "hashes"
        hashes.mkdir()
        for chemin in self.figes.rglob("*"):
            if chemin.is_file() and chemin.name != "empreintes.sha256":
                (hashes / str(chemin).replace("/", "_")).write_text(sha(chemin) + "\n", encoding="utf-8")
        cible = self.figes / "copie" / "tools" / "gh_issue.py"
        cible.write_text(cible.read_text(encoding="utf-8") + "# modifié\n", encoding="utf-8")
        fonction = rf'() {{ local h f; read -r h f; command cat "{hashes}/${{f//\//_}}"; }}'
        r = self.lance("gh_issue.sh", "list", env={"BASH_FUNC_cut%%": fonction, "cut": fonction})
        self.refuse(r, 97, L97.format("copie/tools/gh_issue.py"))

    def test_aucun_effet_avant_la_verification(self):
        (self.figes / "empreintes.sha256").unlink()
        self.lance("gh_issue.sh", "new-idea", "--title", "T", "--body-file", str(self.scratch / "x.md"))
        self.rien_lance()


class SousCommandes(Dossier):
    def test_ci_local_ne_permet_que_run_et_places(self):
        for sous in ("build", "up", "cle", "--help", "", "x; rm"):
            with self.subTest(sous=sous):
                attendu = L96_SOUS.format(sous if re.fullmatch(r"[A-Za-z0-9-]+", sous) else "?")
                self.refuse(self.lance("ci_local.sh", *([sous] if sous else [])), 96, attendu)
        for sous in ("run", "places"):
            self.assertEqual(self.lance("ci_local.sh", sous).returncode, 0)

    def test_flow_views_ne_permet_que_show(self):
        for sous in ("list", "version-share", "masked-cells", "team-ids-check"):
            with self.subTest(sous=sous):
                self.refuse(self.lance("flow_views.sh", sous), 96, L96_SOUS.format(sous))
        self.assertEqual(self.lance("flow_views.sh", "show", "v_team_status", "--min-cell", "7").returncode, 0)
        self.assertEqual(self.trace("flow")["argv"], ["show", "v_team_status", "--min-cell", "7"])

    def test_gh_issue_ne_permet_que_les_sous_commandes_de_l_outil(self):
        for sous in ("bogus", "api", "delete-issue", ""):
            with self.subTest(sous=sous):
                attendu = L96_SOUS.format(sous if sous else "?")
                self.refuse(self.lance("gh_issue.sh", *([sous] if sous else [])), 96, attendu)
        for sous in ("view", "list", "status", "sub-issues"):
            self.assertEqual(self.lance("gh_issue.sh", sous).returncode, 0, sous)

    def test_la_liste_de_l_enveloppe_est_celle_du_parseur_de_l_outil(self):
        """Source : le parseur de tools/gh_issue.py ; un écart (sous-commande ajoutée ou retirée d'un seul côté) fait échouer ce test."""
        import argparse
        import gh_issue
        actions = [a for a in gh_issue.build_parser()._actions if isinstance(a, argparse._SubParsersAction)]
        parseur = set(actions[0].choices)
        texte = (SOURCE / "gh_issue.sh").read_text(encoding="utf-8")
        m = re.search(r'^SOUS_COMMANDES="(.*?)"$', texte, re.M | re.S)
        self.assertIsNotNone(m)
        enveloppe = set(m.group(1).replace("\\\n", " ").split())
        self.assertEqual(enveloppe, parseur)
        self.assertLessEqual({"view", "list"}, parseur)

    def test_worktree_ne_permet_que_add(self):
        for sous in ("remove", "list", "prune", ""):
            with self.subTest(sous=sous):
                attendu = L96_SOUS.format(sous if sous else "?")
                self.refuse(self.lance("worktree.sh", *([sous] if sous else [])), 96, attendu)


class Worktree(Dossier):
    def test_run_index_et_run_travail_acceptent_un_worktree_existant(self):
        wt = self.worktree()
        for forme in (("run", "--index", "--worktree", str(wt)), ("run", "--travail", "--worktree", str(wt), "sandbox_config"),
                      ("run", "--worktree", str(wt), "--travail"), ("run", "--index", f"--worktree={wt}", "doctor")):
            with self.subTest(forme=forme):
                r = self.lance("ci_local.sh", *forme)
                self.assertEqual(r.returncode, 0, r.stderr)
                trace = self.args_ci()
                self.assertEqual(trace[0], str(wt.resolve()))          # le script figé tourne dans ce worktree
                self.assertEqual(trace[1], "run")
                self.assertNotIn("--worktree", trace)                   # l'option n'est pas transmise
                self.assertFalse([a for a in trace if a.startswith("--worktree")])
                self.assertIn(forme[1] if forme[1] != "--worktree" else "--travail", trace)

    def test_sans_worktree_le_script_fige_tourne_dans_le_workspace_jamais_dans_le_dossier_courant(self):
        """B2 : la forme inverse de l'ancien test : le dossier courant de la session ne décide de rien."""
        wt = self.worktree()
        for cwd in (wt, self.hors, self.base, self.worktrees):
            with self.subTest(cwd=str(cwd)):
                self.assertEqual(self.lance("ci_local.sh", "places", cwd=cwd).returncode, 0)
                self.assertEqual(self.args_ci()[0], str(self.workspace.resolve()))
                self.assertEqual(self.lance("ci_local.sh", "run", cwd=cwd).returncode, 0)
                self.assertEqual(self.args_ci()[0], str(self.workspace.resolve()))

    def test_worktree_non_inscrit_par_le_workspace_code_96(self):
        """B2 : un dossier qui a un fichier .git sous les worktrees mais que le workspace n'inscrit pas (ou inscrit sous un autre chemin) est refusé."""
        wt = self.worktree("wt-libre", inscrit=False)
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(wt)), 96, L96_ARG.format("--worktree"))
        self.ecrire(self.workspace / ".git" / "worktrees" / "autre" / "gitdir", f"{self.hors.resolve()}/.git\n")      # une inscription qui vise ailleurs
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(wt)), 96, L96_ARG.format("--worktree"))
        self.ecrire(self.workspace / ".git" / "worktrees" / "wt-libre" / "gitdir", f"{wt.resolve()}/.git\n")           # inscrit : accepté
        self.assertEqual(self.lance("ci_local.sh", "run", "--index", "--worktree", str(wt)).returncode, 0)

    def test_worktree_inscrit_mais_sous_un_sous_dossier_code_96(self):
        wt = self.worktree()
        (wt / "mothra").mkdir()
        self.ecrire(wt / "mothra" / ".git", "gitdir: x\n")
        self.ecrire(self.workspace / ".git" / "worktrees" / "m" / "gitdir", f"{(wt / 'mothra').resolve()}/.git\n")
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(wt / "mothra")), 96, L96_ARG.format("--worktree"))
        niveau2 = self.worktrees / "groupe" / "wt-b"
        self.ecrire(niveau2 / ".git", "gitdir: x\n")
        self.ecrire(self.workspace / ".git" / "worktrees" / "b" / "gitdir", f"{niveau2.resolve()}/.git\n")
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(niveau2)), 96, L96_ARG.format("--worktree"))

    def test_worktree_hors_du_dossier_des_worktrees_code_96(self):
        dehors = self.hors / "wt"
        self.ecrire(dehors / ".git", "gitdir: x\n")
        for cible in (dehors, self.base / "inexistant", self.worktrees, self.worktrees / "absent", Path("relatif/wt-a")):
            with self.subTest(cible=str(cible)):
                r = self.lance("ci_local.sh", "run", "--index", "--worktree", str(cible))
                self.refuse(r, 96, L96_ARG.format("--worktree"), secrets=(cible,) if cible.is_absolute() else ())

    def test_dossier_sous_les_worktrees_sans_fichier_git_code_96(self):
        (self.worktrees / "simple").mkdir()
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(self.worktrees / "simple")), 96, L96_ARG.format("--worktree"))

    def test_sous_dossier_d_un_worktree_code_96(self):
        wt = self.worktree()
        (wt / "mothra").mkdir()
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(wt / "mothra")), 96, L96_ARG.format("--worktree"))

    def test_lien_vers_l_exterieur_code_96(self):
        dehors = self.hors / "vrai"
        self.ecrire(dehors / ".git", "gitdir: x\n")
        (self.worktrees / "lien").symlink_to(dehors)
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", str(self.worktrees / "lien")), 96, L96_ARG.format("--worktree"))

    def test_dotdot_dans_le_chemin_code_96(self):
        wt = self.worktree()
        chemin = f"{self.worktrees}/../worktrees/{wt.name}"
        self.refuse(self.lance("ci_local.sh", "run", "--index", "--worktree", chemin), 96, L96_ARG.format("--worktree"))

    def test_worktree_refuse_hors_de_run_index_et_run_travail(self):
        wt = str(self.worktree())
        for forme in (("places", "--worktree", wt), ("run", "--worktree", wt), ("run", "--rejeu", "portable", "x", "--worktree", wt),
                      ("run", "--index", "--worktree"), ("run", "--index", "--worktree", "")):
            with self.subTest(forme=forme):
                self.refuse(self.lance("ci_local.sh", *forme), 96, L96_ARG.format("--worktree"))

    def test_code_7_quand_le_worktree_est_dans_la_liste_du_verrou_de_fin(self):
        """Le script figé tourne dans le worktree nommé : son gel ciblé (règle de finish_lock, évaluée sur son dossier de travail) rend 7 ;
        la doublure lit une liste du verrou et rend 7 quand son dossier de travail y figure."""
        gele, libre = self.worktree("wt-gele"), self.worktree("wt-libre")
        self.ecrire(self.aux / "verrou-liste.txt", f"{gele.resolve()}\n")
        r = self.lance("ci_local.sh", "run", "--index", "--worktree", str(gele))
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertEqual(self.args_ci()[0], str(gele.resolve()))        # il a bien été lancé dans ce worktree-là
        r = self.lance("ci_local.sh", "run", "--index", "--worktree", str(libre))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.args_ci()[0], str(libre.resolve()))


class Fichiers(Dossier):
    def appel(self, *args):
        return self.lance("gh_issue.sh", *args)

    def test_body_file_et_comment_file_acceptes_sous_le_scratchpad_et_les_etapes(self):
        for dossier in (self.scratch, self.etapes, self.sessions / "s2" / "scratchpad"):
            (dossier).mkdir(parents=True, exist_ok=True)
            fichier = dossier / "corps.md"
            fichier.write_text("texte\n", encoding="utf-8")
            for option in ("--body-file", "--comment-file", "--description-file"):
                with self.subTest(dossier=str(dossier), option=option):
                    sous = {"--body-file": "new-idea", "--comment-file": "comment-idea", "--description-file": "edit-milestone"}[option]
                    r = self.appel(sous, "x", option, str(fichier))
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual(self.trace("gh")["argv"], [sous, "x", option, str(fichier)])
                    (self.aux / "trace-gh.json").unlink()

    def test_fichier_hors_des_dossiers_permis_code_96_sans_la_valeur(self):
        dehors = self.hors / "corps.md"
        dehors.write_text("x\n", encoding="utf-8")
        for option in ("--body-file", "--comment-file", "--description-file"):
            with self.subTest(option=option, forme="séparée"):
                self.refuse(self.appel("new-idea", option, str(dehors)), 96, L96_ARG.format(option), secrets=(dehors, self.hors))
            with self.subTest(option=option, forme="égal"):
                self.refuse(self.appel("new-idea", f"{option}={dehors}"), 96, L96_ARG.format(option), secrets=(dehors, self.hors))

    def test_les_abreviations_de_l_option_ne_contournent_pas_le_controle(self):
        dehors = self.hors / "corps.md"
        dehors.write_text("x\n", encoding="utf-8")
        for abrege, complet in (("--body-f", "--body-file"), ("--body-", "--body-file"), ("--comment", "--comment-file"),
                                ("--comment-f", "--comment-file"), ("--descr", "--description-file"), ("--sort", "--sortie"),
                                ("--so", "--sortie")):
            with self.subTest(abrege=abrege):
                self.refuse(self.appel("new-idea", abrege, str(dehors)), 96, L96_ARG.format(complet), secrets=(dehors,))
                self.refuse(self.appel("new-idea", f"{abrege}={dehors}"), 96, L96_ARG.format(complet), secrets=(dehors,))

    def test_body_texte_n_est_pas_une_option_de_fichier(self):
        r = self.appel("new-idea", "--title", "T", "--body", str(self.hors / "texte-libre"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_chemins_refuses_relatif_dotdot_et_liens(self):
        dedans = self.scratch / "corps.md"
        dedans.write_text("x\n", encoding="utf-8")
        dehors = self.hors / "secret.md"
        dehors.write_text("x\n", encoding="utf-8")
        (self.scratch / "lien.md").symlink_to(dehors)                       # un fichier lien, sous le scratchpad, vers l'extérieur
        (self.sessions / "s1" / "dossier-lien").symlink_to(self.hors)       # un dossier lien vers l'extérieur
        cas = {"relatif": "corps.md", "dotdot": f"{self.scratch}/../../../ailleurs/secret.md", "lien-fichier": str(self.scratch / "lien.md"),
               "lien-dossier": str(self.sessions / "s1" / "dossier-lien" / "secret.md"),
               "dossier-parent-absent": str(self.scratch / "absent" / "corps.md"), "vide": ""}
        for nom, valeur in cas.items():
            with self.subTest(cas=nom):
                self.refuse(self.appel("new-idea", "--body-file", valeur), 96, L96_ARG.format("--body-file"))

    def test_option_de_fichier_sans_valeur_code_96(self):
        self.refuse(self.appel("new-idea", "--body-file"), 96, L96_ARG.format("--body-file"))

    def test_sortie_sous_le_scratchpad_acceptee_et_ailleurs_refusee(self):
        dedans = self.scratch / "lecture.json"
        r = self.appel("list", "--sortie", str(dedans))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(dedans.exists())                                    # la doublure écrit le fichier de --sortie
        self.assertEqual(self.trace("gh")["argv"], ["list", "--sortie", str(dedans)])
        (self.aux / "trace-gh.json").unlink()
        r = self.appel("view", "R-1", f"--sortie={dedans}")
        self.assertEqual(r.returncode, 0, r.stderr)
        for dehors in (self.etapes / "lecture.json", self.hors / "lecture.json", self.maison / "lecture.json"):
            with self.subTest(dehors=str(dehors)):
                (self.aux / "trace-gh.json").unlink(missing_ok=True)
                self.refuse(self.appel("list", "--sortie", str(dehors)), 96, L96_ARG.format("--sortie"), secrets=(dehors,))
                self.refuse(self.appel("view", "R-1", f"--sortie={dehors}"), 96, L96_ARG.format("--sortie"), secrets=(dehors,))

    def test_les_options_apres_le_double_tiret_sont_laissees_telles_quelles(self):
        r = self.appel("new-idea", "--title", "T", "--", "--body-file")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.trace("gh")["argv"], ["new-idea", "--title", "T", "--", "--body-file"])


class Environnement(Dossier):
    SESSION = {"PMZILLA_GH": "/bin/false", "FINISH_LOCK_TOKEN": "jeton", "CI_LOCAL_DOCKER": "faux-docker", "GH_TOKEN": "secret-session",
               "GIT_DIR": "/inexistant", "GIT_WORK_TREE": "/inexistant", "PMZILLA_LAB_DATA": "/session/donnees", "PMZILLA_LAB_WORKSPACE": "/session/ws",
               "PMZILLA_LAB_SENSITIVE_NAMES": "/session/noms", "UV_OFFLINE": "0", "HOME": "/session/maison", "BASH_ENV": "/session/bashenv",
               "ENV": "/session/env", "CDPATH": "/session", "LD_PRELOAD": "/session/lib", "FOO": "bar", "PYTHONPATH": "/session/py"}

    def verifie(self, env, en_plus=()):
        attendu = {"HOME": str(self.maison), "UV_OFFLINE": "1", "UV_NO_CONFIG": "1", "UV_CACHE_DIR": str(self.cache_uv), "UV_PYTHON": sys.executable,
                   "GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0", "PMZILLA_LAB_WORKSPACE": str(self.workspace),
                   "PMZILLA_LAB_DATA": str(self.donnees), "PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms), "LANG": "en_US.UTF-8",
                   "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": str(self.crochets),
                   "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"}
        for cle, valeur in attendu.items():
            self.assertEqual(env.get(cle), valeur, cle)
        self.assertTrue(env["PATH"].startswith(f"{self.maison}/.local/bin:"))
        self.assertEqual(set(env) - ENV_FERME - set(en_plus) - AJOUTES_PAR_LES_INTERPRETEURS, set())
        for cle in set(self.SESSION) - ENV_FERME:
            self.assertNotIn(cle, env)
        self.assertNotIn("secret-session", json.dumps(env))

    def test_les_variables_de_la_session_sont_ignorees(self):
        for enveloppe, args, trace, en_plus in (("gh_issue.sh", ("list",), "gh", ENV_GH_EN_PLUS), ("flow_views.sh", ("show", "v"), "flow", ())):
            with self.subTest(enveloppe=enveloppe):
                self.assertEqual(self.lance(enveloppe, *args, env=self.SESSION).returncode, 0)
                self.verifie(self.trace(trace)["env"], en_plus)
        self.assertEqual(self.lance("ci_local.sh", "places", env=self.SESSION).returncode, 0)
        env = dict(l.split("=", 1) for l in (self.aux / "trace-ci-env.txt").read_text(encoding="utf-8").splitlines() if "=" in l)
        self.verifie(env)

    def test_la_valeur_de_la_session_pour_cf_user_text_encoding_ne_passe_jamais(self):
        """R-20261111-13 : sous macOS, CoreFoundation pose __CF_USER_TEXT_ENCODING dans l'interpréteur lancé (elle est donc admise, voir
        AJOUTES_PAR_LES_INTERPRETEURS), mais la valeur de la session ne doit jamais atteindre l'outil : une valeur repérable posée par la session
        n'est jamais celle que l'outil trace. Sur les autres plateformes la variable est absente de l'environnement de l'outil."""
        repere = "0xDEAD:0xBEEF:0x42"
        session = {"__CF_USER_TEXT_ENCODING": repere}
        self.assertEqual(self.lance("gh_issue.sh", "list", env=session).returncode, 0)
        self.assertEqual(self.lance("flow_views.sh", "show", "v", env=session).returncode, 0)
        self.assertEqual(self.lance("ci_local.sh", "places", env=session).returncode, 0)
        env_ci = dict(l.split("=", 1) for l in (self.aux / "trace-ci-env.txt").read_text(encoding="utf-8").splitlines() if "=" in l)
        for nom, env in (("gh", self.trace("gh")["env"]), ("flow", self.trace("flow")["env"]), ("ci", env_ci)):
            with self.subTest(outil=nom):
                self.assertNotEqual(env.get("__CF_USER_TEXT_ENCODING"), repere)
                self.assertNotIn(repere, json.dumps(env))

    def test_cf_user_text_encoding_est_admise_seulement_sous_darwin(self):
        self.assertEqual("__CF_USER_TEXT_ENCODING" in AJOUTES_PAR_LES_INTERPRETEURS, sys.platform == "darwin")

    def test_les_variables_propres_a_l_outil_de_file_sont_ignorees_quand_la_session_les_pose(self):
        """B4 et B5 : la racine et les dossiers permis viennent de dossiers.conf et du dossier courant contrôlé, jamais de la session."""
        session = {"PMZILLA_GH_ISSUE_RACINE": str(self.hors), "PMZILLA_GH_ISSUE_BASES_LECTURE": str(self.hors), "PMZILLA_GH_ISSUE_BASES_SORTIE": str(self.hors)}
        self.assertEqual(self.lance("gh_issue.sh", "list", env=session).returncode, 0)
        env = self.trace("gh")["env"]
        self.assertEqual(env["PMZILLA_GH_ISSUE_RACINE"], str(self.workspace))
        self.assertEqual(env["PMZILLA_GH_ISSUE_BASES_LECTURE"], f"{self.sessions}:{self.etapes}")
        self.assertEqual(env["PMZILLA_GH_ISSUE_BASES_SORTIE"], str(self.sessions))

    def test_la_racine_de_l_outil_de_file(self):
        """B4 : le dossier courant physique s'il est le workspace ou un worktree inscrit, sinon le workspace."""
        inscrit, libre = self.worktree("wt-inscrit"), self.worktree("wt-libre", inscrit=False)
        (inscrit / "mothra").mkdir()
        lien = self.base / "lien-vers-le-worktree"
        lien.symlink_to(inscrit)
        cas = ((self.workspace, self.workspace), (inscrit, inscrit), (lien, inscrit), (libre, self.workspace), (inscrit / "mothra", self.workspace),
               (self.hors, self.workspace), (self.worktrees, self.workspace), (self.base, self.workspace))
        for cwd, attendu in cas:
            with self.subTest(cwd=str(cwd)):
                (self.aux / "trace-gh.json").unlink(missing_ok=True)
                self.assertEqual(self.lance("gh_issue.sh", "list", cwd=cwd).returncode, 0)
                self.assertEqual(self.trace("gh")["env"]["PMZILLA_GH_ISSUE_RACINE"], str(attendu.resolve()))

    def test_l_outil_tourne_depuis_le_dossier_des_copies_figees(self):
        """B3 : ni la configuration de uv du dossier courant de la session, ni son .python-version ne sont lus."""
        for enveloppe, args, trace in (("gh_issue.sh", ("list",), "gh"), ("flow_views.sh", ("show", "v"), "flow")):
            with self.subTest(enveloppe=enveloppe):
                self.assertEqual(self.lance(enveloppe, *args, cwd=self.hors).returncode, 0)
                self.assertEqual(self.trace(trace)["cwd"], str((self.figes / "copie").resolve()))

    def test_sans_liste_des_noms_code_97(self):
        """La liste des noms sensibles est obligatoire (elle ne l'était pas : sans elle, la variable restait absente)."""
        self.ecrire_conf(noms=None)
        self.releve()
        self.refuse(self.lance("gh_issue.sh", "list"), 97, L97.format("dossiers.conf"))

    def test_une_cle_manquante_ou_non_absolue_de_dossiers_conf_code_97(self):
        for cle in CLES_CONF:
            for valeur in (None, "relatif"):
                with self.subTest(cle=cle, valeur=valeur):
                    self.ecrire_conf(**{cle: valeur})
                    self.releve()
                    for enveloppe, args in (("gh_issue.sh", ("list",)), ("flow_views.sh", ("show", "v")), ("ci_local.sh", ("places",)),
                                            ("worktree.sh", ("add", "feat/x", "main"))):
                        self.refuse(self.lance(enveloppe, *args), 97, L97.format("dossiers.conf"))

    def test_le_scratchpad_doit_etre_un_chemin_physique_propre_au_compte(self):
        """Point (c) : jamais `/`, `/tmp`, `/private/tmp` ; ni « ~ », ni « / » final, ni lien, ni dossier absent."""
        lien = self.base / "lien-sessions"
        lien.symlink_to(self.sessions)
        mauvais = ("/", "/tmp", "/private/tmp", f"{self.sessions}/", "~/sessions", f"{self.base}/~x", str(lien), str(self.base / "absent"),
                   f"{self.sessions}:{self.etapes}", f"{self.base}/./sessions")
        for valeur in mauvais:
            with self.subTest(scratchpad=valeur):
                self.ecrire_conf(scratchpad=valeur)
                self.releve()
                self.refuse(self.lance("gh_issue.sh", "list"), 97, L97.format("dossiers.conf"))
        self.ecrire_conf()
        self.releve()
        self.assertEqual(self.lance("gh_issue.sh", "list").returncode, 0)

    def test_le_code_de_l_outil_figé_est_rendu(self):
        for enveloppe, args, code in (("ci_local.sh", ("run",), 5), ("gh_issue.sh", ("status", "R-1", "Ready"), 3), ("flow_views.sh", ("show", "v"), 78)):
            with self.subTest(enveloppe=enveloppe):
                nom = {"ci_local.sh": "ci", "gh_issue.sh": "gh", "flow_views.sh": "flow"}[enveloppe]
                self.ecrire(self.aux / f"code-{nom}.txt", str(code))
                self.assertEqual(self.lance(enveloppe, *args).returncode, code)

    def test_aucune_ligne_n_imprime_la_valeur_d_un_argument(self):
        canari = "VALEUR-SECRETE-9137"
        # Une sous-commande refusée est imprimée par son nom quand elle a la forme d'un mot (la ligne « sous-commande refusée : <nom> » de D12) ;
        # un texte qui n'a pas cette forme (ici avec des points) n'est jamais repris.
        libre = "valeur.secrete.9137"
        refus = (("ci_local.sh", ("run", "--index", "--worktree", f"/{canari}")), ("ci_local.sh", (libre,)),
                 ("gh_issue.sh", (libre,)), ("gh_issue.sh", ("new-idea", "--body-file", f"/{canari}/x.md")),
                 ("gh_issue.sh", ("list", f"--sortie=/{canari}/x.json")), ("flow_views.sh", (libre,)),
                 ("worktree.sh", ("add", f"main-{canari}", "main")), ("worktree.sh", ("add", f"bonne/{canari}", f"absente-{canari}")),
                 ("worktree.sh", (libre,)))
        for enveloppe, args in refus:
            with self.subTest(enveloppe=enveloppe, args=args):
                r = self.lance(enveloppe, *args)
                self.assertEqual(r.returncode, 96, r.stdout + r.stderr)
                self.assertNotIn(canari, r.stdout + r.stderr)
                self.assertNotIn(libre, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")


def git(*args, cwd, env_extra=None):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}
    env.update(env_extra or {})
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} : {r.stderr}")
    return r.stdout.strip()


class CreationDeWorktree(Dossier):
    def setUp(self):
        super().setUp()
        git("init", "-q", cwd=self.workspace)
        git("symbolic-ref", "HEAD", "refs/heads/main", cwd=self.workspace)
        self.ecrire(self.workspace / "README.md", "base\n")
        git("add", "-A", cwd=self.workspace)
        git("commit", "-q", "-m", "initial", cwd=self.workspace)
        git("branch", "base-ok", cwd=self.workspace)
        git("tag", "une-etiquette", cwd=self.workspace)
        self.commit = git("rev-parse", "HEAD", cwd=self.workspace)

    def ajoute(self, branche, base, **kw):
        return self.lance("worktree.sh", "add", branche, base, **kw)

    def dossiers_des_worktrees(self):
        return sorted(p.name for p in self.worktrees.iterdir())

    def test_cree_la_branche_depuis_la_base_et_le_worktree_sous_le_dossier_des_worktrees(self):
        r = self.ajoute("spec/exemple-n2", "base-ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        dossier = self.worktrees / "wt-spec-exemple-n2"
        self.assertTrue((dossier / ".git").is_file())
        self.assertTrue((dossier / "README.md").is_file())
        self.assertEqual(git("rev-parse", "spec/exemple-n2", cwd=self.workspace), self.commit)
        self.assertEqual(git("symbolic-ref", "--short", "HEAD", cwd=dossier), "spec/exemple-n2")
        self.assertEqual(self.dossiers_des_worktrees(), ["wt-spec-exemple-n2"])
        self.assertEqual(git("worktree", "list", "--porcelain", cwd=self.workspace).count("worktree "), 2)

    def test_chaque_barre_oblique_devient_un_tiret(self):
        self.assertEqual(self.ajoute("feat/a/b", "main").returncode, 0)
        self.assertTrue((self.worktrees / "wt-feat-a-b").is_dir())
        self.assertEqual(self.ajoute("simple", "main").returncode, 0)
        self.assertTrue((self.worktrees / "wt-simple").is_dir())

    def test_nom_vide_ou_commencant_par_main_code_96_et_rien_cree(self):
        for nom in ("", "main", "main-x", "mainline", "main/x"):
            with self.subTest(nom=nom):
                r = self.ajoute(nom, "base-ok")
                self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("branche")), r.stdout)
        self.assertEqual(self.dossiers_des_worktrees(), [])
        self.assertEqual(git("branch", "--list", cwd=self.workspace).count("\n"), 1)         # main et base-ok seulement

    def test_nom_invalide_pour_git_code_96(self):
        for nom in ("-x", "--force", "a..b", "x y", "a~1", "x/", ".cache", "a.lock", "x:y"):
            with self.subTest(nom=nom):
                r = self.ajoute(nom, "base-ok")
                self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("branche")))
        self.assertEqual(self.dossiers_des_worktrees(), [])

    def test_les_noms_que_git_developperait_sont_refuses(self):
        """R3 : `HEAD` et tout nom qui contient `@{` (`@{-1}`, `main@{1}`) ne sont ni une branche ni une base."""
        for nom in ("HEAD", "@{-1}", "feat@{1}", "x@{u}"):
            with self.subTest(branche=nom):
                r = self.ajoute(nom, "base-ok")
                self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("branche")), r.stdout)
            with self.subTest(base=nom):
                r = self.ajoute("feat/y", nom)
                self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("base")), r.stdout)
        self.assertEqual(self.dossiers_des_worktrees(), [])

    def test_le_nombre_d_arguments_est_controle_en_premier(self):
        """R3 : quatre arguments ou plus : « argument refusé : base », même quand la branche est elle-même refusée."""
        for args in (("add", "-x", "main", "en-trop"), ("add", "", "", "a", "b"), ("add", "feat/x", "absente", "en-trop")):
            with self.subTest(args=args):
                r = self.lance("worktree.sh", *args)
                self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("base")))
        self.assertEqual(self.dossiers_des_worktrees(), [])

    def test_la_base_est_lue_dans_refs_heads_meme_quand_une_etiquette_porte_le_meme_nom(self):
        git("branch", "double", cwd=self.workspace)                                    # la branche : le commit initial
        self.ecrire(self.workspace / "suite.md", "suite\n")
        git("add", "-A", cwd=self.workspace)
        git("commit", "-q", "-m", "suite", cwd=self.workspace)
        git("tag", "double", cwd=self.workspace)                                       # l'étiquette de même nom : le commit suivant
        etiquette = git("rev-parse", "refs/tags/double", cwd=self.workspace)
        self.assertNotEqual(etiquette, self.commit)
        r = self.ajoute("feat/double", "double")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(git("rev-parse", "feat/double", cwd=self.workspace), self.commit)

    def test_les_crochets_et_la_configuration_de_git_viennent_de_dossiers_conf(self):
        """Ceinture de B1 : core.hooksPath posé par l'environnement l'emporte sur celui du dépôt, que la session peut écrire."""
        du_depot = self.hors / "crochets-du-depot"
        for dossier, marque in ((self.crochets, "conf"), (du_depot, "depot")):
            dossier.mkdir(parents=True, exist_ok=True)
            crochet = dossier / "post-checkout"
            crochet.write_text(f'#!/bin/sh\necho {marque} >> "{self.aux}/crochet-{marque}.txt"\n', encoding="utf-8")
            crochet.chmod(0o755)
        git("config", "core.hooksPath", str(du_depot), cwd=self.workspace)
        r = self.ajoute("feat/crochets", "main", env={"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": str(du_depot)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.aux / "crochet-conf.txt").exists())
        self.assertFalse((self.aux / "crochet-depot.txt").exists())

    def test_sans_argument_la_branche_est_refusee_puis_la_base(self):
        r = self.lance("worktree.sh", "add")
        self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("branche")))
        r = self.lance("worktree.sh", "add", "feat/x")
        self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("base")))
        r = self.lance("worktree.sh", "add", "feat/x", "main", "en-trop")
        self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("base")))
        self.assertEqual(self.dossiers_des_worktrees(), [])

    def test_base_qui_n_est_pas_une_branche_locale_code_96(self):
        for base in ("", "absente", "une-etiquette", self.commit, self.commit[:8], "origin/main", "refs/heads/absente", "HEAD", "-x", "--detach"):
            with self.subTest(base=base):
                r = self.ajoute("feat/x", base)
                self.assertEqual((r.returncode, r.stderr.strip()), (96, L96_ARG.format("base")), r.stdout)
        self.assertEqual(self.dossiers_des_worktrees(), [])
        self.assertNotIn("feat/x", git("branch", "--list", cwd=self.workspace))

    def test_branche_existante_ouverte_nulle_part_est_rouverte_sans_etre_recreee(self):
        # R-20261110-22 (Q10), remplace test_branche_deja_existante_rend_le_code_de_git : une branche locale qui existe et n'est ouverte dans aucun
        # worktree est reprise telle quelle (git worktree add sans -b), jamais recréée ni ramenée sur la base.
        self.ecrire(self.workspace / "suite.md", "suite\n")
        git("add", "-A", cwd=self.workspace)
        git("commit", "-q", "-m", "suite", cwd=self.workspace)                    # main avance ; la branche reste sur le commit initial
        git("branch", "reprise", self.commit, cwd=self.workspace)
        self.assertNotEqual(git("rev-parse", "main", cwd=self.workspace), self.commit)
        r = self.ajoute("reprise", "main")
        self.assertEqual(r.returncode, 0, r.stderr)
        dossier = self.worktrees / "wt-reprise"
        self.assertTrue((dossier / ".git").is_file())
        self.assertEqual(git("symbolic-ref", "--short", "HEAD", cwd=dossier), "reprise")
        self.assertEqual(git("rev-parse", "reprise", cwd=self.workspace), self.commit)       # non ramenée sur main
        self.assertFalse((dossier / "suite.md").exists())
        self.assertEqual(self.dossiers_des_worktrees(), ["wt-reprise"])

    def test_branche_ouverte_dans_un_autre_worktree_rend_le_code_de_git(self):
        # Le code de refus de git dépend de sa version (128 sur le Mac, 255 dans l'image de la CI) : il est mesuré sur le même git,
        # par la même commande lancée directement, puis comparé à celui que rend l'enveloppe. Aucun code de l'enveloppe n'est ajouté.
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.workspace), "GIT_CONFIG_NOSYSTEM": "1"}
        git("branch", "occupee", cwd=self.workspace)
        git("worktree", "add", "-q", str(self.hors / "ouvert"), "occupee", cwd=self.workspace)
        direct = subprocess.run(["git", "worktree", "add", str(self.hors / "direct"), "occupee"], cwd=str(self.workspace),
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(direct.returncode, 0, direct.stderr)
        r = self.ajoute("occupee", "main")
        self.assertEqual(r.returncode, direct.returncode, r.stderr)
        self.assertIn("occupee", r.stderr)
        self.assertEqual(self.dossiers_des_worktrees(), [])
        self.assertFalse((self.hors / "direct").exists())

    def test_reglage_local_du_chemin_de_la_liste_pose_et_ignore_par_git(self):
        # Comme tools/worktree.sh : .claude/settings.local.json porte le chemin de la liste des noms sensibles de dossiers.conf. La liste n'est jamais
        # ouverte (test d'existence seulement). Posé seulement quand git l'ignore dans le worktree créé ; sinon rien n'est écrit et le code reste 0.
        reglage = ".claude/settings.local.json"
        r = self.ajoute("feat/sans-ignore", "main")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.worktrees / "wt-feat-sans-ignore" / reglage).exists())
        self.ecrire(self.workspace / ".gitignore", f"{reglage}\n")
        git("add", "-A", cwd=self.workspace)
        git("commit", "-q", "-m", "ignorer le réglage local", cwd=self.workspace)
        r = self.ajoute("feat/avec-ignore", "main")
        self.assertEqual(r.returncode, 0, r.stderr)
        dossier = self.worktrees / "wt-feat-avec-ignore"
        contenu = json.loads((dossier / reglage).read_text(encoding="utf-8"))
        self.assertEqual(contenu["env"], {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms), "PMZILLA_NOMS": str(self.noms)})
        git("check-ignore", "-q", reglage, cwd=dossier)
        self.assertEqual(git("status", "--porcelain", cwd=dossier), "")
        self.assertEqual(self.noms.read_text(encoding="utf-8"), "fictif\n")

    def test_reglage_local_jamais_ecrit_par_un_lien_de_la_branche(self):
        """Le dossier .claude d'une branche qui est un lien : l'enveloppe, hors du bac à sable, n'écrit rien à travers lui. Ici le chemin passe par la
        branche « non ignoré » : git check-ignore échoue au-delà d'un lien, donc le réglage est jugé non ignoré et rien n'est écrit."""
        cible = self.hors / "cible"
        cible.mkdir()
        self.ecrire(self.workspace / ".gitignore", ".claude/settings.local.json\n")
        os.symlink(cible, self.workspace / ".claude")
        git("add", "-A", cwd=self.workspace)
        git("commit", "-q", "-m", "un lien .claude", cwd=self.workspace)
        r = self.ajoute("feat/lien", "main")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(cible.iterdir()), [])

    def test_les_variables_git_de_la_session_ne_passent_pas(self):
        autre = self.hors / "autre-depot"
        autre.mkdir()
        git("init", "-q", cwd=autre)
        r = self.ajoute("feat/env", "main", env={"GIT_DIR": str(autre / ".git"), "GIT_WORK_TREE": str(autre), "GIT_INDEX_FILE": str(autre / "x"),
                                                 "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/inexistant"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(git("rev-parse", "feat/env", cwd=self.workspace), self.commit)
        self.assertNotIn("feat/env", git("branch", "--list", cwd=autre))

    def test_empreinte_controlee_avant_tout(self):
        (self.figes / "dossiers.conf").write_text((self.figes / "dossiers.conf").read_text(encoding="utf-8") + "# x\n", encoding="utf-8")
        r = self.ajoute("feat/x", "main")
        self.assertEqual((r.returncode, r.stderr.strip()), (97, L97.format("dossiers.conf")))
        self.assertEqual(self.dossiers_des_worktrees(), [])

    def test_liste_des_noms_absente_code_3_rien_cree(self):
        self.noms.unlink()
        r = self.ajoute("feat/sans-liste", "main")
        self.assertEqual((r.returncode, r.stderr.strip()), (3, "outil figé : liste des noms sensibles absente ; rien n'est créé"), r.stdout)
        self.assertEqual(self.dossiers_des_worktrees(), [])
        self.assertNotIn("feat/sans-liste", git("branch", "--list", cwd=self.workspace))

    # --- 7.7 : ni npm ni aucun autre programme que git ----------------------------------------------------------------------------------
    def test_aucun_npm_ni_script_d_installation_meme_quand_la_base_en_declare_un(self):
        bin_faux = self.base / "bin-faux"
        bin_faux.mkdir()
        appels = self.aux / "appels-npm.txt"
        for programme in ("npm", "npx", "node"):
            faux = bin_faux / programme
            faux.write_text(f'#!/bin/sh\necho "{programme} $@" >> "{appels}"\n', encoding="utf-8")
            faux.chmod(0o755)
        marqueur = self.aux / "marqueur-installation"
        paquet = {"name": "x", "version": "1.0.0", "scripts": {"install": f"touch {marqueur}", "postinstall": f"touch {marqueur}",
                                                                "prepare": f"touch {marqueur}"}}
        self.ecrire(self.workspace / "mothra" / "package.json", json.dumps(paquet))
        self.ecrire(self.workspace / "mothra" / "package-lock.json", json.dumps({"name": "x", "lockfileVersion": 3, "packages": {}}))
        git("add", "-A", cwd=self.workspace)
        git("commit", "-q", "-m", "paquet avec un script d'installation", cwd=self.workspace)
        git("branch", "base-npm", cwd=self.workspace)
        env = {"PATH": f"{bin_faux}:/usr/bin:/bin", "WORKTREE_NPM": str(bin_faux / "npm"), "npm_config_ignore_scripts": "false"}
        r = self.ajoute("feat/npm", "base-npm", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.worktrees / "wt-feat-npm" / "mothra" / "package.json").is_file())
        self.assertFalse(appels.exists(), "un faux npm, npx ou node a été appelé")
        self.assertFalse(marqueur.exists(), "un script d'installation a tourné")
        self.assertFalse((self.worktrees / "wt-feat-npm" / "mothra" / "node_modules").exists())

    def test_l_enveloppe_n_appelle_que_git_et_les_outils_du_relevé(self):
        """Lecture statique des lignes de code (hors commentaires) de l'enveloppe : aucun programme d'installation n'y figure."""
        code = [l for l in (SOURCE / "worktree.sh").read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]
        for mot in ("npm", "npx", "node", "yarn", "pnpm", "uv", "python", "pip", "make", "docker", "gh"):
            for ligne in code:
                self.assertIsNone(re.search(rf"(?<![\w-]){re.escape(mot)}(?![\w-])", ligne), f"{mot} : {ligne}")


class Rafraichissement(unittest.TestCase):
    """Le script de copie (tâche 7.3) : liste fermée, copies à l'identique, relevé lu par les enveloppes et par le contrôle du doctor."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.dest = self.base / "outils-figes"
        self.dest.mkdir()
        (self.base / "sessions").mkdir()
        (self.dest / "dossiers.conf").write_text("".join(f"{cle}={self.base / dossier}\n" for cle, dossier in
                                                         (("maison", "maison"), ("workspace", "workspace"), ("worktrees", "worktrees"),
                                                          ("etapes", "etapes"), ("scratchpad", "sessions"), ("donnees", "donnees"),
                                                          ("noms", "noms.txt"), ("crochets", "crochets"), ("cache_uv", "cache-uv"))) +
                                                 f"python={sys.executable}\n", encoding="utf-8")

    def depot_sans_git(self):
        """Une image des fichiers de la liste, sans .git (comme le dossier de préparation de la fin d'un train) : les contrôles Git de R-20261110-06 n'y valent pas."""
        depot = self.base / "image"
        for genre, chemin in liste_figee():
            source = SOURCE / chemin if genre == "E" else RACINE / chemin
            cible = (depot / "tools" / "outils_figes" / chemin) if genre == "E" else depot / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(source.read_bytes())
        (depot / "tools" / "outils_figes" / "liste.txt").write_bytes((SOURCE / "liste.txt").read_bytes())
        return depot

    def copie(self, depot=None, dest=None):
        depot = depot or self.depot_sans_git()
        return subprocess.run(["/bin/bash", str(SOURCE / "rafraichir.sh"), str(depot), str(dest or self.dest), "--extrait-du-train"], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"})

    def test_copie_chaque_fichier_de_la_liste_et_ecrit_le_relevé(self):
        r = self.copie()
        self.assertEqual(r.returncode, 0, r.stderr)
        liste = liste_figee()
        attendus = {}
        for genre, chemin in liste:
            source = SOURCE / chemin if genre == "E" else RACINE / chemin
            cible = self.dest / (chemin if genre == "E" else f"copie/{chemin}")
            self.assertTrue(cible.is_file() and not cible.is_symlink(), chemin)
            self.assertEqual(cible.read_bytes(), source.read_bytes(), chemin)
            attendus[cible.relative_to(self.dest).as_posix()] = sha(cible)
        attendus["dossiers.conf"] = sha(self.dest / "dossiers.conf")
        lignes = (self.dest / "empreintes.sha256").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lignes), len(attendus))
        for ligne in lignes:
            self.assertRegex(ligne, r"^[0-9a-f]{64}  \S+$")
        self.assertEqual({l.split("  ", 1)[1]: l.split("  ", 1)[0] for l in lignes}, attendus)
        self.assertEqual([l.split("  ", 1)[1] for l in lignes], sorted(l.split("  ", 1)[1] for l in lignes))
        self.assertNotIn("empreintes.sha256", "".join(lignes))
        self.assertEqual(sorted(p.name for p in self.dest.glob("*nouveau*")), [])         # aucun fichier temporaire laissé

    @SANS_SOURCE_GEREE
    def test_le_relevé_est_lu_par_le_module_partage_et_couvre_les_enveloppes_exclues(self):
        self.assertEqual(self.copie().returncode, 0)
        self.assertIsNotNone(sandbox_config.lire_releve(self.dest))
        self.assertEqual(sandbox_config.ecarts_releve(self.dest, RACINE), [])       # aucune enveloppe exclue ne manque, aucune copie ne diffère

    def test_les_enveloppes_reelles_acceptent_le_relevé_reel(self):
        self.assertEqual(self.copie().returncode, 0)
        for enveloppe, args in (("ci_local.sh", ("build",)), ("gh_issue.sh", ("bogus",)), ("flow_views.sh", ("list",)), ("worktree.sh", ("remove",))):
            with self.subTest(enveloppe=enveloppe):
                r = subprocess.run(["/bin/bash", str(self.dest / enveloppe), *args], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
                self.assertEqual(r.returncode, 96, r.stderr)          # le relevé est passé (sinon 97) ; la sous-commande est refusée

    @SANS_SOURCE_GEREE
    def test_une_copie_modifiee_apres_coup_est_vue_par_l_enveloppe_et_par_le_module(self):
        self.assertEqual(self.copie().returncode, 0)
        (self.dest / "copie" / "tools" / "db.py").write_text("# modifié\n", encoding="utf-8")
        r = subprocess.run(["/bin/bash", str(self.dest / "flow_views.sh"), "show", "v"], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual((r.returncode, r.stderr.strip()), (97, L97.format("copie/tools/db.py")))
        self.assertEqual(sandbox_config.ecarts_releve(self.dest, RACINE), ["copie/tools/db.py"])

    def test_un_second_passage_donne_le_meme_relevé(self):
        self.assertEqual(self.copie().returncode, 0)
        premier = (self.dest / "empreintes.sha256").read_bytes()
        self.assertEqual(self.copie().returncode, 0)
        self.assertEqual((self.dest / "empreintes.sha256").read_bytes(), premier)

    def test_sans_dossiers_conf_code_4_et_rien_n_est_copie(self):
        (self.dest / "dossiers.conf").unlink()
        r = self.copie()
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), [])

    def test_source_absente_code_4_avant_toute_copie(self):
        depot = self.base / "depot"
        (depot / "tools" / "outils_figes").mkdir(parents=True)
        (depot / "tools" / "outils_figes" / "liste.txt").write_text("E ci_local.sh\nC tools/absent.py\n", encoding="utf-8")
        (depot / "tools" / "outils_figes" / "ci_local.sh").write_text("x\n", encoding="utf-8")
        r = self.copie(depot)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def test_ligne_de_liste_refusee_code_4(self):
        for ligne in ("C ../hors.py", "C /absolu.py", "X tools/x.py", "C tools/avec espace.py"):
            with self.subTest(ligne=ligne):
                depot = self.base / "depot"
                (depot / "tools" / "outils_figes").mkdir(parents=True, exist_ok=True)
                (depot / "tools" / "outils_figes" / "liste.txt").write_text(ligne + "\n", encoding="utf-8")
                r = self.copie(depot)
                self.assertEqual(r.returncode, 4, r.stderr)

    def test_usage_code_2(self):
        r = subprocess.run(["/bin/bash", str(SOURCE / "rafraichir.sh")], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.copie(RACINE, self.base / "absent").returncode, 2)


class Liste(unittest.TestCase):
    """La liste fermée, ses dépendances (7.1) et son accord avec le fichier géré : un écart fait échouer ces tests."""

    def test_chaque_fichier_de_la_liste_existe(self):
        for genre, chemin in liste_figee():
            self.assertTrue(((SOURCE if genre == "E" else RACINE) / chemin).is_file(), chemin)

    @SANS_SOURCE_GEREE
    def test_les_enveloppes_exclues_par_le_fichier_gere_sont_dans_la_liste(self):
        noms_e = {chemin for genre, chemin in liste_figee() if genre == "E"}
        self.assertLessEqual(sandbox_config.noms_figes_attendus(RACINE), noms_e)
        self.assertLessEqual(set(ENVELOPPES) | {"enveloppe.sh"}, noms_e)
        self.assertEqual(noms_e, set(ENVELOPPES) | {"enveloppe.sh"})

    def test_les_reglages_de_la_file_sont_figes_et_exiges_par_l_enveloppe_de_l_outil_de_file(self):
        """Point (b) : gh_issue.py lit tools/roadmap_settings.yaml dans le dossier du code, donc dans la copie figée ; l'enveloppe le relève."""
        self.assertIn(("C", "tools/roadmap_settings.yaml"), liste_figee())
        texte = (SOURCE / "gh_issue.sh").read_text(encoding="utf-8").replace("\\\n", " ")
        self.assertIn("copie/tools/roadmap_settings.yaml", re.search(r"^fige_verifier (.*)$", texte, re.M).group(1).split())

    def test_pas_de_doublon_dans_la_liste(self):
        lignes = liste_figee()
        self.assertEqual(len(lignes), len(set(lignes)))

    def test_chaque_enveloppe_exige_au_relevé_des_noms_qui_viennent_de_la_liste(self):
        possibles = {"dossiers.conf"} | {chemin if genre == "E" else f"copie/{chemin}" for genre, chemin in liste_figee()}
        for nom in ENVELOPPES:
            texte = (SOURCE / nom).read_text(encoding="utf-8")
            m = re.search(r"^fige_verifier (.*)$", texte.replace("\\\n", " "), re.M)
            self.assertIsNotNone(m, nom)
            exigés = m.group(1).split()
            self.assertIn(nom, exigés)
            self.assertLessEqual(set(exigés), possibles, nom)

    def test_les_dependances_locales_des_outils_figes_sont_dans_la_liste(self):
        """Source : les imports des fichiers Python figés et les `$ICI/...` du script de CI ; un import qui sort de la liste fait échouer ce test."""
        figes = {chemin for genre, chemin in liste_figee() if genre == "C"}
        a_lire = [c for c in figes if c.endswith(".py")]
        manquants = []
        for chemin in a_lire:
            for ligne in (RACINE / chemin).read_text(encoding="utf-8").splitlines():
                m = re.match(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", ligne)
                if m and (RACINE / "tools" / f"{m.group(1)}.py").is_file() and f"tools/{m.group(1)}.py" not in figes:
                    manquants.append(f"{chemin} importe tools/{m.group(1)}.py")
        code = [l for l in (RACINE / "tools" / "ci_local.sh").read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]
        texte = "\n".join(code)
        for ref in set(re.findall(r'\$ICI/([A-Za-z0-9_./-]+)', texte)):
            visee = (Path("tools") / ref).as_posix()
            visee = os.path.normpath(visee)
            if visee not in figes:
                manquants.append(f"tools/ci_local.sh lit {visee}")
        self.assertEqual(sorted(set(manquants)), [])

    def test_aucun_chemin_de_test_dans_les_fichiers_de_l_outillage_figé(self):
        for chemin in SOURCE.iterdir():
            texte = chemin.read_text(encoding="utf-8")
            self.assertNotRegex(texte, r"\b(tests|mothra)/", chemin.name)


if __name__ == "__main__":
    unittest.main()
