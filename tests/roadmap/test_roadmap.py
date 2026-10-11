"""
Tests du lecteur de la file de travail (tools/roadmap.py).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import roadmap  # noqa: E402

DOCUMENT_REEL = RACINE / "docs" / "pmzilla" / "feuille-de-route.md"


def job(i, **kw):
    d = {"id": f"R-{i}", "title": f"Travail {i}", "depends_on": [], "conditions": "", "state": "ready",
         "estimate": "1h", "method": "direct-prompt", "model": "tbd"}
    d.update(kw)
    return d


def rendu(j):
    """Un job en YAML de style bloc, une clé par ligne."""
    lignes = []
    for n, (k, v) in enumerate(j.items()):
        if isinstance(v, list):
            v = "[" + ", ".join(v) + "]"
        elif isinstance(v, str):
            v = f'"{v}"' if (v == "" or k in ("title", "conditions")) else v
        lignes.append(("  - " if n == 0 else "    ") + f"{k}: {v}")
    return "\n".join(lignes)


def document(jobs, avant="Prose libre.\n\n", apres="\nFin.\n"):
    return avant + "```yaml\njobs:\n" + "\n".join(rendu(j) for j in jobs) + "\n```\n" + apres


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "feuille.md"

    def ecrit(self, texte):
        self.chemin.write_text(texte, encoding="utf-8")

    def lance(self, *args):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                code = roadmap.main(list(args))
            except SystemExit as e:
                code = e.code
        return code, sortie.getvalue(), erreur.getvalue()

    def check(self, jobs=None, texte=None):
        self.ecrit(texte if texte is not None else document(jobs))
        return self.lance("check", "--file", str(self.chemin))

    def next(self, budget, jobs, today="2026-10-10"):
        self.ecrit(document(jobs))
        return self.lance("next", "--budget", budget, "--today", today, "--file", str(self.chemin))


class TestFormat(Base):
    def test_file_valide(self):
        code, out, _ = self.check([job(1), job(2, state="blocked", depends_on=["R-1"], not_before="2026-11-01",
                                         due="2026-12-01", change="un-change", estimate="tbd", method="openspec")])
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("roadmap : "))

    def test_deux_blocs_yaml(self):
        texte = document([job(1)]) + "\n```yaml\nautre: 1\n```\n"
        code, out, _ = self.check(texte=texte)
        self.assertEqual(code, 1)
        self.assertIn("2 bloc", out)

    def test_aucun_bloc_yaml(self):
        code, out, _ = self.check(texte="Seulement de la prose.\n")
        self.assertEqual(code, 1)
        self.assertIn("0 bloc", out)

    def test_bloc_non_yaml_ignore(self):
        texte = "```bash\nls\n```\n" + document([job(1)])
        self.assertEqual(self.check(texte=texte)[0], 0)

    def test_champ_obligatoire_absent(self):
        j = job(1)
        del j["method"]
        code, out, _ = self.check([j])
        self.assertEqual(code, 1)
        self.assertIn("R-1 : method", out)

    def test_valeurs_interdites(self):
        for champ, valeur in (("state", "waiting"), ("method", "magic"), ("estimate", "bientot"), ("estimate", "0h"),
                              ("id", "X-1"), ("not_before", "demain"), ("due", "2026-13-40"), ("model", "gpt"),
                              ("model", "Opus"), ("model", "claude-opus"), ("model", "")):
            with self.subTest(champ=champ, valeur=valeur):
                j = job(1)
                j[champ] = valeur
                code, out, _ = self.check([j])
                self.assertEqual(code, 1)
                self.assertIn(f": {champ} :", out)

    def test_modeles_admis(self):
        """Décision R-16 du 2026-10-10 : opus, sonnet, haiku ou tbd, rien d'autre."""
        for m in ("opus", "sonnet", "haiku", "tbd"):
            with self.subTest(m=m):
                self.assertEqual(self.check([job(1, model=m)])[0], 0)

    def test_le_message_du_modele_nomme_les_valeurs_admises(self):
        code, out, _ = self.check([job(1, model="gpt")])
        self.assertEqual(code, 1)
        self.assertIn("R-1 : model : valeur hors de opus, sonnet, haiku, tbd", out)

    def test_durees_valides(self):
        for d in ("45min", "2h", "1h30", "tbd"):
            with self.subTest(d=d):
                self.assertEqual(self.check([job(1, estimate=d)])[0], 0)

    def test_champ_inconnu(self):
        code, out, _ = self.check([job(1, extra="x")])
        self.assertEqual(code, 1)
        self.assertIn("R-1 : extra", out)

    def test_une_ligne_par_probleme(self):
        code, out, _ = self.check([job(1, state="x"), job(2, method="y")])
        self.assertEqual(code, 1)
        self.assertEqual(len(out.strip().splitlines()), 2)
        self.assertTrue(all(l.startswith("roadmap : ") for l in out.splitlines()))


class TestCoherence(Base):
    def test_identifiant_en_double(self):
        code, out, _ = self.check([job(1), job(1)])
        self.assertEqual(code, 1)
        self.assertIn("R-1 : id", out)

    def test_dependance_inconnue(self):
        code, out, _ = self.check([job(1, depends_on=["R-9"], state="blocked")])
        self.assertEqual(code, 1)
        self.assertIn("R-1 : depends_on", out)
        self.assertIn("R-9", out)

    def test_cycle(self):
        code, out, _ = self.check([job(1, depends_on=["R-2"], state="blocked"), job(2, depends_on=["R-1"], state="blocked")])
        self.assertEqual(code, 1)
        self.assertIn("cycle", out)
        self.assertIn("R-1", out)
        self.assertIn("R-2", out)

    def test_ready_avec_dependance_en_attente(self):
        code, out, _ = self.check([job(1, state="in-progress"), job(2, depends_on=["R-1"])])
        self.assertEqual(code, 1)
        self.assertIn("R-2 : state", out)

    def test_done_avec_dependance_non_done(self):
        code, out, _ = self.check([job(1, state="blocked"), job(2, depends_on=["R-1"], state="done")])
        self.assertEqual(code, 1)
        self.assertIn("R-2 : state", out)

    def test_ready_avec_dependance_done(self):
        self.assertEqual(self.check([job(1, state="done"), job(2, depends_on=["R-1"])])[0], 0)

    def test_check_ne_modifie_pas(self):
        texte = document([job(1)])
        self.check(texte=texte)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), texte)


class TestNext(Base):
    def test_budget_rempli_dans_l_ordre(self):
        code, out, _ = self.next("2h", [job(1, estimate="1h"), job(2, estimate="90min"), job(3, estimate="30min")])
        self.assertEqual(code, 0, out)
        propose, _, reste = out.partition("trop long")
        self.assertIn("R-1", propose)
        self.assertIn("R-3", propose)
        self.assertNotIn("R-2", propose)
        self.assertIn("R-2", reste)
        self.assertIn("total 1h30", out)

    def test_estimation_tbd_a_part_et_non_comptee(self):
        code, out, _ = self.next("1h", [job(1, estimate="tbd"), job(2, estimate="1h")])
        self.assertEqual(code, 0)
        avant, _, apres = out.partition("sans estimation")
        self.assertIn("R-2", avant)
        self.assertNotIn("R-1", avant)
        self.assertIn("R-1", apres)
        self.assertIn("total 1h", out)

    def test_date_not_before_future_et_atteinte(self):
        jobs = [job(1, not_before="2026-11-20"), job(2, not_before="2026-10-10")]
        _, out, _ = self.next("2h", jobs, today="2026-10-10")
        self.assertNotIn("R-1", out)
        self.assertIn("R-2", out)
        _, out, _ = self.next("2h", jobs, today="2026-11-20")
        self.assertIn("R-1", out)

    def test_jobs_non_proposables(self):
        jobs = [job(1, state="blocked"), job(2, state="in-progress"), job(3, state="done"),
                job(4, state="done"), job(5, depends_on=["R-4"])]
        jobs[4]["state"] = "ready"
        _, out, _ = self.next("8h", jobs)
        for i in (1, 2, 3):
            self.assertNotIn(f"R-{i} ", out)
        self.assertIn("R-5", out)

    def test_dependance_non_done_exclut(self):
        # file invalide (ready avec dépendance en attente) : code 1, rien proposé
        code, out, _ = self.next("8h", [job(1, state="blocked"), job(2, depends_on=["R-1"])])
        self.assertEqual(code, 1)
        self.assertNotIn("jobs proposés", out)

    def test_affichage_complet(self):
        _, out, _ = self.next("2h", [job(1, estimate="1h", method="openspec", model="opus", conditions="a confirmer", due="2026-10-23")])
        for attendu in ("R-1", "Travail 1", "1h", "openspec", "opus", "a confirmer", "2026-10-23"):
            self.assertIn(attendu, out)

    def test_budget_mal_forme(self):
        for b in ("beaucoup", "tbd", "0h", "", "2 heures"):
            with self.subTest(b=b):
                code, out, err = self.next(b, [job(1)])
                self.assertEqual(code, 2)
                self.assertNotIn("R-1", out)

    def test_file_invalide(self):
        self.assertEqual(self.next("2h", [job(1, state="x")])[0], 1)

    def test_ne_modifie_pas(self):
        self.ecrit(document([job(1)]))
        avant = self.chemin.read_text(encoding="utf-8")
        self.lance("next", "--budget", "1h", "--file", str(self.chemin))
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)


class TestDone(Base):
    def test_une_seule_ligne_change_et_debloques_listes(self):
        jobs = [job(1, state="in-progress"), job(2, depends_on=["R-1"], state="blocked"),
                job(3, depends_on=["R-1", "R-4"], state="blocked"), job(4, state="blocked")]
        avant = document(jobs)
        self.ecrit(avant)
        code, out, _ = self.lance("done", "R-1", "--file", str(self.chemin))
        self.assertEqual(code, 0, out)
        apres = self.chemin.read_text(encoding="utf-8")
        a, b = avant.split("\n"), apres.split("\n")
        self.assertEqual(len(a), len(b))
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        self.assertEqual(diff, [("    state: in-progress", "    state: done")])
        self.assertIn("R-2", out)
        self.assertNotIn("R-3", out)
        self.assertIn("blocked", apres)  # R-2 reste blocked
        self.assertEqual(self.lance("check", "--file", str(self.chemin))[0], 0)

    def test_etat_sur_la_ligne_du_tiret(self):
        texte = "Prose.\n\n```yaml\njobs:\n  - state: ready\n    id: R-1\n    title: \"T\"\n    depends_on: []\n    conditions: \"\"\n" \
                "    estimate: 1h\n    method: openspec\n    model: tbd\n```\nFin.\n"
        self.ecrit(texte)
        self.assertEqual(self.lance("done", "R-1", "--file", str(self.chemin))[0], 0)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), texte.replace("state: ready", "state: done"))

    def test_identifiant_inconnu(self):
        self.ecrit(document([job(1)]))
        avant = self.chemin.read_text(encoding="utf-8")
        code, out, _ = self.lance("done", "R-9", "--file", str(self.chemin))
        self.assertEqual(code, 1)
        self.assertIn("R-9", out)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)

    def test_file_invalide(self):
        self.ecrit(document([job(1, state="x")]))
        avant = self.chemin.read_text(encoding="utf-8")
        self.assertEqual(self.lance("done", "R-1", "--file", str(self.chemin))[0], 1)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)

    def test_usage_sans_identifiant(self):
        self.ecrit(document([job(1)]))
        self.assertEqual(self.lance("done", "--file", str(self.chemin))[0], 2)


class TestCodesDeSortie(Base):
    def test_fichier_absent(self):
        for args in (("check",), ("next", "--budget", "1h"), ("done", "R-1")):
            with self.subTest(args=args):
                code, _, err = self.lance(*args, "--file", str(self.chemin))
                self.assertEqual(code, 2)
                self.assertIn("roadmap : ", err)

    def test_usage(self):
        self.assertEqual(self.lance()[0], 2)
        self.assertEqual(self.lance("inconnu")[0], 2)
        self.assertEqual(self.lance("next", "--file", str(self.chemin))[0], 2)

    def test_date_du_jour_injectable_par_environnement(self):
        import os
        self.ecrit(document([job(1, not_before="2026-11-20")]))
        os.environ["ROADMAP_TODAY"] = "2026-11-20"
        try:
            _, out, _ = self.lance("next", "--budget", "1h", "--file", str(self.chemin))
        finally:
            del os.environ["ROADMAP_TODAY"]
        self.assertIn("R-1", out)


def paragraphes(*ids):
    """Intro, titre de section et un paragraphe de description par identifiant."""
    return "Intro.\n\n## Travaux décrits\n\n" + "".join(f"**R-{i}, travail {i}.** Description du travail {i}.\n\n" for i in ids)


class TestArchive(Base):
    def setUp(self):
        super().setUp()
        self.archive = self.chemin.with_name("feuille-archive.md")

    def ecrit_file(self, jobs, ids=None):
        self.ecrit(document(jobs, avant=paragraphes(*(ids or [j["id"][2:] for j in jobs]))))

    def archive_cmd(self, *extra):
        return self.lance("archive", "--file", str(self.chemin), *extra)

    def ids(self, chemin):
        return [l.split("R-")[1] for l in chemin.read_text(encoding="utf-8").splitlines() if l.startswith("  - id: R-")]

    def test_deplacement_mot_pour_mot(self):
        self.ecrit_file([job(1, state="done"), job(2)])
        avant = self.chemin.read_text(encoding="utf-8")
        code, out, _ = self.archive_cmd()
        self.assertEqual(code, 0)
        self.assertIn("R-1", out)
        actif = self.chemin.read_text(encoding="utf-8")
        archive = self.archive.read_text(encoding="utf-8")
        self.assertEqual(self.ids(self.chemin), ["2"])
        self.assertEqual(self.ids(self.archive), ["1"])
        self.assertNotIn("**R-1,", actif)
        self.assertIn("**R-1, travail 1.** Description du travail 1.\n", archive)
        self.assertIn(rendu(job(1, state="done")), archive)
        # la file ne perd que l'entrée et le paragraphe de R-1
        retire = avant.replace(rendu(job(1, state="done")) + "\n", "").replace("**R-1, travail 1.** Description du travail 1.\n\n", "")
        self.assertEqual(actif, retire)
        self.assertEqual(self.lance("check", "--file", str(self.chemin))[0], 0)

    def test_en_tete_de_l_archive_d_une_phrase(self):
        self.ecrit_file([job(1, state="done"), job(2)])
        self.archive_cmd()
        premieres = self.archive.read_text(encoding="utf-8").splitlines()
        self.assertTrue(premieres[0].startswith("# "))
        self.assertIn("feuille.md", premieres[2])

    def test_travail_garde_car_un_travail_ouvert_en_depend(self):
        self.ecrit_file([job(1, state="done"), job(2, depends_on=["R-1"]), job(3, state="done"),
                         job(4, state="done"), job(5, state="done", depends_on=["R-4"])])
        code, _, _ = self.archive_cmd()
        self.assertEqual(code, 0)
        self.assertEqual(self.ids(self.chemin), ["1", "2"])
        self.assertEqual(sorted(self.ids(self.archive)), ["3", "4", "5"])
        self.assertIn("**R-1,", self.chemin.read_text(encoding="utf-8"))

    def test_dependance_d_un_travail_archive_vers_un_travail_garde(self):
        self.ecrit_file([job(1, state="done"), job(2, state="done", depends_on=["R-1"]), job(3, depends_on=["R-1"])])
        self.assertEqual(self.archive_cmd()[0], 0)
        self.assertEqual(self.ids(self.chemin), ["1", "3"])
        self.assertEqual(self.ids(self.archive), ["2"])
        self.assertEqual(self.lance("check", "--file", str(self.chemin))[0], 0)

    def test_idempotence(self):
        self.ecrit_file([job(1, state="done"), job(2)])
        self.archive_cmd()
        actif, archive = self.chemin.read_text(encoding="utf-8"), self.archive.read_text(encoding="utf-8")
        code, out, _ = self.archive_cmd()
        self.assertEqual(code, 0)
        self.assertIn("rien à archiver", out)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), actif)
        self.assertEqual(self.archive.read_text(encoding="utf-8"), archive)

    def test_les_nouveaux_travaux_passent_en_tete_de_l_archive(self):
        self.ecrit_file([job(1, state="done"), job(2, depends_on=["R-1"])])
        self.assertIn("rien", self.archive_cmd()[1])  # R-1 gardé : R-2 en dépend
        self.assertFalse(self.archive.exists())
        self.ecrit_file([job(1, state="done"), job(2, state="done", depends_on=["R-1"]), job(3, state="done")])
        self.archive_cmd()
        self.assertEqual(self.ids(self.archive), ["1", "2", "3"])
        self.ecrit_file([job(4, state="done")])
        self.archive_cmd()
        self.assertEqual(self.ids(self.archive), ["4", "1", "2", "3"])
        archive = self.archive.read_text(encoding="utf-8")
        self.assertLess(archive.index("**R-4,"), archive.index("**R-1,"))
        self.assertEqual(self.lance("check", "--file", str(self.chemin))[0], 0)

    def test_dry_run_n_ecrit_rien(self):
        self.ecrit_file([job(1, state="done"), job(2)])
        avant = self.chemin.read_text(encoding="utf-8")
        code, out, _ = self.archive_cmd("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("R-1", out)
        self.assertNotIn("R-2", out)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)
        self.assertFalse(self.archive.exists())

    def test_file_invalide_avant(self):
        self.ecrit_file([job(1, state="done"), job(2, state="bizarre")])
        avant = self.chemin.read_text(encoding="utf-8")
        code, out, _ = self.archive_cmd()
        self.assertEqual(code, 1)
        self.assertIn("R-2", out)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)
        self.assertFalse(self.archive.exists())

    def test_travail_sans_paragraphe_de_description(self):
        self.ecrit(document([job(1, state="done"), job(2)], avant=paragraphes(2)))
        self.assertEqual(self.archive_cmd()[0], 0)
        self.assertEqual(self.ids(self.archive), ["1"])
        self.assertIn("**R-2,", self.chemin.read_text(encoding="utf-8"))

    def test_dernier_travail_archive_laisse_une_file_vide_valide(self):
        self.ecrit_file([job(1, state="done")])
        self.assertEqual(self.archive_cmd()[0], 0)
        self.assertEqual(self.lance("check", "--file", str(self.chemin))[0], 0)
        self.assertEqual(self.ids(self.archive), ["1"])


class TestDeuxFichiers(Base):
    def setUp(self):
        super().setUp()
        self.archive = self.chemin.with_name("feuille-archive.md")

    def ecrit_deux(self, actifs, archives):
        self.ecrit(document(actifs))
        self.archive.write_text(document(archives), encoding="utf-8")

    def test_check_resout_une_dependance_archivee(self):
        self.ecrit_deux([job(2, depends_on=["R-1"])], [job(1, state="done")])
        self.assertEqual(self.lance("check", "--file", str(self.chemin))[0], 0)

    def test_dependance_absente_des_deux_fichiers(self):
        self.ecrit_deux([job(2, depends_on=["R-9"])], [job(1, state="done")])
        code, out, _ = self.lance("check", "--file", str(self.chemin))
        self.assertEqual(code, 1)
        self.assertIn("R-2 : depends_on : dépendance inconnue R-9", out)

    def test_identifiant_en_double_entre_les_deux_fichiers(self):
        self.ecrit_deux([job(1)], [job(1, state="done")])
        code, out, _ = self.lance("check", "--file", str(self.chemin))
        self.assertEqual(code, 1)
        self.assertIn("R-1 : id : identifiant en double", out)

    def test_l_archive_ne_contient_que_des_travaux_done(self):
        self.ecrit_deux([job(2)], [job(1, state="ready")])
        code, out, _ = self.lance("check", "--file", str(self.chemin))
        self.assertEqual(code, 1)
        self.assertIn("R-1 : state", out)

    def test_archive_illisible(self):
        self.ecrit(document([job(2)]))
        self.archive.write_text("pas de bloc\n", encoding="utf-8")
        code, out, _ = self.lance("check", "--file", str(self.chemin))
        self.assertEqual(code, 1)
        self.assertIn("archive", out)

    def test_next_compte_un_travail_archive_comme_done(self):
        self.ecrit_deux([job(2, depends_on=["R-1"])], [job(1, state="done")])
        code, out, _ = self.lance("next", "--budget", "2h", "--today", "2026-10-10", "--file", str(self.chemin))
        self.assertEqual(code, 0)
        self.assertIn("R-2", out)

    def test_done_debloque_en_lisant_l_archive(self):
        self.ecrit_deux([job(3, depends_on=["R-1", "R-2"], state="blocked"), job(2)], [job(1, state="done")])
        code, out, _ = self.lance("done", "R-2", "--file", str(self.chemin))
        self.assertEqual(code, 0)
        self.assertIn("R-3", out)

    def test_done_sur_un_identifiant_archive(self):
        self.ecrit_deux([job(2)], [job(1, state="done")])
        avant, avant_archive = self.chemin.read_text(encoding="utf-8"), self.archive.read_text(encoding="utf-8")
        code, out, _ = self.lance("done", "R-1", "--file", str(self.chemin))
        self.assertEqual(code, 0)
        self.assertIn("R-1", out)
        self.assertIn("archiv", out)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)
        self.assertEqual(self.archive.read_text(encoding="utf-8"), avant_archive)


class TestDocumentReel(unittest.TestCase):
    def test_garde_sur_le_document_reel(self):
        if not DOCUMENT_REEL.exists():
            self.skipTest(f"{DOCUMENT_REEL.relative_to(RACINE)} n'existe pas encore (tâche 3.3 : amorçage de la file)")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = roadmap.main(["check", "--file", str(DOCUMENT_REEL)])
        # n'affiche que « job : champ », jamais le texte libre des jobs
        self.assertEqual(code, 0, "\n".join(l.split(" : ", 3)[1] + " : " + l.split(" : ", 3)[2] if l.count(" : ") >= 2 else l
                                            for l in sortie.getvalue().splitlines()))


if __name__ == "__main__":
    unittest.main()
