#!/bin/bash
## masterofpis ##
## masterofpis ##
## masterofpis ##
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

MyUSERDUMP="root"     # USERNAME
MyPASS="h0whigh"      # PASSWORD
MyHOST="localhost"    # Hostname of database

# Paths
# Backup Dest directory, change this if you have someother location
WHEN="$(date +"%Y%m%d")"
#DEST="/home/$USER/backups/$WHEN"
DEST="/opt/backups/$WHEN"
# Results in directory where backup will be stored
MBD="$DEST/mysql-bups"

# Linux bin paths, change this if it can not be autodetected via which command
MYSQL="/usr/bin/mysql"
MYSQLDUMP="/usr/bin/mysqldump"
CHOWN="/bin/chown"
CHMOD="/bin/chmod"
GZIP="/bin/gzip"
HOST="$(hostname)"
# Get data in dd-mm-yyyy format
NOW="$(date +"%Y%m%d%H%M")"
# File to store current backup file
FILE=""
# Store list of databases
DBS="mesoraw weatherpi"
# DO NOT BACKUP these databases
IGGY="mesoweather performance_schema phpmyadmin my_wiki efergy freezerpi weewx mysql"

#logger "sqlbackup running?"

# /usr/local/sbin/remountrw
[ ! -d $MBD ] && mkdir -p $MBD || :

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
                 FILELOCK="$MBD/$db.host-$HOST.$NOW-skiplock.gz"
                 $MYSQLDUMP -u $MyUSERDUMP -p$MyPASS -h $MyHOST --skip-opt --single-transaction -q $db archive -w"dateTime>1497259000"
      fi
done
# /usr/local/sbin/remountro

exit 0


# to restore...
# http://alvinalexander.com/blog/post/mysql/how-restore-mysql-database-from-backup-file

#echo -e "\t\t\t TO RESTORE THESE \n\n"

#echo -e "\tcd /var/lib/mysql\n"
#echo -e "\tshow databases;\n"
#echo -e "\tdrop database freezerpi;\n"
#echo -e "\tcreate database freezerpi;\n"
#echo -e "\t{now redundant ---mysqladmin -u root -p create freezerpi}\t\n"
#echo -e "\tmysql -u root -p freezerpi < freezerpi.host-whitebeard.201603041728.gz\t\n"
#mysql> show databases;
#+--------------------+
#| Database           |
#+--------------------+
#| information_schema |
#| freezerpi          |
#| mysql              |
#| performance_schema |
#| phpmyadmin         |
#| weatherpi          |
#+--------------------+
#6 rows in set (0.00 sec)
#
#mysql> drop database freezerpi;
#Query OK, 2 rows affected (0.02 sec)
#
#mysql> drop database weatherpi;
#Query OK, 2 rows affected (0.03 sec)
#
#mysql> create database weatherpi;
#Query OK, 1 row affected (0.00 sec)
#
#mysql> create database freezerpi;
#Query OK, 1 row affected (0.00 sec)
#
#mysql> quit
#Bye
#
#:root@masterofpis:/var/lib/mysql
#06:04 PM $ mysql -uroot -p freezerpi < /home/pi/freezerpi.host-whitebeard.201603041758
#freezerpi.host-whitebeard.201603041758.gz           freezerpi.host-whitebeard.201603041758-skiplock.gz
#:root@masterofpis:/var/lib/mysql
#06:04 PM $ gunzip  /home/pi/freezerpi.host-whitebeard.201603041758-skiplock.gz
#:root@masterofpis:/var/lib/mysql
#06:05 PM $ gunzip  /home/pi/weatherpi.host-whitebeard.201603041758-skiplock.gz
#:root@masterofpis:/var/lib/mysql
#06:06 PM $ ls  /home/pi/weatherpi.host-whitebeard.201603041758-skiplock
#/home/pi/weatherpi.host-whitebeard.201603041758-skiplock
#:root@masterofpis:/var/lib/mysql
#06:06 PM $ mysql -uroot -p weatherpi <  /home/pi/weatherpi.host-whitebeard.201603041758-skiplock
#Enter password:
#
