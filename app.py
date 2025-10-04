# app.py
import os
import sys
import datetime
import tkinter as tk
from tkinter import ttk
from config import TEMPLATE_FILE, OUTPUT_FILE, DJELOVODNI_BROJ, DANASNJI_DATUM, \
                   MJESTO_PLACEHOLDER, OPSTINA_PLACEHOLDER, LOG_FILENAME, DEBUG, \
                   DEBUG_DATA, RAZREDI, STRUKE, RAZLOZI
from ui_components import labeled_entry, info_box, user_error, error_window
from docx_utils import load_and_replace
from virtual_keyboard import VirtualKeyboard
from logging_utils import error_logging

# check template early
if not os.path.exists(TEMPLATE_FILE):
    # create a temp root to show error dialog and exit
    temp_root = tk.Tk()
    temp_root.withdraw()
    error_logging(temp_root, LOG_FILENAME, f"Template file does not exist: {TEMPLATE_FILE}", error_window)
    temp_root.destroy()
    sys.exit(1)

root = tk.Tk()
root.title("Window")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.bind("<Escape>", lambda e: root.destroy())

try:
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.geometry(f"{screen_w}x{screen_h}")
except:
    root.geometry("1920x1080")

main = tk.Frame(root, padx=20, pady=20)
main.pack(fill="both", expand=True)
main.columnconfigure(0, weight=1)
main.columnconfigure(1, weight=1)
main.columnconfigure(2, weight=1)

# Row 0
left_frame, ime_entry = labeled_entry(main, "Име и презиме ученика", placeholder=None)
left_frame.grid(row=0, column=0, padx=10, pady=8, sticky="nsew")

mid_frame, roditelj_entry = labeled_entry(main, "Име родитеља", placeholder=None)
mid_frame.grid(row=0, column=1, padx=10, pady=8, sticky="nsew")

tk.Frame(main).grid(row=0, column=2, padx=10, pady=8, sticky="nsew")

# Row 1 - date
date_frame = tk.Frame(main)
tk.Label(date_frame, text="Датум рођења").pack(anchor="w")
date_inner = tk.Frame(date_frame)
date_inner.pack(anchor="w", pady=2)

godina_var = tk.StringVar()
mjesec_var = tk.StringVar()
dan_var = tk.StringVar()

godine = list(range(2000, datetime.datetime.now().year + 1))
godina_cb = ttk.Combobox(date_inner, textvariable=godina_var, values=godine, state="readonly", width=8)
godina_cb.grid(row=0, column=0, padx=(0,6))
mjesec_cb = ttk.Combobox(date_inner, textvariable=mjesec_var, values=list(range(1,13)), state="disabled", width=6)
mjesec_cb.grid(row=0, column=1, padx=(0,6))
dan_cb = ttk.Combobox(date_inner, textvariable=dan_var, values=list(range(1,32)), state="disabled", width=6)
dan_cb.grid(row=0, column=2)

def on_godina_selected(event=None):
    mjesec_cb.config(state="readonly")
def on_mjesec_selected(event=None):
    dan_cb.config(state="readonly")

godina_cb.bind("<<ComboboxSelected>>", on_godina_selected)
mjesec_cb.bind("<<ComboboxSelected>>", on_mjesec_selected)
date_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")

# mjesto / opstina
mj_frame, mjesto_entry = labeled_entry(main, "Мјесто рођења", placeholder=MJESTO_PLACEHOLDER)
mj_frame.grid(row=1, column=1, padx=10, pady=8, sticky="nsew")
op_frame, opstina_entry = labeled_entry(main, "Општина", placeholder=OPSTINA_PLACEHOLDER)
op_frame.grid(row=1, column=2, padx=10, pady=8, sticky="nsew")

# Row 2 - comboboxes
razred_var = tk.StringVar()
struka_var = tk.StringVar()
reason_var = tk.StringVar()

f_r = tk.Frame(main)
tk.Label(f_r, text="Разред").pack(anchor="w")
razred_cb = ttk.Combobox(f_r, textvariable=razred_var, values=RAZREDI, state="readonly")
razred_cb.pack(fill="x")
f_r.grid(row=2, column=0, padx=10, pady=8, sticky="nsew")

f_s = tk.Frame(main)
tk.Label(f_s, text="Струка").pack(anchor="w")
struka_cb = ttk.Combobox(f_s, textvariable=struka_var, values=STRUKE, state="readonly")
struka_cb.pack(fill="x")
f_s.grid(row=2, column=1, padx=10, pady=8, sticky="nsew")

f_rz = tk.Frame(main)
tk.Label(f_rz, text="Разлог").pack(anchor="w")
reason_cb = ttk.Combobox(f_rz, textvariable=reason_var, values=RAZLOZI, state="readonly")
reason_cb.pack(fill="x")
f_rz.grid(row=2, column=2, padx=10, pady=8, sticky="nsew")

# Buttons
btn_frame = tk.Frame(main)
btn_frame.grid(row=3, column=0, columnspan=3, pady=12)

def submit():
    ime = ime_entry.get().strip()
    roditelj = roditelj_entry.get().strip()
    mjesto = mjesto_entry.get().strip()
    opstina = opstina_entry.get().strip()
    razred = razred_var.get()
    struka = struka_var.get()
    reason = reason_var.get()

    missing = []
    if not ime: missing.append("Име ученика")
    if not roditelj: missing.append("Име родитеља")
    if not godina_var.get() or not mjesec_var.get() or not dan_var.get():
        missing.append("Датум рођења")
    if not mjesto or mjesto == MJESTO_PLACEHOLDER: missing.append("Мјесто рођења")
    if not opstina or opstina == OPSTINA_PLACEHOLDER: missing.append("Општина")
    if not razred: missing.append("Разред")
    if not struka: missing.append("Струка")
    if not reason: missing.append("Разлог")

    if missing:
        user_error(root, "Морате попунити поље/поља:\n- " + "\n- ".join(missing))
        return

    datum_rodjenja = f"{dan_var.get()}.{mjesec_var.get()}.{godina_var.get()}"

    placeholders = {
        "{{DJELOVODNI_BROJ}}": DJELOVODNI_BROJ,
        "{{DANASNJI_DATUM}}": DANASNJI_DATUM,
        "{{IME}}": ime,
        "{{RODITELJ}}": roditelj,
        "{{DATUM_RODJENJA}}": datum_rodjenja,
        "{{MJESTO}}": mjesto,
        "{{OPSTINA}}": opstina,
        "{{RAZRED}}": razred,
        "{{STRUKA}}": struka,
        "{{REASON}}": reason,
    }

    try:
        load_and_replace(TEMPLATE_FILE, OUTPUT_FILE, placeholders)
    except Exception as e:
        error_logging(root, LOG_FILENAME, f"Failed to open/save template: {e}", error_window)
        return

    # --- print: File conversion and sending to printer ---
    from print_subprocess import print_docx

    try:
        ok, msg = print_docx(OUTPUT_FILE, printer=None)
        if ok:
            info_box(root, "Успјешно", "Документ је послан на принтер.")
        else:
            error_logging(root, LOG_FILENAME, f"Print error: {msg}", error_window)
            user_error(root, "Грешка при штампању:\n" + str(msg))
    except Exception as e:
        error_logging(root, LOG_FILENAME, f"Print failed (unexpected): {e}", error_window)

tk.Button(btn_frame, text="Испринтај", command=submit, bg="lightblue", padx=12, pady=6).pack()

# Virtual keyboard
kbd = VirtualKeyboard(root, mjesto_entry=mjesto_entry, opstina_entry=opstina_entry,
                      mjesto_placeholder=MJESTO_PLACEHOLDER, opstina_placeholder=OPSTINA_PLACEHOLDER)
kbd.pack(side="bottom", fill="x")

# Debug Data
if DEBUG:
    # Remove placeholder temporarily
    for e in [mjesto_entry, opstina_entry]:
        e.delete(0, "end")
        e.config(fg="black")

    # Fill with dummy data
    ime_entry.insert(0, DEBUG_DATA["IME"])
    roditelj_entry.insert(0, DEBUG_DATA["RODITELJ"])
    godina_var.set(DEBUG_DATA["GODINA"])
    mjesec_var.set(DEBUG_DATA["MJESEC"])
    dan_var.set(DEBUG_DATA["DAN"])
    mjesec_cb.config(state="readonly")
    dan_cb.config(state="readonly")
    mjesto_entry.insert(0, DEBUG_DATA["MJESTO"])
    opstina_entry.insert(0, DEBUG_DATA["OPSTINA"])
    razred_var.set(DEBUG_DATA["RAZRED"])
    struka_var.set(DEBUG_DATA["STRUKA"])
    reason_var.set(DEBUG_DATA["REASON"])


ime_entry.focus_set()
root.mainloop()