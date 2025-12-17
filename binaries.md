## Binaries Part of the Artifact

We currently provide three binaries as part of the artifact. Other components are code, documentation
or datasets. This document is a brief index for the binaries used.

+ `hyp/memclave.qcow2` is a disk image containing a minimal install of Debian 12. The install also includes
  the source code for the Memclave linux driver. The code can be found in the artifact in the `/driver` folder.
  A similar image could be build by installing Debian 12 manually and then moving the `/driver` folder into
  the VM.
+ `memclave-qemu.tar` is a docker image that is used for setting up QEMU with our patches. Manual build 
  instructions are provided in `setup.md`.
+ `memclave.tar` is a docker image used for building the Memclave hypervisor and used as a generic development
  environment for building memclave subkernels. Manual build instructions are provided in `setup.md`. This
  build takes a long time, due to the necessity of compiling a patched LLVM from scratch.