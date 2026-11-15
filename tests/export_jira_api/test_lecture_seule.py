"""Export en lecture seule et garde du périmètre (change jira-read-only-client) : sondes réelles contre un faux serveur local, refus codes 5
et 6, filtre des réponses.

    bash tests/run_all.sh export_jira_api

Faux restants (design D6), déclarés ici : le jeton (JETON, `lire_jeton` remplacé), la couche brute en mémoire (MagasinMemoire), la date
du jour figée et la passerelle (`API_ATLASSIAN`) qui pointe sur la machine locale en HTTP simple. Le réseau, lui, est réel : le faux
serveur journalise chaque requête reçue avant tout contrôle. Clés fictives seulement (ABC, OTHER, SUPX).
"""
import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_export_jira_api as base  # noqa: E402

ex, hj = base.ex, base.hj
CHAMP = base.CHAMP
RECHERCHE = "/rest/api/3/search/jql"
# Paires que les sondes de cette suite doivent voir exactement : tests/history_jira/test_lecture_seule.py les reprend (PAIRES_EXPORT).
PAIRES_ATTENDUES = {("GET", "/rest/api/3/field"), ("POST", RECHERCHE)}
PHRASE_ECRITURE = "Jira request refused: write forbidden (PUT)"
PHRASE_PERIMETRE = "Jira request refused: outside the declared scope projects"


def autre_ticket(**options):
    return base.champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200", equipes=["Equipe A"], **options)


class Sondes(base.Base):
    def paires(self) -> set:
        return {(m, urlparse(c).path[len(base.PASSERELLE):] if urlparse(c).path.startswith(base.PASSERELLE) else urlparse(c).path)
                for m, c, _ in self.faux.brut}

    def verifier(self):
        self.assertTrue(self.faux.brut, "aucune requête reçue")
        liste = hj.lectures_autorisees()
        for methode, chemin in self.paires():
            self.assertTrue(any(m == methode and re.fullmatch(p, chemin) for m, p, _ in liste), (methode, chemin))
        self.assertEqual([c for _, c, auth in self.faux.brut if auth and not c.startswith(base.PASSERELLE + "/")], [])
        self.assertEqual({p for m, p in self.paires() if m == "POST"} - {RECHERCHE}, set())

    def test_sondes_des_sous_commandes(self):
        vues = set()
        lancements = (("diagnose",), ("fields", "--search", "team"), ("export",), ("export", "--query", "a"),
                      ("export", "--strict-teams"))
        for argv in lancements:
            self.faux.brut.clear()
            if argv[:2] == ("export", "--query"):
                self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
            else:
                self.ecrire_reglages()
            self.lancer(*argv)
            self.verifier()
            vues |= self.paires()
        self.assertEqual(vues, PAIRES_ATTENDUES)

    def test_comptage_de_remplissage(self):
        self.lancer("fields", "--project", "ABC", "--field", CHAMP)
        self.verifier()


class Refus(base.Base):
    def test_refus_pendant_l_export_code_5_et_rien_d_enregistre(self):
        ecriture = lambda client, jql, champs, une_page=False: client.requete("PUT", "/rest/api/3/issue/ABC-1/changelog")  # noqa: E731
        with mock.patch.object(ex, "interroger", ecriture):
            code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 5, sortie)
        self.assertIn(PHRASE_ECRITURE, sortie)
        self.assertEqual((self.magasin.passages, self.magasin.instantanes), ([], []))
        self.assertEqual([m for m, _, _ in self.faux.brut if m not in ("GET", "POST")], [])
        self.assertEqual(self.faux.appels, [])

    def test_refus_pendant_diagnose_et_fields_code_5(self):
        ecriture = lambda client, jql, champs, une_page=False: client.requete("PUT", "/rest/api/3/issue/ABC-1/changelog")  # noqa: E731
        with mock.patch.object(ex, "interroger", ecriture):
            code, sortie = self.lancer("diagnose", "--language", "en")
        self.assertEqual((code, PHRASE_ECRITURE in sortie), (5, True))
        with mock.patch.object(hj.Client, "json", lambda client, m, c, **kw: client.requete("DELETE", c)):
            code, sortie = self.lancer("fields", "--search", "team", "--language", "en")
        self.assertEqual((code, "Jira request refused: write forbidden (DELETE)" in sortie), (5, True))

    def test_requete_d_export_non_restreinte_code_6(self):
        self.ecrire_reglages(f"jql_export: status = Done\nexport_team_field: {CHAMP}\n")
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 6, sortie)
        self.assertIn(PHRASE_PERIMETRE, sortie)
        self.assertEqual((self.magasin.passages, self.magasin.instantanes), ([], []))
        self.assertEqual([c for _, c, _ in self.faux.brut if RECHERCHE in c], [])
        self.assertNotIn("status", sortie)
        code, sortie = self.lancer("export")
        self.assertIn("requête Jira refusée : hors des projets déclarés du périmètre", sortie)

    def test_liste_des_projets_refuses_absente_code_6(self):
        for garde in ("scope_projects: [ABC]\n", "scope_projects: [ABC]\nforbidden_projects: []\n",
                      "scope_projects: [ABC]\nforbidden_projects: SUPX\n"):
            self.ecrire_reglages(garde=garde)
            for argv in (("diagnose",), ("fields", "--search", "team"), ("export",)):
                self.faux.brut.clear()
                code, sortie = self.lancer(*argv, "--language", "en")
                self.assertEqual(code, 6, (argv, sortie))
                self.assertIn("Jira request refused: setting missing, empty or unreadable (forbidden_projects)", sortie)
                self.assertEqual(self.faux.brut, [], argv)
                self.assertNotIn("SUPX", sortie)
            self.assertEqual((self.magasin.passages, self.magasin.instantanes), ([], []))

    def test_liste_des_projets_declares_absente_code_6(self):
        self.ecrire_reglages(garde="forbidden_projects: [SUPX]\n")
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 6, sortie)
        self.assertIn("setting missing, empty or unreadable (scope_projects)", sortie)
        self.assertEqual(self.faux.brut, [])


class Perimetre(base.Base):
    def test_ticket_d_un_autre_projet_non_enregistre_et_ligne_de_compte(self):
        self.faux.tickets["OTHER-1"] = autre_ticket()
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets outside the declared projects set aside: 1", sortie)
        self.assertNotIn("OTHER", sortie)
        self.assertEqual({i["issue_key"] for i in self.magasin.instantanes}, set(base.TICKETS))
        code, sortie = self.lancer("export")
        self.assertIn("tickets hors des projets déclarés écartés : 1", sortie)

    def test_aucun_ticket_ecarte_aucune_ligne(self):
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("set aside", sortie)

    def test_lien_parent_et_sous_tache_enregistres_reduits_a_la_cle_et_au_type(self):
        self.faux.tickets["ABC-1"]["subtasks"] = [{"key": "ABC-2", "fields": {"summary": "Titre secret", "issuetype": {"name": "Task"}}}]
        self.faux.tickets["ABC-1"]["parent"] = {"key": "ABC-9", "fields": {"summary": "Titre secret", "status": {"name": "Open"}}}
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        enregistre = repr(self.magasin.instantanes)
        self.assertNotIn("Titre secret", enregistre)
        self.assertNotIn("Titre secret", sortie)
        self.assertIn("ABC-9", repr(self.magasin.dernier("ABC-1")))          # le parent reste connu par sa clé
        self.assertIn("ABC-3", repr(self.magasin.dernier("ABC-1")))          # un lien reste connu par la clé liée et son type

    def test_projet_refuse_retire_avec_ses_liens_aucune_cle_en_sortie(self):
        self.faux.tickets["SUPX-5"] = autre_ticket()
        self.faux.tickets["ABC-1"]["issuelinks"].append(base.lien("Blocks", "Outward", "SUPX-4"))
        code, sortie = self.lancer("export", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets outside the declared projects set aside: 2", sortie)
        self.assertNotIn("SUPX", sortie + repr(self.magasin.instantanes))


if __name__ == "__main__":
    unittest.main()
