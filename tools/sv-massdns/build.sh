#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_directory=$(mktemp -d "$here/.build.XXXXXX")
trap 'rm -rf "$build_directory"' EXIT HUP INT TERM
mkdir -p "$here/bin"
curl -fL --retry 3 --connect-timeout 30 https://codeload.github.com/blechschmidt/massdns/tar.gz/30c380908b4f9afd0931d3d83f85884844831846 -o "$build_directory/source.tar.gz"
printf '%s  %s\n' 5e8785174a6aacc8945bae568c5f8374dc5f3d71aefe9b006e0d59539b271b85 "$build_directory/source.tar.gz" | sha256sum -c -
tar -xzf "$build_directory/source.tar.gz" -C "$build_directory" --strip-components=1
make -C "$build_directory" 'PROJECT_FLAGS=-DMASSDNS_REVISION=\"30c380908b4f9afd0931d3d83f85884844831846\"'
install -m 0755 "$build_directory/bin/massdns" "$here/bin/massdns"
