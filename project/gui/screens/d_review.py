import tkinter as tk

from project.gui import screen_ids


class ReviewScreen(tk.Frame):
    """Step 2/3: Review entered data before printing."""

    def __init__(self, parent, manager=None):
        super().__init__(parent)
        self.manager = manager

        self.title = tk.Label(self, text="Провјера података", font=("Arial", 28, "bold"))
        self.title.pack(pady=(30, 10))

        self.box = tk.Frame(self, padx=20, pady=20, relief="groove", bd=2)
        self.box.pack(padx=60, pady=10, fill="both", expand=False)

        self.lines = []
        for _ in range(6):
            lbl = tk.Label(self.box, text="", font=("Arial", 18), anchor="w", justify="left")
            lbl.pack(fill="x", pady=4)
            self.lines.append(lbl)

        btns = tk.Frame(self)
        btns.pack(pady=30)
        tk.Button(btns, text="Назад (исправи)", padx=18, pady=10, command=self._back).pack(side="left", padx=10)
        tk.Button(btns, text="ШТАМПАЈ", padx=22, pady=10, bg="lightblue", command=self._print).pack(side="left", padx=10)

    def on_show(self):
        data = (self.manager.state.get("form_data") if self.manager else None) or {}

        ime = data.get("ime", "")
        roditelj = data.get("roditelj", "")
        datum = f"{data.get('dan','')}.{data.get('mjesec','')}.{data.get('godina','')}"
        mjesto = data.get("mjesto", "")
        opstina = data.get("opstina", "")
        razred = data.get("razred", "")
        struka = data.get("struka", "")
        razlog = data.get("razlog", "")

        rows = [
            f"Име и презиме:  {ime}",
            f"Име родитеља:   {roditelj}",
            f"Датум рођења:   {datum}",
            f"Мјесто/Општина: {mjesto}, {opstina}",
            f"Разред/Струка:  {razred} / {struka}",
            f"Разлог:         {razlog}",
        ]
        for lbl, text in zip(self.lines, rows):
            lbl.config(text=text)

    def _back(self):
        if self.manager:
            self.manager.show_frame(screen_ids.FORM)

    def _print(self):
        if self.manager:
            self.manager.show_frame(screen_ids.PRINTING)
