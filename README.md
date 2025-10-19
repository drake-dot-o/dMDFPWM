# dMDFPWM - Drake's Fork of MDFPWM

**dMDFPWM** (Drake's MDFPWM) is a flexible container format, initially built as a fork of [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3), that extends the original specification to support arbitrary multi-channel audio configurations for ComputerCraft/CC:Tweaked audio systems.

## Key Differences from MDFPWM3

| Feature | MDFPWM3 | dMDFPWM |
|---------|---------|---------|
| **Format Magic** | `MDFPWM\003` | `DMDFPWM\x01` |
| **Channel Support** | Fixed stereo only | Arbitrary channels (2.0, 4.0, 5.1, etc.) |
| **Chunk Size** | Fixed 12000 bytes | Configurable per channel |
| **Bitrate** | Fixed 48kbps per channel | Variable bitrates per channel |
| **Metadata** | Simple text fields | Simple text fields (artist/title/album) |
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
│ Track Information (Variable)        │
├─────────────────────────────────────┤
│ - Artist (null-terminated UTF-8)    │
│ - Title (null-terminated UTF-8)     │
│ - Album (null-terminated UTF-8)     │
├─────────────────────────────────────┤
│ Audio Payload (Interleaved DFPWM)   │
└─────────────────────────────────────┘
```

### Track Information Format

The track information consists of three null-terminated UTF-8 strings:
- **Artist**: Performer or group name
- **Title**: Song or track title
- **Album**: Album or release name

### JSON Channel Configuration

```json
[
  {
    "name": "FL",
    "filter": "highpass=50,lowpass=4000"
  },
  {
    "name": "FR",
    "filter": "highpass=50,lowpass=4000"
  }
]
```

Note: The "index" field is optional and automatically assigned based on array position.
## Usage

### Input Options
- **Local file**: `/path/to/audio/file.wav`
- **HTTP URL**: `http://example.com/audio/file.wav`

### Interactive Mode (Recommended)
```bash
python dmdfpwm_encoder.py
```

### Command Line Mode
```bash
python dmdfpwm_encoder.py --input audio.wav --output output.dmdfpwm --config configs/surround_7.1.json
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
- Extended track information format

## License & Credits

dMDFPWM started out as a fork of [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3) by Drucifer, and has been extended with:
- Flexible multi-channel support
- JSON-based configuration
- Python encoder
