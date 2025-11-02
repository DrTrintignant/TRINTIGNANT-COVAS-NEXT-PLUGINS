# Covasify v2.0.0

Voice-controlled Spotify integration for COVAS NEXT. Play music, control playback, and bind tracks to custom voice commands.

**⚠️ Requires Spotify Premium** - Free accounts cannot use playback control features.

## What It Does

- Play tracks, albums, artists, and playlists by voice
- Control playback (pause, skip, seek, volume, shuffle, repeat)
- Save tracks to your Liked Songs
- **Bind tracks to custom phrases** - Say "workout intro" to instantly play your bound track
- Get current track info

## Installation

### 1. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app with these settings:
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
3. Copy your **Client ID** and **Client Secret**

### 2. Install Plugin

1. Place the `Covasify` folder in: `%appdata%\com.covas-next.ui\plugins\`

2. Restart COVAS NEXT

3. Open COVAS NEXT menu → Navigate to **Covasify Spotify Integration** settings

4. Enter your credentials:
   - **Client ID**: Paste your Spotify Client ID
   - **Client Secret**: Paste your Spotify Client Secret
   - **Redirect URI**: Leave as default `http://127.0.0.1:8888/callback`

5. First use will open browser for Spotify authorization (one-time setup)

**Requirements**: 
- **Spotify Premium account** (mandatory - free accounts cannot control playback)
- Active Spotify device (desktop app, mobile, or web player)

## Voice Commands

### Playing Music

```
"Play Bohemian Rhapsody"          # Track search
"Play Abbey Road album"           # Album
"Play Queen"                      # Artist (shuffled)
"Play Queen's top tracks"         # Top 10 hits
"Play workout playlist"           # Playlists
"Play Liked Songs"                # Your library
```

### Playback Control

```
"Pause" / "Resume" / "Stop"
"Next" / "Previous" / "Restart"
"Seek to 2:30"
"Volume up" / "Volume down" / "Set volume to 50" / "Mute"
"Shuffle on" / "Shuffle off"
"Repeat track" / "Repeat playlist" / "Repeat off"
```

### Library

```
"What's playing?"
"Save this track"
"Remove this track"
```

### Bindings

```
"Bind this to workout intro"      # Bind current track
"Workout intro"                   # Play bound track
"List bindings"
"Unbind workout intro"
"Unbind all"
```

### Performance

```
"Show Covasify cache stats"
```

## Troubleshooting

**"No active Spotify devices found"**
- Open Spotify on any device and start playing something first

**"Not connected to Spotify"**
- Check Settings UI has valid credentials entered
- Delete `.spotify_cache` and restart COVAS to re-authenticate
- Test with: "Test Covasify"

**Binding doesn't play immediately**
- Say the phrase again if needed (plugin overrides COVAS safety protocols but may need retry on first attempt)

**Need to re-authorize**
- Delete `.spotify_cache` from plugin folder
- Restart COVAS - browser will open for re-auth on first command

## What's NOT Possible

Due to Spotify API restrictions (November 2024):
- True radio/recommendations (API deprecated for new apps)
- Endless queue (API limitation - use artist/playlist playback instead)
- Related artists suggestions (API blocked)

## Files

```
Covasify/
  - Covasify.py              # Main plugin
  - manifest.json            # Plugin metadata
  - spotify_bindings.json    # Your bindings (auto-created)
  - .spotify_cache           # OAuth tokens (auto-created)
  - deps/                    # Bundled dependencies
```

## Version History

**v2.0.0** - Settings UI integration, credential management via COVAS NEXT menu  
**v1.0.0** - Initial release

## Credits

**Author**: D. Trintignant  
**COVAS NEXT**: https://ratherrude.github.io/Elite-Dangerous-AI-Integration/  
**Spotify API**: Spotipy library
