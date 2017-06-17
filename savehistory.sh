#!/bin/bash -x
# save and sort (with no-dupes!) history files·
# to reduce rollout of early commands
# users
# $USER for interactive shell
# $LOGNAME for crontab
#SHELL='/bin/bash'

# Horrible cludge to work around shell script not working as intended
# when called from crontab's
if [ $USER -a $LOGNAME ]
then
 echo "nothing to do, must be a real shell!"
  else
   USER="$LOGNAME"
    echo "Probably called from cron, USER is now..."$USER
fi

# archive directory
histarch=.old_history/
# file to archive
shhist=.bash_history
# identifier
datestamp=`date '+%Y%m%d%M'`
#/usr/bin/printenv

if [ $USER = pi -o $LOGNAME = pi ]
   then
      rdir=/home/pi/
elif [ $USER = graybeard  -o $LOGNAME = graybeard ]
   then
       rdir=/home/graybeard/
elif [ $USER = root -o $LOGNAME = root ]
   then
       rdir=/root/
    else
     echo "Unknown user: exiting now"
     exit 1
fi

if [ -d $rdir$histarch ]
   then
        :
    else
         mkdir $rdir$histarch
fi

cp $rdir$shhist $rdir$histarch$datestamp$shhist
sort -u $rdir$shhist -o $rdir$shhist

# pre user selection additions above
#cp $pir$shhist $pir$histarch$shhist$datestamp
#sort -u $pir$shhist -o $pir$shhist

exit 0
