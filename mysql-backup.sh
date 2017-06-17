#!/bin/bash 
## whitebeard ## 
## whitebeard ## 
## whitebeard ## 
## whitebeard ## 
## whitebeard ## 
## whitebeard ## 
## whitebeard ## 
#exec 5> debug_output.txt
#BASH_XTRACEFD="5"
# Shell script to backup MySql database
# To backup Nysql databases file to /backup dir and later pick up by your
# script. You can skip few databases from backup too.
# For more info please see (Installation info):
# http://www.cyberciti.biz/nixcraft/vivek/blogger/2005/01/mysql-backup-script.html
# Last updated: Aug - 2005
# --------------------------------------------------------------------
# This is a free shell script under GNU GPL version 2.0 or above
# Copyright (C) 2004, 2005 nixCraft project
# Feedback/comment/suggestions : http://cyberciti.biz/fb/
# -------------------------------------------------------------------------
# This script is part of nixCraft shell script collection (NSSC)
# Visit http://bash.cyberciti.biz/ for more information.
# -------------------------------------------------------------------------
#
# https://bash.cyberciti.biz/backup/backup-mysql-database-server-2/

MyUSERSHOW="root"     # USERNAME
MyUSERDUMP="root"     # USERNAME
# same user name should be for both - used this way for debug DEBUGMODE
#MyPASS="h0whigh"       # PASSWORD
MyPASS="h0whigh"       # PASSWORD
MyHOST="localhost"          # Hostname

callusage(){
if [ $# -ne 1 ]
then
    echo -e "\n\\033[35m Usage: $0 dryrun | doit (with optional 2nd argument) of debug\\033[0;39m"
    echo -e "Script to backup mysql databases - editing of this script ($0)may be required"
    echo -e "'dryrun' will go through the motions | 'doit' will cut metal!\n"
    echo -e "combine with debug to get equivalent of #!/bin/bash -x\n"
        exit 1
fi
}

callusage $1


case $1 in
      dryrun)
       MyUSERDUMP="MADE-TO-FAIL"     # USERNAME
       ;;
       *)
       ;;
esac

if [ $# -eq 2 ]
then
 case $2 in
 debug)
       set -x #v
       ;;
     *)
     # clear
     echo -e "\n2nd option can only be 'debug'\n"
     callusage
     exit 1
  esac
 fi

callpasswd(){
	echo "Password for root access to database?"
	read MyPASS
}


# Linux bin paths, change this if it can not be autodetected via which command
MYSQL="$(which mysql)"
MYSQLDUMP="$(which mysqldump)"
CHOWN="$(which chown)"
CHMOD="$(which chmod)"
GZIP="$(which gzip)"
# Backup Dest directory, change this if you have someother location
WHEN="$(date +"%Y%m%d")"
DEST="/home/$USER/backups/$WHEN"
# Main directory where backup will be stored
MBD="$DEST/mysql-bups"
#if [ ! -d $MBD ]
# then
#  mkdir $MBD
#fi
# Get hostname
HOST="$(hostname)"
# Get data in dd-mm-yyyy format
NOW="$(date +"%Y%m%d%H%M")"
# File to store current backup file
FILE=""
# Store list of databases
#DBS="mesoraw my_wiki weatherpi efergy freezerpi weewx mysql"
DBS="mesoraw weatherpi"
# DO NOT BACKUP these databases
# IGGY="#mysql50#weewx.first performance_schema mysql weewx.first"
#IGGY="information_schema mesowx mysql #mysql50#mythconverg.120814 #mysql50#mythconverg.org performance_schema phpmyadmin weewx #mysql50#weewx-mysql"
IGGY="mesoweather performance_schema phpmyadmin my_wiki efergy freezerpi weewx mysql"

[ ! -d $MBD ] && mkdir -p $MBD || :
# Only root can access it!
#$CHOWN 0.0 -R $DEST
#$CHMOD 0600 $DEST
# Get all database list first

# -- # callpasswd $MyPASS
# Warning: Using a password on the command line interface can be insecure.


# Uncomment to do them all, potherwise use variable at DBS start.
###DBS="$($MYSQL -u $MyUSERSHOW -h $MyHOST -p$MyPASS -Bse 'show databases')"
#DBS="$($MYSQL -u $MyUSERSHOW -h $MyHOST -p$MyPASS -Bse 'show databases' | grep pi )"
for db in $DBS
do
    skipdb=-1
        if [ "$IGGY" != "" ];
        then
           for i in $IGGY
           do
              [ "$db" == "$i" ] && skipdb=1 || :
           done
         fi
         if [ "$skipdb" == "-1" ] ;
         then
                 FILE="$MBD/$db.host-$HOST.$NOW.gz"
                 FILELOCK="$MBD/$db.host-$HOST.$NOW-skiplock.gz"
# do all inone job in pipe,
# connect to mysql using mysqldump for select mysql database
# and pipe it out to gz file in backup dir :)
         case  $1 in
            dryrun)
                 $MYSQLDUMP -u $MyUSERDUMP -h $MyHOST -p$MyPASS $db | $GZIP -9 > $FILE
                 #$MYSQLDUMP --skip-lock-tables -u $MyUSERDUMP -h $MyHOST -p$MyPASS $db | $GZIP -9 > $FILELOCK
		 # https://stackoverflow.com/questions/104612/run-mysqldump-without-locking-tables
		 # mysqldump -uuid -ppwd --skip-opt --single-transaction --max_allowed_packet=1G -q db |   mysql -u root --password=xxx -h localhost db
                 $MYSQLDUMP -u $MyUSERDUMP -h $MyHOST -p$MyPASS --skip-opt --single-transaction -q $db | $GZIP -9 > $FILELOCK
		 echo -e "\t\n'\e[1;33m'Backup file is... $FILE'\e[0;0m'\n"
		 echo -e "\t\n'\e[1;33m'Backup file is... $FILELOCK'\e[0;0m'\n"
                  ;;
              doit)
                 ###$MYSQLDUMP -u $MyUSERDUMP -h $MyHOST -p$MyPASS $db | $GZIP -9 > $FILE
                 #$MYSQLDUMP --skip-lock-tables -u $MyUSERDUMP -h $MyHOST -p$MyPASS $db | $GZIP -9 > $FILELOCK
		 # https://stackoverflow.com/questions/104612/run-mysqldump-without-locking-tables
		 # mysqldump -uuid -ppwd --skip-opt --single-transaction --max_allowed_packet=1G -q db |   mysql -u root --password=xxx -h localhost db
                 $MYSQLDUMP -u $MyUSERDUMP -h $MyHOST -p$MyPASS --skip-opt --single-transaction -q $db | $GZIP -9 > $FILELOCK
		 ###echo -e "\t\n'\e[1;33m'Backup file is... $FILE'\e[0;0m'\n"
		 echo -e "\t\n'\e[1;33m'Backup file is... $FILELOCK'\e[0;0m'\n"
                  ;;
                *)
                callusage
                  ;;
         esac
      fi
done

exit 0


# to restore...
# http://alvinalexander.com/blog/post/mysql/how-restore-mysql-database-from-backup-file

echo -e "\t\t\t TO RESTORE THESE \n\n"

echo -e "\tcd /var/lib/mysql\n"
echo -e "\tshow databases;\n"
echo -e "\tdrop database freezerpi;\n"
echo -e "\tcreate database freezerpi;\n"
echo -e "\t{now redundant ---mysqladmin -u root -p create freezerpi}\t\n"
echo -e "\tmysql -u root -p freezerpi < freezerpi.host-whitebeard.201603041728.gz\t\n"
mysql> show databases;
+--------------------+
| Database           |
+--------------------+
| information_schema |
| freezerpi          |
| mysql              |
| performance_schema |
| phpmyadmin         |
| weatherpi          |
+--------------------+
6 rows in set (0.00 sec)

mysql> drop database freezerpi;
Query OK, 2 rows affected (0.02 sec)

mysql> drop database weatherpi;
Query OK, 2 rows affected (0.03 sec)

mysql> create database weatherpi;
Query OK, 1 row affected (0.00 sec)

mysql> create database freezerpi;
Query OK, 1 row affected (0.00 sec)

mysql> quit
Bye

:root@masterofpis:/var/lib/mysql
06:04 PM $ mysql -uroot -p freezerpi < /home/pi/freezerpi.host-whitebeard.201603041758
freezerpi.host-whitebeard.201603041758.gz           freezerpi.host-whitebeard.201603041758-skiplock.gz
:root@masterofpis:/var/lib/mysql
06:04 PM $ gunzip  /home/pi/freezerpi.host-whitebeard.201603041758-skiplock.gz
:root@masterofpis:/var/lib/mysql
06:05 PM $ gunzip  /home/pi/weatherpi.host-whitebeard.201603041758-skiplock.gz
:root@masterofpis:/var/lib/mysql
06:06 PM $ ls  /home/pi/weatherpi.host-whitebeard.201603041758-skiplock
/home/pi/weatherpi.host-whitebeard.201603041758-skiplock
:root@masterofpis:/var/lib/mysql
06:06 PM $ mysql -uroot -p weatherpi <  /home/pi/weatherpi.host-whitebeard.201603041758-skiplock
Enter password:

