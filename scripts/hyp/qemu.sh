#!/bin/bash
set -euxo pipefail

cd /memclave
rm -rf ./qemu/common
cp -r ./common ./qemu
cd qemu
mkdir -p build
cd build

../configure --without-default-features --enable-kvm --enable-slirp --target-list="x86_64-softmmu"
make -j12

cp -r ../pc-bios/* ./

exit 0
