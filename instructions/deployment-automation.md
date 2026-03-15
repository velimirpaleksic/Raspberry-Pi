# Deployment automation

Ovaj projekat sada ima tri praktične skripte za teren i image workflow.

## 1. Factory reset za redeploy

Skripta: `scripts/factory_reset_for_redeploy.sh`

Namjena:
- briše lokalnu runtime bazu, jobove, exporte i logove
- pravi backup u `/var/tmp/...`
- nakon restarta servis ponovo kreira praznu bazu i terminal se vraća na setup wizard

Pokretanje:

```bash
sudo ./scripts/factory_reset_for_redeploy.sh --yes
```

Koristi kada:
- seliš terminal u drugu školu
- želiš čist redeploy bez starog audit sadržaja
- želiš vratiti uređaj na “first boot” stanje

## 2. Priprema image-a za kloniranje

Skripta: `scripts/prepare_image_for_clone.sh`

Namjena:
- uradi cleanup
- ukloni runtime tragove iz aplikacije
- ostavi image spremnijim za kloniranje

Pokretanje:

```bash
sudo ./scripts/prepare_image_for_clone.sh --yes
```

Nakon toga ručno provjeri:
- hostname strategiju
- machine-id strategiju
- da li image želiš odmah ugasiti i klonirati

## 3. Acceptance check nakon deploya

Skripta: `scripts/deployment_acceptance_check.sh`

Namjena:
- brza provjera da li su servis, CUPS i health sloj živi

Pokretanje:

```bash
sudo ./scripts/deployment_acceptance_check.sh
```

## Preporučeni redoslijed za finalni deploy

1. Flash Raspberry Pi OS image
2. Pokreni installer projekta
3. Reboot
4. Prođi touchscreen setup wizard
5. Uradi printer test i template validation
6. Uradi test notifikacije
7. Otvori `Production readiness`
8. Pokreni `deployment_acceptance_check.sh`
9. Tek onda terminal smatraj spremnim za školu
