#
#    Copyright (c) 2017 Glenn McKechnie glenn.mckechnie@gmail.com>
#    Credit to Tom Keffer <tkeffer@gmail.com> and the core weewx team.
#
#
#    See the file LICENSE.txt for your full rights.
#
#

import os
import errno
import sys
import shutil
import gzip
import subprocess
import syslog
import time
from datetime import datetime
# https://stackoverflow.com/questions/3600948/python-subprocess-mysqldump-and-pipes

import weewx.engine
import weewx.manager
import weewx.units
from weewx.cheetahgenerator import SearchList
from weeutil.weeutil import to_bool


class MYSQLBackup(SearchList):
    """ Notes and WARNINGS

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
    eg:  weatherpi-host.masterofpis-201706132105-24hours.gz

    Those intervals are handled easily on my setup and do not interrupt the report
    generation in weewx. YMWV

 Jun 13 21:05:42 masterofpis wee_reports[26062]: sqlbackup: Created backup in 0.31 seconds

    You'll need to adjust the values to suit you. Set sql_debug = "2" in the skin.conf
    while you do so. 
    This script currently performs no error checking so check the resulting files for
    integrity.
    disk ful, will return silence!
    empty database, will return silence!

    Reasons for doing it this way (instead of seperate scripts and cron) are that it
    should integrate easily with the weewx proces. This report runs after database
    writes have been done (providing you don't ask too much of it), and keeping it
    under the weewx umbrella fits the "one stop shop" model.
    Keep it small and sensible and that should all remain true.

    Testing: Backup your mysql database first - via other methods.
    Modify your variables, and turn on debug in the skin.conf file
    Then copy and modify a minimal weewx.conf file as weewx.wee.conf and invoke it by using.

    wee_reports /etc/weewx/weewx.wee.conf && tail -n20 /var/log/syslog | grep wee_report
    """

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        """
        report_timing: See the weewx documentation for the full description on
        this addition. There are many options eg:-
        @daily, @weekly, @monthly, etc
        """
        # essentials specific to weewx, should be able to get some of them directly from weewx.conf?
        self.user = self.generator.skin_dict['MYSQLBackup']['mysql_user']
        self.host = self.generator.skin_dict['MYSQLBackup']['mysql_host']
        self.passwd = self.generator.skin_dict['MYSQLBackup']['mysql_pass']
        self.dbase = self.generator.skin_dict['MYSQLBackup']['mysql_database']
        self.table = self.generator.skin_dict['MYSQLBackup'].get('mysql_table',"")
        self.bup_dir = self.generator.skin_dict['MYSQLBackup']['mysql_bup_dir']
        self.dated_dir = to_bool(self.generator.skin_dict['MYSQLBackup'].get('mysql_dated_dir', True))
        # these need to match, let the user do it for now
        self.tp_eriod = self.generator.skin_dict['MYSQLBackup']['mysql_tp_eriod']
        self.tp_label = self.generator.skin_dict['MYSQLBackup']['mysql_tp_label']
        self.gen_report = to_bool(self.generator.skin_dict['MYSQLBackup'].get('mysql_gen_report', True))
        self.html_root = self.generator.skin_dict['MYSQLBackup']['html_root']
        # local debug switch
        self.sql_debug = int(self.generator.skin_dict['MYSQLBackup']['sql_debug'])

        t1 = time.time() # this process's start time

        # Because we use the  "--where..." clause, we run into trouble when dumping all tables so we use "--ignore..."
        # to prevent an incomplete dump - because there is no dateTime in the metadata table.
        if len(self.table) < 1:
            self.ignore = "--ignore-table=%s.archive_day__metadata" % self.dbase
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: ALL tables specified, including option %s" % self.ignore)
        else:
            self.ignore = ""

        #https://stackoverflow.com/questions/4271740/how-can-i-use-python-to-get-the-system-hostname
        this_host = os.uname()[1]
        file_stamp = time.strftime("%Y%m%d%H%M")

        past_time = int(time.time()) - int(self.tp_eriod)  # then for the dump process
        #https://stackoverflow.com/questions/3682748/converting-unix-timestamp-string-to-readable-date-in-python
        readable_time = (datetime.fromtimestamp(past_time).strftime('%Y-%m-%d %H:%M:%S'))
        if weewx.debug >= 2 or self.sql_debug >= 2:
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: mysqldump is starting from %s" % readable_time)
        # If true, create the remote directory with a date structure
        # eg: <path to backup directory>/2017/02/12/var/lib/weewx...
        if self.dated_dir:
            date_dir_str = time.strftime("/%Y%m%d")
        else:
            date_dir_str = ''
        dump_dir = self.bup_dir + "%s" % (date_dir_str)

        # https://stackoverflow.com/questions/273192/how-can-i-create-a-directory-if-it-does-not-exist
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir)
        if weewx.debug >= 2 or self.sql_debug >= 2:
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: directory used to store mysqldump file - %s" % dump_dir)

        dump_file = dump_dir + "/%s-host.%s-%s-%s.gz"  % (self.dbase, this_host, file_stamp, self.tp_label)
       # cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
        cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
            self.user, self.passwd, self.host, self.dbase, self.table, past_time, self.ignore)

        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        dump_output = p1.communicate()[0]
        with gzip.open(dump_file, 'wb') as f:
            f.write(dump_output)
        f.close()

        if weewx.debug >= 2 or self.sql_debug >= 2:
            self.passwd = "XxXxX"
          #  cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
            cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
                self.user, self.passwd, self.host, self.dbase, self.table, past_time, self.ignore)
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: command used was %s" % (cmd))

        if self.gen_report:
            # Output for a report using templates
            # ugly html generation,
            t3= time.time()
            tmp_inc_dir = "/tmp/inc"
            stamp_file = "%s/timestamp.inc" % tmp_inc_dir
            head_file = "%s/head.inc" % tmp_inc_dir
            tail_file = "%s/tail.inc" % tmp_inc_dir
            df_file = "%s/df.inc" % tmp_inc_dir
            free_file = "%s/free.inc" % tmp_inc_dir
            mount_file = "%s/mount.inc" % tmp_inc_dir
            inc_file = "%s/dump.inc" % tmp_inc_dir

            # avoid potential confusion, remove old
            if os.path.exists(tmp_inc_dir):
                shutil.rmtree(tmp_inc_dir)
            os.makedirs(tmp_inc_dir)
            gen_time = time.strftime("%A %B %d, %Y at %H:%M")
            os.system("echo %s > %s " % (gen_time, stamp_file))
            os.system("echo '</b>, starting its capture from <b>%s.\n' >> %s " % (readable_time, stamp_file))
            #os.system("echo '<br>%s\n' >> %s " % (cmd, stamp_file))
            # broken pipe error is due to head truncating the operation?
            os.system("echo %s > %s " % (cmd, head_file))
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: report command used was %s into %s" % (cmd, head_file))
            my_head = "zcat  %s | head -n100 >> %s" % (dump_file, head_file)
            os.system(my_head)
            my_tail = "zcat %s | tail -n20 > %s" % (dump_file, tail_file)
            os.system(my_tail)
            os.system("df -h > %s" % df_file)
            os.system("free -h > %s" % free_file)
            os.system("mount > %s" % mount_file)
            if weewx.debug >= 2 or self.sql_debug >= 2 :
                t4= time.time() 
                syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: Created %s in %.2f secs" % (inc_file, t4-t3))


        # and then the whole process's finishing time
        t2= time.time()
        if weewx.debug >= 2 or self.sql_debug >= 2 :
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup:DEBUG: Created %s backup in %.2f seconds" % (dump_file, t2-t1))
        else:
            syslog.syslog(syslog.LOG_INFO, "mysqlbackup: Created backup in %.2f seconds" % (t2-t1))

# date -d "11-june-2017 21:00:00" +'%s'
# 1497178800

if __name__ == '__main__':

    # None of this works ! :-)
    # use wee_reports instead.
    sqlbackup()
