#!/usr/bin/env python3 -u
##########################################################################
##
##  Author:             Chris Wilkinson
##                      cmwilki@gmail.com
##  Date:               03 Nov 2015
##
##                      Converted to Python 3 on 16 June 2018
##
##  Goals:
##                      Fast enough to record 2 streams from HDhomerun
##                      to external HD mounted on a BeagleBone Black
##
##                      Dynamic update of recording configuration
##                      (separate python script / cPickle file)
##
##                      Detection of recordings that have errors with
##                      automated restarts
##
##                      Different levels of debug
##
##########################################################################
import os
import sys
import time
import datetime
import subprocess
import getopt
import stat
import json
import math
import random
import string
import pprint

CFG_HDHRID         = '1052A5C2'
CFG_Num_Tuners     = 2
CFG_Dev_Check_Time = 60  ## How often to check to make sure the HDhomerun device is still alive on the network
CFG_Rec_Check_Time = 15  ## How often to check to make sure an active recording is working
CFG_OS_cmd         = '/home/cmwilki/libhdhomerun/hdhomerun_config'
CFG_Save_Dir       = '/mnt/nas/TV/'
CFG_LOCKKEY        = str(random.SystemRandom().choice(list(range(1,10)))) + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(7))

CFG_CHANNELS       = {'ABC':{'name':'2.1 WSB-HD','channel':39,'subchannel':1},
                      'MeTV':{'name':'2.2 Me TV','channel':39,'subchannel':2},
                      'FOX':{'name':'5.1 WAGA-HD','channel':27,'subchannel':3},
                      'CBS':{'name':'46.1 WGCL-TV','channel':19,'subchannel':3},
                      'GRIT':{'name':'46.3 WGCLSD2','channel':19,'subchannel':5},
                      'NBC':{'name':'11.1 WXIA-TV','channel':10,'subchannel':3},
                      'MyTV':{'name':'36.1 WATL-DT','channel':25,'subchannel':3},
                      'Bounce':{'name':'36.2 Bounce','channel':25,'subchannel':4},
                      'UNIV':{'name':'11.3 WXIA-JN','channel':10,'subchannel':5},
                      'ION':{'name':'14.1 ION','channel':31,'subchannel':3},
                      'CW':{'name':'69.1 WUPA-HD','channel':43,'subchannel':1},
                      'PeachTreeTV':{'name':'17.1 WPCH-DT','channel':20,'subchannel':3},
                      'PBS':{'name':'30.1 WPBA-HD','channel':21,'subchannel':3},
                      'Univision':{'name':'34.1 WUVG-DT','channel':48,'subchannel':1}}

def usage():
	print('Usage:' , sys.argv[0] , '[options]')
	print('Description: Record TV from HDhomerun')
	print('')
	print('Options:')
	print('-h  --help			Show this helpful information')
	print('-c  --config=[file]	Specifies the recording configuration filename (required argument)')
	print('-d  --debug[=level]	print debug info')
	print('')


def changeChannel(tuner,channel,subchannel):
	cmd = [CFG_OS_cmd,CFG_HDHRID,'set','/tuner' + str(tuner) + '/lockkey',CFG_LOCKKEY]
	resp = subprocess.call(cmd)
	if resp != 0:
		print('ERROR:   FAILED TO SET LOCKKEY ON TUNER %d TO %s' %(tuner,CFG_LOCKKEY))
		return False

	cmd = [CFG_OS_cmd,CFG_HDHRID,'key',CFG_LOCKKEY,'set','/tuner' + str(tuner) + '/channel',str(channel)]
	resp = subprocess.call(cmd)
	if resp != 0:
		print('ERROR:   FAILED TO CHANGE CHANNEL ON TUNDER %d TO %d' %(tuner,channel))
		return False

	cmd = [CFG_OS_cmd,CFG_HDHRID,'key',CFG_LOCKKEY,'set','/tuner' + str(tuner) + '/program',str(subchannel)]
	resp = subprocess.call(cmd)
	if resp != 0:
		print('ERROR:   FAILED TO CHANGE SUB-CHANNEL ON TUNDER %d TO %d' %(tuner,subchannel))
		return False

	return True


def saveChannel(tuner,title,filename_prefix):
	if not os.path.exists(CFG_Save_Dir + title + '/'):
		try:
			os.mkdir(CFG_Save_Dir + title + '/')
		except Exception as diag:
			print('ERROR:   FAILED TO CREATE DESTINATION DIRECTORY %s' %(CFG_Save_Dir + title + '/'))
			return False

	filename = CFG_Save_Dir + title + '/' + filename_prefix + '_' + time.strftime('%d%b%Y') + '.ts'

	## Make sure we don't overwrite any previous recordings of this show (in case of device reboot)
	attempt = 1
	while os.path.exists(filename) and attempt < 100:
		filename = CFG_Save_Dir + title + '/' + filename_prefix + '_' + time.strftime('%d%b%Y') + '_%02d.ts' %(attempt)
		attempt += 1

	cmd = [CFG_OS_cmd,CFG_HDHRID,'key',CFG_LOCKKEY,'save','/tuner' + str(tuner),filename]

	DEVNULL = open(os.devnull,'wb')
	p = subprocess.Popen(cmd,stdout=DEVNULL,stderr=DEVNULL)
	if p.pid == 0:
		print('ERROR:   FAILED TO SAVE CHANNEL TO %s' %(CFG_Save_Dir))
		return False

	return (p,filename)


def killRecording(recording):
	recording['status'] = None
	recording['handle'].kill()

	cmd = [CFG_OS_cmd,CFG_HDHRID,'key',CFG_LOCKKEY,'set','/tuner' + str(recording['tuner']) + '/lockkey','none']

	resp = subprocess.call(cmd)
	if resp != 0:
		print('ERROR:   FAILED TO REMOVE LOCK KEY ON TUNER %d' %(recording['tuner']))

	del(recording['handle'])
	del(recording['tuner'])
	del(recording['filename'])
	del(recording['lastCheck'])


def findOpenTuner(debug):
	avail_tuners = list(range(CFG_Num_Tuners))
	for name in CFG_RECORDINGS:
		if 'tuner' in CFG_RECORDINGS[name] and CFG_RECORDINGS[name]['tuner'] in avail_tuners:
			if debug:
				print('INFO:    TUNER %d IS CURRENTLY BUSY' %(CFG_RECORDINGS[name]['tuner']))
			avail_tuners.remove(CFG_RECORDINGS[name]['tuner'])
	return avail_tuners


def detectDevice(debug):
	cmd = [CFG_OS_cmd,'discover']
	p = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
	stdout,stderr = p.communicate()
	if debug > 1:
		print(stdout, end=' ')

	return str(stdout).find(CFG_HDHRID)


def readRecordingConfig(config_filename):
	with open(config_filename,'r') as fptr:
		recordings = json.load(fptr)

	return recordings


def updateUnixTimes(recordings,debug):
	global CFG_Dev_Check_Time
	for name in list(recordings.keys()):

		## Check to make sure the status keyword exists
		if 'status' not in recordings[name]:
			recordings[name]['status'] = None

		## Check to make sure the unix start/stop time keywords exists
		if 'unix_start_time' not in recordings[name] or 'unix_stop_time' not in recordings[name]:
			recordings[name]['unix_start_time'] = 0
			recordings[name]['unix_stop_time'] = 0

		## If current time < stop time, then no need to update the unix start/stop time
		if time.time() < recordings[name]['unix_stop_time'] + CFG_Dev_Check_Time:
			continue

		today_midnight = datetime.datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)

		if debug > 2:
			print('INFO:    updateUnixTimes(), tonight_midnight = ', today_midnight)

		## Find next day to record based on day of week
		num_days = 0
		while num_days < 8:
			if debug > 2:
				print('INFO:    updateUnixTimes(), num_days = %d' %(num_days))
			test_day_datetime = today_midnight + datetime.timedelta(seconds=86400 * num_days)
			test_day = test_day_datetime.strftime('%a')

			if debug > 2:
				print('INFO:    updateUnixTimes(), test_day = %s' %(test_day))

			if test_day in recordings[name]['day'] or test_day == recordings[name]['day']:
				#print 'INFO:    updateUnixTimes(), Day %s matched requested day' %(test_day)

				## Calculate theoretical start/end time to see if this time has already passed
				test_start_time = int(test_day_datetime.replace(hour= int(recordings[name]['start'][:2]),minute=int(recordings[name]['start'][-2:])).strftime('%s'))
				test_end_time = int(test_day_datetime.replace(hour= int(recordings[name]['end'][:2]),minute=int(recordings[name]['end'][-2:])).strftime('%s'))

				## This recording spans midnight; adjust end time accordingly
				if test_end_time < test_start_time:
					test_end_time += 86400

				if debug > 2:
					print('INFO:    updateUnixTimes(), test_start_time = %d; test_end_time = %d; now = %d' %(test_start_time,test_end_time,int(time.time())))

				if time.time() < test_end_time:
					recordings[name]['unix_start_time'] = test_start_time
					recordings[name]['unix_stop_time'] = test_end_time

					if debug > 0:
						print('INFO:    %s SCHEDULED FOR %s -> %s' %(name,\
						time.strftime('%a, %b %d %Y %I:%M %p %Z',time.localtime(recordings[name]['unix_start_time'])),\
						time.strftime('%a, %b %d %Y %I:%M %p %Z',time.localtime(recordings[name]['unix_stop_time']))))
						print('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')
					break
			num_days += 1


if __name__ == '__main__':
	debug = 0
	confg_filename = None

	#################################################################
	## Get all of the command line options
	#################################################################
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:d:', ['help', 'config=','debug='])
	except getopt.GetoptError as err:
		# print help information and exit:
		print(str(err)) # will print something like "option -a not recognized"
		usage()
		sys.exit(2)

	for opt, arg in opts:
		if opt in ("-h", "--help"):
			usage()
			sys.exit()
		elif opt in ('-d', '--debug'):
			debug = int(arg)
		elif opt in ('-c', '--config'):
			confg_filename = arg
		else:
			assert False, 'unhandled option'

	if not confg_filename:
		print('ERROR:   FAILED TO SPECIFY A RECORDING CONFIGURATION FILE')
		sys.exit(3)

	#################################################################
	## Read the initial recording configuration
	#################################################################
	if debug > 2:
		print('INFO:    Attempting to open configuration file ' + confg_filename)

	CFG_RECORDINGS = readRecordingConfig(confg_filename)
	updateUnixTimes(CFG_RECORDINGS,debug)

	if debug > 2:
		pprint.pprint(CFG_RECORDINGS)

	#################################################################
	## Make sure the HDhomerun device is on the network
	#################################################################
	while True:
		if detectDevice(debug) < 0:
			print('ERROR:   FAILED TO DETECT HD HOME RUN DEVICE %s' %(CFG_HDHRID))
			print('NOTICE:  SLEEPING 10 SECONDS')
			time.sleep(10)
		else:
			print('INFO:    FOUND HD HOMERUN DEVICE %s' %(CFG_HDHRID))
			lastDeviceDetectTime = time.time()
			break
	print('INFO:    CFG_LOCKKEY IS %s' %(CFG_LOCKKEY))

	#################################################################
	## The main body of the process.  Loop forever, checking the
	## status of the HDhomerun device, active recordings, and
	## re-reading the recording configuration file periodically
	#################################################################
	while True:
		ymd  = time.strftime('%Y-%m-%d')
		day  = time.strftime('%a')
		hour = time.strftime('%H')
		mins = time.strftime('%M')

		for name in CFG_RECORDINGS:
			recording = CFG_RECORDINGS[name]

			if debug > 2:
				print('INFO:    RECORD DURATION FOR %s IS %02d:%02d HOURS' %(\
				name,math.floor((recording['unix_stop_time'] - recording['unix_start_time']) / 3600),math.fmod((recording['unix_stop_time'] - recording['unix_start_time']),3600) / 60))

			#################################################################
			## Check to see if we need to start recording this show
			#################################################################
			if time.time() > recording['unix_start_time'] and time.time() < recording['unix_stop_time'] and type(CFG_RECORDINGS[name]['status']) == type(None):
				if debug:
					print('INFO:    ATTEMPTING TO RECORD %s' %(name))

				## Find an open tuner on the HDhomerun device (based on our internal tracking of what
				## we're currently recording)
				avail_tuners = findOpenTuner(debug)
				if len(avail_tuners) == 0:
					print('ERROR:   FAILED TO FIND AN OPEN TUNER TO RECORD %s' %(name))
					continue
				else:
					## Pick the first available tuner
					tuner = avail_tuners[0]
					if debug:
						print('INFO:    ASSIGNING %s TO TUNER %d' %(name,tuner))

				#################################################################
				## Determine channel information and change the assigned tuner
				## to the proper channel
				#################################################################
				channel = CFG_CHANNELS[CFG_RECORDINGS[name]['channel_name']]['channel']
				subchannel = CFG_CHANNELS[CFG_RECORDINGS[name]['channel_name']]['subchannel']

				forceCheck = False
				if not changeChannel(tuner,channel,subchannel):
					print('WARNING: FAILED TO SET CHANNEL TO RECORD %s ON TUNER %d' %(name,tuner))
					if len(avail_tuners) > 1:
						tuner = avail_tuners[1]
						if debug:
							print('INFO:    ASSIGNING %s TO TUNER %d' %(name,tuner))
						if not changeChannel(tuner,channel,subchannel):
							forceCheck = True
					else:
						forceCheck = True

				if forceCheck:
					del(forceCheck)
					## Force a device check at the end of this while loop
					lastDeviceDetectTime = time.time() - (2 * CFG_Dev_Check_Time)
					break

				#################################################################
				## Start recording the stream to disk
				#################################################################
				proc_handle,filename = saveChannel(tuner,name,recording['filename_prefix'])
				if not proc_handle:
					print('WARNING: FAILED TO START RECORDING %s ON TUNER %d' %(name,tuner))

					## Force a device check at the end of this while loop
					lastDeviceDetectTime = time.time() - (2 * CFG_Dev_Check_Time)
					break

				CFG_RECORDINGS[name]['status']    = 'active'
				CFG_RECORDINGS[name]['handle']    = proc_handle
				CFG_RECORDINGS[name]['tuner']     = tuner
				CFG_RECORDINGS[name]['filename']  = filename
				CFG_RECORDINGS[name]['lastCheck'] = time.time()
				print('INFO:    STARTED RECORDING %s TO %s' %(name,CFG_RECORDINGS[name]['filename']))

			#################################################################
			## Check to make sure an active recording is working properly or
			## if it needs to be stopped
			#################################################################
			elif recording['status'] == 'active':
				if time.time() >= recording['unix_stop_time']:
					print('INFO:    ENDING RECORDING OF %s' %(name))
					killRecording(CFG_RECORDINGS[name])

				elif (time.time() - recording['lastCheck']) > CFG_Rec_Check_Time:
					## Check to make sure the recording file is growing
					if not os.path.exists(CFG_RECORDINGS[name]['filename']):
						print('ERROR:   FAILED TO FIND FILE %s' %(CFG_RECORDINGS[name]['filename']))
						print('NOTICE:  KILLING RECORDING FOR %s' %(name))

						## Kill the recording now; the next iteration will restart it
						killRecording(CFG_RECORDINGS[name])
						continue

					initial_size = os.stat(CFG_RECORDINGS[name]['filename'])[stat.ST_SIZE]
					time.sleep(1.5)

					if os.stat(CFG_RECORDINGS[name]['filename'])[stat.ST_SIZE] == initial_size:
						print('ERROR:   FAILED TO DETECT GROWING FILE %s' %(CFG_RECORDINGS[name]['filename']))
						print('NOTICE:  KILLING RECORDING FOR %s' %(name))

						## Kill the recording now; the next iteration will restart it
						killRecording(CFG_RECORDINGS[name])

					else:
						CFG_RECORDINGS[name]['lastCheck'] = time.time()

			elif debug > 2:
				print('NOTICE:  NOTHING TO DO FOR PROGRAM %s' %(name))

		#################################################################
		##  Do some housekeeping every CFG_Dev_Check_Time seconds
		#################################################################
		if (time.time() - lastDeviceDetectTime) >= CFG_Dev_Check_Time:

			#################################################################
			## Find new recording configurations
			#################################################################
			tmp = readRecordingConfig(confg_filename)
			for name in tmp:
				## If we already have this recording in our list, check to see if the
				## configuration is different.  If so, replace it's configuration
				## with whatever is in the updated configuration file
				if name in list(CFG_RECORDINGS.keys()):
					if not CFG_RECORDINGS[name]['status'] and (CFG_RECORDINGS[name]['start'] != tmp[name]['start'] or CFG_RECORDINGS[name]['end'] != tmp[name]['end'] or CFG_RECORDINGS[name]['day'] != tmp[name]['day']):
						print('NOTICE:  MODIFYING RECORDING INFORMATION FOR %s' %(name))

						if CFG_RECORDINGS[name]['status']:
							tmp[name]['status']    = 'active'
							tmp[name]['handle']    = CFG_RECORDINGS[name]['handle']
							tmp[name]['handle']    = CFG_RECORDINGS[name]['tuner']
							tmp[name]['filename']  = CFG_RECORDINGS[name]['filename']
							tmp[name]['lastCheck'] = CFG_RECORDINGS[name]['lastCheck']
						else:
							tmp[name]['status'] = None

						CFG_RECORDINGS[name] = tmp[name]

						if CFG_RECORDINGS[name]['status']:
							updateUnixTimes(CFG_RECORDINGS,0)

							if time.time() < CFG_RECORDINGS[name]['unix_start_time'] or time.time() > CFG_RECORDINGS[name]['unix_stop_time']:
								print('NOTICE:  %s WAS ACTIVELY RECORDING.  KILLING RECORDING NOW' %(name))
								killRecording(CFG_RECORDINGS[name])
				else:
					## This is a new entry
					print('INFO:    ADDING NEW RECORDING INFORMATION FOR %s' %(name))
					CFG_RECORDINGS[name] = tmp[name]

			#################################################################
			## Remove unused recording configurations.  Kill the recording if
			## it's actively recording
			#################################################################
			del_list = []
			for name in CFG_RECORDINGS:
				if name not in list(tmp.keys()):
					print('NOTICE:  DELETING RECORDING CONFIGURATION FOR %s' %(name))

					## If this is an active recording, kill the recording now
					if CFG_RECORDINGS[name]['status']:
						print('NOTICE:  WAS ACTIVELY RECORDING.  KILLING RECORDING NOW' %(name))
						killRecording(CFG_RECORDINGS[name])

					## Add the show to the deletion list
					del_list.append(name)

			for name in del_list:
				del(CFG_RECORDINGS[name])

			updateUnixTimes(CFG_RECORDINGS,1 if debug > 1 else 0)

			if debug > 2:
				pprint.pprint(CFG_RECORDINGS)

			#################################################################
			## Make sure the device is STILL on the network
			################################################################
			if detectDevice(debug) < 0:
				print('ERROR:   FAILED TO DETECT HD HOME RUN DEVICE %s' %(CFG_HDHRID))

				## Reset all of the active recordings to off - the device has crapped itself out
				for name in CFG_RECORDINGS:
					if 'handle' in CFG_RECORDINGS[name] and type(CFG_RECORDINGS[name]['handle']) != type(None):
						print('NOTICE:  WAS ACTIVELY RECORDING.  KILLING RECORDING NOW' %(name))
						killRecording(CFG_RECORDINGS[name])

				## Wait forever until the device comes back online before proceeding
				while detectDevice(debug) < 0:
					print('ERROR:   FAILED TO DETECT HD HOME RUN DEVICE %s' %(CFG_HDHRID))
					time.sleep(10)
				print('INFO:    HD HOME RUN DEVICE %s IS BACK ONLINE!' %(CFG_HDHRID))

			else:
				## HDhomerun device seems to be OK!
				lastDeviceDetectTime = time.time()
				if debug:
					print('INFO:    HD HOMERUN DEVICE %s IS STILL ALIVE' %(CFG_HDHRID))

		time.sleep(1)

