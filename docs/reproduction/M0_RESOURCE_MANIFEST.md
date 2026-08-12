# M0 资源清单与落地记录

> 执行时间：2026-08-12（UTC）
>
> 状态：**已落地并验证**

## 1. 官方 archive

| 项目 | 值 |
|---|---|
| 官方来源 | VLN-DUET README 指向的 Dropbox shared archive |
| URL | `https://www.dropbox.com/sh/u3lhng7t2gq36td/AABAIdFnJxhhCg2ItpAhMtUBa?dl=1` |
| staging | `/root/autodl-tmp/ProofNav/.m0-staging/download/datasets.zip` |
| bytes | 20,121,983,052 |
| SHA-256 | `362aefa62a8f57dcab0f6d7475a0818f1cc140357b31fa6806346075d34effe8` |
| members | 167；CRC 通过；member-name manifest SHA-256 `d831cc13...657627` |

解压前审计了绝对路径、`..`、drive prefix、NUL、symlink、重复文件名、CRC 和
必需路径。Dropbox archive 含一个零长度、CRC 0 的 `/` directory member；通用
解压会把它识别成绝对路径，因此使用 `m0_safe_extract.py` 明确跳过这一 inert
member，并逐项验证其余目标都位于 staging root 内。

只从 archive 选择了 R2R connectivity、一个 panorama HDF5、五个 REVERIE
annotation split、`BBoxes.json`、一个 object HDF5 和一个 REVERIE checkpoint；
提取 108 个成员（含目录）、最终 101 个文件，跳过 58 个与 M0 无关成员。正式目录
占用约 5.3 GiB。archive 继续保留，未删除用户文件。

## 2. 正式资源与 hash

| 资源 | 正式路径 | bytes | SHA-256 |
|---|---|---:|---|
| connectivity scan list | `datasets/R2R/connectivity/scans.txt` | 1,080 | `a09a1f19...d3c39` |
| panorama features | `datasets/R2R/features/pth_vit_base_patch16_224_imagenet.hdf5` | 3,141,482,913 | `ae0ff208...d31bbc` |
| object features | `datasets/REVERIE/features/obj.avg.top3.min80_vit_base_patch16_224_imagenet.hdf5` | 259,365,852 | `9d9f591f...26b615` |
| BBoxes | `datasets/REVERIE/annotations/BBoxes.json` | 7,757,728 | `21d22701...e58296` |
| train annotation | `datasets/REVERIE/annotations/REVERIE_train_enc.json` | 5,851,327 | `94141a48...3fee8` |
| val_train_seen annotation | `datasets/REVERIE/annotations/REVERIE_val_train_seen_enc.json` | 68,901 | `d42359a2...953b4` |
| val_seen annotation | `datasets/REVERIE/annotations/REVERIE_val_seen_enc.json` | 743,527 | `f133b472...a77b1c` |
| val_unseen annotation | `datasets/REVERIE/annotations/REVERIE_val_unseen_enc.json` | 1,888,617 | `7fec9f5c...bf0f3` |
| test annotation | `datasets/REVERIE/annotations/REVERIE_test_enc.json` | 1,699,626 | `1fe65add...4820d` |
| DUET checkpoint | `datasets/REVERIE/trained_models/best_val_unseen` | 2,175,032,658 | `c74aad4b...18dc` |

所有 101 个文件的完整、未截断 SHA-256 和 byte size 保存于
`/root/autodl-tmp/ProofNav/.m0-results/audits/resource_hash_manifest.json`；该
manifest 自身 SHA-256 为
`db835cf71e51109b5aff5adc4cf5904171232fe21c6e6f47f83efd0ee3bf8510`。

## 3. Schema 与覆盖验证

| 项目 | 实测 |
|---|---|
| REVERIE train | 4,150 paths / 10,466 instructions / 60 scans |
| val_train_seen | 50 / 123 / 27 |
| val_seen | 515 / 1,423 / 46 |
| val_unseen | 1,328 / 3,521 / 10 |
| test | 2,304 / 6,292 / 16；匿名 schema，无 evaluator objId/path_id |
| union scans | 86 REVERIE scans，均存在 connectivity |
| included viewpoints | 10,318 |
| panorama HDF5 | 10,567 keys，全部 `(36, 1768)`；REVERIE viewpoint 缺失 0 |
| object HDF5 | 7,003 keys；feature width 1,768；directions/sizes/obj_ids attrs 全匹配 |
| BBoxes | 10,559 scan-viewpoint entries |
| checkpoint | epoch field 16,001；VLN-BERT 429 tensors，critic 4 tensors；strict load 通过 |

staging 和正式路径各运行一次 schema audit，均通过。完整结果位于
`.m0-results/audits/resource_schema_{staging,formal}.json`。

## 4. Python/CUDA 环境

| 项目 | 冻结值 |
|---|---|
| environment | `/root/autodl-tmp/vlnduet-m0` |
| Python | 3.8.10 |
| PyTorch | 2.0.1+cu118，来自官方 PyTorch CUDA 11.8 wheel index |
| GPU | NVIDIA GeForce RTX 4080 SUPER；实际 CUDA tensor smoke 通过 |
| tokenizer/config | `bert-base-uncased` local cache；vocab 30,522、hidden size 768 |
| pip freeze | [M0_PIP_FREEZE.txt](M0_PIP_FREEZE.txt) |

历史官方 torch 1.7.1+cu101 不支持该 Ada GPU，因此兼容环境使用 2.0.1+cu118。
`tensorboardX==2.4.1` 的旧 protobuf 生成代码要求 `protobuf==3.20.3`。机器默认
pip mirror、已发生的同版本 PyPI 重装、可获得的 installed-distribution metadata
hash 均如实记录在 [M0_ENVIRONMENT_LOCK.md](M0_ENVIRONMENT_LOCK.md)。没有污染
base 或其他环境。

## 5. MatterSim

| 项目 | 冻结值 |
|---|---|
| source | official Matterport3DSimulator recursive clone |
| checkout | `589d091b111333f9e9f9d6cfd021b2eb68435925` |
| pybind11 | `86e2ad4f77442c3350f9a2476650da6bee253c52` |
| nested clang | `6a00cbc4a9b8e68b71caf7f774b3f9c753ae84d5` |
| build | `cmake -DOSMESA_RENDERING=ON`，GNU C++ 9.4.0，全部 targets 成功 |
| binding | `/root/autodl-tmp/Matterport3DSimulator/build/MatterSim.cpython-38-x86_64-linux-gnu.so` |

精确 apt 版本与 OpenCV 4 两行兼容补丁见
[环境冻结](M0_ENVIRONMENT_LOCK.md)和
[补丁](M0_MATTERSIM_OPENCV4.patch)。raw scans 在 rendering disabled 的 M0
baseline 中不需要，未下载。

## 6. 明确未获取的资源

- raw Matterport3D RGB/depth/skybox scans；
- LXMERT `model_LXRT.pth`；
- BERT base model weights；
- archive 中 R4R、SOON、R2R/REVERIE pretraining 数据和其他 checkpoint；
- paired REVERIE、ProofNav/M1 数据或任何训练产物。

test predictions 只保存在本地，没有上传 leaderboard。资源仍受用户已确认的
Matterport3D/REVERIE 研究使用条款约束，`datasets/`、staging、cache 和 results
均由 `.gitignore` 排除，不应再分发。
