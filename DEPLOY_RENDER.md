# SolarShare — Render deployment instructions

This is the uploaded Flask project, adapted for public hosting. **This package is not yet deployed.**

## 1. Put the code on GitHub

Create a new private GitHub repository and upload the contents of this `solarshare_complete` folder (app.py, requirements.txt, templates/, static/). Do not upload existing `solarshare.db`, passwords, or .env files.

## 2. Create a Render Web Service

- Visit https://dashboard.render.com and select New > Web Service.
- Connect the GitHub repository.
- Runtime: Python.
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 app:app`
- Set environment variables:
  - `SECRET_KEY`: long random secret, keep private. Generate locally: `python -c "import secrets; print(secrets.token_hex(32))"`
  - `ADMIN_EMAIL`: email address that **you** will use when registering the admin account. Set before public sign-ups.
  - `PUBLIC_DEPLOYMENT`: `1`
  - `DATABASE_PATH`: for a **demo only**, use `/opt/render/project/src/solarshare.db` (ephemeral; resets on rebuild/redeploy or restart). For durable SQLite, attach a **persistent disk** and set `DATABASE_PATH` to a file path on that disk, such as `/var/data/solarshare.db`.
- Deploy and open the assigned onrender.com URL.

## Critical data persistence limitation

On Render services **without a persistent disk**, SQLite data on the local filesystem can disappear on restart/redeploy. This is suitable only for a disposable college demo, not long-term accounts or records. Persistent disks may require a paid plan; check Render's current pricing and availability. The app is currently SQLite-based, **not PostgreSQL-based**. Adding a hosted PostgreSQL service would require database code changes; setting a PostgreSQL URL alone will not work.

## Security / project notes

- Register the admin email specified in `ADMIN_EMAIL` before inviting other users.
- Admin authorization is still a simplified college prototype. Do not use real customer data or passwords reused elsewhere.
- Solar sharing is simulated; it is not real electricity trading.
- For real public production use, implement CSRF protections, rate limiting, robust account verification, database backups and production security review.
- When developing locally: `python -m pip install -r requirements.txt` then `python app.py`.
