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

1. Open `notebooks/00_download_videos_from_dryad.ipynb` and run cells to download videos
2. Video analysis notebooks are 'notebooks/01_video_analysis*.ipynb' 
3. Respirometry analysis is in A_batch_respirometry_final.ipynb
4. Figures are created in Figure*.ipynb

Git tips:
- Videos in `video/` are ignored by default via `.gitignore` to keep the repo lean. Keep the `.gitkeep` so the folder exists in Git.
- If you need to version videos, consider enabling Git LFS and removing the ignore rule for specific files.