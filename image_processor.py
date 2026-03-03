import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
import csv
from matplotlib.widgets import RectangleSelector

script_dir = os.path.dirname(os.path.abspath(__file__))
img_folder = os.path.join(script_dir, 'images')
output_root = os.path.join(script_dir, 'processed_wings')
csv_path = os.path.join(script_dir, 'wing_results.csv')

if not os.path.exists(output_root):
    os.makedirs(output_root)

def quit_program():
    # os._exit bypasses Python teardown, killing the macOS event loop
    # that plt leaves running in the background — prevents the spinning wheel
    plt.close('all')
    os._exit(0)

def adjust_gamma(image, gamma=1.0):
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

class PolygonEditor:
    PICK_PX = 15

    def __init__(self, ax, verts):
        self.ax = ax
        self.verts = [list(v) for v in verts]
        self.drag_idx = None
        self.line, = ax.plot([], [], 'r-', lw=2, alpha=0.7, zorder=3)
        self.dots, = ax.plot([], [], 'ro', ms=6, alpha=0.9, zorder=4)
        self._redraw()
        c = ax.figure.canvas
        c.mpl_connect('button_press_event',   self._press)
        c.mpl_connect('button_release_event', self._release)
        c.mpl_connect('motion_notify_event',  self._motion)

    def _nearest(self, event):
        if not self.verts or event.xdata is None:
            return None
        disp = self.ax.transData.transform(self.verts)
        dists = np.hypot(disp[:, 0] - event.x, disp[:, 1] - event.y)
        i = int(np.argmin(dists))
        return i if dists[i] < self.PICK_PX else None

    def _redraw(self):
        xs = [v[0] for v in self.verts] + [self.verts[0][0]]
        ys = [v[1] for v in self.verts] + [self.verts[0][1]]
        self.line.set_data(xs, ys)
        self.dots.set_data([v[0] for v in self.verts], [v[1] for v in self.verts])
        self.ax.figure.canvas.draw_idle()

    def _press(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        idx = self._nearest(event)
        if event.button == 1 and event.key == 'shift':
            # insert new vertex on the nearest edge
            n = len(self.verts)
            best, best_d = 0, float('inf')
            for i in range(n):
                ax_, ay_ = self.verts[i]
                bx_, by_ = self.verts[(i + 1) % n]
                dx, dy = bx_ - ax_, by_ - ay_
                t = np.clip(((event.xdata - ax_) * dx + (event.ydata - ay_) * dy) / (dx*dx + dy*dy + 1e-10), 0, 1)
                d = np.hypot(event.xdata - (ax_ + t*dx), event.ydata - (ay_ + t*dy))
                if d < best_d:
                    best_d, best = d, i
            self.verts.insert(best + 1, [event.xdata, event.ydata])
            self._redraw()
        elif event.button == 3 and idx is not None and len(self.verts) > 3:
            self.verts.pop(idx)
            self._redraw()
        elif event.button == 1 and idx is not None:
            self.drag_idx = idx

    def _release(self, event):
        self.drag_idx = None

    def _motion(self, event):
        if self.drag_idx is None or event.inaxes != self.ax or event.xdata is None:
            return
        self.verts[self.drag_idx] = [event.xdata, event.ydata]
        self._redraw()

    def get_verts(self):
        return np.array(self.verts)


def ask_overwrite(name):
    raw = input(f'  "{name}" already in CSV. [y]es / [n]o / [q]uit: ').strip().lower()
    if raw == 'q': quit_program()
    return raw == 'y'


valid_exts = ('.jpg', '.jpeg', '.png')
if not os.path.exists(img_folder):
    print(f"error: images folder not found at {img_folder}")
    exit()

images = sorted([f for f in os.listdir(img_folder) if f.lower().endswith(valid_exts)])

CSV_HEADER = ['filename', 'ppc_x', 'ppc_y', 'area_cm2']
csv_rows = {}
if os.path.exists(csv_path):
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if header == CSV_HEADER:
            for row in reader:
                if row: csv_rows[row[0]] = row
        else:
            print("  note: existing CSV is old format (single ppc) — all images will be re-processed")

n_existing = sum(1 for img in images if img in csv_rows)
if n_existing > 0:
    print(f"\n{n_existing}/{len(images)} images already in CSV.")
    raw = input("  [s]kip existing / [r]edo all / [a]sk per file: ").strip().lower()
    overwrite_mode = {'r': 'redo', 'a': 'ask'}.get(raw, 'skip')
else:
    overwrite_mode = 'skip'

TITLE = dict(fontsize=14, color='blue')
HINT  = dict(ha='center', va='top', fontsize=9, color='gray')
total = len(images)

for idx, img_name in enumerate(images, 1):
    plt.close('all')

    if img_name in csv_rows:
        if overwrite_mode == 'skip':
            continue
        elif overwrite_mode == 'ask' and not ask_overwrite(img_name):
            continue

    img = cv2.imread(os.path.join(img_folder, img_name))
    if img is None: continue
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    print(f"\n[{idx}/{total}] {img_name}")

    restart = True
    while restart:
        restart = False

        # Step 1: Calibrate (X and Y axes separately using the grid)
        print("  [1/3] calibrate — click 2 horizontal pts 10 cm apart, then 2 vertical pts 10 cm apart")
        pts = []
        quit_flag = [False]
        restart_flag = [False]
        fig, ax = plt.subplots(figsize=(12, 9))
        fig.text(0.5, 0.99, "ESC: exit program  ·  R: restart image", **HINT)
        ax.imshow(img_rgb)
        ax.set_title(f"Step 1/3 [{idx}/{total}] — Click 2 horizontal pts (10 cm apart), then 2 vertical pts (10 cm apart)", **TITLE)
        def on_cal_click(event):
            if event.inaxes != ax or event.button != 1 or len(pts) >= 4:
                return
            pts.append((event.xdata, event.ydata))
            n = len(pts)
            color = 'lime' if n <= 2 else 'deepskyblue'
            ax.plot(event.xdata, event.ydata, '+', color=color, ms=14, mew=2.5, zorder=5)
            # connect each pair with a line once both points are placed
            if n == 2:
                ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]], '-', color='lime', lw=1.5, alpha=0.6, zorder=4)
            elif n == 4:
                ax.plot([pts[2][0], pts[3][0]], [pts[2][1], pts[3][1]], '-', color='deepskyblue', lw=1.5, alpha=0.6, zorder=4)
                # brief pause so both lines are visible before advancing — timer fires
                # from within the event loop, which is required for thread safety on macOS
                fig._cal_timer = fig.canvas.new_timer(interval=700)
                fig._cal_timer.add_callback(plt.close, fig)
                fig._cal_timer.start()
            fig.canvas.draw_idle()
        def on_cal_key(event):
            if event.key == 'escape':   quit_flag[0] = True;    plt.close('all')
            elif event.key == 'r':      restart_flag[0] = True; plt.close('all')
        fig.canvas.mpl_connect('button_press_event', on_cal_click)
        fig.canvas.mpl_connect('key_press_event', on_cal_key)
        plt.tight_layout()
        plt.pause(0.1)
        try: fig.canvas.manager.window.raise_()   # grab OS focus so first click registers
        except Exception: pass
        plt.show()
        plt.close('all')

        if quit_flag[0]: quit_program()
        if restart_flag[0]: restart = True; continue
        if len(pts) < 4: print("  skipping"); break

        # use only the relevant axis component for each calibration pair
        ppc_x = abs(pts[1][0] - pts[0][0]) / 10.0
        ppc_y = abs(pts[3][1] - pts[2][1]) / 10.0

        # Step 2: Select wing box
        print("  [2/3] select wing — draw a box, then press ENTER")
        roi_coords = [None]
        quit_flag = [False]
        restart_flag = [False]
        fig, ax = plt.subplots(figsize=(12, 9))
        fig.text(0.5, 0.99, "ESC: exit program  ·  R: restart image", **HINT)
        ax.imshow(img_rgb)
        ax.set_title(f"Step 2/3 [{idx}/{total}] — Draw a box around the wing, then press ENTER", **TITLE)

        def on_roi_select(eclick, erelease):
            roi_coords[0] = (eclick.xdata, eclick.ydata, erelease.xdata, erelease.ydata)
        def on_roi_key(event):
            if event.key == 'enter' and roi_coords[0] is not None: plt.close('all')
            elif event.key == 'escape':  quit_flag[0] = True;    plt.close('all')
            elif event.key == 'r':       restart_flag[0] = True; plt.close('all')

        rs = RectangleSelector(ax, on_roi_select, useblit=True, button=[1],
                               minspanx=5, minspany=5, spancoords='pixels', interactive=True)
        fig.canvas.mpl_connect('key_press_event', on_roi_key)
        plt.tight_layout()
        plt.pause(0.1)
        plt.show()
        plt.close('all')

        if quit_flag[0]: quit_program()
        if restart_flag[0]: restart = True; continue
        if roi_coords[0] is None: print("  skipping"); break

        x1, y1, x2, y2 = roi_coords[0]
        x, y = int(min(x1, x2)), int(min(y1, y2))
        w, h = int(abs(x2 - x1)), int(abs(y2 - y1))

        # auto-detect outline
        crop = img[y:y+h, x:x+w]
        bright_crop = adjust_gamma(crop, gamma=2.0)
        crop_gray = cv2.cvtColor(bright_crop, cv2.COLOR_BGR2GRAY)
        _, crop_mask = cv2.threshold(crop_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        grid_kernel = np.ones((5, 5), np.uint8)
        crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_OPEN, grid_kernel)
        close_kernel = np.ones((15, 15), np.uint8)
        crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_CLOSE, close_kernel)
        contours, _ = cv2.findContours(crop_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: break
        main_contour = max(contours, key=cv2.contourArea)
        approx_poly = cv2.approxPolyDP(main_contour, 0.007 * cv2.arcLength(main_contour, True), True)
        initial_verts = approx_poly.reshape(-1, 2).astype(float)
        initial_verts[:, 0] += x
        initial_verts[:, 1] += y

        # Step 3: Fine tune
        print("  [3/3] fine tune — adjust outline, then press ENTER")
        quit_flag = [False]
        restart_flag = [False]
        fig, ax = plt.subplots(figsize=(12, 9))
        fig.text(0.5, 0.99, "ESC: exit program  ·  R: restart image", **HINT)
        ax.imshow(img_rgb)
        ax.set_title(f"Step 3/3 [{idx}/{total}] — Drag to move  ·  Shift+click to add  ·  Right-click to remove  ·  ENTER to confirm", **TITLE)

        editor = PolygonEditor(ax, initial_verts)

        def handle_keypress(event):
            if event.key == 'enter':    plt.close('all')
            elif event.key == 'escape': quit_flag[0] = True;    plt.close('all')
            elif event.key == 'r':      restart_flag[0] = True; plt.close('all')

        fig.canvas.mpl_connect('key_press_event', handle_keypress)
        plt.tight_layout()
        plt.pause(0.1)
        plt.show()
        plt.close('all')

        if quit_flag[0]: quit_program()
        if restart_flag[0]: restart = True; continue

        # fill solid and save
        img_h, img_w = img.shape[:2]
        mask_solid = np.zeros((img_h, img_w), dtype=np.uint8)
        res_verts = editor.get_verts()

        if len(res_verts) > 0:
            cv2.fillPoly(mask_solid, [res_verts.astype(np.int32)], 255)
            area_cm2 = np.sum(mask_solid == 255) / (ppc_x * ppc_y)
            cv2.imwrite(os.path.join(output_root, f"mask_{img_name}"), mask_solid)

            new_row = [img_name, round(ppc_x, 2), round(ppc_y, 2), round(area_cm2, 2)]
            csv_rows[img_name] = new_row
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER)
                writer.writerows(csv_rows.values())

            print(f"  saved: {area_cm2:.2f} cm²")

print("\nall done.")
