#!/bin/bash
set -euxo pipefail

cd /memclave/ci-switch

cp -r ./ /tmp/ci-switch

cmake -B build .
cmake --build build --target ci-switch

cd /tmp/ci-switch
sed -i 's/IME_REPORT_STATS=0/IME_REPORT_STATS=1/' ./ime/CMakeLists.txt

cmake -B build .
cmake --build build --target ci-switch
cp ./build/ci-switch /memclave/ci-switch/build/ci-switch-stats

exit 0