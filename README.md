# 🌙 M4CRO MOONWALK v6.1 — Macro Spam Tombol (Windows)

Macro buat spam tombol otomatis (moonwalk / strafe / bunny hop) di game.

## Empat pilihan tampilan

Ganti dari dalam app: **Tampilan → Model tampilan**, atau ubah 1 baris di atas
`moonwalk_macro.py`:

```python
LAYOUT = "macos"      # "macos" | "game" | "minimal" | "pro"
```

### Game menu — dialog di atas background blur

![game](preview/ui-game-run.png)

Toggle, slider hijau, radio, checkbox, dropdown, tombol Save/Cancel — semuanya digambar
manual di canvas. Background langit senjanya juga digambar sendiri (gradasi + glow),
warnanya ngikut tema yang dipilih.

| Dropdown | Rekam tombol |
|---|---|
| ![dropdown](preview/ui-game-menu.png) | ![rekam](preview/ui-game-modal.png) |

Ada 2 tab di dalam dialognya: **SETELAN** dan **TAMPILAN**. Background senjanya bisa
dimatiin — kalau dimatiin, window-nya otomatis nyusut pas seukuran panel (566×666),
jadi nggak ada bingkai gelap yang nganggur sama sekali.

![tampilan](preview/ui-game-tampilan.png)

### macOS — gaya System Settings (default)

![macos](preview/ui-mac.png)

Sidebar + kartu setting + popup menu beneran (lengkap sama tanda ✓ dan bulatan warna):

| Urutan tombol | Popup menu |
|---|---|
| ![urutan](preview/ui-mac-urutan.png) | ![menu](preview/ui-mac-menu.png) |

Isinya 5 halaman: **Macro · Kecepatan · Urutan Tombol · Tampilan · Tentang**.
Lampu lalu lintas kiri atas: 🔴 keluar · 🟡 minimize · 🟢 mini overlay.

### Minimalis & Pro

| `minimal` — 404×620 | `pro` — 940×580 |
|---|---|
| ![minimal](preview/ui-min-run.png) | ![pro](preview/ui-aktif.png) |

Di semua layout, tombol yang lagi dikirim **nyala** ngikutin macro-nya.

---

## 🚀 Cara pakai

1. Install **Python** dari https://www.python.org/downloads/
   → pas install **CENTANG "Add Python to PATH"**
2. Double-click **`JALANKAN.bat`**
3. Tahan hotkey (default `Q`) → tombol A dan D di-spam bergantian

### Mau jadi `.exe`?
Double-click **`build_exe.bat`** → tunggu 1-2 menit → hasilnya di **`dist\MoonwalkMacro.exe`**

---

## 🎮 Kontrol

| Aksi | Tombol |
|---|---|
| Spam tombol | **Hotkey** (default `Q`) |
| ON / OFF macro | **F2** atau tombol besar di kiri bawah |
| Mini overlay | ikon **⤡** di title bar |
| Ganti tema | tab **TAMPILAN** → pilih warna |
| Selalu di atas | tab **TAMPILAN** → `YA` / `TIDAK` |
| Pindahin jendela | drag di title bar |
| Minimize / keluar | **—** / **✕** |

### Dua tab di panel kiri
- **MACRO** — trigger (hotkey + mode) dan kecepatan (speed + jitter)
- **TAMPILAN** — 5 tema warna, always-on-top, dan tombol mini overlay

---

## 🎛️ Action Editor (panel kanan)

Tiap baris = satu action (satu tombol yang ditekan lalu dilepas). Dijalanin urut dari
atas ke bawah, terus ngulang.

**Toolbar di atas:**

| Tombol | Fungsi |
|---|---|
| `+` | tambah action — tekan tombol apa aja setelah diklik |
| `COPY` | gandain action yang lagi dipilih |
| `↑` `↓` | geser urutannya |
| `HAPUS` | hapus action yang dipilih |
| `RESET` | balik ke A → D |

**Cara pakai:** klik barisnya buat milih (border-nya jadi nyala), terus pakai toolbar.
Atau klik ikon **✕** di kanan baris buat langsung hapus.

**Preset cepat** di bawah list: `MOONWALK (A→D)` · `MAJU MUNDUR (W→S)` ·
`A D + LOMPAT` · `ZIGZAG (A A D D)`

Maksimal 7 action.

Tombol yang didukung: `A–Z`, `0–9`, `F1–F12`, `SPACE`, `SHIFT`, `CTRL`, `ALT`, `TAB`,
`ENTER`, `ESC`, dan tombol arah.

---

## ⚡ Speed & Jitter

**Speed** — slider 5–150 ms + 4 preset (`LAMBAT 60` · `NORMAL 35` · `CEPAT 20` · `GILA 10`).
Ini jeda tiap tombol; makin kecil makin cepat.

**Jeda antar tombol** — waktu diam setelah tombol dilepas sebelum tombol berikutnya
ditekan. Default `0`. Kalau game-nya kayak nggak nangkep input, naikin ke `10–20 ms`.

**Jitter** — bikin delay-nya **acak** dalam rentang tertentu:

| Jitter | Efek pada speed 35 ms |
|---|---|
| `OFF` | pas 35 ms terus |
| `10%` | acak 31–38 ms |
| `20%` | acak 28–42 ms |
| `30%` | acak 24–45 ms |

Kenapa berguna? Manusia nggak mungkin nekan tombol presisi 35.000 ms berulang-ulang.
Jitter bikin polanya lebih natural. **Rekomendasi: 10–20%.**

---

## 🔀 Mode

- **TAHAN (HOLD)** → tahan hotkey = spam jalan, lepas = berhenti *(paling enak buat game)*
- **TOGGLE** → tekan sekali jalan, tekan lagi berhenti

---

## 📌 Mini overlay

Klik ikon **⤡** → jendela mengecil jadi widget 304×74 px yang cuma nampilin status,
kecepatan, dan urutan tombol. Semi-transparan, selalu di atas, bisa di-drag ke pojok layar.
Klik **⤢** buat balik ke ukuran penuh.

---

## ⚙️ Cara kerjanya

Input dikirim pakai **SendInput + scan code** (bukan karakter biasa), jadi kebaca game yang
pakai DirectInput/RawInput. Untuk tiap tombol dalam urutan:

```
tombol ditekan → tunggu (speed ± jitter) → tombol dilepas → lanjut tombol berikutnya
```

Dua thread jalan barengan: satu ngintip hotkey tiap 5 ms, satu ngirim input. Pas macro
dimatiin, **semua tombol otomatis dilepas** biar karakter nggak nyangkut jalan.

---

## 🖥️ Kalau tampilan keliatan beda / aneh

Screenshot di atas dirender di Linux, jadi fontnya bukan Segoe UI. Di Windows layout-nya
sama persis, cuma hurufnya lebih ramping. Program milih font otomatis:
`Segoe UI` → `Inter` → `Roboto` → `Noto Sans` → `DejaVu Sans`

### Ada masalah jendela? Edit baris paling atas `moonwalk_macro.py`:

```python
USE_CUSTOM_TITLEBAR = True   # False = pakai frame Windows biasa
ALWAYS_ON_TOP       = True   # False = jendela bisa ketutup window lain
```

| Masalah | Solusi |
|---|---|
| Nggak muncul di taskbar / nggak bisa Alt+Tab | `USE_CUSTOM_TITLEBAR = False` |
| Jendela nutupin game terus | `ALWAYS_ON_TOP = False` |
| Teks kegedean/kekecilan | DPI scaling, udah dihandle otomatis |


### Mini overlay — tiap tema beda bentuk

![mini tema](preview/ui-mini-tema.png)

Bukan cuma warnanya yang ganti, **desainnya beda-beda**:

| Tema | Gaya | Isinya |
|---|---|---|
| Emas | Bar klasik | titik status, keys/s, badge urutan |
| Cyan | HUD | angka gede + equalizer yang gerak ngikut kecepatan |
| Ungu | Kapsul | ring melingkar yang keisi makin cepet makin penuh |
| Merah | Gamer tag | sudut runcing, tombol urutan jadi kotak-kotak |
| Hijau | Terminal | gaya konsol, ada kursor kedip pas lagi spam |

Ukuran window-nya juga nyesuain sendiri tiap gaya.

### Layout game juga full ikut tema

![game tema](preview/ui-game-tema.png)

Toggle, slider, checkbox, tombol utama, sampai langit senjanya nyesuain. Mau persis
kayak menu game aslinya yang serba hijau? Pilih tema **Hijau**.

---

## 🤖 Build `.exe` otomatis

Workflow `.github/workflows/build.yml` bikin `MoonwalkMacro.exe` tiap ada push ke
`main`, terus dipasang di halaman **Releases** dengan tag sesuai `VERSION`.

- Runner: `windows-latest` · PyInstaller `--onefile --noconsole` · ikon `icon.ico`
- Nggak perlu install apa-apa di komputer sendiri
- Cara pasangnya ada di [CARA_UPLOAD_GITHUB.md](CARA_UPLOAD_GITHUB.md)

Catatan: file PyInstaller sering kena peringatan palsu Windows Defender. Itu normal.

---

## 🔄 Update tanpa download manual

Mulai v5.6 app-nya bisa update sendiri. Sekali setting, seterusnya cukup 1 klik.

Langkah lengkapnya ada di **[CARA_UPLOAD_GITHUB.md](CARA_UPLOAD_GITHUB.md)**.

**Ringkasnya (sekali doang):**

1. Taruh `moonwalk_macro.py` versi terbaru di **GitHub** (atau Gist), ambil link **Raw**-nya
2. Copy link itu
3. Buka **Tentang → Link update → Tempel link**

**Habis itu:** tinggal klik **Cek update**. App bakal:
- ngebandingin `VERSION` di file online sama yang lokal
- kalau lebih baru → download, backup file lama jadi `moonwalk_macro.py.bak`, terus restart sendiri
- kalau udah paling baru → kasih tau "udah versi terbaru"

Kalau file yang diambil ternyata bukan `moonwalk_macro.py` (atau ukurannya nggak masuk akal),
update-nya dibatalin — jadi nggak bakal ngerusak file yang udah jalan.

> Nggak mau ribet? Ya tinggal timpa `moonwalk_macro.py` yang lama. Semua fitur ada di
> **1 file itu doang** — folder `preview/` cuma buat README, boleh dihapus.

---

## 🎮 Da Hood — cara yang bener

**Penting: Da Hood itu BUKAN spam A/D.** Speed glitch / moonwalk di Da Hood jalannya
dengan nge-spam tombol **zoom kamera `I` dan `O`**, bukan tombol gerak. Makanya macro
A→D nggak ngefek apa-apa di sana.

![da hood](preview/ui-mac-dahood.png)

Buka halaman **Da Hood** di sidebar → klik **Pasang**. Itu langsung nyetel:
urutan `I → O`, delay `15 ms`, tanpa jeda, mode tahan.

### Langkah di dalam game

1. Nyalain **shift lock**
2. Pakai **emote greet**
3. Pas tangannya naik deket kepala → **keluarin senjata, langsung simpen lagi**
4. Hadap ke arah tujuan (kamu bakal jalan mundur)
5. **Tahan hotkey + tahan `S`**

Bagian tersusah itu timing naruh senjatanya. Wajar gagal beberapa kali.

### Delay yang cocok

| Kondisi | Delay |
|---|---|
| FPS 60 (default) | **12 – 18 ms** |
| Pakai FPS unlocker (144+) | **8 – 10 ms** |

Karakter cuma **getar di tempat** = delay kekecilan, naikin.
Jalan tapi **pelan** = delay kegedean, turunin 1-2 ms.

Nyalain juga **Low GFX** di setelan Da Hood, dan turunin grafik Roblox ke level 1-2.
FPS yang stabil = macro yang stabil.

### Kalau macro-nya nggak kirim tombol sama sekali

1. **Jendela game harus lagi aktif** — input dikirim ke window yang fokus. App bakal
   kasih peringatan merah kalau jendelanya sendiri yang lagi aktif.
2. **Run as Administrator**
3. **Tes di Notepad** — tahan hotkey, harusnya muncul `ioioio...`. Muncul = macro normal,
   berarti masalahnya di game.
4. Roblox jangan Fullscreen Exclusive (tekan `F11`).

### Gerakannya patah-patah?

Udah dibenerin di **v5.2**: Windows defaultnya cuma bangunin thread tiap ~15,6 ms, jadi
`sleep(15 ms)` beneran jalan 15 atau 31 ms — acak. Sekarang pakai `timeBeginPeriod(1)` +
spin. Hasil ukur: **±0,01 ms** di delay 15 ms.

⚠️ Macro di game online tetap ada risiko kena banned. Tanggung sendiri ya.

---

## 🛠️ Kalau nggak jalan di game

1. **Run as Administrator** (klik kanan → Run as administrator)
2. Game **Fullscreen Exclusive** kadang nolak — ganti ke **Borderless / Windowed**
3. Naikkan speed ke `40–50 ms`; kalau kekencengan game bisa skip input
4. Antivirus kadang nandain macro sebagai suspicious — false positive umum, whitelist aja

---

## 🎨 Bikin tema sendiri

Tambah 1 baris di `THEMES` dalam `moonwalk_macro.py`:

```python
"pink": {"label": "Pink", "top": "#140a12", "bot": "#22101c",
         "acc": "#ff6bc1", "hot": "#ff2d9e", "glow2": "#8a5bff"},
```
Terus tambahin `"pink"` ke `THEME_ORDER`. Warna kartu, border, dan teks dihitung otomatis.

---

## 📁 Isi folder

```
moonwalk-macro/
├── moonwalk_macro.py   ← program utama
├── JALANKAN.bat        ← klik 2x buat jalanin
├── build_exe.bat       ← klik 2x buat jadiin .exe
├── moonwalk.ahk        ← versi AutoHotkey v2 (ringan, tanpa GUI)
├── settings.json       ← dibuat otomatis, nyimpen semua setting
├── HANDOFF_KE_AI.md    ← brief buat lanjutin project pakai AI lain
├── prompt_singkat.txt  ← versi copy-paste dari brief di atas
├── preview/            ← screenshot UI
└── README.md
```

---

## ⚠️ Catatan

Sebagian game online (apalagi yang pakai anticheat) **melarang macro** dan bisa kena
banned — termasuk Roblox untuk game tertentu. Aman dipakai di game offline / single-player
/ yang emang ngizinin. Risiko ditanggung sendiri 🙏
# moonwalk-macro
