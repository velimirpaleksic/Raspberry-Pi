import tkinter as tk
from tkinter import messagebox
from docx import Document
import os

# Path to your template file
TEMPLATE_FILE = "docs/template.docx"
OUTPUT_FILE = "docs/output.docx"
PRINTER_NAME = "Printer_Name"

root = tk.Tk()
root.title("Window")
root.geometry("800x600")

# Input field
entry = tk.Entry(root, font=("Arial", 18))
entry.pack(pady=20, padx=20, fill="x")

# Virtual keyboard layout with šđčćž
keyboard_rows = [
    list("qwertyuiop"),
    list("asdfghjklšđ"),
    list("zxcvbnmčćž"),
    ["Space", "Backspace", "Clear"]
]

def key_press(key):
    if key == "Space":
        entry.insert(tk.END, " ")
    elif key == "Backspace":
        current_text = entry.get()
        entry.delete(0, tk.END)
        entry.insert(0, current_text[:-1])
    elif key == "Clear":
        entry.delete(0, tk.END)
    else:
        entry.insert(tk.END, key)

# Build virtual keyboard
keyboard_frame = tk.Frame(root)
keyboard_frame.pack()

for row in keyboard_rows:
    row_frame = tk.Frame(keyboard_frame)
    row_frame.pack(pady=5)
    for key in row:
        btn = tk.Button(row_frame, text=key, width=6, height=2, command=lambda k=key: key_press(k))
        btn.pack(side="left", padx=2)

# Save and update document
def save_document():
    name = entry.get()
    if not name:
        messagebox.showerror("Error", "Please type a name first!")
        return

    # Load template
    doc = Document(TEMPLATE_FILE)

    # Replace placeholder {{NAME}} with actual name
    for p in doc.paragraphs:
        if "{{NAME}}" in p.text:
            p.text = p.text.replace("{{NAME}}", name)

    # Save new file
    doc.save(OUTPUT_FILE)
    messagebox.showinfo("Success", f"Document saved as {OUTPUT_FILE}")

    # Send to printer (Linux command)
    os.system(f"libreoffice --headless --pt '{PRINTER_NAME}' {OUTPUT_FILE}")

    # Delete file after printing
    os.remove(OUTPUT_FILE)

# Print button
print_btn = tk.Button(root, text="Print", font=("Arial", 14), command=save_document)
print_btn.pack(pady=20)

root.mainloop()
