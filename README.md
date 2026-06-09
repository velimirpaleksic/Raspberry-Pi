# Uvjerenja Terminal MVP (Raspberry Pi)

Minimalna ručno-pokretana verzija za izdavanje i štampanje školskih uvjerenja.

## Šta radi
- start ekran sa jednim velikim dugmetom **ЗАПОЧНИ**
- unos podataka
- provjera unosa sa povratkom nazad
- pokušaj štampe
- jasna poruka ako štampa ne uspije
- retry dugme nakon neuspjele štampe
- success ekran
- `Escape` za izlaz iz aplikacije

## Šta je uklonjeno
- admin panel
- tutorial ekran
- baza
- stari hardkodirani autostart pri bootu
- systemd GUI servis

## Lokalno pokretanje iz repoa

Pokreni iz desktop terminala, ne iz SSH/TTY bez GUI display-a:

```bash
chmod +x run_uvjerenja_terminal.sh
./run_uvjerenja_terminal.sh
```

## Telegram kontrola

Aplikacija moze pokrenuti Telegram bot za daljinsku kontrolu. Podesavanja su u `.env`:

```env
POTVRDE_TELEGRAM_BOT_TOKEN="PASTE_TELEGRAM_BOT_TOKEN_HERE"
POTVRDE_TELEGRAM_ALLOWED_USER_ID="6598155929"

Ne objavljuj pravi Telegram bot token u GitHub repo, ZIP fajl ili screenshot. Koristi `.env.example` kao šablon, a pravi token drži samo lokalno na Raspberry Pi ili u `/etc/uvjerenja-terminal/uvjerenja-terminal.env`. Ako token slučajno izađe van, napravi novi token kroz BotFather.
```

Bot odgovara samo privatnom chatu sa korisnikom `6598155929`.
Nakon instalacije na Raspberry Pi, podesavanja se cuvaju u `/etc/uvjerenja-terminal/uvjerenja-terminal.env`.
Ako taj fajl vec postoji, installer ga ne pregazi; tada ponovo upisi token tamo ili ukloni fajl prije nove instalacije.

Podrzane komande:
- `/help` prikazuje dostupne komande
- `/status` prikazuje app, Telegram, slobodan prostor, internet/Wi-Fi i printer status
- `/space` prikazuje slobodan prostor na Raspberry Pi-ju
- `/ping` provjerava da Telegram bot odgovara
- `/network` prikazuje internet/Wi-Fi diagnostiku
- `/reconnectwifi` pokusava ponovo povezati Wi-Fi/network
- `/restartcups` restartuje CUPS servis za stampu
- `/logs` prikazuje zadnje greske iz loga
- `/openapp` prikazuje kiosk prozor ako je sakriven
- `/closeapp` sakriva kiosk prozor, ali Telegram kontrola ostaje aktivna
- `/restartapp` restartuje/ponovo otvara kiosk aplikaciju
- `/reopen` alias za `/restartapp`
- `/unlock` skida update/input lock ako ekran ostane zakljucan
- `/restart` restartuje Raspberry Pi
- `/update` zakljuca ekran/tastaturu/mis, azurira projekat, zatim otvara novu verziju aplikacije
- `/printers` prikazuje dostupne CUPS printere, CUPS default i printer koji aplikacija koristi
- `/setprinter IME_PRINTERA` postavlja aktivni printer u aplikaciji i CUPS default printer
- `/usecupsdefault` brise izbor printera u aplikaciji i koristi trenutni CUPS default

Telegram `/update` je podesen kroz `.env` da pokrece `bash ./update_uvjerenja_terminal.sh`.
Taj script pull-a iz:

```text
https://github.com/velimirpaleksic/Raspberry-Pi.git
```

Podrazumijevani update radi ovako:
- ako source repo ne postoji, clone-uje repo
- ako repo vec postoji, fetch-uje branch iz `origin`
- lokalni source resetuje na `origin/<branch>` da lokalne izmjene ne blokiraju update
- nakon toga pokrece `install_uvjerenja_terminal.sh`
- nakon uspjesnog update-a Telegram bot pokrece launcher za novu verziju i zatvara staru aplikaciju

Lokaciju source repoa mozes promijeniti u `.env`:

```env
POTVRDE_UPDATE_SOURCE_DIR="/home/pi/Raspberry-Pi"
```

Launcher koji se pokrece nakon update-a mozes promijeniti u `.env`:

```env
POTVRDE_RELAUNCH_COMMAND="/usr/local/bin/uvjerenja-terminal-run"
```

Za `/restart` restart komanda mora raditi bez interaktivne sudo lozinke. Na Raspberry Pi-ju provjeri da korisnik koji pokrece aplikaciju moze izvrsiti:

```bash
sudo -n shutdown -r now
```

Printer se moze promijeniti dok aplikacija radi. Prvo posalji:

```text
/printers
```

Zatim izaberi tacno ime printera iz liste:

```text
/setprinter HP_LaserJet_Pro
```

Za trenutni Wi-Fi printer:

```text
/setprinter HP_LaserJet_M111w_AEC184
```

Izbor se cuva u `/var/lib/uvjerenja-terminal/settings.json`, pa ostaje aktivan i nakon restarta.

## Instalacija na Raspberry Pi

```bash
chmod +x install_uvjerenja_terminal.sh
./install_uvjerenja_terminal.sh
```

Tokom instalacije installer pita da li aplikacija treba da se automatski pokrene kada se otvori Raspberry Pi desktop. Možeš to zadati i bez pitanja:

```bash
./install_uvjerenja_terminal.sh --autostart
./install_uvjerenja_terminal.sh --no-autostart
```

Installer radi samo:
- deploy u `/opt/uvjerenja-terminal`
- virtualenv + Python paketi
- CUPS/LibreOffice dependencies
- desktop shortcut i menu entry za ručno pokretanje
- opciono autostart kroz `~/.config/autostart/uvjerenja-terminal.desktop`
- koristi **CUPS default printer** ako nije ručno upisan printer name

Nakon instalacije pokreći ručno preko desktop ikonice **Uvjerenja Terminal** ili komandom:

```bash
/usr/local/bin/uvjerenja-terminal-run
```

## Dodavanje printera i default printer

Detaljno:
- `instructions/printer-setup.txt`
- `instructions/printer-test.txt`

Najkraće:

```bash
sudo systemctl enable --now cups
sudo usermod -aG lpadmin $USER
sudo hp-setup -i
lpstat -p -d
sudo lpoptions -d IME_PRINTERA
```

Aplikacija zatim koristi taj CUPS default printer.

## Gdje se čuva PDF

Svaki print job dobije svoj folder u:

```text
/var/lib/uvjerenja-terminal/jobs/<job_id>/
```

Tu ostaju:
- `output.docx`
- `output.pdf`
- `job.json`

PDF se čuva i kada štampa ne uspije.

## Flow
`Start -> Form -> Review -> Printing -> Done`


## Napomena
- Početni ekran prikazuje samo dugme **ЗАПОЧНИ**.
- Automatski povratak na početak dešava se samo na završnom ekranu, nakon 10 sekundi.
