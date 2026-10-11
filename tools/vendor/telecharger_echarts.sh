#!/bin/zsh
# PMZilla Lab : télécharge Apache ECharts UNE FOIS, dans tools/vendor/ (versionné avec sa licence et son empreinte).
# Le tableau de bord (flow_board.py) lit ensuite ce fichier : aucun appel réseau à l'exécution, aucun CDN.
#
#   zsh tools/vendor/telecharger_echarts.sh              version par défaut (5.6.0)
#   zsh tools/vendor/telecharger_echarts.sh 5.6.0 [dossier]   version et dossier de destination (par défaut : ce dossier)
#
# Le paquet vient de npm (`npm pack`) ; son intégrité SHA-512 est comparée à celle du registre avant toute extraction.
# Sont écrits : echarts.min.js (bibliothèque complète, environ 1 Mo), LICENSE-echarts et NOTICE-echarts (Apache-2.0),
# echarts.sha256 (empreinte SHA-256 que flow_board.py vérifie à chaque génération) et echarts.version.
set -eu

VERSION="${1:-5.6.0}"
DEST="${2:-${0:A:h}}"
command -v npm >/dev/null || { echo "npm est introuvable (Node est installé avec BMAD : voir installation.md)." >&2; exit 1; }
[[ "$VERSION" =~ '^[0-9]+\.[0-9]+\.[0-9]+$' ]] || { echo "Version attendue : 5.6.0" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cd "$tmp"
npm pack "echarts@$VERSION" --silent >/dev/null
archive="echarts-$VERSION.tgz"
attendu=$(npm view "echarts@$VERSION" dist.integrity)
reel="sha512-$(openssl dgst -sha512 -binary "$archive" | openssl base64 -A)"
if [[ "$attendu" != "$reel" ]]; then
  echo "Intégrité de $archive non conforme au registre npm : rien n'est installé." >&2
  exit 1
fi
tar xzf "$archive" package/dist/echarts.min.js package/LICENSE package/NOTICE
mkdir -p "$DEST"
cp package/dist/echarts.min.js "$DEST/echarts.min.js"
cp package/LICENSE "$DEST/LICENSE-echarts"
cp package/NOTICE "$DEST/NOTICE-echarts"
(cd "$DEST" && shasum -a 256 echarts.min.js > echarts.sha256)
echo "$VERSION" > "$DEST/echarts.version"
echo "ECharts $VERSION installé dans $DEST"
echo "SHA-256 : $(cut -d' ' -f1 "$DEST/echarts.sha256")"
echo "Licence : Apache-2.0 (LICENSE-echarts, NOTICE-echarts). Pense à commiter ces fichiers."
