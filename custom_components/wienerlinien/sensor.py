"""
A integration that allows you to get information about next departure from specified stop.
For more details about this component, please refer to the documentation at
https://github.com/tofuSCHNITZEL/home-assistant-wienerlinien
"""
import logging
from datetime import timedelta

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.entity import Entity

from custom_components.wienerlinien.const import BASE_URL, DEPARTURES

CONF_STOPS = "stops"
CONF_APIKEY = "apikey"
CONF_FIRST_NEXT = "firstnext"

SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_APIKEY): cv.string,
        vol.Optional(CONF_STOPS, default=None): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_FIRST_NEXT, default="first"): cv.string,
    }
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup."""
    _LOGGER.info("Loading WienerLinien")
    stops = config.get(CONF_STOPS)
    firstnext = config.get(CONF_FIRST_NEXT)
    dev = []
    for stopid in stops:
        api = WienerlinienAPI(async_create_clientsession(hass), hass.loop, stopid)
        data = await api.get_json()
        for monitor in data["data"]["monitors"]:
            try:
                _LOGGER.info("Appending Wienerlinien Monitor: " + monitor["locationStop"]["properties"]["attributes"]["rbl"])
                dev.append(WienerlinienSensor(api, monitor, 'next'))
                #dev.append(WienerlinienSensor(api, monitor, 'following'))
            except Exception:
                raise PlatformNotReady()
    add_devices_callback(dev, True)


class WienerlinienSensor(Entity):
    """WienerlinienSensor."""

    def __init__(self, api, monitor, firstnext):
        """Initialize."""
        self.api = api
        self.firstnext = firstnext
        self._name = monitor["locationStop"]["properties"]["title"] + ": " +  monitor["lines"][0]["name"] + " towards " + monitor["lines"][0]["towards"]
        self._lineId = monitor["lines"][0]["linienId"]
        self._monitor = monitor
        self._state = None
        self.attributes = {}
        self._attr_unique_id = self._lineId +"_" +  monitor["locationStop"]["properties"]["attributes"]["rbl"] +"_" + monitor["lines"][0]["direction"]

    async def async_update(self):
        """Update data."""
        try:
            data = await self.api.get_json()
            _LOGGER.debug(data)
            if data is None:
                return
            data = data.get("data", {})
        except:
            _LOGGER.debug("Could not get new state")
            return

        if data is None:
            return
        try:
            for monitor in data["data"]["monitors"]:
                if monitor["lines"][0]["linienId"] == self._lineId:
                    line = monitor["lines"][0]
                    departure = line["departures"]["departure"][
                        DEPARTURES[self.firstnext]["key"]
                    ]
                    if "timeReal" in departure["departureTime"]:
                        self._state = departure["departureTime"]["timeReal"]
                    elif "timePlanned" in departure["departureTime"]:
                        self._state = departure["departureTime"]["timePlanned"]
                    else:
                        self._state = self._state
        
                    self.attributes = {
                        "destination": line["towards"],
                        "platform": line["platform"],
                        "direction": line["direction"],
                        "name": line["name"],
                        "countdown": departure["departureTime"]["countdown"],
                    }
        except Exception:
            pass

    @property
    def name(self):
        """Return name."""
        return DEPARTURES[self.firstnext]["name"].format(self._name)

    @property
    def state(self):
        """Return state."""
        if self._state is None:
            return self._state
        else:
            return f"{self._state[:-2]}:{self._state[26:]}"

    @property
    def icon(self):
        """Return icon."""
        return "mdi:bus"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self.attributes

    @property
    def device_class(self):
        """Return device_class."""
        return "timestamp"


class WienerlinienAPI:
    """Call API."""

    def __init__(self, session, loop, stopid):
        """Initialize."""
        self.session = session
        self.loop = loop
        self.stopid = stopid

    async def get_json(self):
        """Get json from API endpoint."""
        value = None
        url = BASE_URL.format(self.stopid)
        try:
            async with async_timeout.timeout(10):
                response = await self.session.get(url)
                value = await response.json()
        except Exception:
            pass

        return value
