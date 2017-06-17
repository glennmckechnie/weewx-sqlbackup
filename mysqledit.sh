#!/bin/bash

# calc ?? or date or alter
action=$1

# NO error checking! 
rainextreme=10

echo "Preparing to act ($action) on Rain values > $rainextreme"
read  -s -p "Mysql password is ??" password
echo

#tmpfile=/tmp/$RANDOM
tmpfile=$(date +"%y%m%d%H%M%S")
echo "SELECT  datetime,rain FROM archive WHERE (rain > $rainextreme);" | mysql -uroot -p$password weatherpi > $tmpfile
cat $tmpfile

tail -n+2 $tmpfile | awk -F " " '{print $1}' > "$tmpfile"-col1
echo $tmpfile-col1
tail -n+2 $tmpfile | awk -F " " '{print $2}' > "$tmpfile"-col2
echo $tmpfile-col2
#exit 0

case $action in
    calc)
        while IFS='' read -r line || [[ -n "$line" ]] ; do
	echo "  $line"
	echo "        scale=2; $line/0.254" | bc -l
        done < $tmpfile-col2
	;;
    date)
        while IFS='' read -r line || [[ -n "$line" ]] ; do
        epochtoreal=$(date --date=@"$line")
        echo $epochtoreal
        done < $tmpfile-col1
        #exit 0
	;;
    alter)
        while IFS='' read -r line || [[ -n "$line" ]] ; do
        #dtime in 'cat $tmpfile-col1'
        #do
        echo "SELECT rain FROM archive WHERE (datetime = $line);" | mysql -uroot -p$password weatherpi
        echo "UPDATE archive  SET rain=NULL  where  datetime = $line ;"| mysql -uroot -p$password weatherpi
        echo "UPDATE archive  SET rainRate=NULL  where  datetime = $line ;"| mysql -uroot -p$password weatherpi
        echo "SELECT rain FROM archive WHERE (datetime = $line);" | mysql -uroot -p$password weatherpi

        #echo $line
        # echo "next line"
        done < $tmpfile-col1
        ;;
	*)
	echo "Nothing to do - use 'calc' ??? or 'date' or 'alter'"
	;;
esac
echo  $tmpfile-col1
