# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]", "numpy", "httpx", "pyyaml", "mcp>=1.2,<2"]
# ///
"""
PMZilla Lab : recopie de la bibliothèque (library.sqlite) dans le schéma knowledge de PostgreSQL (lot 4, application.md 5.1 et 9).

    uv run tools/knowledge_import.py import [--dry-run] [--deep] [--keep-removed] [--allow-empty]
    uv run tools/knowledge_import.py verify [--vectors N]
    uv run tools/knowledge_import.py status

Options communes : --sqlite CHEMIN (défaut : l'index de pmzilla_lab_library), --dbname NOM (autre base de l'instance : bases jetables des tests).

La copie est fidèle : ni reconversion des livres, ni recalcul des vecteurs (bge-m3), ni appel à Ollama. Le blob float16 de SQLite devient le
littéral halfvec exact ; `texte` devient `text` ; `ref` et `meta` (JSON) sont copiés tels quels en jsonb ; les collections prennent leur nom
canonique (« veille » devient « watch »). SQLite est ouvert en lecture seule (mode=ro). Les écritures se font sous le rôle pmzilla_knowledge.

Import incrémental, par livre, idempotent :
- un livre absent de la base est ajouté ; un livre dont le sha256, le modèle, le titre, les métadonnées, les collections, la date d'indexation
  ou les comptes (passages, figures) ont changé est remplacé en entier, dans UNE transaction (jamais de livre à moitié copié) ;
  --deep compare aussi l'empreinte de contenu (relit tous les vecteurs de la base : plus long, à lancer à la main) ;
- un livre retiré de SQLite est supprimé de la base (en cascade), sauf --keep-removed ; un index SQLite sans aucun livre face à une base
  qui en contient est refusé sans --allow-empty ;
- --dry-run n'écrit rien (connexion en lecture seule) et annonce « N à ajouter, M à remplacer, K à supprimer, P inchangés ».

`verify` recalcule des deux côtés les comptes (livres, passages, figures, collections par nom canonique) et l'empreinte de contenu de chaque livre
(sha256 de, par passage dans l'ordre position puis identifiant : position, section, texte, kind, ref JSON trié, octets float16 du vecteur).
`verify --vectors N` relit en plus N vecteurs tirés au hasard (livre et rang du passage) dans PostgreSQL, les compare à ceux de SQLite et affiche
seulement l'écart maximal, le cosinus minimal, les normes extrêmes et le nombre de vecteurs nuls.
La sortie ne contient que des comptes et des noms de fichiers : jamais un extrait de livre, jamais de mot de passe.

`verify` lance aussi une sonde de l'index BM25 (`chunks_bm25`), en lecture seule sous le rôle pmzilla_knowledge_ro : une requête plein texte sur un mot
courant, sans filtre puis filtrée par type de passage (figure). Une erreur de la sonde (par exemple InternalError « bitmap intersection stream …
claimed twice » d'un index abîmé) est nommée « index BM25 illisible » ; rien n'est réparé (REINDEX : installation.md, « Damaged BM25 index »).

Codes de sortie : 0 réussi ; 1 écart, index SQLite introuvable ou erreur de copie ; 2 base injoignable (démarrer : bash tools/db_up.sh) ;
3 index BM25 illisible (prime sur 1 : les écarts de copie éventuels sont affichés quand même).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402  (DB_PATH)

DIMENSIONS = 1024
ROLE_ECRITURE = "pmzilla_knowledge"
KIND_VERS_POSTGRES = {"texte": "text", "figure": "figure", "text": "text"}
TOLERANCE_VECTEUR = 1e-6      # écart maximal admis entre un vecteur SQLite et sa copie (ils doivent être identiques)
ROLE_LECTURE = "pmzilla_knowledge_ro"
CODE_BM25_ILLISIBLE = 3
MOT_SONDE = "the flux flow"   # des mots courants (OU de mots, comme la recherche) : la sonde doit lire l'index, pas chercher un cas rare
TOLERANCE_DATE = 1.0          # secondes : indexed_at SQLite (réel) contre timestamptz


class ErreurImport(Exception):
    """Erreur de copie ou de lecture, message sans texte de livre ni mot de passe."""


# --- Valeurs communes aux deux côtés ------------------------------------------------------------------------------

def canonique_json(texte_ou_objet) -> str:
    """JSON canonique (clés triées, sans espace) d'un texte JSON ou d'un objet ; vide ou absent = objet vide."""
    objet = texte_ou_objet
    if isinstance(texte_ou_objet, (str, bytes)):
        objet = json.loads(texte_ou_objet or "{}")
    return json.dumps(objet if objet is not None else {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def collections_canoniques(texte: str) -> frozenset[str]:
    return frozenset(nom for nom in (texte or "").split("|") if nom)


def blob_vers_litteral(blob: bytes) -> str:
    """Blob float16 de SQLite -> littéral halfvec exact. 9 chiffres significatifs suffisent à ramener le float32 (donc le float16) à l'identique."""
    if len(blob) != DIMENSIONS * 2:
        raise ErreurImport(f"vecteur de {len(blob) // 2} dimensions au lieu de {DIMENSIONS}")
    valeurs = np.frombuffer(blob, dtype=np.float16).astype(np.float32)
    return "[" + ",".join("%.9g" % float(v) for v in valeurs) + "]"


def litteral_vers_blob(texte: str) -> bytes:
    """Sortie texte d'un halfvec -> octets float16 (le chemin inverse, utilisé par l'empreinte côté PostgreSQL)."""
    valeurs = np.array([float(v) for v in texte.strip()[1:-1].split(",")], dtype=np.float32)
    return valeurs.astype(np.float16).tobytes()


def empreinte(passages) -> str:
    """Empreinte d'un livre : passages = (position, section, texte, kind, ref, octets float16), déjà dans l'ordre position puis identifiant."""
    h = hashlib.sha256()
    for position, section, texte, kind, ref, vecteur in passages:
        h.update(json.dumps([position, section, texte, KIND_VERS_POSTGRES.get(kind, kind), canonique_json(ref)],
                            ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        h.update(len(vecteur).to_bytes(4, "big"))
        h.update(vecteur)
    return h.hexdigest()


# --- SQLite (lecture seule) ---------------------------------------------------------------------------------------

@dataclass
class LivreSqlite:
    id: int
    file_name: str
    title: str
    sha256: str
    model: str
    indexed_at: float
    meta: str                       # JSON canonique
    collections: frozenset[str]
    passages: int = 0
    figures: int = 0


def ouvrir_sqlite(chemin: Path) -> sqlite3.Connection:
    if not Path(chemin).exists():
        raise ErreurImport(f"Index SQLite introuvable : {chemin}")
    return sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)


def livres_sqlite(connexion: sqlite3.Connection) -> dict[str, LivreSqlite]:
    colonnes = {ligne[1] for ligne in connexion.execute("PRAGMA table_info(books)")}
    meta = "meta" if "meta" in colonnes else "'{}'"
    comptes = {ligne[0]: (ligne[1], ligne[2]) for ligne in connexion.execute(
        "SELECT book_id, COUNT(*), COALESCE(SUM(kind = 'figure'), 0) FROM chunks GROUP BY book_id")}
    livres = {}
    for ligne in connexion.execute(
            f"SELECT id, file_name, title, sha256, model, indexed_at, {meta}, collections FROM books ORDER BY file_name"):
        passages, figures = comptes.get(ligne[0], (0, 0))
        livres[ligne[1]] = LivreSqlite(ligne[0], ligne[1], ligne[2], ligne[3], ligne[4], float(ligne[5]),
                                       canonique_json(ligne[6]), collections_canoniques(ligne[7]), passages, figures)
    return livres


def passages_sqlite(connexion: sqlite3.Connection, livre_id: int, par_identifiant: bool = False):
    """Passages d'un livre : par position (empreinte, comparable des deux côtés) ou, pour la copie, par identifiant SQLite, afin que
    l'ordre des identifiants PostgreSQL reproduise celui de SQLite (les égalités de classement se départagent par id)."""
    colonnes = {ligne[1] for ligne in connexion.execute("PRAGMA table_info(chunks)")}
    kind = "kind" if "kind" in colonnes else "'texte'"
    ref = "ref" if "ref" in colonnes else "'{}'"
    for position, section, texte, blob, k, r in connexion.execute(
            f"SELECT position, section, text, embedding, {kind}, {ref} FROM chunks WHERE book_id = ? "
            f"ORDER BY {'id' if par_identifiant else 'position, id'}",
            (livre_id,)):
        yield position, section, texte, KIND_VERS_POSTGRES.get(k, k), json.loads(r or "{}"), bytes(blob)


def empreinte_sqlite(connexion: sqlite3.Connection, livre: LivreSqlite) -> str:
    return empreinte(passages_sqlite(connexion, livre.id))


# --- PostgreSQL ---------------------------------------------------------------------------------------------------

@dataclass
class LivrePg:
    id: int
    file_name: str
    title: str
    sha256: str
    model: str
    indexed_at: float
    meta: str
    collections: frozenset[str] = field(default_factory=frozenset)
    passages: int = 0
    figures: int = 0


def livres_pg(connexion) -> dict[str, LivrePg]:
    livres = {}
    for ligne in connexion.execute(
            "SELECT b.id, b.file_name, b.title, b.sha256, b.model, extract(epoch FROM b.indexed_at)::float8, b.meta, "
            "(SELECT count(*) FROM knowledge.chunks c WHERE c.book_id = b.id), "
            "(SELECT count(*) FROM knowledge.chunks c WHERE c.book_id = b.id AND c.kind = 'figure') "
            "FROM knowledge.books b ORDER BY b.file_name"):
        livres[ligne[1]] = LivrePg(ligne[0], ligne[1], ligne[2], ligne[3], ligne[4], float(ligne[5]), canonique_json(ligne[6]),
                                   passages=int(ligne[7]), figures=int(ligne[8]))
    noms: dict[int, set[str]] = {}
    for livre_id, nom in connexion.execute(
            "SELECT bc.book_id, c.name FROM knowledge.book_collections bc JOIN knowledge.collections c ON c.id = bc.collection_id"):
        noms.setdefault(livre_id, set()).add(nom)
    for livre in livres.values():
        livre.collections = frozenset(noms.get(livre.id, set()))
    return livres


def passages_pg(connexion, livre_id: int):
    for position, section, texte, kind, ref, vecteur in connexion.execute(
            "SELECT position, section, text, kind, ref, embedding::text FROM knowledge.chunks WHERE book_id = %s "
            "ORDER BY position, id", (livre_id,)):
        yield position, section, texte, kind, ref, litteral_vers_blob(vecteur)


def empreinte_pg(connexion, livre: LivrePg) -> str:
    return empreinte(passages_pg(connexion, livre.id))


def ouvrir_pg(dbname: str | None = None, *, lecture_seule: bool = False, fabrique=None):
    """Connexion superutilisateur du cluster (db.connect) ; les écritures passent ensuite sous pmzilla_knowledge."""
    connexion = (fabrique or (lambda nom: db.connect(dbname=nom)))(dbname)
    if lecture_seule:
        connexion.read_only = True
    else:
        connexion.execute(f"SET ROLE {ROLE_ECRITURE}")
        connexion.commit()
    return connexion


# --- Plan et copie ------------------------------------------------------------------------------------------------

def different(sq: LivreSqlite, pg: LivrePg) -> list[str]:
    """Champs qui diffèrent (peu coûteux : aucun vecteur relu)."""
    ecarts = []
    for nom in ("title", "sha256", "model", "meta", "collections", "passages", "figures"):
        if getattr(sq, nom) != getattr(pg, nom):
            ecarts.append(nom)
    if abs(sq.indexed_at - pg.indexed_at) > TOLERANCE_DATE:
        ecarts.append("indexed_at")
    return ecarts


@dataclass
class Plan:
    ajouter: list[str] = field(default_factory=list)
    remplacer: list[str] = field(default_factory=list)
    supprimer: list[str] = field(default_factory=list)
    inchanges: list[str] = field(default_factory=list)

    def resume(self) -> str:
        return (f"{len(self.ajouter)} à ajouter, {len(self.remplacer)} à remplacer, {len(self.supprimer)} à supprimer, "
                f"{len(self.inchanges)} inchangés")


def etablir_plan(sqlite_conn, pg_conn, sq: dict[str, LivreSqlite], pg: dict[str, LivrePg], *, deep: bool, garder_retires: bool) -> Plan:
    plan = Plan()
    for nom, livre in sq.items():
        existant = pg.get(nom)
        if existant is None:
            plan.ajouter.append(nom)
        elif different(livre, existant) or (deep and empreinte_sqlite(sqlite_conn, livre) != empreinte_pg(pg_conn, existant)):
            plan.remplacer.append(nom)
        else:
            plan.inchanges.append(nom)
    if not garder_retires:
        plan.supprimer = sorted(set(pg) - set(sq))
    return plan


def copier_livre(sqlite_conn, pg_conn, livre: LivreSqlite) -> None:
    """Remplace (ou ajoute) un livre en entier dans la transaction ouverte ; l'appelant valide ou annule."""
    pg_conn.execute("DELETE FROM knowledge.books WHERE file_name = %s", (livre.file_name,))
    livre_id = pg_conn.execute(
        "INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) "
        "VALUES (%s, %s, %s::jsonb, %s, %s, to_timestamp(%s)) RETURNING id",
        (livre.file_name, livre.title, livre.meta, livre.sha256, livre.model, livre.indexed_at)).fetchone()[0]
    for nom in sorted(livre.collections):
        collection_id = pg_conn.execute(
            "INSERT INTO knowledge.collections (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (nom,)).fetchone()[0]
        pg_conn.execute("INSERT INTO knowledge.book_collections (book_id, collection_id) VALUES (%s, %s)", (livre_id, collection_id))
    lignes = [(livre_id, position, section, texte, blob_vers_litteral(vecteur), kind, canonique_json(ref))
              for position, section, texte, kind, ref, vecteur in passages_sqlite(sqlite_conn, livre.id, par_identifiant=True)]
    with pg_conn.cursor() as curseur:
        curseur.executemany(
            "INSERT INTO knowledge.chunks (book_id, position, section, text, embedding, kind, ref) "
            "VALUES (%s, %s, %s, %s, %s::halfvec, %s, %s::jsonb)", lignes)


def supprimer_livre(pg_conn, nom: str) -> None:
    pg_conn.execute("DELETE FROM knowledge.books WHERE file_name = %s", (nom,))


def nettoyer_collections(pg_conn) -> None:
    pg_conn.execute("DELETE FROM knowledge.collections c WHERE NOT EXISTS "
                    "(SELECT 1 FROM knowledge.book_collections bc WHERE bc.collection_id = c.id)")


def commande_import(args, fabrique) -> int:
    sqlite_conn = ouvrir_sqlite(Path(args.sqlite))
    try:
        sq = livres_sqlite(sqlite_conn)
        pg_conn = ouvrir_pg(args.dbname, lecture_seule=args.dry_run, fabrique=fabrique)
        try:
            pg = livres_pg(pg_conn)
            if not sq and pg and not args.allow_empty:
                print(f"Refus : l'index SQLite ne contient aucun livre et la base en contient {len(pg)} "
                      "(--allow-empty pour tout supprimer quand même).")
                return 1
            plan = etablir_plan(sqlite_conn, pg_conn, sq, pg, deep=args.deep, garder_retires=args.keep_removed)
            print(f"{'À faire' if args.dry_run else 'Plan'} : {plan.resume()}")
            if args.dry_run:
                for nom in plan.ajouter:
                    print(f"  ajouter   : {nom}")
                for nom in plan.remplacer:
                    print(f"  remplacer : {nom}")
                for nom in plan.supprimer:
                    print(f"  supprimer : {nom}")
                print("Rien n'a été écrit (--dry-run).")
                return 0
            # dans l'ordre des identifiants de livres SQLite : l'ordre des identifiants PostgreSQL reproduit celui de SQLite
            a_copier = sorted([(sq[nom].id, "ajouté", nom) for nom in plan.ajouter] + [(sq[nom].id, "remplacé", nom) for nom in plan.remplacer])
            for _, etiquette, nom in a_copier:
                try:
                    copier_livre(sqlite_conn, pg_conn, sq[nom])
                    pg_conn.commit()
                except Exception as erreur:      # un livre à la fois : rien de partiel, le suivant n'est pas tenté
                    pg_conn.rollback()
                    print(f"Échec de la copie de {nom} : {type(erreur).__name__}. Rien n'a été écrit pour ce livre ; "
                          "relancer l'import après correction.")
                    return 1
                print(f"{etiquette} : {nom} ({sq[nom].passages} passages)")
            for nom in plan.supprimer:
                supprimer_livre(pg_conn, nom)
                pg_conn.commit()
                print(f"supprimé : {nom}")
            nettoyer_collections(pg_conn)
            pg_conn.commit()
            print(f"Import terminé : {plan.resume()}.")
            return 0
        finally:
            pg_conn.close()
    finally:
        sqlite_conn.close()


# --- verify et status ---------------------------------------------------------------------------------------------

def comptes_collections(livres) -> dict[str, int]:
    comptes: dict[str, int] = {}
    for livre in livres.values():
        for nom in livre.collections:
            comptes[nom] = comptes.get(nom, 0) + 1
    return comptes


def comparer_vecteurs(paires) -> dict:
    """Compare des couples (vecteur SQLite, vecteur PostgreSQL) en float32 : écart maximal, cosinus minimal (1 si les deux sont nuls),
    normes extrêmes côté SQLite et nombre de vecteurs nuls ou non finis côté SQLite. Aucun texte, que des nombres."""
    ecart, cosinus, normes, nuls = 0.0, 1.0, [], 0
    for a, b in paires:
        a, b = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
        ecart = max(ecart, float(np.max(np.abs(a - b))) if a.shape == b.shape else float("inf"))
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        normes.append(na)
        if not np.isfinite(na) or na == 0.0:
            nuls += 1
        if na > 0.0 and nb > 0.0:
            cosinus = min(cosinus, float(a @ b) / (na * nb))
        elif (na == 0.0) != (nb == 0.0):
            cosinus = -1.0
    return {"n": len(normes), "ecart_max": ecart, "cosinus_min": cosinus,
            "norme_min": min(normes) if normes else 0.0, "norme_max": max(normes) if normes else 0.0, "nuls": nuls}


def echantillon_vecteurs(sqlite_conn, pg_conn, sq: dict, n: int, graine: int | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """N couples de vecteurs pris au hasard : un livre au hasard (pondéré par son nombre de passages), puis le k-ième passage dans l'ordre
    position puis identifiant, des deux côtés (comme l'empreinte)."""
    import random
    hasard = random.Random(graine)
    livres = [l for l in sq.values() if l.passages > 0]
    if not livres:
        return []
    paires = []
    for _ in range(n):
        livre = hasard.choices(livres, weights=[l.passages for l in livres])[0]
        rang = hasard.randrange(livre.passages)
        ligne = sqlite_conn.execute("SELECT embedding FROM chunks WHERE book_id = ? ORDER BY position, id LIMIT 1 OFFSET ?",
                                    (livre.id, rang)).fetchone()
        autre = pg_conn.execute(
            "SELECT c.embedding::text FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id WHERE b.file_name = %s "
            "ORDER BY c.position, c.id LIMIT 1 OFFSET %s", (livre.file_name, rang)).fetchone()
        if ligne is None or autre is None:
            raise ErreurImport(f"vecteur introuvable d'un côté : {livre.file_name}, rang {rang}")
        paires.append((np.frombuffer(bytes(ligne[0]), dtype=np.float16).astype(np.float32),
                       np.frombuffer(litteral_vers_blob(autre[0]), dtype=np.float16).astype(np.float32)))
    return paires


def resume_vecteurs(m: dict) -> str:
    return (f"Vecteurs relus : {m['n']} · écart maximal {m['ecart_max']:.3g} · cosinus minimal {m['cosinus_min']:.9f} · "
            f"normes SQLite de {m['norme_min']:.4f} à {m['norme_max']:.4f} · vecteurs nuls ou non finis : {m['nuls']}")


def sonde_bm25(pg_conn) -> str | None:
    """Lit l'index BM25 comme le fait la recherche (sans filtre, puis filtré par type de passage), sous le rôle de lecture. None si les deux
    requêtes réussissent ; sinon « variante : type de l'erreur (première ligne) ». Aucun texte de livre : l'erreur d'un index parle d'un segment."""
    variantes = (("sans filtre", ""), ("type figure", " AND c.kind = ANY(%s::text[])"))
    try:
        for nom, filtre in variantes:
            parametres = (MOT_SONDE,) + ((["figure"],) if filtre else ())
            try:
                pg_conn.execute(f"SET ROLE {ROLE_LECTURE}")
                pg_conn.execute("SELECT c.id FROM knowledge.chunks c WHERE c.fts_text ||| %s" + filtre +
                                " ORDER BY pdb.score(c.id) DESC LIMIT 50", parametres).fetchall()
            except Exception as erreur:      # InternalError d'un index abîmé, mais aussi toute autre erreur de la sonde
                ligne = (str(erreur).strip().splitlines() or [""])[0][:200]
                return f"{nom} : {type(erreur).__name__} ({ligne})"
            finally:
                pg_conn.rollback()           # défait SET ROLE et ferme la transaction, aussi après une erreur
    except Exception as erreur:              # rollback impossible : la sonde ne peut pas conclure
        return f"sonde impossible : {type(erreur).__name__}"
    return None


def commande_verify(args, fabrique) -> int:
    sqlite_conn = ouvrir_sqlite(Path(args.sqlite))
    try:
        sq = livres_sqlite(sqlite_conn)
        pg_conn = ouvrir_pg(args.dbname, lecture_seule=True, fabrique=fabrique)
        try:
            pg = livres_pg(pg_conn)
            problemes = []
            totaux = {"livres": (len(sq), len(pg)),
                      "passages": (sum(l.passages for l in sq.values()), sum(l.passages for l in pg.values())),
                      "figures": (sum(l.figures for l in sq.values()), sum(l.figures for l in pg.values()))}
            for nom, (a, b) in totaux.items():
                if a != b:
                    problemes.append(f"{nom} : SQLite {a}, base {b}")
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
                elif empreinte_sqlite(sqlite_conn, sq[nom]) != empreinte_pg(pg_conn, pg[nom]):
                    problemes.append(f"{nom} : empreinte de contenu différente")
            mesure = None
            if getattr(args, "vectors", 0):
                mesure = comparer_vecteurs(echantillon_vecteurs(sqlite_conn, pg_conn, sq, args.vectors, getattr(args, "seed", None)))
                if mesure["ecart_max"] > TOLERANCE_VECTEUR or mesure["cosinus_min"] < 1 - TOLERANCE_VECTEUR:
                    problemes.append(f"vecteurs : écart maximal {mesure['ecart_max']:.3g}, cosinus minimal {mesure['cosinus_min']:.9f}")
            bm25 = sonde_bm25(pg_conn)
        finally:
            pg_conn.close()
    finally:
        sqlite_conn.close()
    if bm25:
        print(f"Vérification en échec : index BM25 illisible ({bm25})")
        print("  Reconstruction par l'utilisateur seul, en superutilisateur : installation.md, « Damaged BM25 index ».")
    if problemes:
        print(f"Vérification en échec : {len(problemes)} écart(s)")
        for ligne in problemes:
            print(f"  {ligne}")
        if mesure:
            print(resume_vecteurs(mesure))
        return CODE_BM25_ILLISIBLE if bm25 else 1
    if bm25:
        return CODE_BM25_ILLISIBLE
    print(f"Vérification réussie : {totaux['livres'][0]} livres, {totaux['passages'][0]} passages, {totaux['figures'][0]} figures, "
          f"{len(cs)} collections, empreintes identiques, index BM25 lisible.")
    if mesure:
        print(resume_vecteurs(mesure))
    return 0


def commande_status(args, fabrique) -> int:
    pg_conn = ouvrir_pg(args.dbname, lecture_seule=True, fabrique=fabrique)
    try:
        pg = livres_pg(pg_conn)
    finally:
        pg_conn.close()
    print(f"Base : {len(pg)} livres, {sum(l.passages for l in pg.values())} passages, {sum(l.figures for l in pg.values())} figures, "
          f"{len(comptes_collections(pg))} collections.")
    chemin = Path(args.sqlite)
    if not chemin.exists():
        print(f"SQLite : index introuvable ({chemin}).")
        return 0
    sqlite_conn = ouvrir_sqlite(chemin)
    try:
        sq = livres_sqlite(sqlite_conn)
    finally:
        sqlite_conn.close()
    print(f"SQLite : {len(sq)} livres, {sum(l.passages for l in sq.values())} passages, {sum(l.figures for l in sq.values())} figures, "
          f"{len(comptes_collections(sq))} collections.")
    return 0


# --- Ligne de commande --------------------------------------------------------------------------------------------

def analyseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Recopie la bibliothèque SQLite dans le schéma knowledge de PostgreSQL.")
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument("--sqlite", default=str(library.DB_PATH), help="index SQLite (défaut : celui de pmzilla_lab_library)")
    commun.add_argument("--dbname", default=None, help="autre base de l'instance (tests)")
    sous = p.add_subparsers(dest="commande", required=True)
    importer = sous.add_parser("import", parents=[commun], help="copier ou mettre à jour la base")
    importer.add_argument("--dry-run", action="store_true", help="annoncer le plan sans rien écrire")
    importer.add_argument("--deep", action="store_true", help="comparer aussi l'empreinte de contenu des livres identiques")
    importer.add_argument("--keep-removed", action="store_true", help="ne pas supprimer les livres retirés de SQLite")
    importer.add_argument("--allow-empty", action="store_true", help="accepter un index SQLite vide face à une base remplie")
    verifier = sous.add_parser("verify", parents=[commun], help="comparer comptes et empreintes des deux côtés")
    verifier.add_argument("--vectors", type=int, default=0, metavar="N", help="relire N vecteurs au hasard et afficher l'écart maximal et le cosinus minimal")
    verifier.add_argument("--seed", type=int, default=None, help="graine du tirage (reproductible)")
    sous.add_parser("status", parents=[commun], help="comptes des deux côtés")
    return p


def main(argv: list[str] | None = None, fabrique=None) -> int:
    """`fabrique(dbname)` ouvre la connexion (tests) ; par défaut db.connect (Trousseau puis variable d'environnement)."""
    args = analyseur().parse_args(argv)
    commandes = {"import": commande_import, "verify": commande_verify, "status": commande_status}
    try:
        return commandes[args.commande](args, fabrique)
    except db.ErreurBase as erreur:
        print(f"Base injoignable : {erreur}\nDémarrer la base : bash tools/db_up.sh", file=sys.stderr)
        return 2
    except ErreurImport as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
