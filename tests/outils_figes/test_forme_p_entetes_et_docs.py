"""Les en-têtes des enveloppes et la documentation disent la forme unique (bash-sandbox-n2, tâche 19.9, design D13 ; R-20261111-22, -29, -38).

 - les lignes d'usage des quatre enveloppes exclues du bac à sable sont écrites dans la forme `/bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/…`
   (R-20261111-48 : le chemin absolu de la base des comptes, jamais `~` ni le nom du compte dans un fichier suivi) ;
   `npm_ci.sh` ne change pas (elle n'est pas exclue) ;
 - le paragraphe « limite réelle » dit ce que `-p` ferme sur le /bin/bash 3.2 (ENV, BASH_ENV, fonctions importées, SHELLOPTS), que CDPATH reste tenu par la
   relance sous `env -i` et par la garde de session, et ce qui reste à la garde (PATH, IFS, LANG, LC_*) ; l'ancien ordre `-p --noprofile --norc` n'y figure plus
   que pour être refusé ;
 - orchestration.md (règle de l'appel, appel imprimé par le lanceur) et installation.md (enveloppes exclues, lanceur) donnent la même forme.

Remplace : rien. Retrait : avec le bac à sable.

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh outils_figes
"""
import re
import unittest

import test_outils_figes as base

FORME = "/bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/"   # R-20261111-48 : jamais `~`, jamais le nom du compte (fichiers suivis)
ANCIEN_ORDRE = "/bin/bash -p --noprofile --norc"
EXCLUES = ("ci_local", "gh_issue", "flow_views", "worktree")
DOCS = base.RACINE / "docs" / "pmzilla"
# orchestration.md est exclu de l'édition publique (manifeste) : les cas qui le lisent sautent quand il est absent, avec un message qui le nomme ; dans le dépôt
# privé il existe et ces cas tournent comme avant. Un test statique de tests/build_edition le garde (R-20261114-107).
ORCHESTRATION_ABSENTE = "docs/pmzilla/orchestration.md absent (exclu de l'édition publique)"
SANS_ORCHESTRATION = unittest.skipUnless((DOCS / "orchestration.md").is_file(), ORCHESTRATION_ABSENTE)


def entete(nom):
    texte = (base.SOURCE / nom).read_text(encoding="utf-8")
    lignes = []
    for ligne in texte.splitlines():
        if not ligne.startswith("#"):
            break
        lignes.append(ligne)
    return "\n".join(lignes)


class EnTetes(unittest.TestCase):
    def test_la_ligne_d_usage_est_dans_la_forme_unique(self):
        for nom in EXCLUES:
            with self.subTest(enveloppe=nom):
                usage = [l for l in entete(f"{nom}.sh").splitlines() if f"outils-figes/{nom}.sh" in l]
                self.assertTrue(usage, "aucune ligne d'usage")
                for ligne in usage:
                    self.assertIn(FORME + f"{nom}.sh", ligne)
                    self.assertNotRegex(ligne, r"(?<!-p )(?<!/)\bbash ~/")
                    self.assertNotIn(f"-p ~/.pmzilla-lab/outils-figes/{nom}.sh", ligne)   # revue C6 : `-p ~/…` refusé, la forme écrite est `<dossier personnel>`

    def test_npm_ci_ne_change_pas(self):
        self.assertIn("bash ~/.pmzilla-lab/outils-figes/npm_ci.sh <chemin absolu d'un worktree>", entete("npm_ci.sh"))

    def test_le_paragraphe_de_limite_reelle_dit_ce_que_p_ferme_et_ce_qui_reste_a_la_garde(self):
        for nom in EXCLUES + ("enveloppe",):
            with self.subTest(enveloppe=nom):
                texte = re.sub(r"\s*\n#\s*", " ", entete(f"{nom}.sh"))
                self.assertIn("-p", texte)
                for mot in ("BASH_ENV", "CDPATH", "env -i", "PATH", "IFS"):
                    self.assertIn(mot, texte, mot)
                self.assertNotIn("jusqu'à la forme `/bin/bash -p --noprofile --norc`", texte)
                self.assertNotIn(ANCIEN_ORDRE, texte.replace(f"l'ancien ordre `{ANCIEN_ORDRE}`", ""))


class Documentation(unittest.TestCase):
    @SANS_ORCHESTRATION
    def test_orchestration_regle_de_l_appel_et_appel_imprime(self):
        texte = (DOCS / "orchestration.md").read_text(encoding="utf-8")
        forme_anglaise = FORME.replace("<dossier personnel>", "<home directory>")   # R-20261111-48 : les docs sont en anglais
        self.assertIn(f"`{forme_anglaise}ci_local.sh run --travail --worktree ~/PMZilla-Lab/worktrees/<n> <suites>`", texte)
        regle = [l for l in texte.splitlines() if l.startswith("- **Rule of the call.**")]
        self.assertEqual(len(regle), 1)
        self.assertIn("/bin/bash --noprofile --norc -p", regle[0])
        self.assertIn("<home directory>/.pmzilla-lab/outils-figes/", regle[0])   # revue C6
        remplace = [l for l in texte.splitlines() if l.startswith("- **Replaces:** the direct commands of the local CI runner")]
        self.assertEqual(len(remplace), 1)
        self.assertIn("/bin/bash --noprofile --norc -p", remplace[0])

    @SANS_ORCHESTRATION
    def test_orchestration_garde_la_forme_de_npm_ci(self):
        texte = (DOCS / "orchestration.md").read_text(encoding="utf-8")
        self.assertIn("`bash ~/.pmzilla-lab/outils-figes/npm_ci.sh <absolute path of the worktree>`", texte)

    def test_installation_dit_la_forme_a_deux_endroits(self):
        lignes = (DOCS / "installation.md").read_text(encoding="utf-8").splitlines()
        exclues = [l for l in lignes if l.startswith("- **Excluded commands (frozen envelopes).**")]
        runner = [l for l in lignes if l.startswith("- **The test runner under the sandbox.**")]
        self.assertEqual((len(exclues), len(runner)), (1, 1))
        for ligne in (exclues[0], runner[0]):
            self.assertIn("/bin/bash --noprofile --norc -p", ligne)
            self.assertIn("<home directory>/.pmzilla-lab/outils-figes/", ligne)   # revue C6 : la forme écrite des docs

    def test_installation_dit_les_lignes_observees_de_la_sonde(self):
        """Revue C13 : la puce « The probe » nomme les lignes observées (R4-security, V10-*, V11-*) et leur ligne `observé … non compté`."""
        puce = [l for l in (DOCS / "installation.md").read_text(encoding="utf-8").splitlines() if l.startswith("- **The probe.**")]
        self.assertEqual(len(puce), 1)
        for mot in ("R4-security", "V10", "V11", "non compté"):
            self.assertIn(mot, puce[0], mot)

    def test_aucune_doc_n_ecrit_l_ancienne_forme_des_quatre(self):
        for nom in ("orchestration.md", "installation.md"):
            with self.subTest(doc=nom):
                if not (DOCS / nom).is_file():
                    self.skipTest(f"docs/pmzilla/{nom} absent (exclu de l'édition publique)")   # seul orchestration.md est exclu ; installation.md reste publié
                texte = (DOCS / nom).read_text(encoding="utf-8")
                for env in EXCLUES:
                    self.assertNotRegex(texte, rf"(?<!-p )(?<!/)\bbash ~/\.pmzilla-lab/outils-figes/{env}\.sh", f"{nom} : {env}")
                    self.assertNotIn(f"-p ~/.pmzilla-lab/outils-figes/{env}.sh", texte, f"{nom} : {env} (revue C6 : jamais `-p ~/…`)")


if __name__ == "__main__":
    unittest.main()
