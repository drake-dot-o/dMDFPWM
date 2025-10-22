# dMDFPWM - Drake's version of MDFPWM

**dMDFPWM** is a flexible container format, initially based on [Drucifer](https://github.com/drucifer-sc)'s [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3), that extends the specification to support arbitrary multi-channel audio configurations for ComputerCraft/CC:Tweaked audio systems. Initially it only supported L/R stereo.


## **!!! NOTICE !!!**: **Part of the code in this repository has been generated/modified by AI 🤖 tools.**

 While I have tried to review and validate the AI-generated content to the best of my own ability, this is a project that I undertook with a ***VERY*** limited understanding of audio from a software perspective. I am simply leaving this notice at the top for transparency. 
 So, please don't flame me if it's kind of ugly. Any guidance or pointing out what is being done wrong is infinitely more helpful.
 :)


# So... what *exactly* is this and how do I use it?
- **dMDFPWM** is a container format for audio tracks in ComputerCraft. **dMDFPWM files are a container file of multiple `.dfpwm` files and metadata** 
- **Header data** contains a bit of information to make the file easily readable by the player, as well as track/artist/album infos
- They hold a layer of audio (`.dfpwm`) for **each** channel of audio which gets interleaved and can be played using multiple speakers ingame.
- The result is basically **full surround with this as if it were an actual surround speaker setup in real life!**

- It layers multiple [.dfpwm](https://tweaked.cc/library/cc.audio.dfpwm.html)'s on top of each other [one per speaker channel] at its core to achieve this, in an adjacent fashion to `MDFPWM`.

### If you want to skip all the boring technical stuff below, then all you need is: 

- [dmdfpwm_encoder.py](https://github.com/drake-dot-o/dMDFPWM/blob/main/dmdfpwm_encoder.py) to convert the files to dMDFPWM
  - The encoder **requires** [ffmpeg](https://www.ffmpeg.org).

- [dplayer.lua](https://github.com/drake-dot-o/dMDFPWM/blob/main/cc/dplayer.lua) to play `.dmdfpwm` files ingame. 
  - It is **IMPERATIVE** that you use all of the speakers  on a wired network attached to **ONLY ONE (1)** side of the computer. The player gives issues if you attach it to the same wired network on more than one side of a computer.
  - `dplayer.lua` contains optional configuration for setting specific speakers for each channel. 
  - It will automatically detect speakers and assign them a channel if configuration is not set manually
    - ...but just like a quality surround system in real life, it would be advisable to assign your channels to speakers manually, that are placed in a surround layout instead of randomly. 

- A speaker for every channel that you intend to use, connected to **ONE (1)** network, **on ONE (1)** side of the computer.

  - Common layouts such as 5.1, 7.1, and other surround sound layout mappings can be found outlined in [mappings.md](https://github.com/drake-dot-o/dMDFPWM/blob/main/mappings.md). 
    - ...however, you can configure them however you wish; feel free to experiment and play around with it and see what works best for you
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
│   Default: 6000 bytes per chunk     │
|    per channel/second@48kHz         |
|                                     |
│     ^^ configurable, not set        │
└─────────────────────────────────────┘
```

**Default Chunk Size**: 6000 bytes (1 second at 48kHz per channel)

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

## License

`dMDFPWM` is licensed under the [GNU Lesser General Public License v2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html).

This software is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

**You may:**
- Use this software for any purpose, including commercial applications
- Modify and distribute the source code
- Link this library with proprietary software
- Distribute modified versions under the same LGPL license
- Use the library in your own projects without restriction
- Credit Drucifer and/or myself in your projects that use this code for making it possible :)

**You must:**
- Include the original license text with your distribution
- Include copyright notices and warranty disclaimers
- Make source code available when distributing binaries
- Clearly mark any modifications you make

## Credits

`dMDFPWM` started out based on the [MDFPWM3](https://github.com/drucifer-sc/MDFPWM3) spec by [Drucifer](https://github.com/drucifer-sc), and has been extended with:
- Flexible multi-channel support
- JSON-based configuration for different surround layouts
- Python encoder (requires ffmpeg)

And finally, notably, shout out to [Ale32bit](https://github.com/Ale32bit)'s projects based on the `MDFPWM3` spec, [Quartz](https://github.com/Ale32bit/Quartz) and [QuartzEncoder](https://github.com/Ale32bit/QuartzEncoder/); they were a great help in understanding how the container itself works.
