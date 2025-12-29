# Backup Manager Guide

Fastband's Backup Manager automatically protects your project data with scheduled backups, retention policies, and easy restore capabilities.

## Overview

The Backup Manager provides:

- **Automatic backups** - Daily, weekly, or on-change
- **Database support** - SQLite, PostgreSQL, MySQL
- **Retention policies** - Keep backups for 3-30 days
- **Easy restoration** - Restore from any backup point
- **Storage management** - Automatic cleanup of old backups

## Quick Start

After running `fastband init`, backups are configured automatically. To check status:

```bash
fastband backup status
```

## Configuration

### During Setup

The setup wizard (`fastband init`) configures backups by:

1. **Detecting your database** - Finds SQLite, PostgreSQL, or MySQL
2. **Setting frequency** - Daily (default), weekly, or on-change
3. **Configuring retention** - How long to keep backups (default: 7 days)
4. **Testing the backup** - Verifies write access to backup directory

### Manual Configuration

Edit `.fastband/config.yaml`:

```yaml
backup:
  enabled: true

  # Daily backups
  daily_enabled: true
  daily_time: "02:00"        # Run at 2 AM
  daily_retention: 7         # Keep for 7 days

  # Weekly backups
  weekly_enabled: true
  weekly_day: "sunday"       # Run on Sundays
  weekly_retention: 4        # Keep for 4 weeks

  # On-change backups
  change_detection: true     # Backup when data changes
```

## CLI Commands

### Check Backup Status

```bash
# View backup configuration and last backup time
fastband backup status

# Verbose output with all settings
fastband backup status --verbose
```

### Create Manual Backup

```bash
# Create a backup now
fastband backup create

# Create with custom name
fastband backup create --name "before-migration"

# Create with description
fastband backup create --description "Pre-deployment backup"
```

### List Backups

```bash
# List all backups
fastband backup list

# List with sizes
fastband backup list --show-size

# List only daily backups
fastband backup list --type daily

# List backups from last 3 days
fastband backup list --days 3
```

### Restore from Backup

```bash
# Restore the latest backup
fastband backup restore --latest

# Restore a specific backup by name
fastband backup restore --name "2024-12-15_daily"

# Restore with confirmation prompt
fastband backup restore --name "2024-12-15_daily" --confirm

# Dry run (see what would happen)
fastband backup restore --name "2024-12-15_daily" --dry-run
```

### Delete Old Backups

```bash
# Clean up backups older than retention period
fastband backup cleanup

# Force cleanup without confirmation
fastband backup cleanup --yes

# Preview what would be deleted
fastband backup cleanup --dry-run
```

## Backup Types

### Daily Backups

Run every day at a specified time (default: 2:00 AM).

```yaml
backup:
  daily_enabled: true
  daily_time: "02:00"
  daily_retention: 7  # Days to keep
```

Best for: Most projects, active development.

### Weekly Backups

Run once a week on a specified day.

```yaml
backup:
  weekly_enabled: true
  weekly_day: "sunday"
  weekly_retention: 4  # Weeks to keep
```

Best for: Long-term archival, production systems.

### On-Change Backups

Backup whenever data changes are detected.

```yaml
backup:
  change_detection: true
```

Best for: Critical data, infrequent changes.

## Database-Specific Notes

### SQLite

SQLite databases are backed up by copying the `.db` file.

```bash
# Default location
.fastband/data.db → .fastband/backups/data_2024-12-15.db
```

The backup process:
1. Creates a database checkpoint (WAL mode)
2. Copies the database file
3. Verifies the backup integrity

### PostgreSQL

PostgreSQL backups use `pg_dump`:

```yaml
backup:
  postgres:
    host: "localhost"
    port: 5432
    database: "fastband"
    user: "fastband_user"
```

Set the password via environment variable:
```bash
export PGPASSWORD="your-password"
```

### MySQL

MySQL backups use `mysqldump`:

```yaml
backup:
  mysql:
    host: "localhost"
    port: 3306
    database: "fastband"
    user: "fastband_user"
```

Set the password via environment variable:
```bash
export MYSQL_PWD="your-password"
```

## Storage Location

Backups are stored in:

```
your-project/
└── .fastband/
    └── backups/
        ├── data_2024-12-15_daily.db
        ├── data_2024-12-14_daily.db
        ├── data_2024-12-08_weekly.db
        └── data_before-migration.db  # Manual backup
```

### Changing Storage Location

```yaml
backup:
  storage_path: "/path/to/backups"
```

Or use an environment variable:
```bash
export FASTBAND_BACKUP_PATH="/path/to/backups"
```

## Retention Policies

Backups are automatically deleted after their retention period:

| Type | Default Retention | Configurable |
|------|-------------------|--------------|
| Daily | 7 days | 1-30 days |
| Weekly | 4 weeks | 1-12 weeks |
| Manual | Never deleted | Manual only |

To change retention:

```yaml
backup:
  daily_retention: 14    # Keep daily backups for 2 weeks
  weekly_retention: 8    # Keep weekly backups for 2 months
```

## Scheduled Backups

Fastband uses a background scheduler for automatic backups.

### Start the Scheduler

```bash
# Start backup scheduler
fastband backup scheduler start

# Start with verbose logging
fastband backup scheduler start --verbose
```

### Stop the Scheduler

```bash
fastband backup scheduler stop
```

### Check Scheduler Status

```bash
fastband backup scheduler status
```

### Run as a Service

For production, run the scheduler as a system service.

**systemd (Linux):**

Create `/etc/systemd/system/fastband-backup.service`:

```ini
[Unit]
Description=Fastband Backup Scheduler
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/your/project
ExecStart=/usr/local/bin/fastband backup scheduler start
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable fastband-backup
sudo systemctl start fastband-backup
```

**launchd (macOS):**

Create `~/Library/LaunchAgents/com.fastband.backup.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fastband.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/fastband</string>
        <string>backup</string>
        <string>scheduler</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/your/project</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.fastband.backup.plist
```

## Programmatic Access

### Using the Backup Module

```python
from fastband.backup import BackupManager, get_backup_manager

# Get the backup manager
manager = get_backup_manager()

# Create a backup
backup = manager.create_backup(name="my-backup")
print(f"Created: {backup.path}")

# List backups
backups = manager.list_backups()
for b in backups:
    print(f"{b.name}: {b.created_at} ({b.size_mb:.1f} MB)")

# Restore a backup
manager.restore_backup(name="my-backup")

# Get status
status = manager.get_status()
print(f"Last backup: {status.last_backup}")
print(f"Next backup: {status.next_scheduled}")
```

### Backup Events

Listen for backup events:

```python
from fastband.core.events import subscribe

@subscribe("backup.created")
def on_backup_created(event):
    print(f"Backup created: {event.data['name']}")
    print(f"Size: {event.data['size_mb']:.1f} MB")

@subscribe("backup.failed")
def on_backup_failed(event):
    print(f"Backup failed: {event.data['error']}")
```

## Best Practices

### 1. Test Your Backups

Regularly verify backups can be restored:

```bash
# Create a test restore
fastband backup restore --latest --dry-run
```

### 2. Use Multiple Retention Periods

Combine daily and weekly for balanced protection:

```yaml
backup:
  daily_enabled: true
  daily_retention: 7      # Last week of daily backups
  weekly_enabled: true
  weekly_retention: 4     # Last month of weekly backups
```

### 3. Monitor Backup Health

Check backup status regularly:

```bash
# Add to your monitoring
fastband backup status --json | jq '.last_backup_age_hours'
```

### 4. Store Backups Off-Site

For critical data, copy backups to external storage:

```bash
# Example: sync to S3
aws s3 sync .fastband/backups/ s3://my-bucket/fastband-backups/
```

### 5. Document Your Restore Process

Write down the exact steps to restore from backup, so you're prepared in an emergency.

## Troubleshooting

### "Backup directory not writable"

Check permissions:
```bash
ls -la .fastband/
chmod 755 .fastband/backups/
```

### "Database locked during backup"

For SQLite, ensure no active writes:
```bash
# Check for locks
fuser .fastband/data.db
```

### "pg_dump not found"

Install PostgreSQL client tools:
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
apt install postgresql-client

# RHEL/CentOS
yum install postgresql
```

### "Backup too large"

Consider compression or archival:
```bash
# Compress old backups
gzip .fastband/backups/data_2024-12-01_daily.db
```

### "Scheduler not running"

Check if it's already running:
```bash
fastband backup scheduler status
ps aux | grep fastband
```

## Next Steps

- [Ticket Manager Guide](ticket-manager.md) - Learn about task tracking
- [Configuration Reference](../getting-started/configuration.md) - All backup options
- [AI Providers Guide](ai-providers.md) - Configure AI providers
