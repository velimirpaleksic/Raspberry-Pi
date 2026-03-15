# Prebuilt image workflow

## Cilj
Da teren setup bude:
1. flash SD kartice
2. prvi boot
3. touchscreen setup wizard
4. gotovo

## Minimalni workflow
- pripremi referentni Raspberry Pi
- instaliraj pakete i app
- potvrdi da launcher, systemd i cleanup timer rade
- očisti osjetljive podatke (tokeni, chat ID, aktivni printer, backup bundle-ovi)
- ostavi `setup_completed=0`
- ugasi uređaj
- kloniraj SD karticu kao master image

## Šta image treba već sadržati
- Raspberry Pi OS with desktop
- CUPS i osnovne printer alate
- LibreOffice / soffice
- aplikaciju i systemd servis
- launcher skriptu
- setup wizard kao first-boot tok

## Šta NE treba bake-ovati u image
- stvarni Telegram token
- stvarni chat ID
- stvarni aktivni printer queue za drugu školu
- lokalni backup bundle-ovi
- produkcijske baze iz druge škole

## Deployment po školi
- ubaci SD
- boot
- setup wizard
- test print po printeru
- import template
- test notifikacija
- backup na USB
