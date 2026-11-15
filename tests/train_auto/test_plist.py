"""
Tâche 2.8 (change autonomous-trains-observe) : le modèle launchd imprimé par `train_auto.py plist` (conception D10). Le modèle est imprimé, jamais
installé ni chargé par l'outil ; l'horaire n'existe qu'une fois, dans les constantes de l'outil.
"""
import plistlib
import sys
import unittest

from aide_auto import AvecAuto, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402


class Modele(AvecAuto):
    def modele(self):
        r = self.auto("plist")
        self.assertEqual(r.code, 0, r.texte)
        return plistlib.loads(r.sortie.encode("utf-8")), r.sortie

    def test_le_modele_est_une_liste_de_proprietes_valide_avec_les_heures_de_l_outil(self):
        p, _ = self.modele()
        self.assertEqual(p["Label"], "com.pmzilla.train-auto")
        intervalles = p["StartCalendarInterval"]
        attendu = [{"Hour": int(debut.split(":")[0]), "Minute": int(debut.split(":")[1])} for debut, _tard in train_auto.WINDOWS]
        self.assertEqual(intervalles, attendu)
        self.assertEqual(len(intervalles), len(train_auto.WINDOWS))

    def test_le_modele_porte_quatorze_passages_horaires_de_8_h_a_21_h(self):
        """D13 (tâche 9.6) : test statique du modèle, indépendant de la constante, qui épingle l'horaire de la conception (R-20261101-83)."""
        p, _ = self.modele()
        self.assertEqual(p["StartCalendarInterval"], [{"Hour": h, "Minute": 0} for h in range(8, 22)])
        self.assertEqual(len(p["StartCalendarInterval"]), 14)

    def test_ni_runatload_ni_keepalive_ni_startinterval(self):
        p, texte = self.modele()
        for cle in ("RunAtLoad", "KeepAlive", "StartInterval", "StartOnMount", "WatchPaths", "QueueDirectories"):
            self.assertNotIn(cle, p)
            self.assertNotIn(f"<key>{cle}</key>", texte)

    def test_la_copie_du_dossier_d_execution_est_lancee_par_l_interpreteur_de_la_generation_sous_i(self):
        p, _ = self.modele()   # R-20261110-36 : sys.executable de la génération, plus /usr/bin/python3 ; -I reste exigé
        self.assertEqual(p["ProgramArguments"], [sys.executable, "-I", f"{self.t.run}/tools/train_auto.py", "pass"])
        self.assertEqual(p["WorkingDirectory"], str(self.t.run))

    def test_le_journal_de_la_tache(self):
        p, _ = self.modele()
        self.assertTrue(p["StandardOutPath"].endswith("/Library/Logs/pmzilla-train-auto.log"))
        self.assertEqual(p["StandardOutPath"], p["StandardErrorPath"])

    def test_l_outil_n_installe_ni_ne_charge_rien(self):
        avant = sorted(str(f) for f in self.t.lab.rglob("*") if f.is_file())
        self.modele()
        self.assertEqual(sorted(str(f) for f in self.t.lab.rglob("*") if f.is_file()), avant)
        source = (RACINE / "tools" / "train_auto.py").read_text(encoding="utf-8")
        for mot in ("launchctl", "LaunchAgents"):
            self.assertNotIn(f'"{mot}', source)

    def test_aucun_autre_fichier_du_depot_ne_porte_l_horaire(self):
        heures = {debut for debut, _ in train_auto.WINDOWS} | {tard for _, tard in train_auto.WINDOWS}
        porteurs = []
        for dossier in ("tools", "docs", "openspec"):
            for f in (RACINE / dossier).rglob("*"):
                if not f.is_file() or f.suffix not in (".py", ".sh", ".plist", ".md", ".yaml", ".txt") or f.name in ("train_auto.py",):
                    continue
                if f.name == "doctor.py":
                    # D13 (tâche 9.6) : les passages deviennent horaires (08:00 à 21:25) ; le littéral "08:00" de tools/doctor.py est l'heure d'échéance de la veille
                    # (DOCTOR_WATCH_DUE), sans rapport avec l'horaire du passage. Exception signalée à l'auteur dans le commit (un test existant change : décision D13 citée).
                    continue
                if "changes/autonomous-trains-observe" in str(f) or "/archive/" in str(f):
                    continue   # le change qui décrit l'outil, et les archives, citent ses constantes sans les copier
                texte = f.read_text(encoding="utf-8", errors="ignore")
                if any(f'"{h}"' in texte for h in heures):
                    porteurs.append(str(f.relative_to(RACINE)))
        self.assertEqual(porteurs, [], "l'horaire est dans les constantes de tools/train_auto.py seulement")
        self.assertFalse((RACINE / "tools" / "com.pmzilla.train-auto.plist").exists())


if __name__ == "__main__":
    unittest.main()
