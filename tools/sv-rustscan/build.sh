#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_directory=$(mktemp -d "$here/.build.XXXXXX")
trap 'rm -rf "$build_directory"' EXIT HUP INT TERM
mkdir -p "$here/bin"
cargo install rustscan --version 2.4.1 --locked --jobs "${SVENT_BUILD_JOBS:-2}" --root "$build_directory"
install -m 0755 "$build_directory/bin/rustscan" "$here/bin/rustscan"
