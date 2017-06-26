#
#    Copyright (c) 2017 Glenn McKechnie glenn.mckechnie@gmail.com>
#    Credit to Tom Keffer <tkeffer@gmail.com>, Matthew Wall and the core
#    weewx team, all from whom I've borrowed heavily.
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

import weewx.engine
import weewx.manager
import weewx.units
from weewx.wxengine import StdService
from weewx.cheetahgenerator import SearchList
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'sqlbackup : %s' % msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def tlwrite(txt):
    tl = open(self.tail_file, 'w')
    tl.write(txt)
    tl.close()

class SqlBackup(SearchList):
    """ Notes and WARNINGS

    DON'T back the whole database up with this skin. You'll overload weewx and
    weird things could happen. Report generation may be skipped.

    The idea is to instead select a small rolling window from the database (if
    its a MySQL or MariaDB) and dump this at each report_timing interval. We
    will use that as a partial backup.
    At restore time we'll then need to select some or all of the dump files, and
    stitch them together as appropriate.

    If it's an sqlite dtabase, it will dump it (them) all.

    This skin was created to backup a mysql database that runs purely in memory,
    it has since evolved to include sqlite databases as well.
    Because running a database is a little! fragile (to say the least.) I 
    configured my script to run every hour, and dumps the last 24 hours of the
    database to the  xxsql_bup_file in the format...
         {database}-host.{hostname}-{epoch-timestamp}-{window-time-period}.gz
    eg:  weatherpi-host.masterofpis-201706132105-24hours.gz

    Those intervals are handled easily on my setup and do not interrupt the
    report generation in weewx. Your processor, memory, database, archive
    interval will be different to mine... YMWV

    Jun 13 21:05:42 masterofpis wee_reports[26062]: sqlbackup: Created backup in 0.31 seconds
    
    You'll need to adjust the values to suit you. Setting sql_debug = "2" in the
    skin.conf will inform you while you make changes, look at the logs.
    Or, if you set sql_debug = "4" it will be included at the foot of the 
    sqlbackup.html page.

    This script currently performs no error checking so check the resulting 
    files for integrity.
    disk full, it will return silence!
    empty database, it will also return silence!

    Reasons for doing it this way (instead of seperate scripts and cron) are 
    that it should integrate easily with the weewx proces. This report runs
    after database writes have been done (providing you don't ask too much of
    it), and keeping it under the weewx umbrella fits the "one stop shop" model.
    If we don't interfere too much we should slip under the radar.
    Keep it small and sensible and that should all remain true.

    Testing: BACK UP your database first - via other methods. (Okay, Truth is.
    I've used this script by passing a suitable unix time string as the sql_tperiod
    and have lived to tell the tale. I was able to put the pieces together
    again.)
    60*60*24*365*2
    sql_tperiod = "63072000"
    
    In short...
    Open skin.conf, modify the variables, turn on sql_debug - 2

    To help speed up the process, bypass the report_timing setting and cycle
    through the setup process quickly by copying and modifying a minimal 
    weewx.conf file as weewx.wee.conf and invoke that by using.
    One hiccup with the wee_reports method is that it may return longer times if
    it encounters a locked database. The ultimate test is when it's run under
    weewx's control, wee_reports is still very useful to fine tune your setup

    wee_reports /etc/weewx/weewx.wee.conf && tail -n20 /var/log/syslog | grep wee_report

    then watch your logs, or the sqlbackup.html page if you're generating the
    report.

    # only because I can never remember
    # date -d "11-june-2017 21:00:00" +'%s'
    # 1497178800
    #
    # date +"%s"
    # returns  current epoch time
    """

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        """
        The following options are exclusive to the skin.conf file.
        That allows them to be changed on the fly - while weewx is running, so
        changing these values, in the skin.conf file will affect the next
        report run. This makes it very easy to manipulate - databases, timings
        etc.

        report_timing: See the weewx documentation for the full description on
        this addition. There are many options eg:- '5 1 * * *' ,  @daily,
        @weekly, @monthly, etc

        self.sql_debug: use to include additional info in logs, or optional html
         report. default is off, although the newly installed skin comes with it
         turned on.
         0 is off,
         2 is logging only (setting debug = 2 in weewx.conf will also work)
         4 includes it in the optional html report.

        mysql, mariadb are interchangable. where mysql is mentioned, mariadb
        also applies

        self.user: mysql user; defaults to weewx.conf value. Can be overwritten
         via skin.conf
        self.passwd: mysql password; defaults to weewx.conf value. Can be
        overwritten via skin.conf
        self.host: mysql database location; defaults to weewx.conf value. Can be
         overwritten via skin.conf.
        self.myd_base: mysql database name; defaults to 'None'. Can be
         overwritten via skin.con. Use skin.conf for multiple databases, space
         seperated list.
        self.d_base: sqlite database name; defaults to'None'. Can be overwritten
         via skin.con. Use skin.conf for multiple databases, space seperated
         list.
        self.table: mysql table to archive; defaults to 'None' which means 'all'
        self.mybup_dir: mysql backup directory; defaults to '/var/backups/mysql'
        self.bup_dir: sqlite backup directory; defaults to '/var/backups/sql'
        self.tp_eriod: mysql; time period for dump; defaults to 86400
         seconds (24hours)
        self.tp_label: mysql; text label to match above. This has meaning
         to you.
        self.html_root: location to store the generated html files. It's taken
        from weewx.conf but can be overwritten via a skin.conf value.
        self.dated_dir: optional string to append to self.xxx_dir. eg: 20171231
         default is true.
        self.gen_report: optional html report, helps with quick status check. Its
         location is governed by HTML_ROOT in weewx.conf or html_root in 
         skin.conf
        self.inc_dir: location of .inc files used in html generation; defaults
         to /tmp/sqlbackup. These are temporary files only , but are needed for
         the cheetah templates (see Seasons skin in newskin branch or latest
         release)
        """

        t1 = time.time() # this process's start time

        # local debug switch "2"==weewx.debug, "4" adds extra to html report page
        # 5 is bordering on extreme (release testing)
        self.sql_debug = int(self.generator.skin_dict['SqlBackup'].get('sql_debug','0'))

        self.user = self.generator.skin_dict['SqlBackup'].get('sql_user')
        if not self.user:
            self.user = self.generator.config_dict['DatabaseTypes']['MySQL'].get('user')
            if self.sql_debug >= 5 :
                #loginf("5: weewx.conf user is  %s" % (self.user))
                loginf("5: weewx.conf user was used")
        self.passwd = self.generator.skin_dict['SqlBackup'].get('sql_pass')
        if not self.passwd:
            self.passwd = self.generator.config_dict['DatabaseTypes']['MySQL'].get('password')
            if self.sql_debug >= 5 :
                #loginf("5: weewx.conf passwd is  %s" % (self.passwd))
                loginf("5: weewx.conf passwd was used")
        self.host = self.generator.skin_dict['SqlBackup'].get('sql_host')
        if not self.host:
            self.host = self.generator.config_dict['DatabaseTypes']['MySQL'].get('host')
            if self.sql_debug >= 5 :
                loginf("5: weewx.conf host is  %s" % (self.host))
        self.myd_base = self.generator.skin_dict['SqlBackup'].get('mysql_database','')
        self.d_base = self.generator.skin_dict['SqlBackup'].get('sql_database','')
        if not self.myd_base and not self.d_base:
            defd_base = self.generator.config_dict['DataBindings']['wx_binding'].get('database')
            if self.sql_debug >= 5 :
                loginf("5: weewx.conf database is %s" % (defd_base))
            if defd_base == 'archive_mysql':
                self.myd_base = self.generator.config_dict['Databases'][defd_base].get('database_name')
                if self.sql_debug >= 5 :
                    loginf("5: so weewx.conf mysql database is %s" % (self.myd_base))
            elif defd_base == 'archive_sqlite':
                self.d_base = self.generator.config_dict['Databases'][defd_base].get('database_name')
                if self.sql_debug >= 5 :
                    loginf("5: so weewx.conf sqlite database is %s" % (self.d_base))
            else:
                pass
        self.table = self.generator.skin_dict['SqlBackup'].get('sql_table','')
        self.mybup_dir = self.generator.skin_dict['SqlBackup'].get('mysql_bup_dir','/var/backups/mysql')
        self.bup_dir = self.generator.skin_dict['SqlBackup'].get('sql_bup_dir','/var/backups/sql')
        self.tp_eriod = self.generator.skin_dict['SqlBackup'].get('sql_tperiod','86400')
        self.tp_label = self.generator.skin_dict['SqlBackup'].get('sql_tlabel','daily')
        self.html_root = self.generator.skin_dict['SqlBackup'].get('htmlroot','')
        if not self.html_root:
            self.html_root = self.generator.config_dict['StdReport'].get('HTML_ROOT')
            if self.sql_debug >= 5 :
                loginf("5: weewx.conf html_root is  %s" % (self.html_root))
        self.dated_dir = to_bool(self.generator.skin_dict['SqlBackup'].get('sql_dated_dir', True))
        self.gen_report = to_bool(self.generator.skin_dict['SqlBackup'].get('sql_gen_report', True))
        self.inc_dir = self.generator.skin_dict['SqlBackup'].get('inc_dir', '/tmp/sqlbackup')

        if self.sql_debug >= 5 :
            loginf("5: using sql_debug level of %s" %self.sql_debug)
            loginf("5: generate report is %s" %self.gen_report)
            loginf("5: mysql databases selected: %s" %self.myd_base)
            loginf("5: sql databases selected: %s" %self.d_base)

        carry_index = '<hr><b>Databases :: </b>'
        start_loop = 0

        # Do the housework first, we clean out all the *.inc 's now rather
        # than later. That allows their content to be inspected between runs.
        if os.path.exists(self.inc_dir):
            shutil.rmtree(self.inc_dir)
        if not os.path.exists(self.inc_dir):
            os.makedirs(self.inc_dir)

        self.all_file = "%s/alldumps.inc" % (self.inc_dir)
        self.head_file = "%s/head.inc" % (self.inc_dir)
        self.tail_file = "%s/tail.inc" % (self.inc_dir)
        self.links_file = "%s/links.inc" % self.inc_dir
        self.sys_file = "%s/syslinks.inc" % self.inc_dir

        chck = open(self.all_file, 'a')
        chck.write("<p><b>There's nothing to report.</b></p><p>Do you have any "
            "databases configured?</br> Check the config file (skin.conf)</p>")
        chck.close()
        strt = open(self.links_file, 'w')
        strt.write(carry_index)
        strt.close()

       # sys.exit()
        # Because we use the  "--where..." clause, we run into trouble when
        # dumping all tables so we use "--ignore..."  to prevent an incomplete
        #dump - because there is no dateTime in the metadata table.
        if len(self.table) < 1:
            self.ignore = "--ignore-table=%s.archive_day__metadata" % self.dbase
            loginf("DEBUG: ALL tables specified,including option %s" % self.ignore)
        else:
            self.ignore = ""

        this_host = os.uname()[1]
        file_stamp = time.strftime("%Y%m%d%H%M")

        # add 900 seconds to ensure data ovelaps between runs.
        self.tp_eriod = int(self.tp_eriod) + int('900')
        # then for the dump process
        past_time = int(time.time()) - int(self.tp_eriod)

        readable_time = (datetime.fromtimestamp(past_time).strftime(
            '%Y-%m-%d %H:%M:%S'))
        if weewx.debug >= 2 or self.sql_debug >= 2:
            loginf("DEBUG: starting from %s" % readable_time)
        # If true, create the remote directory with a date structure
        # eg: <path to backup directory>/2017/02/12/var/lib/weewx...
        if self.dated_dir:
            date_dir_str = time.strftime("/%Y%m%d")
        else:
            date_dir_str = ''
        mydump_dir = self.mybup_dir + "%s" % (date_dir_str)
        dump_dir = self.bup_dir + "%s" % (date_dir_str)

        if not os.path.exists(mydump_dir):
            os.makedirs(mydump_dir)
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir)
        if weewx.debug >= 2 or self.sql_debug >= 2:
           loginf("DEBUG: directory for backup files - %s, sqlite files %s" % (
               mydump_dir,dump_dir))

        if self.myd_base:
            self.mydbase = self.myd_base.split()
            mydbase_len = len(self.mydbase)
            if weewx.debug >= 2 or self.sql_debug >= 2 :
                loginf("DEBUG: databases, mysql %s named %s" % (mydbase_len,
                self.mydbase))
            for step in range(mydbase_len):
                myd_base = self.mydbase[step]
                t5 = time.time() # this loops start time
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("DEBUG:  mysql database is %s" % myd_base)

                mydump_file = mydump_dir + "/%s-host.%s-%s-%s.gz"  % (
                    myd_base, this_host, file_stamp, self.tp_label)
                #cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
                cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
                       self.user, self.passwd, self.host, myd_base, self.table, past_time, self.ignore)

                p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, shell=True)
                dump_output = p1.communicate()[0]
                with gzip.open(mydump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t6 = time.time() # this loops finishing  time

                userXx = passXx = "XxXxX"
                #passXx = self.passwd
                #userXx = self.user
                #cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
                cmd = "/usr/bin/mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
                    userXx, passXx, self.host, myd_base, self.table, past_time, self.ignore)
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("DEBUG: %.2f secs to run %s" % ((t6-t5), cmd))

                if self.gen_report:
                    line_count = "100"
                    sql_name = "mysql"
                    self.report(self.inc_dir, carry_index, cmd,
                                mydump_file, myd_base, line_count, sql_name, start_loop)
                    carry_index = link_index
                    start_loop = strt_loop

        if self.d_base:
            self.dbase = self.d_base.split()
            dbase_len = len(self.dbase)
            if weewx.debug >= 2 or self.sql_debug >= 2:
                loginf("DEBUG: databases, sqlite %s named %s" % 
                    (dbase_len, self.dbase))
            for step in range(dbase_len):
                d_base = self.dbase[step]
                t7 = time.time() # this loops start time
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("DEBUG:  sql database is %s" % d_base)
                dump_file = dump_dir + "/%s-host.%s-%s-%s.gz"  % (
                               d_base, this_host, file_stamp, self.tp_label)
                cmd = "echo .dump | sqlite3 /var/lib/weewx/%s.sdb" %(d_base)

                p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, shell=True)
                dump_output = p1.communicate()[0]
                with gzip.open(dump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t8 = time.time() # this loops start time

                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("DEBUG: %.2f secs to run %s" % ((t8-t7), cmd))

                if self.gen_report:
                    line_count = "20"
                    sql_name = "sql"
                    self.report(self.inc_dir, carry_index, cmd, 
                                dump_file, d_base, line_count, sql_name, start_loop)
                    carry_index = link_index
                    start_loop = strt_loop

        # complete the remainder of the report .inc's
        # we generate a time stamp regardless
        gen_time = time.strftime("%A %B %d, %Y at %H:%M")
        hd = open(self.head_file, 'w')
        hd.write("<b> %s </b><br>\nIt started the capture from <b>%s</b>\n" % (
                    gen_time, readable_time))
        hd.close()

        if self.gen_report: # and not self.sql_debug == 0:
            sys_links=open(self.sys_file, 'w')
            if self.sql_debug >= 4 :
                sys_index =('<br>&nbsp;&nbsp;&nbsp;<b>System ::</b>'
                            '&nbsp;&nbsp;&nbsp;&nbsp;'
                            '<a href="#disk">disks</a>&nbsp;-&nbsp;'
                            '<a href="#memory">memory</a>&nbsp;-&nbsp;'
                            '<a href="#mounts">mounts</a>&nbsp;&nbsp;'
                            '<b>DEBUG output :: </b>'
                            '<a href="#logs">logs</a>&nbsp;-&nbsp;'
                            '<a href="#mysql">mysql</a>&nbsp;-&nbsp;'
                            '<a href="#sql">sql</a>&nbsp;&nbsp;'
                            '<br>')
            else:
                sys_index =('<br>&nbsp;&nbsp;&nbsp;<b>System ::</b>'
                            '&nbsp;&nbsp;&nbsp;&nbsp;'
                            '<a href="#disk">disks</a>&nbsp;-&nbsp;'
                            '<a href="#memory">memory</a>&nbsp;-&nbsp;'
                            '<a href="#mounts">mounts</a>&nbsp;&nbsp;'
                            '<br>')

            h_tml =[sys_index, "<hr>"]
            sys_links.writelines(h_tml)
            sys_links.close()

            tl = open(self.tail_file, 'w')
            tl.write('\n<a id="disk"></a><a href="#Top">Back to top</a><h2>'
                       ' Disk Usage: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n<pre>')
            tl.close()
            os.system("df -h >> %s" % self.tail_file)
            tl = open(self.tail_file, 'a')
            tl.write('</pre><hr>\n<a id="memory"></a><a href="#Top">Back to top'
                     '</a><h2> Memory Usage: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n<pre>')
            tl.close()
            os.system("free -h >> %s" % self.tail_file)
            tl = open(self.tail_file, 'a')
            tl.write('</pre><hr>\n<a id="mounts"></a><a href="#Top">Back to top'
                       '</a><h2> Mounted File Systems: </h2>&nbsp;&nbsp;&nbsp;'
                       '&nbsp;\n<pre>')
            tl.close()
            os.system("mount >> %s" % self.tail_file)
            tl = open(self.tail_file, 'a')
            tl.write("</pre>")
            tl.close()

            # add debug extras to sqlbackup.html
            if self.sql_debug >= 4 :
                tl = open(self.tail_file, 'a')
                tl.write('<hr>\n<h2> DEBUG output</h2>\n'
                           '<a id="logs"></a><a href="#Top">Back to top</a>'
                           '<h2> Log snippet: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                           '<pre>')
                tl.close()
                # sanitize the output. If we get a cheetahgenerator error referencing
                # an #include we risk getting stuck in a loop, in a loop.
                os.system("grep /var/log/syslog -e '#' -v|grep  -e 'sqlbackup'"
                          "| tail -n50 >> %s"% self.tail_file)

                tl = open(self.tail_file, 'a')
                tl.write('</pre><hr>\n<a id="mysql"></a><a href="#Top">'
                         'Back to top</a>'
                         '<h2>MySQL files: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                         '<pre>')
                tl.close()
                os.system("ls -gtr %s | tail -n10 >> %s" % (
                           mydump_dir, self.tail_file))

                tl = open(self.tail_file, 'a')
                tl.write('</pre><hr>'
                         '\n<a id="sql"></a><a href="#Top">Back to top</a>'
                         '<h2>sqlite files: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                         '<pre>')
                tl.close()
                os.system("ls -gtr %s | tail -n10 >> %s" % (dump_dir,self.tail_file))

                tl = open(self.tail_file, 'a')
                tl.write('</pre>\n')
                tl.close()
        else:
            skp = open(self.all_file, 'w')
            skp.write("<p>Report generation is disabled in skin.conf</p>")
            skp.close()
            empty = open(self.tail_file, 'w')
            empty.write("\n")
            empty.close()
            empty = open(self.links_file, 'w')
            empty.write("\n")
            empty.close()
            empty = open(self.sys_file, 'w')
            empty.write("\n")
            empty.close()

        # and then the whole process's finishing time, which will only appear
        # in the system logs
        t2= time.time()
        loginf("Total time used in backups "
                      "and report output: %.2f seconds" % (t2-t1))


    def report(self, inc_dir, carry_index, cmd, dump_file, data_base,
               line_count, sql_name, start_loop):
            # Output for a report using templates
            global link_index
            global strt_loop
            t3= time.time()
            inc_file = "%s/%s.inc" % (inc_dir, data_base)
            self.links_file = "%s/links.inc" % inc_dir
            self.all_file = "%s/alldumps.inc" % inc_dir

            if start_loop <= 0:
                strt_loop = 1
                strt = open(self.all_file, 'w')
                strt.write("\n")
                strt.close()

            next_index = ('%s.<a href="#%s">%s</a>&nbsp;&nbsp;' % (
                          sql_name, data_base, data_base))
            link_index = carry_index + next_index

            if not os.path.exists(inc_dir):
                os.makedirs(inc_dir)

            inc = open(inc_file, 'w')
            inc.write('&nbsp;&nbsp;&nbsp;&nbsp;<a id="%s"></a><a href='
                      '"#Top">Back to top</a>\n<h2>Extract from the %s '
                      'Database dump file: </h2>\n<pre>%s\n\n\n' % (
                      data_base, data_base, cmd))
            # broken pipe error from wee_reports appears harmless & is due to
            # head truncating the operation.
            inc.close()
            my_head = "zcat  %s | head -n%s >> %s" % (
                       dump_file, line_count, inc_file)
            os.system(my_head)
            inc = open(inc_file, 'a')
            inc.write("\n[...]\n\n")
            inc.close()
            my_tail = "zcat %s | tail -n20 >> %s" % (dump_file, inc_file)
            os.system(my_tail)

            l_inks=open(self.links_file, 'w')
            h_tml =[link_index, "</br>"]
            l_inks.writelines(h_tml)
            l_inks.close()

            os.system("cat %s >> %s" % (inc_file, self.all_file))
            all_lot = open(self.all_file, 'a')
            all_lot.write("</pre>")
            all_lot.close()

            if weewx.debug >= 2 or self.sql_debug >= 2 :
                t4= time.time() 
                loginf("DEBUG: Created %s in %.2f secs" % (inc_file, t4-t3))

            return (link_index, strt_loop)



if __name__ == '__main__':
    # Hmmm!
    # use wee_reports instead, see the inline comments above.
    pass
