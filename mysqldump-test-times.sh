#!/bin/sh
date
#1+36=37
#26+15=41
 $(/usr/bin/mysqldump -uroot -ph0whigh -hlocalhost -q weatherpi  archive  > /tmp/deletethis )
date
#24+13=37
#45+47=93
$(/usr/bin/mysqldump -uroot -ph0whigh -hlocalhost -q weatherpi  archive  -q > /tmp/deletethis)
date
#13+35=48
  $(/usr/bin/mysqldump -uroot -ph0whigh -hlocalhost -q weatherpi  archive --skip-opt > /tmp/deletethis)
date
#57+1=58
#25+19=44
  $(/usr/bin/mysqldump -uroot -ph0whigh -hlocalhost -q weatherpi  archive -q --skip-opt > /tmp/deletethis)
date
#51+03=54
  $(/usr/bin/mysqldump -uroot -ph0whigh -hlocalhost -q weatherpi  archive --skip-opt --single-transaction > /tmp/deletethis)
date
#45
#44
  $(/usr/bin/mysqldump -uroot -ph0whigh -hlocalhost -q weatherpi  archive -q --skip-opt --single-transaction > /tmp/deletethis)
date

exit 0
READ WRITE : :root@masterofpis:~
09:32 PM $ bash /home/pi/bin/mysqldump-test-times.sh                                                                                                                                                                
Sunday 11 June  21:32:59 AEST 2017
Sunday 11 June  21:33:36 AEST 2017
Sunday 11 June  21:34:13 AEST 2017
Sunday 11 June  21:35:01 AEST 2017
Sunday 11 June  21:35:46 AEST 2017
READ WRITE : :root@masterofpis:~
09:35 PM $ vim /home/pi/bin/mysqldump-test-times.sh                                                                                                                                                                 
READ WRITE : :root@masterofpis:~
09:40 PM $ bash /home/pi/bin/mysqldump-test-times.sh                                                                                                                                                                
Sunday 11 June  21:40:34 AEST 2017
Sunday 11 June  21:41:15 AEST 2017
Sunday 11 June  21:41:47 AEST 2017
Sunday 11 June  21:42:35 AEST 2017
Sunday 11 June  21:43:19 AEST 2017
Sunday 11 June  21:44:03 AEST 2017
Sunday 11 June  21:44:47 AEST 2017
READ WRITE : :root@masterofpis:~

