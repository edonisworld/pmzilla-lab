"""Lecture d'un script Python du dépôt pour le manuel d'utilisation (change user-manual, design D4 et D5).

Module de bibliothèque, pas une commande. Le script décrit n'est jamais importé ni exécuté : le texte est lu puis
analysé par `ast`. Une source illisible (SyntaxError, UnicodeDecodeError) remonte telle quelle à l'appelant.

Fonction publique : `lire_script(chemin)`. Les formes de données sont fixées par le contrat du change.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

VALEUR_CALCULEE = "valeur calculée"

PREFIXES_USAGE = ("uv run tools/", "python3 tools/", "python tools/", "bash tools/", "zsh tools/")
MOTIF_CODES_LIGNE = re.compile(r"^Codes?(?: de sortie)?\s*:\s*(.*)$")
MOTIF_CODES_SECTION = re.compile(r"^Codes de sortie\s*$")
APPELS_SANS_PARSEUR = {
    "print", "isinstance", "vars", "len", "repr", "str", "getattr", "setattr", "hasattr", "id", "type", "list",
    "tuple", "dict", "set", "sorted", "iter", "next", "bool", "int", "float", "format", "dir", "callable"}
METHODES_PARSEUR = {"add_argument", "add_argument_group", "add_mutually_exclusive_group", "add_subparsers",
                    "add_parser"}
PROFONDEUR_MAX = 6


# --- docstring : rôle, usages, codes de sortie ---------------------------------------------------------------------

def _indentation(ligne: str) -> int:
    return len(ligne) - len(ligne.lstrip())


def _role(doc: str | None) -> str | None:
    for ligne in (doc or "").splitlines():
        if ligne.strip():
            return ligne.strip()
    return None


def _usages(doc: str | None) -> list[str]:
    lignes = [ligne.strip() for ligne in (doc or "").splitlines()]
    return [ligne for ligne in lignes if ligne.startswith(PREFIXES_USAGE)]


def _codes_forme_ligne(lignes: list[str], debut: int, valeur: str) -> list[str]:
    """Forme `Codes : ...` avec ses lignes de continuation plus indentées que la ligne d'ouverture."""
    indent = _indentation(lignes[debut])
    suite = []
    for ligne in lignes[debut + 1:]:
        if not ligne.strip() or _indentation(ligne) <= indent:
            break
        suite.append(ligne.strip())
    morceaux = ([valeur] if valeur else []) + suite
    if not morceaux:
        return []
    jointe = " ".join(" ".join(morceaux).split())
    # Une entrée par ligne quand les lignes de suite commencent chacune par un chiffre et que rien n'est séparé par « ; ».
    if ";" not in jointe and len(morceaux) > 1 and all(m[:1].isdigit() for m in morceaux):
        return [" ".join(m.split()) for m in morceaux]
    return [element.strip() for element in jointe.split(";") if element.strip()]


def _codes_forme_section(lignes: list[str], debut: int) -> list[str]:
    """Section `Codes de sortie` : ses lignes jusqu'à la première ligne vide, une ligne par élément."""
    elements = []
    for position, ligne in enumerate(lignes[debut + 1:]):
        texte = ligne.strip()
        if not texte:
            break
        if position == 0 and set(texte) <= set("-=~"):
            continue
        elements.append(texte)
    return elements


def _codes(doc: str | None) -> list[str] | None:
    lignes = (doc or "").splitlines()
    for position, ligne in enumerate(lignes):
        texte = ligne.strip()
        correspondance = MOTIF_CODES_LIGNE.match(texte)
        if correspondance:
            elements = _codes_forme_ligne(lignes, position, correspondance.group(1).strip())
        elif MOTIF_CODES_SECTION.match(texte):
            elements = _codes_forme_section(lignes, position)
        else:
            continue
        if elements:
            return elements
    return None


# --- valeurs littérales ---------------------------------------------------------------------------------------------

def _texte(noeud: ast.AST | None) -> str | None:
    """Valeur textuelle d'une expression purement littérale, sinon None."""
    if isinstance(noeud, ast.Constant):
        return noeud.value if isinstance(noeud.value, str) else None
    if isinstance(noeud, ast.JoinedStr):
        morceaux = []
        for partie in noeud.values:
            if isinstance(partie, ast.Constant) and isinstance(partie.value, str):
                morceaux.append(partie.value)
            else:
                return None
        return "".join(morceaux)
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Add):
        gauche, droite = _texte(noeud.left), _texte(noeud.right)
        return None if gauche is None or droite is None else gauche + droite
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Mod):
        gauche = _texte(noeud.left)
        if gauche is None:
            return None
        try:
            droite = ast.literal_eval(noeud.right)
            return gauche % droite
        except Exception:
            return None
    return None


def _litteral(noeud: ast.AST) -> tuple[bool, object]:
    try:
        return True, ast.literal_eval(noeud)
    except Exception:
        return False, None


def _aide(noeud: ast.AST | None) -> str | None:
    if noeud is None:
        return None
    if isinstance(noeud, ast.Constant) and noeud.value is None:
        return None
    texte = _texte(noeud)
    return VALEUR_CALCULEE if texte is None else texte


def _supprime(noeud: ast.AST | None) -> bool:
    if isinstance(noeud, ast.Attribute) and noeud.attr == "SUPPRESS":
        return True
    if isinstance(noeud, ast.Name) and noeud.id == "SUPPRESS":
        return True
    return isinstance(noeud, ast.Constant) and noeud.value == "==SUPPRESS=="


def _choix(noeud: ast.AST | None):
    if noeud is None:
        return None
    if isinstance(noeud, (ast.Tuple, ast.List, ast.Set)):
        valeurs = []
        for element in noeud.elts:
            lisible, valeur = _litteral(element)
            if not lisible or isinstance(valeur, (list, tuple, set, dict, frozenset)):
                return VALEUR_CALCULEE
            valeurs.append(str(valeur))
        return valeurs
    return VALEUR_CALCULEE


def _defaut(noeud: ast.AST | None):
    if noeud is None:
        return None
    lisible, valeur = _litteral(noeud)
    if not lisible:
        return VALEUR_CALCULEE
    return None if valeur is None else str(valeur)


def _chaine_litterale(noeud: ast.AST | None) -> str | None:
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    return None


def _booleen(noeud: ast.AST | None) -> bool | None:
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, bool):
        return noeud.value
    return None


# --- modèle interne -------------------------------------------------------------------------------------------------

class _Noeud:
    """Un parseur ou un sous-parseur en cours de construction."""

    def __init__(self, nom=None, aide=None, description=None):
        self.nom = nom
        self.aide = aide
        self.description = description
        self.arguments: list[dict] = []
        self.enfants: list[_Noeud] = []
        self.parents: list[_Noeud] = []
        self.partagee = False
        self.requis_sous: bool | None = None
        self.exclusifs = 0


class _Groupe:
    """Groupe d'arguments ou groupe exclusif : ses arguments vont dans le noeud propriétaire."""

    def __init__(self, proprietaire: _Noeud, exclusif: int | None):
        self.proprietaire = proprietaire
        self.exclusif = exclusif


class _SousParseurs:
    """Résultat de `add_subparsers(...)`."""

    def __init__(self, parent: _Noeud):
        self.parent = parent


class _Portee:
    def __init__(self, env: dict, pile: tuple):
        self.env = env
        self.pile = pile
        self.cache: dict[int, object] = {}


def _portee_noeuds(corps: list[ast.stmt]):
    """Tous les noeuds d'une portée sans descendre dans les fonctions, classes et lambdas imbriquées."""
    pile = list(corps)
    while pile:
        noeud = pile.pop()
        yield noeud
        for enfant in ast.iter_child_nodes(noeud):
            if not isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                pile.append(enfant)


def _position(noeud: ast.AST) -> tuple[int, int]:
    return noeud.lineno, noeud.col_offset


class _Analyse:
    """Parcours d'un module : construit les noeuds, applique les assistants définis dans le même fichier."""

    def __init__(self, arbre: ast.Module):
        self.arbre = arbre
        self.definitions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.fonctions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.fonctions.append(noeud)
                self.definitions.setdefault(noeud.name, noeud)
        self.fonctions.sort(key=_position)
        self.classes_parseur = {"ArgumentParser"}
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ClassDef):
                for base in noeud.bases:
                    nom_base = base.id if isinstance(base, ast.Name) else (
                        base.attr if isinstance(base, ast.Attribute) else None)
                    if nom_base in self.classes_parseur:
                        self.classes_parseur.add(noeud.name)
        self.creations: dict[tuple[int, int], object] = {}
        self.principal: _Noeud | None = None
        self.appel_principal: ast.Call | None = None
        premier = None
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and self._est_parseur(noeud):
                if premier is None or _position(noeud) < _position(premier):
                    premier = noeud
        self.appel_principal = premier

    def _est_parseur(self, appel: ast.Call) -> bool:
        """Appel de `ArgumentParser` ou d'une sous-classe définie dans le même fichier."""
        fonction = appel.func
        return (isinstance(fonction, ast.Name) and fonction.id in self.classes_parseur) or (
            isinstance(fonction, ast.Attribute) and fonction.attr in self.classes_parseur)

    def lancer(self) -> _Noeud | None:
        if self.appel_principal is None:
            return None
        self._portee(self.arbre.body, {}, ())
        for fonction in self.fonctions:
            self._portee(fonction.body, {}, (fonction.name,))
        return self.principal

    # -- parcours d'une portée --

    def _portee(self, corps: list[ast.stmt], env: dict, pile: tuple):
        portee = _Portee(env, pile)
        evenements = []
        for noeud in _portee_noeuds(corps):
            if isinstance(noeud, (ast.Assign, ast.AnnAssign, ast.Call)):
                evenements.append(noeud)
        evenements.sort(key=_position)
        for evenement in evenements:
            try:
                if isinstance(evenement, ast.Call):
                    self._appel(evenement, portee)
                else:
                    self._affectation(evenement, portee)
            except RecursionError:
                continue
        retour = None
        for noeud in _portee_noeuds(corps):
            if isinstance(noeud, ast.Return) and noeud.value is not None:
                objet = self._resoudre(noeud.value, portee)
                if objet is not None and retour is None:
                    retour = objet
        return retour

    def _affectation(self, noeud, portee: _Portee):
        valeur = noeud.value
        cibles = noeud.targets if isinstance(noeud, ast.Assign) else [noeud.target]
        if valeur is None:
            return
        for cible in cibles:
            if isinstance(cible, ast.Attribute) and cible.attr == "required" and isinstance(cible.value, ast.Name):
                sous = portee.env.get(cible.value.id)
                if isinstance(sous, _SousParseurs) and _booleen(valeur) is not None:
                    sous.parent.requis_sous = _booleen(valeur)
        objet = self._resoudre(valeur, portee)
        for cible in cibles:
            if isinstance(cible, ast.Name):
                if objet is not None:
                    portee.env[cible.id] = objet
                else:
                    portee.env.pop(cible.id, None)

    def _resoudre(self, expression: ast.AST, portee: _Portee):
        if isinstance(expression, ast.Name):
            return portee.env.get(expression.id)
        if isinstance(expression, ast.Call):
            return self._appel(expression, portee)
        return None

    # -- un appel --

    def _creer(self, cle: tuple[int, int], fabrique):
        if cle not in self.creations:
            self.creations[cle] = fabrique()
        return self.creations[cle]

    def _appel(self, appel: ast.Call, portee: _Portee):
        if id(appel) in portee.cache:
            return portee.cache[id(appel)]
        portee.cache[id(appel)] = None
        resultat = self._appel_brut(appel, portee)
        portee.cache[id(appel)] = resultat
        return resultat

    def _appel_brut(self, appel: ast.Call, portee: _Portee):
        fonction = appel.func
        if self._est_parseur(appel):
            return self._parseur(appel, portee)
        if isinstance(fonction, ast.Attribute):
            recepteur = self._resoudre(fonction.value, portee)
            if recepteur is not None and fonction.attr in METHODES_PARSEUR:
                return self._methode(recepteur, fonction.attr, appel, portee)
            if recepteur is not None:
                return None
        return self._assistant(appel, portee)

    def _parseur(self, appel: ast.Call, portee: _Portee):
        def fabrique():
            noeud = _Noeud(description=_texte(self._mot(appel, "description")))
            for parent in self._parents(appel, portee):
                noeud.parents.append(parent)
            if appel is self.appel_principal:
                self.principal = noeud
            return noeud
        return self._creer((0, id(appel)), fabrique)

    @staticmethod
    def _mot(appel: ast.Call, nom: str) -> ast.AST | None:
        for mot in appel.keywords:
            if mot.arg == nom:
                return mot.value
        return None

    def _parents(self, appel: ast.Call, portee: _Portee) -> list[_Noeud]:
        valeur = self._mot(appel, "parents")
        if not isinstance(valeur, (ast.List, ast.Tuple)):
            return []
        trouves = []
        for element in valeur.elts:
            objet = self._resoudre(element, portee)
            if isinstance(objet, _Noeud):
                trouves.append(objet)
        return trouves

    def _methode(self, recepteur, nom: str, appel: ast.Call, portee: _Portee):
        proprietaire = recepteur.proprietaire if isinstance(recepteur, _Groupe) else (
            recepteur.parent if isinstance(recepteur, _SousParseurs) else recepteur)
        cle = (id(recepteur), id(appel))
        if nom == "add_argument" and isinstance(recepteur, (_Noeud, _Groupe)):
            if cle not in self.creations:
                self.creations[cle] = True
                exclusif = recepteur.exclusif if isinstance(recepteur, _Groupe) else None
                argument = self._argument(appel, exclusif)
                if argument is not None:
                    proprietaire.arguments.append(argument)
            return None
        if nom == "add_argument_group" and isinstance(recepteur, (_Noeud, _Groupe)):
            return self._creer(cle, lambda: _Groupe(proprietaire, None))
        if nom == "add_mutually_exclusive_group" and isinstance(recepteur, (_Noeud, _Groupe)):
            def fabrique():
                numero = proprietaire.exclusifs
                proprietaire.exclusifs += 1
                return _Groupe(proprietaire, numero)
            return self._creer(cle, fabrique)
        if nom == "add_subparsers" and isinstance(recepteur, _Noeud):
            def fabrique_sous():
                if recepteur.requis_sous is None:
                    recepteur.requis_sous = _booleen(self._mot(appel, "required"))
                return _SousParseurs(recepteur)
            return self._creer(cle, fabrique_sous)
        if nom == "add_parser" and isinstance(recepteur, _SousParseurs):
            def fabrique_enfant():
                premier = appel.args[0] if appel.args else None
                nom_sous = _chaine_litterale(premier) or VALEUR_CALCULEE
                enfant = _Noeud(nom=nom_sous, aide=_aide(self._mot(appel, "help")))
                enfant.parents = self._parents(appel, portee)
                recepteur.parent.enfants.append(enfant)
                return enfant
            return self._creer(cle, fabrique_enfant)
        return None

    def _assistant(self, appel: ast.Call, portee: _Portee):
        """Appel d'une fonction ordinaire : suit un assistant défini dans le fichier, signale les autres."""
        fonction = appel.func
        nom = None
        decalage = 0
        if isinstance(fonction, ast.Name):
            nom = fonction.id
        elif isinstance(fonction, ast.Attribute) and isinstance(fonction.value, ast.Name) \
                and fonction.value.id in ("self", "cls"):
            nom = fonction.attr
            decalage = 1
        premier = None
        if appel.args and not isinstance(appel.args[0], ast.Starred):
            premier = self._resoudre(appel.args[0], portee)
        definition = self.definitions.get(nom) if nom else None
        if premier is None and definition is None:
            return None
        if premier is not None and definition is None:
            nom_appele = fonction.id if isinstance(fonction, ast.Name) else (
                fonction.attr if isinstance(fonction, ast.Attribute) else None)
            if nom_appele not in APPELS_SANS_PARSEUR:
                self._marquer_partagee(premier)
            return None
        if nom in portee.pile or len(portee.pile) >= PROFONDEUR_MAX:
            if premier is not None and nom not in portee.pile:
                self._marquer_partagee(premier)
            return None
        parametres = [p.arg for p in definition.args.posonlyargs + definition.args.args][decalage:]
        env = {}
        if premier is not None and parametres:
            env[parametres[0]] = premier
        elif premier is not None:
            self._marquer_partagee(premier)
        return self._portee(definition.body, env, portee.pile + (nom,))

    @staticmethod
    def _marquer_partagee(objet) -> None:
        if isinstance(objet, _Groupe):
            objet.proprietaire.partagee = True
        elif isinstance(objet, _SousParseurs):
            objet.parent.partagee = True
        elif isinstance(objet, _Noeud):
            objet.partagee = True

    # -- un argument --

    def _argument(self, appel: ast.Call, exclusif: int | None) -> dict | None:
        mots = {mot.arg: mot.value for mot in appel.keywords if mot.arg}
        if "help" in mots and _supprime(mots["help"]):
            return None
        noms = []
        for position in appel.args:
            noms.append(_chaine_litterale(position) or VALEUR_CALCULEE)
        if not noms:
            noms = [VALEUR_CALCULEE]
        positionnel = not noms[0].startswith("-") and noms[0] != VALEUR_CALCULEE
        if noms[0] == VALEUR_CALCULEE:
            positionnel = False
        nargs = None
        if "nargs" in mots and isinstance(mots["nargs"], ast.Constant) \
                and isinstance(mots["nargs"].value, (str, int)) and not isinstance(mots["nargs"].value, bool):
            nargs = mots["nargs"].value
        requis = _booleen(mots.get("required")) is True
        if positionnel and nargs not in ("?", "*"):
            requis = True
        metavar = _chaine_litterale(mots.get("metavar"))
        return {
            "noms": noms, "positionnel": positionnel, "dest": _chaine_litterale(mots.get("dest")),
            "requis": requis, "action": _chaine_litterale(mots.get("action")), "nargs": nargs,
            "choix": _choix(mots.get("choices")), "defaut": _defaut(mots.get("default")),
            "aide": _aide(mots.get("help")), "metavar": metavar, "exclusif": exclusif}


# --- conversion vers les formes du contrat -------------------------------------------------------------------------

def _arguments(noeud: _Noeud, vus: tuple = ()) -> list[dict]:
    resultat = []
    for parent in noeud.parents:
        if id(parent) not in vus:
            resultat.extend(dict(a) for a in _arguments(parent, vus + (id(noeud),)))
    resultat.extend(noeud.arguments)
    return resultat


def _sous_commande(noeud: _Noeud) -> dict:
    return {"nom": noeud.nom, "aide": noeud.aide, "arguments": _arguments(noeud),
            "sous_commandes": [enfant.nom for enfant in noeud.enfants], "fonction_partagee": noeud.partagee}


def _parseur(noeud: _Noeud) -> dict:
    return {"description": noeud.description, "arguments": _arguments(noeud),
            "sous_commandes": [_sous_commande(enfant) for enfant in noeud.enfants],
            "sous_commandes_requises": noeud.requis_sous, "fonction_partagee": noeud.partagee}


def _a_bloc_principal(arbre: ast.Module) -> bool:
    for noeud in arbre.body:
        if not isinstance(noeud, ast.If) or not isinstance(noeud.test, ast.Compare):
            continue
        test = noeud.test
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            continue
        elements = [test.left, test.comparators[0]]
        noms = any(isinstance(e, ast.Name) and e.id == "__name__" for e in elements)
        principal = any(isinstance(e, ast.Constant) and e.value == "__main__" for e in elements)
        if noms and principal:
            return True
    return False


def lire_script(chemin: Path) -> dict | None:
    """Lit un script Python sans l'importer ; None pour un module de bibliothèque (pas de bloc `__main__`)."""
    texte = Path(chemin).read_text(encoding="utf-8")
    arbre = ast.parse(texte, filename=str(chemin))
    if not _a_bloc_principal(arbre):
        return None
    doc = ast.get_docstring(arbre, clean=False)
    principal = _Analyse(arbre).lancer()
    return {
        "role": _role(doc), "usages": _usages(doc), "codes": _codes(doc),
        "parseur": None if principal is None else _parseur(principal),
        "sans_parseur": principal is None}
