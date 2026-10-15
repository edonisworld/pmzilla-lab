"""
Tests des idées ignorées par le lecteur (D7) et de `release-notes` (D5), sur le faux `gh` : aucun réseau, aucune écriture.
Liste de noms sensibles fictive (fixture) ; aucune vraie liste n'est lue.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_roadmap_github import Base, feature, sous_issue  # noqa: E402
import roadmap_model as rm  # noqa: E402

NOM = "Zorglubian"      # nom fictif de la liste de noms sensibles


def idee(number, titre="Une idée", *, state="OPEN", milestone=None, labels=None, corps=None):
    return {
        "number": number, "title": titre, "state": state,
        "body": corps if corps is not None else rm.idea_marker(rm.idea_slug(titre)) + "\n\nRésumé.",
        "labels": {"nodes": [{"name": x} for x in (labels if labels is not None else [rm.LABEL_IDEA])]},
        "milestone": {"title": milestone, "state": "OPEN"} if milestone else None,
        "parent": None, "blockedBy": {"nodes": []}, "projectItems": {"nodes": []},
    }


def faite(n, titre="Travail", *, jour="2026-10-01", theme="outillage", milestone="Hydra", raison="COMPLETED", **kw):
    """Feature fermée du jalon, avec sa raison de fermeture."""
    noeud = feature(n, titre, state="CLOSED", status="Done", milestone=milestone, theme=theme, bloc={"done_on": jour}, **kw)
    noeud["stateReason"] = raison
    return noeud


class TestIdees(Base):
    def base(self):
        return [feature(1), feature(2, blocked_by=[101], status="Todo")]

    def test_check_ignore_les_idees(self):
        self.depot(*self.base(), idee(900), idee(901, "Autre idée", state="CLOSED"), idee(902, "Avec jalon", milestone="Hydra"))
        code, sortie, _ = self.lance("check")
        self.assertEqual((code, sortie), (0, "roadmap : file valide\n"))

    def test_idee_dans_un_jalon_ferme_n_est_pas_signalee(self):
        self.depot(*self.base(), idee(900, milestone="Griffon"))
        n = self.lance("check")[0]
        self.assertEqual(n, 0)

    def test_idee_avec_sous_issue_parent_n_est_pas_une_sous_issue(self):
        i = idee(900)
        self.depot(*self.base(), i)
        self.assertEqual(self.lance("check")[0], 0)

    def test_next_ne_propose_pas_les_idees(self):
        self.depot(*self.base(), idee(900, "Prête en apparence", labels=[rm.LABEL_IDEA, rm.LABEL_FEATURE]))
        code, sortie, _ = self.lance("next", "--budget", "8h", "--today", "2026-10-12")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Prête en apparence", sortie)
        self.assertNotIn("#900", sortie)
        self.assertIn("R-1 |", sortie)

    def test_status_ne_compte_pas_les_idees(self):
        self.depot(*self.base())
        _, attendu, _ = self.lance("status")
        self.depot(*self.base(), idee(900), idee(901, "Fermée", state="CLOSED"))
        code, sortie, _ = self.lance("status")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie, attendu)

    def test_board_ne_compte_pas_les_idees(self):
        self.depot(*self.base())
        self.lance("board")
        page = (self.dir / "data" / "feuille-de-route.html").read_text(encoding="utf-8")
        self.depot(*self.base(), idee(900, "Titre d'idée"), idee(901, "Fermée", state="CLOSED"))
        code, _, _ = self.lance("board")
        self.assertEqual(code, 0)
        apres = (self.dir / "data" / "feuille-de-route.html").read_text(encoding="utf-8")
        self.assertEqual(apres, page)
        self.assertNotIn("Titre d&#x27;idée", apres)

    def test_une_idee_sans_label_idee_reste_signalee(self):
        self.depot(*self.base(), idee(900, labels=["autre"]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("#900", sortie)


class TestNotesBase(Base):
    def setUp(self):
        super().setUp()
        self.noms = self.dir / "noms.txt"
        self.noms.write_text(NOM + "\n", encoding="utf-8")
        p = mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms)})
        p.start()
        self.addCleanup(p.stop)

    def notes(self, jalon="Hydra"):
        return self.lance("release-notes", "--milestone", jalon)

    def assertAucuneEcriture(self):
        for appel in self.appels():
            self.assertEqual(appel[:2], ["api", "graphql"], appel)
            self.assertFalse(any("mutation" in a.lower() for a in appel), appel)
            self.assertFalse(any(a in ("POST", "PATCH", "PUT", "DELETE") for a in appel), appel)


class TestNotesSelection(TestNotesBase):
    def test_themes_ordre_et_prefixe(self):
        self.depot(
            faite(1, "Zèbre", jour="2026-10-03", theme="veille"),
            faite(2, "Alpha", jour="2026-10-01", theme="base"),
            faite(3, "Bravo", jour="2026-10-01", theme="base"),
            faite(4, "Premier du thème", jour="2026-09-20", theme="base"),
            faite(5, "Outil", jour="2026-10-02", theme="outillage"))
        code, sortie, erreur = self.notes()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie, "## base\n\n- Premier du thème\n- Alpha\n- Bravo\n\n## outillage\n\n- Outil\n\n## veille\n\n- Zèbre\n")
        self.assertEqual(erreur, "")
        self.assertNotIn("R-", sortie)

    def test_meme_jour_ordre_numerique_de_l_identifiant(self):
        self.depot(faite(10, "Dix"), faite(9, "Neuf"), faite(100, "Cent"))
        _, sortie, _ = self.notes()
        self.assertEqual(sortie.splitlines()[2:], ["- Neuf", "- Dix", "- Cent"])

    def test_date_inconnue_en_dernier(self):
        a, b = faite(1, "Sans date"), faite(2, "Datée", jour="2026-10-05")
        a["body"] = a["body"].replace("done_on: '2026-10-01'", "done_on: unknown").replace("done_on: 2026-10-01", "done_on: unknown")
        self.depot(a, b)
        _, sortie, _ = self.notes()
        self.assertEqual(sortie.splitlines()[2:], ["- Datée", "- Sans date"])

    def test_laisse_de_cote_ouvertes_sous_issues_idees_et_autres_jalons(self):
        self.depot(
            faite(1, "Livrée"),
            feature(2, "Encore ouverte"), feature(3, "Ouverte aussi"),
            faite(4, "Autre jalon", milestone="Griffon"),
            faite(5, "Abandonnée", raison="NOT_PLANNED"),
            sous_issue(1, 1, 101, state="CLOSED", number=601),
            idee(900, "Idée du jalon", state="CLOSED", milestone="Hydra"))
        code, sortie, erreur = self.notes()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie, "## outillage\n\n- Livrée\n")
        self.assertEqual(erreur, "roadmap : not listed: 2 open feature(s)\n")

    def test_issues_sans_label_de_type_par_numero_seulement(self):
        autre = idee(777, "Titre secret de l'issue", milestone="Hydra", labels=["bug"])
        autre2 = idee(555, "Autre titre", milestone="Hydra", labels=[], state="CLOSED")
        self.depot(faite(1), autre, autre2, idee(800, "Hors jalon", labels=[]))
        code, sortie, erreur = self.notes()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(erreur, "roadmap : not listed: issues without a type label: #555, #777\n")
        self.assertNotIn("secret", erreur + sortie)

    def test_aucune_feature_fermee(self):
        self.depot(feature(1))
        code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (0, ""))
        self.assertIn("roadmap : not listed: 1 open feature(s)\n", erreur)
        self.assertIn("roadmap : no closed feature in Hydra\n", erreur)

    def test_jalon_connu_sans_issue(self):
        self.depot(faite(1))
        os.environ["FAKE_GH_MILESTONES"] = json.dumps([{"title": "Vide", "state": "OPEN"}])
        code, sortie, erreur = self.notes("Vide")
        self.assertEqual((code, sortie, erreur), (0, "", "roadmap : no closed feature in Vide\n"))

    def test_jalon_inconnu(self):
        self.depot(faite(1))
        code, sortie, erreur = self.notes("Inconnu")
        self.assertEqual((code, sortie), (2, ""))
        self.assertEqual(erreur, "usage: unknown milestone Inconnu\n")

    def test_jalon_obligatoire(self):
        self.depot(faite(1))
        self.assertEqual(self.lance("release-notes")[0], 2)

    def test_aucune_ecriture_ni_fichier(self):
        self.depot(faite(1), feature(2))
        avant = set(Path(self.dir).rglob("*"))
        self.notes()
        self.assertTrue(self.appels())
        self.assertAucuneEcriture()
        nouveaux = {p.name for p in set(Path(self.dir).rglob("*")) - avant}
        self.assertLessEqual(nouveaux, {"data", "roadmap-cache.json", "appels.log"})


class TestNotesGarde(TestNotesBase):
    def test_nom_sensible_refuse(self):
        self.depot(faite(1, "Propre", theme="base"), faite(2, f"Avec {NOM} dedans", theme="veille"))
        code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (3, ""))
        self.assertIn("refused: sensitive name in notes, line 7; nothing was printed", erreur)
        self.assertNotIn(NOM, erreur)
        self.assertNotIn("dedans", erreur)

    def test_cle_de_ticket_refusee(self):
        self.depot(faite(1, "Corrige ABC-1234 enfin"))
        code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (3, ""))
        self.assertIn("refused: ticket key in notes, line 3; nothing was printed", erreur)
        self.assertNotIn("ABC-1234", erreur)

    def test_identifiant_personnel_refuse(self):
        secret = "identifiant-fictif-xyz"
        with mock.patch("identifiants_personnels.identifiants", lambda racine: [secret]):
            self.depot(faite(1, f"Chez {secret} ici"))
            code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (3, ""))
        self.assertIn("refused: personal identifier in notes, line 3; nothing was printed", erreur)
        self.assertNotIn(secret, erreur)

    def test_liste_absente_code_4(self):
        os.environ["PMZILLA_LAB_SENSITIVE_NAMES"] = str(self.dir / "absente.txt")
        self.depot(faite(1))
        code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (4, ""))
        self.assertIn("guard could not run: sensitive-names list absent", erreur)

    def test_liste_vide_code_4(self):
        self.noms.write_text("# rien\n", encoding="utf-8")
        self.depot(faite(1))
        code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (4, ""))
        self.assertIn("guard could not run:", erreur)

    def test_refus_sans_ecriture(self):
        self.depot(faite(1, f"{NOM} encore"))
        self.notes()
        self.assertAucuneEcriture()

    def test_les_titres_des_features_ouvertes_ne_passent_pas_le_garde(self):
        self.depot(faite(1), feature(2, f"Ouverte avec {NOM}"))
        code, sortie, _ = self.notes()
        self.assertEqual(code, 0)
        self.assertEqual(sortie, "## outillage\n\n- Travail\n")


class TestNotesHorsLigne(TestNotesBase):
    def test_banniere_sur_stderr_et_notes_sur_stdout(self):
        self.depot(faite(1, "Livrée"))
        self.lance("check")
        os.environ["FAKE_GH_MODE"] = "offline"
        code, sortie, erreur = self.notes()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie, "## outillage\n\n- Livrée\n")
        self.assertEqual(erreur, "roadmap : GitHub unreachable; read from the cache of 2026-10-11\n")

    def test_sans_cache_code_5(self):
        self.depot(faite(1))
        os.environ["FAKE_GH_MODE"] = "offline"
        code, sortie, erreur = self.notes()
        self.assertEqual((code, sortie), (5, ""))
        self.assertIn("GitHub unreachable and no cache", erreur)

    def test_la_raison_de_fermeture_survit_au_cache(self):
        self.depot(faite(1, "Livrée"), faite(2, "Abandonnée", raison="NOT_PLANNED"))
        self.lance("check")
        os.environ["FAKE_GH_MODE"] = "offline"
        _, sortie, _ = self.notes()
        self.assertEqual(sortie, "## outillage\n\n- Livrée\n")

    def test_jalon_inconnu_hors_ligne(self):
        self.depot(faite(1))
        self.lance("check")
        os.environ["FAKE_GH_MODE"] = "offline"
        code, _, erreur = self.notes("Nul")
        self.assertEqual(code, 2)
        self.assertIn("usage: unknown milestone Nul", erreur)


class TestNotesPubliques(TestNotesBase):
    """`release-notes --public` (edition-publish-tooling, D20) : seules les features étiquetées edition:public, titres inchangés."""
    ETIQUETTE = "edition:public"

    def trois_features(self):
        base = [rm.LABEL_FEATURE, rm.label_theme("outillage")]
        self.depot(faite(1, "Première livraison", labels=base), faite(2, "Livraison publique", labels=base + [self.ETIQUETTE]),
                   faite(3, "Troisième livraison", labels=base))

    def test_public_ne_garde_que_la_feature_etiquetee(self):
        self.trois_features()
        code, sortie, erreur = self.lance("release-notes", "--milestone", "Hydra", "--public")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie, "## outillage\n\n- Livraison publique\n")      # titre inchangé, en français
        self.assertEqual(erreur, "roadmap : not listed: 2 closed feature(s) without edition:public\n")
        self.assertNotIn("Première", sortie + erreur)
        self.assertAucuneEcriture()

    def test_public_aucune_feature_etiquetee(self):
        base = [rm.LABEL_FEATURE, rm.label_theme("outillage")]
        self.depot(faite(1, "Privée", labels=base))
        code, sortie, erreur = self.lance("release-notes", "--milestone", "Hydra", "--public")
        self.assertEqual((code, sortie), (0, ""))
        self.assertIn("not listed: 1 closed feature(s) without edition:public", erreur)

    def test_sans_public_les_trois_sont_listees(self):
        self.trois_features()
        code, sortie, erreur = self.notes()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie, "## outillage\n\n- Première livraison\n- Livraison publique\n- Troisième livraison\n")
        self.assertEqual(erreur, "")


if __name__ == "__main__":
    unittest.main()
