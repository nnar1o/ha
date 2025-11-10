#!/usr/bin/env python3
"""
Gammu Connection Probe Module
Tests different gammu connection types and provides detailed diagnostics
"""

import os
import sys
import time
import subprocess
import traceback
from datetime import datetime, timezone

# Import gammu
try:
    import gammu
    GAMMU_AVAILABLE = True
except ImportError:
    GAMMU_AVAILABLE = False

# Import custom logger
try:
    from logger import get_logger
    _LOGGER = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s UTC - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _LOGGER = logging.getLogger(__name__)


class GammuProbeResult:
    """Result of a gammu connection probe"""
    
    def __init__(self, connection, section='gammu'):
        self.connection = connection
        self.section = section
        self.success = False
        self.timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        self.stdout = ''
        self.stderr = ''
        self.exception = None
        self.device_path = None
        self.error_details = None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'connection': self.connection,
            'section': self.section,
            'success': self.success,
            'timestamp': self.timestamp,
            'stdout': self.stdout[:1000] if self.stdout else '',  # Truncate for JSON
            'stderr': self.stderr[:1000] if self.stderr else '',
            'exception': str(self.exception) if self.exception else None,
            'device_path': self.device_path,
            'error_details': self.error_details
        }


def generate_temp_gammurc(device_path, connection, section='gammu', config_path='/tmp/gammurc_try.ini'):
    """
    Generate a temporary gammurc file for testing
    
    Args:
        device_path: Path to the device (e.g., /dev/ttyUSB0)
        connection: Connection type (e.g., 'at115200', 'at9600', 'at')
        section: Section name in gammurc
        config_path: Path where to save the config file
    
    Returns:
        bool: True if successful, False otherwise
    """
    gammurc_content = f"""[{section}]
port = {device_path}
connection = {connection}
"""
    
    try:
        with open(config_path, 'w') as f:
            f.write(gammurc_content)
        _LOGGER.debug(f"Generated temporary gammurc at {config_path}")
        _LOGGER.debug(f"Content:\n{gammurc_content}")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to generate temporary gammurc: {e}")
        return False


def test_gammu_identify(device_path, connection, section='gammu', timeout=5):
    """
    Test gammu --identify command
    
    Args:
        device_path: Device path
        connection: Connection type
        section: Section name
        timeout: Timeout in seconds
    
    Returns:
        tuple: (success, stdout, stderr)
    """
    config_path = '/tmp/gammurc_try.ini'
    
    # Generate temporary config
    if not generate_temp_gammurc(device_path, connection, section, config_path):
        return False, '', 'Failed to generate config'
    
    try:
        # Set environment variable to use our config
        env = os.environ.copy()
        env['GAMMURC'] = config_path
        
        _LOGGER.debug(f"Running: gammu --identify (connection: {connection}, timeout: {timeout}s)")
        
        result = subprocess.run(
            ['gammu', '--identify'],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        
        success = result.returncode == 0
        
        if success:
            _LOGGER.debug(f"✓ gammu --identify succeeded with {connection}")
        else:
            _LOGGER.debug(f"✗ gammu --identify failed with {connection}")
        
        return success, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        _LOGGER.debug(f"✗ gammu --identify timeout with {connection}")
        return False, '', f'Timeout after {timeout}s'
    except Exception as e:
        _LOGGER.debug(f"✗ gammu --identify exception with {connection}: {e}")
        return False, '', str(e)
    finally:
        # Clean up temp file
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except:
            pass


def test_gammu_python_init(device_path, connection, section='gammu', timeout=10):
    """
    Test gammu Python API StateMachine.Init()
    
    Args:
        device_path: Device path
        connection: Connection type
        section: Section name
        timeout: Timeout in seconds
    
    Returns:
        tuple: (success, error_message, exception_traceback)
    """
    if not GAMMU_AVAILABLE:
        return False, 'Gammu Python module not available', None
    
    config_path = '/tmp/gammurc_try.ini'
    
    # Generate temporary config
    if not generate_temp_gammurc(device_path, connection, section, config_path):
        return False, 'Failed to generate config', None
    
    try:
        # Set environment variable (kept for backward compatibility, but not used)
        old_gammurc = os.environ.get('GAMMURC')
        os.environ['GAMMURC'] = config_path
        
        _LOGGER.debug(f"Testing Python gammu.StateMachine.Init() with {connection}")
        
        # Create state machine and try to initialize
        sm = gammu.StateMachine()
        
        # Set configuration programmatically (not from file)
        config = {
            'Device': device_path,
            'Connection': connection,
        }
        _LOGGER.debug(f"Setting gammu config: Device={device_path}, Connection={connection}")
        sm.SetConfig(0, config)
        
        # Init with timeout simulation (gammu doesn't have built-in timeout)
        # We'll rely on the identify test to catch most issues
        sm.Init()
        
        _LOGGER.debug(f"✓ Python gammu.StateMachine.Init() succeeded with {connection}")
        
        # Restore environment
        if old_gammurc:
            os.environ['GAMMURC'] = old_gammurc
        elif 'GAMMURC' in os.environ:
            del os.environ['GAMMURC']
        
        return True, None, None
        
    except Exception as e:
        # Format error message with more details
        error_msg = str(e)
        if hasattr(e, 'args') and len(e.args) > 0:
            if isinstance(e.args[0], dict):
                error_msg = f"{e.args[0]}"
        
        _LOGGER.debug(f"✗ Python gammu.StateMachine.Init() failed with {connection}: {error_msg}")
        
        # Get full traceback
        tb = traceback.format_exc()
        
        # Restore environment
        if old_gammurc:
            os.environ['GAMMURC'] = old_gammurc
        elif 'GAMMURC' in os.environ:
            del os.environ['GAMMURC']
        
        return False, error_msg, tb
    finally:
        # Clean up temp file
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except:
            pass


def probe_connection(device_path, connection, section='gammu'):
    """
    Probe a single connection type
    
    Args:
        device_path: Device path
        connection: Connection type
        section: Section name
    
    Returns:
        GammuProbeResult object
    """
    result = GammuProbeResult(connection, section)
    result.device_path = device_path
    
    _LOGGER.info(f"Probing connection: {connection} on {device_path}")
    
    # Step 1: Test with gammu --identify
    identify_success, stdout, stderr = test_gammu_identify(device_path, connection, section)
    result.stdout = stdout
    result.stderr = stderr
    
    if not identify_success:
        result.success = False
        result.error_details = f"gammu --identify failed: {stderr}"
        _LOGGER.debug(f"Connection {connection} failed at identify stage")
        return result
    
    # Step 2: Test with Python gammu API
    python_success, error_msg, exception_tb = test_gammu_python_init(device_path, connection, section)
    
    if not python_success:
        result.success = False
        result.exception = error_msg
        result.error_details = exception_tb
        _LOGGER.debug(f"Connection {connection} failed at Python Init stage")
        return result
    
    # Both tests passed
    result.success = True
    _LOGGER.info(f"✓ Connection {connection} is working!")
    
    return result


def probe_all_connections(device_path, connections=['at115200', 'at9600', 'at']):
    """
    Probe all connection types and return diagnostics
    
    Args:
        device_path: Device path to test
        connections: List of connection types to test (in order)
    
    Returns:
        dict with keys:
            - successful_connection: str or None (first successful connection)
            - all_results: list of GammuProbeResult objects
            - diagnostics: dict suitable for JSON serialization
    """
    _LOGGER.info("=" * 60)
    _LOGGER.info("Starting Gammu Connection Probe")
    _LOGGER.info(f"Device: {device_path}")
    _LOGGER.info(f"Connections to test: {', '.join(connections)}")
    _LOGGER.info("=" * 60)
    
    all_results = []
    successful_connection = None
    
    # Probe each connection
    for i, connection in enumerate(connections):
        section = 'gammu' if i == 0 else f'gammu{i}'
        
        result = probe_connection(device_path, connection, section)
        all_results.append(result)
        
        # Stop at first success
        if result.success and not successful_connection:
            successful_connection = connection
            _LOGGER.info(f"Found working connection: {connection}")
            # Don't break - continue testing for diagnostic purposes
    
    # Build diagnostics object
    diagnostics = {
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'device': device_path,
        'successful_connection': successful_connection,
        'all_failed': successful_connection is None,
        'tested_connections': [r.to_dict() for r in all_results]
    }
    
    _LOGGER.info("=" * 60)
    if successful_connection:
        _LOGGER.info(f"✓ Probe completed successfully. Working connection: {successful_connection}")
    else:
        _LOGGER.warning("⚠ Probe completed. No working connection found.")
    _LOGGER.info("=" * 60)
    
    return {
        'successful_connection': successful_connection,
        'all_results': all_results,
        'diagnostics': diagnostics
    }


def save_probe_log(all_results, device_path, log_path='/tmp/gammu.log'):
    """
    Save detailed probe log to file (append mode)
    
    Args:
        all_results: List of GammuProbeResult objects
        device_path: Device path that was tested
        log_path: Path to log file
    """
    try:
        with open(log_path, 'a') as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write("Gammu Connection Probe Log\n")
            f.write(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"Device: {device_path}\n")
            f.write("=" * 60 + "\n\n")
            
            for result in all_results:
                f.write(f"Connection: {result.connection} (section: [{result.section}])\n")
                f.write(f"Timestamp: {result.timestamp}\n")
                f.write(f"Success: {result.success}\n")
                f.write("-" * 40 + "\n")
                
                if result.stdout:
                    f.write("stdout:\n")
                    f.write(result.stdout)
                    f.write("\n")
                
                if result.stderr:
                    f.write("stderr:\n")
                    f.write(result.stderr)
                    f.write("\n")
                
                if result.exception:
                    f.write("Exception:\n")
                    f.write(str(result.exception))
                    f.write("\n")
                
                if result.error_details:
                    f.write("Error Details:\n")
                    f.write(result.error_details)
                    f.write("\n")
                
                f.write("=" * 60 + "\n\n")
        
        _LOGGER.info(f"Saved probe log to {log_path}")
    except Exception as e:
        _LOGGER.error(f"Failed to save probe log to {log_path}: {e}")


if __name__ == '__main__':
    # Test mode - probe a device if specified
    if len(sys.argv) > 1:
        device = sys.argv[1]
        connections = sys.argv[2:] if len(sys.argv) > 2 else ['at115200', 'at9600', 'at']
        
        results = probe_all_connections(device, connections)
        save_probe_log(results['all_results'], device)
        
        if results['successful_connection']:
            print(f"\nSuccessful connection: {results['successful_connection']}")
            sys.exit(0)
        else:
            print("\nNo working connection found")
            sys.exit(1)
    else:
        print("Usage: gammu_probe.py <device_path> [connection1] [connection2] ...")
        print("Example: gammu_probe.py /dev/ttyUSB0 at115200 at9600 at")
        sys.exit(1)
