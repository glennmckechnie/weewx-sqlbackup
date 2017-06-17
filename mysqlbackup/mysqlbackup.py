#
#    Copyright (c) 2012 Will Page <compenguy@gmail.com>
#    Derivative of ftpupload.py, credit to Tom Keffer <tkeffer@gmail.com>
#
#    Modified to allow multiple source directories to be transferred in the one
#    session, rsync to localhost, addition of dated dir structure on remote,
#    include an rsync_option, skin name for logging
#    (c) 2017 Glenn McKechnie <glenn.mckechnie@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Id: rsyncupload.py 2766 2014-12-02 02:45:36Z tkeffer $
#
"""For uploading files to a remove server via Rsync"""

import os
import errno
import sys
import subprocess
import syslog
import time

import weewx.engine
import weewx.manager
import weewx.units


class SQLBackup(object):
    """Uploads a directory and all its descendants to a remote server.

    Its default behaviour is to keep track of what files have changed,
    and only updates changed files, eg: /var/www/html/weewx transfers
    for the web server.
    
    Now modified to allow recursive behaviour, as well as additional
    directories at the remote end.
    """

    def __init__(self, local_root, remote_root, server,
                 dated_dir, user=None, delete=False, port=None,
                 rsync_opt=None, ssh_options=None, compress=False,
                 log_success=True):
        """Initialize an instance of RsyncUpload.

        After initializing, call method run() to perform the upload.

        HTML_ROOT: The default value for remote_root as read from weewx.conf.
        To use another destination, specify it as HTML_ROOT = /path/to/files
        in weewx.conf

        All other config variables - stanzas. Can exist in either weewx.conf or
        in an appropriately named skin file. They are...

        local_root: path of directory to be transferred. Multiple paths can
        be added as a space separated list - the only time spaces can be added
        to a config variable.

        server: The remote server to which the files are to be uploaded. DNS
        qualified name or IP address. Use localhost if copying locally.
        localhost can't write to / Any attempts will be redirected to
        /tmp/localhost

        user: The user name that is to be used. [Optional, maybe] If
        server = localhost is specified, user becomes ''

        dated_dir: Optional structure for remote tree eg: 2017/02/02 rolling
        over as required. this end builds those directories as required.

        rsync_option: Added to allow addition of -R, ( --relative use relative
        path name. Others may be included but that's untested. No spaces allowed

        report_timing: See the weewx documentation for the full description on
        this addition. There are many options eg:-
        @daily, @weekly, @monthly, etc

        delete: delete remote files that don't match with local files. Use
        with caution.  [Optional.  Default is False.]

        self_report_name: always defaults to the [[section]] name used in
        weewx.conf
        """
        #self.local_root  = os.path.normpath(local_root)
        self.local_root  = local_root
        self.remote_root = os.path.normpath(remote_root)
        self.server      = server
        self.user        = user
        self.dated_dir   = dated_dir
        self.delete      = delete
        self.port        = port
        self.rsync_opt = rsync_opt
        self.ssh_options = ssh_options
        self.compress    = compress
        self.log_success = log_success

    def run(self):
        """Perform the actual upload.

        Check for rsync error codes and log the obvious ones
        """
	"""
        t1 = time.time()
        # With multiple configs available, prefix with the skin or label name
        # for log clarity
        # Do we have spaces in this string? If so we'll have multiple directories
        # Set up for later tests
        src_dir = self.local_root.split()
        src_len = len(src_dir)
        if weewx.debug >= 2:
            syslog.syslog(syslog.LOG_DEBUG, "local root string length: %s" % src_len)

        # If true, create the remote directory with a date structure
        # eg: <path to backup directory>/2017/02/12/var/lib/weewx...
        if self.dated_dir:
            date_dir_str = time.strftime("/%Y/%m/%d/")
        else:
            date_dir_str = ''
        if weewx.debug >= 2:
            syslog.syslog(syslog.LOG_INFO, "timestamp used for rsyncremotespec  - %s" % date_dir_str)

        # allow local transfers
        if self.server == 'localhost':
            rsyncremotespec = "%s%s" % (self.remote_root, date_dir_str)
            rsync_rem_dir = "%s%s" % (self.remote_root, date_dir_str)
            self.user = ''
            if weewx.debug >= 2:
                syslog.syslog(syslog.LOG_DEBUG, "self.remote_root is %s and rsync_rem_dir is %s" %  (self.remote_root, rsync_rem_dir))
            # and attempt to prevent disasters!
            if self.remote_root == '/':
                rsyncremotespec = '/tmp/%s/' % (self.server)
                err_mes = "rsyncupload:  ERR Attempting to write files to %s redirecting to %s ! FIXME !" %  (self.remote_root, rsyncremotespec)
                syslog.syslog(syslog.LOG_ERR, "%s" %  (err_mes))

        else:
            # construct string for remote ssh
            if self.user is not None and len(self.user.strip()) > 0:
                rsyncremotespec = "%s@%s:%s%s" % (self.user, self.server, self.remote_root, date_dir_str)
                rsync_rem_dir = "%s%s" % (self.remote_root, date_dir_str)
            else:
                # ?? same account (user) as weewx
                rsyncremotespec = "%s:%s%s" % (self.server, self.remote_root, date_dir_str)
                rsync_rem_dir = "%s%s" % (self.remote_root, date_dir_str)
        # A chance to add rsync options eg -R (no spaces allowed)
        if self.rsync_opt is not None and len(self.rsync_opt.strip()) > 0:
            rsyncoptstring = "%s" % (self.rsync_opt)
        else:
            rsyncoptstring = "-a"
        # haven't used nor tested this (-p 222) ???
        if self.port is not None and len(self.port.strip()) > 0:
            rsyncsshstring = "ssh -p %s" % (self.port,)
        else:
            rsyncsshstring = "ssh"

        # nor tested this ???
        if self.ssh_options is not None and len(self.ssh_options.strip()) > 0:
            rsyncsshstring = rsyncsshstring + " " + self.ssh_options

        # construct the command argument
        cmd = ['rsync']
        # -a archive means:
        #   recursive, copy symlinks as symlinks, preserve perm's, preserve
        #   modification times, preserve group and owner, preserve device
        #   files and special files, but not ACLs, no hardlinks, and no
        #   extended attributes
        #cmd.extend(["-a"])

        # add any others as required, but add them now (before ssh str)
        if self.rsync_opt:
            cmd.extend(["%s" % rsyncoptstring])

        # provide some stats on the transfer
        cmd.extend(["--stats"])

        # Remove files remotely when they're removed locally
        if self.delete:
            cmd.extend(["--delete"])
        if self.compress:
            cmd.extend(["--compress"])

        # Are we operating locally? If so tweak the cmd
        if self.server != 'localhost':
            cmd.extend(["-e %s" % rsyncsshstring])

        # If src_lentest shows we have multiple, space separated local
        # directories, seperate them out and add them back as individual stanzas
        # If we don't do this, rsync will complain about non existant files
        if src_len > 1:
            if weewx.debug >= 2:
                syslog.syslog(syslog.LOG_DEBUG, "original local root string: %s" % self.local_root)
                syslog.syslog(syslog.LOG_DEBUG, "local root string length: %s" % src_len)
                syslog.syslog(syslog.LOG_DEBUG, "src_dir: %s" % src_dir)
            for step in range(src_len):
                # we don't want to force os.sep if we have multiple dirs use them as entered
                #if src_dir[step].endswith(os.sep):
                multi_loc = src_dir[step]
                if weewx.debug >= 2:
                    syslog.syslog(syslog.LOG_DEBUG, "multi_loc = %s" % multi_loc)
                cmd.extend([multi_loc])
        else:
            # Keep original 'transfer to remote web server' behaviour - append
            # a slash to ensure only directories contents are copied.
            # If the source path ends with a slash, rsync interprets that as a
            # request to copy all the directory's *contents*, whereas if it
            # doesn't, it copies the entire directory.
            # For a single directory copy, we want the former (backwards
            # compatabile); so make it end  with a slash.
            #
            # of note : self.local_root  = os.path.normpath(local_root)
            # stanza used at the start (above) strips the last slash off ?????
            # seems redundant when we reinsert it anyway?
            # tested without and seems to make no difference - assuming no major
            # typos by user - we'll give them the benefit.
            # Removing this to allow multi path to work - original +os.sep
            # makes it redundant 2017/02/15 Glenn.McKechnie
            if self.local_root.endswith(os.sep):
                rsynclocalspec = self.local_root
                cmd.extend([rsynclocalspec])
                if weewx.debug >= 2:
                    syslog.syslog(syslog.LOG_DEBUG, "rsynclocalspec ends with %s" % rsynclocalspec)
            else:
                rsynclocalspec = self.local_root + os.sep
                cmd.extend([rsynclocalspec])
                if weewx.debug >= 2:
                    syslog.syslog(syslog.LOG_DEBUG, "rsynclocalspec + os.sep %s" % rsynclocalspec)
        cmd.extend([rsyncremotespec])

        try:
            # perform the actual rsync transfer...
            if weewx.debug >= 2:
                syslog.syslog(syslog.LOG_DEBUG, "rsync cmd is ... %s" % (cmd))
            rsynccmd = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print "cmd = ", cmd
            stdout = rsynccmd.communicate()[0]
            stroutput = stdout.encode("utf-8").strip()
        except OSError, e:
            #print "EXCEPTION"
            if e.errno == errno.ENOENT:
                syslog.syslog(syslog.LOG_ERR, "rsyncupload: rsync does not appear to be installed on this system. (errno %d, \"%s\")" % (e.errno, e.strerror))
            raise

        # we have some output from rsync so generate an appropriate message
        if stroutput.find('rsync error:') < 0:
            # no rsync error message so parse rsync --stats results
            rsyncinfo = {}
            for line in iter(stroutput.splitlines()):
                if line.find(':') >= 0:
                    (n, v) = line.split(':', 1)
                    rsyncinfo[n.strip()] = v.strip()
            # get number of files and bytes transferred and produce an
            # appropriate message
            try:
                if 'Number of regular files transferred' in rsyncinfo:
                    N = rsyncinfo['Number of regular files transferred']
                else:
                    N = rsyncinfo['Number of files transferred']

                Nbytes = rsyncinfo['Total transferred file size']
                if N is not None and Nbytes is not None:
                    rsync_message = "rsync'd %s files (%s) in %%0.2f seconds" % (N, Nbytes)
                else:
                    rsync_message = "rsync executed in %0.2f seconds"
            except:
                rsync_message = "rsync :exception raised: executed in %0.2f seconds"
        else:
            # suspect we have an rsync error so tidy stroutput
            # and display a message
            stroutput = stroutput.replace("\n", ". ")
            stroutput = stroutput.replace("\r", "")
            # Attempt to catch a few errors that may occur and deal with them
            # see man rsync for EXIT VALUES
            rsync_message = "rsync command failed after %0.2f seconds (set 'weewx.debug = 1'),"
            if "code 1)" in stroutput:
                if weewx.debug >= 1:
                    syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync code 1 - %s" % stroutput)
                rsync_message = "syntax error in rsync command - set debug = 1 - ! FIX ME !"
                syslog.syslog(syslog.LOG_INFO, "rsyncupload:  ERR %s " % (rsync_message))
                rsync_message = "code 1, syntax error, failed rsync executed in %0.2f seconds"

            elif ("code 23" and "Read-only file system") in stroutput:
                # read-only file system
                # sadly, won't be detected until after first succesful transfer
                # but it's useful then!
                if weewx.debug >= 1:
                    syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync code 23 - %s" % stroutput)
                syslog.syslog(syslog.LOG_INFO, "  ERR Read only file system ! FIX ME !")
                rsync_message = "code 23, read-only, rsync failed executed in %0.2f seconds"
            elif ("code 23" and "link_stat") in stroutput:
                # likely to be that a local path doesn't exist - possible typo?
                if weewx.debug >= 1:
                    syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync code 23 found %s" % stroutput)
                rsync_message = "rsync code 23 : is %s correct? ! FIXME !" % (rsynclocalspec)
                syslog.syslog(syslog.LOG_INFO, "rsyncupload:  ERR %s " % rsync_message)
                rsync_message = "code 23, link_stat, rsync failed executed in %0.2f seconds"

            elif "code 11" in stroutput:
                # directory structure at remote end is missing - needs creating
                # on this pass. Should be Ok on next pass.
                if weewx.debug >= 1:
                    syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync code 11 - %s" % stroutput)
                rsync_message = "rsync code 11 found Creating %s as a fix?" % (rsync_rem_dir)
                syslog.syslog(syslog.LOG_INFO, "rsyncupload: %s"  % rsync_message)
                # laborious but apparently necessary, the only way the command will run!?
                # build the ssh command - n.b:  spaces cause wobblies!
                if self.server == 'localhost':
                    cmd = ['mkdir']
                    cmd.extend(['-p'])
                    cmd.extend(["%s" % rsyncremotespec])
                    if weewx.debug >= 2:
                        syslog.syslog(syslog.LOG_DEBUG, "mkdircmd %s" % cmd)
                    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    rsync_message = "code 11, rsync mkdir cmd executed in % 0.2f seconds"
                else:
                    cmd = ['ssh']
                    cmd.extend(["%s@%s" % (self.user, self.server)])
                    mkdirstr = "mkdir -p"
                    cmd.extend([mkdirstr])
                    cmd.extend([rsync_rem_dir])
                    if weewx.debug >= 2:
                        syslog.syslog(syslog.LOG_DEBUG, "sshcmd %s" % cmd)
                    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    rsyncremotespec = rsync_rem_dir
                    rsync_message = "code 11, rsync mkdir cmd executed in % 0.2f seconds"
                rsync_message = "rsync executed in %0.2f seconds, built destination (remote) directories"
            elif ("code 12") and ("Permission denied") in stroutput:
                if weewx.debug >= 1:
                    syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync code 12 - %s" % stroutput)
                rsync_message = "Permission error in rsync command, probably remote authentication ! FIX ME !"
                syslog.syslog(syslog.LOG_INFO, "rsyncupload:  ERR %s " % (rsync_message))
                rsync_message = "code 12, rsync failed, executed in % 0.2f seconds"
            elif ("code 12") and ("No route to host") in stroutput:
                if weewx.debug >= 1:
                    syslog.syslog(syslog.LOG_DEBUG, "rsyncupload: rsync code 12 - %s" % stroutput)
                rsync_message = "No route to host error in rsync command ! FIX ME !"
                syslog.syslog(syslog.LOG_INFO, "rsyncupload:  ERR %s " % (rsync_message))
                rsync_message = "code 12, rsync failed, executed in % 0.2f seconds"
            else:
                syslog.syslog(syslog.LOG_ERR, "ERROR: rsyncupload: [%s] reported this error: %s" % (cmd, stroutput))

        if self.log_success:
            if weewx.debug == 0:
                to = ''
                rsyncremotespec = ''
            else:
                to = ' to '
            t2= time.time()
            syslog.syslog(syslog.LOG_INFO, "rsyncupload: %s" % rsync_message % (t2-t1) + to + rsyncremotespec)
            # Keep record of all http://australiawx.net/ uploads
            #cmd =' cat /var/www/html/weewx/DATA/WL_stickertags.txt > /var/www/html/weewx/DATA/ALL_WL_stickertags.txt'
            #catcmd = ['cat']
            #catcmd.extend(['/var/www/html/weewx/DATA/WL_stickertags.txt'])
            #catcmd.extend([' >> '])
            #catcmd.extend(['/var/www/html/weewx/DATA/ALL_WL_stickertags.txt'])
            #if weewx.debug >= 2:
            #    syslog.syslog(syslog.LOG_DEBUG, "cat cmd %s" % catcmd)
            #syslog.syslog(syslog.LOG_DEBUG, "cat cmd %s" % catcmd)
            #subprocess.Popen(catcmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            #date_cat_str = time.strftime("%Y%m%d")
            #catcmd = ['/bin/cat']
            #catcmd.extend(['/var/www/html/weewx/DATA/WL_stickertags.txt'])
            #catcmd.extend(['>>'])
            #cat_dest = "/var/www/html/weewx/DATA/" + date_cat_str + "_WL_stickertags.txt"
            #catcmd.extend([cat_dest])
            #if weewx.debug >= 2:
            #    syslog.syslog(syslog.LOG_DEBUG, "catcmd %s" % catcmd)
            #syslog.syslog(syslog.LOG_DEBUG, "dated catcmd %s" % catcmd)
            #subprocess.Popen(catcmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            #try:
            #    # perform the actual rsync transfer...
            #    if weewx.debug >= 2:
            #        syslog.syslog(syslog.LOG_DEBUG, "cat cmd is ... %s" % (catcmd))
            #    runcatcmd = subprocess.Popen(catcmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            #    print "catcmd = ", runcatcmd
            #    stdout = runcatcmd.communicate()[0]
            #    stroutput = stdout.encode("utf-8").strip()
            #except OSError, e:
            #    #print "EXCEPTION"
            #    if e.errno == errno.ENOENT:
            #        syslog.syslog(syslog.LOG_ERR, "rsyncupload:cat  does not appear to be installed on this system. (errno %d, \"%s\")" % (e.errno, e.strerror))
            #    raise

            #https://stackoverflow.com/questions/13613336/python-concatenate-text-files
            #os.system("cat /var/www/html/weewx/DATA/WL_stickertags.txt >> /var/www/html/weewx/DATA/catALL_WL_stickertags.txt")
            date_cat_str = time.strftime("%Y%m%d")
            """
	os.system("/home/pi/bin/mysql-backup.sh doit")



if __name__ == '__main__':

   # To run this manually it's best to construct a minimalist, renamed
   # weewx.conf file, with (possibly) modified skin files, and run that
   # to test this script with :-
   #
   # wee_reports /etc/weewx/weewx-test.conf
   #
   # The report_timing stanza is ignored when testing with wee_reports -
   # everything else will be actioned on though.
   #
   # Running this directly returns an error
   #$ PYTHONPATH=/usr/share/weewx python /usr/share/weewx/weeutil/rsyncupload.py
   #   Traceback (most recent call last):
   #  File "/usr/share/weewx/weeutil/rsyncupload.py", line 23, in <module>
   #    import weewx.engine
   #  File "/usr/share/weewx/weewx/engine.py", line 26, in <module>
   #    import weewx.accum
   #  File "/usr/share/weewx/weewx/accum.py", line 12, in <module>
   #    from weewx.units import ListOfDicts
   #  File "/usr/share/weewx/weewx/units.py", line 15, in <module>
   #    import weeutil.weeutil
   #ImportError: No module named weeutil


    import weewx
    import configobj

    weewx.debug = 1
    syslog.openlog('rsyncupload', syslog.LOG_PID|syslog.LOG_CONS)
    syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

    if len(sys.argv) < 2:
        print """Usage: rsyncupload.py path-to-configuration-file [path-to-be-rsync'd]"""
        sys.exit(weewx.CMD_ERROR)

    try:
        config_dict = configobj.ConfigObj(sys.argv[1], file_error=True)
    except IOError:
        print "Unable to open configuration file ", sys.argv[1]
        raise

    if len(sys.argv) == 2:
        try:
            rsync_dir = os.path.join(config_dict['WEEWX_ROOT'],
                                     config_dict['StdReport']['HTML_ROOT'])
        except KeyError:
            print "No HTML_ROOT in configuration dictionary."
            sys.exit(1)
    else:
        rsync_dir = sys.argv[2]

    rsync_upload = RsyncUpload(rsync_dir, **config_dict['StdReport']['RSYNC'])
    rsync_upload.run()
