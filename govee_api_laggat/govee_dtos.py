"""dto's used in the Govee API"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class GoveeSource(Enum):
    HISTORY = "history"
    API = "api"
    BLE = "ble"


class GoveeDeviceType(Enum):
    """Defines the type of the device"""
    DEVICE = "device"
    APPLIANCE_DEVICE = "appliance_device"


@dataclass
class GoveeDeviceMode(object):
    """Mode of a Govee device"""
    name: str  # Name of the mode
    value: str  # Value of this mode


@dataclass
class GoveeDevice(object):
    """Govee Device DTO."""
    device_type: GoveeDeviceType  # type of this device. Defines which API  need to be used to control this device
    device: str  # name of the device, must e unique
    model: str  # model information
    device_name: str  # custom name of that device configured by user
    controllable: bool  # is the device controllable?
    retrievable: bool  # do we get state from Govee API for this device?
    support_cmds: List[str]  # list of all supported commands
    support_turn: bool  # on/off is supported
    support_brightness: bool  # brightness control is supported
    support_color: bool  # color control is supported
    support_color_tem: bool  # color temperature control is supported
    support_mode: bool  # supports the setting of a specific mode
    online: bool  # is the device online (connected to Govee API, and the library can connect the same API)
    power_state: bool  # On/Off state
    modes: List[GoveeDeviceMode]  # modes the device can have (if device has mode functionality)
    mode: GoveeDeviceMode
    brightness: int  # brightness state
    color: Tuple[int, int, int]  # color state
    color_temp: int  # color temperature state
    timestamp: int  # timestamp of last change
    source: GoveeSource  # source of the last change, API or History
    error: str  # last and active error
    lock_set_until: int  # we do not allow a set command until that time in seconds passed
    lock_get_until: int  # we do not allow to get state until that time in seconds passed
    learned_set_brightness_max: int  # 100 or 255, defining how we need to set brightness for this device
    learned_get_brightness_max: int  # 100 or 255, defining how we need to read brightness state for this device
    before_set_brightness_turn_on: bool  # defines if we need to send a ON command before we can set brightness
    config_offline_is_off: bool  # if the device is offline, show it as off, or show it in the last known on/off state.
