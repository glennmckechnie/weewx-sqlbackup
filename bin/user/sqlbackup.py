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


class SqlBackup(SearchList):
    """ Notes and WARNINGS

    DON'T back the whole database up with this skin. You'll overload weewx and weird
    things will happen.

    The idea is to instead select a small rolling window from the database, and dump
    this at each report_timing interval. We will use that as a partial backup.
    At restore time we'll then need to select some or all, and stitch them together as
    appropriate.

    This skin was created to backup a mysql database that runs purely in memory, it has
    since evolved to include sqlite databases as well.
    And because that's a little! fragile, the script runs every hour, and dumps the last
    24 hours of the database to the sql_bup_file in the format...
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

    Testing: Backup your database first - via other methods.
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
        self.user = self.generator.skin_dict['SqlBackup'].get('sql_user','weewx')
        self.host = self.generator.skin_dict['SqlBackup'].get('sql_host','localhost')
        self.passwd = self.generator.skin_dict['SqlBackup'].get('sql_pass','weewx')
        self.myd_base = self.generator.skin_dict['SqlBackup'].get('mysql_database','')
        self.d_base = self.generator.skin_dict['SqlBackup'].get('sql_database','')
        self.table = self.generator.skin_dict['SqlBackup'].get('sql_table','')
        self.mybup_dir = self.generator.skin_dict['SqlBackup'].get('mysql_bup_dir','/var/backups/mysql')
        self.bup_dir = self.generator.skin_dict['SqlBackup'].get('sql_bup_dir','/var/backups/sql')
        self.tp_eriod = self.generator.skin_dict['SqlBackup'].get('sql_tp_eriod','86400')
        self.tp_label = self.generator.skin_dict['SqlBackup'].get('sql_tp_label','daily')
        self.html_root = self.generator.skin_dict['SqlBackup'].get('html_root','/var/www/html/weewx')
        self.dated_dir = to_bool(self.generator.skin_dict['SqlBackup'].get('sql_dated_dir', True))
        self.gen_report = to_bool(self.generator.skin_dict['SqlBackup'].get('sql_gen_report', True))
        self.inc_dir = self.generator.skin_dict['SqlBackup'].get('inc_dir', '/tmp/sqlbackup')
        # local debug switch
        self.sql_debug = int(self.generator.skin_dict['SqlBackup'].get('sql_debug','0'))

        carry_index = '<hr><b>Databases :: </b>'

        t1 = time.time() # this process's start time

        # Sigh, we need these files to exist, with some content or Cheetah complains
        # Doing this, now rather than at the finish to allow file inspection
        # so, empty them all 
        if os.path.exists(self.inc_dir):
            shutil.rmtree(self.inc_dir)

        # and re-create \n empties
        if not os.path.exists(self.inc_dir):
            os.makedirs(self.inc_dir)

        all_file = "%s/alldumps.inc" % (self.inc_dir)
        empty = open(all_file, 'w')
        empty.write("\n")
        empty.close()
        head_file = "%s/head.inc" % (self.inc_dir)
        empty = open(head_file, 'w')
        empty.write("\n")
        empty.close()
        tail_file = "%s/tail.inc" % (self.inc_dir)
        empty = open(tail_file, 'w')
        empty.write("\n")
        empty.close()
       # sys.exit()
        # Because we use the  "--where..." clause, we run into trouble when dumping all tables so we use "--ignore..."
        # to prevent an incomplete dump - because there is no dateTime in the metadata table.
        if len(self.table) < 1:
            self.ignore = "--ignore-table=%s.archive_day__metadata" % self.dbase
            syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: ALL tables specified, including option %s" % self.ignore)
        else:
            self.ignore = ""

        #https://stackoverflow.com/questions/4271740/how-can-i-use-python-to-get-the-system-hostname
        this_host = os.uname()[1]
        file_stamp = time.strftime("%Y%m%d%H%M")

        # add 900 seconds to ensure data ovelaps between runs.
        self.tp_eriod = int(self.tp_eriod) + int('900')
        past_time = int(time.time()) - int(self.tp_eriod)  # then for the dump process
        #https://stackoverflow.com/questions/3682748/converting-unix-timestamp-string-to-readable-date-in-python
        readable_time = (datetime.fromtimestamp(past_time).strftime('%Y-%m-%d %H:%M:%S'))
        if weewx.debug >= 2 or self.sql_debug >= 2:
            syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: starting from %s" % readable_time)
        # If true, create the remote directory with a date structure
        # eg: <path to backup directory>/2017/02/12/var/lib/weewx...
        if self.dated_dir:
            date_dir_str = time.strftime("/%Y%m%d")
        else:
            date_dir_str = ''
        mydump_dir = self.mybup_dir + "%s" % (date_dir_str)
        dump_dir = self.bup_dir + "%s" % (date_dir_str)

        # https://stackoverflow.com/questions/273192/how-can-i-create-a-directory-if-it-does-not-exist
        if not os.path.exists(mydump_dir):
            os.makedirs(mydump_dir)
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir)
        if weewx.debug >= 2 or self.sql_debug >= 2:
            syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: directory for mysql files - %s, sqlite files %s" % (mydump_dir,dump_dir))

        if self.myd_base:
            self.mydbase = self.myd_base.split()
            mydbase_len = len(self.mydbase)
            if weewx.debug >= 2 or self.sql_debug >= 2 :
                syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: databases, mysql %s named %s" % (mydbase_len, self.mydbase))
            for step in range(mydbase_len):
                myd_base = self.mydbase[step]
                t5 = time.time() # this loops start time
                if self.sql_debug >= 2:
                    syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG:  mysql database is %s" % myd_base)

                mydump_file = mydump_dir + "/%s-host.%s-%s-%s.gz"  % (myd_base, this_host, file_stamp, self.tp_label)
                #cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
                cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
                      self.user, self.passwd, self.host, myd_base, self.table, past_time, self.ignore)

                p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                dump_output = p1.communicate()[0]
                with gzip.open(mydump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t6 = time.time() # this loops finishing  time

                passwd = "XxXxX"
                #cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
                cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
                    passwd, passwd, self.host, myd_base, self.table, past_time, self.ignore)
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: %.2f secs to run %s" % ((t6-t5), cmd))

                if self.gen_report:
                    line_count = "100"
                    sql_name = "mysql"
                    self.report(self.inc_dir, carry_index, readable_time, cmd, mydump_file, myd_base, line_count, sql_name)
                    carry_index = link_index

        if self.d_base:
            self.dbase = self.d_base.split()
            dbase_len = len(self.dbase)
            if self.sql_debug >= 2:
                syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: databases, sqlite %s named %s" % (dbase_len, self.dbase))
            for step in range(dbase_len):
                d_base = self.dbase[step]
                t7 = time.time() # this loops start time
                if self.sql_debug >= 2:
                    syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG:  sql database is %s" % d_base)
                dump_file = dump_dir + "/%s-host.%s-%s-%s.gz"  % (d_base, this_host, file_stamp, self.tp_label)
                cmd = "echo .dump | sqlite3 /var/lib/weewx/%s.sdb" %(d_base)

                p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                dump_output = p1.communicate()[0]
                with gzip.open(dump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t8 = time.time() # this loops start time

                if weewx.debug >= 2 or self.sql_debug >= 2:
                    syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: %.2f secs to run %s" % ((t8-t7), cmd))

                if self.gen_report:
                    line_count = "20"
                    sql_name = "sql"
                    self.report(self.inc_dir, carry_index, readable_time, cmd, dump_file, d_base, line_count, sql_name)

                    carry_index = link_index
        # and then the whole process's finishing time
        t2= time.time()
        syslog.syslog(syslog.LOG_INFO, "sqlbackup: Total time used in backups and report output: %.2f seconds" % (t2-t1))

# date -d "11-june-2017 21:00:00" +'%s'
# 1497178800


    def report(self, inc_dir, carry_index, readable_time, cmd, dump_file, data_base, line_count, sql_name):
            # Output for a report using templates
            # ugly html generation,
            global link_index
            t3= time.time()
            inc_file = "%s/%s.inc" % (inc_dir, data_base)
            links_file = "%s/links.inc" % inc_dir
            all_file = "%s/alldumps.inc" % inc_dir
            head_file = "%s/head.inc" % inc_dir
            tail_file = "%s/tail.inc" % inc_dir
            #stamp_file = "%s/timestamp.inc" % inc_dir

            next_index = ('%s.<a href="#%s">%s</a>&nbsp;&nbsp;' % (sql_name, data_base, data_base))
            link_index = carry_index + next_index


            if not os.path.exists(inc_dir):
                os.makedirs(inc_dir)
            gen_time = time.strftime("%A %B %d, %Y at %H:%M")

            #os.system("echo %s > %s " % (gen_time, stamp_file))
            #os.system("echo '</b></br>It started the capture from <b>%s.\n' >> %s " % (readable_time, stamp_file))

            head = open(head_file, 'w')
            #head.write("This page shows a summary of the output from the"
            #            "sqlbackup that last ran on <b> %s </b><br>\nIt "
            #            "started the capture from <b>%s</b>\n" % (
            #            gen_time, readable_time))
            head.write("<b> %s </b><br>\nIt started the capture from <b>%s</b>\n" % (
                        gen_time, readable_time))
            head.close()

            inc = open(inc_file, 'w')
            inc.write('&nbsp;&nbsp;&nbsp;&nbsp;<a id="%s"></a><a href='
                      '"#Top">Back to top</a>\n<h2>Extract from the %s '
                      'Database dump file: </h2>\n<pre>%s\n\n\n' % (
                      data_base, data_base, cmd))
            # broken pipe error from wee_reports appears harmless & is due to head truncating the operation.
            inc.close()
            my_head = "zcat  %s | head -n%s >> %s" % (dump_file, line_count, inc_file)
            os.system(my_head)
            inc = open(inc_file, 'a')
            inc.write("\n[...]\n")
            inc.close()
            my_tail = "zcat %s | tail -n20 >> %s" % (dump_file, inc_file)
            os.system(my_tail)

            l_inks=open(links_file, 'w')
            sys_index =('<br>&nbsp;&nbsp;&nbsp;<b>System ::</b>&nbsp;&nbsp;'
                        '&nbsp;&nbsp;<a href="#disk">disks</a>&nbsp;-&nbsp;'
                        '<a href="#memory">memory</a>&nbsp;-&nbsp;<a href='
                        '"#mounts">mounts</a>&nbsp;&nbsp;<br>')
            h_tml =[link_index, sys_index, "<hr>"]
            l_inks.writelines(h_tml)
            l_inks.close()

            os.system("cat %s >> %s" % (inc_file, all_file))
            all_lot = open(all_file, 'a')
            all_lot.write("</pre>")
            all_lot.close()

            tail = open(tail_file, 'w')
            tail.write('\n<a id="disk"></a><a href="#Top">Back to top</a><h2>'
                       ' Disk Usage: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n<pre>')
            tail.close()
            tail = open(tail_file, 'a')
            os.system("df -h >> %s" % tail_file)
            tail.write('</pre><hr>\n<a id="memory"></a><a href="#Top">Back to top'
                        '</a><h2> Memory Usage: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n<pre>')
            tail.close()
            os.system("free -h >> %s" % tail_file)
            tail = open(tail_file, 'a')
            tail.write('</pre><hr>\n<a id="mounts"></a><a href="#Top">Back to top'
                       '</a><h2> Mounted File Systems: </h2>&nbsp;&nbsp;&nbsp;'
                       '&nbsp;\n<pre>')
            tail.close()
            os.system("mount >> %s" % tail_file)
            tail = open(tail_file, 'a')
            tail.write("</pre>")
            tail.close()

            if weewx.debug >= 2 or self.sql_debug >= 2 :
                t4= time.time() 
                syslog.syslog(syslog.LOG_INFO, "sqlbackup:DEBUG: Created %s in %.2f secs" % (
                    inc_file, t4-t3))

            return link_index



if __name__ == '__main__':

    # None of this works ! :-)
    # use wee_reports instead.
    pass
