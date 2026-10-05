#!/bin/sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rm -rf "$here/bin"; mkdir -p "$here/bin"
GOBIN="$here/bin" go install -ldflags "-s -w" github.com/d3mondev/puredns/v2@latest
