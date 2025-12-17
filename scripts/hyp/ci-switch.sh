#!/bin/bash
set -euxo pipefail

cd /memclave/ci-switch
cmake -B build .
cmake --build build --target ci-switch

exit 0