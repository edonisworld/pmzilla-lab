"""tools/flux_config.py : noms anglais des réglages de flux.yaml, anciens noms refusés avec le nom actuel, migration.

Données inventées ; aucun accès à Flux-Lab/ ni à Jira."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_config  # noqa: E402
from yaml_strict import charger  # noqa: E402

ANCIEN = """# réglages de la série (commentaire conservé)
jira_site: https://exemple.atlassian.net
colonnes:
  type: [Issue Type]
  etat: [Status]
  categorie: [Status Category]
  cle: [Issue key]
  cree: [Created]
  resolu: [Resolved]
  motif: [Resolution]
  debut: [Status Category Changed]
  equipe: [Team]
  parent: [Parent]
  modifie: [Updated]
  story_points: [Story Points]
etats_en_cours: [In Progress]
etats_a_faire: [To Do]
etats_attente: [Ready for]
motifs_exclus: [Rejected]
types_portefeuille: [Epic]
projets_exclus: [BUG]
projets_perimetre: [ABC]
segments:
  definition: [Open]
  pret: [Ready]            # commentaire de fin de ligne
  implementation: [In Progress]
  revue_verification: [In Review]
  acceptation: [Accepted]
segments_hors_calcul:
  a_faire: [Backlog]
  termine: [Done]
point_engagement: pret
separateur_equipes: ";"
seuil_fermetures_groupees: 5
motifs_fermetures_groupees: [Done]
serie_par_defaut: serie-x
noms_projets:
  ABC: Alpha
tableaux:
  series:
    - nom: serie-a
      dependances: dep-a
      dependances_projets: dep-p
      base: ref-a
    - nom: serie-b
jira_email: moi@exemple.org
jira_jeton: scopes
export_champ_equipe: customfield_1
export_entete_equipe: Team
export_champ_verification: customfield_2
export_entete_verification: Verification
export_fuseau: Europe/Paris
types_bloquants: [Blocks]
types_attente: [Relates]
jql_export: "project = ABC"
"""


def sans_avertissement(f, *args):
    tampon = io.StringIO()
    with contextlib.redirect_stderr(tampon):
        resultat = f(*args)
    return resultat, tampon.getvalue()


class Tables(unittest.TestCase):
    def test_vingt_cinq_cles_de_premier_niveau(self):
        self.assertEqual(len(flux_config.TOP), 25)

    def test_noms_du_plan(self):
        self.assertEqual(flux_config.TOP["etats_a_faire"], "todo_states")
        self.assertEqual(flux_config.TOP["types_portefeuille"], "portfolio_types")
        self.assertEqual(flux_config.TOP["jira_jeton"], "jira_token_type")
        self.assertEqual(flux_config.COLUMNS["etat"], "status")
        self.assertEqual(flux_config.COLUMNS["motif"], "resolution")
        self.assertEqual(flux_config.COLUMNS["debut"], "category_changed")
        self.assertEqual(flux_config.SEGMENTS["revue_verification"], "review_verification")
        self.assertEqual(flux_config.UNCOUNTED, {"a_faire": "todo", "termine": "done"})
        self.assertEqual(flux_config.BOARD, {"nom": "name", "dependances": "dependencies",
                                        "dependances_projets": "project_dependencies", "base": "baseline"})

    def test_noms_inchanges_hors_table(self):
        for cle in flux_config.INCHANGEES:
            self.assertNotIn(cle, flux_config.TOP)


class VersLesNomsInternes(unittest.TestCase):
    def test_ancien_nom_refuse_avec_le_nom_actuel(self):
        with self.assertRaises(SystemExit) as c:
            flux_config.to_internal({"etats_a_faire": "%d"})
        self.assertNotEqual(c.exception.code, 0)
        self.assertIn("« etats_a_faire » n'existe plus ; utiliser « todo_states »", str(c.exception))

    def test_nouveau_nom_sans_avertissement(self):
        interne, erreur = sans_avertissement(flux_config.to_internal, {"todo_states": "%d", "in_progress_states": ["A"],
                                             "columns": {"status": ["S"], "team": ["T"]},
                                             "commitment_point": "ready", "jira_token_type": "scoped"})
        self.assertEqual(interne, {"etats_a_faire": "%d", "etats_en_cours": ["A"],
                                   "colonnes": {"etat": ["S"], "equipe": ["T"]},
                                   "point_engagement": "pret", "jira_jeton": "scopes"})
        self.assertEqual(erreur, "")

    def test_sous_cles_et_series(self):
        brut = {"boards": {"series": [{"name": "a", "dependencies": "d", "baseline": "b"}]},
                "segments": {"ready": ["R"], "review_verification": ["V"], "definition": ["D"]},
                "uncounted_segments": {"todo": ["T"], "done": ["F"]}}
        interne, erreur = sans_avertissement(flux_config.to_internal, brut)
        self.assertEqual(interne["tableaux"], {"series": [{"nom": "a", "dependances": "d", "base": "b"}]})
        self.assertEqual(interne["segments"], {"pret": ["R"], "revue_verification": ["V"], "definition": ["D"]})
        self.assertEqual(interne["segments_hors_calcul"], {"a_faire": ["T"], "termine": ["F"]})
        self.assertEqual(erreur, "")

    def refus(self, brut) -> str:
        with self.assertRaises(flux_config.ErreurConfig) as c:
            flux_config.to_internal(brut)
        self.assertNotEqual(c.exception.code, 0)
        return str(c.exception)

    def test_ancien_nom_de_sous_cle_refuse(self):
        self.assertIn("« columns.etat » n'existe plus ; utiliser « columns.status »", self.refus({"columns": {"etat": ["S"]}}))
        self.assertIn("« segments.pret » n'existe plus ; utiliser « segments.ready »", self.refus({"segments": {"pret": ["R"]}}))

    def test_ancienne_valeur_refusee(self):
        self.assertIn("valeur « pret » du réglage commitment_point n'existe plus ; utiliser « ready »",
                      self.refus({"commitment_point": "pret"}))
        self.assertIn("valeur « classique » du réglage jira_token_type n'existe plus ; utiliser « classic »",
                      self.refus({"jira_token_type": "classique"}))

    def test_ancien_et_nouveau_nom_ensemble_refuses_sur_l_ancien(self):
        for brut in ({"etats_a_faire": "x", "todo_states": "y"}, {"todo_states": "y", "etats_a_faire": "x"}):
            self.assertIn("« etats_a_faire » n'existe plus ; utiliser « todo_states »", self.refus(brut))

    def test_types_exclus_refuse(self):
        self.assertIn("« types_exclus » n'existe plus ; utiliser « portfolio_types »", self.refus({"types_exclus": ["Epic"]}))

    def test_le_message_ne_montre_aucune_valeur(self):
        self.assertNotIn("Secret", self.refus({"etats_a_faire": "Secret"}))
        self.assertNotIn("Secret", self.refus({"types_exclus": ["Secret"]}))

    def test_cles_inconnues_et_inchangees_conservees(self):
        interne, erreur = sans_avertissement(flux_config.to_internal, {"jira_site": "x", "jql_export": "q", "autre": 1})
        self.assertEqual(interne, {"jira_site": "x", "jql_export": "q", "autre": 1})
        self.assertEqual(erreur, "")

    def test_export_points_field_lu_sans_avertissement_et_migration_inchangee(self):
        interne, erreur = sans_avertissement(flux_config.to_internal, {"export_points_field": "customfield_3"})
        self.assertEqual(interne, {"export_points_field": "customfield_3"})
        self.assertEqual(erreur, "")
        texte = "# note\nexport_points_field: customfield_3\njira_jeton: scopes\n"
        nouveau, changements = flux_config.migrate_text(texte)
        self.assertEqual(nouveau, "# note\nexport_points_field: customfield_3\njira_token_type: scoped\n")
        self.assertTrue(all("customfield_3" not in c for c in changements))

    def test_fichier_vide(self):
        self.assertEqual(flux_config.to_internal(None), {})


class RefusDesAnciennesOptions(unittest.TestCase):
    def refus(self, argv):
        tampon = io.StringIO()
        with contextlib.redirect_stderr(tampon), self.assertRaises(SystemExit) as c:
            flux_config.refuse_old_options(argv, {**flux_config.OPTIONS_COMMUNES, "--cle": "--key"})
        return c.exception.code, tampon.getvalue()

    def test_ancien_nom_refuse_avec_le_nom_actuel(self):
        code, erreur = self.refus(["collecte", "--equipe", "X"])
        self.assertEqual(code, 2)
        self.assertIn("« --equipe » n'existe plus ; utiliser « --team »", erreur)

    def test_forme_avec_egal_refusee(self):
        code, erreur = self.refus(["--cle=K-1"])
        self.assertEqual(code, 2)
        self.assertIn("« --cle » n'existe plus ; utiliser « --key »", erreur)

    def test_nouveau_nom_et_valeurs_inchanges(self):
        argv = ["--team", "--equipe-x", "--nom-long", "a", "--", "--equipe"]
        tampon = io.StringIO()
        with contextlib.redirect_stderr(tampon):
            self.assertEqual(flux_config.refuse_old_options(argv, flux_config.OPTIONS_COMMUNES), argv)
        self.assertEqual(tampon.getvalue(), "")


class VersLesNomsPublics(unittest.TestCase):
    def test_aller_retour(self):
        interne = {"colonnes": {"etat": ["S"]}, "point_engagement": "pret", "segments": {"pret": ["R"]},
                   "tableaux": {"series": [{"nom": "a"}]}, "jira_jeton": "scopes", "etats_a_faire": "x"}
        public = flux_config.to_public(interne)
        self.assertEqual(public, {"columns": {"status": ["S"]}, "commitment_point": "ready",
                                  "segments": {"ready": ["R"]}, "boards": {"series": [{"name": "a"}]},
                                  "jira_token_type": "scoped", "todo_states": "x"})
        retour, erreur = sans_avertissement(flux_config.to_internal, public)
        self.assertEqual(retour, interne)
        self.assertEqual(erreur, "")


class Migration(unittest.TestCase):
    def test_toutes_les_cles_sont_reecrites(self):
        nouveau, changements = flux_config.migrate_text(ANCIEN)
        for ancien in flux_config.TOP:
            if flux_config.TOP[ancien] != ancien:
                self.assertNotIn(f"\n{ancien}:", nouveau, ancien)
                self.assertIn(f"\n{flux_config.TOP[ancien]}:", nouveau, ancien)
        for ancien, nom in list(flux_config.COLUMNS.items()) + list(flux_config.UNCOUNTED.items()):
            if ancien != nom:
                self.assertIn(f"  {nom}:", nouveau)
        for ancien in ("pret", "revue_verification", "acceptation"):
            self.assertNotIn(f"  {ancien}:", nouveau)
        for ancien in ("dependances", "dependances_projets", "base"):
            self.assertNotIn(f"      {ancien}:", nouveau)
        self.assertIn("    - name: serie-a", nouveau)
        self.assertIn("      dependencies: dep-a", nouveau)
        self.assertIn("      project_dependencies: dep-p", nouveau)
        self.assertIn("      baseline: ref-a", nouveau)
        self.assertIn("    - name: serie-b", nouveau)
        self.assertIn("commitment_point: ready", nouveau)
        self.assertIn("jira_token_type: scoped", nouveau)

    def test_commentaires_valeurs_et_cles_inchangees_conservees(self):
        nouveau, _ = flux_config.migrate_text(ANCIEN)
        self.assertIn("# réglages de la série (commentaire conservé)", nouveau)
        self.assertIn("  ready: [Ready]            # commentaire de fin de ligne", nouveau)
        for ligne in ("jira_site: https://exemple.atlassian.net", "jira_email: moi@exemple.org",
                      'jql_export: "project = ABC"', "  type: [Issue Type]", "  parent: [Parent]",
                      "  definition: [Open]", "  implementation: [In Progress]", "  ABC: Alpha", 'team_separator: ";"'):
            self.assertIn(ligne, nouveau)

    def test_le_resultat_se_lit_et_l_ancien_est_refuse(self):
        import yaml
        nouveau, _ = flux_config.migrate_text(ANCIEN)
        lu_nouveau, erreur = sans_avertissement(flux_config.to_internal, yaml.safe_load(nouveau))
        self.assertEqual(erreur, "")
        self.assertEqual(flux_config.to_public(lu_nouveau), yaml.safe_load(nouveau))
        with self.assertRaises(flux_config.ErreurConfig):                # le fichier d'avant la migration est refusé
            flux_config.to_internal(yaml.safe_load(ANCIEN))

    def test_idempotent(self):
        premier, changements = flux_config.migrate_text(ANCIEN)
        second, encore = flux_config.migrate_text(premier)
        self.assertEqual(second, premier)
        self.assertEqual(encore, [])
        self.assertTrue(changements)

    def test_les_changements_ne_contiennent_aucune_valeur(self):
        _, changements = flux_config.migrate_text(ANCIEN)
        texte = "\n".join(changements)
        for valeur in ("exemple.atlassian", "moi@", "Europe/Paris", "customfield_1", "serie-a", "Alpha"):
            self.assertNotIn(valeur, texte)
        self.assertIn("jira_jeton -> jira_token_type", texte)
        self.assertIn("valeur de jira_jeton : scopes -> scoped", texte)

    def test_types_exclus_devient_portfolio_types(self):
        nouveau, _ = flux_config.migrate_text("types_exclus: [Epic]\n")
        self.assertEqual(nouveau, "portfolio_types: [Epic]\n")

    def test_une_cle_d_un_autre_bloc_n_est_pas_touchee(self):
        nouveau, changements = flux_config.migrate_text("noms_projets:\n  etat: Alpha\n  nom: Beta\n")
        self.assertEqual(nouveau, "project_names:\n  etat: Alpha\n  nom: Beta\n")
        self.assertEqual(changements, ["L1 : noms_projets -> project_names"])

    def test_fichier_sans_ancien_nom(self):
        texte = "todo_states: x\ncolumns:\n  status: [S]\n"
        self.assertEqual(flux_config.migrate_text(texte), (texte, []))


class MigrationDeFichier(unittest.TestCase):
    def test_sauvegarde_ecriture_et_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "flux.yaml"
            chemin.write_text(ANCIEN, encoding="utf-8")
            vus = flux_config.migrate_file(chemin, dry_run=True)
            self.assertTrue(vus)
            self.assertEqual(chemin.read_text(encoding="utf-8"), ANCIEN)
            self.assertFalse((Path(d) / "flux.yaml.avant-migration").exists())
            faits = flux_config.migrate_file(chemin)
            self.assertEqual(faits, vus)
            self.assertEqual((Path(d) / "flux.yaml.avant-migration").read_text(encoding="utf-8"), ANCIEN)
            self.assertIn("todo_states:", chemin.read_text(encoding="utf-8"))
            self.assertEqual(flux_config.migrate_file(chemin), [])            # rien à faire la deuxième fois
            self.assertEqual((Path(d) / "flux.yaml.avant-migration").read_text(encoding="utf-8"), ANCIEN)


class DeuxAnciennesClesUneSeuleNouvelle(unittest.TestCase):
    """Garde du renommage : deux réglages distincts ne doivent jamais aboutir au même nom (la migration en écraserait un).
    La seule exception documentée est `types_exclus`, ancien nom d'avant 7.6 de `types_portefeuille` (un seul réglage)."""

    EXCEPTIONS = {"portfolio_types": {"types_exclus", "types_portefeuille"}}

    def groupes(self, table: dict[str, str]) -> dict[str, set[str]]:
        groupes: dict[str, set[str]] = {}
        for ancien, nouveau in table.items():
            groupes.setdefault(nouveau, set()).add(ancien)
        return groupes

    def test_deux_anciennes_cles_distinctes_ne_donnent_jamais_la_meme_nouvelle(self):
        alias = {a: flux_config.TOP[c] for a, c in flux_config.ANCIENS_ALIAS.items()}
        tables = {"TOP + alias": {**flux_config.TOP, **alias},
                  "COLUMNS": flux_config.COLUMNS, "SEGMENTS": flux_config.SEGMENTS, "UNCOUNTED": flux_config.UNCOUNTED,
                  "BOARD": flux_config.BOARD, "OPTIONS_COMMUNES": flux_config.OPTIONS_COMMUNES,
                  "valeur jira_jeton": flux_config.VALEURS["jira_jeton"]}
        for nom, table in tables.items():
            for nouveau, anciens in self.groupes(table).items():
                if len(anciens) > 1:
                    self.assertEqual(anciens, self.EXCEPTIONS.get(nouveau), f"{nom} : {sorted(anciens)} -> {nouveau}")

    def test_l_exception_est_exactement_l_alias_documente(self):
        self.assertEqual(flux_config.ANCIENS_ALIAS, {"types_exclus": "types_portefeuille"})

    def test_aucune_nouvelle_cle_ne_reprend_un_autre_ancien_nom(self):
        """Une nouvelle clé qui serait l'ancien nom d'un autre réglage rendrait la migration ambiguë."""
        anciens = {a for a, n in flux_config.TOP.items() if a != n}
        for ancien, nouveau in flux_config.TOP.items():
            if nouveau != ancien:
                self.assertNotIn(nouveau, anciens, f"{ancien} -> {nouveau}")


class DoubleNomRefuse(unittest.TestCase):
    """Un ancien nom est refusé, avec le numéro de ligne quand le fichier vient de `charger`, et le nom actuel."""

    def lire(self, texte: str):
        return flux_config.to_internal(charger(texte), "flux.yaml")

    def refus(self, texte: str) -> str:
        with self.assertRaises(flux_config.ErreurConfig) as c:
            self.lire(texte)
        return str(c.exception)

    def test_premier_niveau_avec_le_numero_de_ligne(self):
        message = self.refus("jira_site: x\netats_en_cours: a\netats_a_faire: [T]\n")
        self.assertIn("flux.yaml : L2 : « etats_en_cours » n'existe plus ; utiliser « in_progress_states »", message)

    def test_types_exclus_avec_ligne(self):
        message = self.refus("types_exclus: [Epic]\n")
        self.assertIn("L1 : « types_exclus » n'existe plus ; utiliser « portfolio_types »", message)

    def test_sous_cle_d_un_reglage(self):
        message = self.refus("columns:\n  status: [S]\n  cle: [K]\n")
        self.assertIn("L3 : « columns.cle » n'existe plus ; utiliser « columns.key »", message)

    def test_cle_d_une_serie(self):
        message = self.refus("boards:\n  series:\n    - nom: a\n")
        self.assertIn("L3 : « boards.series.nom » n'existe plus ; utiliser « boards.series.name »", message)

    def test_sans_numero_quand_le_dictionnaire_ne_vient_pas_de_charger(self):
        with self.assertRaises(flux_config.ErreurConfig) as c:
            flux_config.to_internal({"etats_a_faire": "a"})
        self.assertTrue(str(c.exception).startswith("flux.yaml : « etats_a_faire » n'existe plus"))

    def test_aucune_valeur_dans_le_message(self):
        self.assertNotIn("Secret", self.refus("etats_a_faire: SecretA\n"))

    def test_un_nom_par_reglage_reste_accepte(self):
        self.assertEqual(self.lire("todo_states: x\ncolumns:\n  status: [S]\n"),
                         {"etats_a_faire": "x", "colonnes": {"etat": ["S"]}})

    def test_le_message_arrete_le_script_avec_le_code_1(self):
        with self.assertRaises(SystemExit) as c:
            flux_config.to_internal({"etats_a_faire": "a"})
        self.assertIsInstance(c.exception.code, str)


FICHIER_DEUX_CLES = """# réglages factices
types_exclus: [Epic]
types_portefeuille: [Epic, Initiative]
projets_exclus: [ABC]
colonnes:
  debut: [Status Category Changed]
"""


class MigrationDeConflits(unittest.TestCase):
    def test_types_exclus_et_types_portefeuille_ensemble_sont_un_conflit(self):
        with self.assertRaises(flux_config.MigrationConflict) as c:
            flux_config.migrate_text(FICHIER_DEUX_CLES)
        self.assertEqual(c.exception.conflits, ["L2 et L3 : « types_exclus » et « types_portefeuille » donnent la même clé « portfolio_types »"])
        self.assertIn("L4 : projets_exclus -> excluded_projects", c.exception.changements)     # le reste est montré
        self.assertNotIn("Initiative", "\n".join(c.exception.conflits + c.exception.changements))

    def test_le_conflit_n_ecrit_rien_meme_hors_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "flux.yaml"
            chemin.write_text(FICHIER_DEUX_CLES, encoding="utf-8")
            for dry in (True, False):
                with self.assertRaises(flux_config.MigrationConflict):
                    flux_config.migrate_file(chemin, dry_run=dry)
            self.assertEqual(chemin.read_text(encoding="utf-8"), FICHIER_DEUX_CLES)
            self.assertFalse((Path(d) / "flux.yaml.avant-migration").exists())

    def test_un_seul_des_deux_noms_se_migre_sans_conflit(self):
        nouveau, changements = flux_config.migrate_text("types_exclus: [Epic]\nprojets_exclus: [ABC]\n")
        self.assertEqual(nouveau, "portfolio_types: [Epic]\nexcluded_projects: [ABC]\n")
        self.assertEqual(changements, ["L1 : types_exclus -> portfolio_types", "L2 : projets_exclus -> excluded_projects"])

    def test_ancien_et_nouveau_nom_du_meme_reglage_sont_un_conflit(self):
        with self.assertRaises(flux_config.MigrationConflict) as c:
            flux_config.migrate_text("etats_a_faire: a\ntodo_states: b\n")
        self.assertEqual(len(c.exception.conflits), 1)

    def test_une_cle_ecrite_deux_fois(self):
        with self.assertRaises(flux_config.MigrationConflict) as c:
            flux_config.migrate_text("projets_exclus: [A]\netats_a_faire: [X]\nprojets_exclus: [B]\n")
        self.assertEqual(c.exception.conflits, ["L1 et L3 : « projets_exclus » est écrite deux fois"])

    def test_la_meme_cle_dans_deux_series_n_est_pas_un_conflit(self):
        texte = "tableaux:\n  series:\n    - nom: a\n      dependances: d1\n    - nom: b\n      dependances: d2\n"
        nouveau, changements = flux_config.migrate_text(texte)
        self.assertIn("    - name: b\n      dependencies: d2", nouveau)
        self.assertEqual(changements, ["L1 : tableaux -> boards", "L3 : tableaux.series.nom -> name",
                                       "L4 : tableaux.series.dependances -> dependencies",
                                       "L5 : tableaux.series.nom -> name", "L6 : tableaux.series.dependances -> dependencies"])

    def test_le_chemin_complet_est_celui_du_fichier(self):
        _, changements = flux_config.migrate_text("colonnes:\n  debut: [X]\n  motif: [Y]\n")
        self.assertEqual(changements, ["L1 : colonnes -> columns", "L2 : colonnes.debut -> category_changed",
                                       "L3 : colonnes.motif -> resolution"])

    def test_debut_et_category_changed_sont_la_meme_colonne(self):
        """`colonnes.debut` : date de changement de catégorie d'état (« Status Category Changed » dans Jira)."""
        self.assertEqual(flux_config.COLUMNS["debut"], "category_changed")
        interne, _ = sans_avertissement(flux_config.to_internal, {"columns": {"category_changed": ["Status Category Changed"]}})
        self.assertEqual(interne, {"colonnes": {"debut": ["Status Category Changed"]}})


class AnciensReglagesRefuses(unittest.TestCase):
    """date_format / format_date et les noms français de colonnes ont disparu avec l'export manuel : un flux.yaml qui les
    contient encore est refusé, avec ce qu'il faut faire."""

    def refus(self, brut) -> str:
        with self.assertRaises(flux_config.ErreurConfig) as c:
            flux_config.to_internal(brut)
        return str(c.exception)

    def test_date_format_sous_les_deux_noms_refuse(self):
        for nom in ("date_format", "format_date"):
            message = self.refus({nom: "%Y-%m-%d", "in_progress_states": ["A"]})
            self.assertIn(f"« {nom} » n'existe plus : l'export de l'API a un format de date fixe", message)
            self.assertNotIn("%Y", message)                      # jamais la valeur

    def test_date_format_n_est_plus_un_reglage_connu(self):
        self.assertNotIn("format_date", flux_config.TOP)
        self.assertNotIn("date_format", flux_config.TOP.values())

    def test_alias_francais_refuses(self):
        self.assertIn("« Statut » n'existe plus", self.refus({"columns": {"status": ["Statut", "Status"]}}))

    def test_alias_francais_compares_sans_casse(self):
        self.assertIn("n'existe plus", self.refus({"columns": {"team": [" ÉQUIPE ", "Team"]}}))

    def test_autres_noms_de_colonnes_gardes(self):
        interne, erreur = sans_avertissement(flux_config.to_internal, {"columns": {"team": ["Squad"]}})
        self.assertEqual(interne, {"colonnes": {"equipe": ["Squad"]}})
        self.assertEqual(erreur, "")

    def test_un_flux_yaml_ancien_est_refuse_par_les_scripts(self):
        import flux_jira
        import dependencies_jira
        with tempfile.TemporaryDirectory() as d:
            flux = Path(d) / "Flux-Lab"
            flux.mkdir()
            (flux / "flux.yaml").write_text('date_format: "%d/%m/%Y"\n', encoding="utf-8")
            for module in (flux_jira, dependencies_jira):
                ancien = module.CONFIG_FILE
                module.CONFIG_FILE = flux / "flux.yaml"
                if hasattr(module, "FLUX_DIR"):
                    module.FLUX_DIR = flux
                try:
                    with self.assertRaises(SystemExit) as c:
                        module.config()
                finally:
                    module.CONFIG_FILE = ancien
                self.assertIn("« date_format » n'existe plus", str(c.exception))


if __name__ == "__main__":
    unittest.main()
