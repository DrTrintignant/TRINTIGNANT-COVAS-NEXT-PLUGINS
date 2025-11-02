from typing import override
import json
import os
import sys
import string  # Added for punctuation stripping
import re  # Moved from inside function
import random  # For random sound selection in bindings
import threading  # For ReliabilityClient thread safety
import time  # For retry delays
from datetime import datetime  # For cache TTL tracking

# Set up deps path BEFORE importing pygame and requests
current_dir = os.path.dirname(os.path.abspath(__file__))
deps_path = os.path.join(current_dir, 'deps')
if deps_path not in sys.path:
    sys.path.insert(0, deps_path)

# NOW import pygame and requests (they'll be found in deps/)
import pygame
import requests

from lib.PluginHelper import PluginHelper, PluginManifest
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid, TextSetting, ToggleSetting
from lib.Logger import log
from lib.EventManager import Projection
from lib.PluginBase import PluginBase
from lib.Event import Event

# ============================================================================
# PLAYLIST MONITOR - Background Thread for Auto-Advance
# ============================================================================

class PlaylistMonitor(threading.Thread):
    """Background thread that monitors playlist playback and handles auto-advance"""
    
    def __init__(self, plugin):
        super().__init__(daemon=True)  # Daemon thread dies with main program
        self.plugin = plugin
        self.running = True
        self.check_interval = 0.5  # Check every 0.5 seconds
        
    def run(self):
        """Main loop - checks for song endings and advances playlist"""
        log('info', 'SONGBIRD: Playlist monitor thread started')
        
        while self.running:
            try:
                time.sleep(self.check_interval)
                
                # Check if playlist is active and song ended
                if self.plugin.playlist_mode:
                    if not pygame.mixer.music.get_busy():
                        # Song ended, advance to next
                        self.plugin.check_and_advance_playlist()
                        
            except Exception as e:
                log('error', f'SONGBIRD: Playlist monitor error: {str(e)}')
        
        log('info', 'SONGBIRD: Playlist monitor thread stopped')
    
    def stop(self):
        """Stop the monitoring thread"""
        self.running = False

# ============================================================================
# RELIABILITY CLIENT - Caching System (from Covinance v7.6)
# ============================================================================

class ReliabilityClient:
    """Caching wrapper for Freesound API calls - 1 hour cache TTL"""
    
    TTL_DEFAULT = 3600  # 1 hour
    INFLIGHT_WAIT_TIMEOUT = 30
    
    def __init__(self):
        self.cache = {}
        self.lock = threading.RLock()
        self.in_flight = {}
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'inflight_hits': 0,
            'api_calls': 0,
            'errors': 0
        }
    
    def _make_cache_key(self, endpoint, params):
        """Generate cache key from endpoint and parameters"""
        param_str = json.dumps(params, sort_keys=True) if params else ""
        return f"{endpoint}:{param_str}"
    
    def get_cached_or_fetch(self, endpoint, params, fetch_fn):
        """
        Get cached data or fetch from API with in-flight deduplication.
        
        Args:
            endpoint: API endpoint identifier (e.g. 'freesound_search')
            params: Parameters for the request (used in cache key)
            fetch_fn: Function to call if cache miss - receives (endpoint, params)
        
        Returns:
            API response data or cached data
        """
        key = self._make_cache_key(endpoint, params)
        
        # Check cache first
        with self.lock:
            if key in self.cache:
                cached_data, cached_time, cached_ttl = self.cache[key]
                age = (datetime.now() - cached_time).total_seconds()
                if age < cached_ttl:
                    self.stats['cache_hits'] += 1
                    log('info', f'SONGBIRD: Cache HIT for {endpoint} (age: {age:.1f}s)')
                    return cached_data
            
            # Check if another thread is already fetching this
            if key in self.in_flight:
                event, result_holder = self.in_flight[key]
                log('info', f'SONGBIRD: In-flight HIT for {endpoint}')
        
        # Wait for in-flight request to complete
        if key in self.in_flight:
            event.wait(timeout=self.INFLIGHT_WAIT_TIMEOUT)
            with self.lock:
                if key in self.cache:
                    cached_data, cached_time, cached_ttl = self.cache[key]
                    age = (datetime.now() - cached_time).total_seconds()
                    if age < cached_ttl:
                        self.stats['inflight_hits'] += 1
                        return cached_data
        
        # Mark this request as in-flight
        with self.lock:
            if key not in self.in_flight:
                event = threading.Event()
                result_holder = [None, None]  # [result, error]
                self.in_flight[key] = (event, result_holder)
            else:
                event, result_holder = self.in_flight[key]
        
        # Double-check if another thread completed while we were setting up
        if result_holder[0] is not None or result_holder[1] is not None:
            event.wait(timeout=self.INFLIGHT_WAIT_TIMEOUT)
            with self.lock:
                if key in self.cache:
                    return self.cache[key][0]
                if result_holder[1] is not None:
                    raise result_holder[1]
        
        ttl = self.TTL_DEFAULT
        last_error = None
        result = None
        
        with self.lock:
            self.stats['cache_misses'] += 1
        
        try:
            # Retry logic with exponential backoff
            for attempt in range(3):
                try:
                    with self.lock:
                        self.stats['api_calls'] += 1
                    log('info', f'SONGBIRD: Cache MISS - Fetching {endpoint} (attempt {attempt + 1}/3)')
                    result = fetch_fn(endpoint, params)
                    
                    # Don't cache errors
                    is_error = (isinstance(result, dict) and 'error' in result) or result is None
                    
                    if is_error:
                        error_msg = result.get('error') if isinstance(result, dict) else 'None'
                        log('warning', f'SONGBIRD: Not caching error for {endpoint}: {error_msg}')
                        with self.lock:
                            result_holder[0] = result
                            self.stats['errors'] += 1
                        return result
                    
                    # Cache successful result
                    with self.lock:
                        self.cache[key] = (result, datetime.now(), ttl)
                        result_holder[0] = result
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    if attempt < 2:
                        wait = 2 ** attempt
                        log('warning', f'SONGBIRD: Retry in {wait}s...')
                        time.sleep(wait)
                    else:
                        log('error', f'SONGBIRD: Failed after 3 attempts: {str(e)}')
            
            with self.lock:
                result_holder[1] = last_error
                self.stats['errors'] += 1
            raise last_error
            
        finally:
            # Clean up in-flight tracking
            with self.lock:
                if key in self.in_flight:
                    event, _ = self.in_flight[key]
                    event.set()
                    del self.in_flight[key]

    def get_stats(self):
        """Get cache performance statistics"""
        with self.lock:
            total = self.stats['cache_hits'] + self.stats['cache_misses']
            hit_rate = (self.stats['cache_hits'] / total * 100) if total > 0 else 0
            
            return {
                'cache_hit_rate': f"{hit_rate:.1f}%",
                'total_requests': total,
                'api_calls_saved': self.stats['cache_hits'] + self.stats['inflight_hits'],
                **self.stats
            }

# ============================================================================
# PARALLEL RUNNER - Concurrent API Execution (from Covinance v7.6)
# ============================================================================

class ParallelRunner:
    """Execute API calls in parallel with progress tracking"""
    
    def __init__(self, max_workers: int = 5):
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def run_batch(self, tasks, timeout_per_task: float = 10.0):
        """
        Execute tasks in parallel.
        
        Args:
            tasks: List of callable functions (no arguments)
            timeout_per_task: Max seconds per individual task
        
        Returns:
            (successful_results, exceptions)
        """
        from concurrent.futures import as_completed
        
        if not tasks:
            return [], []
        
        futures = [self.executor.submit(task) for task in tasks]
        results = []
        exceptions = []
        
        for future in as_completed(futures, timeout=len(tasks) * timeout_per_task):
            try:
                result = future.result(timeout=timeout_per_task)
                if result is not None:
                    results.append(result)
            except Exception as e:
                exceptions.append(e)
                log('warning', f'SONGBIRD: Parallel task failed: {str(e)}')
        
        return results, exceptions
    
    def shutdown(self):
        """Cleanup thread pool"""
        self.executor.shutdown(wait=True)

# Main plugin class
class SONGBIRD(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        
        # Initialize reliability client for caching (1 hour TTL)
        self.reliability_client = ReliabilityClient()
        
        # Initialize parallel runner for concurrent API calls (5 workers for 5 pages)
        self.parallel_runner = ParallelRunner(max_workers=5)
        
        # Initialize pygame mixer for audio playback
        try:
            pygame.mixer.init()
            log('info', 'SONGBIRD: pygame mixer initialized')
        except Exception as e:
            log('error', f'SONGBIRD: Failed to initialize pygame mixer: {str(e)}')

        # Track currently playing sound for binding system
        self.current_playing = None
        self.last_played_description = None
        
        # Store API key (loaded from Settings UI in on_plugin_helper_ready)
        self.api_key = None
        
        # Playlist state management
        self.playlist_mode = False
        self.playlist_queue = []  # List of filepaths
        self.playlist_index = 0
        self.playlist_name = ""
        self.playlist_loop = False
        self.playlist_shuffle = False
        
        # Thread safety lock for playlist state
        self.playlist_lock = threading.Lock()
        
        # Start background monitor thread for auto-advance
        self.playlist_monitor = PlaylistMonitor(self)
        self.playlist_monitor.start()
        
        # pygame event for auto-advancing playlists
        self.PLAYLIST_END_EVENT = pygame.USEREVENT + 1

        # Settings UI for Freesound API Key
        self.settings_config: PluginSettings | None = PluginSettings(
            key="SONGBIRDPlugin",
            label="SONGBIRD Sound Integration",
            icon="volume_up",
            grids=[
                SettingsGrid(
                    key="freesound_api",
                    label="Freesound API Configuration",
                    fields=[
                        TextSetting(
                            key="api_key",
                            label="Freesound API Key",
                            type="text",
                            readonly=False,
                            placeholder="Your Freesound API Key",
                            default_value=""
                        )
                    ]
                )
            ]
        )
    
    def normalize_phrase(self, phrase: str) -> str:
        """
        Normalize phrase for consistent matching across binding system.
        
        Converts phrase to lowercase, removes punctuation, and trims whitespace.
        Used for both creating and matching sound bindings.
        
        Args:
            phrase: Raw phrase string to normalize
            
        Returns:
            Normalized phrase with lowercase, no punctuation, single spaces
            Returns empty string if input is empty
            
        Example:
            >>> normalize_phrase("Play, the Sound!")
            'play the sound'
        """
        if not phrase:
            return ""
        # Remove punctuation
        cleaned = phrase.translate(str.maketrans('', '', string.punctuation))
        # Remove extra whitespace and lowercase
        return ' '.join(cleaned.lower().split())
    
    def convert_word_numbers_to_digits(self, text: str) -> str:
        """
        Convert word numbers to digit format for filename matching.
        
        Converts number words (one, two, three) to digits (1, 2, 3) to help
        match user speech with numbered sound files like "Login 1.mp3".
        
        Args:
            text: String potentially containing word numbers
            
        Returns:
            String with word numbers converted to digits
            Non-number words unchanged
            
        Example:
            >>> convert_word_numbers_to_digits("play login one")
            'play login 1'
            >>> convert_word_numbers_to_digits("play sound twenty")
            'play sound 20'
        """
        word_to_digit = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
            'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
            'eighteen': '18', 'nineteen': '19', 'twenty': '20'
        }
        
        words = text.split()
        converted = []
        for word in words:
            if word.lower() in word_to_digit:
                converted.append(word_to_digit[word.lower()])
            else:
                converted.append(word)
        
        return ' '.join(converted)
    
    @override
    def register_actions(self, helper: PluginHelper):
        helper.register_action(
            'songbird_play_sound', 
            "Play any sound request including: new sounds from Freesound, replay requests (play again, replay, play it again, replay last song, replay it), and cached sound playback. Use cache for replay requests, Freesound for new/different sounds.", 
            {
                "type": "object",
                "properties": {
                    "sound_description": {
                        "type": "string",
                        "description": "Natural language description of the sound to play, including replay requests like 'last song', 'it', 'that sound'"
                    },
                    "replay_mode": {
                        "type": "string",
                        "description": "Whether this is a replay request ('again', 'same') or new request ('another', 'different', 'new')",
                        "enum": ["again", "new", "auto"]
                    },
                    "context": {
                        "type": "string", 
                        "description": "Optional context about when/why this sound should play"
                    }
                },
                "required": ["sound_description"]
            }, 
            self.songbird_play_sound, 
            'global'
        )

        helper.register_action(
            'songbird_control', 
            "Control Songbird audio playback. Use this to: pause or resume audio, stop playback entirely, restart current sound from beginning, skip to next sound in playlist, go to previous sound in playlist, increase or decrease volume, set volume to specific percentage, mute or unmute audio, enable or disable shuffle mode, enable or disable repeat mode.", 
            {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Control command: pause, resume, play, stop, restart, next, previous, skip, back, volume_up, volume_down, volume_set, mute, unmute, shuffle_on, shuffle_off, repeat_on, repeat_off"
                    },
                    "value": {
                        "type": "integer",
                        "description": "Value for volume_set command (0-100)"
                    }
                },
                "required": ["command"]
            }, 
            self.songbird_control, 
            'global'
        )
        
        helper.register_action(
            'songbird_seek',
            "Seek to a specific position in the currently playing sound. Accepts natural time formats like '2:30' or total seconds. Note: Seeking works best with MP3/OGG files, limited support for WAV.",
            {
                "type": "object",
                "properties": {
                    "time_input": {
                        "type": "string",
                        "description": "Time position to seek to. Can be 'MM:SS' format (e.g., '2:30'), 'H:MM:SS' format (e.g., '1:15:30'), or total seconds (e.g., '150')"
                    }
                },
                "required": ["time_input"]
            },
            self.songbird_seek,
            'global'
        )
        
        helper.register_action(
            'songbird_current',
            "Get information about the currently playing sound: name, duration, current position, source (playlist/standalone). Use this for queries like 'how long is this sound', 'what position are we at', 'what's playing'.",
            {
                "type": "object",
                "properties": {}
            },
            self.songbird_current,
            'global'
        )

        helper.register_action(
            'songbird_test', 
            "Test the SONGBIRD plugin functionality.", 
            {
                "type": "object",
                "properties": {}
            }, 
            self.songbird_test, 
            'global'
        )

        helper.register_action(
            'songbird_cache_stats',
            "Show SONGBIRD cache performance statistics including hit rate, API calls saved, and total requests.",
            {
                "type": "object",
                "properties": {}
            },
            self.songbird_cache_stats,
            'global'
        )

        helper.register_action(
            'songbird_delete_sound',
            "Delete a specific sound file from local cache by name. Example: 'Delete explosion 3'",
            {
                "type": "object",
                "properties": {
                    "sound_name": {
                        "type": "string",
                        "description": "Name of the sound file to delete"
                    }
                },
                "required": ["sound_name"]
            },
            self.songbird_delete_sound,
            'global'
        )

        helper.register_action(
            'songbird_delete_current',
            "Delete the currently playing sound from local cache. Example: 'Delete this sound'",
            {
                "type": "object",
                "properties": {}
            },
            self.songbird_delete_current,
            'global'
        )

        helper.register_action(
            'songbird_clear_sounds',
            "Delete all sound files matching a pattern. Example: 'Clear explosion sounds' removes all files with 'explosion' in the name.",
            {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Pattern to match (e.g., 'explosion', 'thunder', 'login')"
                    }
                },
                "required": ["pattern"]
            },
            self.songbird_clear_sounds,
            'global'
        )

        helper.register_action(
            'songbird_clean_cache',
            "Delete ALL downloaded sound files from cache. Example: 'Clean cache' or 'Clear all sounds'. WARNING: This removes all cached audio files.",
            {
                "type": "object",
                "properties": {}
            },
            self.songbird_clean_cache,
            'global'
        )

        helper.register_action(
            'songbird_bind_sound', 
            "Bind the last played sound to a specific command phrase for future replay. If the phrase already exists, adds this sound to that phrase's sound list (for random selection).", 
            {
                "type": "object",
                "properties": {
                    "bind_phrase": {
                        "type": "string",
                        "description": "The command phrase to bind the current sound to"
                    }
                },
                "required": ["bind_phrase"]
            }, 
            self.songbird_bind_sound, 
            'global'
        )

        helper.register_action(
            'songbird_bind_multiple', 
            "Bind multiple sound files to a phrase in one command. Searches for each sound name in cached sounds and binds all matches to the phrase for random selection.", 
            {
                "type": "object",
                "properties": {
                    "sound_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of sound names to bind (e.g., ['Login 1', 'Login 2', 'Login 3'])"
                    },
                    "bind_phrase": {
                        "type": "string",
                        "description": "The command phrase to bind all these sounds to"
                    }
                },
                "required": ["sound_names", "bind_phrase"]
            }, 
            self.songbird_bind_multiple, 
            'global'
        )

        helper.register_action(
            'songbird_replay_bound', 
            "CRITICAL: Execute this action IMMEDIATELY when user says a bound sound phrase. If multiple sounds are bound to the phrase, randomly selects one to play (provides variety on repeated triggers). NO confirmation required. The bound phrase itself IS the execution command. If user says a short phrase (1-3 words) that could be a sound binding, call this action INSTANTLY.", 
            {
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "The bound phrase to trigger replay"
                    }
                },
                "required": ["phrase"]
            }, 
            self.songbird_replay_bound, 
            'global'
        )

        helper.register_action(
            'songbird_list_bound', 
            "List all sounds that have been bound to command phrases.", 
            {
                "type": "object",
                "properties": {}
            }, 
            self.songbird_list_bound, 
            'global'
        )

        helper.register_action(
            'songbird_unbind_sound', 
            "Remove a specific sound binding by phrase.", 
            {
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "The exact phrase to unbind"
                    }
                },
                "required": ["phrase"]
            }, 
            self.songbird_unbind_sound, 
            'global'
        )

        helper.register_action(
            'songbird_unbind_all', 
            "Remove all sound bindings at once.", 
            {
                "type": "object",
                "properties": {}
            }, 
            self.songbird_unbind_all, 
            'global'
        )

        # NEW ACTION: List cached sounds
        helper.register_action(
            'songbird_list_cached', 
            "CRITICAL: ALWAYS call this action for ANY question about sounds, audio files, or what's available. Trigger on: 'what sounds', 'which sounds', 'how many sounds', 'do you have sounds', 'sounds saved', 'sounds cached', 'sounds downloaded', 'list sounds', 'show sounds', 'see sounds', 'check sounds', 'sounds in cache', 'available sounds', 'my sounds', 'sound files', 'audio files', 'what audio', 'sound list', or ANY variation asking about sound availability. DO NOT respond with 'I don't know' or 'no sounds' without calling this action first. This checks actual sound files in the sounds folder.", 
            {
                "type": "object",
                "properties": {}
            }, 
            self.songbird_list_cached, 
            'global'
        )
        
        # Playlist Actions
        helper.register_action(
            'songbird_play_playlist',
            "Play all sounds in a folder as a sequential playlist. Use for requests like 'play Defence playlist', 'play sounds in Login folder', or 'play all sounds from Combat'. The folder name is extracted from user's request.",
            {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Name of the folder inside sounds/ directory to play as playlist"
                    },
                    "shuffle": {
                        "type": "boolean",
                        "description": "Whether to shuffle the playlist order",
                        "default": False
                    },
                    "loop": {
                        "type": "boolean",
                        "description": "Whether to loop the playlist when it ends",
                        "default": False
                    }
                },
                "required": ["folder_name"]
            },
            self.songbird_play_playlist,
            'global'
        )
        
        helper.register_action(
            'songbird_playlist_info',
            "Get information about the currently playing playlist: current song, position, total songs, shuffle/loop status.",
            {
                "type": "object",
                "properties": {}
            },
            self.songbird_playlist_info,
            'global'
        )
        
        helper.register_action(
            'songbird_list_playlists',
            "List all available playlists (folders in sounds directory that contain audio files).",
            {
                "type": "object",
                "properties": {}
            },
            self.songbird_list_playlists,
            'global'
        )
        
        helper.register_action(
            'songbird_playlist_contents',
            "Show the contents (track list) of a specific playlist without playing it. Use for queries like 'what's in Prova playlist', 'show me tracks in Combat playlist', 'list songs in Login folder'.",
            {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Name of the playlist folder to inspect"
                    }
                },
                "required": ["folder_name"]
            },
            self.songbird_playlist_contents,
            'global'
        )

        log('info', f"SONGBIRD actions registered successfully")
        
    @override
    def register_projections(self, helper: PluginHelper):
        pass

    @override
    def register_sideeffects(self, helper: PluginHelper):
        pass
        
    @override
    def register_prompt_event_handlers(self, helper: PluginHelper):
        pass
        
    @override
    def register_status_generators(self, helper: PluginHelper):
        # Register status generator for playlist auto-advance
        helper.register_status_generator(
            'songbird_playlist_status',
            self.check_playlist_status,
            'global'
        )
    
    def check_playlist_status(self, projected_states) -> str:
        """
        Status generator - no longer needed for auto-advance since background thread handles it.
        Kept for compatibility but does nothing.
        """
        return ""

    @override
    def register_should_reply_handlers(self, helper: PluginHelper):
        pass
    
    def load_api_key(self, helper: PluginHelper) -> str:
        """
        Load Freesound API key from Settings UI.
        Returns empty string if not configured.
        """
        try:
            log('info', 'SONGBIRD: Loading API key from Settings UI')
            api_key = helper.get_plugin_setting('SONGBIRDPlugin', 'freesound_api', 'api_key')
            
            if api_key:
                log('info', f'SONGBIRD: API key loaded from Settings UI (length: {len(api_key)} characters)')
                return api_key
            else:
                log('warning', 'SONGBIRD: No API key found in Settings UI')
                return ""
                
        except Exception as e:
            log('error', f'SONGBIRD: Error loading API key from Settings: {str(e)}')
            return ""
    
    @override
    def on_plugin_helper_ready(self, helper: PluginHelper):
        log('info', 'SONGBIRD plugin helper is ready')
        
        # Load API key from Settings UI
        self.api_key = self.load_api_key(helper)
        if not self.api_key:
            log('warning', 'SONGBIRD: No API key configured. Please add your Freesound API key in Settings.')
        else:
            log('info', 'SONGBIRD: API key loaded successfully')
    
    @override
    def on_chat_stop(self, helper: PluginHelper):
        log('info', 'SONGBIRD: Chat stopped - cleaning up resources')
        
        # Stop playlist monitor thread
        try:
            self.playlist_monitor.stop()
            log('info', 'SONGBIRD: Playlist monitor stopped successfully')
        except Exception as e:
            log('error', f'SONGBIRD: Error stopping playlist monitor: {str(e)}')
        
        # Cleanup parallel runner thread pool
        try:
            self.parallel_runner.shutdown()
            log('info', 'SONGBIRD: Parallel runner shut down successfully')
        except Exception as e:
            log('error', f'SONGBIRD: Error shutting down parallel runner: {str(e)}')

    def get_plugin_folder_path(self) -> str:
        """
        Get absolute path to Songbird plugin folder.
        
        Tries two methods to locate the plugin folder:
        1. Directory of current file (__file__)
        2. Standard APPDATA path construction
        
        Returns:
            Absolute path to plugin folder, or empty string if not found
            
        Note:
            Plugin folder contains:
            - sounds/ directory (cached audio files)
            - bound_sounds.json (binding configuration)
            - Songbird.py (this file)
        """
        try:
            # Method 1: Get directory of current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            return current_dir
        except:
            try:
                # Method 2: Construct from APPDATA
                appdata = os.getenv('APPDATA')
                if appdata:
                    return os.path.join(appdata, 'com.covas-next.ui', 'plugins', 'Songbird')
            except:
                pass
        return ""

    def search_freesound(self, query: str, page: int = 1) -> dict:
        """Search Freesound API for sounds matching the query (CACHED)"""
        # Use ReliabilityClient for caching with 1-hour TTL
        endpoint = 'freesound_search'
        params = {
            'query': query,
            'page': page
        }
        
        return self.reliability_client.get_cached_or_fetch(
            endpoint, 
            params, 
            self._fetch_freesound
        )
    
    def _fetch_freesound(self, endpoint: str, params: dict) -> dict:
        """
        Internal method: Actual Freesound API call (used by ReliabilityClient).
        This is called only on cache miss.
        """
        try:
            # Extract params (api_key_hash is only for cache key)
            query = params['query']
            page = params['page']
            
            url = "https://freesound.org/apiv2/search/text/"
            headers = {
                "Authorization": f"Token {self.api_key}"
            }
            request_params = {
                "query": query,
                "page": page,
                "page_size": 15,
                "fields": "id,name,previews,download,url,username"
            }
            
            log('info', f"SONGBIRD: Fetching from Freesound API: '{query}' (page {page})")
            response = requests.get(url, headers=headers, params=request_params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                log('info', f"SONGBIRD: API returned {count} total sounds for '{query}' (page {page})")
                return data
            elif response.status_code == 401:
                log('error', f"SONGBIRD: Invalid API key (401 Unauthorized)")
                return {"error": "Invalid API key"}
            else:
                log('error', f"SONGBIRD: API request failed with status {response.status_code}: {response.text}")
                return {"error": f"API request failed: {response.status_code}"}
                
        except Exception as e:
            log('error', f"SONGBIRD: API fetch error - {str(e)}")
            return {"error": str(e)}

    def get_varied_freesound_results(self, query: str) -> list:
        """
        Get varied results from multiple pages of Freesound.
        Fetches pages 1-5 CONCURRENTLY for speed (benefits from caching).
        """
        try:
            log('info', f"SONGBIRD: Starting parallel search for '{query}' (5 pages)")
            
            # Create 5 tasks to fetch pages 1-5 concurrently
            tasks = [
                lambda page=p: self.search_freesound(query, page)
                for p in range(1, 6)
            ]
            
            # Execute all page fetches in parallel
            page_results, exceptions = self.parallel_runner.run_batch(tasks, timeout_per_task=10.0)
            
            # Log any exceptions
            if exceptions:
                log('warning', f"SONGBIRD: {len(exceptions)} page fetch(es) failed during parallel search")
            
            # Process results
            all_results = []
            first_page_error = None
            
            for page_data in page_results:
                # Check for errors
                if isinstance(page_data, dict) and "error" in page_data:
                    # Track first error (for page 1 failure handling)
                    if first_page_error is None:
                        first_page_error = page_data["error"]
                    continue
                
                # Extract results from this page
                results = page_data.get('results', []) if isinstance(page_data, dict) else []
                if results:
                    all_results.extend(results)
            
            # If no results and we had a first page error, return error
            if not all_results and first_page_error:
                log('error', f"SONGBIRD: First page failed with: {first_page_error}")
                return [{"error": first_page_error}]
            
            # If no results at all
            if not all_results:
                log('warning', f"SONGBIRD: No results found for '{query}'")
                return []
            
            log('info', f"SONGBIRD: Parallel search completed - Collected {len(all_results)} total results from {len(page_results)} pages")
            return all_results
            
        except Exception as e:
            log('error', f"SONGBIRD: Error in parallel search: {str(e)}")
            return [{"error": str(e)}]

    def select_random_sound(self, results: list) -> dict:
        """
        Select a random sound from search results for variety.
        
        Args:
            results: List of sound dictionaries from Freesound API
            
        Returns:
            Single randomly-selected sound dictionary
            Returns error dict if results empty or selection fails
            
        Note:
            Used to provide variety - same search query returns
            different sounds on repeated plays. Prevents predictability
            and makes soundboard more engaging.
        """
        try:
            if not results:
                return {"error": "No results to select from"}
            
            # Randomly select from available results
            selected = random.choice(results)
            
            log('info', f"SONGBIRD: Randomly selected '{selected.get('name', 'Unknown')}' from {len(results)} options")
            return selected
            
        except Exception as e:
            log('error', f"SONGBIRD: Error selecting random sound: {str(e)}")
            return results[0] if results else {"error": "No results available"}

    def download_and_play_sound(self, sound_data: dict) -> str:
        """Download and play a sound file using pygame"""
        try:
            # Get preview URL - simplified with priority list
            previews = sound_data.get('previews', {})
            preview_url = None
            file_extension = '.mp3'
            
            # Priority list: best quality first
            PREVIEW_PRIORITY = [
                ('preview-hq-mp3', '.mp3'),
                ('preview-lq-mp3', '.mp3'),
                ('preview-hq-ogg', '.ogg'),
                ('preview-lq-ogg', '.ogg')
            ]
            
            for preview_key, ext in PREVIEW_PRIORITY:
                if preview_key in previews and previews[preview_key]:
                    preview_url = previews[preview_key]
                    file_extension = ext
                    break
            
            if not preview_url:
                return "No preview available for this sound"
            
            log('info', f"SONGBIRD: Downloading from {preview_url}")
            
            # Download the sound file
            response = requests.get(preview_url, timeout=30)
            if response.status_code != 200:
                return f"Failed to download sound (HTTP {response.status_code})"
            
            # Create sounds folder in plugin directory
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            
            # Create sounds directory if it doesn't exist
            if not os.path.exists(sounds_folder):
                os.makedirs(sounds_folder)
                log('info', f"SONGBIRD: Created sounds folder at {sounds_folder}")
            
            # Create filename based on sound info
            sound_name = sound_data.get('name', 'unknown_sound')
            sound_id = sound_data.get('id', 'unknown')
            # Clean filename (remove invalid characters)
            safe_name = "".join(c for c in sound_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_name}_{sound_id}{file_extension}"
            filepath = os.path.join(sounds_folder, filename)
            
            # Save the file
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            log('info', f"SONGBIRD: Sound saved to {filepath}")
            
            # Play the sound using pygame
            try:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                
                log('info', f"SONGBIRD: Playing sound invisibly: {sound_name}")
                return f"Playing '{sound_name}'"
                
            except Exception as play_error:
                log('error', f"SONGBIRD: Error playing sound with pygame: {str(play_error)}")
                return f"Downloaded '{sound_name}' to sounds folder but failed to play: {str(play_error)}"
                    
        except Exception as e:
            log('error', f"SONGBIRD: Error in download_and_play_sound: {str(e)}")
            return f"Error downloading/playing sound: {str(e)}"

    def songbird_control(self, args, projected_states) -> str:
        """Control audio playback using structured commands (Covasify pattern)"""
        try:
            # Check if playlist song ended and auto-advance
            self.check_and_advance_playlist()
            
            command = args.get('command', '').lower().strip()
            value = args.get('value', 50)
            
            log('info', f"SONGBIRD: Control command: '{command}'")
            
            # Pause commands
            if command in ['pause', 'hold']:
                pygame.mixer.music.pause()
                log('info', 'SONGBIRD: Paused playback')
                return "SONGBIRD: Audio paused"
            
            # Resume commands
            elif command in ['resume', 'play', 'unpause']:
                pygame.mixer.music.unpause()
                log('info', 'SONGBIRD: Resumed playback')
                return "SONGBIRD: Audio resumed"
            
            # Stop commands
            elif command in ['stop', 'halt', 'end']:
                pygame.mixer.music.stop()
                if self.playlist_mode:
                    self.playlist_mode = False
                    self.playlist_queue = []
                    log('info', 'SONGBIRD: Stopped playback and exited playlist mode')
                    return "SONGBIRD: Audio stopped and playlist ended"
                log('info', 'SONGBIRD: Stopped playback')
                return "SONGBIRD: Audio stopped"
            
            # Restart current sound
            elif command in ['restart', 'restart_track', 'restart_sound', 'start_over']:
                pygame.mixer.music.rewind()
                log('info', 'SONGBIRD: Restarted from beginning')
                return "SONGBIRD: Restarted sound from beginning"
            
            # Volume up
            elif command in ['volume_up', 'louder', 'increase_volume']:
                current_volume = pygame.mixer.music.get_volume()
                new_volume = min(1.0, current_volume + 0.1)
                pygame.mixer.music.set_volume(new_volume)
                log('info', f'SONGBIRD: Volume increased to {int(new_volume * 100)}%')
                return f"SONGBIRD: Volume increased to {int(new_volume * 100)}%"
            
            # Volume down
            elif command in ['volume_down', 'quieter', 'decrease_volume']:
                current_volume = pygame.mixer.music.get_volume()
                new_volume = max(0.0, current_volume - 0.1)
                pygame.mixer.music.set_volume(new_volume)
                log('info', f'SONGBIRD: Volume decreased to {int(new_volume * 100)}%')
                return f"SONGBIRD: Volume decreased to {int(new_volume * 100)}%"
            
            # Set specific volume
            elif command in ['volume_set', 'set_volume']:
                pygame_volume = max(0.0, min(1.0, value / 100.0))
                pygame.mixer.music.set_volume(pygame_volume)
                log('info', f'SONGBIRD: Volume set to {int(pygame_volume * 100)}%')
                return f"SONGBIRD: Volume set to {int(pygame_volume * 100)}%"
            
            # Mute
            elif command in ['mute', 'silence']:
                pygame.mixer.music.set_volume(0.0)
                log('info', 'SONGBIRD: Muted')
                return "SONGBIRD: Audio muted"
            
            # Unmute
            elif command in ['unmute', 'unsilence']:
                pygame.mixer.music.set_volume(0.7)
                log('info', 'SONGBIRD: Unmuted to 70%')
                return "SONGBIRD: Audio unmuted to 70%"
            
            # Playlist: Next/Skip
            elif command in ['next', 'skip', 'skip_forward']:
                if self.playlist_mode and self.playlist_queue:
                    return self.playlist_next()
                else:
                    return "SONGBIRD: No playlist active. Use 'play [folder] playlist' to start one."
            
            # Playlist: Previous/Back
            elif command in ['previous', 'back', 'skip_back']:
                if self.playlist_mode and self.playlist_queue:
                    return self.playlist_previous()
                else:
                    return "SONGBIRD: No playlist active. Use 'play [folder] playlist' to start one."
            
            # Playlist: Shuffle on
            elif command in ['shuffle_on', 'enable_shuffle', 'shuffle']:
                if self.playlist_mode:
                    self.playlist_shuffle = True
                    # Re-shuffle remaining songs
                    if self.playlist_index < len(self.playlist_queue) - 1:
                        remaining = self.playlist_queue[self.playlist_index + 1:]
                        random.shuffle(remaining)
                        self.playlist_queue[self.playlist_index + 1:] = remaining
                    log('info', 'SONGBIRD: Shuffle enabled')
                    return "SONGBIRD: Shuffle enabled for playlist"
                else:
                    return "SONGBIRD: No playlist active"
            
            # Playlist: Shuffle off
            elif command in ['shuffle_off', 'disable_shuffle', 'no_shuffle']:
                if self.playlist_mode:
                    self.playlist_shuffle = False
                    log('info', 'SONGBIRD: Shuffle disabled')
                    return "SONGBIRD: Shuffle disabled"
                else:
                    return "SONGBIRD: No playlist active"
            
            # Playlist: Repeat/Loop on
            elif command in ['repeat_on', 'loop_on', 'repeat', 'loop']:
                if self.playlist_mode:
                    self.playlist_loop = True
                    log('info', 'SONGBIRD: Repeat enabled')
                    return "SONGBIRD: Playlist will loop"
                else:
                    return "SONGBIRD: No playlist active"
            
            # Playlist: Repeat/Loop off
            elif command in ['repeat_off', 'loop_off', 'no_repeat', 'no_loop']:
                if self.playlist_mode:
                    self.playlist_loop = False
                    log('info', 'SONGBIRD: Repeat disabled')
                    return "SONGBIRD: Playlist will stop at end"
                else:
                    return "SONGBIRD: No playlist active"
            
            else:
                return f"SONGBIRD: Unknown command '{command}'. Available: pause, resume, stop, restart, volume_up, volume_down, volume_set, mute, unmute, next, previous, shuffle, repeat"
            
        except Exception as e:
            log('error', f"SONGBIRD control error: {str(e)}")
            return f"SONGBIRD: Control error - {str(e)}"
    
    def songbird_seek(self, args, projected_states) -> str:
        """Seek to specific position in currently playing sound - handles multiple time formats"""
        try:
            time_input = args.get('time_input', '').strip()
            
            if not time_input:
                return "SONGBIRD: No time position provided."
            
            log('info', f'SONGBIRD: Seek request: {time_input}')
            
            # Check if music is playing
            if not pygame.mixer.music.get_busy():
                return "SONGBIRD: No sound currently playing to seek."
            
            # Parse time input to seconds (pygame uses seconds, not milliseconds)
            position_seconds = self._parse_time_to_seconds(time_input)
            
            if position_seconds is None:
                return f"SONGBIRD: Could not parse time '{time_input}'. Use format like '2:30' or '150' seconds."
            
            # Get current sound info if available
            sound_name = "current sound"
            if self.current_playing:
                sound_name = self.current_playing.get('sound_name', 'current sound')
            
            # Try to seek using pygame's set_pos
            # NOTE: set_pos support varies by format:
            # - MP3/OGG: Good support
            # - WAV: Limited or no support
            # - Position is from start of file, in seconds (float)
            try:
                pygame.mixer.music.set_pos(position_seconds)
                
                # Format position for response
                seek_min = int(position_seconds // 60)
                seek_sec = int(position_seconds % 60)
                
                log('info', f'SONGBIRD: Seeked to {seek_min}:{seek_sec:02d} in {sound_name}')
                return f"SONGBIRD: Seeked to {seek_min}:{seek_sec:02d} in {sound_name}."
                
            except pygame.error as pg_error:
                # Seeking not supported for this format
                log('warning', f'SONGBIRD: Seeking not supported: {str(pg_error)}')
                return f"SONGBIRD: Seeking not supported for this audio format. (Works best with MP3/OGG files)"
            
        except Exception as e:
            log('error', f'SONGBIRD seek error: {str(e)}')
            return f"SONGBIRD: Failed to seek - {str(e)}"

    def _parse_time_to_seconds(self, time_input: str) -> float:
        """Parse time string to seconds - handles MM:SS, H:MM:SS, or seconds"""
        try:
            time_input = time_input.strip().lower()
            
            # Remove common words
            time_input = time_input.replace('minutes', '').replace('minute', '')
            time_input = time_input.replace('seconds', '').replace('second', '')
            time_input = time_input.replace('and', '').strip()
            
            # Check if it's just a number (seconds)
            try:
                return float(time_input)
            except ValueError:
                pass
            
            # Check for MM:SS or H:MM:SS format
            if ':' in time_input:
                parts = time_input.split(':')
                
                if len(parts) == 2:
                    # MM:SS format
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    return float(minutes * 60 + seconds)
                    
                elif len(parts) == 3:
                    # H:MM:SS format
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    return float(hours * 3600 + minutes * 60 + seconds)
            
            # Try to extract numbers (e.g., "2 minutes 30 seconds")
            numbers = re.findall(r'\d+', time_input)
            
            if len(numbers) == 2:
                # Assume first is minutes, second is seconds
                minutes = int(numbers[0])
                seconds = int(numbers[1])
                return float(minutes * 60 + seconds)
            elif len(numbers) == 1:
                # Just one number - assume seconds
                return float(numbers[0])
            
            return None
            
        except Exception as e:
            log('error', f'SONGBIRD: Error parsing time {time_input}: {str(e)}')
            return None
    
    def songbird_current(self, args, projected_states) -> str:
        """
        Get information about currently playing sound.
        Shows: name, duration, position, source (playlist/standalone).
        """
        try:
            # Check if anything is playing
            if not pygame.mixer.music.get_busy():
                return "SONGBIRD: No sound currently playing."
            
            # Get current sound info
            if not self.current_playing:
                return "SONGBIRD: Sound playing but no metadata available."
            
            sound_name = self.current_playing.get('sound_name', 'Unknown')
            
            # Get position using pygame (returns seconds as float)
            try:
                current_pos = pygame.mixer.music.get_pos() / 1000.0  # Convert ms to seconds
            except:
                current_pos = 0
            
            # Try to get duration from audio file
            duration = None
            if 'filepath' in self.current_playing:
                try:
                    from mutagen import File as MutagenFile
                    audio = MutagenFile(self.current_playing['filepath'])
                    if audio and hasattr(audio.info, 'length'):
                        duration = audio.info.length
                except:
                    # If mutagen not available or fails, we can't get duration
                    pass
            
            # Format position
            pos_formatted = self._format_time(current_pos)
            
            # Build response
            if duration:
                duration_formatted = self._format_time(duration)
                progress_info = f"Position: {pos_formatted} / {duration_formatted}"
            else:
                progress_info = f"Position: {pos_formatted}"
            
            # Check if part of playlist
            source_info = ""
            if self.playlist_mode and self.playlist_queue:
                playlist_name = self.playlist_name if hasattr(self, 'playlist_name') else 'playlist'
                track_num = self.playlist_index + 1
                total_tracks = len(self.playlist_queue)
                source_info = f" (Track {track_num}/{total_tracks} in '{playlist_name}')"
            
            result = f"SONGBIRD: Now playing '{sound_name}'. {progress_info}.{source_info}"
            
            log('info', f'SONGBIRD: Current sound info - {sound_name} at {pos_formatted}')
            return result
            
        except Exception as e:
            log('error', f'SONGBIRD current error: {str(e)}')
            return f"SONGBIRD: Failed to get current sound info - {str(e)}"
    
    def playlist_next(self) -> str:
        """Skip to next sound in playlist"""
        try:
            if not self.playlist_mode or not self.playlist_queue:
                return "SONGBIRD: No playlist active"
            
            # Move to next sound
            self.playlist_index += 1
            
            # Check if we reached the end
            if self.playlist_index >= len(self.playlist_queue):
                if self.playlist_loop:
                    # Loop back to start
                    self.playlist_index = 0
                    log('info', 'SONGBIRD: Playlist looping back to start')
                else:
                    # End of playlist
                    self.playlist_mode = False
                    pygame.mixer.music.stop()
                    log('info', 'SONGBIRD: Reached end of playlist')
                    return "SONGBIRD: Reached end of playlist"
            
            # Play next sound
            return self._play_playlist_sound()
            
        except Exception as e:
            log('error', f"SONGBIRD playlist_next error: {str(e)}")
            return f"SONGBIRD: Error skipping to next sound - {str(e)}"
    
    def playlist_previous(self) -> str:
        """Go to previous sound in playlist"""
        try:
            if not self.playlist_mode or not self.playlist_queue:
                return "SONGBIRD: No playlist active"
            
            # Move to previous sound
            self.playlist_index = max(0, self.playlist_index - 1)
            
            # Play previous sound
            return self._play_playlist_sound()
            
        except Exception as e:
            log('error', f"SONGBIRD playlist_previous error: {str(e)}")
            return f"SONGBIRD: Error going to previous sound - {str(e)}"
    
    def _play_playlist_sound(self) -> str:
        """Internal helper to play current playlist sound"""
        try:
            if not self.playlist_mode or not self.playlist_queue:
                return "SONGBIRD: No playlist active"
            
            if self.playlist_index >= len(self.playlist_queue):
                return "SONGBIRD: Invalid playlist index"
            
            filepath = self.playlist_queue[self.playlist_index]
            filename = os.path.basename(filepath)
            
            # Remove extension and Freesound ID for display
            name_without_ext = os.path.splitext(filename)[0]
            name_parts = name_without_ext.rsplit('_', 1)
            if len(name_parts) == 2 and name_parts[1].isdigit():
                display_name = name_parts[0].replace('_', ' ')
            else:
                display_name = name_without_ext.replace('_', ' ')
            
            # Load and play
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            # Set end event for auto-advance
            pygame.mixer.music.set_endevent(self.PLAYLIST_END_EVENT)
            
            position = self.playlist_index + 1
            total = len(self.playlist_queue)
            
            log('info', f"SONGBIRD: Playing playlist sound {position}/{total}: {display_name}")
            return f"SONGBIRD: Playing {position}/{total}: '{display_name}'"
            
        except Exception as e:
            log('error', f"SONGBIRD _play_playlist_sound error: {str(e)}")
            return f"SONGBIRD: Error playing playlist sound - {str(e)}"
    
    def _check_playlist_events(self):
        """Check for pygame events (playlist auto-advance)"""
        try:
            for event in pygame.event.get():
                if event.type == self.PLAYLIST_END_EVENT:
                    if self.playlist_mode:
                        log('info', 'SONGBIRD: Playlist sound ended, auto-advancing')
                        self.playlist_next()
        except Exception as e:
            log('error', f"SONGBIRD _check_playlist_events error: {str(e)}")
    
    def check_and_advance_playlist(self) -> bool:
        """
        Check if current song ended and auto-advance to next.
        Call this before returning control to user in any action.
        Thread-safe: Can be called from background monitor or user commands.
        
        Returns:
            True if advanced, False if no action taken
        """
        # Thread safety: lock to prevent race conditions
        with self.playlist_lock:
            try:
                # Only check if playlist is active
                if not self.playlist_mode or not self.playlist_queue:
                    return False
                
                # Check if music stopped playing
                if not pygame.mixer.music.get_busy():
                    log('info', 'SONGBIRD: Song ended, auto-advancing playlist')
                    
                    # Move to next song
                    self.playlist_index += 1
                    
                    # Check if we reached the end
                    if self.playlist_index >= len(self.playlist_queue):
                        if self.playlist_loop:
                            # Loop back to start
                            self.playlist_index = 0
                            log('info', 'SONGBIRD: Playlist looping back to start')
                            self._play_playlist_sound()
                            return True
                        else:
                            # End of playlist
                            self.playlist_mode = False
                            log('info', 'SONGBIRD: Playlist ended')
                            return False
                    
                    # Play next sound
                    self._play_playlist_sound()
                    return True
                
                return False
                
            except Exception as e:
                log('error', f"SONGBIRD check_and_advance_playlist error: {str(e)}")
                return False
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into MM:SS or HH:MM:SS"""
        try:
            total_seconds = int(seconds)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            secs = total_seconds % 60
            
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes}:{secs:02d}"
        except:
            return "0:00"
    
    def songbird_play_playlist(self, args, projected_states) -> str:
        """Play all sounds in a folder as a playlist"""
        try:
            folder_name = args.get('folder_name', '').strip()
            shuffle = args.get('shuffle', False)
            loop = args.get('loop', True)  # Loop enabled by default
            
            if not folder_name:
                return "SONGBIRD: Please specify a folder name"
            
            log('info', f"SONGBIRD: Play playlist request for folder: '{folder_name}'")
            
            # Build folder path
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            playlist_folder = os.path.join(sounds_folder, folder_name)
            
            if not os.path.exists(playlist_folder):
                return f"SONGBIRD: Folder '{folder_name}' not found in sounds directory"
            
            if not os.path.isdir(playlist_folder):
                return f"SONGBIRD: '{folder_name}' is not a folder"
            
            # Get all audio files in folder
            supported_extensions = ['.mp3', '.ogg', '.wav']
            audio_files = []
            
            for filename in os.listdir(playlist_folder):
                if any(filename.lower().endswith(ext) for ext in supported_extensions):
                    filepath = os.path.join(playlist_folder, filename)
                    audio_files.append(filepath)
            
            if not audio_files:
                return f"SONGBIRD: No audio files found in folder '{folder_name}'"
            
            # Sort alphabetically by default
            audio_files.sort()
            
            # Shuffle if requested
            if shuffle:
                random.shuffle(audio_files)
                log('info', f'SONGBIRD: Shuffled playlist with {len(audio_files)} sounds')
            
            # Setup playlist state
            self.playlist_mode = True
            self.playlist_queue = audio_files
            self.playlist_index = 0
            self.playlist_name = folder_name
            self.playlist_loop = loop
            self.playlist_shuffle = shuffle
            
            # Start playing first sound
            result = self._play_playlist_sound()
            
            shuffle_text = "shuffled " if shuffle else ""
            loop_text = " (looping enabled)" if loop else " (say 'loop on' to repeat playlist)"
            
            log('info', f'SONGBIRD: Started playlist "{folder_name}" with {len(audio_files)} sounds')
            return f"SONGBIRD: Started {shuffle_text}playlist '{folder_name}' with {len(audio_files)} sounds{loop_text}. {result}"
            
        except Exception as e:
            log('error', f"SONGBIRD play_playlist error: {str(e)}")
            return f"SONGBIRD: Error starting playlist - {str(e)}"
    
    def songbird_playlist_info(self, args, projected_states) -> str:
        """Get information about current playlist"""
        try:
            # Check if song ended and auto-advance
            if self.check_and_advance_playlist():
                # Song auto-advanced, get new info
                pass
            
            if not self.playlist_mode:
                return "SONGBIRD: No playlist currently active"
            
            if not self.playlist_queue:
                return "SONGBIRD: Playlist is empty"
            
            # Get current song info
            current_filepath = self.playlist_queue[self.playlist_index]
            current_filename = os.path.basename(current_filepath)
            
            # Clean up display name
            name_without_ext = os.path.splitext(current_filename)[0]
            name_parts = name_without_ext.rsplit('_', 1)
            if len(name_parts) == 2 and name_parts[1].isdigit():
                display_name = name_parts[0].replace('_', ' ')
            else:
                display_name = name_without_ext.replace('_', ' ')
            
            position = self.playlist_index + 1
            total = len(self.playlist_queue)
            
            # Get playback position and duration
            try:
                # Get current position (in milliseconds)
                current_pos_ms = pygame.mixer.music.get_pos()
                
                # Get track length using pygame.mixer.Sound (for duration)
                # Note: mixer.music doesn't provide duration, so we estimate or use Sound
                try:
                    sound_obj = pygame.mixer.Sound(current_filepath)
                    duration_seconds = sound_obj.get_length()
                    current_seconds = current_pos_ms / 1000.0
                    
                    # Format timestamps
                    current_time = self._format_time(current_seconds)
                    total_time = self._format_time(duration_seconds)
                    timestamp = f" [{current_time} / {total_time}]"
                except:
                    # Fallback if Sound loading fails
                    current_seconds = current_pos_ms / 1000.0
                    current_time = self._format_time(current_seconds)
                    timestamp = f" [{current_time}]"
            except:
                timestamp = ""
            
            # Build status string
            status_parts = []
            if self.playlist_shuffle:
                status_parts.append("shuffle ON")
            if self.playlist_loop:
                status_parts.append("loop ON")
            
            status_text = f" ({', '.join(status_parts)})" if status_parts else ""
            
            result = f"SONGBIRD: Playlist '{self.playlist_name}' - Playing {position}/{total}: '{display_name}'{timestamp}{status_text}"
            
            log('info', 'SONGBIRD: Playlist info requested')
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD playlist_info error: {str(e)}")
            return f"SONGBIRD: Error getting playlist info - {str(e)}"
    
    def songbird_list_playlists(self, args, projected_states) -> str:
        """List all available playlists (folders with audio files)"""
        try:
            log('info', 'SONGBIRD: Listing available playlists')
            
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            
            if not os.path.exists(sounds_folder):
                return "SONGBIRD: Sounds folder not found"
            
            # Find folders containing audio files
            supported_extensions = ['.mp3', '.ogg', '.wav']
            playlists = []
            
            for item in os.listdir(sounds_folder):
                item_path = os.path.join(sounds_folder, item)
                
                # Only check directories
                if os.path.isdir(item_path):
                    # Count audio files in folder
                    audio_count = 0
                    for filename in os.listdir(item_path):
                        if any(filename.lower().endswith(ext) for ext in supported_extensions):
                            audio_count += 1
                    
                    if audio_count > 0:
                        playlists.append((item, audio_count))
            
            if not playlists:
                return "SONGBIRD: No playlists found. Create a folder inside sounds/ and add audio files to it."
            
            # Sort by folder name
            playlists.sort()
            
            # Build result string
            playlist_list = []
            for folder_name, count in playlists:
                playlist_list.append(f"- '{folder_name}' ({count} sounds)")
            
            result = f"SONGBIRD: Found {len(playlists)} playlists:\n" + "\n".join(playlist_list)
            
            log('info', f'SONGBIRD: Listed {len(playlists)} playlists')
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD list_playlists error: {str(e)}")
            return f"SONGBIRD: Error listing playlists - {str(e)}"
    
    def songbird_playlist_contents(self, args, projected_states) -> str:
        """
        Show contents of a playlist without playing it.
        Lists all tracks in the specified playlist folder.
        """
        try:
            folder_name = args.get('folder_name', '').strip()
            
            if not folder_name:
                return "SONGBIRD: Please specify which playlist to inspect."
            
            log('info', f'SONGBIRD: Requesting contents of playlist: {folder_name}')
            
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            playlist_path = os.path.join(sounds_folder, folder_name)
            
            # Check if folder exists
            if not os.path.exists(playlist_path):
                return f"SONGBIRD: Playlist '{folder_name}' not found. Say 'list playlists' to see available playlists."
            
            if not os.path.isdir(playlist_path):
                return f"SONGBIRD: '{folder_name}' is not a playlist folder."
            
            # Get all audio files
            supported_extensions = ['.mp3', '.ogg', '.wav']
            tracks = []
            
            for filename in os.listdir(playlist_path):
                if any(filename.lower().endswith(ext) for ext in supported_extensions):
                    # Remove extension and make readable
                    name_without_ext = os.path.splitext(filename)[0]
                    readable_name = name_without_ext.replace('_', ' ').replace('-', ' ')
                    
                    # Get file size (optional info)
                    filepath = os.path.join(playlist_path, filename)
                    try:
                        file_size = os.path.getsize(filepath)
                        size_mb = file_size / (1024 * 1024)
                        size_info = f" ({size_mb:.1f}MB)" if size_mb >= 0.1 else ""
                    except:
                        size_info = ""
                    
                    tracks.append({
                        'filename': filename,
                        'readable_name': readable_name,
                        'size_info': size_info
                    })
            
            if not tracks:
                return f"SONGBIRD: Playlist '{folder_name}' is empty (no audio files found)."
            
            # Sort tracks by filename
            tracks.sort(key=lambda x: x['filename'].lower())
            
            # Build result
            track_list = []
            for i, track in enumerate(tracks, 1):
                track_list.append(f"{i}. {track['readable_name']}{track['size_info']}")
            
            result = f"SONGBIRD: Playlist '{folder_name}' contains {len(tracks)} tracks:\n" + "\n".join(track_list)
            
            log('info', f'SONGBIRD: Listed {len(tracks)} tracks in playlist {folder_name}')
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD playlist_contents error: {str(e)}")
            return f"SONGBIRD: Error getting playlist contents - {str(e)}"

    def is_specific_sound_request(self, sound_description: str) -> bool:
        """
        Determine if request is for a specific file vs generic sound.
        
        Specific: "explosion 3", "cicadas thunder 2", "login 1"
        Generic: "explosion sound", "thunder", "login"
        
        Args:
            sound_description: User's sound description
            
        Returns:
            True if specific filename request, False if generic sound type
        """
        description_lower = sound_description.lower().strip()
        
        # Has a number? Likely specific ("explosion 3")
        if any(char.isdigit() for char in description_lower):
            return True
        
        # Check if it matches an actual filename in cache
        sound_files = self.get_local_sounds()
        if sound_files:
            for sound in sound_files:
                sound_normalized = sound['readable_name'].lower().replace('-', ' ').replace('_', ' ')
                desc_normalized = description_lower.replace('-', ' ').replace('_', ' ')
                
                # Exact or very close match to cached filename
                if sound_normalized == desc_normalized or desc_normalized in sound_normalized:
                    return True
        
        # Generic request
        return False
    
    def should_use_freesound(self, sound_description: str, replay_mode: str = "auto") -> bool:
        """
        Determine whether to use Freesound or check local cache.
        
        Logic:
        - replay_mode "again" → Local cache
        - replay_mode "new" → Freesound
        - Keywords "another"/"different"/"new" → Freesound (FORCE)
        - Specific filename ("explosion 3") → Local cache
        - Generic description ("explosion sound") → Freesound
        
        Args:
            sound_description: User's sound description
            replay_mode: Explicit mode from action
            
        Returns:
            True = Use Freesound, False = Check local cache first
        """
        # If explicit replay mode specified
        if replay_mode == "again":
            return False  # Check cache first
        elif replay_mode == "new":
            return True   # Always use Freesound
        
        # Auto-detect from description
        description_lower = sound_description.lower()
        
        # Words that indicate wanting a new/different sound (PRIORITY)
        freesound_keywords = [
            'another', 'different', 'new', 'fresh', 'other'
        ]
        
        # Check for explicit indicators FIRST
        for keyword in freesound_keywords:
            if keyword in description_lower:
                log('info', f"SONGBIRD: Detected Freesound keyword '{keyword}' - FORCING Freesound search")
                return True
        
        # Words that indicate replay request
        replay_keywords = [
            'again', 'same', 'repeat', 'replay', 'once more', 'it'
        ]
        
        for keyword in replay_keywords:
            if keyword in description_lower:
                log('info', f"SONGBIRD: Detected replay keyword '{keyword}'")
                return False
        
        # Check if specific file request vs generic
        if self.is_specific_sound_request(sound_description):
            log('info', f"SONGBIRD: Detected specific file request - checking local cache")
            return False
        
        # Default: Generic descriptions go to Freesound for variety
        log('info', f"SONGBIRD: Generic sound request - using Freesound")
        return True

    def get_local_sounds(self) -> list:
        """Get list of locally cached sound files"""
        try:
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            
            if not os.path.exists(sounds_folder):
                return []
            
            sound_files = []
            supported_extensions = ['.mp3', '.ogg', '.wav']
            
            for filename in os.listdir(sounds_folder):
                if any(filename.lower().endswith(ext) for ext in supported_extensions):
                    filepath = os.path.join(sounds_folder, filename)
                    # Remove extension first
                    name_without_ext = os.path.splitext(filename)[0]
                    
                    # Check if this is a Freesound file (ends with underscore + numbers)
                    name_parts = name_without_ext.rsplit('_', 1)
                    if len(name_parts) == 2 and name_parts[1].isdigit():
                        # Freesound format: soundname_12345
                        readable_name = name_parts[0].replace('_', ' ')
                    else:
                        # User file: use full filename without extension
                        readable_name = name_without_ext.replace('_', ' ')
                    
                    sound_files.append({
                        'filename': filename,
                        'filepath': filepath,
                        'readable_name': readable_name
                    })
            
            return sound_files
            
        except Exception as e:
            log('error', f"SONGBIRD: Error getting local sounds: {str(e)}")
            return []

    def find_local_sound(self, search_term: str):
        """
        Find a local sound file that matches the search term.
        
        Priority matching order:
        1. EXACT filename match (with/without extension)
        2. Exact readable name match
        3. Word-based matching
        4. Partial matching
        
        Args:
            search_term: User's search description
            
        Returns:
            Sound info dict or None if not found
        """
        try:
            sound_files = self.get_local_sounds()
            
            if not sound_files:
                return None
            
            search_lower = search_term.lower().strip()
            
            # Handle "it again" or replay requests using last played description
            if ('it' in search_lower or 'again' in search_lower) and self.last_played_description:
                search_lower = self.last_played_description.lower()
                log('info', f"SONGBIRD: Using last played description '{self.last_played_description}' for replay")
            
            # Convert word numbers to digits (e.g., "wrong one" becomes "wrong 1")
            search_with_digits = self.convert_word_numbers_to_digits(search_lower)
            
            log('info', f"SONGBIRD: Searching for '{search_lower}' among {len(sound_files)} local sounds")
            
            # PRIORITY 1: Try EXACT filename match (with or without extension)
            # This handles cases like "explosion01wav" or "explosion01.wav"
            for sound in sound_files:
                filename_lower = sound['filename'].lower()
                filename_no_ext = os.path.splitext(filename_lower)[0]
                
                # Remove dots, spaces, hyphens for comparison
                search_clean = search_with_digits.replace('.', '').replace(' ', '').replace('-', '').replace('_', '')
                filename_clean = filename_no_ext.replace('.', '').replace(' ', '').replace('-', '').replace('_', '')
                
                # Exact match on cleaned filename
                if search_clean == filename_clean:
                    log('info', f"SONGBIRD: EXACT filename match: {sound['filename']}")
                    return sound
                
                # Also try with extension in search
                if search_clean == filename_lower.replace('.', '').replace(' ', '').replace('-', '').replace('_', ''):
                    log('info', f"SONGBIRD: EXACT filename match (with ext): {sound['filename']}")
                    return sound
            
            # PRIORITY 2: Normalize and try exact readable name match
            search_normalized = search_with_digits.replace('-', ' ').replace('_', ' ')
            search_words = set(search_normalized.split())
            
            for sound in sound_files:
                sound_normalized = sound['readable_name'].lower().replace('-', ' ').replace('_', ' ')
                if search_normalized == sound_normalized:
                    log('info', f"SONGBIRD: Exact readable name match: {sound['readable_name']}")
                    return sound
            
            # PRIORITY 3: Word-based matching (all search words present)
            for sound in sound_files:
                sound_normalized = sound['readable_name'].lower().replace('-', ' ').replace('_', ' ')
                sound_words = set(sound_normalized.split())
                if search_words.issubset(sound_words):
                    log('info', f"SONGBIRD: Word match found: {sound['readable_name']}")
                    return sound
            
            # PRIORITY 4: Partial matching (any search word matches)
            # Only use this for generic searches, not filename-like searches
            if not any(char.isdigit() for char in search_lower):
                for sound in sound_files:
                    sound_normalized = sound['readable_name'].lower().replace('-', ' ').replace('_', ' ')
                    if any(word in sound_normalized for word in search_words):
                        log('info', f"SONGBIRD: Partial match found: {sound['readable_name']}")
                        return sound
            
            log('info', f"SONGBIRD: No local sound found matching '{search_lower}'")
            return None
                
        except Exception as e:
            log('error', f"SONGBIRD: Error finding local sound: {str(e)}")
            return None

    def play_local_sound(self, sound_info: dict) -> str:
        """Play a local sound file using pygame"""
        try:
            filepath = sound_info['filepath']
            readable_name = sound_info['readable_name']
            
            if not os.path.exists(filepath):
                return f"Sound file not found: {readable_name}"
            
            # Play the sound using pygame
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            log('info', f"SONGBIRD: Playing local sound: {readable_name}")
            return f"Playing cached sound: '{readable_name}'"
            
        except Exception as e:
            log('error', f"SONGBIRD: Error playing local sound: {str(e)}")
            return f"Error playing local sound: {str(e)}"

    def songbird_play_sound(self, args, projected_states) -> str:
        """Play sound using hybrid approach: cache for replay, Freesound for new sounds"""
        try:
            # Check if playlist song ended and auto-advance
            self.check_and_advance_playlist()
            
            sound_description = args.get('sound_description', '')
            replay_mode = args.get('replay_mode', 'auto')
            context = args.get('context', '')
            
            log('info', f"SONGBIRD: Request for '{sound_description}' (mode: {replay_mode})")
            
            if not sound_description:
                return "SONGBIRD: No sound description provided."
            
            # Determine whether to check cache or use Freesound
            use_freesound = self.should_use_freesound(sound_description, replay_mode)
            
            if not use_freesound:
                # Try to find in local cache first
                local_match = self.find_local_sound(sound_description)
                
                if local_match is not None:
                    # Found in cache, play it
                    log('info', f"SONGBIRD: Playing from cache: {local_match['readable_name']}")
                    play_result = self.play_local_sound(local_match)
                    
                    # Update current playing for binding
                    self.current_playing = {
                        'sound_name': local_match['readable_name'],
                        'filepath': local_match['filepath'],
                        'description_used': sound_description,
                        'username': 'Local Cache'
                    }
                    
                    return f"SONGBIRD: {play_result}"
                else:
                    log('info', f"SONGBIRD: No cached sound found, falling back to Freesound")
            else:
                log('info', f"SONGBIRD: Using Freesound for new/different sound")
            
            # No cached match found OR user wants new sound - search Freesound
            if not self.api_key:
                return "SONGBIRD: No API key configured. Please add your Freesound API key in the Settings menu."
            
            # Get varied results from multiple pages (uses cached searches)
            all_results = self.get_varied_freesound_results(sound_description)
            
            if not all_results or (len(all_results) == 1 and "error" in all_results[0]):
                if all_results and "error" in all_results[0]:
                    error = all_results[0]["error"]
                    if error == "Invalid API key":
                        return "SONGBIRD: Invalid Freesound API key. Please check your Settings."
                    return f"SONGBIRD: Search failed - {error}"
                return f"SONGBIRD: No sounds found for '{sound_description}'. Try a different description."
            
            # Always use random selection for variety
            selected_sound = self.select_random_sound(all_results)
            
            if "error" in selected_sound:
                return f"SONGBIRD: Error selecting sound - {selected_sound['error']}"
            
            sound_name = selected_sound.get('name', 'Unknown')
            username = selected_sound.get('username', 'Unknown')
            
            # Download and play the sound
            play_result = self.download_and_play_sound(selected_sound)
            
            # Build filepath for tracking
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            sound_id = selected_sound.get('id', 'unknown')
            safe_name = "".join(c for c in sound_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            # Determine file extension
            previews = selected_sound.get('previews', {})
            file_extension = '.mp3'
            if 'preview-hq-mp3' in previews or 'preview-lq-mp3' in previews:
                file_extension = '.mp3'
            elif 'preview-hq-ogg' in previews or 'preview-lq-ogg' in previews:
                file_extension = '.ogg'
            
            filename = f"{safe_name}_{sound_id}{file_extension}"
            filepath = os.path.join(sounds_folder, filename)
            
            # Track current playing sound for binding system
            self.current_playing = {
                'sound_data': selected_sound,
                'sound_name': sound_name,
                'username': username,
                'description_used': sound_description,
                'filepath': filepath
            }
            
            # Track last played for replay functionality
            self.last_played_description = sound_description
            
            log('info', f"SONGBIRD: Set current playing sound: {sound_name}")
            
            return f"SONGBIRD: Found '{sound_name}' by {username}. {play_result}"
            
        except Exception as e:
            log('error', f"SONGBIRD error: {str(e)}")
            return f"SONGBIRD: Error - {str(e)}"

    def songbird_test(self, args, projected_states) -> str:
        try:
            log('info', 'SONGBIRD: Running test')
            
            version = self.plugin_manifest.version
            name = self.plugin_manifest.name
            
            # Check if API key is loaded
            if self.api_key:
                result = f"SONGBIRD Test: {name} v{version} - Active with Freesound API integration. API key loaded from Settings UI."
            else:
                result = f"SONGBIRD Test: {name} v{version} - Active but no API key configured. Please add your Freesound API key in Settings."
            
            log('info', 'SONGBIRD: Test completed')
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD test error: {str(e)}")
            return f"SONGBIRD: Test failed - {str(e)}"
    
    def songbird_cache_stats(self, args, projected_states) -> str:
        """Show cache performance statistics"""
        try:
            stats = self.reliability_client.get_stats()
            
            result = "SONGBIRD Cache Statistics:\n"
            result += f"• Cache Hit Rate: {stats['cache_hit_rate']}\n"
            result += f"• Total Requests: {stats['total_requests']}\n"
            result += f"• Cache Hits: {stats['cache_hits']}\n"
            result += f"• Cache Misses: {stats['cache_misses']}\n"
            result += f"• In-flight Hits: {stats['inflight_hits']}\n"
            result += f"• API Calls: {stats['api_calls']}\n"
            result += f"• API Calls Saved: {stats['api_calls_saved']}\n"
            result += f"• Errors: {stats['errors']}"
            
            log('info', f"SONGBIRD: Cache stats - {stats['cache_hit_rate']} hit rate, {stats['api_calls_saved']} API calls saved")
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD cache stats error: {str(e)}")
            return f"SONGBIRD: Error getting cache stats - {str(e)}"
    
    def songbird_delete_sound(self, args, projected_states) -> str:
        """
        Delete a specific sound file from local cache by name.
        
        Args:
            sound_name: Name or pattern of sound to delete
            
        Returns:
            Success or error message
        """
        try:
            sound_name = args.get('sound_name', '').strip()
            
            if not sound_name:
                return "SONGBIRD: Please specify which sound to delete."
            
            log('info', f"SONGBIRD: Delete request for '{sound_name}'")
            
            # Find the sound
            local_match = self.find_local_sound(sound_name)
            
            if local_match is None:
                return f"SONGBIRD: Sound '{sound_name}' not found in cache. Say 'List cached sounds' to see available files."
            
            filepath = local_match['filepath']
            readable_name = local_match['readable_name']
            
            # Delete the file
            if os.path.exists(filepath):
                os.remove(filepath)
                log('info', f"SONGBIRD: Deleted sound file: {readable_name}")
                return f"SONGBIRD: Deleted '{readable_name}' from cache."
            else:
                return f"SONGBIRD: File not found: {readable_name}"
                
        except Exception as e:
            log('error', f"SONGBIRD: Error deleting sound: {str(e)}")
            return f"SONGBIRD: Error deleting sound - {str(e)}"
    
    def songbird_delete_current(self, args, projected_states) -> str:
        """
        Delete the currently playing sound from cache.
        
        Returns:
            Success or error message
        """
        try:
            if not self.current_playing:
                return "SONGBIRD: No sound is currently playing to delete."
            
            sound_name = self.current_playing.get('sound_name')
            filepath = self.current_playing.get('filepath')
            
            if not filepath or not os.path.exists(filepath):
                return "SONGBIRD: Current sound file not found."
            
            log('info', f"SONGBIRD: Deleting current sound: {sound_name}")
            
            # Delete the file
            os.remove(filepath)
            
            # Clear current playing
            self.current_playing = None
            
            log('info', f"SONGBIRD: Deleted: {sound_name}")
            return f"SONGBIRD: Deleted '{sound_name}' from cache."
            
        except Exception as e:
            log('error', f"SONGBIRD: Error deleting current sound: {str(e)}")
            return f"SONGBIRD: Error deleting sound - {str(e)}"
    
    def songbird_clear_sounds(self, args, projected_states) -> str:
        """
        Delete all sound files matching a pattern.
        
        Args:
            pattern: Pattern to match in filenames
            
        Returns:
            Success message with count of deleted files
        """
        try:
            pattern = args.get('pattern', '').strip().lower()
            
            if not pattern:
                return "SONGBIRD: Please specify a pattern (e.g., 'explosion', 'thunder')."
            
            log('info', f"SONGBIRD: Clear request for pattern '{pattern}'")
            
            # Get all sounds
            all_sounds = self.get_local_sounds()
            
            if not all_sounds:
                return "SONGBIRD: No sounds in cache to delete."
            
            # Find matching sounds
            matches = []
            for sound in all_sounds:
                sound_normalized = sound['readable_name'].lower()
                filename_normalized = sound['filename'].lower()
                
                if pattern in sound_normalized or pattern in filename_normalized:
                    matches.append(sound)
            
            if not matches:
                return f"SONGBIRD: No sounds found matching '{pattern}'. Say 'List cached sounds' to see available files."
            
            # Delete all matches
            deleted_count = 0
            for sound in matches:
                try:
                    if os.path.exists(sound['filepath']):
                        os.remove(sound['filepath'])
                        deleted_count += 1
                        log('info', f"SONGBIRD: Deleted: {sound['readable_name']}")
                except Exception as e:
                    log('error', f"SONGBIRD: Failed to delete {sound['readable_name']}: {str(e)}")
            
            log('info', f"SONGBIRD: Cleared {deleted_count} sound(s) matching '{pattern}'")
            return f"SONGBIRD: Deleted {deleted_count} sound(s) matching '{pattern}'."
            
        except Exception as e:
            log('error', f"SONGBIRD: Error clearing sounds: {str(e)}")
            return f"SONGBIRD: Error clearing sounds - {str(e)}"
    
    def songbird_clean_cache(self, args, projected_states) -> str:
        """
        Delete ALL downloaded sound files from cache.
        
        WARNING: This removes all cached audio files.
        
        Returns:
            Success message with count of deleted files
        """
        try:
            log('info', 'SONGBIRD: Clean cache request - deleting ALL sounds')
            
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            
            if not os.path.exists(sounds_folder):
                return "SONGBIRD: Cache is already empty (sounds folder doesn't exist)."
            
            # Get all sound files
            deleted_count = 0
            for filename in os.listdir(sounds_folder):
                filepath = os.path.join(sounds_folder, filename)
                
                # Only delete audio files (safety check)
                if filename.lower().endswith(('.mp3', '.ogg', '.wav')):
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                    except Exception as e:
                        log('error', f"SONGBIRD: Failed to delete {filename}: {str(e)}")
            
            # Clear current playing
            self.current_playing = None
            
            log('info', f"SONGBIRD: Cache cleaned - deleted {deleted_count} file(s)")
            return f"SONGBIRD: Cache cleaned. Deleted {deleted_count} sound file(s)."
            
        except Exception as e:
            log('error', f"SONGBIRD: Error cleaning cache: {str(e)}")
            return f"SONGBIRD: Error cleaning cache - {str(e)}"

    def get_bound_sounds_file(self) -> str:
        """Get path to bound sounds configuration file"""
        plugin_folder = self.get_plugin_folder_path()
        return os.path.join(plugin_folder, 'bound_sounds.json')

    def load_bound_sounds(self) -> dict:
        """Load bound sounds from configuration file"""
        try:
            bound_file = self.get_bound_sounds_file()
            if os.path.exists(bound_file):
                with open(bound_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            log('error', f"SONGBIRD: Error loading bound sounds: {str(e)}")
            return {}

    def save_bound_sounds(self, bound_sounds: dict) -> bool:
        """Save bound sounds to configuration file"""
        try:
            bound_file = self.get_bound_sounds_file()
            with open(bound_file, 'w', encoding='utf-8') as f:
                json.dump(bound_sounds, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            log('error', f"SONGBIRD: Error saving bound sounds: {str(e)}")
            return False

    def songbird_bind_sound(self, args, projected_states) -> str:
        """Bind the last played sound to a command phrase - supports multiple sounds per phrase"""
        try:
            bind_phrase = args.get('bind_phrase', '').strip()
            
            # Normalize phrase (lowercase + strip punctuation)
            normalized_phrase = self.normalize_phrase(bind_phrase)
            
            if not normalized_phrase:
                return "SONGBIRD: Please specify a phrase to bind the sound to."
            
            log('info', f"SONGBIRD: Binding request for phrase: '{bind_phrase}' (normalized: '{normalized_phrase}')")
            
            if not self.current_playing:
                return "SONGBIRD: No sound has been played yet to bind. Play a sound first, then bind it."
            
            sound_name = self.current_playing.get('sound_name')
            filepath = self.current_playing.get('filepath')
            
            if not sound_name or not filepath:
                return "SONGBIRD: Current sound information incomplete. Try playing a sound again."
            
            if not os.path.exists(filepath):
                return f"SONGBIRD: Sound file not found. Try playing the sound again."
            
            # Load existing bound sounds
            bound_sounds = self.load_bound_sounds()
            
            # Check if phrase already exists
            if normalized_phrase in bound_sounds:
                # Phrase exists - check if it's a list or single sound
                existing_binding = bound_sounds[normalized_phrase]
                
                # Convert old single-sound format to list format
                if not isinstance(existing_binding, list):
                    bound_sounds[normalized_phrase] = [existing_binding]
                
                # Add new sound to the list
                new_sound_entry = {
                    'sound_name': sound_name,
                    'filepath': filepath,
                    'description_used': self.current_playing.get('description_used', ''),
                    'username': self.current_playing.get('username', 'Unknown')
                }
                
                # Check if this exact sound is already in the list
                already_exists = False
                for sound_entry in bound_sounds[normalized_phrase]:
                    if sound_entry['filepath'] == filepath:
                        already_exists = True
                        break
                
                if already_exists:
                    return f"SONGBIRD: '{sound_name}' is already bound to phrase '{bind_phrase}'"
                
                bound_sounds[normalized_phrase].append(new_sound_entry)
                
                # Save bound sounds
                if self.save_bound_sounds(bound_sounds):
                    count = len(bound_sounds[normalized_phrase])
                    log('info', f"SONGBIRD: Added '{sound_name}' to phrase '{normalized_phrase}' (now {count} sounds)")
                    return f"SONGBIRD: Added '{sound_name}' to phrase '{bind_phrase}' (now {count} sounds total)"
                else:
                    return "SONGBIRD: Error saving bound sound"
            else:
                # New phrase - create as a list with one sound
                bound_sounds[normalized_phrase] = [{
                    'sound_name': sound_name,
                    'filepath': filepath,
                    'description_used': self.current_playing.get('description_used', ''),
                    'username': self.current_playing.get('username', 'Unknown')
                }]
                
                # Save bound sounds
                if self.save_bound_sounds(bound_sounds):
                    log('info', f"SONGBIRD: Bound '{sound_name}' to phrase '{normalized_phrase}'")
                    return f"SONGBIRD: Bound '{sound_name}' to phrase '{bind_phrase}'"
                else:
                    return "SONGBIRD: Error saving bound sound"
            
        except Exception as e:
            log('error', f"SONGBIRD bind error: {str(e)}")
            return f"SONGBIRD: Bind error - {str(e)}"

    def songbird_bind_multiple(self, args, projected_states) -> str:
        """Bind multiple sounds to a phrase in one command"""
        try:
            sound_names = args.get('sound_names', [])
            bind_phrase = args.get('bind_phrase', '').strip()
            
            # Normalize phrase
            normalized_phrase = self.normalize_phrase(bind_phrase)
            
            if not normalized_phrase:
                return "SONGBIRD: Please specify a phrase to bind the sounds to."
            
            if not sound_names or len(sound_names) == 0:
                return "SONGBIRD: Please specify at least one sound name to bind."
            
            log('info', f"SONGBIRD: Multiple bind request for {len(sound_names)} sounds to phrase '{bind_phrase}'")
            
            # Get all cached sounds
            all_sounds = self.get_local_sounds()
            
            if not all_sounds:
                return "SONGBIRD: No cached sounds available to bind."
            
            # Find matching sounds
            found_sounds = []
            not_found = []
            
            for sound_name in sound_names:
                # Try to find this sound
                found = False
                search_normalized = sound_name.lower().replace('-', ' ').replace('_', ' ')
                search_words = set(search_normalized.split())
                
                for sound in all_sounds:
                    sound_normalized = sound['readable_name'].lower().replace('-', ' ').replace('_', ' ')
                    sound_words = set(sound_normalized.split())
                    
                    # Check for match using word-based matching (more accurate)
                    # Match if: exact match OR all search words are present in sound name
                    if (search_normalized == sound_normalized or 
                        search_words.issubset(sound_words)):
                        found_sounds.append(sound)
                        found = True
                        log('info', f"SONGBIRD: Found match for '{sound_name}': {sound['readable_name']}")
                        break
                
                if not found:
                    not_found.append(sound_name)
                    log('info', f"SONGBIRD: No match found for '{sound_name}'")
            
            if len(found_sounds) == 0:
                return f"SONGBIRD: None of the specified sounds were found in cache. Not found: {', '.join(not_found)}"
            
            # Load existing bound sounds
            bound_sounds = self.load_bound_sounds()
            
            # Initialize or convert existing binding to list format
            if normalized_phrase in bound_sounds:
                existing = bound_sounds[normalized_phrase]
                if not isinstance(existing, list):
                    bound_sounds[normalized_phrase] = [existing]
            else:
                bound_sounds[normalized_phrase] = []
            
            # Add all found sounds
            added_count = 0
            skipped_count = 0
            
            for sound in found_sounds:
                # Check if already in the list
                already_exists = False
                for existing_sound in bound_sounds[normalized_phrase]:
                    if existing_sound['filepath'] == sound['filepath']:
                        already_exists = True
                        break
                
                if not already_exists:
                    bound_sounds[normalized_phrase].append({
                        'sound_name': sound['readable_name'],
                        'filepath': sound['filepath'],
                        'description_used': '',
                        'username': 'Local Cache'
                    })
                    added_count += 1
                else:
                    skipped_count += 1
            
            # Save bound sounds
            if self.save_bound_sounds(bound_sounds):
                total = len(bound_sounds[normalized_phrase])
                result_parts = [f"SONGBIRD: Bound {added_count} sound(s) to phrase '{bind_phrase}' (total: {total})"]
                
                if skipped_count > 0:
                    result_parts.append(f"Skipped {skipped_count} duplicate(s)")
                
                if len(not_found) > 0:
                    result_parts.append(f"Not found: {', '.join(not_found)}")
                
                log('info', f"SONGBIRD: Successfully bound {added_count} sounds to '{normalized_phrase}'")
                return ". ".join(result_parts)
            else:
                return "SONGBIRD: Error saving bound sounds"
            
        except Exception as e:
            log('error', f"SONGBIRD bind multiple error: {str(e)}")
            return f"SONGBIRD: Bind multiple error - {str(e)}"

    def songbird_replay_bound(self, args, projected_states) -> str:
        """Replay a sound bound to a specific phrase - randomly selects if multiple sounds"""
        try:
            phrase = args.get('phrase', '').strip()
            
            # Normalize phrase for matching
            normalized_phrase = self.normalize_phrase(phrase)
            
            if not normalized_phrase:
                return "SONGBIRD: Please specify the bound phrase."
            
            log('info', f"SONGBIRD: Replay bound sound for phrase: '{phrase}' (normalized: '{normalized_phrase}')")
            
            # Load bound sounds
            bound_sounds = self.load_bound_sounds()
            
            # Check if phrase exists
            if normalized_phrase not in bound_sounds:
                return f"SONGBIRD: No sound bound to phrase '{phrase}'. Use 'list bound sounds' to see available phrases."
            
            bound_data = bound_sounds[normalized_phrase]
            
            # Handle both old single-sound format and new list format
            if isinstance(bound_data, list):
                # Multiple sounds - randomly select one
                selected = random.choice(bound_data)
                filepath = selected['filepath']
                sound_name = selected['sound_name']
                log('info', f"SONGBIRD: Randomly selected '{sound_name}' from {len(bound_data)} sounds for phrase '{normalized_phrase}'")
            else:
                # Old format - single sound (backwards compatibility)
                filepath = bound_data['filepath']
                sound_name = bound_data['sound_name']
            
            # Check if file still exists
            if not os.path.exists(filepath):
                return f"SONGBIRD: Bound sound file not found: {sound_name}"
            
            # Play the bound sound
            try:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                
                log('info', f"SONGBIRD: Playing bound sound: {sound_name}")
                return f"SONGBIRD: Playing bound sound '{sound_name}'"
                
            except Exception as play_error:
                log('error', f"SONGBIRD: Error playing bound sound: {str(play_error)}")
                return f"SONGBIRD: Error playing bound sound: {str(play_error)}"
            
        except Exception as e:
            log('error', f"SONGBIRD replay bound error: {str(e)}")
            return f"SONGBIRD: Replay bound error - {str(e)}"

    def songbird_list_bound(self, args, projected_states) -> str:
        """List all bound sound phrases with sound counts"""
        try:
            log('info', 'SONGBIRD: Listing bound sounds')
            
            bound_sounds = self.load_bound_sounds()
            
            if not bound_sounds:
                return "SONGBIRD: No sounds bound to phrases yet. Use 'bind this to [phrase]' to create bindings."
            
            bound_list = []
            for phrase, data in bound_sounds.items():
                # Handle both list format (new) and single sound format (old)
                if isinstance(data, list):
                    sound_count = len(data)
                    if sound_count == 1:
                        sound_name = data[0]['sound_name']
                        bound_list.append(f"- '{phrase}' -> {sound_name}")
                    else:
                        sound_names = [s['sound_name'] for s in data]
                        bound_list.append(f"- '{phrase}' -> {sound_count} sounds: {', '.join(sound_names)}")
                else:
                    # Old format - single sound
                    sound_name = data['sound_name']
                    bound_list.append(f"- '{phrase}' -> {sound_name}")
            
            result = f"SONGBIRD: Found {len(bound_sounds)} bound phrases:\n" + "\n".join(bound_list)
            
            log('info', f'SONGBIRD: Listed {len(bound_sounds)} bound phrases')
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD list bound error: {str(e)}")
            return f"SONGBIRD: Error listing bound sounds - {str(e)}"

    def songbird_unbind_sound(self, args, projected_states) -> str:
        """Remove a specific sound from a binding, or the entire phrase if only one sound"""
        try:
            phrase = args.get('phrase', '').strip()
            
            # Normalize phrase for matching
            normalized_phrase = self.normalize_phrase(phrase)
            
            if not normalized_phrase:
                return "SONGBIRD: Please specify the phrase to unbind."
            
            log('info', f"SONGBIRD: Unbind request for phrase: '{phrase}' (normalized: '{normalized_phrase}')")
            
            # Load bound sounds
            bound_sounds = self.load_bound_sounds()
            
            # Check if phrase exists
            if normalized_phrase not in bound_sounds:
                return f"SONGBIRD: No sound bound to phrase '{phrase}'."
            
            bound_data = bound_sounds[normalized_phrase]
            
            # Handle both formats
            if isinstance(bound_data, list):
                sound_count = len(bound_data)
                sound_names = [s['sound_name'] for s in bound_data]
                sounds_text = ', '.join(sound_names)
            else:
                sound_count = 1
                sounds_text = bound_data['sound_name']
            
            # Remove the entire phrase binding
            del bound_sounds[normalized_phrase]
            
            # Save updated bindings
            if self.save_bound_sounds(bound_sounds):
                log('info', f"SONGBIRD: Unbound phrase '{normalized_phrase}' ({sound_count} sound(s))")
                return f"SONGBIRD: Unbound phrase '{phrase}' ({sound_count} sound(s): {sounds_text})"
            else:
                return "SONGBIRD: Error saving updated bindings"
            
        except Exception as e:
            log('error', f"SONGBIRD unbind error: {str(e)}")
            return f"SONGBIRD: Unbind error - {str(e)}"

    def songbird_unbind_all(self, args, projected_states) -> str:
        """Remove all sound bindings"""
        try:
            log('info', 'SONGBIRD: Unbind all request')
            
            # Load current bindings to count them
            bound_sounds = self.load_bound_sounds()
            count = len(bound_sounds)
            
            if count == 0:
                return "SONGBIRD: No sound bindings to remove."
            
            # Clear all bindings
            if self.save_bound_sounds({}):
                log('info', f'SONGBIRD: Removed all {count} sound bindings')
                return f"SONGBIRD: Removed all {count} sound bindings"
            else:
                return "SONGBIRD: Error clearing bindings"
            
        except Exception as e:
            log('error', f"SONGBIRD unbind all error: {str(e)}")
            return f"SONGBIRD: Unbind all error - {str(e)}"

    def songbird_list_cached(self, args, projected_states) -> str:
        """List all locally cached sound files and playlists"""
        try:
            log('info', 'SONGBIRD: Listing cached sounds and playlists')
            
            plugin_folder = self.get_plugin_folder_path()
            sounds_folder = os.path.join(plugin_folder, 'sounds')
            
            # Get individual sound files
            sound_files = self.get_local_sounds()
            
            # Get playlists (folders with audio files)
            supported_extensions = ['.mp3', '.ogg', '.wav']
            playlists = []
            
            if os.path.exists(sounds_folder):
                for item in os.listdir(sounds_folder):
                    item_path = os.path.join(sounds_folder, item)
                    
                    # Only check directories
                    if os.path.isdir(item_path):
                        # Count audio files in folder
                        audio_count = 0
                        for filename in os.listdir(item_path):
                            if any(filename.lower().endswith(ext) for ext in supported_extensions):
                                audio_count += 1
                        
                        if audio_count > 0:
                            playlists.append((item, audio_count))
            
            # Build result
            result_parts = []
            
            # Individual sounds section
            if sound_files:
                cached_list = []
                for sound in sound_files:
                    cached_list.append(f"- '{sound['readable_name']}'")
                
                result_parts.append(f"SONGBIRD: Found {len(sound_files)} cached sounds:")
                result_parts.append("\n".join(cached_list))
            else:
                result_parts.append(f"SONGBIRD: No individual sounds cached yet.")
            
            # Playlists section
            if playlists:
                playlists.sort()
                playlist_list = []
                for folder_name, count in playlists:
                    playlist_list.append(f"- Playlist '{folder_name}' ({count} sounds)")
                
                result_parts.append(f"\nPlaylists available:")
                result_parts.append("\n".join(playlist_list))
            
            if not sound_files and not playlists:
                return f"SONGBIRD: No sounds or playlists found. Sounds folder: {sounds_folder}"
            
            result = "\n".join(result_parts)
            
            log('info', f'SONGBIRD: Listed {len(sound_files)} sounds and {len(playlists)} playlists')
            return result
            
        except Exception as e:
            log('error', f"SONGBIRD list cached error: {str(e)}")
            return f"SONGBIRD: Error listing cached sounds - {str(e)}"