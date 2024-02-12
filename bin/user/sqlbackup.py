# Copyright (c) 2017-2020 Glenn McKechnie <glenn.mckechnie@gmail.com>
# Credit to Tom Keffer <tkeffer@gmail.com>, Matthew Wall and the core
#        weewx team, all from whom I've borrowed heavily.
# Mistakes are mine, corrections and or improvements welcomed
#      https://github.com/glennmckechnie/weewx-sqlbackup
#
# See the file LICENSE.txt for your full rights.
#
#

import os
import shutil
import gzip
import subprocess
import syslog
import time
import datetime

import weewx.engine
import weewx.manager
import weewx.units
from weewx.cheetahgenerator import SearchList
from weeutil.weeutil import to_bool

sql_version = "0.5"

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'sqlbackup: %s:' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)

"""
add to weewx.conf if debug output is required
sql_debug = 5 will also need to be set in skin.conf
[Logging]
    [[loggers]]
        [[[user.sqlbackup]]]
            level = DEBUG
            handlers = syslog,
            propagate = 0

"""


class SqlBackup(SearchList):
    """ Notes and WARNINGS

    DON'T back the whole database up with this skin. You'll overload weewx and
    weird things could happen. Report generation may be skipped as a result.

    The idea is to instead select a small rolling window from the database (if
    its a MySQL or MariaDB) and dump this at each report_timing interval. We
    will use that as a partial backup.
    At restore time we'll then need to select some or all of the dump files,
    and stitch them together as appropriate.

    If it's an sqlite database, it will dump it (them) all, or now the default
    is to do as for mysql - a partial dump

    This skin was created to backup a mysql database that runs purely in
    memory, it has since evolved to include sqlite databases as well.
    Because running a database in memory is a little! fragile (to say the
    least.)
    I configured my script to run every hour, and it dumps the last 24 hours of
    the database to the  xxsql_bup_file in the format...
         {database}-host.{hostname}-{epoch-timestamp}-{window-time-period}.gz
    eg:  weatherpi-host.masterofpis-201706132105-24hours.gz

    Those intervals are handled easily on my setup and do not interrupt the
    report generation in weewx. Your processor, memory, database, archive
    interval will be different to mine... YMWV

    You'll need to adjust the values to suit you. Setting sql_debug = "2" in
    the skin.conf will inform you while you make changes, look at the logs.
    Or, if you set sql_debug = "4" it will be included at the foot of the
    sqlbackup/index.html page.

    This script currently performs no error checking so check the resulting
    files for integrity.
    disk full, it will return silence!
    empty database, it will also return silence!

    Reasons for doing it this way (instead of seperate scripts and cron) are
    that it should integrate easily with the weewx proces. This report runs
    after database writes have been done (providing you don't ask too much of
    it), and keeping it under the weewx umbrella fits the "one stop shop" model
    If we don't interfere too much we should slip under the radar.
    Keep it small and sensible and that should all remain true.

    Testing: BACK UP your database first - via other methods. (Okay, Truth is.
    I've used this script by passing a suitable unix time string as the
    sql_period and have lived to tell the tale. I was able to put the pieces
    together again.)
    60*60*24*365*2
    sql_period = "63072000"

    In short...
    Open skin.conf, modify the variables, turn on sql_debug - 2 or 4

    To help speed up the process, you can bypass the report_timing setting and
    cycle through the setup process quickly by copying and modifying a minimal
    weewx.conf file as weewx.wee.conf and invoke that by using.

    wee_reports /etc/weewx/weewx.wee.conf && tail -n50 /var/log/syslog |
     grep wee_report

    then watch your logs, or the sqlbackup/index.html page if you're generating
    the report.

    One hiccup with the wee_reports method is that it may return longer times
    if it encounters a locked database. The ultimate test is when it's run
    under weewx's control, but wee_reports is still very useful to fine tune
    your setup.

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

        report_timing: This is an essential. See the weewx documentation for
        the full description on this addition. There are many options
        eg:- '2 * * * 1' ,  @daily, @weekly, @monthly, etc


        mysql, mariadb are interchangable. Where mysql is mentioned, mariadb
        also applies

        sql_period: mysql; time period for dump; defaults to 86400
         seconds (24hours)
        sql_label: mysql; text label to match above. This has meaning
         to you.
        self.mybup_dir: mysql backup directory: default is '/var/tmp/backups/mysql'
        self.bup_dir: sqlite backup directory: default is '/var/tmp/backups/sql'
        sql_dated_dir: optional string to append to self.xxx_dir. It will be of
         the form 20171231 The default is true. Useful if backups are taken
         often, possibly not so useful if only occasional.
        sql_gen_report: optional html report, helps with quick status check and
         is the only way to catch any errors - std output is directed to the
         bup_file so thats where they are found. The report shows enough to
         identify these.
        part_sqlite: Default is True, to perform a partial dump of sqlite.
         Previously it was limited to a full dump, which equates to False
        self.sql_debug: Used to include additional info in logs, or optional
         html report. default is off, although the newly installed skin comes
         with it turned on.
         0 is off,
         2 is logging only (setting debug = 2 in weewx.conf will also work)
         4 includes the above info in the optional html report.
         ( 5 is used for release testing and can be safely ignored. )

        The following are not listed in the skin.conf file for whatever reason.
        Mostly to avoid confusion in an already wordy config file. They come
        under the umbrella of advanced, or rarely used options but could,
        can, might prove handy at times!

        sql_user: mysql user; defaults to weewx.conf value. Can be overwritten
         via skin.conf
        sql_pass: mysql password; defaults to weewx.conf value. Can be
        overwritten via skin.conf
        sql_host: mysql database location; defaults to weewx.conf value. Can be
         overwritten via skin.conf.
        mysql_database: mysql database name; defaults to 'None'(see next entry)
        sql_database: sqlite database name; defaults to'None'. If both these
         values are None in skin.conf, it will default to the weewx.conf
         default database. Supplying a value other than none in skin.conf will
         override that behaviour. This is useful to backup multiple databases
         using a space seperated list.
        sql_table: mysql / sqlite tables to dump; This defaults to 'archive'.
         Works on full sqlite .dump only.   Use '' to specify 'all' tables.
        sqlite_table: sqlite tables to dump when doing a partial dump; This
         defaults to 'archive' and unless you have a really, really good reason
         - don't change it.
        hide_password: hide_password from logs. Default is True, set to False
         if you really, really want to bypass this small bit of obscurity.
        inc_dir: location of .inc files used in html generation; defaults
         to /tmp/sqlbackup. These are temporary files only , but are needed for
         the cheetah templates (see Seasons skin in newskin branch or latest
         release) They aren't persistent so /tmp is a good spot.
        """

        t1 = time.time()  # this process's start time

        # This probably abuses the weewx naming practice but it enables re-use
        # of the skin (seperate reports) with different values:
        # possibly databases, time_periods, all with their own report_timing
        # stanzas of their own.
        # If multiple skins are configured then it's probably best not to use
        # the @daily etc shortcuts but rather use the '5 * 7 * *' style as the
        # minutes can then be adjusted to prevent clashes were they to coincide
        # skin_name also allows log messages to  reflect this skin re-use
        global skin_name
        skin_name = self.generator.skin_dict['skin']
        self.skin_name = skin_name  # for export to the template / html

        # local (skin) debug switch "2" or weewx.debug, "4" adds extra to html
        # report page
        # 5 is for release testing only and can safely be ignored by users
        try:
            self.sql_debug = int(self.generator.skin_dict[skin_name].get(
                'sql_debug', '0'))
        except KeyError as e:
            # err with duplicate skin, if skin.conf [section] isn't renamed
            logerr("KeyError: Missing skin [section] heading? - %s" % e)
            return
        if weewx.debug >= 1 or self.sql_debug >= 1:
            loginf('version is %s' % sql_version)

        self.user = self.generator.skin_dict[skin_name].get('sql_user')
        if not self.user:
            self.user = self.generator.config_dict['DatabaseTypes'] \
                ['MySQL'].get('user')
        self.passwd = self.generator.skin_dict[skin_name].get('sql_pass')
        if not self.passwd:
            self.passwd = self.generator.config_dict['DatabaseTypes'] \
                ['MySQL'].get('password')
        self.host = self.generator.skin_dict[skin_name].get('sql_host')
        if not self.host:
            self.host = self.generator.config_dict['DatabaseTypes'] \
                ['MySQL'].get('host')

        self.my_dbase = self.generator.skin_dict[skin_name].get(
            'mysql_database', '')
        self.sq_dbase = self.generator.skin_dict[skin_name].get(
            'sql_database', '')
        if not self.my_dbase and not self.sq_dbase:
            def_dbase = self.generator.config_dict['DataBindings'] \
                ['wx_binding'].get('database')
            if self.sql_debug >= 5 :
                logdbg(" 5:1 weewx.conf database is %s" % def_dbase)
            if def_dbase == 'archive_mysql':
                self.my_dbase = self.generator.config_dict['Databases'] \
                    [def_dbase].get('database_name')
                if self.sql_debug >= 5 :
                    logdbg("5:2 weewx.conf mysql dbase is %s" % self.my_dbase)
            elif def_dbase == 'archive_sqlite':
                self.sq_dbase = self.generator.config_dict['Databases'] \
                    [def_dbase].get('database_name')
                if self.sql_debug >= 5:
                    logdbg("5:3 so weewx.conf sqlite database is %s" %
                           self.sq_dbase)
        self.table = self.generator.skin_dict[skin_name].get('sql_table',
                                                             'archive')
        self.sqtable = self.generator.skin_dict[skin_name].get('sqlite_table',
                                                               'archive')

        self.mybup_dir = self.generator.skin_dict[skin_name].get(
            'mysql_bup_dir', '/var/tmp/backups/mysql')
        self.bup_dir = self.generator.skin_dict[skin_name].get(
            'sql_bup_dir', '/var/tmp/backups/sql')
        self.t_period = self.generator.skin_dict[skin_name].get(
            'sql_period', '86400')
        self.t_label = self.generator.skin_dict[skin_name].get(
            'sql_label', 'daily')
        self.dated_dir = to_bool(self.generator.skin_dict[skin_name].get(
            'sql_dated_dir', True))
        self.gen_report = to_bool(self.generator.skin_dict[skin_name].get(
            'sql_gen_report', True))
        self.hide_pass = to_bool(self.generator.skin_dict[skin_name].get(
            'hide_password', True))
        self.part_sql = to_bool(self.generator.skin_dict[skin_name].get(
            'part_sqlite', True))
        self.inc_dir = self.generator.skin_dict[skin_name].get(
            'inc_dir', '/tmp/sqlbackup')
        self.log_dir = self.generator.skin_dict[skin_name].get(
            'log_dir', '/var/log/syslog')
        # no skin.conf option
        self.sq_root = self.generator.config_dict['DatabaseTypes'] \
            ['SQLite'].get('SQLITE_ROOT')

        if self.sql_debug >= 5:  # sanity check for releases - safely ignored.
            if not self.hide_pass:
                logdbg("5: user is  %s" % self.user)
                logdbg("5: passwd is  %s" % self.passwd)
            logdbg("5: host is %s" % self.host)
            logdbg("5: mysql database/s selected: %s" % self.my_dbase)
            logdbg("5: sqlite database/s selected: %s" % self.sq_dbase)
            logdbg("5: mysql table is %s" % self.table)
            logdbg("5: sqlite table is %s" % self.sqtable)
            logdbg("5: mysql backup dir is %s" % self.mybup_dir)
            logdbg("5: sqlite backup dir is %s" % self.bup_dir)
            logdbg("5: dated directory is %s" % self.dated_dir)
            logdbg("5: generate report is %s" % self.gen_report)
            logdbg("5: hide password is %s" % self.hide_pass)
            logdbg("5: sqlite method is %s" % self.part_sql)
            logdbg("5: using sql_debug level of %s" % self.sql_debug)
            logdbg("5: using log_dir of %s" % self.log_dir)

        carry_index = '<hr><b>Databases :: </b>'
        start_loop = 0
        e = ''
        cmd_err = log_cmd = ''

        # Strictly speaking. If we're not generating reports then the following
        # is redundant but we'll leave the structure in place as we do generate
        # the report page, with a message saying we're not generating reports!
        # To disable reports completely comment out the following lines in the
        # skin.conf file
        #   #[[ToDate]]
        #   #    [[[index]]]
        #   #        template = index.html.tmpl
        #
        # Back to it... Do the housework first, we clean out all the *.inc 's
        # now rather than later. This allows their content to be inspected
        # between runs.
        if os.path.exists(self.inc_dir):
            try:
                shutil.rmtree(self.inc_dir)
            except OSError:
                logerr("ERR  %s" % e)
                return
        if not os.path.exists(self.inc_dir):
            try:
                os.makedirs(self.inc_dir)
            except OSError as e:
                logerr("ERR  %s" % e)
                return

        self.all_file = "%s/alldumps.inc" % (self.inc_dir)
        self.head_file = "%s/head.inc" % (self.inc_dir)
        self.tail_file = "%s/tail.inc" % (self.inc_dir)
        self.links_file = "%s/links.inc" % self.inc_dir
        self.sys_file = "%s/syslinks.inc" % self.inc_dir
        self.no_file = "%s/none.inc" % self.inc_dir

        # test if at least one .inc file can be created & bail out if it fails
        try:
            chck = open(self.head_file, 'w+')
        except IOError as e:
            logerr("ERR  %s" % e)
            return
        chck.close()

        # start with a no report message. If we do generate reports we'll
        # overwrite it. This is probably now redundant as we pick up the
        # default database.
        chck = open(self.all_file, 'a')
        chck.write("<p><b>There's nothing to report.</b></p><p>Do you have"
                   " any databases configured?</br> Check the config file"
                   " (skin.conf)</p>")
        chck.close()

        # then prime the links .inc with the start of the page index - to be
        # continued
        try:
            strt = open(self.links_file, 'w')
        except IOError as e:
            logerr("ERR  %s" % e)
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
        if self.sql_debug == 2 or self.sql_debug == 4:
            logdbg(" starting from %s" % readable_time)
        # If true, setup the remote directory name with a date structure
        # eg: <path to backup directory>/2017/02/12/
        if self.dated_dir:
            date_dir_str = time.strftime("/%Y%m%d")
        else:
            date_dir_str = ''
        mydump_dir = self.mybup_dir + "%s" % (date_dir_str)
        dump_dir = self.bup_dir + "%s" % (date_dir_str)

        # Start the mysql dump process
        if self.my_dbase:
            self.mydbase = self.my_dbase.split()
            mydbase_len = len(self.mydbase)
            if self.sql_debug == 2 or self.sql_debug == 4:
                logdbg(" databases, mysql %s named %s" % (mydbase_len,
                       self.mydbase))
            if not os.path.exists(mydump_dir):
                try:
                    os.makedirs(mydump_dir)
                except OSError as e:
                    logerr("ERR  %s" % e)
                    return
            if self.sql_debug == 2 or self.sql_debug == 4:
                logdbg(" directory for mysql backup files %s" % mydump_dir)

            for step in range(mydbase_len):
                t5 = time.time()  # this loops start time
                my_dbase = self.mydbase[step]
                # Because we use the  "--where..." clause, we run into trouble
                # when dumping all tables so we use "--ignore..."  to prevent
                # an incomplete dump. This is because there is no dateTime in
                # the metadata table.
                # And thankfully, this is silently ignored if there is no table
                # of this name; for databases such as mesoraw and sqlite3
                if len(self.table) < 1:
                    self.ignore = ("--ignore-table=%s.archive_day__metadata" %
                                   my_dbase)
                    logdbg("ALL tables specified,including option %s"
                           % self.ignore)
                else:
                    self.ignore = ""
                if self.sql_debug == 2 or self.sql_debug == 4:
                    logdbg(" processing mysql database, %s" % my_dbase)
                mydump_file = mydump_dir + "/%s-host.%s-%s-%s.gz" % (
                    my_dbase, this_host, file_stamp, self.t_label)
                if self.sql_debug == 2 or self.sql_debug == 4:
                    logdbg(" dump_file for mysql backup files %s" %
                           mydump_file)
                # cmd = "mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\"
                #       "%s -R --triggers --single-transaction --skip-opt"
                # We pass a '>' and this requires shell=True
                cmd = ("mysqldump -u%s -p%s -h%s -q  %s %s -w\"dateTime>%s\""
                       " %s --single-transaction --skip-opt" % (
                        self.user, self.passwd, self.host, my_dbase,
                        self.table, past_time, self.ignore))
                dumpcmd = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, shell=True)
                dump_output, dump_err = dumpcmd.communicate()
                dump_err = dump_err.decode('utf-8')
                if dump_err:
                    cmd_err = ("ERROR : %s)" % dump_err)
                    logerr(cmd_err)
                with gzip.open(mydump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t6 = time.time()  # this loops finishing  time

                # obfuscate for logs: hide_password = True as default
                if self.hide_pass:
                    log_cmd = cmd.replace(self.user, "XxXxX", 1)
                    log_cmd = log_cmd.replace(self.passwd, "XxXxX", 1)
                else:
                    log_cmd = cmd
                if self.sql_debug == 2 or self.sql_debug == 4:
                    logdbg(" %.2f secs to run %s" % ((t6-t5), log_cmd))

                if self.gen_report:
                    line_count = "100"
                    sql_name = "mysql"
                    if len(cmd_err) > 1:
                        log_cmd = ("%s \n\n %s \n" % (log_cmd, cmd_err))
                        cmd_err = ''
                    self.report(self.inc_dir, carry_index, log_cmd,
                                mydump_file, my_dbase, line_count,
                                sql_name, start_loop)
                    carry_index = link_index
                    start_loop = strt_loop

        # Start the sqlite dump process
        if self.sq_dbase:
            self.dbase = self.sq_dbase.split()
            dbase_len = len(self.dbase)
            if self.sql_debug == 2 or self.sql_debug == 4:
                logdbg(" databases, sqlite %s named %s" %
                       (dbase_len, self.dbase))
            if not os.path.exists(dump_dir):
                try:
                    os.makedirs(dump_dir)
                except OSError as e:
                    logerr("%s" % e)
                    return
            if self.sql_debug == 2 or self.sql_debug == 4:
                logdbg(" directory for sqlite backup files %s" % dump_dir)

            for step in range(dbase_len):
                t7 = time.time()  # this loops start time
                d_base = self.dbase[step]

                # one-shot pass to get a header file - used for tablei
                # reconstruction for partial dumps, could be useful for full?
                schema_file = dump_dir + "/%s-host.%s-schema.sql" % (
                                   d_base, this_host)
                if not os.path.isfile(schema_file):

                    cmd = ("sqlite3 %s/%s '.schema %s'" % (
                          self.sq_root, d_base, self.sqtable))
                    # cmd = ("sqlite3 -header -insert /var/lib/weewx/%s "
                    #       "'SELECT * from archive where dateTime = "
                    #    " (select max (dateTime) from archive );'" % (d_base))
                    headcmd = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               shell=True)
                    hed_output, hed_err = headcmd.communicate()
                    hed_output = hed_output.decode('utf-8')
                    hed_err = hed_err.decode('utf-8')
                    if hed_err:
                        cmd_err = ("ERROR : %s)" % hed_err)
                        logerr(cmd_err)
                    with open(schema_file, 'w+') as f:
                        f.write(hed_output)
                    f.close()

                if self.sql_debug == 2 or self.sql_debug == 4:
                    logdbg(" processing sqlite database, %s" % d_base)
                # dump_file = dump_dir + "/%s-host.%s-%s-%s.gz"  % (
                #               d_base, this_host, file_stamp, self.t_label)
                # logdbg("dump_file for sqlite backup files %s" %
                #   dump_dir)
                # We pass a '|' and this also requires shell=True
                # cmd = "echo '.dump %s' | sqlite3 /var/lib/weewx/%s" % (
                #         self.table, d_base)
                # csv method
                # https://sqlite.org/cli.html
                # cmd = ("sqlite3 -insert /var/lib/weewx/%s "
                #       " 'SELECT * from archive where dateTime > %s;'" % (
                #         d_base, past_time))
                # loginf("self.part.sql is ?? : %s" % self.part_sql)
                if self.part_sql:
                    # loginf("ifself.part.sql says True or:%s" % self.part_sql)
                    dump_file = dump_dir + "/%s-host.%s-%s-%s.gz" % (
                                   d_base, this_host, file_stamp, self.t_label)
                    if self.sql_debug == 2 or self.sql_debug == 4:
                        logdbg(" dump_file for sqlite backup files %s" %
                               dump_file)
                    cmd = ("sqlite3 %s/%s '.mode \"insert\" \"%s\"' "
                           " 'SELECT * from %s where dateTime > %s;'" % (
                             self.sq_root, d_base, self.sqtable, self.sqtable,
                             past_time))
                else:
                    dump_file = dump_dir + "/%s-host.%s-all.gz" % (
                                   d_base, this_host)
                    if self.sql_debug == 2 or self.sql_debug == 4:
                        logdbg(" dump_file for sqlite backup files %s" %
                               dump_file)
                    cmd = "echo '.dump %s' | sqlite3 %s/%s" % (
                             self.table, self.sq_root, d_base)

                dumpcmd = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, shell=True)
                dump_output, dump_err = dumpcmd.communicate()
                dump_err = dump_err.decode('utf-8')
                if dump_err:
                    cmd_err = ("ERROR : %s)" % dump_err)
                    logerr(cmd_err)
                with gzip.open(dump_file, 'wb') as f:
                    f.write(dump_output)
                f.close()
                t8 = time.time()  # this loops start time

                if self.sql_debug == 2 or self.sql_debug == 4:
                    logdbg(" %.2f secs to run %s" % ((t8-t7), cmd))

                if self.gen_report:
                    line_count = "20"
                    sql_name = "sql"
                    if len(cmd_err) > 1:
                        log_cmd = ("%s \n\n %s \n" % (cmd, cmd_err))
                        cmd_err = ''
                    else:
                        log_cmd = cmd
                    self.report(self.inc_dir, carry_index, log_cmd,
                                dump_file, d_base, line_count,
                                sql_name, start_loop)
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
            sys_links = open(self.sys_file, 'w')
            if self.sql_debug >= 4:
                sys_index = ('<b>System ::</b>'
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
                sys_index = ('<br>&nbsp;&nbsp;&nbsp;<b>System ::</b>'
                             '&nbsp;&nbsp;&nbsp;&nbsp;'
                             '<a href="#disk">disks</a>&nbsp;-&nbsp;'
                             '<a href="#memory">memory</a>&nbsp;-&nbsp;'
                             '<a href="#mounts">mounts</a>&nbsp;&nbsp;'
                             '<br>')

            h_tml = [sys_index, "<hr>"]
            sys_links.writelines(h_tml)
            sys_links.close()

            tl = open(self.tail_file, 'w')
            tl.write('\n<a id="disk"></a><a href="#Top">Back to top</a><h2>'
                     ' Disk Usage: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                     '<pre class="gry">')
            tl.close()
            os.system("df -h >> %s" % self.tail_file)
            tl = open(self.tail_file, 'a')
            tl.write('</pre><hr>\n<a id="memory"></a><a href="#Top">Back to top'
                     '</a><h2> Memory Usage: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                     '<pre class="gry">')
            tl.close()
            os.system("free -h >> %s" % self.tail_file)
            tl = open(self.tail_file, 'a')
            tl.write('</pre><hr>\n<a id="mounts"></a><a href="#Top">Back to top'
                     '</a><h2> Mounted File Systems: </h2>&nbsp;&nbsp;&nbsp;'
                     '&nbsp;\n<pre class="gry">')
            tl.close()
            os.system("mount >> %s" % self.tail_file)
            tl = open(self.tail_file, 'a')
            tl.write("</pre>")
            tl.close()

            # add debug extras to sqlbackup/index.html
            if self.sql_debug >= 4:
                tl = open(self.tail_file, 'a')
                tl.write('<hr>\n<h2> DEBUG output</h2>\n'
                         '<a id="logs"></a><a href="#Top">Back to top</a>'
                         '<h2> Log snippet: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                         '<pre class="gry">')
                tl.close()
                # sanitize the output. If we get a cheetahgenerator error
                # referencing an #include we risk getting stuck in a
                # loop, in a loop.
                os.system("grep %s -e '#' -v|grep  -e 'sqlbackup'"
                          "| tail -n50 >> %s" % (self.log_dir, self.tail_file))
                # default install finds only 1 database, deal with it only
                if os.path.exists(mydump_dir):
                    tl = open(self.tail_file, 'a')
                    tl.write('</pre><hr>\n<a id="mysql"></a><a href="#Top">'
                             'Back to top</a>'
                             '<h2>MySQL files: </h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                             '<pre class="gry">\n%s\n\n' % mydump_dir)
                    tl.close()
                    os.system("ls -gtr %s | tail -n10 >> %s" % (
                               mydump_dir, self.tail_file))

                # default install finds only 1 database, deal with it only
                if os.path.exists(dump_dir):
                    tl = open(self.tail_file, 'a')
                    tl.write('</pre><hr>'
                             '\n<a id="sql"></a><a href="#Top">Back to top</a>'
                             '<h2>sqlite files:</h2>&nbsp;&nbsp;&nbsp;&nbsp;\n'
                             '<pre class="gry">\n%s\n\n' % dump_dir)
                    tl.close()
                    os.system("ls -gtr %s | tail -n10 >> %s" % (
                              dump_dir, self.tail_file))

                tl = open(self.tail_file, 'a')
                tl.write('</pre>\n')
                tl.close()

        # or else: we're not reporting. State that & nullify .inc's
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
        # in the system logs (not the html report, that's done and dusted)
        t2 = time.time()
        loginf("Total time used in backups "
               "and report output: %.2f seconds" % (t2-t1))

    def report(self, inc_dir, carry_index, log_cmd, dump_file, data_base,
               line_count, sql_name, start_loop):
        # If we're reporting then we need to build the text output as we
        # loop through the databases. We can do more than one when we
        # specify a space seperated list in skin.conf
        # Create output for a report using templates *.inc
        global link_index
        global strt_loop
        t3 = time.time()
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
            except OSError as e:
                logerr("%s: ERR  %s" % (skin_name, e))
                return

        inc = open(inc_file, 'w')
        inc.write('&nbsp;&nbsp;&nbsp;&nbsp;<a id="%s"></a><a href='
                  '"#Top">Back to top</a>\n<h2>Extract from the %s '
                  'Database dump file: </h2>\n<pre class="gry">%s\n\n\n' % (
                   data_base, data_base, log_cmd))
        inc.close()
        # my_head = "zcat  %s | head -n%s >> %s" % (
        #           dump_file, line_count, inc_file)
        # broken pipe error from wee_reports seems harmless but is annoying
        # & is due to head truncating the operation. Ah! more at ...
        # https://blog.nelhage.com/2010/02/a-very-subtle-bug/
        # switch to subprocess method and ignore it.
        # os.system(my_head)
        my_head = "zcat  %s | head -n%s " % (
                   dump_file, line_count)
        headcmd = subprocess.Popen(my_head, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=True)
        myhead_out, myhead_err = headcmd.communicate()
        myhead_out = myhead_out.decode('utf-8')
        myhead_err = myhead_err.decode('utf-8')
        inc = open(inc_file, 'a')
        all_head = [myhead_out, "\n[...]\n\n"]
        inc.writelines(all_head)
        inc.close()
        my_tail = "zcat %s | tail -n20 >> %s" % (dump_file, inc_file)
        os.system(my_tail)

        l_inks = open(self.links_file, 'w')
        h_tml = [link_index, "</br>"]
        l_inks.writelines(h_tml)
        l_inks.close()

        os.system("cat %s >> %s" % (inc_file, self.all_file))
        all_lot = open(self.all_file, 'a')
        all_lot.write("</pre>")
        all_lot.close()

        if self.sql_debug == 2 or self.sql_debug == 4:
            t4 = time.time()
            logdbg(" Created %s in %.2f secs" % (inc_file, t4-t3))

        return (link_index, strt_loop)


if __name__ == '__main__':
    # Hmmm!
    # use wee_reports instead, see the inline comments above.
    pass
