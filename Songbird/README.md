SONGBIRD PLUGIN FOR COVAS NEXT
================================

Voice-controlled sound effects for COVAS NEXT. Play sounds from Freesound, manage local audio files, playlists, and bind sounds to custom voice commands.

## What It Does

- Play sound effects from Freesound by voice
- Play custom audio files (MP3, OGG, WAV)
- **Playlists** - Auto-advance, loop by default
- **Seeking** - Jump to any time position
- **Current info** - Check duration and position
- Control playback (pause, resume, stop, volume, seek)
- **Bind sounds to phrases** - Multiple sounds → random playback
- Cache sounds locally for instant replay

## Installation

1. Go to [Freesound.org](https://freesound.org/), register, get API key (Settings → API Keys)
2. Place `Songbird` folder in: `%appdata%\com.covas-next.ui\plugins\`
3. Add API key in COVAS NEXT Settings → SONGBIRD → Freesound API Key
4. Restart COVAS NEXT
5. Test: "Test SONGBIRD plugin"

## Voice Commands

### Playing Sounds
```
"Play explosion sound"
"Play [filename]"
"Play it again"
```

### Playback Control
```
"Pause" / "Resume" / "Stop" / "Restart"
"Volume up" / "Volume down" / "Set volume to 50%"
"Mute" / "Unmute"
```

### Seeking
```
"Skip to 2:30"
"Move to 4 minutes"
"Seek to 150 seconds"
```
Formats: MM:SS, H:MM:SS, seconds, natural language ("2 minutes 30")
Works best with MP3/OGG, limited WAV support.

### Current Info
```
"How long is this sound?"
"What position are we at?"
"Current sound info"
```

### Playlists
Create folders in `sounds/` directory with audio files.

```
"Play [folder] playlist"
"Next" / "Previous"
"Loop off" / "Shuffle on"
"Playlist info"
"What's in [folder] playlist?"  (preview without playing)
"List playlists"
```

Auto-advance enabled. Loop on by default.

### Bindings
**Create:**
```
"Play [sound]" then "Bind this to [phrase]"
"Bind [sound1], [sound2], [sound3] to [phrase]"  (random playback)
```

**Use:**
```
"[phrase]"  (plays bound sound)
```

**Manage:**
```
"List bound sounds"
"Unbind [phrase]"
"Unbind all sounds"
```

### Custom Audio
Drop files in `sounds/` folder:
- Standalone: Drop directly in `sounds/`
- Playlist: Create subfolder, drop files there

## Advanced

**Multi-sound binding:**
```
"Bind Login 1, Login 2, Login 3 to password correct"
→ Each time: random Login sound plays
```

**Combine with COVAS memory:**
```
Tell COVAS: "When I say 'Hello COVAS', ask for password. 
If correct, say 'password correct'."

Then: "Bind Login 1, Login 2, Login 3 to password correct"
```

## Troubleshooting

**Plugin won't load:** Restart COVAS, check logs
**No sounds playing:** Verify API key, internet connection
**Bindings not working:** "List bound sounds" to verify
**Can't find files:** "List cached sounds", verify filename

## Files

```
Songbird/
├── Songbird.py          # Main plugin
├── manifest.json        # Plugin metadata
├── bound_sounds.json    # Bindings (auto-created)
├── deps/                # Dependencies
└── sounds/              # Audio files (auto-created)
```

## What's New in v3.0

- **Playlists**: Auto-advance, loop by default, organize in folders
- **Seeking**: Jump to any time position (MM:SS or seconds)
- **Current info**: Check duration/position anytime
- **Background thread**: True auto-advance without user interaction
- Multi-sound bindings and random selection
- Better file matching

## Credits

**Author**: D. Trintignant  
**Version**: 3.0  
**COVAS NEXT**: https://ratherrude.github.io/Elite-Dangerous-AI-Integration/  
**Freesound API**: https://freesound.org/  
**Game**: Elite Dangerous (Frontier Developments)  
**License**: MIT