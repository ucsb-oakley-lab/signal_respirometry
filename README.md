# Signal respirometry

Analysis code, input data, and figure-generation notebooks accompanying the associated study of signal production and respirometry. The repository is organized so that its tracked data and analysis notebooks can be run locally; raw video files are retrieved separately because they are too large for Git.

## Setup

Create the reproducible Conda environment from the repository root:

```bash
conda env create -f environment.yml
conda activate respirometry
```

The environment includes the Python packages used by the notebooks and the R runtime and packages required by `scripts/consumption_rate.R`. Launch Jupyter from the repository root so that the notebooks can locate the project directories:

```bash
jupyter lab
```

## Data layout

- `data/csvs-and-code-jan2026/` is the canonical respirometry input dataset used by `A_batch_respirometry_final.ipynb`.
- `data/adriana_final_r/` is an earlier data delivery retained for provenance; it is not the default analysis input.
- `data/pilot_exp/` contains data used for the pilot analysis in Figure S1.
- `data/config/` contains video-analysis parameters and region-of-interest definitions.
- `data/processed/` contains derived analysis tables, including the inputs consumed by the figure notebooks.
- `figures/` contains generated main-text and supplemental figures.

Raw videos are deliberately excluded from version control. Obtain them from the [Dryad data deposit](https://doi.org/10.5061/dryad.x0k6djj17), place them in `video/`, and then run the video-analysis notebooks below. `notebooks/videonotebooks/00_download_videos_from_dryad.ipynb` provides a downloader template; populate its file manifest with the direct Dryad file URLs before using it.

## Reproducing the analyses

Run the notebooks in this order when regenerating all derived tables and figures:

1. `notebooks/A_batch_respirometry_final.ipynb` processes the canonical respirometry CSV files with `scripts/consumption_rate.R` and writes `data/processed/batch_summary.csv`.
2. With the raw videos in `video/`, run `notebooks/videonotebooks/01_video_analysis_nov10.ipynb` through `04_video_analysis_nov14.ipynb`. These write per-video filtered detection tables to `data/processed/`.
3. Run `notebooks/FigureS2_AllVideosComparison.ipynb` to create the all-video comparison and `data/processed/signal_rate_summary.csv`.
4. Run the remaining figure and table notebooks:
   - `Figure1_S3_SlopeGraph.ipynb`
   - `Figure2_S1_BarChart.ipynb`
   - `Figure2_S5_BarChart.ipynb`
   - `Figure3_S4_S6_Regression.ipynb`
   - `Figure4_comparative.ipynb`
   - `FigureS1_Pilot.ipynb`
   - `TableS1_DataTable.ipynb`

The displayed outputs in the tracked notebooks and the files in `figures/` are the generated analysis artifacts. The code is released under the [MIT License](LICENSE).
