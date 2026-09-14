"""Pattern editor and simulator for the 5x5x5 RGB LED cube.

Left-click an LED to paint it with the current colour, right-click to switch
it off.  A pattern is a list of frames; see patterns.py for the file format
and send_serial.py for the link to the cube.
"""
import copy
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog

import pygame
from serial import SerialException

from cube_layout import SIZE, XYZ, layer_indices, led_index
from patterns import MAX_TIME, MIN_TIME, new_frame, read_pattern, write_pattern
from send_serial import preview_frames, suggest_sd_name, write_frames_to_sd

# ---------------------------------------------------------------- layout ----
window_size = (1200, 800)
circlesize = 16
h_spacing = 95      # between LEDs along x
h_stagger = 28      # shift per row back (y)
v_spacing = 105     # between layers (z)
v_stagger = -18     # rise per row back (y)
h_offset = 40
v_offset = 100
button_pos = (660, 30)
palette_pos = (40, 590)
swatch = 34
off_colours = [(70, 70, 70), (62, 62, 62), (54, 54, 54), (46, 46, 46), (38, 38, 38)]  # per row back
bin_filetypes = [("Cube pattern", "*.bin"), ("All files", "*.*")]

# Paint palette: hues at full brightness; the level row scales them.
palette = [(255, 0, 0), (255, 96, 0), (255, 200, 0), (128, 255, 0), (0, 255, 0), (0, 255, 128),
           (0, 255, 255), (0, 128, 255), (0, 0, 255), (160, 0, 255), (255, 0, 255), (255, 0, 128),
           (255, 255, 255)]
levels = [1.0, 0.5, 0.25, 0.1]

script_dir = Path(__file__).parent
patterns_dir = script_dir / "Patterns"
settings_path = script_dir / ".led_cube_settings.json"

# ----------------------------------------------------------------- state ----
frames = [new_frame()]
frameNo = 0
run_frames = False
display_end_time = 0
block_start = None      # inclusive frame numbers set with the Start / End buttons
block_end = None
clipboard = []
button_registry = {}
base_colour = palette[0]
level = 0               # index into levels
current_layer = 0       # z of the last LED clicked; Fill/Clear layer act on it

try:
    last_serial_port = json.loads(settings_path.read_text()).get("serial_port")
except (OSError, ValueError, AttributeError):
    last_serial_port = None

pygame.init()
screen = pygame.display.set_mode(window_size)
pygame.display.set_caption("5 x 5 x 5 RGB LED Cube")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
small_font = pygame.font.SysFont("Arial", 14)

tk_root = tk.Tk()  # one hidden root owns every dialog
tk_root.withdraw()


def paint_colour():
    return tuple(int(channel * levels[level]) for channel in base_colour)


class Button:
    def __init__(self, x, y, width, height, buttonText="Button", onclickFunction=None):
        self.name = buttonText
        self.text = buttonText
        self.onclickFunction = onclickFunction
        self.fillColors = {"normal": "#ffffff", "hover": "#666666", "pressed": "#33aa33"}
        self.buttonSurface = pygame.Surface((width, height))
        self.buttonRect = pygame.Rect(x, y, width, height)
        self.alreadyPressed = False
        button_registry[self.name] = self
        self.set_text(buttonText)

    def set_text(self, new_text):
        self.text = new_text
        self.buttonSurf = font.render(self.text, True, (20, 20, 20))

    def process(self):
        mousePos = pygame.mouse.get_pos()
        self.buttonSurface.fill(self.fillColors["normal"])
        if self.buttonRect.collidepoint(mousePos):
            self.buttonSurface.fill(self.fillColors["hover"])
            if pygame.mouse.get_pressed(num_buttons=3)[0]:
                self.buttonSurface.fill(self.fillColors["pressed"])
                if self.onclickFunction and not self.alreadyPressed:
                    self.onclickFunction()
                    self.alreadyPressed = True
            else:
                self.alreadyPressed = False
        self.buttonSurface.blit(self.buttonSurf, [
            self.buttonRect.width / 2 - self.buttonSurf.get_rect().width / 2,
            self.buttonRect.height / 2 - self.buttonSurf.get_rect().height / 2,
        ])
        screen.blit(self.buttonSurface, self.buttonRect)


class TextBox:
    def __init__(self, text, position, text_color=(0, 0, 0), bg_color=(255, 255, 255), padding=15, use_font=None):
        self.text_color = text_color
        self.bg_color = bg_color
        self.padding = padding
        self.position = position
        self.font = use_font or font
        self.update_text(text)

    def update_text(self, new_text):
        self.text_surface = self.font.render(new_text, True, self.text_color)
        width, height = self.text_surface.get_size()
        self.rect = pygame.Rect(self.position[0], self.position[1], width + 2 * self.padding, height + 2 * self.padding)

    def draw(self, screen):
        pygame.draw.rect(screen, self.bg_color, self.rect)
        screen.blit(self.text_surface, (self.rect.x + self.padding, self.rect.y + self.padding))


# ------------------------------------------------------------- frame ops ----
def show_frame(number):
    """Make frame `number` current (clamped to the pattern)."""
    global frameNo
    frameNo = max(0, min(number, len(frames) - 1))

def set_frames(new_frames):
    """Replace the whole pattern, keeping at least one blank frame."""
    global frames
    frames = new_frames or [new_frame()]
    clear_block()
    show_frame(0)

def nextFrame():
    show_frame(frameNo + 1)

def previousFrame():
    show_frame(frameNo - 1)

def copyFrame():
    frames.insert(frameNo, copy.deepcopy(frames[frameNo]))

def speedup():
    frames[frameNo]["time"] = max(MIN_TIME, int(frames[frameNo]["time"] * 0.8))

def slowdown():
    frames[frameNo]["time"] = min(MAX_TIME, int(frames[frameNo]["time"] * 1.2))

def apply_time_to_all_frames():
    for frame in frames:
        frame["time"] = frames[frameNo]["time"]

def playFile():
    global run_frames, display_end_time
    display_end_time = pygame.time.get_ticks() + frames[frameNo]["time"]
    run_frames = True

def stop_play():
    global run_frames
    run_frames = False

def newFile():
    if messagebox.askyesno("New pattern", "Discard the current frames and start a new pattern?", parent=tk_root):
        set_frames([new_frame()])

# ------------------------------------------------------------ paint ops ----
def set_led(index, colour):
    frames[frameNo]["colours"][index] = list(colour)

def fill_layer():
    for index in layer_indices(current_layer):
        set_led(index, paint_colour())

def clear_layer():
    for index in layer_indices(current_layer):
        set_led(index, (0, 0, 0))

def fill_all():
    for index in range(len(XYZ)):
        set_led(index, paint_colour())

def clear_all():
    for index in range(len(XYZ)):
        set_led(index, (0, 0, 0))

def custom_colour():
    global base_colour, level
    rgb, _ = colorchooser.askcolor(color="#%02x%02x%02x" % base_colour, parent=tk_root, title="Paint colour")
    if rgb:
        base_colour = tuple(int(channel) for channel in rgb)
        level = 0

# ------------------------------------------------------------- block ops ----
def block_range():
    """Inclusive (start, end) of the selected block; just the current frame if none is set."""
    start = frameNo if block_start is None else min(block_start, len(frames) - 1)
    end = frameNo if block_end is None else min(block_end, len(frames) - 1)
    return min(start, end), max(start, end)

def update_block_text():
    if block_start is None and block_end is None:
        block_text.update_text("Block: current frame")
    else:
        start, end = block_range()
        block_text.update_text(f"Block: {start} - {end}")

def set_block_start():
    global block_start
    block_start = frameNo
    update_block_text()

def set_block_end():
    global block_end
    block_end = frameNo
    update_block_text()

def clear_block():
    global block_start, block_end
    block_start = block_end = None
    update_block_text()

def copy_block():
    global clipboard
    start, end = block_range()
    clipboard = copy.deepcopy(frames[start:end + 1])

def cut_block():
    global frames
    copy_block()
    start, end = block_range()
    del frames[start:end + 1]
    if not frames:
        frames = [new_frame()]
    clear_block()
    show_frame(start)

def paste_block():
    """Insert the copied frames after the current frame and move to the first of them."""
    if not clipboard:
        messagebox.showinfo("Paste", "Nothing copied yet. Use Copy or Cut first.", parent=tk_root)
        return
    frames[frameNo + 1:frameNo + 1] = copy.deepcopy(clipboard)
    clear_block()
    show_frame(frameNo + 1)

def reverse_block():
    start, end = block_range()
    frames[start:end + 1] = frames[start:end + 1][::-1]

# -------------------------------------------------------------- file ops ----
def file_dialog_dir():
    return patterns_dir if patterns_dir.is_dir() else script_dir

def openFile():
    filename = filedialog.askopenfilename(parent=tk_root, title="Open pattern file",
                                          initialdir=file_dialog_dir(), filetypes=bin_filetypes)
    if filename:
        try:
            set_frames(read_pattern(filename))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Open failed", str(exc), parent=tk_root)

def save_pattern_file():
    """Ask where to save the current frames; returns the path, or None if cancelled."""
    filename = filedialog.asksaveasfilename(parent=tk_root, title="Write pattern file",
                                            initialdir=file_dialog_dir(), defaultextension=".bin",
                                            filetypes=bin_filetypes)
    if not filename:
        return None
    write_pattern(filename, frames)
    return filename

def writeFile():
    save_pattern_file()

def quit_pressed():
    pygame.quit()
    sys.exit()

# -------------------------------------------------------------- playlist ----
def choose_playlist():
    """Build an ordered list of .bin files. Returns the list of paths, or None if cancelled."""
    files = []
    result = {"files": None}
    dialog = tk.Toplevel(tk_root)
    dialog.title("Playlist")
    dialog.attributes("-topmost", True)
    listbox = tk.Listbox(dialog, width=48, height=14, selectmode="single", exportselection=False)
    listbox.grid(row=0, column=0, rowspan=7, padx=10, pady=10)

    def refresh(select=None):
        listbox.delete(0, "end")
        for path in files:
            listbox.insert("end", Path(path).name)
        if select is not None and files:
            listbox.selection_set(select)
            listbox.see(select)

    def selected():
        choice = listbox.curselection()
        return choice[0] if choice else None

    def add():
        chosen = filedialog.askopenfilenames(parent=dialog, title="Add pattern files",
                                             initialdir=file_dialog_dir(), filetypes=bin_filetypes)
        files.extend(chosen)
        refresh(len(files) - 1)

    def remove():
        index = selected()
        if index is not None:
            del files[index]
            refresh(min(index, len(files) - 1))

    def move(delta):
        index = selected()
        if index is not None and 0 <= index + delta < len(files):
            files.insert(index + delta, files.pop(index))
            refresh(index + delta)

    def load():
        if files:
            result["files"] = list(files)
        dialog.destroy()

    for row, (label, command) in enumerate([("Add files...", add), ("Remove", remove),
                                            ("Move up", lambda: move(-1)), ("Move down", lambda: move(1))]):
        tk.Button(dialog, text=label, width=14, command=command).grid(row=row, column=1, padx=10, pady=3)
    tk.Button(dialog, text="Load", width=14, command=load).grid(row=5, column=1, padx=10, pady=(20, 3))
    tk.Button(dialog, text="Cancel", width=14, command=dialog.destroy).grid(row=6, column=1, padx=10, pady=3)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    tk_root.wait_window(dialog)
    return result["files"]

def playlist():
    """Load several files as one pattern; play, preview or write it as usual."""
    files = choose_playlist()
    if files:
        combined = []
        for path in files:
            combined.extend(read_pattern(path))
        set_frames(combined)

# ---------------------------------------------------------------- serial ----
def choose_port():
    global last_serial_port
    selected_port = simpledialog.askstring("Arduino connection", "Serial port (for example COM3):",
                                           initialvalue=last_serial_port or "COM3", parent=tk_root)
    if selected_port:
        last_serial_port = selected_port.strip()
        try:
            settings_path.write_text(json.dumps({"serial_port": last_serial_port}, indent=2))
        except OSError:
            pass
    return last_serial_port if selected_port else None

def arduino_port():
    return last_serial_port or choose_port()

def serial_error(title, exc):
    if isinstance(exc, SerialException):
        if messagebox.askyesno(title, f"{exc}\n\nChoose a different serial port?", parent=tk_root):
            choose_port()
    else:
        messagebox.showerror(title, str(exc), parent=tk_root)

def ask_after_preview():
    """Shown while the cube holds the last frame. Returns "again" or "resume"."""
    choice = {"value": "resume"}
    dialog = tk.Toplevel(tk_root)
    dialog.title("LED cube")
    dialog.attributes("-topmost", True)

    def pick(value):
        choice["value"] = value
        dialog.destroy()

    tk.Label(dialog, text="Preview complete. The cube is holding the last frame.", padx=20, pady=15).pack()
    buttons = tk.Frame(dialog, pady=10)
    buttons.pack()
    tk.Button(buttons, text="Show again", width=16, command=lambda: pick("again")).pack(side="left", padx=8)
    tk.Button(buttons, text="Resume random", width=16, command=lambda: pick("resume")).pack(side="left", padx=8)
    dialog.protocol("WM_DELETE_WINDOW", lambda: pick("resume"))
    tk_root.wait_window(dialog)
    return choice["value"]

def previewCube():
    port = arduino_port()
    if not port:
        return
    try:
        preview_frames(port, frames, after_preview=ask_after_preview)
    except Exception as exc:
        serial_error("LED cube preview failed", exc)

def saveToArduinoSD():
    """Save locally first, then write the same name (8.3 form) to the Arduino SD card."""
    port = arduino_port()
    if not port:
        return
    local_file = save_pattern_file()
    if local_file:
        sd_name, exact = suggest_sd_name(local_file)
    else:
        sd_name, exact = "PATTERN.BIN", False
    if not exact:
        sd_name = simpledialog.askstring("SD filename", "8.3 filename on SD card:", initialvalue=sd_name, parent=tk_root)
        if not sd_name:
            return
    try:
        write_frames_to_sd(port, sd_name, frames)
        messagebox.showinfo("LED cube", f"Saved {sd_name} to the Arduino SD card.", parent=tk_root)
    except Exception as exc:
        serial_error("SD card transfer failed", exc)

# --------------------------------------------------------------- buttons ----
bx, by = button_pos
Button(bx,       by,       90, 50, "New", newFile)
Button(bx + 100, by,       90, 50, "Open File", openFile)
Button(bx + 200, by,       90, 50, "Write File", writeFile)
Button(bx + 300, by,       90, 50, "Quit", quit_pressed)
Button(bx + 30,  by + 70,  46, 46, "<", previousFrame)
Button(bx + 240, by + 70,  46, 46, ">", nextFrame)
Button(bx,       by + 140, 100, 50, "copy Frame", copyFrame)
Button(bx + 110, by + 140, 100, 50, "Stop", stop_play)
Button(bx + 220, by + 140, 100, 50, "Play File", playFile)
Button(bx,       by + 210, 150, 50, "Apply to all frames", apply_time_to_all_frames)
Button(bx + 360, by + 210, 22, 20, " ▲", slowdown)
Button(bx + 360, by + 235, 22, 20, " ▼", speedup)
Button(bx,       by + 280, 60, 50, "Start", set_block_start)
Button(bx + 250, by + 280, 60, 50, "End", set_block_end)
Button(bx + 320, by + 280, 60, 50, "Clear", clear_block)
Button(bx,       by + 350, 90, 50, "Copy", copy_block)
Button(bx + 100, by + 350, 90, 50, "Cut", cut_block)
Button(bx + 200, by + 350, 90, 50, "Paste", paste_block)
Button(bx + 300, by + 350, 90, 50, "Reverse", reverse_block)
Button(bx,       by + 420, 100, 50, "Fill layer", fill_layer)
Button(bx + 110, by + 420, 100, 50, "Clear layer", clear_layer)
Button(bx + 220, by + 420, 100, 50, "Fill all", fill_all)
Button(bx + 330, by + 420, 100, 50, "Clear all", clear_all)
Button(bx,       by + 490, 130, 50, "Preview Cube", previewCube)
Button(bx + 140, by + 490, 130, 50, "Save to SD", saveToArduinoSD)
Button(bx + 280, by + 490, 130, 50, "Playlist", playlist)
Button(palette_pos[0] + 13 * (swatch + 6) + 20, palette_pos[1] - 8, 110, 50, "Custom...", custom_colour)

frame_text = TextBox("", (bx + 115, by + 70))
time_text = TextBox("", (bx + 165, by + 210))
block_text = TextBox("", (bx + 70, by + 280), padding=12)
layer_text = TextBox("", (bx + 300, by + 70), padding=12)
paint_text = TextBox("", (palette_pos[0], palette_pos[1] + 2 * (swatch + 6) + 10), padding=8, use_font=small_font)
update_block_text()

def show_text_boxes():
    frame_text.update_text(f"Frame {frameNo} of {len(frames) - 1}")
    time_text.update_text(f"Display Time {frames[frameNo]['time']}")
    layer_text.update_text(f"Layer {current_layer}")
    r, g, b = paint_colour()
    paint_text.update_text(f"Paint colour  R {r}  G {g}  B {b}      left-click paints, right-click switches off")
    for box in (frame_text, time_text, block_text, layer_text, paint_text):
        box.draw(screen)

# ------------------------------------------------------------ cube layout ----
led_rect = [None] * len(XYZ)    # by chain index
row_labels = []
for z in range(SIZE):
    row = SIZE - 1 - z          # top layer drawn at the top of the window
    for y in range(SIZE):
        for x in range(SIZE):
            pos = (h_offset + x * h_spacing + y * h_stagger, v_offset + row * v_spacing + y * v_stagger)
            led_rect[led_index(x, y, z)] = pygame.Rect(pos, (circlesize, circlesize))
    label = "top" if z == SIZE - 1 else "bottom" if z == 0 else ""
    row_labels.append(small_font.render(f"z = {z} {label}".strip(), True, (160, 160, 160)))

swatch_rects = [pygame.Rect(palette_pos[0] + i * (swatch + 6), palette_pos[1], swatch, swatch) for i in range(len(palette))]
level_rects = [pygame.Rect(palette_pos[0] + i * (swatch + 6), palette_pos[1] + swatch + 6, swatch, swatch) for i in range(len(levels))]

def click_at(pos, button):
    global base_colour, level, current_layer
    for index, rect in enumerate(led_rect):
        if rect.collidepoint(pos):
            current_layer = XYZ[index][2]
            set_led(index, paint_colour() if button == 1 else (0, 0, 0))
            return
    for i, rect in enumerate(swatch_rects):
        if rect.collidepoint(pos):
            base_colour = palette[i]
            return
    for i, rect in enumerate(level_rects):
        if rect.collidepoint(pos):
            level = i
            return

def draw_cube():
    colours = frames[frameNo]["colours"]
    for index, rect in enumerate(led_rect):
        x, y, z = XYZ[index]
        r, g, b = colours[index]
        colour = (r, g, b) if (r or g or b) else off_colours[y]
        pygame.draw.circle(screen, colour, rect.center, circlesize / 2)
    for z, label in enumerate(row_labels):
        screen.blit(label, (h_offset, v_offset + (SIZE - 1 - z) * v_spacing + 4 * v_stagger - 20))

def draw_palette():
    for i, rect in enumerate(swatch_rects):
        pygame.draw.rect(screen, palette[i], rect)
        if palette[i] == base_colour:
            pygame.draw.rect(screen, (255, 255, 255), rect.inflate(6, 6), 2)
    for i, rect in enumerate(level_rects):
        pygame.draw.rect(screen, tuple(int(channel * levels[i]) for channel in base_colour), rect)
        if i == level:
            pygame.draw.rect(screen, (255, 255, 255), rect.inflate(6, 6), 2)
    preview = pygame.Rect(level_rects[-1].right + 20, level_rects[0].top, 3 * swatch, swatch)
    pygame.draw.rect(screen, paint_colour(), preview)
    pygame.draw.rect(screen, (200, 200, 200), preview, 1)
    screen.blit(small_font.render("paint", True, (160, 160, 160)), (preview.right + 8, preview.top + 9))

# ------------------------------------------------------------- main loop ----
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            quit_pressed()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            click_at(event.pos, event.button)
    screen.fill((0, 0, 0))
    draw_cube()
    draw_palette()
    for btn in button_registry.values():
        btn.process()
    show_text_boxes()
    pygame.display.flip()
    if run_frames:
        now = pygame.time.get_ticks()
        if now >= display_end_time:
            show_frame((frameNo + 1) % len(frames))
            display_end_time = now + frames[frameNo]["time"]
    clock.tick(60)
