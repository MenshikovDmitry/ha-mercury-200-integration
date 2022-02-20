"""
Integration for reading the data from Mercury-200.02 electricity counter
through it's build-in RS485 interface. ZigBee -> RS485 modem is needed.

Current integration uses MQTT bus for communication.

Example of configuration.yaml entry:
# Electricity Counter
mercury200:
  - type: mercury200.02
    device_serial: !secret mercury_serial # example: "04023330"
    topic: "zigbee2mqtt/electricity_counter" # the topic of MQTT zigbee2RS485 modem
"""

from __future__ import annotations

import logging
import voluptuous as vol
import json
import homeassistant.helpers.config_validation as cv

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "mercury200"
SUPPORTED_DEVICES = ["mercury200.02"]

CONF_TOPIC = 'topic'
CONF_DEVICE = 'device_serial'

ZONES = ['T1', 'T2', 'T3', 'T4']
GET_ENERGY = '27'
GET_STATUS = '63'

SUPPORTED_COMMANDS = {
    "get_status": GET_STATUS,
    "get_energy": GET_ENERGY
}

from .mercury_protocol import (verify_checksum, device_id_to_bytes, decode_tarif_data, 
                                decode_status_data, mercury_request)


# Schema to validate the configured MQTT topic TO BE DONE
#CONFIG_SCHEMA = vol.Schema({
#    vol.Optional(CONF_TOPIC, default=False): mqtt.valid_subscribe_topic
#    vol.Optional(CONF_DEVICE, default=False): str,
#})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MQTT component."""
    if hass.data.get(DOMAIN, None) is None:
        hass.data[DOMAIN] = {}
    if hass.data[DOMAIN].get('devices', None) is None:
        hass.data[DOMAIN]['devices'] = {}
    device_list = [] # list of devices for creating the entities
    for cfg_entry in config.get(DOMAIN, []):
        device_type = cfg_entry['type']
        if device_type not in SUPPORTED_DEVICES:
            _LOGGER.Error(f"Device type '{device_type}' is not supported (yet). Must be one of {SUPPORTED_DEVICES}")
            continue
        topic = cfg_entry[CONF_TOPIC]
        device_id = str(cfg_entry[CONF_DEVICE])
        device_id_bytes = device_id_to_bytes(device_id)
        device_list.append(device_id)
        # map devices byte code to device_id for quick search
        hass.data[DOMAIN]['devices'][device_id_bytes] = device_id
        if hass.data[DOMAIN].get(device_id, None) is None:
            hass.data[DOMAIN][device_id] = {}
        # update cfg data. It could have ben changed
        hass.data[DOMAIN][device_id]['device_id'] = device_id
        hass.data[DOMAIN][device_id]['device_type'] = device_type
        hass.data[DOMAIN][device_id]['device_id_bytes'] = device_id_bytes
        hass.data[DOMAIN][device_id]['topic'] = topic

        if hass.data[DOMAIN].get('power') is None:   
            # assuming sensors data were not initiated before 
            hass.data[DOMAIN][device_id]['power'] = 0
            hass.data[DOMAIN][device_id]['voltage'] = 0
            for z in ZONES:
                hass.data[DOMAIN][device_id][z] = 0

    # is not used
    def update_entities():
        for update_method in hass.data[DOMAIN]['update_methods']:
            try:
                update_method()
            except Exception as e:
                _LOGGER.error(f"Error updating with {e}")

    # Listen to a message on MQTT.
    @callback
    async def message_received(topic: str, payload: str, qos: int) -> None:
        """A new MQTT message has been received."""
        _LOGGER.info(f"The data recieved: {payload}")

        try:
            pl = json.loads(payload)
        except Exception as e:
            _LOGGER.warning(f"Cant parse {payload} with {e}")
            return
        response = pl.get('action', "")
        if len(response) == 0: return
        try:
            if not verify_checksum(response):
                _LOGGER.info(f"Checksum verification fail: '{response}'")
                return
        except:
            # can not verify checlsum It might be string command. It is fine
            return
        device_serial = tuple(response[1:4]) # in bytes
        request_id = response[4]
        request_id = hex(request_id)[-2:]
        data = response[5:-2]

        counter_id = hass.data[DOMAIN]['devices'].get(device_serial, None)
        if counter_id is None: 
            _LOGGER.warning(f"Message from unregistered device serial: {device_serial}")
            return
        
        if request_id == GET_ENERGY:
            tarif_data = decode_tarif_data(data)
            #_LOGGER.info(f"Processing Tarif data: {data} -> {tarif_data} for {counter_id})
            if tarif_data[0] is None:
                # no data for T1. Nonesence
                return
            for zone, zone_data in zip(ZONES, tarif_data):
                hass.data[DOMAIN][counter_id][zone] = zone_data
            return

        if request_id == GET_STATUS:
            voltage, current, power = decode_status_data(data)
            if voltage is None:
                return
            hass.data[DOMAIN][counter_id]['voltage'] = voltage
            hass.data[DOMAIN][counter_id]['power'] = power
            hass.data[DOMAIN][counter_id]['current'] = current
            #hass.states.asyncset(f"mercuru200_{counter_id}_power", str(power))
            return

    # add listener
    await hass.components.mqtt.async_subscribe(topic, message_received)


    def publish_request(device_id: str, command: str):
        device = hass.data[DOMAIN].get(device_id, None)
        if device is None:
            _LOGGER.error(f"Device '{device_id}' is not registered. Expected one of: {list(hass.data[DOMAIN]['devices'].values())}")
            return
        request_topic = device['topic']+ "/set"
        mqtt_command = mercury_request(device_id=device['device_id'], request_id=command)
        hass.components.mqtt.publish(hass=hass, topic=request_topic, payload='{"action": ' + f"{mqtt_command}" + '}')


    # Service to publish a message on MQTT.
    @callback
    def submit(call: ServiceCall) -> None:
        """Service to send a message."""
        request_device_id = call.data.get('device_id', None)
        command = str(call.data.get('command', None))
        if request_device_id is None or command is None:
            _LOGGER.error(f"Must contain keys 'device_id' and 'command'")
            return
        command_id = SUPPORTED_COMMANDS.get(command, None)
        if command_id is None: 
            _LOGGER.error(f"{command} is not supported by platform. Must be one of {SUPPORTED_COMMANDS.keys()}")
        publish_request(request_device_id, command_id)

    # Register our service with Home Assistant.
    hass.services.async_register(DOMAIN, 'submit_command', submit)


    # Add sensors
    hass.helpers.discovery.load_platform('sensor', DOMAIN, {'device_IDs': device_list}, config)


    # get fresh data from devices NOT used now
    #def update_all():
    #    for device_id in hass.data[DOMAIN]['devices'].values():
    #        for command in SUPPORTED_COMMANDS.values():
    #            publish_request(device_id, command)
    
    #hass.data[DOMAIN]['update'] = update_all

    # Return boolean to indicate that initialization was successfully.
    return True
