#!/bin/sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rm -rf "$here/bin" "$here/.cargo-root"; mkdir -p "$here/bin"
cargo install rustscan --root "$here/.cargo-root" --locked
cp "$here/.cargo-root/bin/rustscan" "$here/bin/rustscan"
rm -rf "$here/.cargo-root"
