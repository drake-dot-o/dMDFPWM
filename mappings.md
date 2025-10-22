# FFmpeg Channel Layout Mappings
## Notice: center channels (FC, BC) still need to be mixed and currently don't work.


## Standard Channel Abbreviations

| Abbreviation | Description |
|-------------|-------------|
| `FL` | Front Left |
| `FR` | Front Right |
| `FC` | Front Center |
| `LFE` | Low Frequency Effects (subwoofer) |
| `BL` | Back Left |
| `BR` | Back Right |
| `BC` | Back Center |
| `SL` | Side Left |
| `SR` | Side Right |

## Common Layouts

| Layout | Channel Configuration | Total Channels |
|--------|---------------------|----------------|
| **Mono** | `FC` | 1 |
| **Stereo (2.0)** | `FL + FR` | 2 |
| **Stereo + LFE (2.1)** | <pre>FL + FR<br>  LFE</pre> | 3 |
| **Stereo + Center (3.0)** | `FL + FC + FR` | 3 |
| **Surround (3.1)** | <pre>FL + FC + FR<br>    LFE</pre> | 4 |
| **Quad (4.0)** | <pre>FL + FR<br>BL + BR</pre> | 4 |
| **Quad + LFE (4.1)** | <pre>FL + FR<br>BL + BR<br>  LFE</pre> | 5 |
| **Quad + Side + LFE** | <pre>FL + FR<br>BL + BR<br>    LFE<br>    SL + SR</pre> | 5 |
| **5.0 Surround** | <pre>FL + FC + FR<br>   SL + SR</pre> | 5 |
| **5.1 Surround** | <pre>FL + FC + FR<br>  BL + BR<br>    LFE</pre> | 6 |
| **6.0 Surround** | <pre>FL + FC + FR<br>BL + BC + BR</pre> | 6 |
| **6.1 Surround** | <pre>FL + FC + FR<br>BL + BC + BR<br>    LFE</pre> | 7 |
| **7.1 Surround** | <pre>FL + FC + FR<br>  SL + SR<br>  BL + BR<br>    LFE</pre> | 8 |

## FFmpeg Channel Constants

```c
#define AV_CH_FRONT_LEFT             (1 << 0)   // FL
#define AV_CH_FRONT_RIGHT            (1 << 1)   // FR
#define AV_CH_FRONT_CENTER           (1 << 2)   // FC
#define AV_CH_LOW_FREQUENCY          (1 << 3)   // LFE
#define AV_CH_BACK_LEFT              (1 << 4)   // BL
#define AV_CH_BACK_RIGHT             (1 << 5)   // BR
#define AV_CH_BACK_CENTER            (1 << 8)   // BC
#define AV_CH_SIDE_LEFT              (1 << 9)   // SL
#define AV_CH_SIDE_RIGHT             (1 << 10)  // SR
```

## Usage Examples

```bash
# Extract front left only
pan=1c|c0=FL

# Extract with lowpass filter for rear channels
pan=1c|c0=BL,lowpass=2000

# Mix multiple channels to mono
pan=1c|c0=0.5*FL+0.5*FR+0.3*FC
```

## Notes

- Channels are 0-indexed in FFmpeg syntax
- `c0` = first output channel, `c1` = second output channel, etc
- Use `pan=1c` for mono output from any input layout
- Combine with audio filters: `pan=1c|c0=FL,highpass=30,lowpass=8000`
