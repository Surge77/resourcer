"""Named constants — tunable in one place, no magic numbers elsewhere."""

APP_NAME = "resourcer"
APP_VERSION = "0.1.0"

# Polling cadence.
POLL_INTERVAL_MS = 1000          # fast timer: system metrics @ 1 Hz
PROCESS_INTERVAL_MS = 2000       # slow timer: process list @ 0.5 Hz
PARTITION_INTERVAL_MS = 5000     # slowest timer: disk capacity @ 0.2 Hz

# Chart history window.
HISTORY_WINDOW_SECONDS = 60
HISTORY_POINTS = HISTORY_WINDOW_SECONDS * 1000 // POLL_INTERVAL_MS  # 60 points

# Process table.
PROCESS_TOP_N = 300              # cap rows rebuilt per refresh

# Process kill: how long to wait for graceful terminate before force kill.
KILL_WAIT_SECONDS = 0.5

# Poll-interval selector choices: (label, milliseconds).
POLL_INTERVAL_CHOICES = (("1 s", 1000), ("2 s", 2000), ("5 s", 5000))

# Byte formatting.
BYTE_UNIT = 1024.0
BYTE_SUFFIXES = ("B", "KB", "MB", "GB", "TB", "PB")

# Percent bounds.
PERCENT_MIN = 0.0
PERCENT_MAX = 100.0

# Sustained-load alert: fire when CPU/memory stays at/above this for this long.
ALERT_PERCENT = 90.0
ALERT_DURATION_SECONDS = 10.0
