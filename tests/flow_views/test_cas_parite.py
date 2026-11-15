"""
Joueur Python des cas de parité (contrats/cas-parite.json, mothra-slices D4, tâches 11.5 (décision F14) et 15.2).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Le même fichier de cas synthétiques est joué par la suite npm du paquet de contrat et par ce joueur, contre les fonctions de seuil et de liste
fermée du lecteur (tools/flow_views.py). Le joueur s'arrête au premier cas différent et le nomme : « cas de parité différent : <nom> ».

Joués ici :
  * les cas de seuil à résultat (« expected.threshold ») : seuil_effectif(configure, option), le contrat et le réglage relevant ensemble le
    seuil configuré (max(5, seuil du contrat, réglage, option), mothra-slices D2) ;
  * les cas de vue : une vue est acceptée quand elle est dans la liste fermée du lecteur (VUES) et dans le contrat (contrats/vues.json),
    comparaison exacte (casse, espaces, nom qualifié, texte d'injection).
Pas encore joués, attendus d'une tranche ultérieure (le lecteur ne lit pas encore le contrat) :
  * les cas de seuil à refus (CONTRACT_FLOOR, CONTRACT_INVALID) : le lecteur n'a pas de fonction de refus du contrat ;
  * les cas de cellule : la cellule du lecteur (« value / masked / threshold ») n'est pas encore alignée sur la cellule du contrat
    (« state / value / threshold », mothra-slices D3).
Le test des cas non joués compare leur liste au fichier : un nouveau genre de cas ne passe pas sous silence.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

CAS = RACINE / "contrats" / "cas-parite.json"
CONTRAT = RACINE / "contrats" / "vues.json"


def charger_cas() -> dict:
    return json.loads(CAS.read_text(encoding="utf-8"))


def vues_du_contrat() -> set:
    return {v["name"] for v in json.loads(CONTRAT.read_text(encoding="utf-8"))["views"]}


def seuil_du_lecteur(cas: dict) -> int:
    """Seuil effectif du lecteur pour un cas de seuil sans refus : le contrat et le réglage relèvent ensemble le seuil configuré."""
    configure = max(cas["contractThreshold"] or 0, cas["setting"] or 0)
    return fv.seuil_effectif(configure, cas["option"])


def vue_acceptee_par_le_lecteur(vue: str, contrat: set) -> bool:
    return vue in fv.VUES and vue in contrat


def cas_non_joues(cas: dict) -> list:
    """Noms des cas que ce joueur ne joue pas encore : les cas de cellule et les cas de seuil à refus."""
    return [c["name"] for c in cas["cells"]] + [c["name"] for c in cas["thresholds"] if "refusal" in c["expected"]]


def jouer(cas: dict, contrat: set):
    """Joue les cas joués ; retourne le nom du premier cas différent, ou None. Une exception levée par un cas le rend différent."""
    for c in cas["views"]:
        try:
            if vue_acceptee_par_le_lecteur(c["view"], contrat) != c["accepted"]:
                return c["name"]
        except Exception:
            return c["name"]
    for c in cas["thresholds"]:
        if "refusal" in c["expected"]:
            continue
        try:
            if {"threshold": seuil_du_lecteur(c)} != c["expected"]:
                return c["name"]
        except Exception:
            return c["name"]
    return None


def verifier(cas: dict, contrat: set):
    nom = jouer(cas, contrat)
    if nom is not None:
        raise AssertionError(f"cas de parité différent : {nom}")


class CasDeParite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cas = charger_cas()
        cls.contrat = vues_du_contrat()

    def copie(self) -> dict:
        return copy.deepcopy(self.cas)

    def test_le_fichier_porte_les_trois_genres_de_cas_chacun_avec_un_nom_unique(self):
        for genre in ("cells", "views", "thresholds"):
            self.assertTrue(self.cas[genre], genre)
        noms = [c["name"] for genre in ("cells", "views", "thresholds") for c in self.cas[genre]]
        self.assertEqual(len(set(noms)), len(noms))

    def test_chaque_cas_joue_donne_son_resultat_attendu(self):
        verifier(self.cas, self.contrat)

    def test_chaque_vue_du_contrat_est_dans_la_liste_fermee_du_lecteur(self):
        self.assertEqual(sorted(self.contrat - set(fv.VUES)), [])
        self.assertTrue(set(fv.VUES_TRANCHE_1) <= self.contrat)

    def test_les_cas_de_vue_couvrent_table_qualifie_casse_injection_et_vide(self):
        vues = {c["view"] for c in self.cas["views"]}
        for attendu in ("issues", "flow.v_team_status", "V_TEAM_STATUS", "v_team_status; DROP TABLE flow.issues", ""):
            self.assertIn(attendu, vues)

    def test_les_cas_non_joues_sont_les_cellules_et_les_refus_de_seuil(self):
        refus = [c["name"] for c in self.cas["thresholds"] if "refusal" in c["expected"]]
        self.assertTrue(refus)
        self.assertEqual(cas_non_joues(self.cas), [c["name"] for c in self.cas["cells"]] + refus)
        for c in self.cas["thresholds"]:
            self.assertTrue("threshold" in c["expected"] or "refusal" in c["expected"], c["name"])

    def test_la_liste_des_cas_non_joues_est_figee_par_leurs_noms(self):
        """Un cas de cellule ou de refus ajouté, retiré ou renommé dans le fichier change cette liste : il faut alors décider s'il se joue."""
        self.assertEqual(cas_non_joues(self.cas), [
            "cell-count-above-threshold", "cell-count-at-threshold", "cell-count-just-under-threshold", "cell-count-under-threshold",
            "cell-count-zero", "cell-null-from-the-database", "cell-raised-threshold-masks-eight", "cell-raised-threshold-shows-ten",
            "cell-null-with-raised-threshold", "cell-threshold-under-floor-is-raised", "plain-column-team", "plain-column-status",
            "plain-column-small-text-is-not-a-count",
            "threshold-contract-three-is-refused", "threshold-contract-four-is-refused", "threshold-contract-zero-is-refused",
            "threshold-contract-negative-is-invalid", "threshold-contract-fraction-is-invalid",
        ])

    def test_le_fichier_n_a_que_les_trois_genres_de_cas(self):
        self.assertEqual(set(self.cas), {"cells", "views", "thresholds"})

    @unittest.skip("tranche ultérieure : la cellule du lecteur n'est pas encore alignée sur la cellule du contrat (mothra-slices D3)")
    def test_les_cas_de_cellule(self):
        pass


class JoueurDeParite(unittest.TestCase):
    """Le joueur s'arrête au premier cas différent et le nomme : il est éprouvé sur des fichiers de cas altérés."""

    @classmethod
    def setUpClass(cls):
        cls.cas = charger_cas()
        cls.contrat = vues_du_contrat()

    def copie(self) -> dict:
        return copy.deepcopy(self.cas)

    def test_un_cas_de_seuil_different_est_nomme(self):
        cas = self.copie()
        cas["thresholds"][8]["expected"] = {"threshold": 3}
        with self.assertRaises(AssertionError) as e:
            verifier(cas, self.contrat)
        self.assertEqual(str(e.exception), f"cas de parité différent : {cas['thresholds'][8]['name']}")

    def test_un_cas_de_vue_different_est_nomme(self):
        cas = self.copie()
        cas["views"][1]["accepted"] = True
        self.assertEqual(jouer(cas, self.contrat), cas["views"][1]["name"])

    def test_le_premier_cas_different_est_nomme_pas_le_suivant(self):
        cas = self.copie()
        cas["views"][2]["accepted"] = True
        cas["views"][3]["accepted"] = True
        cas["thresholds"][0]["expected"] = {"threshold": 9}
        self.assertEqual(jouer(cas, self.contrat), cas["views"][2]["name"])

    def test_un_cas_de_seuil_different_est_nomme_apres_les_cas_de_vue_corrects(self):
        cas = self.copie()
        cas["thresholds"][2]["expected"] = {"threshold": 9}
        self.assertEqual(jouer(cas, self.contrat), cas["thresholds"][2]["name"])

    def test_une_vue_hors_du_contrat_est_refusee_meme_dans_la_liste_du_lecteur(self):
        self.assertIn("v_teams", fv.VUES)
        self.assertFalse(vue_acceptee_par_le_lecteur("v_teams", self.contrat))

    def test_une_vue_du_contrat_hors_de_la_liste_du_lecteur_est_refusee(self):
        self.assertFalse(vue_acceptee_par_le_lecteur("v_inconnue", self.contrat | {"v_inconnue"}))

    def test_un_cas_qui_leve_une_exception_est_nomme(self):
        cas = self.copie()
        cas["thresholds"][1]["option"] = "abc"
        self.assertEqual(jouer(cas, self.contrat), cas["thresholds"][1]["name"])

    def test_un_fichier_sans_difference_ne_nomme_rien(self):
        self.assertIsNone(jouer(self.copie(), self.contrat))


if __name__ == "__main__":
    unittest.main()
