"""Suite de tools/settings_assemble.py (R-137) : l'assemblage des fragments du dépôt rend, octet pour octet, .claude/settings.json.

    bash tests/run_all.sh settings_assemble

Le dépôt réel est lu en lecture seule ; les refus et le mode --write s'essaient sur des racines temporaires.
"""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import settings_assemble as sa  # noqa: E402

BASE = {
    "permissions": {"deny": [], "allow": ["Bash(ls*)"]},
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo \"x\""}]}]},
}


def lancer(*arguments) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = sa.principal(list(arguments))
    return code, sortie.getvalue()


class RacineTemporaire(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self._dossier.cleanup)
        self.racine = Path(self._dossier.name)
        (self.racine / ".claude" / "deny").mkdir(parents=True)
        self.base(BASE)

    def base(self, contenu):
        (self.racine / ".claude" / "settings.base.json").write_text(json.dumps(contenu, indent=2) + "\n", encoding="utf-8")

    def ordre(self, *noms):
        (self.racine / ".claude" / "deny" / "ORDRE").write_text("".join(f"{n}\n" for n in noms), encoding="utf-8")

    def fragment(self, nom, *regles, brut=None):
        texte = brut if brut is not None else "".join(f"{r}\n" for r in regles)
        (self.racine / ".claude" / "deny" / nom).write_text(texte, encoding="utf-8")

    def deux_fragments(self):
        self.fragment("01-a.txt", "Read(./a/**)", "Bash(cat *a*)")
        self.fragment("02-b.txt", "Bash(rm *b*)", "Edit(./b)")
        self.ordre("01-a.txt", "02-b.txt")

    def instantane(self) -> dict:
        return {str(p.relative_to(self.racine)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in sorted(self.racine.rglob("*")) if p.is_file()}

    def refus(self, attendu: str):
        code, sortie = lancer("--check", "--root", str(self.racine))
        self.assertEqual(code, 2, sortie)
        self.assertIn(attendu, sortie)
        self.assertFalse((self.racine / ".claude" / "settings.json").exists())
        return sortie


class DepotReel(unittest.TestCase):
    def test_assemblage_identique_au_fichier_actuel_octet_pour_octet(self):
        texte, regles, _ = sa.assembler(RACINE)
        actuel = (RACINE / ".claude" / "settings.json").read_bytes()
        self.assertEqual(texte.encode("utf-8"), actuel)
        self.assertGreater(len(regles), 2000)

    def test_check_du_depot_rend_zero(self):
        code, sortie = lancer("--check", "--root", str(RACINE))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(lancer("--root", str(RACINE))[0], 0)  # --check est le défaut

    def test_lancement_en_ligne_de_commande(self):
        resultat = subprocess.run([sys.executable, str(RACINE / "tools" / "settings_assemble.py"), "--check"],
                                  capture_output=True, text=True, cwd=RACINE)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_chaque_fragment_est_liste_non_vide_sans_doublon(self):
        noms = sa.lire_ordre(RACINE)
        self.assertEqual(len(noms), len(set(noms)))
        for nom in noms:
            self.assertTrue(sa.lire_fragment(RACINE, nom), nom)
        sur_disque = {p.name for p in (RACINE / ".claude" / "deny").iterdir()
                      if p.is_file() and not p.name.startswith(".") and p.name != "ORDRE"}
        self.assertEqual(sur_disque, set(noms))

    def test_les_fragments_gardent_l_ordre_des_reglages(self):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        a_la_suite = [r for nom in sa.lire_ordre(RACINE) for r in sa.lire_fragment(RACINE, nom)]
        self.assertEqual(a_la_suite, reglages["permissions"]["deny"])


class Assemblage(RacineTemporaire):
    def test_ordre_stable_et_json_standard(self):
        self.deux_fragments()
        premier, regles, origines = sa.assembler(self.racine)
        second, _, _ = sa.assembler(self.racine)
        self.assertEqual(premier, second)
        self.assertEqual(regles, ["Read(./a/**)", "Bash(cat *a*)", "Bash(rm *b*)", "Edit(./b)"])
        self.assertEqual(origines[2], ("02-b.txt", 1))
        self.assertTrue(premier.endswith("}\n"))
        self.assertIn('\n  "permissions": {\n    "deny": [\n      "Read(./a/**)"', premier)
        self.assertEqual(json.loads(premier)["permissions"]["allow"], ["Bash(ls*)"])

    def test_l_ordre_du_fichier_ordre_commande_l_assemblage(self):
        self.deux_fragments()
        self.ordre("02-b.txt", "01-a.txt")
        _, regles, _ = sa.assembler(self.racine)
        self.assertEqual(regles[:2], ["Bash(rm *b*)", "Edit(./b)"])

    def test_les_guillemets_sont_echappes_comme_dans_le_json_du_depot(self):
        self.fragment("01-a.txt", 'Bash(cp *.git"*)', "Bash(cp *.git'*)")
        self.ordre("01-a.txt")
        texte, _, _ = sa.assembler(self.racine)
        self.assertIn('"Bash(cp *.git\\"*)"', texte)

    def test_write_ecrit_puis_check_rend_zero(self):
        self.deux_fragments()
        code, _ = lancer("--write", "--root", str(self.racine))
        self.assertEqual(code, 0)
        self.assertEqual(lancer("--check", "--root", str(self.racine))[0], 0)
        self.assertEqual((self.racine / ".claude" / "settings.json").read_text(encoding="utf-8"),
                         sa.assembler(self.racine)[0])


class ModeWrite(RacineTemporaire):
    def reglages(self) -> Path:
        return self.racine / ".claude" / "settings.json"

    def temporaires(self) -> list[str]:
        return sorted(p.name for p in (self.racine / ".claude").iterdir() if p.name not in ("settings.json", "settings.base.json", "deny"))

    def test_ecriture_atomique_echec_du_temporaire_laisse_le_fichier_intact(self):
        self.deux_fragments()
        self.reglages().write_text(json.dumps({"permissions": {"deny": ["Read(./x)"]}}) + "\n", encoding="utf-8")
        avant = self.reglages().read_bytes()
        with mock.patch.object(sa.os, "fsync", side_effect=OSError("disque plein")):
            code, sortie = lancer("--write", "--root", str(self.racine), "--allow-fewer")
        self.assertEqual(code, 2, sortie)
        self.assertEqual(self.reglages().read_bytes(), avant)
        self.assertEqual(self.temporaires(), [])

    def test_ecriture_atomique_echec_du_remplacement(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        avant = self.reglages().read_bytes()
        self.fragment("02-b.txt", "Bash(rm *b*)", "Edit(./b)", "Edit(./c)")
        with mock.patch.object(sa.os, "replace", side_effect=OSError("refus")):
            code, _ = lancer("--write", "--root", str(self.racine))
        self.assertEqual(code, 2)
        self.assertEqual(self.reglages().read_bytes(), avant)
        self.assertEqual(self.temporaires(), [])

    def test_ecriture_garde_le_mode_du_fichier_existant(self):
        self.deux_fragments()
        self.reglages().write_text("{}\n", encoding="utf-8")
        os.chmod(self.reglages(), 0o640)
        code, _ = lancer("--write", "--root", str(self.racine), "--allow-fewer")
        self.assertEqual(code, 0)
        self.assertEqual(stat.S_IMODE(self.reglages().stat().st_mode), 0o640)
        self.assertEqual(self.temporaires(), [])

    def test_ecriture_sans_fichier_existant(self):
        self.deux_fragments()
        self.assertEqual(lancer("--write", "--root", str(self.racine))[0], 0)
        self.assertEqual(self.temporaires(), [])

    def test_baisse_du_nombre_de_regles_refusee_sans_option(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        self.fragment("02-b.txt", "Bash(rm *b*)")
        avant = self.reglages().read_bytes()
        code, sortie = lancer("--write", "--root", str(self.racine))
        self.assertEqual(code, 2, sortie)
        self.assertIn("--allow-fewer", sortie)
        self.assertEqual(self.reglages().read_bytes(), avant)
        self.assertNotIn("Edit(./b)", sortie)

    def test_baisse_acceptee_avec_l_option(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        self.fragment("02-b.txt", "Bash(rm *b*)")
        code, _ = lancer("--write", "--allow-fewer", "--root", str(self.racine))
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(self.reglages().read_text(encoding="utf-8"))["permissions"]["deny"]), 3)

    def test_nombre_de_regles_apres_write_egal_a_l_assemblage(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        self.fragment("02-b.txt", "Bash(rm *b*)", "Edit(./b)", "Edit(./c)")
        code, _ = lancer("--write", "--root", str(self.racine))
        self.assertEqual(code, 0)
        ecrites = json.loads(self.reglages().read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertEqual(len(ecrites), len(sa.assembler(self.racine)[1]))

    def test_write_affiche_le_diff_court_avant_d_ecrire_sans_texte_de_regle(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        self.fragment("02-b.txt", "Bash(rm *b*)", "Edit(./b)", "Edit(./secret-ajoutee)")
        code, sortie = lancer("--write", "--root", str(self.racine))
        self.assertEqual(code, 0)
        self.assertIn("rangs", sortie)
        self.assertIn("02-b.txt", sortie)
        self.assertNotIn("secret-ajoutee", sortie)
        self.assertLess(sortie.index("rangs"), sortie.index("écrit ("))


class ModeCheck(RacineTemporaire):
    def test_check_n_ecrit_rien_identique_ou_different(self):
        self.deux_fragments()
        avant = self.instantane()
        code, _ = lancer("--check", "--root", str(self.racine))
        self.assertEqual(code, 1)  # settings.json absent
        self.assertEqual(self.instantane(), avant)
        lancer("--write", "--root", str(self.racine))
        avant = self.instantane()
        self.assertEqual(lancer("--check", "--root", str(self.racine))[0], 0)
        self.assertEqual(self.instantane(), avant)
        self.fragment("02-b.txt", "Bash(rm *b*)", "Edit(./c)", "Edit(./d)")
        avant = self.instantane()
        self.assertEqual(lancer("--check", "--root", str(self.racine))[0], 1)
        self.assertEqual(self.instantane(), avant)

    def test_check_refuse_sans_rien_ecrire(self):
        self.deux_fragments()
        self.fragment("02-b.txt", "Write(./b)")
        avant = self.instantane()
        self.assertEqual(lancer("--check", "--root", str(self.racine))[0], 2)
        self.assertEqual(self.instantane(), avant)

    def test_diff_court_en_positions_sans_texte_de_regle(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        self.fragment("02-b.txt", "Bash(rm *secret-nouveau*)", "Edit(./b)", "Edit(./ajoutee)")
        code, sortie = lancer("--check", "--root", str(self.racine))
        self.assertEqual(code, 1)
        self.assertIn("diffère de l'assemblage", sortie)
        self.assertIn("rangs", sortie)
        self.assertIn("02-b.txt", sortie)
        for regle in ("secret-nouveau", "ajoutee", "Read(./a/**)", "Bash(cat"):
            self.assertNotIn(regle, sortie)

    def test_diff_reste_du_fichier(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        self.base({**BASE, "permissions": {"deny": [], "allow": ["Bash(ls*)", "Bash(pwd)"]}})
        code, sortie = lancer("--check", "--root", str(self.racine))
        self.assertEqual(code, 1)
        self.assertIn("reste du fichier", sortie)

    def test_diff_court_est_borne(self):
        self.deux_fragments()
        lancer("--write", "--root", str(self.racine))
        reglages = json.loads((self.racine / ".claude" / "settings.json").read_text(encoding="utf-8"))
        reglages["permissions"]["deny"] = [f"Bash(x{i})" for i in range(60)]
        (self.racine / ".claude" / "settings.json").write_text(json.dumps(reglages, indent=2) + "\n", encoding="utf-8")
        _, sortie = lancer("--check", "--root", str(self.racine))
        self.assertLessEqual(len(sortie.splitlines()), sa.MAX_LIGNES_DIFF + 4)


class Refus(RacineTemporaire):
    def test_fragment_en_double_dans_ordre(self):
        self.deux_fragments()
        self.ordre("01-a.txt", "02-b.txt", "01-a.txt")
        self.refus("fragment en double dans ORDRE")

    def test_regle_en_double_dans_un_fragment(self):
        self.fragment("01-a.txt", "Read(./a)", "Bash(ls *)", "Read(./a)")
        self.ordre("01-a.txt")
        sortie = self.refus("règle en double : 01-a.txt ligne 3, déjà dans 01-a.txt ligne 1")
        self.assertNotIn("Read(./a)", sortie)

    def test_regle_en_double_entre_deux_fragments(self):
        self.fragment("01-a.txt", "Read(./a)")
        self.fragment("02-b.txt", "Bash(ls *)", "Read(./a)")
        self.ordre("01-a.txt", "02-b.txt")
        self.refus("règle en double : 02-b.txt ligne 2, déjà dans 01-a.txt ligne 1")

    def test_regle_write_et_notebook_edit(self):
        for regle in ("Write(./x)", "NotebookEdit(./x)"):
            with self.subTest(regle=regle):
                self.fragment("01-a.txt", "Read(./a)", regle)
                self.ordre("01-a.txt")
                self.refus("01-a.txt, ligne 2 : règle Write ou NotebookEdit")

    def test_fragment_vide(self):
        self.fragment("01-a.txt", brut="")
        self.ordre("01-a.txt")
        self.refus("fragment vide : 01-a.txt")

    def test_fragment_qui_ne_contient_qu_un_saut_de_ligne(self):
        self.fragment("01-a.txt", brut="\n")
        self.ordre("01-a.txt")
        self.refus("01-a.txt, ligne 1 : ligne vide")

    def test_ligne_vide_au_milieu(self):
        self.fragment("01-a.txt", brut="Read(./a)\n\nRead(./b)\n")
        self.ordre("01-a.txt")
        self.refus("01-a.txt, ligne 2 : ligne vide")

    def test_regle_mal_formee(self):
        self.fragment("01-a.txt", "pas une regle")
        self.ordre("01-a.txt")
        self.refus("règle mal formée")

    def test_fragment_inconnu_de_la_liste_ordonnee(self):
        self.deux_fragments()
        self.fragment("03-orphelin.txt", "Read(./z)")
        self.refus("fragment inconnu de la liste ordonnée : 03-orphelin.txt")

    def test_fragment_liste_et_absent(self):
        self.deux_fragments()
        self.ordre("01-a.txt", "02-b.txt", "03-absent.txt")
        self.refus("fragment listé et absent : 03-absent.txt")

    def test_liste_ordonnee_vide_ou_absente(self):
        self.deux_fragments()
        self.ordre()
        self.refus("liste ordonnée vide")
        (self.racine / ".claude" / "deny" / "ORDRE").unlink()
        self.refus("liste ordonnée illisible")

    def test_deny_non_vide_dans_la_base(self):
        self.deux_fragments()
        self.base({"permissions": {"deny": ["Read(./x)"]}})
        self.refus("permissions.deny doit exister et être vide")

    def test_base_invalide(self):
        self.deux_fragments()
        (self.racine / ".claude" / "settings.base.json").write_text("{pas du json", encoding="utf-8")
        self.refus("base illisible ou JSON invalide")

    def test_write_refuse_n_ecrit_pas(self):
        self.fragment("01-a.txt", "Read(./a)", "Read(./a)")
        self.ordre("01-a.txt")
        (self.racine / ".claude" / "settings.json").write_text("ancien\n", encoding="utf-8")
        code, _ = lancer("--write", "--root", str(self.racine))
        self.assertEqual(code, 2)
        self.assertEqual((self.racine / ".claude" / "settings.json").read_text(encoding="utf-8"), "ancien\n")

    def test_fragment_non_utf8(self):
        (self.racine / ".claude" / "deny" / "01-a.txt").write_bytes(b"Read(./caf\xe9)\n")
        self.ordre("01-a.txt")
        self.refus("fragment illisible : 01-a.txt")

    def test_ordre_non_utf8(self):
        self.fragment("01-a.txt", "Read(./a)")
        (self.racine / ".claude" / "deny" / "ORDRE").write_bytes(b"01-a.txt\n\xff\xfe\n")
        self.refus("liste ordonnée illisible")

    def test_ordre_nom_invalide_sans_recopier_la_ligne(self):
        self.fragment("01-a.txt", "Read(./a)")
        for nom in ("../x.txt", "01-A.txt", "a.txt", "01-a.json", "01-a/b.txt", "01-a.txt.bak"):
            with self.subTest(nom=nom):
                self.ordre("01-a.txt", nom)
                sortie = self.refus("ORDRE, ligne 2")
                self.assertNotIn(nom, sortie)

    def test_ordre_avec_espaces(self):
        self.fragment("01-a.txt", "Read(./a)")
        for contenu in (" 01-a.txt\n", "01-a.txt \n", "01-a.txt\n\n02-b.txt\n"):
            with self.subTest(contenu=contenu):
                (self.racine / ".claude" / "deny" / "ORDRE").write_text(contenu, encoding="utf-8")
                self.refus("ORDRE, ligne")

    def test_regle_avec_espaces_autour(self):
        for brut in (" Read(./a)\n", "Read(./a) \n", "\tRead(./a)\n"):
            with self.subTest(brut=brut):
                self.fragment("01-a.txt", brut=brut)
                self.ordre("01-a.txt")
                sortie = self.refus("01-a.txt, ligne 1 : ligne vide ou avec espaces")
                self.assertNotIn("Read(./a)", sortie)

    def test_fins_de_ligne_crlf_refusees(self):
        self.fragment("01-a.txt", brut="Read(./a)\r\nRead(./b)\r\n")
        self.ordre("01-a.txt")
        self.refus("01-a.txt, ligne 1")
        self.fragment("01-a.txt", "Read(./a)")
        (self.racine / ".claude" / "deny" / "ORDRE").write_bytes(b"01-a.txt\r\n")
        self.refus("ORDRE, ligne 1")

    def test_formes_admises(self):
        regles = ["WebFetch", "mcp__serveur__outil", "mcp__serveur__outil(*)", "Bash(rm *)", "Read(./a/**)"]
        self.fragment("01-a.txt", *regles)
        self.ordre("01-a.txt")
        self.assertEqual(sa.assembler(self.racine)[1], regles)

    def test_formes_refusees(self):
        for regle in ("Write", "NotebookEdit", "Write(./x)", "mcp__serveur", "Bash()", "Bash(", "(x)", "pas une regle",
                      "Web Fetch", "mcp__a__b c", "Bash(x) y"):
            with self.subTest(regle=regle):
                self.fragment("01-a.txt", regle)
                self.ordre("01-a.txt")
                self.refus("01-a.txt, ligne 1")

    def test_fichiers_caches_ignores_dans_le_dossier(self):
        self.deux_fragments()
        (self.racine / ".claude" / "deny" / ".DS_Store").write_bytes(b"\x00\x01binaire")
        (self.racine / ".claude" / "deny" / ".cache").write_text("x", encoding="utf-8")
        (self.racine / ".claude" / "deny" / "sous-dossier").mkdir()
        self.assertEqual(len(sa.assembler(self.racine)[1]), 4)

    def test_usage_check_et_write_ensemble(self):
        sortie = io.StringIO()
        with contextlib.redirect_stderr(sortie):
            self.assertEqual(lancer("--check", "--write")[0], 2)


if __name__ == "__main__":
    unittest.main()
