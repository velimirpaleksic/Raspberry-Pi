# Prebuilt image factory flow

Ovo je praktični završni workflow za pretvaranje projekta u gotov Raspberry Pi image koji se može više puta klonirati.

## 1. Golden uređaj
Na jednom Raspberry Pi uređaju uradi:
- instalaciju OS-a
- aplikacije i systemd servisa
- CUPS/driver osnovu
- touchscreen test
- setup wizard test
- acceptance check

## 2. Sanitize prije kloniranja
Pokreni:

```bash
sudo ./scripts/prepare_image_for_clone.sh --yes
```

Po potrebi dodatno:
- očisti Wi-Fi konekcije koje ne želiš dijeliti
- ukloni privatne bot/webhook kredencijale ako image ide za više lokacija

## 3. Release bundle
Pokreni:

```bash
./scripts/build_prebuilt_release_bundle.sh
```

Time dobijaš bundle sa systemd jedinicama, pratećim skriptama i release manifestom.

## 4. Kloniranje image-a
Napravi SD image sa provjerenog uređaja tek nakon sanitize koraka.

## 5. Prvi boot klona
Na kloniranom uređaju:
- first boot finalize servis zapisuje manifest i health rezultat
- pokreni setup wizard ako uređaj ide na novu lokaciju
- uradi test printera, template validaciju i readiness check

## 6. Dvije strategije distribucije
### A. Semi-configured image
Image već sadrži aplikaciju i servisni sloj, ali setup wizard ostaje otvoren za svaku školu.

### B. Fully configured per-site image
Image je već vezan za jednu lokaciju/printer/template. Ovo je brže, ali manje fleksibilno i traži pažljiviji backup/reset model.
