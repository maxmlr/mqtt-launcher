#!/usr/bin/env python3

# Copyright (c) 2014 Jan-Piet Mens <jpmens()gmail.com>
# Copyright (c) 2014-2020 Jan-Piet Mens <jpmens()gmail.com>; Maximilian Miller <miller.deutschland()gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of mosquitto nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

__author__    = 'Jan-Piet Mens <jpmens()gmail.com>; Maximilian Miller <miller.deutschland()gmail.com>'
__copyright__ = 'Copyright 2014-2020 Jan-Piet Mens; Maximilian Miller'

import os
import sys
import subprocess
import logging
import paho.mqtt.client as paho
import time
import socket
import string

QOS=2
CONFIG=os.getenv('MQTTLAUNCHERCONFIG', 'launcher.conf')

class Config(object):
    def __init__(self, filename=CONFIG):
        self.config = {}
        exec(compile(open(filename).read(), filename, 'exec'), self.config)
        del self.config['__builtins__']

    def get(self, key, default=None):
        return self.config.get(key, default)

try:
    cf = Config()
except Exception as e:
    print(f"Cannot load configuration from file {CONFIG}: {e}")
    sys.exit(2)

LOGFILE = cf.get('logfile', 'logfile')
LOGFORMAT = '%(asctime)-15s %(message)s'
LOGLEVEL = cf.get('loglevel')

DEBUG = True if LOGLEVEL and LOGLEVEL == "debug" else False

if DEBUG:
    logging.basicConfig(filename=LOGFILE, level=logging.DEBUG, format=LOGFORMAT)
else:
    logging.basicConfig(filename=LOGFILE, level=logging.INFO, format=LOGFORMAT)

logging.info("Starting mqtt-launcher...")
logging.info(f'Loglevel: {"DEBUG" if DEBUG else "INFO"}')

def runprog(topic, param=None):

    publish = "%s/report" % topic

    if param is not None and all(c in string.printable for c in param) == False:
        logging.debug(f"Param for topic {topic} is not printable; skipping")
        return

    if not topic in topiclist:
        logging.info(f"Topic {topic} isn't configured")
        return

    if param is not None and param in topiclist[topic]:
        cmd = topiclist[topic].get(param)
    else:
        if None in topiclist[topic]: ### and topiclist[topic][None] is not None:
            cmd = [p.replace('@!@', param) for p in topiclist[topic][None]]
        else:
            logging.info(f"No matching param ({param}) for {topic}")
            return

    logging.debug(f"Running t={topic}: {cmd}")

    try:
        res = subprocess.check_output(cmd, stdin=None, stderr=subprocess.STDOUT, shell=False, universal_newlines=True, cwd='/tmp')
    except Exception as e:
        res = f"*****> {e}"

    payload = res.rstrip('\n')
    (res, mid) =  mqttc.publish(publish, payload, qos=QOS, retain=False)


def on_message(mosq, userdata, msg):
    logging.debug(f"{msg.topic} {msg.qos} {msg.payload}")

    runprog(msg.topic, str(msg.payload.decode()))


def on_connect(mosq, userdata, flags, result_code):
    logging.debug("Connected to MQTT broker, subscribing to topics...")
    for topic in topiclist:
        mqttc.subscribe(topic, QOS)


def on_disconnect(mosq, userdata, rc):
    logging.debug("mqtt-launcher disconnects.")
    time.sleep(10)


if __name__ == '__main__':

    userdata = {
    }
    topiclist = cf.get('topiclist')

    if topiclist is None:
        logging.info("No topic list. Aborting")
        sys.exit(2)

    clientid = cf.get('mqtt_clientid', 'mqtt-launcher-%s' % os.getpid())
    # initialise MQTT broker connection
    mqttc = paho.Client(clientid, clean_session=False)

    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect

    mqttc.will_set('clients/mqtt-launcher', payload="Adios!", qos=0, retain=False)

    # Delays will be: 3, 6, 12, 24, 30, 30, ...
    #mqttc.reconnect_delay_set(delay=3, delay_max=30, exponential_backoff=True)

    if cf.get('mqtt_username') is not None:
        mqttc.username_pw_set(cf.get('mqtt_username'), cf.get('mqtt_password'))
    
    if cf.get('mqtt_tls') is not None:
        mqttc.tls_set()

    mqttc.connect(cf.get('mqtt_broker', 'localhost'), int(cf.get('mqtt_port', '1883')), 60)

    while True:
        try:
            mqttc.loop_forever()
        except socket.error:
            time.sleep(5)
        except KeyboardInterrupt:
            sys.exit(0)
