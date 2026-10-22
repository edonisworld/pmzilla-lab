"""
L'indexeur et les notes de contexte (organisation-context, design D4 et D11 ; tâche 4.1) : tools/pmzilla_lab_library.py, option --context.

    bash tests/run_all.sh pmzilla_lab_library

Sur le faux magasin en mémoire (fake_store.FakeStore) et un dossier de contexte inventé (tests/context_lab/fixtures_context.py), jamais le
vrai. Le plongement est un faux déterministe dont les appels sont comptés. Des surveillants échouent sur tout chemin sous `originaux/`.
"""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "context_lab"))
from fixtures_context import (IDENTIFIANT, NOM_EXTRAIT, NOM_GENERIQUE, NOM_SENSIBLE, SENTINELLE, Contexte, Surveillant,  # noqa: E402
                              note)
from test_pmzilla_lab_library import Base, code_de_sortie, library, livre  # noqa: E402
import identifiants_personnels  # noqa: E402
import private_collections  # noqa: E402

CORPS = ("## Périmètre\n\nUne organisation inventée : trois équipes alignées sur un flux, un forum mensuel de décisions "
         "et une liste de dépendances entre équipes, tenue par un rôle de coordination.\n")
NOTE = "2026-09-01-organisation-de-test.md"


class AvecContexte(Base):
    def setUp(self):
        super().setUp()
        self.ctx = Contexte(notes={NOTE: note(body=CORPS)})
        self.addCleanup(self.ctx.close)
        # La fausse liste et de faux identifiants, jamais les vrais (context-index-name-guard, D7).
        self.liste(self.ctx.liste)
        identifiants = mock.patch.object(identifiants_personnels, "identifiants", return_value=[IDENTIFIANT])
        identifiants.start()
        self.addCleanup(identifiants.stop)

    def liste(self, chemin):
        patch = mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(chemin), "PMZILLA_NOMS": str(chemin)})
        patch.start()
        self.addCleanup(patch.stop)

    def lancer(self, context="defaut", dossiers=None, **options):
        """index(...) : (code, sortie standard, sortie d'erreur) ; le code est celui d'un SystemExit éventuel."""
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0
        contexte = self.ctx.dossier if context == "defaut" else context
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                library.index(dossiers or [self.racine], store=self.store, context=contexte, **options)
            except SystemExit as arret:
                code = code_de_sortie(arret)
                if isinstance(arret.code, str):
                    erreur.write(arret.code)
        return code, sortie.getvalue(), erreur.getvalue()

    def notes_stockees(self):
        return {n: b for n, b in self.store.books.items() if private_collections.CONTEXT_COLLECTION in b["collections"]}


class IndexationDesNotes(AvecContexte):
    def test_les_notes_vont_dans_la_collection_de_contexte_avec_leurs_champs_et_sans_auteur(self):
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)
        stockee = self.notes_stockees()
        self.assertEqual(set(stockee), {NOTE})
        livre_note = stockee[NOTE]
        self.assertEqual(livre_note["collections"], {private_collections.CONTEXT_COLLECTION})
        self.assertEqual(livre_note["title"], "Organisation de test")
        self.assertEqual(livre_note["meta"], {"note_date": "2026-09-01", "nature": "declarative",
                                              "source": "entretien avec un rôle", "review_date": "2027-03-01"})
        self.assertNotIn("author", livre_note["meta"])
        self.assertTrue(livre_note["passages"])
        self.assertIn("trois équipes alignées", livre_note["passages"][0]["text"])

    def test_les_livres_gardent_leurs_collections(self):
        self.lancer()
        self.assertEqual(self.store.books["Flux.md"]["collections"], {"flow"})
        self.assertEqual(self.store.books["article-flux.md"]["collections"], {"watch"})
        self.assertEqual(len(self.store.books), 5)

    def test_la_carte_garde_sa_marque(self):
        self.ctx.ecrire("carte-contexte.md", note(title="Carte", kind="map", body=CORPS))
        self.lancer()
        self.assertEqual(self.store.books["carte-contexte.md"]["meta"]["kind"], "map")

    def test_inchange_ne_recalcule_rien(self):
        self.lancer()
        appels = self.calls
        code, sortie, _ = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, appels)
        self.assertIn("unchanged: 5", sortie)

    def test_note_modifiee_est_reindexee_et_note_supprimee_est_retiree(self):
        self.lancer()
        (self.ctx.notes / NOTE).unlink()
        code, sortie, _ = self.lancer()
        self.assertEqual(code, 0)
        self.assertIn(f"removed: {NOTE}", sortie)
        self.assertEqual(self.notes_stockees(), {})

    def test_le_dossier_de_notes_absent_est_refuse(self):
        sans_notes = Contexte(avec_dossier=False)
        self.addCleanup(sans_notes.close)
        sans_notes.dossier.mkdir()
        code, sortie, erreur = self.lancer(context=sans_notes.dossier)
        self.assertEqual(code, 1)
        self.assertIn("context notes folder not found", erreur)
        self.assertEqual((self.store.writes, self.calls), ([], 0))


class Refus(AvecContexte):
    def test_dossier_de_contexte_donne_comme_dossier_de_collections(self):
        for dossiers in ([self.ctx.dossier], [self.racine, self.ctx.dossier]):
            with self.subTest(dossiers=len(dossiers)):
                code, sortie, erreur = self.lancer(context=None, dossiers=dossiers)
                self.assertEqual(code, 1)
                self.assertIn("context folder given as a collections folder, refused: use --context", erreur)
                self.assertEqual((self.store.opened, self.store.writes, self.calls), (0, [], 0))

    def test_dossier_de_collections_qui_porte_un_dossier_originaux(self):
        autre = self.tmp / "autre"
        (autre / "originaux").mkdir(parents=True)
        (autre / "originaux" / "x.md").write_text(livre("Piège", {"S": SENTINELLE * 5}), encoding="utf-8")
        with Surveillant(autre / "originaux").actif() as surveillant:
            code, sortie, erreur = self.lancer(context=None, dossiers=[autre])
        self.assertEqual(code, 1)
        self.assertIn("context folder given as a collections folder, refused: use --context", erreur)
        self.assertEqual(surveillant.vus, [])
        self.assertEqual((self.store.opened, self.store.writes, self.calls), (0, [], 0))

    def test_en_tete_invalide_la_note_est_nommee_les_autres_sont_stockes_code_1(self):
        self.ctx.ecrire("2026-09-02-sans-revue.md", note(title="Sans revue", sans=("review",), body=CORPS))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("not indexed: 2026-09-02-sans-revue.md: header field missing: review", erreur)
        self.assertEqual(set(self.notes_stockees()), {NOTE})
        self.assertIn("Flux.md", self.store.books)

    def test_nom_deja_pris_par_un_livre(self):
        self.ctx.ecrire("Flux.md", note(title="Même nom", body=CORPS))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("not indexed: Flux.md: name already used by another collection", erreur)
        self.assertEqual(self.store.books["Flux.md"]["collections"], {"flow"})
        self.assertEqual(self.store.books["Flux.md"]["title"], "Flux inventé")

    def test_nom_deja_pris_par_un_article_d_un_autre_dossier(self):
        self.ctx.ecrire("article-flux.md", note(title="Même nom", body=CORPS))
        code, _, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("name already used by another collection", erreur)
        self.assertEqual(self.store.books["article-flux.md"]["collections"], {"watch"})


class Confidentialite(AvecContexte):
    """La garde de confidentialité de l'indexeur (context-index-name-guard, design D1 à D4 et D6 ; tâches 2.1 et 2.4)."""

    SECRETE = "2026-09-05-note-secrete.md"

    def setUp(self):
        super().setUp()
        self.textes = []
        plongement = self.plongement

        def enregistre(texts):
            self.textes.extend(texts)
            return plongement(texts)
        self.plongement = enregistre

    def note_avec(self, contenu, nom=None):
        """Écrit une note dont la ligne 9 (première ligne du corps) porte `contenu` ; renvoie son texte."""
        texte = note(title="Note secrète", date="2026-09-05", body=f"{contenu}\n\nsuite du corps.\n")
        self.assertEqual(texte.splitlines()[8], contenu)
        self.ctx.ecrire(nom or self.SECRETE, texte)
        return texte

    def assertSansFuite(self, *sorties, valeur=NOM_SENSIBLE, ligne=None):
        for sortie in sorties:
            self.assertNotIn(valeur, sortie)
            if ligne:
                self.assertNotIn(ligne, sortie)
        for texte in self.textes:
            self.assertNotIn(valeur, texte)

    def test_nom_de_la_liste_note_refusee_sans_valeur_ni_plongement(self):
        self.note_avec(f"le rôle voit {NOM_SENSIBLE} souvent")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {self.SECRETE}: sensitive name in line 9", erreur)
        self.assertNotIn(self.SECRETE, self.store.books)
        self.assertIn(NOTE, self.store.books)
        self.assertSansFuite(sortie, erreur, ligne="le rôle voit")

    def test_identifiant_personnel_refuse(self):
        self.note_avec(f"chemin {IDENTIFIANT} ici")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {self.SECRETE}: personal identifier in line 9", erreur)
        self.assertSansFuite(sortie, erreur, valeur=IDENTIFIANT)

    def test_nom_liste_apres_l_indexation_la_note_inchangee_est_retiree(self):
        self.note_avec("le rôle voit Plombuxor souvent")
        code, _, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)
        self.assertIn(self.SECRETE, self.store.books)
        self.ctx.liste.write_text(f"{NOM_SENSIBLE}\nPlombuxor\n", encoding="utf-8")
        appels = self.calls
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {self.SECRETE}: sensitive name in line 9", erreur)
        self.assertIn(f"removed: {self.SECRETE}", sortie)
        self.assertNotIn(self.SECRETE, self.store.books)
        self.assertIn(NOTE, self.store.books)
        self.assertEqual(self.calls, appels)
        self.assertNotIn("Plombuxor", sortie + erreur)

    def test_note_stockee_refusee_pour_son_en_tete_est_retiree(self):
        self.note_avec("rien de sensible")
        self.lancer()
        self.assertIn(self.SECRETE, self.store.books)
        self.ctx.ecrire(self.SECRETE, note(title="Note secrète", date="2026-09-05", sans=("review",), body="rien de sensible\n"))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {self.SECRETE}: header field missing: review", erreur)
        self.assertIn(f"removed: {self.SECRETE}", sortie)
        self.assertNotIn(self.SECRETE, self.store.books)

    def test_sans_l_option_la_note_refusee_reste(self):
        self.note_avec("le rôle voit Plombuxor souvent")
        self.lancer()
        self.ctx.liste.write_text(f"{NOM_SENSIBLE}\nPlombuxor\n", encoding="utf-8")
        code, sortie, erreur = self.lancer(context=None)
        self.assertEqual(code, 0, erreur)
        self.assertIn(self.SECRETE, self.store.books)
        self.assertNotIn("removed:", sortie)

    def test_liste_absente_aucune_note_touchee_livres_indexes_code_1(self):
        self.lancer()
        self.ecrire("flow/Nouveau.md", livre("Nouveau livre inventé", {"Chapitre": "Un texte inventé sur le flux. " * 20}))
        self.ctx.ecrire(NOTE, note(body=CORPS + "\nune ligne de plus.\n"))
        self.note_avec("une note nouvelle")
        avant = {n: (b["title"], b["sha256"], len(b["passages"])) for n, b in self.notes_stockees().items()}
        self.liste(self.ctx.tmp / "absente.txt")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertEqual((sortie + erreur).count("sensitive-names list unavailable: context notes not indexed"), 1)
        apres = {n: (b["title"], b["sha256"], len(b["passages"])) for n, b in self.notes_stockees().items()}
        self.assertEqual(apres, avant)
        self.assertNotIn(self.SECRETE, self.store.books)
        self.assertIn("Nouveau.md", self.store.books)
        self.assertNotIn("removed:", sortie)

    def test_liste_vide_avec_un_extrait_reste_indisponible(self):
        self.ctx.ecrire_extrait()
        self.ctx.liste.write_text("# rien\n", encoding="utf-8")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("sensitive-names list unavailable: context notes not indexed", sortie + erreur)
        self.assertEqual(self.notes_stockees(), {})
        self.assertIn("Flux.md", self.store.books)

    def test_nom_de_l_extrait_refuse_sans_le_nom(self):
        self.ctx.ecrire_extrait()
        self.note_avec(f"avec {NOM_EXTRAIT} chaque semaine")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {self.SECRETE}: extract team name in line 9", erreur)
        self.assertNotIn(self.SECRETE, self.store.books)
        self.assertSansFuite(sortie, erreur, valeur=NOM_EXTRAIT, ligne="chaque semaine")

    def test_nom_generique_de_l_extrait_indexe(self):
        self.ctx.ecrire_extrait()
        self.note_avec(f"avec {NOM_GENERIQUE} chaque semaine")
        code, _, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)
        self.assertIn(self.SECRETE, self.store.books)

    def test_fuite_le_nom_fictif_n_apparait_dans_aucune_sortie(self):
        self.ctx.ecrire_extrait()
        self.note_avec(f"avec {NOM_EXTRAIT}")
        self.ctx.ecrire("carte-contexte.md", note(title="Carte", kind="map", body=f"## Forums\n\n{NOM_EXTRAIT}\n"))
        sorties = []
        for contexte in ("defaut", None, "defaut"):
            code, sortie, erreur = self.lancer(context=contexte)
            sorties += [sortie, erreur]
        for texte in sorties + self.textes:
            self.assertNotIn(NOM_EXTRAIT, texte)
        self.assertNotIn("carte-contexte.md", self.store.books)
        for livre_stocke in self.store.books.values():
            for passage in livre_stocke["passages"]:
                self.assertNotIn(NOM_EXTRAIT, passage["text"])

    def test_les_originaux_restent_hors_de_portee(self):
        self.note_avec(f"le rôle voit {NOM_SENSIBLE} souvent")
        with Surveillant(self.ctx.originaux).actif() as surveillant:
            self.lancer()
            self.liste(self.ctx.tmp / "absente.txt")
            self.lancer()
        self.assertEqual(surveillant.vus, [])


class SansLOption(AvecContexte):
    def test_les_notes_sont_gardees_sans_l_option(self):
        self.lancer()
        ecritures = len(self.store.writes)
        code, sortie, erreur = self.lancer(context=None)
        self.assertEqual(code, 0, erreur)
        self.assertIn("context notes kept unchanged (no --context)", sortie)
        self.assertNotIn("removed:", sortie)
        self.assertEqual(set(self.notes_stockees()), {NOTE})
        self.assertEqual(len(self.store.writes), ecritures)

    def test_la_garde_du_scan_vide_ne_compte_que_les_autres_collections(self):
        self.lancer()
        for chemin in list(self.racine.rglob("*.md")):
            chemin.unlink()
        code, sortie, erreur = self.lancer(context=None)
        self.assertEqual(code, 1)
        self.assertIn("No book found in the folders while the database holds 4", erreur)
        self.assertIn(NOTE, self.notes_stockees())

    def test_allow_empty_sans_l_option_ne_retire_pas_les_notes(self):
        self.lancer()
        for chemin in list(self.racine.rglob("*.md")):
            chemin.unlink()
        code, sortie, _ = self.lancer(context=None, allow_empty=True)
        self.assertEqual(code, 0)
        self.assertEqual(set(self.store.books), {NOTE})

    def test_sans_note_en_base_pas_de_ligne_sur_les_notes(self):
        code, sortie, _ = self.lancer(context=None)
        self.assertNotIn("kept unchanged", sortie)


class Boucle_locale(AvecContexte):
    """Une collection privée ne s'embarque que sur la machine (design D11)."""

    DISTANT = "http://serveur-distant.example:11434"

    def test_loopback_refuse_une_adresse_distante_sans_aucun_appel(self):
        avant = {n: dict(b) for n, b in self.store.books.items()}
        with mock.patch.object(library, "OLLAMA_URL", self.DISTANT):
            code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("private collection: embedding service not local, nothing indexed", erreur)
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.store.books, avant)
        self.assertEqual(self.store.writes, [])

    def test_loopback_accepte_les_adresses_locales(self):
        for adresse in ("http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"):
            with self.subTest(adresse):
                self.store.books.clear()
                self.store.collections.clear()
                with mock.patch.object(library, "OLLAMA_URL", adresse):
                    code, _, erreur = self.lancer()
                self.assertEqual(code, 0, erreur)
                self.assertIn(NOTE, self.store.books)

    def test_loopback_une_adresse_distante_sans_note_a_embarquer_ne_bloque_pas(self):
        with mock.patch.object(library, "OLLAMA_URL", self.DISTANT):
            code, _, erreur = self.lancer(context=None)
        self.assertEqual(code, 0, erreur)
        self.assertGreater(self.calls, 0)

    def test_loopback_note_inchangee_ne_demande_aucun_embarquement(self):
        self.lancer()
        with mock.patch.object(library, "OLLAMA_URL", self.DISTANT):
            code, _, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)


class Originaux(AvecContexte):
    def test_l_indexeur_ne_touche_pas_aux_originaux(self):
        with Surveillant(self.ctx.originaux).actif() as surveillant:
            code, sortie, erreur = self.lancer()
            self.lancer(context=None)
        self.assertEqual(surveillant.vus, [])
        self.assertNotIn(SENTINELLE, sortie + erreur)


class LigneDeCommande(AvecContexte):
    def lancer_main(self, *arguments):
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur), \
                mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", *arguments]):
            try:
                library.main(store=self.store)
            except SystemExit as arret:
                code = code_de_sortie(arret)
                if isinstance(arret.code, str):
                    erreur.write(arret.code)
        return code, sortie.getvalue() + erreur.getvalue()

    def test_option_context_en_ligne_de_commande(self):
        code, sortie = self.lancer_main("index", str(self.racine), "--context", str(self.ctx.dossier))
        self.assertEqual(code, 0, sortie)
        self.assertIn(NOTE, self.store.books)

    def test_option_context_sans_valeur(self):
        code, sortie = self.lancer_main("index", str(self.racine), "--context")
        self.assertEqual(code, 1)
        self.assertIn("--context needs the context folder", sortie)

    def test_la_documentation_de_l_indexeur_cite_l_option(self):
        self.assertIn("--context", library.__doc__)


if __name__ == "__main__":
    unittest.main()
