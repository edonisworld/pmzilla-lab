"""Tests de export_jira_api.py : un faux serveur HTTP local, des données inventées, un faux jeton.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v

Aucun appel au vrai Jira. L'export n'écrit aucun fichier (database-only) : les tests lisent les passages et les instantanés du
faux magasin de la couche brute (aide_couche_brute.py). Ils vérifient aussi que les sous-commandes retirées (teams-table, compare)
renvoient vers la voie à suivre.
"""
import base64
import contextlib
import copy
import datetime as dt
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import export_jira_api as ex          # noqa: E402
import history_jira as hj          # noqa: E402
from aide_couche_brute import MagasinMemoire          # noqa: E402

JETON = "test-token-000"
EMAIL = "utilisateur@example.org"
CLOUD_ID = "cloud-123"
PASSERELLE = f"/ex/jira/{CLOUD_ID}"     # le seul chemin des appels authentifiés
CHAMP = "customfield_10001"
AUJOURDHUI = "2026-10-04"


def champs(type_, etat, categorie, cree, resolu=None, motif=None, debut=None, parent=None, equipes=(), liens=(), maj=None):
    return {"issuetype": {"name": type_}, "status": {"name": etat, "statusCategory": {"name": categorie}},
            "created": cree, "resolutiondate": resolu, "resolution": {"name": motif} if motif else None,
            "statuscategorychangedate": debut or resolu or cree, "parent": {"key": parent} if parent else None,
            "updated": maj or resolu or cree,           # Jira renvoie toujours la date de mise à jour (sans elle, pas d'instantané)
            "issuelinks": [dict(l) for l in liens], "summary": "Titre secret",
            CHAMP: [{"value": e} for e in equipes]}


def lien(type_, sens, cle):
    return {"type": {"name": type_, "inward": "is blocked by", "outward": "blocks"},
            ("outwardIssue" if sens == "Outward" else "inwardIssue"): {"key": cle, "fields": {"summary": "Titre secret"}}}


TICKETS = {
    "ABC-1": champs("Story", "Closed", "Done", "2026-06-01T08:00:00.000+0200", "2026-07-10T10:30:00.000+0200", "Done",
                    parent="ABC-9", equipes=["Equipe A", "Equipe B"],
                    liens=[lien("Blocks", "Outward", "ABC-2"), lien("Blocks", "Outward", "ABC-3"),
                           lien("Relates", "Inward", "ABC-3")]),
    "ABC-2": champs("Task", "Implementation - Ongoing", "In Progress", "2026-08-03T09:15:00.000+0200",
                    equipes=["Equipe A"], liens=[lien("Blocks", "Inward", "ABC-1")]),
    "ABC-3": champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200", equipes=[],
                    liens=[lien("Blocks", "Inward", "ABC-1"), lien("Relates", "Outward", "ABC-1")]),
    "ABC-9": champs("Epic", "In Progress", "In Progress", "2026-01-12T07:05:00.000+0100", equipes=["Equipe B"]),
}


class FauxJira:
    def __init__(self):
        self.tickets = {k: json.loads(json.dumps(v)) for k, v in TICKETS.items()}
        self.taille_page = 100
        self.jeton_repete = False
        self.requetes = []
        self.appels_get = []
        self.hors_passerelle = []     # chemins appelés avec authentification en dehors de la passerelle
        self.appels = []              # (méthode, chemin) de chaque appel reçu, écritures comprises (aucune n'est admise)
        self.champs = [
            {"id": "summary", "name": "Summary", "custom": False, "searchable": True, "schema": {"type": "string"}},
            {"id": "customfield_10001", "name": "[G] Team/s", "custom": True, "schema": {"type": "array"}},
            {"id": "customfield_10002", "name": "[G] team label", "custom": True},
            {"id": "customfield_10003", "name": "Story Points", "custom": True},
            {"id": "assignee", "name": "Assignee", "custom": False}]
        self.attendu = "Basic " + base64.b64encode(f"{EMAIL}:{JETON}".encode()).decode()


def fabriquer_serveur(faux: FauxJira):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def repondre(self, code, corps=None):
            donnees = json.dumps(corps if corps is not None else {}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)

        def hors(self) -> bool:
            """Vrai (et appel noté) si la requête authentifiée ne passe pas par la passerelle ; sinon retire le préfixe."""
            if "Authorization" in self.headers and not self.path.startswith(PASSERELLE + "/"):
                faux.hors_passerelle.append(self.path)
                return True
            self.path = self.path[len(PASSERELLE):] if self.path.startswith(PASSERELLE + "/") else self.path
            return False

        def do_GET(self):
            if self.hors():
                return self.repondre(404)
            faux.appels.append(("GET", self.path))
            if self.headers.get("Authorization") != faux.attendu:
                return self.repondre(401)
            faux.appels_get.append(self.path)
            if self.path != "/rest/api/3/field":
                return self.repondre(404)
            return self.repondre(200, faux.champs)

        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.hors():
                return self.repondre(404)
            faux.appels.append(("POST", self.path))
            if self.headers.get("Authorization") != faux.attendu:
                return self.repondre(401)
            if self.path != "/rest/api/3/search/jql":
                return self.repondre(404)
            faux.requetes.append(corps)
            demandes = corps.get("fields") or []
            cles = list(faux.tickets)
            if str(corps.get("jql", "")).startswith("key in ("):
                voulues = str(corps["jql"])[len("key in ("):-1].split(",")
                cles = [c for c in cles if c in voulues]
            jeton = corps.get("nextPageToken") or "0"
            debut = faux.taille_page if jeton == "boucle" else int(jeton)
            fin = debut + faux.taille_page
            issues = [{"id": str(i), "key": c, "fields": {f: faux.tickets[c][f] for f in demandes if f in faux.tickets[c]}}
                      for i, c in enumerate(cles[debut:fin], start=debut)]
            suite = {} if fin >= len(cles) else {"nextPageToken": "boucle" if faux.jeton_repete else str(fin)}
            return self.repondre(200, {"issues": issues, **suite})

        def ecriture(self):
            """Toute méthode d'écriture est notée puis refusée : l'export ne doit jamais en émettre."""
            self.hors()
            faux.appels.append((self.command, self.path))
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            return self.repondre(405)

        do_PUT = do_DELETE = do_PATCH = ecriture

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class Base(unittest.TestCase):
    def setUp(self):
        self.faux = FauxJira()
        self.serveur = fabriquer_serveur(self.faux)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        flux = self.ws / "Flux-Lab"
        flux.mkdir()
        self.magasin = MagasinMemoire()         # couche brute en mémoire : l'export ne se connecte à aucune base dans ces tests
        for p in (mock.patch.object(ex, "ouvrir_magasin", lambda: self.magasin),
                  mock.patch.object(hj, "WORKSPACE", self.ws), mock.patch.object(hj, "FLUX_DIR", flux),
                  mock.patch.object(hj, "CONFIG_FILE", flux / "flux.yaml"),
                  mock.patch.object(hj, "lire_jeton", lambda: JETON),
                  mock.patch.object(hj, "API_ATLASSIAN", self.url), mock.patch.object(hj, "PAUSE", 0),
                  mock.patch.object(hj, "_JETON", None),
                  mock.patch.object(hj, "aujourd_hui", lambda: dt.date.fromisoformat(AUJOURDHUI))):     # conservation : date fixe
            p.start()
            self.addCleanup(p.stop)
        self.ecrire_reglages()

    def ecrire_reglages(self, extra: str = None, jeton: str | None = "scoped", cloud: str | None = CLOUD_ID):
        """jeton et cloud : None retire le réglage ; « classic » est refusé par l'outil."""
        extra = f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n" if extra is None else extra
        connexion = f"jira_site: {self.url}\njira_email: {EMAIL}\n"
        connexion += f"jira_token_type: {jeton}\n" if jeton else ""
        connexion += f"jira_cloud_id: {cloud}\n" if cloud else ""
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(connexion + extra, encoding="utf-8")

    def lancer(self, *argv):
        sortie = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            try:
                ex.main(list(argv))
            except SystemExit as s:
                code = s.code or 0
                if isinstance(code, str):            # réglage refusé (ErreurConfig) : message sur stderr et code 1, comme au lancement
                    print(code)
                    code = 1
        return code, sortie.getvalue()

    def exporter(self, *options: str) -> dict[str, dict]:
        """Lance l'export (il n'écrit aucun fichier) et rend, par clé, le dernier instantané écrit dans la couche brute."""
        code, sortie = self.lancer("export", *options)
        self.assertEqual(code, 0, sortie)
        return {i["issue_key"]: i for i in self.magasin.instantanes}

    def equipes(self, instantane: dict) -> list[str]:
        return [e["name"] for e in instantane["teams"]]


class AnciensNoms(Base):
    """Anciens noms d'options et de réglages refusés avec le nom actuel, anciens noms de sous-commandes refusés."""

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        # l'ancienne option --sortie (devenue --output) n'est plus testée ici : --output est retirée (database-only, D1)
        for args, ancien, nouveau in ((("fields", "--cherche", "team"), "--cherche", "--search"),):
            code, sortie = self.lancer(*args)
            self.assertEqual(code, 2, sortie)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau} »", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_anciens_noms_de_reglages_refuses_avec_le_nom_actuel(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_champ_equipe: {CHAMP}\n")
        code, sortie = self.lancer("export")
        self.assertNotEqual(code, 0)
        self.assertIn("« export_champ_equipe » n'existe plus ; utiliser « export_team_field »", str(code) + sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("diagnostic", "champs", "table-equipes", "comparer"):
            code, _ = self.lancer(ancien)
            self.assertEqual(code, 2, ancien)
        self.assertEqual(self.faux.requetes, [])


class JetonAScopes(Base):
    """Le client de l'export est celui de history_jira.py : passerelle seule, cloudId des réglages, « classic » refusé."""

    def commandes(self):
        return (("export",), ("fields", "--search", "team"), ("diagnose",))

    def test_les_appels_passent_par_la_passerelle(self):
        for argv in self.commandes():
            self.lancer(*argv)
        self.assertGreater(len(self.faux.requetes) + len(self.faux.appels_get), 0)
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_reglage_absent_utilise_la_passerelle(self):
        self.ecrire_reglages(jeton=None)
        code, sortie = self.lancer("fields", "--search", "team")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_classic_refuse_avant_le_trousseau_et_tout_appel(self):
        self.ecrire_reglages(jeton="classic")
        jeton = mock.Mock(return_value=JETON)
        for argv, attendu in ((self.commandes()[0], "jeton classique refusé : utiliser un jeton à scopes"),
                              (self.commandes()[1], "jeton classique refusé : utiliser un jeton à scopes"),
                              (self.commandes()[2], "jeton classique refusé : utiliser un jeton à scopes"),
                              (self.commandes()[0] + ("--language", "en"), "classic token refused: use a scoped token")):
            with self.subTest(argv=argv), mock.patch.object(hj, "lire_jeton", jeton):
                code, sortie = self.lancer(*argv)
                self.assertEqual(code, 1)
                self.assertIn(attendu, sortie)
                self.assertNotIn("Traceback", sortie)
        jeton.assert_not_called()
        self.assertEqual((self.faux.requetes, self.faux.appels_get, self.faux.hors_passerelle), ([], [], []))

    def test_cloud_id_absent_ou_inexploitable(self):
        jeton = mock.Mock(return_value=JETON)
        for cloud in (None, "a/../b"):
            self.ecrire_reglages(cloud=cloud)
            for argv in self.commandes():
                with self.subTest(cloud=cloud, argv=argv), mock.patch.object(hj, "lire_jeton", jeton):
                    code, sortie = self.lancer(*argv)
                    self.assertEqual(code, 1)
                    self.assertIn("cloudId introuvable", sortie)
                    self.assertNotIn("Traceback", sortie)
        jeton.assert_not_called()
        self.assertEqual((self.faux.requetes, self.faux.appels_get, self.faux.hors_passerelle), ([], [], []))

    def test_aucune_lecture_du_cloud_id_sur_le_site(self):
        original = hj.Client.requete
        vus = []

        def espion(client, methode, chemin, **kwargs):
            vus.append(chemin)
            return original(client, methode, chemin, **kwargs)

        with mock.patch.object(hj.Client, "requete", espion):
            self.exporter()
        self.assertGreater(len(vus), 0)
        self.assertNotIn("/_edge/tenant_info", vus)


class Export(Base):
    def test_instantanes_des_attributs_autorises(self):
        instantanes = self.exporter()
        self.assertEqual(set(instantanes), {"ABC-1", "ABC-2", "ABC-3", "ABC-9"})
        t1 = instantanes["ABC-1"]
        self.assertEqual((t1["project"], t1["type"], t1["status"], t1["status_category"], t1["resolution"], t1["parent_key"]),
                         ("ABC", "Story", "Closed", "Done", "Done", "ABC-9"))
        self.assertEqual([t1[c].isoformat() for c in ("created_at", "resolved_at", "status_category_changed_at")],
                         ["2026-06-01T08:00:00+02:00", "2026-07-10T10:30:00+02:00", "2026-07-10T10:30:00+02:00"])
        self.assertEqual(self.equipes(t1), ["Equipe A", "Equipe B"])                  # dans l'ordre de l'API
        self.assertEqual({(l["target"], l["type"], l["direction"]) for l in t1["links"]},
                         {("ABC-2", "Blocks", "outward"), ("ABC-3", "Blocks", "outward"), ("ABC-3", "Relates", "inward")})
        self.assertEqual(instantanes["ABC-3"]["teams"], [])                           # aucune équipe
        self.assertEqual(instantanes["ABC-9"]["created_at"].isoformat(), "2026-01-12T07:05:00+01:00")   # heure d'hiver de Paris

    def test_un_passage_une_visite_par_ticket_et_aucun_fichier(self):
        self.exporter()
        self.assertEqual(len(self.magasin.passages), 1)
        self.assertEqual(self.magasin.cles_vues(), {"ABC-1", "ABC-2", "ABC-3", "ABC-9"})
        self.assertFalse((self.ws / "Flux-Lab" / "exports").exists())
        self.assertEqual([p.name for p in self.ws.rglob("*") if p.is_file()], ["flux.yaml"])        # rien d'autre n'est écrit

    def test_pagination_complete(self):
        self.faux.taille_page = 1
        instantanes = self.exporter()
        self.assertEqual(len(instantanes), 4)
        self.assertEqual(len(self.faux.requetes), 4)
        self.assertEqual(self.faux.requetes[1]["nextPageToken"], "1")

    def test_jeton_de_page_qui_se_repete_ne_boucle_pas(self):
        self.faux.taille_page = 2
        self.faux.jeton_repete = True
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.faux.requetes), 2)

    def test_aucun_titre_demande_a_jira_et_rien_de_sensible_en_sortie(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        demandes = {f for r in self.faux.requetes for f in r["fields"]}
        self.assertNotIn("summary", demandes)
        for interdit in ("assignee", "reporter", "creator", "description", "labels", "fixVersions"):
            self.assertNotIn(interdit, demandes)
        for instantane in self.magasin.instantanes:
            self.assertNotIn("Titre secret", repr(instantane))
            self.assertNotIn(JETON, repr(instantane))
        self.assertNotIn("Titre secret", sortie)
        self.assertNotIn(JETON, sortie)
        self.assertNotIn("ABC-", sortie)
        self.assertNotIn("Equipe", sortie)
        self.assertNotIn(self.url, sortie)
        self.assertNotIn("project = ABC", sortie)
        self.assertIn("Tickets : 4 ; pages : 1", sortie)

    def test_sans_champ_d_equipe_aucune_equipe(self):
        self.ecrire_reglages("jql_export: project = ABC\n")
        instantanes = self.exporter()
        self.assertTrue(all(i["teams"] == [] for i in instantanes.values()))
        self.assertNotIn(CHAMP, {f for r in self.faux.requetes for f in r["fields"]})

    def test_ancien_reglage_de_l_entete_d_equipe_accepte_sans_effet(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             "export_team_header: '[G] Team/s (label)'\n")
        self.assertEqual(self.equipes(self.exporter()["ABC-1"]), ["Equipe A", "Equipe B"])

    def test_requete_absente(self):
        self.ecrire_reglages("")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertIn("jql_export", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_erreur_d_acces_ne_montre_que_le_code(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertEqual(sortie.strip(), "HTTP 401")


class Champs(Base):
    def test_affiche_seulement_identifiant_et_nom_sans_tenir_compte_de_la_casse(self):
        code, sortie = self.lancer("fields", "--search", "TEAM")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.faux.appels_get, ["/rest/api/3/field"])
        self.assertEqual(sortie.splitlines(), ["2 champ(s) sur 5 dont le nom contient le texte cherché.",
                                               "  customfield_10002  [G] team label",
                                               "  customfield_10001  [G] Team/s"])
        for autre in ("Summary", "Story Points", "Assignee", "schema", "searchable", "array", "true", "True"):
            self.assertNotIn(autre, sortie)
        self.assertEqual(self.faux.requetes, [])                          # aucun ticket lu

    def test_recherche_partielle_et_aucun_resultat(self):
        code, sortie = self.lancer("fields", "--search", "team/s")
        self.assertIn("1 champ(s) sur 5", sortie)
        self.assertIn("customfield_10001  [G] Team/s", sortie)
        code, sortie = self.lancer("fields", "--search", "introuvable")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.strip(), "0 champ(s) sur 5 dont le nom contient le texte cherché.")

    def test_texte_obligatoire_et_non_vide(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                ex.main(["fields"])
        code, sortie = self.lancer("fields", "--search", "  ")
        self.assertEqual(code, 1)
        self.assertIn("donner un texte", sortie)
        self.assertEqual(self.faux.appels_get, [])

    def test_fonctionne_sans_jql_export(self):
        self.ecrire_reglages("")
        code, sortie = self.lancer("fields", "--search", "team")
        self.assertEqual(code, 0, sortie)

    def test_erreur_d_acces_ne_montre_que_le_code(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("fields", "--search", "team")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 401"))

    def test_jeton_et_adresse_jamais_affiches(self):
        code, sortie = self.lancer("fields", "--search", "team")
        for secret in (JETON, self.url, EMAIL):
            self.assertNotIn(secret, sortie)


def objet(n: int) -> dict:
    return {"workspaceId": "ws-secret", "id": f"ws-secret:{n}", "objectId": str(n)}


def catalogue_de(paires: dict) -> str:
    """Texte d'un catalogue (equipes-jira.yaml) : une entrée par identifiant -> libellé (données inventées)."""
    return "teams:\n" + "".join(f"  - name: {libelle}\n    jira_team_ids: ['{identifiant}']\n"
                                for identifiant, libelle in paires.items())


class TableEquipes(Base):
    """Champ d'équipe renvoyé en objets Assets : le catalogue identifiant -> libellé (equipes-jira.yaml, change team-mapping)
    traduit les identifiants ; l'ancienne table n'est plus lue."""

    EQUIPES = {            # clé -> (objets Assets de l'API, libellés attendus dans le CSV)
        "ABC-1": ([objet(1)], ["Equipe A"]),
        "ABC-2": ([objet(2)], ["Equipe B"]),
        "ABC-3": ([objet(1), objet(2)], ["Equipe A", "Equipe B"]),
        "ABC-4": ([objet(3), objet(1)], ["Equipe C", "Equipe A"]),             # ordre de l'API conservé
        "ABC-5": ([objet(4)], ["(équipe inconnue)"]),                          # absent de la table
        "ABC-7": ([objet(6), objet(5)], ["(équipe inconnue)", "(équipe inconnue)"])}

    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        for cle, (objets, _) in self.EQUIPES.items():
            t = champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200")
            t[CHAMP] = objets
            self.faux.tickets[cle] = t

    def ecrire_table(self, paires: dict | None = None) -> Path:
        """Écrit le catalogue (nom conservé pour les tests ci-dessous : il tient la place de l'ancienne table)."""
        chemin = self.ws / "Flux-Lab" / "equipes-jira.yaml"
        chemin.write_text(catalogue_de(paires or {"1": "Equipe A", "2": "Equipe B", "3": "Equipe C"}), encoding="utf-8")
        return chemin

    def test_export_traduit_par_le_catalogue_les_equipes_de_chaque_ticket(self):
        self.ecrire_table()
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        instantanes = {i["issue_key"]: i for i in self.magasin.instantanes}
        for cle, (_, attendu) in self.EQUIPES.items():
            self.assertEqual(self.equipes(instantanes[cle]), attendu, cle)
        self.assertEqual([e["jira_team_id"] for e in instantanes["ABC-4"]["teams"]], ["3", "1"])        # identifiant gardé, ordre de l'API
        self.assertIn("identifiants d'équipe ni dans le référentiel ni dans le catalogue : 3, sur 2 tickets", sortie)
        self.assertIn("équipes hors organisation : 3 identifiants, 4 tickets", sortie)
        for interdit in ("Equipe", "ABC-", "ws-secret"):
            self.assertNotIn(interdit, sortie)

    def test_export_liste_les_identifiants_inconnus_sans_libelle_ni_cle(self):
        self.ecrire_table()
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiants à ajouter : 4 ; 5 ; 6", sortie)
        for interdit in ("Equipe", "ABC-", "ws-secret", "workspace", "teams-table", self.url, JETON):
            self.assertNotIn(interdit, sortie)

    def test_export_liste_les_identifiants_inconnus_en_anglais(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiers to add: 4; 5; 6", sortie)
        self.assertIn("team identifiers in neither the referential nor the catalogue: 3, on 2 tickets", sortie)

    def test_catalogue_complet_aucun_identifiant_a_lister(self):
        self.ecrire_table({str(i): chr(64 + i) for i in range(1, 7)})
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("à ajouter", sortie)
        self.assertNotIn("ni dans le référentiel", sortie)

    def test_strict_teams_identifiant_inconnu_sort_avec_3_sans_rien_enregistrer(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))      # database-only, D1
        self.assertTrue(sortie.rstrip().endswith("identifiants d'équipe inconnus : export incomplet"), sortie)
        for interdit in ("Equipe", "ABC-", "ws-secret", "Fichier écrit"):
            self.assertNotIn(interdit, sortie)

    def test_strict_teams_en_anglais(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--strict-teams", "--language", "en")
        self.assertEqual(code, 3, sortie)
        self.assertTrue(sortie.rstrip().endswith("unknown team identifiers: export incomplete"), sortie)

    def test_strict_teams_catalogue_complet_sort_avec_0(self):
        self.ecrire_table({str(i): chr(64 + i) for i in range(1, 7)})
        code, sortie = self.lancer("export", "--strict-teams")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("export incomplet", sortie)
        self.assertEqual(len(self.magasin.passages), 1)

    def test_sans_strict_teams_le_code_reste_0_et_le_passage_est_ecrit(self):
        self.ecrire_table()
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("export incomplet", sortie)
        self.assertEqual(len(self.magasin.passages), 1)

    def test_strict_teams_requetes_nommees_une_seule_phrase_a_la_fin(self):
        self.ecrire_table()
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual(sortie.count("export incomplet"), 1)
        self.assertEqual(self.magasin.passages, [])

    def test_cles_conflits_et_appuis_de_l_ancienne_table_ignorees_a_la_lecture(self):
        """`charger_table` ne sert plus qu'à check-teams et migrate-teams : ni l'export ni diagnose ne la lisent."""
        (self.ws / "Flux-Lab" / "equipes-assets.yaml").write_text(
            "equipes: {'1': Equipe A, '2': Equipe B, '3': Equipe C}\nconflits: {'4': [D, E]}\nappuis: {'1': 1}\n", encoding="utf-8")
        self.assertEqual(ex.charger_table(), {"1": "Equipe A", "2": "Equipe B", "3": "Equipe C"})

    def test_diagnostic_accepte_les_identifiants_quand_le_catalogue_existe(self):
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1, sortie)                                       # sans source
        self.ecrire_table()
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("sources d'équipes : référentiel 0 identifiants, catalogue 3 identifiants", sortie)
        self.assertNotIn("Equipe", sortie)

    def test_sans_source_l_export_s_arrete_et_donne_la_structure_des_deux_fichiers(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertEqual(self.magasin.passages, [])
        self.assertIn("aucune source d'équipes : compléter jira_team_ids du référentiel et du catalogue", sortie)
        self.assertIn("organisation.yaml", sortie)
        self.assertIn("equipes-jira.yaml", sortie)
        self.assertIn("jira_team_ids", sortie)
        self.assertIn("`diagnose`", sortie)
        self.assertNotIn("teams-table", sortie)
        self.assertNotIn("table-equipes", sortie)
        code, sortie = self.lancer("export", "--language", "en")
        self.assertIn("no team source: fill jira_team_ids in the referential and the catalogue", sortie)

    def test_l_ancienne_table_illisible_n_arrete_rien_elle_n_est_pas_lue(self):
        (self.ws / "Flux-Lab" / "equipes-assets.yaml").write_text("equipes: [pas, un, dictionnaire", encoding="utf-8")
        self.ecrire_table()
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("illisible", sortie)

    def test_regles_deny_de_la_table_et_de_la_commande(self):
        reglages = json.loads((TOOLS.parent / ".claude" / "settings.json").read_text(encoding="utf-8"))
        deny = reglages["permissions"]["deny"]
        self.assertIn("Bash(uv run tools/export_jira_api.py table-equipes*)", deny)     # sous-commande retirée, règle gardée
        self.assertIn("Bash(uv run *export_jira_api.py teams-table*)", deny)
        self.assertIn("Read(./Flux-Lab/equipes-assets.yaml)", deny)


class SousCommandesRetirees(Base):
    """teams-table et compare n'existent plus : l'appel est refusé (code 2, sans traceback) avec la voie à suivre."""

    def test_compare_refuse_avec_la_voie_api(self):
        for argv in (["compare", "m.csv", "a.csv"], ["compare", "m.csv", "a.csv", "--tolerance", "2"], ["compare"]):
            code, sortie = self.lancer(*argv)
            self.assertEqual(code, 2, sortie)
            self.assertIn("la sous-commande compare est retirée", sortie)
            self.assertIn("export_jira_api.py export", sortie)
            self.assertIn("flow_compare.py", sortie)
            self.assertNotIn("Traceback", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_teams_table_refuse_avec_la_voie_a_la_main(self):
        for argv in (["teams-table", "m1.csv", "m2.csv"], ["teams-table"]):
            code, sortie = self.lancer(*argv)
            self.assertEqual(code, 2, sortie)
            self.assertIn("la sous-commande teams-table est retirée", sortie)
            self.assertIn("equipes-jira.yaml", sortie)
            self.assertIn("à la main", sortie)
            self.assertIn("liste les identifiants à ajouter", sortie)
            self.assertNotIn("Traceback", sortie)
        self.assertEqual(self.faux.requetes, [])
        self.assertFalse((self.ws / "Flux-Lab" / "equipes-assets.yaml").exists())

    def test_refus_en_anglais(self):
        code, sortie = self.lancer("compare", "a", "b", "--language", "en")
        self.assertEqual(code, 2)
        self.assertIn("the compare subcommand is retired", sortie)
        code, sortie = self.lancer("teams-table", "--language", "en")
        self.assertEqual(code, 2)
        self.assertIn("the teams-table subcommand is retired", sortie)

    def test_option_inconnue_toujours_refusee_ailleurs(self):
        code, _ = self.lancer("export", "--tolerance", "2")
        self.assertEqual(code, 2)

    def test_aide_ne_liste_pas_les_sous_commandes_retirees(self):
        code, sortie = self.lancer("--help")
        self.assertEqual(code, 0)
        # review-teams : change names-and-team-review ; extract-teams : change team-names-readable (tâche 3.2)
        self.assertIn("{diagnose,fields,export,check-teams,migrate-teams,review-teams,extract-teams}", sortie)
        self.assertNotRegex(sortie, r"(?m)^\s{2,}(compare|teams-table)\b")


class ChampEquipeIllisible(Base):
    """Le champ d'équipe renvoie un identifiant d'objet Assets : rien n'est deviné, rien n'est écrit."""

    def setUp(self):
        super().setUp()
        for cle, t in self.faux.tickets.items():
            t[CHAMP] = [{"workspaceId": "ws-secret", "id": "w:123", "objectId": "123"}]

    def test_export_s_arrete_sans_rien_ecrire(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))
        self.assertIn("ne renvoie pas le libellé", sortie)
        self.assertIn("aucune source d'équipes : compléter jira_team_ids du référentiel et du catalogue", sortie)
        self.assertIn("objet {id, objectId, workspaceId}", sortie)              # forme, jamais les valeurs
        for valeur in ("ws-secret", "w:123", '"123"', "ABC-"):
            self.assertNotIn(valeur, sortie)

    def test_diagnostic_dit_la_forme_et_les_options(self):
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1)
        self.assertIn("Libellés exploitables : non", sortie)
        self.assertIn("objet {id, objectId, workspaceId} 4", sortie)
        self.assertNotIn("ws-secret", sortie)

    def test_identifiant_seul_n_est_pas_un_libelle(self):
        for valeur in ("12345", "0a1b2c3d-1111-2222-3333-444455556666", [{"value": "42"}]):
            self.assertIsNone(ex.libelles(valeur), valeur)
        self.assertEqual(ex.libelles([{"value": "Equipe A"}, {"name": "Equipe B"}, "Equipe C"]),
                         ["Equipe A", "Equipe B", "Equipe C"])


class Diagnostic(Base):
    def test_libelles_exploitables_sans_aucune_valeur(self):
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Libellés exploitables : oui", sortie)
        self.assertIn("liste de objet {value}", sortie)
        self.assertNotIn("Equipe", sortie)
        self.assertEqual(len(self.faux.requetes), 1)                           # une seule page
        self.assertEqual(self.faux.requetes[0]["fields"], [CHAMP])

    def test_champ_absent_des_reponses(self):
        self.ecrire_reglages("jql_export: project = ABC\nexport_team_field: customfield_99999\n")
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1)
        self.assertIn("absent des réponses", sortie)


class FuseauExport(Base):
    def test_dates_a_l_heure_de_paris_par_defaut(self):
        paris = ex.fuseau_export({})
        self.assertEqual(ex.instant_api("2026-07-01T06:30:00.000+0000", paris).isoformat(), "2026-07-01T08:30:00+02:00")    # été
        self.assertEqual(ex.instant_api("2026-01-15T23:30:00.000+0000", paris).isoformat(), "2026-01-16T00:30:00+01:00")    # hiver
        self.assertEqual(ex.instant_api("2026-07-01T09:00:00.000-0500", paris).isoformat(), "2026-07-01T16:00:00+02:00")

    def test_fuseau_reglable_et_invalide(self):
        self.assertEqual(ex.instant_api("2026-07-01T06:30:00.000+0000", ex.fuseau_export({"export_fuseau": "UTC"})).isoformat(),
                         "2026-07-01T06:30:00+00:00")
        with self.assertRaises(ex.Arret):
            ex.fuseau_export({"export_fuseau": "Mars/Olympus"})

    def test_instant_a_la_minute_et_dates_illisibles(self):
        paris = ex.fuseau_export({})
        self.assertEqual(ex.instant_api("2026-03-01T00:05:30.123+0000", paris).isoformat(), "2026-03-01T01:05:00+01:00")
        self.assertIsNone(ex.instant_api(None, paris))
        self.assertIsNone(ex.instant_api("pas une date", paris))

    def test_export_enregistre_les_dates_a_l_heure_de_paris(self):
        self.faux.tickets = {"ABC-1": champs("Story", "Open", "To Do", "2026-07-01T06:30:00.000+0000")}
        self.assertEqual(self.exporter()["ABC-1"]["created_at"].isoformat(), "2026-07-01T08:30:00+02:00")
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_timezone: UTC\n")
        self.magasin = MagasinMemoire()          # un magasin neuf : le même instant ne s'écrit pas deux fois dans le même magasin
        self.assertEqual(self.exporter()["ABC-1"]["created_at"].isoformat(), "2026-07-01T06:30:00+00:00")

    def test_fuseau_invalide_arrete_l_export_avant_jira(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_timezone: Mars/X\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertIn("export_timezone", sortie)
        self.assertEqual((self.faux.requetes, self.magasin.passages), ([], []))


class RequetesNommees(Base):
    def reglages(self, extra=""):
        self.ecrire_reglages(f"export_team_field: {CHAMP}\n{extra}")

    def test_sans_requete_execute_toutes_les_requetes_dans_un_seul_passage(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = AAA", "project = BBB"])
        self.assertIn("[a] Tickets : 4", sortie)
        self.assertIn("[b] Tickets : 4", sortie)
        self.assertEqual(self.magasin.passages, [{"genre": "export", "nb_requetes": 2, "toutes": True}])     # un passage, aucun nom
        self.assertEqual(self.magasin.cles_vues(), {"ABC-1", "ABC-2", "ABC-3", "ABC-9"})                   # même fuseau, mêmes équipes
        self.assertEqual(len(self.magasin.instantanes), 4)

    def test_requete_nommee_seule_ne_compte_pas_comme_jeu_complet(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--query", "b")
        self.assertEqual(code, 0, sortie)
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = BBB"])
        self.assertEqual(self.magasin.passages, [{"genre": "export", "nb_requetes": 1, "toutes": False}])

    def test_nom_inconnu_arrete_avec_la_liste_sans_appeler_jira(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--query", "c")
        self.assertEqual(code, 1)
        self.assertIn("Disponibles : a, b", sortie)
        self.assertEqual(self.faux.requetes, [])
        self.assertEqual(self.magasin.passages, [])

    def test_requete_sans_jql_exports(self):
        code, sortie = self.lancer("export", "--query", "a")
        self.assertEqual(code, 1)
        self.assertIn("jql_exports", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_jql_export_seul_comme_avant(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.passages, [{"genre": "export", "nb_requetes": 1, "toutes": True}])

    def test_jql_exports_prime_sur_jql_export(self):
        self.reglages("jql_export: project = ZZZ\njql_exports:\n  a: project = AAA\n")
        self.lancer("export")
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = AAA"])

    def test_option_sortie_retiree_avec_une_ou_plusieurs_requetes(self):
        """--output est retirée (database-only, D1) : code 2 et la phrase de design D6, avant tout appel à Jira et toute connexion."""
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        for argv in (("export", "--output", str(self.ws / "x.csv")), ("export", "--query", "a", "--output", str(self.ws / "x.csv"))):
            code, sortie = self.lancer(*argv)
            self.assertEqual(code, 2, sortie)
            self.assertIn("--output est retirée : l'export écrit dans la base", sortie)
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"), "--language", "en")
        self.assertEqual(code, 2, sortie)
        self.assertIn("--output is retired: the export writes into the database", sortie)
        self.assertEqual((self.faux.requetes, self.magasin.passages), ([], []))
        self.assertFalse((self.ws / "x.csv").exists())

    def test_noms_et_requetes_invalides(self):
        for extra in ("jql_exports:\n  'a b': project = AAA\n", "jql_exports:\n  a: ''\n", "jql_exports: [x]\n"):
            self.reglages(extra)
            code, _ = self.lancer("export")
            self.assertEqual(code, 1, extra)
        self.assertEqual(self.faux.requetes, [])

    def test_diagnostic_utilise_la_premiere_requete(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        self.lancer("diagnose")
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = AAA"])


class ChampVerification(Base):
    """Réglages export_verification_field et export_verification_header : aucun lecteur ne lit la colonne (database-only, Q7 (b)). Le
    champ n'est plus demandé à Jira, rien n'en est enregistré, et les anciens réglages restent acceptés."""
    VERIF = "customfield_10009"

    def setUp(self):
        super().setUp()
        tickets = copy.deepcopy(TICKETS)
        tickets["ABC-1"][self.VERIF] = {"value": "Yes"}
        tickets["ABC-2"][self.VERIF] = True
        self.faux.tickets = tickets
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             f"export_verification_field: {self.VERIF}\nexport_verification_header: Vérification requise\n")

    def test_le_champ_n_est_pas_demande_et_rien_n_en_est_enregistre(self):
        instantanes = self.exporter()
        self.assertNotIn(self.VERIF, {f for r in self.faux.requetes for f in r["fields"]})
        self.assertNotIn("Yes", repr(list(instantanes.values())))

    def test_identifiant_invalide_n_arrete_plus_rien(self):
        self.ecrire_reglages("jql_export: project = ABC\nexport_verification_field: pas un identifiant\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Vérification", sortie)


class ColonneUpdated(Base):
    """La date de mise à jour est toujours demandée et enregistrée dans chaque instantané, dans le fuseau de l'export."""

    def setUp(self):
        super().setUp()
        self.faux.tickets["ABC-1"]["updated"] = "2026-07-11T23:30:00.000+0000"
        self.faux.tickets["ABC-2"]["updated"] = "2026-08-04T10:00:00.000+0200"

    def test_demandee_a_jira_et_enregistree_comme_instant(self):
        instantanes = self.exporter()
        self.assertIn("updated", self.faux.requetes[0]["fields"])
        self.assertEqual({cle: i["updated_at"].isoformat() for cle, i in instantanes.items()},
                         {"ABC-1": "2026-07-12T01:30:00+02:00", "ABC-2": "2026-08-04T10:00:00+02:00",
                          "ABC-3": "2026-09-01T16:45:00+02:00", "ABC-9": "2026-01-12T07:05:00+01:00"})

    def test_fuseau_du_reglage(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_timezone: UTC\n")
        self.assertEqual(self.exporter()["ABC-1"]["updated_at"].isoformat(), "2026-07-11T23:30:00+00:00")

    def test_ticket_sans_date_de_mise_a_jour_n_a_pas_d_instantane(self):
        del self.faux.tickets["ABC-3"]["updated"]
        instantanes = self.exporter()
        self.assertNotIn("ABC-3", instantanes)
        self.assertIn("ABC-3", self.magasin.cles_vues())          # lu, donc vu


class ChampPoints(Base):
    """Réglage export_points_field : les story points de chaque instantané."""
    PTS = "customfield_10003"

    def setUp(self):
        super().setUp()
        tickets = copy.deepcopy(TICKETS)
        tickets["ABC-1"][self.PTS] = 5                                   # entier
        tickets["ABC-2"][self.PTS] = 2.5                                 # décimal
        tickets["ABC-3"][self.PTS] = None
        tickets["ABC-9"][self.PTS] = "beaucoup"                          # non numérique
        self.faux.tickets = tickets

    def reglages(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             f"export_points_field: {self.PTS}\n")

    def points(self, instantanes: dict) -> dict:
        return {cle: (None if i["story_points"] is None else str(i["story_points"])) for cle, i in instantanes.items()}

    def test_sans_reglage_aucun_point_et_le_champ_n_est_pas_demande(self):
        self.assertEqual(set(self.points(self.exporter()).values()), {None})
        self.assertNotIn(self.PTS, self.faux.requetes[0]["fields"])

    def test_points_enregistres_et_champ_demande(self):
        self.reglages()
        points = self.points(self.exporter())
        self.assertIn(self.PTS, self.faux.requetes[0]["fields"])
        self.assertEqual(points, {"ABC-1": "5", "ABC-2": "2.5", "ABC-3": None, "ABC-9": None})

    def test_champ_absent_de_la_reponse_donne_des_points_nuls(self):
        del self.faux.tickets["ABC-3"][self.PTS]
        self.reglages()
        self.assertIsNone(self.points(self.exporter())["ABC-3"])

    def test_booleen_non_numerique(self):
        self.faux.tickets["ABC-3"][self.PTS] = True
        self.reglages()
        self.assertIsNone(self.points(self.exporter())["ABC-3"])

    def test_sortie_sans_valeur_ni_cle(self):
        self.reglages()
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Story points : 2 ticket(s) renseigné(s) sur 4", sortie)
        self.assertIn("1 valeur(s) non numérique(s)", sortie)
        for interdit in ("2.5", "beaucoup", "ABC-", "Titre secret"):
            self.assertNotIn(interdit, sortie)

    def test_sortie_en_anglais(self):
        self.reglages()
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("2 ticket(s) filled out of 4", sortie)
        self.assertIn("1 non-numeric value(s)", sortie)

    def test_identifiant_invalide_arrete_avant_jira(self):
        self.ecrire_reglages("jql_export: project = ABC\nexport_points_field: pas un identifiant\n")
        code, sortie = self.lancer("export")
        self.assertNotEqual(code, 0)
        self.assertIn("export_points_field doit être un identifiant", sortie)
        self.assertEqual(self.faux.requetes, [])


class ListeDeChampsPoints(Base):
    """export_points_field : un identifiant ou une liste ; la valeur prend le premier champ non vide, dans l'ordre de la liste."""
    A, B = "customfield_10003", "customfield_10004"

    def setUp(self):
        super().setUp()
        tickets = copy.deepcopy(TICKETS)
        # ABC-1 : seul A ; ABC-2 : seul B ; ABC-3 : les deux, valeurs égales (3 et 3.0) ; ABC-9 : les deux, valeurs différentes
        tickets["ABC-1"].update({self.A: 5, self.B: None})
        tickets["ABC-2"].update({self.A: None, self.B: 8})
        tickets["ABC-3"].update({self.A: 3, self.B: 3.0})
        tickets["ABC-9"].update({self.A: 13, self.B: "beaucoup"})
        self.faux.tickets = tickets

    def reglages(self, liste: str):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_points_field: {liste}\n")

    def points(self, instantanes: dict) -> dict:
        return {cle: (None if i["story_points"] is None else str(i["story_points"])) for cle, i in instantanes.items()}

    def test_premiere_valeur_non_vide_dans_l_ordre_de_la_liste(self):
        self.reglages(f"[{self.A}, {self.B}]")
        self.assertEqual(self.points(self.exporter()), {"ABC-1": "5", "ABC-2": "8", "ABC-3": "3", "ABC-9": "13"})
        self.assertIn(self.A, self.faux.requetes[0]["fields"])
        self.assertIn(self.B, self.faux.requetes[0]["fields"])

    def test_l_ordre_de_la_liste_decide(self):
        self.faux.tickets["ABC-3"].update({self.A: 3, self.B: 4})
        self.reglages(f"[{self.B}, {self.A}]")
        points = self.points(self.exporter())
        self.assertEqual(points["ABC-3"], "4")
        self.assertEqual(points["ABC-1"], "5")

    def test_un_seul_identifiant_comme_avant(self):
        self.reglages(self.A)
        self.assertEqual(self.points(self.exporter()), {"ABC-1": "5", "ABC-2": None, "ABC-3": "3", "ABC-9": "13"})
        self.assertNotIn(self.B, self.faux.requetes[0]["fields"])

    def test_liste_d_un_element_et_doublon(self):
        self.reglages(f"[{self.A}, {self.A}]")
        points = self.points(self.exporter())
        self.assertEqual(self.faux.requetes[0]["fields"].count(self.A), 1)
        self.assertEqual(points["ABC-1"], "5")

    def test_sortie_par_identifiant_sans_valeur_ni_cle(self):
        self.faux.tickets["ABC-3"].update({self.A: 3, self.B: 4})          # désaccord sur ABC-3 ; ABC-9 : B est non numérique
        self.reglages(f"[{self.A}, {self.B}]")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertIn(f"Champ {self.A} : renseigné pour 3 ticket(s) sur 4 ; 1 ticket(s) où un autre champ de points est renseigné "
                      f"avec une valeur différente", sortie)
        self.assertIn(f"Champ {self.B} : renseigné pour 2 ticket(s) sur 4 ; 1 ticket(s) où un autre champ", sortie)
        self.assertIn("Story points : 4 ticket(s) renseigné(s) sur 4", sortie)
        self.assertIn("1 valeur(s) non numérique(s)", sortie)
        for interdit in ("beaucoup", "ABC-", "Titre secret", ": 13", " 13 "):
            self.assertNotIn(interdit, sortie)
        en = self.lancer("export", "--language", "en")[1]
        self.assertIn(f"Field {self.A}: filled for 3 ticket(s) out of 4; 1 ticket(s) where another points field", en)

    def test_identifiant_invalide_dans_la_liste_arrete_avant_jira(self):
        self.reglages(f"[{self.A}, pas un identifiant]")
        code, sortie = self.lancer("export")
        self.assertNotEqual(code, 0)
        self.assertIn("export_points_field doit être un identifiant", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_reglage_lu_comme_liste_ou_comme_texte(self):
        self.assertEqual(ex.reglage_points({"export_points_field": f"{self.A}"}), [self.A])
        self.assertEqual(ex.reglage_points({"export_points_field": [self.A, self.B]}), [self.A, self.B])
        self.assertEqual(ex.reglage_points({}), [])
        self.assertEqual(ex.reglage_points({"export_points_field": []}), [])


class NouveauxComportements(Base):
    """Exigences du change database-only : lecture complète à chaque passage, --full, aucune recherche sur la date de mise à jour,
    passage unique et rien d'enregistré en cas d'erreur (spec jira-flow-export)."""

    def test_second_passage_relit_tout_sans_condition_sur_la_date_de_mise_a_jour(self):
        self.exporter()
        self.faux.tickets["ABC-2"]["updated"] = "2026-10-01T10:00:00.000+0200"          # un ticket modifié entre les deux passages
        self.exporter()
        self.assertEqual(len(self.faux.requetes), 2)
        for requete in self.faux.requetes:
            self.assertEqual(requete["jql"], "project = ABC")                          # ni « updated », ni instant d'un passage antérieur
            self.assertNotIn("updated", requete["jql"].lower())
        self.assertEqual(len(self.magasin.passages), 2)
        self.assertEqual(self.magasin.cles_vues(2), {"ABC-1", "ABC-2", "ABC-3", "ABC-9"})            # tout est vu à chaque passage
        self.assertEqual(len(self.magasin.instantanes_de("ABC-2")), 2)                              # le ticket modifié a un nouvel instantané
        self.assertEqual(len(self.magasin.instantanes_de("ABC-1")), 1)

    def test_option_full_accepte_et_sans_effet(self):
        code_a, sortie_a = self.lancer("export", "--full")
        code_b, sortie_b = self.lancer("export")
        self.assertEqual((code_a, code_b), (0, 0), sortie_a + sortie_b)
        sans_comptes = lambda sortie: [l for l in sortie.splitlines() if not l.startswith("couche brute")]       # les comptes de la base changent
        self.assertEqual(sans_comptes(sortie_a), sans_comptes(sortie_b))
        self.assertEqual(self.faux.requetes[0], self.faux.requetes[1])
        self.assertNotIn("incrémental", sortie_a)
        self.assertNotIn("incremental", sortie_a)

    def test_passage_en_echec_n_enregistre_rien_et_le_suivant_relit_tout(self):
        self.magasin.echec_ecriture = RuntimeError("base en panne")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1, sortie)
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))
        self.assertIn("Erreur inattendue (RuntimeError)", sortie)
        self.assertNotIn("base en panne", sortie)
        self.magasin.echec_ecriture = None
        self.exporter()
        self.assertEqual(self.magasin.cles_vues(1), {"ABC-1", "ABC-2", "ABC-3", "ABC-9"})

    def test_erreur_de_jira_apres_la_premiere_page_n_enregistre_rien(self):
        self.faux.taille_page = 1
        vrai = hj.Client.json
        appels = []

        def json_en_echec(client, methode, chemin, **kwargs):
            appels.append(chemin)
            if len(appels) == 2:
                raise hj.ErreurHTTP(500)
            return vrai(client, methode, chemin, **kwargs)

        with mock.patch.object(hj.Client, "json", json_en_echec):
            code, sortie = self.lancer("export")
        self.assertEqual(code, 1, sortie)
        self.assertEqual(sortie.strip().splitlines()[-1], "HTTP 500")              # seul le code est affiché
        self.assertEqual((self.magasin.passages, self.magasin.visites, self.magasin.instantanes), ([], [], []))

    def test_base_injoignable_arrete_avant_tout_appel_a_jira(self):
        def refuse():
            raise ex.Arret(ex.t("raw_db_unreachable"))

        with mock.patch.object(ex, "ouvrir_magasin", refuse):
            code, sortie = self.lancer("export")
        self.assertEqual(code, 1, sortie)
        self.assertEqual(self.faux.requetes, [])
        self.assertIn("base injoignable", sortie)

    def test_aucun_fichier_de_donnees_dans_le_dossier_des_flux(self):
        self.exporter()
        self.assertEqual(sorted(p.name for p in (self.ws / "Flux-Lab").iterdir()), ["flux.yaml"])

    def test_champs_demandes_sans_etiquette_ni_version(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             "declared_labels:\n  ready: {prefix: x, labels: [x-ready]}\n")
        self.exporter()
        demandes = {f for r in self.faux.requetes for f in r["fields"]}
        self.assertTrue({"labels", "fixVersions"}.isdisjoint(demandes))


class TypeDesEquipes(Base):
    """Complément « Complement: team type column » : le type de chaque équipe rencontrée s'écrit dans la transaction de la couche brute."""

    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        for cle, ids in (("ABC-1", [1]), ("ABC-2", [2]), ("ABC-3", [3]), ("ABC-4", [9])):
            ticket = champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200")
            ticket[CHAMP] = [objet(i) for i in ids]
            self.faux.tickets[cle] = ticket
        flux = self.ws / "Flux-Lab"
        (flux / "equipes-jira.yaml").write_text(
            "teams:\n  - name: Alpha\n    jira_team_ids: ['1']\n    type: Development Team\n"
            "  - name: Beta\n    jira_team_ids: ['2']\n    type: Verification Team\n"
            "  - name: Gamma\n    jira_team_ids: ['3']\n", encoding="utf-8")
        (flux / "organisation.yaml").write_text(
            "source_date: 2026-10-01\nsites: [Site 1]\ndepartments:\n  - name: Departement 1\n    site: Site 1\n    headcount: 10\n"
            "    teams: [Beta, Delta]\nteams:\n  - name: Beta\n    headcount: 5\n    jira_team_ids: ['2']\n"
            "  - name: Delta\n    headcount: 5\n    jira_team_ids: ['3']\n    type: Product Management Team\n",
            encoding="utf-8")

    def test_types_du_catalogue_et_du_referentiel_et_type_nul_pour_un_identifiant_inconnu(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.types, {"Alpha": "Development Team", "Beta": "Verification Team",
                                              "Delta": "Product Management Team", "(équipe inconnue)": None})
        self.assertEqual(self.magasin.sans_type, 1)
        self.assertIn("équipes sans type : 1", sortie)
        for interdit in ("Alpha", "Beta", "Delta", "Gamma", "Development Team"):
            self.assertNotIn(interdit, sortie)

    def test_mise_a_jour_seulement_d_un_type_qui_change(self):
        self.lancer("export")
        premieres = list(self.magasin.ecritures_de_type)
        (self.ws / "Flux-Lab" / "equipes-jira.yaml").write_text(
            "teams:\n  - name: Alpha\n    jira_team_ids: ['1']\n    type: Other Team\n"
            "  - name: Beta\n    jira_team_ids: ['2']\n    type: Verification Team\n"
            "  - name: Gamma\n    jira_team_ids: ['3']\n", encoding="utf-8")
        self.lancer("export")
        self.assertEqual(self.magasin.ecritures_de_type[len(premieres):], ["Alpha"])
        self.assertEqual(self.magasin.types["Alpha"], "Other Team")

    def test_sortie_en_anglais(self):
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("teams without a type: 1", sortie)


if __name__ == "__main__":
    unittest.main()
