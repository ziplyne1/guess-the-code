#!/usr/bin/env bash
# Downloads the two data files pwords.py needs (~20MB download, 56MB on disk).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
if [ ! -f data/cmudict.dict ]; then
  echo "fetching CMU pronouncing dictionary (syllable counts)..."
  curl -sL -o data/cmudict.dict \
    https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
fi
if [ ! -d data/wordnet ]; then
  echo "fetching WordNet 3.1 (definitions)..."
  curl -sL -o /tmp/wn31.tar.gz https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz
  tar xzf /tmp/wn31.tar.gz -C data
  mv data/dict data/wordnet
  rm -f /tmp/wn31.tar.gz
fi
echo "ready:"
ls -la data
