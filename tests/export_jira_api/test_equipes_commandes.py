"""check-teams et migrate-teams (change team-mapping, groupe 5, tâches 5.1 à 5.13).

    bash tests/run_all.sh export_jira_api </dev/null

Spécifications : jira-flow-export (« Team sources check », « Catalogue migration from the complete Assets list », « Strict reading of
the Assets list », « Obsolete flag written from the Assets status », « Referential cross-checked with the Assets list », etc.).
Aucun appel à Jira, listes Assets et catalogues INVENTÉS, libellés sentinelles : aucun libellé, nom ni valeur ne doit paraître dans
la sortie (sauf la proposition de libellés distinctifs de migrate-teams). La variable CLAUDECODE est retirée de l'environnement du
test (les sous-commandes la refusent) ; le test de refus la pose.
"""
import datetime as dt
import os
import stat
import unittest
from unittest import mock

import yaml

from test_export_jira_api import Base, CHAMP, ex
from test_catalogue_export import catalogue, entree

ENTETE = "id,type,libelle,nom_court,statut"
DEV, VER, PRO, OTH = "Development Team", "Verification Team", "Product Management Team", "Other Team"
SENTINELLE = "ZZSENTINELLE"

# Référentiel : Equipe A (1), Equipe B (2), Equipe C (3, 33), Equipe D sans identifiant.
REF = """source_date: 2026-10-01
sites: [Site 1]
departments:
  - name: Departement 1
    site: Site 1
    headcount: 16
    teams: [Equipe A, Equipe B, Equipe C, Equipe D]
teams:
  - name: Equipe A
    headcount: 4
    jira_team_ids: ['1']
  - name: Equipe B
    headcount: 4
    jira_team_ids: ['2']
  - name: Equipe C
    headcount: 4
    jira_team_ids: ['3', '33']
  - name: Equipe D
    headcount: 4
"""
REF_COMPLET = REF.replace("  - name: Equipe D\n    headcount: 4\n", "  - name: Equipe D\n    headcount: 4\n    jira_team_ids: ['4']\n")


def liste(*objets, entete=ENTETE):
    """CSV d'une liste Assets inventée : objets = (id, type, libelle, nom_court, statut)."""
    return entete + "\n" + "".join(",".join(o) + "\n" for o in objets)


def objet(identifiant, type_=DEV, libelle=None, statut="active", court=None):
    return (str(identifiant), type_, libelle if libelle is not None else f"Libelle-{identifiant}",
            court if court is not None else f"SC{identifiant}", statut)


class Socle(Base):
    def setUp(self):
        super().setUp()
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.flux = self.ws / "Flux-Lab"
        # La revue du catalogue lit la base (database-only, D13) : le lecteur est remplacé par un faux, jamais la vraie base.
        # self.vues : décomptes par nom d'équipe que rend la vue des équipes vues ; None : base injoignable.
        import export_jira_api_equipes as eq
        self.vrai_lecteur = eq.lire_equipes_vues
        self.vues = None

        def faux_lecteur(ouvrir=None):
            if self.vues is None:
                raise eq.EquipesVuesInjoignables()
            return dict(self.vues)
        patch_vues = mock.patch.object(eq, "lire_equipes_vues", faux_lecteur)
        patch_vues.start()
        self.addCleanup(patch_vues.stop)

    def ecrire(self, nom, contenu):
        chemin = self.flux / nom
        chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def liste_assets(self, *objets, date="2026-10-16", **options):
        return self.ecrire(f"equipes-assets-complet-{date}.csv", liste(*objets, **options))

    def etat_du_dossier(self):
        return {str(p.relative_to(self.flux)): p.read_bytes() for p in sorted(self.flux.rglob("*")) if p.is_file()}

    def fichiers(self):
        return sorted(str(p.relative_to(self.flux)) for p in self.flux.rglob("*") if p.is_file())

    def verifier_neutre(self, sortie, *sentinelles):
        for interdit in (SENTINELLE, "Equipe", "Libelle", "Table", "ws-secret", *sentinelles):
            self.assertNotIn(interdit, sortie)


class Refus(Socle):
    """Refus dans une session Claude Code, avant toute lecture (5.1, 5.2)."""

    def test_check_teams_refuse_avant_toute_lecture(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), mock.patch("pathlib.Path.read_text", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.is_file", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.exists", side_effect=AssertionError("lu")):
            code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 3, sortie)
        self.assertIn("Refusé dans une session Claude Code", sortie)

    def test_migrate_teams_refuse_avant_toute_lecture_en_anglais(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), mock.patch("pathlib.Path.read_text", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.is_file", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.exists", side_effect=AssertionError("lu")):
            code, sortie = self.lancer("migrate-teams", "--from-assets", "Flux-Lab/equipes-assets-complet-2026-10-16.csv",
                                       "--language", "en")
        self.assertEqual(code, 3, sortie)
        self.assertIn("Refused inside a Claude Code session", sortie)

    def test_aucun_appel_a_jira(self):
        self.ecrire("organisation.yaml", REF)
        self.lancer("check-teams")
        self.assertEqual(self.faux.requetes, [])
        self.assertEqual(self.faux.appels, [])


class VerificationDesSources(Socle):
    """5.1 : check-teams, comptes et codes de sortie."""

    def test_migration_incomplete_code_4_sans_libelle(self):
        self.ecrire("organisation.yaml", REF)
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-Quimbo", "'50'")))
        self.ecrire("equipes-assets.yaml", f"equipes: {{'1': {SENTINELLE}-A, '50': {SENTINELLE}-B, '7': {SENTINELLE}-C, '8': {SENTINELLE}-D}}\n")
        avant = self.etat_du_dossier()
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)
        self.assertIn("identifiants de l'ancienne table non couverts : 2", sortie)
        self.assertIn("identifiants à placer : 7 ; 8", sortie)
        self.assertIn("ancienne table des équipes plus lue : supprimer equipes-assets.yaml", sortie)
        self.verifier_neutre(sortie)
        self.assertEqual(self.etat_du_dossier(), avant)                 # rien n'est écrit, la table n'est pas modifiée

    def test_migration_complete(self):
        self.ecrire("organisation.yaml", REF)
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-Quimbo", "'50'", "    obsolete: true\n"), entree("Libelle-Z", "'60'")))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("sources d'équipes cohérentes : référentiel 4 identifiants, catalogue 2 identifiants, 1 obsolètes", sortie)
        self.assertNotIn("non couverts", sortie)
        self.assertNotIn("plus lue", sortie)
        code, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("team sources consistent: referential 4 identifiers, catalogue 2 identifiers, 1 obsolete", sortie)

    def test_ancienne_table_nettoyee_et_toujours_presente_code_0(self):
        self.ecrire("organisation.yaml", REF)
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-Quimbo", "'50'", "    obsolete: true\n")))
        self.ecrire("equipes-assets.yaml", "equipes: {'1': A, '50': B}\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("sources d'équipes cohérentes", sortie)
        self.assertIn("ancienne table des équipes plus lue : supprimer equipes-assets.yaml", sortie)
        self.assertNotIn("non couverts", sortie)

    def test_cle_a_confirmer_refusee_code_1(self):
        self.ecrire("organisation.yaml", REF)
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-Quimbo", "'50'", "    obsolete_to_confirm: true\n")))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("teams[0].obsolete_to_confirm", sortie)
        self.assertNotIn("Quimbo", sortie)

    def test_nom_du_referentiel_avec_identifiant_hors_referentiel_code_1(self):
        self.ecrire("organisation.yaml", REF)
        self.ecrire("equipes-jira.yaml", catalogue(entree("Equipe A", "'1', '99'")))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("équipe du catalogue nommée comme une équipe du référentiel", sortie)

    def test_tables_absentes_et_catalogue_vide(self):
        self.ecrire("organisation.yaml", REF)
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("catalogue 0 identifiants, 0 obsolètes", sortie)

    def test_l_ancienne_table_illisible_n_est_comptee_que_par_check_teams(self):
        self.ecrire("organisation.yaml", REF)
        self.ecrire("equipes-assets.yaml", "equipes: [pas, un")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)


class EquipesSansIdentifiant(Socle):
    """5.11 : écart attendu E3, toujours contrôlé."""

    def test_une_equipe_sans_identifiant_chemin_et_ligne_sans_nom(self):
        self.ecrire("organisation.yaml", REF.replace("Equipe D", f"Equipe {SENTINELLE}"))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du référentiel sans identifiant : 1", sortie)
        self.assertIn("équipes sans identifiant : teams[3] (L", sortie)
        self.assertNotIn(SENTINELLE, sortie)
        code, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("referential teams without identifier: 1", sortie)
        self.assertIn("teams without identifier: teams[3] (L", sortie)

    def test_toutes_avec_identifiant_compte_zero_sans_ligne(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du référentiel sans identifiant : 0", sortie)
        self.assertNotIn("équipes sans identifiant", sortie)

    def test_controle_fait_aussi_sans_liste_assets(self):
        self.ecrire("organisation.yaml", REF)
        _, sortie = self.lancer("check-teams")
        self.assertIn("aucune liste Assets trouvée", sortie)
        self.assertIn("équipes du référentiel sans identifiant : 1", sortie)


class SignalDeRevue(Socle):
    """5.3, 14.1 : entrées du catalogue vues sur les tickets stockés, lues par la vue des équipes vues (database-only, D13) ; le lecteur
    de la base est remplacé par un faux qui rend les décomptes par nom d'équipe."""

    def exporter_fichier(self, nom, cellules, entete="Issue key,Status,Team,Team\n"):
        """Écrit un CSV d'export, que check-teams ne doit plus jamais ouvrir ; rend aussi, comme la vue, un décompte par équipe."""
        (self.flux / "exports").mkdir(exist_ok=True)
        lignes = "".join(f"ABC-{i},Open,{a},{b}\n" for i, (a, b) in enumerate(cellules, 1))
        (self.flux / "exports" / nom).write_text(entete + lignes, encoding="utf-8")
        if self.vues is None:
            self.vues = {}
        for a, b in cellules:
            for equipe in {a, b} - {""}:
                self.vues[equipe] = self.vues.get(equipe, 0) + 1

    def sources(self, extra=""):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-Quimbo", "'50', '51'"), entree("Libelle-Plinth", "'52'", "    obsolete: true\n"),
                                                   entree("Libelle-Vexor", "'1'")) + extra)

    def test_entree_vue_trois_tickets_deux_identifiants_sans_libelle(self):
        self.sources()
        self.exporter_fichier("api-2026-10-16.csv", [("Libelle-Quimbo", ""), ("Equipe A", "Libelle-Quimbo"), ("Libelle-Quimbo", "")])
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du catalogue vues sur des tickets de l'export, à revoir : 1 entrées, 3 tickets", sortie)
        self.assertIn("identifiants à revoir : 50 ; 51", sortie)
        self.verifier_neutre(sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("catalogue teams seen on export tickets, to review: 1 entries, 3 tickets", sortie)
        self.assertIn("identifiers to review: 50; 51", sortie)

    def test_entree_obsolete_non_signalee(self):
        self.sources()
        self.exporter_fichier("api-2026-10-16.csv", [("Libelle-Plinth", "")])
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("à revoir", sortie)

    def test_entree_dont_le_referentiel_liste_tous_les_identifiants_non_signalee(self):
        self.sources()
        self.exporter_fichier("api-2026-10-16.csv", [("Libelle-Vexor", ""), ("Equipe A", "")])
        code, sortie = self.lancer("check-teams")
        self.assertNotIn("à revoir", sortie)

    def test_le_signal_ne_change_pas_le_code_4(self):
        self.sources()
        self.ecrire("equipes-assets.yaml", "equipes: {'700': Table X}\n")
        self.exporter_fichier("api-2026-10-16.csv", [("Libelle-Quimbo", "")])
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)
        self.assertIn("à revoir", sortie)
        self.assertIn("non couverts : 1", sortie)

    def test_base_injoignable_la_revue_est_sautee_le_code_est_celui_des_autres_controles(self):
        self.sources()
        self.vues = None                       # le faux lecteur lève EquipesVuesInjoignables
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("base injoignable : revue du catalogue sautée", sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("database unreachable: catalogue review skipped", sortie)
        self.assertNotIn("à revoir", sortie)
        self.ecrire("equipes-assets.yaml", "equipes: {'700': Table X}\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)                       # le code des autres contrôles, inchangé
        self.assertIn("base injoignable", sortie)

    def test_aucun_ticket_dans_la_base(self):
        self.sources()
        self.vues = {}
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("aucun ticket dans la base : revue du catalogue sautée", sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("no ticket in the database: catalogue review skipped", sortie)

    def test_la_phrase_des_fichiers_d_export_a_disparu(self):
        import export_jira_api_equipes_messages as m
        for langue in ("fr", "en"):
            self.assertNotIn("review_skipped", m.CATALOGS_EQUIPES[langue])
        self.sources()
        for vues in (None, {}):
            self.vues = vues
            _, sortie = self.lancer("check-teams")
            self.assertNotIn("fichier d'export", sortie)

    def test_aucun_fichier_d_export_n_est_ouvert(self):
        """Un CSV d'export présent dans le dossier des exports n'est jamais lu : la revue vient de la base seule."""
        self.sources()
        self.exporter_fichier("api-2026-10-16.csv", [("Libelle-Quimbo", "")] * 3)
        self.vues = {"Libelle-Wumpa": 1}                          # la base ne dit rien de l'entrée du fichier
        ouverts = []
        vrai_open = type(self.flux).open
        vrai_lire = type(self.flux).read_text
        with mock.patch.object(type(self.flux), "open", lambda p, *a, **k: (ouverts.append(p.name), vrai_open(p, *a, **k))[1]), \
                mock.patch.object(type(self.flux), "read_text", lambda p, *a, **k: (ouverts.append(p.name), vrai_lire(p, *a, **k))[1]):
            code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertFalse([n for n in ouverts if n.endswith(".csv")], ouverts)
        self.assertNotIn("à revoir", sortie)

    def test_un_decompte_inferieur_a_cinq_est_utilise_tel_quel(self):
        self.sources()
        self.vues = {"Libelle-Quimbo": 1}
        _, sortie = self.lancer("check-teams")
        self.assertIn("à revoir : 1 entrées, 1 tickets", sortie)
        self.vues = {"Libelle-Quimbo": 37}
        _, sortie = self.lancer("check-teams")
        self.assertIn("à revoir : 1 entrées, 37 tickets", sortie)

    def test_nombre_de_tickets_a_revoir_somme_des_decomptes_des_entrees_nouvelles(self):
        """Question ouverte 5 du design : un ticket qui porte deux entrées à revoir compte deux fois dans la somme."""
        self.sources()
        self.vues = {"Libelle-Quimbo": 2, "Libelle-Plinth": 9, "Libelle-Vexor": 4, "Equipe A": 8, "Libelle-Absente": 6}
        _, sortie = self.lancer("check-teams")
        self.assertIn("à revoir : 1 entrées, 2 tickets comptés par entrée", sortie)
        _, sortie_en = self.lancer("check-teams", "--language", "en")
        self.assertIn("to review: 1 entries, 2 tickets counted per entry", sortie_en)
        self.assertIn("à revoir : 1 entrées, 2 tickets", sortie)          # obsolète, référentiel et inconnue : hors de la somme
        self.verifier_neutre(sortie)

    def test_la_revue_n_ouvre_pas_la_base_hors_de_la_vue(self):
        """Le lecteur réel n'interroge que la vue : sa requête nomme flow.v_team_tickets_seen et aucune table."""
        import export_jira_api_equipes as eq
        requetes = []

        class Connexion:
            def execute(self, sql, *args):
                requetes.append(sql)
                return self

            def fetchall(self):
                return [("Equipe X", 3)]

            def close(self):
                requetes.append("close")
        self.assertEqual(self.vrai_lecteur(ouvrir=lambda: Connexion()), {"Equipe X": 3})
        self.assertEqual(requetes, [eq.REQUETE_EQUIPES_VUES, "close"])
        self.assertIn("flow.v_team_tickets_seen", eq.REQUETE_EQUIPES_VUES)
        for table in ("issues", "issue_teams", "teams", "raw_", "transitions", "links"):
            self.assertNotIn(f"flow.{table}", eq.REQUETE_EQUIPES_VUES)
        self.assertNotRegex(eq.REQUETE_EQUIPES_VUES, r"(?i)\b(insert|update|delete)\b")

    def test_le_lecteur_reel_ne_laisse_passer_aucun_detail_de_la_base(self):
        def echoue():
            raise RuntimeError("mot de passe ws-secret pour PROJ-1")
        import export_jira_api_equipes as eq
        with self.assertRaises(eq.EquipesVuesInjoignables) as ctx:
            self.vrai_lecteur(ouvrir=echoue)
        self.assertNotIn("ws-secret", str(ctx.exception) + repr(ctx.exception))


class ControlesAvecLaListeAssets(Socle):
    """5.10 : référentiel recoupé avec Assets ; aucun effet sur le code de sortie."""

    def sources(self, cat=None, ref=REF_COMPLET):
        self.ecrire("organisation.yaml", ref)
        self.ecrire("equipes-jira.yaml", cat if cat is not None else catalogue(
            entree("Libelle-1", "'1'", f"    type: {DEV}\n"), entree("Libelle-2", "'2'", f"    type: {DEV}\n"),
            entree("Libelle-3", "'3', '33'", f"    type: {DEV}\n"), entree("Libelle-4", "'4'", f"    type: {DEV}\n")))

    def complete(self, **extra):
        return [objet(1), objet(2), objet(3), objet(33), objet(4)]

    def test_identifiant_du_referentiel_absent_d_assets(self):
        self.sources()
        self.liste_assets(*[o for o in self.complete() if o[0] != "33"])
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiants du référentiel absents d'Assets : 1", sortie)
        self.assertIn("identifiants absents d'Assets : 33", sortie)
        self.verifier_neutre(sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("referential identifiers absent from Assets: 1", sortie)
        self.assertIn("identifiers absent from Assets: 33", sortie)

    def test_aucun_identifiant_absent_compte_zero_sans_liste(self):
        self.sources()
        self.liste_assets(*self.complete())
        _, sortie = self.lancer("check-teams")
        self.assertIn("identifiants du référentiel absents d'Assets : 0", sortie)
        self.assertNotIn("identifiants absents d'Assets", sortie)

    def test_equipe_avec_identifiant_inactif_ou_abandonne(self):
        self.sources()
        objets = self.complete()
        objets[1] = objet(2, statut="inactive")
        objets[4] = objet(4, statut="discarded")
        self.liste_assets(*objets)
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du référentiel avec un identifiant inactif ou abandonné dans Assets : 2", sortie)
        self.assertIn("identifiants inactifs ou abandonnés dans Assets : 2 ; 4", sortie)
        self.verifier_neutre(sortie)

    def test_types_differents_dans_le_catalogue_code_4_inchange(self):
        self.sources(catalogue(entree("Libelle-1", "'1'", f"    type: {DEV}\n"), entree("Libelle-2", "'2'", f"    type: {DEV}\n"),
                               entree("Libelle-3", "'3'", f"    type: {DEV}\n"), entree("Libelle-33", "'33'", f"    type: {VER}\n"),
                               entree("Libelle-4", "'4'", f"    type: {DEV}\n")))
        self.ecrire("equipes-assets.yaml", "equipes: {'700': X}\n")
        self.liste_assets(*self.complete())
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)
        self.assertIn("équipes du référentiel aux identifiants de types différents : 1", sortie)
        self.assertIn("identifiants de types différents : 3 ; 33", sortie)

    def test_types_differents_aussi_sans_liste(self):
        self.sources(catalogue(entree("Libelle-3", "'3'", f"    type: {DEV}\n"), entree("Libelle-33", "'33'", f"    type: {VER}\n")))
        _, sortie = self.lancer("check-teams")
        self.assertIn("aucune liste Assets trouvée", sortie)
        self.assertIn("équipes du référentiel aux identifiants de types différents : 1", sortie)

    def test_aucun_type_different_compte_zero(self):
        self.sources()
        self.liste_assets(*self.complete())
        _, sortie = self.lancer("check-teams")
        self.assertIn("équipes du référentiel aux identifiants de types différents : 0", sortie)
        self.assertNotIn("identifiants de types différents :", sortie.replace("types différents : 0", ""))

    def test_liste_choisie_par_la_date_du_nom_pas_par_la_date_de_modification(self):
        self.sources()
        recente = self.liste_assets(*self.complete(), date="2026-10-16")
        ancienne = self.liste_assets(*[o for o in self.complete() if o[0] != "33"], date="2026-09-01")
        os.utime(recente, (1_000_000_000, 1_000_000_000))                 # la plus récente par le nom est la plus ancienne par la date de fichier
        os.utime(ancienne, (2_000_000_000, 2_000_000_000))
        _, sortie = self.lancer("check-teams")
        self.assertIn("identifiants du référentiel absents d'Assets : 0", sortie)
        self.assertIn("liste Assets utilisée : equipes-assets-complet-2026-10-16.csv", sortie)

    def test_seul_le_nom_du_fichier_est_imprime(self):
        self.sources()
        self.liste_assets(*self.complete())
        _, sortie = self.lancer("check-teams")
        ligne = [l for l in sortie.splitlines() if "liste Assets utilisée" in l][0]
        self.assertEqual(ligne, "liste Assets utilisée : equipes-assets-complet-2026-10-16.csv")
        self.assertNotIn(str(self.ws), sortie)
        self.assertNotIn("Flux-Lab", sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("assets list used: equipes-assets-complet-2026-10-16.csv", sortie)

    def test_noms_invalides_ignores(self):
        self.sources()
        self.ecrire("equipes-assets-complet-2026-13-45.csv", "n'importe quoi")      # date impossible : ignorée
        self.ecrire("equipes-assets-complet-2026-10-16.csv.bak", "n'importe quoi")
        self.ecrire("equipes-assets-complet-copie.csv", "n'importe quoi")
        _, sortie = self.lancer("check-teams")
        self.assertIn("aucune liste Assets trouvée", sortie)

    def test_sans_liste_la_phrase_nomme_les_trois_controles(self):
        self.sources()
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("aucune liste Assets trouvée : contrôles sautés : identifiants du référentiel absents d'Assets, "
                      "équipes du référentiel inactives dans Assets, types d'équipe changés dans Assets", sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("no assets list found: checks skipped: referential identifiers absent from Assets, referential teams inactive "
                      "in Assets, team types changed in Assets", sortie)

    def test_identifiant_partage_avec_des_noms_differents_aucune_ligne(self):
        self.sources()
        self.liste_assets(*self.complete())
        _, sortie = self.lancer("check-teams")
        for interdit in ("nom", "libellé", "label", "Libelle", "Equipe"):
            self.assertNotIn(interdit, sortie.replace("noms", ""))

    def test_aucune_ligne_par_entree_a_confirmer(self):
        self.sources()
        self.liste_assets(*self.complete())
        for langue in ("fr", "en"):
            _, sortie = self.lancer("check-teams", "--language", langue)
            self.assertNotIn("confirm", sortie.lower())

    def test_liste_refusee_code_1(self):
        self.sources()
        self.liste_assets(*self.complete(), entete=ENTETE + ",responsable")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("liste Assets refusée : colonne inconnue en position 6", sortie)

    def test_ni_le_referentiel_ni_un_type_ne_sont_ecrits(self):
        self.sources()
        self.liste_assets(*self.complete())
        avant = self.etat_du_dossier()
        self.lancer("check-teams")
        self.assertEqual(self.etat_du_dossier(), avant)


class TypesForces(Socle):
    """5.12 et 5.13 : trois signaux sur le type, lus du catalogue, sans effet sur le code de sortie."""

    def referentiel_force(self, type_="Verification Team"):
        return REF_COMPLET.replace("    jira_team_ids: ['1']\n", f"    jira_team_ids: ['1']\n    type: {type_}\n")

    def cat(self, type_=DEV):
        return catalogue(entree("Libelle-1", "'1'", f"    type: {type_}\n"), entree("Libelle-2", "'2'", f"    type: {DEV}\n"),
                         entree("Libelle-3", "'3', '33'", f"    type: {DEV}\n"), entree("Libelle-4", "'4'", f"    type: {DEV}\n"))

    def test_type_force_liste_avec_le_type_assets_et_le_code_4_inchange(self):
        self.ecrire("organisation.yaml", self.referentiel_force().replace("Equipe A", f"Equipe {SENTINELLE}"))
        self.ecrire("equipes-jira.yaml", self.cat())
        self.ecrire("equipes-assets.yaml", "equipes: {'700': X}\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)
        self.assertIn("équipes du référentiel au type forcé : 1", sortie)
        self.assertRegex(sortie, r"type forcé en teams\[0\]\.type \(L\d+\) : Verification Team, type Assets : Development Team")
        self.assertNotIn(SENTINELLE, sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertRegex(sortie, r"forced type at teams\[0\]\.type \(L\d+\): Verification Team, Assets type: Development Team")

    def test_force_sans_type_deduit_aucun(self):
        self.ecrire("organisation.yaml", self.referentiel_force())
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-9", "'9'", f"    type: {DEV}\n")))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("type Assets : aucun", sortie)
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("Assets type: none", sortie)

    def test_force_avec_types_differents(self):
        self.ecrire("organisation.yaml", self.referentiel_force().replace("jira_team_ids: ['1']", "jira_team_ids: ['1', '2']", 1)
                    .replace("jira_team_ids: ['2']", "jira_team_ids: ['5']"))
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-1", "'1'", f"    type: {DEV}\n"), entree("Libelle-2", "'2'", f"    type: {OTH}\n")))
        _, sortie = self.lancer("check-teams")
        self.assertIn("type Assets : types différents", sortie)
        self.assertIn("équipes du référentiel au type forcé différent du type déduit : 0", sortie)      # jamais compté ici
        self.assertIn("types forcés devenus inutiles, à retirer : 0", sortie)                           # ni ici

    def test_aucun_type_force_compte_zero_sans_ligne_par_equipe(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", self.cat())
        _, sortie = self.lancer("check-teams")
        self.assertIn("équipes du référentiel au type forcé : 0", sortie)
        self.assertNotIn("type forcé en", sortie)
        self.assertIn("types forcés devenus inutiles, à retirer : 0", sortie)

    def test_force_different_du_deduit_compte_avec_les_identifiants(self):
        self.ecrire("organisation.yaml", self.referentiel_force())
        self.ecrire("equipes-jira.yaml", self.cat())
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du référentiel au type forcé différent du type déduit : 1", sortie)
        self.assertIn("identifiants des équipes au type forcé différent du type déduit : 1", sortie)

    def test_forcage_devenu_inutile_signale_avec_son_chemin(self):
        self.ecrire("organisation.yaml", self.referentiel_force(DEV).replace("Equipe A", f"Equipe {SENTINELLE}"))
        self.ecrire("equipes-jira.yaml", self.cat())
        avant = self.etat_du_dossier()
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("types forcés devenus inutiles, à retirer : 1", sortie)
        self.assertRegex(sortie, r"types forcés à retirer : teams\[0\]\.type \(L\d+\)")
        self.assertIn("équipes du référentiel au type forcé différent du type déduit : 0", sortie)
        self.assertNotIn(SENTINELLE, sortie)
        self.assertEqual(self.etat_du_dossier(), avant)                       # le référentiel n'est pas écrit
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("forced types no longer needed, to remove: 1", sortie)
        self.assertRegex(sortie, r"forced types to remove: teams\[0\]\.type \(L\d+\)")

    def test_signaux_de_type_sans_liste_assets(self):
        self.ecrire("organisation.yaml", self.referentiel_force())
        self.ecrire("equipes-jira.yaml", self.cat())
        _, sortie = self.lancer("check-teams")
        self.assertIn("aucune liste Assets trouvée", sortie)
        self.assertIn("équipes du référentiel au type forcé : 1", sortie)

    # --- 5.13 : type changé dans Assets depuis l'écriture du catalogue
    def test_type_change_dans_assets(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", self.cat(OTH))
        self.liste_assets(objet(1, VER), objet(2), objet(3), objet(33), objet(4))
        avant = self.etat_du_dossier()
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("types d'équipe changés dans Assets depuis l'écriture du catalogue : 1", sortie)
        self.assertIn("identifiants au type changé : 1", sortie)
        self.verifier_neutre(sortie)
        self.assertEqual(self.etat_du_dossier(), avant)                       # catalogue inchangé
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("team types changed in Assets since the catalogue was written: 1", sortie)
        self.assertIn("identifiers with a changed type: 1", sortie)

    def test_catalogue_ecrit_depuis_la_meme_liste_compte_zero_sans_ligne(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", self.cat())
        self.liste_assets(objet(1), objet(2), objet(3), objet(33), objet(4))
        _, sortie = self.lancer("check-teams")
        self.assertIn("types d'équipe changés dans Assets depuis l'écriture du catalogue : 0", sortie)
        self.assertNotIn("identifiants au type changé", sortie)

    def test_entree_a_la_main_sans_type_et_identifiant_absent_de_la_liste_non_comptes(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", self.cat() + entree("Libelle-main", "'80'") + entree("Libelle-main2", "'81'", f"    type: {OTH}\n"))
        self.liste_assets(objet(1), objet(2), objet(3), objet(33), objet(4), objet(80, VER))
        _, sortie = self.lancer("check-teams")
        self.assertIn("changés dans Assets depuis l'écriture du catalogue : 0", sortie)         # 80 sans type, 81 absent

    def test_type_change_avec_identifiant_de_l_ancienne_table_dans_aucune_source_code_4(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", self.cat(OTH))
        self.ecrire("equipes-assets.yaml", "equipes: {'700': X}\n")
        self.liste_assets(objet(1, VER), objet(2), objet(3), objet(33), objet(4))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)
        self.assertIn("changés dans Assets depuis l'écriture du catalogue : 1", sortie)
        self.assertIn("non couverts : 1", sortie)

    def test_sans_liste_le_controle_est_nomme_dans_la_phrase_sautee(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", self.cat())
        _, sortie = self.lancer("check-teams")
        self.assertIn("types d'équipe changés dans Assets", sortie.split("contrôles sautés")[1])
        self.assertNotIn("changés dans Assets depuis", sortie)


class LectureStricteDeLaListe(Socle):
    """5.6 : lecture stricte, partagée par migrate-teams et check-teams."""

    def migrer(self, *objets, nom="equipes-assets-complet-2026-10-16.csv", contenu=None, extra=(), **options):
        chemin = self.flux / nom
        chemin.write_text(contenu if contenu is not None else liste(*objets, **options), encoding="utf-8")
        return self.lancer("migrate-teams", "--from-assets", str(chemin), *extra)

    def tout_refuse(self, code, sortie, phrase):
        self.assertEqual(code, 1, sortie)
        self.assertIn(phrase, sortie)
        self.assertFalse((self.flux / "equipes-jira.yaml").exists())
        self.verifier_neutre(sortie)

    def test_colonnes_dans_un_autre_ordre_lues_comme_dans_l_ordre_de_l_auteur(self):
        objets = [objet(5, VER, "Libelle-Cinq"), objet(6, DEV, "Libelle-Six", "inactive")]
        code, sortie = self.migrer(contenu="statut,nom_court,libelle,type,id\n" + "".join(
            f"{o[4]},{o[3]},{o[2]},{o[1]},{o[0]}\n" for o in objets))
        self.assertEqual(code, 0, sortie)
        ordre_auteur = yaml.safe_load((self.flux / "equipes-jira.yaml").read_text(encoding="utf-8"))
        (self.flux / "equipes-jira.yaml").unlink()
        code, sortie = self.migrer(*objets)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(yaml.safe_load((self.flux / "equipes-jira.yaml").read_text(encoding="utf-8")), ordre_auteur)

    def test_colonne_nominative_refusee_avant_toute_lecture_de_ses_cellules(self):
        code, sortie = self.migrer(contenu=ENTETE + ",responsable\n" + f"1,{DEV},Libelle-1,SC1,active,{SENTINELLE}-Personne\n")
        self.tout_refuse(code, sortie, "liste Assets refusée : colonne inconnue en position 6")
        self.assertNotIn("responsable", sortie)

    def test_colonne_manquante(self):
        code, sortie = self.migrer(contenu="id,type,libelle,nom_court\n1,Development Team,L,S\n")
        self.tout_refuse(code, sortie, "liste Assets refusée : colonne manquante statut")

    def test_type_entoure_d_espaces_accepte(self):
        code, sortie = self.migrer(objet(1, f"  {VER}  "))
        self.assertEqual(code, 0, sortie)
        entrees = yaml.safe_load((self.flux / "equipes-jira.yaml").read_text(encoding="utf-8"))["teams"]
        self.assertEqual(entrees[0]["type"], VER)

    def test_libelle_vide_avec_un_nom_court_refuse_et_compte(self):
        code, sortie = self.migrer(objet(1), objet(2, libelle=" "))
        self.tout_refuse(code, sortie, "liste Assets refusée : libelle vide, 1 lignes concernées (première : ligne 3)")

    def test_identifiant_vide_sur_deux_lignes_refus_avec_le_compte(self):
        code, sortie = self.migrer(objet(1), ("", DEV, "Libelle-A", "SCA", "active"), objet(3), ("", VER, "Libelle-B", "SCB", "draft"))
        self.tout_refuse(code, sortie, "liste Assets refusée : id vide, 2 lignes concernées (première : ligne 3)")

    def test_type_vide_refus_avec_le_compte(self):
        code, sortie = self.migrer(objet(1), objet(2, ""))
        self.tout_refuse(code, sortie, "liste Assets refusée : type vide, 1 lignes concernées (première : ligne 3)")

    def test_statut_vide_refus_avec_le_compte(self):
        code, sortie = self.migrer(objet(1, statut=""), objet(2, statut=""), objet(3, statut=""))
        self.tout_refuse(code, sortie, "liste Assets refusée : statut vide, 3 lignes concernées (première : ligne 2)")

    def test_libelle_et_nom_court_vides_sur_la_meme_ligne_refus_compte(self):
        code, sortie = self.migrer(objet(1), objet(2, libelle="", court=""), objet(3, libelle="", court=""))
        self.tout_refuse(code, sortie, "liste Assets refusée : libelle et nom_court vides sur la même ligne, 2 lignes concernées "
                                       "(première : ligne 3)")

    def test_refus_des_cellules_vides_en_anglais(self):
        code, sortie = self.migrer(objet(1, libelle="", court=""), objet(2, statut=""), extra=("--language", "en"))
        self.assertEqual(code, 1, sortie)
        self.assertIn("assets list refused: statut empty, 1 lines concerned (first: line 3)", sortie)
        self.assertIn("assets list refused: label and short name empty on the same line, 1 lines concerned (first: line 2)", sortie)

    def test_identifiant_non_numerique_ligne_sans_valeur(self):
        code, sortie = self.migrer(objet(1), ("12a", DEV, "L", "S", "active"))
        self.tout_refuse(code, sortie, "liste Assets refusée : id non numérique à la ligne 3")
        self.assertNotIn("12a", sortie)

    def test_type_hors_des_quatre_noms_meme_par_la_casse(self):
        code, sortie = self.migrer(objet(1, "development team"))
        self.tout_refuse(code, sortie, "liste Assets refusée : type autre que les quatre sous-types de Team à la ligne 2")
        self.assertNotIn("development team", sortie)

    def test_statut_hors_des_quatre_valeurs(self):
        code, sortie = self.migrer(objet(1, statut="archived"))
        self.tout_refuse(code, sortie, "liste Assets refusée : statut autre que active, draft, inactive ou discarded à la ligne 2")
        self.assertNotIn("archived", sortie)

    def test_statut_accepte_sans_tenir_compte_de_la_casse(self):
        code, sortie = self.migrer(objet(1, statut=" ACTIVE "))
        self.assertEqual(code, 0, sortie)

    def test_identifiant_en_double_les_deux_lignes_sans_valeur(self):
        code, sortie = self.migrer(objet(1), objet(2), objet(1, libelle="Autre"))
        self.tout_refuse(code, sortie, "liste Assets refusée : identifiant en double aux lignes 2, 4")

    def test_meme_libelle_avec_deux_types(self):
        code, sortie = self.migrer(objet(1, DEV, "Meme"), objet(2, VER, "Meme"))
        self.tout_refuse(code, sortie, "liste Assets refusée : même libellé avec deux types aux lignes 2, 3")

    def test_chemin_hors_du_dossier_des_flux_ou_mal_nomme(self):
        autre = self.ws / "equipes-assets-complet-2026-10-16.csv"
        autre.write_text(liste(objet(1)), encoding="utf-8")
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(autre))
        self.tout_refuse(code, sortie, "liste Assets absente ou hors du dossier des flux : rien n'est écrit")
        code, sortie = self.migrer(objet(1), nom="liste.csv")
        self.tout_refuse(code, sortie, "liste Assets absente ou hors du dossier des flux : rien n'est écrit")
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(self.flux / "equipes-assets-complet-2030-01-01.csv"))
        self.tout_refuse(code, sortie, "liste Assets absente ou hors du dossier des flux : rien n'est écrit")

    def test_option_sans_chemin_ou_absente_code_2(self):
        for argv in (["migrate-teams"], ["migrate-teams", "--from-assets"]):
            code, sortie = self.lancer(*argv)
            self.assertEqual(code, 2, sortie)
        self.assertEqual(self.fichiers(), ["flux.yaml"])               # aucun catalogue écrit

    def test_valeurs_sentinelles_absentes_et_nom_court_non_ecrit(self):
        code, sortie = self.migrer(objet(1, libelle=f"{SENTINELLE}-Libelle", court=f"{SENTINELLE}-Court"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn(f"{SENTINELLE}-Court", sortie)
        ecrit = (self.flux / "equipes-jira.yaml").read_text(encoding="utf-8")
        self.assertNotIn("Court", ecrit)
        self.assertIn(f"{SENTINELLE}-Libelle", ecrit)

    def test_l_identifiant_est_ecrit_tel_que_lu_sans_conversion(self):
        code, sortie = self.migrer(objet("  007 "))
        self.assertEqual(code, 0, sortie)
        entrees = yaml.safe_load((self.flux / "equipes-jira.yaml").read_text(encoding="utf-8"))["teams"]
        self.assertEqual(entrees[0]["jira_team_ids"], ["007"])
        self.assertIsInstance(entrees[0]["jira_team_ids"][0], str)

    def test_refus_en_anglais(self):
        code, sortie = self.migrer(objet(1, statut="archived"), extra=("--language", "en"))
        self.assertIn("assets list refused: status other than active, draft, inactive or discarded at line 2", sortie)

    def test_check_teams_accepte_un_nom_court_vide_comme_migrate_teams(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.liste_assets(objet(1, court=""), objet(2, statut="inactive", court=""))
        code, sortie = self.lancer("check-teams")
        self.assertNotIn("liste Assets refusée", sortie)
        self.assertIn("liste Assets utilisée", sortie)
        self.liste_assets(objet(1, court=""), ("", DEV, "Libelle-A", "", "active"))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("liste Assets refusée : id vide, 1 lignes concernées (première : ligne 3)", sortie)

    def test_check_teams_lit_la_liste_avec_la_meme_lecture_stricte(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.liste_assets(objet(1, "development team"))
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("liste Assets refusée : type autre que les quatre sous-types de Team à la ligne 2", sortie)


class MigrationDepuisAssets(Socle):
    """5.2, 5.7, 5.8, 5.9 : catalogue écrit une fois, drapeau obsolète, comparaison avec l'ancienne table, types."""

    def migrer(self, *objets, extra=(), **options):
        chemin = self.liste_assets(*objets, **options)
        return self.lancer("migrate-teams", "--from-assets", str(chemin), *extra)

    def catalogue_ecrit(self):
        return yaml.safe_load((self.flux / "equipes-jira.yaml").read_text(encoding="utf-8"))["teams"]

    def test_premiere_migration(self):
        self.ecrire("organisation.yaml", REF)
        # trois objets actifs ; « Equipe A » est le nom d'une équipe du référentiel qui ne liste pas l'identifiant 900
        code, sortie = self.migrer(objet(900, DEV, "Equipe A"), objet(901, VER, "Libelle-Quimbo-Plinth"), objet(902, OTH, "Libelle-Vexor-Glimmer"))
        self.assertEqual(code, 0, sortie)
        entrees = self.catalogue_ecrit()
        self.assertEqual([(e["name"], e["jira_team_ids"], e["type"]) for e in entrees],
                         [("Equipe A", ["900"], DEV), ("Libelle-Quimbo-Plinth", ["901"], VER), ("Libelle-Vexor-Glimmer", ["902"], OTH)])
        self.assertIn("catalogue écrit : 3 entrées, 1 identifiants nommés comme une équipe du référentiel, à placer dans le référentiel", sortie)
        self.assertIn("identifiants nommés comme une équipe du référentiel : 900", sortie)
        self.assertIn("types d'équipe écrits : 1 développement, 1 vérification, 0 gestion de produit, 1 autres", sortie)
        self.assertEqual(stat.S_IMODE((self.flux / "equipes-jira.yaml").stat().st_mode), 0o600)
        self.assertEqual((self.flux / "organisation.yaml").read_text(encoding="utf-8"), REF)
        self.assertNotIn("Equipe A", sortie)

    def test_identifiant_nomme_comme_une_equipe_du_referentiel_et_liste_par_elle_non_signale(self):
        self.ecrire("organisation.yaml", REF)
        code, sortie = self.migrer(objet(1, DEV, "Equipe A"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 entrées, 0 identifiants nommés comme une équipe du référentiel", sortie)
        self.assertNotIn("identifiants nommés comme une équipe du référentiel :", sortie)

    def test_identifiant_deja_dans_le_referentiel_sous_un_autre_nom_ecrit_et_non_signale(self):
        self.ecrire("organisation.yaml", REF)
        code, sortie = self.migrer(objet(1, VER, "Autre-Nom"))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.catalogue_ecrit()[0]["jira_team_ids"], ["1"])
        self.assertEqual(self.catalogue_ecrit()[0]["type"], VER)
        self.assertIn("0 identifiants nommés comme une équipe du référentiel", sortie)
        self.assertNotIn("Autre-Nom", sortie.replace("labels", ""))

    def test_aucune_phrase_des_identifiants_a_deplacer_dans_le_referentiel(self):
        self.ecrire("organisation.yaml", REF)
        for langue in ("fr", "en"):
            (self.flux / "equipes-jira.yaml").unlink(missing_ok=True)
            _, sortie = self.migrer(objet(1), extra=("--language", langue))
            self.assertNotIn("à déplacer", sortie)
            self.assertNotIn("to move", sortie)

    def test_lecture_de_la_liste_un_objet_par_statut(self):
        code, sortie = self.migrer(objet(1, statut="active"), objet(2, statut="draft"), objet(3, statut="inactive"), objet(4, statut="discarded"))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.catalogue_ecrit()), 4)
        self.assertIn("liste Assets lue : 4 objets, 1 actifs, 1 brouillons (écrits comme actifs), 1 inactifs, 1 abandonnés", sortie)
        (self.flux / "equipes-jira.yaml").unlink()
        _, sortie = self.migrer(objet(1, statut="active"), objet(2, statut="draft"), objet(3, statut="inactive"),
                                objet(4, statut="discarded"), extra=("--language", "en"))
        self.assertIn("assets list read: 4 objects, 1 active, 1 draft (written as active), 1 inactive, 1 discarded", sortie)

    # --- repli sur le libellé quand nom_court est vide (R-87)
    REPLIS = [objet(1, DEV, "Zorblax-Alpha", "active", ""), objet(2, VER, "Quimbo-Plinth", "inactive", ""),
              objet(3, OTH, "Vexor-Glimmer", "draft", ""), objet(4, DEV, "Frondel-Mastic", "discarded", ""),
              objet(5, DEV, "Normal-Present")]

    def test_nom_court_vide_repli_sur_le_libelle_avec_avertissement_par_statut(self):
        code, sortie = self.migrer(*self.REPLIS)
        self.assertEqual(code, 0, sortie)
        entrees = self.catalogue_ecrit()
        self.assertEqual([(e["name"], e.get("obsolete")) for e in entrees],
                         [("Zorblax-Alpha", None), ("Quimbo-Plinth", True), ("Vexor-Glimmer", None), ("Frondel-Mastic", True),
                          ("Normal-Present", None)])
        self.assertIn("nom_court vide, libellé repris : 4 lignes (1 actives, 1 inactives, 1 brouillons écrits comme actifs, "
                      "1 abandonnées)", sortie)
        avertissement = [ligne for ligne in sortie.splitlines() if "nom_court vide" in ligne]
        self.assertEqual(len(avertissement), 1)
        for libelle in ("Zorblax", "Quimbo", "Vexor", "Frondel", "Normal"):
            self.assertNotIn(libelle, avertissement[0])
        avant_proposition = sortie.split("libellés à ajouter à la liste des noms sensibles")[0]
        for libelle in ("Zorblax", "Quimbo", "Vexor", "Frondel", "Normal"):
            self.assertNotIn(libelle, avant_proposition)

    def test_libelles_repris_proposes_pour_les_noms_sensibles(self):
        code, sortie = self.migrer(*self.REPLIS, objet(6, DEV, "Core", "active", ""))
        self.assertEqual(code, 0, sortie)
        proposition = sortie.split("libellés à ajouter à la liste des noms sensibles")[1]
        for libelle in ("Zorblax-Alpha", "Quimbo-Plinth", "Vexor-Glimmer", "Frondel-Mastic"):
            self.assertIn(libelle, proposition)
        self.assertNotIn("Core", proposition.split("libellés écartés")[0].split("\n", 1)[1])      # filtré comme les autres (trop court)

    def test_aucun_repli_aucune_phrase_d_avertissement(self):
        code, sortie = self.migrer(objet(1))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("nom_court vide", sortie)

    def test_avertissement_du_repli_en_anglais(self):
        _, sortie = self.migrer(*self.REPLIS, extra=("--language", "en"))
        self.assertIn("short name empty, label used: 4 lines (1 active, 1 inactive, 1 draft written as active, 1 discarded)", sortie)

    def test_catalogue_deja_present_rien_n_est_ecrit(self):
        existant = self.ecrire("equipes-jira.yaml", catalogue(entree(f"{SENTINELLE}-X", "'1'")))
        avant = existant.read_bytes()
        code, sortie = self.migrer(objet(2))
        self.assertEqual(code, 1, sortie)
        self.assertIn("catalogue déjà présent : rien n'est écrit", sortie)
        self.assertEqual(existant.read_bytes(), avant)
        self.assertNotIn(SENTINELLE, sortie)
        _, sortie = self.migrer(objet(2), extra=("--language", "en"))
        self.assertIn("catalogue already present: nothing written", sortie)

    def test_deux_objets_de_meme_libelle_et_de_meme_type_une_seule_entree(self):
        code, sortie = self.migrer(objet(1, libelle="Meme"), objet(2, libelle="Meme"))
        self.assertEqual(code, 0, sortie)
        entrees = self.catalogue_ecrit()
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0]["jira_team_ids"], ["1", "2"])

    def test_aucun_objet_ecarte_ni_trie(self):
        objets = [objet(30, libelle="Zeta"), objet(10, libelle="Alpha", statut="inactive"), objet(20, libelle="Mu", statut="discarded")]
        code, sortie = self.migrer(*objets)
        self.assertEqual(code, 0, sortie)
        self.assertEqual([e["name"] for e in self.catalogue_ecrit()], ["Zeta", "Alpha", "Mu"])      # ordre de la liste

    def test_le_catalogue_ecrit_se_relit_avec_le_lecteur_strict(self):
        import flow_organisation as org
        self.migrer(objet(1), objet(2, statut="inactive"), objet(3, OTH, statut="draft"))
        cat = org.charger_catalogue_si_present(self.flux / "equipes-jira.yaml")
        self.assertEqual([e.obsolete for e in cat.entrees], [False, True, False])

    # --- 5.7 drapeau obsolète
    def test_inactive_et_discarded_ecrits_obsoletes_et_listes(self):
        self.ecrire("organisation.yaml", REF)
        code, sortie = self.migrer(objet(1, libelle="Libelle-Un", statut="inactive"), objet(500, statut="discarded"), objet(501))
        self.assertEqual(code, 0, sortie)
        entrees = self.catalogue_ecrit()
        self.assertEqual([e.get("obsolete") for e in entrees], [True, True, None])
        self.assertIn("entrées écrites obsolètes (inactives ou abandonnées dans Assets) : 2", sortie)
        self.assertIn("identifiants écrits obsolètes : 1 ; 500", sortie)
        ecrit = (self.flux / "equipes-jira.yaml").read_text(encoding="utf-8")
        self.assertNotIn("obsolete_to_confirm", ecrit)
        self.assertNotIn("#", ecrit)

    def test_phrases_obsoletes_en_anglais(self):
        _, sortie = self.migrer(objet(1, statut="inactive"), extra=("--language", "en"))
        self.assertIn("entries written obsolete (inactive or discarded in Assets): 1", sortie)
        self.assertIn("identifiers written obsolete: 1", sortie)

    def test_brouillon_traite_comme_actif_sans_drapeau(self):
        code, sortie = self.migrer(objet(1, statut="draft"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("obsolete", self.catalogue_ecrit()[0])
        self.assertIn("1 brouillons (écrits comme actifs)", sortie)
        self.assertIn("entrées écrites obsolètes (inactives ou abandonnées dans Assets) : 0", sortie)
        self.assertNotIn("identifiants écrits obsolètes", sortie)

    def test_entree_aux_statuts_meles_ecrite_sans_drapeau_et_listee(self):
        code, sortie = self.migrer(objet(1, libelle="Meme", statut="active"), objet(2, libelle="Meme", statut="inactive"))
        self.assertEqual(code, 0, sortie)
        entrees = self.catalogue_ecrit()
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0]["jira_team_ids"], ["1", "2"])
        self.assertNotIn("obsolete", entrees[0])
        self.assertIn("entrées aux objets actifs et inactifs, écrites non obsolètes : 1", sortie)
        self.assertIn("identifiants des entrées aux statuts mêlés : 1 ; 2", sortie)
        self.assertIn("entrées écrites obsolètes (inactives ou abandonnées dans Assets) : 0", sortie)

    def test_deux_objets_fusionnes_tous_inactifs_ecrits_obsoletes(self):
        code, sortie = self.migrer(objet(1, libelle="Meme", statut="inactive"), objet(2, libelle="Meme", statut="discarded"))
        self.assertEqual(code, 0, sortie)
        self.assertTrue(self.catalogue_ecrit()[0]["obsolete"])
        self.assertIn("entrées aux objets actifs et inactifs, écrites non obsolètes : 0", sortie)

    def test_phrase_des_statuts_meles_en_anglais(self):
        _, sortie = self.migrer(objet(1, libelle="Meme"), objet(2, libelle="Meme", statut="inactive"), extra=("--language", "en"))
        self.assertIn("entries with active and inactive objects, written not obsolete: 1", sortie)
        self.assertIn("identifiers of entries with mixed statuses: 1; 2", sortie)

    # --- 5.8 comparaison avec l'ancienne table
    def test_comparaison_avec_l_ancienne_table_divergente(self):
        self.ecrire("equipes-assets.yaml", f"equipes: {{'1': Libelle-1, '2': {SENTINELLE}-Autre, '9': {SENTINELLE}-Seul}}\n")
        avant = (self.flux / "equipes-assets.yaml").read_bytes()
        code, sortie = self.migrer(objet(1), objet(2), objet(3), objet(4))
        self.assertEqual(code, 0, sortie)
        self.assertIn("ancienne table et liste Assets comparées : 1 identifiants seulement dans la table, 2 seulement dans la liste, "
                      "1 avec un libellé différent", sortie)
        self.assertIn("identifiants seulement dans l'ancienne table : 9", sortie)
        self.assertNotIn(SENTINELLE, sortie)               # aucun libellé de la table (la proposition D9 imprime ceux du catalogue)
        self.assertEqual((self.flux / "equipes-assets.yaml").read_bytes(), avant)
        self.assertNotIn("9", [i for e in self.catalogue_ecrit() for i in e["jira_team_ids"]])

    def test_comparaison_sources_identiques(self):
        self.ecrire("equipes-assets.yaml", "equipes: {'1': Libelle-1, '2': Libelle-2}\n")
        _, sortie = self.migrer(objet(1), objet(2))
        self.assertIn("0 identifiants seulement dans la table, 0 seulement dans la liste, 0 avec un libellé différent", sortie)
        self.assertNotIn("identifiants seulement dans l'ancienne table :", sortie)

    def test_table_absente_aucune_ligne_de_comparaison_et_pas_de_refus(self):
        code, sortie = self.migrer(objet(1))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("comparées", sortie)

    def test_comparaison_en_anglais(self):
        self.ecrire("equipes-assets.yaml", "equipes: {'9': X}\n")
        _, sortie = self.migrer(objet(1), extra=("--language", "en"))
        self.assertIn("former table and assets list compared: 1 identifiers only in the table, 1 only in the list, 0 with a different label", sortie)
        self.assertIn("identifiers only in the former table: 9", sortie)

    # --- 5.9 types
    def test_types_ecrits_un_objet_par_type(self):
        code, sortie = self.migrer(objet(1, DEV), objet(2, VER), objet(3, PRO), objet(4, OTH), objet(5, OTH))
        self.assertEqual(code, 0, sortie)
        self.assertEqual([e["type"] for e in self.catalogue_ecrit()], [DEV, VER, PRO, OTH, OTH])
        self.assertIn("types d'équipe écrits : 1 développement, 1 vérification, 1 gestion de produit, 2 autres", sortie)
        ligne = [l for l in sortie.splitlines() if "types d'équipe écrits" in l][0]
        self.assertNotIn("Libelle", ligne)

    def test_types_en_anglais(self):
        _, sortie = self.migrer(objet(1, DEV), extra=("--language", "en"))
        self.assertIn("team types written: 1 development, 0 verification, 0 product management, 0 other", sortie)

    def test_ordre_des_lignes_de_la_migration(self):
        self.ecrire("equipes-assets.yaml", "equipes: {'9': X}\n")
        _, sortie = self.migrer(objet(1, libelle="Libelle-Distinctif-Zorblax", statut="inactive"),
                                objet(2, libelle="Meme"), objet(3, libelle="Meme", statut="inactive"))
        cles = ["liste Assets lue", "ancienne table et liste", "catalogue écrit", "types d'équipe écrits", "entrées écrites obsolètes",
                "entrées aux objets actifs et inactifs", "libellés à ajouter"]
        positions = [sortie.index(c) for c in cles]
        self.assertEqual(positions, sorted(positions))

    def test_aucun_autre_fichier_que_le_catalogue_n_est_ecrit(self):
        self.ecrire("noms-sensibles.txt", "Quelquechose\n")
        avant = self.fichiers()
        liste = self.liste_assets(objet(1, libelle="Libelle-Distinctif-Zorblax"))
        apres_liste = self.fichiers()
        self.lancer("migrate-teams", "--from-assets", str(liste))
        self.assertEqual(sorted(set(self.fichiers()) - set(apres_liste)), ["equipes-jira.yaml"])
        self.assertEqual((self.flux / "noms-sensibles.txt").read_text(encoding="utf-8"), "Quelquechose\n")      # jamais lue ni modifiée
        self.assertEqual(sorted(set(apres_liste) - set(avant)), [liste.name])

    def test_le_fichier_temporaire_est_retire_apres_un_echec_d_ecriture(self):
        """R-84 : un échec avant le renommage ne laisse pas `equipes-jira.tmp` (il ferait échouer le lancement suivant)."""
        liste = self.liste_assets(objet(1, libelle="Libelle-Distinctif-Zorblax"))
        avant = self.fichiers()
        with mock.patch("os.replace", side_effect=OSError("renommage impossible")):
            code, _ = self.lancer("migrate-teams", "--from-assets", str(liste))
        self.assertNotEqual(code, 0)
        self.assertEqual(self.fichiers(), avant)
        self.assertFalse((self.flux / "equipes-jira.tmp").exists())

    def test_le_lancement_suivant_reussit_apres_un_echec_d_ecriture(self):
        liste = self.liste_assets(objet(1, libelle="Libelle-Distinctif-Zorblax"))
        with mock.patch("os.replace", side_effect=OSError("renommage impossible")):
            self.lancer("migrate-teams", "--from-assets", str(liste))
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(liste))
        self.assertEqual(code, 0, sortie)
        self.assertTrue((self.flux / "equipes-jira.yaml").exists())


class ProposeDesLibellesDistinctifs(Socle):
    """5.4 : filtre du design D9 (longueur minimale 6, mots de trois lettres ou moins, mots courants), proposition imprimée seulement."""

    def proposition(self, *libelles, extra=()):
        objets = [objet(100 + i, libelle=l) for i, l in enumerate(libelles)]
        chemin = self.liste_assets(*objets)
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin), *extra)
        self.assertEqual(code, 0, sortie)
        lignes = sortie.splitlines()
        i = next(k for k, l in enumerate(lignes) if l.startswith(("libellés à ajouter", "labels to add")))
        k = int(lignes[i].rsplit(":", 1)[1])
        ecartes = int(lignes[i + 1 + k].rsplit(":", 1)[1])
        return lignes[i + 1:i + 1 + k], ecartes

    def test_longueur_minimale_six_caracteres(self):
        proposes, ecartes = self.proposition("Zorbl", "Zorblx")
        self.assertEqual(proposes, ["Zorblx"])
        self.assertEqual(ecartes, 1)

    def test_acronyme_plus_long_que_le_minimum_ecarte(self):
        proposes, ecartes = self.proposition("ABC DEF GHI", "XY-ZW-QRS")
        self.assertEqual(proposes, [])
        self.assertEqual(ecartes, 2)

    def test_mots_courants_et_acronymes_ecartes_en_majuscules_et_avec_accents(self):
        proposes, ecartes = self.proposition("Équipe Support PLATEFORME", "TEAM SERVICES API", "ÉQUIPE données")
        self.assertEqual(proposes, [])
        self.assertEqual(ecartes, 3)

    def test_libelle_distinctif_propose_et_compte_a_part(self):
        proposes, ecartes = self.proposition("Zorblax Quimbo", "Ab", "Support", "Wumpa Team")
        self.assertEqual(proposes, ["Zorblax Quimbo", "Wumpa Team"])
        self.assertEqual(ecartes, 2)

    def test_proposition_en_anglais(self):
        proposes, ecartes = self.proposition("Zorblax Quimbo", extra=("--language", "en"))
        self.assertEqual(proposes, ["Zorblax Quimbo"])

    def comptes(self, *libelles, extra=()):
        chemin = self.liste_assets(*[objet(100 + i, libelle=l) for i, l in enumerate(libelles)])
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin), *extra)
        self.assertEqual(code, 0, sortie)
        return sortie

    def test_compte_des_libelles_ecartes_comme_mots_courants(self):
        sortie = self.comptes("Delivery Platform", "Zorblax Quimbo", "ABC DEF GHI", "Product Discovery")
        self.assertIn("libellés écartés comme mots courants : 2", sortie)

    def test_compte_des_mots_courants_en_anglais(self):
        sortie = self.comptes("Delivery Platform", "Zorblax Quimbo", extra=("--language", "en"))
        self.assertIn("labels left out as common words: 1", sortie)

    def test_le_compte_suit_celui_du_filtre_et_n_imprime_aucun_libelle(self):
        sortie = self.comptes("Quality Integration", "Zorblax Quimbo")
        lignes = sortie.splitlines()
        i = next(k for k, l in enumerate(lignes) if l.startswith("libellés écartés par le filtre"))
        self.assertTrue(lignes[i + 1].startswith("libellés écartés comme mots courants"))
        self.assertNotIn("Quality", sortie)
        self.assertNotIn("Integration", sortie)

    def test_mots_courants_du_metier_ne_sont_pas_proposes(self):
        proposes, ecartes = self.proposition("Release Engineering", "Platform Discovery", "Integration Quality")
        self.assertEqual(proposes, [])

    def test_les_libelles_ecartes_ne_sont_pas_imprimes(self):
        self.liste_assets(objet(1, libelle="Support"), objet(2, libelle="ZZECARTE"))
        _, sortie = self.lancer("migrate-teams", "--from-assets", str(self.flux / "equipes-assets-complet-2026-10-16.csv"))
        self.assertNotIn("Support", sortie)

    def test_la_liste_des_noms_sensibles_n_est_ni_lue_ni_ecrite(self):
        self.ecrire("noms-sensibles.txt", "Intact\n")
        lue = []
        vrai = type(self.flux).read_text
        with mock.patch.object(type(self.flux), "read_text", lambda p, *a, **k: (lue.append(p.name), vrai(p, *a, **k))[1]):
            self.liste_assets(objet(1, libelle="Zorblax Quimbo"))
            self.lancer("migrate-teams", "--from-assets", str(self.flux / "equipes-assets-complet-2026-10-16.csv"))
        self.assertNotIn("noms-sensibles.txt", lue)
        self.assertEqual((self.flux / "noms-sensibles.txt").read_text(encoding="utf-8"), "Intact\n")

    def test_constante_de_longueur_minimale(self):
        import export_jira_api_equipes as eq
        self.assertEqual(eq.LONGUEUR_MINIMALE, 6)
        self.assertTrue(eq.est_distinctif("Zorblx"))
        self.assertFalse(eq.est_distinctif("Zorbl"))
        self.assertFalse(eq.est_distinctif("Équipe"))
        self.assertFalse(eq.est_distinctif("équipe SUPPORT api"))
        self.assertTrue(eq.est_distinctif("api zorblax"))


class CataloguesDeMessages(unittest.TestCase):
    """tools/export_jira_api_equipes_messages.py : mêmes clés et mêmes champs en français et en anglais, fusionnés au catalogue."""

    def test_memes_cles_et_memes_champs_dans_les_deux_langues(self):
        from export_jira_api_equipes_messages import CATALOGS_EQUIPES
        from export_jira_api_messages import CATALOGS
        from messages import check_catalogs
        self.assertEqual(check_catalogs(CATALOGS_EQUIPES), [])
        for langue, messages in CATALOGS_EQUIPES.items():
            self.assertLessEqual(set(messages), set(CATALOGS[langue]))


class AideEtSousCommandes(Socle):
    """5.5 : seules diagnose, fields, export, check-teams et migrate-teams sont listées."""

    def test_aide_liste_les_cinq_sous_commandes(self):
        code, sortie = self.lancer("--help")
        self.assertEqual(code, 0)
        # review-teams rejoint la liste (change names-and-team-review) : l'attendu d'origine ne la connaissait pas
        # extract-teams rejoint la liste (change team-names-readable, tâche 3.2) : extension de l'attendu
        self.assertIn("{diagnose,fields,export,check-teams,migrate-teams,review-teams,extract-teams}", sortie)
        self.assertNotRegex(sortie, r"(?m)^\s{2,}(compare|teams-table)\b")

    def test_l_aide_de_migrate_teams_montre_l_option_obligatoire(self):
        code, sortie = self.lancer("migrate-teams", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--from-assets", sortie)

    def test_docstring_du_module(self):
        doc = ex.__doc__
        for commande in ("diagnose", "fields", "export", "check-teams", "migrate-teams"):
            self.assertIn(f"export_jira_api.py {commande}", doc)
        self.assertIn("--from-assets", doc)
        self.assertNotIn("teams-table ", doc.split("Les sous-commandes teams-table et compare")[0])


if __name__ == "__main__":
    unittest.main()
