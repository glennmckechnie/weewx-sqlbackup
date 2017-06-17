#!/bin/sh
# transfer, edit, restore sdb file for weewx
# user graybeard
# copy sqlite file from remote machine 
# https://serverfault.com/questions/215756/how-do-i-run-a-local-bash-script-on-remote-machines-via-ssh
#

GREEN="\\033[1;32m"
BLUE="\\033[1;34m"
DARKGREEN="\\033[0;32m"
CYAN="\\033[1;36m"
YELLOW="\\033[1;33m"
BROWN="\\033[0;33m"
RED="\\033[1;31m"
PURPLE="\\033[35m"
PINK="\\033[1;35m"

NORM="\\033[0;39m"
NORM2="[0m"


if [ $# -ne 1 ]
then
    echo "$PURPLE Usage: $0  backup|readonly|writeto $NORM"
    echo "\nTo read or modify the remote weewx database using the sqlite browser on this machine"
    echo "-- 'readonly' means to read the remote database locally - no change to the running weewx daemon"
    echo "-- 'writeto' allows the remote database to be edited and the weewx daemon restarted to use those mods\n"
    exit 1
    fi

   # rtdir=/home/graybeard/bin/
    tymestamp=`date +"%Y%m%d%H%M"`
    tempspace=/tmp
   # copiedsdb="$tymestamp.weewx.sdb"
   # bupofsdb="$tymestamp.bupweewx.sdb"
    database_name="freezerpiweewx.sdb" # from /etc/weewx.conf
    SQLITE_ROOT="/var/lib/weewx"  # also from /etc/weewx.conf
    scp_location=" pi@192.168.0.110:/home/pi/weewx-database-backups/$tymestamp-$database_name"

#    mkdir $tempspace
#    cd $tempspace

case "$1" in
	backup)
	scp $SQLITE_ROOT/$database_name $scp_location
	;;
        readonly-none)
               echo " $BROWN file transferred as... $tempspace/$copiedsdb $NORM"
                      scp pi@192.168.0.108:/var/lib/weewx/weewx.sdb /tmp/weewx$tymestamp.sdb
                     /usr/bin/sqlitebrowser /tmp/weewx$tymestamp.sdb
                    exit 0
                  ;;

          writeto-none)
  # stop the daemon to eliminate locking problems and move the database to the backup location
                ssh -t pi@192.168.0.108  "sudo /usr/sbin/service weewx stop ; sudo -i /bin/mv -f /var/lib/weewx/weewx.sdb /var/opt/weewx-lib/$bupofsdb"

# transfer database back to workstation and echo the location
              scp pi@192.168.0.108:/var/opt/weewx-lib/$bupofsdb $tempspace/$copiedsdb
                    echo "$BROWN file transferred as... $tempspace/$copiedsdb [0m"

    #open this copied database for editing or whatever
                  /usr/bin/sqlitebrowser $tempspace/$copiedsdb

  # closing sqlitebrowser will then transfer the database back to the server... 
                scp $tempspace/$copiedsdb pi@192.168.0.108:/home/pi/$copiedsdb

# where it needs to be moved around a bit before restarting the weewx daemon
              ssh -t pi@192.168.0.108 "sudo -i /bin/cp /home/pi/$copiedsdb /var/lib/weewx/weewx.sdb ; sudo -i /bin/cp /home/pi/$copiedsdb /var/opt/weewx-lib/weewx.sdb ; sudo -i /usr/sbin/service weewx start"

                    echo "$BLUE \nRun concluded, opening remote terminal for checking\n $NORM"
    # to check if all is okay
                  ssh -t pi@192.168.0.108 'sudo -i mc /var/lib/weewx'
                exit 0
             ;;
                 *)
               echo "$RED arfle garble gloop $NORM\n Wrong arguments - use 'readonly' or 'writeto'"
                     exit 1
             ;;
     esac

     exit 0
