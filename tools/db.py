# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]"]
# ///
"""
PMZilla Lab : couche d'accès unique à la base PostgreSQL et exécuteur de migrations (lot 1, docs/pmzilla/application.md, sections 4 et 7).

    uv run tools/db.py migrate [--dry-run]    applique les migrations en attente (ou les liste avec --dry-run)
    uv run tools/db.py status                 migrations appliquées et en attente
    uv run tools/db.py role-password ROLE     pose le mot de passe d'un rôle qui se connecte (saisie masquée) et le rend
                                              capable de se connecter ; seuls pmzilla_flow_views (lot 6),
                                              pmzilla_knowledge_ro (lot 4), pmzilla_cases_ro et pmzilla_cases (lot 2) sont acceptés

Connexion : l'adresse vient de PMZILLA_LAB_DB_URL (défaut postgresql://postgres@127.0.0.1:<PMZILLA_LAB_DB_PORT ou 5432>/pmzilla).
Elle ne contient jamais de mot de passe : une adresse qui en contient un est refusée, sans l'afficher. Le mot de passe est lu au
moment de la connexion, d'abord dans le Trousseau macOS (service pmzilla-lab-db, commande `security`, sortie capturée), à défaut
dans la variable PMZILLA_LAB_DB_PASSWORD. Il est passé à psycopg hors de l'adresse ; il n'est ni affiché, ni journalisé, ni écrit,
et les erreurs de connexion sont réécrites sans lui. PMZILLA_LAB_DB_SECURITY_BIN remplace la commande `security` (tests).

Rôle limité (lot 6) : connect(role="pmzilla_flow_views") se connecte sous ce rôle, dont le mot de passe est lu dans le Trousseau
(service pmzilla-lab-db-pmzilla_flow_views) ou dans PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS ; ce rôle ne lit que les vues
agrégées de flow. Même procédé pour pmzilla_knowledge_ro (lot 4, service pmzilla-lab-db-pmzilla_knowledge_ro) : lecture seule du
schéma knowledge, utilisé par la recherche de la bibliothèque. Même procédé pour les rôles des cas (lot 2) : pmzilla_cases_ro (service pmzilla-lab-db-pmzilla_cases_ro, variable
PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES_RO) lit le schéma cases ; pmzilla_cases (service pmzilla-lab-db-pmzilla_cases, variable
PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES) y lit et y écrit, sans DDL. Le mot de passe d'un rôle n'est jamais celui du superutilisateur.

Migrations : db/migrations/NNNN_description.sql (quatre chiffres, suite continue à partir de 0001), appliquées dans l'ordre, une
transaction par migration, suivies dans public.schema_migrations (numéro, nom, empreinte sha256, date). L'exécuteur s'arrête, sans
rien appliquer, si l'empreinte d'un fichier déjà appliqué a changé ou si un fichier appliqué a disparu. Un verrou consultatif
empêche deux exécuteurs simultanés. Chaque fichier indique en tête (commentaire) le schéma qu'il touche.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

try:
    import psycopg
    import psycopg.sql
except ImportError:  # les fonctions sans base (noms, empreintes, adresse) restent utilisables
    psycopg = None

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_MIGRATIONS = RACINE / "db" / "migrations"
SERVICE_TROUSSEAU = "pmzilla-lab-db"
VARIABLE_MOT_DE_PASSE = "PMZILLA_LAB_DB_PASSWORD"
VARIABLE_URL = "PMZILLA_LAB_DB_URL"
VARIABLE_SECURITY = "PMZILLA_LAB_DB_SECURITY_BIN"
CLE_VERROU = 7_262_024_001  # identifiant du verrou consultatif des migrations
MODELE_NOM = re.compile(r"^(\d{4})_([a-z0-9]+(?:_[a-z0-9]+)*)\.sql$")
DELAI_CONNEXION = 5
ROLES_AVEC_MOT_DE_PASSE = ("pmzilla_flow_views", "pmzilla_knowledge_ro", "pmzilla_cases_ro", "pmzilla_cases")    # rôles qui peuvent se connecter (vues de flow ; bibliothèque en lecture seule, lot 4 ; cas en lecture, puis en lecture-écriture, lot 2)


class ErreurBase(Exception):
    """Erreur d'accès ou de migration ; le message ne contient jamais le mot de passe."""


@dataclass(frozen=True)
class Migration:
    numero: int
    nom: str        # nom du fichier
    chemin: Path
    empreinte: str  # sha256 du contenu


def url_par_defaut() -> str:
    port = os.environ.get("PMZILLA_LAB_DB_PORT") or "5432"
    return f"postgresql://postgres@127.0.0.1:{port}/pmzilla"


def verifier_url(url: str) -> str:
    """Refuse une adresse qui porte un mot de passe (dans l'autorité ou en paramètre), sans l'afficher."""
    try:
        morceaux = urlsplit(url)
        parametres = [cle.lower() for cle, _ in parse_qsl(morceaux.query, keep_blank_values=True)]
        a_mot_de_passe = morceaux.password is not None or "password" in parametres or "passfile" in parametres
    except ValueError:
        raise ErreurBase("Adresse de connexion illisible (valeur non affichée).") from None
    if a_mot_de_passe:
        raise ErreurBase(f"{VARIABLE_URL} ne doit pas contenir de mot de passe : il est lu dans le Trousseau "
                         f"(service {SERVICE_TROUSSEAU}) ou dans {VARIABLE_MOT_DE_PASSE}. Retirez-le de l'adresse.")
    return url


def service_du_role(role: str | None) -> str:
    return f"{SERVICE_TROUSSEAU}-{role}" if role else SERVICE_TROUSSEAU


def variable_du_role(role: str | None) -> str:
    return f"{VARIABLE_MOT_DE_PASSE}_{role.upper()}" if role else VARIABLE_MOT_DE_PASSE


def mot_de_passe_trousseau(security: str | None = None, role: str | None = None) -> str | None:
    """Mot de passe du Trousseau macOS (stdout capturé), ou None s'il est absent ou si `security` est indisponible."""
    commande = security or os.environ.get(VARIABLE_SECURITY) or "security"
    try:
        fait = subprocess.run([commande, "find-generic-password", "-s", service_du_role(role), "-w"],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    valeur = fait.stdout.rstrip("\n")
    return valeur if fait.returncode == 0 and valeur else None


def lire_mot_de_passe(security: str | None = None, role: str | None = None) -> str | None:
    """Trousseau d'abord, puis la variable d'environnement ; None si aucun des deux."""
    return mot_de_passe_trousseau(security, role) or os.environ.get(variable_du_role(role)) or None


def _masquer(texte: str, secret: str | None) -> str:
    return texte.replace(secret, "***") if secret else texte


def connect(url: str | None = None, *, password: str | None = None, security: str | None = None, dbname: str | None = None,
            autocommit: bool = False, timeout: int = DELAI_CONNEXION, role: str | None = None):
    """Connexion psycopg. Le mot de passe est lu ici (argument, Trousseau, variable) et passé hors de l'adresse.

    `dbname` remplace la base de l'adresse (bases jetables des tests). `role` se connecte sous ce rôle de lecture limitée (son
    propre mot de passe, jamais celui du superutilisateur). Toute erreur est réécrite en ErreurBase sans le mot de passe.
    """
    if psycopg is None:
        raise ErreurBase("psycopg est absent : lancer avec uv run (dépendance psycopg[binary]).")
    adresse = verifier_url(url or os.environ.get(VARIABLE_URL) or url_par_defaut())
    if role is not None and role not in ROLES_AVEC_MOT_DE_PASSE:
        raise ErreurBase(f"Rôle non autorisé à se connecter par mot de passe : {role}.")
    secret = password if password is not None else lire_mot_de_passe(security, role)
    options = {"dbname": dbname} if dbname else {}
    if role:
        options["user"] = role
    try:
        return psycopg.connect(adresse, password=secret, connect_timeout=timeout, autocommit=autocommit, **options)
    except psycopg.Error as erreur:
        message = " ".join(_masquer(str(erreur), secret).split())
        indice = "" if secret else (f" Aucun mot de passe trouvé (Trousseau {service_du_role(role)}, "
                                    f"puis {variable_du_role(role)}).")
        raise ErreurBase(f"Connexion à la base impossible : {message}.{indice}") from None


def definir_mot_de_passe(conn, role: str, mot_de_passe: str, autorises: tuple[str, ...] = ROLES_AVEC_MOT_DE_PASSE) -> None:
    """Pose le mot de passe d'un rôle de lecture limitée et l'autorise à se connecter. Le mot de passe ne figure ni dans
    un fichier ni dans un message : la commande est composée côté client et n'est pas journalisée par ce script."""
    if role not in autorises:
        raise ErreurBase(f"Rôle non autorisé : {role} (acceptés : {', '.join(autorises)}).")
    if len(mot_de_passe) < 12:
        raise ErreurBase("Mot de passe trop court (12 caractères au moins).")
    conn.execute(psycopg.sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
        psycopg.sql.Identifier(role), psycopg.sql.Literal(mot_de_passe)))
    conn.commit()


# --- Migrations ---------------------------------------------------------------------------------------------------

def empreinte_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def lister_migrations(dossier: Path = DOSSIER_MIGRATIONS) -> list[Migration]:
    """Migrations du dossier, triées. Refuse un nom mal formé, un numéro en double ou un trou dans la suite."""
    if not dossier.is_dir():
        raise ErreurBase(f"Dossier de migrations introuvable : {dossier}")
    migrations: list[Migration] = []
    for chemin in sorted(dossier.iterdir()):
        if not chemin.is_file() or chemin.suffix != ".sql":
            continue
        trouve = MODELE_NOM.match(chemin.name)
        if not trouve:
            raise ErreurBase(f"Nom de migration mal formé : {chemin.name} (attendu NNNN_description.sql, quatre chiffres, "
                             "minuscules, chiffres et tirets bas).")
        migrations.append(Migration(int(trouve.group(1)), chemin.name, chemin, empreinte_fichier(chemin)))
    migrations.sort(key=lambda m: m.numero)
    for precedente, courante in zip(migrations, migrations[1:]):
        if courante.numero == precedente.numero:
            raise ErreurBase(f"Numéro de migration en double : {precedente.nom} et {courante.nom}.")
    for attendu, migration in enumerate(migrations, start=1):
        if migration.numero != attendu:
            raise ErreurBase(f"Trou dans la suite des migrations : {attendu:04d} manque avant {migration.nom}.")
    return migrations


@dataclass
class Etat:
    appliquees: list[Migration]
    en_attente: list[Migration]


def _appliquees_en_base(conn) -> dict[int, tuple[str, str]]:
    existe = conn.execute("SELECT to_regclass('public.schema_migrations') IS NOT NULL").fetchone()[0]
    if not existe:
        return {}
    lignes = conn.execute("SELECT numero, nom, empreinte FROM public.schema_migrations ORDER BY numero").fetchall()
    return {numero: (nom, empreinte) for numero, nom, empreinte in lignes}


def calculer_etat(conn, migrations: list[Migration]) -> Etat:
    """Compare les fichiers au suivi en base ; ErreurBase si un fichier appliqué a changé ou disparu."""
    en_base = _appliquees_en_base(conn)
    par_numero = {m.numero: m for m in migrations}
    for numero, (nom, empreinte) in sorted(en_base.items()):
        fichier = par_numero.get(numero)
        if fichier is None or fichier.nom != nom:
            raise ErreurBase(f"La migration {numero:04d} ({nom}) est appliquée mais son fichier manque ou a changé de nom. "
                             "Aucune migration n'a été appliquée.")
        if fichier.empreinte != empreinte:
            raise ErreurBase(f"Le fichier {nom} a été modifié depuis son application (empreinte différente). Une migration "
                             "appliquée ne se modifie jamais : écrire une nouvelle migration. Aucune migration n'a été appliquée.")
    return Etat([m for m in migrations if m.numero in en_base], [m for m in migrations if m.numero not in en_base])


def migrer(conn, migrations: list[Migration], *, dry_run: bool = False, sortie=None) -> Etat:
    """Applique les migrations en attente, une transaction chacune ; renvoie l'état d'avant. `conn` : connexion hors autocommit."""
    def dire(texte: str) -> None:
        if sortie is not None:
            print(texte, file=sortie)

    conn.commit()
    if not conn.execute("SELECT pg_try_advisory_lock(%s)", (CLE_VERROU,)).fetchone()[0]:
        conn.commit()
        raise ErreurBase("Un autre exécuteur de migrations est en cours sur cette base. Réessayer plus tard.")
    try:
        etat = calculer_etat(conn, migrations)
        conn.commit()
        if dry_run:
            for m in etat.en_attente:
                dire(f"En attente : {m.nom}")
            if not etat.en_attente:
                dire("Rien à appliquer.")
            return etat
        with conn.transaction():
            conn.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations ("
                         "numero integer PRIMARY KEY, nom text NOT NULL UNIQUE, empreinte text NOT NULL, "
                         "appliquee_le timestamptz NOT NULL DEFAULT now())")
        for m in etat.en_attente:
            try:
                with conn.transaction():
                    conn.execute(m.chemin.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO public.schema_migrations (numero, nom, empreinte) VALUES (%s, %s, %s)",
                                 (m.numero, m.nom, m.empreinte))
            except psycopg.Error as erreur:
                detail = " ".join(str(erreur).split())
                raise ErreurBase(f"La migration {m.nom} a échoué et a été annulée : {detail}") from None
            conn.commit()
            dire(f"Appliquée : {m.nom}")
        if not etat.en_attente:
            dire("Rien à appliquer.")
        return etat
    finally:
        conn.rollback()
        conn.execute("SELECT pg_advisory_unlock(%s)", (CLE_VERROU,))
        conn.commit()


# --- Ligne de commande --------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None, dossier: Path = DOSSIER_MIGRATIONS) -> int:
    analyseur = argparse.ArgumentParser(description="Accès à la base PMZilla Lab et migrations.")
    sous = analyseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("migrate", help="applique les migrations en attente").add_argument("--dry-run", action="store_true")
    sous.add_parser("status", help="migrations appliquées et en attente")
    sous.add_parser("role-password", help="pose le mot de passe d'un rôle de lecture limitée").add_argument(
        "role", choices=ROLES_AVEC_MOT_DE_PASSE)
    args = analyseur.parse_args(argv)
    try:
        if args.commande == "role-password":
            premier = getpass.getpass(f"Nouveau mot de passe de {args.role} : ")
            if premier != getpass.getpass("Encore une fois : "):
                raise ErreurBase("Les deux saisies diffèrent.")
            conn = connect()
            try:
                definir_mot_de_passe(conn, args.role, premier)
            finally:
                conn.close()
            print(f"Mot de passe posé. Rangez-le dans le Trousseau (saisie masquée) :\n"
                  f"  security add-generic-password -U -s {service_du_role(args.role)} -a \"$USER\" -w")
            return 0
        migrations = lister_migrations(dossier)
        conn = connect()
        try:
            if args.commande == "migrate":
                migrer(conn, migrations, dry_run=args.dry_run, sortie=sys.stdout)
            else:
                etat = calculer_etat(conn, migrations)
                for m in etat.appliquees:
                    print(f"Appliquée  : {m.nom}")
                for m in etat.en_attente:
                    print(f"En attente : {m.nom}")
                if not migrations:
                    print("Aucune migration.")
        finally:
            conn.close()
    except ErreurBase as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
