"""Dérivation des champs de livraison et des références de version à l'import (change jira-delivery-fields ; spec jira-flow-delivery-fields
« Delivery fields derived at import », « Version without ticket at import » ; design D3, D5, D12). Partie sans base.

    bash tests/run_all.sh flow_import

Une fausse connexion (test_reconstruction.FausseConnexion) répond aux lectures de flow_raw avec des lignes inventées et note les écritures.
"""
import contextlib
import datetime as dt
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_delivery  # noqa: E402
import flow_import  # noqa: E402
import flow_raw  # noqa: E402
from flow_import_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402
from test_derivation import FausseConnexionDerivation  # noqa: E402
from test_reconstruction import instantane, vivant  # noqa: E402

UTC = dt.timezone.utc
MAINTENANT = dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
LIVRAISON = {"sprints": [{"id": "31", "state": "closed", "start": "2026-09-01T08:00:00Z", "end": "2026-09-14T17:00:00Z", "complete": None},
                         {"id": "32", "state": "active", "start": "2026-09-15T08:00:00Z", "end": None, "complete": None}],
             "assets": {"target": ["101"], "resolution": ["102"]}, "single": {"isp": "5"}, "flags": {"customer_commitment": True},
             "rank": "4", "options": {"workflow_option": ["7"]}}          # R-20261102-51 : identifiants d'option seuls, jamais une valeur


def vivante(cle, livraison):
    """Les lignes vivantes qu'une dérivation de `livraison` aurait écrites, telles que les requêtes de lecture les rendent."""
    lignes = flow_delivery.lignes_de(cle, livraison)
    return {genre: sorted(lignes[genre], key=str) for genre in lignes}


def ecritures_de(connexion, debut):
    return [sql for sql, _ in connexion.ecritures if sql.startswith(debut)]


class ChampsDifferents(unittest.TestCase):
    def avec(self, livraison_du_snap, lignes_vivantes):
        snap = instantane("PROJ-1", delivery=livraison_du_snap)
        v = vivant("PROJ-1")
        v["livraison"] = {genre: set(lignes) for genre, lignes in lignes_vivantes.items()}
        return flow_raw.champs_differents(snap, v)

    def test_aucune_difference_quand_les_lignes_sont_celles_de_l_instantane(self):
        self.assertEqual(self.avec(LIVRAISON, vivante("PROJ-1", LIVRAISON)), [])

    def test_ticket_sans_livraison_et_sans_ligne(self):
        self.assertEqual(self.avec(None, vivante("PROJ-1", None)), [])

    def test_sprint_retire_dans_jira(self):
        reste = {**LIVRAISON, "sprints": LIVRAISON["sprints"][:1]}
        self.assertEqual(self.avec(reste, vivante("PROJ-1", LIVRAISON)), ["delivery"])

    def test_etat_de_sprint_change(self):
        change = {**LIVRAISON, "sprints": [{**LIVRAISON["sprints"][1], "state": "closed"}, LIVRAISON["sprints"][0]]}
        self.assertEqual(self.avec(change, vivante("PROJ-1", LIVRAISON)), ["delivery"])

    def test_livraison_retiree_efface_les_lignes(self):
        self.assertEqual(self.avec(None, vivante("PROJ-1", LIVRAISON)), ["delivery"])

    def test_sans_cle_livraison_dans_la_ligne_vivante_rien_n_est_compare(self):
        self.assertEqual(flow_raw.champs_differents(instantane("PROJ-1", delivery=LIVRAISON), vivant("PROJ-1")), [])


class Derivation(unittest.TestCase):
    def connexion(self, livraison_snap=LIVRAISON, livraison_vivante=None, **plus):
        c = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")])
        c.livraisons_instantanees = {} if livraison_snap is None else {"PROJ-1": livraison_snap}
        c.livraison_vivante = vivante("PROJ-1", livraison_vivante)
        for nom, valeur in plus.items():
            setattr(c, nom, valeur)
        return c

    def test_la_livraison_est_ecrite_pour_un_ticket_dont_les_lignes_different(self):
        c = self.connexion(livraison_vivante=None)
        # le ticket est déjà stocké et inchangé : seule la livraison diffère
        resultat = flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        self.assertEqual(resultat["modifies"], 1)
        self.assertEqual(len(ecritures_de(c, "INSERT INTO flow.sprints")), 2)
        self.assertEqual(len(ecritures_de(c, "INSERT INTO flow.issue_current_sprints")), 2)
        self.assertEqual(len(ecritures_de(c, "INSERT INTO flow.issue_current_asset_versions")), 2)
        self.assertEqual(len(ecritures_de(c, "INSERT INTO flow.issue_delivery_fields")), 1)
        self.assertEqual(len(ecritures_de(c, "INSERT INTO flow.issue_delivery_options")), 1)
        self.assertEqual(ecritures_de(c, "INSERT INTO flow.issue_defect_fields"), [])

    def test_sprint_retire_remplace_les_lignes_du_ticket(self):
        reste = {**LIVRAISON, "sprints": LIVRAISON["sprints"][:1]}
        c = self.connexion(livraison_snap=reste, livraison_vivante=LIVRAISON)
        flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        self.assertEqual(len(ecritures_de(c, "DELETE FROM flow.issue_current_sprints")), 1)
        self.assertEqual(len(ecritures_de(c, "INSERT INTO flow.issue_current_sprints")), 1)

    def test_le_dernier_instantane_sans_livraison_vide_les_lignes_du_ticket(self):
        # le dernier instantané du ticket a un delivery nul (il a perdu tous ses champs) : les lignes périmées partent
        c = self.connexion(livraison_snap=LIVRAISON, livraison_vivante=LIVRAISON)
        c.livraisons_instantanees = {"PROJ-1": None}
        flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        self.assertEqual(len(ecritures_de(c, "DELETE FROM flow.issue_current_sprints")), 1)
        self.assertEqual(len(ecritures_de(c, "DELETE FROM flow.issue_current_asset_versions")), 1)
        self.assertEqual(ecritures_de(c, "INSERT INTO flow.issue_current_sprints"), [])
        self.assertEqual(ecritures_de(c, "INSERT INTO flow.issue_current_asset_versions"), [])

    def test_la_requete_lit_le_dernier_instantane_meme_nul(self):
        self.assertNotIn("WHERE", flow_raw.SQL_DERNIERES_LIVRAISONS)

    def test_aucune_ecriture_quand_les_lignes_sont_celles_de_l_instantane(self):
        c = self.connexion(livraison_vivante=LIVRAISON)
        resultat = flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        self.assertEqual(resultat["modifies"], 0)
        self.assertEqual(ecritures_de(c, "INSERT INTO flow."), [])
        self.assertEqual(ecritures_de(c, "DELETE FROM flow."), [])

    def test_un_ticket_neuf_sans_livraison_n_ecrit_aucune_ligne_de_livraison(self):
        c = FausseConnexionDerivation([instantane("PROJ-9")], [])
        flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        for table in ("issue_delivery_fields", "issue_current_sprints", "issue_current_asset_versions", "issue_delivery_options",
                      "issue_defect_fields"):
            self.assertEqual(ecritures_de(c, f"DELETE FROM flow.{table}"), [], table)
        self.assertEqual(ecritures_de(c, "INSERT INTO flow.sprints"), [])

    def test_references_de_version_creees_puis_inchangees(self):
        contenu = {"short_name": "ZzNomCourt", "status": "Released", "status_category": "Done", "started": "2026-01-05",
                   "released": "2026-03-10"}
        c = self.connexion(livraison_vivante=LIVRAISON, versions_brutes=[("101", contenu, MAINTENANT)])
        resultat = flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        self.assertEqual(resultat["versions_ecrites"], 1)
        ecriture = [(s, p) for s, p in c.ecritures if s.startswith("INSERT INTO flow.release_versions")]
        self.assertEqual(len(ecriture), 1)
        self.assertEqual(ecriture[0][1], ("101", "ZzNomCourt", "Released", "Done", dt.date(2026, 1, 5), dt.date(2026, 3, 10), MAINTENANT))
        deja = self.connexion(livraison_vivante=LIVRAISON, versions_brutes=[("101", contenu, MAINTENANT)],
                              references_vivantes=[("101", "ZzNomCourt", "Released", "Done", dt.date(2026, 1, 5), dt.date(2026, 3, 10))])
        self.assertEqual(flow_raw.deriver(deja, appliquer=True, maintenant=MAINTENANT)["versions_ecrites"], 0)

    def test_attributs_de_version_modifies_mis_a_jour(self):
        contenu = {"short_name": "ZzNomCourt", "status": "Released", "status_category": "Done", "started": None, "released": "2026-03-11"}
        c = self.connexion(livraison_vivante=LIVRAISON, versions_brutes=[("101", contenu, MAINTENANT)],
                           references_vivantes=[("101", "ZzNomCourt", "Open", "To Do", None, None)])
        flow_raw.deriver(c, appliquer=True, maintenant=MAINTENANT)
        self.assertEqual(len(ecritures_de(c, "UPDATE flow.release_versions")), 1)
        self.assertEqual(ecritures_de(c, "INSERT INTO flow.release_versions"), [])


class Affichage(unittest.TestCase):
    RESULTAT = {"rien": False, "compares": 1, "inseres": 0, "modifies": 1, "inchanges": 0, "equipes": 0, "liens_ajoutes": 0, "liens_retires": 0,
                "hors_conservation": 0, "marques": 0, "revenus": 0, "disparus_revus": 0, "versions_ecrites": 0, "versions_sans_ticket": 1}

    def sortie(self, langue, **plus):
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            flow_import.afficher({**self.RESULTAT, **plus}, False, Messages(CATALOGS, langue))
        return tampon.getvalue()

    def test_versions_sans_ticket_de_version(self):
        self.assertIn("versions without version ticket: 1", self.sortie("en"))
        self.assertIn("versions sans ticket de version : 1", self.sortie("fr"))

    def test_ligne_absente_a_zero_et_aussi_sans_nouveau_passage(self):
        self.assertNotIn("without version ticket", self.sortie("en", versions_sans_ticket=0))
        self.assertIn("versions without version ticket: 1", self.sortie("en", rien=True))

    def test_aucun_identifiant_dans_la_sortie(self):
        self.assertNotIn("101", self.sortie("en"))


if __name__ == "__main__":
    unittest.main()
