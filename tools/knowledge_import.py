# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]", "numpy", "httpx", "pyyaml", "mcp>=1.2,<2"]
# ///
"""
PMZilla Lab : comparateur de parité entre library.sqlite (l'ancienne voie) et le schéma knowledge de PostgreSQL (R-37, design.md D6 et D7).

    uv run tools/knowledge_import.py verify [--vectors N] [--seed G]
    uv run tools/knowledge_import.py verify --parity --since AAAA-MM-JJ [--vectors N] [--seed G]
    uv run tools/knowledge_import.py status

Options communes : --sqlite CHEMIN (défaut : library.sqlite du dossier de données $PMZILLA_LAB_DATA, ~/.pmzilla-lab par défaut),
--dbname NOM (autre base de l'instance : bases jetables des tests).

`import` est retiré : l'indexeur (pmzilla_lab_library.py index) écrit directement dans la base. La commande, avec toutes ses anciennes
options, sort en code 1 sans se connecter à la base ni ouvrir SQLite. Le script garde son nom jusqu'au changement R-27, qui le supprime.

Le script n'écrit jamais dans la base : SQLite est ouvert en lecture seule (mode=ro), la base sous le rôle de lecture pmzilla_knowledge_ro,
en transaction en lecture seule. Il ne sonde plus l'index BM25 (c'est `pmzilla_lab_library.py probe`) : le code de sortie 3 a disparu.

`verify` recalcule des deux côtés les comptes (livres, passages, figures, collections par nom canonique, « veille » comptant comme « watch »),
compare par livre le titre, les métadonnées, les collections, le sha256, le modèle et les comptes, puis l'empreinte de contenu (sha256 de, par
passage dans l'ordre position puis identifiant : position, section, texte, kind, ref JSON trié et, hors parité, octets float16 du vecteur).
`--vectors N` relit en plus N vecteurs tirés au hasard des deux côtés et affiche seulement l'écart maximal, le cosinus minimal, les normes
extrêmes et le nombre de vecteurs nuls ou non finis.

`verify --parity --since AAAA-MM-JJ` (fenêtre de parité, D7) : l'empreinte est calculée sans les octets des vecteurs, les deux voies calculant
chacune leurs vecteurs ; pour chaque livre indexé à partir de la date de début des deux côtés, chaque vecteur de passage est comparé (cosinus
minimal, livres identiques à l'octet, vecteurs nuls ou non finis) ; un livre réindexé d'un seul côté (recalcul forcé) est compté et ses vecteurs
ne sont pas comparés. Verdict « identique » quand comptes, champs et empreintes sont égaux, que le cosinus minimal atteint TOLERANCE_COSINUS
et qu'aucun vecteur n'est nul ou non fini ; « écart » sinon (code 1), les livres en écart nommés par leur nom de fichier. Une ligne est ajoutée
à parite-sqlite.log dans le dossier de données (date, verdict, les quatre comptes de la base, livres réindexés des deux côtés, livres
identiques à l'octet, cosinus minimal : des nombres et des mots, jamais un nom de fichier) ; la sortie finit par « Parité SQLite : identique »
ou « Parité SQLite : écart » et « jours identiques consécutifs : n », compté depuis ce journal (un jour sans ligne ne compte pas et ne remet
pas à zéro ; une ligne « écart » remet à zéro).

La sortie ne contient que des comptes, des noms de fichiers et des verdicts : jamais un extrait de livre, jamais de mot de passe.

Codes de sortie : 0 réussi ; 1 écart, index SQLite introuvable ou import refusé ; 2 base injoignable (démarrer : bash tools/db_up.sh).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import watch_paths  # noqa: E402

DIMENSIONS = 1024
ROLE_LECTURE = "pmzilla_knowledge_ro"
KIND_VERS_POSTGRES = {"texte": "text", "figure": "figure", "text": "text"}
TOLERANCE_VECTEUR = 1e-6      # écart maximal admis entre deux vecteurs hors parité (ils doivent être identiques)
TOLERANCE_COSINUS = 0.9999    # parité : cosinus minimal admis entre les vecteurs d'un livre réindexé par les deux voies
JOURNAL_PARITE = "parite-sqlite.log"
MESSAGE_IMPORT_RETIRE = "import retiré : l'indexeur écrit directement dans la base (pmzilla_lab_library.py index)"


class ErreurImport(Exception):
    """Erreur de lecture, message sans texte de livre ni mot de passe."""


def dossier_donnees() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_DATA", "~/.pmzilla-lab")).expanduser()


# --- Valeurs communes aux deux côtés ------------------------------------------------------------------------------

def canonique_json(texte_ou_objet) -> str:
    """JSON canonique (clés triées, sans espace) d'un texte JSON ou d'un objet ; vide ou absent = objet vide."""
    objet = texte_ou_objet
    if isinstance(texte_ou_objet, (str, bytes)):
        objet = json.loads(texte_ou_objet or "{}")
    return json.dumps(objet if objet is not None else {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def nom_canonique(nom: str) -> str:
    return watch_paths.NEW["collection"] if nom == watch_paths.OLD["collection"] else nom


def collections_canoniques(noms) -> frozenset[str]:
    """Noms canoniques d'une liste « a|b » (SQLite) ou d'un itérable de noms (base)."""
    if isinstance(noms, str):
        noms = noms.split("|")
    return frozenset(nom_canonique(nom) for nom in (noms or ()) if nom)


def litteral_vers_blob(texte: str) -> bytes:
    """Sortie texte d'un halfvec -> octets float16."""
    valeurs = np.array([float(v) for v in texte.strip()[1:-1].split(",")], dtype=np.float32)
    return valeurs.astype(np.float16).tobytes()


def en_float32(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float16).astype(np.float32)


def empreinte(passages, *, vecteurs: bool = True) -> str:
    """Empreinte d'un livre : passages = (position, section, texte, kind, ref, octets float16), déjà dans l'ordre position puis identifiant.
    `vecteurs=False` (parité) : les octets des vecteurs n'entrent pas dans l'empreinte."""
    h = hashlib.sha256()
    for position, section, texte, kind, ref, vecteur in passages:
        h.update(json.dumps([position, section, texte, KIND_VERS_POSTGRES.get(kind, kind), canonique_json(ref)],
                            ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if vecteurs:
            h.update(len(vecteur).to_bytes(4, "big"))
            h.update(vecteur)
    return h.hexdigest()


@dataclass
class Livre:
    id: int
    file_name: str
    title: str
    sha256: str
    model: str
    indexed_at: float
    meta: str                       # JSON canonique
    collections: frozenset[str] = field(default_factory=frozenset)
    passages: int = 0
    figures: int = 0


# --- SQLite (lecture seule) ---------------------------------------------------------------------------------------

def ouvrir_sqlite(chemin: Path) -> sqlite3.Connection:
    if not Path(chemin).exists():
        raise ErreurImport(f"Index SQLite introuvable : {chemin}")
    return sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)


class CoteSqlite:
    """Lecture de library.sqlite (ancienne voie)."""

    def __init__(self, connexion: sqlite3.Connection):
        self.connexion = connexion

    def livres(self) -> dict[str, Livre]:
        colonnes = {ligne[1] for ligne in self.connexion.execute("PRAGMA table_info(books)")}
        meta = "meta" if "meta" in colonnes else "'{}'"
        comptes = {ligne[0]: (ligne[1], ligne[2]) for ligne in self.connexion.execute(
            "SELECT book_id, COUNT(*), COALESCE(SUM(kind = 'figure'), 0) FROM chunks GROUP BY book_id")}
        livres = {}
        for ligne in self.connexion.execute(
                f"SELECT id, file_name, title, sha256, model, indexed_at, {meta}, collections FROM books ORDER BY file_name"):
            passages, figures = comptes.get(ligne[0], (0, 0))
            livres[ligne[1]] = Livre(ligne[0], ligne[1], ligne[2], ligne[3], ligne[4], float(ligne[5]),
                                     canonique_json(ligne[6]), collections_canoniques(ligne[7]), passages, figures)
        return livres

    def passages(self, livre: Livre):
        colonnes = {ligne[1] for ligne in self.connexion.execute("PRAGMA table_info(chunks)")}
        kind = "kind" if "kind" in colonnes else "'texte'"
        ref = "ref" if "ref" in colonnes else "'{}'"
        for position, section, texte, blob, k, r in self.connexion.execute(
                f"SELECT position, section, text, embedding, {kind}, {ref} FROM chunks WHERE book_id = ? ORDER BY position, id",
                (livre.id,)):
            yield position, section, texte, KIND_VERS_POSTGRES.get(k, k), json.loads(r or "{}"), bytes(blob)

    def vecteur_au_rang(self, livre: Livre, rang: int) -> bytes | None:
        ligne = self.connexion.execute("SELECT embedding FROM chunks WHERE book_id = ? ORDER BY position, id LIMIT 1 OFFSET ?",
                                       (livre.id, rang)).fetchone()
        return None if ligne is None else bytes(ligne[0])

    def close(self):
        self.connexion.close()


# --- PostgreSQL (lecture seule, rôle de lecture) ------------------------------------------------------------------

def ouvrir_pg(dbname: str | None = None, *, fabrique=None):
    """Connexion du cluster (db.connect), passée en lecture seule sous le rôle pmzilla_knowledge_ro : rien ne peut être écrit."""
    connexion = (fabrique or (lambda nom: db.connect(dbname=nom)))(dbname)
    connexion.read_only = True
    connexion.execute(f"SET ROLE {ROLE_LECTURE}")
    connexion.commit()          # le SET ROLE vaut pour la session
    return connexion


class CotePg:
    """Lecture du schéma knowledge (nouvelle voie)."""

    def __init__(self, connexion):
        self.connexion = connexion

    def livres(self) -> dict[str, Livre]:
        livres = {}
        for ligne in self.connexion.execute(
                "SELECT b.id, b.file_name, b.title, b.sha256, b.model, extract(epoch FROM b.indexed_at)::float8, b.meta, "
                "(SELECT count(*) FROM knowledge.chunks c WHERE c.book_id = b.id), "
                "(SELECT count(*) FROM knowledge.chunks c WHERE c.book_id = b.id AND c.kind = 'figure') "
                "FROM knowledge.books b ORDER BY b.file_name"):
            livres[ligne[1]] = Livre(ligne[0], ligne[1], ligne[2], ligne[3], ligne[4], float(ligne[5]), canonique_json(ligne[6]),
                                     passages=int(ligne[7]), figures=int(ligne[8]))
        noms: dict[int, set[str]] = {}
        for livre_id, nom in self.connexion.execute(
                "SELECT bc.book_id, c.name FROM knowledge.book_collections bc JOIN knowledge.collections c ON c.id = bc.collection_id"):
            noms.setdefault(livre_id, set()).add(nom)
        for livre in livres.values():
            livre.collections = collections_canoniques(noms.get(livre.id, ()))
        return livres

    def passages(self, livre: Livre):
        for position, section, texte, kind, ref, vecteur in self.connexion.execute(
                "SELECT position, section, text, kind, ref, embedding::text FROM knowledge.chunks WHERE book_id = %s "
                "ORDER BY position, id", (livre.id,)):
            yield position, section, texte, kind, ref, litteral_vers_blob(vecteur)

    def vecteur_au_rang(self, livre: Livre, rang: int) -> bytes | None:
        ligne = self.connexion.execute("SELECT embedding::text FROM knowledge.chunks WHERE book_id = %s ORDER BY position, id "
                                       "LIMIT 1 OFFSET %s", (livre.id, rang)).fetchone()
        return None if ligne is None else litteral_vers_blob(ligne[0])

    def close(self):
        self.connexion.close()


# --- Comparaison --------------------------------------------------------------------------------------------------

def different(sq: Livre, pg: Livre) -> list[str]:
    """Champs qui diffèrent (aucun vecteur relu). La date d'indexation n'en fait pas partie : chaque voie indexe à son heure."""
    return [nom for nom in ("title", "sha256", "model", "meta", "collections", "passages", "figures") if getattr(sq, nom) != getattr(pg, nom)]


def comptes_collections(livres) -> dict[str, int]:
    comptes: dict[str, int] = {}
    for livre in livres.values():
        for nom in livre.collections:
            comptes[nom] = comptes.get(nom, 0) + 1
    return comptes


def totaux(livres) -> dict[str, int]:
    return {"livres": len(livres), "passages": sum(l.passages for l in livres.values()),
            "figures": sum(l.figures for l in livres.values()), "collections": len(comptes_collections(livres))}


def comparer_vecteurs(paires) -> dict:
    """Compare des couples (vecteur SQLite, vecteur base) en float32 : écart maximal, cosinus minimal (1 si les deux sont nuls, -1 si un
    seul l'est), normes extrêmes côté SQLite, vecteurs nuls ou non finis côté SQLite (`nuls`) et des deux côtés (`nuls_deux_cotes`)."""
    ecart, cosinus, normes, nuls, nuls_deux = 0.0, 1.0, [], 0, 0
    for a, b in paires:
        a, b = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
        ecart = max(ecart, float(np.max(np.abs(a - b))) if a.shape == b.shape else float("inf"))
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        normes.append(na)
        nul_a, nul_b = not np.isfinite(na) or na == 0.0, not np.isfinite(nb) or nb == 0.0
        nuls += nul_a
        nuls_deux += nul_a + nul_b
        if na > 0.0 and nb > 0.0:
            cosinus = min(cosinus, float(a @ b) / (na * nb))
        elif (na == 0.0) != (nb == 0.0):
            cosinus = -1.0
    return {"n": len(normes), "ecart_max": ecart, "cosinus_min": cosinus,
            "norme_min": min(normes) if normes else 0.0, "norme_max": max(normes) if normes else 0.0, "nuls": nuls,
            "nuls_deux_cotes": nuls_deux}


def echantillon_vecteurs(cote_sq, cote_pg, sq: dict, pg: dict, n: int, graine: int | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """N couples de vecteurs pris au hasard : un livre présent des deux côtés (pondéré par son nombre de passages), puis le k-ième passage
    dans l'ordre position puis identifiant, des deux côtés (comme l'empreinte)."""
    import random
    hasard = random.Random(graine)
    livres = [l for l in sq.values() if l.passages > 0 and l.file_name in pg]
    if not livres:
        return []
    paires = []
    for _ in range(n):
        livre = hasard.choices(livres, weights=[l.passages for l in livres])[0]
        rang = hasard.randrange(livre.passages)
        a, b = cote_sq.vecteur_au_rang(livre, rang), cote_pg.vecteur_au_rang(pg[livre.file_name], rang)
        if a is None or b is None:
            raise ErreurImport(f"vecteur introuvable d'un côté : {livre.file_name}, rang {rang}")
        paires.append((en_float32(a), en_float32(b)))
    return paires


def resume_vecteurs(m: dict) -> str:
    return (f"Vecteurs relus : {m['n']} · écart maximal {m['ecart_max']:.3g} · cosinus minimal {m['cosinus_min']:.9f} · "
            f"normes SQLite de {m['norme_min']:.4f} à {m['norme_max']:.4f} · vecteurs nuls ou non finis : {m['nuls']}")


@dataclass
class MesureParite:
    reindexes: int = 0              # livres indexés à partir de la date de début des deux côtés
    identiques_octet: int = 0
    unilateraux: int = 0            # indexés à partir de la date de début d'un seul côté : vecteurs non comparés
    cosinus_min: float | None = None
    nuls: int = 0


def debut_du_jour(jour: dt.date) -> float:
    return dt.datetime.combine(jour, dt.time.min).timestamp()


def mesurer_parite(cote_sq, cote_pg, sq: dict, pg: dict, depuis: dt.date) -> MesureParite:
    seuil = debut_du_jour(depuis)
    mesure = MesureParite()
    for nom in sorted(set(sq) & set(pg)):
        recent_sq, recent_pg = sq[nom].indexed_at >= seuil, pg[nom].indexed_at >= seuil
        if recent_sq != recent_pg:
            mesure.unilateraux += 1
            continue
        if not recent_sq:
            continue
        mesure.reindexes += 1
        a = [p[5] for p in cote_sq.passages(sq[nom])]
        b = [p[5] for p in cote_pg.passages(pg[nom])]
        if a == b:
            mesure.identiques_octet += 1
        if len(a) != len(b):        # passages en nombre différent : l'empreinte le signale déjà
            continue
        m = comparer_vecteurs([(en_float32(x), en_float32(y)) for x, y in zip(a, b)])
        if m["n"]:
            mesure.cosinus_min = m["cosinus_min"] if mesure.cosinus_min is None else min(mesure.cosinus_min, m["cosinus_min"])
        mesure.nuls += m["nuls_deux_cotes"]
    return mesure


# --- Journal de parité --------------------------------------------------------------------------------------------

def aujourdhui() -> dt.date:
    return dt.date.today()


def ligne_journal(jour: dt.date, verdict: str, comptes: dict, mesure: MesureParite) -> str:
    """Des nombres et des mots seulement : jamais un nom de fichier ni un texte de livre."""
    cosinus = "aucun" if mesure.cosinus_min is None else f"{mesure.cosinus_min:.9f}"
    return (f"{jour.isoformat()} {verdict} livres {comptes['livres']} passages {comptes['passages']} figures {comptes['figures']} "
            f"collections {comptes['collections']} réindexés {mesure.reindexes} identiques à l'octet {mesure.identiques_octet} "
            f"cosinus minimal {cosinus}")


def jours_identiques_consecutifs(lignes) -> int:
    """Jours distincts des dernières lignes « identique », en remontant jusqu'à la dernière ligne « écart » (exclue)."""
    jours: set[str] = set()
    for ligne in reversed([l for l in lignes if l.strip()]):
        morceaux = ligne.split()
        if len(morceaux) < 2:
            continue
        if morceaux[1] != "identique":
            break
        jours.add(morceaux[0])
    return len(jours)


def noter_parite(ligne: str) -> int:
    chemin = dossier_donnees() / JOURNAL_PARITE
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as journal:
        journal.write(ligne + "\n")
    return jours_identiques_consecutifs(chemin.read_text(encoding="utf-8").splitlines())


# --- verify et status ---------------------------------------------------------------------------------------------

def ouvrir_base_par_defaut(fabrique):
    return lambda dbname: CotePg(ouvrir_pg(dbname, fabrique=fabrique))


def chemin_sqlite(args) -> Path:
    return Path(args.sqlite) if args.sqlite else dossier_donnees() / "library.sqlite"


def commande_verify(args, ouvrir_base) -> int:
    parite = args.parity
    cote_sq = CoteSqlite(ouvrir_sqlite(chemin_sqlite(args)))
    try:
        sq = cote_sq.livres()
        cote_pg = ouvrir_base(args.dbname)
        try:
            pg = cote_pg.livres()
            problemes = []
            t_sq, t_pg = totaux(sq), totaux(pg)
            for nom in ("livres", "passages", "figures"):
                if t_sq[nom] != t_pg[nom]:
                    problemes.append(f"{nom} : SQLite {t_sq[nom]}, base {t_pg[nom]}")
            cs, cp = comptes_collections(sq), comptes_collections(pg)
            for nom in sorted(set(cs) | set(cp)):
                if cs.get(nom, 0) != cp.get(nom, 0):
                    problemes.append(f"collection {nom} : SQLite {cs.get(nom, 0)} livre(s), base {cp.get(nom, 0)}")
            for nom in sorted(set(sq) - set(pg)):
                problemes.append(f"absent de la base : {nom}")
            for nom in sorted(set(pg) - set(sq)):
                problemes.append(f"absent de SQLite : {nom}")
            for nom in sorted(set(sq) & set(pg)):
                ecarts = different(sq[nom], pg[nom])
                if ecarts:
                    problemes.append(f"{nom} : champs différents ({', '.join(ecarts)})")
                elif (empreinte(cote_sq.passages(sq[nom]), vecteurs=not parite)
                      != empreinte(cote_pg.passages(pg[nom]), vecteurs=not parite)):
                    problemes.append(f"{nom} : empreinte de contenu différente")
            mesure_parite = mesurer_parite(cote_sq, cote_pg, sq, pg, args.since) if parite else None
            mesure = None
            if args.vectors:
                mesure = comparer_vecteurs(echantillon_vecteurs(cote_sq, cote_pg, sq, pg, args.vectors, args.seed))
                if parite:
                    if mesure["n"] and mesure["cosinus_min"] < TOLERANCE_COSINUS:
                        problemes.append(f"vecteurs relus : cosinus minimal {mesure['cosinus_min']:.9f} sous la tolérance {TOLERANCE_COSINUS}")
                elif mesure["ecart_max"] > TOLERANCE_VECTEUR or mesure["cosinus_min"] < 1 - TOLERANCE_VECTEUR:
                    problemes.append(f"vecteurs : écart maximal {mesure['ecart_max']:.3g}, cosinus minimal {mesure['cosinus_min']:.9f}")
        finally:
            cote_pg.close()
    finally:
        cote_sq.close()

    if parite:
        if mesure_parite.cosinus_min is not None and mesure_parite.cosinus_min < TOLERANCE_COSINUS:
            problemes.append(f"vecteurs des livres réindexés des deux côtés : cosinus minimal {mesure_parite.cosinus_min:.9f} "
                             f"sous la tolérance {TOLERANCE_COSINUS}")
        if mesure_parite.nuls:
            problemes.append(f"vecteurs nuls ou non finis dans les livres réindexés des deux côtés : {mesure_parite.nuls}")
        return conclure_parite(args, problemes, t_pg, mesure_parite, mesure)

    if problemes:
        print(f"Vérification en échec : {len(problemes)} écart(s)")
        for ligne in problemes:
            print(f"  {ligne}")
        if mesure:
            print(resume_vecteurs(mesure))
        return 1
    print(f"Vérification réussie : {t_sq['livres']} livres, {t_sq['passages']} passages, {t_sq['figures']} figures, "
          f"{t_sq['collections']} collections, empreintes identiques.")
    if mesure:
        print(resume_vecteurs(mesure))
    return 0


def conclure_parite(args, problemes: list[str], comptes: dict, mesure_parite: MesureParite, mesure: dict | None) -> int:
    verdict = "écart" if problemes else "identique"
    if problemes:
        print(f"Comparaison en écart : {len(problemes)} écart(s)")
        for ligne in problemes:
            print(f"  {ligne}")
    cosinus = "aucun vecteur comparé" if mesure_parite.cosinus_min is None else f"{mesure_parite.cosinus_min:.9f}"
    print(f"Depuis le {args.since.isoformat()} : {mesure_parite.reindexes} livre(s) réindexé(s) des deux côtés, "
          f"{mesure_parite.identiques_octet} identique(s) à l'octet, cosinus minimal {cosinus} (tolérance {TOLERANCE_COSINUS}), "
          f"vecteurs nuls ou non finis : {mesure_parite.nuls} ; {mesure_parite.unilateraux} livre(s) réindexé(s) d'un seul côté "
          "(vecteurs non comparés).")
    if mesure:
        print(resume_vecteurs(mesure))
    consecutifs = noter_parite(ligne_journal(aujourdhui(), verdict, comptes, mesure_parite))
    print(f"Parité SQLite : {verdict}")
    print(f"jours identiques consécutifs : {consecutifs}")
    return 1 if problemes else 0


def commande_status(args, ouvrir_base) -> int:
    cote_pg = ouvrir_base(args.dbname)
    try:
        t = totaux(cote_pg.livres())
    finally:
        cote_pg.close()
    print(f"Base : {t['livres']} livres, {t['passages']} passages, {t['figures']} figures, {t['collections']} collections.")
    chemin = chemin_sqlite(args)
    if not chemin.exists():
        print(f"SQLite : index introuvable ({chemin}).")
        return 0
    cote_sq = CoteSqlite(ouvrir_sqlite(chemin))
    try:
        t = totaux(cote_sq.livres())
    finally:
        cote_sq.close()
    print(f"SQLite : {t['livres']} livres, {t['passages']} passages, {t['figures']} figures, {t['collections']} collections.")
    return 0


# --- Ligne de commande --------------------------------------------------------------------------------------------

def date_iso(texte: str) -> dt.date:
    try:
        return dt.date.fromisoformat(texte)
    except ValueError:
        raise argparse.ArgumentTypeError(f"date attendue au format AAAA-MM-JJ : {texte!r}")


def analyseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compare library.sqlite (ancienne voie) et le schéma knowledge de PostgreSQL, sans rien écrire.")
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument("--sqlite", default=None, help="index SQLite (défaut : library.sqlite du dossier de données)")
    commun.add_argument("--dbname", default=None, help="autre base de l'instance (tests)")
    sous = p.add_subparsers(dest="commande", required=True)
    importer = sous.add_parser("import", parents=[commun], help="retiré : l'indexeur écrit directement dans la base")
    for option in ("--dry-run", "--deep", "--keep-removed", "--allow-empty"):      # anciennes options, acceptées puis refusées avec la commande
        importer.add_argument(option, action="store_true", help=argparse.SUPPRESS)
    verifier = sous.add_parser("verify", parents=[commun], help="comparer comptes et empreintes des deux côtés")
    verifier.add_argument("--vectors", type=int, default=0, metavar="N", help="relire N vecteurs au hasard et afficher l'écart maximal et le cosinus minimal")
    verifier.add_argument("--seed", type=int, default=None, help="graine du tirage (reproductible)")
    verifier.add_argument("--parity", action="store_true", help="comparaison de la fenêtre de parité (empreinte sans vecteurs, cosinus, journal)")
    verifier.add_argument("--since", type=date_iso, default=None, metavar="AAAA-MM-JJ", help="date de début de la fenêtre de parité (avec --parity)")
    sous.add_parser("status", parents=[commun], help="comptes des deux côtés")
    return p


def main(argv: list[str] | None = None, fabrique=None, ouvrir_base=None) -> int:
    """`fabrique(dbname)` ouvre la connexion PostgreSQL (tests) ; par défaut db.connect (Trousseau puis variable d'environnement).
    `ouvrir_base(dbname)` rend directement le côté base (tests sans base) ; par défaut CotePg sur la connexion de `fabrique`."""
    parseur = analyseur()
    args = parseur.parse_args(argv)
    if args.commande == "import":
        print(MESSAGE_IMPORT_RETIRE)
        return 1
    if args.commande == "verify" and args.parity != (args.since is not None):
        parseur.error("--parity et --since vont ensemble")
    ouvrir_base = ouvrir_base or ouvrir_base_par_defaut(fabrique)
    commandes = {"verify": commande_verify, "status": commande_status}
    try:
        return commandes[args.commande](args, ouvrir_base)
    except db.ErreurBase as erreur:
        print(f"Base injoignable : {erreur}\nDémarrer la base : bash tools/db_up.sh", file=sys.stderr)
        return 2
    except ErreurImport as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
