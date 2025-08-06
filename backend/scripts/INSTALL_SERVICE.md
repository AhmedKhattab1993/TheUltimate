# Installing Universe Loader as a System Service

This guide explains how to set up the universe data loader as a systemd service for automatic daily updates.

## Installation Steps

1. **Copy service files to systemd directory**:
   ```bash
   sudo cp universe_loader.service /etc/systemd/system/
   sudo cp universe_loader.timer /etc/systemd/system/
   ```

2. **Update service file with correct paths and user**:
   ```bash
   sudo nano /etc/systemd/system/universe_loader.service
   # Update User, Group, and WorkingDirectory as needed
   ```

3. **Reload systemd daemon**:
   ```bash
   sudo systemctl daemon-reload
   ```

4. **Enable and start the timer**:
   ```bash
   # Enable timer to start on boot
   sudo systemctl enable universe_loader.timer
   
   # Start the timer
   sudo systemctl start universe_loader.timer
   ```

5. **Check timer status**:
   ```bash
   sudo systemctl status universe_loader.timer
   sudo systemctl list-timers | grep universe_loader
   ```

## Manual Service Execution

To run the service manually:
```bash
sudo systemctl start universe_loader.service
```

## Monitoring

### View Service Logs
```bash
# Recent logs
sudo journalctl -u universe_loader.service -n 50

# Follow logs in real-time
sudo journalctl -u universe_loader.service -f

# Logs from today
sudo journalctl -u universe_loader.service --since today
```

### Check Timer Schedule
```bash
systemctl list-timers universe_loader.timer
```

## Customization

### Change Schedule

Edit the timer file:
```bash
sudo nano /etc/systemd/system/universe_loader.timer
```

Example schedules:
- `OnCalendar=Mon..Fri 17:00:00` - 5 PM local time on weekdays
- `OnCalendar=Mon..Fri 22:00:00 UTC` - 5 PM ET (10 PM UTC) on weekdays
- `OnCalendar=daily` - Every day at midnight
- `OnCalendar=Mon..Fri *-*-* 09:30:00` - 9:30 AM on weekdays

### Add Email Notifications

Add to service file:
```ini
[Service]
OnFailure=notify-email@%i.service
```

Create email notification service:
```bash
sudo nano /etc/systemd/system/notify-email@.service
```

```ini
[Unit]
Description=Send email notification for failed %i service

[Service]
Type=oneshot
ExecStart=/usr/bin/bash -c 'echo "Service %i failed on $(hostname)" | mail -s "Service Failure: %i" admin@example.com'
```

## Troubleshooting

### Service Won't Start
```bash
# Check service status
sudo systemctl status universe_loader.service

# Check full logs
sudo journalctl -u universe_loader.service --no-pager

# Test service directly
cd /home/ahmed/TheUltimate/backend
python3 scripts/universe_data_loader.py --daily
```

### Timer Not Triggering
```bash
# Check timer status
sudo systemctl status universe_loader.timer

# List all timers
systemctl list-timers --all

# Check system time
timedatectl status
```

### Permission Issues
- Ensure the service user has access to:
  - Python environment
  - Database credentials
  - Polygon API key
  - Working directory

## Uninstall

To remove the service:
```bash
# Stop and disable
sudo systemctl stop universe_loader.timer
sudo systemctl disable universe_loader.timer

# Remove files
sudo rm /etc/systemd/system/universe_loader.service
sudo rm /etc/systemd/system/universe_loader.timer

# Reload daemon
sudo systemctl daemon-reload
```