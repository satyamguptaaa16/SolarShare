# SolarShare — Complete Standalone Full-Stack Prototype

A self-contained Flask + SQLite web app with a premium landing page and resident/admin dashboards. **No Lovable, Supabase, React, npm, or cloud service required.** The optional Google Fonts request falls back to local fonts when offline.

## Start (Windows PowerShell / VS Code)

1. Extract the ZIP.
2. Open the **solarshare_complete** folder in VS Code (the one containing `app.py`).
3. Open a terminal and run:

```powershell
python -m pip install -r requirements.txt
python app.py
```

4. Open **http://127.0.0.1:5000**.

If your terminal is in the parent folder, run `cd solarshare_complete` first. The earlier `can't open file ... app.py` error happens when running from the wrong folder.

## Features

- Public landing page with solar-inspired visual design
- Password-hashed registration/login and session authentication
- First registered account automatically becomes the **admin** for this local demo; subsequent accounts are residents
- Solar installation registration
- Daily generation/consumption readings
- Dashboard with energy bar chart, estimated savings and CO₂ avoided
- Same-society surplus energy allocation simulation with transaction history
- Maintenance reminders and completion tracking
- Download CSV reports
- Admin society-wide totals and resident list
- SQLite database created automatically at `solarshare.db` in this folder

## Test sharing

1. Register the first account (admin) with society `Green Heights`.
2. Add an energy reading: generated `20`, consumed `8`.
3. Log out, register a second account with the **same** society name.
4. Log in as the first account, open **Energy sharing**, allocate up to `12` kWh to the second user.
5. Refresh to confirm data persists.

## Important limits

This is an **educational local prototype**, not a production utility or energy exchange. Data is entered manually. Sharing is a record-only simulation, not physical transfer or billing. Savings assume ₹8 per self-consumed kWh, CO₂ avoided assumes 0.7 kg/kWh. Totals across all readings are simplified and do not model time matching, actual tariffs, net metering or regulations. The first-user admin rule is for demo setup only; production needs invitation-based admin authorization, CSRF protection, secure cookies/HTTPS, secrets configuration, rate limiting, backups, tests and hardened deployment. `app.py` intentionally runs with Flask debug disabled.

**Do not copy an older database into this new folder**: it has its own schema. Keep your older project as a backup. This project is independent.
