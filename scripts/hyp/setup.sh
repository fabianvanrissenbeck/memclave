#!/bin/bash
set -euxo pipefail

MEMCLAVE_ROOT=$(realpath $(dirname "$0")/../../)

rm -rf $MEMCLAVE_ROOT/ci-switch/build

docker run --rm --user ${UID} -v $MEMCLAVE_ROOT:/memclave -v $MEMCLAVE_ROOT/scripts/hyp/ci-switch.sh:/ci-switch.sh memclave:latest bash /ci-switch.sh
docker run --rm --user ${UID} -v $MEMCLAVE_ROOT:/memclave -v $MEMCLAVE_ROOT/scripts/hyp/qemu.sh:/qemu.sh memclave-qemu:latest bash /qemu.sh

mkdir -p ${MEMCLAVE_ROOT}/hyp ${MEMCLAVE_ROOT}/hyp/bin
cp -r ${MEMCLAVE_ROOT}/qemu/build/* ${MEMCLAVE_ROOT}/hyp/bin
cp ${MEMCLAVE_ROOT}/ci-switch/build/ci-switch ${MEMCLAVE_ROOT}/hyp/bin
cp ${MEMCLAVE_ROOT}/ci-switch/build/ci-switch-stats ${MEMCLAVE_ROOT}/hyp/bin
cp ${MEMCLAVE_ROOT}/scripts/hyp/boot.sh ${MEMCLAVE_ROOT}/hyp
cp ${MEMCLAVE_ROOT}/scripts/hyp/boot.sh ${MEMCLAVE_ROOT}/hyp/boot-stats.sh
sed -i 's/ci-switch/ci-switch-stats/' ${MEMCLAVE_ROOT}/hyp/boot-stats.sh
