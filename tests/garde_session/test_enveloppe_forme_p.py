"""Garde de session, règles `E-enveloppe` et `E-interprete` (bash-sandbox-n2, tâche 19.4, design D13 ; R-20261111-21, -29, -30, -32, -33, -35).

Les quatre enveloppes figées exclues du bac à sable (`ci_local`, `gh_issue`, `flow_views`, `worktree`) ne s'appellent que dans la forme

    /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/<enveloppe>.sh …

seule dans l'appel Bash et en mots littéraux (liste blanche de caractères du design D13) ; toute autre forme est refusée, avant et après la forme. Un refus par
forme, par opérateur et par expansion ; les témoins passent. Une fonction ou un alias nommé `bash`, `/bin/bash` ou comme une enveloppe est refusé
(`E-interprete`). La ligne de refus est écrite caractère pour caractère.

R-20261111-48 (DN2-Q1 (a)) : le dossier personnel est celui de la base des comptes (pwd.getpwuid), jamais HOME ; la forme avec `~` est refusée. Le dossier
personnel du test est celui de l'arbre jetable (le contexte le reçoit) ; la classe `HomeDeLAppelant` laisse la garde le calculer elle-même.

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh garde_session

Aucun processus. Le contrôle de la configuration effective de Git est coupé.
"""
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, g  # noqa: E402

_ARBRE = Arbre()   # un arbre pour tout le module : les chemins de la forme portent son dossier personnel (fermé par tearDownModule)
PREFIXE = f"/bin/bash --noprofile --norc -p {_ARBRE.home}/.pmzilla-lab/outils-figes/"
FORME = PREFIXE + "gh_issue.sh view 742"
LIGNE_ENVELOPPE = ("garde de session : refusé : E : enveloppe figée hors de la forme admise. Voie permise : /bin/bash --noprofile --norc -p "
                   "<dossier personnel>/.pmzilla-lab/outils-figes/<enveloppe>.sh …, seule dans son appel (ci_local, gh_issue, flow_views ou worktree).")


def tearDownModule():
    _ARBRE.fermer()
LIGNE_INTERPRETE = ("garde de session : refusé : E : fonction ou alias nommé bash, /bin/bash ou une enveloppe figée. Voie permise : un nom neutre ; "
                    "l'enveloppe s'appelle par la forme admise, seule dans son appel.")
# Les vrais arguments des quatre enveloppes (design D13, section Tests).
TEMOINS = (
    PREFIXE + "ci_local.sh places --json",
    PREFIXE + "ci_local.sh run --travail --worktree ~/PMZilla-Lab/worktrees/wt-a une_suite",
    PREFIXE + "gh_issue.sh view R-742/u3 --sortie /scratchpad/vue.json",
    PREFIXE + "gh_issue.sh list --label type:feature",
    PREFIXE + "gh_issue.sh sync-tasks R-1 --groups 2-8,11",
    PREFIXE + "gh_issue.sh edit R-1 --set key=value",
    PREFIXE + "gh_issue.sh edit R-1 --set date=2026-11-30",
    PREFIXE + "flow_views.sh show v_team_status --lang fr",
    PREFIXE + "worktree.sh add spec/x-n2 main",
    PREFIXE + "gh_issue.sh status R-1 'In progress'",
    PREFIXE + "gh_issue.sh horizon R-1 'Plus tard'",
    PREFIXE + "gh_issue.sh new-idea --title 'Une idee simple' --body-file /scratchpad/idee.md",
    "bash ~/.pmzilla-lab/outils-figes/npm_ci.sh /Users/x/PMZilla-Lab/worktrees/wt-a",
)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = _ARBRE

    def refuse(self, cle, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande, self.a.wt), cle)

    def passe(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertIsNone(self.a.cle(commande, self.a.wt))


class Ligne(Base):
    def test_la_ligne_de_e_enveloppe_caractere_pour_caractere(self):
        self.assertEqual(g.message(g.verdict("E-enveloppe")), LIGNE_ENVELOPPE)
        self.assertEqual(g.verdict("E-enveloppe").classe, "E")

    def test_la_ligne_de_e_interprete_caractere_pour_caractere(self):
        self.assertEqual(g.message(g.verdict("E-interprete")), LIGNE_INTERPRETE)
        self.assertEqual(g.verdict("E-interprete").classe, "E")


class FormeAdmise(Base):
    def test_les_temoins_de_la_forme_passent(self):
        self.passe(TEMOINS)

    def test_les_quatre_enveloppes_passent_dans_la_forme(self):
        self.passe([PREFIXE + f"{nom}.sh x" for nom in ("ci_local", "gh_issue", "flow_views", "worktree")])

    def test_npm_ci_passe_par_bash_sans_forme(self):
        self.passe(("bash ~/.pmzilla-lab/outils-figes/npm_ci.sh /un/chemin/absolu",))


class FormeAvecTilde(Base):
    """R-20261111-48 : la forme avec `~` n'est plus admise (elle devient la forme du chemin absolu) ; refusée pour chacune des quatre enveloppes."""

    def test_la_forme_avec_tilde_est_refusee_pour_chaque_enveloppe(self):
        self.refuse("E-enveloppe", [f"/bin/bash --noprofile --norc -p ~/.pmzilla-lab/outils-figes/{nom}.sh x" for nom in ("ci_local", "gh_issue", "flow_views", "worktree")])
        self.refuse("E-enveloppe", ("/bin/bash --noprofile --norc -p ~/.pmzilla-lab/outils-figes/ci_local.sh places --json",))


class HomeDeLAppelant(unittest.TestCase):
    """R-20261111-48 : le dossier personnel de la garde vient de la base des comptes (pwd.getpwuid de l'utilisateur courant), jamais de HOME : un HOME
    modifié par l'appelant ne déplace pas la forme admise."""

    def setUp(self):
        self.vrai = pwd.getpwuid(os.getuid()).pw_dir
        self.autre = os.path.realpath(tempfile.mkdtemp(prefix="autre-maison-"))   # revue C10 : un dossier jetable créé par le test
        self.addCleanup(shutil.rmtree, self.autre, True)
        self.ancien_home = os.environ.get("HOME")
        self.addCleanup(self.restaurer)

    def restaurer(self):
        if self.ancien_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.ancien_home

    def cle(self, commande):
        v = g.decider(commande, g.Contexte(controle_configuration=False))
        return v.cle if v else None

    def appel(self, dossier):
        return f"/bin/bash --noprofile --norc -p {dossier}/.pmzilla-lab/outils-figes/gh_issue.sh view 742"

    def test_le_chemin_de_la_base_des_comptes_est_admis_meme_si_home_change(self):
        os.environ["HOME"] = self.autre
        self.assertIsNone(self.cle(self.appel(self.vrai)))   # revue C4 : le chemin brut de la base des comptes, sans realpath

    def test_le_chemin_construit_sur_le_home_modifie_est_refuse(self):
        os.environ["HOME"] = self.autre
        self.assertEqual(self.cle(self.appel(self.autre)), "E-enveloppe")

    def test_le_dossier_de_la_forme_vient_de_la_base_des_comptes_et_home_des_autres_regles_reste_celui_de_main(self):
        """Revue C3 : seul `dossier_forme` (pour `forme_admise`) vient de getpwuid ; `Contexte.home`, que les autres règles lisent, reste `realpath(expanduser("~"))`."""
        os.environ["HOME"] = self.autre
        contexte = g.Contexte(controle_configuration=False)
        self.assertEqual(contexte.home, os.path.realpath(self.autre))
        self.assertEqual(contexte.dossier_forme, self.vrai)
        self.assertEqual(g.dossier_personnel(), self.vrai)


class GardeEnProcessusEnfant(unittest.TestCase):
    """Revue C2 (tâche 24.1) : la vraie garde, lancée comme Claude Code la lance (`python3 -I tools/garde_session.py`, l'entrée du crochet sur l'entrée standard),
    avec un HOME jetable dans l'environnement de l'enfant : le chemin construit sur ce HOME est refusé, celui de la base des comptes est admis."""

    GARDE = Path(__file__).resolve().parents[2] / "tools" / "garde_session.py"

    def lancer(self, dossier, home):
        commande = f"/bin/bash --noprofile --norc -p {dossier}/.pmzilla-lab/outils-figes/gh_issue.sh view 742"
        entree = json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}})
        return subprocess.run([sys.executable, "-I", str(self.GARDE)], input=entree, capture_output=True, text=True, timeout=60,
                              env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home})

    def test_le_chemin_construit_sur_le_home_de_l_enfant_est_refuse_et_celui_de_getpwuid_admis(self):
        with tempfile.TemporaryDirectory() as jetable:
            jetable = os.path.realpath(jetable)
            refuse = self.lancer(jetable, jetable)
            self.assertEqual(refuse.returncode, 2, refuse.stderr)
            self.assertIn("enveloppe figée hors de la forme admise", refuse.stderr)
            admis = self.lancer(pwd.getpwuid(os.getuid()).pw_dir, jetable)
            self.assertEqual(admis.returncode, 0, admis.stderr)


class HorsDeLaForme(Base):
    """Une enveloppe parmi les quatre appelée hors de la forme : comme programme, comme script d'un shell, de `.` ou de `source`, par un lanceur, avec une
    variable devant, dans l'ancien ordre des options (R-20261111-29)."""

    def appels(self, nom="gh_issue"):
        chemin = f"{_ARBRE.home}/.pmzilla-lab/outils-figes/{nom}.sh"   # R-20261111-48 : le chemin de la forme est absolu
        return (f"bash {chemin} list", f"/bin/bash {chemin} list", f"bash --noprofile --norc -p {chemin} list", f"/bin/bash -p {chemin} list",
                f"/bin/bash --noprofile -p {chemin} list", f"/bin/bash --norc --noprofile -p {chemin} list", f"/bin/bash --noprofile --norc {chemin} list",
                f"/bin/bash -p --noprofile --norc {chemin} list",   # l'ancien ordre (R-20261111-29)
                f"{chemin} list", f"/Users/x/.pmzilla-lab/outils-figes/{nom}.sh list", f"sh {chemin} list", f"zsh {chemin} list", f". {chemin} list",
                f"source {chemin} list", f"env /bin/bash {chemin} list", f"nohup bash {chemin} list", f"command bash {chemin} list",
                f"X=1 /bin/bash --noprofile --norc -p {chemin} list", f"env X=1 /bin/bash --noprofile --norc -p {chemin} list",
                f"exec /bin/bash --noprofile --norc -p {chemin} list", f"time /bin/bash --noprofile --norc -p {chemin} list",
                f"bash -c '/bin/bash {chemin} list'", f"/bin/bash --noprofile --norc -p {chemin} list --sortie /scratchpad/x.json; ls")

    def test_chaque_forme_hors_de_la_forme_est_refusee_pour_chaque_enveloppe(self):
        for nom in ("ci_local", "gh_issue", "flow_views", "worktree"):
            self.refuse("E-enveloppe", self.appels(nom)[:-1])

    def test_les_trois_chemins_qui_se_ressemblent_dans_la_forme(self):
        """`..`, `/./` et `//` dans le chemin (R-20261111-32), et un nom qui n'est pas l'un des quatre."""
        h = _ARBRE.home   # R-20261111-48 : la forme est celle du chemin absolu ; les mêmes refus, ici sur ce chemin
        self.refuse("E-enveloppe", (
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/../outils-figes/gh_issue.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/./gh_issue.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes//gh_issue.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/./outils-figes/gh_issue.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab//outils-figes/gh_issue.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/autre.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/enveloppe.sh list",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/dossiers.conf",
            f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/../outils-figes/npm_ci.sh /x",
        ))

    def test_lire_une_enveloppe_n_est_pas_l_appeler(self):
        self.passe(("cat ~/.pmzilla-lab/outils-figes/gh_issue.sh", "grep -n relance ~/.pmzilla-lab/outils-figes/ci_local.sh",
                    "ls ~/.pmzilla-lab/outils-figes/", "head -5 ~/.pmzilla-lab/outils-figes/worktree.sh"))


class SeuleEtLitterale(Base):
    """R-20261111-30 : la forme n'est admise que seule dans l'appel et en mots littéraux ; chaque opérateur et chaque expansion, avant et après."""

    def test_les_deux_exemples_de_la_decision(self):
        self.refuse("E-enveloppe", (PREFIXE + 'gh_issue.sh view "$(python3 x.py)"', PREFIXE + "gh_issue.sh view 742 > ~/.zshenv"))

    def test_une_expansion_ou_un_operateur_apres_la_forme(self):
        suffixes = (' "$(python3 x.py)"', " $(id)", " `id`", " $X", " ${X}", " $((1+2))", " <(ls)", " >(cat)", " > f", " >> f", " < f", " 2>&1", " >&2",
                    " &> f", " <<< x", " *", " ?", " [a]", " {a,b}", " | cat", " |& cat", " && true", " || true", "; ls", ";ls", " ; ls", " &", " & ls", "\nls",
                    "\n", " ", "  ", " ;")   # `; true` : refusé aussi depuis la tâche 21.2 (test_admissions_temporaires.py)
        self.refuse("E-enveloppe", [FORME + s for s in suffixes])

    def test_une_commande_avant_la_forme(self):
        prefixes = ("cd /x && ", "cd /x; ", "true; ", "true && ", "true || ", "ls | ", "X=1 ", "X=1; ", "echo $(", "! ", "(", "{ ", "ls &\n", "\n", " ", "time ",
                    "echo a\n")
        self.refuse("E-enveloppe", [p + FORME for p in prefixes])

    def test_la_forme_dans_une_substitution_ou_une_chaine(self):
        self.refuse("E-enveloppe", (f"echo $({FORME})", f"echo `{FORME}`", f"( {FORME} )", f"{{ {FORME}; }}", f"if true; then {FORME}; fi",
                                    f"bash -c '{FORME}'", f"eval '{FORME}'", f"for i in 1; do {FORME}; done"))


class ListeBlanche(Base):
    """Les mots après la forme sont jugés par une liste blanche de caractères (retouche 1), jamais par une liste de caractères interdits."""

    def mot(self, mot):
        return FORME + " " + mot

    def test_les_expansions_de_zsh_sans_dollar_ni_chevron(self):
        self.refuse("E-enveloppe", [self.mot(m) for m in ("=(cmd)", "=python3", "x(e:'cmd':)", "~[nom]", "~user", "~+", "~-", "~", "a~b", "--worktree=~/x", "a=~/x")])

    def test_guillemet_double_antislash_et_diese(self):
        self.refuse("E-enveloppe", [self.mot(m) for m in ('"a"', 'a"b', 'a\\b', "\\a", "#", "#742", "a#b")])

    def test_les_autres_caracteres_hors_de_la_liste(self):
        self.refuse("E-enveloppe", [self.mot(m) for m in ("@", "a@b", "%", "+", "a+b", "!", "^", "{a}", "(", ")", "[a]", "*", "?", "$", "`", "<", ">", "|", "&", ";", "é", "a é")])

    def test_les_signes_permis_passent(self):
        self.passe([self.mot(m) for m in ("R-742/u3", "key=value", "a=b", "2026-11-30", "2-8,11", "type:feature", "a_b.c", "~/x/y", "~/PMZilla-Lab/worktrees/wt-a")])

    def test_le_egal_n_est_jamais_le_premier_caractere_d_un_mot_non_quote(self):
        self.refuse("E-enveloppe", [self.mot("=x"), self.mot("--set =x")])

    def test_deux_espaces_ou_un_mot_vide_ne_passent_pas(self):
        self.refuse("E-enveloppe", (FORME + "  x", PREFIXE + "gh_issue.sh  view"))


class MotEntreApostrophes(Base):
    """R-20261111-35 : un mot entier entre apostrophes, au moins un caractère, fait de la liste blanche et de l'espace."""

    def mot(self, mot):
        return FORME + " " + mot

    def test_les_temoins(self):
        self.passe((PREFIXE + "gh_issue.sh status R-1 'In progress'", PREFIXE + "gh_issue.sh horizon R-1 'Plus tard'", self.mot("'a b c'"), self.mot("'x=~/y'"),
                    self.mot("'a'"), self.mot("'R-1/u2 : titre, simple'")))

    def test_un_refus_par_forme(self):
        self.refuse("E-enveloppe", [self.mot(m) for m in (
            "$'a'", "$'a b'", "'a'\"b\"", "\"a\"'b'", "'a'b", "b'a'", "--title='a b'", "'a", "a'", "'a'b'", "'a'\\''b'", "''", "'a;b'", "'$x'", "'a\"b'",
            "'a`b`'", "'a|b'", "'é'", "'a\\b'", "'a#b'", "'a b'c", "'a' 'b'c", "'a'\n", "'a\nb'", "'(a)'", "'a&b'", "'a>b'", "'a<b'", "'a*b'", "'a?b'")])

    def test_un_apostrophe_ferme_apres_un_mot_non_quote_ne_sauve_rien(self):
        self.refuse("E-enveloppe", (self.mot("a 'b' c; ls"), self.mot("'a' > f")))


class Interprete(Base):
    """R-20261111-33 : une fonction ou un alias nommé `bash`, `/bin/bash` ou comme une enveloppe est refusé, où qu'il soit dans la commande."""

    def test_fonctions_et_alias_nommes_comme_l_interpreteur(self):
        self.refuse("E-interprete", ("bash() { :; }", "bash () { :; }", "function bash { :; }", "function bash() { :; }", "/bin/bash() { :; }",
                                     "function /bin/bash { :; }", "function /bin/bash() { :; }", "alias bash='x'", "alias bash=x", "alias /bin/bash=x", "alias -g bash=x",
                                     "alias -s bash=x", "alias -g /bin/bash=x", "alias -- bash=x"))

    def test_fonctions_et_alias_nommes_par_le_chemin_d_une_enveloppe(self):
        for chemin in ("~/.pmzilla-lab/outils-figes/gh_issue.sh", "/Users/x/.pmzilla-lab/outils-figes/ci_local.sh", "~/.pmzilla-lab/outils-figes/../outils-figes/worktree.sh",
                       "~/.pmzilla-lab/outils-figes/./flow_views.sh", "~/.pmzilla-lab//outils-figes/gh_issue.sh"):
            self.refuse("E-interprete", (f"{chemin}() {{ :; }}", f"function {chemin} {{ :; }}", f"alias {chemin}=x", f"alias -g {chemin}=x"))

    def test_function_lit_tous_les_noms_de_la_definition(self):
        """R-20261111-40 point 2 : zsh admet `function a b … {` ; chaque nom est lu, pas seulement le premier."""
        self.refuse("E-interprete", ("function a bash { :; }", "function a b bash { :; }", "function a /bin/bash { :; }", "function a b c bash() { :; }",
                                     "function a ~/.pmzilla-lab/outils-figes/gh_issue.sh { :; }", "function sonde_a bash\n{ :; }", "ls; function a bash { :; }"))

    def test_function_a_plusieurs_noms_neutres_passe(self):
        self.passe(("function a b { :; }", "function a b c() { :; }", "function f { bash -c ls; }", "function f { :; }"))

    def test_affectations_de_functions_et_aliases_a_un_nom_interdit(self):
        """R-20261111-40 point 2 : `functions[<nom>]=…` et `aliases[<nom>]=…` définissent une fonction ou un alias sans `()` ni `alias`."""
        self.refuse("E-interprete", ("functions[bash]='x'", "functions[bash]=x", "functions[/bin/bash]=x", "aliases[bash]=x", "aliases[/bin/bash]=x",
                                     "functions['bash']=x", 'aliases["bash"]=x', "functions[~/.pmzilla-lab/outils-figes/gh_issue.sh]=x",
                                     "aliases[~/.pmzilla-lab/outils-figes/ci_local.sh]=x", "ls; functions[bash]=x", "true && aliases[bash]=x",
                                     "galiases[bash]=x", "saliases[bash]=x", "functions[bash]+=x"))

    def test_affectations_de_functions_et_aliases_a_un_nom_neutre_passent(self):
        self.passe(("functions[sonde_fct]=x", "aliases[sonde_alias]=x", "aliases[bashrc]=x", "functions[mybash]=x", "echo functions[bash]"))

    def test_une_definition_apres_une_autre_commande(self):
        self.refuse("E-interprete", ("ls; bash() { :; }", "true && alias bash=x", "echo a\nfunction /bin/bash { :; }", "ls | cat; alias -g bash=x",
                                     "echo a; ~/.pmzilla-lab/outils-figes/gh_issue.sh() { :; }", "cd /x && alias /bin/bash=x"))

    def test_les_noms_neutres_passent_les_temoins_de_x14a(self):
        self.passe(("sonde_fct() { :; }", "function sonde_fct { :; }", "alias sonde_alias='echo ok'", "alias -g sonde_alias=x", "ls; sonde_fct() { :; }",
                    "alias bashrc=x", "bash_version() { :; }", "function mybash { :; }"))

    def test_le_mot_bash_ailleurs_qu_en_nom_de_definition_passe(self):
        self.passe(("echo bash", "alias ll='bash -c ls'", "f() { bash -c ls; }"))


class AnalyseEnEchec(Base):
    """R-20261111-40 point 1 : le repli sur une analyse en échec cherche `outils-figes/` dans le texte débarrassé de `'`, `"` et `\\`, pas seulement dans le
    littéral. Une commande illisible suivie d'un nom de dossier coupé par des guillemets ou une barre oblique inverse est refusée comme le littéral."""

    def test_le_dossier_coupe_par_des_guillemets_ou_une_barre_est_refuse(self):
        coupes = ("outils-fig''es", 'outils-fig""es', "outils-fi\\g\\es", 'outils-"fig"es', "outils-f'i'g'e's", "outil\\s-figes", "outils-figes\\/")
        for coupe in coupes:
            with self.subTest(coupe=coupe):
                commande = f"ls '\n/bin/bash --noprofile --norc -p ~/.pmzilla-lab/{coupe}/gh_issue.sh list"
                self.assertEqual(self.a.cle(commande, self.a.wt), "E-enveloppe")

    def test_le_temoin_litteral_reste_refuse_et_npm_ci_reste_hors_du_repli(self):
        self.assertEqual(self.a.cle("ls '\n/bin/bash ~/.pmzilla-lab/outils-figes/gh_issue.sh list", self.a.wt), "E-enveloppe")
        self.assertIsNone(self.a.cle("echo 'abc ~/.pmzilla-lab/outils-fig''es/npm_ci.sh", self.a.wt))


class RepliFermeSurLesOutils(Base):
    """R-20261111-43 point 3 : le repli d'une analyse en échec est fermé par défaut sur tout chemin `pmzilla-lab/outils…` (pas seulement `outils-figes/`) ;
    un repli n'admet jamais. Remplace : la recherche du seul littéral `outils-figes/`. Retrait : avec le bac à sable."""

    def test_un_chemin_des_outils_sans_barre_finale_ou_voisin_est_refuse(self):
        for chemin in ("~/.pmzilla-lab/outils-figes", "~/.pmzilla-lab/outils", "~/.pmzilla-lab/outils/gh_issue.sh", "~/.pmzilla-lab/outils-*/gh_issue.sh",
                       "$HOME/.pmzilla-lab/outils-fig*", "/Users/x/.pmzilla-lab/outils-figes"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.a.cle(f"ls '\ncd {chemin}", self.a.wt), "E-enveloppe")

    def test_les_graphies_detournees_du_dossier_sont_refusees(self):
        """R-20261112-19 : `./`, `//`, une variable devant `outils-figes/`, un `cd` suivi d'un chemin relatif, `npm_ci.sh/../` ne passent pas le repli."""
        for chemin in ("~/.pmzilla-lab/./outils-figes/gh_issue.sh", "~/.pmzilla-lab//outils-figes/gh_issue.sh", "$D/outils-figes/gh_issue.sh",
                       "cd ~/.pmzilla-lab && outils-figes/gh_issue.sh", "outils-figes/npm_ci.sh/../gh_issue.sh"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.a.cle(f"ls '\n{chemin}", self.a.wt), "E-enveloppe")

    def test_le_repli_n_admet_jamais_meme_avec_la_forme_dans_le_texte(self):
        self.assertEqual(self.a.cle(f"ls '\n{FORME}", self.a.wt), "E-enveloppe")

    def test_npm_ci_et_les_textes_sans_outils_restent_hors_du_repli(self):
        self.assertIsNone(self.a.cle("echo 'abc ~/.pmzilla-lab/outils-figes/npm_ci.sh", self.a.wt))
        self.assertIsNone(self.a.cle("echo 'abc ~/.pmzilla-lab/autre", self.a.wt))


class TableauxZsh(Base):
    """R-20261111-43 point 4 : les formes de tableau zsh `set -A` et `functions=(…)` / `aliases=(…)` définissent un nom comme `functions[…]=` ; refusées comme elles."""

    def test_set_a_vers_functions_ou_aliases_avec_un_nom_interdit(self):
        self.refuse("E-interprete", ("set -A functions bash x", "set -A aliases bash x", "set -A aliases k bash", "set -A galiases /bin/bash x", "set -A saliases bash x",
                                     "set -A functions ~/.pmzilla-lab/outils-figes/gh_issue.sh x", "set -A aliases 'bash' x", "ls; set -A functions bash x",
                                     "set -Ah aliases bash x", "set +A aliases bash x"))

    def test_affectation_composee_de_functions_ou_aliases_avec_un_nom_interdit(self):
        self.refuse("E-interprete", ("aliases=(bash x)", "functions=(bash x)", "aliases+=(bash x)", "functions+=(k x /bin/bash y)", "galiases=(bash x)",
                                     "aliases=('bash' x)", "ls; aliases+=(bash x)"))

    def test_paires_cle_valeur_et_set_apres_options_refuses(self):
        """R-20261112-19 : `aliases=([bash]=x)` (clé ou valeur), `set -e -A aliases bash x` et `'set' -A …` définissent aussi un nom interdit."""
        self.refuse("E-interprete", ("aliases=([bash]=x)", "functions+=([/bin/bash]=f)", "aliases=([k]=bash)", "set -e -A aliases bash x",
                                     "'set' -A aliases bash x", "set -o posix -A aliases bash x"))

    def test_les_noms_neutres_et_les_autres_tableaux_passent(self):
        self.passe(("set -A aliases sonde x", "set -A mon_tableau bash x", "set -A functions sonde x", "aliases=(sonde x)", "functions+=(sonde x)",
                    "mon_tableau=(bash x)", "set -e", "echo set -A aliases"))


class OrdreDesRegles(Base):
    def test_regle_allexport_avant_e_enveloppe(self):
        """R-20261111-32 : la commande qui a à la fois un allexport avec une fonction et l'ancienne forme garde la clé `E` de l'allexport."""
        for commande in ("bash -c 'set -a; exec(){ builtin exec \"$@\"; }; cut(){ echo x; }; /bin/bash ~/.pmzilla-lab/outils-figes/gh_issue.sh list'",
                         "set -a; f(){ :; }; /bin/bash ~/.pmzilla-lab/outils-figes/gh_issue.sh list"):
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande, self.a.wt), "E")


if __name__ == "__main__":
    unittest.main()
