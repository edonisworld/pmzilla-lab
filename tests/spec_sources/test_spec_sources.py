"""Contrôle des lignes « Source: » des specs principales (idée #390, R-136).

    python3 -m unittest discover -s tests/spec_sources -v

Chaque exigence d'une spec principale (openspec/specs/*/spec.md, jamais un change ni une archive) peut porter une ligne
« Source: » qui renvoie à un fichier, à une classe ou à une méthode de test. Ce test lit ces lignes et vérifie, sans importer aucun
test (texte et ast seulement) :

- chaque chemin cité existe dans le dépôt (un motif comme `.claude/commands/*.md` doit désigner au moins un fichier) ;
- chaque nom cité entre parenthèses après un fichier Python (`Classe`, `Classe.methode`, `test_x`, `test_x*`) existe dans ce fichier ;
- les lignes « untested until implemented » et « to be covered by » sont listées à part, sans échec ;
- les exigences sans aucune ligne Source sont comptées dans le rapport.

Une référence cassée hors de EXCEPTIONS fait échouer le test en nommant la spec et la ligne. Une exception périmée (la référence
n'est plus cassée, ou la ligne a disparu) échoue aussi : la liste ne grossit jamais en silence. Aucun appel réseau ni payant.
"""
import ast
import fnmatch
import re
import tempfile
import unittest
from pathlib import Path

RACINE_REELLE = Path(__file__).resolve().parents[2]

# Références cassées connues, déclarées avec une raison par ligne : (spec, référence) -> raison. La référence est
# « chemin » pour un chemin, « chemin::nom » pour un nom. Vide quand toutes les références sont saines.
_REFERENTIEL = "tests/export_jira_api/test_referentiel_et_etiquettes.py"
EXCEPTIONS: dict[tuple[str, str], str] = {
    ("jira-flow-compare", "tests/flow_compare/test_flow_compare.py::test_main_de_bout_en_bout"):
        "test retiré quand flow_compare a été réduit à reports ; la cible de remplacement n'est pas établie",
    ("jira-flow-import", "tests/flow_import/test_import.py"):
        "fichier supprimé avec la fin des anciens noms ; la suite flow_import n'a plus que des tests de dérivation et de reconstruction",
    ("jira-flow-labels", f"{_REFERENTIEL}::test_sans_bloc_aucune_colonne_d_etiquette_meme_si_le_ticket_en_porte"):
        "test renommé ou retiré (le fichier ne garde que AucuneEtiquetteNiVersion) ; correspondance non évidente",
    ("jira-flow-labels", f"{_REFERENTIEL}::EtiquettesProches"):
        "classe absente du fichier ; correspondance non évidente",
    ("jira-flow-store", "tests/flow_store/test_ordre_rapports.py"):
        "fichier absent de tests/flow_store ; correspondance non évidente",
    ("library-search-hybrid-ranking", "tests/hybrid_search/test_hybrid_search.py::FusionEtFraicheur.test_fusion_identique_a_library_search"):
        "test retiré ; la parité est portée aujourd'hui par tests/parity, correspondance à confirmer par l'auteur",
    ("tooling-permission-guards", "tests/settings_deny/roadmap_import.py"):
        "nom d'un ancien script cité entre parenthèses (lu comme un chemin) ; l'outil n'existe plus dans tools/",
    # Désherbage du 2026-10-28 (branche chore/desherbage-tests-settings-deny, décision globale de l'auteur) : trois références de la spec
    # tooling-permission-guards visent des tests ou des noms retirés avec leurs règles deny. La spec n'est pas modifiée par cette branche
    # (seules les deux exigences de watch_copy, D34, l'étaient) : à corriger par l'auteur avec les exigences concernées.
    ("tooling-permission-guards", "tests/settings_deny/test_settings_deny.py::test_import_de_la_bibliotheque_interdit_a_la_session"):
        "test retiré avec les règles de knowledge_import.py (D32) ; l'exigence « Library import and indexing… » cite encore le script d'import ; tombe quand l'auteur corrige l'exigence de openspec/specs/tooling-permission-guards/spec.md (D80)",
    ("tooling-permission-guards", "tests/settings_deny/test_settings_deny.py::test_regles_d_avant_le_lot_3_toujours_presentes"):
        "test retiré avec les règles des anciens noms et des sous-commandes retirées (D25, D28, D29) ; l'exigence « Pre-rename rules retained » est à retirer ou à reformuler ; tombe quand l'auteur corrige l'exigence de openspec/specs/tooling-permission-guards/spec.md (D80)",
    ("tooling-permission-guards", "tests/settings_deny/test_settings_deny_github.py::IMPORT"):
        "constante retirée avec les règles de roadmap_import.py (D33) ; l'exigence « The roadmap import tool is denied to the session » est à retirer ; tombe quand l'auteur corrige l'exigence de openspec/specs/tooling-permission-guards/spec.md (D80)",
    ("watch-shadow-scoring", "tasks.md"):
        "renvoi en prose à la décision de projet du change (tâche 4.4), sans test ; ce n'est pas un chemin du dépôt",
    ("watch-triage", "tests/watch_triage/test_watch_triage.py::test_main_accepte_ancien_et_nouveau_nom_d_option_et_de_sous_commande"):
        "test absent ; test_anciennes_options_refusees_avec_le_nom_actuel dit l'inverse (refus de l'ancien nom), pas de renommage sûr",
}

# Références cassées propres à l'arbre public de l'édition : (spec, préfixe du chemin cité). Les specs publiées citent des chemins que le
# manifeste `edition/manifest.yaml` exclut ; ces références ne sont tolérées que si `edition/manifest.yaml` est absent à la racine de l'arbre
# testé (l'arbre public ne le publie pas). Dans le dépôt privé, elles restent des références cassées comme les autres.
# Remplace : rien. Retrait : tombe quand le chemin est publié ou quand la référence est retirée de la spec.
# Source de la liste : le manifeste `edition/manifest.yaml` (chaque préfixe y est exclu). Détection d'un écart : le test
# `GardeEcartExclusEdition`, dans le dépôt privé, vérifie que le manifeste exclut chaque préfixe.
EXCLUS_EDITION: tuple[tuple[str, str], ...] = (
    ("tooling-edition", "tests/build_edition/"),
    ("library-search-domain-sorting", "tests/sort_by_domain/test_mapping_prive.py"),
    ("tooling-finish-train", "openspec/test-gaps.md"),
)


def arbre_public(racine: Path) -> bool:
    """Vrai pour l'arbre public généré : le manifeste de l'édition n'y est pas publié."""
    return not (racine / "edition" / "manifest.yaml").is_file()


def exclue_de_l_edition(spec: str, reference: str) -> bool:
    return any(spec == s and reference.startswith(prefixe) for s, prefixe in EXCLUS_EDITION)


LIGNE_SOURCE = re.compile(r"^Source:\s*(.*)$")
EN_ATTENTE = re.compile(r"^(untested until implemented|to be covered by)\b", re.IGNORECASE)
EXIGENCE = re.compile(r"^### Requirement:")
EXTENSIONS = r"(?:py|sh|md|yaml|yml|json|txt|toml)"
JETON_CHEMIN = re.compile(r"[\w.*/-]+")
NOM_PYTHON = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_*]\w*\*?)?\*?$")


def _nettoyer(jeton: str) -> str:
    return jeton.strip("`").rstrip(".,;:")


def est_chemin(jeton: str, racine: Path) -> bool:
    """Un jeton est un chemin s'il commence par un dossier de la racine ou s'il est un nom de fichier seul avec extension."""
    if "/" in jeton:
        return (racine / jeton.split("/")[0]).exists() and not jeton.startswith("/")
    return re.fullmatch(rf"[\w-]+\.{EXTENSIONS}", jeton) is not None


def references(texte: str, racine: Path) -> list[tuple[str, list[str]]]:
    """Les chemins cités par une ligne Source, chacun avec les noms de la parenthèse qui le suit.

    Un nom de fichier seul (« test_controle.py ») se lit dans le dossier du chemin précédent quand celui-ci est un dossier ou un
    fichier : les deux cas sont donnés par le dossier de ce chemin.
    """
    trouves: list[tuple[str, list[str]]] = []
    dernier_dossier = ""
    position = 0
    while position < len(texte):
        correspondance = JETON_CHEMIN.search(texte, position)
        if not correspondance:
            break
        position = correspondance.end()
        jeton = _nettoyer(correspondance.group())
        if not jeton or not est_chemin(jeton, racine):
            continue
        if "/" not in jeton and dernier_dossier and not (racine / jeton).exists():
            jeton = f"{dernier_dossier}/{jeton}"
        if "/" in jeton:
            dernier_dossier = jeton.rsplit("/", 1)[0] if re.search(rf"\.{EXTENSIONS}$", jeton) else jeton
        noms: list[str] = []
        reste = texte[position:].lstrip("` ")
        if reste.startswith("(") and jeton.endswith(".py"):
            profondeur, fin = 0, 0
            for i, caractere in enumerate(reste):
                profondeur += caractere == "("
                profondeur -= caractere == ")"
                if profondeur == 0:
                    fin = i
                    break
            for brut in re.split(r"[,;:]", reste[1:fin]):
                nom = brut.strip().strip("`")
                if NOM_PYTHON.match(nom) and not re.search(rf"\.{EXTENSIONS}$", nom) and (nom.startswith("test") or nom[0].isupper() or "." in nom):
                    noms.append(nom)
        trouves.append((jeton, noms))
    return trouves


def definitions_python(fichier: Path) -> tuple[set[str], dict[str, set[str]]]:
    """Les noms de fonctions et de classes d'un fichier Python (ast), et les méthodes de chaque classe."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    fonctions: set[str] = set()
    classes: dict[str, set[str]] = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fonctions.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            fonctions.update(c.id for c in noeud.targets if isinstance(c, ast.Name))
        elif isinstance(noeud, ast.ClassDef):
            classes[noeud.name] = {
                n.name for n in noeud.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return fonctions, classes


def nom_existe(nom: str, fonctions: set[str], classes: dict[str, set[str]]) -> bool:
    if "." in nom:
        classe, methode = nom.split(".", 1)
        return any(fnmatch.fnmatchcase(c, classe) for c in classes) and any(
            fnmatch.fnmatchcase(m, methode)
            for c, methodes in classes.items()
            if fnmatch.fnmatchcase(c, classe)
            for m in methodes
        )
    return any(fnmatch.fnmatchcase(n, nom) for n in fonctions | set(classes))


def chemin_existe(chemin: str, racine: Path) -> bool:
    if "*" in chemin:
        return any(racine.glob(chemin))
    return (racine / chemin).exists()


def inventaire(racine: Path) -> dict:
    """Lit les specs principales de `racine` : lignes Source, références cassées, lignes en attente, exigences sans Source."""
    resultat = {"lignes": 0, "en_attente": [], "cassees": [], "sans_source": [], "exigences": 0, "formes": {}}
    caches: dict[Path, tuple[set[str], dict[str, set[str]]]] = {}
    for spec in sorted((racine / "openspec" / "specs").glob("*/spec.md")):
        nom_spec = spec.parent.name
        exigence, a_source = None, False

        def cloturer():
            if exigence is not None and not a_source:
                resultat["sans_source"].append((nom_spec, exigence))

        for ligne in spec.read_text(encoding="utf-8").splitlines():
            if EXIGENCE.match(ligne):
                cloturer()
                exigence, a_source = ligne[len("### Requirement:"):].strip(), False
                resultat["exigences"] += 1
                continue
            source = LIGNE_SOURCE.match(ligne)
            if not source:
                continue
            a_source = True
            resultat["lignes"] += 1
            texte = source.group(1)
            if EN_ATTENTE.match(texte):
                resultat["en_attente"].append((nom_spec, texte))
                continue
            for chemin, noms in references(texte, racine):
                forme = "motif" if "*" in chemin else ("avec noms" if noms else "chemin seul")
                resultat["formes"][forme] = resultat["formes"].get(forme, 0) + 1
                if not chemin_existe(chemin, racine):
                    resultat["cassees"].append((nom_spec, chemin, f"ligne Source : {texte}"))
                    continue
                if not noms:
                    continue
                fichier = racine / chemin
                if fichier not in caches:
                    caches[fichier] = definitions_python(fichier)
                for nom in noms:
                    if not nom_existe(nom, *caches[fichier]):
                        resultat["cassees"].append((nom_spec, f"{chemin}::{nom}", f"ligne Source : {texte}"))
        cloturer()
    return resultat


def rapport(donnees: dict) -> str:
    lignes = [
        f"lignes Source : {donnees['lignes']} ; références cassées : {len(donnees['cassees'])} ; "
        f"lignes en attente : {len(donnees['en_attente'])}",
        f"exigences : {donnees['exigences']} ; sans aucune ligne Source : {len(donnees['sans_source'])}",
        "formes : " + ", ".join(f"{k} {v}" for k, v in sorted(donnees["formes"].items())),
    ]
    for cle, titre in (("en_attente", "en attente"), ("sans_source", "sans Source")):
        par_spec: dict[str, int] = {}
        for spec, _ in donnees[cle]:
            par_spec[spec] = par_spec.get(spec, 0) + 1
        lignes.append(f"{titre} par spec : " + ", ".join(f"{s} {n}" for s, n in sorted(par_spec.items())))
    return "\n".join(lignes)


class SurLArbreReel(unittest.TestCase):
    @unittest.skipUnless((RACINE_REELLE / "openspec" / "specs").is_dir(), "arbre sans specs OpenSpec (édition)")
    def test_aucune_reference_cassee_hors_exceptions(self):
        donnees = inventaire(RACINE_REELLE)
        print("\n" + rapport(donnees))
        connues = {cle for cle in EXCEPTIONS}
        cassees = {(spec, ref): msg for spec, ref, msg in donnees["cassees"]}
        if arbre_public(RACINE_REELLE):
            cassees = {cle: msg for cle, msg in cassees.items() if not exclue_de_l_edition(*cle)}
        nouvelles = [f"{spec} : {ref} introuvable ; {msg}" for (spec, ref), msg in cassees.items() if (spec, ref) not in connues]
        self.maxDiff = None
        self.assertEqual([], nouvelles, "références cassées hors exceptions (spec : ligne)")
        perimees = [cle for cle in connues if cle not in cassees]
        self.assertEqual([], perimees, "exceptions périmées : la référence n'est plus cassée, à retirer")

    def test_chaque_exception_a_une_raison(self):
        self.assertEqual([], [cle for cle, raison in EXCEPTIONS.items() if not raison.strip()])


class GardeEcartExclusEdition(unittest.TestCase):
    @unittest.skipIf(arbre_public(RACINE_REELLE), "édition publique : manifeste non livré")
    def test_chaque_prefixe_de_la_table_est_exclu_par_le_manifeste(self):
        import sys

        import yaml

        sys.path.insert(0, str(RACINE_REELLE / "tools"))
        import build_edition

        regles = yaml.safe_load((RACINE_REELLE / "edition" / "manifest.yaml").read_text(encoding="utf-8"))["rules"]
        for spec, prefixe in EXCLUS_EDITION:
            with self.subTest(spec=spec, prefixe=prefixe):
                action = next((r["action"] for r in regles if build_edition.make_matcher(r["path"])(prefixe)), None)
                self.assertEqual("exclude", action, f"{prefixe} n'est plus exclu par le manifeste : retirer l'entrée de EXCLUS_EDITION")


class SurUnDepotFactice(unittest.TestCase):
    def _depot(self, spec: str, fichiers: dict[str, str]) -> Path:
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        racine = Path(dossier.name)
        (racine / "openspec" / "specs" / "demo").mkdir(parents=True)
        (racine / "openspec" / "specs" / "demo" / "spec.md").write_text(spec, encoding="utf-8")
        for chemin, contenu in fichiers.items():
            (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
            (racine / chemin).write_text(contenu, encoding="utf-8")
        return racine

    TEST = "class Cas:\n    def test_un(self): pass\n    def test_deux(self): pass\n\ndef test_libre(): pass\n"

    def test_references_saines(self):
        spec = (
            "### Requirement: A\nSource: tests/x/test_x.py (Cas.test_un, test_libre); `tests/x/test_x.py` (Cas)\n\n"
            "### Requirement: B\nSource: tests/x/test_x.py (Cas.test_*)\n\n"
            "### Requirement: C\nSource: tests/x (test_x.py)\n"
        )
        donnees = inventaire(self._depot(spec, {"tests/x/test_x.py": self.TEST}))
        self.assertEqual([], donnees["cassees"])
        self.assertEqual(3, donnees["lignes"])

    def test_chemin_et_noms_casses_sont_nommes(self):
        spec = (
            "### Requirement: A\nSource: tests/x/absent.py (Cas)\n\n"
            "### Requirement: B\nSource: tests/x/test_x.py (Cas.test_trois, Autre)\n"
        )
        donnees = inventaire(self._depot(spec, {"tests/x/test_x.py": self.TEST}))
        references_cassees = sorted(ref for _, ref, _ in donnees["cassees"])
        self.assertEqual(
            ["tests/x/absent.py", "tests/x/test_x.py::Autre", "tests/x/test_x.py::Cas.test_trois"], references_cassees
        )
        self.assertTrue(all(spec == "demo" for spec, _, _ in donnees["cassees"]))

    def test_en_attente_sans_echec_et_exigence_sans_source_comptee(self):
        spec = (
            "### Requirement: A\nSource: untested until implemented (tests/nouveau, task 1.1)\n\n"
            "### Requirement: B\nSource: to be covered by tests/composants (task 2.1)\n\n"
            "### Requirement: C\nSans ligne.\n"
        )
        donnees = inventaire(self._depot(spec, {}))
        self.assertEqual([], donnees["cassees"])
        self.assertEqual(2, len(donnees["en_attente"]))
        self.assertEqual([("demo", "C")], donnees["sans_source"])
        self.assertEqual(3, donnees["exigences"])

    def test_motif_sans_fichier_est_casse(self):
        spec = "### Requirement: A\nSource: .claude/commands/*.md; untested\n"
        donnees = inventaire(self._depot(spec, {".claude/commands/note.txt": ""}))
        self.assertEqual(1, len(donnees["cassees"]))


if __name__ == "__main__":
    unittest.main()
