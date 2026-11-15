"""Contrôle train-auto-plist (faux 65 du train automatique, D11 ; R-20261110-14) : le modèle launchd installé du train automatique est lu, jamais chargé ni régénéré.
Les interpréteurs sont de faux scripts `python3` qui répondent 3.9 ou 3.14 ; le modèle attendu est celui de train_auto.plist_model. Aucun launchctl d'écriture."""
import json
import plistlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import DOCTOR, RACINE, Labo  # noqa: E402

import train_auto  # noqa: E402

COMMANDE = "python3 -I <dossier d'exécution>/tools/train_auto.py plist"


class ControleTrainAutoPlist(Labo):
    def faux_python(self, nom, sortie):
        dossier = self.base / nom
        dossier.mkdir()
        faux = dossier / "python3"
        faux.write_text(f'#!/bin/sh\necho "{sortie}"\n', encoding="utf-8")
        faux.chmod(0o755)
        return dossier

    def installer_modele(self, dossier_python=None, modifier=None):
        modele = train_auto.plist_model((dossier_python or self.base) / "python3", str(self.run), str(self.maison))
        if modifier:
            modifier(modele)
        (self.agents / f"{train_auto.LABEL}.plist").write_bytes(plistlib.dumps(modele))

    def ligne(self):
        p = self.lancer()
        lignes = [l for l in p.stdout.splitlines() if l.startswith("train-auto-plist : ")]
        self.assertEqual(len(lignes), 1, p.stdout)
        return lignes[0]

    def test_non_installe_est_ignore(self):
        niveau, _, p = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "skipped", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_modele_sans_chemin_est_un_probleme_avec_la_cle_et_la_commande(self):
        bon = self.faux_python("py314", "Python 3.14.0")
        self.installer_modele(bon, modifier=lambda m: m.pop("EnvironmentVariables"))
        niveau, _, p = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "problem")
        self.assertEqual(p.returncode, 1)
        ligne = self.ligne()
        self.assertIn("EnvironmentVariables", ligne)
        self.assertIn(COMMANDE, ligne)
        self.assertIn("3.10", ligne)
        self.assertIn("recharge", ligne)
        self.assertEqual([a for a in self.appels() if a.startswith("launchctl") and not a.startswith("launchctl print")], [])

    def test_python_du_modele_trop_ancien(self):
        self.installer_modele(self.faux_python("py39", "Python 3.9.6"))
        niveau, _, _ = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "problem")
        ligne = self.ligne()
        self.assertIn("plus ancien que 3.10", ligne)
        self.assertIn(COMMANDE, ligne)

    def test_python_du_modele_absent(self):
        vide = self.base / "vide"
        vide.mkdir()
        self.installer_modele(vide)
        niveau, _, _ = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "problem")
        ligne = self.ligne()
        self.assertIn("pas de python3", ligne)
        self.assertIn(COMMANDE, ligne)

    def test_modele_different_ailleurs(self):
        self.installer_modele(self.faux_python("py314", "Python 3.14.0"), modifier=lambda m: m.update(WorkingDirectory="/ailleurs"))
        niveau, _, _ = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "problem")
        self.assertIn("WorkingDirectory", self.ligne())

    def test_interpreteur_de_programarguments_different_du_python3_du_path(self):
        """R-20261110-34 : un ProgramArguments qui garde un autre interpréteur que le python3 du premier dossier du PATH est un problème, avec la commande de régénération."""
        bon = self.faux_python("py314", "Python 3.14.0")
        self.installer_modele(bon, modifier=lambda m: m["ProgramArguments"].__setitem__(0, "/usr/bin/python3"))
        niveau, _, p = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "problem", p.stdout)
        ligne = self.ligne()
        self.assertIn("ProgramArguments", ligne)
        self.assertIn(COMMANDE, ligne)

    def test_modele_conforme_avec_un_python_3_14(self):
        self.installer_modele(self.faux_python("py314", "Python 3.14.0"))
        niveau, _, p = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "ok", p.stdout)

    def test_modele_illisible(self):
        (self.agents / f"{train_auto.LABEL}.plist").write_bytes(b"pas une liste de proprietes")
        niveau, _, _ = self.niveau("train-auto-plist")
        self.assertEqual(niveau, "problem")
        self.assertIn(COMMANDE, self.ligne())

    def test_un_probleme_entre_dans_le_compte_du_doctor(self):
        self.installer_modele(self.faux_python("py39", "Python 3.9.6"))
        p, donnees = self.resultat_json()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(donnees["counts"]["problem"], 1)

    def test_le_fichier_d_etat_ne_porte_aucun_chemin(self):
        self.installer_modele(self.faux_python("py39", "Python 3.9.6"))
        self.lancer("--record")
        texte = (self.donnees / "doctor-etat.json").read_text(encoding="utf-8")
        etat = json.loads(texte)
        entree = [c for c in etat["checks"] if c["id"] == "train-auto-plist"][0]
        self.assertEqual((entree["level"], entree["reason"]["key"]), ("problem", "python_old"))
        self.assertNotIn(str(self.base), texte)
        self.assertNotIn(str(self.maison), texte)
        self.assertNotIn("/Users/", texte)

    def test_le_doctor_n_ecrit_ni_ne_charge_rien(self):
        self.installer_modele(self.faux_python("py39", "Python 3.9.6"))
        avant = self.fichiers()
        self.lancer()
        self.assertEqual(self.fichiers(), avant)


class ComparaisonDeVersions(unittest.TestCase):
    """La règle « local seulement, sans versions » : la comparaison du python3 du modèle avec 3.10 est la troisième permise, citant R-20261110-14 ;
    elle vit dans train_auto.installed_plist_check(), et le doctor ne fait que la mettre en forme."""

    def test_le_doctor_n_a_aucune_comparaison_de_version_propre(self):
        source = DOCTOR.read_text(encoding="utf-8")
        self.assertNotIn("version_info", source)
        self.assertNotIn("(3, 10)", source)
        self.assertIn("R-20261110-14", source)

    def test_la_comparaison_permise_cite_la_decision(self):
        self.assertIn("R-20261110-14", train_auto.__doc__ + (train_auto.installed_plist_check.__doc__ or ""))
        self.assertEqual(train_auto.PYTHON_MINIMUM, (3, 10))

    def test_la_regle_ne_permet_que_trois_comparaisons(self):
        """Le texte de la règle (tooling-doctor) et l'en-tête du doctor nomment les trois comparaisons : Node, Claude Code, et le python3 du modèle."""
        entete = DOCTOR.read_text(encoding="utf-8").split('"""')[1]
        for morceau in ("mothra/.node-version", "Claude Code", "python3", "3.10", "R-20261110-14"):
            self.assertIn(morceau, entete)


if __name__ == "__main__":
    unittest.main()
