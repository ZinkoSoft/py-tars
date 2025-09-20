This directory is mounted writable at /mosquitto/config inside the broker container.
On first startup the base mosquitto.conf from ../mosquitto.conf is copied here if not present.
The passwd file and persistence artifacts (mosquitto.db) will be created here.
