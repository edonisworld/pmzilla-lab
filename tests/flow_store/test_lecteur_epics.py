"""Lecteur des épics de flow_store pour `flux_jira.py epics` (R-89, conception D13, tâche 2.5).

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; les tests avec base sont sautés sans elle)

`flow_store.lire_epics(settings, motifs_exclus)` rend un élément par épic des types d'épic des réglages, sans clé :
type, projet, statut, création et résolution (instants avec le fuseau d'export), classe de résolution (`done` ou `not_done`
d'après la liste passée, jamais le texte de la résolution), équipes dans l'ordre d'attribution, transitions, drapeau d'historique et
périodes d'étiquettes déclarées par rôle (clé de cycle d'une étiquette de cycle, sens d'une étiquette de confirmation, jamais le
texte de l'étiquette). Les tickets marqués hors export ne sont rendus nulle part.

Deux familles : sans base (fausse connexion, toujours exécutée) et avec base (sautée sans Docker). Données inventées.
"""
from __future__ import annotations

import datetime as dt
import sys
import unittest
import unittest.mock
from pathlib import Path
from zoneinfo import ZoneInfo

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402

import flow_store                 # noqa: E402
import flux_config                # noqa: E402
from yaml_strict import charger   # noqa: E402

UTC = dt.timezone.utc
PARIS = ZoneInfo("Europe/Paris")
MARQUE = "out_of_export_at IS NULL"
DISTINCTIVE = "zz-domaine-secret"
TEXTE_RESOLUTION = "Won't Do Distinctif"
REGLAGES_TEXTE = f"""export_timezone: Europe/Paris
epic_types: [Epic]
declared_labels:
  pilot_domain: {{prefix: "zz-", labels: ["{DISTINCTIVE}"]}}
  cycle: {{prefix: "zc-", labels: ["zc-un", "zc-deux"], cycle_keys: {{zc-un: 2026-C1, zc-deux: 2026-C2}}}}
  ready: {{prefix: "zr-", labels: ["zr-pret"]}}
  epic_review: {{prefix: "ze-", labels: ["ze-revue"]}}
  confirmation: {{prefix: "zf-", labels: ["zf-pris", "zf-non"], meanings: {{zf-pris: taken_in, zf-non: not_taken_in}}}}
cycles:
  2026-C1: {{fix_version: vA-1, start: 2026-01-05, end: 2026-02-27}}
  2026-C2: {{fix_version: vA-2, start: 2026-03-02, end: 2026-04-24}}
"""
REGLAGES = flux_config.to_internal(charger(REGLAGES_TEXTE))
MOTIFS = {"won't do distinctif"}


class ConnexionCannee:
    """Rend des lignes préparées selon la table interrogée (le premier motif trouvé dans la requête) ; enregistre requêtes et paramètres."""

    def __init__(self, epics=(), equipes=(), transitions=(), periodes=()):
        self.requetes = []
        self.lignes = [("flow.transitions", list(transitions)), ("issue_label_periods", list(periodes)),
                       ("flow.issue_teams", list(equipes)), ("FROM flow.issues i", list(epics))]

    def execute(self, requete, params=None):
        self.requetes.append((requete, params))
        return next(lignes for motif, lignes in self.lignes if motif in requete)

    def close(self):
        pass


def lire_avec(connexion, motifs=MOTIFS, reglages=REGLAGES):
    with unittest.mock.patch.object(flow_store, "ouvrir", return_value=connexion):
        return flow_store.lire_epics(reglages, motifs)


class SansBase(unittest.TestCase):
    def setUp(self):
        self.cree = dt.datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        self.resolu = dt.datetime(2026, 2, 10, 23, 30, tzinfo=UTC)
        self.ajout = dt.datetime(2026, 1, 6, 8, 0, tzinfo=UTC)
        self.retrait = dt.datetime(2026, 2, 5, 18, 0, tzinfo=UTC)
        # (clé, projet, type, statut, création, résolution, texte de résolution, avec historique, première équipe)
        epics = [("ZZE-1", "ZZE", "Epic", "Idee", self.cree, self.resolu, "Done", True, "Equipe B"),
                 ("ZZE-2", None, "Epic", "Prete", self.cree, self.resolu, TEXTE_RESOLUTION, False, None)]
        self.connexion = ConnexionCannee(
            epics=epics,
            equipes=[("ZZE-1", "Equipe B"), ("ZZE-1", "Equipe A")],
            transitions=[("ZZE-1", self.ajout, None, "Idee"), ("ZZE-1", self.retrait, "Idee", "Prete")],
            periodes=[("ZZE-1", DISTINCTIVE, self.ajout, None), ("ZZE-1", "ze-revue", self.ajout, self.retrait),
                      ("ZZE-1", "zc-deux", self.ajout, None), ("ZZE-1", "zf-pris", self.retrait, None),
                      ("ZZE-1", "zr-pret", self.retrait, None)])

    def epics(self):
        return lire_avec(self.connexion)

    def test_un_element_par_epic_sans_cle_ni_texte_d_etiquette(self):
        e1, e2 = self.epics()
        self.assertEqual((e1["type"], e1["projet"], e1["etat"]), ("Epic", "ZZE", "Idee"))
        self.assertEqual(e2["projet"], "ZZE")                       # projet déduit de la clé
        self.assertNotIn("cle", e1)
        texte = repr([e1, e2])
        for secret in ("ZZE-1", "ZZE-2", DISTINCTIVE, "zc-deux", "ze-revue", "zf-pris", "zr-pret", TEXTE_RESOLUTION):
            self.assertNotIn(secret, texte)

    def test_equipes_dans_l_ordre_d_attribution_et_repli_sur_la_premiere_equipe(self):
        e1, e2 = self.epics()
        self.assertEqual(e1["equipes"], ["Equipe B", "Equipe A"])
        self.assertEqual(e2["equipes"], [])
        self.connexion.lignes[3] = ("FROM flow.issues i", [("ZZE-3", "ZZE", "Epic", "Idee", self.cree, None, None, True, "Equipe C")])
        self.assertEqual(lire_avec(self.connexion)[0]["equipes"], ["Equipe C"])

    def test_instants_dans_le_fuseau_d_export(self):
        e1, _ = self.epics()
        self.assertEqual(e1["cree"], self.cree)
        self.assertEqual(e1["cree"].utcoffset(), dt.timedelta(hours=1))                 # Paris en janvier
        self.assertEqual(e1["resolu"].astimezone(PARIS).date(), dt.date(2026, 2, 11))   # 23:30 UTC, le 11 à Paris
        self.assertEqual(e1["transitions"], [(self.ajout, None, "Idee"), (self.retrait, "Idee", "Prete")])
        self.assertEqual(e1["transitions"][0][0].utcoffset(), dt.timedelta(hours=1))

    def test_classe_de_resolution_sans_le_texte(self):
        e1, e2 = self.epics()
        self.assertEqual(e1["classe"], "done")
        self.assertEqual(e2["classe"], "not_done")
        self.connexion.lignes[3] = ("FROM flow.issues i", [("ZZE-3", "ZZE", "Epic", "Idee", self.cree, None, None, True, None)])
        self.assertIsNone(lire_avec(self.connexion)[0]["classe"])                      # non résolu : aucune classe

    def test_periodes_par_role(self):
        e1, _ = self.epics()
        par_role = {p["role"]: p for p in e1["periodes"]}
        self.assertEqual(set(par_role), {"pilot_domain", "epic_review", "cycle", "confirmation", "ready"})
        self.assertEqual((par_role["cycle"]["cycle"], par_role["cycle"]["retrait"]), ("2026-C2", None))
        self.assertEqual(par_role["confirmation"]["sens"], "taken_in")
        self.assertEqual((par_role["epic_review"]["ajout"], par_role["epic_review"]["retrait"]), (self.ajout, self.retrait))
        self.assertTrue(all(p["ajout"].tzinfo is not None for p in e1["periodes"]))

    def test_drapeau_d_historique(self):
        e1, e2 = self.epics()
        self.assertEqual((e1["a_historique"], e2["a_historique"]), (True, False))

    def test_les_etiquettes_non_declarees_ne_sont_pas_lues(self):
        lire_avec(self.connexion)
        requete, parametres = next((r, p) for r, p in self.connexion.requetes if "issue_label_periods" in r)
        self.assertIn("%(etiquettes)s", requete)
        self.assertEqual(set(parametres["etiquettes"]), {DISTINCTIVE, "zc-un", "zc-deux", "zr-pret", "ze-revue", "zf-pris", "zf-non"})

    def test_chaque_requete_ecarte_les_tickets_marques_et_filtre_les_types(self):
        lire_avec(self.connexion)
        self.assertEqual(len(self.connexion.requetes), 4)
        for requete, parametres in self.connexion.requetes:
            self.assertIn("flow.issues", requete)
            self.assertIn(MARQUE, requete, requete)
            self.assertIn("%(types)s", requete)
            self.assertEqual(parametres["types"], ["epic"])
            self.assertEqual(parametres["tz"], "Europe/Paris")

    def test_sans_bloc_d_etiquettes_aucune_periode(self):
        reglages = flux_config.to_internal(charger("export_timezone: Europe/Paris\nepic_types: [Epic]\n"))
        e1, _ = lire_avec(self.connexion, reglages=reglages)
        self.assertEqual(e1["periodes"], [])
        self.assertFalse([r for r, _ in self.connexion.requetes if "issue_label_periods" in r])

    def test_types_d_epic_des_reglages(self):
        reglages = flux_config.to_internal(charger("epic_types: [Epic, Feature]\nexport_timezone: Europe/Paris\n"))
        lire_avec(self.connexion, reglages=reglages)
        self.assertEqual(self.connexion.requetes[0][1]["types"], ["epic", "feature"])

    def test_la_lecture_passe_par_le_role_de_lecture_seule(self):
        self.assertEqual(flow_store.ROLE_LECTURE, "pmzilla_flow_ro")


def ecrire_periodes(conn, etiquettes=()):
    conn.execute("SET ROLE pmzilla_flow")
    for cle, nom, ajout, retrait in etiquettes:
        conn.execute("INSERT INTO flow.issue_label_periods (issue_key, label, added_at, removed_at) VALUES (%s, %s, %s, %s)",
                     (cle, nom, ajout, retrait))
    conn.execute("RESET ROLE")
    conn.commit()


def marquer(conn, *cles):
    conn.execute("SET ROLE pmzilla_flow")
    conn.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = ANY(%s)", (list(cles),))
    conn.execute("RESET ROLE")
    conn.commit()


class AvecBase(base.AvecBase):
    """Sautée sans la base jetable : les lignes insérées sous le rôle d'import sont relues sous le rôle de lecture seule."""

    def setUp(self):
        super().setUp()
        self.ajout = dt.datetime(2026, 1, 6, 8, 0, tzinfo=UTC)
        self.retrait = dt.datetime(2026, 2, 5, 18, 0, tzinfo=UTC)
        self.liste = [
            jeu.issue("PROJ-1", "Epic", "Idee", "In Progress", jeu.moment(100), None, "", None, ["Beta", "Alpha"]),
            jeu.issue("PROJ-2", "Epic", "Close", "Done", jeu.moment(100), dt.datetime(2026, 2, 10, 23, 30), "Done", None, ["Alpha"]),
            jeu.issue("PROJ-3", "Epic", "Close", "Done", jeu.moment(100), dt.datetime(2026, 2, 12, 10, 0), TEXTE_RESOLUTION, None, []),
            jeu.issue("PROJ-4", "Story", "Idee", "In Progress", jeu.moment(100), None, "", None, ["Alpha"]),
        ]
        self.inserer(self.liste, [], [("PROJ-1", self.ajout, "Idee", "Prete"), ("PROJ-1", self.retrait, "Prete", "Idee"),
                                      ("PROJ-4", self.ajout, "A", "B")], avec_historique=["PROJ-1", "PROJ-2"])
        ecrire_periodes(self.conn, [("PROJ-1", DISTINCTIVE, self.ajout, None), ("PROJ-1", "ze-revue", self.ajout, self.retrait),
                                    ("PROJ-1", "zc-un", self.ajout, None), ("PROJ-1", "autre-non-declaree", self.ajout, None),
                                    ("PROJ-4", DISTINCTIVE, self.ajout, None)])

    def epics(self):
        return flow_store.lire_epics(REGLAGES, MOTIFS)

    def par_type_et_equipes(self):
        return {tuple(e["equipes"]): e for e in self.epics()}

    def test_epic_avec_historique_et_sans_story(self):
        epics = self.par_type_et_equipes()
        self.assertEqual(len(self.epics()), 3)                                  # la Story n'est pas rendue
        e = epics[("Beta", "Alpha")]
        self.assertEqual(e["equipes"], ["Beta", "Alpha"])                       # ordre d'attribution
        self.assertEqual([t[2] for t in e["transitions"]], ["Prete", "Idee"])
        self.assertEqual({p["role"] for p in e["periodes"]}, {"pilot_domain", "epic_review", "cycle"})
        self.assertEqual(e["a_historique"], True)
        self.assertTrue(all(t[0].tzinfo is not None for t in e["transitions"]))
        self.assertEqual(e["transitions"][0][0].utcoffset(), dt.timedelta(hours=1))

    def test_texte_d_etiquette_et_cle_absents_du_resultat(self):
        texte = repr(self.epics())
        for secret in ("PROJ-", DISTINCTIVE, "zc-un", "ze-revue", "autre-non-declaree", TEXTE_RESOLUTION):
            self.assertNotIn(secret, texte)
        cycle = next(p for e in self.epics() for p in e["periodes"] if p["role"] == "cycle")
        self.assertEqual(cycle["cycle"], "2026-C1")

    def test_classe_de_resolution(self):
        classes = sorted(str(e["classe"]) for e in self.epics())
        self.assertEqual(classes, ["None", "done", "not_done"])

    def test_resolution_en_jour_du_fuseau_d_export(self):
        e = self.par_type_et_equipes()[("Alpha",)]
        self.assertEqual(e["resolu"].astimezone(PARIS).date(), dt.date(2026, 2, 10))      # 23:30 heure locale : le 10, pas le 11 UTC
        self.assertEqual(e["resolu"].tzinfo.key, "Europe/Paris")

    def test_epic_marque_hors_export_absent_avec_ses_transitions_et_ses_periodes(self):
        marquer(self.conn, "PROJ-1")
        epics = self.epics()
        self.assertEqual(len(epics), 2)
        self.assertNotIn(("Beta", "Alpha"), {tuple(e["equipes"]) for e in epics})
        for e in epics:
            self.assertEqual(e["periodes"], [])
            self.assertEqual(e["transitions"], [])

    def test_la_lecture_est_en_lecture_seule(self):
        conn = flow_store.ouvrir()
        try:
            with self.assertRaises(Exception):
                conn.execute("INSERT INTO flow.issue_label_periods (issue_key, label, added_at) VALUES ('PROJ-1', 'x', now())")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
