#!/usr/bin/python3

import sys
import json
import pprint

CFG_RECORDINGS = {'CBS Nightly News':{'day':['Mon','Tue','Wed','Thu','Fri'],'start':'18:29','end':'19:01','channel_name':'CBS','filename_prefix':'CBSNightlyNews'},
                  'The Late Late Show':{'day':['Tue','Wed','Thu','Fri','Sat'],'start':'00:36','end':'01:40','channel_name':'CBS','filename_prefix':'LateLateShow'},
                  'The Tonight Show':{'day':['Mon','Tue','Wed','Thu','Fri'],'start':'23:34','end':'00:38','channel_name':'NBC','filename_prefix':'TheTonightShow'},
                  'CBS This Morning':{'day':['Mon','Tue','Wed','Thu','Fri'],'start':'06:59','end':'07:23','channel_name':'CBS','filename_prefix':'CBS_ThisMorning'},

                  ## Sunday stuff
                  '60 Minutes':{'day':'Sun','start':'18:59','end':'21:01','channel_name':'CBS','filename_prefix':'60Minutes'},
#                  'Madam Secretary':{'day':'Sun','start':'21:59','end':'23:01','channel_name':'CBS','filename_prefix':'MadamSecretary'},
#                  'Brooklyn Nine Nine':{'day':'Sun','start':'20:29','end':'21:01','channel_name':'FOX','filename_prefix':'BrooklynNineNine'},
#                  'Family Guy':{'day':'Sun','start':'20:59','end':'21:31','channel_name':'FOX','filename_prefix':'FamilyGuy'},

                  ## Monday stuff
#                  'Kevin Can Wait':{'day':'Mon','start':'20:59','end':'21:31','channel_name':'CBS','filename_prefix':'KevinCanWait'},
                  'Elementary':{'day':'Mon','start':'21:59','end':'23:01','channel_name':'CBS','filename_prefix':'Elementary'},

                  ## Tuesday
#                  'LA to Vegas':{'day':'Tue','start':'20:59','end':'21:31','channel_name':'FOX','filename_prefix':'LA2Vegas'},
#                  'NCIS':{'day':'Tue','start':'19:59','end':'21:01','channel_name':'CBS','filename_prefix':'NCIS'},
#                  'Bull':{'day':'Tue','start':'20:59','end':'22:01','channel_name':'CBS','filename_prefix':'Bull'},

                  ## Wednesday
#                  'The Goldbergs':{'day':'Wed','start':'19:59','end':'20:32','channel_name':'ABC','filename_prefix':'TheGoldbergs'},
                  'Master Chef':{'day':'Fri','start':'19:59','end':'22:01','channel_name':'FOX','filename_prefix':'MasterChef'},

                  ## Thursday
#                  'Big Bang Theory':{'day':'Thu','start':'19:59','end':'20:32','channel_name':'CBS','filename_prefix':'BigBangTheory'},
#                  'The Mick':{'day':'Tue','start':'21:29','end':'22:01','channel_name':'FOX','filename_prefix':'TheMick'},
#                  'The Orville':{'day':'Thu','start':'21:00','end':'22:02','channel_name':'FOX','filename_prefix':'TheOrville'},

                  ## Friday
#                  'Hawaii Five-O':{'day':'Fri','start':'20:59','end':'22:00','channel_name':'CBS','filename_prefix':'HawaiiFiveO'},
#                  'Blue Bloods':{'day':'Fri','start':'22:00','end':'23:01','channel_name':'CBS','filename_prefix':'BlueBloods'},
#                  'Master Chef Junior':{'day':'Fri','start':'19:59','end':'22:01','channel_name':'FOX','filename_prefix':'MasterChefJunior'},

                  ## Saturday
#                  '48 Hours':{'day':'Sat','start':'21:59','end':'23:01','channel_name':'CBS','filename_prefix':'48Hours'},
#                  'Saturday Night Live':{'day':'Sat','start':'23:28','end':'01:02','channel_name':'NBC','filename_prefix':'SNL'}}
}

fptr = open(sys.argv[1],'w')
json.dump(CFG_RECORDINGS,fptr)
fptr.close()
