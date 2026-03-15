# Prebuilt image runbook

## Cilj
Da deployment po školi bude:
1. flash SD kartice
2. prvi boot
3. health + setup wizard
4. test print
5. import template
6. backup

## Master image priprema
Na referentnom Raspberry Pi uređaju:
- instaliraj Raspberry Pi OS with desktop
- instaliraj app i zavisnosti
- potvrdi da rade:
  - systemd servis
  - launcher skripta
  - cleanup timer
  - CUPS
  - NetworkManager
  - LibreOffice / soffice
- vrati `setup_completed=0`
- obriši stvarne tokene i lokalne backup bundle-ove
- ugasi uređaj
- napravi master image SD kartice

## Šta mora ostati generičko
- admin PIN može biti default samo za staging
- bez produkcijskog printer queue-a druge škole
- bez Telegram tokena/chat ID-a
- bez lokalne produkcijske baze druge škole

## Acceptance test poslije flash-a
- sistem boota direktno u app
- health ekran radi
- setup wizard se otvara kada `setup_completed=0`
- mreža se može podesiti touch ekranom
- printer se može testirati po queue-u
- template se može validirati i aktivirati
- readiness ekran ne pokazuje kritične blockere

## Kada raditi novi master image
- poslije većeg UI/DB patcha
- poslije promjene systemd/launcher logike
- poslije promjene printer setup toka
- poslije promjene setup wizard koraka
