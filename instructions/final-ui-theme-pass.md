# Final UI theme pass

Ovaj patch uvodi jedan zajednički dark appliance theme za kiosk terminal.

## Šta je cilj
- konzistentan kontrast na touch ekranu
- veći i čitljiviji touch targeti
- isti vizuelni jezik za setup, admin, health i readiness ekrane
- manje ručnog stilizovanja po pojedinačnim ekranima

## Kako radi
- `project/gui/ui_components.py` sada sadrži centralni theme/palette sloj
- `ScreenManager` radi automatski theme pass pri kreiranju i prikazu ekrana
- touch dijalozi i virtual keyboard koriste isti vizuelni stil

## Praktična korist
- novi/dinamički admin sadržaj se automatski približava istom vizuelnom stilu
- budući ekrani mogu koristiti postojeće helper funkcije bez posebnog ručnog stilizovanja
