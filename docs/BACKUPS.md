# OmniAI Backups

## SQLite (default)

### Recommended: Online consistent backup (no downtime)

Use `sqlite3 .backup` to produce a consistent snapshot even while the app is running.

```bash
sqlite3 path/to/omniai.db ".backup 'backups/omniai-$(date +%F).db'"
```

**Windows PowerShell:**

```powershell
sqlite3 .\omniai.db ".backup 'backups\omniai-$(Get-Date -Format yyyy-MM-dd).db'"
```

### If using WAL mode

If you copy files directly, you must also copy:
- `omniai.db`
- `omniai.db-wal`
- `omniai.db-shm`

Prefer `.backup` instead.

### Restore

1. Stop the backend
2. Replace the DB file with the backup
3. Start the backend
4. Run a smoke test (`/v1/health`, login, list conversations)

---

## Postgres (docker-compose / production)

### Backup

```bash
pg_dump -Fc -d "$DATABASE_URL" -f backups/omniai-$(date +%F).dump
```

### Restore

```bash
pg_restore -d "$DATABASE_URL" --clean --if-exists backups/omniai-YYYY-MM-DD.dump
```

---

## Retention + encryption

- Retain daily backups for 7–14 days, weekly for 8–12 weeks
- Encrypt backups at rest (e.g., filesystem encryption or age/gpg)
- Periodically perform a restore drill

---

## Restore Drill Checklist (Quarterly)

Perform this drill quarterly to verify backup integrity and recovery procedures.

### Pre-Drill Preparation

- [ ] Notify team of maintenance window
- [ ] Ensure no active user sessions
- [ ] Document current database size and backup count

### Restore Test

- [ ] Create isolated restore directory
- [ ] Copy latest backup to restore directory
- [ ] For SQLite: `sqlite3 restored.db ".restore backups/omniai-YYYY-MM-DD.db"`
- [ ] For Postgres: `pg_restore -d postgres://restore_test "backups/omniai-YYYY-MM-DD.dump"`
- [ ] Verify schema integrity (list tables, indexes)
- [ ] Spot-check 3-5 recent conversations for data completeness
- [ ] Verify audit logs are intact

### Post-Drill

- [ ] Document any issues found
- [ ] Delete restore test database
- [ ] Log drill completion date in audit notes
- [ ] Update backup procedures if issues found


---

## Test / CI commands

```bash
# Required security gate
pytest -m "security or csrf"

# Full suite
pytest
```

---

## Security Configuration

### Content Security Policy (CSP)

CSP configuration is documented in [SECURITY.md](./SECURITY.md). Add the CSP directive to `frontend/index.html` for production hardening.

---

