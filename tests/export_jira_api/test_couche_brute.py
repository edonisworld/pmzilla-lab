"""Export : écriture de la couche brute datée à côté des fichiers CSV (change jira-data-architecture, D3, D4, D11, D13 ; specs
jira-flow-export « Export writes the raw layer beside its CSV file », « Export files and run written together », « Export connects
to the database as the import role before any Jira call » ; jira-flow-raw-layer « One dated run per export », « Snapshot only when
a ticket changes », « Snapshot teams keep their Jira identifiers », « Raw-layer counts without content »). Tâche 4.5 (rouge d'abord).

    uv run --with pyyaml --with requests --with "psycopg[binary]" python -m unittest discover -s tests/export_jira_api -v

Faux serveur Jira et magasin en mémoire (aide_couche_brute.py) : aucune base, aucun appel réseau. La classe ExportEnBase, sautée sans
base jetable (bash tools/dbtest.sh export_jira_api), exerce le vrai magasin sous le rôle d'import. Données inventées.
"""
import copy
import datetime as dt
import os
import re
import unittest
from unittest import mock

from test_export_jira_api import AUJOURDHUI, CHAMP, TICKETS, Base, champs, ex, hj, objet
from test_referentiel_et_etiquettes import REFERENTIEL

import flow_raw  # noqa: E402  (tools/ est déjà sur le chemin d'import : test_export_jira_api l'y place)

LIGNE_FR = re.compile(r"^couche brute : (\d+) tickets vus, (\d+) instantanés ajoutés$", re.M)
LIGNE_EN = re.compile(r"^raw layer: (\d+) tickets seen, (\d+) snapshots added$", re.M)
ETAT_NEUF = ("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200")
INCONNUE = "(équipe inconnue)"
ORIGINAL = ex.ouvrir_magasin if hasattr(ex, "ouvrir_magasin") else None


MODIFIE = "2026-09-20T10:00:00.000+0200"
FAUX_MOT_DE_PASSE = "MotDePasse" + "Invente-5d2a77c1"   # fabriqué à l'exécution : aucun littéral pour la garde des secrets


def modifie(ticket, instant=MODIFIE):
    """Les tickets du faux serveur n'ont pas de champ « updated » : Jira le renvoie toujours, un ticket sans lui n'a pas d'instantané."""
    ticket["updated"] = instant
    return ticket


def trois_tickets():
    return {cle: modifie(copy.deepcopy(TICKETS[cle])) for cle in ("ABC-1", "ABC-2", "ABC-3")}


class AvecCouche(Base):
    def setUp(self):
        super().setUp()
        self.faux.tickets = trois_tickets()
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        self.exports = self.ws / "Flux-Lab" / "exports"

    def exporter(self, *extra, nom=None):
        sortie = ["export", *extra]
        return self.lancer(*sortie)

    def fichiers(self):
        return sorted(p.name for p in self.exports.glob("*")) if self.exports.exists() else []


class PassageEtVisites(AvecCouche):
    def test_premier_export_de_deux_requetes_nommees(self):
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.fichiers(), [])                     # l'export n'écrit aucun fichier (database-only, D1)
        self.assertEqual(self.magasin.passages, [{"genre": "export", "nb_requetes": 2, "toutes": True}])
        self.assertEqual(self.magasin.cles_vues(1), {"ABC-1", "ABC-2", "ABC-3"})
        self.assertEqual(len(self.magasin.instantanes), 3)
        for fichier in ("api-a", "api-b"):
            self.assertNotIn(fichier, repr(self.magasin.passages))             # ni nom de fichier ni nom de requête

    def test_une_seule_requete_n_est_pas_toutes_les_requetes(self):
        code, sortie = self.exporter("--query", "a")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.passages, [{"genre": "export", "nb_requetes": 1, "toutes": False}])

    def test_requete_sans_nom_compte_pour_toutes(self):
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        self.exporter()
        self.assertEqual(self.magasin.passages, [{"genre": "export", "nb_requetes": 1, "toutes": True}])

    def test_aucun_fichier_n_est_ecrit_ni_dans_les_exports_ni_ailleurs(self):
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        self.assertFalse(self.exports.exists())
        self.assertEqual([p.name for p in self.ws.rglob("*") if p.is_file()], ["flux.yaml"])
        self.assertNotIn("Fichier écrit", sortie)

    def test_la_ligne_de_la_couche_brute_termine_les_comptes(self):
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        trouve = LIGNE_FR.search(sortie)
        self.assertEqual(trouve.groups(), ("3", "3"))
        self.assertEqual(sortie.splitlines()[-1], trouve.group(0))

    def test_la_ligne_en_anglais(self):
        code, sortie = self.exporter("--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(LIGNE_EN.search(sortie).groups(), ("3", "3"))
        self.assertIsNone(LIGNE_FR.search(sortie))


class InstantanesSeulementAuChangement(AvecCouche):
    def test_second_export_sans_changement_ajoute_des_visites_mais_aucun_instantane(self):
        self.exporter()
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.magasin.passages), 2)
        self.assertEqual(self.magasin.cles_vues(2), {"ABC-1", "ABC-2", "ABC-3"})
        self.assertEqual(len(self.magasin.instantanes), 3)
        self.assertEqual(LIGNE_FR.search(sortie).groups(), ("3", "0"))

    def test_un_champ_change_un_seul_instantane(self):
        self.exporter()
        self.faux.tickets["ABC-2"]["status"] = {"name": "Closed", "statusCategory": {"name": "Done"}}
        self.faux.tickets["ABC-2"]["updated"] = "2026-10-01T10:00:00.000+0200"
        self.exporter()
        self.assertEqual([len(self.magasin.instantanes_de(c)) for c in ("ABC-1", "ABC-2", "ABC-3")], [1, 2, 1])
        self.assertEqual(self.magasin.instantanes_de("ABC-2")[-1]["status"], "Closed")

    def test_un_instantane_plus_ancien_que_le_dernier_n_est_pas_ecrit(self):
        self.faux.tickets["ABC-2"]["updated"] = "2026-10-01T10:00:00.000+0200"
        self.exporter()
        self.faux.tickets["ABC-2"]["status"] = {"name": "Closed", "statusCategory": {"name": "Done"}}
        self.faux.tickets["ABC-2"]["updated"] = "2026-09-01T10:00:00.000+0200"            # avant le dernier instantané
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes_de("ABC-2")), 1)

    def test_aucun_texte_de_ticket_dans_les_instantanes(self):
        self.exporter()
        self.assertNotIn("Titre secret", repr(self.magasin.instantanes))                 # le titre n'est même pas demandé
        for instantane in self.magasin.instantanes:
            self.assertFalse({"summary", "title", "description", "labels", "fixVersions", "assignee"} & set(instantane))


class IdentifiantsDEquipe(AvecCouche):
    def setUp(self):
        super().setUp()
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(REFERENTIEL, encoding="utf-8")
        self.faux.tickets = {}
        for cle, objets in {"ABC-1": [objet(1)], "ABC-2": [objet(2), objet(4)], "ABC-3": [objet(9), objet(3)]}.items():
            ticket = modifie(champs(*ETAT_NEUF))
            ticket[CHAMP] = objets
            self.faux.tickets[cle] = ticket

    def equipes(self, cle, rang=-1):
        return [(e["name"], e["jira_team_id"]) for e in self.magasin.instantanes_de(cle)[rang]["teams"]]

    def test_identifiants_dans_l_ordre_de_l_api_l_inconnu_garde_le_sien(self):
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.equipes("ABC-1"), [("Equipe A", "1")])
        self.assertEqual(self.equipes("ABC-2"), [("Equipe B", "2"), (INCONNUE, "4")])
        self.assertEqual(self.equipes("ABC-3"), [(INCONNUE, "9"), ("Equipe C", "3")])

    def test_nom_traduit_corrige_un_instantane_par_ticket_de_l_identifiant(self):
        self.exporter()
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(REFERENTIEL.replace("Equipe A", "Equipe Alpha"), encoding="utf-8")
        self.exporter()
        self.assertEqual([len(self.magasin.instantanes_de(c)) for c in ("ABC-1", "ABC-2", "ABC-3")], [2, 1, 1])
        self.assertEqual(self.equipes("ABC-1"), [("Equipe Alpha", "1")])

    def test_champ_lu_comme_libelles_sans_identifiant(self):
        self.faux.tickets = {"ABC-1": modifie(champs(*ETAT_NEUF, equipes=["Equipe A", "Equipe B"]))}
        self.exporter()
        self.assertEqual(self.equipes("ABC-1"), [("Equipe A", None), ("Equipe B", None)])

    def test_la_ligne_de_la_couche_brute_ne_porte_aucun_identifiant_ni_nom(self):
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        ligne = LIGNE_FR.search(sortie).group(0)
        self.assertEqual(re.sub(r"\d+", "N", ligne), "couche brute : N tickets vus, N instantanés ajoutés")
        for interdit in ("ABC-", "Equipe", "ws-secret"):
            self.assertNotIn(interdit, ligne)


class TicketsHorsConservation(AvecCouche):
    def test_ni_visite_ni_instantane_pour_un_ticket_resolu_avant_la_conservation(self):
        ancien = modifie(champs("Story", "Closed", "Done", "2024-01-05T09:00:00.000+0100", "2024-02-05T09:00:00.000+0100", "Done"))
        self.faux.tickets["ABC-OLD"] = ancien
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("ABC-OLD", self.magasin.cles_vues(1))
        self.assertEqual(self.magasin.instantanes_de("ABC-OLD"), [])
        self.assertEqual(LIGNE_FR.search(sortie).groups(), ("3", "3"))


class EquipesInconnuesEnMode_strict(AvecCouche):
    def test_code_3_sans_fichier_et_sans_rien_enregistrer(self):
        """Sur la voie sans fichier, un export strict incomplet n'enregistre ni passage, ni visite, ni instantané (database-only, D1 ;
        R3 de la réalignement de R-70 : le code 3 avec écriture double est de la période transitoire)."""
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(REFERENTIEL, encoding="utf-8")
        ticket = modifie(champs(*ETAT_NEUF))
        ticket[CHAMP] = [objet(8)]
        self.faux.tickets = {"ABC-1": ticket}
        code, sortie = self.exporter("--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual(self.fichiers(), [])
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))
        self.assertTrue(sortie.rstrip().endswith("identifiants d'équipe inconnus : export incomplet"), sortie)
        self.assertNotIn("couche brute", sortie)
        self.assertTrue(self.magasin.ferme)


class ErreursSansRienLaisser(AvecCouche):
    def test_erreur_jira_apres_la_premiere_requete(self):
        vrai = ex.interroger
        appels = []

        def interroger(client, jql, champs_, une_page=False):
            appels.append(jql)
            if len(appels) == 2:
                raise hj.ErreurHTTP(500)
            return vrai(client, jql, champs_, une_page)
        with mock.patch.object(ex, "interroger", interroger):
            code, sortie = self.exporter()
        self.assertEqual(code, 1, sortie)
        self.assertEqual(self.fichiers(), [])                       # ni fichier final ni fichier temporaire
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))

    def test_erreur_de_base_apres_les_lectures(self):
        self.magasin.echec_ecriture = RuntimeError("ZZSECRET-cle-ABC-1-mot-de-passe")
        code, sortie = self.exporter()
        self.assertEqual(code, 1, sortie)
        self.assertIn("RuntimeError", sortie)                       # le type seul
        self.assertNotIn("ZZSECRET", sortie)
        self.assertNotIn("ABC-1", sortie)
        self.assertEqual(self.fichiers(), [])
        self.assertEqual(self.magasin.passages, [])

    def test_echec_de_la_validation(self):
        self.magasin.echec_validation = RuntimeError("validation")
        code, sortie = self.exporter()
        self.assertEqual(code, 1, sortie)
        self.assertEqual(self.fichiers(), [])
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))

    def test_un_export_precedent_reste_en_place_quand_le_suivant_echoue(self):
        self.exporter()
        avant = {p.name: p.read_bytes() for p in self.exports.glob("*")}
        self.faux.tickets["ABC-2"]["status"] = {"name": "Closed", "statusCategory": {"name": "Done"}}
        self.magasin.echec_validation = RuntimeError("x")
        code, _ = self.exporter()
        self.assertEqual(code, 1)
        self.assertEqual({p.name: p.read_bytes() for p in self.exports.glob("*")}, avant)
        self.assertEqual(len(self.magasin.passages), 1)

    def test_le_magasin_est_ferme_dans_tous_les_cas(self):
        self.exporter()
        self.assertTrue(self.magasin.ferme)
        self.magasin.ferme = False
        self.magasin.echec_ecriture = RuntimeError("x")
        self.exporter()
        self.assertTrue(self.magasin.ferme)


class ConnexionAvantTouteRequete(Base):
    """Le seam des autres tests est retiré : la vraie ouverture du magasin, sans mot de passe ou sans base."""

    def setUp(self):
        super().setUp()
        self.vrai = ORIGINAL
        patch = mock.patch.object(ex, "ouvrir_magasin", ORIGINAL)
        patch.start()
        self.addCleanup(patch.stop)
        faux_security = self.ws / "security_absent"
        faux_security.write_text("#!/bin/sh\nexit 44\n")
        faux_security.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PMZILLA_LAB_DB_")}
        env["PMZILLA_LAB_DB_SECURITY_BIN"] = str(faux_security)
        patch_env = mock.patch.dict(os.environ, env, clear=True)
        patch_env.start()
        self.addCleanup(patch_env.stop)

    def verifier_arret(self, code, sortie, phrase):
        self.assertEqual(code, 1, sortie)
        self.assertIn(phrase, sortie)
        self.assertEqual(self.faux.appels, [])                       # aucun appel à Jira
        self.assertFalse((self.ws / "Flux-Lab" / "exports").exists() and list((self.ws / "Flux-Lab" / "exports").glob("*")))

    def test_mot_de_passe_du_role_d_import_absent(self):
        code, sortie = self.lancer("export")
        self.verifier_arret(code, sortie, "mot de passe du rôle d'import absent : le poser avec db.py role-password")
        code, sortie = self.lancer("export", "--language", "en")
        self.verifier_arret(code, sortie, "import role password missing: set it with db.py role-password")

    def test_base_injoignable(self):
        os.environ["PMZILLA_LAB_DB_URL"] = "postgresql://postgres@127.0.0.1:1/pmzilla"
        os.environ["PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW"] = FAUX_MOT_DE_PASSE
        code, sortie = self.lancer("export")
        self.verifier_arret(code, sortie, "base injoignable : export arrêté avant tout appel à Jira")
        self.assertNotIn(FAUX_MOT_DE_PASSE, sortie)
        code, sortie = self.lancer("export", "--language", "en")
        self.verifier_arret(code, sortie, "database unreachable: export stopped before any Jira call")

    def test_diagnose_et_fields_ne_se_connectent_pas(self):
        with mock.patch.object(ex, "ouvrir_magasin", side_effect=AssertionError("connexion")):
            code, sortie = self.lancer("fields", "--search", "team")
            self.assertEqual(code, 0, sortie)
            code, sortie = self.lancer("diagnose")
            self.assertEqual(code, 0, sortie)

    def test_check_teams_et_migrate_teams_ne_se_connectent_pas(self):
        # Quel que soit leur résultat (refus en session Claude Code, fichier absent, contrôle), elles n'ouvrent jamais la base.
        with mock.patch.object(ex, "ouvrir_magasin", side_effect=AssertionError("connexion")):
            for argv in (("check-teams",), ("migrate-teams", "--from-assets", str(self.ws / "absent.csv"))):
                code, sortie = self.lancer(*argv)
                self.assertNotIn("AssertionError", sortie, (argv, sortie))
                self.assertEqual(self.faux.appels, [])                       # ni connexion à la base, ni appel à Jira

    def test_le_reglage_invalide_arrete_avant_la_base(self):
        self.ecrire_reglages("jql_export: p\nexport_timezone: Mars/X\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1, sortie)
        self.assertIn("export_timezone", sortie)                     # l'erreur de réglage passe avant la connexion


class ExportDeCaractereDistinctif(AvecCouche):
    def test_aucune_cle_ni_libelle_distinctif_dans_la_sortie(self):
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_export: project = ABC\n")
        self.faux.tickets = {f"ZZKEY-{i}": modifie(champs(*ETAT_NEUF, equipes=["ZZDISTINCT-EQUIPE"])) for i in (1, 2)}
        code, sortie = self.exporter()
        self.assertEqual(code, 0, sortie)
        self.assertIsNotNone(LIGNE_FR.search(sortie))
        for chaine in ("ZZKEY", "ZZDISTINCT"):
            self.assertNotIn(chaine, sortie)


class FonctionsPures(unittest.TestCase):
    """Choix des instantanés et empreinte, sans export."""

    def instantane(self, **valeurs):
        base = {"issue_key": "PROJ-1", "updated_at": dt.datetime(2026, 10, 1, 10, 0, tzinfo=dt.timezone.utc), "project": "PROJ",
                "type": "Story", "status": "Open", "status_category": "To Do",
                "created_at": dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc), "resolved_at": None, "resolution": None,
                "status_category_changed_at": None, "story_points": None, "parent_key": None,
                "teams": [{"name": "Alpha", "jira_team_id": "1"}], "links": None}
        base.update(valeurs)
        base["content_hash"] = flow_raw.empreinte(base)
        return base

    def test_empreinte_stable_et_sensible_a_chaque_champ_et_aux_identifiants(self):
        a = self.instantane()
        self.assertEqual(a["content_hash"], self.instantane()["content_hash"])
        for champ, valeur in (("status", "Done"), ("type", "Bug"), ("project", "OTHER"), ("resolution", "Done"),
                              ("story_points", 3), ("parent_key", "PROJ-9"), ("links", []),
                              ("resolved_at", dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc)),
                              ("teams", [{"name": "Alpha", "jira_team_id": "2"}]),
                              ("teams", [{"name": "Alpha", "jira_team_id": None}]),
                              ("teams", [{"name": "Beta", "jira_team_id": "1"}]),
                              ("updated_at", dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc))):
            self.assertNotEqual(a["content_hash"], self.instantane(**{champ: valeur})["content_hash"], (champ, valeur))

    def test_choisir_nouveau_changement_identique_et_plus_ancien(self):
        existant = self.instantane()
        derniers = {"PROJ-1": (existant["updated_at"], existant["content_hash"])}
        nouveau = self.instantane(issue_key="PROJ-2")
        change = self.instantane(status="Done", updated_at=dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc))
        plus_ancien = self.instantane(status="Done", updated_at=dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc))
        self.assertEqual(flow_raw.choisir({"PROJ-2": nouveau}, derniers), [nouveau])
        self.assertEqual(flow_raw.choisir({"PROJ-1": existant}, derniers), [])
        self.assertEqual(flow_raw.choisir({"PROJ-1": change}, derniers), [change])
        self.assertEqual(flow_raw.choisir({"PROJ-1": plus_ancien}, derniers), [])


if __name__ == "__main__":
    unittest.main()
