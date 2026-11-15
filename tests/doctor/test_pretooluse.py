"""Contrôle pretooluse (idée 399) : la version de Claude Code comparée à celle du dernier essai du crochet PreToolUse, enregistré par
tools/essai_crochet_pretooluse.sh dans `essai-crochet-pretooluse.json`. Le `claude` est une doublure en tête du PATH ; le doctor ne
lance jamais l'essai. Deuxième partie : l'essai lui-même, par subprocess, avec un faux `claude` qui rejoue (ou non) le crochet."""
import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import Labo, VERSION_CLAUDE, TOOLS  # noqa: E402

ESSAI = TOOLS / "essai_crochet_pretooluse.sh"
ETAT = "essai-crochet-pretooluse.json"


class ControlePretooluse(Labo):
    def cle(self, env=None):
        niveau, entree, _ = self.niveau("pretooluse", env=env)
        return niveau, entree["reason"]["key"]

    def lignes(self, langue="fr", env=None):
        sortie = self.lancer("--language", langue, env=env).stdout
        return [ligne for ligne in sortie.splitlines() if ligne.startswith("pretooluse")]

    def test_meme_version_et_lu_ok(self):
        self.assertEqual(self.cle(), ("ok", "ok"))
        self.assertEqual(self.lignes(), ["pretooluse : ok : Claude Code est à la version du dernier essai conforme du crochet PreToolUse"])

    def test_version_differente_avertit_avec_la_commande(self):
        env = {"FAUX_CLAUDE_VERSION": "2.2.0"}
        niveau, entree, p = self.niveau("pretooluse", env=env)
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "version_changed"))
        self.assertEqual(p.returncode, 0)
        ligne = self.lignes(env=env)[0]
        self.assertIn("2.2.0", ligne)
        self.assertIn(VERSION_CLAUDE, ligne)
        self.assertIn("bash tools/essai_crochet_pretooluse.sh", ligne)
        self.assertIn("bash tools/essai_crochet_pretooluse.sh", self.lignes("en", env=env)[0])

    def test_aucun_essai_avertit(self):
        (self.donnees / ETAT).unlink()
        self.assertEqual(self.cle(), ("warning", "no_trial"))
        self.assertIn("bash tools/essai_crochet_pretooluse.sh", self.lignes()[0])
        self.assertIn(VERSION_CLAUDE, self.lignes()[0])

    def test_etat_illisible_avertit(self):
        for contenu in ("{pas du json", "[]", json.dumps({"claude_version": VERSION_CLAUDE, "verdict": "peut-etre"}),
                        json.dumps({"verdict": "lu"})):
            with self.subTest(contenu=contenu):
                (self.donnees / ETAT).write_text(contenu, encoding="utf-8")
                self.assertEqual(self.cle(), ("warning", "state_unreadable"))

    def test_claude_introuvable_ignore(self):
        import doctor
        from unittest import mock
        with mock.patch.object(doctor.subprocess, "run", side_effect=FileNotFoundError("claude")):
            self.assertEqual(doctor.version_claude(), (None, "missing"))
            ctx = doctor.Contexte(__import__("datetime").date(2026, 10, 14), __import__("datetime").time(9, 0), self.donnees,
                                  self.journaux, self.maison, {})
            r = doctor.controle_pretooluse(ctx, [])
        self.assertEqual((r.niveau, r.cle), ("skipped", "claude_missing"))
        import doctor_messages
        self.assertEqual(doctor_messages.CATALOGS["fr"]["raison_pretooluse_claude_missing"], "commande claude introuvable")

    def test_version_illisible_a_sa_propre_raison(self):
        for env in ({"FAUX_CLAUDE_ABSENT": "1"}, {"FAUX_CLAUDE_VERSION": "abc"}):
            with self.subTest(env=env):
                self.assertEqual(self.cle(env=env), ("skipped", "claude_version_unreadable"))
        env = {"FAUX_CLAUDE_ABSENT": "1"}
        self.assertEqual(self.lignes(env=env), ["pretooluse : ignoré : version de claude illisible"])
        self.assertEqual(self.lignes("en", env=env), ["pretooluse: skipped: claude version unreadable"])

    def test_prefixe_v_tolere_dans_la_version(self):
        self.assertEqual(self.cle(env={"FAUX_CLAUDE_VERSION": "v" + VERSION_CLAUDE}), ("ok", "ok"))

    def test_verdict_non_lu_est_un_probleme_avec_le_retour_a_la_forme_a(self):
        self.ecrire_essai_crochet(VERSION_CLAUDE, "non lu")
        niveau, entree, p = self.niveau("pretooluse")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "not_read"))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("forme A", self.lignes()[0])
        self.assertIn("form A", self.lignes("en")[0])

    def test_ne_lance_jamais_l_essai_ni_n_ecrit(self):
        avant = self.fichiers()
        self.lancer(env={"FAUX_CLAUDE_VERSION": "2.2.0"})
        self.assertEqual(self.fichiers(), avant)
        self.assertEqual([a for a in self.appels() if a.startswith("claude") and a != "claude --version"], [])


FAUX_CLAUDE = r"""#!/bin/bash
# Faux claude de l'essai : FAUX_CLAUDE_MODE = tous | pre-ignore | post-ignore | sans-crochet
echo "claude $*" >> "$STUB_LOG"
if [ "$1" = "--version" ]; then echo "${FAUX_CLAUDE_VERSION:-2.1.303} (Claude Code)"; exit 0; fi
commande="$(sed -nE 's/.*"command": "([^"]+)".*/\1/p' .claude/settings.json)"
evenement=PostToolUse; grep -q PreToolUse .claude/settings.json && evenement=PreToolUse
mode="${FAUX_CLAUDE_MODE:-tous}"
[ "$mode" = sans-crochet ] && { echo AUCUN; exit 0; }
sortie="$("$commande" < /dev/null)"
canari="$(printf '%s' "$sortie" | sed -E 's/.*"additionalContext":"([^"]*)".*/\1/')"
case "$mode:$evenement" in
  tous:*|pre-ignore:PostToolUse) echo "$canari" ;;
  *) echo AUCUN ;;
esac
"""


class EssaiDuCrochet(Labo):
    def setUp(self):
        super().setUp()
        (self.donnees / ETAT).unlink()
        faux = self.bin / "claude"
        faux.write_text(FAUX_CLAUDE, encoding="utf-8")
        faux.chmod(0o755)

    def essai(self, mode="tous", **extra):
        env = self.environnement(FAUX_CLAUDE_MODE=mode, PMZILLA_LAB_TODAY="2026-10-22", **extra)
        env.pop("CLAUDECODE", None)
        env.update({k: str(v) for k, v in extra.items()})
        return subprocess.run(["bash", str(ESSAI)], capture_output=True, text=True, timeout=60, env=env, cwd=str(self.base))

    def etat(self):
        return json.loads((self.donnees / ETAT).read_text(encoding="utf-8"))

    def test_temoin_et_essai_lus_ecrivent_l_etat_lu(self):
        p = self.essai("tous")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.etat(), {"version": 1, "claude_version": VERSION_CLAUDE, "date": "2026-10-22", "verdict": "lu"})
        self.assertEqual(stat.S_IMODE((self.donnees / ETAT).stat().st_mode), 0o600)
        self.assertEqual([f.name for f in self.donnees.iterdir() if f.name.startswith(".essai")], [])
        self.assertEqual(self.niveau("pretooluse")[0], "ok")

    def test_la_version_enregistree_est_celle_de_claude(self):
        p = self.essai("tous", FAUX_CLAUDE_VERSION="2.4.1")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.etat()["claude_version"], "2.4.1")

    def test_version_lue_comme_le_doctor_prefixe_v_et_numero_pas_en_debut(self):
        p = self.essai("tous", FAUX_CLAUDE_VERSION="v2.4.1")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.etat()["claude_version"], "2.4.1")

    def test_version_illisible_arrete_l_essai_sans_ecrire(self):
        p = self.essai("tous", FAUX_CLAUDE_VERSION="abc")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertFalse((self.donnees / ETAT).exists())

    def test_essai_non_lu_ecrit_l_etat_non_lu(self):
        p = self.essai("pre-ignore")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.etat()["verdict"], "non lu")
        self.assertEqual(self.niveau("pretooluse")[1]["reason"]["key"], "not_read")

    def test_temoin_non_lu_n_ecrit_rien(self):
        p = self.essai("post-ignore")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse((self.donnees / ETAT).exists())

    def test_essai_invalide_n_ecrit_rien(self):
        p = self.essai("sans-crochet")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("invalide", p.stdout)
        self.assertFalse((self.donnees / ETAT).exists())

    def test_refuse_dans_une_session_claude_code(self):
        env = self.environnement(FAUX_CLAUDE_MODE="tous", CLAUDECODE="1")
        p = subprocess.run(["bash", str(ESSAI)], capture_output=True, text=True, timeout=60, env=env, cwd=str(self.base))
        self.assertEqual(p.returncode, 3)
        self.assertFalse((self.donnees / ETAT).exists())
        self.assertEqual([a for a in self.appels() if a.startswith("claude")], [])

    def test_dossier_jetable_avec_un_mktemp_gnu(self):
        """Un faux mktemp GNU en tête du PATH refuse « -t » sans motif en X (comme GNU : « too few X's in template ») ; l'essai doit
        donc donner un modèle explicite avec XXXXXX, valable aussi sous BSD."""
        faux = self.base / "bin-gnu"
        faux.mkdir()
        script = faux / "mktemp"
        script.write_text(
            '#!/bin/sh\n'
            'for a in "$@"; do\n'
            '  if [ "$a" = "-t" ]; then echo "mktemp: too few X\'s in template" >&2; exit 1; fi\n'
            'done\n'
            'for a in "$@"; do case "$a" in -*) ;; *XXXXXX) exec /usr/bin/mktemp "$@" ;; esac; done\n'
            'echo "mktemp: too few X\'s in template" >&2; exit 1\n', encoding="utf-8")
        script.chmod(0o755)
        env = self.environnement(FAUX_CLAUDE_MODE="tous", PMZILLA_LAB_TODAY="2026-10-22")
        env.pop("CLAUDECODE", None)
        env["PATH"] = f"{faux}{os.pathsep}{env['PATH']}"
        p = subprocess.run(["bash", str(ESSAI)], capture_output=True, text=True, timeout=60, env=env, cwd=str(self.base))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("too few X", p.stderr)

    def test_le_script_n_a_pas_de_bit_executable_et_se_lance_par_bash(self):
        self.assertFalse(os.access(ESSAI, os.X_OK))


if __name__ == "__main__":
    unittest.main()
