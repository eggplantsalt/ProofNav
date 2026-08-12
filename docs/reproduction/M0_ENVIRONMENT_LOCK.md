# M0 compatibility environment lock

This lock records the environment used for the M0 DUET REVERIE compatibility
reproduction. It does not claim bitwise identity with the historical CUDA 10.1
environment.

## Python and CUDA

- environment path: `/root/autodl-tmp/vlnduet-m0`
- Python: 3.8.10
- PyTorch: 2.0.1+cu118 (official PyTorch CUDA 11.8 wheel index)
- CUDA build reported by PyTorch: 11.8
- runtime device: NVIDIA GeForce RTX 4080 SUPER
- CUDA smoke: available; an on-device square-and-sum returned `140.0`
- complete Python package set: [M0_PIP_FREEZE.txt](M0_PIP_FREEZE.txt)
- compatibility pin: `protobuf==3.20.3`, required by the frozen
  `tensorboardX==2.4.1` generated protobuf modules

The machine-level pip configuration is
`global.index-url=http://mirrors.aliyun.com/pypi/simple` with that host marked
trusted. The first general-dependency installation used this configured mirror;
PyTorch itself came from the explicitly selected official PyTorch CUDA 11.8
index. An unnecessary same-version, no-cache reinstall of the non-PyTorch
packages against `https://pypi.org/simple` was completed before the user asked
that no such source-normalization repeats be made. No further reinstall or
artifact re-download is permitted without a concrete integrity failure.

The original wheels were not retained, so this lock does not mislabel installed
tree hashes as wheel hashes. Available PyTorch installed-distribution metadata
hashes are: `METADATA` SHA-256
`9b8fc8cc6824a6f2c51292544aca7831f005749cd32f6d5c1ebd7ac6eab748a8` and
`RECORD` SHA-256
`ee8e82b8980ae37b439c03d06da9c59ddc47e1879734ab0e5016bc474434e9e2`.
Data archive, extracted data, and checkpoint hashes are recorded separately
because those source artifacts are retained locally.

The tokenizer and config for `bert-base-uncased` are cached below
`/root/autodl-tmp/ProofNav/.m0-cache/huggingface`. The local-only smoke returned
`BertTokenizerFast`, vocabulary size 30,522, and BERT hidden size 768. No BERT
base weights or LXMERT weights were requested for this step.

## MatterSim

- source: official recursive Matterport3DSimulator repository
- checkout: `589d091b111333f9e9f9d6cfd021b2eb68435925`
- pybind11 submodule: `86e2ad4f77442c3350f9a2476650da6bee253c52`
- nested pybind11 clang checkout: `6a00cbc4a9b8e68b71caf7f774b3f9c753ae84d5`
- build: CMake OSMesa backend, GNU C++ 9.4.0; all targets built
- Python binding:
  `/root/autodl-tmp/Matterport3DSimulator/build/MatterSim.cpython-38-x86_64-linux-gnu.so`

Exact apt build dependencies:

```text
libglew-dev=2.1.0-4
libglew2.1=2.1.0-4
libglm-dev=0.9.9.7+ds-1
libglu1-mesa=9.0.1-1build1
libglu1-mesa-dev=9.0.1-1build1
libjsoncpp-dev=1.7.4-3.1ubuntu2
libosmesa6-dev=21.2.6-0ubuntu0.1~20.04.2
```

The frozen MatterSim source used two OpenCV 2/3 constants removed by the host's
OpenCV 4.2. Two same-semantics namespace replacements were required. The exact
recorded patch is [M0_MATTERSIM_OPENCV4.patch](M0_MATTERSIM_OPENCV4.patch).
