# Setup Wizard (touchscreen)

Nakon prvog boota terminal automatski ulazi u Setup Wizard ako `setup_completed=0`.

Koraci:
1. Postavi admin PIN
2. Podesi brojač i year mode
3. Osvježi listu printera, uradi **Test print** na željenom printeru, zatim klikni **Odaberi ovaj printer**
4. Završi setup

## Važno
- Printer se ne može postaviti kao aktivni dok prethodno ne pošalješ test stranicu na taj isti queue.
- Ako više printera postoji u CUPS-u, test stranicom potvrđuješ koji je fizički printer reagovao.
- Setup se kasnije može ponovo otvoriti sa početnog ekrana (`SETUP`) ili iz admin panela (`Setup wizard`).
