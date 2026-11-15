"""
Tests de tools/gh_issue.py sync-tasks : options --change, --groups, --dry-run et préfixe « Mothra : » des titres.
Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import unittest
from unittest import mock

from test_gh_issue import NAME, Base, g, rm

MOTHRA = "product:mothra"


def cles(test):
    """Clés des sous-issues créées, d'après les marqueurs des corps."""
    return sorted(i["body"].split(" -->")[0].removeprefix("<!-- roadmap-id: ") for i in test.load()["issues"]
                  if "/" in i["body"].split(" -->")[0])


class Change(Base):
    def test_sans_champ_change_refuse_puis_option(self):
        self.add_feature(1)
        code, _, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 7)
        self.assertIn("no change", err)
        code, out, err = self.run_cli("sync-tasks", "R-1", "--change", "demo")
        self.assertEqual(code, 0, err)
        self.assertEqual(cles(self), ["R-1/g1", "R-1/g2", "R-1/g3", "R-1/t2.2"])

    def test_option_egale_au_champ_accepte(self):
        self.add_feature(1, change="demo")
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--change", "demo")[0], 0)

    def test_option_contredit_le_champ_refus_sans_ecriture(self):
        self.add_feature(1, change="demo")
        code, _, err = self.run_cli("sync-tasks", "R-1", "--change", "autre")
        self.assertEqual(code, 7)
        self.assertIn("contradicts", err)
        self.assertEqual(self.calls(writes_only=True), [])


class Groupes(Base):
    def test_intervalle_limite_les_groupes(self):
        self.add_feature(1, change="demo")
        code, out, err = self.run_cli("sync-tasks", "R-1", "--groups", "2-3")
        self.assertEqual(code, 0, err)
        self.assertEqual(cles(self), ["R-1/g2", "R-1/g3", "R-1/t2.2"])

    def test_liste_et_intervalles(self):
        self.add_feature(1, change="demo")
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--groups", "1,3")[0], 0)
        self.assertEqual(cles(self), ["R-1/g1", "R-1/g3"])

    def test_groupe_inconnu_refuse_avant_toute_ecriture(self):
        self.add_feature(1, change="demo")
        code, _, err = self.run_cli("sync-tasks", "R-1", "--groups", "2-9")
        self.assertEqual(code, 7)
        self.assertIn("unknown group", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_forme_invalide_ou_inversee(self):
        self.add_feature(1, change="demo")
        for bad in ("a", "3-1", "1,,2"):
            code, _, err = self.run_cli("sync-tasks", "R-1", "--groups", bad)
            self.assertEqual(code, 2, bad)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])


class TitresMothra(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1, change="demo")
        self.run_cli("edit", "R-1", "--product", "mothra")

    def titres(self):
        return {k: self.issue(k)["title"] for k in ("R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3")}

    def test_prefixe_ajoute(self):
        self.assertEqual(self.run_cli("sync-tasks", "R-1")[0], 0)
        self.assertEqual(self.titres(), {"R-1/g1": "R-1 · Mothra : 1. Inputs", "R-1/g2": "R-1 · Mothra : 2. Build",
                                         "R-1/t2.2": "R-1 · Mothra : 2.2 (user step)", "R-1/g3": "R-1 · Mothra : 3. User run"})

    def test_prefixe_jamais_double(self):
        path = self.root / "openspec" / "changes" / "demo" / "tasks.md"
        path.write_text(path.read_text(encoding="utf-8").replace("## 1. Inputs", "## 1. Mothra : Inputs"), encoding="utf-8")
        self.run_cli("sync-tasks", "R-1")
        self.assertEqual(self.issue("R-1/g1")["title"], "R-1 · Mothra : 1. Inputs")   # le « Mothra : » du groupe est retiré, posé une fois en tête
        self.assertEqual(g.mothra_title("R-1 · Mothra : x"), "R-1 · Mothra : x")
        self.assertEqual(g.mothra_title("R-1 · Mothra : Mothra : x"), "R-1 · Mothra : x")
        self.assertEqual(g.mothra_title("R-1 · 2.2 Mothra : x"), "R-1 · Mothra : 2.2 x")

    def test_feature_sans_produit_titres_inchanges(self):
        self.run_cli("edit", "R-1", "--product", "none")
        self.run_cli("sync-tasks", "R-1")
        self.assertEqual(self.issue("R-1/g1")["title"], "R-1 · 1. Inputs")

    def test_controle_refuse_un_titre_sans_prefixe_avant_ecriture(self):
        n = len(self.calls(writes_only=True))
        with mock.patch.object(g, "mothra_title", lambda t: t):
            code, _, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 7)
        self.assertIn("Mothra : ", err)
        self.assertEqual(len(self.calls(writes_only=True)), n)


class DryRun(Base):
    def test_dry_run_n_ecrit_rien_et_liste(self):
        self.add_feature(1, change="demo")
        self.run_cli("edit", "R-1", "--product", "mothra")
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("sync-tasks", "R-1", "--dry-run", "--groups", "2-3")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertIn("would create R-1/g2: R-1 · Mothra : 2. Build", out)
        self.assertIn("model:sonnet", out)
        self.assertIn("estimate 1h", out)
        self.assertNotIn("R-1/g1", out)
        self.assertNotIn("nothing to do", out)

    def test_dry_run_annonce_la_memorisation(self):
        self.add_feature(1)
        code, out, err = self.run_cli("sync-tasks", "R-1", "--dry-run", "--change", "demo", "--groups", "2-3")
        self.assertEqual(code, 0, err)
        self.assertIn("would remember in the block of R-1: change=demo, groups=2-3", out)
        self.assertNotIn("groups", rm.parse_block(self.issue("R-1")["body"]))
        self.run_cli("sync-tasks", "R-1", "--change", "demo", "--groups", "2-3")
        code, out, _ = self.run_cli("sync-tasks", "R-1", "--dry-run", "--change", "demo", "--groups", "2-3")
        self.assertNotIn("would remember", out)                 # le bloc porte déjà les mêmes valeurs

    def test_dry_run_avec_change_et_sans_champ(self):
        self.add_feature(1)
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("sync-tasks", "R-1", "--dry-run", "--change", "demo")
        self.assertEqual(code, 0, err)
        self.assertIn("would create R-1/g1", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_dry_run_refuse_comme_le_vrai_run(self):
        self.add_feature(1, change="demo")
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--dry-run", "--groups", "9")[0], 7)
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--dry-run", "--change", "autre")[0], 7)

    def test_dry_run_signale_l_existant(self):
        self.add_feature(1, change="demo")
        self.run_cli("sync-tasks", "R-1")
        code, out, _ = self.run_cli("sync-tasks", "R-1", "--dry-run")
        self.assertIn("exists", out)
        self.assertNotIn("would create", out)

    def test_dry_run_existant_titre_reel_et_prefixe_manquant(self):
        self.add_feature(1, change="demo")
        self.run_cli("sync-tasks", "R-1")                       # créées sans préfixe (feature sans produit)
        self.run_cli("edit", "R-1", "--product", "mothra")
        code, out, _ = self.run_cli("sync-tasks", "R-1", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("R-1/g1: R-1 · 1. Inputs", out)            # le titre réel, pas le titre prévu
        self.assertIn("WARNING: title lacks 'Mothra : '", out)

    def test_dry_run_refuse_par_le_garde_de_noms(self):
        self.add_feature(1, change="demo")
        path = self.root / "openspec" / "changes" / "demo" / "tasks.md"
        path.write_text(path.read_text(encoding="utf-8").replace("## 3. User run [user]", f"## 3. Avec {NAME} [user]"), encoding="utf-8")
        code, out, err = self.run_cli("sync-tasks", "R-1", "--dry-run")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name", err)
        self.assertNotIn(NAME, out + err)
        self.assertEqual(self.calls(writes_only=True), [])


class Options(Base):
    def test_groups_vide_refuse_code_2(self):
        self.add_feature(1, change="demo")
        code, _, err = self.run_cli("sync-tasks", "R-1", "--groups", "")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_change_forme_refusee_code_2(self):
        self.add_feature(1)
        for bad in ("", "Demo", "-x", "a b", "../demo"):
            code, _, err = self.run_cli("sync-tasks", "R-1", "--change", bad)
            self.assertEqual(code, 2, bad)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])


def tasks_23():
    return "# Tasks\n\n" + "".join(f"## {n}. Groupe {n} [model: sonnet]\n\n- [ ] {n}.1 Faire.\n\n" for n in range(1, 24))


class Memorisation(Base):
    """Le périmètre des groupes est mémorisé dans le bloc de la feature : plus de dérive vers les 23 groupes."""

    def setUp(self):
        super().setUp()
        (self.root / "openspec" / "changes" / "demo" / "tasks.md").write_text(tasks_23(), encoding="utf-8")

    def hors(self, lo=2, hi=11):
        return [k for k in cles(self) if k.startswith("R-1/g") and not lo <= int(k.removeprefix("R-1/g")) <= hi]

    def block(self):
        return rm.parse_block(self.issue("R-1")["body"])

    def test_premier_lancement_memorise_groups_et_change(self):
        self.add_feature(1)
        code, out, err = self.run_cli("sync-tasks", "R-1", "--change", "demo", "--groups", "2-11")
        self.assertEqual(code, 0, err)
        self.assertEqual((self.block()["change"], self.block()["groups"]), ("demo", "2-11"))
        self.assertEqual(self.hors(), [])
        self.assertEqual(len(cles(self)), 10)

    def test_dry_run_ne_memorise_rien(self):
        self.add_feature(1)
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--change", "demo", "--groups", "2-11", "--dry-run")[0], 0)
        self.assertNotIn("groups", self.block())
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_ne_memorise_rien(self):
        self.add_feature(1)
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--change", "demo", "--groups", "2-30")[0], 7)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertNotIn("groups", self.block())

    def test_cas_dangereux_sync_sans_option(self):
        self.add_feature(1, change="demo", groups="2-11")
        self.run_cli("edit", "R-1", "--product", "mothra")
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.hors(), [])
        self.assertEqual(len(cles(self)), 10)

    def test_cas_dangereux_close_feature_taches_ouvertes(self):
        self.add_feature(1, change="demo", groups="2-11")
        self.run_cli("edit", "R-1", "--product", "mothra")
        code, _, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 7)
        self.assertIn("open sub-issues remain", err)
        self.assertEqual(self.hors(), [])
        self.assertEqual(len(cles(self)), 10)                   # la synchronisation de la fermeture a bien eu lieu, dans 2-11

    def test_cas_dangereux_close_feature_va_au_bout(self):
        self.add_feature(1, change="demo", groups="2-11")
        self.run_cli("edit", "R-1", "--product", "mothra")
        (self.root / "openspec" / "changes" / "demo" / "tasks.md").write_text(
            "# Tasks\n\n" + "".join(f"## {n}. Groupe {n} [model: sonnet]\n\n- [{'x' if 2 <= n <= 11 else ' '}] {n}.1 Faire.\n\n"
                                    for n in range(1, 24)), encoding="utf-8")
        code, _, err = self.run_cli("close-feature", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.hors(), [])
        self.assertEqual(len(cles(self)), 10)
        self.assertEqual(self.issue("R-1")["state"], "closed")
        self.assertEqual(self.block()["groups"], "2-11")        # la fermeture ne perd pas la clé
        self.assertIn("done_on", self.block())

    def test_deuxieme_sync_sans_option_apres_groups(self):
        self.add_feature(1)
        self.run_cli("sync-tasks", "R-1", "--change", "demo", "--groups", "2-11")
        code, _, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.hors(), [])
        self.assertEqual(len(cles(self)), 10)

    def test_groups_contradictoire_refuse_sans_ecriture(self):
        self.add_feature(1, change="demo", groups="2-11")
        code, _, err = self.run_cli("sync-tasks", "R-1", "--groups", "2-12")
        self.assertEqual(code, 7)
        self.assertIn("contradicts", err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.run_cli("sync-tasks", "R-1", "--groups", "11,2-10")[0], 0)   # même ensemble : accepté

    def test_feature_sans_groups_inchangee(self):
        self.add_feature(1, change="demo")
        self.assertEqual(self.run_cli("sync-tasks", "R-1")[0], 0)
        self.assertEqual(len(cles(self)), 23)
        self.assertNotIn("groups", self.block())

    def test_validation_du_bloc(self):
        self.add_feature(1, change="demo")
        for bad in ("a", "3-1", "1,,2", "", "2-"):
            code, _, err = self.run_cli("edit", "R-1", "--set", f"groups={bad}")
            self.assertEqual(code, 7, bad)
        self.assertEqual(self.run_cli("edit", "R-1", "--set", "groups=2-8,11")[0], 0)

    def test_forme_normalisee(self):
        self.assertEqual(g.format_groups({11, 2, 3, 4, 9}), "2-4,9,11")
        self.assertEqual(g.format_groups({5}), "5")


if __name__ == "__main__":
    unittest.main()
