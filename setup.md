# Setup Instruction for Memclave

These instructions allow setting up Memclave on a device equipped with
UPMEM hardware. To make the build instructions clear, we define three
different environments:
1. The *development environment* can be any recent x86_64 machine that is
   able to run Docker under Linux. Most compilation steps are transparently
   handled in Docker containers, reducing the amount of specific requirements
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
`memclave` and `memclave-qemu` containers are imported or build. Simply run
```bash
./scripts/hyp/setup.sh
```
after setting up the containers, to compile `qemu`, the `ci-switch` and all the
relevant PIM kernels. The results will be stored in the `hyp` folder.

## Launching the Virtual Machine

Now that the hypervisor is build, we can move all hypervisor related files, which are
placed in the `hyp` folder to the *execution environment*. The exact way for this depends
on your concrete setup, for a remote *execution environment*, you may whish to compress
the `hyp` folder into a `.tar.xz` file and then `scp` it over:
```bash
tar cf hyp.tar hyp
xz -0 hyp.tar
scp hyp.tar your-remote-environment:~
```

The `hyp` folder, now on your *execution environment*, contains a `qemu` build, the `ci-switch`,
and a script to simplify booting up the *memclave environment*. You may notice that it also
contains a premade disk image `memclave.qcow2`. This image contains a small, already set-up
version of Debian 12. The VM image also already contains the memclave linux driver in the
`/home/memclave/driver` folder. We have set up two users, `root` with the password `root` and
`memclave` with the password `memclave`. Therer is no necessity to use this image, memclave
works with all semi-recent linux distributions.

In the execution environment, cd into your `hyp` folder, make the `boot.sh` script executable
if necessary and run the script. This will start the `ci-switch` and boot the *memclave environment*.
The `boot.sh` script configures `qemu` to use the tty as the main output, so you should be able
to interact with the virtual machine, though in a somewhat limiting environment.

**Setting Up SSH to the *Memclave Environment***

You may wish to directly SSH into the *memclave environment* from your *development environment*.
A way to do this, is to create an SSH reverse proxy from the *memclave environment* to the
*execution environment* and then a proxy from the *development environment* to the *execution environment*.
For this, run
```bash
ssh -NR 127.0.0.1:26173:localhost:22 <execution environment address*>
```
in the *memclave environment* and
```bash
ssh -NL 26173:localhost:26173 <execution environment address>
```
in the *development environment*. Note that the address of the *execution environment* will be different
from the usual one in the *memclave environment*, if you are using the `boot.sh` script. The
IP of the execution environment should be something like `10.0.2.2`. Now you should be able to run
```bash
ssh -p 26173 memclave@127.0.0.1
```
on your *development environment*, establishing direct SSH access to the *memclave environment*.

**Compiling and Loading the Memclave Driver**

In the *memclave environment*, cd to `/home/memclave/driver`. There you build the driver by running
```bash
make
```
and load it using the
```bash
insmod vpim.ko
```
command. Once loaded, the driver will create device nodes for all available ranks under `/dev/vpimN`,
where `N` is a number between 0 and 39 (inclusive). How many ranks are available depends on the
`ci-switch` invocation in the `boot.sh` script on the *execution environment*. Adding the `--nr-ranks=N`
option will cause the allocation of exactly `N` ranks. The default is just one rank.

**NOTE:** The Memclave driver is not loaded automatically at boot. Programs using memclave's client library
will fail if the driver has not been loaded via `insmod`.

## Beyond the Memclave Setup

If you've completed all steps, you've successfully set-up a development environment for Memclave.
From here, you can run the benchmarks also provided as part of this artifact, or develop your own
programs using Memclave.