-- DMDFPWM Player for ComputerCraft
-- Configurable speaker mapping for surround sound channels

-- ========================================
-- SPEAKER CONFIGURATION
-- ========================================
-- Configure which speakers to use for each channel
-- Comment out channels you don't have speakers for
-- Available channels: FL, FR, FC, LFE, BL, BR, SL, SR

local SPEAKER_CONFIG = {
    -- Front Left
    FL = "speaker_2",      -- Set to your speaker name (e.g., "speaker_0", "left_speaker")

    -- Front Right
    FR = "speaker_3",      -- Set to your speaker name

    -- Front Center (optional)
    FC = "speaker_10",      -- Set to your speaker name if you have center channel

    -- LFE (Subwoofer, optional)
    LFE = "speaker_6",     -- Set to your speaker name if you have LFE

    -- Back Left (Rear Left, optional)
    BL = "speaker_8",      -- Set to your speaker name if you have back left

    -- Back Right (Rear Right, optional)
    BR = "speaker_9",      -- Set to your speaker name if you have back right

    -- Side Left (optional)
    SL = "speaker_4",      -- Set to your speaker name if you have side left

    -- Side Right (optional)
    SR = "speaker_5",      -- Set to your speaker name if you have side right
}

-- Auto-detect speakers if not configured (backup)
local AUTO_DETECT = true  -- Set to false to only use configured speakers

-- ========================================

local function parseDFPWM(filename)
    local file = fs.open(filename, "rb")
    if not file then
        return false, "File not found"
    end

    -- Read DMDFPWM header
    local magic = file.read(7)
    if magic ~= "DMDFPWM" then
        file.close()
        return false, "Not a DMDFPWM file"
    end

    local version = file.read(1)
    if version ~= "\x01" then
        file.close()
        return false, "Unsupported version"
    end

    -- Read header data
    local payloadLen, channelCount, chunkSize = string.unpack("<IHH", file.read(8))

    -- Read metadata
    local metadataLen = string.byte(file.read(1))
    local metadata = file.read(metadataLen)
    local meta = textutils.unserializeJSON(metadata) or {}

    -- Read channel config
    local configLen = string.byte(file.read(1))
    local config = file.read(configLen)
    local channels = textutils.unserializeJSON(config) or {}

    -- Calculate data offset and sample count
    local dataOffset = 16 + 1 + metadataLen + 1 + configLen
    local totalDataLen = payloadLen - metadataLen - configLen - 2
    local bytesPerSecond = chunkSize * channelCount
    local totalSamples = math.floor(totalDataLen / bytesPerSecond)

    -- Return player object
    local player = {
        file = file,
        dataOffset = dataOffset,
        bytesPerSecond = bytesPerSecond,
        totalSamples = totalSamples,
        metadata = meta,
        channels = channels,
        channelCount = channelCount,
        chunkSize = chunkSize
    }

    return true, player
end

local function getSample(player, second)
    if second < 1 or second > player.totalSamples then
        return nil
    end

    -- Calculate offset for this second
    local offset = player.dataOffset + (second - 1) * player.bytesPerSecond

    player.file.seek("set", offset)
    local sampleData = player.file.read(player.bytesPerSecond)

    if not sampleData or #sampleData < player.bytesPerSecond then
        return nil
    end

    -- Split into channels
    local channels = {}
    for i = 1, player.channelCount do
        local start = (i - 1) * player.chunkSize + 1
        local finish = i * player.chunkSize
        channels[i] = sampleData:sub(start, finish)
    end

    return channels
end

local function playDFPWM(player)
    if not player then
        return
    end

    print("Playing: " .. (player.metadata.title or "Unknown"))
    print("Artist: " .. (player.metadata.artist or "Unknown"))
    print("Duration: " .. player.totalSamples .. " seconds")
    print("Channels: " .. player.channelCount)

    -- Find available speakers
    local speakers = {}
    local peripherals = peripheral.getNames()

    for _, name in ipairs(peripherals) do
        if string.find(name, "speaker") then
            local speaker = peripheral.wrap(name)
            if speaker and speaker.playAudio then
                table.insert(speakers, {name = name, peripheral = speaker})
            end
        end
    end

    if #speakers == 0 then
        print("No speakers found!")
        return
    end

    print("Found " .. #speakers .. " speakers:")
    for _, spk in ipairs(speakers) do
        print("  " .. spk.name)
    end

    -- Assign speakers to channels using configuration
    local channelSpeakers = {}
    print("")
    print("Channel assignments:")

    -- Create mapping of available speakers by name for quick lookup
    local availableSpeakers = {}
    for _, spk in ipairs(speakers) do
        availableSpeakers[spk.name] = spk.peripheral
    end

    for i = 1, player.channelCount do
        local channelName = "Channel " .. i
        local channelConfigName = "unknown"

        -- Try to get channel name from file configuration
        if player.channels and player.channels[i] and player.channels[i].name then
            channelConfigName = player.channels[i].name
            channelName = channelName .. " (" .. channelConfigName .. ")"
        else
            channelName = channelName .. " (unknown)"
        end

        -- Try to get speaker from configuration first
        local assignedSpeaker = nil
        if channelConfigName ~= "unknown" and SPEAKER_CONFIG[channelConfigName] then
            if availableSpeakers[SPEAKER_CONFIG[channelConfigName]] then
                assignedSpeaker = availableSpeakers[SPEAKER_CONFIG[channelConfigName]]
                print("  " .. channelName .. " -> " .. SPEAKER_CONFIG[channelConfigName] .. " (configured)")
            elseif SPEAKER_CONFIG[channelConfigName] and AUTO_DETECT then
                print("  " .. channelName .. " -> " .. SPEAKER_CONFIG[channelConfigName] .. " (configured, but not found - using auto-detect)")
                assignedSpeaker = speakers[i] and speakers[i].peripheral
            else
                print("  " .. channelName .. " -> " .. SPEAKER_CONFIG[channelConfigName] .. " (configured, but not found)")
            end
        else
            -- Fall back to auto-detection if enabled
            if AUTO_DETECT and speakers[i] then
                assignedSpeaker = speakers[i].peripheral
                print("  " .. channelName .. " -> " .. speakers[i].name .. " (auto-detected)")
            else
                print("  " .. channelName .. " -> No speaker assigned")
            end
        end

        channelSpeakers[i] = assignedSpeaker
    end

    -- Show configuration status
    print("")
    print("Speaker Configuration Status:")
    for channel, speakerName in pairs(SPEAKER_CONFIG) do
        if speakerName then
            if availableSpeakers[speakerName] then
                print("  " .. channel .. " -> " .. speakerName)
            else
                print("  " .. channel .. " -> " .. speakerName .. " (not found)")
            end
        else
            print("  " .. channel .. " -> Not configured")
        end
    end

    -- Create DFPWM decoders for each channel
    local dfpwm = require("cc.audio.dfpwm")
    local decoders = {}
    for i = 1, player.channelCount do
        decoders[i] = dfpwm.make_decoder()
    end

    print("Playing multi-channel audio...")

    -- Play each second simultaneously across all channels
    for second = 1, player.totalSamples do
        local channels = getSample(player, second)
        if not channels then
            print("Error reading sample " .. second)
            break
        end

        -- Decode all channels first
        local decodedChannels = {}
        for i, channelData in ipairs(channels) do
            if channelData and #channelData > 0 then
                local success, decodedAudio = pcall(decoders[i], channelData)
                if success and decodedAudio then
                    decodedChannels[i] = decodedAudio
                end
            end
        end

        -- Play all channels simultaneously
        for i, decodedAudio in ipairs(decodedChannels) do
            if decodedAudio and channelSpeakers[i] then
                -- Play audio and wait for buffer space if needed
                while not channelSpeakers[i].playAudio(decodedAudio) do
                    os.pullEvent("speaker_audio_empty")
                end
            end
        end

        -- Small delay to allow all speakers to start playing simultaneously
        os.sleep(0.05)
    end

    print("Playback finished!")
end

-- Main program
print("DMDFPWM Player for ComputerCraft")
print("Enter the filename of the DMDFPWM file to play:")

local filename = read()
if not fs.exists(filename) then
    print("File not found: " .. filename)
    return
end

print("Loading file...")
local success, result = parseDFPWM(filename)
if not success then
    print("Error loading file: " .. result)
    return
end

local player = result
    print("File loaded successfully!")

    -- Debug: Save detailed channel config to log file
    local debugLines = {
        "=== DMDFPWM Debug Log ===",
        "Timestamp: " .. os.date(),
        "File: " .. filename,
        "",
        "File Info:",
        "  Channel count: " .. player.channelCount,
        "  Chunk size: " .. player.chunkSize,
        "  Total samples: " .. player.totalSamples,
        "",
        "Channel Configuration:"
    }

    if player.channels then
        table.insert(debugLines, "  player.channels type: " .. type(player.channels))
        table.insert(debugLines, "  player.channels length: " .. #player.channels)

        for i, ch in ipairs(player.channels) do
            table.insert(debugLines, "  Channel " .. i .. ":")
            table.insert(debugLines, "    type: " .. type(ch))
            if ch then
                table.insert(debugLines, "    name: " .. tostring(ch.name))
                table.insert(debugLines, "    index: " .. tostring(ch.index))
                table.insert(debugLines, "    bitrate: " .. tostring(ch.bitrate))
                table.insert(debugLines, "    filter: " .. tostring(ch.filter))
            else
                table.insert(debugLines, "    ch is nil")
            end
        end
    else
        table.insert(debugLines, "  player.channels is nil")
    end

    table.insert(debugLines, "")
    table.insert(debugLines, "Metadata:")
    if player.metadata then
        for key, value in pairs(player.metadata) do
            table.insert(debugLines, "  " .. key .. ": " .. tostring(value))
        end
    end

    table.insert(debugLines, "")
    table.insert(debugLines, "=== End Debug Log ===")

    -- Save to log file
    local logFile = fs.open("dmdfpwm_debug.txt", "w")
    if logFile then
        for _, line in ipairs(debugLines) do
            logFile.writeLine(line)
        end
        logFile.close()
        print("Debug info saved to dmdfpwm_debug.txt")
    else
        print("Failed to save debug log!")
    end

playDFPWM(player)

if player.file then
    player.file.close()
end

print("Done!")
