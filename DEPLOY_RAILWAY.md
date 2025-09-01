# Deploy pe Railway – Ghid Pas cu Pas

Acest ghid te ajută să publici aplicația Django pe Railway folosind Postgres și Gunicorn.

## 0) Cerințe
- Cont Railway: https://railway.app
- Repository GitHub cu proiectul
- Secret key generat pentru producție

## 1) Pregătiri în proiect (deja incluse în patch)
- Procfile cu comanda de pornire Gunicorn.
- Configurare `DATABASE_URL` în `settings.py` prin `dj-database-url`, cu fallback la SQLite pentru dev.
- WhiteNoise este configurat pentru static files.

## 2) Publică pe GitHub
- Commit & push toate modificările în branch-ul principal (ex: `main`).

## 3) Creează proiect în Railway
- New Project → Deploy from GitHub → alege repo-ul.
- Railway va crea un serviciu pentru aplicația ta și va porni un build cu Nixpacks (automat).

Referințe: Ghid oficial Railway pentru Django [[4]](https://docs.railway.com/guides/django).

## 4) Adaugă baza de date Postgres
- În proiectul Railway: Add New → Database → PostgreSQL.
- Railway expune automat variabila `DATABASE_URL` către serviciul web.

## 5) Configurează variabile de mediu la serviciul Web
Setează următoarele Environment Variables:
- `DJANGO_SECRET_KEY` = o valoare secretă (random și PRIVATĂ)
- `DJANGO_DEBUG` = `0`
- `DJANGO_ALLOWED_HOSTS` = domeniul Railway al serviciului (ex: `myapp.up.railway.app`)
- `DJANGO_CSRF_TRUSTED_ORIGINS` = `https://myapp.up.railway.app`

Dacă folosești un domeniu personalizat, adaugă-l și pe acesta în `DJANGO_ALLOWED_HOSTS` și în `DJANGO_CSRF_TRUSTED_ORIGINS` (cu schema https://).

## 6) Setează comenzi de migrare și colectare statice
Ai două opțiuni:
- În Railway, la serviciul Web, adaugă un Deploy Command / Hook:
  - `python manage.py migrate --noinput && python manage.py collectstatic --noinput`
- Sau rulează manual după primul deploy din Shell-ul Railway:
  - `python manage.py migrate --noinput`
  - `python manage.py collectstatic --noinput`

Notă: Procfile definește startul aplicației cu Gunicorn. Dacă nu e detectat automat, setează Start Command la:
`gunicorn hotelapp.wsgi:application`

Referințe despre Procfile / Nixpacks [[2]](https://devpress.csdn.net/postgresql/62f233d3c6770329307f6268.html), [[3]](https://blog.acel.dev/deploying-your-django-app-on-railway).

## 7) Rulează deploy
- Trigger Deploy în Railway și așteaptă terminarea build-ului.
- Deschide URL-ul serviciului (ex: `https://myapp.up.railway.app`).

## 8) Creează un superuser (opțional)
- Din Shell în Railway, rulează: `python manage.py createsuperuser`

## 9) Domeniu personalizat (opțional)
- Atașează domeniul în Railway (DNS → CNAME/A conform instrucțiunilor).
- Actualizează `DJANGO_ALLOWED_HOSTS` și `DJANGO_CSRF_TRUSTED_ORIGINS` să includă noul domeniu.

## 10) Troubleshooting
- 400 Bad Request: verifică `DJANGO_ALLOWED_HOSTS`.
- Probleme autentificare/admin: verifică `DJANGO_CSRF_TRUSTED_ORIGINS` (cu schema `https://`).
- Static files lipsă: asigură-te că ai rulat `collectstatic` și că WhiteNoise rămâne în middleware.
- Conexiune DB: verifică `DATABASE_URL` (este setat de serviciul Postgres).

## Referințe
- Ghid Railway Django [[4]](https://docs.railway.com/guides/django)
- Procfile pentru buildpack/Nixpacks [[2]](https://devpress.csdn.net/postgresql/62f233d3c6770329307f6268.html)
- Nixpacks – configurare și exemple [[3]](https://blog.acel.dev/deploying-your-django-app-on-railway)
