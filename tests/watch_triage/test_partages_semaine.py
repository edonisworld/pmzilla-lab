"""
Tests des partages, de l'inventaire hebdomadaire et de la relance de la notation en ombre (tools/watch_triage.py).

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

Articles et comptes inventés ; faux client social (`veille.links_from_bluesky` remplacé), faux modèle (`httpx.post`).
Aucun réseau, aucun modèle local, aucun dossier réel : tout est dans le dossier temporaire de la classe Base voisine.
Couvre : cmd_shares (marquage, références, saut sans identifiant, service arrêté), cmd_week (lignes du fichier, période,
plafond, aucun texte d'article) et la relance unique d'une réponse anglaise inutilisable (aucune sur une erreur réseau).
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_triage as tri  # noqa: E402
import watch_lab as veille  # noqa: E402
import test_watch_triage as voisin  # noqa: E402
import test_shadow as ombre  # noqa: E402

AUJOURD_HUI = dt.date.today()


def il_y_a(jours: int) -> str:
    return (AUJOURD_HUI - dt.timedelta(days=jours)).isoformat()


class Partages(voisin.Base):
    def reglages(self, compte="compte.test"):
        tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tri.CONFIG_FILE.write_text("mode: observation\nmodel: faux\nto_read: 5\ndays: 7\nsubstance_threshold: 3\n"
                                   "themes:\n  - t\n", encoding="utf-8")
        if compte:   # l'identifiant va dans la couche locale, jamais dans tri.yaml
            tri.local_config_file().write_text(f"bluesky: {compte}\n", encoding="utf-8")

    def partages(self, posts):
        patch = mock.patch.object(veille, "links_from_bluesky", return_value=posts)
        self.faux_lien = patch.start()
        self.addCleanup(patch.stop)

    def test_article_partage_marque_et_ajoute_aux_references(self):
        self.reglages()
        self.ajouter("a.md", 4, url="https://s.test/a")
        self.ajouter("b.md", 4, url="https://s.test/b")
        self.partages([("https://www.s.test/a?utm_source=x", "2026-10-03"), ("https://ailleurs.test/z", "2026-10-04")])
        sortie = self.lancer(tri.cmd_shares, pages=2)
        self.assertEqual([tuple(r) for r in self.connection.execute("SELECT file, url, post_date FROM shared")],
                         [("a.md", "https://s.test/a", "2026-10-03")])
        partages = [tuple(r) for r in self.connection.execute("SELECT url, title FROM refs WHERE origin = 'partage'")]
        self.assertEqual(partages, [("https://s.test/a", "a.md")])
        self.assertEqual(self.faux_lien.call_args.kwargs["max_pages"], 2)
        self.assertIn("2 liens lus", sortie)
        self.assertIn("1 nouveaux articles", sortie)

    def test_deuxieme_passage_n_ajoute_rien(self):
        self.reglages()
        self.ajouter("a.md", 4, url="https://s.test/a")
        self.partages([("https://s.test/a", "2026-10-03")])
        self.lancer(tri.cmd_shares, pages=1)
        sortie = self.lancer(tri.cmd_shares, pages=1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM shared").fetchone()[0], 1)
        self.assertIn("0 nouveaux", sortie)

    def test_sans_identifiant_l_etape_est_sautee_sans_rien_changer(self):
        self.reglages(compte="")
        self.ajouter("a.md", 4, url="https://s.test/a")
        self.partages([("https://s.test/a", "2026-10-03")])
        sortie = self.lancer(tri.cmd_shares, pages=1)
        self.assertIn("étape sautée", sortie)
        self.faux_lien.assert_not_called()
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM shared").fetchone()[0], 0)

    def test_service_arrete_le_passage_continue(self):
        self.reglages()
        self.ajouter("a.md", 4, url="https://s.test/a")
        patch = mock.patch.object(veille, "links_from_bluesky", side_effect=httpx.ConnectError("service coupé"))
        patch.start()
        self.addCleanup(patch.stop)
        sortie = self.lancer(tri.cmd_shares, pages=1)   # ne lève rien
        self.assertIn("n'a pas répondu", sortie)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM shared").fetchone()[0], 0)

    def test_compte_inconnu_est_traite_comme_un_service_sans_reponse(self):
        self.reglages()
        patch = mock.patch.object(veille, "links_from_bluesky", side_effect=SystemExit("compte inconnu"))
        patch.start()
        self.addCleanup(patch.stop)
        self.assertIn("n'a pas répondu", self.lancer(tri.cmd_shares, pages=1))


class Semaine(voisin.Base):
    def setUp(self):
        super().setUp()
        self.fichier = self.tmp / "_semaine.md"
        patch = mock.patch.object(tri, "WEEK_FILE", self.fichier)
        patch.start()
        self.addCleanup(patch.stop)

    def dater(self, nom, publie, collecte):
        self.connection.execute("UPDATE scores SET published = ?, collected = ? WHERE file = ?", (publie, collecte, nom))
        self.connection.commit()

    def semaine(self, **options):
        return self.lancer(tri.cmd_week, **{"days": 7, "max": 40, "per_run": False, **options})

    def test_lignes_du_fichier_et_marque_partage(self):
        self.ajouter("a.md", 4, titre="Un titre inventé", source="s.test", url="https://s.test/a")
        self.dater("a.md", il_y_a(1), il_y_a(1))
        self.connection.execute("INSERT INTO shared VALUES ('a.md', 'https://s.test/a', '2026-10-03', '2026-10-04')")
        self.connection.commit()
        sortie = self.semaine()
        texte = self.fichier.read_text(encoding="utf-8")
        self.assertIn("## Un titre inventé", texte)
        self.assertIn(f"- Source : s.test · publié le {il_y_a(1)} · pertinence", texte)
        self.assertIn("substance 4/5 · partagé", texte)
        self.assertIn("- Lien : https://s.test/a", texte)
        self.assertIn("- Fichier : a.md", texte)
        self.assertIn("- Résumé : résumé", texte)
        self.assertIn("- Apport : pourquoi", texte)
        self.assertIn("1 articles, classés par pertinence", texte)
        self.assertIn("1 articles retenus, publiés", sortie)

    def test_aucun_texte_d_article(self):
        self.ajouter("a.md", 4)
        self.dater("a.md", il_y_a(1), il_y_a(1))
        self.semaine()
        self.assertNotIn("texte inventé", self.fichier.read_text(encoding="utf-8"))

    def test_periode_par_date_de_publication_par_defaut_et_de_collecte_sur_demande(self):
        self.ajouter("ancien.md", 4)   # publié il y a longtemps, collecté hier (source ajoutée récemment)
        self.dater("ancien.md", il_y_a(60), il_y_a(1))
        self.ajouter("recent.md", 4)   # publié hier, collecté il y a longtemps
        self.dater("recent.md", il_y_a(1), il_y_a(60))
        self.semaine()
        texte = self.fichier.read_text(encoding="utf-8")
        self.assertIn("- Fichier : recent.md", texte)
        self.assertNotIn("- Fichier : ancien.md", texte)
        self.assertIn(f"publiés du {il_y_a(7)}", texte)
        self.semaine(per_run=True)
        texte = self.fichier.read_text(encoding="utf-8")
        self.assertIn("- Fichier : ancien.md", texte)
        self.assertNotIn("- Fichier : recent.md", texte)
        self.assertIn(f"collectés du {il_y_a(7)}", texte)

    def test_la_duree_borne_la_periode(self):
        self.ajouter("a.md", 4)
        self.dater("a.md", il_y_a(10), il_y_a(10))
        self.semaine(days=7)
        self.assertNotIn("- Fichier : a.md", self.fichier.read_text(encoding="utf-8"))
        self.semaine(days=30)
        self.assertIn("- Fichier : a.md", self.fichier.read_text(encoding="utf-8"))

    def test_le_plafond_garde_les_plus_pertinents_et_les_articles_ecartes_restent_dehors(self):
        for nom in ("a.md", "b.md", "c.md"):   # l'angle croît : a est le plus pertinent
            self.ajouter(nom, 4)
            self.dater(nom, il_y_a(1), il_y_a(1))
        self.ajouter("promo.md", 4, promo=1)
        self.dater("promo.md", il_y_a(1), il_y_a(1))
        sortie = self.semaine(max=2)
        texte = self.fichier.read_text(encoding="utf-8")
        self.assertEqual(texte.count("\n## "), 2)
        self.assertIn("2 articles retenus", sortie)
        self.assertNotIn("promo.md", texte)
        self.assertEqual([l for l in texte.splitlines() if l.startswith("- Fichier")],
                         ["- Fichier : a.md", "- Fichier : b.md"])   # les deux plus pertinents, dans l'ordre


class RelanceEnAnglais(ombre.Ombre):
    def appels_pour(self, echec):
        self.reglages(ombre=True)
        self.article("a1.md", "§5")
        self.article("a2.md", "§3")
        faux = ombre.FauxModele(echec_en=echec)
        with mock.patch.object(httpx, "post", faux):
            sortie = self.noter()
        return faux, sortie

    def test_reponse_anglaise_inutilisable_retentee_une_fois(self):
        faux, sortie = self.appels_pour("valeur")
        self.assertEqual(faux.appels, {"fr": 2, "en": 4})   # deux essais par article, pas trois
        self.assertEqual(self.lignes_ombre(), [])
        self.assertIn("2 échec(s)", sortie)

    def test_erreur_reseau_anglaise_non_retentee(self):
        faux, sortie = self.appels_pour("reseau")
        self.assertEqual(faux.appels, {"fr": 2, "en": 2})   # un seul essai par article
        self.assertIn("2 échec(s)", sortie)

    def test_sans_echec_un_seul_appel_anglais_par_article(self):
        faux, _ = self.appels_pour(None)
        self.assertEqual(faux.appels, {"fr": 2, "en": 2})
        self.assertEqual(len(self.lignes_ombre()), 2)


if __name__ == "__main__":
    unittest.main()
