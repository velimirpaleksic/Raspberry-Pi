# First boot redoslijed i printer support matrix

## First boot redoslijed
1. Raspberry Pi OS boot
2. systemd pokrene launcher
3. Health screen provjeri DB, template, jobs dir, soffice, lp, printer, disk
4. Ako setup nije završen -> Setup Wizard
5. PIN -> brojač/godina -> printer -> template -> završetak
6. Start ekran sa setup score statusom

## Printer support matrix

### Najbolji slučaj
- već dodan CUPS printer
- test print po printeru
- selekcija aktivnog queue-a

### Vrlo dobar slučaj
- driverless IPP / IPPS printer
- setup wizard može otkriti URI i dodati queue

### Dobar fallback
- socket://9100 ili lpd:// printer
- ručni URI unos iz admin/setup panela

### Servisni fallback
- vendor-specific USB driver koji ne radi driverless
- dodaj ga kroz OS/CUPS/HPLIP pa se onda vrati u wizard i testiraj

## Restore politika
- settings only: sigurno
- template only: sigurno
- settings + template: preporučeno za redeploy
- DB restore: radi samo offline servisno
