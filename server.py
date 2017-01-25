#!/usr/bin/env python

# Dependencies:
# sudo apt-get install -y python-gobject
# sudo apt-get install -y python-smbus

import time
import signal
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject
import logging
import threading
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from os import curdir, sep
import urllib2
import Queue
from pprint import pprint
import coloredlogs

SERVICE_NAME = "org.bluez"
AGENT_IFACE = SERVICE_NAME + '.Agent1'
ADAPTER_IFACE = SERVICE_NAME + ".Adapter1"
DEVICE_IFACE = SERVICE_NAME + ".Device1"
PLAYER_IFACE = SERVICE_NAME + '.MediaPlayer1'
TRANSPORT_IFACE = SERVICE_NAME + '.MediaTransport1'

#LOG_LEVEL = logging.INFO
coloredlogs.install(level='DEBUG')
LOG_LEVEL = logging.DEBUG
LOG_FILE = "/dev/stdout"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

"""Utility functions from bluezutils.py"""
def getManagedObjects():
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
    return manager.GetManagedObjects()

def findAdapter():
    objects = getManagedObjects();
    bus = dbus.SystemBus()
    for path, ifaces in objects.iteritems():
        adapter = ifaces.get(ADAPTER_IFACE)
        if adapter is None:
            continue
        obj = bus.get_object(SERVICE_NAME, path)
        return dbus.Interface(obj, ADAPTER_IFACE)
    raise Exception("Bluetooth adapter not found")

TRACK_QUEUE = Queue.Queue()

class BluePlayer(dbus.service.Object):
    AGENT_PATH = "/blueplayer/agent"
    CAPABILITY = "DisplayOnly"

    lcd = None
    bus = None
    adapter = None
    device = None
    deviceAlias = None
    player = None
    transport = None
    connected = None
    state = None
    status = None
    discoverable = None
    track = None

    def __init__(self):
        """Initialize gobject, start the LCD, and find any current media players"""
        self.bus = dbus.SystemBus()

        dbus.service.Object.__init__(self, dbus.SystemBus(), BluePlayer.AGENT_PATH)

        self.bus.add_signal_receiver(self.playerHandler,
                bus_name="org.bluez",
                dbus_interface="org.freedesktop.DBus.Properties",
                signal_name="PropertiesChanged",
                path_keyword="path")

        self.registerAgent()

        adapter_path = findAdapter().object_path
        #self.bus.add_signal_receiver(self.adapterHandler,
        #        bus_name = "org.bluez",
        #        path = adapter_path,
        #        dbus_interface = "org.freedesktop.DBus.Properties",
        #        signal_name = "PropertiesChanged",
        #        path_keyword = "path")


        self.findPlayer()
        self.updateTrackInfo()

    def start(self):
        """Start the BluePlayer by running the gobject mainloop()"""
        try:
            mainloop = gobject.MainLoop()
            mainloop.run()
        except:
            self.end()

    def findPlayer(self):
        """Find any current media players and associated device"""
        manager = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()

        player_path = None
        transport_path = None
        for path, interfaces in objects.iteritems():
            if PLAYER_IFACE in interfaces:
                player_path = path
            if TRANSPORT_IFACE in interfaces:
                transport_path = path

        if player_path:
            logging.debug("Found player on path [{}]".format(player_path))
            self.connected = True
            self.getPlayer(player_path)
            player_properties = self.player.GetAll(PLAYER_IFACE, dbus_interface="org.freedesktop.DBus.Properties")
            if "Status" in player_properties:
                self.status = player_properties["Status"]
            if "Track" in player_properties:
                self.track = player_properties["Track"]
        else:
            logging.debug("Could not find player")

        if transport_path:
            logging.debug("Found transport on path [{}]".format(player_path))
            self.transport = self.bus.get_object("org.bluez", transport_path)
            logging.debug("Transport [{}] has been set".format(transport_path))
            transport_properties = self.transport.GetAll(TRANSPORT_IFACE, dbus_interface="org.freedesktop.DBus.Properties")
            if "State" in transport_properties:
                self.state = transport_properties["State"]

    def getPlayer(self, path):
        """Get a media player from a dbus path, and the associated device"""
        self.player = self.bus.get_object("org.bluez", path)
        logging.debug("Player [{}] has been set".format(path))
        device_path = self.player.Get("org.bluez.MediaPlayer1", "Device", dbus_interface="org.freedesktop.DBus.Properties")
        self.getDevice(device_path)

    def getDevice(self, path):
        """Get a device from a dbus path"""
        self.device = self.bus.get_object("org.bluez", path)
        self.deviceAlias = self.device.Get(DEVICE_IFACE, "Alias", dbus_interface="org.freedesktop.DBus.Properties")

    def playerHandler(self, interface, changed, invalidated, path):
        """Handle relevant property change signals"""
        #logging.debug("Event [{}] changed [{}] on path [{}]".format(interface, changed, path))
        iface = interface[interface.rfind(".") + 1:]

        if iface == "MediaPlayer1":
            if "Track" in changed:
                logging.debug("Track has changed to [{}]".format(changed["Track"]))
                self.track = changed["Track"]
                self.updateTrackInfo()
            if "Status" in changed:
                logging.debug("Status has changed to [{}]".format(changed["Status"]))
                self.status = (changed["Status"])


    def updateTrackInfo(self):
        """Display the current track"""
        print self.status
        #pprint(vars(self))
        if self.track is None:
            return
        logging.debug("Updating track for connected: [{}]; state: [{}]; status: [{}]; discoverable [{}]".format(self.connected, self.state, self.status, self.discoverable))
        logging.info("Playing: {} - {} - {}".format(self.track["Title"], self.track["Artist"], self.track["Album"]))
        TRACK_QUEUE.put(self.track)

    def getStatus(self):
        return self.status

    """Pairing agent methods"""
    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        """Always confirm"""
        logging.debug("RequestConfirmation returns")
        self.trustDevice(device)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        """Always authorize"""
        logging.debug("Authorize service returns")
        return

    def trustDevice(self, path):
        """Set the device to trusted"""
        device_properties = dbus.Interface(self.bus.get_object(SERVICE_NAME, path), "org.freedesktop.DBus.Properties")
        device_properties.Set(DEVICE_IFACE, "Trusted", True)

    def registerAgent(self):
        """Register BluePlayer as the default agent"""
        manager = dbus.Interface(self.bus.get_object(SERVICE_NAME, "/org/bluez"), "org.bluez.AgentManager1")
        manager.RegisterAgent(BluePlayer.AGENT_PATH, BluePlayer.CAPABILITY)
        manager.RequestDefaultAgent(BluePlayer.AGENT_PATH)
        logging.debug("Blueplayer is registered as a default agent")

    def startPairing(self):
        logging.debug("Starting to pair")
        """Make the adpater discoverable"""
        adapter_path = findAdapter().object_path
        adapter = dbus.Interface(self.bus.get_object(SERVICE_NAME, adapter_path), "org.freedesktop.DBus.Properties")
        adapter.Set(ADAPTER_IFACE, "Discoverable", True)

logging.basicConfig(filename=LOG_FILE, format=LOG_FORMAT, level=LOG_LEVEL)
logging.info("Starting BTCoverArt")

gobject.threads_init()
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

time.sleep(2)

def notificationStream():
    #while True:
    track = TRACK_QUEUE.get()
    yield "event: trackchange\ndata: {}\n\n ".format(track['Album'])


class BTWebServer(BaseHTTPRequestHandler):
    def do_GET(self):

        path, _, params = self.path.partition('?')

        if path=="/":
            path="/index.html"
        elif path == '/cors':
            f = urllib2.urlopen(params)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(f.read())
            f.close()
            return
        elif path == '/notifications':
            logging.info('/notifications')
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.end_headers()
            stream = notificationStream()
            while True:
                self.wfile.write(stream.next())

        try:
            #Check the file extension required and
            #set the right mime type

            sendReply = False
            if path.endswith(".html"):
                mimetype='text/html'
                sendReply = True
            if path.endswith(".jpg"):
                mimetype='image/jpg'
                sendReply = True
            if path.endswith(".gif"):
                mimetype='image/gif'
                sendReply = True
            if path.endswith(".js"):
                mimetype='application/javascript'
                sendReply = True
            if path.endswith(".css"):
                mimetype='text/css'
                sendReply = True

            if sendReply == True:
                #Open the static file requested and send it
                f = open('../now-playing/' + path)
                self.send_response(200)
                self.send_header('Content-type',mimetype)
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
            return

        except IOError:
            self.send_error(404,'File Not Found: %s' % path)

    def log_message(self,format, *args):
        """Silence the web server log"""
        return

def webserver():
    PORT = 8080
    server = HTTPServer(('', PORT), BTWebServer)
    logging.info("Starting Web Server on :{}".format(PORT))
    server.serve_forever()


player = None
try:
    player = BluePlayer()

    wt = threading.Thread(name="webserver", target=webserver)
    wt.start()

    mainloop = gobject.MainLoop()
    mainloop.run()
except KeyboardInterrupt as ex:
    logging.info("BluePlayer canceled by user")
except Exception as ex:
    logging.error("How embarrassing. The following error occurred {}".format(ex))
finally:
    logging.info("cleaning up")
    wt.join()
