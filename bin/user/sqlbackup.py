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
import datetime

import weewx.engine
import weewx.manager
import weewx.units
from weewx.wxengine import StdService
from weewx.cheetahgenerator import SearchList
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, '%s' % msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def tlwrite(txt): # unused
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
    Because running a database in memory is a little! fragile (to say the least.)
    I configured my script to run every hour, and dumps the last 24 hours of the
    database to the  xxsql_bup_file in the format...
         {database}-host.{hostname}-{epoch-timestamp}-{window-time-period}.gz
    eg:  weatherpi-host.masterofpis-201706132105-24hours.gz

    Those intervals are handled easily on my setup and do not interrupt the
    report generation in weewx. Your processor, memory, database, archive
    interval will be different to mine... YMWV

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
    I've used this script by passing a suitable unix time string as the sql_period
    and have lived to tell the tale. I was able to put the pieces together
    again.)
    60*60*24*365*2
    sql_period = "63072000"

    In short...
    Open skin.conf, modify the variables, turn on sql_debug - 2 or 4

    To help speed up the process, bypass the report_timing setting and cycle
    through the setup process quickly by copying and modifying a minimal
    weewx.conf file as weewx.wee.conf and invoke that by using.

    wee_reports /etc/weewx/weewx.wee.conf && tail -n20 /var/log/syslog | grep wee_report

    then watch your logs, or the sqlbackup.html page if you're generating the
    report.

    One hiccup with the wee_reports method is that it may return longer times if
    it encounters a locked database. The ultimate test is when it's run under
    weewx's control, but wee_reports is still very useful to fine tune your setup.

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
        The following options are available in the skin.conf file. weewx.conf
        may take precedence though so some may be ignored - seemingly.
        This allows them to be changed on the fly - while weewx is running, so
        changing these values in the skin.conf file will affect the next
        report run. This makes it very easy to manipulate - databases, timings
        etc. while setting up the skin. No need to restart weewx.

        report_timing: This is an essential. See the weewx documentation for the
        full description on this addition. There are many options
        eg:- '2 * * * 1' ,  @daily, @weekly, @monthly, etc

        self.sql_debug: Used to include additional info in logs, or optional
         html report. default is off, although the newly installed skin comes
         with it turned on.
         0 is off,
         2 is logging only (setting debug = 2 in weewx.conf will also work)
         4 includes the above info in the optional html report.
         5 is bordering on absurd (it's used for release testing.)

        mysql, mariadb are interchangable. Where mysql is mentioned, mariadb
        also applies

        self.user: mysql user; defaults to weewx.conf value. Can be overwritten
         via skin.conf
        self.passwd: mysql password; defaults to weewx.conf value. Can be
        overwritten via skin.conf
        self.host: mysql database location; defaults to weewx.conf value. Can be
         overwritten via skin.conf.
        self.myd_base: mysql database name; defaults to 'None' (see nect)
        self.d_base: sqlite database name; defaults to'None'. If both these
         values are None in skin.conf, it will defaulkt to the weewx.conf default
         database. Supplying a value other than none in skin.conf will override
         that behaviour. This is useful to backup multiple databases using a space
         seperated list.
        self.table: mysql / sqlite tables to dump; This defaults to 'archive'.
        Use '' to specify 'all' tables.
        self.mybup_dir: mysql backup directory; defaults to '/var/backups/mysql'
        self.bup_dir: sqlite backup directory; defaults to '/var/backups/sql'
        self.t_period: mysql; time period for dump; defaults to 86400
         seconds (24hours)
        self.t_label: mysql; text label to match above. This has meaning
         to you.
        self.dated_dir: optional string to append to self.xxx_dir. It will be of
         the form 20171231 The default is true. Useful if backups are taken often
         Possibly not so useful if only occasional.
        self.gen_report: optional html report, helps with quick status check and
         is the only way to catch any errors - std output is directed to the
         bup_file so thats where they are found. The report shows enough to
         identify these.
        self.inc_dir: location of .inc files used in html generation; defaults
         to /tmp/sqlbackup. These are temporary files only , but are needed for
         the cheetah templates (see Seasons skin in newskin branch or latest
         release) They aren't persistent so /tmp is a good spot.
        """

        t1 = time.time() # this process's start time

        # This probably abuses the weewx naming practice but it enables re-use of
        # the skin (seperate reports) with different values:
        # possibly databases, time_periods, all with their own report_timing stanzas
        # of their own.
        # If multiple skins are configured then it's probably best not to use the
        # @daily etc shortcuts but rather use the '5 * 7 * *' style as the minutes
        # can then be adjusted to prevent clashes were they to coincide.
        # skin_name also allows log messages to  reflect this skin re-use
        global skin_name
        skin_name =  self.generator.skin_dict['skin']
        self.skin_name = skin_name # for export to the template / html

        # local debug switch "2" also = weewx.debug, "4" adds extra to html report page
        # 5 is bordering on absurd (used for release testing)
        self.sql_debug = int(self.generator.skin_dict[skin_name].get('sql_debug','0'))

        self.user = self.generator.skin_dict[skin_name].get('sql_user')
        if not self.user:
            self.user = self.generator.config_dict['DatabaseTypes']['MySQL'].get('user')
        self.passwd = self.generator.skin_dict[skin_name].get('sql_pass')
        if not self.passwd:
            self.passwd = self.generator.config_dict['DatabaseTypes']['MySQL'].get('password')
        self.host = self.generator.skin_dict[skin_name].get('sql_host')
        if not self.host:
            self.host = self.generator.config_dict['DatabaseTypes']['MySQL'].get('host')

        self.myd_base = self.generator.skin_dict[skin_name].get('mysql_database','')
        self.d_base = self.generator.skin_dict[skin_name].get('sql_database','')
        if not self.myd_base and not self.d_base:
            defd_base = self.generator.config_dict['DataBindings']['wx_binding'].get('database')
            if self.sql_debug >= 5 :
                loginf("%s 5:1 weewx.conf database is %s" % (skin_name, defd_base))
            if defd_base == 'archive_mysql':
                self.myd_base = self.generator.config_dict['Databases'][defd_base].get('database_name')
                if self.sql_debug >= 5 :
                    loginf("%s 5:2 so weewx.conf mysql database is %s" % (skin_name, self.myd_base))
            elif defd_base == 'archive_sqlite':
                self.d_base = self.generator.config_dict['Databases'][defd_base].get('database_name')
                if self.sql_debug >= 5 :
                    loginf("%s 5:3 so weewx.conf sqlite database is %s" % (skin_name, self.d_base))
        self.table = self.generator.skin_dict[skin_name].get('sql_table','archive')
        self.mybup_dir = self.generator.skin_dict[skin_name].get('mysql_bup_dir','/var/backups/mysql')
        self.bup_dir = self.generator.skin_dict[skin_name].get('sql_bup_dir','/var/backups/sql')
        self.t_period = self.generator.skin_dict[skin_name].get('sql_period','86400')
        self.t_label = self.generator.skin_dict[skin_name].get('sql_label','daily')
        self.dated_dir = to_bool(self.generator.skin_dict[skin_name].get('sql_dated_dir', True))
        self.gen_report = to_bool(self.generator.skin_dict[skin_name].get('sql_gen_report', True))
        self.inc_dir = self.generator.skin_dict[skin_name].get('inc_dir', '/tmp/sqlbackup')

        if self.sql_debug >= 5 : # sanity check for releases - safely ignored!
            #loginf("%s 5: weewx.conf user is  %s" % (skin_name, self.user))
            loginf("%s 5: weewx.conf user was used" % skin_name)
            #loginf("%s 5: weewx.conf passwd is  %s" % (skin_name, self.passwd))
            loginf("%s 5: weewx.conf passwd was used" % skin_name)
            loginf("%s 5: weewx.conf host is  %s" % (skin_name, self.host))
            loginf("%s 5: using sql_debug level of %s" % (skin_name, self.sql_debug))
            loginf("%s 5: generate report is %s" % (skin_name, self.gen_report))
            loginf("%s 5: mysql databases selected: %s" % (skin_name, self.myd_base))
            loginf("%s 5: sql databases selected: %s" % (skin_name, self.d_base))

        carry_index = '<hr><b>Databases :: </b>'
        start_loop = 0
        e = ''
        cmd_err = ''

        # Strictly speaking. If we're not generating reports then the following is redundant
        # but we'll leave the structure in place as we do generate the report page, with a
        # message saying we're not generating reports!
        # To disable reports completely comment out the following lines in the skin.conf file
        #   #[[ToDate]]
        #   #    [[[index]]]
        #   #        template = sqlbackup.html.tmpl
        #
        # Back to it... Do the housework first, we clean out all the *.inc 's now rather
        # than later. This allows their content to be inspected between runs.
        if os.path.exists(self.inc_dir):
            try:
                shutil.rmtree(self.inc_dir)
            except OSError:
                loginf("%s: ERR  %s" % (skin_name, e))
                return
        if not os.path.exists(self.inc_dir):
            try:
                os.makedirs(self.inc_dir)
            except OSError,e:
                loginf("%s: ERR  %s" % (skin_name, e))
                return

        self.all_file = "%s/alldumps.inc" % (self.inc_dir)
        self.head_file = "%s/head.inc" % (self.inc_dir)
        self.tail_file = "%s/tail.inc" % (self.inc_dir)
        self.links_file = "%s/links.inc" % self.inc_dir
        self.sys_file = "%s/syslinks.inc" % self.inc_dir
        self.no_file = "%s/none.inc" % self.inc_dir

        # test if at least one .inc file can be created and bail out if it fails
        try:
            chck = open(self.head_file, 'w+')
        except IOError, e:
            loginf("%s: ERR  %s" % (skin_name, e))
            return
        chck.close()

        # start with a no report message. If we do generate reports we'll overwrite it.
        # This is probably now redundant as we pick up the default database.
        chck = open(self.all_file, 'a')
        chck.write("<p><b>There's nothing to report.</b></p><p>Do you have any "
             "databases configured?</br> Check the config file (skin.conf)</p>")
        chck.close()

        # then prime the links .inc with the start of the page index - to be continued
        try:
            strt = open(self.links_file, 'w')
        except IOError, e:
            loginf("%s: ERR  %s" % (skin_name, e))
            return
        strt.write(carry_index)
        strt.close()

        # Setup for the dump process's

        this_host = os.uname()[1]
        file_stamp = time.strftime("%Y%m%d%H%M")

        # add 900 seconds to ensure data ovelaps between runs.
        self.t_period = int(self.t_period) + int('900')
        # then for the dump process
        past_time = int(time.time()) - int(self.t_period)

        readable_time = (datetime.datetime.fromtimestamp(past_time).strftime(
            '%Y-%m-%d %H:%M:%S'))
        if weewx.debug >= 2 or self.sql_debug >= 2:
            loginf("%s DEBUG: starting from %s" % (skin_name, readable_time))
        # If true, setup the remote directory name with a date structure
        # eg: <path to backup directory>/2017/02/12/var/lib/weewx...
        if self.dated_dir:
            date_dir_str = time.strftime("/%Y%m%d")
        else:
            date_dir_str = ''
        mydump_dir = self.mybup_dir + "%s" % (date_dir_str)
        dump_dir = self.bup_dir + "%s" % (date_dir_str)

        if not os.path.exists(mydump_dir):
            try:
                os.makedirs(mydump_dir)
            except OSError,e:
                loginf("%s: ERR  %s" % (skin_name, e))
                return

        if not os.path.exists(dump_dir):
            try:
                os.makedirs(dump_dir)
            except OSError,e:
                loginf("%s: ERR  %s" % (skin_name, e))
                return

        if weewx.debug >= 2 or self.sql_debug >= 2:
           loginf("%s DEBUG: directory for backup files - %s, sqlite files %s" % (
              skin_name, mydump_dir,dump_dir))

        # Start the mysql dump process
        if self.myd_base:
            self.mydbase = self.myd_base.split()
            mydbase_len = len(self.mydbase)
            if weewx.debug >= 2 or self.sql_debug >= 2 :
                loginf("%s DEBUG: databases, mysql %s named %s" % (skin_name, mydbase_len,
                self.mydbase))
            for step in range(mydbase_len):
                t5 = time.time() # this loops start time
                myd_base = self.mydbase[step]
                # Because we use the  "--where..." clause, we run into trouble when
                # dumping all tables so we use "--ignore..."  to prevent an incomplete
                # dump. This is because there is no dateTime in the metadata table.
                # And thankfully, this is silently ignored if there is no table of this name;
                # for databases such as mesoraw and sqlite3
                if len(self.table) < 1:
                    self.ignore = "--ignore-table=%s.archive_day__metadata" % myd_base
                    loginf("%s DEBUG: ALL tables specified,including option %s" % (skin_name, self.ignore))
                else:
                    self.ignore = ""
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("%s DEBUG:  mysql database is %s" % (skin_name, myd_base))
                mydump_file = mydump_dir + "/%s-host.%s-%s-%s.gz"  % (
                    myd_base, this_host, file_stamp, self.t_label)
                # We pass a '>' and this requires shell=True
                #cmd = "mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s -R --triggers --single-transaction --skip-opt" %(
                cmd = "mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\" %s --single-transaction --skip-opt" %(
                       self.user, self.passwd, self.host, myd_base, self.table, past_time, self.ignore)
                dumpcmd = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, shell=True)
                dump_output, dump_err = dumpcmd.communicate()
                if dump_err:
                    cmd_err = ("%s  ERROR : %s)" % (skin_name, dump_err))
                    logerr(cmd_err)
                with gzip.open(mydump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t6 = time.time() # this loops finishing  time

                # obfuscate for logs
                log_cmd = cmd.replace(self.user ,"XxXxX" )
                log_cmd = log_cmd.replace(self.passwd ,"XxXxX" )
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("%s DEBUG: %.2f secs to run %s" % (skin_name, (t6-t5), log_cmd))

                if self.gen_report:
                    line_count = "100"
                    sql_name = "mysql"
                    log_cmd = ("%s \n\n %s \n" % (log_cmd, cmd_err))
                    cmd_err = ''
                    self.report(self.inc_dir, carry_index, log_cmd,
                                mydump_file, myd_base, line_count, sql_name, start_loop)
                    carry_index = link_index
                    start_loop = strt_loop

        # Start the sqlite dump process
        if self.d_base:
            self.dbase = self.d_base.split()
            dbase_len = len(self.dbase)
            if weewx.debug >= 2 or self.sql_debug >= 2:
                loginf("%s DEBUG: databases, sqlite %s named %s" %
                    (skin_name, dbase_len, self.dbase))
            for step in range(dbase_len):
                t7 = time.time() # this loops start time
                d_base = self.dbase[step]
                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("%s DEBUG:  sql database is %s" % (skin_name, d_base))
                dump_file = dump_dir + "/%s-host.%s-%s-%s.gz"  % (
                               d_base, this_host, file_stamp, self.t_label)
                # We pass a '|' and this also requires shell=True
                cmd = "echo '.dump %s' | sqlite3 /var/lib/weewx/%s.sdb" %(self.table, d_base)

                dumpcmd = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, shell=True)
                dump_output, dump_err = dumpcmd.communicate()
                #dumpoutput = dump_output.encode("utf-8").strip()
                if dump_err:
                    cmd_err = ("%s  ERROR : %s)" % (skin_name, dump_err))
                    logerr(cmd_err)
                with gzip.open(dump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t8 = time.time() # this loops start time

                if weewx.debug >= 2 or self.sql_debug >= 2:
                    loginf("%s DEBUG: %.2f secs to run %s" % (skin_name, (t8-t7), cmd))

                if self.gen_report:
                    line_count = "20"
                    sql_name = "sql"
                    log_cmd = ("%s \n\n %s \n" % (cmd, cmd_err))
                    cmd_err = ''
                    self.report(self.inc_dir, carry_index, log_cmd,
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

        # decide if we're adding content or else: nullifying
        if self.gen_report:
            sys_links=open(self.sys_file, 'w')
            if self.sql_debug >= 4 :
                sys_index =('<b>System ::</b>'
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
                         '<pre>\n%s\n\n' % mydump_dir)
                tl.close()
                os.system("ls -gtr %s | tail -n10 >> %s" % (
                           mydump_dir, self.tail_file))

                tl = open(self.tail_file, 'a')
                tl.write('</pre><hr>'
                         '\n<a id="sql"></a><a href="#Top">Back to top</a>'
                         '<h2>sqlite files: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                         '<pre>\n%s\n\n' % dump_dir)
                tl.close()
                os.system("ls -gtr %s | tail -n10 >> %s" % (dump_dir,self.tail_file))

                tl = open(self.tail_file, 'a')
                tl.write('</pre>\n')
                tl.close()

        # or else: we're not reporting. state that & nullify .inc's
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
        loginf("%s: Total time used in backups "
                      "and report output: %.2f seconds" % (skin_name, (t2-t1)))


    def report(self, inc_dir, carry_index, log_cmd, dump_file, data_base,
               line_count, sql_name, start_loop):
            # If we're reporting then we need to build the text output as we loop
            # through the databases. We can do more than one when we specify a
            # space seperated list in skin.conf
            # Create output for a report using templates *.inc
            global link_index
            global strt_loop
            t3= time.time()
            inc_file = "%s/%s.inc" % (inc_dir, data_base)
            self.links_file = "%s/links.inc" % inc_dir
            self.all_file = "%s/alldumps.inc" % inc_dir

            # we are generating a report so we overwrite the "no report" message
            if start_loop <= 0:
                strt_loop = 1
                strt = open(self.all_file, 'w')
                strt.write("\n")
                strt.close()

            next_index = ('%s.<a href="#%s">%s</a>&nbsp;&nbsp;' % (
                          sql_name, data_base, data_base))
            link_index = carry_index + next_index

            if not os.path.exists(inc_dir):
                try:
                    os.makedirs(inc_dir)
                except OSError,e:
                    loginf("%s: ERR  %s" % (skin_name, e))
                    return

            inc = open(inc_file, 'w')
            inc.write('&nbsp;&nbsp;&nbsp;&nbsp;<a id="%s"></a><a href='
                      '"#Top">Back to top</a>\n<h2>Extract from the %s '
                      'Database dump file: </h2>\n<pre>%s\n\n\n' % (
                      data_base, data_base, log_cmd))
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
                loginf("%s DEBUG: Created %s in %.2f secs" % (skin_name, inc_file, t4-t3))

            return (link_index, strt_loop)



if __name__ == '__main__':
    # Hmmm!
    # use wee_reports instead, see the inline comments above.
    pass
