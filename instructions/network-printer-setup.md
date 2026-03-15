# Network printer setup (touchscreen flow)

## Gdje se koristi
- Setup wizard → korak **Printer**
- Admin panel → **Setup printera** ili **Setup wizard** na printer koraku

## Preporučeni redoslijed
1. Klikni **Pronađi mrežne URI-jeve**.
2. Ako vidiš svoj printer, klikni **Dodaj i postavi aktivni**.
3. Nakon toga uradi **Test print** na novom queue-u.
4. Tek kad fizički printer reaguje, klikni **Odaberi ovaj printer**.

## Ako printer nije automatski pronađen
Ručno unesi:
- **Queue name**: npr. `office_printer`
- **URI**: npr. `ipp://192.168.1.50/ipp/print`

Podržani URI prefiksi:
- `ipp://`
- `ipps://`
- `socket://`
- `lpd://`
- `dnssd://`
- `mdns://`

## Napomena
Za modernije mrežne printere najbolji rezultat je obično sa `ipp://` ili `ipps://` driverless setupom.
Ako `socket://` setup ne radi, pokušaj pronaći IPP/Bonjour URI preko mrežne pretrage.
