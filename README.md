## SQLBackup README

**Update Jul 2022**: Minor documentation only

Works with weewx4, python 2.7 or python 3.x

This skin (sqlbackup) uses a Search List Extension (SLE) of the same name to call mysqldump and/or sqlite3 to dump data from the weeWX database.
It will dump a user specified timeframe with the default being a daily dump (performed around midnight). In both cases the default is to only dump the archive tables.
It will do all this at regular intervals as specified by the [report_timing](http://www.weewx.com/docs/customizing.htm#customizing_gen_time) feature of weeWX.

This skin was originally configured for partial dumps of the MySQL (MariaDB) databases. It has since been expanded to incorporate partial dumps of the sqlite databases as well.  We thus limit ourselves to a small, very manageable portion of the database (daily, around midnight) and allow weeWX to do its main function - recording our precious data.

If that default configuration is altered to perform a longer period, in particular a full backup then it may interfere with weeWX, usually just the Report generation cycle. However compared to MySQL, sqlite is not as demanding, so it may still be fit for duty when performing a much longer, or full database backup.

In most cases a full dump probably won't matter too much and you'll just get a message about Report generation being skipped. However, if we lock weeWX out of its database for too long though, then the weird and wonderful may start to occur. Experimenting will define your limits.

Sqlite databases can also be backed up by simply copying them, if you want a similar 'skinned' approach that does just that then have a look at [Using the RSYNC skin as a backup solution.](https://github.com/weewx/weewx/wiki/Using-the-RSYNC-skin-as-a-backup-solution)
Both these methods aim to create a backup during a quiet window of time (when there are no database writes) that's available within the weeWX cycle.

With the variation in weeWX setups, the only way to know how it will work for you is to give it a try. Just start off gently and DON'T ask for too much at once, be conservative with what you're asking for.

A fresh install should work without any configuration. After midnight the */var/backups* directory should include one of two new directories, *mysql* and/or *sql* depending on which is your default database. That's where your backups will be.


### Installation

This SLE's prerequisites are

    * sqlite3 (Which I don't think is installed by default?)
    * mysqldump (Which I believe is part of the default mysql install)

Everything else should be there already as they are listed under Debian as [essential] packages, except 'free' but I believe that's also included on a default install.

#### Otherwise...

1 Run the installer:

**wee_extension --install weewx-sqlbackup-master.zip**

2 Edit the skin.conf file to suit your installation

   * Select a suitable *report_timing* stanza

   * [Optional] Select a suitable archive period and name (sql_period and sql_label.)

   * Check that the remaining defaults are correct for your setup.

   * In particular, check the backup directory (xxsql_bup_dir) paths. They will be created on the first run.

   * The default is to generate reports - sqlbackup/index.html.

   * The templates take their style from the Seasons skin.

3 restart weewx:

**sudo /etc/init.d/weewx stop**

**sudo /etc/init.d/weewx start**

The html template makes heavy use of #include files to generate the report page. These files are located in /tmp/sqlbackup and will remain after each run (if you need to inspect them or see what's happening). They will be blanked, deleted, re-generated on each run of the skin. ie: they are all renewed and should reflect each runs output. There are no stale files, they are unique to each run - thus their placement in the /tmp directory.

See the [sqlbackup wiki](https://github.com/glennmckechnie/weewx-sqlbackup/wiki) for further information. Or for a local copy (after installation) see sqlbackup/sqlbackupREADME.html
