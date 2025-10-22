

-- dplayer.lua: a dMDFPWM player for ComputerCraft
-- Format spec and encoder available at https://github.com/drake-dot-o/dMDFPWM

-- Supports local files and direct HTTP/HTTPS URLs, and streams audio without storing to disk

-- ========================================
-- SPEAKER CONFIGURATION
-- ========================================
local SPEAKER_CONFIG = {
    FL = {"speaker_667"},   -- Front Left (single speaker)
    FR = {"speaker_668"},   -- Front Right (single speaker)
    SL = {"speaker_663"},   -- Side Left (single speaker)
    SR = {"speaker_664"},   -- Side Right (single speaker)
    LFE = {"speaker_669", "speaker_670"},  -- Subwoofer (can be multiple speakers)
    BL = {"speaker_662"},   -- Back Left (single speaker)
    BR = {"speaker_661"},-- Back Right (single speaker)
}

local AUTO_DETECT = false  -- Auto-detect speakers if not configured

-- ========================================
-- UTILITY FUNCTIONS
-- ========================================

local function isURL(input)
    return input:match("^https?://") ~= nil
end

local function downloadChunk(url, startByte, endByte)
    local headers = {}
    if startByte and endByte then
        headers["Range"] = "bytes=" .. startByte .. "-" .. endByte
    end
    
    local response = http.get(url, headers)
    if not response then
        return nil, "Failed to download chunk"
    end
    
    local data = response.readAll()
    response.close()
    return data
end

-- ========================================
-- PARSER FOR STREAMING
-- ========================================

local function parseHeaderFromURL(url)
    -- Download just the header (first 512 bytes should be enough)
    local headerData = downloadChunk(url, 0, 511)
    if not headerData then
        return false, "Failed to download header"
    end
    
    -- Parse header
    local magic = headerData:sub(1, 7)
    if magic ~= "DMDFPWM" then
        return false, "Not a DMDFPWM file"
    end
    
    local version = headerData:sub(8, 8)
    if version ~= "\x01" then
        return false, "Unsupported version"
    end
    
    -- Read header data
    local payloadLen, channelCount, chunkSize = string.unpack("<IHH", headerData:sub(9, 16))
    
    -- Read metadata length and metadata
    local metadataLen = string.byte(headerData:sub(17, 17))
    local metadata = headerData:sub(18, 17 + metadataLen)
    local meta = textutils.unserializeJSON(metadata) or {}

    -- Read channel config length and config (2 bytes, little-endian)
    local configLen = string.unpack("<H", headerData:sub(18 + metadataLen, 19 + metadataLen))
    local config = headerData:sub(20 + metadataLen, 19 + metadataLen + configLen)
    local channels = textutils.unserializeJSON(config) or {}

    -- Debug: Write to log file instead of printing
    local logFile = fs.open("debug.log", "w")
    logFile.writeLine("=== DMDFPWM Header Parsing Debug ===")
    logFile.writeLine("Header offset calculation:")
    logFile.writeLine("  Base offset (16 + 1): 17")
    logFile.writeLine("  Metadata length: " .. metadataLen)
    logFile.writeLine("  Config length byte at position: " .. (18 + metadataLen))
    logFile.writeLine("  Config data from position: " .. (19 + metadataLen) .. " to " .. (18 + metadataLen + configLen))
    logFile.writeLine("Raw config data (first 500 chars):")
    logFile.writeLine(config:sub(1, 500))
    logFile.writeLine("Raw config data (remaining chars):")
    if #config > 500 then
        logFile.writeLine(config:sub(501))
    end
    logFile.writeLine("Config length: " .. configLen)
    logFile.writeLine("Attempting JSON parse...")
    logFile.writeLine("Parsed channels type: " .. type(channels))
    logFile.writeLine("Parsed channels length: " .. (channels and #channels or "nil"))
    if channels then
        logFile.writeLine("First channel: " .. textutils.serialize(channels[1] or "none"))
    end
    logFile.close()

    print("Debug info written to debug.log")
    
    -- Calculate offsets (header + metadata_len_byte + metadata + config_len_bytes + config)
    local dataOffset = 16 + 1 + metadataLen + 2 + configLen
    local totalDataLen = payloadLen - metadataLen - configLen - 2
    local bytesPerSecond = chunkSize * channelCount
    local totalSamples = math.floor(totalDataLen / bytesPerSecond)
    
    return true, {
        url = url,
        dataOffset = dataOffset,
        bytesPerSecond = bytesPerSecond,
        totalSamples = totalSamples,
        metadata = meta,
        channels = channels,
        channelCount = channelCount,
        chunkSize = chunkSize,
        isStreaming = true
    }
end

local function parseHeaderFromFile(filename)
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
    
    -- Read channel config length (2 bytes, little-endian)
    local configLen = string.unpack("<H", file.read(2))
    local config = file.read(configLen)
    local channels = textutils.unserializeJSON(config) or {}

    -- Debug: Write to log file for file parsing
    local logFile = fs.open("debug.log", "w")
    logFile.writeLine("=== DMDFPWM FILE Header Parsing Debug ===")
    logFile.writeLine("Header offset calculation:")
    logFile.writeLine("  Base offset (16 + 1): 17")
    logFile.writeLine("  Metadata length: " .. metadataLen)
    logFile.writeLine("  Config length byte at position: " .. (18 + metadataLen))
    logFile.writeLine("  Config data from position: " .. (19 + metadataLen) .. " to " .. (18 + metadataLen + configLen))
    logFile.writeLine("Raw config data (first 500 chars):")
    logFile.writeLine(config:sub(1, 500))
    logFile.writeLine("Raw config data (remaining chars):")
    if #config > 500 then
        logFile.writeLine(config:sub(501))
    end
    logFile.writeLine("Config length: " .. configLen)
    logFile.writeLine("Attempting JSON parse...")
    logFile.writeLine("Parsed channels type: " .. type(channels))
    logFile.writeLine("Parsed channels length: " .. (channels and #channels or "nil"))
    if channels then
        logFile.writeLine("First channel: " .. textutils.serialize(channels[1] or "none"))
    end
    logFile.close()

    print("Debug info written to debug.log")
    
    -- Calculate offsets (header + metadata_len_byte + metadata + config_len_bytes + config)
    local dataOffset = 16 + 1 + metadataLen + 2 + configLen
    local totalDataLen = payloadLen - metadataLen - configLen - 2
    local bytesPerSecond = chunkSize * channelCount
    local totalSamples = math.floor(totalDataLen / bytesPerSecond)
    
    return true, {
        file = file,
        dataOffset = dataOffset,
        bytesPerSecond = bytesPerSecond,
        totalSamples = totalSamples,
        metadata = meta,
        channels = channels,
        channelCount = channelCount,
        chunkSize = chunkSize,
        isStreaming = false
    }
end

-- ========================================
-- SAMPLE RETRIEVAL
-- ========================================

local function getSampleFromURL(player, second)
    if second < 1 or second > player.totalSamples then
        return nil
    end
    
    -- Calculate byte range for this second
    local offset = player.dataOffset + (second - 1) * player.bytesPerSecond
    local endOffset = offset + player.bytesPerSecond - 1
    
    local sampleData = downloadChunk(player.url, offset, endOffset)
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

local function getSampleFromFile(player, second)
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

local function getSample(player, second)
    if player.isStreaming then
        return getSampleFromURL(player, second)
    else
        return getSampleFromFile(player, second)
    end
end

-- ========================================
-- SPEAKER SETUP
-- ========================================

local function setupSpeakers(player)
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
        return nil, "No speakers found!"
    end
    
    print("Found " .. #speakers .. " speakers:")
    for _, spk in ipairs(speakers) do
        print("  " .. spk.name)
    end
    
    -- Create mapping of available speakers by name
    local availableSpeakers = {}
    for _, spk in ipairs(speakers) do
        availableSpeakers[spk.name] = spk.peripheral
    end
    
    -- Assign speakers to channels
    local channelSpeakers = {}
    print("")
    print("Channel assignments:")

    for i = 1, player.channelCount do
        local channelName = "Channel " .. i
        local channelConfigName = "unknown"

        -- Get channel name from file configuration
        if player.channels and player.channels[i] and player.channels[i].name then
            channelConfigName = player.channels[i].name
            channelName = channelName .. " (" .. channelConfigName .. ")"
        else
            channelName = channelName .. " (unknown)"
        end

        -- Get configured speakers for this channel (may be multiple)
        local configuredSpeakers = SPEAKER_CONFIG[channelConfigName] or {}
        local assignedSpeakers = {}
        local validConfiguredSpeakers = {}

        -- Filter out empty speaker names from configuration
        for _, speakerName in ipairs(configuredSpeakers) do
            if speakerName and speakerName ~= "" then
                table.insert(validConfiguredSpeakers, speakerName)
            end
        end

        -- Try to assign configured speakers first
        if #validConfiguredSpeakers > 0 then
            for _, speakerName in ipairs(validConfiguredSpeakers) do
                if availableSpeakers[speakerName] then
                    table.insert(assignedSpeakers, availableSpeakers[speakerName])
                end
            end

            if #assignedSpeakers > 0 then
                print("  " .. channelName .. " -> " .. table.concat(validConfiguredSpeakers, ", ") .. " (configured)")
            else
                print("  " .. channelName .. " -> Configured speakers not available: " .. table.concat(validConfiguredSpeakers, ", "))
                -- Fall back to auto-detection if enabled
                if AUTO_DETECT and speakers[i] then
                    table.insert(assignedSpeakers, speakers[i].peripheral)
                    print("  " .. channelName .. " -> " .. speakers[i].name .. " (auto-detected fallback)")
                else
                    print("  " .. channelName .. " -> No speaker assigned")
                end
            end
        else
            -- No configured speakers, fall back to auto-detection
            if AUTO_DETECT and speakers[i] then
                table.insert(assignedSpeakers, speakers[i].peripheral)
                print("  " .. channelName .. " -> " .. speakers[i].name .. " (auto-detected)")
            else
                print("  " .. channelName .. " -> No speaker assigned (auto-detect disabled)")
            end
        end

        channelSpeakers[i] = assignedSpeakers
    end
    
    return channelSpeakers
end

-- ========================================
-- PLAYBACK ENGINE - STREAMING OPTIMIZED
-- ========================================

-- Note: Could likely be further optimized, however it is working fine in its current state

local function playDFPWM(player)
    if not player then
        return
    end
    
    print("")
    print("=== Track Info ===")
    print("Playing: " .. (player.metadata.title or "Unknown"))
    print("Artist: " .. (player.metadata.artist or "Unknown"))
    print("Duration: " .. player.totalSamples .. " seconds")
    print("Channels: " .. player.channelCount)
    print("Source: " .. (player.isStreaming and "Streaming (URL)" or "Local File"))
    print("")
    
    -- Setup speakers
    local channelSpeakers, err = setupSpeakers(player)
    if not channelSpeakers then
        print(err)
        return
    end
    
    -- Create DFPWM decoders for each channel
    local dfpwm = require("cc.audio.dfpwm")
    local decoders = {}
    for i = 1, player.channelCount do
        decoders[i] = dfpwm.make_decoder()
    end

    -- Display channel header information
    print("")
    print("=== Channel Information ===")
    if player.channels and #player.channels > 0 then
        print("Channels in file:")
        for i = 1, math.min(player.channelCount, #player.channels) do
            local channelInfo = player.channels[i]
            if channelInfo and channelInfo.name then
                print("  Channel " .. i .. " -> " .. channelInfo.name)
                if channelInfo.filter then
                    print("    Filter: " .. channelInfo.filter)
                end
            else
                print("  Channel " .. i .. " -> Unknown")
            end
        end

        -- Show channel mapping summary
        print("")
        print("Channel mapping:")
        local channelNames = {}
        for i = 1, math.min(player.channelCount, #player.channels) do
            local channelInfo = player.channels[i]
            if channelInfo and channelInfo.name then
                table.insert(channelNames, channelInfo.name)
            else
                table.insert(channelNames, "CH" .. i)
            end
        end
        print("  " .. table.concat(channelNames, " | "))
    else
        print("No channel information found in file header")
        print("Channels: " .. player.channelCount .. " (unnamed)")
    end

    print("")
    print("Playing multi-channel audio...")
    print("Press Ctrl+T to stop")
    print("")
    
    -- Main streaming loop: download → decode → play → wait → repeat
    for second = 1, player.totalSamples do
        -- Step 1: Download this second's data
        local channels = getSample(player, second)
        if not channels then
            print("Error: Failed to download second " .. second)
            break
        end
        
        -- Step 2: Decode all channels
        local decodedChannels = {}
        for i, channelData in ipairs(channels) do
            if channelData and #channelData > 0 and channelSpeakers[i] and #channelSpeakers[i] > 0 then
                local success, decodedAudio = pcall(decoders[i], channelData)
                if success and decodedAudio then
                    decodedChannels[i] = decodedAudio
                else
                    print("Warning: Failed to decode channel " .. i .. " at second " .. second)
                end
            end
        end
        
        -- Step 3: Play all decoded channels simultaneously to multiple speakers
        local playSuccess = {}
        for i, decodedAudio in ipairs(decodedChannels) do
            playSuccess[i] = {}
            for j = 1, #channelSpeakers[i] do
                playSuccess[i][j] = false
            end
        end

        -- Keep trying to play all channels on all their speakers until they're all accepted
        while true do
            local allQueued = true

            for i, decodedAudio in ipairs(decodedChannels) do
                for j, speaker in ipairs(channelSpeakers[i]) do
                    if not playSuccess[i][j] then
                        if speaker.playAudio(decodedAudio) then
                            playSuccess[i][j] = true
                        else
                            allQueued = false
                        end
                    end
                end
            end

            if allQueued then
                break
            end

            -- Step 4: Wait for speaker buffer space
            os.pullEvent("speaker_audio_empty")
        end
        
        -- Update progress every 10 seconds
        if second % 10 == 0 or second == player.totalSamples then
            local progress = math.floor((second / player.totalSamples) * 100)
            term.clearLine()
            term.setCursorPos(1, select(2, term.getCursorPos()))
            write("Progress: " .. second .. "/" .. player.totalSamples .. " (" .. progress .. "%)")
        end
    end
    
    print("")
    print("Playback finished!")
end

-- ========================================
-- MAIN PROGRAM
-- ========================================

print("DMDFPWM Streaming Player for ComputerCraft")
print("==========================================")
print("")
print("Enter filename or URL:")
print("  Local file: myaudio.dmdfpwm")
print("  Remote URL: https://example.com/audio.dmdfpwm")
print("")

local input = read()
if not input or input == "" then
    print("No input provided!")
    return
end

-- Determine if input is URL or file
local player, err
if isURL(input) then
    print("Streaming from URL...")
    local success
    success, player = parseHeaderFromURL(input)
    if not success then
        print("Error loading URL: " .. player)
        return
    end
else
    if not fs.exists(input) then
        print("File not found: " .. input)
        return
    end
    print("Loading local file...")
    local success
    success, player = parseHeaderFromFile(input)
    if not success then
        print("Error loading file: " .. player)
        return
    end
end

print("File loaded successfully!")
print("")

-- Play the audio
playDFPWM(player)

-- Cleanup
if player.file then
    player.file.close()
end

print("")
print("Done!")
