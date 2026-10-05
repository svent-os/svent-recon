#!/bin/sh
# Build amass from upstream into ./bin/amass
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rm -rf "$here/bin"; mkdir -p "$here/bin"
GOBIN="$here/bin" go install -v github.com/owasp-amass/amass/v4/...@master
