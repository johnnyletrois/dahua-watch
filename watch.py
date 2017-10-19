#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import socket
import pycurl
import time
import shlex
import subprocess
import paho.mqtt.client as mqtt

ALARM_DELAY = 30

#PLAY_TEMPLATE = "gst-launch-1.0 playbin uri=\"rtsp://{user}:{pass}@{host}:554/cam/realmonitor?channel=1&subtype=2\" latency=300000000 audio-sink=\"autoaudiosink sync=false\""
URL_TEMPLATE = "http://{host}:{port}/cgi-bin/eventManager.cgi?action=attach&codes=%5B{events}%5D"

CAMERAS = [
	{
		"host": "CAM_1_IP",
		"port": 80,
		"user": "USERNAME",
		"pass": "PASSWORD",
		"events": "CrossLineDetection"
	},
	{
		"host": "CAM_2_IP",
		"port": 80,
		"user": "USER",
		"pass": "PASSWORD",
		"events": "CrossLineDetection"
	},
	{
		"host": "CAM_3_IP",
		"port": 80,
		"user": "USER",
		"pass": "PASSWORD",
		"events": "CrossLineDetection"
	}
]

class DahuaCamera():
	def __init__(self, master, index, camera):
		self.Master = master
		self.Index = index
		self.Camera = camera
		self.CurlObj = None
		self.Connected = None
		self.Reconnect = None

		self.Alarm = dict({
			"Active": None,
			"Last": None
		})
		#self.Player = None

	#def StartPlayer(self):
	#	if self.Player:
	#		return

	#	print("[{0}] StartPlayer()".format(self.Index))
	#	self.Master.OnStartPlayer()

	#	Command = PLAY_TEMPLATE.format(**self.Camera)
	#	Args = shlex.split(Command)
	#	self.Player = subprocess.Popen(Args,
	#					stdin = subprocess.DEVNULL,
	#					stdout = subprocess.DEVNULL,
	#					stderr = subprocess.DEVNULL)

	#def StopPlayer(self):
	#	if not self.Player:
	#		return

	#	print("[{0}] StopPlayer()".format(self.Index))
	#	self.Player.kill()
	#	self.Player.wait()
	#	self.Player = None
	#	self.Master.OnStopPlayer()
		
	def SensorOn(self):
		sensorurl = ("home-assistant/cameras/{0}/IVS").format(self.Index);
		client = mqtt.Client()
		client.connect("MQTT_BROKER_IP",1883,60)
		#client.publish("home-assistant/cameras/garage/motion", "ON");
		#client.publish("home-assistant/cameras/garage/IVS", "ON");
		client.publish(sensorurl, "ON");
		client.disconnect();
		
	def SensorOff(self):
		sensorurl = ("home-assistant/cameras/{0}/IVS").format(self.Index);
		client = mqtt.Client()
		client.connect("MQTT_BROKER_IP",1883,60)
		#client.publish("home-assistant/cameras/garage/motion", "OFF");
		#client.publish("home-assistant/cameras/garage/IVS", "OFF");
		client.publish(sensorurl, "OFF");
		client.disconnect();

	def OnAlarm(self, State):
		#print("[{0}] Alarm triggered! -> {1}".format(self.Index, "ON" if State else "OFF"))

		if State:
			self.SensorOn()
			print("Motion Detected")
		else:
			self.SensorOff()
			print("Motion Stopped")

	def OnConnect(self):
		print("[{0}] OnConnect()".format(self.Index))
		self.Connected = True

	def OnDisconnect(self, reason):
		print("[{0}] OnDisconnect({1})".format(self.Index, reason))
		self.Connected = False
	#	self.StopPlayer()

	def OnTimer(self):
		#if self.Player:
		#	self.Player.poll()
		#	if self.Player.returncode != None:
		#		self.StopPlayer()

		if self.Alarm["Active"] == False and time.time() - self.Alarm["Last"] > ALARM_DELAY:
			self.Alarm["Active"] = None
			self.Alarm["Last"] = None

			self.OnAlarm(False)

	def OnReceive(self, data):
		Data = data.decode("utf-8", errors="ignore")
		#print("[{0}]: {1}".format(self.Index, Data))

		for Line in Data.split("\r\n"):
			if Line == "HTTP/1.1 200 OK":
				self.OnConnect()

			if not Line.startswith("Code="):
				continue

			Alarm = dict()
			for KeyValue in Line.split(';'):
				Key, Value = KeyValue.split('=')
				Alarm[Key] = Value

			self.ParseAlarm(Alarm)

	def ParseAlarm(self, Alarm):
		print("[{0}] ParseAlarm({1})".format(self.Index, Alarm))

		if Alarm["Code"] not in self.Camera["events"].split(','):
			return

		if Alarm["action"] == "Start":
			if self.Alarm["Active"] == None:
				self.OnAlarm(True)
			self.Alarm["Active"] = True
		elif Alarm["action"] == "Stop":
			self.Alarm["Active"] = False
			self.Alarm["Last"] = time.time()


class DahuaMaster():
	def __init__(self):
		self.Cameras = []
		self.NumActivePlayers = 0

		self.CurlMultiObj = pycurl.CurlMulti()
		self.NumCurlObjs = 0

		for Index, Camera in enumerate(CAMERAS):
			DahuaCam = DahuaCamera(self, Index, Camera)
			self.Cameras.append(DahuaCam)
			Url = URL_TEMPLATE.format(**Camera)

			CurlObj = pycurl.Curl()
			DahuaCam.CurlObj = CurlObj

			CurlObj.setopt(pycurl.URL, Url)
			CurlObj.setopt(pycurl.CONNECTTIMEOUT, 30)
			CurlObj.setopt(pycurl.TCP_KEEPALIVE, 1)
			CurlObj.setopt(pycurl.TCP_KEEPIDLE, 30)
			CurlObj.setopt(pycurl.TCP_KEEPINTVL, 15)
			CurlObj.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_DIGEST)
			CurlObj.setopt(pycurl.USERPWD, "%s:%s" % (Camera["user"], Camera["pass"]))
			CurlObj.setopt(pycurl.WRITEFUNCTION, DahuaCam.OnReceive)

			self.CurlMultiObj.add_handle(CurlObj)
			self.NumCurlObjs += 1

	#def OnStartPlayer(self):
	#	self.NumActivePlayers += 1
	#	if self.NumActivePlayers == 1:
	#		subprocess.run(["xset", "dpms", "force", "on"])

	#def OnStopPlayer(self):
	#	self.NumActivePlayers -= 1
	#	if self.NumActivePlayers == 0:
	#		subprocess.run(["xset", "dpms", "force", "off"])

	def OnTimer(self):
		for Camera in self.Cameras:
			Camera.OnTimer()

	def Run(self, timeout = 1.0):
		while 1:
			Ret, NumHandles = self.CurlMultiObj.perform()
			if Ret != pycurl.E_CALL_MULTI_PERFORM:
				break

		while 1:
			Ret = self.CurlMultiObj.select(timeout)
			if Ret == -1:
				self.OnTimer()
				continue

			while 1:
				Ret, NumHandles = self.CurlMultiObj.perform()

				if NumHandles != self.NumCurlObjs:
					_, Success, Error = self.CurlMultiObj.info_read()

					for CurlObj in Success:
						Camera = next(filter(lambda x: x.CurlObj == CurlObj, self.Cameras))
						if Camera.Reconnect:
							continue

						Camera.OnDisconnect("Success")
						Camera.Reconnect = time.time() + 5

					for CurlObj, ErrorNo, ErrorStr in Error:
						Camera = next(filter(lambda x: x.CurlObj == CurlObj, self.Cameras))
						if Camera.Reconnect:
							continue

						Camera.OnDisconnect("{0} ({1})".format(ErrorStr, ErrorNo))
						Camera.Reconnect = time.time() + 5

					for Camera in self.Cameras:
						if Camera.Reconnect and Camera.Reconnect < time.time():
							self.CurlMultiObj.remove_handle(Camera.CurlObj)
							self.CurlMultiObj.add_handle(Camera.CurlObj)
							Camera.Reconnect = None

				if Ret != pycurl.E_CALL_MULTI_PERFORM:
					break

			self.OnTimer()

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)

	Master = DahuaMaster()
	Master.Run()
