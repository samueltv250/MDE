#!/usr/bin/env python3

import sys
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

AGENT_PATH = "/org/bluez/AutoPairAgent"
AGENT_CAPABILITY = "NoInputNoOutput"
SERVICE_NAME = "org.bluez"
ADAPTER_INTERFACE = SERVICE_NAME + ".Adapter1"
DEVICE_INTERFACE = SERVICE_NAME + ".Device1"
AGENT_INTERFACE = SERVICE_NAME + ".Agent1"
AGENT_MANAGER_INTERFACE = SERVICE_NAME + ".AgentManager1"

class AutoPairAgent(dbus.service.Object):
    def __init__(self, bus, path):
        super(AutoPairAgent, self).__init__(bus, path)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def AuthorizeService(self, device, uuid):
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        return ""

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        self._confirm(device)

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        self._confirm(device)

    def _confirm(self, device_path):
        device = dbus.Interface(bus.get_object(SERVICE_NAME, device_path), DEVICE_INTERFACE)
        device.Trusted = True
        device.Pair()

if __name__ == "__main__":
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()

    agent = AutoPairAgent(bus, AGENT_PATH)

    obj = bus.get_object(SERVICE_NAME, "/org/bluez")
    agent_manager = dbus.Interface(obj, AGENT_MANAGER_INTERFACE)
    agent_manager.RegisterAgent(AGENT_PATH, AGENT_CAPABILITY)
    agent_manager.RequestDefaultAgent(AGENT_PATH)

    mainloop = GLib.MainLoop()
    mainloop.run()