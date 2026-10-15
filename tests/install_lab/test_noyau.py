"""
Tests du noyau du script d'installation (tools/install_lab.py) : ligne de commande, modes, exécuteur d'étapes, passage à blanc, rapport,
codes de sortie, gardes d'isolation. Écrits avant le code (change install-script, tâches 2.2 et 2.3).

    uv run python -W ignore -m unittest discover -s tests/install_lab -q -f
"""
import io
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aide_install import AMORCE, ORCHESTRATEUR, TOOLS_REELS, CasDeBase

sys.path.insert(0, str(TOOLS_REELS))
import install_lab as noyau            # noqa: E402
import install_lab_context as c        # noqa: E402

ETAPES = ["prereqs", "repo", "hooks", "runtree", "links", "database", "launchd", "mcp", "check"]
PHRASE_MODE = 'is not available in this version, see the "Install script" section of docs/pmzilla/installation.md'


class LigneDeCommande(CasDeBase):
    def test_liste_des_etapes_dans_l_ordre(self):
        p = self.fx.lancer("--mode", "fresh", "--list")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual([l.split()[0] for l in p.lignes() if l.strip()], ETAPES)
        self.assertEqual(p.appels, [])

    def test_liste_sans_mode(self):
        self.assertEqual(self.fx.lancer("--list").code, 0)

    def test_autre_mode_refuse(self):
        for mode in ("migrate", "bidon"):
            p = self.fx.lancer("--mode", mode)
            self.assertEqual(p.code, 2, p.texte)
            self.assertIn(f"mode {mode} {PHRASE_MODE}", p.texte)
            self.assertEqual(p.appels, [], "aucune étape ne doit tourner")

    def test_mode_manquant(self):
        p = self.fx.lancer("--dry-run")
        self.assertEqual(p.code, 2)
        self.assertEqual(p.appels, [])

    def test_options_de_migration_refusees(self):
        for args in (["--bundle", "x"], ["--dumps", "x"], ["pack"], ["--mode", "fresh", "--bundle", "x"], ["--mode", "fresh", "pack"],
                     ["--mode", "fresh", "--dumps"]):
            p = self.fx.lancer(*args)
            self.assertEqual(p.code, 2, (args, p.texte))
            self.assertEqual(p.appels, [], args)

    def test_pas_de_oui_global(self):
        for args in (["--mode", "fresh", "--yes"], ["--mode", "fresh", "-y"], ["--mode", "fresh", "--dry-run", "--yes"]):
            p = self.fx.lancer(*args)
            self.assertEqual(p.code, 2, args)
            self.assertEqual(p.appels, [])

    def test_etape_inconnue_ou_hors_mode(self):
        for etape in ("bidon", "restore-db", "restore-files", "pack"):
            p = self.fx.lancer("--mode", "fresh", "--step", etape)
            self.assertEqual(p.code, 2, etape)
            self.assertEqual(p.appels, [])
        self.assertEqual(self.fx.lancer("--mode", "fresh", "--start-at", "bidon").code, 2)

    def test_une_etape_et_une_etape_de_depart_ensemble(self):
        p = self.fx.lancer("--mode", "fresh", "--step", "mcp", "--start-at", "links")
        self.assertEqual(p.code, 2)
        self.assertEqual(p.appels, [])

    def test_vrai_passage_sans_terminal_refuse_avant_toute_action(self):
        p = self.fx.lancer("--mode", "fresh", sans_terminal_ok=False)
        self.assertEqual(p.code, 2, p.texte)
        self.assertEqual(p.appels, [])

    def test_passage_a_blanc_sans_terminal_accepte(self):
        p = self.fx.lancer("--mode", "fresh", "--dry-run", sans_terminal_ok=False)
        self.assertNotEqual(p.code, 2, p.texte)

    def test_aide_sans_effet_et_sans_mode(self):
        p = self.fx.lancer("--help")
        self.assertEqual(p.code, 0)
        self.assertIn("--dry-run", p.texte)
        self.assertEqual(p.appels, [])

    def test_messages_prefixes_et_en_anglais(self):
        p = self.fx.lancer("--mode", "fresh", "--dry-run")
        for l in p.sortie.splitlines():
            if l.strip() and not l.startswith(("    ", "\t")):
                self.assertTrue(l.startswith("install_lab: ") or l.startswith(" "), l)


class PasseALaBlancEtRapport(CasDeBase):
    def test_passage_a_blanc_ne_change_rien(self):
        avant = self.fx.empreinte()
        p = self.fx.lancer("--mode", "fresh", "--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.fx.empreinte(), avant, "le décor ne doit pas changer")
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [], "appels qui changent l'état en passage à blanc")
        self.assertIn("dry run: nothing was changed", p.texte)

    def test_fin_de_passage_a_blanc(self):
        lignes = [l for l in self.fx.lancer("--mode", "fresh", "--dry-run").lignes() if l.strip()]
        self.assertEqual(lignes[-1], "dry run: nothing was changed")

    def test_la_liste_manuelle_est_toujours_la_et_plus_la_note_des_versions(self):
        """Depuis R-36 les scripts ont leur fichier .lock : le rappel « versions du jour » serait faux."""
        t = self.fx.lancer("--mode", "fresh", "--dry-run").texte
        self.assertIn("remaining manual steps:", t)
        self.assertNotIn("resolved on the day", t)

    def test_les_commandes_de_role_viennent_de_db_py_et_ne_sont_pas_lancees(self):
        p = self.fx.lancer("--mode", "fresh", "--dry-run")
        for role in ("roles_test_a", "roles_test_b"):
            self.assertIn(f"db.py role-password {role}", p.texte)
        self.assertEqual([a for a in p.appels if "role-password" in a], [])


class Executeur(unittest.TestCase):
    """Exécuteur d'étapes, testé en processus avec des étapes factices (aucun appel de commande)."""
    def ctx(self, **kw):
        return c.Contexte(racine=Path("."), maison=Path("."), **kw)

    @staticmethod
    def etape(nom, fait=False, etat=c.FAIT, depend=()):
        trace = []
        e = c.Etape(nom, ("fresh",), tuple(depend), lambda ctx: fait, lambda ctx: (trace.append(nom), c.Resultat(etat))[1])
        e.trace = trace
        return e

    def lancer(self, etapes, **kw):
        with redirect_stdout(io.StringIO()) as sortie:
            res = noyau.lancer_etapes(self.ctx(**kw.pop("ctx", {})), etapes, **kw)
        return res, sortie.getvalue()

    def test_deja_fait_saute_sans_executer(self):
        a = self.etape("a", fait=True)
        res, sortie = self.lancer([a])
        self.assertEqual(res["a"].etat, c.DEJA)
        self.assertEqual(a.trace, [])
        self.assertIn("install_lab: step a: already done, skipped", sortie)

    def test_dependance_non_faite_reporte_et_nomme(self):
        a, b = self.etape("a", etat=c.REFUSE), self.etape("b", depend=["a"])
        res, sortie = self.lancer([a, b])
        self.assertEqual(res["b"].etat, c.REPORTE)
        self.assertEqual(b.trace, [])
        self.assertIn("step b: deferred", sortie)
        self.assertIn("a", res["b"].detail)

    def test_une_etape_seule_interroge_la_sonde_de_sa_dependance(self):
        fait, pas_fait = self.etape("a", fait=True), self.etape("a2", fait=False)
        b, b2 = self.etape("b", depend=["a"]), self.etape("b2", depend=["a2"])
        res, _ = self.lancer([fait, b], seule="b")
        self.assertEqual(res["b"].etat, c.FAIT)
        self.assertNotIn("a", res)
        res, _ = self.lancer([pas_fait, b2], seule="b2")
        self.assertEqual(res["b2"].etat, c.REPORTE)
        self.assertIn("a2", res["b2"].detail)

    def test_a_partir_de(self):
        a, b, d = self.etape("a"), self.etape("b"), self.etape("d")
        res, _ = self.lancer([a, b, d], depuis="b")
        self.assertEqual(list(res), ["b", "d"])
        self.assertEqual(a.trace, [])

    def test_echec_arrete_la_suite(self):
        a, b = self.etape("a", etat=c.ECHEC), self.etape("b")
        res, _ = self.lancer([a, b])
        self.assertEqual(res["a"].etat, c.ECHEC)
        self.assertEqual(b.trace, [])
        self.assertEqual(res["b"].etat, c.NON_LANCE)

    def test_passage_a_blanc_compte_comme_satisfait_pour_les_dependances(self):
        a, b = self.etape("a", etat=c.A_BLANC), self.etape("b", etat=c.A_BLANC, depend=["a"])
        res, _ = self.lancer([a, b], ctx={"a_blanc": True})
        self.assertEqual(res["b"].etat, c.A_BLANC)

    def test_une_etape_de_fin_est_reportee_si_une_etape_du_passage_n_est_pas_en_ordre(self):
        a, fin = self.etape("a", etat=c.REFUSE), self.etape("fin")
        fin.apres_tout = True
        res, sortie = self.lancer([a, fin])
        self.assertEqual(res["fin"].etat, c.REPORTE)
        self.assertEqual(fin.trace, [])
        self.assertIn("a", res["fin"].detail)
        b, fin2 = self.etape("b", etat=c.FAIT), self.etape("fin2")
        fin2.apres_tout = True
        res, _ = self.lancer([b, fin2])
        self.assertEqual(res["fin2"].etat, c.FAIT)

    def test_etape_de_fin_lancee_seule_n_est_pas_reportee(self):
        fin = self.etape("fin")
        fin.apres_tout = True
        res, _ = self.lancer([self.etape("a", etat=c.REFUSE), fin], seule="fin")
        self.assertEqual(res["fin"].etat, c.FAIT)

    def test_codes_de_sortie(self):
        R = c.Resultat
        self.assertEqual(noyau.code_de_sortie({"a": R(c.FAIT), "b": R(c.DEJA)}), 0)
        self.assertEqual(noyau.code_de_sortie({"a": R(c.FAIT), "b": R(c.REFUSE)}), 4)
        self.assertEqual(noyau.code_de_sortie({"a": R(c.REPORTE, "x")}), 4)
        self.assertEqual(noyau.code_de_sortie({"a": R(c.MANUEL)}), 4)
        self.assertEqual(noyau.code_de_sortie({"a": R(c.ECHEC, "cmd"), "b": R(c.REFUSE)}), 1)
        self.assertEqual(noyau.code_de_sortie({"a": R(c.A_BLANC)}), 0)


class Gardes(unittest.TestCase):
    """Garde du texte des scripts (spec « Tests have no real effect », « No secret is handled »)."""
    FICHIERS = sorted(TOOLS_REELS.glob("install_lab*.py")) + [AMORCE]
    CHEMIN_ABSOLU = re.compile(r"(?<![\w.~$}\)])/(usr|opt|bin|sbin|Users|Library|System|etc|var|private|Applications|home)(/|\b)")

    @staticmethod
    def chaines_de_code(fichier: Path):
        """Chaînes littérales d'un script Python, hors docstrings et commentaires."""
        import ast
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        docstrings = set()
        for n in ast.walk(arbre):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and ast.get_docstring(n, clean=False):
                docstrings.add(id(n.body[0].value))
        return [n.value for n in ast.walk(arbre) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]

    def test_les_fichiers_existent(self):
        self.assertTrue(ORCHESTRATEUR.exists())

    def test_aucun_chemin_absolu_de_commande_ni_de_dossier_utilisateur(self):
        for f in self.FICHIERS:
            if not f.exists():
                continue
            if f.suffix == ".py":
                morceaux = self.chaines_de_code(f)
            else:
                # seule exception : le chargement de l'environnement de Homebrew (« brew shellenv »), dont le préfixe est fixe sur Apple Silicon
                morceaux = [l for l in f.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#") and "shellenv" not in l]
            for m in morceaux:
                self.assertIsNone(self.CHEMIN_ABSOLU.search(m), f"{f.name} : chemin absolu dans {m!r}")

    def test_aucune_lecture_ni_ecriture_du_trousseau(self):
        for f in self.FICHIERS:
            if not f.exists():
                continue
            code = "\n".join(self.chaines_de_code(f)) if f.suffix == ".py" else "\n".join(
                l for l in f.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
            self.assertNotIn("find-generic-password", code, f.name)
            self.assertNotIn("delete-generic-password", code, f.name)
            # add-generic-password n'apparaît que dans une commande AFFICHÉE à l'utilisateur, jamais comme argument d'un appel
            for ligne in code.splitlines():
                if "add-generic-password" in ligne:
                    self.assertNotRegex(ligne, r"subprocess|\.act\(|\.sonde", f"{f.name} : {ligne}")

    def test_aucun_outil_interdit_n_est_appele(self):
        interdits = ("db_backup.sh", "db_restore_test.sh", "sauvegarde_sanctum.sh", "history_jira", "export_jira_api", "posture_evals",
                     "convert_books", "pmzilla_lab_library.py index")
        for f in self.FICHIERS:
            if not f.exists() or f.suffix != ".py":
                continue
            for m in self.chaines_de_code(f):
                for nom in interdits:
                    self.assertNotIn(nom, m, f"{f.name} : {nom} ne doit pas être appelé")

    def test_pas_de_chemin_homebrew_fixe_pour_uv(self):
        for f in self.FICHIERS:
            if f.exists():
                texte = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines() if "shellenv" not in l)
                self.assertNotIn("/opt/homebrew", texte, f.name)


if __name__ == "__main__":
    unittest.main()
