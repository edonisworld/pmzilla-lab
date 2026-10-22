"""Tickets sortis de l'export (R-58, capacité jira-flow-store) : aucun lecteur de la base ne rend un ticket dont out_of_export_at est non nul.

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

Deux familles. Sans base (classe RequetesSansBase, toujours exécutée) : chaque requête émise par un lecteur écarte les tickets marqués,
vérifié sur le texte SQL par une fausse connexion. Avec base : les structures lues sont égales à celles du chargeur de test des fixtures CSV pour le jeu
amputé des tickets marqués, un lien vers un ticket marqué se lit comme un lien vers un ticket hors export. Données inventées (PROJ-n).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402

sys.path.append(str(ICI.parents[1] / "tests" / "flux_jira"))
import chargeur_csv as chargeur   # noqa: E402
import dependencies_jira as dj    # noqa: E402
import flow_store                 # noqa: E402
import flux_jira as fj            # noqa: E402

MARQUE = "out_of_export_at IS NULL"


class FausseConnexion:
    """Enregistre les requêtes ; rend des lignes vides (les lecteurs ne dépendent pas du contenu pour cette vérification)."""

    def __init__(self):
        self.requetes = []

    def execute(self, requete, params=None):
        self.requetes.append(requete)
        return []

    def close(self):
        pass


class RequetesSansBase(unittest.TestCase):
    def requetes_emises(self, lecteur):
        fausse = FausseConnexion()
        with unittest.mock.patch.object(flow_store, "ouvrir", return_value=fausse):
            lecteur({**fj.DEFAULT_CONFIG})
        return fausse.requetes

    def test_les_requetes_de_tickets_ecartent_les_marques(self):
        for lecteur in (flow_store.lire_tickets_flux, flow_store.lire_dependances):
            requetes = self.requetes_emises(lecteur)
            self.assertTrue(any("FROM flow.issues" in r and MARQUE in r for r in requetes), lecteur.__name__)

    def test_la_requete_des_liens_ecarte_les_liens_dont_la_source_est_marquee(self):
        requetes = self.requetes_emises(flow_store.lire_dependances)
        liens = [r for r in requetes if "flow.links" in r]
        self.assertEqual(len(liens), 1)
        self.assertIn("JOIN flow.issues s ON s.key = l.source_key", liens[0])
        self.assertIn(MARQUE, liens[0])

    def test_la_requete_de_l_historique_ecarte_les_marques(self):
        requetes = self.requetes_emises(flow_store.lire_historique)
        self.assertEqual(len(requetes), 1)
        self.assertIn("flow.transitions", requetes[0])
        self.assertIn(MARQUE, requetes[0])

    def test_aucune_requete_de_lecture_sans_le_filtre(self):
        """Toute requête qui touche flow.issues, flow.links ou flow.transitions porte le filtre : un nouveau lecteur sans filtre échoue ici."""
        for lecteur in (flow_store.lire_tickets_flux, flow_store.lire_dependances, flow_store.lire_historique):
            for requete in self.requetes_emises(lecteur):
                if any(table in requete for table in ("flow.issues", "flow.links", "flow.transitions")):
                    self.assertIn(MARQUE, requete, requete)

    def test_aucune_requete_ne_lit_les_periodes_ni_la_colonne_dans_la_sortie(self):
        for lecteur in (flow_store.lire_tickets_flux, flow_store.lire_dependances, flow_store.lire_historique):
            for requete in self.requetes_emises(lecteur):
                self.assertNotIn("_periods", requete)
                self.assertNotRegex(requete.split("FROM", 1)[0], "out_of_export_at")     # filtrée, jamais rendue


def trier(tickets):
    return sorted(tickets, key=lambda t: t["cle"])


class LecteursSansLesMarques(base.AvecBase):
    def setUp(self):
        super().setUp()
        self.dossier = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dossier, ignore_errors=True))
        self.liste = jeu.tickets()

    def marquer(self, *cles):
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = ANY(%s)", (list(cles),))
        self.conn.execute("RESET ROLE")
        self.conn.commit()

    def csv_sans(self, marques, liens_base):
        chemin = self.dossier / "export.csv"
        jeu.ecrire_csv(chemin, [t for t in self.liste if t["cle"] not in marques], liens_base=liens_base)
        return str(chemin)

    def test_ticket_ouvert_marque_rapport_de_flux_egal_au_csv(self):
        """Scénario « Marked open ticket » : la base contient un ticket ouvert marqué, le CSV du jour ne l'a pas."""
        ouverts = [t["cle"] for t in self.liste if not t["resolu"]][:3]
        self.assertTrue(ouverts)
        self.inserer(self.liste, jeu.liens(), [])
        self.marquer(*ouverts)
        reglages = {**fj.DEFAULT_CONFIG}
        attendu = chargeur.lire_tickets_flux(reglages, [self.csv_sans(set(ouverts), jeu.liens())])
        lu = flow_store.lire_tickets_flux(reglages)
        self.assertEqual(trier(lu[0]), trier(attendu[0]))
        self.assertEqual(lu[1:], attendu[1:])
        self.assertFalse({t["cle"] for t in lu[0]} & set(ouverts))
        self.assertEqual(len(lu[0]), len(self.liste) - len(ouverts))

    def test_ticket_resolu_marque_ecarte_du_debit(self):
        resolus = [t["cle"] for t in self.liste if t["resolu"]][:3]
        self.inserer(self.liste, [], [])
        self.marquer(*resolus)
        cles = {t["cle"] for t in flow_store.lire_tickets_flux({**fj.DEFAULT_CONFIG})[0]}
        self.assertFalse(cles & set(resolus))

    def test_lien_vers_un_ticket_marque_se_lit_comme_hors_export(self):
        """Scénario « Link to a marked ticket » : PROJ-21 attend PROJ-30, marqué. Comme dans la voie CSV, le lien reste et sa cible
        est absente des tickets lus. Les liens dont la source est marquée (PROJ-10) disparaissent."""
        liens = jeu.liens()
        self.inserer(self.liste, liens, [])
        marques = {"PROJ-10", "PROJ-30"}
        self.marquer(*marques)
        reglages = {**dj.DEFAULTS}
        attendu = chargeur.lire_dependances(reglages, [self.csv_sans(marques, [l for l in liens if l[0] not in marques])])
        lu = flow_store.lire_dependances(reglages)
        self.assertEqual(lu["tickets"], attendu["tickets"])
        self.assertEqual(lu["liens"], attendu["liens"])
        self.assertNotIn("PROJ-30", lu["tickets"])
        self.assertIn(("PROJ-21", "PROJ-30", "Blocks", "sortant"), lu["liens"])
        self.assertFalse([l for l in lu["liens"] if l[0] == "PROJ-10"])
        self.assertEqual(lu["liens_types"], attendu["liens_types"])

    def test_historique_sans_les_marques(self):
        transitions = [t for t in jeu.transitions() if t[0] in {x["cle"] for x in self.liste}]
        self.inserer(self.liste, [], transitions)
        avant = flow_store.lire_historique({**fj.DEFAULT_CONFIG})
        self.assertIn("PROJ-1", avant)
        self.marquer("PROJ-1", "PROJ-3")        # PROJ-1 a des transitions, PROJ-3 une entrée vide
        apres = flow_store.lire_historique({**fj.DEFAULT_CONFIG})
        self.assertNotIn("PROJ-1", apres)
        self.assertNotIn("PROJ-3", apres)
        self.assertEqual(apres, {k: v for k, v in avant.items() if k not in ("PROJ-1", "PROJ-3")})

    def test_sans_ticket_marque_rien_ne_change(self):
        self.inserer(self.liste, jeu.liens(), [])
        reglages = {**fj.DEFAULT_CONFIG}
        avant = flow_store.lire_tickets_flux(reglages)
        self.marquer()
        self.assertEqual(flow_store.lire_tickets_flux(reglages), avant)

    def test_ticket_demarque_revient(self):
        self.inserer(self.liste, [], [])
        self.marquer("PROJ-5")
        reglages = {**fj.DEFAULT_CONFIG}
        self.assertNotIn("PROJ-5", {t["cle"] for t in flow_store.lire_tickets_flux(reglages)[0]})
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("UPDATE flow.issues SET out_of_export_at = NULL WHERE key = 'PROJ-5'")
        self.conn.execute("RESET ROLE")
        self.conn.commit()
        self.assertIn("PROJ-5", {t["cle"] for t in flow_store.lire_tickets_flux(reglages)[0]})


if __name__ == "__main__":
    unittest.main()
