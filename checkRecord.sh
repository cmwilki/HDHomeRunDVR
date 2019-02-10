#!/bin/bash

OUTPUT=`/bin/ps -elf | /bin/grep recordTV3.py | /bin/grep -v grep | /usr/bin/wc -l`

if [ "$OUTPUT" -eq 0 ]; then
    if [ ! -e /mnt/nas/TV ]; then
        echo "RECORDER WAS NOT RUNNING BUT MOUNT POINT DID NOT EXISTS..."
        echo "EXITING"
        exit
    else
        echo "RECORDER WAS NOT RUNNING... STARTING IT AGAIN"
        /usr/bin/nohup /usr/bin/python3 -u ${HOME}/bin/recordTV3.py -c ${HOME}/bin/dvr.cfg |& ${HOME}/bin/logger /mnt/nas/TV/ recordTV 86400 &
    fi
fi

## BZIP2 compress 2 day old log files; Remove log files older than 5 days
/usr/bin/find /mnt/nas/TV -type f -name "record*.log" -mmin +1440 | /usr/bin/xargs --no-run-if-empty --max-lines=1 /bin/bzip2
/usr/bin/find /mnt/nas/TV -type f -name "record*.log*" -mmin +7200 | /usr/bin/xargs --no-run-if-empty /bin/rm -f

/usr/bin/find /mnt/nas/TV/CBS\ Nightly\ News/ -name "*.ts" -mtime +1 | /usr/bin/xargs --max-lines=1 -t --no-run-if-empty -i /bin/rm -f "{}" 
/usr/bin/find /mnt/nas/TV/CBS\ This\ Morning/ -name "*.ts" -mtime +1 | /usr/bin/xargs --max-lines=1 -t --no-run-if-empty -i /bin/rm -f "{}"
/usr/bin/find /mnt/nas/TV/The\ Late\ Late\ Show/ -name "*.ts" -mtime +2 | /usr/bin/xargs --max-lines=1 -t --no-run-if-empty -i /bin/rm -f "{}"
/usr/bin/find /mnt/nas/TV/The\ Tonight\ Show/ -name "*.ts" -mtime +2 | /usr/bin/xargs --max-lines=1 -t --no-run-if-empty -i /bin/rm -f "{}" 

## Keep the file system under 97% usage
while [ `/bin/df -hP | /bin/grep nas | /usr/bin/awk '{print $5}' | /bin/sed 's/\%//g'` -gt 97 ]; do
	fileToRemove=`/usr/bin/find /mnt/nas/TV/ -type f -name "*.ts" -printf "%p:%T@\n" | /usr/bin/sort -t : -n --key 2 | /usr/bin/head -1 | /usr/bin/awk -F : '{print $1}'`
	echo "NOTICE:   [`/bin/date +'%Y-%m-%d %H:%M:%S'`] REMOVING FILE ${fileToRemove}"
	/bin/rm -f "${fileToRemove}"
done

