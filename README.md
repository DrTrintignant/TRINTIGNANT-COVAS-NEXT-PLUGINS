# COVAS-NEXT-PLUGINS 
This repository contains individual plugin packages for COVAS:NEXT (https://ratherrude.github.io/Elite-Dangerous-AI-Integration/)
Each plugin has its own README with installation instructions and usage details.

## Available Plugins

* **Songbird** — Voice-controlled sound effects from Freesound with local soundboard
* **Covasify** — Spotify integration with voice-controlled playback and track binding
* **Covinance** — Elite Dangerous commodity trading and market analysis via Ardent API

## Installation

1. Download or clone this repository
2. Copy the desired plugin folder(s) to `%appdata%\com.covas-next.ui\plugins\`
3. Restart COVAS NEXT
4. Configure plugin settings via COVAS NEXT menu (if required)

## Registered Actions (Quick Reference)

### Songbird
* `songbird_play_sound` — Play sounds from Freesound or local cache
* `songbird_control` — Pause, resume, stop, restart, volume control, mute
* `songbird_seek` — Seek to specific time position (MM:SS or seconds)
* `songbird_current` — Get current sound info (duration, position, track)
* `songbird_play_playlist` — Play folder as playlist (auto-advance, loop by default)
* `songbird_playlist_info` — Get current playlist status
* `songbird_playlist_contents` — Preview playlist tracks without playing
* `songbird_list_playlists` — List all available playlists
* `songbird_bind_sound` — Bind sounds to custom voice phrases
* `songbird_replay_bound` — Play previously bound sound
* `songbird_list_bound` — List all bound phrases
* `songbird_unbind_sound` — Remove specific binding
* `songbird_unbind_all` — Clear all bindings
* `songbird_list_cached` — List all downloaded sounds
* `songbird_delete_sound` — Delete specific cached sound
* `songbird_delete_current` — Delete currently playing sound
* `songbird_clear_sounds` — Delete sounds matching pattern
* `songbird_clean_cache` — Delete all cached sounds
* `songbird_cache_stats` — View cache performance metrics

### Covasify
* `covasify_play_track` — Search and play tracks
* `covasify_play_album` — Play complete albums
* `covasify_play_artist` — Play artist's music (shuffled)
* `covasify_play_top_tracks` — Play artist's top 10 hits
* `covasify_play_playlist` — Play user playlists or Liked Songs
* `covasify_control` — Pause, resume, next, previous, restart, stop, volume, mute, shuffle, repeat
* `covasify_seek` — Seek to time position (MM:SS or seconds)
* `covasify_current` — Get currently playing track info
* `covasify_save_track` — Add track to Liked Songs
* `covasify_remove_track` — Remove track from Liked Songs
* `covasify_bind_track` — Bind current track to custom phrase
* `covasify_play_bound` — Play previously bound track
* `covasify_list_bindings` — List all track bindings
* `covasify_unbind` — Remove specific binding
* `covasify_unbind_all` — Clear all bindings
* `covasify_cache_stats` — View cache performance metrics

### Covinance
* `covinance_best_buy` / `covinance_best_sell` — Find best commodity prices
* `covinance_nearby_buy` / `covinance_nearby_sell` — Search within radius
* `covinance_best_trade_from_here` — Optimal single-hop trade
* `covinance_trade_route` — Best commodity for A→B route
* `covinance_circular_route` — Multi-hop round-trip trading
* `covinance_optimal_trade_now` — Journal-aware trade optimization
* `covinance_list_rare_goods` — Discover rare goods within radius
* `covinance_safe_interstellar_factors` — Find bounty clearance (Anarchy systems)
* `covinance_find_service` — Locate nearest service/facility
* Station/system info, market data, and 30+ more trading actions

## Configuration

* **Songbird:** Requires Freesound API key (Settings → SONGBIRD)
* **Covasify:** Requires Spotify API credentials (Settings → Covasify)
* **Covinance:** No API key required (uses Ardent Insight API)

## License

MIT License — See individual plugin folders for details.