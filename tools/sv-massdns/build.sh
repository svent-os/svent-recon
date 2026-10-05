#!/bin/sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rm -rf "$here/bin"; mkdir -p "$here/bin"
git clone --depth 1 https://github.com/blechschmidt/massdns "$here/.src" && make -C "$here/.src" && cp "$here/.src/bin/massdns" "$here/bin/" && rm -rf "$here/.src"
