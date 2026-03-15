# Telegram remote status bot

Ovaj sloj koristi isti Telegram bot token i chat ID koji su već podešeni u admin panelu.

Podržane komande:
- `/status`
- `/health`
- `/readiness`
- `/printer`
- `/network`
- `/analytics`
- `/help`

## Ručni test
```bash
python -m project.core.maintenance_cli telegram-poll-once --timeout-seconds 1
```

## Kontinuirani poll loop
Primjer systemd jedinice je u:
- `deploy/systemd/uvjerenja-telegram-remote.service.example`

Skripta za loop je u:
- `scripts/telegram_remote_poll_loop.sh`

## Napomena
Trenutno je implementiran polling model, ne webhook model. To je jednostavnije za Raspberry Pi terminal i radi iza NAT-a bez dodatnog reverse proxy sloja.
