"""Règles `deny` de npm, npx, node et des autres gestionnaires de paquets (change mothra-session-guards, design D1 à D5, idée #383,
spec tooling-permission-guards). Bloc réduit par la décision de l'auteur du 2026-10-20 au soir (option e) : les formes de #383 et de la
spec validée, sous les têtes de chemins actuelles.

La session ne lance ni `npm install` (ni `i`, ni `add`), ni `npm ci` (`--offline` compris), ni `npm update`, ni `npm audit fix`, ni
`npm publish`, ni `npm exec` (ni `x`), ni `npx`, ni `node -e`, `--eval`, `-p`, `--print` (drapeaux combinés comme `-pe` compris) ou
`node -` (programme sur l'entrée standard), ni pnpm, yarn, bun, bunx ou corepack. Elle garde `npm test`, `npm run <script>`, `npm start`
(gardé par le refus du serveur sans base jetable, mothra-slices F2), `npm ls`, `npm view`, `npm outdated`, `npm audit` sans `fix`,
`npm help`, `npm --version`, `npm config get`, `node --version` et le lancement d'un fichier par `node <fichier>`.
Une règle compare le texte de la commande de la session, jamais une commande qu'un script lance en dedans : le `npm ci --offline` que
tools/worktree.sh lance après le oui de l'auteur reste permis (mothra-npm-ready : « The rule list of #383 must not refuse it »).

Formes de D2 : 1 et 2 (nue, options avant la sous-commande) par une seule tête `npm*` ; 3 (`cd … &&`, `cd …;`) ; 4 (`env`, avec ou sans
variables) ; 5 (chemins absolus de l'installation de l'auteur) : l'alias par défaut de fnm sous ses trois écritures (`/Users/*/`, `~/`,
`$HOME/`) et le préfixe Homebrew (`/opt/homebrew/bin/`). La garde partagée n'interdit que le joker en tête NU (spec
tooling-permission-guards) ; ce module est plus strict par Q10 et D2 (5) : aucune règle ne commence par un joker, pas même `*/`.
Un mot de quatre lettres ou plus est une règle ouverte (`install*`) ; un mot plus court est ancré par deux règles (`i` et `i *`).

Effet général énoncé : la tête `npm*` admet n'importe quoi avant le mot ; tout mot d'argument qui commence par un mot refusé ouvert, ou
qui égale un mot refusé ancré, déclenche le refus : `npm run install-check`, `npm help install`, `npm run build -- --target x`.

Limites déclarées (design, « Risks and limits », et guide), assertées NON refusées : abréviations uniques et écritures camelCase de npm
(`npm upd`, `npm cleanInstall`), aliases et sous-commandes de npm hors de ce bloc (`npm up`, `npm uninstall`, `npm version`, `npm config
set`…), autres formes de node (`node` seul, `-i`, `node < fichier`, `--import data:`), chemins par shell de fnm, `fnm exec`, toute forme
lancée par un script ou un lanceur intermédiaire (`sh -c`, `bash -c`, `command`, `time`, `nohup`), un programme passé à node par un tube.
Condition décidée : aucun premier commit de code sous mothra/ sans le crochet PreToolUse qui résout ces commandes comme npm lui-même.

Conception (même motif que test_settings_deny_push_merge.py) : l'auteur pose le bloc (tâche 6.1). La suite reste VERTE avant et après :
 - la matrice des formes s'applique au bloc déclaré, toujours ;
 - les tests « dans le fichier de réglages » sont SAUTÉS tant qu'aucune règle du bloc n'y est (« règles npm et Node non posées »),
   ÉCHOUENT dès que le bloc est partiel (« garde npm : règle absente de .claude/settings.json : <règle> ») et rejouent la matrice contre
   les règles RÉELLES quand tout y est.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_npm.py --json        (le bloc à copier dans permissions.deny)
    python3 tests/settings_deny/test_settings_deny_npm.py --familles    (le bloc par famille : une ligne par commande)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny import motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
SAUT = "règles npm et Node non posées"
ABSENTE = "garde npm : règle absente de .claude/settings.json : "
JOKER = "garde npm : joker en tête de règle : "


class Moteur:
    """Même règle de correspondance que les autres modules (`*` vaut toute suite, le reste est littéral, la commande entière), avec un
    filtre rapide : une commande ne passe à l'expression que si elle commence par le premier morceau littéral et contient les autres."""

    def __init__(self, regles):
        self.regles = []
        for regle in regles:
            if regle.startswith("Bash(") and regle.endswith(")"):
                motif = regle[len("Bash("):-1]
                morceaux = motif.split("*")
                self.regles.append((regle, morceaux[0], [m for m in morceaux[1:] if m], motif_en_regex(motif)))

    @staticmethod
    def _correspond(entree, commande: str) -> bool:
        _, debut, autres, expression = entree
        return commande.startswith(debut) and all(m in commande for m in autres) and bool(expression.fullmatch(commande))

    def interdite(self, commande: str) -> bool:
        return any(self._correspond(e, commande) for e in self.regles)

    def regles_mortes(self, commandes) -> list:
        commandes = list(commandes)
        return [e[0] for e in self.regles if not any(self._correspond(e, c) for c in commandes)]


# --- Le bloc déclaré ---------------------------------------------------------------------------------------------------------------------

# Sous-commandes de #383 et de la spec validée, avec les seuls alias que la spec nomme (`i`, `add`, `x`) ; `ci` vient de Q7.
MOTS_NPM = ("install", "i", "add", "ci", "update", "audit fix", "publish", "exec", "x")
MOTIFS_NODE = ("-e*", "--eval*", "-p*", "--print*", "-", "- *")
GESTIONNAIRES = ("pnpm*", "pnpx*", "pnx*", "pn", "pn *", "yarn*", "bun", "bun *", "bunx*", "corepack*")
GESTIONNAIRES_FNM = ("pnpm*", "pnpx*", "pnx*", "pn", "pn *")   # installés par l'auteur dans l'installation de fnm (inventaire 1.2)

FNM = ".local/share/fnm/aliases/default/bin/"
RACINES_ABSOLUES = (f"/Users/*/{FNM}", f"~/{FNM}", f"$HOME/{FNM}", "/opt/homebrew/bin/")
RACINES_FNM = RACINES_ABSOLUES[:3]


def motifs_du_mot(mot: str) -> list:
    return [f"{mot}*"] if len(mot) >= 4 else [mot, f"{mot} *"]


def motifs_npm() -> list:
    return [m for mot in MOTS_NPM for m in motifs_du_mot(mot)]


def tetes(commande: str, racines=RACINES_ABSOLUES) -> list:
    """Têtes des formes 3 à 5 de D2 pour une commande ; la forme nue vient en premier."""
    return [commande, f"cd * && {commande}", f"cd *; {commande}", f"env *{commande}"] + [f"{r}{commande}" for r in racines]


def regles_npm() -> list:
    return [f"Bash({t} {m})" for t in tetes("npm*") for m in motifs_npm()]


def regles_npx() -> list:
    return [f"Bash({t})" for t in tetes("npx*")]


def regles_node() -> list:
    return [f"Bash({t}{milieu}{m})" for t in tetes("node") for milieu in (" ", " * ") for m in MOTIFS_NODE]


def regles_gestionnaires() -> list:
    sorties = [f"Bash({t}{g})" for t in ("", "cd * && ", "cd *; ", "env *") for g in GESTIONNAIRES]
    sorties += [f"Bash({r}{g})" for r in RACINES_FNM for g in GESTIONNAIRES_FNM]
    sorties += [f"Bash(/opt/homebrew/bin/{g})" for g in GESTIONNAIRES]
    return sorties


def regles_attendues() -> list:
    """Le bloc à ajouter à permissions.deny de .claude/settings.json (imprimé par --json)."""
    return regles_npm() + regles_npx() + regles_node() + regles_gestionnaires()


def familles() -> list:
    """Le bloc par famille, une ligne par commande : (commande, têtes, règles) ; la somme des règles est la taille du bloc."""
    lignes = [(f"npm {m}", 8, 8 * len(motifs_du_mot(m))) for m in MOTS_NPM]
    lignes.append(("npx", 8, 8))
    lignes += [(f"node {m.rstrip(' *')}" + (" (avec argument)" if m.endswith(" *") else ""), 8, 16) for m in MOTIFS_NODE]
    for g in GESTIONNAIRES:
        if g.endswith(" *"):
            continue
        nom = g.rstrip("*")
        nb_formes = 2 if f"{nom} *" in GESTIONNAIRES else 1
        nb_tetes = 5 + (3 if g in GESTIONNAIRES_FNM else 0)
        lignes.append((nom, nb_tetes, nb_tetes * nb_formes))
    return lignes


def jokers_en_tete(regles) -> list:
    """Une ligne par règle Bash(...) dont le motif commence par un joker (Q10 et D2 (5) : pas même `*/`)."""
    return [f"{JOKER}{r}" for r in regles if r.startswith("Bash(") and r[len("Bash("):].startswith("*")]


def manquantes_dans(deny: list) -> list:
    """Les lignes d'échec d'une pose partielle (vide si rien n'est posé ou si tout l'est)."""
    presentes = [r for r in regles_attendues() if r in deny]
    if not presentes:
        return []
    return [f"{ABSENTE}{r}" for r in regles_attendues() if r not in deny]


def deny_de(chemin: Path) -> list:
    return json.loads(chemin.read_text(encoding="utf-8")).get("permissions", {}).get("deny", [])


# --- Les formes de commande --------------------------------------------------------------------------------------------------------------

ABS_FNM = ("/Users/quelquun/.local/share/fnm/aliases/default/bin/", "~/.local/share/fnm/aliases/default/bin/",
           "$HOME/.local/share/fnm/aliases/default/bin/")
LANCEURS_NPM = (
    "npm {}", "npm --prefix mothra {}", "npm -w server {}", "npm --workspace=web {}", "npm --prefix=mothra --loglevel silent {}",
    "cd mothra && npm {}", "cd ~/PMZilla-Lab/worktrees/wt-feat-x/mothra && npm --prefix . {}", "cd mothra; npm {}",
    "env npm {}", "env NODE_ENV=test npm {}", "env -u NPM_TOKEN npm --prefix mothra {}",
) + tuple(f"{r}npm {{}}" for r in ABS_FNM) + ("/opt/homebrew/bin/npm {}", "/opt/homebrew/bin/npm --prefix mothra {}",
                                             "env /opt/homebrew/bin/npm {}")
SUITES = ("", " fastify")
SPECIALES = ("ci --offline", "ci --offline --ignore-scripts", "install --save-dev typescript", "audit fix --force", "x tsc",
             "exec -- tsc", "update fastify", "publish --dry-run")

LANCEURS_NPX = ("npx {}", "cd mothra && npx {}", "cd mothra; npx {}", "env npx {}", "env CI=1 npx {}") + tuple(
    f"{r}npx {{}}" for r in ABS_FNM) + ("/opt/homebrew/bin/npx {}",)
SUITES_NPX = ("tsc", "--yes create-vite x", "-p typescript tsc")

TETES_NODE = ("node", "cd mothra && node", "cd mothra; node", "env node", "env NODE_ENV=test node") + tuple(
    f"{r}node" for r in ABS_FNM) + ("/opt/homebrew/bin/node",)
LANCEURS_NODE = tuple(f"{t} {o}{{}}" for t in TETES_NODE for o in ("", "--no-warnings ", "--trace-warnings --stack-size=900 "))
EVALUATIONS = ('-e "require(\'pg\')"', "--eval 1+1", "-p process.version", "--print 1", "-pe 1", "-ep 1", "-", "- < script.js",
               "--input-type=module -e 'import(\"pg\")'", "--input-type=module --eval x")

LANCEURS_GESTIONNAIRES = ("{}", "cd mothra && {}", "cd mothra; {}", "env {}", "env CI=1 {}", "/opt/homebrew/bin/{}")
GESTIONNAIRES_COMMANDES = ("pnpm install", "pnpm add fastify", "pnpx tsc", "pnx tsc", "pn", "pn install", "yarn", "yarn add fastify",
                           "yarnpkg install", "bun install", "bun", "bunx tsc", "corepack enable", "corepack prepare pnpm@latest")
GESTIONNAIRES_FNM_COMMANDES = ("pnpm install", "pnpx tsc", "pnx tsc", "pn", "pn install")

PERMISES = (
    "npm test", "npm t", "npm tst", "npm test -- --run", "npm run build", "npm run-script build", "npm run lint", "npm run typecheck",
    "npm run dev", "npm run clean", "npm start", "npm ls", "npm ls --all", "npm list", "npm view fastify", "npm view fastify version",
    "npm view fastify dist-tags", "npm view fastify --json", "npm info fastify", "npm outdated", "npm audit", "npm audit --json",
    "npm help", "npm --version", "npm -v", "npm config get registry", "npm explain fastify", "npm why fastify",
    "npm --prefix mothra test", "npm --prefix mothra run build", "npm -w server run build", "npm --workspace=web test",
    "cd mothra && npm test", "cd mothra && npm run build", "cd mothra; npm start", "env NODE_ENV=test npm test",
    f"{ABS_FNM[1]}npm test", f"{ABS_FNM[0]}npm run build", "/opt/homebrew/bin/npm start",
    "node --version", "node -v", "node server.js", "node --test tests/", "node --env-file=.env server.js", "node --inspect server.js",
    "node --experimental-strip-types src/index.ts", "cd mothra && node dist/server.js", f"{ABS_FNM[2]}node --version",
    'grep -rn "npm install" docs/', 'grep -n "npm ci --offline" tools/worktree.sh', "git grep npx", 'git grep -n "npm exec"',
    'grep -n "node -e" CLAUDE.md', 'rg "pnpm install" docs', 'grep -rn "yarn add" openspec', 'git grep -n "corepack"',
    "bash tools/worktree.sh feat/mothra-slice-0", "bash tools/worktree.sh feat/x", "bash tests/run_all.sh mothra",
    "bash tools/ci_local.sh run", "bash tests/run_all.sh settings_deny", "uv run tools/pilot.py freeze --check",
    "git commit -m x", "git status --short", "fnm list", "fnm current", "command -v npm",
)

# Effets énoncés (D2 et effet général), assertés refusés : ils ne sont pas cachés.
EFFETS = (
    "npm --prefix mothra run install-check",      # D2 : un script dont le nom commence par une sous-commande refusée, options avant run
    "npm run install-check",                      # même effet sans option : la tête `npm*` couvre les formes 1 et 2 d'une seule règle
    "npm run update-snapshots",
    "npm help install",
    "npm install --help",
    "npm run build -- --target x",                # un mot refusé ancré nu en argument (i, x, ci, add)
    "node app.js -p 3000",                        # un argument qui ressemble à une option d'évaluation, après un fichier
)

# Limites déclarées (décision du 2026-10-20 au soir, option e), assertées NON refusées : le crochet PreToolUse les couvrira.
LIMITES = (
    "npm upd", "npm inst fastify", "npm isntall fastify", "npm cleanInstall", "npm clean-install", "npm ic", "npm up",
    "npm upgrade", "npm uninstall fastify", "npm rm fastify", "npm link", "npm version patch",
    "npm config set registry https://exemple.invalid", "npm pkg set name=y", "npm explore fastify", "npm unpublish fastify",
    "npm dist-tag rm fastify beta",
    "node", "node -i", "node --interactive", "node < script.js", "node --import=data:text/javascript,x", 'echo "1" | node',
    "~/.local/state/fnm_multishells/123_456/bin/npm install", "fnm exec npm install", 'sh -c "npm install"', 'bash -c "npm ci"',
    "command npm install", "time npm install", "nohup npm install",
)


def refusees():
    """Toutes les commandes que le bloc doit refuser."""
    for lanceur, mot, suite in itertools.product(LANCEURS_NPM, MOTS_NPM, SUITES):
        yield lanceur.format(mot + suite)
    for lanceur, speciale in itertools.product(LANCEURS_NPM, SPECIALES):
        yield lanceur.format(speciale)
    for lanceur, suite in itertools.product(LANCEURS_NPX, SUITES_NPX):
        yield lanceur.format(suite)
    yield "npx"
    for lanceur, evaluation in itertools.product(LANCEURS_NODE, EVALUATIONS):
        yield lanceur.format(evaluation)
    for lanceur, commande in itertools.product(LANCEURS_GESTIONNAIRES, GESTIONNAIRES_COMMANDES):
        yield lanceur.format(commande)
    for racine, commande in itertools.product(ABS_FNM, GESTIONNAIRES_FNM_COMMANDES):
        yield f"{racine}{commande}"


def non_refusees(moteur: Moteur, commandes) -> list:
    return [c for c in commandes if not moteur.interdite(c)]


def refusees_a_tort(moteur: Moteur, commandes) -> list:
    return [c for c in commandes if moteur.interdite(c)]


# --- Le bloc déclaré ---------------------------------------------------------------------------------------------------------------------

class Declaration(unittest.TestCase):
    def test_comptes(self):
        self.assertEqual(len(motifs_npm()), 13)
        self.assertEqual((len(regles_npm()), len(regles_npx()), len(regles_node()), len(regles_gestionnaires())), (104, 8, 96, 65))
        self.assertEqual(len(regles_attendues()), 273)

    def test_les_familles_rendent_compte_du_bloc(self):
        self.assertEqual(sum(n for _, _, n in familles()), len(regles_attendues()))

    def test_le_bloc_passe_la_garde_partagee(self):
        self.assertEqual(garde_regles.constats(regles_attendues()), [])

    def test_la_garde_partagee_trouve_la_liste_sans_declaration(self):
        self.assertTrue(garde_regles.imprime_json(Path(__file__).read_text(encoding="utf-8")))
        self.assertEqual(garde_regles._liste_du_module(Path(__file__), garde_regles.CONVENTION), regles_attendues())

    def test_aucune_regle_write_ni_notebookedit_ni_vide(self):
        for regle in regles_attendues():
            self.assertTrue(regle.startswith("Bash(") and regle.endswith(")") and regle != "Bash()", regle)

    def test_aucun_joker_en_tete(self):
        self.assertEqual(jokers_en_tete(regles_attendues()), [])

    def test_un_joker_en_tete_est_refuse_et_nomme(self):
        self.assertEqual(jokers_en_tete(["Bash(npm install*)", "Bash(*/npm install*)", "Bash(* npm ci)"]),
                         [f"{JOKER}Bash(*/npm install*)", f"{JOKER}Bash(* npm ci)"])

    def test_chaque_regle_d_ancrage_absolu_commence_par_un_chemin_connu(self):
        for regle in regles_attendues():
            motif = regle[len("Bash("):-1]
            if motif.startswith("/"):
                self.assertTrue(motif.startswith(("/Users/*/.local/share/fnm/", "/opt/homebrew/bin/")), regle)

    def test_les_mots_courts_sont_ancres(self):
        """Un mot de trois lettres ou moins n'est jamais une règle ouverte : `npm* i*` refuserait `npm info`."""
        for motif in motifs_npm():
            if motif.endswith("*") and " " not in motif:
                self.assertGreaterEqual(len(motif.rstrip("*")), 4, motif)


class MatriceDuBloc(unittest.TestCase):
    """La matrice contre le bloc déclaré, toujours (verte avant comme après la pose)."""

    @classmethod
    def setUpClass(cls):
        cls.bloc = Moteur(regles_attendues())

    def test_chaque_forme_refusee(self):
        manquantes = non_refusees(self.bloc, refusees())
        self.assertEqual(manquantes[:10], [], f"{len(manquantes)} commande(s) non refusée(s)")

    def test_formes_de_la_spec(self):
        """Les scénarios de la spec validée, mot pour mot."""
        for commande in ("npm install fastify", "npm i", "npm --prefix mothra install", "cd mothra && npm ci", "npm ci --offline",
                         "env npm update", "/opt/homebrew/bin/npm install", "npx fastify", "cd mothra && npx tsc", "npm exec fastify",
                         'node -e "1"', "node --print 1", "node -pe 1", "node - < script.js", "yarn add fastify", "pnpm install",
                         "bunx fastify", "npm --prefix mothra run install-check"):
            self.assertTrue(self.bloc.interdite(commande), commande)

    def test_commandes_permises_non_refusees(self):
        self.assertEqual(refusees_a_tort(self.bloc, PERMISES), [])

    def test_npm_start_permis(self):
        for commande in ("npm start", "npm --prefix mothra start", "cd mothra && npm start"):
            self.assertFalse(self.bloc.interdite(commande), commande)

    def test_l_offre_du_worktree_n_est_pas_refusee(self):
        """Le `npm ci --offline` de tools/worktree.sh tourne dans le script : la ligne de la session ne nomme que le script."""
        for commande in ("bash tools/worktree.sh feat/mothra-slice-0", "bash tools/worktree.sh feat/x --yes", "zsh tools/worktree.sh feat/x"):
            self.assertFalse(self.bloc.interdite(commande), commande)

    def test_effets_enonces_refuses(self):
        for commande in EFFETS:
            self.assertTrue(self.bloc.interdite(commande), f"effet énoncé non refusé : {commande}")

    def test_limites_declarees_non_refusees(self):
        """Les limites du design et du guide, assertées telles quelles : elles attendent le crochet PreToolUse."""
        self.assertEqual(refusees_a_tort(self.bloc, LIMITES), [])

    def test_chaque_regle_refuse_au_moins_une_commande_de_la_matrice(self):
        mortes = self.bloc.regles_mortes(list(refusees()) + list(EFFETS))
        self.assertEqual(mortes, [], "règle(s) qu'aucune forme de la matrice n'exerce")


class FichierDeReglages(unittest.TestCase):
    """Le fichier réel : rien à poser par la session (tâche 6.1, l'auteur)."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_de(REGLAGES)
        cls.presentes = [r for r in regles_attendues() if r in cls.deny]

    def test_aucune_regle_du_bloc_deja_posee_hors_pose_complete(self):
        """Une règle du bloc déjà dans le fichier serait dupliquée par la pose : seuls 0 (avant) ou tout le bloc (après) sont admis."""
        self.assertIn(len(self.presentes), (0, len(regles_attendues())),
                      "\n".join(manquantes_dans(self.deny)[:10]))

    def test_les_regles_existantes_ne_refusent_pas_les_commandes_permises(self):
        moteur = Moteur([r for r in self.deny if r not in set(regles_attendues())])
        self.assertEqual(refusees_a_tort(moteur, PERMISES), [], "refusées par une règle déjà dans .claude/settings.json")

    def test_pose_partielle_sur_un_faux_fichier(self):
        bloc = regles_attendues()
        self.assertEqual(manquantes_dans(["Read(./a)"]), [])
        self.assertEqual(manquantes_dans(bloc), [])
        self.assertEqual(manquantes_dans(bloc[1:]), [f"{ABSENTE}{bloc[0]}"])


class DansLeFichierDeReglages(unittest.TestCase):
    """Sauté avant la pose, échoue si la pose est partielle, rejoue la matrice si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_de(REGLAGES)
        cls.posees = any(r in cls.deny for r in regles_attendues())

    def setUp(self):
        if not self.posees:
            self.skipTest(SAUT)

    def test_tout_le_bloc_est_pose(self):
        lignes = manquantes_dans(self.deny)
        self.assertEqual(lignes, [], "\n" + "\n".join(lignes[:20]))

    def test_la_matrice_contre_les_regles_reelles(self):
        if manquantes_dans(self.deny):
            self.skipTest("pose partielle : voir test_tout_le_bloc_est_pose")
        reel = Moteur(self.deny)
        manquantes = non_refusees(reel, refusees())
        self.assertEqual(manquantes[:10], [], f"{len(manquantes)} commande(s) non refusée(s) par les règles réelles")
        self.assertEqual(refusees_a_tort(reel, PERMISES), [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--familles" in sys.argv:
        for commande, nb_tetes, nb_regles in familles():
            print(f"{commande} : {nb_tetes} têtes, {nb_regles} règles")
        print(f"total : {len(regles_attendues())} règles")
    else:
        unittest.main()
