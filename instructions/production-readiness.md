# Production readiness ekran

Ovaj ekran daje operativni odgovor na pitanje da li je terminal spreman za produkcijski rad bez nadzora.

## Šta prikazuje
- ukupni readiness score
- startup health rezultat
- setup checklist rezultat
- blockers
- warnings i preporuke
- acceptance / teren check korake

## Kako koristiti
1. Otvori ekran `SPREMNOST` sa start ekrana ili `Production readiness` iz admin panela.
2. Ako postoje **BLOCKER** stavke, prvo njih zatvori.
3. Kada blocker-a nema, prođi acceptance listu na stvarnom Raspberry Pi uređaju.
4. Tek nakon toga pusti terminal u redovan rad.

## Savjet
Readiness ekran nije zamjena za stvarni test printera i probnu potvrdu. On je centralni pregled stanja i najbrži ulaz na tačne popravke.
