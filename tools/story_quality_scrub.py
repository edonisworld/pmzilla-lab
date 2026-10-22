"""PMZilla Lab : nettoyage des textes des stories et des epics avant stockage (change story-quality-audit, design D4, couche 2).

Fonctions pures : aucune base, aucun Jira, aucune sortie. Chacun des trois textes (titre, description, critères d'acceptation) est
réécrit avant d'être stocké, donc avant toute analyse, tout affichage et tout envoi au moteur :

  - un nœud de mention du texte riche (format de document d'Atlassian) devient « [person] », sans l'identifiant de compte ;
  - un lien d'utilisateur de style wiki (« [~accountid:…] », « [~identifiant] ») devient « [person] » ;
  - un lien vers une page de profil (marque de lien du texte riche, « [libellé|adresse] » de style wiki) devient « [person] », libellé
    compris ;
  - une adresse électronique devient « [email] » ;
  - chaque entrée de la liste des noms sensibles, comparée sans casse et en mot entier, devient « [name] » ;
  - une image, un média ou un lien de pièce jointe est retiré et remplacé par « [media] ».

Les marques sont les mêmes dans les deux langues. Seul le nombre de remplacements est rendu, jamais ce qui a été remplacé. Les attributs
des nœuds (identifiants, adresses des liens, auteurs) ne sont jamais repris : seul le texte visible l'est. Un nom écrit en clair et
absent de la liste reste dans le texte (risque accepté par l'utilisateur le 2026-10-15, relecture d'un échantillon par équipe).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

PERSONNE, ADRESSE, NOM, MEDIA = "[person]", "[email]", "[name]", "[media]"
MARQUES = (PERSONNE, ADRESSE, NOM, MEDIA)
MOT = "A-Za-z0-9_"

ESPACES = "[\\s  ]+"
LARGEUR_NULLE = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF])
LIEN_UTILISATEUR_WIKI = re.compile(r"\[~(?:accountid:)?[^\]\s]+\]|\[[^\]|]*\|~[^\]]+\]")
PROFIL = re.compile(r"/jira/people/|ViewProfile\.jspa\?name=|/secure/ViewProfile|accountId=", re.IGNORECASE)
LIEN_WIKI = re.compile(r"\[[^\]|\n]*\|([^\]\n]+)\]")     # [libellé|adresse] : remplacé seulement si l'adresse est une page de profil
MEDIA_WIKI = re.compile(r"!(?:https?://[^!\s|]+|[^!\s|]+\.[A-Za-z0-9]{2,5})(?:\|[^!\n]*)?!|\[\^[^\]\n]+\]")
ADRESSE_ELECTRONIQUE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PIECE_JOINTE = re.compile(r"/(?:rest/api/\d+/attachment|secure/attachment|attachment)/", re.IGNORECASE)
MARQUE_EXISTANTE = r"\[(?:person|email|name|media)\]"

NOEUDS_MEDIA = {"mediaSingle", "mediaGroup", "media", "mediaInline"}
NOEUDS_CARTE = {"inlineCard", "blockCard", "embedCard"}
NOEUDS_BLOC = {"paragraph", "heading", "bulletList", "orderedList", "listItem", "blockquote", "codeBlock", "panel", "table",
               "tableRow", "tableHeader", "tableCell", "rule", "expand", "nestedExpand", "taskList", "taskItem", "decisionList",
               "decisionItem", "mediaSingle", "mediaGroup", "blockCard", "embedCard", "layoutSection", "layoutColumn"}
CLES_OPTION = ("value", "name", "label", "title")      # option d'un champ de liste ; jamais displayName (champ de personne)


class Nettoyeur:
    """Nettoyeur lié à une liste de noms sensibles (non vide : sans liste, rien ne doit être collecté)."""

    def __init__(self, noms):
        noms = sorted({_normaliser(n).strip() for n in noms if n and _normaliser(n).strip()}, key=len, reverse=True)
        if not noms:
            raise ValueError("liste des noms sensibles vide")
        alternatives = "|".join(ESPACES.join(re.escape(p) for p in n.split()) for n in noms)
        self._noms = re.compile(rf"({MARQUE_EXISTANTE})|(?<![{MOT}])(?:{alternatives})(?![{MOT}])", re.IGNORECASE)

    def nettoyer(self, valeur) -> tuple[str, int]:
        """(texte nettoyé, nombre de remplacements) d'une valeur de champ : texte, document riche, option, liste ou None."""
        compte = [0]
        texte = _normaliser(_rendre(valeur, compte)).strip()
        texte = self._texte(texte, compte)
        return texte, compte[0]

    def _texte(self, texte: str, compte: list) -> str:
        def lien_wiki(m):                    # avant les adresses : une adresse de profil peut porter un « @ »
            if not PROFIL.search(m.group(1)):
                return m.group(0)
            compte[0] += 1
            return PERSONNE
        texte = LIEN_WIKI.sub(lien_wiki, texte)
        for motif, marque in ((LIEN_UTILISATEUR_WIKI, PERSONNE), (MEDIA_WIKI, MEDIA), (ADRESSE_ELECTRONIQUE, ADRESSE)):
            texte, n = motif.subn(marque, texte)
            compte[0] += n

        def nom(m):
            if m.group(1):                   # une marque déjà posée reste telle quelle, même si la liste porte son mot
                return m.group(1)
            compte[0] += 1
            return NOM
        return self._noms.sub(nom, texte)


def _normaliser(texte: str) -> str:
    """NFC, sans caractère de largeur nulle : un nom ne doit pas échapper à la liste par sa forme d'écriture."""
    return unicodedata.normalize("NFC", texte).translate(LARGEUR_NULLE)


def _rendre(valeur, compte: list) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, str):
        return valeur
    if isinstance(valeur, bool):
        return ""
    if isinstance(valeur, (int, float)):
        return str(valeur)
    if isinstance(valeur, list):
        return "\n".join(t for t in (_rendre(v, compte).strip() for v in valeur) if t)
    if isinstance(valeur, dict):
        if "type" in valeur:
            return _noeud(valeur, compte)[0]
        for cle in CLES_OPTION:
            if isinstance(valeur.get(cle), str):
                return valeur[cle]
    return ""


def _noeud(noeud: dict, compte: list) -> tuple[str, bool]:
    """(texte, est un bloc) d'un nœud du format de document d'Atlassian. Seul le texte visible est repris, jamais un attribut."""
    genre = noeud.get("type")
    attrs = noeud.get("attrs") if isinstance(noeud.get("attrs"), dict) else {}
    bloc = genre in NOEUDS_BLOC
    if genre == "text":
        if any(isinstance(m, dict) and m.get("type") == "link" and isinstance(m.get("attrs"), dict)
               and PROFIL.search(str(m["attrs"].get("href") or "")) for m in noeud.get("marks") or []):
            compte[0] += 1                   # le texte d'un lien vers un profil est d'ordinaire un nom
            return PERSONNE, False
        return str(noeud.get("text") or ""), False
    if genre == "mention":
        compte[0] += 1
        return PERSONNE, False
    if genre in NOEUDS_MEDIA:
        compte[0] += 1
        return MEDIA, bloc
    if genre in NOEUDS_CARTE:
        url = str(attrs.get("url") or "")
        if PROFIL.search(url):
            compte[0] += 1
            return PERSONNE, bloc
        if PIECE_JOINTE.search(url):
            compte[0] += 1
            return MEDIA, bloc
        return url, bloc
    if genre == "hardBreak":
        return "\n", False
    if genre in ("emoji", "status"):
        return str(attrs.get("text") or attrs.get("shortName") or ""), False
    if genre in ("date", "rule", "placeholder"):
        return "", bloc
    parties: list[tuple[str, bool]] = [_noeud(e, compte) for e in noeud.get("content") or [] if isinstance(e, dict)]
    texte = ""
    precedent_bloc = False
    for i, (morceau, est_bloc) in enumerate(parties):
        if i and (est_bloc or precedent_bloc):
            texte += "\n"
        texte += morceau.strip("\n") if est_bloc else morceau
        precedent_bloc = est_bloc
    return texte, bloc or genre == "doc"


def empreinte(titre: str, description: str, criteres: str) -> str:
    """Empreinte du contenu nettoyé (sha256 des trois textes) : sert à reconnaître un texte inchangé, ne se relit pas en texte."""
    return hashlib.sha256("\x00".join((titre, description, criteres)).encode("utf-8")).hexdigest()
