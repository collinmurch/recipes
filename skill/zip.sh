#!/bin/sh
# Builds skill/recipes.zip for uploading to Claude or ChatGPT.
set -eu
cd "$(dirname "$0")"
rm -f recipes.zip
zip -qrX recipes.zip recipes -x '*.DS_Store'
echo "wrote skill/recipes.zip"
