

This weewx skin (SLE) calls mysqldump and instructs it to dump data from the weewx database, for a predetermined timeframe.
It will do this at regular intervals, as specified by the report_timing feature of weewx (see the weewx docs)

This is not intended to be used to dump the whole database, or even a large portion of it. If you do that it can seriously overload weewx and weird and bizarre things will start to happen within weewx - ie: report generation, data collection, archiving can all be disrupted.

This skin is only configured for MySQL (MariaDB) databases.
Sqlite databases can be effectively backed up by simply copying them, if you want a similar 'skinned' approach to this then have a look at 'Using the RSYNC skin as a backup solution' https://github.com/weewx/weewx/wiki/Using-the-RSYNC-skin-as-a-backup-solution That approach also aims to create a backup during a quite window of time (no database writes) available within the weewx cycle.

### Installation

1 run the installer:

**wee_extension --install weewx-mysqlbackup-master.zip**

2 edit the skin.conf file to suit your installation

   * select a suitable *report_timing* stanza
 
   * select a suitable archive period

3 restart weewx:

**sudo /etc/init.d/weewx stop**

**sudo /etc/init.d/weewx start**





To use this backup method effectively, you need to dump (backup) your main weewx database first. We can then add these files, to that database.
You can do this manually by invoking mysqldump from the command line, similar to the following.

Get the epoch date string to use in the filename

    date +%s   
    1497830683

dump the data into a suitable file(name)

    mysqldump -uweewx -p -hlocalhostweatherpi archive--single-transaction --skip-opt | 
            gzip > /{your_backup_directory}/wholebackup-1497830683.sql

Adding the epoch date string to the filename helps in determing its current age, when to do update from. You'll then use the partial backups created by this skin, to restore from that date.

The partial dumps created by this skin have a header, which includes the CREATE TABLE statement - a lot of INSERT statements and a footer.

```-- MySQL dump 10.13Distrib 5.5.55, for debian-linux-gnu (i686) 
-- 
-- Host: localhostDatabase: weatherpi
-- ------------------------------------------------------
-- Server version>······5.5.55-0+deb8u1
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */; 
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */; 
 
 -- 
 -- Table structure for table `archive` 
 -- 

/*!40101 SET @saved_cs_client = @@character_set_client */; 
/*!40101 SET character_set_client = utf8 */; 
CREATE TABLE `archive` ( 
`dateTime` int(11) NOT NULL, 
`usUnits` int(11) NOT NULL,
`interval` int(11) NOT NULL, 
`barometer` double DEFAULT NULL, 
`pressure` double DEFAULT NULL,
`altimeter` double DEFAULT NULL, 
[...]
`windBatteryStatus` double DEFAULT NULL, 
`rainBatteryStatus` double DEFAULT NULL, 
`outTempBatteryStatus` double DEFAULT NULL,
`inTempBatteryStatus` double DEFAULT NULL, 
`lightning` double DEFAULT NULL, 
`rainCount1` double DEFAULT NULL,
`rainCount2` double DEFAULT NULL,
`rainCount3` double DEFAULT NULL,
`rainCount4` double DEFAULT NULL,
PRIMARY KEY (`dateTime`),
UNIQUE KEY `dateTime` (`dateTime`) 
); 
/*!40101 SET character_set_client = @saved_cs_client */; 
 
 -- 
 -- Dumping data for table `archive`-- 
 -- WHERE:dateTime>1497622847
 ```
 Everything above is the **header** (we need that only once)
 Below are the actual **INSERT** statements (as many as cover the time we need to restore)

```INSERT INTO `archive` VALUES (1497622860,17,1,1025.077,970.031046132267,1023.07394604233,2.86341264282514,21.351575,4.703125,36.0077,100,0.937546883483462,78.16020796314,1.05551635888867,78.5858585858586,0,0,4.703125,4.703125,4.703125,0.000408665001435199,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.95,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
INSERT INTO `archive` VALUES (1497622920,17,1,1025.077,970.056190971907,1023.10020511329,3.01429914403898,21.320325,4.734375,36.0083,100,0.775430162444809,77.9557099825767,0.931337963725294,77.7777777777778,0,0,4.734375,4.734375,4.734375,0.000409593627050564,17.220975,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.9525,4.95,4.95,4.93,NULL,20227104,NULL,404,556);

 [...]

INSERT INTO `archive` VALUES (1497622980,17,1,1025.077,970.021751502796,1023.06423954295,3.02441428710914,21.3047,4.625,36.005275,100,0.574028000130207,78.0280725907076,0.711203535935679,78.5858585858586,0,0,4.625,4.625,4.625,0.000410737550744648,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.95,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
```
The **INSERT** statements finish
and we continue below with the **footer** (which are also only needed once)

```/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */; 

-- Dump completed on 2017-06-180:20:47
``` 

Any of these files will re-populate a database by themselves.
To attempt the same process immediately with another file will create an error.
These files are one-shot only - unless we modify them.

To add data from another of these files, you need to do some editing.

If you want to use more than one file...

We need:-
1 only header
1 only footer
As many INSERT INTO statements as required.


    mkdir /tmp/dump-work
    cd /tmp/dump-work
    cp our_partial_backups to_here
    gunzip *

That's the groundwork, we should now be ready to start...

    cp weatherpi-host.masterofpis-201706150020-24hours header
    cp weatherpi-host.masterofpis-201706150020-24hours footer

Edit the header and footer files to contain only those fields (we don't want any INSERT INTO instructions)
header = everything above the first INSERT INTO statement
footer = everything below the last INSERT INTO statement


    cp weatherpi-host.masterofpis-201706150020-24hours 1
    cp weatherpi-host.masterofpis-201706151033-24hours.gz 1a
    cp weatherpi-host.masterofpis-201706170020-24hours-middle 2
    cp weatherpi-host.masterofpis-201706190021-daily 3

with these, we only want the INSERT INTO instructions - delete the header and footers within these files.

    sort -u 1 1a 2 3 > 11a23

Remove duplicate lines and create a file containing all the INSERT statements that we want.

    cat header  > new_file
    cat 11a23 >> new_file
    cat footer >> new_file

We create a new file with a header, all the INSERT's we require, plus the footer

    mysql -u root -p
    create database dumpnewtest;

Create the database

    mysql -u root -p dumptestnew < new_file

Insert our new file into it

    mysqldump -u root -p -q --single-transaction --skip-opt dumptestnew > dumptestnew-compare
    vim -d new_file dumptestnew-compare

If you want to, dump that and compare it to what we restored from new_file


That's an outline of the process. Names will obviously be changed to suit


## Notes and WARNINGS (Again! and from skin.conf)

DON'T back the whole database up with this skin. You'll overload weewx and weird
things will happen.

The idea is to instead select a small rolling window from the database, and dump
this at each report_timing interval. We will use that as a partial backup.
At restore time we'll then need to select some or all, and stitch them together as
appropriate.

This skin was created to backup a mysql database that runs purely in memory.
And because that's a little! fragile, the script runs every hour, and dumps the last
24 hours of the database to the mysql_bup_file in the format... 
{database}-host.{hostname}-{epoch-timestamp}-{window-time-period}.gz 
 eg:weatherpi-host.masterofpis-201706132105-24hours.gz 

 Those intervals are handled easily on my setup and do not interrupt the report
generation in weewx. YMWV 
 
Jun 13 21:05:42 masterofpis wee_reports[26062]: sqlbackup: Created backup in 0.31 seconds

You'll need to adjust the values to suit you. Set sql_debug = "2" in the skin.conf
while you do so.
This script currently performs no error checking so check the resulting files for 
integrity.
disk full, will return silence!
empty database, will return silence!

Reasons for doing it this way (instead of seperate scripts and cron) are that it
should integrate easily with the weewx process. This report runs after database
writes have been done (providing you don't ask too much of it), and keeping it
under the weewx umbrella fits the "one stop shop" model.
Keep it small and sensible and that should all remain true.

Testing: Backup your mysql database first - via other methods.
Modify your variables, and turn on debug in the skin.conf file
Then copy and modify a minimal weewx.conf file as weewx.wee.conf and invoke it by using.

    wee_reports /etc/weewx/weewx.wee.conf && tail -n20 /var/log/syslog | grep wee_report
