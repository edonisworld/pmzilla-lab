"""PMZilla Lab : détecteur de données de patient dans le texte nettoyé des stories et des epics (change patient-data-detection, design D1 et D2).

Module pur : aucune base, aucun réseau, aucune sortie, aucune écriture. Il n'importe aucune bibliothèque HTTP ni de socket.

    DETECTOR_VERSION                       entier relevé à chaque changement d'un motif, d'une liste intégrée ou d'une règle
    count(text, extra_labels=())           {code de catégorie: nombre de détections} ; jamais une valeur trouvée ni une position
    mask(text, extra_labels=())            (texte, nombre de remplacements) ; chaque détection devient la marque de sa catégorie
    labels_fingerprint(labels)             empreinte de la liste facultative d'étiquettes (None sans étiquette)

`count` et `mask` partagent les mêmes motifs compilés : le compte, le contrôle avant envoi et le masquage ne divergent jamais, et
`count(mask(t))` vaut zéro pour toutes les catégories. Les règles s'appliquent au texte déjà nettoyé : une marque existante
([person], [email], [name], [media] et celles de ce module) n'est jamais reconnue à nouveau. Les étiquettes se comparent sans accent ni
casse ; les noms propres de P5 doivent s'écrire avec une majuscule.

Catégories (voir design D2) : P1 numéro de sécurité sociale (structure et clé valide), P2 identifiant de patient (étiquette puis un mot
d'au moins quatre chiffres), P3 numéro de séjour, de dossier ou de prélèvement, P4 date de naissance (étiquette puis date complète),
P5 nom de patient (mot de civilité ou « patient » puis un nom propre hors liste de mots courants), P6 date de naissance et nom dans la même
phrase, P7 numéro de téléphone, P8 adresse postale (numéro, mot de voie, code postal de cinq chiffres sur une ligne), P9 un mot clinique de
la liste courte dans la phrase d'une détection P1, P2, P3, P5 ou P6. Le vocabulaire clinique seul ne compte jamais ; les identifiants de
soignants et d'établissements sont hors périmètre.

Choix hors design : le nom de P5 n'est reconnu qu'après un mot de civilité ou « patient » (jamais un nom en majuscules isolé), pour ne pas
compter chaque sigle ; un nom suit au plus deux mots propres.

Cette liste de règles est nouvelle et ne remplace rien. Condition de retrait : permanente (chaque nouvelle collecte peut apporter du
texte écrit par des personnes qui travaillent avec des dossiers de patients).
"""
from __future__ import annotations

import bisect
import hashlib
import re
import unicodedata
from functools import lru_cache

DETECTOR_VERSION = 1
CATEGORIES = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9")

# Marques de la phase 2 (design D7), les mêmes dans les deux langues. P6 n'a pas de marque propre : ses deux parties sont celles de P4 et P5 ;
# P9 n'en a pas non plus.
MARKERS = {"P1": "[ssn]", "P2": "[patient-id]", "P3": "[record-no]", "P4": "[birth-date]", "P5": "[patient-name]", "P7": "[phone]",
           "P8": "[address]"}
EXISTING_MARKER = re.compile(r"\[(?:person|email|name|media|ssn|patient-id|record-no|birth-date|patient-name|phone|address)\]")

_ID_WORD = r"(?:identifier|identifiant|number|numero|num|nbr|nr|no|id|n°)"
_TOKEN = r"(?P<tok>[a-z0-9][a-z0-9_\-/]{3,})"
_SEP = r"[ \t:=#\- .]{0,4}"
_LEFT, _RIGHT = r"(?<![a-z0-9])", r"(?![a-z])"
_RECORD_NOUN = (r"(?:medical[ ]+record|dossier|record|stay|sejour|encounter|visit|visite|admission|venue|passage|specimen|accession|"
                r"prelevement|echantillon)")

_P2_LABELS = (rf"patient[ _\-]?{_ID_WORD}", rf"{_ID_WORD}[ _\-]?(?:du[ ]+|de[ ]+la[ ]+|of[ ]+(?:the[ ]+)?)?patient", r"ipp")
_P3_LABELS = (rf"{_RECORD_NOUN}[ _\-]?{_ID_WORD}",
              rf"{_ID_WORD}[ _\-]?(?:de[ ]+|d['’]|du[ ]+|of[ ]+(?:the[ ]+)?)?{_RECORD_NOUN}", r"mrn")

_SEPARATEUR_P1 = r"[   .]?"
_P1 = re.compile(
    r"(?<![0-9])([1-478])" + _SEPARATEUR_P1 + r"(\d{2})" + _SEPARATEUR_P1 + r"(0[1-9]|1[0-2]|20|3\d|4[0-2]|[5-9]\d)" + _SEPARATEUR_P1
    + r"(\d{2}|2[AB])" + _SEPARATEUR_P1 + r"(\d{3})" + _SEPARATEUR_P1 + r"(\d{3})(?:" + _SEPARATEUR_P1 + r"(\d{2}))?(?![0-9])", re.I)

_BIRTH = (r"(?:date[ ]+of[ ]+birth|birth[ ]*date|date[ ]+de[ ]+naissance|born(?:[ ]+on)?|dob|d\.o\.b\.?|ddn|nee?[ ]+le|naissance)")
_MONTHS = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|janvier|fevrier|mars|avril|mai|juin|"
           r"juillet|aout|septembre|octobre|novembre|decembre|janv|jan|feb|fev|mar|apr|avr|jun|juil|jul|aug|sept|sep|oct|nov|dec)\.?")
_DATE = (r"(?:\d{1,2}[/.\-]\d{1,2}[/.\-](?:\d{4}|\d{2})|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th|er)?[ ]+(?:of[ ]+|de[ ]+)?" + _MONTHS
         + r"[ ]+\d{4}|" + _MONTHS + r"[ ]+\d{1,2}(?:st|nd|rd|th)?,?[ ]+\d{4})")
_P4 = re.compile(_LEFT + _BIRTH + _RIGHT + r"[ \t:=\-, ]{0,5}(?P<val>" + _DATE + r")(?![0-9])", re.I)

_NOM = r"[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?"
_P5 = re.compile(
    r"(?<![A-Za-z0-9])(?i:patient|patiente|patients|mr|mrs|ms|miss|mister|mme|mlle|monsieur|madame|mademoiselle|m\.)(?![A-Za-z])[ \t]+"
    rf"(?P<n1>{_NOM}|[A-Z]{{2,}}(?:[-'][A-Z]{{2,}})?)(?:[ \t]+(?P<n2>{_NOM}))?")
_MOTS_COURANTS = frozenset("""
name names id ids identifier number record records data list lists search file files folder details detail summary banner portal view form
forms screen page pages chart flow journey care admission admissions discharge transfer transfers management manager module modules service
services status history information info profile context card cards safety consent experience allergy allergies diagnosis treatment
medication medications result results vital vitals appointment appointments registration registry merge identity identification matching
selection selector dashboard timeline document documents journal tracking monitoring queue pathway population persona example sample test
type types group count age gender sex birth contact address phone email bed room ward unit location wristband label barcode scan api ehr emr
pdf ui ux kpi mrn ssn dob ipp ne nee born le la du de des and or the a an
nom noms identifiant numero dossier dossiers donnees liste recherche fiche fiches resume bandeau portail vue formulaire ecran parcours soin
soins sortie transfert gestion statut historique informations profil contexte carte securite consentement allergie diagnostic traitement
medicament resultat rendez identite tableau chronologie suivi file attente exemple groupe sexe naissance adresse telephone courriel lit
chambre unite localisation bracelet etiquette code""".split())

# bornes alphanumériques : un identifiant hexadécimal ou un nom collé à des chiffres n'est pas un numéro de téléphone
_P7 = (re.compile(r"(?<![0-9A-Za-z+])\+\d{1,3}[ .\-]?(?:\(0\)[ .\-]?)?\d(?:[ .\-]?\d){7,11}(?![0-9A-Za-z])"),
       re.compile(r"(?<![0-9A-Za-z+])0[1-9](?:[ .\-]?\d{2}){4}(?![0-9A-Za-z])"),
       re.compile(r"(?<![0-9A-Za-z])\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?![0-9A-Za-z])"))
_P8 = re.compile(
    r"(?<![0-9])\d{1,3}(?:[ ]?(?:bis|ter))?,?[ ]+(?:rue|avenue|av\.?|boulevard|bd|bvd|chemin|impasse|allee|place|route|quai|cours|street|st\.?|"
    r"road|rd\.?|ave|lane|drive|way)(?![a-z])[^\n\x00]{0,60}?(?<![0-9])\d{5}(?![0-9])", re.I)
_CLINIQUE = re.compile(
    r"(?<![a-z])(?:diagnos(?:is|es|tic|tics)|conditions?|allerg(?:y|ies|ie|ic)|treatments?|traitements?|results?|resultats?|pathology|"
    r"pathologie|disease|maladie|medication|prescription)(?![a-z])", re.I)
_FIN_DE_PHRASE = re.compile(r"[.!?](?=\s|$)|\n")


def _fold(text: str) -> str:
    """Texte sans accent, de même longueur (un caractère pour un caractère) : les positions valent pour le texte d'origine."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in text)


def _etiquettes(extra_labels) -> tuple[str, ...]:
    return tuple(sorted({_fold(str(e)).casefold().strip() for e in (extra_labels or ()) if e and str(e).strip()}))


def labels_fingerprint(labels) -> str | None:
    """Empreinte de la liste facultative (sans ordre, sans accent ni casse) ; None quand elle est absente ou vide."""
    propres = _etiquettes(labels)
    return hashlib.sha256("\n".join(propres).encode("utf-8")).hexdigest() if propres else None


def _etiquette_en_motif(etiquette: str) -> str:
    return "[ ]+".join(re.escape(p) for p in etiquette.split())


@lru_cache(maxsize=32)
def _motif_etiquettes(prefixes: tuple[str, ...], extra: tuple[str, ...]) -> re.Pattern:
    labels = list(prefixes) + [_etiquette_en_motif(e) for e in extra]
    return re.compile(_LEFT + "(?:" + "|".join(labels) + ")" + _RIGHT + _SEP + _TOKEN, re.I)


def _cle_valide(m: re.Match) -> bool:
    cle = m.group(7)
    if cle is None:
        return True
    base = "".join(m.group(i) for i in range(1, 7)).upper().replace("2A", "19").replace("2B", "18")
    return int(cle) == 97 - int(base) % 97


def _chiffres(texte: str) -> int:
    return sum(c.isdigit() for c in texte)


def _detecter(text: str, extra_labels) -> tuple[list[tuple], list[int], str]:
    """(détections [(code, début, fin, début de la valeur, fin de la valeur)], fins de phrase, texte protégé). Les positions valent pour `text`."""
    plie = _fold(text)
    protege = EXISTING_MARKER.sub(lambda m: "\x00" * len(m.group(0)), plie)
    trouves: list[tuple] = []
    pris: list[tuple[int, int]] = []

    def libre(debut: int, fin: int) -> bool:
        return not any(debut < f and d < fin for d, f in pris)

    def ajouter(code, debut, fin, vdebut=None, vfin=None):
        trouves.append((code, debut, fin, debut if vdebut is None else vdebut, fin if vfin is None else vfin))
        pris.append((debut, fin))

    for m in _P1.finditer(protege):
        if _cle_valide(m) and libre(*m.span()):
            ajouter("P1", *m.span())
    for m in _P4.finditer(protege):
        if libre(*m.span()):
            ajouter("P4", *m.span(), *m.span("val"))
    extra = _etiquettes(extra_labels)
    for code, prefixes, avec_liste in (("P3", _P3_LABELS, False), ("P2", _P2_LABELS, True)):
        for m in _motif_etiquettes(prefixes, extra if avec_liste else ()).finditer(protege):
            if _chiffres(m.group("tok")) >= 4 and libre(*m.span()):
                ajouter(code, *m.span(), *m.span("tok"))
    for m in _P5.finditer(protege):
        n1, n2 = m.group("n1"), m.group("n2")
        if n1.casefold() in _MOTS_COURANTS:
            continue
        fin = m.end("n1")
        if n2 and n2.casefold() not in _MOTS_COURANTS:
            fin = m.end("n2")
        if libre(m.start(), fin):
            ajouter("P5", m.start(), fin, m.start("n1"), fin)
    for motif in _P7:
        for m in motif.finditer(protege):
            if libre(*m.span()):
                ajouter("P7", *m.span())
    for m in _P8.finditer(protege):
        if libre(*m.span()):
            ajouter("P8", *m.span())
    fins = [m.start() for m in _FIN_DE_PHRASE.finditer(protege)]
    return trouves, fins, protege


def count(text: str, extra_labels=()) -> dict[str, int]:
    """Nombre de détections par catégorie (toutes les catégories sont présentes, à 0 quand rien n'est trouvé). Aucune valeur, aucune position."""
    resultat = dict.fromkeys(CATEGORIES, 0)
    if not text:
        return resultat
    trouves, fins, protege = _detecter(str(text), extra_labels)
    phrase = lambda position: bisect.bisect_left(fins, position)          # noqa: E731
    par_phrase: dict[int, set[str]] = {}
    for code, debut, *_ in trouves:
        resultat[code] += 1
        par_phrase.setdefault(phrase(debut), set()).add(code)
    for codes in par_phrase.values():
        if {"P4", "P5"} <= codes:
            resultat["P6"] += 1
    identites = {"P1", "P2", "P3", "P5"}
    for numero in {phrase(m.start()) for m in _CLINIQUE.finditer(protege)}:
        codes = par_phrase.get(numero, set())
        if codes & identites or {"P4", "P5"} <= codes:
            resultat["P9"] += 1
    return resultat


def found_in(texts, extra_labels=()) -> dict[str, list[int]]:
    """{code: rang des textes où la catégorie compte au moins une détection} pour les textes d'un élément (titre, description, critères), chaque
    texte lu à part. Source unique du scan et du contrôle avant envoi : ni compte, ni valeur, ni position."""
    trouves: dict[str, list[int]] = {}
    for rang, texte in enumerate(texts):
        for code, n in count(texte, extra_labels).items():
            if n:
                trouves.setdefault(code, []).append(rang)
    return trouves


def retained(texts, extra_labels=()) -> bool:
    """Vrai quand un des textes de l'élément porte une détection de n'importe quelle catégorie, P5 compris : le contrôle avant envoi (D8)."""
    return bool(found_in(texts, extra_labels))


def mask(text: str, extra_labels=()) -> tuple[str, int]:
    """(texte, nombre de remplacements) : la valeur de chaque détection devient la marque de sa catégorie (P6 et P9 n'ont pas de marque propre)."""
    texte = str(text or "")
    trouves, _, _ = _detecter(texte, extra_labels)
    remplacements = sorted(((v, f, MARKERS[c]) for c, _, _, v, f in trouves if c in MARKERS), reverse=True)
    for debut, fin, marque in remplacements:
        texte = texte[:debut] + marque + texte[fin:]
    return texte, len(remplacements)
