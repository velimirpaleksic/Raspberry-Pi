# Uvjerenja Terminal (Raspberry Pi)

Appliance-style sistem za generisanje i štampanje školskih potvrda (DOCX → PDF → CUPS print), dizajniran da radi **"zero‑touch"**: uključiš Raspberry Pi i aplikacija radi sama.

## Instalacija (preporučeno)

Na Raspberry Pi OS (Desktop/X11):

```bash
chmod +x install_uvjerenja_terminal.sh
./install_uvjerenja_terminal.sh
```

Skripta radi:
- instalira sistemske pakete (Tkinter, CUPS, LibreOffice headless, HP driveri)
- deploy koda u `/opt/uvjerenja-terminal/src` i venv u `/opt/uvjerenja-terminal/venv`
- kreira config u `/etc/uvjerenja-terminal/uvjerenja-terminal.env`
- kreira job queue/output u `/var/lib/uvjerenja-terminal/jobs`
- instalira i starta systemd servis `uvjerenja-terminal.service`
- (opciono) pokreće touchscreen kalibraciju (X11)

### Logovi

```bash
sudo journalctl -u uvjerenja-terminal.service -f
```

### Konfiguracija

```bash
sudo nano /etc/uvjerenja-terminal/uvjerenja-terminal.env
sudo systemctl restart uvjerenja-terminal.service
```

Najvažnije varijable:
- `POTVRDE_PRINTER_NAME` (CUPS queue name)
- `POTVRDE_DJELOVODNI_BROJ`
- `POTVRDE_VAR_DIR` (default `/var/lib/uvjerenja-terminal`)
- `POTVRDE_TEMPLATE_PATH` (default `project/docs/template.docx`)

## Pokretanje (dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m project.core.app
```

## Struktura (bitno)

- `project/gui/` – Tkinter UI (Start → Form → Review → Printing → Done)
- `project/services/print_job.py` – backend pipeline (DOCX→PDF→print)
- `project/core/config.py` – config iz ENV (systemd EnvironmentFile)
- `project/docs/template.docx` – DOCX template

## Licence
MIT (vidi `LICENSE`).
