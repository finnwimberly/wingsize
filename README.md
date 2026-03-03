# wingsize

This program helps to calculate seabird wing area from images. It is semi-automated — you calibrate the scale against a background grid, and initial outline the of the wing is guessed using color detection, and then you can fine-tune the polygon. The results are saved to `wing_results.csv`. All setup, run-actions are done from the terminal. This will prompt imagine and polygon pop-ups.  

---

## first-time setup
**1. clone the repo**
```
git clone https://github.com/finnwimberly/wingsize.git
cd wingsize
```

**2. install miniconda if needed** 

https://docs.conda.io/en/latest/miniconda.html

**3. build the environment**
```
conda env create -f environment.yml
```

This installs all dependencies into a self-contained env.

**4. make the launcher executable** (one time only)
```
chmod +x run.sh
```

**5. add your images**
drop `.jpg` / `.jpeg` / `.png` files into the `images/` folder.


## running
```
./run.sh
```

This activates the env and launches the script automatically — no manual `conda activate` needed.

---

## workflow

each image steps through three windows:

**step 1 — calibrate**

Click two points on a horizontal grid line 10 cm apart (shown in green), then two points on a vertical grid line 10 cm apart (shown in blue). Calibrating both axes independently corrects for any camera tilt.

**step 2 — select wing**

Draw a bounding box around the wing, then press `enter`. the script auto-detects the outline using otsu thresholding.

**step 3 — fine-tune**

Adjust the polygon before confirming:

| action | result |
|---|---|
| drag a vertex | move it |
| shift + click | add a vertex on the nearest edge |
| right-click a vertex | remove it |
| `enter` | confirm and save |

---

## controls (any window)

- `esc` — exit the program
- `r` — restart the current image from step 1

---

## outputs

- `wing_results.csv` — one row per image: filename, ppc_x, ppc_y, area_cm²
- `processed_wings/` — binary wing masks saved as `.jpg`

---

## re-running on existing data

On startup, the script checks which images already have entries in the csv and asks how to handle them:

- `s` — skip existing, only process new images
- `r` — redo all images regardless
- `a` — ask for action image by image
