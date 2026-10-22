"""
Fixture du dossier de contexte (organisation-context, design D14, tâche 3.1) : un dossier temporaire avec `originaux/` (une sentinelle),
`notes/` (notes inventées de chaque sorte), une fausse liste de noms sensibles, des identifiants personnels fictifs, une date injectable
et des surveillants d'accès au dossier des originaux. Rien de réel : aucun nom de personne, d'équipe ni de projet.

Importé par tests/context_lab, tests/pmzilla_lab_library, tests/library_backend, tests/wake_postures, tests/watch_sh et tests/build_edition.
"""
import builtins
import contextlib
import datetime as dt
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))

SENTINELLE = "SENTINELLE-DES-ORIGINAUX-9f3a"
CORPS_UNIQUE = "CORPS-UNIQUE-DE-LA-NOTE-77c1"
NOM_SENSIBLE = "Zorglubix"             # le seul nom de la fausse liste
IDENTIFIANT = "identifiant-fictif-42"   # l'identifiant personnel fictif
NOM_EXTRAIT = "Zorblax Unit"            # nom d'équipe fictif du faux extrait, absent de la fausse liste (context-index-name-guard, D4)
NOM_GENERIQUE = "Quibblon Works"        # nom fictif du faux extrait que la fausse liste des noms génériques écarte
AUJOURDHUI = dt.date(2026, 10, 18)
ANCIEN_DOSSIER = "Contexte" + "-Lab"    # écrit en deux morceaux : ce fichier ne porte pas l'ancien nom en littéral


def note(title="Organisation de test", date="2026-09-01", nature="declarative", source="entretien avec un rôle", review="2027-03-01",
         kind=None, body=None, sans=(), **autres):
    """Texte d'une note : en-tête puis corps. `sans` retire des champs ; `autres` en ajoute ou remplace."""
    champs = {"title": title, "date": date, "nature": nature, "source": source, "review": review}
    if kind:
        champs["kind"] = kind
    champs.update(autres)
    for nom in sans:
        champs.pop(nom, None)
    en_tete = "".join(f"{k}: {v}\n" for k, v in champs.items())
    corps = body if body is not None else f"## Périmètre\n\n{CORPS_UNIQUE}\n"
    return f"---\n{en_tete}---\n\n{corps}"


class Contexte:
    """Un faux lab dans un dossier temporaire : lab/workspace (contenu), lab/contexte (originaux, notes), liste de noms, environnement."""

    def __init__(self, notes=None, avec_liste=True, avec_dossier=True):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.lab = self.tmp / "lab"
        self.workspace = self.lab / "workspace"
        self.workspace.mkdir(parents=True)
        self.dossier = self.lab / "contexte"
        self.originaux = self.dossier / "originaux"
        self.notes = self.dossier / "notes"
        self.liste = self.tmp / "noms-sensibles.txt"
        if avec_liste:
            self.liste.write_text(f"# liste fictive\n{NOM_SENSIBLE}\n", encoding="utf-8")
        if avec_dossier:
            for d in (self.dossier, self.originaux, self.notes):
                d.mkdir(mode=0o700)
                d.chmod(0o700)
            (self.originaux / "piege.txt").write_text(SENTINELLE, encoding="utf-8")
            for nom, texte in (notes or {}).items():
                self.ecrire(nom, texte)

    def close(self):
        self._tmp.cleanup()

    def ecrire(self, nom, texte):
        chemin = self.notes / nom
        chemin.write_text(texte, encoding="utf-8")
        chemin.chmod(0o600)
        return chemin

    def ecrire_extrait(self, noms=(NOM_EXTRAIT, NOM_GENERIQUE), generiques=(NOM_GENERIQUE,)):
        """Faux extrait des noms d'équipes, voisin de la fausse liste (même dossier), et fausse liste des noms génériques."""
        lignes = "".join(f"  - name: {n}\n" for n in noms)
        (self.tmp / "equipes-lisibles.yaml").write_text(f"referential_teams:\n{lignes}catalogue_teams: []\n", encoding="utf-8")
        (self.tmp / "noms-generiques.txt").write_text("".join(f"{n}\n" for n in generiques), encoding="utf-8")

    def env(self, **extra):
        base = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.tmp), "PMZILLA_LAB_WORKSPACE": str(self.workspace),
                "PMZILLA_LAB_CONTEXT": str(self.dossier), "PMZILLA_LAB_SENSITIVE_NAMES": str(self.liste)}
        base.update(extra)
        return base

    def arbre(self):
        """Contenu du dossier hors originaux : {chemin relatif: octets}, pour vérifier qu'une commande n'a rien changé."""
        vu = {}
        for p in sorted(self.dossier.rglob("*")):
            if p.is_file() and "originaux" not in p.relative_to(self.dossier).parts:
                vu[str(p.relative_to(self.dossier))] = p.read_bytes()
        return vu

    def lancer(self, argv, stdin="", **options):
        """context_lab.main en processus : (code, sortie standard, sortie d'erreur)."""
        import context_lab
        sortie, erreur = io.StringIO(), io.StringIO()
        options.setdefault("today", AUJOURDHUI)
        options.setdefault("identifiers", [IDENTIFIANT])
        env = options.pop("env", None) or self.env()
        code = context_lab.main(argv, env=env, stdin=io.StringIO(stdin), out=sortie, err=erreur, **options)
        return code, sortie.getvalue(), erreur.getvalue()


def notes_de_reference():
    """Notes inventées de chaque sorte (D14) : nom de fichier -> texte."""
    return {
        "2026-09-01-organisation-de-test.md": note(),
        "2026-06-01-note-a-revoir.md": note(title="Note ancienne", date="2026-06-01", review="2026-09-01"),
        "carte-contexte.md": note(title="Carte du contexte", kind="map", body="## Périmètre produit\n\nUn produit inventé.\n"),
        "2026-09-02-sans-source.md": note(title="Sans source", sans=("source",)),
        "2026-09-03-nature-inconnue.md": note(title="Nature inconnue", nature="rumeur"),
        "2026-09-04-revue-avant.md": note(title="Revue avant", review="2026-08-01"),
    }


class Surveillant:
    """Échoue (en l'enregistrant) sur tout accès à un chemin STRICTEMENT sous le dossier des originaux : open, os.open, os.stat,
    os.lstat, os.scandir, os.listdir. Le dossier des originaux lui-même n'est pas surveillé (init le crée)."""

    def __init__(self, originaux: Path):
        self.prefixe = str(originaux) + os.sep
        self.vus = []

    def _garde(self, original):
        def enveloppe(chemin, *args, **kwargs):
            if isinstance(chemin, (str, bytes, os.PathLike)) and os.fsdecode(chemin).startswith(self.prefixe):
                self.vus.append(os.fsdecode(chemin))
            return original(chemin, *args, **kwargs)
        return enveloppe

    @contextlib.contextmanager
    def actif(self):
        with contextlib.ExitStack() as pile:
            for objet, nom in ((os, "stat"), (os, "lstat"), (os, "scandir"), (os, "listdir"), (os, "open"), (builtins, "open")):
                pile.enter_context(mock.patch.object(objet, nom, self._garde(getattr(objet, nom))))
            yield self
