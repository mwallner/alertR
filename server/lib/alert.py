#!/usr/bin/python2

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import threading
import os
import time
import logging
import json
from server import AsynchronousSender
from localObjects import SensorAlert, SensorDataType


# this class is woken up if a sensor alert is received
# and executes all necessary steps
class SensorAlertExecuter(threading.Thread):

	def __init__(self, globalData):
		threading.Thread.__init__(self)

		# get global configured data
		self.globalData = globalData
		self.logger = self.globalData.logger
		self.managerUpdateExecuter = self.globalData.managerUpdateExecuter
		self.storage = self.globalData.storage
		self.alertLevels = self.globalData.alertLevels
		self.serverSessions = self.globalData.serverSessions

		# file nme of this file (used for logging)
		self.fileName = os.path.basename(__file__)

		# create an event that is used to wake this thread up
		# and reacte on sensor alert
		self.sensorAlertEvent = threading.Event()
		self.sensorAlertEvent.clear()

		# set exit flag as false
		self.exitFlag = False


	# this internal function recursively updates all values of
	# the rule elements it processes received sensor alerts,
	# updates the timeWhenTriggered values and sets the rule elements
	# to triggered or not triggered respectively
	def _updateRuleValuesRecursively(self, sensorAlertList,
		currentRuleElement):

		# check if rule element is of type "sensor"
		# => update values of rule
		if currentRuleElement.type == "sensor":

			# get node id of sensor client
			ruleNodeId = self.storage.getNodeId(
				currentRuleElement.element.username)
			if ruleNodeId is None:
				self.logger.error("[%s]: Not able to get " % self.fileName
					+ "node id for sensor to update rule.")
				return False

			# get sensor id of sensor
			ruleSensorId = self.storage.getSensorId(ruleNodeId,
				currentRuleElement.element.remoteSensorId)
			if ruleSensorId is None:
				self.logger.error("[%s]: Not able to get " % self.fileName
					+ "sensor id for sensor to update rule.")
				return False

			# update sensor rule element (set as not triggered)
			# if sensor does not count as triggered
			# => unset triggered flag
			utcTimestamp = int(time.time())
			if (((currentRuleElement.timeWhenTriggered
				+ currentRuleElement.timeTriggeredFor) < utcTimestamp)
				and currentRuleElement.triggered):

				self.logger.debug("[%s]: Sensor " % self.fileName
					+ "with id '%d' does not count as triggered anymore."
					% ruleSensorId)

				currentRuleElement.triggered = False

			# update sensor rule values with current sensor alerts
			for sensorAlert in sensorAlertList:
				sensorAlertNodeId = sensorAlert[2]
				sensorAlertSensorId = sensorAlert[1]
				sensorAlertTimeReceived = sensorAlert[3]
				sensorAlertAlertDelay = sensorAlert[4]

				# check if received sensor alert is triggered by
				# the sensor of the rule
				if (sensorAlertNodeId == ruleNodeId
					and sensorAlertSensorId == ruleSensorId):

					self.logger.debug("[%s]: Found match " % self.fileName
						+ "for sensor with id '%d' and sensor in rule."
						% ruleSensorId)

					# checked if the received sensor alert
					# is newer than the stored time when triggered
					# => update time when triggered
					if ((sensorAlertTimeReceived + sensorAlertAlertDelay)
						> currentRuleElement.timeWhenTriggered):

						# check if an alert delay has to be considered
						utcTimestamp = int(time.time())
						if not ((utcTimestamp - sensorAlertTimeReceived)
							> sensorAlertAlertDelay):

							self.logger.debug("[%s]: Sensor alert "
								% self.fileName
								+ "for sensor with id '%d' still delayed for "
								% ruleSensorId
								+ "'%d' seconds."
								% (sensorAlertAlertDelay
								- (utcTimestamp - sensorAlertTimeReceived)))

							continue

						self.logger.debug("[%s]: New sensor "
							% self.fileName
							+ "alert for sensor with id '%d' received."
							% ruleSensorId)

						currentRuleElement.timeWhenTriggered = \
							sensorAlertTimeReceived + sensorAlertAlertDelay

						# check if sensor still counts as triggered
						# => set triggered flag
						if ((currentRuleElement.timeWhenTriggered
							+ currentRuleElement.timeTriggeredFor)
							> utcTimestamp):

							self.logger.debug("[%s]: Sensor "
								% self.fileName
								+ "with id '%d' counts as triggered."
								% ruleSensorId)

							currentRuleElement.triggered = True

						# if sensor does not count as triggered
						# => unset triggered flag
						else:

							self.logger.debug("[%s]: Sensor "
								% self.fileName
							+ "with id '%d' does not count as triggered."
							% ruleSensorId)

							currentRuleElement.triggered = False

		# check if rule element is of type "weekday"
		# => update values of rule according to the date
		elif currentRuleElement.type == "weekday":

			weekdayElement = currentRuleElement.element

			if weekdayElement.time == "local":

				# check if week day matches
				# => set rule element as triggered if it is not yet triggered
				if weekdayElement.weekday == time.localtime().tm_wday:

					# check if rule element is not triggered
					# => set as triggered
					if not currentRuleElement.triggered:

						self.logger.debug("[%s]: Week day "
							% self.fileName
							+ "with value '%d' for '%s' counts as triggered."
							% (weekdayElement.weekday, weekdayElement.time))

						utcTimestamp = int(time.time())
						currentRuleElement.timeWhenTriggered = utcTimestamp
						currentRuleElement.triggered = True

				# check if rule element is triggered
				# => set rule element as not triggered
				elif currentRuleElement.triggered:

					self.logger.debug("[%s]: Week day "
						% self.fileName
						+ "with value '%d' for '%s' no longer "
						% (weekdayElement.weekday, weekdayElement.time)
						+ "counts as triggered.")

					currentRuleElement.triggered = False

			elif weekdayElement.time == "utc":

				# check if week day matches
				# => set rule element as triggered if it is not yet triggered
				if weekdayElement.weekday == time.gmtime().tm_wday:

					# check if rule element is not triggered
					# => set as triggered
					if not currentRuleElement.triggered:

						self.logger.debug("[%s]: Week day "
							% self.fileName
							+ "with value '%d' for '%s' counts as triggered."
							% (weekdayElement.weekday, weekdayElement.time))

						utcTimestamp = int(time.time())
						currentRuleElement.timeWhenTriggered = utcTimestamp
						currentRuleElement.triggered = True

				# check if rule element is triggered
				# => set rule element as not triggered
				elif currentRuleElement.triggered:

					self.logger.debug("[%s]: Week day " % self.fileName
						+ "with value '%d' for '%s' no longer "
						% (weekdayElement.weekday, weekdayElement.time)
						+ "counts as triggered.")

					currentRuleElement.triggered = False

			else:
				self.logger.error("[%s]: No valid value for " % self.fileName
					+ "'time' attribute in weekday tag.")
				return False

		# check if rule element is of type "monthday"
		# => update values of rule according to the date
		elif currentRuleElement.type == "monthday":

			monthdayElement = currentRuleElement.element

			if monthdayElement.time == "local":

				# check if month day matches
				# => set rule element as triggered if it is not yet triggered
				if monthdayElement.monthday == time.localtime().tm_mday:

					# check if rule element is not triggered
					# => set as triggered
					if not currentRuleElement.triggered:

						self.logger.debug("[%s]: Month day " % self.fileName
							+ "with value '%d' for '%s' counts as triggered."
							% (monthdayElement.monthday, monthdayElement.time))

						utcTimestamp = int(time.time())
						currentRuleElement.timeWhenTriggered = utcTimestamp
						currentRuleElement.triggered = True

				# check if rule element is triggered
				# => set rule element as not triggered
				elif currentRuleElement.triggered:

					self.logger.debug("[%s]: Month day " % self.fileName
						+ "with value '%d' for '%s' no longer "
						% (monthdayElement.monthday, monthdayElement.time)
						+ "counts as triggered.")

					currentRuleElement.triggered = False

			elif monthdayElement.time == "utc":

				# check if month day matches
				# => set rule element as triggered if it is not yet triggered
				if monthdayElement.monthday == time.gmtime().tm_mday:

					# check if rule element is not triggered
					# => set as triggered
					if not currentRuleElement.triggered:

						self.logger.debug("[%s]: Month day " % self.fileName
							+ "with value '%d' for '%s' counts as triggered."
							% (monthdayElement.monthday, monthdayElement.time))

						utcTimestamp = int(time.time())
						currentRuleElement.timeWhenTriggered = utcTimestamp
						currentRuleElement.triggered = True

				# check if rule element is triggered
				# => set rule element as not triggered
				elif currentRuleElement.triggered:

					self.logger.debug("[%s]: Month day " % self.fileName
						+ "with value '%d' for '%s' no longer "
						% (monthdayElement.monthday, monthdayElement.time)
						+ "counts as triggered.")

					currentRuleElement.triggered = False

			else:
				self.logger.error("[%s]: No valid value for " % self.fileName
					+ "'time' attribute in monthday tag.")
				return False

		# check if rule element is of type "hour"
		# => update values of rule according to the date
		elif currentRuleElement.type == "hour":

			hourElement = currentRuleElement.element

			if hourElement.time == "local":

				# check if the current hour lies between the start/end
				# of the hour rule element
				# => set rule element as triggered if it is not yet triggered
				if (hourElement.start <= time.localtime().tm_hour
					and time.localtime().tm_hour <= hourElement.end):

					# check if rule element is not triggered
					# => set as triggered
					if not currentRuleElement.triggered:

						self.logger.debug("[%s]: Hour " % self.fileName
							+ "from '%d' to '%d' for '%s' counts as triggered."
							% (hourElement.start, hourElement.end,
							hourElement.time))

						utcTimestamp = int(time.time())
						currentRuleElement.timeWhenTriggered = utcTimestamp
						currentRuleElement.triggered = True

				# check if rule element is triggered
				# => set rule element as not triggered
				elif currentRuleElement.triggered:

					self.logger.debug("[%s]: Hour " % self.fileName
						+ "from '%d' to '%d' for '%s' no longer "
						% (hourElement.start, hourElement.end,
						hourElement.time)
						+ "counts as triggered.")

					currentRuleElement.triggered = False

			elif hourElement.time == "utc":

				# check if the current hour lies between the start/end
				# of the hour rule element
				# => set rule element as triggered if it is not yet triggered
				if (hourElement.start <= time.gmtime().tm_hour
					and time.gmtime().tm_hour <= hourElement.end):

					# check if rule element is not triggered
					# => set as triggered
					if not currentRuleElement.triggered:

						self.logger.debug("[%s]: Hour " % self.fileName
							+ "from '%d' to '%d' for '%s' counts as triggered."
							% (hourElement.start, hourElement.end,
							hourElement.time))

						utcTimestamp = int(time.time())
						currentRuleElement.timeWhenTriggered = utcTimestamp
						currentRuleElement.triggered = True

				# check if rule element is triggered
				# => set rule element as not triggered
				elif currentRuleElement.triggered:

					self.logger.debug("[%s]: Hour " % self.fileName
						+ "from '%d' to '%d' for '%s' no longer "
						% (hourElement.start, hourElement.end,
						hourElement.time)
						+ "counts as triggered.")

					currentRuleElement.triggered = False

			else:
				self.logger.error("[%s]: No valid value for " % self.fileName
					+ "'time' attribute in hour tag.")
				return False

		# check if rule element is of type "minute"
		# => update values of rule according to the date
		elif currentRuleElement.type == "minute":

			minuteElement = currentRuleElement.element

			# check if the current minute lies between the start/end
			# of the minute rule element
			# => set rule element as triggered if it is not yet triggered
			if (minuteElement.start <= time.localtime().tm_min
				and time.localtime().tm_min <= minuteElement.end):

				# check if rule element is not triggered
				# => set as triggered
				if not currentRuleElement.triggered:

					self.logger.debug("[%s]: Minute " % self.fileName
						+ "from '%d' to '%d' counts as triggered."
						% (minuteElement.start, minuteElement.end))

					utcTimestamp = int(time.time())
					currentRuleElement.timeWhenTriggered = utcTimestamp
					currentRuleElement.triggered = True

			# check if rule element is triggered
			# => set rule element as not triggered
			elif currentRuleElement.triggered:

				self.logger.debug("[%s]: Minute " % self.fileName
					+ "from '%d' to '%d' no longer "
					% (minuteElement.start, minuteElement.end)
					+ "counts as triggered.")

				currentRuleElement.triggered = False

		# check if rule element is of type "second"
		# => update values of rule according to the date
		elif currentRuleElement.type == "second":

			secondElement = currentRuleElement.element

			# check if the current second lies between the start/end
			# of the second rule element
			# => set rule element as triggered if it is not yet triggered
			if (secondElement.start <= time.localtime().tm_sec
				and time.localtime().tm_sec <= secondElement.end):

				# check if rule element is not triggered
				# => set as triggered
				if not currentRuleElement.triggered:

					self.logger.debug("[%s]: Second " % self.fileName
						+ "from '%d' to '%d' counts as triggered."
						% (secondElement.start, secondElement.end))

					utcTimestamp = int(time.time())
					currentRuleElement.timeWhenTriggered = utcTimestamp
					currentRuleElement.triggered = True

			# check if rule element is triggered
			# => set rule element as not triggered
			elif currentRuleElement.triggered:

				self.logger.debug("[%s]: Second " % self.fileName
					+ "from '%d' to '%d' no longer "
					% (secondElement.start, secondElement.end)
					+ "counts as triggered.")

				currentRuleElement.triggered = False

		# check if rule element is of type "boolean"
		# => traverse rule recursively
		elif currentRuleElement.type == "boolean":

			# update values of all rule elements in current rule element
			for ruleElement in currentRuleElement.element.elements:
				self._updateRuleValuesRecursively(sensorAlertList,
					ruleElement)

		else:
			self.logger.error("[%s]: Rule element " % self.fileName
				+ "has an invalid type.")
			return False

		return True


	# this internal function evaluates rule elements from type
	# "boolean" recursively
	# (means AND, OR and NOT are evaluated as triggered/not triggered)
	def _evaluateRuleElementsRecursively(self, currentRuleElement):

		# only evaluate rule elements of type "boolean"
		if currentRuleElement.type == "boolean":

			# evaluate "and" rule element
			if currentRuleElement.element.type == "and":

				andElement = currentRuleElement.element

				# check if all elements of the "and" rule element are triggered
				for element in andElement.elements:

					# check if sensor element is not triggered
					# => if it is, set current rule element also as
					# not triggered (if it was triggered) and return
					if element.type == "sensor":
						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Sensor rule element "
									% self.fileName
									+ "with remote id '%d' and username '%s' "
									% (element.element.remoteSensorId,
									element.element.username)
									+ "not triggered. Set 'and' rule "
									+ "also to not triggered.")

								currentRuleElement.triggered = False

							return True

					# check if weekday element is not triggered
					# => if it is, set current rule element also as
					# not triggered (if it was triggered) and return
					elif element.type == "weekday":

						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Week day rule "
									% self.fileName
									+ "element with value '%d' for '%s' not "
									% (element.element.weekday,
									element.element.time)
									+ "triggered. Set 'and' rule "
									+ "also to not triggered.")

								currentRuleElement.triggered = False

							return True

					# check if monthday element is not triggered
					# => if it is, set current rule element also as
					# not triggered (if it was triggered) and return
					elif element.type == "monthday":

						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Month day rule "
									% self.fileName
									+ "element with value '%d' for '%s' not "
									% (element.element.monthday,
									element.element.time)
									+ "triggered. Set 'and' rule "
									+ "also to not triggered.")

								currentRuleElement.triggered = False

							return True

					# check if hour element is not triggered
					# => if it is, set current rule element also as
					# not triggered (if it was triggered) and return
					elif element.type == "hour":

						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Hour rule element "
									% self.fileName
									+ "from '%d' to '%d' for '%s' not "
									% (element.element.start,
									element.element.end,
									element.element.time)
									+ "triggered. Set 'and' rule "
									+ "also to not triggered.")

								currentRuleElement.triggered = False

							return True

					# check if minute element is not triggered
					# => if it is, set current rule element also as
					# not triggered (if it was triggered) and return
					elif element.type == "minute":

						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Minute rule element "
									% self.fileName
									+ "from '%d' to '%d' not "
									% (element.element.start,
									element.element.end)
									+ "triggered. Set 'and' rule "
									+ "also to not triggered.")

								currentRuleElement.triggered = False

							return True

					# check if second element is not triggered
					# => if it is, set current rule element also as
					# not triggered (if it was triggered) and return
					elif element.type == "second":

						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Second rule element "
									% self.fileName
									+ "from '%d' to '%d' not "
									% (element.element.start,
									element.element.end)
									+ "triggered. Set 'and' rule "
									+ "also to not triggered.")

								currentRuleElement.triggered = False

							return True

					elif element.type == "boolean":
						if not self._evaluateRuleElementsRecursively(element):
							return False

						# check if rule element was set to not triggered
						# => if it was, set current rule element
						# also as not triggered (when it was triggered)
						# and return
						if not element.triggered:

							if currentRuleElement.triggered:
								self.logger.debug("[%s]: Rule element "
									% self.fileName
									+ "evaluates to not triggered. Set 'and' "
									+ "rule also to not triggered.")

								currentRuleElement.triggered = False

							return True

					else:
						self.logger.error("[%s]: Type of " % self.fileName
							+ "rule element not valid.")
						return False

				# when this point is reached, every element of the "and"
				# rule is triggered
				# => set current element as triggered (when not triggered)
				# and return
				if not currentRuleElement.triggered:

					self.logger.debug("[%s]: Each rule element evaluates "
						% self.fileName
						+ "to triggered. Set 'and' rule "
						+ "also to triggered.")

					currentRuleElement.triggered = True
					utcTimestamp = int(time.time())
					currentRuleElement.timeWhenTriggered = utcTimestamp

				return True

			# evaluate "or" rule element
			elif currentRuleElement.element.type == "or":

				orElement = currentRuleElement.element

				# first check all elements if there exist a "not rule" element
				# that is triggered
				# => if it does, set current rule element
				# also as triggered (if it was not triggered) and return
				# (done for optimization)
				for element in orElement.elements:

					if (element.type == "sensor"
						and element.triggered == True):

						if not currentRuleElement.triggered:
							self.logger.debug("[%s]: Sensor rule element with "
								% self.fileName
								+ "remote id '%d' and username '%s' "
								% (element.element.remoteSensorId,
								element.element.username)
								+ "triggered. Set 'or' rule "
								+ "also to triggered.")

							currentRuleElement.triggered = True
							utcTimestamp = int(time.time())
							currentRuleElement.timeWhenTriggered = utcTimestamp

						return True

					elif (element.type == "weekday"
						and element.triggered == True):

						if not currentRuleElement.triggered:
							self.logger.debug("[%s]: Week day rule element "
								% self.fileName
								+ "with value '%d' for '%s' "
								% (element.element.weekday,
								element.element.time)
								+ "triggered. Set 'or' rule "
								+ "also to triggered.")

							currentRuleElement.triggered = True
							utcTimestamp = int(time.time())
							currentRuleElement.timeWhenTriggered = utcTimestamp

						return True

					elif (element.type == "monthday"
						and element.triggered == True):

						if not currentRuleElement.triggered:
							self.logger.debug("[%s]: Month day rule element "
								% self.fileName
								+ "with value '%d' for '%s' "
								% (element.element.monthday,
								element.element.time)
								+ "triggered. Set 'or' rule "
								+ "also to triggered.")

							currentRuleElement.triggered = True
							utcTimestamp = int(time.time())
							currentRuleElement.timeWhenTriggered = utcTimestamp

						return True

					elif (element.type == "hour"
						and element.triggered == True):

						if not currentRuleElement.triggered:
							self.logger.debug("[%s]: Hour rule element from "
								% self.fileName
								+ "'%d' to '%d' for '%s' "
								% (element.element.start,
								element.element.end,
								element.element.time)
								+ "triggered. Set 'or' rule "
								+ "also to triggered.")

							currentRuleElement.triggered = True
							utcTimestamp = int(time.time())
							currentRuleElement.timeWhenTriggered = utcTimestamp

						return True

					elif (element.type == "minute"
						and element.triggered == True):

						if not currentRuleElement.triggered:
							self.logger.debug("[%s]: Minute rule element from "
								% self.fileName
								+ "'%d' to '%d' "
								% (element.element.start,
								element.element.end)
								+ "triggered. Set 'or' rule "
								+ "also to triggered.")

							currentRuleElement.triggered = True
							utcTimestamp = int(time.time())
							currentRuleElement.timeWhenTriggered = utcTimestamp

						return True

					elif (element.type == "second"
						and element.triggered == True):

						if not currentRuleElement.triggered:
							self.logger.debug("[%s]: Second rule element from "
								% self.fileName
								+ "'%d' to '%d' "
								% (element.element.start,
								element.element.end)
								+ "triggered. Set 'or' rule "
								+ "also to triggered.")

							currentRuleElement.triggered = True
							utcTimestamp = int(time.time())
							currentRuleElement.timeWhenTriggered = utcTimestamp

						return True

				# if there exists no element that is already triggered
				# => update rule elements and evaluate them
				for element in orElement.elements:

					# only update rule elements
					if element.type == "boolean":
						if not self._evaluateRuleElementsRecursively(element):
							return False

						# check if rule element was set to triggered
						# => if it was, set current rule element
						# also as triggered (if it was not triggered)
						# and return
						if element.triggered:

							if not currentRuleElement.triggered:
								self.logger.debug("[%s]: Rule element "
									% self.fileName
									+ "evaluates to triggered. Set 'or' rule "
									+ "also to triggered.")

								currentRuleElement.triggered = True
								utcTimestamp = int(time.time())
								currentRuleElement.timeWhenTriggered = \
									utcTimestamp

							return True

				# when this point is reached, every element of the "or"
				# rule is not triggered
				# => set current element as not triggered (if it was triggered)
				# and return
				if currentRuleElement.triggered:
					self.logger.debug("[%s]: Each rule element evaluates "
						% self.fileName
						+ "to not triggered. Set 'or' rule "
						+ "also to not triggered.")

					currentRuleElement.triggered = False

				return True

			# evaluate "not" rule element
			elif currentRuleElement.element.type == "not":

				notElement = currentRuleElement.element

				element = notElement.elements[0]

				# check if sensor rule element and current not rule element
				# have the same triggered value
				# => toggle current not element triggered value
				if element.type == "sensor":
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Sensor rule element with "
							% self.fileName
							+ "remote id '%d' and username '%s' has same "
							% (element.element.remoteSensorId,
							element.element.username)
							+ "triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				# check if week day rule element and current not rule element
				# have the same triggered value
				# => toggle current not element triggered value
				elif element.type == "weekday":
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Week day rule element with "
							% self.fileName
							+ "value '%d' for '%s' has same "
							% (element.element.weekday,
							element.element.time)
							+ "triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				# check if month day rule element and current not rule element
				# have the same triggered value
				# => toggle current not element triggered value
				elif element.type == "monthday":
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Month day rule element with "
							% self.fileName
							+ "value '%d' for '%s' has same "
							% (element.element.monthday,
							element.element.time)
							+ "triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				# check if hour rule element and current not rule element
				# have the same triggered value
				# => toggle current not element triggered value
				elif element.type == "hour":
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Hour rule element from "
							% self.fileName
							+ "'%d' to '%d' for '%s' has same "
							% (element.element.start,
							element.element.end,
							element.element.time)
							+ "triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				# check if minute rule element and current not rule element
				# have the same triggered value
				# => toggle current not element triggered value
				elif element.type == "minute":
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Minute rule element from "
							% self.fileName
							+ "'%d' to '%d' has same "
							% (element.element.start,
							element.element.end)
							+ "triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				# check if second rule element and current not rule element
				# have the same triggered value
				# => toggle current not element triggered value
				elif element.type == "second":
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Second rule element from "
							% self.fileName
							+ "'%d' to '%d' has same "
							% (element.element.start,
							element.element.end)
							+ "triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				# check if rule element evaluates to the same triggered value
				# as the current not rule element
				# => toggle current not element triggered value
				elif element.type == "boolean":
					if not self._evaluateRuleElementsRecursively(element):
						return False

					# check if rule element was evaluated to the same
					# triggered value as the not rule element
					# => toggle current not element triggered value
					if element.triggered == currentRuleElement.triggered:

						self.logger.debug("[%s]: Rule element evaluates "
							% self.fileName
							+ "to the same triggered value as 'not' rule. "
							+ "Toggle triggered value of 'not' rule.")

						# toggle current rule element triggered value
						currentRuleElement.triggered = not element.triggered

					return True

				else:
					self.logger.error("[%s]: Type of " % self.fileName
						+ "rule element not valid.")
					return False

		# if current rule element is not of type "boolean"
		# => just return
		else:
			return True


	# this internal function updates all rules and their rule elements
	# (sets new values for them, evaluates the boolean elements etc)
	def _updateRule(self, sensorAlertList, alertLevel):

		self.logger.debug("[%s]: Updating rule values " % self.fileName
			+ "for alert level '%d'." % alertLevel.level)

		# update and evaluate all rules of the alert level
		for ruleStart in alertLevel.rules:

			# update all rule values (sets also the sensors as triggered
			# or not triggered)
			if not self._updateRuleValuesRecursively(sensorAlertList,
				ruleStart):
				self.logger.error("[%s]: Not able to update " % self.fileName
					+ "values for rule with order '%d' "
					% ruleStart.order
					+ "for alert level '%d'."
					% alertLevel.level)
				return False

			# evaluate all and/or/not rule elements
			if not self._evaluateRuleElementsRecursively(ruleStart):
				self.logger.error("[%s]: Not able to evaluate " % self.fileName
					+ "rule with order '%d' for alert level '%d'."
					% (ruleStart.order, alertLevel.level))
				return False


		# if more than one rule exists
		# => check if they had triggered in the correct time frame
		if len(alertLevel.rules) > 1:
			for idx in range(len(alertLevel.rules)):

				# skip first rule start
				if idx == 0:
					continue

				prevRuleStart = alertLevel.rules[idx - 1]
				currRuleStart = alertLevel.rules[idx]

				# check if current rule was triggered
				if currRuleStart.triggered:

					# check if current rule was triggered right between
					# min and max time after previous rule
					# => do not change anything
					if (((prevRuleStart.timeWhenTriggered
						+ currRuleStart.minTimeAfterPrev)
						<= currRuleStart.timeWhenTriggered)
						and
						((prevRuleStart.timeWhenTriggered
						+ currRuleStart.maxTimeAfterPrev)
						>= currRuleStart.timeWhenTriggered)):

						continue

					# if rule had not triggered right between min
					# and max time
					# => reset it
					else:
						self.logger.debug("[%s]: Rule with order '%d' "
							% (self.fileName, currRuleStart.order)
							+ "for alert level '%d' did not trigger "
							% alertLevel.level
							+ "in time. Reset rule.")

						currRuleStart.triggered = False
						currRuleStart.timeWhenTriggered = 0.0


		# check if all received sensor alerts count as triggered
		# and therefore can be removed
		for sensorAlert in list(sensorAlertList):
			sensorAlertTimeReceived = sensorAlert[3]
			sensorAlertAlertDelay = sensorAlert[4]

			# if there does not exist an alert delay
			# => remove sensor alert
			utcTimestamp = int(time.time())
			if sensorAlertAlertDelay == 0:
				sensorAlertList.remove(sensorAlert)

			# if there exist an alert delay
			# => only remove sensor alert from the list when there is no
			# delay to wait (add an artificial delay from 5 seconds
			# to make race condition unlikely)
			elif ((utcTimestamp - sensorAlertTimeReceived)
				> (sensorAlertAlertDelay + 5)):
				sensorAlertList.remove(sensorAlert)


		# check if the counter is activated and when it is activated
		# if the counter limit is reached
		for ruleStart in alertLevel.rules:

			# skip counter checking when counter is not activated
			if not ruleStart.counterActivated:
				continue

			# remove all triggered elements from the counter
			# if the time that they have to wait has passed
			utcTimestamp = int(time.time())
			for counterTimeWhenTriggered in list(ruleStart.counterList):
				if ((counterTimeWhenTriggered + ruleStart.counterWaitTime)
					< utcTimestamp):

					self.logger.debug("[%s]: Counter for rule with order '%d' "
						% (self.fileName, ruleStart.order)
						+ "for alert level '%d' has expired. Removing it."
						% alertLevel.level)

					ruleStart.counterList.remove(counterTimeWhenTriggered)

			# only process counter if the rule is triggered
			if ruleStart.triggered:

				# check if timeWhenTriggered is already processed in the
				# counter list
				# => do nothing
				if ruleStart.timeWhenTriggered in ruleStart.counterList:
					pass

				# when it is not processed yet
				# => add it or reset the trigger
				else:

					# check if the limit of the counter is not yet reached
					# => add timeWhenTriggered to the counter list
					if len(ruleStart.counterList) < ruleStart.counterLimit:

						ruleStart.counterList.append(
							ruleStart.timeWhenTriggered)

					# when the limit is already reached
					# => reset the trigger
					else:

						self.logger.debug("[%s]: Counter for rule "
							% self.fileName
							+ "with order '%d' "
							% ruleStart.order
							+ "for alert level '%d' has reached its limit. "
							% alertLevel.level
							+ "Resetting rule.")

						ruleStart.triggered = False
						ruleStart.timeWhenTriggered = 0.0


	# this internal function evaluates if the rule chain of the given
	# alert level is triggered
	def _evaluateRules(self, alertLevel):

		self.logger.debug("[%s]: Evaluate rules " % self.fileName
			+ "for alert level '%d'." % alertLevel.level)

		# check only the "root" element of the last rule
		# if it has triggered, because only the last rule in the rules chain
		# have to be triggered to trigger the alert level (all other rules
		# in the chain had to be triggered at some point in time to trigger
		# the last rule)
		ruleStart = alertLevel.rules[-1]

		# if the last rule of the chain has triggered
		# => reset all rules in the chain
		if ruleStart.triggered:
			for rule in alertLevel.rules:
				rule.timeWhenTriggered = 0.0
				rule.triggered = False

			return True
		else:
			return False


	# this internal function checks recusrively if a rule element is triggered
	# and therefore the rule is likely to trigger during the next evaluation
	def _checkRulesCanTriggerRecursively(self, currentRuleElement):

		# check if rule element is of type "sensor"
		# => return if it is triggered
		if currentRuleElement.type == "sensor":

			return currentRuleElement.triggered

		# check if rule element is of type "weekday"
		# => return if it is triggered
		elif currentRuleElement.type == "weekday":

			return currentRuleElement.triggered

		# check if rule element is of type "monthday"
		# => return if it is triggered
		elif currentRuleElement.type == "monthday":

			return currentRuleElement.triggered

		# check if rule element is of type "hour"
		# => return if it is triggered
		elif currentRuleElement.type == "hour":

			return currentRuleElement.triggered

		# check if rule element is of type "minute"
		# => return if it is triggered
		elif currentRuleElement.type == "minute":

			return currentRuleElement.triggered

		# check if rule element is of type "second"
		# => return if it is triggered
		elif currentRuleElement.type == "second":

			return currentRuleElement.triggered

		# check if rule element is of type "boolean"
		# => traverse rule recursively
		elif currentRuleElement.type == "boolean":

			# check all rule elements of the current rule element
			# if one rule element is triggered => rule can still trigger
			for ruleElement in currentRuleElement.element.elements:

				if self._checkRulesCanTriggerRecursively(ruleElement):
					return True

			# when this point is reached, no rule element of the current one
			# is triggered
			return False

		else:
			self.logger.error("[%s]: Rule element " % self.fileName
				+ "has an invalid type while checking.")
			return False


	# this internal function checks if a rule is likely to trigger
	# during the next check (means an element of it counts still as triggered)
	def _checkRulesCanTrigger(self, sensorAlertList, alertLevel):

		self.logger.debug("[%s]: Check if rules of " % self.fileName
			+ "alert level '%d' can trigger." % alertLevel.level)

		# check if a sensor alert is still in the list (this happens
		# when a sensor has a delay until it counts as triggered)
		if sensorAlertList:
			return True

		# check all rules if they can still trigger
		# if one of the rules chain can => complete rules chain can trigger
		for ruleElement in alertLevel.rules:
			if self._checkRulesCanTriggerRecursively(ruleElement):
				return True

		# when this point is reached, no rule of the rules chain can trigger
		# at the moment
		return False


	# Internal function that pre-processes sensor alerts from the database.
	# All triggered sensor alerts from the database are filtered and separated
	# into "sensorAlertsToHandle" and "sensorAlertsToHandleWithRules".
	# NOTE: this function updates the argument "sensorAlertsToHandle"
	# and "sensorAlertsToHandleWithRules".
	def _preprocessSensorAlerts(self, sensorAlertsToHandle,
		sensorAlertsToHandleWithRules, sensorAlertList):

		# get the flag if the system is active or not
		isAlertSystemActive = self.storage.isAlertSystemActive()

		# check if sensor alerts from the database
		# have to be handled
		for sensorAlert in sensorAlertList:

			# delete sensor alert from the database
			if not self.storage.deleteSensorAlert(sensorAlert.sensorAlertId):
				self.logger.error("[%s]: Not able to delete "
					% self.fileName
					+ "sensor alert with id '%d' from database."
					% sensorAlert.sensorAlertId)
				continue

			# get all alert levels for this sensor (list of integers)
			sensorAlertLevels = self.storage.getSensorAlertLevels(
				sensorAlert.sensorId)

			if sensorAlertLevels is None:
				self.logger.error("[%s]: No alert levels " % self.fileName
					+ "for sensor in database. Can not trigger alert.")
				continue

			# get all alert levels that are triggered
			# because of this sensor alert (used as a pre filter)
			triggeredAlertLevels = list()
			for configuredAlertLevel in self.alertLevels:
				for sensorAlertLevel in sensorAlertLevels:
					if (configuredAlertLevel.level == sensorAlertLevel):
						# check if alert system is active
						# or alert level triggers always
						if (isAlertSystemActive
							or configuredAlertLevel.triggerAlways):

							# check if the configured alert level
							# should trigger a sensor alert message
							# when the sensor goes to state "triggered"
							# => if not skip configured alert level
							if (not
								configuredAlertLevel.triggerAlertTriggered
								and sensorAlert.state == 1):
								continue

							# check if the configured alert level
							# should trigger a sensor alert message
							# when the sensor goes to state "normal"
							# => if not skip configured alert level
							if (not configuredAlertLevel.triggerAlertNormal
								and sensorAlert.state == 0):
								continue

							# split sensor alerts into alerts with rules
							# (each alert level with a rule is handled
							# as a single sensor alert and appended
							# into a separate list)
							if configuredAlertLevel.rulesActivated:

								# check if an alert level with a rule
								# is already triggered
								# => add current sensor alert to it
								found = False
								for alertWithRule in \
									sensorAlertsToHandleWithRules:

									if (configuredAlertLevel ==
										alertWithRule[1]):

										alertWithRule[0].append(
											sensorAlert)

										found = True
										break

								# if no alert level with a rule was found
								# => create a new sensor alert with rule
								# to handle for it
								if not found:
									sensorAlertsToHandleWithRules.append(
										[ [sensorAlert],
										configuredAlertLevel] )

							# create a list of sensor alerts to handle
							# without rules activated
							else:
								triggeredAlertLevels.append(
									configuredAlertLevel)

			# check if an alert level to trigger was found
			# if not => just ignore it
			if not triggeredAlertLevels:
				self.logger.info("[%s]: No alert level "
					% self.fileName
					+ "to trigger was found.")

				# add sensorId of the sensor alert
				# to the queue for state changes of the
				# manager update executer
				if self.managerUpdateExecuter != None:

					# Returns a tuple of (dataType, data) or None.
					sensorDataTuple = self.storage.getSensorData(
						sensorAlert.sensorId)

					if sensorDataTuple is None:
						self.logger.error("[%s]: Unable to get sensor data "
							% self.fileName
							+ "from database. Skipping manager notification.")
					else:
						managerStateTuple = (sensorAlert.sensorId,
							sensorAlert.state,
							sensorDataTuple[0],
							sensorDataTuple[1])
						self.managerUpdateExecuter.queueStateChange.append(
							managerStateTuple)

				continue

			# update alert levels to trigger
			else:

				# add sensor alert with alert levels
				# to the list of sensor alerts to handle
				sensorAlertsToHandle.append( [sensorAlert,
					triggeredAlertLevels] )


	# Internal function that processes sensor alerts.
	# NOTE: this function updates the argument "sensorAlertsToHandle".
	def _processSensorAlerts(self, sensorAlertsToHandle):

		# get the flag if the system is active or not
		isAlertSystemActive = self.storage.isAlertSystemActive()

		# check all sensor alerts to handle if they have to be triggered
		for sensorAlertToHandle in list(sensorAlertsToHandle):
			sensorAlert = sensorAlertToHandle[0]

			# get all alert levels that are triggered
			# because of this sensor alert
			triggeredAlertLevels = list()
			for configuredAlertLevel in self.alertLevels:
				for sensorAlertLevel in sensorAlertToHandle[1]:
					if (configuredAlertLevel.level ==
						sensorAlertLevel.level):
						# check if alert system is active
						# or alert level triggers always
						if (isAlertSystemActive
							or configuredAlertLevel.triggerAlways):
							triggeredAlertLevels.append(
								configuredAlertLevel)

			# check if an alert level to trigger remains
			# if not => just remove sensor alert to handle from the list
			if not triggeredAlertLevels:
				self.logger.info("[%s]: No alert level " % self.fileName
					+ "to trigger remains.")

				sensorAlertsToHandle.remove(sensorAlertToHandle)

				continue

			# Update alert levels to trigger.
			# If the sensor alert has a delay, we have to remove
			# all alert levels that do not trigger anymore.
			else:
				sensorAlertToHandle[1] = triggeredAlertLevels

			# check if sensor alert has triggered
			utcTimestamp = int(time.time())
			if ((utcTimestamp - sensorAlert.timeReceived)
				> sensorAlert.alertDelay):

				# generate integer list of alert levels that have triggered
				# (needed for sensor alert message)
				for triggeredAlertLevel in triggeredAlertLevels:
					sensorAlert.alertLevels.append(triggeredAlertLevel.level)

				# send sensor alert to all manager and alert clients
				for serverSession in self.serverSessions:
					# ignore sessions which do not exist yet
					# and that are not managers
					if serverSession.clientComm == None:
						continue
					if (serverSession.clientComm.nodeType != "manager"
						and serverSession.clientComm.nodeType != "alert"):
						continue
					if not serverSession.clientComm.clientInitialized:
						continue

					# Only send a sensor alert to a client that actually
					# handles a triggered alert level.
					clientAlertLevels = \
						serverSession.clientComm.clientAlertLevels
					atLeastOne = any(al.level in clientAlertLevels
									 for al in triggeredAlertLevels)
					if not atLeastOne:
						continue

					# sending sensor alert to manager/alert node
					# via a thread to not block the sensor alert executer
					sensorAlertProcess = AsynchronousSender(
						self.globalData, serverSession.clientComm)
					# set thread to daemon
					# => threads terminates when main thread terminates
					sensorAlertProcess.daemon = True
					sensorAlertProcess.sendSensorAlert = True
					sensorAlertProcess.sensorAlert = sensorAlert

					self.logger.debug("[%s]: Sending sensor " % self.fileName
						+ "alert to manager/alert (%s:%d)."
						% (serverSession.clientComm.clientAddress,
						serverSession.clientComm.clientPort))
					sensorAlertProcess.start()

				# after sensor alert was triggered
				# => remove sensor alert to handle
				sensorAlertsToHandle.remove(sensorAlertToHandle)


	# Internal function that processes sensor alerts that affect rules.
	# NOTE: this function updates the argument "sensorAlertsToHandleWithRules".
	def _processSensorAlertsRules(self, sensorAlertsToHandleWithRules):

		# check all sensor alerts to handle with alert levels that have
		# rules if they have to be triggered
		for sensorAlertToHandle in list(sensorAlertsToHandleWithRules):

			# Convert sensor alerts back to tuple list because
			# the rule engine works on a tuple list
			# (has to be done until rule engine is re-factored).
			sensorAlertTupleList = list()
			for sensorAlert in sensorAlertToHandle[0]:
				temp = (sensorAlert.sensorAlertId, sensorAlert.sensorId,
					sensorAlert.nodeId, sensorAlert.timeReceived,
					sensorAlert.alertDelay, sensorAlert.state,
					sensorAlert.description)
				sensorAlertTupleList.append(temp)

			alertLevel = sensorAlertToHandle[1]

			# update the rule chain of the alert level with
			# the received sensor alerts
			self._updateRule(sensorAlertTupleList, alertLevel)

			# check if the rule chain evaluates to triggered
			# => trigger sensor alert for the alert level
			if self._evaluateRules(alertLevel):

				self.logger.info("[%s]: Alert level " % self.fileName
					+ "'%d' rules have triggered." % alertLevel.level)

				# Create a temporary alert level for this triggered rule.
				ruleSensorAlert = SensorAlert()
				ruleSensorAlert.rulesActivated = True
				ruleSensorAlert.sensorId = -1
				ruleSensorAlert.changeState = False
				ruleSensorAlert.alertLevels.append(alertLevel.level)
				ruleSensorAlert.state = 1
				ruleSensorAlert.description = \
					"Rule of Alert Level: '%s'" % alertLevel.name
				ruleSensorAlert.hasOptionalData = False
				ruleSensorAlert.optionalData = None
				ruleSensorAlert.hasLatestData = False
				ruleSensorAlert.dataType = SensorDataType.NONE
				ruleSensorAlert.sensorData = None

				# send sensor alert to all manager and alert clients
				for serverSession in self.serverSessions:
					# ignore sessions which do not exist yet
					# and that are not managers
					if serverSession.clientComm == None:
						continue
					if (serverSession.clientComm.nodeType != "manager"
						and serverSession.clientComm.nodeType != "alert"):
						continue
					if not serverSession.clientComm.clientInitialized:
						continue

					# Only send a sensor alert to a client that actually
					# handles a triggered alert level.
					clientAlertLevels = \
						serverSession.clientComm.clientAlertLevels
					atLeastOne = alertLevel.level in clientAlertLevels
					if not atLeastOne:
						continue

					# sending sensor alert to manager/alert node
					# via a thread to not block the sensor alert executer
					sensorAlertProcess = AsynchronousSender(
						self.globalData, serverSession.clientComm)
					# set thread to daemon
					# => threads terminates when main thread terminates
					sensorAlertProcess.daemon = True
					sensorAlertProcess.sendSensorAlert = True
					sensorAlertProcess.sensorAlert = ruleSensorAlert

					self.logger.debug("[%s]: Sending sensor " % self.fileName
						+ "alert to manager/alert (%s:%d)."
						% (serverSession.clientComm.clientAddress,
						serverSession.clientComm.clientPort))
					sensorAlertProcess.start()

				# remove sensor alert to handle from list
				# after it has triggered
				sensorAlertsToHandleWithRules.remove(sensorAlertToHandle)

			# if rule chain did not evaluate to triggered
			# => check if it is likely that it can trigger during the
			# next evaluation if not => remove the sensor alert to handle
			else:
				if not self._checkRulesCanTrigger(sensorAlertTupleList,
					alertLevel):

					self.logger.debug("[%s]: Alert level " % self.fileName
						+ "'%d' rules can not trigger at the moment."
						% alertLevel.level)

					# remove sensor alert to handle from list
					# when it can not trigger at the current state
					sensorAlertsToHandleWithRules.remove(
						sensorAlertToHandle)


	# this function starts the endless loop of the alert executer thread
	def run(self):

		# Create an empty list for sensor alerts that have to be handled.
		# Structure: [ list(sensorAlert, list(triggered alertLevels) ) ]
		sensorAlertsToHandle = list()

		# Create an empty list for sensor alerts
		# that have to be handled and which alert levels have rules.
		# Structure: [ list(sensorAlerts), possible triggered alertLevel ]
		sensorAlertsToHandleWithRules = list()

		while 1:

			# check if thread should terminate
			if self.exitFlag:
				return

			# check if manager update executer object reference does exist
			# => if not get it from the global data
			if self.managerUpdateExecuter is None:
				self.managerUpdateExecuter = \
					self.globalData.managerUpdateExecuter

			# get a list of all sensor alerts from database
			# list is a list of tuples (sensorAlertId, sensorId, nodeId,
			# timeReceived, alertDelay, state, description, dataJson,
			# changeState, hasLatestData, dataType, sensorData)
			sensorAlertTuples = self.storage.getSensorAlerts()

			# convert list of tuples into sensor alert objects
			sensorAlertList = list()
			for sensorAlertTuple in sensorAlertTuples:
				temp = SensorAlert()
				temp.rulesActivated = False
				temp.sensorAlertId = sensorAlertTuple[0]
				temp.sensorId = sensorAlertTuple[1]
				temp.nodeId = sensorAlertTuple[2]
				temp.timeReceived = sensorAlertTuple[3]
				temp.alertDelay = sensorAlertTuple[4]
				temp.state = sensorAlertTuple[5]
				temp.description = sensorAlertTuple[6]
				temp.changeState = (sensorAlertTuple[8] == 1)
				temp.hasLatestData = (sensorAlertTuple[9] == 1)
				temp.dataType = sensorAlertTuple[10]
				temp.sensorData = sensorAlertTuple[11]

				# get json data string and convert it
				temp.hasOptionalData = False
				temp.optionalData = None
				dataJson = sensorAlertTuple[7]
				if dataJson != "":
					temp.hasOptionalData = True
					try:
						temp.optionalData = json.loads(dataJson)
					except Exception as e:
						self.logger.exception("[%s]: Optional data from "
							% self.fileName
							+ "database not a valid json string. "
							+ "Ignoring data.")

						temp.hasOptionalData = False

				sensorAlertList.append(temp)

			# check if no sensor alerts are to handle and exist in database
			if (not sensorAlertsToHandle
				and not sensorAlertsToHandleWithRules
				and not sensorAlertList):

				self.sensorAlertEvent.wait()
				self.sensorAlertEvent.clear()
				continue

			# Filter and separate sensor alerts from the database.
			# NOTE: argument "sensorAlertsToHandle"
			# and "sensorAlertsToHandleWithRules" is updated by this function.
			self._preprocessSensorAlerts(sensorAlertsToHandle,
				sensorAlertsToHandleWithRules, sensorAlertList)

			# wake up manager update executer
			# => state change will be transmitted
			# (because it is in the queue)
			if not self.managerUpdateExecuter is None:
				self.managerUpdateExecuter.managerUpdateEvent.set()

			# when no sensor alerts exist to handle => restart loop
			if (not sensorAlertsToHandle
				and not sensorAlertsToHandleWithRules):
				continue

			# Process sensor alerts that we have to handle.
			# NOTE: argument "sensorAlertsToHandle" is updated by this function
			self._processSensorAlerts(sensorAlertsToHandle)

			# Process sensor alerts that affect rules.
			# NOTE: argument "sensorAlertsToHandleWithRules" is updated
			# by this function
			self._processSensorAlertsRules(sensorAlertsToHandleWithRules)

			time.sleep(0.5)


	# sets the exit flag to shut down the thread
	def exit(self):
		self.exitFlag = True
		return