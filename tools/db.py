# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]"]
# ///
"""
PMZilla Lab : couche d'accès unique à la base PostgreSQL et exécuteur de migrations (lot 1, docs/pmzilla/application.md, sections 4 et 7).

    uv run tools/db.py migrate [--dry-run]    applique les migrations en attente (ou les liste avec --dry-run)
    uv run tools/db.py role-password ROLE     génère le mot de passe d'un rôle qui se connecte (rien à saisir), le pose (empreinte
                                              SCRAM-SHA-256 calculée côté client), le range dans le Trousseau, relit l'entrée et la
                                              compare avant de valider, puis ouvre une session d'essai sous le rôle ; seuls
                                              pmzilla_flow_views (lot 6),
                                              pmzilla_knowledge_ro (lot 4), pmzilla_cases_ro et pmzilla_cases (lot 2) et
                                              pmzilla_flow (rôle d'import de flow, export Jira) et
                                              pmzilla_quality_views (change story-quality-audit) sont acceptés
    uv run tools/db.py status                 migrations, rôles qui se connectent et version de pg_search, sans rien modifier
                                              (détail : état de chaque rôle de la liste par une session d'essai, rôles hors
                                              liste qui pourraient se connecter, version de pg_search comparée à celle de
                                              l'image de docker-compose.yml ; code 0 sans problème, 3 s'il y en a, 1 si la
                                              commande ne peut pas tourner)

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
PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES) y lit et y écrit, sans DDL. Même procédé pour le rôle d'import de flow pmzilla_flow
(service pmzilla-lab-db-pmzilla_flow, variable PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW) : lecture et écriture dans le schéma flow
seulement, aucun droit ailleurs ; l'export Jira s'y connecte pour écrire la couche brute. Même procédé pour pmzilla_quality_views
(change story-quality-audit, service pmzilla-lab-db-pmzilla_quality_views) : il ne lit que les trois vues agrégées du schéma quality ;
les rôles de lecture-écriture et de lecture seule de ce schéma (pmzilla_quality, pmzilla_quality_ro) ne reçoivent jamais de mot de
passe. Le mot de passe d'un rôle n'est jamais celui du superutilisateur.

Migrations : db/migrations/NNNN_description.sql (quatre chiffres, suite continue à partir de 0001), appliquées dans l'ordre, une
transaction par migration, suivies dans public.schema_migrations (numéro, nom, empreinte sha256, date). L'exécuteur s'arrête, sans
rien appliquer, si l'empreinte d'un fichier déjà appliqué a changé ou si un fichier appliqué a disparu. Un verrou consultatif
empêche deux exécuteurs simultanés. Chaque fichier indique en tête (commentaire) le schéma qu'il touche.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import os
import re
import secrets
import string
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
DELAI_ESSAI = 3            # session d'essai sous un rôle (status)
FICHIER_COMPOSE = RACINE / "docker-compose.yml"
ALPHABET_MOT_DE_PASSE = string.ascii_letters + string.digits + "-_"    # aucun caractère à protéger ; les deux derniers ne commencent jamais le mot de passe
LONGUEUR_MOT_DE_PASSE = 40
ROLES_AVEC_MOT_DE_PASSE = ("pmzilla_flow_views", "pmzilla_knowledge_ro", "pmzilla_cases_ro", "pmzilla_cases",
                           "pmzilla_flow", "pmzilla_quality_views")    # rôles qui peuvent se connecter (vues de flow ; bibliothèque en lecture seule, lot 4 ; cas en lecture, puis en lecture-écriture, lot 2 ; rôle d'import de flow, jira-data-architecture D13 ; vues qualité, story-quality-audit)
ROLES_SANS_MOT_DE_PASSE = ("pmzilla_owner", "pmzilla_knowledge", "pmzilla_flow_ro", "pmzilla_quality", "pmzilla_quality_ro")    # rôles d'application des migrations qui ne reçoivent jamais de mot de passe (propriétaire, écriture de knowledge, lecture seule de flow, écriture et lecture seule de quality)


class ErreurBase(Exception):
    """Erreur d'accès ou de migration ; le message ne contient jamais le mot de passe. `mot_de_passe_refuse` : le serveur a
    refusé l'authentification (contrôle des rôles de status)."""

    def __init__(self, message: str = "", *, mot_de_passe_refuse: bool = False):
        super().__init__(message)
        self.mot_de_passe_refuse = mot_de_passe_refuse


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
        refus = getattr(erreur, "sqlstate", None) == "28P01" or "password authentication failed" in message.lower()
        raise ErreurBase(f"Connexion à la base impossible : {message}.{indice}", mot_de_passe_refuse=refus) from None


def generer_mot_de_passe() -> str:
    """Mot de passe aléatoire (source sécurisée du système), sans caractère à protéger ; commence par une lettre ou un chiffre."""
    return secrets.choice(ALPHABET_MOT_DE_PASSE[:-2]) + "".join(
        secrets.choice(ALPHABET_MOT_DE_PASSE) for _ in range(LONGUEUR_MOT_DE_PASSE - 1))


def verifieur_scram(conn, role: str, mot_de_passe: str) -> str:
    """Empreinte SCRAM-SHA-256 calculée côté client par la bibliothèque de connexion : le serveur ne reçoit pas le mot de passe."""
    try:
        return conn.pgconn.encrypt_password(mot_de_passe.encode(), role.encode(), b"scram-sha-256").decode()
    except Exception:    # la bibliothèque, ou son absence de support : aucun détail, il pourrait porter le mot de passe
        raise ErreurBase("chiffrement du mot de passe impossible côté client ; rien n'a été modifié.") from None


def definir_mot_de_passe(conn, role: str, mot_de_passe: str, autorises: tuple[str, ...] = ROLES_AVEC_MOT_DE_PASSE,
                         *, valider: bool = True) -> None:
    """Pose le mot de passe d'un rôle de lecture limitée et l'autorise à se connecter. Le serveur reçoit une empreinte SCRAM-SHA-256
    et jamais le mot de passe en clair. `valider=False` laisse la transaction ouverte : l'appelant valide ou annule."""
    if role not in autorises:
        raise ErreurBase(f"Rôle non autorisé : {role} (acceptés : {', '.join(autorises)}).")
    if len(mot_de_passe) < 12:
        raise ErreurBase("Mot de passe trop court (12 caractères au moins).")
    verifieur = verifieur_scram(conn, role, mot_de_passe)
    conn.execute(psycopg.sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
        psycopg.sql.Identifier(role), psycopg.sql.Literal(verifieur)))
    if valider:
        conn.commit()


def ranger_dans_trousseau(role: str, mot_de_passe: str, security: str | None = None) -> None:
    """Écrit le mot de passe dans l'entrée du rôle (remplace l'existante). `security` est lancé en mode interactif et la commande
    d'ajout passe par son entrée standard : le mot de passe n'est dans aucun argument de processus."""
    commande = security or os.environ.get(VARIABLE_SECURITY) or "security"
    refus = ErreurBase(f"le Trousseau a refusé l'écriture (service {service_du_role(role)}) ; aucun mot de passe n'a été posé.")
    instruction = f"add-generic-password -U -s {service_du_role(role)} -a {getpass.getuser()} -w {mot_de_passe}\n"
    try:
        fait = subprocess.run([commande, "-i"], input=instruction, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise refus from None
    if fait.returncode != 0:
        raise refus


def verifier_entree_du_trousseau(role: str, secret: str, security: str | None = None) -> None:
    """Relit l'entrée du rôle par la recherche normale du Trousseau (sans la variable d'environnement) et la compare au mot de
    passe généré, en mémoire. Une différence ou un échec de relecture lève une ErreurBase dont la phrase ne porte jamais de secret :
    on ne dépend pas du code de sortie de `security -i`."""
    refus = ErreurBase(f"le Trousseau n'a pas rendu le mot de passe écrit (service {service_du_role(role)}) ; "
                       "aucun mot de passe n'a été posé.")
    try:
        relu = mot_de_passe_trousseau(security, role)
    except Exception:
        raise refus from None
    if relu is None or not hmac.compare_digest(relu.encode(), secret.encode()):
        raise refus


def essai_de_connexion(role: str, secret: str) -> None:
    """Session d'essai sous le rôle, avec le mot de passe relu par la recherche normale (Trousseau d'abord). ErreurBase sans secret."""
    try:
        session = connect(role=role)
    except ErreurBase as erreur:
        raise ErreurBase(_masquer(str(erreur), secret)) from None
    try:
        utilisateur = session.execute("SELECT current_user").fetchone()[0]
    except Exception:
        raise ErreurBase("la session s'est ouverte mais n'a pas répondu.") from None
    finally:
        session.close()
    if utilisateur != role:
        raise ErreurBase(f"la session s'est ouverte sous un autre rôle ({utilisateur}).")


def generer_poser_ranger(role: str, autorises: tuple[str, ...] = ROLES_AVEC_MOT_DE_PASSE) -> None:
    """role-password : génère, pose (transaction), range dans le Trousseau, valide, puis teste. Rien n'est affiché ni renvoyé."""
    secret = generer_mot_de_passe()
    conn = connect()
    try:
        try:
            definir_mot_de_passe(conn, role, secret, autorises, valider=False)
            ranger_dans_trousseau(role, secret)
            verifier_entree_du_trousseau(role, secret)
        except ErreurBase:
            conn.rollback()
            raise
        conn.commit()
    finally:
        conn.close()
    try:
        essai_de_connexion(role, secret)
    except ErreurBase as erreur:
        raise ErreurBase(f"mot de passe posé et rangé, mais la connexion d'essai sous {role} a échoué : {str(erreur).rstrip('.')}.") from None


# --- Contrôles de status : rôles et pg_search -----------------------------------------------------------------------

@dataclass(frozen=True)
class EtatRole:
    role: str
    niveau: str        # ok, non_configure, probleme
    raison: str        # ok, non_configure, absent, sans_mot_de_passe, connexion_interdite, mot_de_passe_refuse, connexion_impossible, connexion_permise
    detail: str = ""   # message masqué de la session d'essai (connexion_impossible)


@dataclass(frozen=True)
class EtatExtension:
    niveau: str        # ok, probleme
    raison: str        # ok, absente, version_differente
    installee: str = ""
    attendue: str = ""


def etat_des_roles(conn, *, security: str | None = None, connecter=None, roles: tuple[str, ...] = ROLES_AVEC_MOT_DE_PASSE,
                   hors_liste: tuple[str, ...] = ROLES_SANS_MOT_DE_PASSE) -> list[EtatRole]:
    """État de chaque rôle de la liste (lecture du catalogue, mot de passe cherché, session d'essai courte) puis des rôles d'application
    hors liste qui peuvent se connecter. Ne modifie rien ; aucun mot de passe n'est renvoyé ni affiché ; aucune session sous un rôle dont
    le mot de passe manque ou dont la connexion est interdite."""
    connecter = connecter or connect
    lignes = conn.execute("SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = ANY(%s)", (list(roles) + list(hors_liste),)).fetchall()
    connexion = {nom: bool(peut) for nom, peut in lignes}
    etats: list[EtatRole] = []
    for role in roles:
        if role not in connexion:
            etats.append(EtatRole(role, "probleme", "absent"))
            continue
        secret = lire_mot_de_passe(security, role)
        if not connexion[role]:
            etats.append(EtatRole(role, "non_configure", "non_configure") if secret is None
                         else EtatRole(role, "probleme", "connexion_interdite"))
        elif secret is None:
            etats.append(EtatRole(role, "probleme", "sans_mot_de_passe"))
        else:
            try:
                connecter(role=role, password=secret, timeout=DELAI_ESSAI).close()
                etats.append(EtatRole(role, "ok", "ok"))
            except ErreurBase as erreur:
                if erreur.mot_de_passe_refuse:
                    etats.append(EtatRole(role, "probleme", "mot_de_passe_refuse"))
                else:
                    etats.append(EtatRole(role, "probleme", "connexion_impossible", _masquer(str(erreur), secret)))
    for role in hors_liste:
        if connexion.get(role):
            etats.append(EtatRole(role, "probleme", "connexion_permise"))
    return etats


def version_attendue_pg_search(fichier_compose: Path = FICHIER_COMPOSE) -> str:
    """Version de pg_search attendue : la partie version du tag de l'image du service `db` de docker-compose.yml, sans le suffixe
    PostgreSQL (0.26.2-pg18 donne 0.26.2). ErreurBase si le tag est illisible."""
    illisible = ErreurBase("version attendue de pg_search illisible dans docker-compose.yml.")
    try:
        lignes = Path(fichier_compose).read_text(encoding="utf-8").splitlines()
    except OSError:
        raise illisible from None
    dans_db = False
    for ligne in lignes:
        if re.match(r"^  \S", ligne):
            dans_db = ligne.strip() == "db:"
        elif dans_db and (trouve := re.match(r"^\s+image:\s*(\S+)\s*$", ligne)):
            tag = re.match(r"^[^@:]+:(\d+(?:\.\d+)+)(?:-pg\d+)?$", trouve.group(1))
            if tag:
                return tag.group(1)
            break
    raise illisible


def etat_pg_search(conn, attendue: str) -> EtatExtension:
    """Compare la version installée de pg_search (catalogue) à l'attendue. Ne modifie rien."""
    ligne = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_search'").fetchone()
    if ligne is None:
        return EtatExtension("probleme", "absente", attendue=attendue)
    if ligne[0] != attendue:
        return EtatExtension("probleme", "version_differente", ligne[0], attendue)
    return EtatExtension("ok", "ok", ligne[0], attendue)


def lignes_roles(etats: list[EtatRole]) -> list[str]:
    """Lignes de status des rôles (design D6)."""
    lignes = []
    for e in etats:
        debut = f"Rôle {e.role} : "
        if e.raison == "ok":
            lignes.append(debut + "ok")
        elif e.raison == "non_configure":
            lignes.append(debut + "non configuré")
        elif e.raison == "absent":
            lignes.append(debut + "problème : absent de la base")
        elif e.raison == "sans_mot_de_passe":
            lignes.append(debut + "problème : connexion permise mais aucun mot de passe rangé "
                          f"(Trousseau {service_du_role(e.role)}, variable {variable_du_role(e.role)})")
        elif e.raison == "connexion_interdite":
            lignes.append(debut + "problème : mot de passe rangé mais connexion interdite")
        elif e.raison == "mot_de_passe_refuse":
            lignes.append(debut + f"problème : mot de passe refusé par la base (relancer : uv run tools/db.py role-password {e.role})")
        elif e.raison == "connexion_impossible":
            lignes.append(debut + f"problème : connexion impossible : {e.detail}")
        else:
            lignes.append(debut + "problème : connexion permise alors qu'il ne reçoit jamais de mot de passe")
    return lignes


def ligne_extension(e: EtatExtension) -> str:
    if e.raison == "ok":
        return f"pg_search : ok ({e.installee})"
    if e.raison == "absente":
        return "pg_search : problème : extension absente"
    return f"pg_search : problème : version {e.installee} installée, {e.attendue} attendue (image de la base)"


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

def main(argv: list[str] | None = None, dossier: Path = DOSSIER_MIGRATIONS, compose: Path = FICHIER_COMPOSE) -> int:
    analyseur = argparse.ArgumentParser(description="Accès à la base PMZilla Lab et migrations.")
    sous = analyseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("migrate", help="applique les migrations en attente").add_argument("--dry-run", action="store_true")
    sous.add_parser("status", help="migrations, rôles qui se connectent, rôles hors liste et version de pg_search ; code 3 si un problème")
    sous.add_parser("role-password", help="génère, pose, range dans le Trousseau et teste le mot de passe d'un rôle limité").add_argument(
        "role", choices=ROLES_AVEC_MOT_DE_PASSE)
    args = analyseur.parse_args(argv)
    try:
        if args.commande == "role-password":
            generer_poser_ranger(args.role)
            print(f"Mot de passe de {args.role} généré, posé et rangé dans le Trousseau (service {service_du_role(args.role)}) ; "
                  "connexion d'essai réussie.")
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
                attendue = version_attendue_pg_search(compose)
                roles = etat_des_roles(conn)
                extension = etat_pg_search(conn, attendue)
                for ligne in lignes_roles(roles):
                    print(ligne)
                print(ligne_extension(extension))
                problemes = sum(e.niveau == "probleme" for e in roles) + (extension.niveau == "probleme")
                print("État : aucun problème." if not problemes else f"État : {problemes} problème(s).")
                if problemes:
                    return 3
        finally:
            conn.close()
    except ErreurBase as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
