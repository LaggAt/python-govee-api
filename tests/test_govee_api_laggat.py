import asyncio
from asynctest import TestCase, MagicMock, patch, CoroutineMock
from aiohttp import ClientSession
from datetime import datetime
from time import time

from govee_api_laggat import Govee, GoveeDevice

_API_URL = "https://developer-api.govee.com"
_API_KEY = "SUPER_SECRET_KEY"
# The maximum number of requests you're permitted to make per minute.
_RATELIMIT_TOTAL = 'Rate-Limit-Total'
# The number of requests remaining in the current rate limit window.
_RATELIMIT_REMAINING = 'Rate-Limit-Remaining'
# The time at which the current rate limit window resets in UTC epoch seconds.
_RATELIMIT_RESET = 'Rate-Limit-Reset'

# json results for lights
JSON_DEVICE_H6163 = {
    'device': '40:83:FF:FF:FF:FF:FF:FF',
    'model': 'H6163',
    'deviceName': 'H6131_FFFF',
    'controllable': True,
    'retrievable': True,
    'supportCmds': [
        'turn',
        'brightness',
        'color',
        'colorTem'
    ]
}
JSON_DEVICE_H6104 = {
    'device': '99:F8:FF:FF:FF:FF:FF:FF',
    'model': 'H6104',
    'deviceName': 'H6104_22DC',
    'controllable': True,
    'retrievable': False,
    'supportCmds': [
        'turn',
        'brightness',
        'color',
        'colorTem'
    ]
}
JSON_DEVICES = {
    'data': {
        'devices': [
            JSON_DEVICE_H6163,
            JSON_DEVICE_H6104
        ]
    }
}
JSON_OK_RESPONSE = {'code': 200, 'data': {}, 'message': 'Success'}
# light device
DUMMY_DEVICE_H6163 = GoveeDevice(
    device=JSON_DEVICE_H6163['device'],
    model=JSON_DEVICE_H6163['model'],
    device_name=JSON_DEVICE_H6163['deviceName'],
    controllable=JSON_DEVICE_H6163['controllable'],
    retrievable=JSON_DEVICE_H6163['retrievable'],
    support_cmds=JSON_DEVICE_H6163['supportCmds'],
    support_turn='turn' in JSON_DEVICE_H6163['supportCmds'],
    support_brightness='brightness' in JSON_DEVICE_H6163['supportCmds'],
    support_color='color' in JSON_DEVICE_H6163['supportCmds'],
    support_color_tem='colorTem' in JSON_DEVICE_H6163['supportCmds'],
    online=True,
    power_state=True,
    brightness=254,
    color=(139, 0, 255),
    timestamp = 0,
    source = 'api', # this device supports status
    error = None
)
DUMMY_DEVICE_H6104 = GoveeDevice(
    device=JSON_DEVICE_H6104['device'],
    model=JSON_DEVICE_H6104['model'],
    device_name=JSON_DEVICE_H6104['deviceName'],
    controllable=JSON_DEVICE_H6104['controllable'],
    retrievable=JSON_DEVICE_H6104['retrievable'],
    support_cmds=JSON_DEVICE_H6104['supportCmds'],
    support_turn='turn' in JSON_DEVICE_H6104['supportCmds'],
    support_brightness='brightness' in JSON_DEVICE_H6104['supportCmds'],
    support_color='color' in JSON_DEVICE_H6104['supportCmds'],
    support_color_tem='colorTem' in JSON_DEVICE_H6104['supportCmds'],
    online=True,
    power_state=False,
    brightness=0,
    color=(0, 0, 0),
    timestamp = 0,
    source = 'history',
    error = None
)
DUMMY_DEVICES = {
    DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163,
    DUMMY_DEVICE_H6104.device: DUMMY_DEVICE_H6104,
}

# json results for light states
JSON_DEVICE_STATE = {
    "data": {
        "device": JSON_DEVICE_H6163['device'],
        "model": JSON_DEVICE_H6163['model'],
        "properties": [
            {
                "online": True
            },
            {
                "powerState": "on"
            },
            {
                "brightness": 254
            },
            {
                "color": {
                    "r": 139,
                    "b": 255,
                    "g": 0
                }
            }
        ]
    },
    "message": "Success",
    "code": 200
}

class GoveeTests(TestCase):

    @patch('aiohttp.ClientSession.get')
    def test_ping(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Pong"
        )
        # act

        async def ping():
            async with Govee(_API_KEY) as govee:
                return await govee.ping()
        result, err = loop.run_until_complete(ping())
        # assert
        assert not err
        assert result
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/ping'

    @patch('aiohttp.ClientSession.get')
    @patch('asyncio.sleep')
    def test_rate_limiter(self, mock_sleep, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            _RATELIMIT_TOTAL: '100',
            _RATELIMIT_REMAINING: '5',
            _RATELIMIT_RESET: f'{sleep_until}'
        }
        mock_sleep.return_value.__aenter__.return_value.text = CoroutineMock()
        # act
        async def get_devices():
            async with Govee(_API_KEY) as govee:
                assert govee.rate_limit_on == 5
                assert govee.rate_limit_total == 100
                assert govee.rate_limit_reset == 0
                assert govee.rate_limit_remaining == 100
                # first run uses defaults, so ping returns immediatly
                _, err1 = await govee.get_devices()
                assert mock_sleep.call_count == 0
                assert govee.rate_limit_remaining == 5
                assert govee.rate_limit_reset == sleep_until
                # second run, rate limit sleeps until the second is over
                _, err2 = await govee.get_devices()
                assert mock_sleep.call_count == 1
                return err1, err2
        err1, err2 = loop.run_until_complete(get_devices())
        # assert
        assert not err1
        assert not err2
        assert mock_get.call_count == 2

    @patch('aiohttp.ClientSession.get')
    def test_rate_limit_exceeded(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 429 # too many requests
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Rate limit exceeded, retry in 1 seconds."
        )
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            _RATELIMIT_TOTAL: '100',
            _RATELIMIT_REMAINING: '5',
            _RATELIMIT_RESET: f'{sleep_until}'
        }
        # act
        async def get_devices():
            async with Govee(_API_KEY) as govee:
                assert govee.rate_limit_on == 5
                assert govee.rate_limit_total == 100
                assert govee.rate_limit_reset == 0
                assert govee.rate_limit_remaining == 100
                # first run uses defaults, so ping returns immediatly
                return await govee.get_devices()
        result1, err1 = loop.run_until_complete(get_devices())
        # assert
        assert not result1
        assert err1 == 'API-Error 429: Rate limit exceeded, retry in 1 seconds.'
        assert mock_get.call_count == 1

    @patch('aiohttp.ClientSession.get')
    def test_rate_limiter_custom_threshold(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        sleep_until = datetime.timestamp(datetime.now()) + 1
        mock_get.return_value.__aenter__.return_value.headers = {
            _RATELIMIT_TOTAL: '100',
            _RATELIMIT_REMAINING: '5',  # by default below 5 it is sleeping
            _RATELIMIT_RESET: f'{sleep_until}'
        }
        # act
        async def get_devices():
            async with Govee(_API_KEY) as govee:
                govee.rate_limit_on = 4
                assert govee.rate_limit_on == 4  # set did work
                # first run uses defaults, so ping returns immediatly
                start = time()
                _, err1 = await govee.get_devices()
                delay1 = start - time()
                # second run, doesn't rate limit either
                _, err2 = await govee.get_devices()
                delay2 = start - time()
                return delay1, err1, delay2, err2
        delay1, err1, delay2, err2 = loop.run_until_complete(get_devices())
        # assert
        assert delay1 < 0.10  # this should return immediatly
        assert delay2 < 0.10  # this should return immediatly
        assert not err1
        assert not err2
        assert mock_get.call_count == 2

    @patch('aiohttp.ClientSession.get')
    def test_get_devices(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        # act

        async def getDevices():
            async with Govee(_API_KEY) as govee:
                return await govee.get_devices()
        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err == None
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        assert mock_get.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert len(result) == 2
        assert isinstance(result[0], GoveeDevice)
        assert result[0].model == 'H6163'
        assert result[1].model == 'H6104'

    @patch('aiohttp.ClientSession.get')
    def test_get_devices_cache(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICES
        )
        # act

        async def getDevices():
            async with Govee(_API_KEY) as govee:
                result, err = await govee.get_devices()
                cache = govee.devices
                return result, cache
        result, cache = loop.run_until_complete(getDevices())
        # assert
        assert mock_get.call_count == 1
        assert len(result) == 2
        assert result == cache

    @patch('aiohttp.ClientSession.get')
    def test_get_devices_invalid_key(self, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_get.return_value.__aenter__.return_value.status = 401
        mock_get.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value={
                "INVALID_API_KEY"
            }
        )
        # act

        async def getDevices():
            async with Govee("INVALID_API_KEY") as govee:
                return await govee.get_devices()
        result, err = loop.run_until_complete(getDevices())
        # assert
        assert err
        assert "401" in err
        assert "INVALID_API_KEY" in err
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices'
        assert mock_get.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'INVALID_API_KEY'}
        assert len(result) == 0

    @patch('aiohttp.ClientSession.put')
    def test_turn_on(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def turn_on():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.turn_on(DUMMY_DEVICE_H6163)
        success, err = loop.run_until_complete(turn_on())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "turn",
                "value": "on"
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.put')
    def test_turn_on_auth_failure(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 401
        mock_put.return_value.__aenter__.return_value.text = CoroutineMock(
            return_value="Test auth failed"
        )
        # act

        async def turn_on():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.turn_on(DUMMY_DEVICE_H6163)
        success, err = loop.run_until_complete(turn_on())
        # assert
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "turn",
                "value": "on"
            }
        }
        assert success == False
        assert "401" in err  # http status
        assert "Test auth failed" in err  # http message
        assert "turn" in err  # command used
        assert DUMMY_DEVICE_H6163.device in err  # device used

    @patch('aiohttp.ClientSession.put')
    def test_turn_off_by_address(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def turn_off():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                # use device address here
                return await govee.turn_off(DUMMY_DEVICE_H6163.device)
        success, err = loop.run_until_complete(turn_off())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "turn",
                "value": "off"
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.get')
    @patch('govee_api_laggat.Govee._state_request_allowed')
    def test_get_states(self, mock_state_request_allowed, mock_get):
        # arrange
        loop = asyncio.get_event_loop()
        mock_state_request_allowed.return_value = True # always get live state
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICE_STATE
        )
        # act
        async def getDevices():
            async with Govee(_API_KEY) as govee:
                # inject devices for testing
                govee._devices = DUMMY_DEVICES
                #for dev in DUMMY_DEVICES:
                #    results_per_device[dev], errors_per_device[dev] = await govee.get_state(dev)
                states = await govee.get_states()
                return states
        states = loop.run_until_complete(getDevices())
        # assert
        assert mock_get.call_count == 1 # only retrievable devices
        assert mock_get.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/state'
        assert mock_get.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'
        }
        assert mock_get.call_args.kwargs['params']['device'] == DUMMY_DEVICE_H6163.device
        assert mock_get.call_args.kwargs['params']['model'] == DUMMY_DEVICE_H6163.model
        assert len(states) == 2
        # to compare the 
        DUMMY_DEVICE_H6163.timestamp = states[0].timestamp
        assert states[0] == DUMMY_DEVICE_H6163
        assert states[1] == DUMMY_DEVICE_H6104
        assert mock_state_request_allowed.call_count == 1

    @patch('aiohttp.ClientSession.put')
    def test_set_brightness_to_high(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        brightness = 255  # too high

        # act
        async def set_brightness():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_brightness(DUMMY_DEVICE_H6163, brightness)
        success, err = loop.run_until_complete(set_brightness())
        # assert
        assert success == False
        assert mock_put.call_count == 0
        assert "254" in err
        assert "brightness" in err

    @patch('aiohttp.ClientSession.put')
    def test_set_brightness_to_low(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        brightness = -1  # too high

        # act
        async def set_brightness():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_brightness(DUMMY_DEVICE_H6163, brightness)
        success, err = loop.run_until_complete(set_brightness())
        # assert
        assert success == False
        assert mock_put.call_count == 0
        assert "254" in err
        assert "brightness" in err

    @patch('aiohttp.ClientSession.put')
    def test_set_brightness(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act
        async def set_brightness():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_brightness(DUMMY_DEVICE_H6163.device, 42)
        success, err = loop.run_until_complete(set_brightness())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "brightness",
                "value": 42 * 100 // 254  # we need to control brightness betweenn 0 .. 100
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.put')
    def test_set_color_temp(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def set_color_temp():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_color_temp(DUMMY_DEVICE_H6163.device, 6000)
        success, err = loop.run_until_complete(set_color_temp())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "colorTem",
                "value": 6000
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.put')
    def test_set_color(self, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        # act

        async def set_color():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                return await govee.set_color(DUMMY_DEVICE_H6163.device, (42, 43, 44))
        success, err = loop.run_until_complete(set_color())
        # assert
        assert err == None
        assert mock_put.call_count == 1
        assert mock_put.call_args.kwargs['url'] == 'https://developer-api.govee.com/v1/devices/control'
        assert mock_put.call_args.kwargs['headers'] == {
            'Govee-API-Key': 'SUPER_SECRET_KEY'}
        assert mock_put.call_args.kwargs['json'] == {
            "device": DUMMY_DEVICE_H6163.device,
            "model": DUMMY_DEVICE_H6163.model,
            "cmd": {
                "name": "color",
                "value": {"r": 42, "g": 43, "b": 44}
            }
        }
        assert success == True

    @patch('aiohttp.ClientSession.put')
    @patch('aiohttp.ClientSession.get')
    def test_turn_on_and_get_cache_state(self, mock_get, mock_put):
        # arrange
        loop = asyncio.get_event_loop()
        mock_put.return_value.__aenter__.return_value.status = 200
        mock_put.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_OK_RESPONSE
        )
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = CoroutineMock(
            return_value=JSON_DEVICE_STATE # never touched
        )
        # act
        async def turn_on_and_get_state():
            async with Govee(_API_KEY) as govee:
                # inject a device for testing
                govee._devices = {DUMMY_DEVICE_H6163.device: DUMMY_DEVICE_H6163}
                await govee.turn_on(DUMMY_DEVICE_H6163)
                # getting state to early (2s after switching)
                return await govee.get_states()
        states = loop.run_until_complete(turn_on_and_get_state())
        # assert
        assert states[0].source == 'history'
        assert mock_put.call_count == 1
        assert mock_get.call_count == 0 # may not get state
