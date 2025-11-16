# signal_respirometry

Standard analysis layout with Jupyter notebooks.

- `notebooks/` — exploratory and analysis notebooks
- `data/` — project data
  - `raw/` — unmodified source data
  - `processed/` — cleaned/derived data
  - `external/` — data from external sources/exports
- `figures/` — generated figures and exports
- `video/` — raw videos and derived clips

Quick start:

1. Open `notebooks/00_project_setup.ipynb` and run cells.
2. Create additional notebooks as needed (e.g., `01_exploration.ipynb`).
3. Save outputs to `figures/`, intermediate files to `data/processed/`, and place videos in `video/`.

Git tips:
- Videos in `video/` are ignored by default via `.gitignore` to keep the repo lean. Keep the `.gitkeep` so the folder exists in Git.
- If you need to version videos, consider enabling Git LFS and removing the ignore rule for specific files.

Notes:
- Empty folders include a `.gitkeep` so they can be committed.
- You can add a `src/` folder later for reusable code modules.
