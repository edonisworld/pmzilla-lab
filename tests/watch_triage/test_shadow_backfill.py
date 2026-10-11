"""
Tests du rattrapage de l'ombre : `watch_triage.py shadow-backfill` (R-30), tools/watch_triage.py.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

Mêmes faux que test_shadow.py : faux modèle (httpx.post), faux embedding, dossiers et tri.sqlite temporaires, Ollama simulé
joignable. Articles inventés. Couvre : PREUVE que les tables scores, forced et excluded, _to-read.md et les articles (gardés
et écartés) ne changent pas d'un octet ; un article déjà noté avec l'empreinte courante n'est pas renoté ; une empreinte périmée
l'est ; un échec du modèle est compté sans arrêter le passage ; les articles avec avis de calibration passent d'abord ;
refus quand l'ombre est désactivée ou qu'Ollama ne répond pas ; --limit ; fichier introuvable sauté ; article écarté relu
dans le dossier des écartés ; message de thresholds (--save).
"""
import csv
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_triage as tri  # noqa: E402
import watch_lab as veille  # noqa: E402
import test_shadow as ombre  # noqa: E402

TABLES_FRANCAISES = ("scores", "forced", "excluded")


class Rattrapage(ombre.Ombre):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(tri, "ollama_reachable", return_value=True)
        self.ollama = patch.start()
        self.addCleanup(patch.stop)

    def preparer(self, fichiers_ecartes=True):
        """Six articles notés en français SANS l'ombre (inactive), puis l'ombre activée : le rattrapage a tout à faire."""
        self.corpus()
        self.reglages(ombre=False)
        with mock.patch.object(ombre.httpx, "post", ombre.FauxModele()):
            self.noter()
        if fichiers_ecartes:
            self.lancer(tri.cmd_apply)         # mode filtre : certains articles passent dans le dossier des écartés
        self.reglages(ombre=True)

    def rattraper(self, faux=None, **options):
        faux = faux or ombre.FauxModele()
        with mock.patch.object(ombre.httpx, "post", faux):
            return self.lancer(tri.cmd_shadow_backfill, **{"limit": 0, **options}), faux

    def tables(self):
        return {t: [tuple(r) for r in self.connection.execute(f"SELECT * FROM {t} ORDER BY 1")] for t in TABLES_FRANCAISES}

    def fichiers(self):
        contenu = {p.name: p.read_bytes() for d in (self.articles, self.archive) if d.exists() for p in d.glob("*.md")}
        return contenu, {p.name for p in self.archive.glob("*.md")} if self.archive.exists() else set()

    def lire_a_lire(self):
        fichier = veille.to_read_file()
        return fichier.read_bytes() if fichier.exists() else None


class Ecritures(Rattrapage):
    def test_ne_change_aucune_decision_octet_pour_octet(self):
        self.preparer()
        tables, (fichiers, ecartes) = self.tables(), self.fichiers()
        self.assertTrue(ecartes)                                      # le test discrimine : des articles sont bien écartés
        a_lire = self.lire_a_lire()
        sortie, faux = self.rattraper()
        self.assertEqual(len(self.lignes_ombre()), 6)                 # écartés compris
        self.assertEqual(faux.appels["fr"], 0)                        # aucun appel français
        self.assertEqual(self.tables(), tables)
        self.assertEqual(self.fichiers(), (fichiers, ecartes))
        self.assertEqual(self.lire_a_lire(), a_lire)
        self.assertIn("6 notés, 0 échec(s), 0 sauté(s)", sortie)

    def test_la_note_a_la_meme_forme_que_l_ombre_quotidienne(self):
        self.preparer()
        self.rattraper()
        ligne = self.lignes_ombre()[0]
        self.assertEqual((ligne["language"], ligne["model"], ligne["prompts_hash"]),
                         ("en", "faux", tri.prompts_hash(self.module_en)))


class Reprise(Rattrapage):
    def test_un_article_deja_note_n_est_pas_renote(self):
        self.preparer()
        _, premier = self.rattraper()
        self.assertEqual(premier.appels["en"], 6)
        sortie, second = self.rattraper()
        self.assertEqual(second.appels["en"], 0)
        self.assertIn("0 article(s) à noter", sortie)

    def test_une_empreinte_perimee_est_renotee(self):
        self.preparer()
        self.rattraper()
        self.connection.execute("UPDATE shadow_scores SET prompts_hash = 'ancienne' WHERE url = 'https://s.test/a1.md'")
        self.connection.commit()
        _, faux = self.rattraper()
        self.assertEqual(faux.appels["en"], 1)
        self.assertEqual(self.connection.execute(
            "SELECT prompts_hash FROM shadow_scores WHERE url = 'https://s.test/a1.md'").fetchone()[0], tri.prompts_hash(self.module_en))

    def test_un_article_non_complet_ou_sans_grille_n_est_pas_candidat(self):
        self.preparer(fichiers_ecartes=False)
        self.connection.execute("UPDATE scores SET criteria = NULL, complete = 0 WHERE file = 'a3.md'")
        self.connection.commit()
        _, faux = self.rattraper()
        self.assertEqual(faux.appels["en"], 5)
        self.assertNotIn("https://s.test/a3.md", [l["url"] for l in self.lignes_ombre()])


class Echecs(Rattrapage):
    def test_un_echec_est_compte_et_n_arrete_pas_le_passage(self):
        self.preparer()

        def modele(url, json=None, timeout=None):
            if "a3.md" in json["messages"][1]["content"] and json["messages"][0]["content"].startswith("You evaluate"):
                raise httpx.ConnectError("réseau coupé")
            return faux(url, json=json, timeout=timeout)
        faux = ombre.FauxModele()
        sortie = self.lancer_avec(modele)
        self.assertIn("5 notés, 1 échec(s)", sortie)
        self.assertEqual(len(self.lignes_ombre()), 5)
        self.assertNotIn("https://s.test/a3.md", [l["url"] for l in self.lignes_ombre()])
        # la reprise ne renote que l'échec
        _, reprise = self.rattraper()
        self.assertEqual(reprise.appels["en"], 1)

    def lancer_avec(self, modele):
        with mock.patch.object(ombre.httpx, "post", modele):
            return self.lancer(tri.cmd_shadow_backfill, limit=0)

    def test_un_fichier_introuvable_est_saute_et_compte(self):
        self.preparer(fichiers_ecartes=False)
        (self.articles / "a2.md").unlink()
        sortie, faux = self.rattraper()
        self.assertEqual(faux.appels["en"], 5)
        self.assertIn("5 notés, 0 échec(s), 1 sauté(s)", sortie)
        self.assertIn("fichier introuvable", sortie)


class Ordre(Rattrapage):
    def avis(self, **par_fichier):
        tri.CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tri.CALIBRATION_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
            ecrivain = csv.writer(handle, delimiter=";")
            ecrivain.writerow(["fichier", "titre", "avis"])
            for fichier, avis in par_fichier.items():
                ecrivain.writerow([fichier, "t", avis])

    def test_les_articles_avec_avis_passent_d_abord(self):
        self.preparer(fichiers_ecartes=False)
        self.avis(**{"a5.md": "g", "a2.md": "e", "a6.md": ""})     # un avis vide ne compte pas
        lignes = tri.shadow_backfill_candidates(self.connection, "en", tri.prompts_hash(self.module_en))
        self.assertEqual([r["file"] for r in lignes], ["a2.md", "a5.md", "a1.md", "a3.md", "a4.md", "a6.md"])

    def test_sans_fichier_de_calibration_l_ordre_des_fichiers(self):
        self.preparer(fichiers_ecartes=False)
        lignes = tri.shadow_backfill_candidates(self.connection, "en", tri.prompts_hash(self.module_en))
        self.assertEqual([r["file"] for r in lignes], ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md"])

    def test_la_progression_suit_cet_ordre(self):
        self.preparer(fichiers_ecartes=False)
        self.avis(**{"a4.md": "g"})
        sortie, _ = self.rattraper(limit=2)
        lignes = [l for l in sortie.splitlines() if l.startswith("[")]
        self.assertTrue(lignes[0].startswith("[1/2] Titre a4.md"))
        self.assertTrue(lignes[1].startswith("[2/2] Titre a1.md"))


class Limite(Rattrapage):
    def test_limit_est_respecte_et_la_suite_reprend(self):
        self.preparer()
        _, faux = self.rattraper(limit=2)
        self.assertEqual(faux.appels["en"], 2)
        self.assertEqual(len(self.lignes_ombre()), 2)
        _, suite = self.rattraper()
        self.assertEqual(suite.appels["en"], 4)


class Refus(Rattrapage):
    def test_ombre_desactivee(self):
        self.preparer()
        self.reglages(ombre=False)
        faux = ombre.FauxModele()
        with mock.patch.object(ombre.httpx, "post", faux), self.assertRaises(SystemExit) as erreur:
            self.lancer(tri.cmd_shadow_backfill, limit=0)
        self.assertIn("enabled: true", str(erreur.exception))
        self.assertEqual(faux.appels, {"fr": 0, "en": 0})
        self.assertEqual(self.lignes_ombre(), [])

    def test_prompts_inutilisables(self):
        self.preparer()
        with mock.patch.object(tri, "load_shadow_prompts", side_effect=ValueError("SYSTEM_PROMPT manque")), \
                self.assertRaises(SystemExit) as erreur:
            self.lancer(tri.cmd_shadow_backfill, limit=0)
        self.assertIn("inutilisables", str(erreur.exception))
        self.assertIn("SYSTEM_PROMPT manque", str(erreur.exception))

    def test_ollama_ne_repond_pas(self):
        self.preparer()
        self.ollama.return_value = False
        faux = ombre.FauxModele()
        with mock.patch.object(ombre.httpx, "post", faux), self.assertRaises(SystemExit) as erreur:
            self.lancer(tri.cmd_shadow_backfill, limit=0)
        self.assertIn("Ollama", str(erreur.exception))
        self.assertEqual(faux.appels, {"fr": 0, "en": 0})

    def test_la_commande_est_declaree(self):
        with mock.patch.object(tri, "cmd_shadow_backfill") as commande, \
                mock.patch.object(tri.sys, "argv", ["watch_triage.py", "shadow-backfill", "--limit", "7"]):
            tri.main()
        self.assertEqual(commande.call_args.args[0].limit, 7)


class MessageThresholds(Rattrapage):
    def test_le_message_cite_save_et_non_enregistrer(self):
        self.reglages(ombre=False)
        tri.CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        champs = ["fichier", "titre", "substance", "compilation", "dans_themes", "promotionnel", "avis"]
        with tri.CALIBRATION_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
            ecrivain = csv.writer(handle, delimiter=";")
            ecrivain.writerow(champs)
            for i in range(12):
                ecrivain.writerow([f"x{i}.md", f"Titre {i}", i % 6, "", "oui", "", "g" if i % 2 else "e"])
        sortie = self.lancer(tri.cmd_thresholds, save=False)
        self.assertIn("thresholds --save", sortie)
        self.assertNotIn("--enregistrer", sortie)


if __name__ == "__main__":
    unittest.main()
