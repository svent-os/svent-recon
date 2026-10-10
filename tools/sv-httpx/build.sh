#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$here/bin"
export GOBIN="$here/bin"
export GOTOOLCHAIN=auto
go install -p "${SVENT_BUILD_JOBS:-2}" -trimpath -ldflags "-s -w" github.com/projectdiscovery/httpx/cmd/httpx@v1.12.0
mv "$here/bin/httpx" "$here/bin/httpx-toolkit"
