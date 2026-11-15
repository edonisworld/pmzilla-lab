"""
Les quatre enveloppes figées exclues du bac à sable, appelées dans leur forme unique (bash-sandbox-n2, tâches 19.2 et 19.3, design D13 ; R-20261111-19, -29).

    /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/<enveloppe>.sh …

R-20261111-48 : le dossier personnel est celui de la base des comptes (le même calcul que la garde de session) ; la forme avec `~` n'est plus la forme.

 - 19.2 : épingles de NON-RÉGRESSION (R-20261111-40 point 9) : des commandes factices placées en tête du PATH et un IFS piégé : aucune n'est appelée, les codes ne
   changent pas (l'enveloppe n'appelle aucune commande par son nom avant d'avoir remis PATH et IFS à zéro). Ce qui neutralise les factices est la relance de
   l'enveloppe sous un environnement vidé (R-20261111-13), PAS `-p` : sous `-p`, bash importe PATH (suite forme_p_mac, M3). Ces tests ne prouvent donc pas que `-p`
   ferme PATH ou IFS ; ils épinglent que la relance vidée les neutralise ;
 - 19.3 : contrat : ni une règle deny, ni la garde npm, ni la garde de session ne refuse la forme admise (modèle : test_npm_ci_enveloppe.py, classe
   ContratAvecLesGardes).

Remplace : rien. Retrait : avec le bac à sable.

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh outils_figes
"""
import json
import os
import pwd
import re
import subprocess
import sys
import unittest
from pathlib import Path

import test_outils_figes as base

RACINE = base.RACINE
HOME_DES_COMPTES = os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir)   # R-20261111-48 : la base des comptes, jamais HOME ni `~`
PREFIXE = f"/bin/bash --noprofile --norc -p {HOME_DES_COMPTES}/.pmzilla-lab/outils-figes/"
# Les vrais arguments des quatre enveloppes (design D13, section Tests) : un appel de chaque sorte.
APPELS = (
    PREFIXE + "ci_local.sh places --json",
    PREFIXE + "ci_local.sh run --travail --worktree ~/PMZilla-Lab/worktrees/wt-a une_suite",
    PREFIXE + "gh_issue.sh view R-742/u3 --sortie /scratchpad/vue.json",
    PREFIXE + "gh_issue.sh list --label type:feature",
    PREFIXE + "gh_issue.sh sync-tasks R-1 --groups 2-8,11",
    PREFIXE + "gh_issue.sh edit R-1 --set key=value",
    PREFIXE + "flow_views.sh show v_team_status --lang fr",
    PREFIXE + "worktree.sh add spec/x-n2 main",
)
COMMANDES_FACTICES = ("cut", "dirname", "basename", "shasum", "sha256sum", "env", "git", "cat", "grep", "sed", "awk", "tr", "head", "tail", "readlink",
                      "realpath", "mktemp", "sleep", "ls", "uv", "date", "id", "whoami", "sort", "wc", "xargs", "find", "touch", "mkdir", "rm", "test", "pwd")
FAUSSE = """#!/bin/bash
echo "{nom}" >> "{aux}/factice-appelee.txt"
exit 77
"""


class FormeUniqueSansFactices(base.Dossier):
    """19.2 : fausses commandes en tête du PATH et IFS piégé, la chaîne exacte de la forme admise. Épingles de non-régression : les factices sont neutralisées par la
    relance sous environnement vidé des enveloppes, pas par `-p` (R-20261111-40 point 9)."""

    def setUp(self):
        super().setUp()
        self.factices = self.base / "factices"
        self.factices.mkdir()
        for nom in COMMANDES_FACTICES:
            self.ecrire(self.factices / nom, FAUSSE.format(nom=nom, aux=self.aux))
            (self.factices / nom).chmod(0o755)

    def lance_p(self, enveloppe, *args, piege=False):
        environ = {"PATH": "/usr/bin:/bin", "HOME": str(self.base)}
        if piege:
            environ.update({"PATH": f"{self.factices}:/usr/bin:/bin", "IFS": "/.-_e"})
        return subprocess.run(["/bin/bash", "--noprofile", "--norc", "-p", str(self.figes / enveloppe), *args], capture_output=True, text=True,
                              cwd=str(self.base), env=environ)

    def test_aucune_commande_factice_n_est_appelee_et_les_codes_ne_changent_pas(self):
        # Une entrée de plus pour npm_ci.sh (hors des quatre, mais elle partage le même début) : un chemin absolu qui n'est pas un worktree, refus 96.
        cas = (("ci_local.sh", ("places", "--json")), ("ci_local.sh", ("build",)), ("gh_issue.sh", ("list",)), ("gh_issue.sh", ("zzz",)),
               ("flow_views.sh", ("show", "v")), ("flow_views.sh", ("zzz",)), ("worktree.sh", ("remove",)), ("worktree.sh", ("add", "x", "main")),
               ("npm_ci.sh", (str(self.hors),)))
        for enveloppe, args in cas:
            with self.subTest(enveloppe=enveloppe, args=args):
                temoin = self.lance_p(enveloppe, *args)
                for fichier in self.aux.glob("trace-*"):
                    fichier.unlink()
                piege = self.lance_p(enveloppe, *args, piege=True)
                self.assertFalse((self.aux / "factice-appelee.txt").exists(), (self.aux / "factice-appelee.txt").read_text() if (self.aux / "factice-appelee.txt").exists() else "")
                self.assertEqual(piege.returncode, temoin.returncode, piege.stderr)
                self.assertEqual(piege.stderr, temoin.stderr)

    def test_le_temoin_les_factices_sont_bien_en_tete_du_path_du_test(self):
        """Contrôle de sensibilité : lancée par son nom avec ce PATH, une factice tourne et laisse sa trace (sinon le test précédent ne prouverait rien)."""
        r = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", "cut -c1"], capture_output=True, text=True, env={"PATH": f"{self.factices}:/usr/bin:/bin"})
        self.assertEqual(r.returncode, 77)
        self.assertTrue((self.aux / "factice-appelee.txt").exists())


class ContratFormeUnique(unittest.TestCase):
    """19.3 : l'appel dans la forme unique n'est refusé ni par la garde npm, ni par les règles deny, ni par la garde de session."""

    def test_la_garde_npm_ne_refuse_pas_la_forme(self):
        sys.path.insert(0, str(RACINE / "tools"))
        try:
            import npm_guard
        finally:
            sys.path.pop(0)
        for commande in APPELS:
            for cwd in (None, str(RACINE), str(RACINE / "mothra")):
                with self.subTest(commande=commande, cwd=cwd):
                    donnees = {"tool_name": "Bash", "tool_input": {"command": commande}}
                    if cwd is not None:
                        donnees["cwd"] = cwd
                    self.assertEqual(npm_guard.main([], json.dumps(donnees)), 0)

    def test_aucune_regle_deny_n_apparie_la_forme(self):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        motifs = []
        for regle in reglages["permissions"]["deny"]:
            if regle.startswith("Bash(") and regle.endswith(")"):
                motif = regle[len("Bash("):-1]
                motifs.append((regle, re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)))
        self.assertTrue(motifs)
        for commande in APPELS + (APPELS[0].replace(HOME_DES_COMPTES, "/Users/quelquun", 1),):
            with self.subTest(commande=commande):
                self.assertEqual([regle for regle, m in motifs if m.fullmatch(commande)], [])

    def test_la_garde_de_session_ne_refuse_pas_la_forme(self):
        sys.path.insert(0, str(RACINE / "tools"))
        try:
            import garde_session
        finally:
            sys.path.pop(0)
        contexte = garde_session.Contexte(cwd=str(RACINE), espace=str(RACINE), controle_configuration=False)
        for commande in APPELS:
            with self.subTest(commande=commande):
                v = garde_session.decider(commande, contexte)
                self.assertIsNone(v, v)

    def test_la_garde_de_session_refuse_la_forme_avec_tilde(self):
        """R-20261111-48 : la forme avec `~` n'est plus admise ; la garde la refuse, la forme au chemin de la base des comptes passe (test ci-dessus)."""
        sys.path.insert(0, str(RACINE / "tools"))
        try:
            import garde_session
        finally:
            sys.path.pop(0)
        contexte = garde_session.Contexte(cwd=str(RACINE), espace=str(RACINE), controle_configuration=False)
        for commande in APPELS:
            tilde = commande.replace(HOME_DES_COMPTES, "~", 1)
            with self.subTest(commande=tilde):
                v = garde_session.decider(tilde, contexte)
                self.assertEqual(v.cle if v else None, "E-enveloppe")


if __name__ == "__main__":
    unittest.main()
