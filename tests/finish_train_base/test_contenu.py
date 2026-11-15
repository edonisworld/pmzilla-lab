"""
Tâche 2.7 (change finish-train-v1) : le contrôle du contenu de tout le train (conception D8 et D9, codes 65 et 68). Chaque commit de la plage
origin/main..<train> est lu : un secret, un nom ou un identifiant ajouté puis retiré dans la branche refuse le train. Listes fictives. Une sentinelle
(la valeur trouvée) n'apparaît ni sur la sortie standard, ni sur la sortie d'erreur, ni dans le journal.
"""
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, CORPS, IDENTIFIANT, NOM_FICTIF, jeton  # noqa: E402


class Trouvailles(AvecTrain):
    def rien_lance(self):
        """Ni la passe Mac (runner) ni le passage du conteneur (faux ci de la convention commune : journal ci-appels) n'ont été lancés."""
        self.assertEqual(self.t.appels("runner"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "le passage du conteneur a été lancé")

    def refuse(self, fichiers, sentinelle, secrets, noms, identifiants):
        self.t.branche("feat/x", {"docs/a.txt": fichiers}, suite=[{"docs/a.txt": None}])
        avant = self.t.instantane()
        r = self.t.lance("feat/x", entree="o\n")
        self.code(r, 65, f"contenu refusé : le contrôle des noms et des secrets a trouvé {secrets} secret(s), {noms} nom(s), {identifiants} identifiant(s) dans le train ; rien n'est fusionné")
        self.contient(r, "range_scan : ")
        self.rien_ne_change(avant)
        self.rien_lance()   # rien n'est lancé après un refus du contenu : ni le conteneur ni la passe Mac
        self.assertNotIn(sentinelle, r.sortie)
        self.assertNotIn(sentinelle, r.erreur)
        self.assertNotIn(sentinelle, self.t.log())

    def test_un_secret_ajoute_puis_retire(self):
        self.refuse(f"intro\ntoken = {jeton()}\n", CORPS, 1, 0, 0)

    def test_un_nom_ajoute_puis_retire(self):
        self.refuse(f"un texte avec {NOM_FICTIF} dedans\n", NOM_FICTIF, 0, 1, 0)

    def test_un_identifiant_ajoute_puis_retire(self):
        self.refuse(f"un texte avec {IDENTIFIANT} dedans\n", IDENTIFIANT, 0, 0, 1)

    def test_un_nom_dans_un_nom_de_branche(self):
        self.t.branche("feat/Vexillonia-x")
        avant = self.t.instantane()
        r = self.t.lance("feat/Vexillonia-x", entree="o\n")
        self.code(r, 65, "contenu refusé : le contrôle des noms et des secrets a trouvé ")
        self.rien_ne_change(avant)

    def test_une_branche_propre_passe_le_controle(self):
        self.t.branche("feat/x", {"docs/a.txt": "du texte sans rien de sensible\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)


class ControleImpossible(AvecTrain):
    def test_liste_des_noms_absente_sort_2_du_scan(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"PMZILLA_LAB_SENSITIVE_NAMES": str(self.t.dossier / "absente.txt")})
        self.code(r, 68, "contrôle de contenu impossible (range_scan, code 2) ; rien n'est fusionné")
        self.rien_ne_change(avant)

    def test_depot_superficiel_sort_3_du_scan(self):
        self.t.branche("feat/x")
        racine = self.t.git("rev-list", "--max-parents=0", "main")
        (self.t.commun() / "shallow").write_text(racine + "\n", encoding="utf-8")
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 68, "contrôle de contenu impossible (range_scan, code 3) ; rien n'est fusionné")
        self.rien_ne_change(avant)

    def test_controle_14_du_train_impossible_a_calculer(self):
        self.t.controle_14_casse()
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 68, "contrôle 14 du train impossible (finish_checks, code 4) ; rien n'est fusionné")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "le passage du conteneur a été lancé")


TRACE = ("Traceback (most recent call last):\n  File \"tools/range_scan.py\", line 91, in <module>\n"
         "TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'\n")


def faux_range_scan(code_texte: int, code_json: int, trace: bool = False, json_texte: str = "") -> str:
    """Un range_scan factice : les codes des deux lectures, une trace éventuelle (sans JSON) ou un JSON donné, et une ligne de la forme du vrai."""
    return (
        "import sys\n"
        "en_json = '--json' in sys.argv\n"
        f"if {trace!r}:\n"
        f"    sys.stderr.write({TRACE!r})\n"
        "    sys.exit(1)\n"
        "if en_json:\n"
        f"    print({json_texte!r})\n"
        f"    sys.exit({code_json})\n"
        "print('range_scan : lecture factice')\n"
        f"sys.exit({code_texte})\n"
    )


class SortieIncoherente(AvecTrain):
    """Faux 65 du train automatique (design D5, D6) : le code 65 demande deux lectures concordantes ; sinon 68, sans trace dans le journal."""

    PHRASE_SANS_TROUVAILLE = "contrôle de contenu impossible (range_scan, sortie incohérente : code 1 sans trouvaille) ; rien n'est fusionné"

    def lance_avec(self, source: str):
        self.t.casser_le_module("range_scan.py", source)
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", entree="o\n")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "le passage du conteneur a été lancé")
        return r

    def test_plantage_a_l_import_donne_68_et_non_65(self):
        r = self.lance_avec(faux_range_scan(1, 1, trace=True))
        self.code(r, 68, self.PHRASE_SANS_TROUVAILLE)
        self.absent(r, "contenu refusé", "Traceback", "TypeError")

    def test_code_1_avec_un_json_sans_trouvaille_donne_68(self):
        r = self.lance_avec(faux_range_scan(1, 1, json_texte='{"format": 1, "findings": [], "exit": 1}'))
        self.code(r, 68, self.PHRASE_SANS_TROUVAILLE)
        self.absent(r, "contenu refusé")

    def test_code_1_avec_un_json_de_code_0_donne_68(self):
        r = self.lance_avec(faux_range_scan(1, 1, json_texte='{"format": 1, "findings": [{"kind": "secret"}], "exit": 0}'))
        self.code(r, 68, self.PHRASE_SANS_TROUVAILLE)

    def test_code_1_avec_un_json_d_un_autre_format_donne_68(self):
        r = self.lance_avec(faux_range_scan(1, 1, json_texte='{"format": 2, "findings": [{"kind": "secret"}], "exit": 1}'))
        self.code(r, 68, self.PHRASE_SANS_TROUVAILLE)

    def test_code_1_avec_une_trouvaille_d_un_genre_inconnu_donne_68(self):
        r = self.lance_avec(faux_range_scan(1, 1, json_texte='{"format": 1, "findings": [{"kind": "autre"}], "exit": 1}'))
        self.code(r, 68, self.PHRASE_SANS_TROUVAILLE)

    def test_un_genre_encoding_suffit_pour_le_65(self):
        r = self.lance_avec(faux_range_scan(1, 1, json_texte='{"format": 1, "findings": [{"kind": "encoding"}], "exit": 1}'))
        self.code(r, 65, "contenu refusé : le contrôle des noms et des secrets a trouvé 0 secret(s), 0 nom(s), 0 identifiant(s) dans le train ; rien n'est fusionné")

    def test_codes_discordants_texte_1_json_0(self):
        r = self.lance_avec(faux_range_scan(1, 0, json_texte='{"format": 1, "findings": [], "exit": 0}'))
        self.code(r, 68, "contrôle de contenu impossible (range_scan, sortie incohérente : codes 1 et 0) ; rien n'est fusionné")
        self.absent(r, "contenu refusé")

    def test_codes_discordants_texte_0_json_1(self):
        r = self.lance_avec(faux_range_scan(0, 1, json_texte='{"format": 1, "findings": [{"kind": "secret"}], "exit": 1}'))
        self.code(r, 68, "contrôle de contenu impossible (range_scan, sortie incohérente : codes 0 et 1) ; rien n'est fusionné")
        self.absent(r, "contenu refusé")

    def test_le_journal_ne_garde_aucune_ligne_de_la_trace(self):
        r = self.lance_avec(faux_range_scan(1, 1, trace=True))
        journal = self.t.log()
        self.assertIn("finish_train : sortie inattendue de range_scan", journal)
        self.assertEqual(r.texte.count("finish_train : sortie inattendue de range_scan"), 1)
        for morceau in ("Traceback", "TypeError", "tools/range_scan.py"):
            self.assertNotIn(morceau, journal)

    def test_les_lignes_range_scan_restent_montrees_et_journalisees(self):
        r = self.lance_avec(faux_range_scan(1, 1, json_texte='{"format": 1, "findings": [], "exit": 1}'))
        self.contient(r, "range_scan : lecture factice")
        self.assertIn("range_scan : lecture factice", self.t.log())
        self.assertNotIn("sortie inattendue", r.texte)


class Resume(AvecTrain):
    def test_le_nombre_de_fichiers_non_examines_est_dans_le_resume(self):
        self.t.branche("feat/x", {"bin/x.dat": b"\x00\x01\x02binaire"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "fichiers non examinés par le contrôle des noms : 1")

    def test_zero_fichier_non_examine(self):
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x")
        self.contient(r, "fichiers non examinés par le contrôle des noms : 0")


if __name__ == "__main__":
    unittest.main()
