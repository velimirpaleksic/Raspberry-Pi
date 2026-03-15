# Raspberry Pi image checklist (Pi 3B+)

## Preporučeni image
- Raspberry Pi OS (32-bit) with desktop
- Raspberry Pi Imager za flashanje SD kartice
- 32 GB microSD kao praktičan minimum za GUI kiosk + logove + backup bundle-ove

## Imager customisation
- hostname: uvjerenja-terminal-01
- username: jedan servisni korisnik za kiosk
- locale/timezone
- Wi‑Fi samo ako stvarno treba
- SSH uključi samo za servisni pristup

## Nakon prvog boota
1. pokreni installer
2. restart uređaja
3. health screen
4. setup wizard
5. test print po printeru
6. import template
7. test notifikacija
8. backup na USB

## Production checklist
- touchscreen kalibrisan
- CUPS radi
- aktivni printer testiran
- setup_completed = 1
- backup testiran
- Telegram/Discord testiran
- disk prag podešen
