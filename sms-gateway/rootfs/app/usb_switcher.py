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
import logging
import glob
from pathlib import Path

# Try to import pyudev if available (optional)
try:
    import pyudev
    PYUDEV_AVAILABLE = True
except ImportError:
    PYUDEV_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s UTC - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_LOGGER = logging.getLogger(__name__)

if PYUDEV_AVAILABLE:
    _LOGGER.debug("pyudev is available for enhanced device detection")
else:
    _LOGGER.debug("pyudev not available, using lsusb and sysfs for device detection")

# Known Huawei VID:PID pairs in storage mode
HUAWEI_STORAGE_MODE_DEVICES = [
    ('12d1', '1f01'),  # Common storage mode
    ('12d1', '1f02'),  # Alternative storage mode
    ('12d1', '1446'),  # Another storage mode
    ('12d1', '14fe'),  # Storage mode variant
    ('12d1', '1520'),  # Storage mode variant
]

# Timeout for waiting for serial devices to appear
DEVICE_WAIT_TIMEOUT = 30  # seconds
POLL_INTERVAL = 1  # seconds

def run_command(cmd, timeout=10):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
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
                        _LOGGER.info(f"Found Huawei device in storage mode: {vid}:{pid}")
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
        'serial': 'unknown'
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
                _LOGGER.debug(f"Retrieved device info via pyudev for {dev_path}")
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
                    
                    if os.path.exists(vendor_file):
                        with open(vendor_file, 'r') as f:
                            metadata['vendor'] = f.read().strip()
                    
                    if os.path.exists(product_file):
                        with open(product_file, 'r') as f:
                            metadata['product'] = f.read().strip()
                    
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
    
    # Also check /dev/serial/by-id/* if available
    by_id_devices = glob.glob('/dev/serial/by-id/*')
    for dev_path in by_id_devices:
        # Resolve symlink to actual device
        real_path = os.path.realpath(dev_path)
        # Only add if not already in list
        if not any(d['path'] == real_path for d in devices):
            metadata = get_device_info_from_path(real_path)
            metadata['by_id_path'] = dev_path
            devices.append(metadata)
            _LOGGER.info(f"Discovered device by-id: {dev_path} -> {real_path}")
    
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
    """Check if a device is a HUAWEI device based on metadata or by-id path"""
    # Check vendor ID (12d1 is Huawei)
    vendor = device_metadata.get('vendor', '').lower()
    if vendor == '12d1':
        return True
    
    # Check model name
    model = device_metadata.get('model', '').lower()
    if 'huawei' in model:
        return True
    
    # Check by-id path if available
    by_id_path = device_metadata.get('by_id_path', '').lower()
    if 'huawei' in by_id_path:
        return True
    
    return False

def generate_gammurc(device_path):
    """Generate /etc/gammurc with device and fallback connections"""
    gammurc_path = '/etc/gammurc'
    
    # Gammurc content with device and fallback connections
    gammurc_content = f"""[gammu]
port = {device_path}
connection = at115200

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
        _LOGGER.info(f"Successfully generated {gammurc_path} for device {device_path}")
        _LOGGER.debug(f"Gammurc content:\n{gammurc_content}")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to generate {gammurc_path}: {e}")
        return False

def main():
    """Main USB switcher logic"""
    _LOGGER.info("=" * 60)
    _LOGGER.info("USB Mode Switcher for SMS Gateway v1.0.12")
    _LOGGER.info("=" * 60)
    
    # Load device from options if configured
    configured_device = None
    try:
        with open('/data/options.json', 'r') as f:
            options = json.load(f)
            configured_device = options.get('device')
            if configured_device:
                _LOGGER.info(f"Device configured in options: {configured_device}")
    except Exception as e:
        _LOGGER.debug(f"Could not load options.json: {e}")
    
    # Step 1: Detect Huawei devices in storage mode
    _LOGGER.info("Step 1: Detecting Huawei devices in storage mode...")
    storage_devices = detect_huawei_storage_devices()
    
    if storage_devices:
        _LOGGER.info(f"Found {len(storage_devices)} Huawei device(s) in storage mode")
        
        # Step 2: Switch each device
        for vid, pid in storage_devices:
            switch_usb_mode(vid, pid)
        
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
    
    # Step 6: Determine device and set environment
    # Priority: configured device > single auto-detected device > HUAWEI among multiple > none
    device_to_use = None
    
    if configured_device:
        # User has explicitly configured a device, respect that choice
        _LOGGER.info(f"Using configured device: {configured_device}")
        device_to_use = configured_device
    elif len(devices) == 1:
        # Exactly one device found - auto-select it
        device_to_use = devices[0]['path']
        _LOGGER.info(f"Exactly one device found, auto-selecting: {device_to_use}")
    elif len(devices) > 1:
        # Multiple devices found - check for HUAWEI devices
        _LOGGER.info("Multiple serial devices found:")
        for i, dev in enumerate(devices, 1):
            _LOGGER.info(f"  {i}. {dev['path']} (vendor: {dev['vendor']}, product: {dev['product']}, model: {dev.get('model', 'unknown')})")
        
        # Try to find a HUAWEI device
        huawei_devices = [dev for dev in devices if is_huawei_device(dev)]
        
        if huawei_devices:
            # Prefer HUAWEI device
            device_to_use = huawei_devices[0].get('by_id_path') or huawei_devices[0]['path']
            _LOGGER.info(f"HUAWEI device detected among multiple devices, auto-selecting: {device_to_use}")
            _LOGGER.info(f"Device details: vendor={huawei_devices[0]['vendor']}, product={huawei_devices[0]['product']}, model={huawei_devices[0].get('model', 'unknown')}")
        else:
            # No HUAWEI device found, keep existing behavior
            _LOGGER.warning("No HUAWEI device found among multiple devices")
            _LOGGER.warning("Please configure the 'device' option in the add-on configuration to specify which device to use")
            _LOGGER.warning("Device list saved to /data/available_usb.json for reference")
    else:
        # No devices found
        _LOGGER.warning("No serial devices found. The modem may not be connected or may require manual intervention")
        _LOGGER.info("The SMS Gateway will start in modem-not-connected mode and will continue polling")
    
    # Set DEVICE environment variable and generate gammurc if device was selected
    if device_to_use:
        os.environ['DEVICE'] = device_to_use
        _LOGGER.info(f"Set DEVICE environment variable to: {device_to_use}")
        
        # Generate /etc/gammurc for the selected device
        generate_gammurc(device_to_use)
    
    # Step 7: Exec gammu_mqtt.py to replace this process
    _LOGGER.info("=" * 60)
    _LOGGER.info("Starting SMS Gateway (gammu_mqtt.py)...")
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
