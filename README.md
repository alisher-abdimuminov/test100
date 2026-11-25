# Test tizimi (Django + Tailwind)

100 ta savol: 30 ingliz tili, 35 informatika, 35 tarix (`config/settings.py` → `TEST_SUBJECT_COUNTS`).
60 daqiqa, har savol 1 ball.

## Ishga tushirish (lokal yoki prod)

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py import_questions questions/     # barcha savollarni yuklash
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

- Test: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/ → **Natijalar** (ball bo'yicha tartiblangan, har birini txt qilib yuklab olish)

## Savollarni yuklash

Savollar `questions/*.txt` fayllarida. Ikki usul:

1. **Terminal:** `uv run python manage.py import_questions questions/`
   - `--dry-run` — faqat tekshiradi, bazaga yozmaydi
   - bitta fayl ham berish mumkin: `... import_questions questions/tarix.txt`
2. **Admin panel:** Savollar → **TXT dan yuklash** (bir nechta faylni birdaniga tanlash mumkin)

Qayta yuklash xavfsiz: matni bir xil savol dublikat qilinmaydi, variantlari/javobi yangilanadi.
Faylda xato bo'lsa, o'sha fayldan hech narsa saqlanmaydi va xato qatori ko'rsatiladi.

### Format (UTF-8)

```
FAN: english

1. She ______ to school every day.
go
# goes
going
gone

MATN:
Bir nechta savolga umumiy matn (reading passage)...

5. Matnga oid savol?
variant
# to'g'ri variant
variant
variant

MATN TUGADI
```

- Savollar bo'sh qator bilan ajratiladi, savol matni bir necha qator bo'lishi mumkin.
- Oxirgi 4 qator — A, B, C, D variantlar; to'g'risi `#` bilan boshlanadi.
- `FAN:` — `english` / `informatics` / `history` (yoki `ingliz`, `informatika`, `tarix`).
