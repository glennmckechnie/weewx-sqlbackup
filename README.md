## SQLBackup README



This skin (sqlbackup) uses a Search List Extension (SLE) of the same name to call mysqldump and/or sqlite to dump data from the weeWX database.
If it's MySQL (MariaDB) then it will dump a user specified timeframe; if it's sqlite then it will dump all of it. The default option in both cases is to only dump the archive tables.
It will do this at regular intervals as specified by the [report_timing](http://www.weewx.com/docs/customizing.htm#customizing_gen_time) feature of weeWX.

If you dump the whole database, and it's large, you can interfere with weeWX's operation and odd things may start to happen. This will depend on your CPU, database size, weeWX setup, maybe even the weather!
In most cases this probably won't matter too much and you'll just get a message about skipping reports. If we lock weeWX out of its database for too long though, the weird and wonderful may start to occur, so it's best we don't push it too far.

This skin was originally configured for MySQL (MariaDB) databases only and we can configure mysqldump to do a partial dump. We can therefore limit ourselves to a small, very managable portion of the database.
Because this has since expanded to incorporate sqlite databases, where it captures the whole database, it may be slower and more prone to interfering with weeWX. But compared to MySQL, sqlite is not as demanding so it may still be fit for duty.
Because we are getting a full backup of the sqlite database on each run, we can perhaps do them less frequently and here the report_timing feature really comes into its own.
Sqlite databases can also be backed up by simply copying them, if you want a similar 'skinned' approach that does just that then have a look at [Using the RSYNC skin as a backup solution.](https://github.com/weewx/weewx/wiki/Using-the-RSYNC-skin-as-a-backup-solution)
Both these methods aim to create a backup during a quiet window of time (when there are no database writes) that's available within the weeWX cycle.

With the variation in weeWX setups, the only way to know how it will work for you is to give it a try. Just start off gently and DON'T ask for too much at once, be conservative with what you're asking for.


### Installation

1 Run the installer:

**wee_extension --install weewx-sqlbackup-master.zip**

2 Edit the skin.conf file to suit your installation

   * Select a suitable *report_timing* stanza

   * Select a suitable archive period and name (sql_period and sql_label.)

   * Check that the defaults are correct for your setup.

   * In particular, check the backup directory (xxsql_bup_dir) paths. They will be created on the first run.

   * The default is to generate reports - sqlbackup.html.

   * If you're not using the newskin branch of weeWX - Seasons, then configure the sqlbackup.html.tmpl etc. to suit.

3 restart weewx:

**sudo /etc/init.d/weewx stop**

**sudo /etc/init.d/weewx start**

The html template makes heavy use of #include files to generate the report page. These files are located in /tmp/sqlbackup and will remain after each run (if you need to inspect them or see what's happening). They will be blanked, deleted, re-generated on each run of the skin. ie: they are all renewed and should reflect each runs output. There are no stale files, they are unique to each run - thus their placement in the /tmp directory.

#### Notes for MySQL (MariaDB) database

If your database is a MySQL one then to use this backup method effectively, you need to do a full dump (backup) of your main weeWX database first. Of note; while dumping the database may take seconds, stretching to minutes, rebuilding it can take hours. The best advice I can offer is to rebuild it as a working copy ASAP. You will then bring that up-todate with the partial dumps. Whatever you do - test your restore strategy well before time.

A strategy I've used is to have a working, preferably empty, sqlite database ready to go. If you need to rebuild your MySQL database you can simply reconfigure weewx to use archive_sqlite while the MySQL is restored. Once the MySQL is restored, swap weewx back to archive_mysql. Dump the sqlite into an sql file, convert and import it into your restored and working MySQL (reference the notes on the wiki - [Transfer from sqlite to MySQL[(http://github.com/weewx/weewx/wiki/Transfer%20from%20sqlite%20to%20MySQL) and you'll fill the gaps nicely - well, most of them.

However you choose to do it, we need a starting point.
To get that initial database, you can do this manually by invoking mysqldump from the command line, similar to the following.

###### Full dump: Method 1

Get the epoch date string to use in the filename (optional but helpful later).

    date +%s
    1497830683

dump the data into a suitable file(name)

    mysqldump -uweewx -p -hlocalhost weatherpi archive --single-transaction --skip-opt |
            gzip > /{your_backup_directory}/wholebackup-1497830683.sql

Adding the epoch date string to the filename helps in determing its current age, when to do update from. You'll then use the partial backups created by this skin, to restore from that date.

When configuring your sqlbackup, DO turn on sql_debug in the skin.conf file and view the output in /var/log/syslog (or your default log) or in the report page, sqlbackup.html 

###### Full dump: Method 2

Or if you want to live dangerously and see just how long it does take to generate a whole backup with this skin, and if my warnings are overstated, then configure the skin.conf for that single run.
Picking a timestamp that precedes your database starting point should do it. Unless you have over 2 years of data the following should work - adjust accordingly.

    60*60*24*365*2
    = 63072000

Plug that value in as your time period - sql_period = "63072000" and change the file label to something meaningful - sql_label = "allofit" so that you know what it is.

    Jun 22 16:13:47 masterofpis weewx[28785]: sqlbackup : DEBUG:  mysql database is weatherpi
    [...]
    Jun 22 16:14:35 masterofpis weewx[28785]: engine: Launch of report thread aborted: existing report thread still running
    [...]
    Jun 22 16:15:18 masterofpis weewx[28785]: sqlbackup : DEBUG: 90.79 secs to run /usr/bin/mysqldump -uXxXxX -pXxXxX -hlocalhost -q  weatherpi archive -w"dateTime>1435039127"  -single-transaction --skip-opt
    [...]
    Jun 22 16:15:51 masterofpis weewx[28785]: imagegenerator: Generated 22 images for StandardReport in 6.35 seconds

    -rw-r--r-- 1 root 58011783 Jun 22 16:15 weatherpi-host.masterofpis-201706221613-allofit.gz

The above shows one hiccup for my single run - it took 90 seconds which exceeds the 60 second archive interval here, therefore weeWX skipped the reports for that time interval. After that it's back to normal, which is OK by me.

And FWIW, opening the resulting file and finding the first dateTime entry show I over estimated at 2 years.

    date -d +@1451720100
    Sat  2 Jan 18:35:00 AEDT 2016

Looks like that's all I've got in there. Yep! It seems I'll have to find and restore a few earlier databases.

Another aside, it took 7 hours on a quad-core AMD A8-5600K to re-instate that database (1 minute weewx archive_interval). There's something to be said for doing this on a (semi-)regular basis, and with small dump files.


#### Configuring the ongoing, partial dumps

The skin.conf file may appear overwhelming but it should run with the values pre-configured. If not wade through it and find what needs tweaking. It's well commented :-)

```
###############################################################################
# Copyright (c) 2017 Glenn McKechnie glenn.mckechnie   gmail.com              #
# With credit to Tom Keffer tkeffer   gmail.com                               #
#                                                                             #
#  SQLDUMP CONFIGURATION FILE                                                 #
#  This 'report' generates gzipped backup files from a running weewx          #
#  database.                                                                  #
#                                                                             #
###############################################################################
#
# Report timing:
# see http://www.weewx.com/docs/customizing.htm#customizing_gen_time
#
#  4 min after, every 12 hours
#report_timing  = '4 */12 * * *'
#  20 min after, every hour
#report_timing = '*/20 * * * *'
report_timing = '@daily'

# First time? Need a refresher? There's a README.md file in the skins directory
# for detailed instructions, or sqlbackupREADME.html on your weewx server.

[sqlbackup]  # This section heading is all lower case to enable report duplication.

        #sql_user = "your_user_if_different_to_weewx.conf"
        #sql_host = "localhost_is_the_default"
        # default is preset as weewx
        #sql_pass = "your_password_if_different_to_weewx.conf"

        # default database is read from weewx.conf. Can be overidden here. Specify
        # here for multiple databases
        #mysql_database = "weatherpi mesoraw"
        #sql_database = "pmon weewx"

        # default is preset as '' (none) which will do the dailies as well.
        # (daily tables get rebuilt when weewx restarts) Leave as archive for slightly 
        # smaller backups
        sql_table = "archive"
        # default is preset as /var/backups
        mysql_bup_dir = "/opt/backups/mysql-backups"
        # default is preset as /var/backups
        sql_bup_dir = "/opt/backups/sql-backups"
        # a dated_dir structure is preset to "True" To disable uncomment the following
        #sql_dated_dir = 'False'

        # generate a summary report for the last run. Useful for obvious errors, not useful
        # for serious testing - test your backups to ensure they actually do what you want!
        # Default is preset to "True" To disable uncomment the following line.
        #sql_gen_report = 'False'
        # html_root is used for the report and readme. The default is HTML_ROOT in weewx.conf
        # but can be redirected under the [Section] or here the current templates are for
        # the Seasons (newskin branch)
        #html_root ="/var/www/html/weewx"

        # these need to match, and the user needs do it for now
        # 86400 seconds = 24 hours # 604800 seconds = 7 days
        # This value will be increased by 900 seconds to ensure backups overlap
        #sql_period = "604800" # time in seconds ('86400 + 900' is the default setting)
        #sql_label = "7days" # meaningful (to you) string for the filename ('daily' is default)

        # Local debugging, ie: for this skin only
        # Default is preset to "0" so commenting it out will disable DEBUG output from this skin
        # Set sql_debug to "2" for extra DEBUG info in the logs.
        # (It will also log when the global weewx.conf debug is set to "2")·
        # Set sql_debug to "4" for extra DEBUG info in the report page - sqlbackup.html
        sql_debug = "4"
###############################################################################
```
### Working with the MySQL dump files

When configuring sqlbackup, DO turn on sql_debug in the skin.conf file.
Set it to at least 2 for system logging (/var/log/syslog). If you're generating the html report then set it to 4 and you'll find the debug output at the bottom of the sqlbackup.html page.
Pay particular attention to the times returned in the DEBUG lines. Make sure they are sane. (Remember the warnings above?)

The partial dumps created by this skin have a header, which includes the CREATE TABLE statement - a lot of INSERT statements and a footer.

```
-- MySQL dump 10.13Distrib 5.5.55, for debian-linux-gnu (i686) 
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

```
INSERT INTO archive VALUES (1497622860,17,1,1025.077,970.031046132267,1023.07394604233,2.86341264282514,21.351575,4.703125,36.0077,100,0.937546883483462,78.16020796314,1.05551635888867,78.5858585858586,0,0,4.703125,4.703125,4.703125,0.000408665001435199,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.95,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
INSERT INTO archive VALUES (1497622920,17,1,1025.077,970.056190971907,1023.10020511329,3.01429914403898,21.320325,4.734375,36.0083,100,0.775430162444809,77.9557099825767,0.931337963725294,77.7777777777778,0,0,4.734375,4.734375,4.734375,0.000409593627050564,17.220975,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.9525,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
 [...]
INSERT INTO archive VALUES (1497622980,17,1,1025.077,970.021751502796,1023.06423954295,3.02441428710914,21.3047,4.625,36.005275,100,0.574028000130207,78.0280725907076,0.711203535935679,78.5858585858586,0,0,4.625,4.625,4.625,0.000410737550744648,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,4.95,4.95,4.95,4.93,NULL,20227104,NULL,404,556);
```

The **INSERT** statements finish

And we continue below with the **footer** (which is only needed once)

```
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */; 

-- Dump completed on 2017-06-180:20:47
``` 

Any of these files will re-populate a database by themselves.
To attempt the same process immediately with another file will create an error as they each have a CREATE TABLE statement.
So these files are one-shot only - unless we modify them.

To add data from another of these files, you need to do some editing.

##### To restore using more than one file...

We need:-

one only header

As many INSERT INTO statements as are required for the database update.

one only footer


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

We now need our data. Duplicate the required files and edit the result.
With these, we only want the **INSERT INTO** instructions, that's all the middle data or the bulk of the file. 
We delete the header and footers within these files.

    cp weatherpi-host.masterofpis-201706150020-24hours 1
    cp weatherpi-host.masterofpis-201706151033-24hours 1a
    cp weatherpi-host.masterofpis-201706170020-24hours-middle 2
    cp weatherpi-host.masterofpis-201706190021-daily 3

Using these modified files we use **sort** to remove duplicate lines and create one compact file containing all the INSERT statements that we want.

    sort -u 1 1a 2 3 > 11a23
    # the order really does not matter, sort will do what it says and the -u flag will get rid of the dupes.

We now create a new file with a header, all the INSERT's we require, plus the footer. We're back to the start, but bigger and better.

    cat header  > new_file.sql
    cat 11a23 >> new_file.sql
    cat footer >> new_file.sql

Create the database

    mysql -u root -p
    create database dumpnewtest;

Redirect our new file into mysql and we will have a database consisting of that data.

    mysql -u root -p dumptestnew < new_file.sql

And if you want to, dump that and compare it to what we restored from the new_file. They should be the same, where it matters!

    mysqldump -u root -p -q --single-transaction --skip-opt dumptestnew > dumptestnew-compare
    vim -d new_file dumptestnew-compare

That's an outline of the process. Names have obviously been changed to suit. Tweak to suit.

#### A psuedo script

The following is a psuedo bash script - it will work as is (after changing names!) but you'll need to be familiar with vim and the process as outlined above, re: headers and footers

```
#!/bin/sh

mkdir restore
cd restore

cp  ../weatherpi-host.masterofpis-*.gz .

for i in * ; do gunzip $i; done
for i in * ; do grep $i -e INSERT >> all.txt ; done
# or with vim as the editor this will work
#for i in * ; do zcat $i | grep -e INSERT >> all.txt ; done

sort -u all.txt > allsorted

#cp  weatherpi-host.masterofpis-201706130020-24hours  head.txt
#cp  weatherpi-host.masterofpis-201706130020-24hours  tail.txt
# and then manually edit these resulting files
# or we can just use vim to do several steps at once..
vim ..
# edit file to keep header section and save that buffer
#:w head.txt
# undo and re-edit to keep tail section and save that buffer
#:wq! tail.txt

cp head.txt newdump.sql
cat allsorted  >> newdump.sql
cat tail.txt  >> newdump.sql

mysql -u root -p
# mysql > drop database newdump;
# mysql > create database newdump;

date && mysql -u root -p newdump < newdump.sql && date
```

#### Notes for sqlite (.sdb) databases

The dumps that this skin creates with sqlite3 are a backup of the whole database (less the daily tables if you choose so)

The process to dump an sqlite database goes a lot faster than the mysqldump process. This doesn't mean that you can ignore the warnings outlined above. It will still take time and you won't know how it long that will be until you've tried it out. If it does fail badly then try another method, such as the one using Rsync outlined on the weeWX wiki (see the link given at the start).

Same method applies as above when you are configuring sqlbackup, DO turn on sql_debug in the skin.conf file. Set it to at least 2 for system logging (/var/log/syslog). If you're generating the html report then set it to 4 and you'll find the debug output at the bottom of the sqlbackup.html page. Pay particular attention to the times returned in the DEBUG lines. Make sure they are sane. (Remember the warnings above?)

To restore it...

    gunzip pmon-host.masterofpis-201706210841-daily.gz

    sqlite3 pmon.sdb < pmon-host.masterofpis-201706210841-daily

check it using sqlite3 and pragma integrity_check...

    09:21 AM $ sqlite3 pmon.sdb
    SQLite version 3.8.7.1 2014-10-29 13:59:56
    Enter ".help" for usage hints.
    sqlite> pragma integrity_check;
    ok
    sqlite> .quit

or

    09:22 AM $ echo 'pragma integrity_check;' | sqlite3 pmon.sdb
    ok
### Setting up the report pages

The report page is optional but recommended. At the very least generate and use it while setting up the skin. It's intended to give a quick overview of what happened during each run.
An extract of the .sql capture is displayed, the command syntax used, and any errors that occured with that system command. The sql extract shows the start and finish of the file so you have an idea of what the file contains and therefore what the command generated. If the dump failed late in the capture, it will often show something to that affect at the end of the file. The mysql extract shows the first 100 lines and last 20. The sqlite shows the first 20 and the last 20.

The report was written with the Seasons skin in mind (ie: the newskin branch at github/weewx) and uses the seasons.css file. It can be adapted to suit any other skin by simply including the #includes as noted within sqlbackup.html.tmpl.

The sqlbackup/sqlbackupREADME.html is a html version of the github README.md and is included to give some background and an example / outline of what to do with the resulting files. It's not meant to be a one stop HowTo. You'll need to do some further reading and attempt a few "restores" well before the time comes that you'll actually need to.

### Multiple databases, multiple skins

The default setup of this skin is to backup the main weewx database. It should do that 'out of the box'.
If you modify the database stanzas it will ignore the default behaviour and do what you ask. A space seperated list will allow you to do each of those databases. If you specify mysql_database and sql_database it will bow down and do those too, what ever you say goes. If it doesn't get up again you may want to rethink that strategy!
Maybe you just want the timing of those backups to be different? If so consider using multiple skins.

This skin can be duplicated if you want to split the backups.
You may want to do this if you have multiple databases and don't want the performance hit of doing them all at once. It may also be because you want to treat them differently. Your main weewx database has a 48 hour snapshot taken daily, then a monthly snapshot taken... monthly? if only because you hate the idea of stitching all the smaller ones together again. Your mesoraw weekly, at some other time, for some other reason, etc.

You'll need to do this skin duplication process, manually.


    cd skins
    cp -r sqlbackup sqlbackupweek

Open the weewx/weewx.conf file and duplicate the sqlbackup entry there, and change as required.

```
   [StdReport]
   [...]
       #original entry
       [[sqlbackup]]
            HTML_ROOT = /var/www/html/weewx/sqlbackup
            skin = sqlbackup
       # 2nd skin
       [[sqlbackupweek]]
            HTML_ROOT = /var/www/html/weewx/sqlbackupweek
            skin = sqlbackupweek
```

Open the new directory, skin/sqlbackupweek and edit the skin.conf within. Change the report_timing stanza and the section heading

```
# Report timing: http://www.weewx.com/docs/customizing.htm#customizing_gen_time
#
# 2 minutes past midnight, on Monday. 2 minutes past the hour may prevent a possible clash with  @daily or @weekly.
# Monday ensures it.
report_timing = '2 * * * 1'

#[...]

#[sqlbackup] # This section heading is all lower case to enable skin duplication.
[sqlbackupweek] # This section heading is all lower case to enable skin duplication.

#sql_user = "your_user_if_different_to_weewx.conf"
```

That's it. You should be good to go. Tread lightly. 
