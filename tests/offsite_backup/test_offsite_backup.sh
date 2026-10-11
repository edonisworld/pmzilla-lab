#!/bin/bash
# Test de tools/offsite_backup.sh : faux utilitaire de disque, faux osascript, faux docker, faux script de test de restauration, volumes
# fabriqués dans un dossier temporaire. Aucun vrai disque, aucun vrai diskutil, aucune vraie base, aucun réseau, aucune notification.
# Chaque fichier factice contient une sentinelle ; le nom du faux disque, son identifiant et un nom de fichier du sanctum aussi : aucun
# ne doit ressortir (sortie, notification, rapport, état) en dehors de setup, qui montre le nom du volume avant confirmation.
# Lancement à la main : bash tests/offsite_backup/test_offsite_backup.sh
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$racine/tools/offsite_backup.sh"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin"
ok=0; ko=0
verifie() { # description  code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}
absent() { ! grep -q -- "$1" "$2"; echo $?; }     # 0 si le motif est absent du fichier
present() { grep -q -- "$1" "$2"; echo $?; }       # 0 si le motif est présent
mode() { stat -f %Lp "$1" 2>/dev/null || stat -c %a "$1"; }

SENT="sentinelle-factice-4d2b"
NOMDISQUE="NOMDISQUE-sentinelle-8e1"
NOMFICHIER="NOMFICHIER-sentinelle-3c9"
ID="AAAAAAAA-1111-4111-8111-ENCRYPTED01"

export FAUX_LOG="$tmp/log"; : > "$FAUX_LOG"
export OSA_LOG="$tmp/osa"; : > "$OSA_LOG"
export FX="$tmp/fx"; mkdir -p "$FX/volumes" "$FX/debranches"
ALL="$tmp/toutes-les-sorties"; : > "$ALL"

# --- Faux utilitaire de disque : ne connaît que « info -plist <identifiant ou point de montage> » ; toute autre commande échoue.
cat > "$bin/diskutil" <<'SCRIPT'
#!/bin/bash
echo "diskutil $*" >> "$FAUX_LOG"
[ "${1:-}" = "info" ] && [ "${2:-}" = "-plist" ] || exit 1
for f in "$FX"/volumes/*.plist; do
  [ -f "$f" ] || continue
  u=$(plutil -extract VolumeUUID raw -o - "$f" 2>/dev/null); m=$(plutil -extract MountPoint raw -o - "$f" 2>/dev/null)
  if [ "$3" = "$u" ] || { [ -n "$m" ] && [ "$3" = "$m" ]; }; then cat "$f"; exit 0; fi
done
exit 1
SCRIPT
cat > "$bin/osascript" <<'SCRIPT'
#!/bin/bash
echo "osascript $*" >> "$OSA_LOG"
SCRIPT
cat > "$bin/docker" <<'SCRIPT'
#!/bin/bash
echo "docker $*" >> "$FAUX_LOG"
[ "${1:-}" = "info" ] && exit 0
if [ "${1:-}" = "compose" ]; then
  case "$*" in
    *"ps -q"*) [ "${FAUX_DB_ARRETEE:-0}" = "1" ] || echo abc123def456; exit 0 ;;
    *pg_isready*) exit 0 ;;
  esac
fi
exit 0
SCRIPT
# Faux mount : un montage réseau, pour le repli de setup quand l'utilitaire de disque ne connaît pas le point de montage.
cat > "$bin/mount" <<SCRIPT
#!/bin/bash
echo "//utilisateur@serveur/partage on $tmp/Volumes/RESEAU (smbfs, nodev, nosuid, mounted by utilisateur)"
SCRIPT
# Faux cp : copie réellement, puis tronque un fichier de la copie si FAUX_CP_CORROMPT=1 (copie corrompue).
cat > "$bin/cp" <<'SCRIPT'
#!/bin/bash
/bin/cp "$@"; code=$?
if [ "${FAUX_CP_CORROMPT:-0}" = "1" ]; then
  derniere="${@: -1}"
  f=$(find "$derniere" -type f | head -1); [ -n "$f" ] && echo "x" >> "$f"
fi
exit $code
SCRIPT
# Faux script de test de restauration : journalise ses arguments, imprime des comptes et des lignes qui ne doivent pas ressortir.
cat > "$tmp/restore_stub.sh" <<SCRIPT
#!/bin/bash
echo "restore \$*" >> "\$FAUX_LOG"
echo "Sauvegarde restaurée : \$2 $SENT"
echo "Lignes par table (restaurée / vraie base) :"
printf '  %-34s %10s / %-10s OK\n' knowledge.books 12 12
printf '  %-34s %10s / %-10s OK\n' flow.issues 40 40
echo "  valeur-de-table $SENT"
echo "Bilan :"
echo "  RESTAURATION OK, comptes identiques, empreinte des migrations identique."
exit \${FAUX_RESTORE_CODE:-0}
SCRIPT
chmod +x "$bin/diskutil" "$bin/osascript" "$bin/docker" "$bin/mount" "$bin/cp" "$tmp/restore_stub.sh"

export HOME="$tmp/home"; mkdir -p "$HOME"
export PATH="$bin:$PATH"
export OFFSITE_DONNEES="$tmp/lab" OFFSITE_SAUVEGARDES="$tmp/lab/sauvegardes" OFFSITE_RESTORE_SCRIPT="$tmp/restore_stub.sh"
export OFFSITE_MOUNT_CMD="$bin/mount" OFFSITE_DATE="2026-10-11"
unset OFFSITE_NOTIFIER OFFSITE_GARDER_RECENTES OFFSITE_GARDER_MOIS OFFSITE_AGE_MAX_JOURS OFFSITE_RAPPORTS_GARDER OFFSITE_LIBRE_KO
LAB="$OFFSITE_DONNEES"; SAUV="$OFFSITE_SAUVEGARDES"; ETAT="$LAB/offsite"

faire_volume() { # fichier uuid nom montage chiffre interne reseau verrouille   (booléens true/false ; montage vide = non monté)
  { echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "<key>VolumeUUID</key><string>$2</string><key>VolumeName</key><string>$3</string>"
    [ -n "$4" ] && echo "<key>MountPoint</key><string>$4</string>"
    echo "<key>FilesystemType</key><string>apfs</string>"
    echo "<key>FileVault</key><$5/><key>Internal</key><$6/><key>NetworkVolume</key><$7/><key>Locked</key><$8/>"
    echo '</dict></plist>'; } > "$1"
}
lance() { # arguments du script (stdin = $ENTREE si définie) : $OUT et $code ; la sortie va aussi dans $ALL
  if [ -n "${ENTREE+x}" ]; then bash "$SCRIPT" "$@" > "$tmp/s" 2>&1 <<<"$ENTREE"; code=$?
  else bash "$SCRIPT" "$@" > "$tmp/s" 2>&1 < /dev/null; code=$?; fi
  cat "$tmp/s" >> "$ALL"
}
arbre() { (cd "$1" 2>/dev/null && find . | LC_ALL=C sort | while IFS= read -r f; do [ -f "$f" ] && echo "$f $(cksum < "$f")" || echo "$f"; done); }

# --- Décor : sauvegardes locales (ordinaires, étiquetée, protégée) ---------------------------------------------------------
for jour in 09 10 11; do
  mkdir -p "$SAUV/db-2026-10-$jour"
  for s in knowledge cases flow; do echo "$SENT $jour $s" > "$SAUV/db-2026-10-$jour/$s.dump"; done
done
mkdir -p "$SAUV/db-2026-10-11-matin"; echo "$SENT etiquetee" > "$SAUV/db-2026-10-11-matin/flow.dump"
mkdir -p "$SAUV/bmad-memory-2026-10-07/sous"; echo "$SENT protegee" > "$SAUV/bmad-memory-2026-10-07/sous/$NOMFICHIER.md"
mkdir -p "$SAUV/bmad-memory-2026-10-10/sous dossier"
echo "$SENT a" > "$SAUV/bmad-memory-2026-10-10/$NOMFICHIER.md"; echo "$SENT b" > "$SAUV/bmad-memory-2026-10-10/sous dossier/autre $NOMFICHIER.md"
chmod 644 "$SAUV/bmad-memory-2026-10-10/$NOMFICHIER.md"
mkdir -p "$SAUV/divers-migration-veille"; echo "$SENT" > "$SAUV/divers-migration-veille/x"
avant_sauvegardes="$(arbre "$SAUV")"

# --- Décor : volumes -------------------------------------------------------------------------------------------------------
V="$tmp/Volumes"; mkdir -p "$V/ENC" "$V/NOENC" "$V/INTERNE" "$V/RESEAU" "$V/AUTRE" "$V/VERROUILLE"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" true false false false
faire_volume "$FX/volumes/noenc.plist" "BBBBBBBB-2222" "Clair" "$V/NOENC" false false false false
faire_volume "$FX/volumes/interne.plist" "CCCCCCCC-3333" "Interne" "$V/INTERNE" true true false false
faire_volume "$FX/volumes/reseau.plist" "DDDDDDDD-4444" "Reseau" "$V/RESEAU" true false true false
faire_volume "$FX/volumes/autre.plist" "EEEEEEEE-5555-AUTRE" "$NOMDISQUE" "$V/AUTRE" true false false false   # même nom, autre identifiant
mkdir -p "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Disque"; SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Disque"
faire_volume "$FX/volumes/sync.plist" "FFFFFFFF-6666" "Synchro" "$SYNC" true false false false
mkdir -p "$tmp/depot/.git" "$tmp/depot/vol"
faire_volume "$FX/volumes/git.plist" "11111111-7777" "Depot" "$tmp/depot/vol" true false false false

# ===========================================================================================================================
# Aide, usage
# ===========================================================================================================================
lance --help
verifie "aide : code 0 et les sous-commandes sont décrites" "$([ $code -eq 0 ] && grep -q 'restore-test' "$tmp/s" && grep -q 'setup' "$tmp/s"; echo $?)"
lance bidon
verifie "sous-commande inconnue : code 2" "$([ $code -eq 2 ]; echo $?)"
lance
verifie "sans sous-commande : code 2" "$([ $code -eq 2 ]; echo $?)"
lance copy --bidon
verifie "option inconnue de copy : code 2" "$([ $code -eq 2 ]; echo $?)"
lance restore-test --bidon
verifie "option inconnue de restore-test : code 2" "$([ $code -eq 2 ]; echo $?)"

# ===========================================================================================================================
# Non configuré
# ===========================================================================================================================
: > "$FAUX_LOG"
avant_volume="$(arbre "$V/ENC")"
lance copy
verifie "non configuré : phrase et code 2" "$([ $code -eq 2 ] && grep -q 'disque hors du Mac non configuré : lancer setup' "$tmp/s"; echo $?)"
verifie "non configuré : rien d'écrit (ni dossier d'état, ni volume), aucun appel à l'utilitaire de disque" "$([ ! -e "$ETAT" ] && [ "$avant_volume" = "$(arbre "$V/ENC")" ] && [ ! -s "$FAUX_LOG" ]; echo $?)"
lance restore-test
verifie "non configuré : restore-test code 2" "$([ $code -eq 2 ] && grep -q 'lancer setup' "$tmp/s"; echo $?)"
lance status
verifie "status sans configuration : code 0, aucun état, rien écrit" "$([ $code -eq 0 ] && grep -q 'aucun état enregistré' "$tmp/s" && [ ! -e "$ETAT" ]; echo $?)"

# ===========================================================================================================================
# setup : refus
# ===========================================================================================================================
ENTREE="y"
lance setup "$V/NOENC"
verifie "setup volume non chiffré : phrase, code 2, rien enregistré" "$([ $code -eq 2 ] && grep -q 'volume non chiffré : refusé' "$tmp/s" && [ ! -e "$ETAT/configuration" ] && [ ! -e "$V/NOENC/pmzilla-offsite" ]; echo $?)"
lance setup "$V/INTERNE"
verifie "setup disque interne : phrase, code 2, rien enregistré" "$([ $code -eq 2 ] && grep -q 'disque interne : refusé' "$tmp/s" && [ ! -e "$ETAT/configuration" ] && [ ! -e "$V/INTERNE/pmzilla-offsite" ]; echo $?)"
lance setup "$V/RESEAU"
verifie "setup volume réseau (propriété) : phrase, code 2, rien enregistré" "$([ $code -eq 2 ] && grep -q 'volume réseau : refusé' "$tmp/s" && [ ! -e "$ETAT/configuration" ] && [ ! -e "$V/RESEAU/pmzilla-offsite" ]; echo $?)"
mkdir -p "$V/PARTAGE"; sed "s|$V/RESEAU|$V/PARTAGE|" "$bin/mount" > "$bin/mount.new"; mv "$bin/mount.new" "$bin/mount"; chmod +x "$bin/mount"
lance setup "$V/PARTAGE"
verifie "setup volume réseau inconnu de l'utilitaire de disque (repli sur la table des montages) : code 2" "$([ $code -eq 2 ] && grep -q 'volume réseau : refusé' "$tmp/s"; echo $?)"
lance setup "$SYNC"
verifie "setup dossier synchronisé : phrase, code 2, rien enregistré" "$([ $code -eq 2 ] && grep -q 'dossier synchronisé ou dépôt Git : refusé' "$tmp/s" && [ ! -e "$ETAT/configuration" ] && [ ! -e "$SYNC/pmzilla-offsite" ]; echo $?)"
lance setup "$tmp/depot/vol"
verifie "setup dans un dépôt Git : phrase, code 2, rien enregistré" "$([ $code -eq 2 ] && grep -q 'dossier synchronisé ou dépôt Git : refusé' "$tmp/s" && [ ! -e "$ETAT/configuration" ] && [ ! -e "$tmp/depot/vol/pmzilla-offsite" ]; echo $?)"
lance setup "$tmp/inexistant"
verifie "setup point de montage inexistant : code 2" "$([ $code -eq 2 ]; echo $?)"
lance setup
verifie "setup sans argument : code 2" "$([ $code -eq 2 ]; echo $?)"
ENTREE="n"
lance setup "$V/ENC"
verifie "setup refusé par l'utilisateur : code 2, rien enregistré, le nom du volume a été montré avant la question" "$([ $code -eq 2 ] && grep -q "$NOMDISQUE" "$tmp/s" && [ ! -e "$ETAT/configuration" ] && [ ! -e "$V/ENC/pmzilla-offsite" ]; echo $?)"
verifie "setup refusé : aucune écriture dans l'état ni sur le volume" "$([ ! -e "$ETAT" ]; echo $?)"

# ===========================================================================================================================
# setup : confirmé
# ===========================================================================================================================
ENTREE="y"
lance setup "$V/ENC"
verifie "setup confirmé : code 0" "$code"
verifie "setup : configuration en 600 avec l'identifiant, dossier d'état en 700" "$([ "$(mode "$ETAT/configuration")" = 600 ] && [ "$(mode "$ETAT")" = 700 ] && grep -q "$ID" "$ETAT/configuration"; echo $?)"
verifie "setup : dossier de copies à la racine du volume, en 700" "$([ -d "$V/ENC/pmzilla-offsite" ] && [ "$(mode "$V/ENC/pmzilla-offsite")" = 700 ]; echo $?)"
verifie "setup : l'identifiant n'est pas affiché" "$(absent "$ID" "$tmp/s")"
unset ENTREE
verifie "setup : le script ne contient pas l'identifiant du volume (aucun fichier suivi ne le porte)" "$(absent "$ID" "$SCRIPT")"
# Après setup, plus aucune sortie ne doit montrer le nom du volume : on repart d'un journal propre pour la vérification finale.
: > "$ALL"

# ===========================================================================================================================
# copy : nominal, modes, déjà présente, étiquetée jamais copiée
# ===========================================================================================================================
: > "$FAUX_LOG"
( umask 000; bash "$SCRIPT" copy > "$tmp/s" 2>&1; echo $? > "$tmp/code" ); code=$(cat "$tmp/code"); cat "$tmp/s" >> "$ALL"
verifie "copy nominale : code 0" "$code"
verifie "copy : la dernière sauvegarde ordinaire de la base est copiée avec son manifeste" "$([ -f "$V/ENC/pmzilla-offsite/db/db-2026-10-11/knowledge.dump" ] && [ -f "$V/ENC/pmzilla-offsite/db/db-2026-10-11/MANIFESTE.sha256" ]; echo $?)"
verifie "copy : la sauvegarde étiquetée n'est pas copiée, ni les anciennes, ni les autres dossiers" "$([ ! -e "$V/ENC/pmzilla-offsite/db/db-2026-10-11-matin" ] && [ ! -e "$V/ENC/pmzilla-offsite/db/db-2026-10-10" ] && [ ! -e "$V/ENC/pmzilla-offsite/divers-migration-veille" ]; echo $?)"
verifie "copy : le sanctum ordinaire le plus récent est copié, pas la sauvegarde protégée" "$([ -f "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-10/MANIFESTE.sha256" ] && [ ! -e "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-07" ]; echo $?)"
verifie "copy : « copie créée » pour chaque série, avec les nombres de fichiers" "$(grep -q 'copie créée : db-2026-10-11 (3 fichiers' "$tmp/s" && grep -q 'copie créée : bmad-memory-2026-10-10 (2 fichiers' "$tmp/s"; echo $?)"
verifie "copy : dossiers en 700 et fichiers en 600, quel que soit l'umask" "$([ -z "$(find "$V/ENC/pmzilla-offsite" -type d ! -perm 700)" ] && [ -z "$(find "$V/ENC/pmzilla-offsite" -type f ! -perm 600)" ]; echo $?)"
verifie "copy : le manifeste liste somme, taille et chemin de chaque fichier (sous-dossiers compris)" "$([ "$(wc -l < "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-10/MANIFESTE.sha256" | tr -d ' ')" = 2 ] && grep -Eq "^[0-9a-f]{64}	[0-9]+	sous dossier/autre " "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-10/MANIFESTE.sha256"; echo $?)"
verifie "copy : les sauvegardes locales ne sont pas modifiées" "$([ "$avant_sauvegardes" = "$(arbre "$SAUV")" ]; echo $?)"
verifie "copy : le journal de l'utilitaire de disque ne contient que des « info -plist »" "$(! grep '^diskutil' "$FAUX_LOG" | grep -vq '^diskutil info -plist '; echo $?)"
verifie "copy : l'état enregistre la dernière réussite et les dernières copies" "$(grep -q '^copy derniere_reussite=2026-10-11 resultat=ok' "$ETAT/statut" && grep -q '^serie-db derniere_copie=db-2026-10-11' "$ETAT/statut" && [ "$(mode "$ETAT/statut")" = 600 ]; echo $?)"
verifie "copy : aucun nom de fichier d'une copie, aucune sentinelle, ni le nom ni l'identifiant du volume dans la sortie" "$(! grep -q -e "$NOMFICHIER" -e "$SENT" -e "$NOMDISQUE" -e "$ID" "$tmp/s"; echo $?)"
avant_disque="$(arbre "$V/ENC/pmzilla-offsite")"
lance copy
verifie "copy déjà présente : « déjà présente » pour chaque série, code 0, rien d'écrit" "$([ $code -eq 0 ] && grep -q 'déjà présente : db-2026-10-11' "$tmp/s" && grep -q 'déjà présente : bmad-memory-2026-10-10' "$tmp/s" && [ "$avant_disque" = "$(arbre "$V/ENC/pmzilla-offsite")" ]; echo $?)"

# --- Copie interrompue : un dossier temporaire laissé est retiré, jamais compté, et la copie est refaite
mkdir -p "$SAUV/db-2026-10-12"; for s in knowledge cases flow; do echo "$SENT 12 $s" > "$SAUV/db-2026-10-12/$s.dump"; done
mkdir -p "$V/ENC/pmzilla-offsite/db/.partiel-db-2026-10-12"; echo "demi-fichier" > "$V/ENC/pmzilla-offsite/db/.partiel-db-2026-10-12/knowledge.dump"
mkdir -p "$V/ENC/pmzilla-offsite/sanctum/.partiel-bmad-memory-2026-10-09"
lance copy
verifie "copie interrompue : temporaires retirés, nouvelle copie complète créée, code 0" "$([ $code -eq 0 ] && [ ! -e "$V/ENC/pmzilla-offsite/db/.partiel-db-2026-10-12" ] && [ ! -e "$V/ENC/pmzilla-offsite/sanctum/.partiel-bmad-memory-2026-10-09" ] && [ -f "$V/ENC/pmzilla-offsite/db/db-2026-10-12/MANIFESTE.sha256" ] && grep -q 'copie créée : db-2026-10-12' "$tmp/s"; echo $?)"
verifie "copie interrompue : la copie du jour contient les vrais fichiers" "$([ "$(cat "$V/ENC/pmzilla-offsite/db/db-2026-10-12/knowledge.dump")" = "$SENT 12 knowledge" ]; echo $?)"

# --- Copie corrompue pendant l'écriture : jamais prise pour complète
mkdir -p "$SAUV/db-2026-10-13"; for s in knowledge cases flow; do echo "$SENT 13 $s" > "$SAUV/db-2026-10-13/$s.dump"; done
FAUX_CP_CORROMPT=1 lance copy
verifie "copie corrompue : « copie incomplète », code 1, ni dossier temporaire ni copie finale" "$([ $code -eq 1 ] && grep -q 'copie incomplète : db-2026-10-13' "$tmp/s" && [ ! -e "$V/ENC/pmzilla-offsite/db/db-2026-10-13" ] && [ -z "$(ls -a "$V/ENC/pmzilla-offsite/db" | grep '^.partiel')" ]; echo $?)"
verifie "copie corrompue : l'état enregistre l'échec sans effacer la dernière réussite" "$(grep -q '^copy derniere_reussite=2026-10-11 resultat=echec' "$ETAT/statut"; echo $?)"
verifie "copie corrompue : pas de rotation après un échec (les copies précédentes restent)" "$([ -d "$V/ENC/pmzilla-offsite/db/db-2026-10-11" ] && [ -d "$V/ENC/pmzilla-offsite/db/db-2026-10-12" ]; echo $?)"
lance copy
verifie "copie reprise sans corruption : copie du 2026-10-13 créée, code 0" "$([ $code -eq 0 ] && [ -f "$V/ENC/pmzilla-offsite/db/db-2026-10-13/MANIFESTE.sha256" ]; echo $?)"

# --- Place insuffisante
mkdir -p "$SAUV/db-2026-10-14"; for s in knowledge cases flow; do echo "$SENT 14 $s" > "$SAUV/db-2026-10-14/$s.dump"; done
avant_disque="$(arbre "$V/ENC/pmzilla-offsite")"
OFFSITE_LIBRE_KO=10 lance copy
verifie "place insuffisante : phrase, code 1, rien d'écrit sur le disque" "$([ $code -eq 1 ] && grep -q 'place insuffisante sur le disque' "$tmp/s" && [ "$avant_disque" = "$(arbre "$V/ENC/pmzilla-offsite")" ]; echo $?)"
rm -rf "$SAUV/db-2026-10-14" "$SAUV/db-2026-10-13" "$SAUV/db-2026-10-12" "$V/ENC/pmzilla-offsite/db/db-2026-10-13" "$V/ENC/pmzilla-offsite/db/db-2026-10-12"

# ===========================================================================================================================
# Rotation : N récentes plus la dernière de chacun des M derniers mois
# ===========================================================================================================================
serie="$V/ENC/pmzilla-offsite/db"
for d in 2026-08-05 2026-08-20 2026-09-03 2026-09-15 2026-10-01 2026-10-02; do mkdir -p "$serie/db-$d"; echo x > "$serie/db-$d/f"; done
mkdir -p "$serie/db-2026-07-01-etiquette" "$serie/autre-dossier"; echo x > "$serie/autre-dossier/f"
OFFSITE_GARDER_RECENTES=2 OFFSITE_GARDER_MOIS=2 lance copy
verifie "rotation : les copies hors rétention sont supprimées, une ligne chacune" "$([ $code -eq 0 ] && grep -qx 'copie supprimée : db-2026-10-01' "$tmp/s" && grep -qx 'copie supprimée : db-2026-09-03' "$tmp/s" && grep -qx 'copie supprimée : db-2026-08-20' "$tmp/s" && grep -qx 'copie supprimée : db-2026-08-05' "$tmp/s"; echo $?)"
verifie "rotation : sont gardées les 2 récentes (10-11, 10-02) et la dernière de chacun des 2 derniers mois (octobre : 10-11, septembre : 09-15)" "$([ -d "$serie/db-2026-10-11" ] && [ -d "$serie/db-2026-10-02" ] && [ -d "$serie/db-2026-09-15" ] && [ ! -e "$serie/db-2026-10-01" ] && [ ! -e "$serie/db-2026-09-03" ] && [ ! -e "$serie/db-2026-08-20" ] && [ ! -e "$serie/db-2026-08-05" ]; echo $?)"
verifie "rotation : un dossier étranger ou étiqueté n'est ni compté, ni supprimé, ni cité" "$([ -d "$serie/db-2026-07-01-etiquette" ] && [ -d "$serie/autre-dossier" ] && ! grep -q -e 'autre-dossier' -e 'etiquette' "$tmp/s"; echo $?)"
verifie "rotation : la copie la plus récente n'est jamais supprimée" "$([ -f "$serie/db-2026-10-11/MANIFESTE.sha256" ]; echo $?)"
avant_disque="$(arbre "$V/ENC/pmzilla-offsite")"
for valeur in 0 -1 mot; do
  OFFSITE_GARDER_RECENTES="$valeur" lance copy
  verifie "rétention invalide ($valeur) : code 2, rien créé ni supprimé" "$([ $code -eq 2 ] && [ "$avant_disque" = "$(arbre "$V/ENC/pmzilla-offsite")" ]; echo $?)"
done
OFFSITE_GARDER_MOIS=0 lance copy
verifie "rétention mensuelle invalide : code 2" "$([ $code -eq 2 ]; echo $?)"
rm -rf "$serie/db-2026-07-01-etiquette" "$serie/autre-dossier" "$serie/db-2026-10-02" "$serie/db-2026-09-15"

# ===========================================================================================================================
# Sauvegarde de sanctum protégée : seulement sur demande, une fois, jamais tournée
# ===========================================================================================================================
lance copy --include-protected
verifie "--include-protected : la sauvegarde protégée est copiée une fois" "$([ $code -eq 0 ] && grep -q 'copie créée : bmad-memory-2026-10-07' "$tmp/s" && [ -f "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-07/MANIFESTE.sha256" ]; echo $?)"
lance copy --include-protected
verifie "--include-protected : seconde fois « déjà présente »" "$([ $code -eq 0 ] && grep -q 'déjà présente : bmad-memory-2026-10-07' "$tmp/s"; echo $?)"
mkdir -p "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-09-01"; echo x > "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-09-01/f"
OFFSITE_GARDER_RECENTES=1 OFFSITE_GARDER_MOIS=1 lance copy --include-protected
verifie "rotation du sanctum : la sauvegarde protégée n'est jamais supprimée, l'ancienne l'est" "$([ -d "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-07" ] && [ ! -e "$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-09-01" ] && grep -qx 'copie supprimée : bmad-memory-2026-09-01' "$tmp/s"; echo $?)"

# ===========================================================================================================================
# Disque absent ou verrouillé, autre disque de même nom
# ===========================================================================================================================
mv "$FX/volumes/enc.plist" "$FX/debranches/enc.plist"
avant_autre="$(arbre "$V/AUTRE")"; : > "$OSA_LOG"
lance copy
verifie "disque débranché, même nom sur un autre disque : phrase, code 3, rien n'est écrit sur l'autre disque" "$([ $code -eq 3 ] && grep -q 'disque absent ou verrouillé : copie reportée' "$tmp/s" && [ "$avant_autre" = "$(arbre "$V/AUTRE")" ] && [ ! -e "$V/AUTRE/pmzilla-offsite" ]; echo $?)"
verifie "disque débranché : lancement à la main, aucune notification" "$([ ! -s "$OSA_LOG" ]; echo $?)"
verifie "disque débranché : l'état note « reporte » sans effacer la dernière réussite" "$(grep -q '^copy derniere_reussite=2026-10-11 resultat=reporte' "$ETAT/statut"; echo $?)"
OFFSITE_NOTIFIER=1 OFFSITE_DATE=2026-10-13 lance copy
verifie "disque débranché, dernière copie récente (2 jours) : code 3, aucune notification" "$([ $code -eq 3 ] && [ ! -s "$OSA_LOG" ]; echo $?)"
OFFSITE_NOTIFIER=1 OFFSITE_DATE=2026-10-20 lance copy
verifie "disque débranché, dernière copie ancienne (9 jours) : une notification qui donne le nombre de jours" "$([ $code -eq 3 ] && [ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ] && grep -q 'aucune copie hors du Mac depuis 9 jours' "$OSA_LOG"; echo $?)"
OFFSITE_NOTIFIER=1 OFFSITE_DATE=2026-10-20 lance copy
verifie "disque débranché, même jour : pas de seconde notification" "$([ $code -eq 3 ] && [ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ]; echo $?)"
OFFSITE_NOTIFIER=1 OFFSITE_DATE=2026-10-21 lance copy
verifie "disque débranché, jour suivant : une nouvelle notification" "$([ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 2 ] && grep -q 'depuis 10 jours' "$OSA_LOG"; echo $?)"
OFFSITE_NOTIFIER=1 OFFSITE_AGE_MAX_JOURS=30 OFFSITE_DATE=2026-10-30 lance copy
verifie "âge de notification réglable (30 jours) : 19 jours, pas de notification" "$([ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 2 ]; echo $?)"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "" true false false true
OFFSITE_DATE=2026-10-11 lance copy
verifie "disque présent mais verrouillé : code 3" "$([ $code -eq 3 ] && grep -q 'disque absent ou verrouillé : copie reportée' "$tmp/s"; echo $?)"
verifie "disque absent : aucune sortie ne montre le nom du volume ni son identifiant" "$(! grep -q -e "$NOMDISQUE" -e "$ID" "$ALL"; echo $?)"

# Jamais réussi : notification qui le dit, une fois par jour
mv "$ETAT/statut" "$tmp/statut.sauve"; rm -f "$ETAT/notification-absence"; : > "$OSA_LOG"
OFFSITE_NOTIFIER=1 lance copy
verifie "jamais de copie réussie : une notification qui le dit" "$([ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ] && grep -q 'aucune copie hors du Mac réussie à ce jour' "$OSA_LOG"; echo $?)"
mv "$tmp/statut.sauve" "$ETAT/statut"

# ===========================================================================================================================
# Disque revenu : refus du disque non chiffré sous le planificateur
# ===========================================================================================================================
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" true false false false
: > "$OSA_LOG"
OFFSITE_NOTIFIER=1 lance copy
verifie "copie réussie sous le planificateur : aucune notification" "$([ $code -eq 0 ] && [ ! -s "$OSA_LOG" ]; echo $?)"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" false false false false
OFFSITE_NOTIFIER=1 lance copy
verifie "volume devenu non chiffré sous le planificateur : code 2, une notification avec la cause et le code" "$([ $code -eq 2 ] && grep -q 'volume non chiffré : refusé' "$tmp/s" && [ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ] && grep -q 'code 2' "$OSA_LOG" && grep -q 'volume non chiffré' "$OSA_LOG"; echo $?)"
: > "$OSA_LOG"
lance copy
verifie "volume non chiffré, lancement à la main : code 2 et aucune notification" "$([ $code -eq 2 ] && [ ! -s "$OSA_LOG" ]; echo $?)"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" true true false false
lance copy
verifie "volume devenu interne : « disque interne : refusé », code 2" "$([ $code -eq 2 ] && grep -q 'disque interne : refusé' "$tmp/s"; echo $?)"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" true false true false
lance copy
verifie "volume devenu réseau : « volume réseau : refusé », code 2" "$([ $code -eq 2 ] && grep -q 'volume réseau : refusé' "$tmp/s"; echo $?)"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" true false false false
: > "$OSA_LOG"
mkdir -p "$SAUV/db-2026-10-15"; for s in knowledge cases flow; do echo "$SENT 15 $s" > "$SAUV/db-2026-10-15/$s.dump"; done
OFFSITE_NOTIFIER=1 OFFSITE_LIBRE_KO=10 lance copy
verifie "place insuffisante sous le planificateur : code 1, une notification avec le code 1" "$([ $code -eq 1 ] && [ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ] && grep -q 'code 1' "$OSA_LOG"; echo $?)"
rm -rf "$SAUV/db-2026-10-15"

# ===========================================================================================================================
# restore-test
# ===========================================================================================================================
: > "$FAUX_LOG"; : > "$OSA_LOG"
lance restore-test
verifie "restore-test : code 0 et dernière ligne « test de restauration hors du Mac : OK »" "$([ $code -eq 0 ] && [ "$(tail -1 "$tmp/s")" = "test de restauration hors du Mac : OK" ]; echo $?)"
verifie "restore-test : le script de restauration est appelé sur la copie de la base du disque (--backup)" "$(grep -q "^restore --backup .*/pmzilla-offsite/db/db-2026-10-11\$" "$FAUX_LOG"; echo $?)"
verifie "restore-test : docker ne reçoit que les sondes (info, ps, pg_isready) : jamais de démarrage, d'arrêt ou d'écriture de la vraie base" "$(! grep '^docker' "$FAUX_LOG" | grep -Eq '^docker (compose )?(up|start|stop|restart|down|run|rm|cp|kill)( |$)|exec -T db (psql|pg_dump|pg_restore)'; echo $?)"
verifie "restore-test : les comptes (noms de tables et nombres) sont reportés, la ligne parasite non" "$(grep -q 'knowledge.books' "$tmp/s" && grep -q 'flow.issues' "$tmp/s" && ! grep -q -e "$SENT" -e 'valeur-de-table' "$tmp/s"; echo $?)"
verifie "restore-test : rapport du mois en 600, dossier en 700" "$([ "$(mode "$ETAT/rapports/restore-2026-10.txt")" = 600 ] && [ "$(mode "$ETAT/rapports")" = 700 ]; echo $?)"
verifie "restore-test : le rapport ne contient que les champs prévus (date, copies, sommes, comptes, sanctum, résultat, code)" "$(! grep -Ev '^(Rapport du test|date : |copie de la base testée : db-|copie du sanctum testée : |somme de contrôle (base|sanctum) : OK \([0-9]+ fichiers\)|restauration de la base \(db_restore_test.sh, code [0-9]+\) :|  +[A-Za-z0-9_]+\.[A-Za-z0-9_]+ +[0-9]+ / [0-9]+ +OK|  +RESTAURATION OK, |sanctum : [0-9]+ fichiers, manifeste : [0-9]+|résultat : OK|code : 0)' "$ETAT/rapports/restore-2026-10.txt" | grep -q .; echo $?)"
verifie "restore-test : l'état enregistre la date et le résultat du test" "$(grep -q '^restore-test derniere_reussite=2026-10-11 resultat=ok' "$ETAT/statut"; echo $?)"
verifie "restore-test : sanctum, nombre de fichiers de la copie égal à celui du manifeste" "$(grep -q 'sanctum : 2 fichiers, manifeste : 2' "$tmp/s"; echo $?)"
verifie "restore-test : succès, aucune notification" "$([ ! -s "$OSA_LOG" ]; echo $?)"
: > "$FAUX_LOG"
lance restore-test
verifie "restore-test déjà fait ce mois : « test du mois déjà fait », code 0, rien lancé" "$([ $code -eq 0 ] && grep -q 'test du mois déjà fait' "$tmp/s" && [ ! -s "$FAUX_LOG" ]; echo $?)"
lance restore-test --force
verifie "restore-test --force : refait le test même si le mois est fait" "$([ $code -eq 0 ] && grep -q 'restore --backup' "$FAUX_LOG"; echo $?)"

# Base réelle arrêtée : le test est reporté, la base n'est jamais démarrée
: > "$FAUX_LOG"
FAUX_DB_ARRETEE=1 lance restore-test --force
verifie "vraie base arrêtée : « vraie base indisponible : test reporté », code 3" "$([ $code -eq 3 ] && grep -q 'vraie base indisponible : test reporté' "$tmp/s"; echo $?)"
verifie "vraie base arrêtée : rien n'est démarré, aucun script de restauration lancé" "$(! grep -Eq '^docker (compose )?(up|start|stop|restart|down|run|rm|cp|kill)( |$)|^restore' "$FAUX_LOG"; echo $?)"

# Copie altérée : somme de contrôle différente, aucun conteneur
: > "$FAUX_LOG"
copie="$V/ENC/pmzilla-offsite/db/db-2026-10-11"
echo "altération" >> "$copie/flow.dump"
lance restore-test --force
verifie "copie altérée (contenu) : « somme de contrôle différente : db-2026-10-11 », code 1" "$([ $code -eq 1 ] && grep -q 'somme de contrôle différente : db-2026-10-11' "$tmp/s"; echo $?)"
verifie "copie altérée : aucun conteneur démarré, script de restauration non lancé" "$(! grep -Eq '^restore|^docker (compose )?run( |$)' "$FAUX_LOG"; echo $?)"
verifie "copie altérée : l'état garde l'échec et le dernier succès, un rapport d'échec existe" "$(grep -q '^restore-test derniere_reussite=2026-10-11 resultat=echec' "$ETAT/statut" && grep -q '^code : 1' "$ETAT/rapports/restore-2026-10.txt"; echo $?)"
echo "$SENT 11 flow" > "$copie/flow.dump"
cp "$SAUV/db-2026-10-11/flow.dump" "$copie/flow.dump"
echo "fichier en trop" > "$copie/en-trop.dump"
lance restore-test --force
verifie "fichier en trop hors du manifeste : somme de contrôle différente, code 1" "$([ $code -eq 1 ] && grep -q 'somme de contrôle différente' "$tmp/s"; echo $?)"
rm -f "$copie/en-trop.dump"; mv "$copie/cases.dump" "$tmp/cases.sauve"
lance restore-test --force
verifie "fichier manquant : somme de contrôle différente, code 1" "$([ $code -eq 1 ] && grep -q 'somme de contrôle différente' "$tmp/s"; echo $?)"
mv "$tmp/cases.sauve" "$copie/cases.dump"
sanctum="$V/ENC/pmzilla-offsite/sanctum/bmad-memory-2026-10-10"
mv "$sanctum/$NOMFICHIER.md" "$tmp/sanctum.sauve"
lance restore-test --force
verifie "sanctum : fichier manquant (écart de nombre) : code 1, sans nom de fichier" "$([ $code -eq 1 ] && grep -q 'somme de contrôle différente : bmad-memory-2026-10-10' "$tmp/s" && ! grep -q "$NOMFICHIER" "$tmp/s"; echo $?)"
mv "$tmp/sanctum.sauve" "$sanctum/$NOMFICHIER.md"
lance restore-test --force
verifie "copies remises en état : le test repasse" "$code"

# Échec du script de restauration : code 1, phrase, notification
: > "$OSA_LOG"
FAUX_RESTORE_CODE=1 OFFSITE_NOTIFIER=1 lance restore-test --force
verifie "échec du script de restauration : code 1 et « test de restauration hors du Mac : échec (code 1) »" "$([ $code -eq 1 ] && grep -q 'test de restauration hors du Mac : échec (code 1)' "$tmp/s"; echo $?)"
verifie "échec du test sous le planificateur : une notification, avec le code" "$([ "$(wc -l < "$OSA_LOG" | tr -d ' ')" = 1 ] && grep -q 'test de restauration hors du Mac : échec (code 1)' "$OSA_LOG"; echo $?)"

# Disque absent ou verrouillé
mv "$FX/volumes/enc.plist" "$FX/debranches/enc.plist"
: > "$FAUX_LOG"
lance restore-test --force
verifie "restore-test disque débranché : « test reporté », code 3, rien lancé" "$([ $code -eq 3 ] && grep -q 'disque absent ou verrouillé : test reporté' "$tmp/s" && ! grep -q -e '^restore' -e '^docker' "$FAUX_LOG"; echo $?)"
mv "$FX/debranches/enc.plist" "$FX/volumes/enc.plist"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" false false false false
lance restore-test --force
verifie "restore-test volume non chiffré : code 2 avant toute lecture" "$([ $code -eq 2 ] && grep -q 'volume non chiffré : refusé' "$tmp/s"; echo $?)"
faire_volume "$FX/volumes/enc.plist" "$ID" "$NOMDISQUE" "$V/ENC" true false false false

# Rétention des rapports
for m in 01 02 03 04 05; do echo "ancien" > "$ETAT/rapports/restore-2026-$m.txt"; done
OFFSITE_RAPPORTS_GARDER=2 lance restore-test --force
verifie "rapports : les plus anciens sont supprimés, les 2 plus récents restent" "$([ $code -eq 0 ] && [ -f "$ETAT/rapports/restore-2026-10.txt" ] && [ -f "$ETAT/rapports/restore-2026-05.txt" ] && [ ! -e "$ETAT/rapports/restore-2026-04.txt" ] && [ ! -e "$ETAT/rapports/restore-2026-01.txt" ]; echo $?)"

# ===========================================================================================================================
# status : lecture seule, sans rien monter
# ===========================================================================================================================
avant_etat="$(arbre "$ETAT")"; : > "$FAUX_LOG"
lance status
verifie "status : code 0, dernières copies et âge affichés" "$([ $code -eq 0 ] && grep -q '^copy ' "$tmp/s" && grep -q '^restore-test ' "$tmp/s" && grep -q 'âge de la dernière copie (db) : 0 jours' "$tmp/s"; echo $?)"
verifie "status : aucun appel à l'utilitaire de disque, rien d'écrit" "$([ ! -s "$FAUX_LOG" ] && [ "$avant_etat" = "$(arbre "$ETAT")" ]; echo $?)"
OFFSITE_DATE=2026-10-15 lance status
verifie "status : l'âge suit la date du jour (copie du 2026-10-10 du sanctum : 5 jours)" "$(grep -q 'âge de la dernière copie (sanctum) : 5 jours' "$tmp/s"; echo $?)"

# ===========================================================================================================================
# Garanties transversales
# ===========================================================================================================================
code_script="$(grep -v '^[[:space:]]*#' "$SCRIPT")"
verifie "aucune commande réseau, copie distante, shell distant ni outil de nuage dans le script (commentaires exclus)" "$(! printf '%s\n' "$code_script" | grep -Eq '(^|[^A-Za-z0-9_-])(curl|wget|scp|sftp|ssh|rsync|nc|ncat|telnet|ftp|rclone|aws|gsutil|dig|nslookup|ping|git push)([^A-Za-z0-9_-]|$)'; echo $?)"
verifie "aucune adresse web dans le script" "$(! printf '%s\n' "$code_script" | grep -Eq 'https?://'; echo $?)"
verifie "aucun appel au Trousseau, à launchctl ni à une commande d'ouverture du disque dans le script" "$(! printf '%s\n' "$code_script" | grep -Eq '(security|launchctl|unlockVolume|mountDisk|mount |diskutil (mount|unlock|apfs))'; echo $?)"
verifie "le script n'utilise pas set -x" "$(! printf '%s\n' "$code_script" | grep -Eq 'set -[a-z]*x'; echo $?)"
verifie "le script applique umask 077" "$(printf '%s\n' "$code_script" | grep -q '^umask 077'; echo $?)"
verifie "aucune sentinelle, aucun nom de fichier d'une copie, ni nom ni identifiant du volume dans toutes les sorties" "$(! grep -q -e "$SENT" -e "$NOMFICHIER" -e "$NOMDISQUE" -e "$ID" "$ALL"; echo $?)"
verifie "aucune sentinelle ni nom de volume dans les notifications, les rapports et l'état" "$(! grep -rq -e "$SENT" -e "$NOMFICHIER" -e "$NOMDISQUE" -e "$ID" "$OSA_LOG" "$ETAT/rapports" "$ETAT/statut" "$ETAT/notification-absence"; echo $?)"
verifie "rien n'est écrit dans le dépôt par ces essais (aucun rapport ni état sous le dépôt)" "$([ -z "$(cd "$racine" && git status --porcelain -- Flux-Lab _bmad-output 2>/dev/null)" ]; echo $?)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
