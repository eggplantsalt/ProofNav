# M3 resource and configuration audit

No resources were downloaded or installed in this stage.

| Resource | Present / verified | Identity / size | Needed next? |
|---|---|---|---|
| DUET checkpoint | yes | `datasets/REVERIE/trained_models/best_val_unseen`, SHA prefix `c74aad...`, 2.175 GB | yes, frozen base |
| panorama ViT features | yes | SHA prefix `ae0ff...`, 3.141 GB | yes |
| object ViT features | yes | SHA `9d9f591f64d98a3547035575803fa0e78e779a57a06dd34467e480373c26b615`, 259 MB | yes; annotated-slot limitation |
| REVERIE BBoxes inventory | yes | SHA `21d227018de2e11eb0a7b3188d760a56a988e8152213d15979ba6ba7a0e58296`, 7.76 MB | offline truth/inventory only |
| annotations/connectivity | yes | 86 connectivity scans; opaque join verified | yes |
| MatterSim | yes | Python 3.8 shared object under `/root/autodl-tmp/Matterport3DSimulator/build` | yes |
| environment | yes | `/root/autodl-tmp/vlnduet-m0`: Python 3.8, PyTorch 2.0.1+cu118, transformers 4.30, h5py 2.10, numpy 1.20, networkx 2.5 | reuse; no reinstall |
| GPU | yes | RTX 4080 SUPER; frozen baseline peak 6264 MiB; champion collection 8.24s | no immediate new run |
| disk / host | yes | about 75 GB free, 503 GiB RAM, 96 logical CPUs at audit | sufficient |
| raw RGB/depth | absent | rendering disabled; no cache | needed only for detector/geometry augmentation |
| detector/VLM/open-vocabulary checkpoint | absent | no GroundingDINO/SAM/CLIP/open_clip/detectron cache | not needed for current conclusion; do not download yet |
| typed/null grounding labels | absent as legal split | current val_train_seen paths/instructions/scans overlap train; val_seen scans also train-seen | **blocks next trained head/calibration** |
| VLN-NF / paired extension artifact | absent | official paper exists; local data absent | needed before full false-premise evaluation |

Current object HDF5 slots exactly track the benchmark BBoxes inventory.  DUET
scores are real online model outputs conditional on that interface, but they do
not prove detector discovery, target presence, identity continuity or residual
absence.  No scalar post-processing removes the observed high-confidence null
failure.

The next minimum resource is not a large VLM.  It is a legally separated set of
at least 59 independent scans with typed target/null/attribute/relation labels
for a frozen whole terminal policy if a 95%/5% zero-error binomial gate is the
target.  Training a small head also requires collecting frozen `vp_embeds` or
equivalent values with code-derived checkpoint/feature/interface identity.
Only if that probe shows a genuine information ceiling should the project
request a specific official detector or image-language embedding resource with
license, size and checksum.
