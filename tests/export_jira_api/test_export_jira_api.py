"""Tests de export_jira_api.py : un faux serveur HTTP local, des données inventées, un faux jeton.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v

Aucun appel au vrai Jira. Les tests vérifient aussi que flux_jira.py et dependencies_jira.py lisent le CSV de l'API
sans modification, et que les sous-commandes retirées (teams-table, compare) renvoient vers la voie à suivre.
"""
import base64
import contextlib
import copy
import csv
import datetime as dt
import io
import json
import os
import subprocess
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

JETON = "test-token-000"
EMAIL = "utilisateur@example.org"
CHAMP = "customfield_10001"
AUJOURDHUI = "2026-10-04"


def champs(type_, etat, categorie, cree, resolu=None, motif=None, debut=None, parent=None, equipes=(), liens=()):
    return {"issuetype": {"name": type_}, "status": {"name": etat, "statusCategory": {"name": categorie}},
            "created": cree, "resolutiondate": resolu, "resolution": {"name": motif} if motif else None,
            "statuscategorychangedate": debut or resolu or cree, "parent": {"key": parent} if parent else None,
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

        def do_GET(self):
            if self.headers.get("Authorization") != faux.attendu:
                return self.repondre(401)
            faux.appels_get.append(self.path)
            if self.path != "/rest/api/3/field":
                return self.repondre(404)
            return self.repondre(200, faux.champs)

        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
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
        for p in (mock.patch.object(hj, "WORKSPACE", self.ws), mock.patch.object(hj, "FLUX_DIR", flux),
                  mock.patch.object(hj, "CONFIG_FILE", flux / "flux.yaml"),
                  mock.patch.object(hj, "lire_jeton", lambda: JETON),
                  mock.patch.object(hj, "API_ATLASSIAN", self.url), mock.patch.object(hj, "PAUSE", 0),
                  mock.patch.object(hj, "_JETON", None)):
            p.start()
            self.addCleanup(p.stop)
        self.ecrire_reglages()

    def ecrire_reglages(self, extra: str = None):
        extra = f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n" if extra is None else extra
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(
            f"jira_site: {self.url}\njira_email: {EMAIL}\njira_token_type: classic\n{extra}", encoding="utf-8")

    def lancer(self, *argv):
        sortie = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            try:
                ex.main(list(argv))
            except SystemExit as s:
                code = s.code or 0
        return code, sortie.getvalue()

    def exporter(self, nom="api.csv") -> Path:
        chemin = self.ws / nom
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        return chemin

    def lignes(self, chemin: Path) -> list[list[str]]:
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f))


class AnciensNoms(Base):
    """Anciens noms d'options et de réglages refusés avec le nom actuel, anciens noms de sous-commandes refusés."""

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        for args, ancien, nouveau in ((("fields", "--cherche", "team"), "--cherche", "--search"),
                                      (("export", "--sortie", str(self.ws / "x.csv")), "--sortie", "--output")):
            code, sortie = self.lancer(*args)
            self.assertEqual(code, 2, sortie)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau} »", sortie)
        self.assertFalse((self.ws / "x.csv").exists())
        self.assertEqual(self.faux.requetes, [])

    def test_anciens_noms_de_reglages_refuses_avec_le_nom_actuel(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_champ_equipe: {CHAMP}\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertNotEqual(code, 0)
        self.assertIn("« export_champ_equipe » n'existe plus ; utiliser « export_team_field »", str(code) + sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("diagnostic", "champs", "table-equipes", "comparer"):
            code, _ = self.lancer(ancien)
            self.assertEqual(code, 2, ancien)
        self.assertEqual(self.faux.requetes, [])


class Export(Base):
    def test_csv_au_format_de_l_export_jira(self):
        lignes = self.lignes(self.exporter())
        entete = lignes[0]
        self.assertEqual(entete[:9], ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved",
                                      "Resolution", "Status Category Changed", "Parent key"])
        self.assertEqual(entete.count("Team"), 2)                                    # deux équipes au plus sur un ticket
        self.assertEqual(entete.count("Outward issue link (Blocks)"), 2)             # colonnes répétées
        self.assertEqual(entete.count("Inward issue link (Blocks)"), 1)
        self.assertEqual(entete.count("Inward issue link (Relates)"), 1)
        self.assertEqual(entete.count("Outward issue link (Relates)"), 1)
        par_cle = {l[0]: dict(zip(range(len(l)), l)) for l in lignes[1:]}
        assert set(par_cle) == {"ABC-1", "ABC-2", "ABC-3", "ABC-9"}
        t1 = lignes[1]
        self.assertEqual(t1[:9], ["ABC-1", "Story", "Closed", "Done", "01/Jun/2026 08:00", "10/Jul/2026 10:30", "Done",
                                  "10/Jul/2026 10:30", "ABC-9"])
        i = entete.index("Team")
        self.assertEqual(t1[i:i + 2], ["Equipe A", "Equipe B"])
        j = entete.index("Outward issue link (Blocks)")
        self.assertEqual(t1[j:j + 2], ["ABC-2", "ABC-3"])
        self.assertEqual(lignes[3][i:i + 2], ["", ""])                               # ABC-3 : aucune équipe
        self.assertEqual(lignes[4][4], "12/Jan/2026 07:05")                          # heure du décalage d'origine

    def test_pagination_complete(self):
        self.faux.taille_page = 1
        lignes = self.lignes(self.exporter())
        self.assertEqual(len(lignes) - 1, 4)
        self.assertEqual(len(self.faux.requetes), 4)
        self.assertEqual(self.faux.requetes[1]["nextPageToken"], "1")

    def test_jeton_de_page_qui_se_repete_ne_boucle_pas(self):
        self.faux.taille_page = 2
        self.faux.jeton_repete = True
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.faux.requetes), 2)

    def test_aucun_titre_demande_a_jira_et_rien_de_sensible_en_sortie(self):
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        demandes = {f for r in self.faux.requetes for f in r["fields"]}
        self.assertNotIn("summary", demandes)
        for interdit in ("assignee", "reporter", "creator", "description"):
            self.assertNotIn(interdit, demandes)
        for texte in (sortie, chemin.read_text(encoding="utf-8-sig")):
            self.assertNotIn("Titre secret", texte)
            self.assertNotIn(JETON, texte)
        for texte in (sortie,):
            self.assertNotIn("ABC-", texte)
            self.assertNotIn("Equipe", texte)
            self.assertNotIn(self.url, texte)
            self.assertNotIn("project = ABC", texte)
        self.assertEqual(oct(chemin.stat().st_mode & 0o777), "0o600")
        self.assertIn("Tickets : 4 ; pages : 1", sortie)

    def test_sans_champ_d_equipe_pas_de_colonne_d_equipe(self):
        self.ecrire_reglages("jql_export: project = ABC\n")
        lignes = self.lignes(self.exporter())
        self.assertNotIn("Team", lignes[0])
        self.assertNotIn(CHAMP, {f for r in self.faux.requetes for f in r["fields"]})

    def test_entete_d_equipe_reglable(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             "export_team_header: '[G] Team/s (label)'\n")
        self.assertIn("[G] Team/s (label)", self.lignes(self.exporter())[0])

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


class TableEquipes(Base):
    """Champ d'équipe renvoyé en objets Assets : la table identifiant -> libellé (equipes-assets.yaml) s'écrit à la main."""

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

    def ecrire_table(self, contenu: str = "equipes: {'1': Equipe A, '2': Equipe B, '3': Equipe C}\n") -> Path:
        chemin = self.ws / "Flux-Lab" / "equipes-assets.yaml"
        chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def test_export_traduit_par_la_table_une_colonne_par_equipe(self):
        self.ecrire_table()
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        lignes = self.lignes(chemin)
        entete = lignes[0]
        self.assertEqual(entete.count("Team"), 2)
        i = entete.index("Team")
        equipes = {l[0]: l[i:i + 2] for l in lignes[1:]}
        for cle, (_, attendu) in self.EQUIPES.items():
            self.assertEqual(equipes[cle], attendu + [""] * (2 - len(attendu)), cle)
        self.assertIn("Équipes inconnues : 3 identifiant(s) distinct(s) absent(s) de la table, 2 ticket(s) concerné(s)", sortie)
        for interdit in ("Equipe", "ABC-", "ws-secret"):
            self.assertNotIn(interdit, sortie)

    def test_export_liste_les_identifiants_inconnus_sans_libelle_ni_cle(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("Complétez equipes-assets.yaml (equipes: identifiant -> libellé) avec ces identifiants : 4 ; 5 ; 6.", sortie)
        for interdit in ("Equipe", "ABC-", "ws-secret", "workspace", "teams-table", self.url, JETON):
            self.assertNotIn(interdit, sortie)

    def test_export_liste_les_identifiants_inconnus_en_anglais(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"), "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Complete equipes-assets.yaml (equipes: identifier -> label) with these identifiers: 4; 5; 6.", sortie)

    def test_table_complete_aucun_identifiant_a_lister(self):
        self.ecrire_table("equipes: {'1': A, '2': B, '3': C, '4': D, '5': E, '6': F}\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Complétez", sortie)
        self.assertNotIn("inconnues", sortie)

    def test_strict_teams_identifiant_inconnu_ecrit_le_fichier_puis_sort_avec_3(self):
        self.ecrire_table()
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--strict-teams", "--output", str(chemin))
        self.assertEqual(code, 3, sortie)
        self.assertTrue(chemin.exists())
        self.assertIn("Fichier écrit", sortie)
        self.assertTrue(sortie.rstrip().endswith("identifiants d'équipe inconnus : export incomplet"), sortie)
        for interdit in ("Equipe", "ABC-", "ws-secret"):
            self.assertNotIn(interdit, sortie.splitlines()[-1])

    def test_strict_teams_en_anglais(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--strict-teams", "--output", str(self.ws / "api.csv"), "--language", "en")
        self.assertEqual(code, 3, sortie)
        self.assertTrue(sortie.rstrip().endswith("unknown team identifiers: export incomplete"), sortie)

    def test_strict_teams_table_complete_sort_avec_0(self):
        self.ecrire_table("equipes: {'1': A, '2': B, '3': C, '4': D, '5': E, '6': F}\n")
        code, sortie = self.lancer("export", "--strict-teams", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("export incomplet", sortie)

    def test_sans_strict_teams_le_code_reste_0(self):
        self.ecrire_table()
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("export incomplet", sortie)

    def test_strict_teams_requetes_nommees_une_seule_phrase_a_la_fin(self):
        self.ecrire_table()
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual(sortie.count("export incomplet"), 1)
        self.assertEqual(sortie.count("Fichier écrit"), 2)

    def test_cles_conflits_et_appuis_ignorees_a_la_lecture(self):
        self.ecrire_table("equipes: {'1': Equipe A, '2': Equipe B, '3': Equipe C}\nconflits: {'4': [D, E]}\nappuis: {'1': 1}\n")
        self.assertEqual(ex.charger_table(), {"1": "Equipe A", "2": "Equipe B", "3": "Equipe C"})
        self.assertEqual(self.lancer("export", "--output", str(self.ws / "api.csv"))[0], 0)

    def test_diagnostic_accepte_les_identifiants_quand_la_table_existe(self):
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1, sortie)                                       # sans table
        self.ecrire_table()
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Libellés exploitables : par la table equipes-assets.yaml (3 identifiant(s))", sortie)
        self.assertNotIn("Equipe", sortie)

    def test_sans_table_l_export_s_arrete_et_dit_de_la_creer_a_la_main(self):
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 1)
        self.assertFalse(chemin.exists())
        self.assertIn("Créer à la main Flux-Lab/equipes-assets.yaml", sortie)
        self.assertIn("equipes: {identifiant: libellé}", sortie)
        self.assertIn("`diagnose`", sortie)
        self.assertNotIn("teams-table", sortie)
        self.assertNotIn("table-equipes", sortie)
        code, sortie = self.lancer("export", "--output", str(chemin), "--language", "en")
        self.assertIn("Create Flux-Lab/equipes-assets.yaml by hand", sortie)
        self.assertIn("equipes: {identifier: label}", sortie)

    def test_table_illisible_arrete_l_export(self):
        self.ecrire_table("equipes: [pas, un, dictionnaire")
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 1)
        self.assertIn("illisible", sortie)
        self.assertNotIn("teams-table", sortie)

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
            self.assertIn("equipes-assets.yaml", sortie)
            self.assertIn("à la main", sortie)
            self.assertIn("liste les identifiants inconnus", sortie)
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
        self.assertIn("{diagnose,fields,export}", sortie)
        self.assertNotRegex(sortie, r"(?m)^\s{2,}(compare|teams-table)\b")


class ChampEquipeIllisible(Base):
    """Le champ d'équipe renvoie un identifiant d'objet Assets : rien n'est deviné, rien n'est écrit."""

    def setUp(self):
        super().setUp()
        for cle, t in self.faux.tickets.items():
            t[CHAMP] = [{"workspaceId": "ws-secret", "id": "w:123", "objectId": "123"}]

    def test_export_s_arrete_sans_rien_ecrire(self):
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 1)
        self.assertFalse(chemin.exists())
        self.assertIn("ne renvoie pas le libellé", sortie)
        self.assertIn("Créer à la main Flux-Lab/equipes-assets.yaml", sortie)
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


MANUEL_ENTETE = ("Issue key,Summary,Issue Type,Status,Status Category,Created,Resolved,Resolution,"
                 "Status Category Changed,Parent key,Team,Team,Outward issue link (Blocks),Outward issue link (Blocks),"
                 "Inward issue link (Blocks),Inward issue link (Relates),Outward issue link (Relates)\n")
MANUEL_LIGNES = (
    "ABC-1,Titre secret,Story,Closed,Done,01/Jun/2026 08:00,10/Jul/2026 10:30,Done,10/Jul/2026 10:30,ABC-9,"
    "Equipe A,Equipe B,ABC-2,ABC-3,,ABC-3,\n"
    "ABC-2,Titre secret,Task,Implementation - Ongoing,In Progress,03/Aug/2026 09:15,,,03/Aug/2026 09:15,,Equipe A,,,,"
    "ABC-1,,\n"
    "ABC-3,Titre secret,Story,Open,To Do,01/Sep/2026 16:45,,,01/Sep/2026 16:45,,,,,,ABC-1,,ABC-1\n"
    "ABC-9,Titre secret,Epic,In Progress,In Progress,12/Jan/2026 07:05,,,12/Jan/2026 07:05,,Equipe B,,,,,,\n")


class LecturePar(Base):
    """flux_jira.py et dependencies_jira.py lisent le CSV de l'API sans modification, comme un export manuel."""

    def manuel(self) -> Path:
        chemin = self.ws / "manuel.csv"
        chemin.write_text(MANUEL_ENTETE + MANUEL_LIGNES, encoding="utf-8")
        return chemin

    def lancer_script(self, script: str, *args: str):
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        return subprocess.run(["uv", "run", str(TOOLS / script), *args], env=env, capture_output=True, text=True)

    def test_flux_jira_donne_le_meme_rapport_sur_les_deux_csv(self):
        api = self.exporter()
        rapports = {}
        for nom, chemin in (("manuel", self.manuel()), ("api", api)):
            r = self.lancer_script("flux_jira.py", "compute", str(chemin), "--name", nom, "--today", AUJOURDHUI,
                                   "--no-comparison")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            js = json.loads((self.ws / "Flux-Lab" / "rapports" / f"flux-{nom}-{AUJOURDHUI}.json").read_text(encoding="utf-8"))
            for cle in ("nom", "colonnes"):
                js.pop(cle, None)
            rapports[nom] = js
        self.assertEqual(rapports["manuel"], rapports["api"])
        self.assertEqual(rapports["api"]["termines"], 1)
        self.assertEqual(rapports["api"]["wip"], 2)           # ABC-2 (In Progress) et l'Epic ABC-9

    def test_flux_jira_lit_les_equipes_repetees_de_l_api(self):
        api = self.exporter()
        r = self.lancer_script("flux_jira.py", "compute", str(api), "--name", "eq", "--today", AUJOURDHUI,
                               "--no-comparison")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        js = json.loads((self.ws / "Flux-Lab" / "rapports" / f"flux-eq-{AUJOURDHUI}.json").read_text(encoding="utf-8"))
        self.assertEqual(js["tickets_plusieurs_equipes"]["total"], 1)

    def test_dependencies_jira_reconnait_les_liens_de_l_api(self):
        api = self.exporter()
        r = self.lancer_script("dependencies_jira.py", "diagnose", str(api))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Blocks", r.stdout)
        self.assertNotIn("ABC-", r.stdout)
        r = self.lancer_script("dependencies_jira.py", "compute", str(api), "--name", "api")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class FuseauExport(Base):
    def test_dates_a_l_heure_de_paris_par_defaut(self):
        self.assertEqual(ex.date_csv("2026-07-01T06:30:00.000+0000", ex.fuseau_export({})), "01/Jul/2026 08:30")   # été
        self.assertEqual(ex.date_csv("2026-01-15T23:30:00.000+0000", ex.fuseau_export({})), "16/Jan/2026 00:30")   # hiver
        self.assertEqual(ex.date_csv("2026-07-01T09:00:00.000-0500", ex.fuseau_export({})), "01/Jul/2026 16:00")

    def test_fuseau_reglable_et_invalide(self):
        self.assertEqual(ex.date_csv("2026-07-01T06:30:00.000+0000", ex.fuseau_export({"export_fuseau": "UTC"})),
                         "01/Jul/2026 06:30")
        with self.assertRaises(ex.Arret):
            ex.fuseau_export({"export_fuseau": "Mars/Olympus"})

    def test_export_ecrit_les_dates_a_l_heure_de_paris(self):
        self.faux.tickets = {"ABC-1": champs("Story", "Open", "To Do", "2026-07-01T06:30:00.000+0000")}
        ligne = self.lignes(self.exporter())[1]
        self.assertEqual(ligne[4], "01/Jul/2026 08:30")
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_timezone: UTC\n")
        self.assertEqual(self.lignes(self.exporter("utc.csv"))[1][4], "01/Jul/2026 06:30")

    def test_fuseau_invalide_arrete_l_export_avant_jira(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_timezone: Mars/X\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertEqual(code, 1)
        self.assertIn("export_timezone", sortie)
        self.assertFalse((self.ws / "x.csv").exists())


class RequetesNommees(Base):
    def reglages(self, extra=""):
        self.ecrire_reglages(f"export_team_field: {CHAMP}\n{extra}")

    def exports(self):
        return sorted(p.name for p in (self.ws / "Flux-Lab" / "exports").glob("*.csv")) \
            if (self.ws / "Flux-Lab" / "exports").exists() else []

    def test_sans_requete_execute_toutes_les_requetes_un_fichier_chacune(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        jour = ex.dt.date.today().isoformat()
        self.assertEqual(self.exports(), [f"api-a-{jour}.csv", f"api-b-{jour}.csv"])
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = AAA", "project = BBB"])
        self.assertIn("[a] Tickets : 4", sortie)
        self.assertIn("[b] Fichier écrit", sortie)
        un, deux = (self.lignes(self.ws / "Flux-Lab" / "exports" / f"api-{n}-{jour}.csv") for n in "ab")
        self.assertEqual(un, deux)                       # même format, même fuseau, mêmes équipes

    def test_requete_nommee_seule(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--query", "b")
        self.assertEqual(code, 0, sortie)
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = BBB"])
        self.assertEqual(len(self.exports()), 1)
        self.assertIn("-b-", self.exports()[0])

    def test_nom_inconnu_arrete_avec_la_liste_sans_appeler_jira(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--query", "c")
        self.assertEqual(code, 1)
        self.assertIn("Disponibles : a, b", sortie)
        self.assertEqual(self.faux.requetes, [])
        self.assertEqual(self.exports(), [])

    def test_requete_sans_jql_exports(self):
        code, sortie = self.lancer("export", "--query", "a")
        self.assertEqual(code, 1)
        self.assertIn("jql_exports", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_jql_export_seul_comme_avant(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.exports(), [f"api-{ex.dt.date.today().isoformat()}.csv"])

    def test_jql_exports_prime_sur_jql_export(self):
        self.reglages("jql_export: project = ZZZ\njql_exports:\n  a: project = AAA\n")
        self.lancer("export")
        self.assertEqual([r["jql"] for r in self.faux.requetes], ["project = AAA"])

    def test_sortie_refusee_avec_plusieurs_requetes_acceptee_avec_une(self):
        self.reglages("jql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertEqual(code, 1)
        self.assertEqual(self.faux.requetes, [])
        code, _ = self.lancer("export", "--query", "a", "--output", str(self.ws / "x.csv"))
        self.assertEqual(code, 0)
        self.assertTrue((self.ws / "x.csv").exists())

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
    """Réglage export_champ_verification : une colonne « Verification Required », sans autre usage."""
    VERIF = "customfield_10009"

    def setUp(self):
        super().setUp()
        tickets = copy.deepcopy(TICKETS)
        tickets["ABC-1"][self.VERIF] = {"value": "Yes"}                  # liste de choix
        tickets["ABC-2"][self.VERIF] = True                              # case à cocher
        tickets["ABC-3"][self.VERIF] = None                              # non renseigné
        tickets["ABC-9"][self.VERIF] = [{"value": "Oui"}, {"value": "Non"}]
        self.faux.tickets = tickets

    def reglages(self, extra=""):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             f"export_verification_field: {self.VERIF}\n{extra}")

    def test_sans_reglage_aucune_colonne_et_le_champ_n_est_pas_demande(self):
        entete = self.lignes(self.exporter())[0]
        self.assertNotIn("Verification Required", entete)
        self.assertNotIn(self.VERIF, self.faux.requetes[0]["fields"])

    def test_colonne_ecrite_apres_les_equipes_avec_le_champ_demande(self):
        self.reglages()
        lignes = self.lignes(self.exporter())
        entete = lignes[0]
        self.assertEqual(entete.count("Verification Required"), 1)
        self.assertIn(self.VERIF, self.faux.requetes[0]["fields"])
        i = entete.index("Verification Required")
        self.assertEqual(entete[i - 2:i], ["Team", "Team"])               # juste après les colonnes d'équipe
        valeurs = {l[0]: l[i] for l in lignes[1:]}
        self.assertEqual(valeurs, {"ABC-1": "Yes", "ABC-2": "true", "ABC-3": "", "ABC-9": "Oui; Non"})

    def test_en_tete_reglable(self):
        self.reglages("export_verification_header: Vérification requise\n")
        entete = self.lignes(self.exporter())[0]
        self.assertIn("Vérification requise", entete)
        self.assertNotIn("Verification Required", entete)

    def test_sortie_sans_valeur_ni_cle_avec_le_nombre_de_tickets_renseignes(self):
        self.reglages()
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        self.assertIn("3 ticket(s) renseigné(s) sur 4", sortie)
        for interdit in ("Yes", "Oui", "ABC-", "Titre secret"):
            self.assertNotIn(interdit, sortie)

    def test_valeur_de_forme_inconnue_ecrite_vide(self):
        self.faux.tickets["ABC-3"][self.VERIF] = {"inconnu": 1}
        self.reglages()
        lignes = self.lignes(self.exporter())
        i = lignes[0].index("Verification Required")
        self.assertEqual({l[0]: l[i] for l in lignes[1:]}["ABC-3"], "")

    def test_identifiant_invalide_arrete_avant_jira(self):
        self.reglages()
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_verification_field: pas un identifiant\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertNotEqual(code, 0)
        self.assertIn("export_verification_field doit être un identifiant", sortie)
        self.assertEqual(self.faux.requetes, [])


class ColonneUpdated(Base):
    """Updated est toujours écrite, juste après « Parent key », dans le fuseau de l'export."""

    def setUp(self):
        super().setUp()
        self.faux.tickets["ABC-1"]["updated"] = "2026-07-11T23:30:00.000+0000"
        self.faux.tickets["ABC-2"]["updated"] = "2026-08-04T10:00:00.000+0200"

    def test_place_apres_parent_key_et_demandee_a_jira(self):
        lignes = self.lignes(self.exporter())
        entete = lignes[0]
        self.assertEqual(entete[8:11], ["Parent key", "Updated", "Team"])
        self.assertIn("updated", self.faux.requetes[0]["fields"])
        valeurs = {l[0]: l[9] for l in lignes[1:]}
        self.assertEqual(valeurs, {"ABC-1": "12/Jul/2026 01:30", "ABC-2": "04/Aug/2026 10:00", "ABC-3": "", "ABC-9": ""})

    def test_fuseau_du_reglage(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_timezone: UTC\n")
        lignes = self.lignes(self.exporter())
        self.assertEqual({l[0]: l[9] for l in lignes[1:]}["ABC-1"], "11/Jul/2026 23:30")


class ChampPoints(Base):
    """Réglage export_points_field : une colonne « Story Points » après Updated, avant les équipes."""
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

    def test_sans_reglage_aucune_colonne_et_le_champ_n_est_pas_demande(self):
        entete = self.lignes(self.exporter())[0]
        self.assertNotIn("Story Points", entete)
        self.assertNotIn(self.PTS, self.faux.requetes[0]["fields"])

    def test_colonne_apres_updated_avant_les_equipes(self):
        self.reglages()
        lignes = self.lignes(self.exporter())
        entete = lignes[0]
        self.assertEqual(entete[9:12], ["Updated", "Story Points", "Team"])
        self.assertIn(self.PTS, self.faux.requetes[0]["fields"])
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}, {"ABC-1": "5", "ABC-2": "2.5", "ABC-3": "", "ABC-9": ""})

    def test_champ_absent_de_la_reponse_donne_une_cellule_vide(self):
        del self.faux.tickets["ABC-3"][self.PTS]
        self.reglages()
        lignes = self.lignes(self.exporter())
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}["ABC-3"], "")

    def test_booleen_non_numerique(self):
        self.faux.tickets["ABC-3"][self.PTS] = True
        self.reglages()
        lignes = self.lignes(self.exporter())
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}["ABC-3"], "")

    def test_sortie_sans_valeur_ni_cle(self):
        self.reglages()
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("« Story Points » : 2 ticket(s) renseigné(s) sur 4", sortie)
        self.assertIn("1 valeur(s) non numérique(s)", sortie)
        for interdit in ("2.5", "beaucoup", "ABC-", "Titre secret"):
            self.assertNotIn(interdit, sortie)

    def test_sortie_en_anglais(self):
        self.reglages()
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"), "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("2 ticket(s) filled out of 4", sortie)
        self.assertIn("1 non-numeric value(s)", sortie)

    def test_identifiant_invalide_arrete_avant_jira(self):
        self.ecrire_reglages("jql_export: project = ABC\nexport_points_field: pas un identifiant\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertNotEqual(code, 0)
        self.assertIn("export_points_field doit être un identifiant", sortie)
        self.assertEqual(self.faux.requetes, [])


class ListeDeChampsPoints(Base):
    """export_points_field : un identifiant ou une liste ; la colonne prend la première valeur non vide, dans l'ordre de la liste."""
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

    def test_premiere_valeur_non_vide_dans_l_ordre_de_la_liste(self):
        self.reglages(f"[{self.A}, {self.B}]")
        lignes = self.lignes(self.exporter())
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}, {"ABC-1": "5", "ABC-2": "8", "ABC-3": "3", "ABC-9": "13"})
        self.assertIn(self.A, self.faux.requetes[0]["fields"])
        self.assertIn(self.B, self.faux.requetes[0]["fields"])

    def test_l_ordre_de_la_liste_decide(self):
        self.faux.tickets["ABC-3"].update({self.A: 3, self.B: 4})
        self.reglages(f"[{self.B}, {self.A}]")
        lignes = self.lignes(self.exporter())
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}["ABC-3"], "4")
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}["ABC-1"], "5")

    def test_un_seul_identifiant_comme_avant(self):
        self.reglages(self.A)
        lignes = self.lignes(self.exporter())
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}, {"ABC-1": "5", "ABC-2": "", "ABC-3": "3", "ABC-9": "13"})
        self.assertNotIn(self.B, self.faux.requetes[0]["fields"])

    def test_liste_d_un_element_et_doublon(self):
        self.reglages(f"[{self.A}, {self.A}]")
        lignes = self.lignes(self.exporter())
        self.assertEqual(self.faux.requetes[0]["fields"].count(self.A), 1)
        self.assertEqual({l[0]: l[10] for l in lignes[1:]}["ABC-1"], "5")

    def test_sortie_par_identifiant_sans_valeur_ni_cle(self):
        self.faux.tickets["ABC-3"].update({self.A: 3, self.B: 4})          # désaccord sur ABC-3 ; ABC-9 : B est non numérique
        self.reglages(f"[{self.A}, {self.B}]")
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertIn(f"Champ {self.A} : renseigné pour 3 ticket(s) sur 4 ; 1 ticket(s) où un autre champ de points est renseigné "
                      f"avec une valeur différente", sortie)
        self.assertIn(f"Champ {self.B} : renseigné pour 2 ticket(s) sur 4 ; 1 ticket(s) où un autre champ", sortie)
        self.assertIn("« Story Points » : 4 ticket(s) renseigné(s) sur 4", sortie)
        self.assertIn("1 valeur(s) non numérique(s)", sortie)
        for interdit in ("beaucoup", "ABC-", "Titre secret", ": 13", " 13 "):
            self.assertNotIn(interdit, sortie)
        en = self.lancer("export", "--output", str(self.ws / "api.csv"), "--language", "en")[1]
        self.assertIn(f"Field {self.A}: filled for 3 ticket(s) out of 4; 1 ticket(s) where another points field", en)

    def test_identifiant_invalide_dans_la_liste_arrete_avant_jira(self):
        self.reglages(f"[{self.A}, pas un identifiant]")
        code, sortie = self.lancer("export", "--output", str(self.ws / "x.csv"))
        self.assertNotEqual(code, 0)
        self.assertIn("export_points_field doit être un identifiant", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_reglage_lu_comme_liste_ou_comme_texte(self):
        self.assertEqual(ex.reglage_points({"export_points_field": f"{self.A}"}), [self.A])
        self.assertEqual(ex.reglage_points({"export_points_field": [self.A, self.B]}), [self.A, self.B])
        self.assertEqual(ex.reglage_points({}), [])
        self.assertEqual(ex.reglage_points({"export_points_field": []}), [])


class FormatDate(unittest.TestCase):
    def test_date_csv(self):
        self.assertEqual(ex.date_csv("2017-11-09T08:49:00.000+0100"), "09/Nov/2017 08:49")
        self.assertEqual(ex.date_csv("2026-03-01T00:05:30.123+0000"), "01/Mar/2026 00:05")
        self.assertEqual(ex.date_csv(None), "")
        self.assertEqual(ex.date_csv("pas une date"), "")


if __name__ == "__main__":
    unittest.main()
