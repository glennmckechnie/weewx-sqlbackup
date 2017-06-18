# installer for MySQLBackup
# Copyright 2016 Matthew Wall
# Co-opted by Glenn McKechnie 2017
# Distributed under the terms of the GNU Public License (GPLv3)

from setup import ExtensionInstaller

def loader():
    return MySQLBackupInstaller()

class InfluxInstaller(ExtensionInstaller):
    def __init__(self):
        super(MySQLBackupInstaller, self).__init__(
            version="0.5",
            name='MySQLBackup',
            description='Partial backup of the MySQL weewx database',
            author="Glenn McKechnie",
            author_email="glenn.mckechnie@gmail.com",
            config={
                'StdReport': {
                    'MySQLBackup': {
                        'skin': 'mysqlbackup',
            files=[('bin/user', ['bin/user/mysqlbackup.py'])]
            )
