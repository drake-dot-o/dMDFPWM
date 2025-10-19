# dMDFPWM - Drake's Fork of MDFPWM

**dMDFPWM** (Drake's MDFPWM) is a flexible container format, initially built as a fork of [Drucifer](https://github.com/drucifer-sc)'s [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3), that extends the original specification to support arbitrary multi-channel audio configurations for ComputerCraft/CC:Tweaked audio systems.



# What *exactly* is this and how do I use it?
- **dMDFPWM** is a container format for audio tracks in ComputerCraft.
- It layers multiple [.dfpwm](https://tweaked.cc/library/cc.audio.dfpwm.html)'s on top of each other [one per speaker channel] at its core to achieve this.
  - This means that it supports **surround** sound speaker configurations (hello, 7.1!). The only limit on channels/speakers is ffmpeg's (or ComputerCraft's) limits.

### If you want to skip all the boring technical stuff below, then all you need is: 

- [dmdfpwm_encoder.py](https://github.com/drake-dot-o/dMDFPWM/blob/main/dmdfpwm_encoder.py) to convert the files to dMDFPWM
  - The encoder **requires** [ffmpeg](https://www.ffmpeg.org).

- [player.lua](https://github.com/drake-dot-o/dMDFPWM/blob/main/cc/player.lua) to play `.dmdfpwm` files ingame.
  - `player.lua` contains optional configuration for setting specific speakers for each channel.

- A speaker for every channel that you intend to use. 
  - Common layouts such as 5.1, 7.1, and other surround sound layout mappings can be found outlined in [mappings.md](https://github.com/drake-dot-o/dMDFPWM/blob/main/mappings.md). However, you can configure them however you wish. 
  - See the [/configs/](https://github.com/drake-dot-o/dMDFPWM/tree/main/configs) folder for (barebones) examples of most common surround layouts.


## Format Specification

### Key Differences from MDFPWM3

| Feature | MDFPWM3 | dMDFPWM |
|---------|---------|---------|
| **Format Magic** | `MDFPWM\003` | `DMDFPWM\x01` |
| **Channel Support** | Stereo (L/R) | Arbitrary channels (2.0, 4.0, 5.1, etc+) |
| **Chunk Size** | Fixed 12000 bytes | Configurable per-channel (defaults 12000 bytes) |
| **Bitrate** | Fixed 48kbps per channel | Variable bitrates/channel (defaults 48kbps) |
| **Metadata** | Artist + Title + Album | Artist + Title + Album |
| **Configuration** | [Fixed] Stereo (L/R) | Set with the config of the encoding |

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
├─────────────────────────────────────┤
│ - Channel 1 DFPWM Data              │
│   - Channel 2 DFPWM Data...         │
│   - Channel N DFPWM Data...         │
│      - ...etc, for each channel     │
|                                     |
│   Default: 12000 bytes per chunk    │
│     ^^ configurable, not set        │
└─────────────────────────────────────┘
```

**Default Chunk Size**: 12000 bytes (1 second at 48kHz per channel)
**Example Configurations**:
- **Stereo (2.0)**: 2 channels × 6000 bytes = 12000 bytes per chunk
- **Surround 5.1**: 6 channels × 2000 bytes = 12000 bytes per chunk
- **Surround 7.1**: 8 channels × 1500 bytes = 12000 bytes per chunk

### Track Information Format

The track information consists of three null-terminated `UTF-8` strings:
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

Note: The "index" field is optional. Speakers are either assigned based on the player's configuration or automatically assigned based on array position in the wired network.

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
Although `dMDFPWM` is based on `MDFPWM3`, it is not (currently) backwards-compatible.
- Different magic bytes and header structure
- Variable channel configurations
- Extended track information format

## License

`dMDFPWM` is licensed under the [GNU Lesser General Public License v2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html).

## Credits

`dMDFPWM` started out as a fork of [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3) by [Drucifer](https://github.com/drucifer-sc) (...and notably also [Ale32bit](https://github.com/Ale32bit)'s projects based on the `MDFPWM3` spec, [Quartz](https://github.com/Ale32bit/Quartz) and [QuartzEncoder](https://github.com/Ale32bit/QuartzEncoder/), were a great help in understanding the audio), and has been extended with:
- Flexible multi-channel support
- JSON-based configuration for different surround layouts
- Python encoder (requires ffmpeg)