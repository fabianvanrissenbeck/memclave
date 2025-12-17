#!/bin/bash
set -euxo pipefail

HYP_PATH=$(realpath $(dirname "$0"))
QEMU_PATH="$HYP_PATH/bin/qemu-system-x86_64"
LIBRARY_PATH="${HYP_PATH}/bin"

UPMEM_VERBOSE="" ${HYP_PATH}/bin/ci-switch &
CI_SWITCH_PID=$!

cd bin
sleep 1

LD_LIBRARY_PATH=$LIBRARY_PATH $QEMU_PATH \
    --nographic \
    --enable-kvm \
    -drive file="${HYP_PATH}/debian.qcow2",if=virtio,media=disk \
    -cpu host \
    -smp $(nproc) \
    -m 16G

cd ..
kill -SIGINT $CI_SWITCH_PID
kill -SIGINT $CI_SWITCH_PID
wait $CI_SWITCH_PID
