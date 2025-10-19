# dMDFPWM - Drake's Fork of MDFPWM

**dMDFPWM** (Drake's MDFPWM) is a flexible container format, initially built as a fork of [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3), that extends the original specification to support arbitrary multi-channel audio configurations for ComputerCraft/CC:Tweaked audio systems.

## Key Differences from MDFPWM3

| Feature | MDFPWM3 | dMDFPWM |
|---------|---------|---------|
| **Format Magic** | `MDFPWM\003` | `DMDFPWM\x01` |
| **Channel Support** | Fixed stereo only | Arbitrary channels (2.0, 4.0, 5.1, etc.) |
| **Chunk Size** | Fixed 12000 bytes | Configurable per channel |
| **Bitrate** | Fixed 48kbps per channel | Variable bitrates per channel |
| **Metadata** | Simple text fields | JSON-based structured metadata |
| **Configuration** | Hardcoded stereo | JSON channel configuration |

## Format Specification

### File Structure

```
┌─────────────────────────────────────┐
│ Header (16 bytes)                   │
├─────────────────────────────────────┤
│ - Magic: "DMDFPWM" (7 bytes)        │
│ - Version: 0x01 (1 byte)            │
│ - Payload Length (4 bytes, LE)      │
│ - Channel Count (2 bytes, LE)       │
│ - Chunk Size (2 bytes, LE)          │
├─────────────────────────────────────┤
│ Metadata Section (Variable)         │
├─────────────────────────────────────┤
│ - Length (1 byte)                   │
│ - JSON Metadata (UTF-8)             │
├─────────────────────────────────────┤
│ Channel Config Section (Variable)   │
├─────────────────────────────────────┤
│ - Length (1 byte)                   │
│ - JSON Channel Config (UTF-8)       │
├─────────────────────────────────────┤
│ Audio Payload (Interleaved DFPWM)   │
└─────────────────────────────────────┘
```

### JSON Metadata Structure

```json
{
  "artist": "Artist Name",
  "title": "Track Title",
  "album": "Album Name",
  "sample_rate": 48000,
  "duration": 123.45,
  "encoder": "dMDFPWM Python Encoder"
}
```

### JSON Channel Configuration

```json
[
  {
    "index": 0,
    "name": "FL",
    "bitrate": 48,
    "filter": "lowpass=4000"
  },
  {
    "index": 1,
    "name": "FR",
    "bitrate": 48,
    "filter": "lowpass=4000"
  }
]

```
## Usage

### Basic Encoding

```bash
# Standard stereo
python dmdfpwm_encoder.py --input audio.wav --output output.dmdfpwm --config stereo_config.json

# Quad surround with custom metadata
python dmdfpwm_encoder.py \
  --input surround.wav \
  --output surround.dmdfpwm \
  --config quad_config.json \
  --metadata '{"artist": "Artist", "title": "Song", "album": "Album"}' \
  --chunk-size 4500
```

### Advanced Encoding Options

```bash
python dmdfpwm_encoder.py \
  --input input.wav \
  --output output.dmdfpwm \
  --config custom_config.json \
  --chunk-size 6000 \
  --metadata '{"artist": "Artist", "title": "Title", "album": "Album"}'
```

## Technical Details

### DFPWM Encoding
- **Sample Rate**: 48,000 Hz (fixed)
- **Bit Depth**: 1-bit DFPWM (Dynamic Field Pulse Width Modulation)
- **Container**: Multi-channel interleaved format
- **Chunk-based**: Configurable chunk sizes for streaming

### Backward Compatibility
While dMDFPWM extends MDFPWM3, the formats are not directly compatible due to:
- Different magic bytes and header structure
- Variable channel configurations
- JSON-based metadata vs. simple text fields

## License & Credits

dMDFPWM is a fork of [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3) by Drucifer, extended with:
- Flexible multi-channel support
- JSON-based configuration
- Python encoder
