============================================================
SUNSET COURTS MANAGEMENT SYSTEM
Administrator Guide
============================================================


STARTING THE SYSTEM
------------------------------------------------------------

The system starts automatically when the Raspberry Pi
is powered on. After a moment, you will see:

  1. A "Verify Date and Time" screen
     - If the date and time shown are correct, press
       "This is Correct"
     - If the date or time are wrong, enter the correct
       values and press "Set Time and Continue"

  2. The Dashboard will appear with court status,
     today's bookings, and quick action buttons

If the browser does not open automatically, open it
manually by clicking the web browser icon on the desktop
and going to:

  http://localhost:5000


SHUTTING DOWN
------------------------------------------------------------

To shut down the Raspberry Pi safely:

  1. On the Export page, press "Exit Kiosk" to leave
     full-screen mode
  2. Click the Raspberry Pi menu in the top-left corner
  3. Select "Shutdown"

NEVER unplug the Pi without shutting down first. This
can corrupt the database.


EXITING AND REOPENING KIOSK MODE
------------------------------------------------------------

If you need to access the desktop (to manage files,
plug in a USB drive, etc.):

  1. Go to the Export page
  2. Scroll to the bottom and click "Exit Kiosk"
  3. A small popup window will appear
  4. Do what you need on the desktop
  5. Click "Reopen Kiosk" on the popup to return


BACKING UP DATA
------------------------------------------------------------

AUTOMATIC BACKUPS:
  The system automatically backs up every Sunday at
  3:00 AM. Backups are stored in the "backups" folder
  inside the application directory. The last 8 weekly
  backups are kept.

USB BACKUP (recommended):
  1. Insert a USB drive into the Pi
  2. Go to the Export page
  3. Click "Backup to USB"
  4. The database and all reports will be saved to a
     "SunsetCourts_Backups" folder on your USB drive
  5. Safely remove the USB drive

DOWNLOADING INDIVIDUAL REPORTS:
  1. Go to the Export page
  2. Click "Download Report" next to any category
  3. Exit kiosk mode to access the downloaded file
     in the Downloads folder


COMMON PROBLEMS AND SOLUTIONS
------------------------------------------------------------

PROBLEM: The screen is black after powering on
  - Wait 30-60 seconds. The Pi takes time to start.
  - If nothing appears after 2 minutes, check that
    the power cable is firmly connected.
  - Check that the HDMI cable is connected.

PROBLEM: The browser opens but shows "This site can't
be reached" or a blank page
  - The application may still be starting. Wait 15
    seconds and refresh the page.
  - If it still does not load, open a terminal
    (Ctrl+Alt+T) and type:
      sudo systemctl restart sunset-courts
    Then refresh the browser.

PROBLEM: The time or date is wrong
  - On the time verification screen at startup, enter
    the correct date and time, then press "Set Time
    and Continue."
  - If the time is wrong after startup, restart the
    Pi and correct it on the verification screen.

PROBLEM: "No USB Drive Detected" when a drive is
plugged in
  - Remove the USB drive and reinsert it. Wait 5
    seconds for the Pi to recognize it.
  - Try a different USB port.
  - The drive may need to be formatted as FAT32 or
    exFAT. Drives formatted as NTFS may not work.

PROBLEM: The system feels slow or unresponsive
  - This is normal after several months of heavy use.
    The database grows as bookings accumulate.
  - Restart the Pi to clear memory.

PROBLEM: A booking or account was accidentally deleted
  - Bookings are never truly deleted. Cancelled
    bookings are hidden from the calendar but remain
    in the database and appear in account history.
  - Deleted accounts cannot be recovered. This is why
    the system asks for confirmation before deleting.
  - Restore from a backup if needed (see below).

PROBLEM: The system shows "MAINTENANCE" on a court
but maintenance is finished
  - Go to the Bookings page and navigate to the date
    of the maintenance booking.
  - Find the MAINTENANCE entry on that court and
    click the X button to cancel it.

PROBLEM: A banned account needs to be unbanned
  - Go to the Accounts page.
  - Find the account and click "Unban."
  - The account can now make bookings again.

PROBLEM: Dues were not reset at the start of the year
  - This happens automatically when the system is
    started for the first time in a new year.
  - If the Pi was off over New Year's, simply start
    it and confirm the correct date on the time
    verification screen. Dues will reset automatically.


RESTORING FROM A BACKUP
------------------------------------------------------------

If the database becomes corrupted or data is lost:

  1. Exit kiosk mode (Export page > Exit Kiosk)
  2. Open a terminal (Ctrl+Alt+T)
  3. Navigate to the application folder:
       cd ~/sunset-courts
  4. Replace the database with a backup:
       cp backups/sunset_courts_backup_YYYY-MM-DD_HHMM.db sunset_courts.db
     (replace YYYY-MM-DD_HHMM with the backup date)
  5. Restart the application:
       sudo systemctl restart sunset-courts
  6. Reopen the kiosk browser or reboot the Pi


USEFUL TERMINAL COMMANDS
------------------------------------------------------------

If you ever need to troubleshoot from the terminal
(Ctrl+Alt+T to open):

  Check if the system is running:
    sudo systemctl status sunset-courts

  Restart the system:
    sudo systemctl restart sunset-courts

  Stop the system:
    sudo systemctl stop sunset-courts

  Start the system:
    sudo systemctl start sunset-courts

  Check backup timer status:
    sudo systemctl list-timers

  View recent error logs:
    sudo journalctl -u sunset-courts -n 30


CONTACT
------------------------------------------------------------

For technical issues beyond this guide, contact the
development team.

System developed by Team 5:
  Henry Scott, Michael Banks, Amber Sturms,
  Landin Lyle, Jordan Smith, William Dulaney

Virginia Western Community College
ITP 258: System Development Project
Spring 2026
