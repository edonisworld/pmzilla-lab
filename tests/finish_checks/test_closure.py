"""
Test statique de la liste de l'outillage protégé par fermeture (tools/finish_protected.txt ; change finish-train-foundations, D16, tâche 3.3).

    uv run python -m unittest discover -s tests/finish_checks -v

Modèle : tests/db/test_couverture_base.py. Aucune base, aucun réseau, aucun lancement de script : tout est lu sur le texte.

La fermeture part des racines (scripts de fin, lanceur de tests, crochets Git, garde du matin, installeur des crochets) et des graines
.py et .sh de tools/, et suit, sans rien exécuter, ce que chacune source, lance ou importe dans tools/ (récursivement), plus tout fichier
suivi dont le chemin figure dans son code (fichiers de données, lus mais non suivis plus loin). Les chemins de la base sont dans le fichier de données
tools/finish_db_paths.txt (finish-single-b3-b6 D15) : plus aucun cas particulier pour un bloc de finish_branch.sh. Le test échoue, en nommant le fichier
ou le motif, quand :
  - un fichier de la fermeture n'est couvert par aucun motif de la liste ;
  - un motif de la liste ne correspond à aucun fichier suivi (sauf un motif permanent ou en attente d'une autre branche, avec sa raison) ;
  - une racine manque ;
  - une exemption de référence, un motif permanent ou un motif en attente n'a pas de raison, ou ne sert plus.

Une exemption est une référence « source -> cible » avec sa raison, jamais un fichier : elle coupe la récursion sur cette arête, la cible
peut entrer par une autre arête.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import finish_checks  # noqa: E402

LISTE = "tools/finish_protected.txt"

# Seule façon de laisser un fichier hors de la fermeture : couper une référence (source, cible) avec sa raison, validée par l'auteur
# (décisions du 2026-10-26, revue 5.1 : E2 les documents, versions et verrous ; E3 le pilotage et la file de travail, hors roadmap_model.py).
_E2 = "décision E2 du 2026-10-26 : document, version ou verrou nommé dans le code d'un outil, jamais exécuté par la fin ; "
_E3 = "décision E3 du 2026-10-26 : pilotage et file de travail ; "
_DOCUMENTS = {   # cible : (raison, sources)
    ".python-version": (_E2 + "version de Python lue par la CI locale et le registre des composants",
                        ("tools/ci_local.sh", "tools/composants.py")),
    "CHANGELOG.md": (_E2 + "journal gelé, nommé par le sélecteur de suites", ("tools/select_suites.py",)),
    "README.md": (_E2 + "documentation nommée par le sélecteur de suites et le lanceur d'évaluations",
                  ("tools/evals_auto.sh", "tools/select_suites.py")),
    "docs/pmzilla/application.md": (_E2 + "documentation nommée dans des messages d'erreur de la base",
                                    ("tools/db.py", "tools/flow_store.py", "tools/flow_views.py", "tools/hybrid_search.py")),
    "docs/pmzilla/bibliotheque-lacunes.md": (_E2 + "documentation nommée par le contrôle des identifiants", ("tools/identifiants_personnels.py",)),
    "docs/pmzilla/composants.yaml": (_E2 + "registre des composants, lu par la CI locale et les composants",
                                     ("tools/ci_local.sh", "tools/composants.py", "tools/mutation_masking.py")),
    "docs/pmzilla/installation.md": (_E2 + "documentation d'installation nommée dans des messages et des outils d'installation",
                                     ("tests/run_all.sh", "tools/composants.py", "tools/evals_auto.sh",
                                      "tools/install_lab.py", "tools/install_lab_database.py", "tools/pmzilla_lab_library.py",
                                      "tools/watch.sh")),   # la source tools/finish_worktree.sh (ligne d'aide de l'enveloppe) est retirée avec le script (B9)
    "docs/pmzilla/manuel.md": (_E2 + "manuel nommé par le sélecteur de suites", ("tools/select_suites.py",)),
    "docs/pmzilla/version-anglaise.md": (_E2 + "documentation nommée par le contrôle des identifiants", ("tools/identifiants_personnels.py",)),
    "mothra/package-lock.json": (_E2 + "verrou npm de Mothra, change à chaque dépendance ajoutée ; verrou lu (jamais exécuté) par "
                                 "tools/finish_train.sh (la liste des chemins d'interface n'est plus dans la fin unitaire retirée : R-20261029-33), qui installe les paquets de "
                                 "Mothra dans le worktree d'intégration ; son contrôleur tools/npm_lock_check.py reste protégé (décision de l'auteur du 2026-10-27)",
                                 ("tools/composants.py", "tools/finish_train.sh", "tools/select_suites.py",
                                  "tools/worktree.sh")),
    "contrats/vues.json": (_E2 + "contrat commun de Mothra, nommé par le sélecteur de suites comme motif de sélection, jamais ouvert",
                           ("tools/select_suites.py",)),
    "contrats/cas-parite.json": (_E2 + "cas de parité de Mothra, nommés par le sélecteur de suites comme motif de sélection, jamais ouverts",
                                 ("tools/select_suites.py",)),
    "contrats/cas-masquage.json": (_E2 + "cas partagés du masquage (R-144), nommés par le sélecteur de suites comme motif de sélection, jamais ouvert par le sélecteur ni par la fin",
                                   ("tools/select_suites.py",)),
    "tools/pilot.py": (_E3 + "seule référence : un message du crochet pre-commit (« uv run tools/pilot.py freeze --wait 60 »), jamais lancé par la fin",
                       ("tools/hooks/pre-commit",)),
    "tools/roadmap.py": (_E3 + "file de travail nommée par l'outil de tickets et le résumé du matin, jamais lancée par la fin",
                         ("tools/gh_issue.py", "tools/morning_summary.py")),
    "tools/roadmap_settings.yaml": (_E3 + "réglages de la file de travail, lus par le modèle de file, jamais lus par la fin",
                                    ("tools/gh_issue.py", "tools/roadmap_model.py")),
}
EXEMPTIONS_REFERENCE: dict[tuple[str, str], str] = {(source, cible): raison for cible, (raison, sources) in _DOCUMENTS.items()
                                                    for source in sources}

# Motifs de la liste que l'arbre de cette branche ne peut pas encore satisfaire : leurs fichiers arrivent par une autre branche du même
# change (feat/scan-diff-noms-secrets). Cette entrée disparaît quand la branche fusionne ; avec un fichier suivi qui la satisfait, le test
# échoue (entrée périmée) ; sans fichier ET sans entrée ici, il échoue aussi.
EN_ATTENTE: dict[str, str] = {
    # Vide depuis le 2026-10-26 : tools/range_scan.py et tests/range_scan/ sont arrivés avec feat/scan-diff-noms-secrets, sur laquelle
    # cette branche a été rejouée.
}

# Motifs permanents sans fichier suivi, par conception : ils protègent un fichier qui peut apparaître plus tard.
PERMANENTS: dict[str, str] = {
    ".gitattributes": "graine déclarée de la conception D16 : le fichier n'existe pas dans l'arbre ; le motif protège un futur .gitattributes",
}

# Écarts propres à l'arbre public de l'édition : le manifeste `edition/manifest.yaml` exclut ces fichiers, que la liste protégée ou les exemptions
# nomment encore. Ils ne sont tolérés que si `edition/manifest.yaml` est absent à la racine de l'arbre testé (l'arbre public ne le publie pas) ;
# dans le dépôt privé, ils restent des écarts comme les autres.
# Remplace : rien. Retrait : tombe quand le chemin est publié ou quand la référence est retirée de la liste ou des exemptions.
# Source : le manifeste `edition/manifest.yaml`. Détection d'un écart : TestGardeEcartEdition, dans le dépôt privé, vérifie que le manifeste exclut
# chaque fichier couvert par ces motifs et chaque cible.
MOTIFS_ABSENTS_EDITION: dict[str, str] = {
    "*/CLAUDE.md": "édition publique : mothra/CLAUDE.md est exclu par le manifeste",
    "tools/story_quality_grid.json": "édition publique : la grille d'audit des stories est exclue par le manifeste",
    "config/gere/": "édition publique : les fichiers gérés du bac à sable sont exclus par le manifeste",
}
CIBLES_ABSENTES_EDITION = ("docs/pmzilla/application.md", "docs/pmzilla/bibliotheque-lacunes.md", "docs/pmzilla/version-anglaise.md")


def arbre_public(racine: Path) -> bool:
    """Vrai pour l'arbre public généré : le manifeste de l'édition n'y est pas publié."""
    return not (racine / "edition" / "manifest.yaml").is_file()


# Graines déclarées de la conception D16 (écrites dans la liste avec leur raison) : le test les exige dans la liste.
GRAINES = finish_checks.GRAINES_FERMETURE


# Racines de la fermeture de ce test : celles du module, plus le script du train (change finish-train-v1, tâche 2.13, conception D20 : « les scripts de
# train à venir s'ajoutent comme racines »). tools/finish_train.sh existe
# et la liste (tools/finish_protected.txt) le nomme : sans l'un ou l'autre, ce test est rouge. Commentaire corrigé le 2026-10-28 (désherbage D90) :
# il remplace l'ancienne phrase « Tant que tools/finish_train.sh n'est pas écrit (3.1) et listé (3.2), ce test est rouge. » ; il se retire avec la racine, si le train cesse d'être une racine de fermeture.
RACINES = tuple(finish_checks.RACINES_FERMETURE) + ("tools/finish_train.sh",)


def ecarts(suivis, lecteur, motifs, exemptions=None, en_attente=None, permanents=None, racines=RACINES,
           graines=finish_checks.GRAINES_FERMETURE):
    """Les écarts, un message par écart (liste vide : tout concorde)."""
    exemptions = EXEMPTIONS_REFERENCE if exemptions is None else exemptions
    en_attente = EN_ATTENTE if en_attente is None else en_attente
    permanents = PERMANENTS if permanents is None else permanents
    resultat = []
    for racine in finish_checks.racines_manquantes(suivis, racines):
        resultat.append(f"racine de la fermeture absente de l'arbre : {racine}")
    fermeture, aretes = finish_checks.parcours(lecteur, suivis, racines, graines, exemptions)
    for chemin in sorted(fermeture):
        if not finish_checks.couvert(chemin, motifs):
            sources = sorted(s for (s, c) in aretes if c == chemin)
            depuis = f", depuis {', '.join(sources)}" if sources else ""
            resultat.append(f"fichier de la fermeture non couvert par {LISTE} : {chemin} ({fermeture[chemin]}{depuis})")
    for motif in motifs:
        if not any(finish_checks.couvert(c, [motif]) for c in suivis) and motif not in en_attente and motif not in permanents:
            resultat.append(f"motif de {LISTE} sans fichier suivi : {motif}")
    for (source, cible), raison in exemptions.items():
        if not raison.strip():
            resultat.append(f"exemption sans raison : {source} → {cible}")
        elif (source, cible) not in aretes:
            resultat.append(f"exemption périmée (l'arête n'existe plus) : {source} → {cible}")
    for motif, raison in en_attente.items():
        if not raison.strip():
            resultat.append(f"motif en attente sans raison : {motif}")
        elif motif not in motifs:
            resultat.append(f"motif en attente absent de la liste : {motif}")
        elif any(finish_checks.couvert(c, [motif]) for c in suivis):
            resultat.append(f"motif en attente périmé (un fichier suivi le satisfait) : {motif}")
    for motif, raison in permanents.items():
        if not raison.strip():
            resultat.append(f"motif permanent sans raison : {motif}")
        elif motif not in motifs:
            resultat.append(f"motif permanent absent de la liste : {motif}")
        elif any(finish_checks.couvert(c, [motif]) for c in suivis):
            resultat.append(f"motif permanent devenu inutile (un fichier suivi le satisfait) : {motif}")
    return resultat


def ecarts_arbre_reel(suivis, motifs):
    """Les écarts de l'arbre testé ; dans l'arbre public seulement (manifeste absent), les motifs et les cibles d'exemption que l'édition exclut sont tolérés."""
    if not arbre_public(RACINE):
        return ecarts(suivis, lecteur_disque(RACINE), motifs)
    exemptions = {cle: raison for cle, raison in EXEMPTIONS_REFERENCE.items()
                  if not (cle[1] in CIBLES_ABSENTES_EDITION and cle[1] not in suivis)}
    return ecarts(suivis, lecteur_disque(RACINE), motifs, exemptions=exemptions, permanents={**PERMANENTS, **MOTIFS_ABSENTS_EDITION})


def suivis_git(racine: Path) -> list[str]:
    import subprocess
    sortie = subprocess.run(["git", "-C", str(racine), "ls-files"], capture_output=True, text=True, check=True).stdout
    return sortie.splitlines()


def lecteur_disque(racine: Path):
    def lire(chemin):
        fichier = racine / chemin
        return fichier.read_text(encoding="utf-8", errors="ignore") if fichier.is_file() else None
    return lire


class TestArbreReel(unittest.TestCase):
    def test_la_liste_couvre_la_fermeture(self):
        suivis = suivis_git(RACINE)
        motifs = finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        fermeture = finish_checks.fermeture(lecteur_disque(RACINE), suivis, RACINES, exemptions=EXEMPTIONS_REFERENCE)
        problemes = ecarts_arbre_reel(suivis, motifs)
        self.assertEqual(problemes, [], f"taille de la fermeture : {len(fermeture)} fichier(s)\n" + "\n".join(problemes))

    def test_le_verrou_npm_de_mothra_est_exempte_et_hors_de_la_liste_protegee(self):
        # décision de l'auteur du 2026-10-27 : une branche qui ne change que le verrou doit pouvoir être admise au train ; le verrou n'est donc pas
        # protégé, il est exempté (E2) avec tools/finish_train.sh parmi ses sources, et son contrôleur reste protégé
        verrou = "mothra/package-lock.json"
        motifs = finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        self.assertFalse(finish_checks.couvert(verrou, motifs), "le verrou npm ne doit pas être dans la liste protégée")
        self.assertTrue(finish_checks.couvert("tools/npm_lock_check.py", motifs), "le contrôleur du verrou reste protégé")
        self.assertIn(("tools/finish_train.sh", verrou), EXEMPTIONS_REFERENCE)
        suivis = suivis_git(RACINE)
        fermeture, aretes = finish_checks.parcours(lecteur_disque(RACINE), suivis, RACINES, finish_checks.GRAINES_FERMETURE, EXEMPTIONS_REFERENCE)
        self.assertIn(("tools/finish_train.sh", verrou), aretes, "tools/finish_train.sh lit le verrou : l'arête existe")

    def test_le_script_du_train_et_sa_suite_sont_couverts_par_la_liste(self):
        # tâche 2.13 : le script du train est une racine ; la liste le couvre (3.2), et la graine « tests/finish_* » couvre sa suite
        motifs = finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        self.assertTrue(finish_checks.couvert("tools/finish_train.sh", motifs), "tools/finish_train.sh absent de la liste")
        for chemin in ("tests/finish_train/aide_train.py", "tests/finish_train/test_lancement.py", "tests/finish_train_fin/test_codes_messages.py", "tests/finish_train_npm/test_npm_mothra.py", "tests/finish_train_base/test_base.py", "tests/finish_train_reprise/test_reprise.py"):
            self.assertTrue(finish_checks.couvert(chemin, motifs), chemin)   # la suite tient en cinq dossiers : finish_train, _fin, _npm, _base et _reprise (R-20261029-38)
        suivis = suivis_git(RACINE)
        fermeture = finish_checks.fermeture(lecteur_disque(RACINE), suivis, RACINES, exemptions=EXEMPTIONS_REFERENCE)
        self.assertIn("tools/finish_train.sh", fermeture, "le script du train est une racine de la fermeture")
        self.assertEqual([c for c in fermeture if c.startswith(("tests/finish_train/", "tests/finish_train_fin/", "tests/finish_train_npm/", "tests/finish_train_base/", "tests/finish_train_reprise/")) and not finish_checks.couvert(c, motifs)], [])

    def test_la_fermeture_est_lue_et_non_vide(self):
        # sans cette lecture, le test ci-dessus serait vide
        suivis = suivis_git(RACINE)
        fermeture = finish_checks.fermeture(lecteur_disque(RACINE), suivis, RACINES, exemptions=EXEMPTIONS_REFERENCE)
        self.assertIn("tools/finish_train.sh", fermeture)
        self.assertIn("tests/run_all.sh", fermeture)
        self.assertIn("tools/hooks/pre-commit", fermeture)
        self.assertIn("tools/finish_lock.sh", fermeture)               # sourcé par le script de fin
        self.assertIn("tests/postures/fichiers-evalues.txt", fermeture)   # donnée nommée dans le code du script de fin
        self.assertGreater(len(fermeture), 20)

    def test_les_graines_sont_des_racines_de_la_recursion(self):
        # gh_issue.py est une graine : ce qu'il importe (roadmap_model.py) entre dans la fermeture, et reste protégé
        suivis = suivis_git(RACINE)
        fermeture = finish_checks.fermeture(lecteur_disque(RACINE), suivis, RACINES, exemptions=EXEMPTIONS_REFERENCE)
        self.assertIn("tools/gh_issue.py", fermeture)
        self.assertIn("tools/roadmap_model.py", fermeture)
        motifs = finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        self.assertTrue(finish_checks.couvert("tools/roadmap_model.py", motifs))

    def test_les_graines_declarees_sont_dans_la_liste(self):
        motifs = finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        manquantes = [g for g in GRAINES if g not in motifs]
        self.assertEqual(manquantes, [], "graines déclarées (conception D16) absentes de la liste")

    def test_tout_fichier_suivi_nomme_claude_md_est_couvert(self):
        motifs = finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        suivis = [s for s in suivis_git(RACINE) if s.rsplit("/", 1)[-1] == "CLAUDE.md"]
        self.assertTrue(arbre_public(RACINE) or "mothra/CLAUDE.md" in suivis)   # dans l'arbre public, mothra/CLAUDE.md est exclu par le manifeste
        self.assertEqual([s for s in suivis if not finish_checks.couvert(s, motifs)], [])

    def test_chaque_motif_a_sa_raison(self):
        # une ligne de motif suit une ligne de commentaire (même groupe, sans ligne vide) ou porte un commentaire en fin de ligne
        sans = []
        commentaire = False
        for ligne in (RACINE / LISTE).read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                commentaire = False
            elif ligne.lstrip().startswith("#"):
                commentaire = True
            elif commentaire or "#" in ligne:
                continue
            else:
                sans.append(ligne)
        self.assertEqual(sans, [], "motifs sans commentaire de raison")

    def test_les_exemptions_les_motifs_permanents_et_en_attente_portent_une_raison(self):
        for cle, raison in EXEMPTIONS_REFERENCE.items():
            self.assertTrue(raison.strip(), cle)
        for table in (PERMANENTS, EN_ATTENTE):
            for cle, raison in table.items():
                self.assertTrue(raison.strip(), cle)

    def test_la_liste_lue_est_celle_du_fichier_suivi(self):
        self.assertIn(LISTE, suivis_git(RACINE))

    def test_les_racines_existent_dans_l_arbre_reel(self):
        self.assertEqual(finish_checks.racines_manquantes(suivis_git(RACINE), RACINES), [])


@unittest.skipIf(arbre_public(RACINE), "édition publique : manifeste non livré")
class TestGardeEcartEdition(unittest.TestCase):
    """Garde d'écart des tables MOTIFS_ABSENTS_EDITION et CIBLES_ABSENTES_EDITION : le manifeste est la source, il doit exclure ce qu'elles tolèrent."""

    @staticmethod
    def exclu(chemin: str) -> bool:
        import yaml
        sys.path.insert(0, str(RACINE / "tools"))
        import build_edition
        regles = yaml.safe_load((RACINE / "edition" / "manifest.yaml").read_text(encoding="utf-8"))["rules"]
        action = next((r["action"] for r in regles if build_edition.make_matcher(r["path"])(chemin)), None)
        return action == "exclude"

    def test_chaque_fichier_couvert_par_un_motif_tolere_est_exclu_par_le_manifeste(self):
        suivis = suivis_git(RACINE)
        for motif in MOTIFS_ABSENTS_EDITION:
            couverts = [s for s in suivis if finish_checks.couvert(s, [motif])]
            self.assertTrue(couverts, f"{motif} ne couvre plus aucun fichier suivi : retirer l'entrée de MOTIFS_ABSENTS_EDITION")
            for chemin in couverts:
                with self.subTest(motif=motif, chemin=chemin):
                    self.assertTrue(self.exclu(chemin), f"{chemin} (motif {motif}) n'est plus exclu par le manifeste : retirer l'entrée")

    def test_chaque_cible_tolerée_est_exclue_par_le_manifeste(self):
        for cible in CIBLES_ABSENTES_EDITION:
            with self.subTest(cible=cible):
                self.assertTrue(self.exclu(cible), f"{cible} n'est plus exclue par le manifeste : retirer l'entrée de CIBLES_ABSENTES_EDITION")


class TestArbreFactice(unittest.TestCase):
    """Un arbre minimal : un script de fin qui source un module, lance un outil Python, importe un module et nomme une donnée."""

    FINISH = ('#!/bin/bash\n# commentaire : tools/ignore_moi.sh et tests/ignore.txt ne comptent pas\n'
              '. "$SCRIPT_DIR/finish_lock.sh"\nbash "$SCRIPT_DIR/morning_state.sh" check\n'
              'LISTE="$SCRIPT_DIR/../tests/postures/fichiers-evalues.txt"\npython3 -I "$SCRIPT_DIR/outil.py"\n')

    def setUp(self):
        self.fichiers = {
            "tools/finish_train.sh": self.FINISH,
            "tests/run_all.sh": "#!/bin/bash\npython3 tools/select_suites.py\n",
            "tools/hooks/pre-commit": "#!/bin/sh\npython3 -I tools/secret_scan.py\n",
            "tools/hooks/commit-msg": "#!/bin/sh\nexit 0\n",
            "tools/morning_state.sh": "#!/bin/bash\nexit 0\n",
            "tools/install_hooks.sh": "#!/bin/bash\nexit 0\n",
            "tools/finish_lock.sh": "# module\n",
            "tools/outil.py": "import json\nimport aide\nfrom autre import x\n",
            "tools/aide.py": "pass\n",
            "tools/autre.py": "x = 1\n",
            "tools/select_suites.py": "pass\n",
            "tools/secret_scan.py": "pass\n",
            "tools/ignore_moi.sh": "pass\n",
            "tests/postures/fichiers-evalues.txt": "CLAUDE.md\n",
            "tests/ignore.txt": "x\n",
        }
        self.motifs = ["tools/finish_train.sh", "tests/run_all.sh", "tools/hooks/", "tools/morning_state.sh",
                       "tools/install_hooks.sh", "tools/finish_lock.sh", "tools/outil.py", "tools/aide.py", "tools/autre.py",
                       "tools/select_suites.py", "tools/secret_scan.py", "tests/postures/fichiers-evalues.txt"]

    def suivis(self):
        return sorted(self.fichiers)

    def ecarts(self, **options):
        return ecarts(self.suivis(), self.fichiers.get, self.motifs, exemptions=options.get("exemptions", {}),
                      en_attente=options.get("en_attente", {}), permanents=options.get("permanents", {}),
                      racines=finish_checks.RACINES_FERMETURE)   # l'arbre factice n'a pas le script du train

    def fermeture(self, **options):
        return finish_checks.fermeture(self.fichiers.get, self.suivis(), finish_checks.RACINES_FERMETURE, **options)

    def test_arbre_concordant(self):
        self.assertEqual(self.ecarts(), [])

    def test_la_fermeture_suit_les_sources_les_lancements_et_les_imports(self):
        f = self.fermeture()
        for chemin in ("tools/finish_lock.sh", "tools/morning_state.sh", "tools/outil.py", "tools/aide.py", "tools/autre.py",
                       "tools/select_suites.py", "tools/secret_scan.py", "tests/postures/fichiers-evalues.txt"):
            self.assertIn(chemin, f)
        self.assertNotIn("tools/ignore_moi.sh", f)   # nommé en commentaire seulement
        self.assertNotIn("tests/ignore.txt", f)

    def test_les_racines_sont_dans_la_fermeture_et_les_crochets_un_par_un(self):
        f = self.fermeture()
        for chemin in ("tools/finish_train.sh", "tests/run_all.sh", "tools/morning_state.sh",
                       "tools/install_hooks.sh", "tools/hooks/pre-commit", "tools/hooks/commit-msg"):
            self.assertIn(chemin, f)

    def test_nouveau_module_source_non_couvert(self):
        self.fichiers["tools/nouveau.sh"] = "# nouveau\n"
        self.fichiers["tools/finish_train.sh"] += '. "$SCRIPT_DIR/nouveau.sh"\n'
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 1)
        self.assertIn("tools/nouveau.sh", problemes[0])
        self.assertIn("depuis tools/finish_train.sh", problemes[0])

    def test_fichier_de_donnees_nomme_dans_le_code_non_couvert(self):
        self.fichiers["tests/suites_x.txt"] = "x\n"
        self.fichiers["tests/run_all.sh"] += 'LISTE=tests/suites_x.txt\n'
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 1)
        self.assertIn("tests/suites_x.txt", problemes[0])

    def test_une_donnee_lue_n_est_pas_suivie_dans_ses_propres_references(self):
        # la donnée nomme un autre fichier suivi : il n'entre pas dans la fermeture (la fermeture ne récurse que par source, lancement, import)
        self.fichiers["tests/postures/fichiers-evalues.txt"] = "CLAUDE.md\ntests/ignore.txt\ntools/ignore_moi.sh\n"
        self.assertEqual(self.ecarts(), [])

    def test_un_module_source_est_suivi_dans_ses_propres_sources(self):
        self.fichiers["tools/finish_lock.sh"] = '. "$SCRIPT_DIR/profond.sh"\n'
        self.fichiers["tools/profond.sh"] = "# profond\n"
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 1)
        self.assertIn("tools/profond.sh", problemes[0])

    def test_un_import_est_suivi_recursivement(self):
        self.fichiers["tools/aide.py"] = "import loin\n"
        self.fichiers["tools/loin.py"] = "pass\n"
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 1)
        self.assertIn("tools/loin.py", problemes[0])

    def test_fichier_nomme_en_commentaire_seulement_est_ignore(self):
        self.fichiers["tools/finish_train.sh"] += "# voir tests/ignore.txt et tools/ignore_moi.sh\n"
        self.assertEqual(self.ecarts(), [])

    # --- règle de lecture : un jeton /<nom>.sh|py dont le nom est un fichier suivi de tools/ est une référence (fail-closed)
    def test_une_valeur_par_defaut_de_variable_est_un_lancement(self):
        # « ${VAR:-python3 -I '$SCRIPT_DIR/valide.py'} » : le mot de lancement suit « - », la règle du lanceur ne le voit pas
        self.fichiers["tools/finish_train.sh"] += 'VALIDATION="${FINISH_BRANCH_VALIDATE:-python3 -I \'$SCRIPT_DIR/valide.py\'}"\n'
        self.fichiers["tools/valide.py"] = "import loin\n"
        self.fichiers["tools/loin.py"] = "pass\n"
        f = self.fermeture()
        self.assertEqual(f.get("tools/valide.py"), "suivi")
        self.assertEqual(f.get("tools/loin.py"), "suivi")   # et ses imports sont suivis
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 2)
        self.assertTrue(any("tools/valide.py" in p for p in problemes))

    def test_faux_positif_connu_un_nom_dans_un_message_compte_comme_reference(self):
        # connu et accepté (fail-closed) : un message d'erreur qui nomme « uv run tools/x.py » compte ; seule une exemption de référence,
        # avec sa raison, le laisse hors de la liste
        self.fichiers["tools/hooks/pre-commit"] += 'echo "relance : uv run tools/pilote.py freeze"\n'
        self.fichiers["tools/pilote.py"] = "pass\n"
        self.assertTrue(any("tools/pilote.py" in p for p in self.ecarts()))
        raison = "message d'erreur, jamais lancé par la fin"
        self.assertEqual(self.ecarts(exemptions={("tools/hooks/pre-commit", "tools/pilote.py"): raison}), [])

    def test_faux_positif_connu_un_nom_de_test_n_est_pas_un_outil(self):
        # un nom de fichier sans « / » devant, ou un nom absent de tools/, n'est jamais une référence
        self.fichiers["tools/finish_train.sh"] += 'echo "voir pilote.py et tests/autre/introuvable.py"\n'
        self.fichiers["tools/pilote.py"] = "pass\n"
        self.assertEqual(self.ecarts(), [])

    # --- plus de cas particulier pour les chemins de la base (finish-single-b3-b6 D15, tâche 4.4) : ils sont dans tools/finish_db_paths.txt, un fichier de
    # données lu (jamais exécuté) par le module ; un tableau CHEMINS_BASE dans un script de fin serait lu comme n'importe quel texte de script.
    def test_un_nom_dans_un_tableau_chemins_base_est_une_reference_comme_les_autres(self):
        self.fichiers["tools/finish_train.sh"] += 'CHEMINS_BASE=(\n  "tools/base_a.py"\n)\npython3 tools/base_a.py\n'
        self.fichiers["tools/base_a.py"] = "pass\n"
        self.assertEqual(self.fermeture().get("tools/base_a.py"), "suivi")

    def test_le_module_ne_retire_plus_le_bloc_chemins_base(self):
        self.assertFalse(hasattr(finish_checks, "retirer_bloc_chemins_base"))

    # --- les graines .py et .sh de tools/ sont des racines de la récursion
    def test_les_imports_d_une_graine_sont_suivis(self):
        self.fichiers["tools/gh_issue.py"] = "import roadmap_model\n"
        self.fichiers["tools/roadmap_model.py"] = "import plus_loin\n"
        self.fichiers["tools/plus_loin.py"] = "pass\n"
        f = self.fermeture()
        self.assertEqual(f.get("tools/gh_issue.py"), "graine")
        self.assertEqual(f.get("tools/roadmap_model.py"), "suivi")
        self.assertEqual(f.get("tools/plus_loin.py"), "suivi")
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 3)   # gh_issue.py, roadmap_model.py et plus_loin.py : aucun motif dans cet arbre
        self.assertTrue(any("tools/roadmap_model.py" in p and "depuis tools/gh_issue.py" in p for p in problemes))

    def test_une_graine_hors_de_tools_ou_sans_extension_de_script_n_est_pas_une_racine(self):
        self.fichiers["tools/secret_scan_exemples.txt"] = "import loin\n"
        self.fichiers["tools/loin.py"] = "pass\n"
        self.assertNotIn("tools/loin.py", self.fermeture())

    def test_motif_perime(self):
        self.motifs.append("tools/disparu.sh")
        problemes = self.ecarts()
        self.assertEqual(len(problemes), 1)
        self.assertIn("motif de tools/finish_protected.txt sans fichier suivi : tools/disparu.sh", problemes[0])

    def test_motif_en_attente_est_toleré_avec_sa_raison(self):
        self.motifs.append("tools/ailleurs.py")
        self.assertEqual(self.ecarts(en_attente={"tools/ailleurs.py": "arrive par une autre branche"}), [])
        problemes = self.ecarts(en_attente={"tools/ailleurs.py": " "})
        self.assertEqual(problemes, ["motif en attente sans raison : tools/ailleurs.py"])

    def test_motif_en_attente_perime_quand_un_fichier_le_satisfait(self):
        self.fichiers["tools/ailleurs.py"] = "pass\n"
        self.motifs.append("tools/ailleurs.py")
        problemes = self.ecarts(en_attente={"tools/ailleurs.py": "arrive par une autre branche"})
        self.assertEqual(problemes, ["motif en attente périmé (un fichier suivi le satisfait) : tools/ailleurs.py"])

    def test_motif_en_attente_absent_de_la_liste_est_signale(self):
        problemes = self.ecarts(en_attente={"tools/ailleurs.py": "arrive par une autre branche"})
        self.assertEqual(problemes, ["motif en attente absent de la liste : tools/ailleurs.py"])

    def test_motif_permanent_est_toleré_avec_sa_raison_sans_fichier(self):
        self.motifs.append(".gitattributes")
        self.assertEqual(self.ecarts(permanents={".gitattributes": "futur fichier protégé"}), [])
        self.assertEqual(self.ecarts(permanents={".gitattributes": ""}), ["motif permanent sans raison : .gitattributes"])
        self.fichiers[".gitattributes"] = "x\n"
        problemes = self.ecarts(permanents={".gitattributes": "futur fichier protégé"})
        self.assertEqual(problemes, ["motif permanent devenu inutile (un fichier suivi le satisfait) : .gitattributes"])

    def test_racine_absente(self):
        del self.fichiers["tools/morning_state.sh"]
        self.motifs.remove("tools/morning_state.sh")
        problemes = self.ecarts()
        self.assertIn("racine de la fermeture absente de l'arbre : tools/morning_state.sh", problemes)

    def test_dossier_de_crochets_vide_est_une_racine_absente(self):
        for chemin in ("tools/hooks/pre-commit", "tools/hooks/commit-msg"):
            del self.fichiers[chemin]
        self.motifs.remove("tools/hooks/")
        self.fichiers["tools/finish_train.sh"] = self.FINISH
        problemes = self.ecarts()
        self.assertIn("racine de la fermeture absente de l'arbre : tools/hooks/", problemes)

    # --- exemptions de référence « source -> cible, avec sa raison »
    def test_exemption_de_reference_laisse_la_cible_hors_de_la_liste_et_coupe_la_recursion(self):
        self.fichiers["tools/aide.py"] = "import loin\n"
        self.fichiers["tools/loin.py"] = "pass\n"
        self.motifs.remove("tools/aide.py")
        self.assertEqual(len(self.ecarts()), 2)   # aide.py et loin.py
        exemption = {("tools/outil.py", "tools/aide.py"): "module de présentation, sans effet sur la fin"}
        self.assertEqual(self.ecarts(exemptions=exemption), [])   # l'arête coupée : ni aide.py ni loin.py
        self.assertNotIn("tools/loin.py", self.fermeture(exemptions=exemption))

    def test_la_cible_d_une_exemption_entre_par_une_autre_arete(self):
        self.fichiers["tools/finish_lock.sh"] = 'python3 tools/aide.py\n'
        self.motifs.remove("tools/aide.py")
        exemption = {("tools/outil.py", "tools/aide.py"): "raison"}
        problemes = self.ecarts(exemptions=exemption)
        self.assertEqual(len(problemes), 1)
        self.assertIn("depuis tools/finish_lock.sh", problemes[0])

    def test_exemption_sans_raison_est_refusee(self):
        self.motifs.remove("tools/aide.py")
        problemes = self.ecarts(exemptions={("tools/outil.py", "tools/aide.py"): ""})
        self.assertEqual(problemes, ["exemption sans raison : tools/outil.py → tools/aide.py"])

    def test_exemption_perimee_quand_l_arete_n_existe_plus(self):
        problemes = self.ecarts(exemptions={("tools/outil.py", "tools/ignore_moi.sh"): "raison"})
        self.assertEqual(problemes, ["exemption périmée (l'arête n'existe plus) : tools/outil.py → tools/ignore_moi.sh"])
        # la source n'est plus atteinte : l'arête n'existe plus non plus
        problemes = self.ecarts(exemptions={("tools/disparu.py", "tools/aide.py"): "raison"})
        self.assertEqual(problemes, ["exemption périmée (l'arête n'existe plus) : tools/disparu.py → tools/aide.py"])

    def test_motifs_dossier_et_joker(self):
        self.assertTrue(finish_checks.couvert("tools/hooks/pre-commit", ["tools/hooks/"]))
        self.assertTrue(finish_checks.couvert("tools/lab_paths.py", ["tools/lab_paths.*"]))
        self.assertTrue(finish_checks.couvert("tools/secret_scan_exemples.txt", ["tools/secret_scan*"]))
        self.assertTrue(finish_checks.couvert("mothra/CLAUDE.md", ["*/CLAUDE.md"]))
        self.assertTrue(finish_checks.couvert("CLAUDE.md", ["CLAUDE.md"]))
        self.assertFalse(finish_checks.couvert("tools/hooksx", ["tools/hooks/"]))
        self.assertFalse(finish_checks.couvert("tools/autre.py", ["tools/aide.py"]))

    def test_motifs_proteges_ignorent_commentaires_et_lignes_vides(self):
        texte = "# titre\n\n  tools/a.py  \n# autre\ntools/b/ # raison en fin de ligne\n"
        self.assertEqual(finish_checks.motifs_proteges(texte), ["tools/a.py", "tools/b/"])


class TestClasses(unittest.TestCase):
    """finish-single-b3-b6, B4 (design D9 et D10) : chaque motif de la liste porte une classe, `juge` ou `sensible`, dans une étiquette de commentaire
    (`#[juge]` ou `#[sensible]`, suivie d'un texte libre) que le lecteur d'aujourd'hui ignore. La fermeture de la liste
    est couverte par TestArbreReel (juge ou sensible) ; aucune règle de fermeture propre aux juges (R-20261030-34)."""

    ETIQUETTE = re.compile(r"\[(juge|sensible)\]")

    def lignes_de_motif(self):
        """(numéro, ligne, commentaire après le premier « # ») pour chaque ligne qui porte un motif."""
        resultat = []
        for n, ligne in enumerate((RACINE / LISTE).read_text(encoding="utf-8").splitlines(), start=1):
            corps = ligne.strip()
            if not corps or corps.startswith("#"):
                continue
            _, _, commentaire = corps.partition("#")
            resultat.append((n, ligne, commentaire))
        return resultat

    def test_chaque_ligne_de_motif_porte_exactement_une_etiquette_connue(self):
        fautes = []
        for n, ligne, commentaire in self.lignes_de_motif():
            trouvees = self.ETIQUETTE.findall(commentaire)
            if len(trouvees) != 1 or not self.ETIQUETTE.match(commentaire):
                fautes.append(f"ligne {n} : {ligne.strip()}")
        self.assertEqual(fautes, [], "lignes sans exactement une étiquette #[juge] ou #[sensible] au début de leur commentaire :\n" + "\n".join(fautes))

    def test_le_lecteur_d_aujourd_hui_lit_les_memes_motifs_avec_ou_sans_etiquette(self):
        texte = (RACINE / LISTE).read_text(encoding="utf-8")
        sans = "\n".join(self.ETIQUETTE.sub("", ligne) for ligne in texte.splitlines())
        self.assertEqual(finish_checks.motifs_proteges(texte), finish_checks.motifs_proteges(sans))
        self.assertGreater(len(finish_checks.motifs_proteges(texte)), 100)

    def test_chaque_motif_garde_une_raison_hors_etiquette(self):
        # l'étiquette seule ne vaut pas raison : la ligne suit un commentaire de son groupe, ou porte du texte après son étiquette
        sans = []
        commentaire = False
        for ligne in (RACINE / LISTE).read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                commentaire = False
            elif ligne.lstrip().startswith("#"):
                commentaire = True
            elif commentaire:
                continue
            else:
                reste = self.ETIQUETTE.sub("", ligne.partition("#")[2]).strip()
                if not reste:
                    sans.append(ligne)
        self.assertEqual(sans, [], "motifs sans raison (ni commentaire de groupe, ni texte après l'étiquette)")

    def test_classes_proteges_lit_l_etiquette_et_compte_juge_sans_etiquette(self):
        texte = "# titre\ntools/a.py  #[juge] raison\ntools/b/ #[sensible]\ntools/c.py\ntools/d.py # raison libre\ntools/e.py #[inconnue] x\n"
        self.assertEqual(finish_checks.classes_proteges(texte), {"tools/a.py": "juge", "tools/b/": "sensible", "tools/c.py": "juge",
                                                                  "tools/d.py": "juge", "tools/e.py": "juge"})

    def test_classes_proteges_une_ligne_a_deux_etiquettes_compte_juge(self):
        texte = "tools/a.py  #[sensible] #[juge]\ntools/b.py  #[sensible] voir #[sensible]\ntools/c.py #[sensible] texte\n"
        self.assertEqual(finish_checks.classes_proteges(texte), {"tools/a.py": "juge", "tools/b.py": "juge", "tools/c.py": "sensible"})

    def test_la_liste_reelle_a_ses_deux_classes(self):
        classes = finish_checks.classes_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        self.assertEqual(set(classes.values()), {"juge", "sensible"})
        self.assertEqual(list(classes), finish_checks.motifs_proteges((RACINE / LISTE).read_text(encoding="utf-8")))

    def test_les_modules_de_ce_change_sont_juges(self):
        classes = finish_checks.classes_proteges((RACINE / LISTE).read_text(encoding="utf-8"))
        for motif in ("tools/finish_stability.sh", "tools/finish_admission.sh", "tools/finish_checks.py", "tools/finish_protected.txt",
                      "tools/finish_train.sh", "tools/train_ready.py", "tools/train_auto.py"):
            with self.subTest(motif=motif):
                self.assertEqual(classes.get(motif), "juge")



if __name__ == "__main__":
    unittest.main()
