kill -USR2 `cat /var/run/anaconda.pid`
kill -HUP `cat /var/run/anaconda.pid`
udevadm info --export-db | less
tail -f /tmp/storage.log
