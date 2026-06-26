"""Named constants — tunable in one place, no magic numbers elsewhere."""

APP_NAME = "resourcer"
APP_VERSION = "0.1.0"

# Polling cadence.
POLL_INTERVAL_MS = 1000          # fast timer: system metrics @ 1 Hz
PROCESS_INTERVAL_MS = 2000       # slow timer: process list @ 0.5 Hz

# Chart history window.
HISTORY_WINDOW_SECONDS = 60
HISTORY_POINTS = HISTORY_WINDOW_SECONDS * 1000 // POLL_INTERVAL_MS  # 60 points

# Process table.
PROCESS_TOP_N = 300              # cap rows rebuilt per refresh

# Byte formatting.
BYTE_UNIT = 1024.0
BYTE_SUFFIXES = ("B", "KB", "MB", "GB", "TB", "PB")

# Percent bounds.
PERCENT_MIN = 0.0
PERCENT_MAX = 100.0
