#!/usr/bin/env python3
"""
USB Mode Switcher for Huawei USB modems
Automatically detects and switches Huawei devices from storage mode to modem mode
"""

import os
import sys
import time
import json
import subprocess
import glob
from pathlib import Path
from datetime import datetime, timezone

# Try to import pyudev if available (optional)
try:
    import pyudev
    PYUDEV_AVAILABLE = True
except ImportError:
    PYUDEV_AVAILABLE = False

# Import custom logger and gammu_probe
try:
    from logger import get_logger, status_modem, status_mqtt
    _LOGGER = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s UTC - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _LOGGER = logging.getLogger(__name__)
    # Fallback status functions if logger module not available
    def status_modem(*args, **kwargs):
        pass
    def status_mqtt(*args, **kwargs):
        pass

# Import gammu_probe
try:
    from gammu_probe import probe_all_connections, save_probe_log
    GAMMU_PROBE_AVAILABLE = True
except ImportError:
    GAMMU_PROBE_AVAILABLE = False
    _LOGGER.warning("gammu_probe module not available, connection testing disabled")

if PYUDEV_AVAILABLE:
    _LOGGER.debug("pyudev is available for enhanced device detection")
else:
    _LOGGER.debug("pyudev not available, using lsusb and sysfs for device detection")

# Known Huawei VID:PID pairs in storage mode with descriptions
HUAWEI_STORAGE_MODE_DEVICES = {
    ('12d1', '1506'): 'Huawei E3276 storage mode',
    ('12d1', '1f01'): 'Huawei common storage mode',
    ('12d1', '1f02'): 'Huawei alternative storage mode',
    ('12d1', '1038'): 'Huawei storage mode variant',
    ('12d1', '1446'): 'Huawei another storage mode',
    ('12d1', '14fe'): 'Huawei storage mode variant',
    ('12d1', '1520'): 'Huawei storage mode variant',
}

# Common Huawei modem patterns for product/model strings
HUAWEI_MODEM_PATTERNS = [
    'e3276', 'e3131', 'e3372', 'e3531', 'e353', 'e173',
    'huawei', 'mobile_connect', 'mobile connect'
]

# Timeout for waiting for serial devices to appear
DEVICE_WAIT_TIMEOUT = 30  # seconds
POLL_INTERVAL = 1  # seconds

def run_command(cmd, timeout=10, env=None):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        _LOGGER.error(f"Command timed out: {' '.join(cmd)}")
        return -1, "", "Timeout"
    except Exception as e:
        _LOGGER.error(f"Error running command {' '.join(cmd)}: {e}")
        return -1, "", str(e)

def detect_huawei_storage_devices():
    """Detect Huawei devices in storage mode using lsusb"""
    devices = []
    
    # Try to run lsusb
    returncode, stdout, stderr = run_command(['lsusb'])
    
    if returncode != 0:
        _LOGGER.warning("lsusb not available or failed")
        return devices
    
    lines = stdout.strip().split('\n')
    for line in lines:
        # lsusb format: Bus XXX Device YYY: ID vvvv:pppp ...
        if 'ID' in line:
            parts = line.split('ID')
            if len(parts) > 1:
                id_part = parts[1].strip().split()[0]
                if ':' in id_part:
                    vid, pid = id_part.split(':')
                    vid = vid.lower()
                    pid = pid.lower()
                    
                    # Check if this is a known Huawei storage mode device
                    if (vid, pid) in HUAWEI_STORAGE_MODE_DEVICES:
                        description = HUAWEI_STORAGE_MODE_DEVICES[(vid, pid)]
                        _LOGGER.info(f"Found Huawei device in storage mode: {vid}:{pid} ({description})")
                        devices.append((vid, pid))
    
    return devices

def switch_usb_mode(vid, pid):
    """Switch USB mode using usb_modeswitch"""
    _LOGGER.info(f"Attempting to switch USB mode for device {vid}:{pid}")
    
    # Try standard switching with -J flag (eject storage)
    _LOGGER.info(f"Running usb_modeswitch -v 0x{vid} -p 0x{pid} -J")
    returncode, stdout, stderr = run_command(
        ['usb_modeswitch', '-v', f'0x{vid}', '-p', f'0x{pid}', '-J'],
        timeout=20
    )
    
    if returncode == 0:
        _LOGGER.info(f"Successfully sent mode switch command for {vid}:{pid}")
        return True
    else:
        _LOGGER.warning(f"Mode switch with -J flag failed, trying -R flag")
        # Try with -R flag (reset)
        returncode, stdout, stderr = run_command(
            ['usb_modeswitch', '-v', f'0x{vid}', '-p', f'0x{pid}', '-R'],
            timeout=20
        )
        
        if returncode == 0:
            _LOGGER.info(f"Successfully sent mode switch command for {vid}:{pid} with -R")
            return True
        else:
            _LOGGER.error(f"Failed to switch mode for {vid}:{pid}: {stderr}")
            return False

def wait_for_serial_devices(timeout=DEVICE_WAIT_TIMEOUT):
    """Wait for serial devices to appear"""
    _LOGGER.info(f"Waiting up to {timeout} seconds for serial devices to appear...")
    
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        # Check for /dev/ttyUSB* devices
        tty_devices = glob.glob('/dev/ttyUSB*')
        
        if tty_devices:
            _LOGGER.info(f"Found {len(tty_devices)} serial device(s): {', '.join(tty_devices)}")
            return True
        
        time.sleep(POLL_INTERVAL)
    
    _LOGGER.warning(f"No serial devices appeared after {timeout} seconds")
    return False

def get_device_info_from_path(dev_path):
    """Get device metadata from sysfs or pyudev"""
    metadata = {
        'path': dev_path,
        'vendor': 'unknown',
        'product': 'unknown',
        'model': 'unknown',
        'serial': 'unknown',
        'manufacturer': 'unknown',
        'by_id_path': None
    }
    
    # Try pyudev first if available
    if PYUDEV_AVAILABLE:
        try:
            context = pyudev.Context()
            device = pyudev.Devices.from_device_file(context, dev_path)
            
            # Get parent USB device
            usb_device = device.find_parent('usb', 'usb_device')
            if usb_device:
                metadata['vendor'] = usb_device.get('ID_VENDOR_ID', 'unknown')
                metadata['product'] = usb_device.get('ID_MODEL_ID', 'unknown')
                metadata['model'] = usb_device.get('ID_MODEL', 'unknown')
                metadata['serial'] = usb_device.get('ID_SERIAL_SHORT', 'unknown')
                metadata['manufacturer'] = usb_device.get('ID_VENDOR', 'unknown')
                
                # Get by-id path if available
                by_id_links = list(usb_device.device_links)
                for link in by_id_links:
                    if '/dev/serial/by-id/' in link:
                        metadata['by_id_path'] = link
                        break
                
                _LOGGER.debug(f"Retrieved device info via pyudev for {dev_path}: vendor={metadata['vendor']}, model={metadata['model']}")
                return metadata
        except Exception as e:
            _LOGGER.debug(f"Error using pyudev for {dev_path}, falling back to sysfs: {e}")
    
    # Fallback to sysfs
    # The ttyUSB devices are typically under /sys/class/tty/ttyUSBX/
    dev_name = os.path.basename(dev_path)
    sys_path = f'/sys/class/tty/{dev_name}'
    
    if os.path.exists(sys_path):
        # Try to read vendor/product from device path
        try:
            device_link = os.path.join(sys_path, 'device')
            if os.path.exists(device_link):
                # Walk up to find idVendor and idProduct
                current = os.path.realpath(device_link)
                for _ in range(5):  # Look up to 5 levels
                    vendor_file = os.path.join(current, '../idVendor')
                    product_file = os.path.join(current, '../idProduct')
                    manufacturer_file = os.path.join(current, '../manufacturer')
                    
                    if os.path.exists(vendor_file):
                        with open(vendor_file, 'r') as f:
                            metadata['vendor'] = f.read().strip()
                    
                    if os.path.exists(product_file):
                        with open(product_file, 'r') as f:
                            metadata['product'] = f.read().strip()
                    
                    if os.path.exists(manufacturer_file):
                        with open(manufacturer_file, 'r') as f:
                            metadata['manufacturer'] = f.read().strip()
                    
                    if metadata['vendor'] != 'unknown' and metadata['product'] != 'unknown':
                        break
                    
                    current = os.path.dirname(current)
        except Exception as e:
            _LOGGER.debug(f"Error reading device info from sysfs for {dev_path}: {e}")
    
    return metadata

def discover_serial_devices():
    """Discover all available serial devices and their metadata"""
    devices = []
    
    # Find /dev/ttyUSB* devices
    tty_devices = sorted(glob.glob('/dev/ttyUSB*'))
    
    for dev_path in tty_devices:
        metadata = get_device_info_from_path(dev_path)
        devices.append(metadata)
        _LOGGER.info(f"Discovered device: {dev_path} (vendor: {metadata['vendor']}, product: {metadata['product']})")
    
    # Also check /dev/serial/by-id/* and associate with existing devices
    by_id_devices = glob.glob('/dev/serial/by-id/*')
    for by_id_path in by_id_devices:
        # Resolve symlink to actual device
        real_path = os.path.realpath(by_id_path)
        # Check if this device is already in our list
        found = False
        for dev in devices:
            if dev['path'] == real_path:
                # Associate the by-id path with this device
                dev['by_id_path'] = by_id_path
                _LOGGER.debug(f"Associated by-id path {by_id_path} with {real_path}")
                found = True
                break
        
        if not found:
            # Device not in list yet, add it
            metadata = get_device_info_from_path(real_path)
            metadata['by_id_path'] = by_id_path
            devices.append(metadata)
            _LOGGER.info(f"Discovered device by-id: {by_id_path} -> {real_path}")
    
    return devices

def save_device_list(devices, output_path='/data/available_usb.json'):
    """Save discovered devices to JSON file"""
    try:
        # Ensure /data directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(devices, f, indent=2)
        
        _LOGGER.info(f"Saved device list to {output_path}")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to save device list to {output_path}: {e}")
        return False

def is_huawei_device(device_metadata):
    """Check if a device is a HUAWEI device based on metadata or by-id path
    
    Priority order:
    1. Check by-id path for 'HUAWEI' (case-insensitive)
    2. Check vendor ID (12d1 is Huawei)
    3. Check manufacturer field for 'Huawei' (case-insensitive)
    4. Check model/product for common Huawei modem patterns
    """
    # Priority 1: Check by-id path if available
    by_id_path = device_metadata.get('by_id_path', '')
    if by_id_path and 'huawei' in by_id_path.lower():
        _LOGGER.debug(f"Device identified as Huawei via by-id path: {by_id_path}")
        return True
    
    # Priority 2: Check vendor ID (12d1 is Huawei)
    vendor = device_metadata.get('vendor', '').lower()
    if vendor == '12d1':
        _LOGGER.debug(f"Device identified as Huawei via vendor ID: {vendor}")
        return True
    
    # Priority 3: Check manufacturer
    manufacturer = device_metadata.get('manufacturer', '').lower()
    if 'huawei' in manufacturer:
        _LOGGER.debug(f"Device identified as Huawei via manufacturer: {manufacturer}")
        return True
    
    # Priority 4: Check model name for common Huawei patterns
    model = device_metadata.get('model', '').lower()
    product = device_metadata.get('product', '').lower()
    
    for pattern in HUAWEI_MODEM_PATTERNS:
        if pattern in model or pattern in product:
            _LOGGER.debug(f"Device identified as Huawei via model/product pattern: {pattern}")
            return True
    
    return False

def generate_gammurc(device_path, connection='at115200'):
    """Generate /etc/gammurc with specified connection as primary"""
    gammurc_path = '/etc/gammurc'
    
    # Gammurc content with specified connection as primary and fallbacks
    gammurc_content = f"""[gammu]
port = {device_path}
connection = {connection}

[gammu1]
port = {device_path}
connection = at9600

[gammu2]
port = {device_path}
connection = at
"""
    
    try:
        with open(gammurc_path, 'w') as f:
            f.write(gammurc_content)
        _LOGGER.info(f"Successfully generated {gammurc_path} for device {device_path} with connection {connection}")
        _LOGGER.debug(f"Gammurc content:\n{gammurc_content}")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to generate {gammurc_path}: {e}")
        return False

def publish_diagnostics_to_mqtt(diagnostics, device_info=None):
    """
    Publish diagnostics to MQTT topic sms-gateway/diagnostics
    
    Args:
        diagnostics: Diagnostics dict from gammu_probe
        device_info: Optional device information dict
    """
    try:
        import paho.mqtt.client as mqtt
        
        # Load MQTT config from options
        mqtt_host = None
        mqtt_port = 1883
        mqtt_user = ''
        mqtt_password = ''
        
        try:
            with open('/data/options.json', 'r') as f:
                options = json.load(f)
                mqtt_config = options.get('mqtt', {})
                mqtt_host = mqtt_config.get('broker', 'core-mosquitto')
                mqtt_port = mqtt_config.get('port', 1883)
                mqtt_user = mqtt_config.get('username', '')
                mqtt_password = mqtt_config.get('password', '')
        except Exception as e:
            _LOGGER.debug(f"Could not load MQTT config from options: {e}")
            mqtt_host = os.getenv('MQTT_HOST', 'core-mosquitto')
            mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
            mqtt_user = os.getenv('MQTT_USER', '')
            mqtt_password = os.getenv('MQTT_PASSWORD', '')
        
        if not mqtt_host:
            _LOGGER.warning("MQTT host not configured, skipping diagnostics publication")
            return
        
        # Add device info to diagnostics if provided
        if device_info:
            diagnostics['device_info'] = device_info
        
        # Create MQTT client and publish
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if mqtt_user:
            client.username_pw_set(mqtt_user, mqtt_password)
        
        _LOGGER.info(f"Publishing diagnostics to MQTT: {mqtt_host}:{mqtt_port}")
        client.connect(mqtt_host, mqtt_port, 60)
        client.loop_start()
        
        # Publish with retain flag
        result = client.publish('sms-gateway/diagnostics', json.dumps(diagnostics), retain=True)
        
        # Wait a bit for publish to complete
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
        
        if result.rc == 0:
            _LOGGER.info("Successfully published diagnostics to MQTT topic: sms-gateway/diagnostics")
        else:
            _LOGGER.warning(f"Failed to publish diagnostics to MQTT, return code: {result.rc}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to publish diagnostics to MQTT: {e}")
        import traceback
        _LOGGER.debug(traceback.format_exc())

def save_diagnostics(diagnostics, output_path='/data/sms_gateway_diagnostics.json'):
    """Save diagnostics to JSON file"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(diagnostics, f, indent=2)
        _LOGGER.info(f"Saved diagnostics to {output_path}")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to save diagnostics to {output_path}: {e}")
        return False

def main():
    """Main USB switcher logic"""
    _LOGGER.info("=" * 60)
    _LOGGER.info("USB Mode Switcher for SMS Gateway v1.0.16")
    _LOGGER.info("=" * 60)
    
    # Load device from options if configured
    configured_device = None
    try:
        with open('/data/options.json', 'r') as f:
            options = json.load(f)
            configured_device = options.get('device')
            if configured_device:
                _LOGGER.info(f"Device configured in options: {configured_device}")
                _LOGGER.info("User-configured device will be respected (not overridden)")
    except Exception as e:
        _LOGGER.debug(f"Could not load options.json: {e}")
    
    # Step 1: Detect Huawei devices in storage mode
    _LOGGER.info("Step 1: Detecting Huawei devices in storage mode...")
    storage_devices = detect_huawei_storage_devices()
    
    if storage_devices:
        _LOGGER.info(f"Found {len(storage_devices)} Huawei device(s) in storage mode")
        
        # Step 2: Switch each device
        for vid, pid in storage_devices:
            _LOGGER.info(f"Attempting USB mode switch for {vid}:{pid}...")
            success = switch_usb_mode(vid, pid)
            if success:
                _LOGGER.info(f"Mode switch command sent successfully for {vid}:{pid}")
            else:
                _LOGGER.warning(f"Mode switch failed for {vid}:{pid}")
        
        # Step 3: Wait for serial devices to appear
        _LOGGER.info("Step 2: Waiting for serial devices to appear after mode switch...")
        wait_for_serial_devices()
    else:
        _LOGGER.info("No Huawei devices in storage mode detected")
        _LOGGER.info("Checking for existing serial devices...")
    
    # Step 4: Discover all serial devices
    _LOGGER.info("Step 3: Discovering available serial devices...")
    devices = discover_serial_devices()
    
    # Step 5: Save device list
    if devices:
        _LOGGER.info(f"Found {len(devices)} serial device(s)")
        save_device_list(devices)
    else:
        _LOGGER.warning("No serial devices found")
        # Still save an empty list
        save_device_list([])
    
    # Step 6: Intelligent device selection
    # Priority: configured device > single auto-detected device > HUAWEI among multiple > none
    device_to_use = None
    selection_reason = None
    selected_dev_info = None  # Track selected device info for diagnostics
    
    if configured_device:
        # User has explicitly configured a device, respect that choice
        device_to_use = configured_device
        selection_reason = "user-configured in add-on options"
        _LOGGER.info(f"Using configured device: {configured_device}")
        _LOGGER.info(f"Reason: {selection_reason}")
        # Try to find device info if available
        for dev in devices:
            if dev['path'] == configured_device or dev.get('by_id_path') == configured_device:
                selected_dev_info = dev
                break
    elif len(devices) == 0:
        # No devices found
        _LOGGER.warning("No serial devices found. The modem may not be connected or may require manual intervention")
        _LOGGER.info("The SMS Gateway will start in modem-not-connected mode and will continue polling")
        selection_reason = "no devices found"
    elif len(devices) == 1:
        # Exactly one device found - auto-select it
        selected_dev_info = devices[0]
        device_to_use = selected_dev_info['path']
        selection_reason = "single device auto-detected"
        _LOGGER.info(f"Exactly one device found, auto-selecting: {device_to_use}")
        _LOGGER.info(f"Reason: {selection_reason}")
    elif len(devices) > 1:
        # Multiple devices found - apply intelligent Huawei preference
        _LOGGER.info("Multiple serial devices found:")
        for i, dev in enumerate(devices, 1):
            _LOGGER.info(f"  {i}. {dev['path']} (vendor: {dev['vendor']}, product: {dev['product']}, model: {dev.get('model', 'unknown')})")
        
        # Apply Huawei preference logic
        huawei_devices = []
        for dev in devices:
            if is_huawei_device(dev):
                huawei_devices.append(dev)
        
        if huawei_devices:
            # Prefer the first Huawei device found
            # Prefer by-id path if available for stability
            selected_dev_info = huawei_devices[0]
            device_to_use = selected_dev_info.get('by_id_path') or selected_dev_info['path']
            selection_reason = "Huawei modem intelligently selected from multiple devices"
            
            _LOGGER.info(f"Huawei device detected among multiple devices, auto-selecting: {device_to_use}")
            _LOGGER.info(f"Reason: {selection_reason}")
            _LOGGER.info(f"Device details: vendor={selected_dev_info['vendor']}, product={selected_dev_info['product']}, "
                        f"model={selected_dev_info.get('model', 'unknown')}, manufacturer={selected_dev_info.get('manufacturer', 'unknown')}")
        else:
            # No HUAWEI device found, keep existing behavior
            selection_reason = "multiple non-Huawei devices, manual config required"
            _LOGGER.warning("No HUAWEI device found among multiple devices")
            _LOGGER.warning("Please configure the 'device' option in the add-on configuration to specify which device to use")
            _LOGGER.warning("Device list saved to /data/available_usb.json for reference")
    
    # Step 7: Test connections and generate gammurc if device was selected
    diagnostics = None
    if device_to_use:
        os.environ['DEVICE'] = device_to_use
        _LOGGER.info(f"Set DEVICE environment variable to: {device_to_use}")
        
        # Test gammu connections using gammu_probe module
        _LOGGER.info("Step 4: Testing gammu connections and generating configuration...")
        
        if GAMMU_PROBE_AVAILABLE:
            test_results = probe_all_connections(device_to_use, ['at115200', 'at9600', 'at'])
            
            diagnostics = test_results['diagnostics']
            diagnostics['selection_reason'] = selection_reason
            diagnostics['configured_device'] = configured_device
            
            # Save diagnostics
            save_diagnostics(diagnostics)
            
            # Save detailed gammu log
            save_probe_log(test_results['all_results'], device_to_use)
            
            # Generate final gammurc with successful connection
            successful_conn = test_results['successful_connection']
            if successful_conn:
                generate_gammurc(device_to_use, successful_conn)
                _LOGGER.info(f"✓ Gammu successfully initialized with connection: {successful_conn}")
                
                # Use status_modem helper to log success
                status_modem('connected', device=device_to_use, connection=successful_conn, 
                           selection_reason=selection_reason)
                
                # Publish success diagnostics to MQTT
                device_info = {}
                if selected_dev_info:
                    device_info = {
                        'vendor': selected_dev_info.get('vendor', 'unknown'),
                        'product': selected_dev_info.get('product', 'unknown'),
                        'model': selected_dev_info.get('model', 'unknown')
                    }
                publish_diagnostics_to_mqtt(diagnostics, device_info)
                
                # Use status_mqtt helper to log diagnostics publication
                try:
                    with open('/data/options.json', 'r') as f:
                        options = json.load(f)
                        mqtt_config = options.get('mqtt', {})
                        mqtt_host = mqtt_config.get('broker', 'core-mosquitto')
                        mqtt_port = mqtt_config.get('port', 1883)
                    status_mqtt('connected', broker=mqtt_host, port=mqtt_port, 
                              topic='sms-gateway/diagnostics', message='diagnostics_published')
                except:
                    pass
            else:
                # No working connection found - generate with default but still publish diagnostics
                generate_gammurc(device_to_use, 'at115200')
                _LOGGER.warning("⚠ All gammu connection tests failed. gammurc generated with default settings.")
                _LOGGER.warning("Check /tmp/gammu.log and /data/sms_gateway_diagnostics.json for details")
                
                # Use status_modem helper to log failure
                status_modem('error', device=device_to_use, connection='at115200', 
                           error='all_connections_failed', selection_reason=selection_reason)
                
                # Publish failure diagnostics to MQTT
                publish_diagnostics_to_mqtt(diagnostics)
        else:
            # Fallback if gammu_probe not available - use old method
            _LOGGER.warning("gammu_probe not available, generating gammurc with default settings")
            generate_gammurc(device_to_use, 'at115200')
    
    # Step 8: Exec gammu_mqtt.py to replace this process
    _LOGGER.info("=" * 60)
    _LOGGER.info("Starting SMS Gateway (gammu_mqtt.py)...")
    if device_to_use:
        _LOGGER.info(f"Selected device: {device_to_use}")
        _LOGGER.info(f"Selection reason: {selection_reason}")
    else:
        _LOGGER.info("No device selected - will run in polling mode")
    _LOGGER.info("=" * 60)
    
    # Exec replaces current process, so gammu_mqtt.py inherits all environment variables
    gammu_script = '/app/gammu_mqtt.py'
    
    try:
        os.execv(sys.executable, [sys.executable, gammu_script])
    except Exception as e:
        _LOGGER.error(f"Failed to exec gammu_mqtt.py: {e}")
        _LOGGER.error("Attempting to run as subprocess instead...")
        # Fallback: run as subprocess
        sys.exit(subprocess.call([sys.executable, gammu_script]))

if __name__ == '__main__':
    main()
