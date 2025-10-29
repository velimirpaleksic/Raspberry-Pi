# Automatsko Printanje Školskih Potvrda

**Automatizovani sistem za generisanje i printanje školskih potvrda**, dizajniran da ubrza rad sekretara i smanji manuelni rad sa dokumentima.

---

## 🎯 Svrha projekta

Sekretar u školi često mora ručno ispisivati potvrde za učenike. Ovaj program:

* Automatizuje **generisanje dokumenata** u PDF formatu
* Omogućava **instant printanje** na HP printer
* Ubrzava proces tako da učenici sami mogu preuzeti dokument, a sekretar samo **potpisuje i pečatira**

---

## 📝 Glavne funkcionalnosti

1. **Generisanje PDF dokumenata** iz unaprijed definisanih šablona (DOCX → PDF)
2. **Unos podataka preko Tkinter GUI-a**
   * Polja: Razred, Struka, Razlog, Ime učenika itd.
   * Debug mode može automatski popuniti polja sa dummy podacima

3. **Printanje** na HP printer preko CUPS-a (Linux / Raspberry Pi)
   * Podržava **USB i mrežne printere**

4. **Višestruki ekrani u GUI-u**
   * Početni tutorijal / upute
   * Unos podataka
   * Završetak / potvrda printanja

5. **Konfiguracija i prilagodba**
   * Dropdown liste i placeholder-i u `config.py`
   * Admini mogu mijenjati vrijednosti ako se nešto promijeni

6. **Logging i debug**
   * Svi print jobovi i greške se loguju za lakše praćenje

7. **Validacija imena učenika** i drugih polja (u planu za buduće verzije)

---

## 🛠️ Tehnički zahtjevi

### Python paketi

`requirements.txt`:

```
pycups
python-docx
```

### Linux / Raspberry Pi sistemski paketi

```bash
sudo apt update
sudo apt install -y python3-tk libreoffice hplip printer-driver-hpcups
```

* **CUPS** – za printanje PDF-a
* **HPLIP** – HP driveri
* **LibreOffice** – konverzija DOCX → PDF

---

## ⚙️ Konfiguracija

Sve liste i placeholderi su u `config.py`:

```python
RAZREDI = ["ПРВИ", "ДРУГИ", "ТРЕЋИ", "ЧЕТВРТИ"]
STRUKE = ["МАШИНСТВО И ОБРАДА МЕТАЛА", "ЕКОНОМИЈА", "ЕЛЕКТРОТЕХНИКА"]
RAZGOVORI = ["УЧЛАЊЕЊА У ОМЛАДИНСКУ ЗАДРУГУ", "ПРЕПИС СВЈЕДОЧАНСТВА", "ПОТВРДА О СТАТУСУ"]
```

Admini mogu mijenjati ove liste ako se pravila promijene.

---

## 🚀 Korištenje

### 1. Pokretanje GUI-a

```bash
python main.py
```

* Prikazuje tutorijal
* Zatim unos podataka
* Na kraju potvrda i print

### 2. Printanje dokumenta

```python
from print_subprocess import print_docx

success = print_docx("template.docx", printer="HP_OfficeJet")
if success:
    print("Print job completed successfully")
else:
    print("Print job failed")
```

---

## 🧩 Debugging

* Uključivanjem **debug mode** polja se popunjavaju dummy podacima
* Logovi se čuvaju u `logs/` folderu


## License
This script is provided under the [MIT License](LICENSE).  

By using this script, you agree to comply with all applicable laws and regulations and use it only for lawful, ethical purposes.