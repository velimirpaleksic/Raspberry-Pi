# admin/test_touch_screen.py
import tkinter as tk


root = tk.Tk()
root.geometry("400x400")

def clicked(e):
    print(f"Clicked at {e.x}, {e.y}")

root.bind("<Button-1>", clicked)
root.mainloop()