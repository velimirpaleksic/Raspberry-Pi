# Template validation

## Šta sada radi sistem
Prije aktivacije novog template-a sistem radi:
- provjeru da je fajl stvarni `.docx`
- otvaranje template-a kroz `python-docx`
- provjeru svih obaveznih placeholdera
- probni render sa lažnim podacima
- probni DOCX → PDF render bez slanja na printer

## Obavezni placeholderi
- `{{DJELOVODNI_BROJ}}`
- `{{DANASNJI_DATUM}}`
- `{{IME}}`
- `{{RODITELJ}}`
- `{{DATUM_RODJENJA}}`
- `{{MJESTO}}`
- `{{OPSTINA}}`
- `{{RAZRED}}`
- `{{STRUKA}}`
- `{{RAZLOG}}`

## Kako koristiti u UI
### Setup wizard
- otvori **Template** korak
- klikni **Provjeri aktivni template** ili **Provjeri template** na USB kandidatu
- pregledaj report
- tek onda uvezi i aktiviraj

### Admin panel
- otvori **Template / USB**
- validiraj aktivni template ili USB kandidat
- report ide u output panel

## Kako čitati rezultat
- `Status: OK` znači da template ima sve placeholder-e i da je prošao probe tok
- `Probe render: OK` znači da je DOCX → PDF probni render prošao
- `Probe render: WARN/FAIL` znači da je template čitljiv, ali PDF probni render nije potvrđen i treba provjeriti LibreOffice / soffice sloj

## Preporučeni teren test
Nakon validacije uradi i:
1. jedan test print
2. jedan pravi dokument
3. backup export na USB
