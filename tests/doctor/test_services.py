"""Contrôles db, ollama, models et disk (tâche 3.2) : sonde TCP seulement, adresses locales seulement, modèles des constantes du dépôt."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import Labo, modeles_du_depot  # noqa: E402


class BaseDeDonnees(Labo):
    def test_port_ouvert_et_veille_saine(self):
        niveau, _, _ = self.niveau("db")
        self.assertEqual(niveau, "ok")

    def test_port_ferme(self):
        self.fermer_base()
        niveau, entree, p = self.niveau("db")
        self.assertEqual(niveau, "problem")
        self.assertEqual(entree["reason"]["key"], "port_closed")
        self.assertEqual(p.returncode, 1)
        self.assertEqual([a for a in self.appels() if a.startswith(("INTERDIT", "psql", "docker"))], [])

    def test_tables_absentes_dans_la_veille_du_jour(self):
        self.vider_journal_veille()
        self.ecrire_journal_veille("2026-10-14", "07:10", "tables")
        niveau, entree, _ = self.niveau("db")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "watch_tables_missing"))

    def test_base_injoignable_dans_la_veille_du_jour(self):
        self.vider_journal_veille()
        self.ecrire_journal_veille("2026-10-14", "07:10", "base")
        niveau, entree, _ = self.niveau("db")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "watch_unreachable"))

    def test_base_injoignable_hier_n_est_pas_un_probleme_du_jour(self):
        self.vider_journal_veille()
        self.ecrire_journal_veille("2026-10-13", "07:10", "base")
        self.ecrire_journal_veille("2026-10-14", "07:10", "ok")
        self.assertEqual(self.niveau("db")[0], "ok")

    def test_hote_non_local_ignore_et_aucun_contact(self):
        niveau, entree, _ = self.niveau("db", env={"PMZILLA_LAB_DB_URL": "postgresql://postgres@db.example.org:5432/pmzilla"})
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "not_local"))

    def test_url_locale_lue_comme_db_py(self):
        url = f"postgresql://postgres@localhost:{self.port_base}/pmzilla"
        self.assertEqual(self.niveau("db", env={"PMZILLA_LAB_DB_URL": url})[0], "ok")

    def test_aucun_client_de_base_ni_trousseau(self):
        self.fermer_base()
        self.lancer()
        self.assertEqual([a for a in self.appels() if a.split(" ")[0] in ("INTERDIT", "security", "psql", "docker")], [])


class Ollama(Labo):
    def test_ollama_repond_et_modeles_presents(self):
        self.assertEqual(self.niveau("ollama")[0], "ok")
        self.assertEqual(self.niveau("models")[0], "ok")

    def test_ollama_arrete_modeles_ignores(self):
        self.ollama.arreter()
        niveau, entree, p = self.niveau("ollama")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "down"))
        niveau, entree, _ = self.niveau("models")
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "depends"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("models : ignoré : dépend de ollama", self.lancer().stdout)
        self.assertNotIn("INTERDIT", "\n".join(self.appels()))

    def test_modele_de_tri_absent_aucun_tirage(self):
        modeles = modeles_du_depot()
        self.assertEqual(len(modeles), 2, "le dépôt doit nommer le modèle de plongement et celui de la veille")
        self.ollama.modeles = [modeles[0]]
        niveau, entree, _ = self.niveau("models")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "missing"))
        sortie = self.lancer("--language", "en").stdout
        self.assertIn("watch triage", sortie)
        self.assertNotIn(modeles[1], sortie)
        self.assertEqual([m for m, chemin in self.ollama.requetes if m != "GET" or chemin != "/api/tags"], [])

    def test_etiquette_latest_acceptee(self):
        self.ollama.modeles = [m if ":" in m else f"{m}:latest" for m in modeles_du_depot()]
        self.assertEqual(self.niveau("models")[0], "ok")

    def test_adresse_non_locale_ignoree(self):
        niveau, entree, _ = self.niveau("ollama", env={"DOCTOR_OLLAMA_URL": "http://ollama.example.org:11434"})
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "not_local"))


class Disque(Labo):
    def test_assez_de_place(self):
        self.assertEqual(self.niveau("disk")[0], "ok")

    def test_entre_les_deux_seuils_avertissement(self):
        niveau, entree, p = self.niveau("disk", env={"DOCTOR_DISK_FREE_GB": "12"})
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("warning", "low", {"free_gb": 12}))
        self.assertNotEqual(p.returncode, 2)

    def test_sous_le_second_seuil_probleme(self):
        niveau, entree, p = self.niveau("disk", env={"DOCTOR_DISK_FREE_GB": "3"})
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "critical"))
        self.assertEqual(p.returncode, 1)

    def test_seuils_reglables(self):
        self.assertEqual(self.niveau("disk", env={"DOCTOR_DISK_FREE_GB": "12", "DOCTOR_DISK_WARN_GB": "10"})[0], "ok")

    def test_mesure_reelle_sans_simulation(self):
        env = self.environnement()
        env.pop("DOCTOR_DISK_FREE_GB")
        import subprocess
        from aide_doctor import DOCTOR
        p = subprocess.run([sys.executable, str(DOCTOR), "--json"], capture_output=True, text=True, env=env, cwd=str(self.base))
        self.assertIn(p.returncode, (0, 1))
        self.assertIn('"id": "disk"', p.stdout)


if __name__ == "__main__":
    unittest.main()
