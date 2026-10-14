# Third-Party Notices

The project glue, plate packing and exports use the MIT license in `LICENSE`.
Model licenses and downloaded dependencies remain separate. This repository does
not redistribute model weights, the Studio/LDraw library, or third-party source.

- **TripoSR**: https://github.com/VAST-AI-Research/TripoSR
  Copyright (c) 2024 Tripo AI & Stability AI; MIT code and model weights.
  Downloaded source retains its original LICENSE and per-file notices, including
  Apache-2.0 notices in transformer modules. Commit is fixed in `models.lock.json`.
- **SD-Turbo**: https://huggingface.co/stabilityai/sd-turbo
  The pinned model card describes research, non-commercial and commercial uses
  and directs commercial users to https://stability.ai/license and membership
  terms. Consult those terms before commercial deployment. MIT licensing of this
  repository does not grant rights to the SD-Turbo weights. The image stage is
  optional: use your own legally obtained image via `run --image`.
- **DINO config**: https://huggingface.co/facebook/dino-vitb16 (Apache-2.0).
  TripoSR initializes its image encoder with this configuration; its encoder
  weights come from the TripoSR checkpoint.
- **rembg / U2NetP**: https://github.com/danielgatis/rembg (MIT) and
  https://github.com/xuebinqin/U-2-Net (Apache-2.0). Background-removal weights are
  downloaded by rembg and are not included in this repository.
- **trimesh** (MIT), **scikit-image** (BSD), **PyTorch** (BSD-style), **diffusers**
  and **transformers** (Apache-2.0), and other Python dependencies retain their
  own licenses. See the installed distributions for full notices.
- **Car2LEGO**: https://github.com/imxiaoxian/Car2LEGO (MIT, copyright 2025
  imxiaoxian). Architecture reference: real part IDs, LDraw outputs, and separate
  digital versus physical validation. No original source or private data copied.

LEGO and BrickLink are trademarks of their owners. This research project is not
affiliated with or endorsed by them.
