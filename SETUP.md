# Setup Instruction for Memclave

These instructions allow setting up Memclave on a device equipped with
UPMEM hardware. To make the build instructions clear, we define three
different environments:
1. The *development environment* can be any recent x86_64 machine that is
   able to run Docker under Linux. Most compilation steps are transparently
   handled in Docker containers, recuding the amount of specific requirements
   for the development environment.
2. The *execution environment* is a machine equipped with UPMEM hardware. You
   may use this machine for the *development environment* as well, but this is
   not strictly necessary. During our development effort, we've used a remote
   UPMEM machine and kept the *development* and *execution* environment seperate.
3. The *memclave environment* is a virtual machine hosted by the memclave hypervisor
   running on the *execution environment*. The virtual machine setup is described
   in this guide.

If not specified otherwise, we assume that you are in the root directory of the
artifact unpacked on the *development environment* for all build steps.

## Building the Containers

We provide two Docker containers as build environments used to construct most
Memclave components. The `memclave` container is the most important one and includes
the full UPMEM toolchain including our own patches to UPMEM's LLVM version. It is
used to build PIM components of Memclave, as well as the `ci-switch`. Furthermore,
is is also meant as a generic build environment for user subkernels. The `memclave-qemu`
container is only used to build `qemu`. This container is not strictly necessary for
building our patched `qemu`. It was a hassle to install build dependencies in our
*execution environment*, so the `memclave-qemu` simply rebuilds the environment of
our *execution environment* with the necessary build dependencies. This allows
moving binaries from the `memclave-qemu` container directly to our *execution environment*.
On your setup, it may be better to just build qemu directly on your *execution environment*,
by just following the usual QEMU build instructions.

To build the `memclave` container, move to the `ime` directory and run
```bash
docker build -t memclave .
```
to begin the build process. Due to our LLVM patches, this build may take a lot of
time. (~40min on a somewhat recent thinkpad) As an alternative to the long build, we also provide the container as a tarball.
Simply run
```bash
docker load -i memclave.tar
```
to import the container image.

To build the `qemu` container, move to the `qemu` directory and run
```bash
docker build -t memclave-qemu .
```
or
```bash
docker load -i memclave-qemu.tar
```
to import the provided container image.

## Building the Hypervisor

Memclave's hypervisor consists of two components, the `ci-switch` and `qemu`. The
`ci-switch` build also compiles all necessary PIM kernels, such as the *loader*,
the first-stage *loader*, and the key exchange and messaging subkernels. These
kernels are included in the final `ci-switch` binary automatically. We provide a
script that automatically builds all hypervisor components assuming that the
`memclave` and `memclave-qemu` containers are imported or build. Simply run the
`scripts/hyp/setup.sh` script, after setting up the containers, to compile `qemu`,
the `ci-switch` and all the relevant PIM kernels. The results will be stored in the
`hyp` folder.
