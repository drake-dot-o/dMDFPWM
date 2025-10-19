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


class DMDFPWMEncoder:
    """DMDFPWM encoder implementation"""

    def __init__(self):
        self.magic = b"DMDFPWM"
        self.version = 0x01

    def parse_channel_config(self, config: List[Dict]) -> List[Dict]:
        """Parse and validate channel configuration"""
        if not isinstance(config, list):
            raise ValueError("Channel config must be a list")

        for channel in config:
            required_fields = ['index', 'name']
            for field in required_fields:
                if field not in channel:
                    raise ValueError(f"Channel missing required field: {field}")

        return sorted(config, key=lambda x: x['index'])

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

    def write_dmdfpwm(self, output_file: str, header: bytes, metadata: Dict,
                     channel_config: List[Dict], audio_data: bytes):
        """Write complete DMDFPWM file"""
        with open(output_file, 'wb') as f:
            f.write(header)

            # Write metadata section
            metadata_json = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
            metadata_length = len(metadata_json)
            f.write(struct.pack('B', metadata_length))
            f.write(metadata_json)

            # Write channel configuration (truncate if too long for uint8)
            config_json = json.dumps(channel_config, separators=(',', ':')).encode('utf-8')
            config_length = len(config_json)

            print(f"  Debug: Channel config length: {config_length} bytes")
            print(f"  Debug: Channel config content: {config_json[:100]}...")  # First 100 bytes

            if config_length > 255:
                print(f"  Warning: Channel config too long ({config_length} bytes), truncating to fit JSON boundary")

                # Find the last complete JSON object/array that fits within 255 bytes
                truncated_json = config_json[:255]

                # Try to find a safe truncation point (end of a complete JSON object)
                # Look for the last closing brace/bracket within the limit
                for i in range(254, 200, -1):  # Search from byte 254 down to 200
                    if truncated_json[i] == 125 or truncated_json[i] == 93:  # '}' or ']'
                        # Check if this creates valid JSON by attempting to parse
                        try:
                            test_config = json.loads(truncated_json[:i+1].decode('utf-8'))
                            if isinstance(test_config, list) and len(test_config) > 0:
                                config_json = truncated_json[:i+1]
                                config_length = i + 1
                                print(f"  Truncated to {config_length} bytes (valid JSON)")
                                break
                        except json.JSONDecodeError:
                            continue
                else:
                    # If no safe truncation point found, use minimal valid JSON
                    config_json = b'[]'
                    config_length = 2
                    print(f"  Using minimal valid JSON (2 bytes)")

                print(f"  Final config length: {config_length} bytes")

            f.write(struct.pack('B', config_length))
            f.write(config_json)

            # Write audio payload
            f.write(audio_data)


def main():
    parser = argparse.ArgumentParser(description='Convert audio to DMDFPWM format')
    parser.add_argument('--input', '-i', required=True, help='Input audio file')
    parser.add_argument('--output', '-o', required=True, help='Output DMDFPWM file')
    parser.add_argument('--config', '-c', required=True, help='Channel configuration JSON file')
    parser.add_argument('--chunk-size', type=int, default=6000, help='Chunk size per channel (default: 6000)')
    parser.add_argument('--metadata', '-m', help='Metadata JSON string')

    args = parser.parse_args()

    # Parse metadata
    metadata = {}
    if args.metadata:
        metadata = json.loads(args.metadata)

    # Load channel configuration
    with open(args.config, 'r') as f:
        channel_config = json.load(f)

    # Initialize encoder
    encoder = DMDFPWMEncoder()

    # Parse and validate channel configuration
    channels = encoder.parse_channel_config(channel_config)

    print(f"Encoding {len(channels)} channels with chunk size {args.chunk_size}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
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

    # Calculate payload length (metadata + config + audio)
    metadata_json = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
    config_json = json.dumps(channels, separators=(',', ':')).encode('utf-8')
    payload_length = len(metadata_json) + len(config_json) + len(interleaved_data) + 2  # +2 for length bytes

    # Build header with correct payload length
    header = encoder.build_header(len(channels), args.chunk_size, payload_length)

    # Write final DMDFPWM file
    encoder.write_dmdfpwm(args.output, header, metadata, channels, interleaved_data)

    print(f"Created DMDFPWM file: {args.output}")
    print(f"Total file size: {os.path.getsize(args.output)} bytes")


if __name__ == "__main__":
    main()
