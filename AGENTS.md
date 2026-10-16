# Project Boundary

- This repository owns the LLM + Blender modelling workflow. Its exact name is `Car2LGEO_3D_LLM`.
- Default CLI and desktop reconstruction to `gpt-blender`; desktop jobs must not silently use Hunyuan3D.
- Open-source reconstruction lives in `D:/Car2LEGO_3D` and GitHub `imxiaoxian/Car2LEGO_3D`.
- Use this checkout's environments, configuration, caches, runs and frontend build output. Default UI/API ports are 8778/8777.
- `D:/lego` is a read-only service provider. Do not alter its source files, database or pending changes.
- Keep GPT image requests in groups of at most five; complete the entire group before dispatching the next group.
- Preserve historical artifacts and their acceptance labels; generated exports and unit tests do not certify model appearance.
- Run the relevant Python regression tests and frontend build before publishing changes.
