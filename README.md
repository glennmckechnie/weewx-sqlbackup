

This weewx skin (SLE) calls mysqldump and instructs it to dump data from the weewx database, for a predetermined timeframe.
It will do this at regular intervals, as specified by the report_timing feature of weewx (see the weewx docs)

This is not intended to be used to dump the whole database, or even a large portion of it. If you do that it can seriously overload weewx and weird and bizarre things will start to happen within weewx - ie: report generation, data collection, archiving can all be disrupted.

This skin was originally  configured for MySQL (MariaDB) databases. It has since grown to incorporate sqlite databases (except it captures the whole database).
Sqlite databases can also be backed up by simply copying them, if you want a similar 'skinned' approach that does it by copying then have a look at [Using the RSYNC skin as a backup solution.](https://github.com/weewx/weewx/wiki/Using-the-RSYNC-skin-as-a-backup-solution) 
Both these methods aim to create a backup during a quite window of time (no database writes) available within the weewx cycle.

### Installation

1 run the installer:

**wee_extension --install weewx-mysqlbackup-master.zip**

2 edit the skin.conf file to suit your installation

   * select a suitable *report_timing* stanza
 
   * select a suitable archive period

3 restart weewx:

**sudo /etc/init.d/weewx stop**

**sudo /etc/init.d/weewx start**


#### Notes for MySQL (MariaDB) database

To use this backup method effectively, you need to dump (backup) your main weewx database first. We can then add these files, to that database.
You can do this manually by invoking mysqldump from the command line, similar to the following.

Get the epoch date string to use in the filename

    date +%s
    1497830683

dump the data into a suitable file(name)

    mysqldump -uweewx -p -hlocalhost weatherpi archive --single-transaction --skip-opt | 
            gzip > /{your_backup_directory}/wholebackup-1497830683.sql

Adding the epoch date string to the filename helps in determing its current age, when to do update from. You'll then use the partial backups created by this skin, to restore from that date.

When configuring your sqlbackup, DO turn on sql_debug in the skin.conf file and view the output in /var/log/syslog (or your default log.) Pay particular attention to the times returned in the DEBUG lines.

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
 
 Everything above is the **header** (we need that only once).
 
 Below are the actual **INSERT** statements (as many that cover the time we need to restore, so we will gather those together in a clump, and keep reading...)

```INSERT INTO archive VALUES (1497622860,17,1,1025.077,970.031046132267,1023.07394604233,2.86341264282514,21.351575,4.703125,36.0077,100,0.937546883483462,78.16020796314,1.05551635888867,78.5858585858586,0,0,4.703125,4.703125,4.703125,0.000408665001435199,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.95,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
INSERT INTO archive VALUES (1497622920,17,1,1025.077,970.056190971907,1023.10020511329,3.01429914403898,21.320325,4.734375,36.0083,100,0.775430162444809,77.9557099825767,0.931337963725294,77.7777777777778,0,0,4.734375,4.734375,4.734375,0.000409593627050564,17.220975,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.9525,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
 [...]
INSERT INTO archive VALUES (1497622980,17,1,1025.077,970.021751502796,1023.06423954295,3.02441428710914,21.3047,4.625,36.005275,100,0.574028000130207,78.0280725907076,0.711203535935679,78.5858585858586,0,0,4.625,4.625,4.625,0.000410737550744648,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.95,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
```

The **INSERT** statements finish

And we continue below with the **footer** (which is only needed once)

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

##### SO, If you want to use more than one file...

We need:-

1 only header

1 only footer

but as many *INSERT INTO* statements as are required for the database update.

For example, if we were to do the following, we'd have success.

    mkdir /tmp/dump-work
    cd /tmp/dump-work
    cp our_partial_backups to_here
    gunzip *

That's the groundwork, we should now be ready to start.
Create some duplicate files
Edit these *header* and *footer* files to contain only those fields (we don't want any INSERT INTO instructions)
header = everything above the first INSERT INTO statement
footer = everything below the last INSERT INTO statement

    cp weatherpi-host.masterofpis-201706150020-24hours header
    cp weatherpi-host.masterofpis-201706150020-24hours footer

we now need our data. Duplicate the required files and edit the result. With these, we only want the **INSERT INTO** instructions, that's all the middle data or the bulk of the file. 
Delete the header and footers within these files.

    cp weatherpi-host.masterofpis-201706150020-24hours 1
    cp weatherpi-host.masterofpis-201706151033-24hours.gz 1a
    cp weatherpi-host.masterofpis-201706170020-24hours-middle 2
    cp weatherpi-host.masterofpis-201706190021-daily 3
    
Using these modified files we use **sort** to remove duplicate lines and create one compact file containing all the INSERT statements that we want.

    sort -u 1 1a 2 3 > 11a23
    
We now create a new file with a header, all the INSERT's we require, plus the footer. We're back to the start, but bigger and better.

    cat header  > new_file
    cat 11a23 >> new_file
    cat footer >> new_file

Create the database

    mysql -u root -p
    create database dumpnewtest;

Insert our new file into it and we should have a database with all that we require.

    mysql -u root -p dumptestnew < new_file

And if you want to, dump that and compare it to what we restored from the new_file. They should be the same, where it matters!

    mysqldump -u root -p -q --single-transaction --skip-opt dumptestnew > dumptestnew-compare
    vim -d new_file dumptestnew-compare

That's an outline of the process. Names have obviously been changed to suit.

#### Notes for sqlite (.sdb) databases

The dumps that this skin creates are a backup of the whole database.

The process to dump an sqlite databases happens a lot quicker than the mysqldump process. This doesn't mean that you've got all the time required to do it cleanly, from within weewx; but it's worth a try before you use another method (one of which is outlined above, on the weewx/wiki)

When configuring your sqlbackup, DO turn on sql_debug in the skin.conf file and view the output in /var/log/syslog (or your default log.) Pay particular attention to the times returned in the DEBUG lines.

To restore it...

    gunzip pmon-host.masterofpis-201706210841-daily.gz

    sqlite3 pmon.sdb < pmon-host.masterofpis-201706210841-daily

check it using sqlite3...

    09:21 AM $ sqlite3 pmon.sdb
    SQLite version 3.8.7.1 2014-10-29 13:59:56
    Enter ".help" for usage hints.
    sqlite> pragma integrity_check;
    ok
    sqlite> .quit

or

    09:22 AM $ echo 'pragma integrity_check;' | sqlite3 pmon.sdb
    ok

### Another view - Info from the scripts comments

    """ Notes and WARNINGS

    DON'T back the whole database up with this skin. You'll overload weewx and weird
    things will happen.

    The idea is to instead select a small rolling window from the database (if its a
    MySQL or  MariaDB) and dump this at each report_timing interval. We will use that
    as a partial backup.
    If it's an sqlite dtabase, it will dump it (them) all.
    At restore time we'll then need to select some or all of the dump files, and stitch
    them together as appropriate.

    This skin was created to backup a mysql database that runs purely in memory, it has
    since evolved to include sqlite databases as well.
    Because running a database is a little! fragile (to say the least mI configured my
    script to run every hour, and dumps the last 24 hours of the database to the
    xxsql_bup_file in the format...
         {database}-host.{hostname}-{epoch-timestamp}-{window-time-period}.gz
    eg:  weatherpi-host.masterofpis-201706132105-24hours.gz

    Those intervals are handled easily on my setup and do not interrupt the report
    generation in weewx. Your processor, memory and database sizes will be different to
    mine... YMWV

 Jun 13 21:05:42 masterofpis wee_reports[26062]: sqlbackup: Created backup in 0.31 seconds

    You'll need to adjust the values to suit you. Setting sql_debug = "2" in the skin.conf
    will inform you while you make changes - look at the logs, or at the foot of the
    sqlbackup.html page.
    This script currently performs no error checking so check the resulting files for
    integrity.
    disk full, it will return silence!
    empty database, it will also return silence!

    Reasons for doing it this way (instead of seperate scripts and cron) are that it
    should integrate easily with the weewx proces. This report runs after database
    writes have been done (providing you don't ask too much of it), and keeping it
    under the weewx umbrella fits the "one stop shop" model. If we don't interfere too much
    we should slip under the radar.
    Keep it small and sensible and that should all remain true.

    Testing: BACK UP your database first - via other methods. (Okay, I've used this script
    by passing the current unix time·
    # date +"%s"
    # returns  current epoch time
    In short...
    Open skin.conf, modify the variables, turn on sql_debug

    To help speed up the process, bypass the report_timing setting and cycle through the
    setup process quickly by copying and modifying a minimal weewx.conf file as weewx.wee.conf
    and invoke that by using.
    One hiccup with the wee_reports method is that it may return longer times if it encounters
    a locked database. The ultimate test is when it's run under weewx's control, wee_reports
    is still very useful to fine tune your setup

    wee_reports /etc/weewx/weewx.wee.conf && tail -n20 /var/log/syslog | grep wee_report

    then watch your logs, or the sqlbackup.html page if you're generating the report.
    """
