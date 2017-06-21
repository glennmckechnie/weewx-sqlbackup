# installer for SqlBackup
# Copyright 2016 Matthew Wall
# Co-opted by Glenn McKechnie 2017
# Distributed under the terms of the GNU Public License (GPLv3)

from setup import ExtensionInstaller

def loader():
    return SqlBackupInstaller()

class SqlBackupInstaller(ExtensionInstaller):
    def __init__(self):
        super(SqlBackupInstaller, self).__init__(
            version="0.3",
            name='sqlbackup',
            description='Use mysqldump or .dump to create partial backups of the '
                        'mysql weewx database, or full backups of the sqlite databases',
            author="Glenn McKechnie",
            author_email="glenn.mckechnie@gmail.com",
            config={
                'StdReport': {
                    'sqlbackup': {
                        'skin': 'sqlbackup'}}},
            files=[('bin/user', ['bin/user/sqlbackup.py']),
                   ('skins/sqlbackup', ['skins/sqlbackup/skin.conf',
                    'skins/sqlbackup/sqlbackup.html.tmpl',
                    'skins/sqlbackup/sqlbackup.inc',
                    'skins/sqlbackup/sqlbackupREADME.html'])
                  ]
        )
