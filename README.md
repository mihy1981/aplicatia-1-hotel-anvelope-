# 🛞 MADYT – Hotel Anvelope

Aplicație web (Streamlit) pentru hotelul de anvelope al SC Madyt Autoserv.
Baza de date este tabelul Google Sheets cu foaia **`Inventar GY`** (exportul GY Fleet). Merge pe telefon, tabletă și calculator.

## Pornire rapidă (sezonul de schimb)
1. Pașii 1–3 de mai jos (cont de serviciu, Share pe tabel ca Editor, secrets). ~15 minute.
2. La prima pornire aplicația **copiază** `Inventar GY` în foile ei (vezi mai jos). `Inventar GY` nu se modifică.
3. ⚙️ **Administrare poziții** → generează rândurile de raft (ex. R1–R10 pentru ARVAL, R11–R18 pentru Autotehnica, restul `COMUN`).
4. 🔁 **Schimb sezon**: scrii numărul auto, vezi anvelopele de pe raft și locația veche GY (ex. `D`), alegi poziția R-N-P (se propune prima liberă a flotei), completezi setul dat jos, confirmi.

## Ce face aplicația

| Tab | Ce faci acolo |
|---|---|
| 🔁 **Schimb sezon** | Scrii numărul auto → apare mare **codul poziției** (ex. `R1-N2-P3`) sau, dacă setul nu are încă poziție, **locația veche din GY** (`ServiceProviderStorageLocation`). Vezi fiecare anvelopă de pe raft (marcă, dimensiune, sezon, profil, DOT, jantă). Montezi setul, pui setul dat jos **în aceeași poziție** și îl completezi: **1–6 anvelope (implicit 4)**, fie **„Set comun”** (aceleași valori pentru toate), fie **„Pe fiecare anvelopă”** (tabel: profil, DOT, observații diferite; căsuța goală = valoarea comună). |
| 🔍 **Căutare stoc** | Câte un rând pe mașină (set): număr auto, VIN, flotă, anvelope, poziție, locație veche. |
| 📦 **Recepție client nou** | Propune prima poziție liberă (rândurile flotei, apoi comune). Anvelopele se introduc la fel ca la schimb. |
| 🚪 **Ieșire din hotel** | Status `RIDICAT`, data ieșirii, poziția se eliberează, anvelopele trec în arhivă. |
| 🗄️ **Rafturi** | Ocupare pe flote și rânduri, hartă rând, poziții libere, seturi încă pe locațiile vechi GY. |
| 📊 **Rapoarte** | Seturi / anvelope în hotel, **peste 180 de zile** (facturare suplimentară), **recomandări anvelope noi** (cel puțin o anvelopă sub 3 mm), seturi de verificat (≠ 4 anvelope sau sezoane amestecate), export CSV. |
| ⚙️ **Administrare poziții** | Generezi poziții, aloci rânduri unei flote sau `COMUN`. |
| 🔄 **GY Fleet** | **Import** din exportul GY Fleet (.xlsx/.csv) și **export** în același format (21 de coloane). |

**Codul poziției:** `R{rând}-N{nivel}-P{picior}`, de exemplu `R1-N1-P1`.
**Pragul de uzură (3 mm) și termenul (180 zile)** se schimbă din secrets (`worn_threshold_mm`, `storage_days_limit`).

### Foile din tabelul Google Sheets
- **`Inventar GY`** – exportul GY Fleet (o linie = o anvelopă). **Aplicația doar îl citește**, o singură dată, la prima pornire; nu scrie niciodată în el (codul refuză scrierea în orice foaie care nu e a aplicației). Dacă foaia nu există cu acest nume, se citește prima foaie. Numele se poate schimba cu `source_sheet` în secrets.
- Foile aplicației, create automat lângă `Inventar GY`:
  - **`Hotel_Anvelope`** – anvelopele aflate acum în hotel, **exact coloanele GY** (o linie = o anvelopă). Al doilea `CITY` (orașul service-ului) e salvat aici sub numele `CITY_2`.
  - **`Hotel`** – un rând pe mașină: `PositionCode`, `Status` (`DEPOZITAT`/`RIDICAT`), `StorageDate` (data depozitării / ultimului schimb, pentru regula de 180 zile), `Season`, `LegacyLocation` (locația veche GY), telefon, email. **Poziția și statusul nu se scriu niciodată în coloanele GY.**
  - **`Pozitii`** – `PositionCode`, `Row`, `Level`, `Leg`, `FleetName`/`COMUN`, `OccupiedPlate`.
  - **`Istoric`** – fiecare schimb, recepție, ieșire, import, cu ambele seturi, poziția și operatorul.
  - **`Arhiva_Anvelope`** – anvelopele scoase din hotel (montate la schimb, ridicate sau înlocuite la import), cu data și motivul.

**Formatul GY este păstrat:** date `lună/zi/an` (`12/29/2023`), profil cu virgulă (`5,0`), `ProductGroup` = sezonul (`Winter`/`Summer`/`All Season`, afișat IARNA/VARA/ALL SEASON), `WheelType` (`Tyre Only`/`Alloy`/`Steel`). Anvelopele noi primesc datele de vehicul/flotă (SOLD-TO, VIN, SHIP-TO, CITY etc.) copiate de pe rândurile vechi ale mașinii.

Rândurile fără număr auto (ex. rândul de totaluri din `Inventar GY`) sunt ignorate.

---

## Import / export GY Fleet

Coloanele (exact ca în `Inventar GY`, `CITY` apare de două ori):

`SOLD-TO, FleetName, CITY, RegistrationNumber, Fleet VIN, Chassis Num, Make/Model, SHIP-TO, ServiceProviderName, CITY, MaterialNumber, BRAND, ProductGroup, MaterialDescription, QUANTITY, StorageDate, TreadDepth, DOT, WheelType, ServiceProviderStorageLocation, StorageNote(Comments/AccessoriesStored)`

**Import** (tab 🔄 GY Fleet):
1. Încarci exportul GY Fleet (.xlsx sau .csv; separatorul `,`/`;` se detectează singur). Numerele auto se normalizează (`B-123 ABC` → `B123ABC`).
2. Previzualizare pe mașini: **noi**, **diferite** (anvelopele din fișier nu coincid cu cele din aplicație) și **neschimbate**.
3. **„Confirmă importul”** – abia atunci se scrie (doar în foile aplicației).
   - Mașinile **noi** intră `DEPOZITAT`, **fără poziție**, cu toate anvelopele lor.
   - Mașinile **diferite** se înlocuiesc doar dacă bifezi opțiunea. Implicit NU, pentru că după un schimb făcut în aplicație, GY are încă setul vechi.
   - **Poziția, statusul și istoricul nu se modifică niciodată din import.** Anvelopele înlocuite trec în arhivă; fiecare mașină primește o înregistrare `IMPORT` în Istoric.

**Export**: „Excel (.xlsx)” și „CSV” descarcă anvelopele aflate acum în hotel, cele 21 de coloane în ordinea GY.

## Pasul 1. Contul de serviciu Google (o singură dată)

1. Intră pe <https://console.cloud.google.com/> cu contul Google al firmei.
2. Sus, selectează proiectul existent (ex. `hotel-anvelope-madyt`) sau creează unul nou.
3. Meniu ☰ → **APIs & Services → Library**. Caută și apasă **Enable** pentru:
   - **Google Sheets API**
   - **Google Drive API**
4. Meniu ☰ → **IAM & Admin → Service Accounts**. Dacă nu ai deja un cont: **Create service account**, dă-i un nume (ex. `hotel-anvelope`), apoi **Done**.
5. Deschide contul → tab-ul **Keys** → **Add key → Create new key → JSON**. Se descarcă un fișier `.json`.
   - Păstrează-l în siguranță. **Nu îl urca pe GitHub** și nu îl trimite pe chat.
   - Dacă fișierul vechi a fost urcat pe GitHub, **șterge cheia veche** din tab-ul Keys și creează una nouă.
6. Notează emailul contului: se termină în `@...iam.gserviceaccount.com` (îl găsești și în JSON, la `client_email`).

## Pasul 2. Partajează tabelul cu contul de serviciu

1. Deschide tabelul Google Sheets.
2. Apasă **Share / Partajează**.
3. Lipește emailul contului de serviciu (`...@...iam.gserviceaccount.com`).
4. Alege rolul **Editor**, debifează notificarea, apasă **Share**.

Fără acest pas aplicația arată: *„Tabelul Google Sheets nu a fost găsit sau nu este partajat…”*.

ID-ul tabelului este partea din link dintre `/d/` și `/edit`. Implicit aplicația folosește
`1qs5DuQ4--vT0Tr91sqH2om4B1dHM_-IyNLnkcvL5leA`; îl poți schimba cu `spreadsheet_id` în secrets.

## Pasul 3a. Publicare pe Streamlit Cloud (recomandat, merge de pe telefon)

1. Urcă pe GitHub doar: `streamlit_app.py`, `requirements.txt`, `README.md`, `.gitignore`, `.streamlit/secrets.toml.example`.
   **Nu urca** fișierul JSON și nici `secrets.toml` (`.gitignore` le exclude deja).
2. Pe <https://share.streamlit.io> → **Create app** → alegi repository-ul, ramura și fișierul `streamlit_app.py`.
3. Înainte de Deploy (sau după, din **⋮ → Settings → Secrets**) lipește conținutul din
   `.streamlit/secrets.toml.example`, completat cu valorile din fișierul tău JSON:
   - fiecare câmp din JSON (`project_id`, `private_key_id`, `private_key`, `client_email` etc.) merge sub `[gcp_service_account]`;
   - la `private_key` copiază exact textul din JSON, inclusiv `\n`, între ghilimele.
4. **Save** → aplicația repornește și se conectează.
5. Ca să nu fie publică: **Settings → Sharing** → „Only specific people can view this app” și adaugi emailurile colegilor.

## Pasul 3b. Rulare locală (pe calculatorul din service)

```bash
# o singură dată
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/Mac:  source .venv/bin/activate
pip install -r requirements.txt

# configurare: copiază exemplul și completează-l
#   .streamlit/secrets.toml.example  ->  .streamlit/secrets.toml
# (sau, local, pune fișierul JSON lângă streamlit_app.py și în secrets.toml scrie doar
#  gcp_service_account_file = "numele-fisierului.json")

streamlit run streamlit_app.py
```
Se deschide în browser la <http://localhost:8501>. De pe telefon, în aceeași rețea Wi-Fi, folosești adresa „Network URL” afișată în terminal.

În loc de secrets poți folosi și variabile de mediu: `MADYT_SA_FILE` (calea spre JSON), `MADYT_SPREADSHEET_ID`, `MADYT_WORN_MM`, `MADYT_STORAGE_DAYS`.

## Mod DEMO (încercare fără Google)

```bash
# Linux/Mac
MADYT_DEMO=1 streamlit run streamlit_app.py
# Windows PowerShell
$env:MADYT_DEMO="1"; streamlit run streamlit_app.py
```
sau `demo_mode = true` în secrets. Datele se salvează în folderul `demo_data/` (fișiere CSV), cu 3 mașini fictive în formatul GY (foaia `Inventar GY.csv`) și poziții de exemplu. Pentru a reporni demo-ul de la zero, șterge folderul `demo_data/`.

## Probleme frecvente

| Mesaj | Ce faci |
|---|---|
| „Nu am găsit cheia contului de serviciu” | Lipsește `[gcp_service_account]` din secrets (Pasul 3). |
| „Tabelul … nu este partajat” | Pasul 2: Share cu emailul `...iam.gserviceaccount.com`, rol Editor. |
| „Google a refuzat accesul … API” | Activează Google Sheets API și Google Drive API (Pasul 1.3). |
| `invalid_grant` / `Invalid JWT` | Cheia a fost ștearsă sau `private_key` e copiat greșit; creează o cheie nouă. Verifică și ora calculatorului. |
| Datele nu apar imediat | Apasă „🔄 Reîncarcă datele” din bara laterală (datele se citesc din cache max. 30 s). |

## Teste (opțional, pentru programatori)
```bash
pip install pytest
python -m pytest -q tests
```

## Note
- Mai mulți colegi pot lucra simultan; fiecare salvare recitește datele proaspete înainte de scriere. Evitați totuși să salvați exact în aceeași secundă aceeași mașină.
- Scrie-ți numele în bara laterală („Operator”), ca să apară în istoric cine a făcut operațiunea.
- Profilul se scrie ca în GY (`5,5` sau `6`); se salvează `5,5` / `6,0`.
- Mai multe valori într-o căsuță (ex. `6/6/5/4`) sunt acceptate; pentru uzură se ia cea mai mică.
