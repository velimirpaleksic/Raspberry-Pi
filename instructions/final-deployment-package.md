# Finalni deployment paket

## Cilj
Da teren setup izgleda ovako:
1. Flash SD kartice ili prebuilt image
2. Prvi boot Raspberry Pi uređaja
3. Health screen
4. Setup wizard
5. Test print po printeru
6. Import template-a
7. Test notifikacija
8. Backup na USB

## Šta se radi 0 puta po školi
Ako koristiš prebuilt image:
- OS + desktop
- CUPS / NetworkManager / LibreOffice paketi
- app deploy
- systemd servis
- cleanup timer
- launcher skripte

## Šta se radi 1 put po školi
- admin PIN
- terminal name / location
- idle/display postavke
- Wi‑Fi ili LAN potvrda
- printer izbor/test
- template import
- Telegram/Discord test
- backup export na USB

## Šta ostaje servisni fallback
- egzotični printer driver setup
- full DB restore dok app radi
- hardverski problemi: USB, napajanje, touchscreen, SD kartica

## Minimalni acceptance test
- Health prolazi ili postoje jasni recovery koraci
- Setup checklist > 80%
- Test print prolazi
- Jedan pravi dokument prolazi kroz DOCX → PDF → print
- Backup export radi na USB
- Recovery ekran daje smislen korak za printer i mrežu
