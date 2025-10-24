#!/usr/bin/env python3
"""
A python encoder for dMDFPWM, a multi-channel audio container for ComputerCraft
Spec can be found at https://github.com/drake-dot-o/dMDFPWM

Converts audio files to DMDFPWM format based on the specification.
Supports multi-channel audio with flexible configurations.
"""

import argparse
import json
import subprocess
import os
import sys
import struct
import glob
import urllib.request
import re
from urllib.parse import urlparse, unquote


class DMDFPWMEncoder:
    """DMDFPWM encoder implementation following MDFPWM format specification"""

    def __init__(self):
        self.magic = b"DMDFPWM"
        self.version = 0x01
        self.configs_dir = "configs"
        self.sample_rate = 48000
        self.bytes_per_second = 6000  # 1 second = 6000 bytes of DFPWM per channel
        self.chunk_size = 6000   # Default chunk size (1 second per channel)

    def find_available_configs(self):
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

    def select_config_interactive(self, available_configs):
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

    def is_url(self, path):
        """Check if a string is a valid URL"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return url_pattern.match(path) is not None

    def extract_filename_from_url(self, url):
        """Extract filename from URL, handling Discord CDN and other URLs"""
        try:
            # Remove query parameters to get the clean path
            parsed = urlparse(url)
            path = unquote(parsed.path)
            
            # Get the filename from the path
            filename = os.path.basename(path)
            
            # If we got a filename with an extension, use it
            if filename and '.' in filename:
                # Remove extension for our temp file
                name_without_ext = os.path.splitext(filename)[0]
                extension = os.path.splitext(filename)[1]
                return f"temp_downloaded_{name_without_ext}{extension}"
            else:
                return "temp_downloaded_audio"
                
        except Exception:
            return "temp_downloaded_audio"

    def download_from_url(self, url):
        """Download file from URL to local path"""
        try:
            print(f"Downloading from URL: {url}")
            
            # Extract a sensible filename from the URL
            local_filename = self.extract_filename_from_url(url)
            
            # Add User-Agent header to avoid blocks
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            with urllib.request.urlopen(req) as response, open(local_filename, 'wb') as out_file:
                out_file.write(response.read())
            
            print(f"Downloaded to: {local_filename}")
            return local_filename
        except Exception as e:
            print(f"Error downloading file: {e}")
            return None

    def get_input_file_interactive(self):
        """Get input file path from user (supports local files and HTTP URLs)"""
        while True:
            try:
                input_path = input("Enter audio file path or HTTP URL (direct links to audio attachments): ").strip()

                if not input_path:
                    print("Please enter a file path or URL.")
                    continue

                # Check if it's a URL
                if self.is_url(input_path):
                    # Download from URL
                    downloaded_file = self.download_from_url(input_path)
                    if downloaded_file:
                        return downloaded_file
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

    def get_output_file_interactive(self):
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

    def get_chunk_size_interactive(self):
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

    def get_track_info_interactive(self):
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

    def parse_channel_config(self, config):
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

    def build_header(self, channel_count, chunk_size, payload_length):
        """Build DMDFPWM file header"""
        header = bytearray()
        header.extend(self.magic)  # Magic: "DMDFPWM"
        header.append(self.version)  # Version: 0x01
        header.extend(struct.pack('<I', payload_length))  # Total payload length
        header.extend(struct.pack('<H', channel_count))  # Channel count
        header.extend(struct.pack('<H', chunk_size))  # Chunk size per channel
        return bytes(header)

    def encode_audio(self, input_file, channel_spec):
        """Encode audio for a specific channel using FFmpeg's built-in DFPWM encoder"""
        try:
            channel_idx = channel_spec['index']
            target_channel = channel_spec['name']
            channel_filter = channel_spec.get('filter', '')

            # First, create a proper surround upmix, then extract the channel
            # The surround filter does phase analysis for better channel separation
            
            if target_channel == "FL":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=FL"
            elif target_channel == "FR":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=FR"
            elif target_channel == "FC":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=FC"
            elif target_channel == "LFE":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=LFE"
                # Backs: 10% of front + surround content
            elif target_channel == "BL":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=0.1*FL+BL"
            elif target_channel == "BR":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=0.1*FR+BR"
                # Sides: 30% of front + surround content
            elif target_channel == "SL":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=0.3*FL+SL"
            elif target_channel == "SR":
                pan_filter = "surround=chl_out=7.1,pan=mono|c0=0.3*FR+SR"
            else:
                print(f"  Warning: Unknown channel {target_channel}, using silence")
                return b'\x55' * 1636771

            # Build filter chain
            filters = [pan_filter]
            if channel_filter:
                filters.append(channel_filter)
            
            filter_chain = ','.join(filters)

            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-filter:a', filter_chain,
                '-acodec', 'dfpwm',
                '-ar', '48000',
                '-ab', '48k',
                '-ac', '1',
            ]

            temp_dfpwm = f"temp_channel_{channel_idx}.dfpwm"
            cmd.append(temp_dfpwm)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")

            with open(temp_dfpwm, 'rb') as f:
                dfpwm_data = f.read()

            os.remove(temp_dfpwm)

            return dfpwm_data

        except Exception as e:
            print(f"Error encoding channel {channel_spec.get('name', 'unknown')}: {e}")
            return b''

    def interleave_audio_chunks(self, channel_data, chunk_size):
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

    def write_dmdfpwm(self, output_file, header, artist, title, album, channels, audio_data):
        """Write complete DMDFPWM file following MDFPWM format specification"""
        with open(output_file, 'wb') as f:
            f.write(header)

            # Write metadata as JSON object
            metadata = {
                "artist": artist,
                "title": title,
                "album": album
            }
            metadata_json = json.dumps(metadata).encode('utf-8')
            metadata_len = len(metadata_json)

            # Write metadata length (1 byte) and metadata
            f.write(bytes([metadata_len]))
            f.write(metadata_json)

            # Write channel configuration as JSON
            channel_config_json = json.dumps(channels).encode('utf-8')
            channel_config_len = len(channel_config_json)

            # Write channel config length (2 bytes, little-endian) and config data
            f.write(struct.pack('<H', channel_config_len))
            f.write(channel_config_json)

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
        if input_file and input_file.startswith("temp_downloaded_") and os.path.exists(input_file):
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

    # Calculate payload length (metadata_len_byte + metadata_json + channel_config_len_bytes + channel_config + audio)
    metadata = {
        "artist": artist,
        "title": title,
        "album": album
    }
    metadata_json = json.dumps(metadata).encode('utf-8')
    metadata_len = len(metadata_json)
    channel_config_json = json.dumps(channels).encode('utf-8')
    channel_config_len = len(channel_config_json)
    payload_length = 1 + metadata_len + 2 + channel_config_len + len(interleaved_data)

    # Build header with correct payload length
    header = encoder.build_header(len(channels), chunk_size, payload_length)

    # Write final DMDFPWM file
    encoder.write_dmdfpwm(output_file, header, artist, title, album, channels, interleaved_data)

    print("\nStep 6: Complete!")
    print("-" * 16)
    print(f"Created DMDFPWM file: {output_file}")
    print(f"Total file size: {os.path.getsize(output_file)} bytes")

    # Clean up temporary downloaded file
    cleanup_temp_files(input_file)


def run_command_line():
    """Run in command line mode with arguments"""
    parser = argparse.ArgumentParser(description='Convert audio to DMDFPWM format')
    parser.add_argument('--input', '-i', required=True, help='Input audio file or URL')
    parser.add_argument('--output', '-o', required=True, help='Output DMDFPWM file')
    parser.add_argument('--config', '-c', help='Channel configuration JSON file (if not specified, will show available configs)')
    parser.add_argument('--chunk-size', type=int, default=6000, help='Chunk size per channel (default: 6000)')
    parser.add_argument('--metadata', '-m', help='Metadata JSON string')

    args = parser.parse_args()

    # Parse metadata
    parsed_metadata = {}
    if args.metadata:
        parsed_metadata = json.loads(args.metadata)

    # Extract artist, title, album from parsed metadata or default to empty
    artist = parsed_metadata.get("artist", "")
    title = parsed_metadata.get("title", "")
    album = parsed_metadata.get("album", "")

    # Initialize encoder
    encoder = DMDFPWMEncoder()

    # Handle input file (local or URL)
    input_file = args.input
    downloaded_file = None
    
    if encoder.is_url(input_file):
        print(f"Detected URL input, downloading...")
        downloaded_file = encoder.download_from_url(input_file)
        if not downloaded_file:
            print(f"Error: Failed to download from URL: {input_file}")
            cleanup_temp_files()
            sys.exit(1)
        input_file = downloaded_file

    # Determine channel configuration
    channel_config = None

    if args.config:
        # Use specified config file
        if not os.path.exists(args.config):
            print(f"Error: Config file '{args.config}' not found")
            cleanup_temp_files(downloaded_file)
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
            cleanup_temp_files(downloaded_file)
            sys.exit(1)

        selected_config = encoder.select_config_interactive(available_configs)

        if not selected_config:
            print("No configuration selected. Exiting.")
            cleanup_temp_files(downloaded_file)
            sys.exit(1)

        channel_config = selected_config['data']
        print(f"Using config: {selected_config['file']}")

    # Parse and validate channel configuration
    channels = encoder.parse_channel_config(channel_config)

    print(f"Encoding {len(channels)} channels with chunk size {args.chunk_size}")
    print(f"Input: {input_file}")
    print(f"Output: {args.output}")

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        cleanup_temp_files(downloaded_file)
        sys.exit(1)

    # Encode each channel
    channel_data = []
    for channel in channels:
        print(f"Encoding channel {channel['index']}: {channel['name']}")
        encoded_data = encoder.encode_audio(input_file, channel)
        channel_data.append(encoded_data)
        print(f"  Encoded {len(encoded_data)} bytes")

    # Interleave audio data
    interleaved_data = encoder.interleave_audio_chunks(channel_data, args.chunk_size)
    print(f"Interleaved {len(interleaved_data)} bytes of audio data")

    # Calculate payload length (metadata_len_byte + metadata_json + channel_config_len_bytes + channel_config + audio)
    metadata = {
        "artist": artist,
        "title": title,
        "album": album
    }
    metadata_json = json.dumps(metadata).encode('utf-8')
    metadata_len = len(metadata_json)
    channel_config_json = json.dumps(channels).encode('utf-8')
    channel_config_len = len(channel_config_json)
    payload_length = 1 + metadata_len + 2 + channel_config_len + len(interleaved_data)

    # Build header with correct payload length
    header = encoder.build_header(len(channels), args.chunk_size, payload_length)

    # Write final DMDFPWM file
    encoder.write_dmdfpwm(args.output, header, artist, title, album, channels, interleaved_data)

    print(f"Created DMDFPWM file: {args.output}")
    print(f"Total file size: {os.path.getsize(args.output)} bytes")
    
    # Clean up downloaded file if it was used
    cleanup_temp_files(downloaded_file)


def cleanup_temp_files(input_file = None):
    """Clean up temporary files"""
    files_to_cleanup = []

    # Clean up downloaded audio file (matches any temp_downloaded_* file)
    if input_file and input_file.startswith("temp_downloaded_") and os.path.exists(input_file):
        files_to_cleanup.append(input_file)

    # Clean up any temporary channel files that might be left behind
    temp_channel_files = glob.glob("temp_channel_*.dfpwm")
    files_to_cleanup.extend(temp_channel_files)
    
    # Clean up any other temp_downloaded files that might be lingering
    temp_downloaded_files = glob.glob("temp_downloaded_*")
    files_to_cleanup.extend(temp_downloaded_files)

    # Remove all identified temp files
    for temp_file in files_to_cleanup:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"Cleaned up temporary file: {temp_file}")
        except Exception as e:
            print(f"Warning: Could not remove temp file {temp_file}: {e}")


if __name__ == "__main__":
    main()
