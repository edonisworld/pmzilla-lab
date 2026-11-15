"""
Suite propre au Mac forme_p_mac (bash-sandbox-n2, tâche 19.1, design D13 ; R-20261111-19, -27, -29, -38) : M1 prouve, sur le vrai /bin/bash 3.2 du Mac,
ce que le mode privilégié `-p` ferme (BASH_ENV, fonction exportée, SHELLOPTS avec PS4 : chacun a son contrôle de sensibilité sans -p) ; ENV est un CONSTAT
(un bash non interactif ne le lit ni avec ni sans -p, R-20261111-40 point 4) ; M2 est un CONSTAT (CDPATH est suivi sous -p, GLOBIGNORE de
l'environnement est inerte avec ou sans -p) et ne prétend à aucune fermeture ; M3 mesure l'EFFET de chacune des six variables (R-20261111-38), pas sa
visibilité. Forme unique des enveloppes figées exclues du bac à sable :

    /bin/bash --noprofile --norc -p <enveloppe> ...

Chaque test lance la chaîne EXACTE du motif. L'enveloppe tourne vraiment : le test lit son code attendu (42) et la lettre `p` dans `$-` lue DANS
la course ; une course qui sort en code 2 sur une option, ou dont `$-` n'a pas `p`, fait échouer le test (R-20261111-29). La relance de l'enveloppe
(R-20261111-13) est sautée par un marqueur forgé par un exec qui garde le PID, pour que `-p` seul soit mis à l'épreuve.

Le script d'essai porte, en tête, la même garde de relance que les vraies enveloppes : sans marqueur égal au PID, il se relancerait sous `env -i`
et sans `-p`, ce que les tests refuseraient. Chaque test a son contrôle de sensibilité : la même chaîne SANS `-p` laisse passer l'effet (sinon le test
ne prouverait rien).

Remplace : rien. Retrait : avec le bac à sable (R-20261111-27). Propre au Mac : seul le Mac a son /bin/bash 3.2 (tests/suites_mac.txt).

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh forme_p_mac
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASH = "/bin/bash"
PREFIXE = [BASH, "--noprofile", "--norc", "-p"]
CODE_ATTENDU = 42

# Lanceur : forge le marqueur de relance (le PID du processus, conservé par execve) puis exécute la chaîne exacte. Python ne lit aucune variable de bash.
LANCEUR = ("import os, sys\n"
           "env = dict(os.environ)\n"
           "env['FIGE_RELANCE'] = str(os.getpid())\n"
           "os.execve(sys.argv[1], sys.argv[1:], env)\n")

# Le script d'essai : la garde de relance des enveloppes, puis un rapport de ce que bash a fait, écrit dans le dossier d'essai ($AUX).
# La ligne de relance (R-20261111-43 point 5) : `exec /usr/bin/env -i "FIGE_RELANCE=$$" "AUX=${AUX-}" /bin/bash --noprofile --norc "$0" "$@"` est celle des vraies
# enveloppes (tools/outils_figes/enveloppe.sh, étape 0 : environnement vidé, ni profil ni rc, marqueur = PID) à une différence près : elle garde `AUX` (le dossier
# d'essai, seule variable que le script rapporte). Aucune des deux ne passe `-p` à la relance : `-p` ne se mesure que sur le premier bash, d'où le marqueur que le
# lanceur forge pour que le script ne se relance jamais ici (sans lui, le test échouerait). Remplace : rien. Retrait : avec le bac à sable (R-20261111-27).
SCRIPT = r"""#!/bin/bash
if [[ ${FIGE_RELANCE-} != "$$" ]]; then
  exec /usr/bin/env -i "FIGE_RELANCE=$$" "AUX=${AUX-}" /bin/bash --noprofile --norc "$0" "$@"
fi
unset FIGE_RELANCE
m_path=$PATH
case $IFS in x) m_ifs=importe ;; *) m_ifs=defaut ;; esac
m_lang=${LANG-absent}
m_lc_all=${LC_ALL-absent}
m_lc_ctype=${LC_CTYPE-absent}
case ":${SHELLOPTS-}:" in *:posix:*) m_posix=oui ;; *) m_posix=non ;; esac
PATH=/usr/bin:/bin
{
  printf 'path=%s\n' "$m_path"
  printf 'ifs=%s\n' "$m_ifs"
  printf 'lang=%s\n' "$m_lang"
  printf 'lc_all=%s\n' "$m_lc_all"
  printf 'lc_ctype=%s\n' "$m_lc_ctype"
  printf 'posix=%s\n' "$m_posix"
  printf 'options=%s\n' "$-"
  printf 'version=%s\n' "${BASH_VERSINFO[0]}.${BASH_VERSINFO[1]}"
  printf 'cut=%s\n' "$(printf 'abc' | cut -c1)"
  printf 'basheopts=%s\n' "${BASHOPTS-absent}"
  if cd sous-dossier 2>/dev/null; then printf 'cdpath=suivi\n'; else printf 'cdpath=ignore\n'; fi
  cd "$AUX" || exit 3
  printf 'glob=%s\n' "$(printf '%s ' fichier-*)"
} >"$AUX/rapport.txt"
exit 42
"""


@unittest.skipUnless(sys.platform == "darwin" and os.path.exists(BASH), "suite propre au Mac : /bin/bash 3.2 de macOS")
class FormeP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dossier = Path(self.tmp.name).resolve()
        self.aux = self.dossier / "aux"
        self.aux.mkdir()
        (self.aux / "fichier-a").write_text("", encoding="utf-8")
        (self.aux / "fichier-b").write_text("", encoding="utf-8")
        self.cwd = self.dossier / "cwd"
        (self.cwd).mkdir()
        (self.dossier / "cdpath" / "sous-dossier").mkdir(parents=True)
        self.script = self.dossier / "enveloppe-essai.sh"
        self.script.write_text(SCRIPT, encoding="utf-8")
        self.script.chmod(0o755)

    # --- lancement ----------------------------------------------------------------------------------------------------------------
    def lance(self, extra=None, avec_p=True):
        """Lance la chaîne exacte du motif (ou, pour le contrôle de sensibilité, la même sans -p) ; rend (code, rapport, stderr)."""
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.dossier), "AUX": str(self.aux)}
        env.update(extra or {})
        chaine = (PREFIXE if avec_p else PREFIXE[:-1]) + [str(self.script), "arg1"]
        r = subprocess.run(["/usr/bin/python3", "-I", "-c", LANCEUR] + chaine, cwd=str(self.cwd), env=env, capture_output=True, text=True, timeout=60)
        rapport = {}
        fichier = self.aux / "rapport.txt"
        if fichier.exists():
            for ligne in fichier.read_text(encoding="utf-8").splitlines():
                cle, _, valeur = ligne.partition("=")
                rapport.setdefault(cle, []).append(valeur)
        return r.returncode, rapport, r.stderr

    def course_valide(self, code, rapport, stderr):
        """L'enveloppe a vraiment tourné : son code, et `p` dans `$-` lu dans la course (R-20261111-29)."""
        self.assertNotEqual(code, 2, f"bash a refusé ses options (code 2) : {stderr}")
        self.assertEqual(code, CODE_ATTENDU, stderr)
        self.assertIn("options", rapport, "l'enveloppe n'a pas écrit son rapport : elle n'a pas tourné")
        self.assertIn("p", rapport["options"][0], f"`p` absent de $- : {rapport['options'][0]}")

    def trace(self, nom):
        return (self.aux / nom).exists()

    # --- M1 -----------------------------------------------------------------------------------------------------------------------
    def test_m1_bash_env_env_fonction_exportee_et_shellopts_sans_effet(self):
        """M1 : BASH_ENV, ENV, une fonction exportée `cut` et SHELLOPTS=xtrace avec un PS4 piégé n'ont aucun effet sous -p. Pour ENV, ce n'est pas -p qui le ferme :
        un bash non interactif ne le lit pas (constat ci-dessous, ni avec ni sans -p)."""
        for nom in ("bash_env", "env"):
            (self.dossier / f"{nom}.sh").write_text(f"touch '{self.aux}/trace-{nom}'\n", encoding="utf-8")
        extra = {"BASH_ENV": str(self.dossier / "bash_env.sh"), "ENV": str(self.dossier / "env.sh"),
                 "BASH_FUNC_cut%%": "() {  echo DETOURNE\n}",
                 "SHELLOPTS": "xtrace", "PS4": f"$(touch '{self.aux}/trace-ps4')+ "}
        code, rapport, stderr = self.lance(extra)
        self.course_valide(code, rapport, stderr)
        for nom in ("bash_env", "env", "ps4"):
            self.assertFalse(self.trace(f"trace-{nom}"), f"{nom} a eu un effet sous -p")
        self.assertEqual(rapport["cut"], ["a"], "la fonction exportée `cut` a été importée")
        self.assertNotIn("x", rapport["options"][0], "SHELLOPTS=xtrace a été pris en compte")

    def test_m1_controle_de_sensibilite_sans_p_les_effets_existent(self):
        """Le même environnement SANS -p : BASH_ENV est lu et la fonction exportée est importée (sinon M1 ne prouverait rien)."""
        (self.dossier / "bash_env.sh").write_text(f"touch '{self.aux}/trace-bash_env'\n", encoding="utf-8")
        extra = {"BASH_ENV": str(self.dossier / "bash_env.sh"), "BASH_FUNC_cut%%": "() {  echo DETOURNE\n}"}
        code, rapport, stderr = self.lance(extra, avec_p=False)
        self.assertNotEqual(code, 2, stderr)
        self.assertTrue(self.trace("trace-bash_env"), "sans -p, BASH_ENV aurait dû être lu")
        self.assertEqual(rapport["cut"], ["DETOURNE"], "sans -p, la fonction exportée aurait dû être importée")

    def test_m1_controle_de_sensibilite_sans_p_shellopts_et_ps4_ecrivent_la_trace(self):
        """R-20261111-40 point 4 : le même SHELLOPTS=xtrace et le même PS4 piégé SANS -p : `x` est dans `$-` et le PS4 s'exécute (la trace est écrite) ; sinon
        la ligne de M1 « sans effet sous -p » ne prouverait rien."""
        extra = {"SHELLOPTS": "xtrace", "PS4": f"$(touch '{self.aux}/trace-ps4')+ "}
        code, rapport, stderr = self.lance(extra, avec_p=False)
        self.assertNotEqual(code, 2, stderr)
        self.assertIn("x", rapport["options"][0], "sans -p, SHELLOPTS=xtrace aurait dû être pris en compte")
        self.assertTrue(self.trace("trace-ps4"), "sans -p, le PS4 piégé aurait dû s'exécuter")

    def test_m1_constat_env_n_est_lu_ni_avec_ni_sans_p_par_un_bash_non_interactif(self):
        """R-20261111-40 point 4, constat : un bash non interactif ne lit pas ENV, avec ou sans -p. -p ne ferme donc pas ENV (il n'y a rien à fermer) ; ce
        constat ne prétend à aucune fermeture par -p."""
        (self.dossier / "env.sh").write_text(f"touch '{self.aux}/trace-env'\n", encoding="utf-8")
        extra = {"ENV": str(self.dossier / "env.sh")}
        code, rapport, stderr = self.lance(extra)
        self.course_valide(code, rapport, stderr)
        self.assertFalse(self.trace("trace-env"), "constat attendu : ENV non lu sous -p")
        code, rapport, stderr = self.lance(extra, avec_p=False)
        self.assertNotEqual(code, 2, stderr)
        self.assertFalse(self.trace("trace-env"), "constat attendu : ENV non lu non plus sans -p")

    # --- M2 : constat (R-20261111-38), sans affirmer de fermeture --------------------------------------------------------------------
    def test_m2_constat_cdpath_est_suivi_sous_p_sur_bash_3_2(self):
        """M2, constat sur /bin/bash 3.2.57 : sous -p, CDPATH venu de l'environnement est SUIVI par `cd`. -p ne ferme donc pas CDPATH ; il est tenu
        par la relance sous `env -i` des enveloppes et par la garde de session (D13, R-20261111-38)."""
        extra = {"CDPATH": str(self.dossier / "cdpath")}
        code, rapport, stderr = self.lance(extra)
        self.course_valide(code, rapport, stderr)
        self.assertEqual(rapport["cdpath"], ["suivi"], "constat attendu : CDPATH suivi sous -p")

    def test_m2_constat_globignore_de_l_environnement_est_inerte_avec_ou_sans_p(self):
        """M2, constat : GLOBIGNORE venu de l'environnement n'agit ni sous -p ni sans -p (bash 3.2.57). Ce n'est donc pas un effet de -p."""
        extra = {"GLOBIGNORE": "*"}
        code, rapport, stderr = self.lance(extra)
        self.course_valide(code, rapport, stderr)
        self.assertEqual(rapport["glob"], ["fichier-a fichier-b "], "constat attendu : GLOBIGNORE inerte sous -p")
        code, rapport, stderr = self.lance(extra, avec_p=False)
        self.assertNotEqual(code, 2, stderr)
        self.assertEqual(rapport["glob"], ["fichier-a fichier-b "], "constat attendu : GLOBIGNORE inerte aussi sans -p")

    def test_m2_controle_de_sensibilite_sans_p_cdpath_est_suivi(self):
        """Le contrôle de sensibilité du constat : `cd` suit bien CDPATH dans ce montage (sinon le constat ne prouverait rien)."""
        extra = {"CDPATH": str(self.dossier / "cdpath")}
        code, rapport, stderr = self.lance(extra, avec_p=False)
        self.assertNotEqual(code, 2, stderr)
        self.assertEqual(rapport["cdpath"], ["suivi"], "sans -p, CDPATH aurait dû être suivi")

    def test_m2_bashopts_n_existe_pas_dans_bash_3_2_et_n_est_pas_compte(self):
        """M2 : BASHOPTS n'existe pas dans bash 3.2 (il apparaît en 4.1) : variable ordinaire, sans sens pour bash. Elle n'est PAS comptée comme une
        preuve de -p ; la fermeture de la famille repose sur les autres variables (M1, M2) et sur la garde de session (R-20261111-29)."""
        code, rapport, stderr = self.lance({"BASHOPTS": "extglob"})
        self.course_valide(code, rapport, stderr)
        self.assertEqual(rapport["version"][0].split(".")[0], "3", "ce test décrit bash 3.2")
        self.assertEqual(rapport["basheopts"], ["extglob"], "BASHOPTS devrait rester une variable ordinaire dans bash 3.2")

    # --- M3 -----------------------------------------------------------------------------------------------------------------------
    def test_m3_effet_de_chaque_variable_sous_p_sur_bash_3_2(self):
        """M3 (R-20261111-38) : l'EFFET de chacune des six variables, pas sa visibilité (sous -p bash laisse voir BASH_ENV, ENV, CDPATH et GLOBIGNORE
        comme variables ordinaires sans les appliquer). Les six sont posées ensemble dans l'environnement de la chaîne exacte du motif ; l'effet
        mesuré est épinglé : seul CDPATH agit sous -p (il est tenu par la relance sous `env -i` et par la garde de session, D13)."""
        (self.dossier / "bash_env.sh").write_text(f"touch '{self.aux}/trace-bash_env'\n", encoding="utf-8")
        (self.dossier / "env.sh").write_text(f"touch '{self.aux}/trace-env'\n", encoding="utf-8")
        extra = {"BASH_ENV": str(self.dossier / "bash_env.sh"), "ENV": str(self.dossier / "env.sh"),
                 "BASH_FUNC_cut%%": "() {  echo DETOURNE\n}",
                 "SHELLOPTS": "xtrace", "PS4": f"$(touch '{self.aux}/trace-ps4')+ ",
                 "CDPATH": str(self.dossier / "cdpath"), "GLOBIGNORE": "*"}
        code, rapport, stderr = self.lance(extra)
        self.course_valide(code, rapport, stderr)
        effets = {
            "BASH_ENV": self.trace("trace-bash_env"),
            "ENV": self.trace("trace-env"),
            "fonction exportée": rapport["cut"] != ["a"],
            "SHELLOPTS+PS4": self.trace("trace-ps4") or "x" in rapport["options"][0],
            "CDPATH": rapport["cdpath"] == ["suivi"],
            "GLOBIGNORE": rapport["glob"] != ["fichier-a fichier-b "],
        }
        self.assertEqual(effets, EFFETS_SOUS_P, f"effets réels sous -p sur bash 3.2 : {effets}")

    def test_m3_effet_de_path_ifs_lang_lc_et_posixly_correct_sous_p_sur_bash_3_2(self):
        """M3, suite (R-20261111-40 point 5) : PATH, IFS, LANG, LC_ALL, LC_CTYPE et POSIXLY_CORRECT, posés ensemble dans l'environnement de la chaîne exacte du motif ;
        pour chacune, la valeur est-elle IMPORTÉE (visible dans la course avant que le script ne fixe son PATH) ou non sous -p ? Valeurs mesurées sur le /bin/bash 3.2.57
        du Mac et épinglées (EFFETS_SOUS_P_SUITE) ; aucune n'est présentée comme fermée par -p, seule l'importation est constatée."""
        extra = {"PATH": "/ailleurs:/usr/bin:/bin", "IFS": "x", "LANG": "en_US.UTF-8", "LC_ALL": "C", "LC_CTYPE": "C", "POSIXLY_CORRECT": "1"}
        code, rapport, stderr = self.lance(extra)
        self.course_valide(code, rapport, stderr)
        effets = {
            "PATH": rapport["path"] == ["/ailleurs:/usr/bin:/bin"],
            "IFS": rapport["ifs"] == ["importe"],
            "LANG": rapport["lang"] == ["en_US.UTF-8"],
            "LC_ALL": rapport["lc_all"] == ["C"],
            "LC_CTYPE": rapport["lc_ctype"] == ["C"],
            "POSIXLY_CORRECT": rapport["posix"] == ["oui"],
        }
        self.assertEqual(effets, EFFETS_SOUS_P_SUITE, f"importations réelles sous -p sur bash 3.2 : {effets}")

    # --- CDPATH tenu par la relance (variante de M2 sur la chaîne exacte, sans marqueur forgé) -----------------------------------------
    def test_m2_variante_cdpath_est_tenu_par_la_relance_de_l_enveloppe(self):
        """R-20261111-40 point 6 : la chaîne exacte `/bin/bash --noprofile --norc -p <enveloppe>` lancée SANS le marqueur forgé : la garde de relance de l'enveloppe
        relance sous `env -i` (sans -p) et CDPATH n'arrive pas à `cd` (ignoré). Le constat de M2 (suivi sous -p seul) est donc tenu par la relance, pas par -p."""
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.dossier), "AUX": str(self.aux), "CDPATH": str(self.dossier / "cdpath")}
        r = subprocess.run(PREFIXE + [str(self.script), "arg1"], cwd=str(self.cwd), env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, CODE_ATTENDU, r.stderr)
        rapport = dict(ligne.partition("=")[::2] for ligne in (self.aux / "rapport.txt").read_text(encoding="utf-8").splitlines())
        self.assertEqual(rapport["cdpath"], "ignore", "CDPATH ne devrait pas survivre à la relance sous env -i")
        self.assertNotIn("p", rapport["options"], "la course relancée n'est plus sous -p : c'est la relance qui tient CDPATH")


# Mesuré sur le /bin/bash 3.2.57 du Mac : l'effet de chaque variable de l'environnement sous `-p` (True : la variable agit).
EFFETS_SOUS_P = {"BASH_ENV": False, "ENV": False, "fonction exportée": False, "SHELLOPTS+PS4": False, "CDPATH": True, "GLOBIGNORE": False}

# Mesuré sur le /bin/bash 3.2.57 du Mac (R-20261111-40 point 5) : la valeur de l'environnement est-elle importée sous `-p` (True : oui) ?
EFFETS_SOUS_P_SUITE = {"PATH": True, "IFS": False, "LANG": True, "LC_ALL": True, "LC_CTYPE": True, "POSIXLY_CORRECT": True}


if __name__ == "__main__":
    unittest.main()
