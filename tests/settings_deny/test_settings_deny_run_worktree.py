"""Règles `deny` du dossier d'exécution (change run-worktree, design D6, tâche 9.1).

Quatre protections, à ajouter par l'auteur à `permissions.deny` de .claude/settings.json (tâche 9.2) :
  1. les outils Edit, Write et NotebookEdit sont refusés sur tout chemin du dossier d'exécution (~/PMZilla-Lab/run), en forme absolue
     (« // »), relative au dossier personnel (« ~/ ») et en motif libre ; la lecture reste permise. Depuis R-84, seules les trois règles
     Edit sont écrites : une règle Edit s'applique à tous les outils qui modifient un fichier (Write et NotebookEdit compris), et les six
     règles Write et NotebookEdit d'origine sont retirées ;
  2. les commandes Git lancées avec `git -C <dossier d'exécution>` qui le modifient sont refusées (les lectures restent permises) ;
  3. `tools/run_worktree.sh create` et `update` sont refusés avec chaque lanceur et chaque façon d'écrire le chemin ; `status`, `--help`,
     la lecture du script et sa suite restent permis ;
  4. tout script refusé par le dossier tools/ l'est aussi par son chemin dans le dossier d'exécution (~/PMZilla-Lab/run/tools/<script>) ;
     depuis le désherbage du 2026-10-28 (D41), le lien du dossier du labo (~/PMZilla-Lab/<script>) n'est plus figé que pour db_backup.sh, doctor.sh,
     finish_branch.sh et finish_worktree.sh (SCRIPTS_RACINE) : db_restore_test.sh, db_up.sh, dbtest.sh et install_lab.sh n'ont pas de lien à la
     racine (tools/install_links.sh), seules leurs formes `*tools/<script>*` les refusent.

Ce fichier est écrit AVANT l'ajout de l'auteur : REGLES_R43 est la liste exacte des règles à fusionner dans permissions.deny (voir
`python3 tests/settings_deny/test_settings_deny_run_worktree.py --regles` pour les imprimer, une par ligne). Même mécanisme que
composants.py check (tâche 8.1) : tant qu'aucune n'y figure, les cas contre les vrais réglages sont SAUTÉS (la suite reste verte pour
les commits) ; si l'ajout est partiel ils échouent en nommant les règles manquantes ; une fois toutes présentes ils vérifient chaque
forme contre la vraie liste. La classe ReglesProposees évalue les mêmes cas sur les règles actuelles complétées de REGLES_R43 : elle est toujours verte.
Les formes permises sont aussi vérifiées contre les vrais réglages dans tous les cas (elles ne dépendent pas de l'ajout).
Limites : une règle ne voit pas `cd … && git …` ni un chemin relatif (`git -C ../run`), ni `bash -c '…'` ; la session n'en écrit jamais.
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import RACINE, motif_en_regex  # noqa: E402
from test_settings_deny_offsite_backup import glob_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

# Édition publique : la liste N2 (test du bac à sable, non publié) vient de test_settings_deny_gardes (liste_n2, SANS_N2), qui porte la tolérance : elle ne
# joue que si le manifeste de l'édition est absent, et échoue dans le dépôt privé quand le fichier manque (source unique, aucune copie ici).
from test_settings_deny_gardes import bac_a_sable, liste_n2, SANS_N2  # noqa: E402
BAC_A_SABLE_LIVRE = bac_a_sable is not None   # le saut de classe plus bas


# Scripts shell refusés aujourd'hui par le dossier tools/ (règles « Bash(<lanceur> *tools/<script>*) » et lancements directs).
# offsite_backup.sh y est absent : ses règles « Bash(*offsite_backup.sh <sous-commande>*) » couvrent déjà tous les chemins.
SCRIPTS_REFUSES = ("db_restore_test.sh", "db_backup.sh", "doctor.sh", "finish_branch.sh", "finish_worktree.sh", "db_up.sh",
                   "dbtest.sh", "install_lab.sh")
# Désherbage du 2026-10-28 (D41) : les règles du lien « ~/PMZilla-Lab/<script> » ne sont plus figées que pour les scripts qui ont un lien vivant à la
# racine du labo (tools/install_links.sh) ou que le cadrage « fin unique » traite à part (finish_branch.sh, finish_worktree.sh) ; db_restore_test.sh,
# db_up.sh, dbtest.sh et install_lab.sh restent refusés par leurs règles `*tools/<script>*` (ils n'ont pas de lien racine).
SCRIPTS_RACINE = ("db_backup.sh", "doctor.sh", "finish_branch.sh", "finish_worktree.sh")
FORMES_RACINE = ("~/PMZilla-Lab/{s}", "$HOME/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}")
LANCEURS_SH = ("bash", "sh", "zsh", "uv run")
COMMANDES_GIT = ("commit", "add", "rm", "mv", "restore", "checkout", "switch", "reset", "clean", "merge", "rebase", "pull", "fetch",
                 "push", "stash", "cherry-pick", "revert", "am", "apply", "update-ref", "symbolic-ref", "branch", "tag", "config",
                 "worktree", "gc", "prune")
# Désherbage du 2026-10-28 (D44) : `pull` et `push` restent refusés (fragments 38 et 26) mais par les règles générales, plus par les règles
# `git -C *PMZilla-Lab/run* <verbe>*` : le comportement est vérifié ci-dessous, la présence de ces deux règles n'est plus exigée. `merge*` reste
# (38:3-4 ne couvre que `merge` et `merge *`, pas `merge-file` ni `mergetool`).
COMMANDES_GIT_SANS_REGLE_PROPRE = ("pull", "push")
DOSSIER_EXEC = "PMZilla-Lab/run"


def formes_du_script(script, formes):
    """Les formes d'un script, sans celles du lien racine pour un script qui n'en a plus de règle."""
    return [f for f in formes if script in SCRIPTS_RACINE or f not in FORMES_RACINE]


def _regles():
    regles = []
    # R-84 : les règles Edit couvrent aussi Write et NotebookEdit ; les six règles de ces deux outils sont retirées.
    regles += [f"Edit(~/{DOSSIER_EXEC}/**)", f"Edit(//**/{DOSSIER_EXEC}/**)", f"Edit(**/{DOSSIER_EXEC}/**)"]
    regles += [f"Bash(git -C *{DOSSIER_EXEC}* {c}*)" for c in COMMANDES_GIT if c not in COMMANDES_GIT_SANS_REGLE_PROPRE]
    regles += ["Bash(*run_worktree.sh create*)", "Bash(*run_worktree.sh update*)",
               "Bash(*run_worktree.sh --language*create*)", "Bash(*run_worktree.sh --language*update*)"]
    # Chaque script refusé par tools/ l'est aussi par son lien « ~/PMZilla-Lab/<script> » (le chemin dans le dossier d'exécution,
    # …/run/tools/<script>, est déjà couvert par les règles « *tools/<script>* » existantes).
    for script in SCRIPTS_RACINE:
        regles += [f"Bash({lanceur} *PMZilla-Lab/{script}*)" for lanceur in LANCEURS_SH]
        regles += [f"Bash(~/PMZilla-Lab/{script}*)", f"Bash($HOME/PMZilla-Lab/{script}*)", f"Bash(/*PMZilla-Lab/{script}*)"]
    return regles


REGLES_R43 = _regles()

# Chemins des trois formes d'un script : dossier tools/, lien du dossier du labo, chemin dans le dossier d'exécution.
FORMES_AVEC_LANCEUR = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                       "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}",
                       "~/PMZilla-Lab/{s}", "$HOME/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}",
                       "~/PMZilla-Lab/run/tools/{s}", "$HOME/PMZilla-Lab/run/tools/{s}", "/Users/quelquun/PMZilla-Lab/run/tools/{s}")
FORMES_DIRECTES = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                   "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}",
                   "~/PMZilla-Lab/{s}", "$HOME/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}",
                   "~/PMZilla-Lab/run/tools/{s}", "$HOME/PMZilla-Lab/run/tools/{s}", "/Users/quelquun/PMZilla-Lab/run/tools/{s}")
LANCEURS_RW = ("bash", "sh", "zsh", "uv run", "uv run -q", "")   # lanceur vide : lancement direct du fichier
SOUS_COMMANDES_RW = ("create", "update", "create --language en", "update --language fr", "--language en update", "--language fr create",
                     "update --help", "create -h")
SOUS_COMMANDES_PERMISES = ("status", "status --language en", "--language en status", "--help", "-h", "--language en --help")

CHEMINS_EDITION = ("~/PMZilla-Lab/run/tools/x.py", "~/PMZilla-Lab/run/CLAUDE.md", "~/PMZilla-Lab/run/openspec/a/b.md",
                   "/Users/quelquun/PMZilla-Lab/run/tools/x.py", "/Users/quelquun/PMZilla-Lab/run/.claude/settings.json",
                   "/Users/quelquun/PMZilla-Lab/run/notebook.ipynb")
CHEMINS_EDITION_PERMIS = ("~/PMZilla-Lab/workspace/tools/x.py", "/Users/quelquun/PMZilla-Lab/workspace/tools/x.py",
                          "~/PMZilla-Lab/db_backup.sh", "/Users/quelquun/PMZilla-Lab/wt-feat-x/tools/x.py", "tools/x.py", "./tools/x.py",
                          "/Users/quelquun/PMZilla-Lab/runner/x.py")
OUTILS_EDITION = ("Edit", "Write", "NotebookEdit")

COMMANDES_PERMISES = (
    "bash tools/run_worktree.sh status", "bash tools/run_worktree.sh --language en status", "bash tools/run_worktree.sh --help",
    "bash ~/PMZilla-Lab/workspace/tools/run_worktree.sh status", "tools/run_worktree.sh status", "./tools/run_worktree.sh --help",
    "bash tests/run_all.sh", "bash tests/run_all.sh run_worktree", "bash tests/run_all.sh --staged",
    "bash tests/run_worktree/test_run_worktree.sh", "sh tests/run_worktree/test_run_worktree.sh",
    "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_run_worktree.py -q",
    "cat tools/run_worktree.sh", "head -n 40 tools/run_worktree.sh", "grep -n update tools/run_worktree.sh",
    "sed -n 1,30p tools/run_worktree.sh", "wc -l tools/run_worktree.sh", "git log --oneline -3 -- tools/run_worktree.sh",
    "ls ~/PMZilla-Lab/run", "cat ~/PMZilla-Lab/run/tools/run_worktree.sh", "head -n 5 ~/PMZilla-Lab/run/CLAUDE.md",
    "git -C ~/PMZilla-Lab/run status", "git -C ~/PMZilla-Lab/run log --oneline -5", "git -C ~/PMZilla-Lab/run diff --stat",
    "git -C /Users/quelquun/PMZilla-Lab/run rev-parse HEAD", "git -C $HOME/PMZilla-Lab/run show --stat HEAD",
    "git -C ~/PMZilla-Lab/run ls-files tools", "git -C ~/PMZilla-Lab/run rev-parse --show-toplevel",
    "git -C ~/PMZilla-Lab/run describe --always",
    "git -C ~/PMZilla-Lab/workspace commit -m x", "git -C ~/PMZilla-Lab/workspace status",
    # Les scripts refusés gardent leurs lectures et leurs suites.
    "cat tools/db_backup.sh", "cat ~/PMZilla-Lab/db_backup.sh", "head -n 20 ~/PMZilla-Lab/run/tools/db_backup.sh",
    "bash tests/db_scripts/test_db_scripts.sh", "bash tests/run_all.sh db_scripts", "ls ~/PMZilla-Lab",
)


class Verifications:
    """Évalue les cas contre `self.regles` (liste de règles de permissions.deny). Mêlé à un cas de test."""

    regles = ()

    def commande_interdite(self, commande):
        if getattr(self, "_cache_regles", None) is not self.regles:
            self._cache_regles = self.regles
            self._motifs = [motif_en_regex(r[len("Bash("):-1]) for r in self.regles if r.startswith("Bash(")]
        return any(m.fullmatch(commande) for m in self._motifs)

    def edition_interdite(self, outil, chemin, regles=None):
        """« // » = chemin absolu depuis la racine du disque, « ~/ » = depuis le dossier personnel, sinon relatif au dossier courant
        (un chemin absolu ou en ~ n'est jamais relatif). Une règle Edit s'applique à tous les outils qui modifient un fichier : c'est
        elle qui décide pour Edit, Write et NotebookEdit (R-84). `regles` : une autre liste à évaluer (défaut : self.regles)."""
        for regle in (self.regles if regles is None else regles):
            if not regle.startswith("Edit("):
                continue
            motif = regle[len("Edit("):-1]
            if motif.startswith("//"):
                if chemin.startswith("/") and glob_en_regex(motif[1:]).fullmatch(chemin):
                    return True
            elif motif.startswith("~/"):
                if chemin.startswith("~/") and glob_en_regex(motif).fullmatch(chemin):
                    return True
            elif not chemin.startswith(("/", "~")) and glob_en_regex(motif.removeprefix("./")).fullmatch(chemin.removeprefix("./")):
                return True
        return False

    def verifier_formes_interdites(self):
        for outil, chemin in itertools.product(OUTILS_EDITION, CHEMINS_EDITION):
            self.assertTrue(self.edition_interdite(outil, chemin), f"{outil} {chemin}")
        for commande in COMMANDES_GIT:
            for dossier in ("~/PMZilla-Lab/run", "$HOME/PMZilla-Lab/run", "/Users/quelquun/PMZilla-Lab/run", '"$HOME/PMZilla-Lab/run"'):
                for suite in (f"{commande}", f"{commande} -m x", f"{commande} --hard HEAD~1" if commande == "reset" else f"{commande} -f"):
                    c = f"git -C {dossier} {suite}"
                    self.assertTrue(self.commande_interdite(c), c)
        for lanceur, sous in itertools.product(LANCEURS_RW, SOUS_COMMANDES_RW):
            for chemin in FORMES_DIRECTES:
                c = f"{lanceur} {chemin.format(s='run_worktree.sh')} {sous}".strip()
                self.assertTrue(self.commande_interdite(c), c)
        for script in SCRIPTS_REFUSES:
            for lanceur in LANCEURS_SH:
                for chemin in formes_du_script(script, FORMES_AVEC_LANCEUR):
                    c = f"{lanceur} {chemin.format(s=script)}"
                    self.assertTrue(self.commande_interdite(c), c)
                    c = f"{lanceur} {chemin.format(s=script)} --help"
                    self.assertTrue(self.commande_interdite(c), c)
            for chemin in formes_du_script(script, FORMES_DIRECTES):
                c = chemin.format(s=script)
                self.assertTrue(self.commande_interdite(c), c)
                c = f"{chemin.format(s=script)} --dry-run"
                self.assertTrue(self.commande_interdite(c), c)
        for env in ("PMZILLA_LAB_RUN=/tmp/x ", "PMZILLA_LAB_RUN=~/PMZilla-Lab/run "):   # variable devant le lanceur
            for sous in ("update", "create"):
                c = f"{env}bash tools/run_worktree.sh {sous}"
                self.assertTrue(self.commande_interdite(c), c)

    def ecarts_formes_permises(self, fragment=REGLES_R43):
        """Les (outil, chemin) de CHEMINS_EDITION_PERMIS que `fragment` fait refuser : refusés(self.regles) != refusés(self.regles moins fragment).

        Invariante de R-20261111-10 (même que P1-Q1) : le fragment vérifié ne refuse aucun chemin permis ; les refus apportés par un autre
        fragment (N2, bac à sable : ~/PMZilla-Lab/workspace/tools/**) sont couverts par les tests de celui-là. Retrait par égalité de chaînes.
        Remplace : l'assertion « aucun chemin permis n'est refusé par la liste complète ». Retrait : permanent, c'est la forme qui tient
        quand un autre fragment refuse l'édition de tools/."""
        sans = [r for r in self.regles if r not in fragment]
        return [(o, c) for o, c in itertools.product(OUTILS_EDITION, CHEMINS_EDITION_PERMIS)
                if self.edition_interdite(o, c) != self.edition_interdite(o, c, sans)]

    def ecarts_formes_permises_stricts(self):
        """Les (outil, chemin) de CHEMINS_EDITION_PERMIS que self.regles moins les règles N2 fait refuser : refusés(self.regles moins N2) == [] est attendu.

        Contrôle strict de R-20261111-12 (P1-Q3 b), ajouté à ecarts_formes_permises, qui reste : seules les règles N2 (bac à sable) peuvent refuser
        un chemin permis ; toute autre règle qui en refuse un rend ce contrôle rouge. Les règles exemptées sont lues à leur source,
        regles_attendues() du test du bac à sable (via liste_n2 de test_settings_deny_gardes), jamais recopiées.
        Remplace : rien. Retrait : quand les règles N2 quittent le deny (retour à la forme stricte sans exemption) ; source des règles exemptées :
        regles_attendues(), aucune copie."""
        n2 = liste_n2()
        sans_n2 = [r for r in self.regles if r not in n2]
        return [(o, c) for o, c in itertools.product(OUTILS_EDITION, CHEMINS_EDITION_PERMIS) if self.edition_interdite(o, c, sans_n2)]

    def verifier_formes_permises(self):
        self.assertEqual(self.ecarts_formes_permises(), [])
        self.assertEqual(self.ecarts_formes_permises_stricts(), [])
        for lanceur, sous in itertools.product(("bash", "sh", "zsh", ""), SOUS_COMMANDES_PERMISES):
            c = f"{lanceur} tools/run_worktree.sh {sous}".strip()
            self.assertFalse(self.commande_interdite(c), c)
        for commande in COMMANDES_PERMISES:
            self.assertFalse(self.commande_interdite(commande), commande)


class ReglesProposees(Verifications, unittest.TestCase):
    """Les cas, évalués sur REGLES_R43 ajoutées aux règles déjà présentes (celles de tools/ couvrent les chemins du dossier d'exécution) :
    toujours verts, ils prouvent que la liste à coller fait ce que la spec demande."""

    @classmethod
    def setUpClass(cls):
        existantes = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.regles = list(dict.fromkeys(existantes + REGLES_R43))

    def test_toutes_les_formes_sont_interdites(self):
        self.verifier_formes_interdites()

    def test_les_formes_permises_restent_permises(self):
        self.verifier_formes_permises()

    def test_aucun_chemin_permis_refuse_par_r43_seul(self):
        """REGLES_R43 seules ne refusent aucun chemin de CHEMINS_EDITION_PERMIS : analogue du bloc seul du fragment 40, ferme le masquage
        d'une règle R43 trop large par les règles N2 de workspace/tools (relecture Opus de R-20261111-10, retouche R3, ajout d'assertion).
        Remplace : rien. Retrait : permanent, c'est la seule vérification de REGLES_R43 indépendante des autres fragments."""
        refuses = [(o, c) for o, c in itertools.product(OUTILS_EDITION, CHEMINS_EDITION_PERMIS) if self.edition_interdite(o, c, REGLES_R43)]
        self.assertEqual(refuses, [])

    def test_pas_de_regle_en_double(self):
        self.assertEqual(len(REGLES_R43), len(set(REGLES_R43)))

    def test_la_lecture_n_a_pas_de_regle(self):
        self.assertEqual([r for r in REGLES_R43 if r.startswith("Read(")], [])

    def test_les_scripts_listes_ont_une_regle_d_origine_dans_settings_json(self):
        """Garde la liste SCRIPTS_REFUSES honnête : chaque script y est déjà refusé par une règle « *tools/<script>* » du fichier réel."""
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        for script in SCRIPTS_REFUSES:
            self.assertIn(f"Bash(bash *tools/{script}*)", deny, script)


class DansLeFichierDeReglages(Verifications, unittest.TestCase):
    """Tâche 9.2 : l'auteur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.regles = cls.deny

    def presentes(self):
        return [r for r in REGLES_R43 if r in self.deny], [r for r in REGLES_R43 if r not in self.deny]

    def exiger_les_regles(self):
        presentes, manquantes = self.presentes()
        if not presentes:
            self.fail("tâche 9.2 : l'auteur n'a pas encore ajouté les règles du dossier d'exécution (REGLES_R43)")
        if manquantes:
            self.fail(f"{len(manquantes)} règle(s) de REGLES_R43 absente(s) de .claude/settings.json, dont : " + " ; ".join(manquantes[:5]))

    def test_les_regles_sont_dans_settings_json(self):
        self.exiger_les_regles()

    def test_toute_forme_est_interdite_par_les_regles_reelles(self):
        self.exiger_les_regles()
        self.verifier_formes_interdites()

    def test_les_formes_permises_le_sont_avec_les_regles_reelles(self):
        self.verifier_formes_permises()

    def test_aucune_regle_de_lecture_du_dossier_d_execution(self):
        self.assertEqual([r for r in self.deny if r.startswith("Read(") and DOSSIER_EXEC in r], [])


@unittest.skipUnless(BAC_A_SABLE_LIVRE, SANS_N2)
class TemoinsControleStrictHorsN2(unittest.TestCase):
    """Témoins du contrôle strict ecarts_formes_permises_stricts (R-20261111-12), sur un deny simulé : deny réel + règles N2.

    Une règle hors N2 qui refuse un chemin permis rend le contrôle rouge ; une règle N2 ne le rend pas rouge.
    Remplace : rien. Retrait : quand les règles N2 quittent le deny (retour à la forme stricte sans exemption) ; source des règles exemptées :
    regles_attendues(), aucune copie."""

    @classmethod
    def setUpClass(cls):
        reel = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.n2 = liste_n2()
        cls.deny = list(dict.fromkeys(reel + cls.n2))

    def cas(self, regles):
        class Cas(Verifications):
            pass
        c = Cas()
        c.regles = list(regles)
        return c

    def test_temoin_une_regle_hors_n2_qui_refuse_un_chemin_permis_rend_le_controle_rouge(self):
        fautive = "Edit(tools/**)"   # refuse « tools/x.py » (permis) ; distincte des règles N2 (formes en ~/ et //)
        self.assertNotIn(fautive, self.n2)
        self.assertEqual(self.cas(self.deny).ecarts_formes_permises_stricts(), [])
        ecarts = self.cas(self.deny + [fautive]).ecarts_formes_permises_stricts()
        self.assertIn(("Edit", "tools/x.py"), ecarts)
        self.assertIn(("NotebookEdit", "./tools/x.py"), ecarts)

    def test_temoin_une_regle_n2_ne_rend_pas_le_controle_rouge(self):
        n2_visant_un_chemin_permis = "Edit(~/PMZilla-Lab/workspace/tools/**)"
        self.assertIn(n2_visant_un_chemin_permis, self.n2)
        seule = self.cas([n2_visant_un_chemin_permis])   # elle refuse bien un chemin permis : l'exemption est réellement exercée
        self.assertTrue(seule.edition_interdite("Edit", "~/PMZilla-Lab/workspace/tools/x.py"))
        self.assertEqual(self.cas(self.deny + [n2_visant_un_chemin_permis]).ecarts_formes_permises_stricts(), [])
        self.assertEqual(self.cas(self.n2).ecarts_formes_permises_stricts(), [])


if __name__ == "__main__":
    if "--regles" in sys.argv:
        print("\n".join(REGLES_R43))
    else:
        unittest.main()
