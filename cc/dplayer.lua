-- dplayer.lua: a dMDFPWM player for ComputerCraft 
-- Format spec and encoder available at https://github.com/drake-dot-o/dMDFPWM

-- Supports local files and direct HTTP/HTTPS URLs, and streams audio without storing to disk

-- ========================================
-- SPEAKER CONFIGURATION
-- ========================================
local SPEAKER_CONFIG = {
    FL = {"speaker_665"},   -- Front Left (single speaker)
    FR = {"speaker_666"},   -- Front Right (single speaker)
    SL = {"speaker_684"},   -- Side Left (single speaker)
    SR = {"speaker_685"},   -- Side Right (single speaker)
    LFE = {"speaker_667", "speaker_668"},  -- Subwoofer (can be multiple speakers)
    BL = {"speaker_662"},   -- Back Left (single speaker)
    BR = {"speaker_661"},-- Back Right (single speaker)
}

local AUTO_DETECT = false-- Auto-detect speakers if not configured
-- ^ I recommend setting this to false once speakers are configured

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

local function clearAllSpeakers()
    local peripherals = peripheral.getNames()
    for _, name in ipairs(peripherals) do
        if string.find(name, "speaker") then
            local speaker = peripheral.wrap(name)
            if speaker and speaker.stop then
                speaker.stop()  -- Clears the speaker's buffer, weird shit happens sometimes without this, no idea why, one or two channels will play the last song played
            end
        end
    end
end

-- ========================================
-- PARSER FOR STREAMING
-- ========================================

local function parseHeaderFromURL(url)
    -- Download just the header (first 2048 bytes should be enough for metadata + config)
    local headerData = downloadChunk(url, 0, 2047)
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
    
    -- Read metadata length and JSON metadata
    local metadataLen = string.byte(headerData:sub(17, 17))
    local metadataJson = headerData:sub(18, 17 + metadataLen)
    local meta = textutils.unserializeJSON(metadataJson) or {artist = "", title = "", album = ""}

    -- Read channel config length and config (2 bytes, little-endian)
    -- Config length starts right after metadata ends
    local configLenStart = 18 + metadataLen
    local configLen = string.unpack("<H", headerData:sub(configLenStart, configLenStart + 1))
    local configStart = configLenStart + 2
    local config = headerData:sub(configStart, configStart + configLen - 1)
    local channels = textutils.unserializeJSON(config) or {}
    
    -- Debug output
    print("Metadata length: " .. metadataLen)
    print("Config length: " .. configLen)
    print("Config data length: " .. #config)
    if #config > 0 then
        print("Config preview: " .. config:sub(1, math.min(100, #config)))
    end
    
    -- Calculate offsets (header + metadata_len_byte + metadata + config_len_bytes + config)
    local dataOffset = 16 + 1 + metadataLen + 2 + configLen
    local totalDataLen = payloadLen - 1 - metadataLen - 2 - configLen
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
    
    -- Read metadata length and JSON metadata
    local metadataLen = string.byte(file.read(1))
    local metadataJson = file.read(metadataLen)
    local meta = textutils.unserializeJSON(metadataJson) or {artist = "", title = "", album = ""}
    
    -- Read channel config length (2 bytes, little-endian)
    local configLen = string.unpack("<H", file.read(2))
    local config = file.read(configLen)
    local channels = textutils.unserializeJSON(config) or {}
    
    -- Debug output
    print("Metadata length: " .. metadataLen)
    print("Config length: " .. configLen)
    print("Config data length: " .. #config)
    if #config > 0 then
        print("Config preview: " .. config:sub(1, math.min(100, #config)))
    end
    
    -- Calculate offsets (header + metadata_len_byte + metadata + config_len_bytes + config)
    local dataOffset = 16 + 1 + metadataLen + 2 + configLen
    local totalDataLen = payloadLen - 1 - metadataLen - 2 - configLen
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
-- PLAYBACK ENGINE
-- ========================================

local function playDFPWM(player)
    if not player then
        return
    end
    
    print("")
    print("=== Track Info ===")
    print("Playing: " .. (player.metadata.title or "Unknown"))
    print("Artist: " .. (player.metadata.artist or "Unknown"))
    print("Album: " .. (player.metadata.album or "Unknown"))
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
    
    -- Clear all speakers before starting playback
    print("Clearing speakers...")
    clearAllSpeakers()
    
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
    
    -- Prefill speaker buffers to ensure synchronized start
    print("Buffering...")
    local bufferSeconds = 1  -- Prefill 1 second
    local prefillBuffers = {}
    
    for i = 1, player.channelCount do
        prefillBuffers[i] = {}
    end
    
    -- Decode the first few seconds
    for second = 1, math.min(bufferSeconds, player.totalSamples) do
        local channels = getSample(player, second)
        if channels then
            for i, channelData in ipairs(channels) do
                if channelData and #channelData > 0 and channelSpeakers[i] and #channelSpeakers[i] > 0 then
                    local success, decodedAudio = pcall(decoders[i], channelData)
                    if success and decodedAudio then
                        table.insert(prefillBuffers[i], decodedAudio)
                    end
                end
            end
        end
    end
    
    -- Queue prefill buffers to all speakers
    for i, buffer in ipairs(prefillBuffers) do
        for _, decodedAudio in ipairs(buffer) do
            for _, speaker in ipairs(channelSpeakers[i]) do
                speaker.playAudio(decodedAudio)
            end
        end
    end

    -- Main playback loop: Queue to each speaker independently with speaker-specific events
    -- Note: Prefill already the first second to ensure synchronized start
    local currentSecond = bufferSeconds + 1
    local lastProgressUpdate = 0
    local playbackSecond = 1  -- Track actual playback position for progress display

    print("Starting playback...")

    while currentSecond <= player.totalSamples do
        -- Step 1: Download this second's data
        local channels = getSample(player, currentSecond)
        if not channels then
            print("Error: Failed to get second " .. currentSecond)
            break
        end
        
        -- Step 2: Decode all channels
        local decodedChannels = {}
        for i, channelData in ipairs(channels) do
            if channelData and #channelData > 0 and channelSpeakers[i] and #channelSpeakers[i] > 0 then
                local success, decodedAudio = pcall(decoders[i], channelData)
                if success and decodedAudio then
                    decodedChannels[i] = decodedAudio
                end
            end
        end
        
        -- Step 3: Queue to each speaker, waiting for THAT SPECIFIC speaker if needed
        for i, decodedAudio in ipairs(decodedChannels) do
            for _, speaker in ipairs(channelSpeakers[i]) do
                -- Get the speaker's name for event matching
                local speakerName = peripheral.getName(speaker)
                
                -- Try to queue, and if buffer is full, wait for THIS speaker specifically
                while not speaker.playAudio(decodedAudio) do
                    repeat
                        local event, name = os.pullEvent("speaker_audio_empty")
                    until name == speakerName
                end
            end
        end
        
        currentSecond = currentSecond + 1
        playbackSecond = playbackSecond + 1
        
        -- Update progress periodically
        if os.clock() - lastProgressUpdate > 0.5 then
            local progress = math.floor((playbackSecond / player.totalSamples) * 100)
            term.clearLine()
            term.setCursorPos(1, select(2, term.getCursorPos()))
            write("Progress: " .. playbackSecond .. "/" .. player.totalSamples .. " (" .. progress .. "%)")
            lastProgressUpdate = os.clock()
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
clearAllSpeakers()  -- Clear speakers after playback ends
if player.file then
    player.file.close()
end

print("")
print("Done!")