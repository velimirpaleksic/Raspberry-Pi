# Touchscreen Wi‑Fi setup

## Šta je novo

Sistem sada ima poseban **Mreža / Wi‑Fi** ekran dostupan iz:
- Setup Wizarda
- Admin dashboarda

## Šta može

- prikazati trenutni mrežni status
- prikazati IP adrese i aktivnu konekciju
- skenirati Wi‑Fi mreže
- touchscreen unos SSID-a i lozinke
- povezati se na Wi‑Fi preko `nmcli` / NetworkManager-a
- prikazati sačuvane Wi‑Fi konekcije i obrisati ih

## Napomena

Za puni touchscreen Wi‑Fi setup potreban je:
- `network-manager`
- aktivan `NetworkManager.service`
- dostupan `nmcli`

Ako `nmcli` nije dostupan, ekran će i dalje prikazivati dijagnostiku, ali neće moći uspostaviti novu Wi‑Fi konekciju.

## Preporučeni flow na terenu

1. Upali Raspberry Pi
2. Prođi Health screen
3. Otvori Setup Wizard
4. Klikni **Mreža / Wi‑Fi**
5. Skeniraj mreže
6. Testiraj/unesi SSID i lozinku
7. Vrati se u Setup Wizard i nastavi printer/template setup
