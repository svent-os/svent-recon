#!/bin/sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
rm -rf "$here/bin"; mkdir -p "$here/bin"
GOBIN="$here/bin" go install -ldflags "-s -w" github.com/projectdiscovery/httpx/cmd/httpx@latest && mv "$here/bin/httpx" "$here/bin/httpx-toolkit"
