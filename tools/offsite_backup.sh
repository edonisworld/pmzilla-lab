#!/bin/bash
# PMZilla Lab : copie hors du Mac des sauvegardes (base et sanctum) sur UN disque externe chiffré, et test de restauration mensuel.
#
#     bash tools/offsite_backup.sh setup <point de montage>   enregistre le disque (identifiant du volume), après vérifications et confirmation
#     bash tools/offsite_backup.sh copy [--include-protected] copie la dernière sauvegarde ordinaire de la base et du sanctum, avec manifeste
#     bash tools/offsite_backup.sh restore-test [--force]     test mensuel : sommes de contrôle, restauration de la base dans un conteneur jetable
#     bash tools/offsite_backup.sh status                     affiche l'état (dernières copies, âge) sans rien monter ni écrire
#     bash tools/offsite_backup.sh --help
#
# Le disque est un volume APFS chiffré, retrouvé par son identifiant de volume (jamais par son nom ni par un chemin). macOS le
# déverrouille ; ce script ne lit, ne demande, ne stocke ni n'affiche aucun mot de passe et n'appelle jamais le Trousseau.
# Refus (code 2, rien écrit) : volume non chiffré, disque interne, volume réseau, dossier synchronisé (iCloud, Dropbox…) ou dépôt Git.
# Aucune commande réseau : les copies vont sous pmzilla-offsite/ à la racine du volume identifié, les rapports et l'état sous
# ~/.pmzilla-lab/offsite/. Les sauvegardes locales ne sont ni modifiées ni supprimées.
#
# Copie : dernière sauvegarde ordinaire datée (db-AAAA-MM-JJ, bmad-memory-AAAA-MM-JJ), jamais une sauvegarde étiquetée ; écrite dans
# .partiel-<nom>, avec un manifeste (somme SHA-256 et taille de chaque fichier), vérifiée sur le disque, puis renommée. Dossiers en 700,
# fichiers en 600. Rotation après une copie vérifiée : N copies récentes plus la dernière de chacun des M derniers mois.
# La sauvegarde de sanctum protégée de la rotation locale n'est copiée que sur --include-protected, une fois, et n'est jamais tournée.
# Il n'affiche que des noms de copies (dates), des nombres de fichiers, des tailles et des statuts : jamais un nom de fichier d'une
# copie, ni une valeur, ni le contenu du sanctum, ni le nom ou l'identifiant du volume (le nom n'est montré que par setup).
#
# Codes : 0 fait, déjà présent ou test non dû ; 1 échec (copie, vérification, place, somme de contrôle, test) ;
# 2 usage ou environnement refusé (option inconnue, rétention invalide, non configuré, volume refusé, setup refusé) ;
# 3 reporté (disque absent ou verrouillé, vraie base indisponible pour le test).
# Notification macOS (osascript) sur les codes 1 et 2, et sur l'absence prolongée du disque (au plus une par jour), seulement si
# OFFSITE_NOTIFIER=1 (posé par les modèles launchd, jamais en lancement à la main).
#
# Variables (pour les tests et le réglage) : OFFSITE_DONNEES (défaut ~/.pmzilla-lab), OFFSITE_SAUVEGARDES (défaut <données>/sauvegardes),
# OFFSITE_DISKUTIL (utilitaire de disque, défaut diskutil), OFFSITE_MOUNT_CMD (défaut mount), OFFSITE_DATE (défaut : date du jour),
# OFFSITE_GARDER_RECENTES (7), OFFSITE_GARDER_MOIS (12), OFFSITE_AGE_MAX_JOURS (7), OFFSITE_RAPPORTS_GARDER (12), OFFSITE_RESTORE_SCRIPT
# (défaut tools/db_restore_test.sh), OFFSITE_PROTEGEE (défaut bmad-memory-2026-10-07), OFFSITE_LIBRE_KO (place libre simulée, en Ko).
# HYPOTHÈSE (à confirmer sur le macOS de l'auteur, tâche 1.3) : noms des clés de `diskutil info -plist`, réglables ici :
# OFFSITE_CLE_UUID (VolumeUUID), OFFSITE_CLE_MONTAGE (MountPoint), OFFSITE_CLE_NOM (VolumeName), OFFSITE_CLES_CHIFFRE (« FileVault
# Encryption » : la première clé vraie vaut chiffré), OFFSITE_CLE_VERROUILLE (Locked), OFFSITE_CLE_INTERNE (Internal), OFFSITE_CLE_RESEAU
# (NetworkVolume), OFFSITE_CLE_FS (FilesystemType, types réseau : smbfs nfs afpfs webdav cifs autofs).
set -uo pipefail
umask 077
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"   # launchd donne un PATH minimal ; ajouté à la fin, un PATH déjà complet reste prioritaire
RACINE="$(cd "$(dirname "$0")/.." && pwd)"

LAB="${OFFSITE_DONNEES:-$HOME/.pmzilla-lab}"
SAUV="${OFFSITE_SAUVEGARDES:-$LAB/sauvegardes}"
DISKUTIL="${OFFSITE_DISKUTIL:-diskutil}"
MOUNT_CMD="${OFFSITE_MOUNT_CMD:-mount}"
DATE="${OFFSITE_DATE:-$(date +%Y-%m-%d)}"
RECENTES="${OFFSITE_GARDER_RECENTES:-7}"
MOIS="${OFFSITE_GARDER_MOIS:-12}"
AGE_MAX="${OFFSITE_AGE_MAX_JOURS:-7}"
RAPPORTS_GARDER="${OFFSITE_RAPPORTS_GARDER:-12}"
RESTORE="${OFFSITE_RESTORE_SCRIPT:-$RACINE/tools/db_restore_test.sh}"
PROTEGEE="${OFFSITE_PROTEGEE:-bmad-memory-2026-10-07}"
CLE_UUID="${OFFSITE_CLE_UUID:-VolumeUUID}"
CLE_MONTAGE="${OFFSITE_CLE_MONTAGE:-MountPoint}"
CLE_NOM="${OFFSITE_CLE_NOM:-VolumeName}"
CLES_CHIFFRE="${OFFSITE_CLES_CHIFFRE:-FileVault Encryption}"
CLE_VERROUILLE="${OFFSITE_CLE_VERROUILLE:-Locked}"
CLE_INTERNE="${OFFSITE_CLE_INTERNE:-Internal}"
CLE_RESEAU="${OFFSITE_CLE_RESEAU:-NetworkVolume}"
CLE_FS="${OFFSITE_CLE_FS:-FilesystemType}"

DOSSIER_OFFSITE="pmzilla-offsite"
MANIFESTE="MANIFESTE.sha256"
ETAT="$LAB/offsite"
CONFIG="$ETAT/configuration"
STATUT="$ETAT/statut"
RAPPORTS="$ETAT/rapports"
NOTIF_ABSENCE="$ETAT/notification-absence"

OPERATION=""; REUSSI=0; RAISON=""; MESSAGE_NOTIF=""; RAPPORT_OUVERT=0
TMP="$(mktemp -d "${TMPDIR:-/tmp}/offsite.XXXXXX")" || exit 2

# ---------------------------------------------------------------------------------------------------------------------------
# Sortie, état, notification
# ---------------------------------------------------------------------------------------------------------------------------
notifier() {   # message : 0 si envoyée. Jamais en lancement à la main. Un échec de notification ne change jamais le code de sortie.
  [ "${OFFSITE_NOTIFIER:-}" = "1" ] || return 1
  osascript -e "display notification \"$1\" with title \"PMZilla offsite\"" >/dev/null 2>&1 || echo "Notification macOS impossible"
  return 0
}
statut_lire() {   # operation champ : valeur du champ, vide si absent
  [ -f "$STATUT" ] || return 0
  sed -n "s/^$1 .*$2=\([^ ]*\).*/\1/p" "$STATUT" | head -1
}
statut_ecrire() {   # cle reste-de-la-ligne : remplace la ligne de la clé
  mkdir -p "$ETAT" && chmod 700 "$ETAT" 2>/dev/null
  { grep -v "^$1 " "$STATUT" 2>/dev/null; echo "$1 $2"; } | LC_ALL=C sort > "$STATUT.tmp" && chmod 600 "$STATUT.tmp" && mv "$STATUT.tmp" "$STATUT"
}
maj_operation() {   # operation resultat reussi(0/1)
  local ancienne; ancienne="$(statut_lire "$1" derniere_reussite)"
  [ "$3" = "1" ] && ancienne="$DATE"
  statut_ecrire "$1" "derniere_reussite=${ancienne:--} resultat=$2 date=$DATE"
}
a_la_sortie() {
  local code=$?
  if [ -n "$OPERATION" ]; then
    case "$code" in
      0) maj_operation "$OPERATION" ok "$REUSSI" ;;
      1) maj_operation "$OPERATION" echec 0 ;;
      2) maj_operation "$OPERATION" refus 0 ;;
      3) maj_operation "$OPERATION" reporte 0 ;;
    esac
  fi
  case "$code" in
    1|2) notifier "${MESSAGE_NOTIF:-Sauvegarde hors du Mac en échec (code $code) : $RAISON}" >/dev/null ;;
  esac
  rm -rf "$TMP"
}
trap a_la_sortie EXIT
echec() {   # code message : affiche, retient pour la notification, sort
  echo "$2"; RAISON="$2"; exit "$1"
}

# ---------------------------------------------------------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------------------------------------------------------
entier_au_moins_1() { printf '%s' "$1" | grep -Eq '^[1-9][0-9]*$'; }
valider_reglages() {
  local nom valeur
  for nom in OFFSITE_GARDER_RECENTES OFFSITE_GARDER_MOIS OFFSITE_AGE_MAX_JOURS OFFSITE_RAPPORTS_GARDER; do
    case "$nom" in
      OFFSITE_GARDER_RECENTES) valeur="$RECENTES" ;; OFFSITE_GARDER_MOIS) valeur="$MOIS" ;;
      OFFSITE_AGE_MAX_JOURS) valeur="$AGE_MAX" ;; *) valeur="$RAPPORTS_GARDER" ;;
    esac
    entier_au_moins_1 "$valeur" || echec 2 "$nom invalide : $valeur (entier au moins égal à 1)"
  done
  printf '%s' "$DATE" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || echec 2 "OFFSITE_DATE invalide : $DATE (attendu AAAA-MM-JJ)"
}
jours() {   # AAAA-MM-JJ : numéro de jour (seules les différences comptent)
  local y="${1%%-*}" r="${1#*-}" m d
  m="${r%%-*}"; d="${r#*-}"; y=$((10#$y)); m=$((10#$m)); d=$((10#$d))
  if [ "$m" -le 2 ]; then y=$((y - 1)); m=$((m + 12)); fi
  echo $((365 * y + y / 4 - y / 100 + y / 400 + (153 * (m - 3) + 2) / 5 + d))
}
SHA() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 -- "$1" | cut -d' ' -f1; else sha256sum -- "$1" | cut -d' ' -f1; fi; }
manifeste_de() {   # dossier : lignes « somme<TAB>taille<TAB>chemin relatif », triées, sans le manifeste lui-même
  ( cd "$1" 2>/dev/null || exit 1
    find . -type f ! -path "./$MANIFESTE" -print | sed 's|^\./||' | LC_ALL=C sort | while IFS= read -r f; do
      printf '%s\t%s\t%s\n' "$(SHA "$f")" "$(wc -c < "$f" | tr -d ' ')" "$f"
    done )
}
copie_verifiee() {   # dossier : 0 si chaque fichier du manifeste est présent, de même taille et même somme, et rien en plus
  [ -f "$1/$MANIFESTE" ] || return 1
  manifeste_de "$1" > "$TMP/verif.txt" || return 1
  cmp -s "$TMP/verif.txt" "$1/$MANIFESTE"
}
plus_recent() {   # dossier prefixe : nom de la copie ordinaire la plus récente (hors sauvegarde protégée)
  ls -1 "$1" 2>/dev/null | grep -E "^$2-[0-9]{4}-[0-9]{2}-[0-9]{2}\$" | grep -vx "$PROTEGEE" | LC_ALL=C sort | tail -1
}

# ---------------------------------------------------------------------------------------------------------------------------
# Disque : propriétés (HYPOTHÈSE sur les clés de l'utilitaire de disque : tout est isolé dans interroger_volume)
# ---------------------------------------------------------------------------------------------------------------------------
cle() { plutil -extract "$2" raw -o - "$1" 2>/dev/null; }
vrai() { case "$1" in true|1|yes|Yes|YES) return 0 ;; *) return 1 ;; esac; }
P_UUID=""; P_MONTAGE=""; P_NOM=""; P_CHIFFRE=0; P_VERROUILLE=0; P_INTERNE=0; P_RESEAU=0
interroger_volume() {   # identifiant ou point de montage : remplit P_* ; 1 si l'utilitaire ne connaît pas ce volume
  local f="$TMP/volume.plist" k fs
  P_UUID=""; P_MONTAGE=""; P_NOM=""; P_CHIFFRE=0; P_VERROUILLE=0; P_INTERNE=0; P_RESEAU=0
  "$DISKUTIL" info -plist "$1" > "$f" 2>/dev/null || return 1
  [ -s "$f" ] && plutil -lint "$f" >/dev/null 2>&1 || return 1
  P_UUID="$(cle "$f" "$CLE_UUID")"; P_MONTAGE="$(cle "$f" "$CLE_MONTAGE")"; P_NOM="$(cle "$f" "$CLE_NOM")"
  for k in $CLES_CHIFFRE; do vrai "$(cle "$f" "$k")" && P_CHIFFRE=1; done
  vrai "$(cle "$f" "$CLE_VERROUILLE")" && P_VERROUILLE=1
  vrai "$(cle "$f" "$CLE_INTERNE")" && P_INTERNE=1
  vrai "$(cle "$f" "$CLE_RESEAU")" && P_RESEAU=1
  fs="$(cle "$f" "$CLE_FS")"
  case "$fs" in smbfs|nfs|afpfs|webdav|cifs|autofs) P_RESEAU=1 ;; esac
  return 0
}
dossier_synchronise_ou_git() {   # chemin : 0 si dans un dossier synchronisé du dossier personnel ou dans un dépôt Git
  local reel home d
  reel="$(cd -P "$1" 2>/dev/null && pwd)" || return 1
  home="$(cd -P "$HOME" 2>/dev/null && pwd)" || home="$HOME"
  case "$reel/" in
    "$home"/Library/Mobile\ Documents/*|"$home"/Library/CloudStorage/*|"$home"/Dropbox*/*|"$home"/Google\ Drive*/*|"$home"/GoogleDrive*/*|"$home"/OneDrive*/*|"$home"/iCloud*/*|"$home"/Nextcloud*/*|"$home"/pCloud*/*|"$home"/MEGA*/*) return 0 ;;
  esac
  d="$reel"
  while [ -n "$d" ] && [ "$d" != "/" ]; do
    [ -e "$d/.git" ] && return 0
    d="$(dirname "$d")"
  done
  return 1
}
verifier_destination() {   # point de montage (P_* à jour) : refuse avec le code 2 sans rien écrire
  [ "$P_CHIFFRE" -eq 1 ] || echec 2 "volume non chiffré : refusé"
  [ "$P_INTERNE" -eq 0 ] || echec 2 "disque interne : refusé"
  [ "$P_RESEAU" -eq 0 ] || echec 2 "volume réseau : refusé"
  if dossier_synchronise_ou_git "$1"; then echec 2 "dossier synchronisé ou dépôt Git : refusé"; fi
}
charger_config() {
  [ -f "$CONFIG" ] || echec 2 "disque hors du Mac non configuré : lancer setup"
  VOLUME_ID="$(sed -n 's/^volume=//p' "$CONFIG" | head -1)"
  [ -n "$VOLUME_ID" ] || echec 2 "disque hors du Mac non configuré : lancer setup"
}
MONTAGE=""
trouver_volume() {   # 0 si le volume configuré est monté et déverrouillé (MONTAGE, P_*), 3 sinon ; trouvé par son identifiant seulement
  MONTAGE=""
  interroger_volume "$VOLUME_ID" || return 3
  [ "$P_UUID" = "$VOLUME_ID" ] || return 3
  [ "$P_VERROUILLE" -eq 0 ] || return 3
  [ -n "$P_MONTAGE" ] && [ -d "$P_MONTAGE" ] || return 3
  MONTAGE="$P_MONTAGE"
  return 0
}

# ---------------------------------------------------------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------------------------------------------------------
sous_commande_setup() {
  [ $# -eq 1 ] || echec 2 "Usage : bash tools/offsite_backup.sh setup <point de montage>"
  local point="$1" reponse
  [ -d "$point" ] || echec 2 "point de montage introuvable : $point"
  if ! interroger_volume "$point"; then
    if "$MOUNT_CMD" 2>/dev/null | grep -F " on $point (" | grep -Eq '\((smbfs|nfs|afpfs|webdav|cifs|autofs)[,)]'; then
      echec 2 "volume réseau : refusé"
    fi
    echec 2 "volume inconnu de l'utilitaire de disque : refusé"
  fi
  [ -n "$P_UUID" ] || echec 2 "identifiant du volume introuvable : refusé"
  verifier_destination "$point"
  echo "Volume proposé : ${P_NOM:-(sans nom)}"
  printf 'Enregistrer ce volume comme disque hors du Mac ? [y/N] '
  reponse=""; read -r reponse || true
  case "$reponse" in y|Y|yes|oui) ;; *) echo; echec 2 "setup refusé : rien n'a été enregistré" ;; esac
  mkdir -p "$point/$DOSSIER_OFFSITE" && chmod 700 "$point/$DOSSIER_OFFSITE" || echec 2 "impossible de créer le dossier de copies sur le volume"
  mkdir -p "$ETAT" && chmod 700 "$ETAT"
  printf 'volume=%s\n' "$P_UUID" > "$CONFIG" && chmod 600 "$CONFIG"
  echo "Disque hors du Mac enregistré."
}

# ---------------------------------------------------------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------------------------------------------------------
rotation() {   # dossier-de-serie prefixe : garde RECENTES copies récentes plus la dernière de chacun des MOIS derniers mois
  local dossier="$1" prefixe="$2" nom n=0 mois vus="" nbmois=0 garder
  for nom in $(ls -1 "$dossier" | grep -E "^$prefixe-[0-9]{4}-[0-9]{2}-[0-9]{2}\$" | grep -vx "$PROTEGEE" | LC_ALL=C sort -r); do
    [ -d "$dossier/$nom" ] || continue
    n=$((n + 1)); garder=0
    mois="${nom#"$prefixe"-}"; mois="${mois%-??}"
    [ "$n" -le "$RECENTES" ] && garder=1
    case " $vus " in
      *" $mois "*) ;;
      *) nbmois=$((nbmois + 1)); vus="$vus $mois"; [ "$nbmois" -le "$MOIS" ] && garder=1 ;;
    esac
    [ "$garder" -eq 1 ] && continue
    rm -rf "${dossier:?}/$nom"
    echo "copie supprimée : $nom"
  done
}
copier_serie() {   # serie prefixe : 0 fait ou rien à faire, 1 échec (message affiché, RAISON posée)
  local serie="$1" prefixe="$2" dossier="$ETAT_DISQUE/$1" nom source partiel taille libre besoin n
  [ -d "$dossier" ] && rm -rf "$dossier"/.partiel-* 2>/dev/null
  nom="$(plus_recent "$SAUV" "$prefixe")"
  if [ -n "$nom" ] && [ -d "$SAUV/$nom" ]; then
    :
  else
    echo "aucune sauvegarde ordinaire locale à copier : $serie"
    nom=""
  fi
  if [ -n "$nom" ]; then
    source="$SAUV/$nom"
    if [ -d "$dossier/$nom" ] && copie_verifiee "$dossier/$nom"; then
      echo "déjà présente : $nom"
    else
      [ -d "$dossier/$nom" ] && echo "copie incomplète : $nom"
      taille="$(du -sk "$source" 2>/dev/null | cut -f1)"; taille="${taille:-0}"
      libre="${OFFSITE_LIBRE_KO:-$(df -Pk "$MONTAGE" 2>/dev/null | awk 'NR==2 {print $4}')}"
      besoin=$((taille + taille / 10 + 1024))
      if [ -z "$libre" ] || [ "$libre" -le "$besoin" ]; then
        RAISON="place insuffisante sur le disque"; echo "$RAISON"; return 1
      fi
      mkdir -p "$dossier" && chmod 700 "$dossier"
      partiel="$dossier/.partiel-$nom"
      manifeste_de "$source" > "$TMP/source.txt"
      if ! cp -R "$source" "$partiel" 2>/dev/null; then
        rm -rf "$partiel"; RAISON="copie incomplète : $nom"; echo "$RAISON"; return 1
      fi
      find "$partiel" -type d -exec chmod 700 {} + 2>/dev/null
      find "$partiel" -type f -exec chmod 600 {} + 2>/dev/null
      manifeste_de "$partiel" > "$TMP/copie.txt"
      if ! cmp -s "$TMP/source.txt" "$TMP/copie.txt"; then
        rm -rf "$partiel"; RAISON="copie incomplète : $nom"; echo "$RAISON"; return 1
      fi
      cp "$TMP/source.txt" "$partiel/$MANIFESTE" && chmod 600 "$partiel/$MANIFESTE"
      [ -d "$dossier/$nom" ] && rm -rf "${dossier:?}/$nom"
      mv "$partiel" "$dossier/$nom" || { rm -rf "$partiel"; RAISON="copie incomplète : $nom"; echo "$RAISON"; return 1; }
      n="$(wc -l < "$TMP/source.txt" | tr -d ' ')"
      echo "copie créée : $nom ($n fichiers, $(du -sk "$dossier/$nom" | cut -f1) Ko)"
    fi
    statut_ecrire "serie-$serie" "derniere_copie=$nom"
    REUSSI=1
  fi
  if [ "$serie" = "sanctum" ] && [ "$INCLURE_PROTEGEE" -eq 1 ] && [ -d "$SAUV/$PROTEGEE" ]; then
    copier_protegee "$dossier" || return 1
  fi
  [ -n "$nom" ] && [ -d "$dossier" ] && rotation "$dossier" "$prefixe"
  return 0
}
copier_protegee() {   # dossier-de-serie : copie la sauvegarde protégée une fois, si absente (jamais tournée)
  local dossier="$1" partiel="$1/.partiel-$PROTEGEE" n
  if [ -d "$dossier/$PROTEGEE" ] && copie_verifiee "$dossier/$PROTEGEE"; then
    echo "déjà présente : $PROTEGEE"; return 0
  fi
  mkdir -p "$dossier" && chmod 700 "$dossier"
  manifeste_de "$SAUV/$PROTEGEE" > "$TMP/protegee-source.txt"
  if ! cp -R "$SAUV/$PROTEGEE" "$partiel" 2>/dev/null; then rm -rf "$partiel"; RAISON="copie incomplète : $PROTEGEE"; echo "$RAISON"; return 1; fi
  find "$partiel" -type d -exec chmod 700 {} + 2>/dev/null
  find "$partiel" -type f -exec chmod 600 {} + 2>/dev/null
  manifeste_de "$partiel" > "$TMP/protegee-copie.txt"
  if ! cmp -s "$TMP/protegee-source.txt" "$TMP/protegee-copie.txt"; then rm -rf "$partiel"; RAISON="copie incomplète : $PROTEGEE"; echo "$RAISON"; return 1; fi
  cp "$TMP/protegee-source.txt" "$partiel/$MANIFESTE" && chmod 600 "$partiel/$MANIFESTE"
  [ -d "$dossier/$PROTEGEE" ] && rm -rf "${dossier:?}/$PROTEGEE"
  mv "$partiel" "$dossier/$PROTEGEE" || { rm -rf "$partiel"; RAISON="copie incomplète : $PROTEGEE"; echo "$RAISON"; return 1; }
  n="$(wc -l < "$TMP/protegee-source.txt" | tr -d ' ')"
  echo "copie créée : $PROTEGEE ($n fichiers, $(du -sk "$dossier/$PROTEGEE" | cut -f1) Ko)"
  return 0
}
absence_notifier() {   # notifie l'âge de la dernière copie réussie, au plus une fois par jour, seulement une fois la copie trop vieille
  local derniere age message
  derniere="$(statut_lire copy derniere_reussite)"
  if [ -z "$derniere" ] || [ "$derniere" = "-" ]; then
    message="aucune copie hors du Mac réussie à ce jour"
  else
    age=$(( $(jours "$DATE") - $(jours "$derniere") ))
    [ "$age" -ge "$AGE_MAX" ] || return 0
    message="aucune copie hors du Mac depuis $age jours"
  fi
  [ "$(cat "$NOTIF_ABSENCE" 2>/dev/null)" = "$DATE" ] && return 0
  if notifier "$message"; then
    mkdir -p "$ETAT" && chmod 700 "$ETAT" 2>/dev/null
    echo "$DATE" > "$NOTIF_ABSENCE" && chmod 600 "$NOTIF_ABSENCE"
  fi
}
sous_commande_copy() {
  INCLURE_PROTEGEE=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --include-protected) INCLURE_PROTEGEE=1; shift ;;
      *) echec 2 "Usage : bash tools/offsite_backup.sh copy [--include-protected]" ;;
    esac
  done
  valider_reglages
  charger_config
  OPERATION="copy"
  trouver_volume
  if [ $? -ne 0 ]; then
    echo "disque absent ou verrouillé : copie reportée"
    absence_notifier
    exit 3
  fi
  verifier_destination "$MONTAGE"
  ETAT_DISQUE="$MONTAGE/$DOSSIER_OFFSITE"
  [ -d "$ETAT_DISQUE" ] || { mkdir -p "$ETAT_DISQUE" && chmod 700 "$ETAT_DISQUE"; }
  local ko=0
  copier_serie db db || ko=1
  copier_serie sanctum bmad-memory || ko=1
  [ "$ko" -eq 0 ] || exit 1
  exit 0
}

# ---------------------------------------------------------------------------------------------------------------------------
# restore-test
# ---------------------------------------------------------------------------------------------------------------------------
LIGNES_RAPPORT="$TMP/rapport-lignes.txt"
R() { printf '%s\n' "$*" >> "$LIGNES_RAPPORT"; }
ecrire_rapport() {   # resultat code
  local fichier="$RAPPORTS/restore-${DATE%-??}.txt" ancien
  mkdir -p "$RAPPORTS" && chmod 700 "$ETAT" "$RAPPORTS" 2>/dev/null
  { echo "Rapport du test de restauration hors du Mac"; echo "date : $DATE"; cat "$LIGNES_RAPPORT" 2>/dev/null
    echo "résultat : $1"; echo "code : $2"; } > "$fichier" && chmod 600 "$fichier"
  n=0
  for ancien in $(ls -1 "$RAPPORTS" | grep -E '^restore-[0-9]{4}-[0-9]{2}\.txt$' | LC_ALL=C sort -r); do
    n=$((n + 1)); [ "$n" -le "$RAPPORTS_GARDER" ] || rm -f "${RAPPORTS:?}/$ancien"
  done
}
echec_test() {   # cause : échec du test (code 1)
  echo "$1"
  echo "test de restauration hors du Mac : échec (code 1)"
  RAISON="$1"; MESSAGE_NOTIF="test de restauration hors du Mac : échec (code 1)"
  [ "$RAPPORT_OUVERT" -eq 1 ] && ecrire_rapport "échec : $1" 1
  exit 1
}
vraie_base_disponible() {   # mêmes sondes que db_restore_test.sh ; ne démarre jamais la base
  command -v docker >/dev/null 2>&1 || return 1
  docker info >/dev/null 2>&1 || return 1
  [ -n "$(cd "$RACINE" && docker compose ps -q --status running db 2>/dev/null)" ] || return 1
  ( cd "$RACINE" && docker compose exec -T db pg_isready -U postgres -d pmzilla >/dev/null 2>&1 ) || return 1
}
sous_commande_restore_test() {
  local forcer=0 dossier_db dossier_sanctum nom_db nom_sanctum code n_manifeste n_fichiers
  while [ $# -gt 0 ]; do
    case "$1" in
      --force) forcer=1; shift ;;
      *) echec 2 "Usage : bash tools/offsite_backup.sh restore-test [--force]" ;;
    esac
  done
  valider_reglages
  if [ "$forcer" -eq 0 ] && [ "$(statut_lire restore-test derniere_reussite | cut -c1-7)" = "${DATE%-??}" ]; then
    echo "test du mois déjà fait"; exit 0
  fi
  charger_config
  OPERATION="restore-test"
  trouver_volume
  if [ $? -ne 0 ]; then echo "disque absent ou verrouillé : test reporté"; exit 3; fi
  verifier_destination "$MONTAGE"
  if ! vraie_base_disponible; then echo "vraie base indisponible : test reporté"; exit 3; fi

  ETAT_DISQUE="$MONTAGE/$DOSSIER_OFFSITE"
  : > "$LIGNES_RAPPORT"; RAPPORT_OUVERT=1
  nom_db="$(plus_recent "$ETAT_DISQUE/db" db)"
  nom_sanctum="$(plus_recent "$ETAT_DISQUE/sanctum" bmad-memory)"
  [ -n "$nom_db" ] || echec_test "aucune copie de la base sur le disque"
  dossier_db="$ETAT_DISQUE/db/$nom_db"
  R "copie de la base testée : $nom_db"
  if ! copie_verifiee "$dossier_db"; then R "somme de contrôle base : différente"; echec_test "somme de contrôle différente : $nom_db"; fi
  R "somme de contrôle base : OK ($(wc -l < "$dossier_db/$MANIFESTE" | tr -d ' ') fichiers)"
  if [ -n "$nom_sanctum" ]; then
    dossier_sanctum="$ETAT_DISQUE/sanctum/$nom_sanctum"
    R "copie du sanctum testée : $nom_sanctum"
    if ! copie_verifiee "$dossier_sanctum"; then R "somme de contrôle sanctum : différente"; echec_test "somme de contrôle différente : $nom_sanctum"; fi
    R "somme de contrôle sanctum : OK ($(wc -l < "$dossier_sanctum/$MANIFESTE" | tr -d ' ') fichiers)"
  else
    R "copie du sanctum testée : aucune sur le disque (non testé)"
  fi

  bash "$RESTORE" --backup "$dossier_db" > "$TMP/restauration.txt" 2>&1; code=$?
  R "restauration de la base (db_restore_test.sh, code $code) :"
  grep -E '^  [A-Za-z0-9_]+\.[A-Za-z0-9_]+ +[0-9]+ / [0-9]+ +[^ ]' "$TMP/restauration.txt" > "$TMP/comptes.txt"
  grep -E '^  (RESTAURATION OK|ÉCHEC [a-z_]+ :)' "$TMP/restauration.txt" | cut -c1-120 >> "$TMP/comptes.txt"
  cat "$TMP/comptes.txt"
  sed 's/^/  /' "$TMP/comptes.txt" >> "$LIGNES_RAPPORT"
  [ "$code" -eq 0 ] || echec_test "restauration de la base en échec : $nom_db"

  if [ -n "$nom_sanctum" ]; then
    n_manifeste="$(wc -l < "$dossier_sanctum/$MANIFESTE" | tr -d ' ')"
    n_fichiers="$(find "$dossier_sanctum" -type f ! -path "$dossier_sanctum/$MANIFESTE" | wc -l | tr -d ' ')"
    R "sanctum : $n_fichiers fichiers, manifeste : $n_manifeste"
    echo "sanctum : $n_fichiers fichiers, manifeste : $n_manifeste"
    [ "$n_fichiers" = "$n_manifeste" ] || echec_test "copie incomplète : $nom_sanctum"
  fi
  ecrire_rapport OK 0
  REUSSI=1
  echo "test de restauration hors du Mac : OK"
  exit 0
}

# ---------------------------------------------------------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------------------------------------------------------
sous_commande_status() {
  [ $# -eq 0 ] || echec 2 "Usage : bash tools/offsite_backup.sh status"
  local ligne serie copie date_copie
  if [ ! -f "$STATUT" ]; then echo "aucun état enregistré"; exit 0; fi
  cat "$STATUT"
  grep -E '^serie-' "$STATUT" | while IFS= read -r ligne; do
    serie="${ligne%% *}"; serie="${serie#serie-}"
    copie="$(printf '%s' "$ligne" | sed -n 's/.*derniere_copie=\([^ ]*\).*/\1/p')"
    date_copie="${copie: -10}"
    printf '%s' "$date_copie" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || continue
    echo "âge de la dernière copie ($serie) : $(( $(jours "$DATE") - $(jours "$date_copie") )) jours"
  done
  exit 0
}

# ---------------------------------------------------------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------------------------------------------------------
SOUS="${1:-}"
[ $# -gt 0 ] && shift
case "$SOUS" in
  --help|-h|help) sed -n '2,/^set -uo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
  setup) sous_commande_setup "$@"; exit 0 ;;
  copy) sous_commande_copy "$@" ;;
  restore-test) sous_commande_restore_test "$@" ;;
  status) sous_commande_status "$@" ;;
  *) echec 2 "Usage : bash tools/offsite_backup.sh setup <point de montage> | copy [--include-protected] | restore-test [--force] | status | --help" ;;
esac
