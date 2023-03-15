import logging
from datetime import datetime, timedelta

#from homeassistant.helpers.entity import Entity
#from homeassistant.helpers.restore_state import  RestoreEntity
#from homeassistant.helpers import async_dispatcher_connect
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,  
#    RestoreSensor, # not in master yet
    SensorStateClass,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT, ELECTRIC_POTENTIAL_VOLT, ELECTRIC_CURRENT_AMPERE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from . import DOMAIN, ZONES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Setup sensor platform"""
    device_list = discovery_info.get('device_IDs', [])
    entities = []
    for counter_id in device_list:
        entities.append(PowerSensor(device_id=counter_id))
        entities.append(VoltageSensor(device_id=counter_id))
        entities.append(CurrentSensor(device_id=counter_id))

        for tar_zone in ZONES: # mercury200.02 support 4 tarif zones
            entities.append(
                CounterSensor(device_id = counter_id, tarif_zone=tar_zone),
            )
    async_add_entities(entities)

#    coordinator = DataUpdateCoordinator(
#            hass,
#            _LOGGER,
#            name="sensor",
#            update_method=hass.data[DOMAIN]['update'],
#            update_interval=timedelta(seconds=60),
#        )


class CounterSensor(SensorEntity):
    """Counter class for T1..T4 values"""
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING


    def __init__(self, device_id:str, tarif_zone:str):
        self.device_id = device_id
        self.tarif_zone = tarif_zone
        self._attr_name = f"mercury200 {self.device_id} {tarif_zone}"
        super().__init__()

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self.hass.data[DOMAIN][self.device_id][self.tarif_zone]

    @property
    def device_state_attributes(self):
        attributes = {
            "device_id": self.device_id,
            "tarif_zone": self.tarif_zone,
            "topic": self.hass.data[DOMAIN][self.device_id]['topic']
        }
        return attributes


class PowerSensor(SensorEntity):
    """Current power"""
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device_id:str):
        self.device_id = device_id
        self._attr_name = f"mercury200 {self.device_id} power"
        super().__init__()

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self.hass.data[DOMAIN][self.device_id]['power']


class VoltageSensor(SensorEntity):
    """Current voltage"""
    _attr_native_unit_of_measurement = ELECTRIC_POTENTIAL_VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device_id:str):
        self.device_id = device_id
        self._attr_name = f"mercury200 {self.device_id} voltage"
        super().__init__()

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self.hass.data[DOMAIN][self.device_id]['voltage']

class CurrentSensor(SensorEntity):
    """Current ampere"""
    _attr_native_unit_of_measurement = ELECTRIC_CURRENT_AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device_id:str):
        self.device_id = device_id
        self._attr_name = f"mercury200 {self.device_id} current"
        super().__init__()

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self.hass.data[DOMAIN][self.device_id]['current']
