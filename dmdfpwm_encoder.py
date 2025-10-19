#!/usr/bin/env python3
"""
DMDFPWM Audio Encoder for Python

Converts audio files to DMDFPWM format based on the specification.
Supports multi-channel audio with flexible configurations.
"""

import argparse
import json
import subprocess
import os
import sys
from pathlib import Path
import struct
import wave
import numpy as np
from typing import Dict, List, Tuple, Optional
import glob
import urllib.request
import re


class DMDFPWMEncoder:
    """DMDFPWM encoder implementation following MDFPWM format specification"""

    def __init__(self):
        self.magic = b"DMDFPWM"
        self.version = 0x01
        self.configs_dir = "configs"
        self.sample_rate = 48000
        self.bytes_per_second = 6000  # 1 second = 6000 bytes of DFPWM per channel
        self.chunk_size = 12000  # 1 second for all channels (6000 bytes * 2 channels minimum)

    def find_available_configs(self) -> List[Dict]:
        """Find all available channel configurations in the configs directory"""
        configs = []

        if not os.path.exists(self.configs_dir):
            print(f"Warning: Configs directory '{self.configs_dir}' not found")
            return configs

        # Look for JSON files in the configs directory
        config_files = glob.glob(os.path.join(self.configs_dir, "*.json"))

        for config_file in config_files:
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)

                # Extract filename without extension for display
                config_name = os.path.splitext(os.path.basename(config_file))[0]

                # Count channels
                channel_count = len(config_data) if isinstance(config_data, list) else 0

                # Get channel names for description
                channel_names = [ch.get('name', 'Unknown') for ch in config_data]
                description = f"{config_name} ({channel_count} channels: {', '.join(channel_names)})"

                configs.append({
                    'file': config_file,
                    'name': config_name,
                    'data': config_data,
                    'description': description,
                    'channel_count': channel_count
                })

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Skipping invalid config file '{config_file}': {e}")
                continue

        # Sort by channel count, then by name
        configs.sort(key=lambda x: (x['channel_count'], x['name']))

        return configs

    def select_config_interactive(self, available_configs: List[Dict]) -> Optional[Dict]:
        """Present user with interactive config selection"""
        if not available_configs:
            print("No valid configurations found!")
            return None

        print("\nAvailable channel configurations:")
        print("=" * 50)

        for i, config in enumerate(available_configs, 1):
            print(f"{i:2d}. {config['description']}")

        print("=" * 50)

        while True:
            try:
                choice = input(f"\nSelect configuration (1-{len(available_configs)}): ").strip()

                if not choice:
                    print("Please enter a number.")
                    continue

                config_num = int(choice)

                if 1 <= config_num <= len(available_configs):
                    selected = available_configs[config_num - 1]
                    print(f"Selected: {selected['description']}")
                    return selected
                else:
                    print(f"Please enter a number between 1 and {len(available_configs)}.")

            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nSelection cancelled.")
                return None

    def is_url(self, path: str) -> bool:
        """Check if a string is a valid URL"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return url_pattern.match(path) is not None

    def download_from_url(self, url: str, local_filename: str) -> bool:
        """Download file from URL to local path"""
        try:
            print(f"Downloading from URL: {url}")
            urllib.request.urlretrieve(url, local_filename)
            print(f"Downloaded to: {local_filename}")
            return True
        except Exception as e:
            print(f"Error downloading file: {e}")
            return False

    def get_input_file_interactive(self) -> Optional[str]:
        """Get input file path from user (supports local files and HTTP URLs)"""
        while True:
            try:
                input_path = input("Enter audio file path or HTTP URL: ").strip()

                if not input_path:
                    print("Please enter a file path or URL.")
                    continue

                # Check if it's a URL
                if self.is_url(input_path):
                    # Download from URL
                    temp_filename = "temp_downloaded_audio"
                    if self.download_from_url(input_path, temp_filename):
                        return temp_filename
                    else:
                        print("Failed to download from URL. Please try again.")
                        continue
                else:
                    # Local file path
                    if os.path.exists(input_path):
                        return input_path
                    else:
                        print(f"File not found: {input_path}")
                        print("Please check the path and try again.")
                        continue

            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return None

    def get_output_file_interactive(self) -> Optional[str]:
        """Get output file name from user and ensure converted/ directory exists"""
        # Create converted directory if it doesn't exist
        converted_dir = "converted"
        if not os.path.exists(converted_dir):
            os.makedirs(converted_dir)
            print(f"Created directory: {converted_dir}")

        while True:
            try:
                output_name = input("Enter output filename (without extension): ").strip()

                if not output_name:
                    print("Please enter a filename.")
                    continue

                # Sanitize filename
                output_name = re.sub(r'[^\w\-_.]', '_', output_name)
                output_path = os.path.join(converted_dir, f"{output_name}.dmdfpwm")

                print(f"Output file will be: {output_path}")
                return output_path

            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return None

    def get_chunk_size_interactive(self) -> int:
        """Get chunk size from user"""
        default_size = 6000

        while True:
            try:
                choice = input(f"Enter chunk size (default: {default_size}): ").strip()

                if not choice:
                    return default_size

                size = int(choice)
                if size > 0:
                    return size
                else:
                    print("Chunk size must be positive.")

            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print(f"\nUsing default chunk size: {default_size}")
                return default_size

    def get_track_info_interactive(self) -> Tuple[str, str, str]:
        """Get artist, title, and album information from user"""
        print("Enter track information (optional):")

        try:
            artist = input("Artist (or press Enter for none): ").strip()
            title = input("Title (or press Enter for none): ").strip()
            album = input("Album (or press Enter for none): ").strip()

            return artist or "", title or "", album or ""

        except KeyboardInterrupt:
            print("\nUsing no track information.")
            return "", "", ""

    def parse_channel_config(self, config: List[Dict]) -> List[Dict]:
        """Parse and validate channel configuration"""
        if not isinstance(config, list):
            raise ValueError("Channel config must be a list")

        for i, channel in enumerate(config):
            required_fields = ['name']
            for field in required_fields:
                if field not in channel:
                    raise ValueError(f"Channel missing required field: {field}")

            # Add index based on position if not present
            if 'index' not in channel:
                channel['index'] = i

        return config

    def build_header(self, channel_count: int, chunk_size: int, payload_length: int) -> bytes:
        """Build DMDFPWM file header"""
        header = bytearray()
        header.extend(self.magic)  # Magic: "DMDFPWM"
        header.append(self.version)  # Version: 0x01
        header.extend(struct.pack('<I', payload_length))  # Total payload length
        header.extend(struct.pack('<H', channel_count))  # Channel count
        header.extend(struct.pack('<H', chunk_size))  # Chunk size per channel
        return bytes(header)

    def encode_audio(self, input_file: str, channel_spec: Dict) -> bytes:
        """Encode audio for a specific channel using FFmpeg's built-in DFPWM encoder"""
        try:
            channel_idx = channel_spec['index']

            # Extract channel and apply any filters from the configuration
            channel_filter = channel_spec.get('filter', '')

            # Map channel index to appropriate FFmpeg channel based on target channel name
            target_channel = channel_spec['name']

            if target_channel == "FL":
                pan_filter = "1c|c0=FL"  # Front left
            elif target_channel == "FR":
                pan_filter = "1c|c0=FR"  # Front right
            elif target_channel == "FC":
                pan_filter = "1c|c0=FC"  # Front center (if available in source)
            elif target_channel == "LFE":
                pan_filter = "1c|c0=LFE"  # LFE (if available in source)
            elif target_channel == "BL":
                pan_filter = "1c|c0=BL"  # Back left (if available in source)
            elif target_channel == "BR":
                pan_filter = "1c|c0=BR"  # Back right (if available in source)
            elif target_channel == "BC":
                pan_filter = "1c|c0=BC"  # Back center (if available in source)
            else:
                # Fallback: try to use the target channel name directly
                # If that fails, simulate from stereo channels
                try:
                    pan_filter = f"1c|c0={target_channel}"
                    print(f"  Trying direct channel mapping: {target_channel}")
                except:
                    print(f"  Warning: Channel {target_channel} not found in source, using silence")
                    return b'\x55' * 1636771

            # Build FFmpeg command with channel extraction and optional filtering
            filters = [f'pan={pan_filter}']

            # Add channel-specific filter if specified in config
            if channel_filter:
                filters.append(channel_filter)

            filter_chain = ','.join(filters)

            cmd = [
                'ffmpeg', '-y',  # -y to overwrite output files
                '-i', input_file,  # Input file
                '-filter:a', filter_chain,  # Apply channel extraction and filters
                '-acodec', 'dfpwm',  # Use FFmpeg's built-in DFPWM encoder
                '-ar', '48000',  # Sample rate (matches C# implementation)
                '-ab', '48k',  # Audio bitrate: 48 kbps (1 bit per sample at 48kHz)
                '-ac', '1',  # Mono output
            ]

            # Output to DFPWM data directly
            temp_dfpwm = f"temp_channel_{channel_idx}.dfpwm"
            cmd.append(temp_dfpwm)

            # Execute FFmpeg command
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")

            # Read the DFPWM file
            with open(temp_dfpwm, 'rb') as f:
                dfpwm_data = f.read()

            # Clean up temporary file
            os.remove(temp_dfpwm)

            return dfpwm_data

        except Exception as e:
            print(f"Error encoding channel {channel_spec.get('name', 'unknown')}: {e}")
            return b''

    def _read_wav_pcm(self, wav_file: str) -> bytes:
        """Read PCM data from WAV file"""
        with wave.open(wav_file, 'rb') as wav:
            # Skip WAV header (44 bytes) and read raw PCM data
            wav.readframes(44)  # Skip WAV header
            return wav.readframes(wav.getnframes())

    def _pcm_to_dfpwm(self, pcm_data: bytes) -> bytes:
        """Convert 16-bit PCM to DFPWM"""
        if not pcm_data:
            return b''

        # Convert bytes to 16-bit samples
        samples = []
        for i in range(0, len(pcm_data), 2):
            if i + 1 < len(pcm_data):
                # Little-endian 16-bit sample
                sample = int.from_bytes(pcm_data[i:i+2], byteorder='little', signed=True)
                samples.append(sample)

        # DFPWM encoding parameters
        strength = 127  # Filter strength
        dfpwm_bytes = bytearray()

        # Initial state
        current_sample = 0
        running_average = 0

        for sample in samples:
            # Scale sample to DFPWM range (-32767 to 32767)
            scaled_sample = int((sample * 32767) / 32768)

            # Calculate target (sample - running average)
            target = scaled_sample - running_average

            # Determine charge to add based on target
            if target > current_sample:
                charge = strength
                current_sample += strength
                dfpwm_bytes.append(1)  # High pulse
            else:
                charge = -strength
                current_sample -= strength
                dfpwm_bytes.append(0)  # Low pulse

            # Update running average
            running_average += charge // 16

            # Clamp running average
            running_average = max(-32767, min(32767, running_average))

        return bytes(dfpwm_bytes)

    def interleave_audio(self, channel_data: List[bytes], chunk_size: int) -> bytes:
        """Interleave channel audio data"""
        if not channel_data:
            return b''

        # Calculate number of chunks needed
        max_length = max(len(data) for data in channel_data)
        num_chunks = (max_length + chunk_size - 1) // chunk_size

        interleaved = bytearray()

        for chunk_idx in range(num_chunks):
            for channel_idx, data in enumerate(channel_data):
                start = chunk_idx * chunk_size
                end = min(start + chunk_size, len(data))
                chunk = data[start:end]

                # Pad with 0x55 if chunk is incomplete
                if len(chunk) < chunk_size:
                    chunk = chunk + b'\x55' * (chunk_size - len(chunk))

                interleaved.extend(chunk)

        return bytes(interleaved)

    def interleave_audio_chunks(self, channel_data: List[bytes], chunk_size: int) -> bytes:
        """Interleave audio data using standard chunking"""
        if not channel_data:
            return b''

        # Calculate number of chunks needed
        max_length = max(len(data) for data in channel_data)
        num_chunks = (max_length + chunk_size - 1) // chunk_size

        interleaved = bytearray()

        for chunk_idx in range(num_chunks):
            for channel_idx, data in enumerate(channel_data):
                start = chunk_idx * chunk_size
                end = min(start + chunk_size, len(data))
                chunk = data[start:end]

                # Pad with 0x55 if chunk is incomplete
                if len(chunk) < chunk_size:
                    chunk = chunk + b'\x55' * (chunk_size - len(chunk))

                interleaved.extend(chunk)

        return bytes(interleaved)

    def write_dmdfpwm(self, output_file: str, header: bytes,
                     artist: str, title: str, album: str, audio_data: bytes):
        """Write complete DMDFPWM file following MDFPWM format specification"""
        with open(output_file, 'wb') as f:
            f.write(header)

            # Write artist, title, album as null-terminated strings
            artist_bytes = artist.encode('utf-8') + b'\x00'
            title_bytes = title.encode('utf-8') + b'\x00'
            album_bytes = album.encode('utf-8') + b'\x00'

            f.write(artist_bytes)
            f.write(title_bytes)
            f.write(album_bytes)

            # Write audio payload
            f.write(audio_data)


def main():
    # Check if any arguments were provided
    if len(sys.argv) == 1:
        # Interactive mode - no arguments provided
        return run_interactive()
    else:
        # Command line mode - arguments provided
        return run_command_line()


def run_interactive():
    """Run in interactive mode with user prompts"""
    print("DMDFPWM Audio Encoder - Interactive Mode")
    print("=" * 50)

    # Initialize encoder
    encoder = DMDFPWMEncoder()

    # Get input file (supports local files and HTTP URLs)
    print("\nStep 1: Input File")
    print("-" * 20)
    input_file = encoder.get_input_file_interactive()
    if not input_file:
        print("No input file selected. Exiting.")
        return

    # Get output file (creates converted/ directory)
    print("\nStep 2: Output File")
    print("-" * 20)
    output_file = encoder.get_output_file_interactive()
    if not output_file:
        print("No output file specified. Exiting.")
        # Clean up downloaded file if it exists
        if input_file == "temp_downloaded_audio" and os.path.exists(input_file):
            os.remove(input_file)
        return

    # Select channel configuration
    print("\nStep 3: Channel Configuration")
    print("-" * 30)
    available_configs = encoder.find_available_configs()
    if not available_configs:
        print("No valid configurations found in configs/ directory!")
        cleanup_temp_files(input_file)
        return

    selected_config = encoder.select_config_interactive(available_configs)
    if not selected_config:
        print("No configuration selected. Exiting.")
        cleanup_temp_files(input_file)
        return

    channel_config = selected_config['data']
    print(f"Using config: {selected_config['file']}")

    # Get track information
    print("\nStep 4: Track Information")
    print("-" * 25)
    artist, title, album = encoder.get_track_info_interactive()

    # Get chunk size
    print("\nStep 5: Encoding Settings")
    print("-" * 25)
    chunk_size = encoder.get_chunk_size_interactive()

    # Parse and validate channel configuration
    channels = encoder.parse_channel_config(channel_config)

    print("\nStep 6: Encoding")
    print("-" * 15)
    print(f"Encoding {len(channels)} channels with chunk size {chunk_size}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")

    # Encode each channel
    channel_data = []
    for channel in channels:
        print(f"Encoding channel {channel['index']}: {channel['name']}")
        encoded_data = encoder.encode_audio(input_file, channel)
        channel_data.append(encoded_data)
        print(f"  Encoded {len(encoded_data)} bytes")

    # Interleave audio data using standard chunking
    interleaved_data = encoder.interleave_audio_chunks(channel_data, chunk_size)
    print(f"Interleaved {len(interleaved_data)} bytes of audio data")

    # Calculate payload length (artist + title + album + audio)
    artist_bytes = artist.encode('utf-8') + b'\x00'
    title_bytes = title.encode('utf-8') + b'\x00'
    album_bytes = album.encode('utf-8') + b'\x00'
    payload_length = len(artist_bytes) + len(title_bytes) + len(album_bytes) + len(interleaved_data)

    # Build header with correct payload length
    header = encoder.build_header(len(channels), chunk_size, payload_length)

    # Write final DMDFPWM file
    encoder.write_dmdfpwm(output_file, header, artist, title, album, interleaved_data)

    print("\nStep 6: Complete!")
    print("-" * 16)
    print(f"Created DMDFPWM file: {output_file}")
    print(f"Total file size: {os.path.getsize(output_file)} bytes")

    # Clean up temporary downloaded file
    cleanup_temp_files(input_file)


def run_command_line():
    """Run in command line mode with arguments"""
    parser = argparse.ArgumentParser(description='Convert audio to DMDFPWM format')
    parser.add_argument('--input', '-i', required=True, help='Input audio file')
    parser.add_argument('--output', '-o', required=True, help='Output DMDFPWM file')
    parser.add_argument('--config', '-c', help='Channel configuration JSON file (if not specified, will show available configs)')
    parser.add_argument('--chunk-size', type=int, default=6000, help='Chunk size per channel (default: 6000)')
    parser.add_argument('--metadata', '-m', help='Metadata JSON string')

    args = parser.parse_args()

    # Parse metadata
    metadata = {}
    if args.metadata:
        metadata = json.loads(args.metadata)

    # Initialize encoder
    encoder = DMDFPWMEncoder()

    # Determine channel configuration
    channel_config = None

    if args.config:
        # Use specified config file
        if not os.path.exists(args.config):
            print(f"Error: Config file '{args.config}' not found")
            cleanup_temp_files()
            sys.exit(1)

        print(f"Using specified config: {args.config}")
        with open(args.config, 'r') as f:
            channel_config = json.load(f)
    else:
        # Auto-detect configs and let user choose
        print("No config specified, scanning for available configurations...")
        available_configs = encoder.find_available_configs()

        if not available_configs:
            print("No valid configurations found in configs/ directory!")
            cleanup_temp_files()
            sys.exit(1)

        selected_config = encoder.select_config_interactive(available_configs)

        if not selected_config:
            print("No configuration selected. Exiting.")
            cleanup_temp_files()
            sys.exit(1)

        channel_config = selected_config['data']
        print(f"Using config: {selected_config['file']}")

    # Parse and validate channel configuration
    channels = encoder.parse_channel_config(channel_config)

    print(f"Encoding {len(channels)} channels with chunk size {args.chunk_size}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        cleanup_temp_files()
        sys.exit(1)

    # Encode each channel
    channel_data = []
    for channel in channels:
        print(f"Encoding channel {channel['index']}: {channel['name']}")
        encoded_data = encoder.encode_audio(args.input, channel)
        channel_data.append(encoded_data)
        print(f"  Encoded {len(encoded_data)} bytes")

    # Interleave audio data
    interleaved_data = encoder.interleave_audio(channel_data, args.chunk_size)
    print(f"Interleaved {len(interleaved_data)} bytes of audio data")

    # Calculate payload length (artist + title + album + audio)
    # For command line mode, use empty strings for track info
    artist_bytes = b'' + b'\x00'
    title_bytes = b'' + b'\x00'
    album_bytes = b'' + b'\x00'
    payload_length = len(artist_bytes) + len(title_bytes) + len(album_bytes) + len(interleaved_data)

    # Build header with correct payload length
    header = encoder.build_header(len(channels), args.chunk_size, payload_length)

    # Write final DMDFPWM file
    encoder.write_dmdfpwm(args.output, header, '', '', '', interleaved_data)

    print(f"Created DMDFPWM file: {args.output}")
    print(f"Total file size: {os.path.getsize(args.output)} bytes")


def cleanup_temp_files(input_file: str = None):
    """Clean up temporary files"""
    files_to_cleanup = []

    # Clean up downloaded audio file
    if input_file == "temp_downloaded_audio" and os.path.exists(input_file):
        files_to_cleanup.append(input_file)

    # Clean up any temporary channel files that might be left behind
    temp_channel_files = glob.glob("temp_channel_*.dfpwm")
    files_to_cleanup.extend(temp_channel_files)

    # Remove all identified temp files
    for temp_file in files_to_cleanup:
        try:
            os.remove(temp_file)
            print(f"Cleaned up temporary file: {temp_file}")
        except Exception as e:
            print(f"Warning: Could not remove temp file {temp_file}: {e}")


if __name__ == "__main__":
    main()
