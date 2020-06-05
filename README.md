## SQLBackup README

**Update Jun 2020**

Works with weewx4, python 2.7 or python 3.x

This skin (sqlbackup) uses a Search List Extension (SLE) of the same name to call mysqldump and/or sqlite3 to dump data from the weeWX database.
If it's MySQL (MariaDB) then it will dump a user specified timeframe; if it's sqlite then it will dump all of it. The default option in both cases is to only dump the archive tables.
It will do this at regular intervals as specified by the [report_timing](http://www.weewx.com/docs/customizing.htm#customizing_gen_time) feature of weeWX.

If you dump the whole database, and it's large, you can interfere with weeWXs operation and odd things may start to happen. This will depend on your CPU, database size, weeWX setup, maybe even the weather!
In most cases this probably won't matter too much and you'll just get a message about skipping reports. If we lock weeWX out of its database for too long though, the weird and wonderful may start to occur, so it's best we don't push it too far.

This skin was originally configured for MySQL (MariaDB) databases only and we can configure mysqldump to do a partial dump. We can therefore limit ourselves to a small, very manageable portion of the database.
Because this has since expanded to incorporate sqlite databases, where it captures the whole database, it may be slower and more prone to interfering with weeWX. But compared to MySQL, sqlite is not as demanding so it may still be fit for duty.
Because we are getting a full backup of the sqlite database on each run, we can perhaps do them less frequently and here the report_timing feature really comes into its own.
Sqlite databases can also be backed up by simply copying them, if you want a similar 'skinned' approach that does just that then have a look at [Using the RSYNC skin as a backup solution.](https://github.com/weewx/weewx/wiki/Using-the-RSYNC-skin-as-a-backup-solution)
Both these methods aim to create a backup during a quiet window of time (when there are no database writes) that's available within the weeWX cycle.

With the variation in weeWX setups, the only way to know how it will work for you is to give it a try. Just start off gently and DON'T ask for too much at once, be conservative with what you're asking for.


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

   * Select a suitable archive period and name (sql_period and sql_label.)

   * Check that the defaults are correct for your setup.

   * In particular, check the backup directory (xxsql_bup_dir) paths. They will be created on the first run.

   * The default is to generate reports - sqlbackup/index.html.

   * The templates take their style from the newskin branch of weeWX - Seasons

3 restart weewx:

**sudo /etc/init.d/weewx stop**

**sudo /etc/init.d/weewx start**

The html template makes heavy use of #include files to generate the report page. These files are located in /tmp/sqlbackup and will remain after each run (if you need to inspect them or see what's happening). They will be blanked, deleted, re-generated on each run of the skin. ie: they are all renewed and should reflect each runs output. There are no stale files, they are unique to each run - thus their placement in the /tmp directory.

See the [sqlbackup wiki](https://github.com/glennmckechnie/weewx-sqlbackup/wiki) for further information. Or for a local copy (after installation) see sqlbackup/sqlbackupREADME.html
