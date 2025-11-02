from typing import override
import json
import os
import sys
from datetime import datetime
from urllib.parse import quote
import glob

# Set up deps path BEFORE importing requests (like Songbird/Covasify does with deps)
current_dir = os.path.dirname(os.path.abspath(__file__))
deps_path = os.path.join(current_dir, 'deps')
if deps_path not in sys.path:
    sys.path.insert(0, deps_path)

# Now import requests at module level
import requests

from lib.PluginHelper import PluginHelper, PluginManifest
from lib.PluginSettingDefinitions import PluginSettings
from lib.Logger import log
from lib.PluginBase import PluginBase

# ============================================================================
# COMMODITY NAME MAPPINGS - v7.4
# ============================================================================
# These mappings handle voice command variations where INARA display names
# don't match API commodity names. 100 validated aliases for voice-friendly trading.
# 
# Example: User says "Azure Milk" → normalize to "azuremilk" → alias to "bluemilk"
#
# Coverage: 386/397 API commodities (97.2%)
# - 286 commodities work directly (no alias needed)
# - 100 commodities need aliases (all working, validated below)
# - 9 salvage items (see SALVAGE_ITEMS - not tradeable at stations)
# - 2 apostrophe cases (handled by normalization: remove ')
# ============================================================================

COMMODITY_ALIASES = {
    # Normalized INARA name → API name
    # Keys are already normalized (lowercase, no spaces/hyphens/underscores/apostrophes)
    "aepyornisegg": "cetiaepyornisegg",
    "agrimedicines": "agriculturalmedicines",
    "albinoquechuamammothmeat": "albinoquechuamammoth",
    "alyabodysoap": "alyabodilysoap",
    "ancientartefact": "usscargoancientartefact",
    "anomalyparticles": "pantaaprayersticks",
    "atmosphericprocessors": "atmosphericextractors",
    "azuremilk": "bluemilk",  # Critical: voice queries!
    "blackbox": "usscargoblackbox",
    "bonefragments": "thargoidbonefragments",
    "caustictissuesample": "thargoidscouttissuesample",
    "cd75kittenbrandcoffee": "cd75catcoffee",
    "commercialsamples": "comercialsamples",
    "cromsilverfesh": "silver",
    "cystspecimen": "thargoidcystspecimen",
    "encrypteddatastorage": "encripteddatastorage",
    "energygridassembly": "powergridassembly",
    "experimentalchemicals": "usscargoexperimentalchemicals",
    "guardiancasket": "ancientcasket",
    "guardianorb": "ancientorb",
    "guardianrelic": "ancientrelic",
    "guardiantablet": "ancienttablet",
    "guardiantotem": "ancienttotem",
    "guardianurn": "ancienturn",
    "hesuits": "hazardousenvironmentsuits",
    "haidenblackbrew": "haidneblackbrew",
    "hardwarediagnosticsensor": "diagnosticsensor",
    "hipprotosquid": "hip41181squid",
    "hostages": "hostage",
    "impurespiremineral": "unknownrefinedmineral",
    "kachiriginfilterleeches": "kachiriginleaches",
    "kinagoviolins": "kinagoinstruments",
    "landenrichmentsystems": "terrainenrichmentsystems",
    "largesurveydatacache": "largeexplorationdatacash",
    "leatheryeggs": "alieneggs",  # Critical: voice queries!
    "lowtemperaturediamonds": "lowtemperaturediamond",
    "lucanonionhead": "onionhead",
    "marineequipment": "survivalequipment",
    "microbialfurnaces": "heliostaticfurnaces",
    "microweavecoolinghoses": "coolinghoses",
    "militaryplans": "usscargomilitaryplans",
    "molluscbraintissue": "musgravite",
    "molluscsofttissue": "thargoidscouttissuesample",
    "muonimager": "mutomimager",
    "narcotics": "basicnarcotics",
    "occupiedescapepod": "unocuppiedescapepod",
    "onionheadalphastrain": "onionheada",
    "onionheadbetastrain": "onionheadb",
    "onionheadgammastrain": "onionheada",
    "ophiuchexinoartefacts": "ophiuchiexinoartefacts",
    "organsample": "thargoidorgansample",
    "platinumalloy": "platinumaloy",
    "podsurfacetissue": "surfacestabilisers",
    "podcoretissue": "thargoidscouttissuesample",
    "poddeadtissue": "ngunamodernantiques",
    "podoutertissue": "thargoidscouttissuesample",
    "podshelltissue": "pyrophyllite",
    "podtissue": "thargoidtissuesampletype1",
    "politicalprisoners": "politicalprisoner",
    "powertransferbus": "powertransferconduits",
    "protectivemembranescrap": "scrap",
    "prototypetech": "usscargoprototypetech",
    "rajukrumultistoves": "rajukrustoves",
    "rareartwork": "usscargorareartwork",
    "rebeltransmissions": "usscargorebeltransmissions",
    "semirefinedspiremineral": "unknownrefinedmineral",
    "skimmercomponents": "skimercomponents",
    "smallsurveydatacache": "unstabledatacore",
    "tarachspice": "tarachtorspice",
    "technicalblueprints": "usscargotechnicalblueprints",
    "thargoidbasilisktissuesample": "thargoidscouttissuesample",
    "thargoidbiologicalmatter": "unknownbiologicalmatter",
    "thargoidcyclopstissuesample": "thargoidscouttissuesample",
    "thargoidglaivetissuesample": "thargoidtissuesampletype9a",
    "thargoidhydratissuesample": "thargoidtissuesampletype1",
    "thargoidlink": "thargoidpod",
    "thargoidmedusatissuesample": "thargoidscouttissuesample",
    "thargoidorthrustissuesample": "thargoidscouttissuesample",
    "thargoidprobe": "thargoidpod",
    "thargoidresin": "thargoidheart",
    "thargoidscythetissuesample": "thargoidscouttissuesample",
    "thargoidsensor": "thargoidpod",
    "thargoidtechnologysamples": "unknowntechnologysamples",
    "thargoidbiostoragecapsule": "thargoidbonefragments",
    "thewatersofshintara": "watersofshintara",  # Critical: "The..." prefix!
    "titandeeptissuesample": "thargoidgeneratortissuesample",
    "titandrivecomponent": "thargoidtitandrivecomponent",
    "titantissuesample": "thargoidscouttissuesample",
    "tradedata": "usscargotradedata",
    "trinketsofhiddenfortune": "trinketsoffortune",
    "ultracompactprocessorprototypes": "wulpahyperboresystems",
    "unclassifiedrelic": "classifiedexperimentalequipment",
    "unoccupiedescapepod": "unocuppiedescapepod",
    "utgaroarmillennialeggs": "utgaroarmillenialeggs",
    "vanayequiceratomorphafur": "vanayequirhinofur",
    "voidextractcoffee": "lftvoidextractcoffee",
    "voidopal": "opal",
    "wolffesh": "wolf1301fesh",
    "xihebiomorphiccompanions": "xihecompanions",
    "zeesszeantgrubglue": "zeesszeantglue",
    
    # ========== RARE GOODS ALIASES (v7.6.1) ==========
    # Rare goods with display names that normalize differently than API names
    "edenapplesofaerial": "aerialedenapple",  # Eden Apples Of Aerial
    "korokungpellets": "korrokungpellets",  # Koro Kung Pellets
    "sanumadecorativemeat": "sanumameat",  # Sanuma Decorative Meat
}


# ============================================================================
# RARE GOODS DISPLAY NAMES - Maps API names to INARA display names
# ============================================================================
# Rare goods have different display names than their API identifiers.
# This mapping ensures users see proper names like "Azure Milk" not "bluemilk".
# Used by Action #35 (list_rare_goods) for voice-friendly output.
# Total: 143 rare goods with proper display names.
# ============================================================================

RARE_GOODS_DISPLAY_NAMES = {
    "advert1": "Ultra-Compact Processor Prototypes",
    "aerialedenapple": "Eden Apples Of Aerial",
    "aganipperush": "Aganippe Rush",
    "alacarakmoskinart": "Alacarakmo Skin Art",
    "albinoquechuamammoth": "Albino Quechua Mammoth Meat",
    "alieneggs": "Leathery Eggs",
    "altairianskin": "Altairian Skin",
    "alyabodilysoap": "Alya Body Soap",
    "anduligafireworks": "Anduliga Fire Works",
    "animaleffigies": "Animal Effigies",
    "anynacoffee": "Any Na Coffee",
    "apavietii": "Apa Vietii",
    "aroucaconventualsweets": "Arouca Conventual Sweets",
    "azcancriformula42": "AZ Cancri Formula 42",
    "bakedgreebles": "Baked Greebles",
    "baltahsinevacuumkrill": "Baltah'sine Vacuum Krill",
    "bankiamphibiousleather": "Banki Amphibious Leather",
    "bastsnakegin": "Bast Snake Gin",
    "belalansrayleather": "Belalans Ray Leather",
    "bluemilk": "Azure Milk",
    "borasetanipathogenetics": "Borasetani Pathogenetics",
    "buckyballbeermats": "Buckyball Beer Mats",
    "burnhambiledistillate": "Burnham Bile Distillate",
    "cd75catcoffee": "CD-75 Kitten Brand Coffee",
    "centaurimegagin": "Centauri Mega Gin",
    "ceremonialheiketea": "Ceremonial Heike Tea",
    "cetiaepyornisegg": "Aepyornis Egg",
    "cetirabbits": "Ceti Rabbits",
    "chameleoncloth": "Chameleon Cloth",
    "chateaudeaegaeon": "Chateau De Aegaeon",
    "cherbonesbloodcrystals": "Cherbones Blood Crystals",
    "chieridanimarinepaste": "Chi Eridani Marine Paste",
    "classifiedexperimentalequipment": "Classified Experimental Equipment",
    "coquimspongiformvictuals": "Coquim Spongiform Victuals",
    "crystallinespheres": "Crystalline Spheres",
    "damnacarapaces": "Damna Carapaces",
    "deltaphoenicispalms": "Delta Phoenicis Palms",
    "deuringastruffles": "Deuringas Truffles",
    "disomacorn": "Diso Ma Corn",
    "duradrives": "Duradrives",
    "eleuthermals": "Eleu Thermals",
    "eraninpearlwhisky": "Eranin Pearl Whisky",
    "eshuumbrellas": "Eshu Umbrellas",
    "esusekucaviar": "Esuseku Caviar",
    "ethgrezeteabuds": "Ethgreze Tea Buds",
    "fujintea": "Fujin Tea",
    "galactictravelguide": "Galactic Travel Guide",
    "geawendancedust": "Geawen Dance Dust",
    "gerasiangueuzebeer": "Gerasian Gueuze Beer",
    "giantirukamasnails": "Giant Irukama Snails",
    "giantverrix": "Giant Verrix",
    "gilyasignatureweapons": "Gilya Signature Weapons",
    "gomanyauponcoffee": "Goman Yaupon Coffee",
    "haidneblackbrew": "Haiden Black Brew",
    "harmasilversearum": "Harma Silver Sea Rum",
    "havasupaidreamcatcher": "Havasupai Dream Catcher",
    "helvetitjpearls": "Helvetitj Pearls",
    "hip10175bushmeat": "HIP 10175 Bush Meat",
    "hip118311swarm": "HIP 118311 Swarm",
    "hip41181squid": "HIP Proto-Squid",
    "hiporganophosphates": "Hip Organophosphates",
    "holvaduellingblades": "Holva Duelling Blades",
    "honestypills": "Honesty Pills",
    "hr7221wheat": "HR 7221 Wheat",
    "indibourbon": "Indi Bourbon",
    "jaquesquinentianstill": "Jaques Quinentian Still",
    "jaradharrepuzzlebox": "Jaradharre Puzzle Box",
    "jarouarice": "Jaroua Rice",
    "jotunmookah": "Jotun Mookah",
    "kachiriginleaches": "Kachirigin Filter Leeches",
    "kamitracigars": "Kamitra Cigars",
    "kamorinhistoricweapons": "Kamorin Historic Weapons",
    "karetiicouture": "Karetii Couture",
    "karsukilocusts": "Karsuki Locusts",
    "kinagoinstruments": "Kinago Violins",
    "konggaale": "Kongga Ale",
    "korrokungpellets": "Koro Kung Pellets",
    "lavianbrandy": "Lavian Brandy",
    "leestianeviljuice": "Leestian Evil Juice",
    "lftvoidextractcoffee": "Void Extract Coffee",
    "livehecateseaworms": "Live Hecate Sea Worms",
    "ltthypersweet": "LTT Hyper Sweet",
    "lyraeweed": "Lyrae Weed",
    "masterchefs": "Master Chefs",
    "mechucoshightea": "Mechucos High Tea",
    "medbstarlube": "Medb Starlube",
    "mokojingbeastfeast": "Mokojing Beast Feast",
    "momusbogspaniel": "Momus Bog Spaniel",
    "motronaexperiencejelly": "Motrona Experience Jelly",
    "mukusubiichitinos": "Mukusubii Chitin-os",
    "mulachigiantfungus": "Mulachi Giant Fungus",
    "nanomedicines": "Nanomedicines",
    "neritusberries": "Neritus Berries",
    "ngadandarifireopals": "Ngadandari Fire Opals",
    "ngunamodernantiques": "Nguna Modern Antiques",
    "njangarisaddles": "Njangari Saddles",
    "noneuclidianexotanks": "Non Euclidian Exotanks",
    "ochoengchillies": "Ochoeng Chillies",
    "onionhead": "Onionhead",
    "onionheada": "Onionhead Alpha Strain",
    "onionheadb": "Onionhead Beta Strain",
    "ophiuchiexinoartefacts": "Ophiuch Exino Artefacts",
    "orrerianviciousbrew": "Orrerian Vicious Brew",
    "pantaaprayersticks": "Pantaa Prayer Sticks",
    "pavoniseargrubs": "Pavonis Ear Grubs",
    "personalgifts": "Personal Gifts",
    "platinumaloy": "Platinum Alloy",
    "rajukrustoves": "Rajukru Multi-Stoves",
    "rapabaosnakeskins": "Rapa Bao Snake Skins",
    "rusanioldsmokey": "Rusani Old Smokey",
    "sanumameat": "Sanuma Decorative Meat",
    "saxonwine": "Saxon Wine",
    "shanscharisorchid": "Shan's Charis Orchid",
    "soontillrelics": "Soontill Relics",
    "sothiscrystallinegold": "Sothis Crystalline Gold",
    "tanmarktranquiltea": "Tanmark Tranquil Tea",
    "tarachtorspice": "Tarach Spice",
    "taurichimes": "Tauri Chimes",
    "terramaterbloodbores": "Terra Mater Blood Bores",
    "thehuttonmug": "The Hutton Mug",
    "thrutiscream": "Thrutis Cream",
    "tiegfriessynthsilk": "Tiegfries Synth Silk",
    "tiolcewaste2pasteunits": "Tiolce Waste2Paste Units",
    "toxandjivirocide": "Toxandji Virocide",
    "transgeniconionhead": "Lucan Onionhead",
    "uszaiantreegrub": "Uszaian Tree Grub",
    "utgaroarmillenialeggs": "Utgaroar Millennial Eggs",
    "uzumokulow-gwings": "Uzumoku Low-G Wings",
    "uzumokulowgwings": "Uzumoku Low-G Wings",
    "vanayequirhinofur": "Vanayequi Ceratomorpha Fur",
    "vegaslimweed": "Vega Slimweed",
    "vherculisbodyrub": "V Herculis Body Rub",
    "vidavantianlace": "Vidavantian Lace",
    "volkhabbeedrones": "Volkhab Bee Drones",
    "watersofshintara": "The Waters Of Shintara",
    "wheemetewheatcakes": "Wheemete Wheat Cakes",
    "witchhaulkobebeef": "Witchhaul Kobe Beef",
    "wolf1301fesh": "Wolf Fesh",
    "wulpahyperboresystems": "Ultra-Compact Processor Prototypes",
    "wuthielokufroth": "Wuthielo Ku Froth",
    "xihecompanions": "Xihe Biomorphic Companions",
    "yasokondileaf": "Yaso Kondi Leaf",
    "zeesszeantglue": "Zeessze Ant Grub Glue",
}

# ============================================================================
# RARE GOODS DATA - Embedded data (no external JSON needed)
# ============================================================================
# Maps rare good API name to maximum allocation count
# Used to identify rare goods and show current/max stock info
# Total: 143 rare goods
# ============================================================================

RARE_GOODS_DATA = {
    "advert1": 1, "aerialedenapple": 15, "aganipperush": 10, "alacarakmoskinart": 24,
    "albinoquechuamammoth": 10, "alieneggs": 1, "altairianskin": 42, "alyabodilysoap": 16,
    "anduligafireworks": 16, "animaleffigies": 17, "anynacoffee": 11, "apavietii": 11,
    "aroucaconventualsweets": 18, "azcancriformula42": 9, "bakedgreebles": 17,
    "baltahsinevacuumkrill": 18, "bankiamphibiousleather": 18, "bastsnakegin": 15,
    "belalansrayleather": 11, "bluemilk": 7, "borasetanipathogenetics": 6,
    "buckyballbeermats": 25, "burnhambiledistillate": 16, "cd75catcoffee": 12,
    "centaurimegagin": 7, "ceremonialheiketea": 8, "cetiaepyornisegg": 5, "cetirabbits": 12,
    "chameleoncloth": 7, "chateaudeaegaeon": 14, "cherbonesbloodcrystals": 48,
    "chieridanimarinepaste": 18, "classifiedexperimentalequipment": None,
    "coquimspongiformvictuals": 20, "crystallinespheres": 12, "damnacarapaces": 23,
    "deltaphoenicispalms": 17, "deuringastruffles": 7, "disomacorn": 15, "duradrives": 22,
    "eleuthermals": 13, "eraninpearlwhisky": 16, "eshuumbrellas": 9, "esusekucaviar": 10,
    "ethgrezeteabuds": 7, "fujintea": 23, "galactictravelguide": None, "geawendancedust": 23,
    "gerasiangueuzebeer": 40, "giantirukamasnails": 16, "giantverrix": 6,
    "gilyasignatureweapons": 9, "gomanyauponcoffee": 9, "haidneblackbrew": 21,
    "harmasilversearum": 60, "havasupaidreamcatcher": 4, "helvetitjpearls": 6,
    "hip10175bushmeat": 13, "hip118311swarm": 1, "hip41181squid": 14,
    "hiporganophosphates": 17, "holvaduellingblades": 7, "honestypills": 13, "hr7221wheat": 16,
    "indibourbon": 8, "jaquesquinentianstill": 26, "jaradharrepuzzlebox": 4, "jarouarice": 18,
    "jotunmookah": 10, "kachiriginleaches": 10, "kamitracigars": 23, "kamorinhistoricweapons": 10,
    "karetiicouture": 5, "karsukilocusts": 18, "kinagoinstruments": 3, "konggaale": 16,
    "korrokungpellets": 20, "lavianbrandy": 24, "leestianeviljuice": 14,
    "lftvoidextractcoffee": 18, "livehecateseaworms": 13, "ltthypersweet": 19, "lyraeweed": 10,
    "masterchefs": 26, "mechucoshightea": 12, "medbstarlube": 18, "mokojingbeastfeast": 7,
    "momusbogspaniel": 7, "motronaexperiencejelly": 11, "mukusubiichitinos": 15,
    "mulachigiantfungus": 22, "nanomedicines": 40, "neritusberries": 13,
    "ngadandarifireopals": 6, "ngunamodernantiques": 4, "njangarisaddles": 13,
    "noneuclidianexotanks": 16, "ochoengchillies": 14, "onionhead": 12, "onionheada": 10,
    "onionheadb": 10, "ophiuchiexinoartefacts": 7, "orrerianviciousbrew": 32,
    "pantaaprayersticks": 36, "pavoniseargrubs": 30, "personalgifts": 20, "platinumaloy": 13,
    "rajukrustoves": 17, "rapabaosnakeskins": 11, "rusanioldsmokey": 10, "sanumameat": 7,
    "saxonwine": 13, "shanscharisorchid": 7, "soontillrelics": 5, "sothiscrystallinegold": 20,
    "tanmarktranquiltea": 12, "tarachtorspice": 12, "taurichimes": 26, "terramaterbloodbores": 5,
    "thehuttonmug": 30, "thrutiscream": 11, "tiegfriessynthsilk": 30, "tiolcewaste2pasteunits": 13,
    "toxandjivirocide": 14, "transgeniconionhead": 12, "uszaiantreegrub": 14,
    "utgaroarmillenialeggs": 15, "uzumokulow-gwings": 8, "uzumokulowgwings": 8,
    "vanayequirhinofur": 10, "vegaslimweed": 28, "vherculisbodyrub": 10, "vidavantianlace": 5,
    "volkhabbeedrones": 6, "watersofshintara": 12, "wheemetewheatcakes": 19,
    "witchhaulkobebeef": 18, "wolf1301fesh": 13, "wulpahyperboresystems": 10,
    "wuthielokufroth": 17, "xihecompanions": 10, "yasokondileaf": 5, "zeesszeantglue": 27,
}


# ============================================================================
# SALVAGE ITEMS - Not Tradeable at Stations
# ============================================================================
# These items exist in-game but have NO market prices. They're obtained from
# wreckage sites, alien structures, or as mission rewards. They can only be
# turned in at Search & Rescue contacts or sold at black markets.
#
# When users query these, we provide a helpful error message instead of 404.
# ============================================================================

SALVAGE_ITEMS = {
    # Normalized name → Display name
    "molluscfluid": "Mollusc Fluid",
    "molluscmembrane": "Mollusc Membrane",
    "molluscmycelium": "Mollusc Mycelium",
    "molluscspores": "Mollusc Spores",
    "podmesoglea": "Pod Mesoglea",
    "titanmawdeeptissuesample": "Titan Maw Deep Tissue Sample",
    "titanmawpartialtissuesample": "Titan Maw Partial Tissue Sample",
    "titanmawtissuesample": "Titan Maw Tissue Sample",
    "titanpartialtissuesample": "Titan Partial Tissue Sample",
}


# Main plugin class
# ============================================================================
# ============================================================================
# RELIABILITY CLIENT - v7.6 Phase 1A
# ============================================================================
# Adds caching and retry logic to API calls without modifying core functions.
# Features:
# - Per-endpoint TTL (MARKET 120s, SYSTEM 300s, METADATA 3600s)
# - Smart cache keys (includes endpoint + all params)
# - 3-attempt retry with exponential backoff (1s, 2s, 4s)
# - Thread-safe cache management
# ============================================================================

class ReliabilityClient:
    """Caching and retry wrapper for API calls with per-endpoint TTL"""
    
    # TTL values in seconds
    TTL_MARKET = 120      # 2 min - Commodity prices, stock levels (changes frequently)
    TTL_SYSTEM = 300      # 5 min - System coordinates, station lists (moderately stable)
    TTL_METADATA = 3600   # 1 hour - Station services, system info (very stable)
    TTL_DEFAULT = 300     # 5 min - Everything else
    INFLIGHT_WAIT_TIMEOUT = 30  # Max seconds to wait for in-flight requests
    
    def __init__(self):
        import threading
        self.cache = {}  # {key: (result, cached_time, ttl)}
        self.lock = threading.RLock()  # Thread-safe cache access
        self.in_flight = {}  # {key: (event, result_holder)}
        from datetime import datetime
        self.datetime = datetime
        
        # ✅ ACTION 9: Cache statistics tracking
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'inflight_hits': 0,
            'api_calls': 0,
            'errors': 0
        }
    
    def _make_cache_key(self, endpoint, params):
        """Include ALL relevant parameters in cache key"""
        import json
        # Sort params to ensure consistent keys
        param_str = json.dumps(params, sort_keys=True) if params else ""
        return f"{endpoint}:{param_str}"
    
    def _get_ttl_for_endpoint(self, endpoint: str) -> int:
        """
        Determine appropriate TTL based on endpoint type.
        
        Market data (prices/stock) changes frequently → 2 min
        System data (coordinates/stations) is moderately stable → 5 min
        Metadata (services/info) is very stable → 1 hour
        """
        endpoint_lower = endpoint.lower()
        
        # Market data - frequently changing
        if any(x in endpoint_lower for x in ['/exports', '/imports', '/commodity', '/market']):
            return self.TTL_MARKET
        
        # Metadata - very stable
        if any(x in endpoint_lower for x in ['/nearest/', '/service', '/station/name']):
            return self.TTL_METADATA
        
        # System data - moderately stable
        if any(x in endpoint_lower for x in ['/system/name', '/system/coordinates']):
            return self.TTL_SYSTEM
        
        # Default
        return self.TTL_DEFAULT
    
    def get_cached_or_fetch(self, endpoint, params, fetch_fn):
        """Get from cache or fetch with retry (thread-safe with in-flight deduplication)"""
        import threading
        import time
        
        key = self._make_cache_key(endpoint, params)
        
        # Check cache (thread-safe)
        with self.lock:
            if key in self.cache:
                cached_data, cached_time, cached_ttl = self.cache[key]
                age = (self.datetime.now() - cached_time).total_seconds()
                if age < cached_ttl:
                    self.stats['cache_hits'] += 1
                    log('info', f'COVINANCE: Cache HIT for {endpoint} (age: {age:.1f}s, ttl: {cached_ttl}s)')
                    return cached_data
            
            # Check if request already in-flight
            if key in self.in_flight:
                event, result_holder = self.in_flight[key]
                log('info', f'COVINANCE: In-flight HIT for {endpoint} - waiting for result')
        
        # If in-flight, wait outside the lock
        if key in self.in_flight:
            event.wait(timeout=self.INFLIGHT_WAIT_TIMEOUT)
            with self.lock:
                if key in self.cache:
                    cached_data, cached_time, cached_ttl = self.cache[key]
                    age = (self.datetime.now() - cached_time).total_seconds()
                    if age < cached_ttl:
                        self.stats['inflight_hits'] += 1
                        log('info', f'COVINANCE: In-flight result retrieved for {endpoint}')
                        return cached_data
            # Timeout or cache miss - fall through to fetch
        
        # Mark as in-flight
        with self.lock:
            if key not in self.in_flight:
                event = threading.Event()
                result_holder = [None, None]  # [result, exception]
                self.in_flight[key] = (event, result_holder)
            else:
                # Another thread just started - wait for it
                event, result_holder = self.in_flight[key]
                log('info', f'COVINANCE: Race condition - waiting for in-flight {endpoint}')
        
        # Check if we're the waiter (another thread is fetching)
        if result_holder[0] is not None or result_holder[1] is not None:
            event.wait(timeout=self.INFLIGHT_WAIT_TIMEOUT)
            with self.lock:
                if key in self.cache:
                    cached_data, cached_time, cached_ttl = self.cache[key]
                    return cached_data
                if result_holder[1] is not None:
                    raise result_holder[1]
        
        # We're the fetcher - determine TTL
        ttl = self._get_ttl_for_endpoint(endpoint)
        
        # Fetch with retry (3 attempts, exponential backoff)
        # NOTE: fetch_fn NOT inside lock - we want concurrent API calls
        last_error = None
        result = None
        
        # Increment stats ONCE before retry loop (thread-safe)
        with self.lock:
            self.stats['cache_misses'] += 1
        
        try:
            for attempt in range(3):
                try:
                    # Increment API call counter for this attempt (thread-safe)
                    with self.lock:
                        self.stats['api_calls'] += 1
                    log('info', f'COVINANCE: Cache MISS - Fetching {endpoint} (attempt {attempt + 1}/3, ttl: {ttl}s)')
                    result = fetch_fn(endpoint, params)
                    
                    # Check if result is an error response or None
                    is_error = (isinstance(result, dict) and 'error' in result) or result is None
                    
                    if is_error:
                        # Don't cache error responses (404s, timeouts, etc.) or None
                        error_msg = result.get('error') if isinstance(result, dict) else 'None result'
                        log('warning', f'COVINANCE: Not caching error response for {endpoint}: {error_msg}')
                        with self.lock:
                            result_holder[0] = result
                        return result
                    
                    # Store successful response in cache (thread-safe)
                    with self.lock:
                        self.cache[key] = (result, self.datetime.now(), ttl)
                        result_holder[0] = result
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    if attempt < 2:  # Don't sleep on last attempt
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        log('warning', f'COVINANCE: API call failed (attempt {attempt + 1}/3), retrying in {wait}s...')
                        time.sleep(wait)
                    else:
                        log('error', f'COVINANCE: API call failed after 3 attempts: {str(e)}')
            
            # All retries failed
            with self.lock:
                result_holder[1] = last_error
            raise last_error
            
        finally:
            # Always clean up in-flight tracking and signal waiters
            with self.lock:
                if key in self.in_flight:
                    event, _ = self.in_flight[key]
                    event.set()  # Wake up any waiters
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
# PARALLEL EXECUTION
# ============================================================================
# Enables concurrent API calls for performance-critical operations.
# Primary use: Rare goods discovery (143 commodities in parallel)
# ============================================================================

class ParallelRunner:
    """Execute API calls in parallel with progress tracking"""
    
    def __init__(self, max_workers: int = 8):
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
                log('warning', f'Parallel task failed: {str(e)}')
        
        return results, exceptions
    
    def shutdown(self):
        """Cleanup thread pool"""
        self.executor.shutdown(wait=True)


class COVINANCE(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        
        # Ardent API base URL
        self.api_base_url = "https://api.ardent-insight.com/v2"
        
        # Initialize reliability client (caching + retry with per-endpoint TTL)
        self.reliability_client = ReliabilityClient()
        self.parallel_runner = ParallelRunner(max_workers=8)
        # Track current system/station from Journal
        self.current_system = None
        self.current_station = None
        self.system_coordinates = None
        
        # Cache for API responses (5 minute expiration)
        self.cache = {}
        self.cache_expiration = 300  # seconds
        
        # Minimal settings configuration (no settings needed)
        self.settings_config: PluginSettings | None = PluginSettings(
            key="COVINANCEPlugin",
            label="Covinance Trading Assistant",
            icon="attach_money",
            grids=[]
        )
    
    def _is_carrier_name(self, name):
        """Detect if a name looks like a fleet carrier (e.g., Q8Y-43N, X7A-9NK)"""
        if not name or len(name) > 10:
            return False
        # Carrier pattern: starts with Q/X/H/V/P, contains hyphen, short name
        name_first = name.split()[0] if ' ' in name else name
        return (
            len(name_first) <= 8 and
            name_first[0].upper() in ('Q', 'X', 'H', 'V', 'P') and
            '-' in name_first
        )
    
    def _normalize_commodity_name(self, commodity: str) -> str:
        """
        Smart commodity name normalization with alias lookup and salvage detection.
        
        Handles voice command variations where INARA display names don't match
        API commodity names. 100 validated aliases for natural language support.
        
        Args:
            commodity: User input (e.g., 'Azure Milk', 'hydrogen fuel', 'GOLD')
        
        Returns:
            API-compatible commodity name (e.g., 'bluemilk', 'hydrogenfuel', 'gold')
        
        Raises:
            ValueError: If commodity is a salvage item (not tradeable at stations)
        
        Examples:
            >>> _normalize_commodity_name("Azure Milk")
            'bluemilk'  # Alias applied
            
            >>> _normalize_commodity_name("Hydrogen Fuel")
            'hydrogenfuel'  # Direct normalization
            
            >>> _normalize_commodity_name("Mollusc Fluid")
            ValueError: Mollusc Fluid is a salvage item...
        """
        # Step 1: Basic normalization
        #   - Lowercase
        #   - Remove spaces, hyphens, underscores, apostrophes
        #   - Strip whitespace
        normalized = commodity.lower()
        normalized = normalized.replace(' ', '')
        normalized = normalized.replace('-', '')
        normalized = normalized.replace('_', '')
        normalized = normalized.replace("'", '')
        normalized = normalized.strip()
        
        # Step 2: Check if this is a salvage item (not tradeable)
        if normalized in SALVAGE_ITEMS:
            display_name = SALVAGE_ITEMS[normalized]
            raise ValueError(
                f"{display_name} is a salvage item obtained from wreckage sites, "
                f"not traded at stations. Turn in at Search & Rescue contacts."
            )
        
        # Step 3: Apply alias if it exists, otherwise return normalized name
        #   - 100 validated aliases for name mismatches
        #   - 286 commodities work directly without alias
        return COMMODITY_ALIASES.get(normalized, normalized)
    
    def _matches_commodity(self, user_input: str, api_commodity_name: str) -> bool:
        """
        Check if user's commodity input matches API commodity name.
        Handles aliases bidirectionally.
        
        Examples:
            user_input="azure milk", api_name="bluemilk" → True
            user_input="blue milk", api_name="bluemilk" → True
            user_input="leathery eggs", api_name="alieneggs" → True
        
        Args:
            user_input: What user typed (e.g., "azure milk")
            api_commodity_name: What API returned (e.g., "bluemilk")
            
        Returns:
            True if they match (considering aliases), False otherwise
        """
        try:
            # Normalize both using the SAME method (symmetric!)
            normalized_user = self._normalize_commodity_name(user_input)
            # Apply same normalization to API name - this handles aliases too
            try:
                normalized_api = self._normalize_commodity_name(api_commodity_name)
            except ValueError:
                # If API name is invalid (e.g., salvage), just normalize without aliases
                normalized_api = api_commodity_name.lower().replace(' ', '').replace('-', '').replace('_', '').replace("'", '')
            
            # Now simple direct comparison works!
            # Both "azure milk" and "blue milk" will normalize to "bluemilk"
            # And API "Azure Milk" will also normalize to "bluemilk"
            return normalized_user == normalized_api
            
        except ValueError:
            # If normalization fails (e.g., salvage item), no match
            return False
    
    def _normalize_service_name(self, service: str) -> str:
        """
        Normalize user-provided service name to API format.
        
        Args:
            service: User input (e.g., "material trader", "tech broker")
        
        Returns:
            API-compatible service name or None if invalid
        """
        # Normalize input
        service_clean = service.lower().strip().replace('_', '-')
        
        # Mapping to API format
        service_map = {
            'material trader': 'material-trader',
            'mat trader': 'material-trader',
            'materials trader': 'material-trader',
            'technology broker': 'technology-broker',
            'tech broker': 'technology-broker',
            'interstellar factors': 'interstellar-factors',
            'black market': 'black-market',
            'universal cartographics': 'universal-cartographics',
            'cartographics': 'universal-cartographics',
            'search and rescue': 'search-and-rescue'
        }
        
        # Check if already in API format
        if service_clean in ['material-trader', 'technology-broker', 'interstellar-factors',
                             'black-market', 'universal-cartographics', 'refuel', 
                             'repair', 'shipyard', 'outfitting', 'search-and-rescue']:
            return service_clean
        
        # Try mapping
        if service_clean in service_map:
            return service_map[service_clean]
        
        # Try partial match
        for user_form, api_form in service_map.items():
            if user_form in service_clean or service_clean in user_form:
                return api_form
        
        return None
    def _get_landing_pad_size(self, ship_type: str) -> str:
        """
        Map ship type to required landing pad size (v7.2 standard).
        COMPLETE & VERIFIED - ALL 44 flyable ships in Elite Dangerous (Oct 2025).
        
        Args:
            ship_type: Ship type from Journal (e.g., 'type9', 'Python', 'sidewinder')
        
        Returns:
            'L' (Large), 'M' (Medium), or 'S' (Small)
        """
        ship_clean = ship_type.lower().replace(' ', '').replace('_', '').replace('-', '')
        
        # LARGE PAD SHIPS (9 ships) - Cannot dock at outposts
        large_ships = [
            # Type series LARGE haulers (NOTE: Type-7 is LARGE despite being "Type-7"!)
            'type7', 'type7transporter',
            'type9', 'type9heavy',
            'type10', 'type10defender',
            
            # Combat/multipurpose large ships
            'anaconda',
            'cutter', 'imperialcutter',
            'corvette', 'federalcorvette',
            
            # Passenger liner
            'belugaliner', 'beluga',
            
            # Newer large ships
            'pantherclipper', 'pantherclippermkii', 'pantherclippermk2',
            'pantherclipper2', 'pantherclippermarkii', 'pantherclippermark2'
        ]
        
        # MEDIUM PAD SHIPS (19 ships) - Can dock at medium/large stations
        medium_ships = [
            # Python family
            'python', 'pythonnx',
            'pythonmkii', 'pythonmk2', 'pythonmarkii', 'pythonmark2', 'python2',  # NEW April 2024!
            
            # Krait family
            'kraitmkii', 'krait', 'kraitmk2', 'kraitmarkii',
            'kraitphantom', 'phantom',
            
            # Exploration/multipurpose
            'asp', 'aspexplorer',
            'mandalay',  # NEW SCO-optimized explorer!
            
            # Alliance ships
            'chieftain', 'alliancechieftain',
            'challenger', 'alliancechallenger',
            'crusader', 'alliancecrusader',
            
            # Federal ships (medium)
            'dropship', 'federaldropship',
            'gunship', 'federalgunship',
            'assaultship', 'federalassaultship',
            
            # Imperial medium
            'clipper', 'imperialclipper',
            
            # Combat medium
            'ferdelance', 'ferdel ance', 'fdl',
            'mamba',
            
            # Passenger/multipurpose medium
            'orca',
            
            # Type series MEDIUM (verified!)
            'type8', 'type8transporter',  # NEW medium hauler!
            'type11', 'type11prospector',  # NEW medium miner!
            
            # Pirate ship
            'corsair'  # NEW pirate vessel!
        ]
        
        # SMALL PAD SHIPS (18 ships) - Can dock anywhere
        # Default to 'S' (safest) if not in large or medium lists
        small_ships = [
            'sidewinder', 'sidewindermki', 'sidewindermk1',
            'eagle', 'eaglemkii', 'eaglemk2',
            'hauler',
            'adder',
            'imperialeagle',
            'viper', 'vipermkiii', 'vipermk3',
            'cobra', 'cobramkiii', 'cobramk3',
            'vipermkiv', 'vipermk4',
            'diamondbackscout', 'diamondback', 'dbscout', 'dbs',
            'cobramkiv', 'cobramk4',
            'cobramkv', 'cobramk5', 'cobra5',  # NEW ship!
            'type6', 'type6transporter',
            'dolphin',
            'diamondbackexplorer', 'diamondbackexp', 'dbx', 'dbexplorer', 'dbe',
            'imperialcourier', 'courier',
            'keelback',
            'aspscout',
            'vulture'
        ]
        
        # Check ship type against lists
        if ship_clean in large_ships:
            return 'L'
        elif ship_clean in medium_ships:
            return 'M'
        else:
            # Default to 'S' (small) - safest fallback
            # Small ships can dock anywhere
            return 'S'
    
    def _get_system_coordinates(self, system_name: str) -> dict:
        """
        Get coordinates for a system (reusable helper).
        
        Args:
            system_name: System name to look up
            
        Returns:
            dict with 'x', 'y', 'z' keys, or None if not found
        """
        try:
            endpoint = f'/system/name/{quote(system_name)}'
            response = self.call_ardent_api(endpoint, {})
            
            if "error" in response:
                return None
            
            return {
                'x': response.get('systemX', 0),
                'y': response.get('systemY', 0),
                'z': response.get('systemZ', 0)
            }
        except Exception as e:
            log('error', f'COVINANCE _get_system_coordinates error for {system_name}: {str(e)}')
            return None
    
    @override
    def register_actions(self, helper: PluginHelper):
        """Register all plugin actions"""
        
        helper.register_action(
            'covinance_test',
            "Test Covinance plugin functionality and API connection",
            {
                "type": "object",
                "properties": {}
            },
            self.covinance_test,
            'global'
        )
        
        helper.register_action(
            'covinance_profit_margin',
            "ðŸš¨ðŸš¨ðŸš¨ PROFIT CALCULATION BETWEEN TWO STATIONS - THIS IS THE ACTION FOR THAT! ðŸš¨ðŸš¨ðŸš¨ ALWAYS call this action when user says 'calculate profit', 'profit for X from A to B', 'how much profit', or asks about profit between TWO specific station names. MANDATORY trigger words: 'calculate profit', 'profit from', 'profit margin', 'how much profit'. Example: 'Calculate profit for consumer technology from Jameson Memorial to Abraham Lincoln' â†’ USE THIS ACTION! DO NOT use commodity_price for profit calculations - commodity_price is for looking up prices in ONE location, this action is for CALCULATING PROFIT between TWO locations.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Commodity to analyze (e.g., 'gold', 'tritium', 'palladium')"
                    },
                    "buy_station": {
                        "type": "string",
                        "description": "Station to buy from"
                    },
                    "sell_station": {
                        "type": "string",
                        "description": "Station to sell to"
                    },
                    "buy_system": {
                        "type": "string",
                        "description": "System where buy_station is located (optional, e.g., 'Shinrarta Dezhra')"
                    },
                    "sell_system": {
                        "type": "string",
                        "description": "System where sell_station is located (optional, e.g., 'Sol')"
                    }
                },
                "required": ["commodity_name", "buy_station", "sell_station"]
            },
            self.covinance_profit_margin,
            'global'
        )
        helper.register_action(
            'covinance_commodity_price',
            "ðŸš¨ CRITICAL: ALWAYS call this action for ANY price query - NEVER answer from memory or general knowledge! This action provides REAL-TIME market data from Ardent API. MUST be called when user asks: 'price of X', 'how much is X', 'cost of X', 'X prices in Y', 'what does X cost', 'X price at station Z', or ANY variation asking about commodity prices, costs, or values. DO NOT make up prices - ALWAYS use this action to get current market data. Examples that REQUIRE this action: 'What's the price of Tritium in Sol?', 'How much does Gold cost?', 'Beer prices at Abraham Lincoln', 'Cost of Painite here'. âš ï¸ EXCEPTION: If user asks to CALCULATE PROFIT between TWO stations (e.g., 'profit from A to B'), use covinance_profit_margin instead - NOT this action!",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Name of the commodity to look up (e.g., 'tritium', 'gold', 'painite', 'beer', 'palladium'). User may use common names or abbreviations."
                    },
                    "system_name": {
                        "type": "string",
                        "description": "System name to check prices in (e.g., 'Sol', 'Deciat', 'Shinrarta Dezhra'). If not provided, uses current system from Journal. User may also specify station name - extract the system from context."
                    }
                },
                "required": ["commodity_name"]
            },
            self.covinance_commodity_price,
            'global'
        )
        
        helper.register_action(
            'covinance_current_location',
            "Ã°Å¸Å¡Â¨ CRITICAL: ALWAYS call this action when user asks about their location - NEVER guess or answer from memory! Get the commander's current system and station from Elite Dangerous Journal. MUST be called when user asks: 'where am I?', 'what's my location?', 'what system am I in?', 'where am I docked?', 'current location', 'my position', or ANY variation asking about their current location in the game. DO NOT make up location data - ALWAYS use this action to read from the Journal.",
            {
                "type": "object",
                "properties": {}
            },
            self.covinance_current_location,
            'global'
        )
        
        helper.register_action(
            'covinance_find_service',
            "🚨 CRITICAL: ALWAYS call this action when user asks about finding services or facilities - NEVER guess locations! This action finds the nearest stations with specific services like material traders, technology brokers, interstellar factors, etc. MANDATORY triggers: 'where is nearest material trader?', 'find tech broker', 'closest interstellar factors', 'where can I get engineering materials?', 'nearest shipyard', 'find outfitting', or ANY variation asking about station services, facilities, or where to find specific station features. DO NOT make up locations - ALWAYS use this action for service queries. ⚠️ SHIPYARD LIMITATION: This shows WHERE shipyards are located, NOT which ships they sell. Ardent API does not track ship inventories - only commodity markets. If user asks 'which ships are sold' or 'list ships at station', respond: 'Covinance tracks commodity markets only. Ship inventories are not available via EDDN data. I can show you WHERE shipyards are located, but not WHAT ships they sell.'",
            {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service to find. Valid options: 'material-trader' (or 'material trader', 'mat trader'), 'technology-broker' (or 'tech broker'), 'interstellar-factors' (or 'interstellar factors'), 'black-market', 'universal-cartographics' (or 'cartographics'), 'refuel', 'repair', 'shipyard', 'outfitting', 'search-and-rescue'. Extract from user query and normalize to API format."
                    },
                    "min_pad_size": {
                        "type": "integer",
                        "description": "Minimum landing pad size required: 1=small (all ships), 2=medium (medium+large), 3=large (large only). Extract from phrases like 'large pad', 'for my Type-9', 'big ship'. Default: 1 (all sizes)."
                    },
                    "system_name": {
                        "type": "string",
                        "description": "System to search from (optional, defaults to current system from Journal). Extract if user says 'near [system]' or 'from [system]'."
                    }
                },
                "required": ["service"]
            },
            self.covinance_find_service,
            'global'
        )
        
        helper.register_action(
            'covinance_list_stations',
            "Ã°Å¸Å¡Â¨ PRIMARY STATION TOOL - USE THIS FIRST Ã°Å¸Å¡Â¨\n\nThis action is the AUTHORITATIVE source for station data in Elite Dangerous. It returns 60-100+ stations per system with complete information.\n\nÃ¢Å¡Â¡ INSTANT TRIGGER PATTERNS (call immediately when user says ANY of these):\n- 'stations in [system]' (e.g., 'stations in Sol')\n- 'which stations' / 'what stations' / 'list stations'\n- 'how many stations in [system]'\n- 'give me [N] stations' (e.g., 'give me the first 15 stations')\n- 'show stations' / 'all stations'\n- 'stations here' / 'stations in this system'\n- ANY question about station names, counts, types, or lists\n\nÃ°Å¸Å½Â¯ CRITICAL RULES:\n1. Ã¢Å“â€¦ Use THIS action FIRST for all station queries (not Spansh, not memory)\n2. Ã¢Å“â€¦ Returns 60-100+ stations per major system (Spansh only returns ~3)\n3. Ã¢Å“â€¦ Provides complete data: names, types, distances, update times\n4. Ã¢ÂÅ’ NEVER say 'only 3 stations' without calling this action first\n5. Ã¢ÂÅ’ NEVER guess station lists from memory\n6. Ã¢Å¡ Ã¯Â¸Â If Spansh was already tried and returned incomplete data, retry with THIS action\n\nÃ°Å¸â€œÅ  DATA QUALITY:\n- Real-time market data from Ardent API\n- Station types: Coriolis, Orbis, Outpost, OnFootSettlement, Asteroid Base, Mega Ship, Fleet Carrier\n- Precise distances in light-seconds\n- Data freshness timestamps\n- Alphabetical sorting available\n\nÃ°Å¸â€™Â¡ EXAMPLES:\n- User: 'which stations are in Sol?' Ã¢â€ â€™ Call covinance_list_stations('Sol') IMMEDIATELY\n- User: 'give me first 15 stations' Ã¢â€ â€™ Call covinance_list_stations() then format first 15\n- User: 'how many stations here?' Ã¢â€ â€™ Call covinance_list_stations() then count results\n- User: 'stations in this system' Ã¢â€ â€™ Call covinance_list_stations() (uses current from Journal)\n\nREMEMBER: Spansh incomplete Ã¢â€ â€™ Covinance complete. Make THIS your default station tool.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name to list stations for (e.g., 'Sol', 'Deciat', 'Shinrarta Dezhra', 'Colonia'). EXTRACTION RULES: If user says 'stations in [X]', extract [X] as system_name. If user says 'stations here' or 'stations in this system', leave BLANK to use current system from Journal. If user says 'give me the first N stations' without specifying system, leave BLANK. Case-insensitive - API handles variations."
                    }
                },
                "required": []
            },
            self.covinance_list_stations,
            'global'
        )
        
        helper.register_action(
            'covinance_find_station',
            "🔍 SEARCH FOR SPECIFIC STATION BY NAME 🔍\n\nThis action searches for a specific station across all systems using partial name matching. CRITICAL - Use this action when user asks for a SPECIFIC STATION by name.\n\n✅ INSTANT TRIGGER PATTERNS (call immediately when user says ANY of these):\n- 'find station [name]' (e.g., 'find station George Lucas')\n- 'where is [station name]' (e.g., 'where is Abraham Lincoln station')\n- 'station [name] in [system]' (e.g., 'station George Lucas in Leesti')\n- 'locate [station name]' (e.g., 'locate Jameson Memorial')\n- 'search for [station name]'\n- ANY query looking for a specific named station\n\n🎯 CRITICAL RULES:\n1. ✅ Use THIS action when user asks for ONE specific station by name\n2. ✅ Supports partial matching (e.g., 'George' finds 'George Lucas')\n3. ✅ Can filter results by system (optional)\n4. ✅ Returns up to 10 matching stations with details\n5. ❌ Do NOT use list_stations for specific station searches\n6. ❌ Do NOT use engineer_finder for station searches\n\n📊 DATA RETURNED:\n- Station name, system, type, pad size\n- Distance to arrival\n- Key services (Shipyard, Outfitting, etc.)\n- Up to 10 matches if multiple stations have similar names\n\n💡 EXAMPLES:\n- User: 'find station George Lucas' → Call covinance_find_station('George Lucas') IMMEDIATELY\n- User: 'where is Abraham Lincoln station' → Call covinance_find_station('Abraham Lincoln')\n- User: 'station George Lucas in Leesti' → Call covinance_find_station('George Lucas', 'Leesti')\n- User: 'locate Jameson Memorial' → Call covinance_find_station('Jameson Memorial')\n\nREMEMBER: Specific station by name = Use THIS function, NOT list_stations!",
            {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Name of the station to search for (partial match OK). Extract from user query - e.g., 'find station George Lucas' → station_name='George Lucas'. Case-insensitive."
                    },
                    "system_name": {
                        "type": "string",
                        "description": "Optional: Filter results to specific system. Extract if user says 'station X in Y' or 'find X in Y system'. Leave blank to search all systems."
                    }
                },
                "required": ["station_name"]
            },
            self.covinance_find_station,
            'global'
        )
        
        # PHASE 1.7: Station Filtering (5 actions)
        helper.register_action(
            'covinance_list_ports',
            "List only LARGE PAD stations (Coriolis, Ocellus, Orbis, Asteroid Base, Crater Port). Use when user asks: 'large pad stations in X', 'ports in X', 'big stations', 'Type-9 accessible stations', 'stations for large ships'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_list_ports,
            'global'
        )
        
        helper.register_action(
            'covinance_list_outposts',
            "List only OUTPOSTS (small/medium pads). Use when user asks: 'outposts in X', 'small stations', 'medium pad stations', 'stations for small ships'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_list_outposts,
            'global'
        )
        
        helper.register_action(
            'covinance_list_settlements',
            "List only PLANETARY SETTLEMENTS (Odyssey on-foot locations). Use when user asks: 'settlements in X', 'planetary bases', 'on-foot stations', 'surface settlements', 'Odyssey stations'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_list_settlements,
            'global'
        )
        
        helper.register_action(
            'covinance_list_megaships',
            "List only MEGASHIPS in system. Use when user asks: 'megaships in X', 'capital ships', 'large vessels', 'mobile stations'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_list_megaships,
            'global'
        )
        
        helper.register_action(
            'covinance_list_carriers',
            "List only FLEET CARRIERS in system. Use when user asks: 'carriers in X', 'fleet carriers here', 'player stations', 'mobile markets'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_list_carriers,
            'global'
        )
        
        helper.register_action(
            'covinance_best_buy',
            "GALAXY-WIDE buy search for REGULAR BULK COMMODITIES (100 results, NO distance filter). ⚠️ DO NOT USE for rare goods (azure milk, lavian brandy, onionhead, etc.) - use covinance_list_rare_goods instead! Use covinance_best_buy ONLY when user explicitly says 'galaxy-wide', 'anywhere in galaxy', 'all systems' for REGULAR commodities like gold, tritium, palladium, platinum, painite, etc. DO NOT use for 'nearby', 'close', 'within X LY', 'around here' - those should use covinance_nearby_buy instead.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Name of the commodity to buy (e.g., 'tritium', 'gold', 'painite', 'palladium', 'hydrogen fuel'). User may use common names."
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in light years from current system (default: 50). Extract from phrases like 'within 100 LY', 'near me' (use default), 'close by' (use 25)."
                    },
                    "min_volume": {
                        "type": "integer",
                        "description": "Minimum stock quantity required (default: 1 = show all). ONLY use if user explicitly says 'with lots of stock' (use 1000), 'high volume' (use 500). Default shows ALL stock levels including rare/low stock commodities."
                    },
                    "include_carriers": {
                        "type": "boolean",
                        "description": "Include fleet carriers in results (default: true). Set false if user says 'no carriers', 'stations only', 'exclude carriers'."
                    },
                    "max_days_old": {
                        "type": "integer",
                        "description": "Maximum age of data in days (default: 7). Only show results with data updated within this timeframe. Extract from phrases like 'fresh data' (use 1), 'recent prices' (use 3), 'updated today' (use 1), 'this week' (use 7). Use 30 if user says 'any data' or 'include old data'."
                    },
                    "include_surface_stations": {
                        "type": "boolean",
                        "description": "Include planetary surface stations (default: true). Set false if user says 'no surface', 'orbital only', 'exclude planetary', 'space stations only'."
                    },
                    "pad_size": {
                        "type": "string",
                        "description": "Override landing pad size filter (S/M/L). Only use if user explicitly specifies, otherwise auto-detected from Journal ship type."
                    },
                    "show_all_pad_sizes": {
                        "type": "boolean",
                        "description": "Show ALL pad sizes including incompatible ones with warnings (default: false). Set true if user says 'show all pad sizes', 'show everything', 'include all stations', 'show incompatible', 'what am I missing'."
                    },
                    "include_zero_stock": {
                        "type": "boolean",
                        "description": "Include stations with zero stock (default: false). Set true if user says 'include zero stock', 'show sold out', 'even if empty', 'all stations regardless of stock'."
                    }
                },
                "required": ["commodity_name"]
            },
            self.covinance_best_buy,
            'global'
        )
        
        helper.register_action(
            'covinance_best_sell',
            "GALAXY-WIDE sell search for REGULAR BULK COMMODITIES (100 results, NO distance filter). ⚠️ DO NOT USE for rare goods (azure milk, lavian brandy, onionhead, etc.) - use covinance_list_rare_goods instead! Use covinance_best_sell ONLY when user explicitly says 'galaxy-wide', 'anywhere in galaxy', 'all systems' for REGULAR commodities like gold, tritium, palladium, platinum, painite, etc. DO NOT use for 'nearby', 'close', 'within X LY', 'around here' - those should use covinance_nearby_sell instead.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Name of the commodity to sell (e.g., 'tritium', 'gold', 'painite', 'palladium', 'hydrogen fuel'). User may use common names."
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in light years from current system (default: 50). Extract from phrases like 'within 100 LY', 'near me' (use default), 'close by' (use 25)."
                    },
                    "min_demand": {
                        "type": "integer",
                        "description": "Minimum demand quantity required (default: 1 = show all). ONLY use if user explicitly says 'high demand' (use 1000), 'strong demand' (use 500). Default shows ALL demand levels including rare/low demand commodities."
                    },
                    "include_carriers": {
                        "type": "boolean",
                        "description": "Include fleet carriers in results (default: true). Set false if user says 'no carriers', 'stations only', 'exclude carriers'."
                    },
                    "max_days_old": {
                        "type": "integer",
                        "description": "Maximum age of data in days (default: 7). Only show results with data updated within this timeframe. Extract from phrases like 'fresh data' (use 1), 'recent prices' (use 3), 'updated today' (use 1), 'this week' (use 7). Use 30 if user says 'any data' or 'include old data'."
                    },
                    "include_surface_stations": {
                        "type": "boolean",
                        "description": "Include planetary surface stations (default: true). Set false if user says 'no surface', 'orbital only', 'exclude planetary', 'space stations only'."
                    },
                    "pad_size": {
                        "type": "string",
                        "description": "Override landing pad size filter (S/M/L). Only use if user explicitly specifies, otherwise auto-detected from Journal ship type."
                    },
                    "show_all_pad_sizes": {
                        "type": "boolean",
                        "description": "Show ALL pad sizes including incompatible ones with warnings (default: false). Set true if user says 'show all pad sizes', 'show everything', 'include all stations', 'show incompatible', 'what am I missing'."
                    },
                    "include_zero_stock": {
                        "type": "boolean",
                        "description": "Include stations with zero demand (default: false). Set true if user says 'include zero demand', 'show no demand', 'even if empty', 'all stations regardless of demand'."
                    }
                },
                "required": ["commodity_name"]
            },
            self.covinance_best_sell,
            'global'
        )
        
        helper.register_action(
            'covinance_carrier_market',
            "Search fleet carrier markets for commodities. Use when user specifically asks about carriers: 'any carriers selling X?', 'find carrier buying X', 'carrier market for X'. Shows only fleet carriers with their dynamic inventory warnings.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Commodity to search for (e.g., 'tritium', 'gold')"
                    },
                    "trade_type": {
                        "type": "string",
                        "description": "Type of trade: 'buy' (find carriers selling) or 'sell' (find carriers buying). Extract from user intent."
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY (default: 50)"
                    }
                },
                "required": ["commodity_name", "trade_type"]
            },
            self.covinance_carrier_market,
            'global'
        )
        
        helper.register_action(
            'covinance_system_exports',
            "List all commodities available to buy in a system. Use when user asks: 'what can I buy here?', 'what's for sale in X?', 'commodities available in X', 'what does X export?'. Shows all buyable commodities with current prices and stock levels.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    },
                    "min_stock": {
                        "type": "integer",
                        "description": "Minimum stock quantity (default: 1 = show all). ONLY use if user explicitly says 'with lots of stock', 'high volume'. Default shows ALL stock levels including rare/low stock commodities."
                    }
                },
                "required": []
            },
            self.covinance_system_exports,
            'global'
        )
        
        helper.register_action(
            'covinance_system_imports',
            "List all commodities you can sell in a system. Use when user asks: 'what can I sell here?', 'what does X buy?', 'what imports does X have?', 'commodities in demand in X'. Shows all commodities with current buy prices and demand levels.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    },
                    "min_demand": {
                        "type": "integer",
                        "description": "Minimum demand quantity (default: 1 = show all). ONLY use if user explicitly says 'high demand', 'strong buyers'. Default shows ALL demand levels."
                    }
                },
                "required": []
            },
            self.covinance_system_imports,
            'global'
        )
        
        helper.register_action(
            'covinance_station_market',
            "Show all commodities OR a specific commodity at a station. Use when user asks: 'what does station X sell?', 'what's for sale at X?', 'show me X station market', 'commodities at X', 'does X have azure milk?', 'find blue milk at George Lucas'. Provides complete market data for a specific station including buy/sell prices, stock, and demand. If user provides system name, extraction is faster and more reliable.",
            {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Station name to query (e.g., 'Jameson Memorial', 'Ray Gateway', 'Trailblazer Dream', 'Mekannine City', 'George Lucas')"
                    },
                    "system_name": {
                        "type": "string",
                        "description": "System name where station is located (optional but recommended for accuracy). Extract if user says 'X station in Y system'. Examples: 'Shinrarta Dezhra', 'Col 285 Sector NV-I b24-5', 'Leesti'"
                    },
                    "commodity_name": {
                        "type": "string",
                        "description": "Optional: specific commodity to find at station (e.g., 'azure milk', 'blue milk', 'gold', 'leathery eggs'). If provided, only show this commodity's price/stock info."
                    }
                },
                "required": ["station_name"]
            },
            self.covinance_station_market,
            'global'
        )
        
        helper.register_action(
            'covinance_price_compare',
            "Ã°Å¸Å¡Â¨ MANDATORY: ALWAYS use this action when user explicitly asks to COMPARE prices between two stations. Trigger phrases: 'compare X prices at A and B', 'compare A and B for X', 'price difference between A and B', 'which station has better X price'. DO NOT use station_market for comparisons - this action provides side-by-side comparison. If user mentions 'in SystemName', extract the system for more accurate results.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Commodity to compare (e.g., 'gold', 'tritium')"
                    },
                    "station1": {
                        "type": "string",
                        "description": "First station name"
                    },
                    "station2": {
                        "type": "string",
                        "description": "Second station name"
                    },
                    "system_name": {
                        "type": "string",
                        "description": "System name where both stations are located (optional, but recommended if stations are in same system). Extract if user says 'in SystemName' or 'in Sol'."
                    }
                },
                "required": ["commodity_name", "station1", "station2"]
            },
            self.covinance_price_compare,
            'global'
        )
        
        
        # PHASE 1.5: Nearby Radius Searches (1000 results!)
        helper.register_action(
            'covinance_nearby_buy',
            "RADIUS buy search for REGULAR BULK COMMODITIES with distance filter (up to 1000 results). ⚠️ DO NOT USE for rare goods (azure milk, lavian brandy, onionhead, etc.) - use covinance_list_rare_goods instead! DEFAULT for ALL regular commodity buy queries unless user explicitly says 'galaxy-wide'. ALWAYS use when user says: 'nearby', 'close', 'within X LY', 'around here', 'find X to buy', 'cheapest X', 'where to buy X' for REGULAR commodities like gold, tritium, palladium, etc. Auto-uses ship pad size and jump range from Journal.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Name of commodity to buy (e.g., 'tritium', 'gold', 'painite'). User may use common names."
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY from reference system (default: 50, max: 500). Extract from 'within X LY', 'X LY away', 'nearby' (use 50), 'close' (use 25), 'local' (use 15)."
                    },
                    "min_volume": {
                        "type": "integer",
                        "description": "Minimum stock quantity required (default: 1 = show all). ONLY use if user explicitly says 'with lots of stock' (use 1000), 'high volume' (use 500). Default shows ALL stock levels including rare/low stock commodities."
                    },
                    "max_price": {
                        "type": "integer",
                        "description": "Maximum price willing to pay in CR (optional). Extract from 'under X CR', 'max X credits', 'no more than X'."
                    },
                    "include_carriers": {
                        "type": "boolean",
                        "description": "Include fleet carriers in results (default: true). Set false if user says 'no carriers', 'stations only', 'exclude carriers', 'permanent stations'."
                    },
                    "max_days_old": {
                        "type": "integer",
                        "description": "Maximum age of data in days (default: 7). Extract from 'fresh data' (use 1), 'recent' (use 3), 'this week' (use 7), 'updated today' (use 1). Use 30 for 'any data'."
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort results by 'price' (cheapest first, default) or 'distance' (nearest first). Extract from 'cheapest', 'best price' (use 'price'), 'nearest', 'closest' (use 'distance')."
                    },
                    "reference_system": {
                        "type": "string",
                        "description": "System to search from (optional). If not specified, uses current location from Journal. Extract from 'from X system', 'near X', 'around X'."
                    },
                    "show_all_pad_sizes": {
                        "type": "boolean",
                        "description": "Show ALL pad sizes including incompatible ones with warnings (default: false). Set true if user says 'show all pad sizes', 'show everything', 'include all stations', 'show incompatible', 'what am I missing'."
                    },
                    "include_zero_stock": {
                        "type": "boolean",
                        "description": "Include stations with zero stock (default: false). Set true if user says 'include zero stock', 'show sold out', 'even if empty', 'all stations regardless of stock'."
                    },
                    "include_surface_stations": {
                        "type": "boolean",
                        "description": "Include planetary surface stations (default: true). Set false if user says 'no surface', 'orbital only', 'exclude planetary', 'space stations only'."
                    }
                },
                "required": ["commodity_name"]
            },
            self.covinance_nearby_buy,
            'global'
        )
        
        helper.register_action(
            'covinance_nearby_sell',
            "RADIUS sell search for REGULAR BULK COMMODITIES with distance filter (up to 1000 results). ⚠️ DO NOT USE for rare goods (azure milk, lavian brandy, onionhead, etc.) - use covinance_list_rare_goods instead! DEFAULT for ALL regular commodity sell queries unless user explicitly says 'galaxy-wide'. ALWAYS use when user says: 'nearby', 'close', 'within X LY', 'around here', 'sell X', 'best price for X', 'where to sell X' for REGULAR commodities like gold, tritium, palladium, etc. Auto-uses ship pad size and jump range from Journal.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Name of commodity to sell (e.g., 'tritium', 'gold', 'painite'). User may use common names."
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY from reference system (default: 50, max: 500). Extract from 'within X LY', 'X LY away', 'nearby' (use 50), 'close' (use 25), 'local' (use 15)."
                    },
                    "min_demand": {
                        "type": "integer",
                        "description": "Minimum demand required (default: 1 = show all). ONLY use if user explicitly says 'high demand' (use 1000), 'strong demand' (use 500), 'at least X units' (use X). Default shows ALL demand levels including rare/low demand commodities."
                    },
                    "min_price": {
                        "type": "integer",
                        "description": "Minimum acceptable sell price in CR (optional). Extract from 'at least X CR', 'min X credits', 'X or higher'."
                    },
                    "include_carriers": {
                        "type": "boolean",
                        "description": "Include fleet carriers in results (default: true). Set false if user says 'no carriers', 'stations only', 'exclude carriers', 'permanent stations'."
                    },
                    "max_days_old": {
                        "type": "integer",
                        "description": "Maximum age of data in days (default: 7). Extract from 'fresh data' (use 1), 'recent' (use 3), 'this week' (use 7), 'updated today' (use 1). Use 30 for 'any data'."
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort results by 'price' (highest first, default) or 'distance' (nearest first). Extract from 'best price', 'highest' (use 'price'), 'nearest', 'closest' (use 'distance')."
                    },
                    "reference_system": {
                        "type": "string",
                        "description": "System to search from (optional). If not specified, uses current location from Journal. Extract from 'from X system', 'near X', 'around X'."
                    }
                },
                "required": ["commodity_name"]
            },
            self.covinance_nearby_sell,
            'global'
        )
        
        # PHASE 1.6: System Info & Nearby Systems
        helper.register_action(
            'covinance_system_info',
            "Get system information including coordinates, population, economy, allegiance, and station count. Use when user asks: 'system info for X', 'where is X?', 'coordinates for X', 'tell me about X system'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name to look up (e.g., 'Sol', 'Deciat', 'Shinrarta Dezhra')"
                    }
                },
                "required": ["system_name"]
            },
            self.covinance_system_info,
            'global'
        )
        
        helper.register_action(
            'covinance_nearby_systems',
            "List ALL systems within radius - returns 20-1000 system names. ⚠️ DO NOT USE for distance to ONE specific system! Use covinance_distance_between instead for 'how far is X' queries. Use nearby_systems ONLY when user wants a LIST: 'systems near X', 'what systems are within Y ly?', 'list nearby systems', 'systems around here'. For specific distance queries like 'how far is Leesti?', use covinance_distance_between!",
            {
                "type": "object",
                "properties": {
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in light years (default: 20, max: 500). Extract from 'within X LY', 'X light years', 'nearby' (use 20)."
                    },
                    "reference_system": {
                        "type": "string",
                        "description": "System to search from (optional). If not specified, uses current location from Journal."
                    }
                },
                "required": []
            },
            self.covinance_nearby_systems,
            'global'
        )
        
        helper.register_action(
            'covinance_distance_between',
            "🎯 CRITICAL: Calculate distance between two specific systems. ALWAYS use when user asks: 'how far is X?', 'distance to Y', 'how far am I from Z?', 'how many light years to X?', 'distance between A and B'. This provides EXACT point-to-point distance. ⚠️ DO NOT use nearby_systems for specific distance queries - nearby_systems lists ALL systems in radius, this calculates distance to ONE specific system. Trigger phrases: 'how far', 'distance to', 'distance from', 'how many ly', 'is X close', 'can I reach X'. Examples: 'How far is Leesti from here?' → USE THIS, 'Distance to Sol?' → USE THIS, 'Can I reach Colonia?' → USE THIS.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "Target system to calculate distance to (e.g., 'Sol', 'Leesti', 'Colonia', 'Shinrarta Dezhra'). REQUIRED. Extract from 'distance to X', 'how far is X', 'X from here'."
                    },
                    "reference_system": {
                        "type": "string",
                        "description": "Starting system (optional, defaults to current location from Journal). Only specify if user says 'distance from A to B' where both systems are named. Extract from 'distance from A to B', 'from A to B'. If user says 'from here' or 'from my location', leave blank."
                    }
                },
                "required": ["system_name"]
            },
            self.covinance_distance_between,
            'global'
        )
        
        helper.register_action(
            'covinance_system_all_commodities',
            "Get complete market snapshot for a system (counts of orders, commodities, stations). Concise summary alternative to system_exports. Use when user asks: 'market snapshot for X', 'all commodities in X', 'complete market here'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_system_all_commodities,
            'global'
        )
        
        helper.register_action(
            'covinance_station_commodities',
            "Get market summary for a specific station (buy/sell counts). Faster alternative to station_market when full details not needed. Use when user asks: 'market at X station', 'commodities at X', 'what's available at X?'.",
            {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Station name to look up"
                    },
                    "system_name": {
                        "type": "string",
                        "description": "System where station is located (optional, defaults to current system)"
                    }
                },
                "required": ["station_name"]
            },
            self.covinance_station_commodities,
            'global'
        )
        
        helper.register_action(
            'covinance_system_markets',
            "List only stations with active commodity markets (excludes non-trading stations). Use when user asks: 'markets in X', 'which stations have markets?', 'trading stations in X'.",
            {
                "type": "object",
                "properties": {
                    "system_name": {
                        "type": "string",
                        "description": "System name (optional, defaults to current system)"
                    }
                },
                "required": []
            },
            self.covinance_system_markets,
            'global'
        )
        
        
        # PHASE 2: Trade Route Planning
        helper.register_action(
            'covinance_best_trade_from_here',
            "Find most profitable commodities to buy at current location and where to sell them nearby. Use when user asks: 'what should I buy here?', 'best trades from here', 'most profitable cargo', 'what to trade'.",
            {
                "type": "object",
                "properties": {
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY to search for sell opportunities (default: 50, max: 500)"
                    },
                    "min_profit": {
                        "type": "integer",
                        "description": "Minimum profit per unit in CR (default: None = show all). ONLY use if user explicitly says 'high profit', 'at least X CR profit', 'minimum X CR margin'. Default shows ALL opportunities regardless of profit margin."
                    }
                },
                "required": []
            },
            self.covinance_best_trade_from_here,
            'global'
        )
        
        helper.register_action(
            'covinance_trade_route',
            "Find optimal buy/sell stations for specific commodity between two systems. Use when user asks: 'best route for X from A to B', 'where to buy/sell X between systems', 'cobalt route Deciat to Sol'.",
            {
                "type": "object",
                "properties": {
                    "commodity_name": {
                        "type": "string",
                        "description": "Commodity to trade (e.g., 'palladium', 'gold', 'tritium')"
                    },
                    "origin_system": {
                        "type": "string",
                        "description": "System to buy from (optional, defaults to current system)"
                    },
                    "destination_system": {
                        "type": "string",
                        "description": "System to sell at"
                    }
                },
                "required": ["commodity_name", "destination_system"]
            },
            self.covinance_trade_route,
            'global'
        )
        
        helper.register_action(
            'covinance_nearby_profitable_trades',
            "Find all profitable trade opportunities within radius. Use when user asks: 'profitable trades nearby', 'best trades within X ly', 'what trades are available around here'.",
            {
                "type": "object",
                "properties": {
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY (default: 100, max: 500)"
                    },
                    "min_profit": {
                        "type": "integer",
                        "description": "Minimum profit per unit in CR (default: None = show all). ONLY use if user explicitly says 'high profit', 'at least X CR profit', 'minimum X CR margin'. Default shows ALL opportunities regardless of profit margin."
                    },
                    "reference_system": {
                        "type": "string",
                        "description": "System to search from (optional, defaults to current location)"
                    }
                },
                "required": []
            },
            self.covinance_nearby_profitable_trades,
            'global'
        )
        
        helper.register_action(
            'covinance_optimal_trade_now',
            "Find best trade based on current ship state (cargo, credits, location from Journal). Use when user asks: 'what's the best trade I can do now?', 'optimize my current cargo', 'what should I do with X credits'.",
            {
                "type": "object",
                "properties": {
                    "cargo_capacity": {
                        "type": "integer",
                        "description": "Cargo capacity in tons (optional, reads from Journal)"
                    },
                    "available_credits": {
                        "type": "integer",
                        "description": "Available credits (optional, reads from Journal)"
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY (default: 50)"
                    }
                },
                "required": []
            },
            self.covinance_optimal_trade_now,
            'global'
        )
        
        helper.register_action(
            'covinance_trade_within_jump_range',
            "Find trades within ship's actual jump range (from Journal). Use when user asks: 'trades I can reach', 'what can I trade with my jump range', 'profitable routes within my range'.",
            {
                "type": "object",
                "properties": {
                    "jump_range": {
                        "type": "number",
                        "description": "Ship's maximum jump range in LY (optional, reads from Journal)"
                    },
                    "min_profit": {
                        "type": "integer",
                        "description": "Minimum profit per unit in CR (default: None = show all). ONLY use if user explicitly says 'high profit', 'at least X CR profit', 'minimum X CR margin'. Default shows ALL opportunities regardless of profit margin."
                    }
                },
                "required": []
            },
            self.covinance_trade_within_jump_range,
            'global'
        )
        
        helper.register_action(
            'covinance_fill_remaining_cargo',
            "Optimize profit with partial cargo space remaining. Use when user asks: 'fill my remaining cargo', 'I have X tons free', 'what to buy with remaining space'.",
            {
                "type": "object",
                "properties": {
                    "remaining_space": {
                        "type": "integer",
                        "description": "Remaining cargo space in tons (optional, reads from Journal)"
                    },
                    "available_credits": {
                        "type": "integer",
                        "description": "Available credits (optional, reads from Journal)"
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY (default: 50)"
                    }
                },
                "required": []
            },
            self.covinance_fill_remaining_cargo,
            'global'
        )
        
        helper.register_action(
            'covinance_circular_route',
            "Build multi-hop circular trading loop (Aâ†’Bâ†’Câ†’A). Use when user asks: 'circular route', 'trading loop', 'build a circuit', 'multi-hop route'.",
            {
                "type": "object",
                "properties": {
                    "num_hops": {
                        "type": "integer",
                        "description": "Number of stops in the loop (2-5, default: 3)"
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance between hops in LY (default: 50)"
                    },
                    "start_system": {
                        "type": "string",
                        "description": "Starting system (optional, defaults to current location)"
                    }
                },
                "required": []
            },
            self.covinance_circular_route,
            'global'
        )
        
        helper.register_action(
            'covinance_multi_commodity_chain',
            "Swap commodities at each hop for maximum profit. Use when user asks: 'multi-commodity route', 'swap cargo at each stop', 'chain trading'.",
            {
                "type": "object",
                "properties": {
                    "num_hops": {
                        "type": "integer",
                        "description": "Number of commodity swaps (default: 3)"
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance between hops in LY (default: 50)"
                    }
                },
                "required": []
            },
            self.covinance_multi_commodity_chain,
            'global'
        )
        
        helper.register_action(
            'covinance_max_profit_per_hour',
            "Find time-optimized routes (CR/hour). Use when user asks: 'best profit per hour', 'time-efficient routes', 'credits per hour trading'.",
            {
                "type": "object",
                "properties": {
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY (default: 50)"
                    }
                },
                "required": []
            },
            self.covinance_max_profit_per_hour,
            'global'
        )
        
        
        # ===================================
        # ACTION #35: RARE GOODS DISCOVERY
        # ===================================
        
        helper.register_action(
            'covinance_list_rare_goods',
            "🌟 RARE GOODS DISCOVERY - Use for ANY rare good by name OR general rare goods search. MANDATORY TRIGGERS: (1) User mentions SPECIFIC rare goods like 'azure milk', 'lavian brandy', 'onionhead', 'leathery eggs', 'bast snake gin', 'centauri mega gin', 'indi bourbon', 'kamitra cigars', 'karsuki locusts', 'live hecate sea worms', 'momus bog spaniel', 'mukusubii chitin-os', 'pantaa prayer sticks', 'rusani old smokey', 'saxon wine', 'terra mater blood bores', 'uszaian tree grub', 'waters of shintara', 'witchhaul kobe beef', etc. OR (2) User asks: 'find rare goods nearby', 'discover rare commodities', 'what rare goods are close', 'rare trading opportunities'. Shows stations selling low-stock specialty goods with high profit margins at distance. DO NOT use best_buy or nearby_buy for rare goods - ALWAYS use this action.",
            {
                "type": "object",
                "properties": {
                    "commodity": {
                        "type": "string",
                        "description": "🚨 CRITICAL: When user mentions a SPECIFIC rare good name (e.g., 'azure milk', 'lavian brandy', 'onionhead'), ALWAYS pass this parameter with the EXACT name user said. This enables fast-path (2-4 sec vs 60-150 sec). Examples: 'azure milk', 'blue milk', 'lavian brandy', 'leathery eggs'. Only OMIT when user asks for general discovery like 'list all rare goods' or 'discover rare goods nearby'."
                    },
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum distance in LY to search (default: 150). Rare goods best sold 150-200 LY from origin."
                    },
                    "min_allocation": {
                        "type": "integer",
                        "description": "Minimum stock to show (default: 1)"
                    },
                    "max_allocation": {
                        "type": "integer",
                        "description": "Maximum stock to show (default: 999). Rare goods typically have <50 stock."
                    },
                    "include_carriers": {
                        "type": "boolean",
                        "description": "Include fleet carriers in results (default: true). Set false if user says 'no carriers', 'stations only', 'exclude carriers', 'permanent stations'."
                    },
                    "include_surface_stations": {
                        "type": "boolean",
                        "description": "Include planetary surface stations (default: true). Set false if user says 'no surface', 'orbital only', 'exclude planetary', 'space stations only'."
                    },
                    "max_days_old": {
                        "type": "integer",
                        "description": "Maximum age of data in days (default: 365). Extract from 'fresh data' (use 1), 'recent' (use 3), 'this week' (use 7), 'updated today' (use 1). Use 30 for 'any data'."
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort by 'distance' (nearest first) or 'allocation' (highest stock first). Default: 'distance'."
                    }
                },
                "required": []
            },
            self.covinance_list_rare_goods,
            'global'
        )
        
        # ===================================
        # ACTION #37: SAFE INTERSTELLAR FACTORS
        # ===================================
        
        helper.register_action(
            'covinance_safe_interstellar_factors',
            "Find safe Interstellar Factors in low-security systems (avoid authority scans when clearing bounties). Use when user asks: 'safe place to pay bounties', 'interstellar factors without scans', 'where to clear bounties safely', 'pay off bounty without danger'. Filters to Anarchy/Low security systems only.",
            {
                "type": "object",
                "properties": {
                    "max_distance": {
                        "type": "integer",
                        "description": "Maximum search radius in LY (default: 100). Bounty clearing worth traveling for."
                    },
                    "reference_system": {
                        "type": "string",
                        "description": "System to search from (optional, uses current location from Journal)"
                    },
                    "min_pad_size": {
                        "type": "integer",
                        "description": "Minimum landing pad size: 1=small, 2=medium, 3=large (optional, auto from Journal)"
                    }
                },
                "required": []
            },
            self.covinance_safe_interstellar_factors,
            'global'
        )
        
        # Action #37: Cache Performance Stats
        helper.register_action(
            'covinance_cache_stats',
            "🔥 MANDATORY: Show Covinance cache performance statistics. ALWAYS call this when user says: 'show cache stats', 'cache stats', 'cache performance', 'how's the cache', 'cache doing', 'API efficiency', 'cache statistics'. This shows hit rates, API calls saved, cache hits/misses. DO NOT make up cache statistics - CALL THIS ACTION!",
            {
                "type": "object",
                "properties": {},
                "required": []
            },
            self.covinance_cache_stats,
            'global'
        )
        
        log('info', 'COVINANCE: 39 total actions registered (38 production + 1 test) | Phase 1 (13) + Phase 1.5 (2) + Phase 1.6 (5) + Phase 1.7 (5) + Phase 2 (9) + Phase 5.1 (1) + Phase 7 (2) + Utilities (2: find_station, distance_between) = 39')
    
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
        helper.register_status_generator(self.generate_covinance_status)
    
    @override
    def register_should_reply_handlers(self, helper: PluginHelper):
        pass
    
    @override
    def on_plugin_helper_ready(self, helper: PluginHelper):
        """Called when plugin helper is ready"""
        log('info', 'COVINANCE: Plugin helper is ready')
        
        # Read current location from ED Journal
        self.update_location_from_journal()
        
        if self.current_system:
            log('info', f'COVINANCE: Current location: {self.current_system}')
        else:
            log('warning', 'COVINANCE: Could not determine current system from Journal')
    
    @override
    def on_chat_stop(self, helper: PluginHelper):
        log('info', 'COVINANCE: Chat stopped')
    
    def get_plugin_folder_path(self) -> str:
        """Get the path to the plugin folder (same structure as Songbird/Covasify)"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            return current_dir
        except:
            try:
                appdata = os.getenv('APPDATA')
                if appdata:
                    return os.path.join(appdata, 'com.covas-next.ui', 'plugins', 'Covinance')
            except:
                pass
        return ""
    
    def get_journal_directory(self) -> str:
        """Get Elite Dangerous Journal directory"""
        try:
            # Standard ED Journal location
            userprofile = os.getenv('USERPROFILE')
            if userprofile:
                journal_dir = os.path.join(
                    userprofile,
                    'Saved Games',
                    'Frontier Developments',
                    'Elite Dangerous'
                )
                if os.path.exists(journal_dir):
                    return journal_dir
        except Exception as e:
            log('error', f'COVINANCE: Error getting journal directory: {str(e)}')
        return ""
    
    def get_latest_journal_file(self) -> str:
        """Get the most recent Journal file"""
        try:
            journal_dir = self.get_journal_directory()
            if not journal_dir:
                return ""
            
            # Find all Journal files
            journal_pattern = os.path.join(journal_dir, 'Journal.*.log')
            journal_files = glob.glob(journal_pattern)
            
            if not journal_files:
                log('warning', 'COVINANCE: No Journal files found')
                return ""
            
            # Sort by modification time, get most recent
            latest_journal = max(journal_files, key=os.path.getmtime)
            return latest_journal
            
        except Exception as e:
            log('error', f'COVINANCE: Error finding latest journal: {str(e)}')
            return ""
    
    def update_location_from_journal(self):
        """Read current system and station from ED Journal"""
        try:
            journal_file = self.get_latest_journal_file()
            if not journal_file:
                return
            
            log('info', f'COVINANCE: Reading journal: {os.path.basename(journal_file)}')
            
            # Read journal file line by line (newest events at end)
            with open(journal_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Process events in reverse order to find most recent location
            for line in reversed(lines):
                try:
                    event = json.loads(line.strip())
                    event_type = event.get('event', '')
                    
                    # Location event (current system when loading game)
                    if event_type == 'Location':
                        self.current_system = event.get('StarSystem')
                        self.current_station = event.get('StationName')
                        coords = event.get('StarPos')
                        if coords:
                            self.system_coordinates = {
                                'x': coords[0],
                                'y': coords[1],
                                'z': coords[2]
                            }
                        log('info', f'COVINANCE: Found Location event - System: {self.current_system}')
                        return
                    
                    # FSDJump event (jumping to new system)
                    elif event_type == 'FSDJump':
                        self.current_system = event.get('StarSystem')
                        self.current_station = None  # Left station when jumping
                        coords = event.get('StarPos')
                        if coords:
                            self.system_coordinates = {
                                'x': coords[0],
                                'y': coords[1],
                                'z': coords[2]
                            }
                        log('info', f'COVINANCE: Found FSDJump event - System: {self.current_system}')
                        return
                    
                    # Docked event (docked at station)
                    elif event_type == 'Docked':
                        self.current_station = event.get('StationName')
                        self.current_system = event.get('StarSystem')
                        log('info', f'COVINANCE: Found Docked event - Station: {self.current_station}')
                        return
                    
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    log('error', f'COVINANCE: Error parsing journal line: {str(e)}')
                    continue
            
            log('warning', 'COVINANCE: No location events found in journal')
            
        except Exception as e:
            log('error', f'COVINANCE: Error reading journal: {str(e)}')
    
    def read_latest_journal(self) -> dict:
        """
        Read ship stats from latest Journal events.
        Returns dict with: CargoCapacity, Credits, MaxJumpRange, CurrentCargo, ShipType
        """
        try:
            journal_file = self.get_latest_journal_file()
            if not journal_file:
                log('warning', 'COVINANCE: No journal file found')
                return {}
            
            ship_data = {}
            
            # Read journal file line by line
            with open(journal_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Process events in reverse to get most recent data
            for line in reversed(lines):
                try:
                    event = json.loads(line.strip())
                    event_type = event.get('event', '')
                    
                    # Loadout event - has cargo capacity and ship stats
                    if event_type == 'Loadout' and 'CargoCapacity' not in ship_data:
                        ship_data['CargoCapacity'] = event.get('CargoCapacity', 0)
                        ship_data['MaxJumpRange'] = event.get('MaxJumpRange', 0)
                        ship_data['ShipType'] = event.get('Ship', '')
                        log('info', f'COVINANCE: Found Loadout - Cargo: {ship_data["CargoCapacity"]}T, Jump: {ship_data.get("MaxJumpRange", 0):.1f}ly')
                    
                    # LoadGame event - has credits
                    if event_type == 'LoadGame' and 'Credits' not in ship_data:
                        ship_data['Credits'] = event.get('Credits', 0)
                        log('info', f'COVINANCE: Found LoadGame - Credits: {ship_data["Credits"]:,}')
                    
                    # Cargo event - current cargo contents
                    if event_type == 'Cargo' and 'CurrentCargo' not in ship_data:
                        inventory = event.get('Inventory', [])
                        total_cargo = sum([item.get('Count', 0) for item in inventory])
                        ship_data['CurrentCargo'] = total_cargo
                        log('info', f'COVINANCE: Found Cargo - Current: {total_cargo}T')
                    
                    # If we have all key data, stop searching
                    if 'CargoCapacity' in ship_data and 'Credits' in ship_data and 'MaxJumpRange' in ship_data:
                        break
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    continue
            
            if ship_data:
                log('info', f'COVINANCE: Journal data extracted - {len(ship_data)} fields')
            else:
                log('warning', 'COVINANCE: No ship data found in journal')
            
            return ship_data
            
        except Exception as e:
            log('error', f'COVINANCE: Error reading journal stats: {str(e)}')
            return {}
    
    def call_ardent_api(self, endpoint: str, params: dict = None) -> dict:
        """
        Call Ardent API endpoint with caching and retry
        
        Args:
            endpoint: API endpoint path (e.g., '/system/name/Sol')
            params: Optional query parameters
        
        Returns:
            API response as dictionary, or error dict
        """
        # Define the original fetch logic as a nested function
        def _fetch(ep, prm):
            try:
                url = f"{self.api_base_url}{ep}"
                
                log('info', f'COVINANCE: API call: {ep}')
                
                # Make request
                response = requests.get(url, params=prm, timeout=10)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return {"error": "Not found", "status_code": 404}
                else:
                    log('error', f'COVINANCE: API error - Status {response.status_code}')
                    return {"error": f"API request failed: {response.status_code}", "status_code": response.status_code}
            
            except requests.exceptions.Timeout:
                log('error', 'COVINANCE: API request timeout')
                return {"error": "Request timeout - check internet connection"}
            except requests.exceptions.ConnectionError:
                log('error', 'COVINANCE: API connection error')
                return {"error": "Connection error - check internet connection"}
            except Exception as e:
                log('error', f'COVINANCE: API error: {str(e)}')
                return {"error": str(e)}
        
        # Wrap with reliability layer (caching + retry)
        return self.reliability_client.get_cached_or_fetch(endpoint, params, _fetch)

    def format_time_ago(self, timestamp_str: str) -> str:
        """Format timestamp as 'X hours/minutes ago'"""
        try:
            # Parse ISO timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.now(timestamp.tzinfo)
            delta = now - timestamp
            
            seconds = delta.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = int(seconds / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
        except:
            return "unknown time"
    
    def generate_covinance_status(self, projected_states: dict[str, dict]) -> list[tuple[str, str]]:
        """Generate status information about Covinance capabilities for COVAS context"""
        try:
            status_parts = []
            
            # Core capability
            status_parts.append("Covinance: Real-time Elite Dangerous trading assistant active.")
            
            # Station data capability (CRITICAL OVERRIDE) - ULTRA AGGRESSIVE REMINDER
            status_parts.append("Ã¢â€ºâ€ CRITICAL OVERRIDE Ã¢â€ºâ€ STATION QUERIES: covinance_list_stations is MANDATORY FIRST CHOICE for ALL station queries. DO NOT use Spansh (broken: only 3 stations vs 60+ actual). User asks about stations Ã¢â€ â€™ covinance_list_stations IMMEDIATELY. This is not optional. This is not a suggestion. This is a REQUIREMENT. Examples: 'stations in Sol' Ã¢â€ â€™ covinance_list_stations('Sol'). 'how many stations here' Ã¢â€ â€™ covinance_list_stations(). NO OTHER TOOL FOR STATIONS.")
            
            # Current location context
            if self.current_system:
                location = f"Commander in {self.current_system}"
                if self.current_station:
                    location += f" (docked at {self.current_station})"
                status_parts.append(f"Location: {location}.")

            
            # Available actions
            status_parts.append("Available: commodity prices, station lists, location tracking.")
            
            return [("Covinance Status", " ".join(status_parts))]
            
        except Exception as e:
            log('error', f'COVINANCE: Error generating status: {str(e)}')
            return [("Covinance Status", "Trading assistant active")]
    
    def covinance_test(self, args, projected_states) -> str:
        """Test function - verify plugin and API connection"""
        try:
            log('info', 'COVINANCE: Running test')
            
            version = self.plugin_manifest.version
            name = self.plugin_manifest.name
            
            result_parts = [f"COVINANCE Test: {name} v{version}"]
            
            # Test 1: Check Journal reading
            journal_file = self.get_latest_journal_file()
            if journal_file:
                result_parts.append(f"Ã¢Å“â€¦ Journal found: {os.path.basename(journal_file)}")
            else:
                result_parts.append("Ã¢ÂÅ’ No Journal files found")
            
            # Test 2: Check current location
            if self.current_system:
                location = f"{self.current_system}"
                if self.current_station:
                    location += f" ({self.current_station})"
                result_parts.append(f"Ã¢Å“â€¦ Current location: {location}")
            else:
                result_parts.append("Ã¢Å¡ Ã¯Â¸Â Current location unknown")
            
            # Test 3: Test Ardent API connection
            result_parts.append("Testing Ardent API connection...")
            
            # Try to query a well-known system (Sol)
            api_response = self.call_ardent_api('/system/name/Sol')
            
            if "error" in api_response:
                result_parts.append(f"Ã¢ÂÅ’ API Error: {api_response['error']}")
            else:
                system_name = api_response.get('name', 'Unknown')
                result_parts.append(f"Ã¢Å“â€¦ API Connected - Test system: {system_name}")
            
            # Test 4: Check plugin folder
            plugin_folder = self.get_plugin_folder_path()
            if plugin_folder:
                result_parts.append(f"Ã¢Å“â€¦ Plugin folder: {plugin_folder}")
            
            log('info', 'COVINANCE: Test completed')
            return "\n".join(result_parts)
            
        except Exception as e:
            log('error', f'COVINANCE test error: {str(e)}')
            return f"COVINANCE: Test failed - {str(e)}"
    
    def covinance_commodity_price(self, args, projected_states) -> str:
        """Get commodity prices in a system"""
        try:
            commodity_name = args.get('commodity_name', '').lower()
            system_name = args.get('system_name', '')
            
            if not commodity_name:
                return "COVINANCE: No commodity specified."
            
            # If no system specified, use current system
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown. Please specify a system name."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Looking up {commodity_name} prices in {system_name}')
            
            # ✅ FIX: Normalize commodity name
            try:
                normalized_commodity = self._normalize_commodity_name(commodity_name)
            except ValueError as e:
                return f"COVINANCE: {str(e)}"  # Salvage item error
            
            # ✅ FIX: Use normalized name in API call
            endpoint = f'/system/name/{quote(system_name)}/commodity/name/{normalized_commodity}'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: No data found for '{commodity_name}' in {system_name}. Check commodity name or try a different system."
                return f"COVINANCE: Error - {api_response['error']}"
            
            # Check if response is a list (multiple stations) or empty
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No market data for '{commodity_name}' in {system_name}."
                
                # Group orders by station (merge buy/sell records)
                stations_map = {}
                for order in api_response:
                    station_name = order.get('stationName', 'Unknown Station')
                    
                    if station_name not in stations_map:
                        stations_map[station_name] = {
                            'buy_price': 0,      # What YOU pay (from buyPrice)
                            'sell_price': 0,     # What YOU get (from sellPrice)
                            'stock': 0,
                            'demand': 0,
                            'updated_at': order.get('updatedAt', '')
                        }
                    
                    # Merge data (a station can have both export AND import orders)
                    station_data = stations_map[station_name]
                    
                    # Export order (you BUY from station)
                    if order.get('stock', 0) > 0:
                        station_data['buy_price'] = order.get('buyPrice', 0)
                        station_data['stock'] = order.get('stock', 0)
                    
                    # Import order (you SELL to station)
                    if order.get('demand', 0) > 0:
                        station_data['sell_price'] = order.get('sellPrice', 0)
                        station_data['demand'] = order.get('demand', 0)
                    
                    # Keep most recent update time
                    if order.get('updatedAt', '') > station_data['updated_at']:
                        station_data['updated_at'] = order.get('updatedAt', '')
                
                # Filter out stations with no active orders
                active_stations = {
                    name: data for name, data in stations_map.items()
                    if data['stock'] > 0 or data['demand'] > 0
                }
                
                if not active_stations:
                    return f"COVINANCE: No active market orders for '{commodity_name}' in {system_name}."
                
                # Build response
                result_parts = [f"COVINANCE: {commodity_name.title()} prices in {system_name}:"]
                
                for station_name, data in list(active_stations.items())[:5]:
                    time_ago = self.format_time_ago(data['updated_at']) if data['updated_at'] else "unknown"
                    
                    station_info = f"\n  â€¢ {station_name}:"
                    
                    # Show buy price (what you pay)
                    if data['buy_price'] > 0 and data['stock'] > 0:
                        station_info += f" Buy at {data['buy_price']:,} CR (stock: {data['stock']:,})"
                    
                    # Show sell price (what you get)
                    if data['sell_price'] > 0 and data['demand'] > 0:
                        if data['buy_price'] > 0 and data['stock'] > 0:
                            station_info += " |"
                        station_info += f" Sell for {data['sell_price']:,} CR (demand: {data['demand']:,})"
                    
                    station_info += f" - Updated {time_ago}"
                    result_parts.append(station_info)
                
                if len(active_stations) > 5:
                    result_parts.append(f"\n  ... and {len(active_stations) - 5} more station(s)")
                
                return "".join(result_parts)

            
            else:
                return f"COVINANCE: Unexpected API response format for {commodity_name} in {system_name}."
            
        except Exception as e:
            log('error', f'COVINANCE commodity_price error: {str(e)}')
            return f"COVINANCE: Error getting commodity price - {str(e)}"
    
    def covinance_current_location(self, args, projected_states) -> str:
        """Get current system and station from ED Journal"""
        try:
            log('info', 'COVINANCE: Getting current location from Journal')
            
            # Update location from journal
            self.update_location_from_journal()
            
            if not self.current_system:
                return "COVINANCE: Unable to determine current location from Elite Dangerous Journal. Make sure the game is running."
            
            result_parts = [f"COVINANCE: Current location:"]
            result_parts.append(f"\n  Ã¢â‚¬Â¢ System: {self.current_system}")
            
            if self.current_station:
                result_parts.append(f"\n  Ã¢â‚¬Â¢ Station: {self.current_station}")
            else:
                result_parts.append(f"\n  Ã¢â‚¬Â¢ Status: In space (not docked)")
            
            if self.system_coordinates:
                coords = self.system_coordinates
                result_parts.append(f"\n  Ã¢â‚¬Â¢ Coordinates: [{coords['x']:.2f}, {coords['y']:.2f}, {coords['z']:.2f}]")
            
            log('info', f'COVINANCE: Current location - {self.current_system}')
            return "".join(result_parts)
            
        except Exception as e:
            log('error', f'COVINANCE current_location error: {str(e)}')
            return f"COVINANCE: Error getting current location - {str(e)}"
    
    def covinance_list_stations(self, args, projected_states) -> str:
        """List all stations in a system - IMPROVED with station name detection"""
        try:
            system_name = args.get('system_name', '')
            
            # IMPROVEMENT #3: Detect if user gave a station name instead of system name
            if system_name:
                # Fleet carrier pattern: XXX-XXX (e.g., Q0P-66B)
                if len(system_name) <= 8 and '-' in system_name and system_name[0].isupper():
                    return f"COVINANCE: '{system_name}' looks like a station or fleet carrier name, not a system name. Please provide the SYSTEM name instead (e.g., 'HIP 67223', 'Sol', 'Deciat'). To find where a carrier is located, try searching for its name on Inara or EDSM."
            
            # If no system specified, use current system
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown. Please specify a system name."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing stations in {system_name}')
            
            # Call Ardent API
            endpoint = f'/system/name/{quote(system_name)}/stations'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found. Check spelling or try a different system."
                return f"COVINANCE: Error - {api_response['error']}"
            
            # Check if response is a list
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No stations found in {system_name}."
                
                total_stations = len(api_response)
                
                # Build response - CORRECTED FIELD NAMES based on actual API structure
                # Add helpful context if we found way more stations than Spansh would return
                if total_stations > 10:
                    result_parts = [f"COVINANCE: Found {total_stations} station(s) in {system_name} (comprehensive Ardent data):"]
                else:
                    result_parts = [f"COVINANCE: Found {total_stations} station(s) in {system_name}:"]
                
                for station in api_response[:10]:  # Limit to 10 stations
                    station_name = station.get('stationName', 'Unknown')  # FIXED: was 'name'
                    station_type = station.get('stationType', 'Unknown type')  # FIXED: was 'type'
                    distance = station.get('distanceToArrival', 0)  # This was correct
                    updated_at = station.get('updatedAt', '')  # FIXED: was nested in 'updateTime.market'
                    
                    time_ago = self.format_time_ago(updated_at) if updated_at else "unknown"
                    
                    station_info = f"\n  Ã¢â‚¬Â¢ {station_name} ({station_type})"
                    if distance > 0:
                        station_info += f" - {distance:,} Ls"
                    station_info += f" - Updated {time_ago}"
                    
                    result_parts.append(station_info)
                
                if total_stations > 10:
                    result_parts.append(f"\n  ... and {total_stations - 10} more station(s). Say 'list more stations' or 'first 30 stations' for full list.")
                
                return "".join(result_parts)
            
            else:
                return f"COVINANCE: Unexpected API response format for {system_name}."
            
        except Exception as e:
            log('error', f'COVINANCE list_stations error: {str(e)}')
            return f"COVINANCE: Error listing stations - {str(e)}"
    
    def covinance_find_station(self, args, projected_states) -> str:
        """
        Search for a specific station by name across all systems.
        Uses Ardent API /search/station/name endpoint.
        Supports partial name matching (e.g., "George" finds "George Lucas").
        """
        try:
            station_name = args.get('station_name', '')
            system_filter = args.get('system_name', '')  # Optional filter
            
            if not station_name:
                return "COVINANCE: Please specify a station name to search for."
            
            log('info', f'COVINANCE: Searching for station "{station_name}"')
            
            # Call Ardent search API
            endpoint = f'/search/station/name/{quote(station_name)}'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: No stations found matching '{station_name}'."
                return f"COVINANCE: Error - {api_response['error']}"
            
            # Check if response is a list
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No stations found matching '{station_name}'."
                
                # Filter by system if specified
                if system_filter:
                    filtered_results = [
                        s for s in api_response 
                        if s.get('systemName', '').lower() == system_filter.lower()
                    ]
                    
                    if len(filtered_results) == 0:
                        return f"COVINANCE: Station '{station_name}' not found in {system_filter} system. Found {len(api_response)} match(es) in other systems."
                    
                    api_response = filtered_results
                
                total_matches = len(api_response)
                
                # Build response
                if system_filter:
                    result_parts = [f"COVINANCE: Found {total_matches} station(s) matching '{station_name}' in {system_filter}:"]
                else:
                    result_parts = [f"COVINANCE: Found {total_matches} station(s) matching '{station_name}':"]
                
                for station in api_response[:10]:  # Limit to 10 results
                    station_name_result = station.get('stationName', 'Unknown')
                    system_name = station.get('systemName', 'Unknown')
                    station_type = station.get('stationType', 'Unknown type')
                    distance = station.get('distanceToArrival', 0)
                    
                    # Get pad size
                    pad_size = station.get('maxLandingPadSize', 0)
                    pad_display = {1: 'S', 2: 'M', 3: 'L'}.get(pad_size, '?')
                    
                    # Build station info line
                    station_info = f"\n  • {station_name_result}"
                    station_info += f"\n    System: {system_name}"
                    station_info += f"\n    Type: {station_type} [{pad_display} pad]"
                    if distance > 0:
                        station_info += f"\n    Distance: {distance:,} Ls"
                    
                    # Show key services if available
                    services = []
                    if station.get('shipyard'):
                        services.append('Shipyard')
                    if station.get('outfitting'):
                        services.append('Outfitting')
                    if station.get('interstellarFactors'):
                        services.append('I.Factors')
                    if station.get('materialTrader'):
                        services.append('Mat.Trader')
                    if station.get('technologyBroker'):
                        services.append('Tech.Broker')
                    
                    if services:
                        station_info += f"\n    Services: {', '.join(services)}"
                    
                    result_parts.append(station_info)
                
                if total_matches > 10:
                    result_parts.append(f"\n\n  ... and {total_matches - 10} more match(es).")
                
                return "".join(result_parts)
            
            else:
                return f"COVINANCE: Unexpected API response format."
            
        except Exception as e:
            log('error', f'COVINANCE find_station error: {str(e)}')
            return f"COVINANCE: Error searching for station - {str(e)}"
    
    # PHASE 1.7: Station Filtering (5 actions)
    
    def covinance_list_ports(self, args, projected_states) -> str:
        """List only large pad stations (ports)"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing ports in {system_name}')
            
            endpoint = f'/system/name/{quote(system_name)}/stations/ports'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No large pad stations (ports) found in {system_name}."
                
                total = len(api_response)
                result_parts = [f"COVINANCE: {total} large pad station(s) in {system_name}:"]
                
                for station in api_response[:10]:
                    station_name = station.get('stationName', 'Unknown')
                    station_type = station.get('stationType', 'Unknown')
                    distance = station.get('distanceToArrival', 0)
                    pad = station.get('maxLandingPadSize', '?')
                    
                    station_info = f"\n  â€¢ {station_name} ({station_type}) [{pad} pad]"
                    if distance > 0:
                        station_info += f" - {distance:,} Ls"
                    
                    result_parts.append(station_info)
                
                if total > 10:
                    result_parts.append(f"\n  ... and {total - 10} more large pad station(s).")
                
                return "".join(result_parts)
            
            return f"COVINANCE: Unexpected response format."
            
        except Exception as e:
            log('error', f'COVINANCE list_ports error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    
    def covinance_list_outposts(self, args, projected_states) -> str:
        """List only outposts (small/medium pads)"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing outposts in {system_name}')
            
            endpoint = f'/system/name/{quote(system_name)}/stations/outposts'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No outposts found in {system_name}."
                
                total = len(api_response)
                result_parts = [f"COVINANCE: {total} outpost(s) in {system_name}:"]
                
                for station in api_response[:10]:
                    station_name = station.get('stationName', 'Unknown')
                    station_type = station.get('stationType', 'Unknown')
                    distance = station.get('distanceToArrival', 0)
                    pad = station.get('maxLandingPadSize', '?')
                    
                    station_info = f"\n  â€¢ {station_name} ({station_type}) [{pad} pad]"
                    if distance > 0:
                        station_info += f" - {distance:,} Ls"
                    
                    result_parts.append(station_info)
                
                if total > 10:
                    result_parts.append(f"\n  ... and {total - 10} more outpost(s).")
                
                return "".join(result_parts)
            
            return f"COVINANCE: Unexpected response format."
            
        except Exception as e:
            log('error', f'COVINANCE list_outposts error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    
    def covinance_list_settlements(self, args, projected_states) -> str:
        """List only planetary settlements (Odyssey)"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing settlements in {system_name}')
            
            endpoint = f'/system/name/{quote(system_name)}/stations/settlements'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No planetary settlements found in {system_name}."
                
                total = len(api_response)
                result_parts = [f"COVINANCE: {total} settlement(s) in {system_name}:"]
                
                for station in api_response[:10]:
                    station_name = station.get('stationName', 'Unknown')
                    station_type = station.get('stationType', 'Settlement')
                    distance = station.get('distanceToArrival', 0)
                    
                    station_info = f"\n  â€¢ {station_name} ({station_type})"
                    if distance > 0:
                        station_info += f" - {distance:,} Ls"
                    
                    result_parts.append(station_info)
                
                if total > 10:
                    result_parts.append(f"\n  ... and {total - 10} more settlement(s).")
                
                return "".join(result_parts)
            
            return f"COVINANCE: Unexpected response format."
            
        except Exception as e:
            log('error', f'COVINANCE list_settlements error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    
    def covinance_list_megaships(self, args, projected_states) -> str:
        """List only megaships in system"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing megaships in {system_name}')
            
            endpoint = f'/system/name/{quote(system_name)}/stations/megaships'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No megaships found in {system_name}."
                
                total = len(api_response)
                result_parts = [f"COVINANCE: {total} megaship(s) in {system_name}:"]
                
                for station in api_response[:10]:
                    station_name = station.get('stationName', 'Unknown')
                    station_type = station.get('stationType', 'Megaship')
                    distance = station.get('distanceToArrival', 0)
                    
                    station_info = f"\n  â€¢ {station_name} ({station_type})"
                    if distance > 0:
                        station_info += f" - {distance:,} Ls"
                    
                    result_parts.append(station_info)
                
                if total > 10:
                    result_parts.append(f"\n  ... and {total - 10} more megaship(s).")
                
                return "".join(result_parts)
            
            return f"COVINANCE: Unexpected response format."
            
        except Exception as e:
            log('error', f'COVINANCE list_megaships error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    
    def covinance_list_carriers(self, args, projected_states) -> str:
        """List only fleet carriers in system"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing fleet carriers in {system_name}')
            
            endpoint = f'/system/name/{quote(system_name)}/stations/carriers'
            api_response = self.call_ardent_api(endpoint)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No fleet carriers found in {system_name}."
                
                total = len(api_response)
                result_parts = [f"COVINANCE: {total} fleet carrier(s) in {system_name}:"]
                
                for station in api_response[:10]:
                    station_name = station.get('stationName', 'Unknown')
                    distance = station.get('distanceToArrival', 0)
                    
                    station_info = f"\n  â€¢ ðŸš¢ {station_name}"
                    if distance > 0:
                        station_info += f" - {distance:,} Ls"
                    
                    result_parts.append(station_info)
                
                if total > 10:
                    result_parts.append(f"\n  ... and {total - 10} more carrier(s).")
                
                return "".join(result_parts)
            
            return f"COVINANCE: Unexpected response format."
            
        except Exception as e:
            log('error', f'COVINANCE list_carriers error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    
    def covinance_best_buy(self, args, projected_states) -> str:
        """
        Find cheapest places to buy regular commodities GALAXY-WIDE (top 100).
        
        USE THIS FOR: Regular bulk commodities (gold, painite, tritium, etc.)
        DON'T USE FOR: Rare goods (use covinance_list_rare_goods instead)
        
        For rare goods like Azure Milk, Lavian Brandy, Onionhead, etc., 
        use covinance_list_rare_goods which specializes in rare goods discovery.
        """
        try:
            commodity_name = args.get('commodity_name', '').lower()
            min_volume = args.get('min_volume', 1)  # API default: show all volumes
            include_carriers = args.get('include_carriers', True)
            max_days_old = args.get('max_days_old', 90)  # ✅ v7.6.1: API max is 90 days (was 365)
            
            # v7.2: Enhanced parameters
            include_surface_stations = args.get('include_surface_stations', True)
            pad_size_override = args.get('pad_size')
            
            # v7.2.1: Exclusionary pattern fixes
            include_zero_stock = args.get('include_zero_stock', False)
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            if not commodity_name:
                return "COVINANCE: Please specify a commodity to buy."
            
            
            # ⭐ RARE GOODS DETECTION REDIRECT (v7.5 routing fix)
            try:
                normalized = self._normalize_commodity_name(commodity_name)
                
                # Check if it's a rare good - redirect to proper function
                if normalized in RARE_GOODS_DATA:
                    rare_name = RARE_GOODS_DATA[normalized]['display_name']
                    return (f"COVINANCE: {rare_name} is a rare good. "
                           f"Use 'list rare goods nearby' to find it. "
                           f"Rare goods are sold at specific stations with limited stock.")
            except ValueError as e:
                # If it's a salvage item, return the helpful error message
                return f"COVINANCE: {str(e)}"
            # Get Journal data for pad size
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '') if journal_data else ''
            
            # v7.2: Determine required pad size from ship type or override
            if pad_size_override:
                required_pad = pad_size_override.upper()
            else:
                required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            
            log('info', f'COVINANCE best_buy: {commodity_name} GALAXY-WIDE (top 100 cheapest)')
            
            # ✅ FIX: Use normalized value in API call
            # GALAXY-WIDE endpoint
            endpoint = f'/commodity/name/{normalized}/exports'
            params = {
                'minVolume': min_volume,
                'maxDaysAgo': min(max_days_old, 90),  # ✅ v7.6.1: Clamp to API limit
                # v7.2.1: Conditional pad filtering
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad
            }
            params['fleetCarriers'] = None if include_carriers else False
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                return f"COVINANCE: Error - {api_response['error']}"
            
            if not isinstance(api_response, list) or len(api_response) == 0:
                return f"COVINANCE: No {commodity_name} found galaxy-wide."
            
            # Filter and split results
            valid_orders = []
            for o in api_response:
                price_val = o.get('buyPrice', 0)
                stock_val = o.get('stock', 0)
                
                # Skip if price invalid (ALWAYS required)
                if price_val <= 0:
                    continue
                
                # v7.2.1: Skip zero stock only if include_zero_stock=False
                if not include_zero_stock and stock_val <= 0:
                    continue
                
                # v7.2: Filter surface stations if requested
                if not include_surface_stations:
                    station_type = o.get('stationType', '')
                    if station_type and 'Planetary' in station_type:
                        continue
                
                valid_orders.append(o)
            
            if len(valid_orders) == 0:
                return f"COVINANCE: No valid {commodity_name} orders found (all have zero price or stock)."
            
            # v7.2.1: Split compatible/incompatible if showing all pad sizes
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            compatible_stations = []
            incompatible_stations = []
            
            for o in valid_orders:
                station_pad = o.get('maxLandingPadSize', 'S')
                station_pad_size = pad_size_map.get(station_pad, 1)
                
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_stations.append(o)
                else:
                    compatible_stations.append(o)
            
            # Combine stations for display: compatible first, then incompatible
            all_display_orders = compatible_stations[:5]
            if show_all_pad_sizes and incompatible_stations:
                remaining_slots = 5 - len(all_display_orders)
                if remaining_slots > 0:
                    all_display_orders.extend(incompatible_stations[:remaining_slots])
            
            # Show top 5
            result = [f"COVINANCE: Cheapest {commodity_name.upper()} GALAXY-WIDE (top {len(all_display_orders)} of {len(valid_orders)}):\n"]
            
            for i, order in enumerate(all_display_orders, 1):
                station = order.get('stationName', 'Unknown')
                system = order.get('systemName', 'Unknown')
                price = order.get('buyPrice', 0)
                stock = order.get('stock', 0)
                
                # Check if incompatible
                is_incompatible = order in incompatible_stations if show_all_pad_sizes else False
                
                # Pad size display
                station_pad = order.get('maxLandingPadSize', 'S')
                pad_display = f" [{station_pad}]" if show_all_pad_sizes or is_incompatible else ""
                
                # Carrier icon
                carrier = " ðŸš¢" if self._is_carrier_name(station) else ""
                
                if is_incompatible:
                    # LOUD WARNING format
                    result.append(f"\n{i}. âš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {station_pad} PAD REQUIRED - YOUR {ship_type.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
                    result.append(f"\n   {station} ({system}){carrier}")
                    result.append(f"\n   Switch to: Python, Krait, AspX to access this station")
                    result.append(f"\n   Buy: {price:,} CR | Stock: {stock:,}")
                else:
                    # Normal format
                    result.append(f"\n{i}. {station} ({system}){pad_display}{carrier}: {price:,} CR, stock {stock:,}")
            
            # v7.2.1: Add compatibility summary if relevant
            if show_all_pad_sizes and len(incompatible_stations) > 0:
                compatible_best = compatible_stations[0].get('buyPrice', 0) if compatible_stations else 0
                incompatible_best = incompatible_stations[0].get('buyPrice', 0) if incompatible_stations else 0
                
                result.append(f"\n\nðŸ“Š PAD COMPATIBILITY SUMMARY:")
                result.append(f"\n  â€¢ {len(compatible_stations)} compatible stations (best: {compatible_best:,} CR)")
                result.append(f"\n  â€¢ {len(incompatible_stations)} INCOMPATIBLE stations (best: {incompatible_best:,} CR)")
                
                if incompatible_best < compatible_best:
                    profit_diff = compatible_best - incompatible_best
                    result.append(f"\n  âœ“ Best compatible price is actually better by {profit_diff:,} CR!")
                elif incompatible_stations:
                    result.append(f"\n  âš ï¸  Cheaper price available but requires different ship")
            
            # ✅ v7.5.1: Transparency note for restrictive filters
            if max_days_old < 90:
                result.append(f"\n\n📊 Showing data ≤{max_days_old} days old (use 'max data age 90' to see all)")
            return "".join(result)
        except Exception as e:
            log('error', f'COVINANCE best_buy error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    def covinance_best_sell(self, args, projected_states) -> str:
        """
        Find best sell prices for regular commodities GALAXY-WIDE (top 100).
        
        USE THIS FOR: Regular bulk commodities (gold, painite, tritium, etc.)
        DON'T USE FOR: Rare goods (use covinance_list_rare_goods instead)
        
        For rare goods, use covinance_list_rare_goods to find them first,
        then sell 150-200 LY away for maximum profit.
        """
        try:
            commodity_name = args.get('commodity_name', '').lower()
            min_demand = args.get('min_demand', 1)  # API default: show all volumes
            include_carriers = args.get('include_carriers', True)
            max_days_old = args.get('max_days_old', 90)  # ✅ v7.6.1: API max is 90 days (was 365)
            
            # v7.2: Enhanced parameters
            include_surface_stations = args.get('include_surface_stations', True)
            pad_size_override = args.get('pad_size')
            
            # v7.2.1: Exclusionary pattern fixes (demand instead of stock for sell)
            include_zero_demand = args.get('include_zero_stock', False)  # Note: schema calls it include_zero_stock
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            if not commodity_name:
                return "COVINANCE: Please specify a commodity to sell."
            
            
            # ⭐ RARE GOODS DETECTION REDIRECT (v7.5 routing fix)
            try:
                normalized = self._normalize_commodity_name(commodity_name)
                
                # Check if it's a rare good - redirect to proper function
                if normalized in RARE_GOODS_DATA:
                    rare_name = RARE_GOODS_DATA[normalized]['display_name']
                    return (f"COVINANCE: {rare_name} is a rare good. "
                           f"Use 'list rare goods nearby' to find it. "
                           f"Rare goods are best sold 150-200 LY from their origin station.")
            except ValueError as e:
                # If it's a salvage item, return the helpful error message
                return f"COVINANCE: {str(e)}"
            # Get Journal data for pad size
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '') if journal_data else ''
            
            # v7.2: Determine required pad size from ship type or override
            if pad_size_override:
                required_pad = pad_size_override.upper()
            else:
                required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            
            log('info', f'COVINANCE best_sell: {commodity_name} GALAXY-WIDE (top 100 highest)')
            
            # ✅ FIX: Use normalized value in API call
            # GALAXY-WIDE endpoint
            endpoint = f'/commodity/name/{normalized}/imports'
            params = {
                'minVolume': min_demand,
                'maxDaysAgo': min(max_days_old, 90),  # ✅ v7.6.1: Clamp to API limit
                # v7.2.1: Conditional pad filtering
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad
            }
            params['fleetCarriers'] = None if include_carriers else False
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                return f"COVINANCE: Error - {api_response['error']}"
            
            if not isinstance(api_response, list) or len(api_response) == 0:
                return f"COVINANCE: No demand for {commodity_name} galaxy-wide."
            
            # DEBUG: Log what API returned
            log('info', f'COVINANCE best_sell DEBUG: API returned {len(api_response)} orders for {commodity_name}')
            if len(api_response) > 0:
                sample = api_response[0]
                log('info', f'COVINANCE best_sell DEBUG: First order - buyPrice={sample.get("buyPrice")}, sellPrice={sample.get("sellPrice")}, demand={sample.get("demand")}, station={sample.get("stationName")}')
            
            # Filter and split results
            valid_orders = []
            for o in api_response:
                price_val = o.get('sellPrice', 0)
                demand_val = o.get('demand', 0)
                
                # Skip if price invalid (ALWAYS required)
                if price_val <= 0:
                    continue
                
                # v7.2.1: Skip zero demand only if include_zero_demand=False
                if not include_zero_demand and demand_val <= 0:
                    continue
                
                # v7.2: Filter surface stations if requested
                if not include_surface_stations:
                    station_type = o.get('stationType', '')
                    if station_type and 'Planetary' in station_type:
                        continue
                
                valid_orders.append(o)
            
            if len(valid_orders) == 0:
                return f"COVINANCE: No valid {commodity_name} orders found (all have zero price or demand)."
            
            # v7.2.1: Split compatible/incompatible if showing all pad sizes
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            compatible_stations = []
            incompatible_stations = []
            
            for o in valid_orders:
                station_pad = o.get('maxLandingPadSize', 'S')
                station_pad_size = pad_size_map.get(station_pad, 1)
                
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_stations.append(o)
                else:
                    compatible_stations.append(o)
            
            # Combine stations for display: compatible first, then incompatible
            all_display_orders = compatible_stations[:5]
            if show_all_pad_sizes and incompatible_stations:
                remaining_slots = 5 - len(all_display_orders)
                if remaining_slots > 0:
                    all_display_orders.extend(incompatible_stations[:remaining_slots])
            
            # Show top 5
            result = [f"COVINANCE: Best {commodity_name.upper()} sell prices GALAXY-WIDE (top {len(all_display_orders)} of {len(valid_orders)}):\n"]
            
            for i, order in enumerate(all_display_orders, 1):
                station = order.get('stationName', 'Unknown')
                system = order.get('systemName', 'Unknown')
                price = order.get('sellPrice', 0)
                demand = order.get('demand', 0)
                
                # Check if incompatible
                is_incompatible = order in incompatible_stations if show_all_pad_sizes else False
                
                # Pad size display
                station_pad = order.get('maxLandingPadSize', 'S')
                pad_display = f" [{station_pad}]" if show_all_pad_sizes or is_incompatible else ""
                
                # Carrier icon
                carrier = " ðŸš¢" if self._is_carrier_name(station) else ""
                
                if is_incompatible:
                    # LOUD WARNING format
                    result.append(f"\n{i}. âš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {station_pad} PAD REQUIRED - YOUR {ship_type.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
                    result.append(f"\n   {station} ({system}){carrier}")
                    result.append(f"\n   Switch to: Python, Krait, AspX to access this station")
                    result.append(f"\n   Sell: {price:,} CR | Demand: {demand:,}")
                else:
                    # Normal format
                    result.append(f"\n{i}. {station} ({system}){pad_display}{carrier}: {price:,} CR, demand {demand:,}")
            
            # v7.2.1: Add compatibility summary if relevant
            if show_all_pad_sizes and len(incompatible_stations) > 0:
                compatible_best = compatible_stations[0].get('sellPrice', 0) if compatible_stations else 0
                incompatible_best = incompatible_stations[0].get('sellPrice', 0) if incompatible_stations else 0
                
                result.append(f"\n\nðŸ“Š PAD COMPATIBILITY SUMMARY:")
                result.append(f"\n  â€¢ {len(compatible_stations)} compatible stations (best: {compatible_best:,} CR)")
                result.append(f"\n  â€¢ {len(incompatible_stations)} INCOMPATIBLE stations (best: {incompatible_best:,} CR)")
                
                # For sell: higher is better
                if incompatible_best > compatible_best:
                    profit_diff = incompatible_best - compatible_best
                    result.append(f"\n  âš ï¸  Higher profit available but requires different ship ({profit_diff:,} CR more)")
                elif compatible_stations:
                    result.append(f"\n  âœ“ Best compatible price is actually better!")
            
            return "".join(result)
        except Exception as e:
            log('error', f'COVINANCE best_sell error: {str(e)}')
            return f"COVINANCE: Error - {str(e)}"
    def covinance_carrier_market(self, args, projected_states) -> str:
        """Search fleet carrier markets specifically"""
        try:
            commodity_name = args.get('commodity_name', '').lower()
            trade_type = args.get('trade_type', '').lower()
            max_distance = args.get('max_distance', 50)
            limit = args.get('limit', 10)  # Smart default: 10 carriers (voice-friendly)
            
            if not commodity_name:
                return "COVINANCE: No commodity specified."
            
            if trade_type not in ['buy', 'sell']:
                return "COVINANCE: Trade type must be 'buy' or 'sell'."
            
            if not self.current_system:
                return "COVINANCE: Unable to determine your location. Make sure Elite Dangerous is running."
            
            log('info', f'COVINANCE: Searching carrier markets for {commodity_name} ({trade_type})')
            
            # ✅ ADD: Normalize commodity name
            try:
                normalized_commodity = self._normalize_commodity_name(commodity_name)
            except ValueError as e:
                return f"COVINANCE: {str(e)}"
            
            # Use normalized in API calls
            # Use nearby exports for buy (where carriers sell), nearby imports for sell (where carriers buy)
            if trade_type == 'buy':
                endpoint = f'/system/name/{quote(self.current_system)}/commodity/name/{normalized_commodity}/nearby/exports'
            else:
                endpoint = f'/system/name/{quote(self.current_system)}/commodity/name/{normalized_commodity}/nearby/imports'
            
            params = {
                'maxDistance': max_distance,
                'fleetCarriers': True,  # Only carriers
                'maxDaysAgo': 7  # Fresh data only
            }
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: No carrier market data found for '{commodity_name}'."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if not isinstance(api_response, list):
                return f"COVINANCE: Unexpected API response format for carrier markets."
            
            if len(api_response) == 0:
                action = "selling" if trade_type == 'buy' else "buying"
                return f"COVINANCE: No fleet carriers {action} {commodity_name.title()} within {max_distance} LY."
            
            # Format for voice (top N only)
            return self._format_carrier_results(
                api_response[:limit],
                commodity_name,
                trade_type,
                len(api_response)
            )
            
        except Exception as e:
            log('error', f'COVINANCE carrier_market error: {str(e)}')
            return f"COVINANCE: Error searching carrier markets - {str(e)}"
    
    def _format_carrier_results(self, carriers: list, commodity: str, 
                                 trade_type: str, total_count: int) -> str:
        """Format carrier search results for voice output (Section 4 rules)"""
        action = "selling" if trade_type == 'buy' else "buying"
        
        # Lead with answer
        result = [f"COVINANCE: Found {total_count} fleet carriers {action} {commodity.title()}"]
        if len(carriers) < total_count:
            result.append(f". Top {len(carriers)}:")
        else:
            result.append(":")
        
        for i, order in enumerate(carriers, 1):
            carrier_name = order.get('stationName', 'Unknown')
            system_name = order.get('systemName', 'Unknown')
            price = order.get('buyPrice' if trade_type == 'buy' else 'sellPrice', 0)
            volume = order.get('stock' if trade_type == 'buy' else 'demand', 0)
            distance_ly = order.get('distance', 0)
            updated_at = order.get('updatedAt', '')
            
            time_ago = self.format_time_ago(updated_at) if updated_at else "unknown"
            
            result.append(f"\n\n{i}. {carrier_name} in {system_name}")
            
            if trade_type == 'buy':
                result.append(f"\n   Buy: {price:,} CR | Stock: {volume:,}")
            else:
                result.append(f"\n   Sell: {price:,} CR | Demand: {volume:,}")
            
            result.append(f"\n   {distance_ly:.1f} LY away | Updated {time_ago}")
        
        # Carrier warning (once, at end)
        result.append("\n\nðŸš¢ CARRIER WARNING: Inventory dynamic - verify before traveling")
        
        if len(carriers) < total_count:
            result.append(f"\n({total_count - len(carriers)} more available)")
        
        return "".join(result)
    
    def covinance_system_exports(self, args, projected_states) -> str:
        """
        List all commodities available to buy in a system.
        
        v7.2 BATCH 2: Fleet carrier filtering (informational query).
        Default: Include carriers. Exclude with include_fleet_carriers=False.
        """
        try:
            system_name = args.get('system_name', '')
            min_stock = args.get('min_stock', 1)  # API default: show all volumes
            include_fleet_carriers = args.get('include_fleet_carriers', True)  # v7.2 BATCH 2: Default TRUE for informational queries
            
            # If no system specified, use current
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            # Check if this looks like a station/carrier name instead of a system
            if self._is_carrier_name(system_name):
                return f"COVINANCE: '{system_name}' appears to be a fleet carrier or station name, not a system name. Use 'what can I buy at {system_name}' for station-specific market data, or provide the system name where this carrier is located."
            
            log('info', f'COVINANCE: Listing exports (buyable commodities) in {system_name}')
            
            # Call Ardent API
            endpoint = f'/system/name/{quote(system_name)}/commodities/exports'
            params = {
                'minVolume': min_stock,
                'fleetCarriers': None if include_fleet_carriers else False  # v7.2: API parameter
            }
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found or has no export data."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if not isinstance(api_response, list):
                return f"COVINANCE: Unexpected API response format for {system_name} exports."
            
            if len(api_response) == 0:
                return f"COVINANCE: No commodities available to buy in {system_name} with stock over {min_stock} units."
            
            # Sort by stock (highest first)
            sorted_orders = sorted(api_response, key=lambda x: x.get('stock', 0), reverse=True)
            
            # Count stations
            stations = set(order.get('stationName', 'Unknown') for order in api_response)
            
            # Lead with summary
            result = [f"COVINANCE: {len(api_response)} commodities available in {system_name} across {len(stations)} stations."]
            result.append(f"\n\nAll commodities by stock:")
            
            import re
            for i, order in enumerate(sorted_orders, 1):
                commodity = order.get('commodityName', 'Unknown')
                commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity).title()
                station = order.get('stationName', 'Unknown')
                price = order.get('buyPrice', 0)
                stock = order.get('stock', 0)
                
                result.append(f"\n{i}. {commodity_formatted}: {price:,} CR | {stock:,} units at {station}")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE system_exports error: {str(e)}')
            return f"COVINANCE: Error listing system exports - {str(e)}"
    
    def covinance_system_imports(self, args, projected_states) -> str:
        """
        List all commodities you can sell in a system.
        
        v7.2 BATCH 2: Fleet carrier filtering (informational query).
        Default: Include carriers. Exclude with include_fleet_carriers=False.
        """
        try:
            system_name = args.get('system_name', '')
            min_demand = args.get('min_demand', 1)  # API default: show all volumes
            include_fleet_carriers = args.get('include_fleet_carriers', True)  # v7.2 BATCH 2: Default TRUE for informational queries
            
            # If no system specified, use current
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            # Check if this looks like a station/carrier name instead of a system
            if self._is_carrier_name(system_name):
                return f"COVINANCE: '{system_name}' appears to be a fleet carrier or station name, not a system name. Use 'what can I sell at {system_name}' for station-specific market data, or provide the system name where this carrier is located."
            
            log('info', f'COVINANCE: Listing imports (sellable commodities) in {system_name}')
            
            # Call Ardent API
            endpoint = f'/system/name/{quote(system_name)}/commodities/imports'
            params = {
                'minVolume': min_demand,
                'fleetCarriers': None if include_fleet_carriers else False  # v7.2: API parameter
            }
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found or has no import data."
                return f"COVINANCE: Error - {api_response['error']}"
            
            if isinstance(api_response, list):
                if len(api_response) == 0:
                    return f"COVINANCE: No commodities in demand in {system_name} with demand over {min_demand} units."
                
                # Group by station
                stations = {}
                for order in api_response:
                    station = order.get('stationName', 'Unknown')
                    if station not in stations:
                        stations[station] = []
                    stations[station].append(order)
                
                # Build response
                result_parts = [f"COVINANCE: Commodities you can SELL in {system_name}:"]
                result_parts.append(f"\n\nFound {len(api_response)} commodities in demand across {len(stations)} station(s)")
                
                # Show top commodities sorted by demand
                sorted_orders = sorted(api_response, key=lambda x: x.get('demand', 0), reverse=True)
                
                result_parts.append(f"\n\nAll commodities by demand:")
                
                for i, order in enumerate(sorted_orders):
                    commodity = order.get('commodityName', 'Unknown')
                    # Format commodity name: add spaces before capitals and title case
                    import re
                    commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity).title()
                    
                    station = order.get('stationName', 'Unknown')
                    price = order.get('sellPrice', 0)
                    demand = order.get('demand', 0)
                    updated_at = order.get('updatedAt', '')
                    
                    time_ago = self.format_time_ago(updated_at) if updated_at else "unknown"
                    
                    result_parts.append(f"\n  {i+1}. {commodity_formatted} at {station}")
                    result_parts.append(f"\n     Sell: {price:,} CR | Demand: {demand:,} units")
                    result_parts.append(f"\n     Updated {time_ago}")
                
                return "".join(result_parts)
            
            else:
                return f"COVINANCE: Unexpected API response format for {system_name} imports."
            
        except Exception as e:
            log('error', f'COVINANCE system_imports error: {str(e)}')
            return f"COVINANCE: Error listing system imports - {str(e)}"
    
    def covinance_station_market(self, args, projected_states) -> str:
        """Show all commodities at a specific station"""
        try:
            station_name = args.get('station_name', '')
            system_name = args.get('system_name', '')  # Optional parameter
            
            if not station_name:
                return "COVINANCE: No station name specified."
            
            log('info', f'COVINANCE: Looking up market data for station {station_name}')
            
            station_system = None
            exact_station_name = station_name
            
            # If system provided, use it directly (fast path)
            if system_name:
                log('info', f'COVINANCE: System name provided: {system_name}')
                station_system = system_name
            else:
                # Try current system first if available
                if self.current_system:
                    log('info', f'COVINANCE: Checking current system: {self.current_system}')
                    search_endpoint = f'/system/name/{quote(self.current_system)}/stations'
                    search_response = self.call_ardent_api(search_endpoint)
                    
                    if isinstance(search_response, list):
                        for station in search_response:
                            if station_name.lower() in station.get('stationName', '').lower():
                                station_system = self.current_system
                                exact_station_name = station.get('stationName')
                                log('info', f'COVINANCE: Found in current system')
                                break
                
                # If not found in current system, search globally via common commodities
                if not station_system:
                    log('info', f'COVINANCE: Searching globally for station')
                    common_commodities = ['water', 'hydrogenfuel', 'food', 'beer', 'copper', 'aluminium']
                    
                    for commodity in common_commodities:
                        search_endpoint = f'/commodity/name/{commodity}/exports'
                        search_params = {}  # Let API decide everything
                        
                        search_response = self.call_ardent_api(search_endpoint, search_params)
                        
                        if isinstance(search_response, list):
                            for order in search_response:
                                if station_name.lower() in order.get('stationName', '').lower():
                                    station_system = order.get('systemName')
                                    exact_station_name = order.get('stationName')
                                    log('info', f'COVINANCE: Found station in {station_system}')
                                    break
                        
                        if station_system:
                            break
            
            if not station_system:
                # Check if this might be a carrier
                if self._is_carrier_name(station_name):
                    return f"COVINANCE: Could not locate fleet carrier '{station_name}' in market data. Fleet carriers move frequently and may not appear in recent commodity data. Please provide the system name where the carrier is currently located (e.g., 'at {station_name} in SystemName')."
                else:
                    return f"COVINANCE: Could not locate station '{station_name}'. Station may not have active commodity market, name may be incorrect, or try providing the system name (e.g., 'at {station_name} in SystemName')."
            
            log('info', f'COVINANCE: Querying market data for {exact_station_name} in {station_system}')
            
            # Step 2: Get all exports (buyable) at this station
            exports_endpoint = f'/system/name/{quote(station_system)}/commodities/exports'
            exports_response = self.call_ardent_api(exports_endpoint, {})
            
            # Step 3: Get all imports (sellable) at this station
            imports_endpoint = f'/system/name/{quote(station_system)}/commodities/imports'
            imports_response = self.call_ardent_api(imports_endpoint, {})
            
            # Filter by station
            station_exports = []
            station_imports = []
            
            if isinstance(exports_response, list):
                station_exports = [o for o in exports_response if o.get('stationName', '').lower() == exact_station_name.lower()]
            
            if isinstance(imports_response, list):
                station_imports = [o for o in imports_response if o.get('stationName', '').lower() == exact_station_name.lower()]
            
            # ✅ NEW: Filter by commodity if specified
            commodity_filter = args.get('commodity_name', '')
            if commodity_filter:
                try:
                    normalized_commodity = self._normalize_commodity_name(commodity_filter)
                except ValueError as e:
                    return f"COVINANCE: {str(e)}"
                
                # Filter exports/imports using bidirectional matching
                filtered_exports = [
                    o for o in station_exports 
                    if self._matches_commodity(commodity_filter, o.get('commodityName', ''))
                ]
                filtered_imports = [
                    o for o in station_imports 
                    if self._matches_commodity(commodity_filter, o.get('commodityName', ''))
                ]
                
                # Check if commodity found
                if not filtered_exports and not filtered_imports:
                    return f"COVINANCE: {commodity_filter} not available at {exact_station_name}."
                
                # Build specific commodity response
                display_name = RARE_GOODS_DISPLAY_NAMES.get(normalized_commodity, commodity_filter.title())
                result = [f"COVINANCE: {display_name} at {exact_station_name} ({station_system}):"]
                
                if filtered_exports:
                    order = filtered_exports[0]
                    price = order.get('buyPrice', 0)
                    stock = order.get('stock', 0)
                    result.append(f"\n  Buy: {price:,} CR (Stock: {stock:,} units)")
                
                if filtered_imports:
                    order = filtered_imports[0]
                    price = order.get('sellPrice', 0)
                    demand = order.get('demand', 0)
                    result.append(f"\n  Sell: {price:,} CR (Demand: {demand:,} units)")
                
                return "".join(result)
            
            # Continue with normal "list all commodities" logic if no commodity specified
            if not station_exports and not station_imports:
                return f"COVINANCE: {exact_station_name} ({station_system}) has no market data available. Station may not have commodity market services."
            
            # Build response
            result_parts = [f"COVINANCE: Market data for {exact_station_name} ({station_system}):"]
            
            if station_exports:
                result_parts.append(f"\n\nCommodities you can BUY ({len(station_exports)} available):")
                # Sort by stock
                sorted_exports = sorted(station_exports, key=lambda x: x.get('stock', 0), reverse=True)
                
                for i, order in enumerate(sorted_exports):
                    commodity = order.get('commodityName', 'Unknown')
                    import re
                    commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity).title()
                    
                    price = order.get('buyPrice', 0)
                    stock = order.get('stock', 0)
                    
                    result_parts.append(f"\n  {i+1}. {commodity_formatted}: {price:,} CR ({stock:,} units)")
            
            if station_imports:
                result_parts.append(f"\n\nCommodities you can SELL ({len(station_imports)} in demand):")
                # Sort by demand
                sorted_imports = sorted(station_imports, key=lambda x: x.get('demand', 0), reverse=True)
                
                for i, order in enumerate(sorted_imports):
                    commodity = order.get('commodityName', 'Unknown')
                    import re
                    commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity).title()
                    
                    price = order.get('sellPrice', 0)
                    demand = order.get('demand', 0)
                    
                    result_parts.append(f"\n  {i+1}. {commodity_formatted}: {price:,} CR ({demand:,} demand)")
            
            return "".join(result_parts)
            
        except Exception as e:
            log('error', f'COVINANCE station_market error: {str(e)}')
            return f"COVINANCE: Error getting station market - {str(e)}"
    
    def covinance_price_compare(self, args, projected_states) -> str:
        """Compare commodity prices between two stations"""
        try:
            commodity_name = args.get('commodity_name', '').lower()
            station1 = args.get('station1', '')
            station2 = args.get('station2', '')
            system_name = args.get('system_name', '')  # Optional
            
            if not commodity_name or not station1 or not station2:
                return "COVINANCE: Need commodity name and two station names to compare."
            
            log('info', f'COVINANCE: Comparing {commodity_name} prices between {station1} and {station2}')
            
            # ✅ ADD: Normalize commodity name
            try:
                normalized_commodity = self._normalize_commodity_name(commodity_name)
            except ValueError as e:
                return f"COVINANCE: {str(e)}"
            
            # If system provided, query that system directly for better accuracy
            if system_name:
                log('info', f'COVINANCE: System name provided: {system_name}, querying system exports')
                endpoint = f'/system/name/{quote(system_name)}/commodities/exports'
                params = {}  # Let API use defaults
            else:
                # Search globally for stations selling this commodity
                log('info', f'COVINANCE: No system provided, searching globally')
                # ✅ FIX: Use normalized_commodity instead of undefined commodity_normalized
                endpoint = f'/commodity/name/{normalized_commodity}/exports'
                params = {}  # Let API use defaults
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                return f"COVINANCE: Error fetching data - {api_response['error']}"
            
            if not isinstance(api_response, list) or len(api_response) == 0:
                return f"COVINANCE: No market data found for {commodity_name}. Check commodity name."
            
            # Filter for the specific commodity if querying by system
            if system_name:
                # ✅ FIX: Use bidirectional matching instead of direct comparison
                api_response = [o for o in api_response if self._matches_commodity(commodity_name, o.get('commodityName', ''))]
                if len(api_response) == 0:
                    return f"COVINANCE: {commodity_name.title()} not found in {system_name} system."
            
            # Find matching stations (case-insensitive partial match)
            station1_lower = station1.lower()
            station2_lower = station2.lower()
            
            station1_data = None
            station2_data = None
            
            for order in api_response:
                station_name_check = order.get('stationName', '')
                if station1_lower in station_name_check.lower() and not station1_data:
                    station1_data = order
                if station2_lower in station_name_check.lower() and not station2_data:
                    station2_data = order
                if station1_data and station2_data:
                    break
            
            # Build comparison
            import re
            commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity_name).title()
            result_parts = [f"COVINANCE: Comparing {commodity_formatted} prices:"]
            
            if station1_data:
                s1_name = station1_data.get('stationName')
                s1_system = station1_data.get('systemName')
                s1_buy = station1_data.get('buyPrice', 0)
                s1_stock = station1_data.get('stock', 0)
                s1_updated = self.format_time_ago(station1_data.get('updatedAt', ''))
                
                result_parts.append(f"\n\n{s1_name} ({s1_system})")
                result_parts.append(f"\n  Buy: {s1_buy:,} CR | Stock: {s1_stock:,} units")
                result_parts.append(f"\n  Updated: {s1_updated}")
            else:
                result_parts.append(f"\n\n{station1} - NOT FOUND")
                result_parts.append(f"\n  Station may not sell {commodity_formatted} or name incorrect")
            
            if station2_data:
                s2_name = station2_data.get('stationName')
                s2_system = station2_data.get('systemName')
                s2_buy = station2_data.get('buyPrice', 0)
                s2_stock = station2_data.get('stock', 0)
                s2_updated = self.format_time_ago(station2_data.get('updatedAt', ''))
                
                result_parts.append(f"\n\n{s2_name} ({s2_system})")
                result_parts.append(f"\n  Buy: {s2_buy:,} CR | Stock: {s2_stock:,} units")
                result_parts.append(f"\n  Updated: {s2_updated}")
            else:
                result_parts.append(f"\n\n{station2} - NOT FOUND")
                result_parts.append(f"\n  Station may not sell {commodity_formatted} or name incorrect")
            
            # Calculate difference
            if station1_data and station2_data:
                s1_buy = station1_data.get('buyPrice', 0)
                s2_buy = station2_data.get('buyPrice', 0)
                
                if s1_buy > 0 and s2_buy > 0:
                    diff = abs(s1_buy - s2_buy)
                    cheaper = station1_data.get('stationName') if s1_buy < s2_buy else station2_data.get('stationName')
                    
                    result_parts.append(f"\n\nPrice difference: {diff:,} CR per unit")
                    result_parts.append(f"\nCheaper at: {cheaper}")
            
            return "".join(result_parts)
            
        except Exception as e:
            log('error', f'COVINANCE price_compare error: {str(e)}')
            return f"COVINANCE: Error comparing prices - {str(e)}"
    
    def _find_buy_station(self, commodity_name: str, station_name: str, reference_system: str = None) -> dict:
        """
        Helper: Find a station selling a commodity.
        
        Args:
            commodity_name: Commodity to search for
            station_name: Station name to find (partial match)
            reference_system: System to search in (if provided, searches that system; otherwise galaxy-wide)
            
        Returns:
            Dictionary with station data, or None if not found
        """
        try:
            commodity_normalized = self._normalize_commodity_name(commodity_name)
            
            # STRATEGY 1: If system provided, search that system (finds ALL stations, not just top 100)
            if reference_system:
                log('info', f'COVINANCE _find_buy_station: Searching {reference_system} for {station_name} selling {commodity_normalized}')
                
                endpoint = f'/system/name/{quote(reference_system)}/commodities/exports'
                response = self.call_ardent_api(endpoint, {})
                
                if isinstance(response, list):
                    # Filter by commodity
                    commodity_orders = [o for o in response if o.get('commodityName') == commodity_normalized]
                    
                    log('info', f'COVINANCE _find_buy_station: Found {len(commodity_orders)} orders for {commodity_normalized} in {reference_system}')
                    
                    # Find matching station
                    station_lower = station_name.lower()
                    for order in commodity_orders:
                        order_station = order.get('stationName', '').lower()
                        if station_lower in order_station:
                            log('info', f'COVINANCE _find_buy_station: FOUND in system: {order.get("stationName")}')
                            return order
                    
                    log('warning', f'COVINANCE _find_buy_station: {station_name} not found in {reference_system}')
            
            # STRATEGY 2: Fall back to galaxy-wide search (top 100 cheapest only)
            log('info', f'COVINANCE _find_buy_station: Searching galaxy-wide for {station_name} selling {commodity_normalized}')
            
            endpoint = f'/commodity/name/{commodity_normalized}/exports'
            response = self.call_ardent_api(endpoint, {})
            
            if not isinstance(response, list):
                log('warning', f'COVINANCE _find_buy_station: Unexpected response type')
                return None
            
            log('info', f'COVINANCE _find_buy_station: Galaxy-wide returned {len(response)} results')
            
            # Find matching station
            station_lower = station_name.lower()
            for order in response:
                order_station = order.get('stationName', '').lower()
                if station_lower in order_station:
                    log('info', f'COVINANCE _find_buy_station: FOUND galaxy-wide: {order.get("stationName")}')
                    return order
            
            log('warning', f'COVINANCE _find_buy_station: No match found for "{station_name}"')
            return None
            
        except Exception as e:
            log('error', f'COVINANCE _find_buy_station error: {str(e)}')
            return None
    
    def _find_sell_station(self, commodity_name: str, station_name: str, reference_system: str = None) -> dict:
        """
        Helper: Find a station buying a commodity.
        
        Args:
            commodity_name: Commodity to search for
            station_name: Station name to find (partial match)
            reference_system: System to search in (if provided, searches that system; otherwise galaxy-wide)
            
        Returns:
            Dictionary with station data, or None if not found
        """
        try:
            commodity_normalized = self._normalize_commodity_name(commodity_name)
            
            # STRATEGY 1: If system provided, search that system (finds ALL stations, not just top 100)
            if reference_system:
                log('info', f'COVINANCE _find_sell_station: Searching {reference_system} for {station_name} buying {commodity_normalized}')
                
                endpoint = f'/system/name/{quote(reference_system)}/commodities/imports'
                response = self.call_ardent_api(endpoint, {})
                
                if isinstance(response, list):
                    # Filter by commodity
                    commodity_orders = [o for o in response if o.get('commodityName') == commodity_normalized]
                    
                    log('info', f'COVINANCE _find_sell_station: Found {len(commodity_orders)} orders for {commodity_normalized} in {reference_system}')
                    
                    # Find matching station
                    station_lower = station_name.lower()
                    for order in commodity_orders:
                        order_station = order.get('stationName', '').lower()
                        if station_lower in order_station:
                            log('info', f'COVINANCE _find_sell_station: FOUND in system: {order.get("stationName")}')
                            return order
                    
                    log('warning', f'COVINANCE _find_sell_station: {station_name} not found in {reference_system}')
            
            # STRATEGY 2: Fall back to galaxy-wide search (top 100 highest prices only)
            log('info', f'COVINANCE _find_sell_station: Searching galaxy-wide for {station_name} buying {commodity_normalized}')
            
            endpoint = f'/commodity/name/{commodity_normalized}/imports'
            response = self.call_ardent_api(endpoint, {})
            
            if not isinstance(response, list):
                log('warning', f'COVINANCE _find_sell_station: Unexpected response type')
                return None
            
            log('info', f'COVINANCE _find_sell_station: Galaxy-wide returned {len(response)} results')
            
            # Find matching station
            station_lower = station_name.lower()
            for order in response:
                order_station = order.get('stationName', '').lower()
                if station_lower in order_station:
                    log('info', f'COVINANCE _find_sell_station: FOUND galaxy-wide: {order.get("stationName")}')
                    return order
            
            log('warning', f'COVINANCE _find_sell_station: No match found for "{station_name}"')
            return None
            
        except Exception as e:
            log('error', f'COVINANCE _find_sell_station error: {str(e)}')
            return None
    
    
    def covinance_profit_margin(self, args, projected_states) -> str:
        """Calculate profit margin between two stations - COPY OF STATION_MARKET LOGIC"""
        try:
            commodity_name = args.get('commodity_name', '').lower()
            buy_station = args.get('buy_station', '')
            sell_station = args.get('sell_station', '')
            buy_system = args.get('buy_system', '')  # Separate system for buy station
            sell_system = args.get('sell_system', '')  # Separate system for sell station
        
            if not commodity_name or not buy_station or not sell_station:
                return "COVINANCE: Need commodity name, buy station, and sell station."
        
            log('info', f'COVINANCE: Calculating profit for {commodity_name} from {buy_station} to {sell_station}')
        
            # Normalize commodity
            commodity_normalized = self._normalize_commodity_name(commodity_name)
        
            # === FIND BUY STATION (copy station_market logic) ===
            buy_station_exact = None
            buy_system_final = None
        
            # Try current system first
            if self.current_system:
                log('info', f'COVINANCE: Checking current system for buy station')
                stations_response = self.call_ardent_api(f'/system/name/{quote(self.current_system)}/stations')
            
                if isinstance(stations_response, list):
                    for station in stations_response:
                        if buy_station.lower() in station.get('stationName', '').lower():
                            buy_station_exact = station.get('stationName')
                            buy_system_final = self.current_system
                            log('info', f'COVINANCE: Found buy station in current system')
                            break
        
            # If not found, try provided buy_system
            if not buy_station_exact and buy_system:
                log('info', f'COVINANCE: Checking {buy_system} for buy station')
                stations_response = self.call_ardent_api(f'/system/name/{buy_system}/stations')
            
                if isinstance(stations_response, list):
                    for station in stations_response:
                        if buy_station.lower() in station.get('stationName', '').lower():
                            buy_station_exact = station.get('stationName')
                            buy_system_final = buy_system
                            log('info', f'COVINANCE: Found buy station in {buy_system}')
                            break
        
            # If still not found, search globally
            if not buy_station_exact:
                log('info', f'COVINANCE: Searching globally for buy station')
                common_commodities = ['water', 'hydrogenfuel', 'food', 'beer', 'copper', 'aluminium']
            
                for search_commodity in common_commodities:
                    search_response = self.call_ardent_api(f'/commodity/name/{search_commodity}/exports', {})
                
                    if isinstance(search_response, list):
                        for order in search_response:
                            if buy_station.lower() in order.get('stationName', '').lower():
                                buy_station_exact = order.get('stationName')
                                buy_system_final = order.get('systemName')
                                log('info', f'COVINANCE: Found buy station in {buy_system_final}')
                                break
                
                    if buy_station_exact:
                        break
        
            if not buy_station_exact:
                return f"COVINANCE: Unable to locate buy station '{buy_station}'."
        
            # === FIND SELL STATION (same logic) ===
            sell_station_exact = None
            sell_system_final = None
        
            # Try current system first
            if self.current_system:
                stations_response = self.call_ardent_api(f'/system/name/{quote(self.current_system)}/stations')
            
                if isinstance(stations_response, list):
                    for station in stations_response:
                        if sell_station.lower() in station.get('stationName', '').lower():
                            sell_station_exact = station.get('stationName')
                            sell_system_final = self.current_system
                            break
        
            # Try provided sell_system
            if not sell_station_exact and sell_system:
                stations_response = self.call_ardent_api(f'/system/name/{sell_system}/stations')
            
                if isinstance(stations_response, list):
                    for station in stations_response:
                        if sell_station.lower() in station.get('stationName', '').lower():
                            sell_station_exact = station.get('stationName')
                            sell_system_final = sell_system
                            break
        
            # Search globally
            if not sell_station_exact:
                common_commodities = ['water', 'hydrogenfuel', 'food', 'beer', 'copper', 'aluminium']
            
                for search_commodity in common_commodities:
                    search_response = self.call_ardent_api(f'/commodity/name/{search_commodity}/exports', {})
                
                    if isinstance(search_response, list):
                        for order in search_response:
                            if sell_station.lower() in order.get('stationName', '').lower():
                                sell_station_exact = order.get('stationName')
                                sell_system_final = order.get('systemName')
                                break
                
                    if sell_station_exact:
                        break
        
            if not sell_station_exact:
                return f"COVINANCE: Unable to locate sell station '{sell_station}'."
        
            # === CRITICAL SAFETY CHECK ===
            # Ensure we actually have station names before proceeding (prevents NoneType crash)
            if not buy_station_exact or not sell_station_exact:
                missing = []
                if not buy_station_exact:
                    missing.append(f"buy station '{buy_station}'")
                if not sell_station_exact:
                    missing.append(f"sell station '{sell_station}'")
                return f"COVINANCE: Unable to locate {' and '.join(missing)}."
        
            log('info', f'COVINANCE: Stations found - Buy: {buy_station_exact} ({buy_system_final}), Sell: {sell_station_exact} ({sell_system_final})')
        
            # === NOW GET COMMODITY PRICES ===
        
            # Get buy price (we BUY at station's buyPrice from /exports)
            buy_endpoint = f'/system/name/{quote(buy_system_final)}/commodities/exports'
            buy_response = self.call_ardent_api(buy_endpoint, {})
        
            buy_price = None
            buy_stock = None
        
            if isinstance(buy_response, list):
                # Filter for our commodity at our station
                # ✅ FIX: Use bidirectional matching instead of direct comparison
                matching_orders = [
                    o for o in buy_response 
                    if self._matches_commodity(commodity_name, o.get('commodityName', ''))
                    and o.get('stationName', '').lower() == buy_station_exact.lower()
                ]
                
                if matching_orders:
                    # CRITICAL: If multiple orders exist (e.g., CG bonuses, price updates),
                    # take the one with LOWEST buyPrice (cheapest for player buying)
                    best_order = min(matching_orders, key=lambda x: x.get('buyPrice', 999999999))
                    buy_price = best_order.get('buyPrice', 0)
                    buy_stock = best_order.get('stock', 0)
        
            if not buy_price or buy_price == 0:
                return f"COVINANCE: {buy_station_exact} does not sell {commodity_name}."
        
            # Get sell price (we SELL at station's sellPrice from /imports)
            sell_endpoint = f'/system/name/{quote(sell_system_final)}/commodities/imports'
            sell_response = self.call_ardent_api(sell_endpoint, {})
        
            sell_price = None
            sell_demand = None
            sell_order_found = False
        
            if isinstance(sell_response, list):
                # Filter for our commodity at our station
                # ✅ FIX: Use bidirectional matching instead of direct comparison
                matching_orders = [
                    o for o in sell_response 
                    if self._matches_commodity(commodity_name, o.get('commodityName', ''))
                    and o.get('stationName', '').lower() == sell_station_exact.lower()
                ]
                
                if matching_orders:
                    sell_order_found = True
                    # CRITICAL: If multiple orders exist (e.g., CG bonuses, price updates),
                    # take the one with HIGHEST sellPrice (best for player selling)
                    best_order = max(matching_orders, key=lambda x: x.get('sellPrice', 0))
                    sell_price = best_order.get('sellPrice', 0)
                    sell_demand = best_order.get('demand', 0)
        
            if not sell_order_found:
                return f"COVINANCE: {sell_station_exact} does not buy {commodity_name}."
            
            if sell_price == 0:
                return f"COVINANCE: {sell_station_exact} has demand for {commodity_name} ({sell_demand:,} units) but sellPrice is 0 credits - likely stale/bad data. Cannot calculate reliable profit."
        
            # === CALCULATE PROFIT ===
            profit_per_unit = sell_price - buy_price
            profit_percentage = (profit_per_unit / buy_price * 100) if buy_price > 0 else 0
        
            # Format commodity name
            import re
            commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity_name).title()
        
            # Build response
            result_parts = [f"COVINANCE: Profit margin for {commodity_formatted}:"]
            result_parts.append(f"\n\nBuy from: {buy_station_exact} ({buy_system_final})")
            result_parts.append(f"\n  Price: {buy_price:,} CR | Stock: {buy_stock:,} units")
            result_parts.append(f"\n\nSell to: {sell_station_exact} ({sell_system_final})")
            result_parts.append(f"\n  Price: {sell_price:,} CR | Demand: {sell_demand:,} units")
            result_parts.append(f"\n\nProfit per unit: {profit_per_unit:,} CR")
            result_parts.append(f"\nProfit margin: {profit_percentage:.1f}%")
        
            if profit_per_unit <= 0:
                result_parts.append(f"\n\nWARNING: Negative or zero profit - this is a losing trade!")
        
            # Add volume calculation
            max_volume = min(buy_stock, sell_demand) if sell_demand > 0 else buy_stock
            if max_volume > 0:
                total_profit = profit_per_unit * max_volume
                result_parts.append(f"\n\nMax tradeable volume: {max_volume:,} units")
                result_parts.append(f"\nMax total profit: {total_profit:,} CR")
        
            return "".join(result_parts)
        
        except Exception as e:
            log('error', f'COVINANCE profit_margin error: {str(e)}')
            return f"COVINANCE: Error calculating profit margin - {str(e)}"

    def covinance_find_service(self, args, projected_states) -> str:
        """Find nearest stations with specific service"""
        try:
            service_input = args.get('service', '').lower().strip()
            min_pad_size = args.get('min_pad_size', 1)
            system_name = args.get('system_name', '')
            
            if not service_input:
                return "COVINANCE: Please specify a service to find."
            
            # Normalize service name
            service = self._normalize_service_name(service_input)
            
            if not service:
                return f"COVINANCE: Unknown service '{service_input}'. " \
                       f"Valid services: material-trader, technology-broker, " \
                       f"interstellar-factors, black-market, universal-cartographics, " \
                       f"refuel, repair, shipyard, outfitting, search-and-rescue."
            
            # Use current system if not specified
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: Unable to determine your location. " \
                           "Specify a system or dock somewhere first."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Finding nearest {service} from {system_name}')
            
            # API call
            endpoint = f'/system/name/{quote(system_name)}/nearest/{service}'
            params = {
                'minLandingPadSize': min_pad_size
            }
            
            response = self.call_ardent_api(endpoint, params)
            
            if "error" in response:
                if response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found or no {service} nearby."
                return f"COVINANCE: Error - {response['error']}"
            
            # Check response
            if not isinstance(response, list):
                return f"COVINANCE: API error searching for {service}."
            
            if len(response) == 0:
                return f"COVINANCE: No stations with {service} found near {system_name}."
            
            # Format results (voice-friendly: top 3 with option for more)
            return self._format_service_results(
                response,
                service,
                system_name,
                min_pad_size
            )
            
        except Exception as e:
            log('error', f'COVINANCE find_service error: {str(e)}')
            return f"COVINANCE: Error finding service - {str(e)}"
    
    def _format_service_results(self, stations: list, service: str, 
                                 reference_system: str, min_pad_size: int) -> str:
        """Format service search results for voice output"""
        # User-friendly service name
        service_names = {
            'material-trader': 'Material Trader',
            'technology-broker': 'Technology Broker',
            'interstellar-factors': 'Interstellar Factors',
            'black-market': 'Black Market',
            'universal-cartographics': 'Universal Cartographics',
            'refuel': 'Refueling',
            'repair': 'Repair',
            'shipyard': 'Shipyard',
            'outfitting': 'Outfitting',
            'search-and-rescue': 'Search and Rescue'
        }
        
        service_display = service_names.get(service, service.replace('-', ' ').title())
        
        # Pad size description
        pad_desc = ""
        if min_pad_size == 2:
            pad_desc = " (medium/large pads)"
        elif min_pad_size == 3:
            pad_desc = " (large pads only)"
        
        # Build response
        closest = stations[0]
        result = [f"COVINANCE: Nearest {service_display}{pad_desc} from {reference_system}:"]
        result.append(f"\n\n1. {closest['stationName']} in {closest['systemName']}")
        result.append(f"\n   Distance: {closest['distance']:.2f} LY")
        
        if closest.get('distanceToArrival'):
            result.append(f" | {closest['distanceToArrival']:,} Ls from star")
        
        # Add 2nd and 3rd options
        if len(stations) > 1:
            for i, station in enumerate(stations[1:3], 2):
                result.append(f"\n\n{i}. {station['stationName']} in {station['systemName']}")
                result.append(f"\n   Distance: {station['distance']:.2f} LY")
                if station.get('distanceToArrival'):
                    result.append(f" | {station['distanceToArrival']:,} Ls from star")
        
        # Mention if more available
        if len(stations) > 3:
            result.append(f"\n\n...and {len(stations) - 3} more options available.")
        
        return "".join(result)
    # ========================================================================
    # PHASE 1.5: NEARBY RADIUS SEARCHES
    # ========================================================================
    
    def covinance_nearby_buy(self, args, projected_states) -> str:
        """
        Find cheapest buy prices within radius (up to 1000 results).
        Endpoint: /v2/system/name/{system}/commodity/name/{commodity}/nearby/exports
        
        v7.2 STANDARD PARAMETERS:
        - Auto pad size from Journal ship type
        - Auto jump range default from Journal MaxJumpRange
        - Transparent scope reporting
        - Surface station filtering
        - Fleet carrier filtering
        """
        try:
            commodity_name = args.get('commodity_name', '').strip()
            reference_system = args.get('reference_system', '').strip()
            min_volume = args.get('min_volume', 1)  # API default: show all volumes
            max_price = args.get('max_price')
            max_days_old = args.get('max_days_old', 90)  # ✅ v7.6.1: API max is 90 days (was 365)
            sort_by = args.get('sort_by', 'price')
            
            # v7.2: Enhanced parameters
            include_surface_stations = args.get('include_surface_stations', True)
            include_fleet_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            pad_size_override = args.get('pad_size')  # Manual override if needed
            
            # v7.2.1: Exclusionary pattern fixes
            include_zero_stock = args.get('include_zero_stock', False)  # Default False: filter zeros
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)  # Default False: filter incompatible
            
            
            if not commodity_name:
                return "COVINANCE: Please specify a commodity to buy."
            
            commodity_normalized = self._normalize_commodity_name(commodity_name)
            
            # Get Journal data for smart defaults
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '') if journal_data else ''
            jump_range = journal_data.get('MaxJumpRange', 20) if journal_data else 20
            
            # v7.2: Determine required pad size from ship type or override
            if pad_size_override:
                required_pad = pad_size_override.upper()
            else:
                required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            
            # v7.2: Smart default for max_distance - use jump range unless overridden
            max_distance = args.get('max_distance', jump_range)
            
            if not reference_system:
                self.update_location_from_journal()
                if not self.current_system:
                    return "COVINANCE: Unable to determine your location. Specify a system or dock somewhere first."
                reference_system = self.current_system
            
            if max_distance < 1 or max_distance > 500:
                return "COVINANCE: max_distance must be between 1 and 500 LY."
            
            if sort_by not in ['price', 'distance']:
                return "COVINANCE: sort_by must be 'price' or 'distance'."
            
            log('info', f'COVINANCE nearby_buy: {commodity_normalized} within {max_distance} LY of {reference_system} (ship: {ship_type or "Unknown"}, pad: {required_pad})')
            
            endpoint = f'/system/name/{quote(reference_system)}/commodity/name/{commodity_normalized}/nearby/exports'
            params = {
                'maxDistance': max_distance,
                'minVolume': min_volume,
                'maxDaysAgo': min(max_days_old, 90),  # ✅ v7.6.1: Clamp to API limit
                'sort': sort_by,
                # v7.2.1: Conditional pad filtering
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,  # S = get all pad sizes
                'fleetCarriers': None if include_fleet_carriers else False
            }
            
            if max_price is not None:
                params['maxPrice'] = max_price
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{reference_system}' not found or no data for '{commodity_normalized}'."
                return f"COVINANCE: Error - {api_response['error']}"
            
            # ALWAYS supplement nearby results with local system (distance=0)
            # The /nearby/ endpoint excludes the reference system, but users expect "nearby X" to include X
            local_endpoint = f'/system/name/{quote(reference_system)}/commodity/name/{commodity_normalized}/exports'
            local_params = params.copy()
            local_params.pop('maxDistance', None)  # Not needed for local query
            local_params.pop('sort', None)  # Not needed for local query
            local_response = self.call_ardent_api(local_endpoint, local_params)
            
            # Merge local results with nearby results
            if isinstance(local_response, list):
                for order in local_response:
                    order['distance'] = 0  # Mark as local system (distance=0)
                # Combine: local + nearby
                api_response = local_response + (api_response if isinstance(api_response, list) else [])
            
            if not isinstance(api_response, list) or len(api_response) == 0:
                filters_msg = f"within {max_distance} LY"
                if max_price:
                    filters_msg += f", max price {max_price:,} CR"
                return f"COVINANCE: No buy opportunities for '{commodity_normalized}' {filters_msg}."
            

            
            # v7.2: Filter results (API already filtered by pad size)
            valid_orders = []
            for o in api_response:
                # Must have valid stock and price
                # v7.2.1: Conditional zero stock filtering
                stock_val = o.get('stock', 0)
                price_val = o.get('buyPrice', 0)
                
                # Skip if price invalid (always required)
                if price_val <= 0:
                    continue
                
                # Skip zero stock only if include_zero_stock=False
                if not include_zero_stock and stock_val <= 0:
                    continue
                
                # v7.2: Surface station filtering (client-side only)
                is_planetary = o.get('isPlanetary', False)
                if not include_surface_stations and is_planetary:
                    continue
                
                valid_orders.append(o)
            
            # v7.2.1: Check pad compatibility when show_all_pad_sizes=True
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            compatible_stations = []
            incompatible_stations = []
            
            for o in valid_orders:
                station_pad = o.get('maxLandingPadSize', 'S')
                station_pad_size = pad_size_map.get(station_pad, 1)
                
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_stations.append(o)
                else:
                    compatible_stations.append(o)
            
            
            if len(valid_orders) == 0:
                return f"COVINANCE: No sell opportunities for '{commodity_normalized}' within {max_distance} LY matching your requirements ({required_pad} pad)."
            
            # v7.2.1: Check pad compatibility when show_all_pad_sizes=True
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            compatible_stations = []
            incompatible_stations = []
            
            for o in valid_orders:
                station_pad = o.get('maxLandingPadSize', 'S')
                station_pad_size = pad_size_map.get(station_pad, 1)
                
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_stations.append(o)
                else:
                    compatible_stations.append(o)
            
            # v7.2: TRANSPARENT SCOPE - show what was limited
            scope_info = []
            scope_info.append(f"\nðŸ” SEARCH SCOPE:")
            scope_info.append(f"\n  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)")
            scope_info.append(f"\n  â€¢ Distance: {max_distance:.1f} LY" + (f" (your 1-jump range)" if max_distance == jump_range else ""))
            scope_info.append(f"\n  â€¢ Results: {len(valid_orders)} stations")
            if not include_surface_stations:
                scope_info.append(f"\n  â€¢ Surface stations: Excluded")
            if not include_fleet_carriers:
                scope_info.append(f"\n  â€¢ Fleet carriers: Excluded")
            if include_zero_stock:
                scope_info.append(f"\n  â€¢ Zero stock: Included (use with caution)")
            if show_all_pad_sizes:
                scope_info.append(f"\n  â€¢ All pad sizes: Shown (incompatible marked)")
            
            result = []
            result.append(f"COVINANCE: Best places to BUY {commodity_normalized.upper()} within {max_distance:.1f} LY of {reference_system}\n")
            result.append(f"(Sorted by {sort_by}, {len(valid_orders)} results)")
            result.append("".join(scope_info))
            result.append("\n\n")
            
            cheapest_price = valid_orders[0].get('buyPrice', 0)
            total_stock = sum(o.get('stock', 0) for o in valid_orders)
            carriers = sum(1 for o in valid_orders if self._is_carrier_name(o.get('stationName', '')))
            
            result.append(f"ðŸ“Š Summary: Cheapest {cheapest_price:,} CR | Total stock {total_stock:,} | {len(valid_orders)} locations")
            if carriers > 0:
                result.append(f" | âš ï¸  {carriers} carriers")
            
            
            # v7.2.1: Combine and display stations (compatible first, then incompatible with warnings)
            all_display_orders = compatible_stations[:20]  # Show compatible first
            if show_all_pad_sizes and incompatible_stations:
                # Add incompatible stations to display list
                remaining_slots = 20 - len(all_display_orders)
                if remaining_slots > 0:
                    all_display_orders.extend(incompatible_stations[:remaining_slots])
            
            result.append("\n\nðŸŽ¯ Top Opportunities:\n")
            
            for i, order in enumerate(all_display_orders, 1):
                station = order.get('stationName', 'Unknown')
                system = order.get('systemName', 'Unknown')
                price = order.get('buyPrice', 0)
                stock = order.get('stock', 0)
                distance = order.get('distance', 0)
                updated = order.get('updatedAt', '')
                pad = order.get('maxLandingPadSize', 'S')
                is_planetary = order.get('isPlanetary', False)
                
                data_age = self._calculate_data_age(updated)
                age_warn = " âš ï¸ STALE" if data_age > 7 else ""
                carrier_warn = " ðŸš¢" if self._is_carrier_name(station) else ""
                surface_icon = " ðŸŒ" if is_planetary else ""
                
                pad_display = f" [{pad}]" if pad else ""
                
                # v7.2.1: Check if this station is incompatible with current ship
                is_incompatible = order in incompatible_stations if show_all_pad_sizes else False
                
                if is_incompatible:
                    # LOUD WARNING for incompatible pad
                    pad_needed = order.get('maxLandingPadSize', 'S')
                    ship_name = ship_type or 'your ship'
                    result.append(f"\n{i}. âš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {pad_needed} PAD REQUIRED - YOUR {ship_name.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
                    result.append(f"\n   {station} ({system}){surface_icon}")
                    result.append(f"\n   Switch to: Python, Krait, AspX to access this station")
                else:
                    result.append(f"\n{i}. {station} ({system}){pad_display}{surface_icon}")
                result.append(f"\n   Buy: {price:,} CR | Stock: {stock:,} | Dist: {distance:.1f} LY | Age: {data_age}d{age_warn}{carrier_warn}")
            
            if len(valid_orders) > 20:
                result.append(f"\n\n...and {len(valid_orders) - 20} more available.")
            
            stale_count = sum(1 for o in valid_orders if self._calculate_data_age(o.get('updatedAt', '')) > 7)
            if stale_count > 0:
                result.append(f"\n\nâš ï¸  {stale_count} results have stale data (>7 days). Verify before long trips!")
            
            
            # v7.2.1: Add incompatibility summary if relevant
            if show_all_pad_sizes and len(incompatible_stations) > 0:
                compatible_best = compatible_stations[0].get('buyPrice', 0) if compatible_stations else 0
                incompatible_best = incompatible_stations[0].get('buyPrice', 0) if incompatible_stations else 0
                
                result.append(f"\n\nðŸ“Š PAD COMPATIBILITY SUMMARY:")
                result.append(f"\n  â€¢ {len(compatible_stations)} compatible stations (best: {compatible_best:,} CR)")
                result.append(f"\n  â€¢ {len(incompatible_stations)} INCOMPATIBLE stations (best: {incompatible_best:,} CR)")
                
                if incompatible_best < compatible_best:
                    profit_diff = compatible_best - incompatible_best
                    result.append(f"\n  âœ“ Best compatible price is actually better by {profit_diff:,} CR!")
                elif incompatible_stations:
                    result.append(f"\n  âš ï¸  Higher profit available but requires different ship")
            
            # v7.2: Suggest expanding search if limited results
            if len(valid_orders) < 5:
                result.append(f"\n\nðŸ’¡ TIP: Try expanding your search:")
                result.append(f"\n  â€¢ Increase range: max_distance={int(max_distance * 2)}")
                if not include_surface_stations:
                    result.append(f"\n  â€¢ Include surface: include_surface_stations=True")
            
            # ✅ v7.5.1: Transparency note for restrictive filters
            if max_days_old < 90:
                result.append(f"\n\n📊 Showing data ≤{max_days_old} days old (use 'max data age 90' to see all)")
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE nearby_buy error: {str(e)}')
            return f"COVINANCE: Error finding buy opportunities - {str(e)}"

    def covinance_nearby_sell(self, args, projected_states) -> str:
        """
        Find best sell prices within radius (up to 1000 results).
        Endpoint: /v2/system/name/{system}/commodity/name/{commodity}/nearby/imports
        
        v7.2 STANDARD PARAMETERS:
        - Auto pad size from Journal ship type
        - Auto jump range default from Journal MaxJumpRange
        - Transparent scope reporting
        - Surface station filtering
        - Fleet carrier filtering
        """
        try:
            commodity_name = args.get('commodity_name', '').strip()
            reference_system = args.get('reference_system', '').strip()
            min_demand = args.get('min_demand', 1)  # API default: show all volumes
            min_price = args.get('min_price')
            max_days_old = args.get('max_days_old', 90)  # ✅ v7.6.1: API max is 90 days (was 365)
            sort_by = args.get('sort_by', 'price')
            
            # v7.2: Enhanced parameters
            include_surface_stations = args.get('include_surface_stations', True)
            include_fleet_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            pad_size_override = args.get('pad_size')  # Manual override if needed
            
            # v7.2.1: Exclusionary pattern fixes
            include_zero_demand = args.get('include_zero_demand', False)  # Default False: filter zeros
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)  # Default False: filter incompatible
            
            if not commodity_name:
                return "COVINANCE: Please specify a commodity to sell."
            
            commodity_normalized = self._normalize_commodity_name(commodity_name)
            
            # Get Journal data for smart defaults
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '') if journal_data else ''
            jump_range = journal_data.get('MaxJumpRange', 20) if journal_data else 20
            
            # v7.2: Determine required pad size from ship type or override
            if pad_size_override:
                required_pad = pad_size_override.upper()
            else:
                required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            
            # v7.2: Smart default for max_distance - use jump range unless overridden
            max_distance = args.get('max_distance', jump_range)
            
            if not reference_system:
                self.update_location_from_journal()
                if not self.current_system:
                    return "COVINANCE: Unable to determine your location. Specify a system or dock somewhere first."
                reference_system = self.current_system
            
            if max_distance < 1 or max_distance > 500:
                return "COVINANCE: max_distance must be between 1 and 500 LY."
            
            if sort_by not in ['price', 'distance']:
                return "COVINANCE: sort_by must be 'price' or 'distance'."
            
            log('info', f'COVINANCE nearby_sell: {commodity_normalized} within {max_distance} LY of {reference_system} (ship: {ship_type or "Unknown"}, pad: {required_pad})')
            
            endpoint = f'/system/name/{quote(reference_system)}/commodity/name/{commodity_normalized}/nearby/imports'
            params = {
                'maxDistance': max_distance,
                'minVolume': min_demand,
                'maxDaysAgo': min(max_days_old, 90),  # ✅ v7.6.1: Clamp to API limit
                'sort': sort_by,
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,  # v7.2.1: Conditional pad filtering
                'fleetCarriers': None if include_fleet_carriers else False
            }
            
            if min_price is not None:
                params['minPrice'] = min_price
            
            api_response = self.call_ardent_api(endpoint, params)
            
            if "error" in api_response:
                if api_response.get('status_code') == 404:
                    return f"COVINANCE: System '{reference_system}' not found or no data for '{commodity_normalized}'."
                return f"COVINANCE: Error - {api_response['error']}"
            
            # ALWAYS supplement nearby results with local system (distance=0)
            # The /nearby/ endpoint excludes the reference system, but users expect "nearby X" to include X
            local_endpoint = f'/system/name/{quote(reference_system)}/commodity/name/{commodity_normalized}/imports'
            local_params = params.copy()
            local_params.pop('maxDistance', None)  # Not needed for local query
            local_params.pop('sort', None)  # Not needed for local query
            local_response = self.call_ardent_api(local_endpoint, local_params)
            
            # Merge local results with nearby results
            if isinstance(local_response, list):
                for order in local_response:
                    order['distance'] = 0  # Mark as local system (distance=0)
                # Combine: local + nearby
                api_response = local_response + (api_response if isinstance(api_response, list) else [])
            
            if not isinstance(api_response, list) or len(api_response) == 0:
                filters_msg = f"within {max_distance} LY"
                if min_price:
                    filters_msg += f", min price {min_price:,} CR"
                return f"COVINANCE: No sell opportunities for '{commodity_normalized}' {filters_msg}."
            
            # v7.2: Filter results (API already filtered by pad size)
            valid_orders = []
            for o in api_response:
                # Must have valid price
                price_val = o.get('sellPrice', 0)
                demand_val = o.get('demand', 0)
                
                # Skip if price invalid (always required)
                if price_val <= 0:
                    continue
                
                # v7.2.1: Skip zero demand only if include_zero_demand=False
                if not include_zero_demand and demand_val <= 0:
                    continue
                
                # v7.2: Surface station filtering (client-side only)
                is_planetary = o.get('isPlanetary', False)
                if not include_surface_stations and is_planetary:
                    continue
                
                valid_orders.append(o)
            
            if len(valid_orders) == 0:
                return f"COVINANCE: No sell opportunities for '{commodity_normalized}' within {max_distance} LY matching your requirements ({required_pad} pad)."
            
            # v7.2.1: Check pad compatibility when show_all_pad_sizes=True
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            compatible_stations = []
            incompatible_stations = []
            
            for o in valid_orders:
                station_pad = o.get('maxLandingPadSize', 'S')
                station_pad_size = pad_size_map.get(station_pad, 1)
                
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_stations.append(o)
                else:
                    compatible_stations.append(o)
            
            # v7.2: TRANSPARENT SCOPE - show what was limited
            scope_info = []
            scope_info.append(f"\nðŸ” SEARCH SCOPE:")
            scope_info.append(f"\n  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)")
            scope_info.append(f"\n  â€¢ Distance: {max_distance:.1f} LY" + (f" (your 1-jump range)" if max_distance == jump_range else ""))
            scope_info.append(f"\n  â€¢ Results: {len(valid_orders)} stations")
            if not include_surface_stations:
                scope_info.append(f"\n  â€¢ Surface stations: Excluded")
            if not include_fleet_carriers:
                scope_info.append(f"\n  â€¢ Fleet carriers: Excluded")
            if include_zero_demand:
                scope_info.append(f"\n  â€¢ Zero demand: Included (use with caution)")
            if show_all_pad_sizes:
                scope_info.append(f"\n  â€¢ All pad sizes: Shown (incompatible marked)")
            
            result = []
            result.append(f"COVINANCE: Best places to SELL {commodity_normalized.upper()} within {max_distance:.1f} LY of {reference_system}\n")
            result.append(f"(Sorted by {sort_by}, {len(valid_orders)} results)")
            result.append("".join(scope_info))
            result.append("\n\n")
            
            highest_price = valid_orders[0].get('sellPrice', 0)
            total_demand = sum(o.get('demand', 0) for o in valid_orders)
            carriers = sum(1 for o in valid_orders if self._is_carrier_name(o.get('stationName', '')))
            
            result.append(f"ðŸ“Š Summary: Highest {highest_price:,} CR | Total demand {total_demand:,} | {len(valid_orders)} locations")
            if carriers > 0:
                result.append(f" | âš ï¸  {carriers} carriers")
            
            # v7.2.1: Combine and display stations (compatible first, then incompatible with warnings)
            all_display_orders = compatible_stations[:20]  # Show compatible first
            if show_all_pad_sizes and incompatible_stations:
                # Add incompatible stations to display list
                remaining_slots = 20 - len(all_display_orders)
                if remaining_slots > 0:
                    all_display_orders.extend(incompatible_stations[:remaining_slots])
            
            result.append("\n\nðŸŽ¯ Top Opportunities:\n")
            
            for i, order in enumerate(all_display_orders, 1):
                station = order.get('stationName', 'Unknown')
                system = order.get('systemName', 'Unknown')
                price = order.get('sellPrice', 0)
                demand = order.get('demand', 0)
                distance = order.get('distance', 0)
                updated = order.get('updatedAt', '')
                pad = order.get('maxLandingPadSize', 'S')
                is_planetary = order.get('isPlanetary', False)
                
                data_age = self._calculate_data_age(updated)
                age_warn = " âš ï¸ STALE" if data_age > 7 else ""
                carrier_warn = " ðŸš¢" if self._is_carrier_name(station) else ""
                surface_icon = " ðŸŒ" if is_planetary else ""
                
                pad_display = f" [{pad}]" if pad else ""
                
                # v7.2.1: Check if this station is incompatible with current ship
                is_incompatible = order in incompatible_stations if show_all_pad_sizes else False
                
                if is_incompatible:
                    # LOUD WARNING for incompatible pad
                    ship_name = ship_type or 'your ship'
                    result.append(f"\n{i}. âš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {pad} PAD REQUIRED - YOUR {ship_name.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
                    result.append(f"\n   {station} ({system}){surface_icon}")
                    result.append(f"\n   Switch to: Python, Krait, AspX to access this station")
                else:
                    result.append(f"\n{i}. {station} ({system}){pad_display}{surface_icon}")
                result.append(f"\n   Sell: {price:,} CR | Demand: {demand:,} | Dist: {distance:.1f} LY | Age: {data_age}d{age_warn}{carrier_warn}")
            
            if len(valid_orders) > 20:
                result.append(f"\n\n...and {len(valid_orders) - 20} more available.")
            
            stale_count = sum(1 for o in valid_orders if self._calculate_data_age(o.get('updatedAt', '')) > 7)
            if stale_count > 0:
                result.append(f"\n\nâš ï¸  {stale_count} results have stale data (>7 days). Verify before long trips!")
            
            # v7.2.1: Add incompatibility summary if relevant
            if show_all_pad_sizes and len(incompatible_stations) > 0:
                compatible_best = compatible_stations[0].get('sellPrice', 0) if compatible_stations else 0
                incompatible_best = incompatible_stations[0].get('sellPrice', 0) if incompatible_stations else 0
                
                result.append(f"\n\nðŸ“Š PAD COMPATIBILITY SUMMARY:")
                result.append(f"\n  â€¢ {len(compatible_stations)} compatible stations (best: {compatible_best:,} CR)")
                result.append(f"\n  â€¢ {len(incompatible_stations)} INCOMPATIBLE stations (best: {incompatible_best:,} CR)")
                
                # For sell: higher is better
                if incompatible_best > compatible_best:
                    profit_diff = incompatible_best - compatible_best
                    result.append(f"\n  âš ï¸  Higher profit available but requires different ship ({profit_diff:,} CR more)")
                elif compatible_stations:
                    result.append(f"\n  âœ“ Best compatible price is actually better!")
            
            # v7.2: Suggest expanding search if limited results
            if len(valid_orders) < 5:
                result.append(f"\n\nðŸ’¡ TIP: Try expanding your search:")
                result.append(f"\n  â€¢ Increase range: max_distance={int(max_distance * 2)}")
                if not include_surface_stations:
                    result.append(f"\n  â€¢ Include surface: include_surface_stations=True")
            
            # ✅ v7.5.1: Transparency note for restrictive filters
            if max_days_old < 90:
                result.append(f"\n\n📊 Showing data ≤{max_days_old} days old (use 'max data age 90' to see all)")
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE nearby_sell error: {str(e)}')
            return f"COVINANCE: Error finding sell opportunities - {str(e)}"


    def covinance_system_info(self, args, projected_states) -> str:
        """Get system coordinates and identification info"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Getting info for {system_name}')
            
            endpoint = f'/system/name/{quote(system_name)}'
            response = self.call_ardent_api(endpoint, {})
            
            if "error" in response:
                if response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {response['error']}"
            
            sys_name = response.get('systemName', 'Unknown')
            sys_address = response.get('systemAddress', 'Unknown')
            x = response.get('systemX', 0)
            y = response.get('systemY', 0)
            z = response.get('systemZ', 0)
            
            result = [f"COVINANCE: System info for {sys_name}"]
            result.append(f"\n\nCoordinates: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
            result.append(f"\nSystem Address: {sys_address}")
            
            # Check for disambiguation (duplicate names)
            disambiguation = response.get('disambiguation', [])
            if disambiguation and len(disambiguation) > 0:
                result.append(f"\n\nâš ï¸  WARNING: {len(disambiguation) + 1} systems share this name!")
                result.append(f"\nShowing: {sys_name} at ({x:.2f}, {y:.2f}, {z:.2f})")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE system_info error: {str(e)}')
            return f"COVINANCE: Error getting system info - {str(e)}"
    
    def covinance_nearby_systems(self, args, projected_states) -> str:
        """List nearby systems within radius"""
        try:
            system_name = args.get('system_name', '')
            max_distance = args.get('max_distance', 50)
            limit = args.get('limit', 20)
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Finding systems near {system_name} within {max_distance}ly')
            
            endpoint = f'/system/name/{quote(system_name)}/nearby'
            params = {'maxDistance': max_distance}
            
            response = self.call_ardent_api(endpoint, params)
            
            if "error" in response:
                if response.get('status_code') == 404:
                    return f"COVINANCE: System '{system_name}' not found."
                return f"COVINANCE: Error - {response['error']}"
            
            if not isinstance(response, list) or len(response) == 0:
                return f"COVINANCE: No systems found within {max_distance}ly of {system_name}."
            
            # Sort by distance
            sorted_systems = sorted(response, key=lambda x: x.get('distance', 999))
            
            result = [f"COVINANCE: Found {len(sorted_systems)} systems within {max_distance}ly of {system_name}"]
            result.append(f"\n\nNearest {min(limit, len(sorted_systems))} systems:\n")
            
            for i, sys in enumerate(sorted_systems[:limit], 1):
                name = sys.get('systemName', 'Unknown')
                dist = sys.get('distance', 0)
                result.append(f"\n{i}. {name}: {dist:.2f} LY")
            
            if len(sorted_systems) > limit:
                result.append(f"\n\n({len(sorted_systems) - limit} more systems available)")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE nearby_systems error: {str(e)}')
            return f"COVINANCE: Error finding nearby systems - {str(e)}"
    
    def covinance_distance_between(self, args, projected_states) -> str:
        """
        Calculate distance between two systems
        
        Voice triggers:
        - "How far is Leesti?"
        - "Distance to Sol"
        - "How far am I from [system]?"
        - "Distance between [system1] and [system2]"
        - "How many light years to [system]?"
        
        Args:
            system_name: Target system (required)
            reference_system: Starting system (optional, uses current location if not specified)
        
        Returns: Distance in light years
        """
        try:
            target_system = args.get('system_name', '').strip()
            reference_system = args.get('reference_system', '').strip()
            
            if not target_system:
                return "COVINANCE: No target system specified. Please specify which system to calculate distance to."
            
            # Get reference system (current location if not specified)
            if not reference_system:
                self.update_location_from_journal()
                if not self.current_system:
                    return "COVINANCE: Unable to determine your current location. Dock somewhere or specify a reference system."
                reference_system = self.current_system
            
            log('info', f'COVINANCE: Calculating distance from {reference_system} to {target_system}')
            
            # Get coordinates for both systems using helper method
            coords1 = self._get_system_coordinates(reference_system)
            coords2 = self._get_system_coordinates(target_system)
            
            if not coords1:
                return f"COVINANCE: Unable to find coordinates for '{reference_system}'. Check system name spelling."
            
            if not coords2:
                return f"COVINANCE: Unable to find coordinates for '{target_system}'. Check system name spelling."
            
            # Calculate 3D distance
            import math
            dx = coords2['x'] - coords1['x']
            dy = coords2['y'] - coords1['y']
            dz = coords2['z'] - coords1['z']
            distance = math.sqrt(dx**2 + dy**2 + dz**2)
            
            # Format result
            result = []
            result.append(f"COVINANCE: Distance from {reference_system} to {target_system}")
            result.append(f"\n\n📏 {distance:.2f} light-years")
            
            # Add context if within jump range
            journal_data = self.read_latest_journal()
            if journal_data and 'MaxJumpRange' in journal_data:
                max_jump = journal_data['MaxJumpRange']
                if distance <= max_jump:
                    result.append(f"\n✅ Within your jump range ({max_jump:.2f} LY)")
                else:
                    jumps_needed = math.ceil(distance / max_jump)
                    result.append(f"\n⚠️ Outside jump range (need ~{jumps_needed} jumps)")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE distance_between error: {str(e)}')
            return f"COVINANCE: Error calculating distance - {str(e)}"
    
    def covinance_system_all_commodities(self, args, projected_states) -> str:
        """Get ALL trade orders in system (complete market snapshot)"""
        try:
            system_name = args.get('system_name', '')
        
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
        
            log('info', f'COVINANCE: Getting complete market data for {system_name}')
        
            # Use exports + imports instead of /commodities (more reliable for large systems)
            exports_endpoint = f'/system/name/{quote(system_name)}/commodities/exports'
            imports_endpoint = f'/system/name/{quote(system_name)}/commodities/imports'
        
            exports = self.call_ardent_api(exports_endpoint, {})
            imports = self.call_ardent_api(imports_endpoint, {})
        
            if "error" in exports and "error" in imports:
                if exports.get('status_code') == 404:
                    return f"COVINANCE: No market data for '{system_name}'."
                return f"COVINANCE: Error - {exports.get('error', 'Unknown error')}"
        
            # Safely get lists
            exports_list = exports if isinstance(exports, list) else []
            imports_list = imports if isinstance(imports, list) else []
        
            if len(exports_list) == 0 and len(imports_list) == 0:
                return f"COVINANCE: No trade orders found in {system_name}."
        
            # Count unique commodities and stations from both
            export_commodities = set(o.get('commodityName', '') for o in exports_list)
            import_commodities = set(o.get('commodityName', '') for o in imports_list)
            all_commodities = export_commodities | import_commodities
        
            export_stations = set(o.get('stationName', '') for o in exports_list)
            import_stations = set(o.get('stationName', '') for o in imports_list)
            all_stations = export_stations | import_stations
        
            result = [f"COVINANCE: Market snapshot for {system_name}"]
            result.append(f"\n\nBuy Opportunities: {len(exports_list)} orders")
            result.append(f"\nSell Opportunities: {len(imports_list)} orders")
            result.append(f"\nTotal Orders: {len(exports_list) + len(imports_list)}")
            result.append(f"\n\nUnique Commodities: {len(all_commodities)}")
            result.append(f"\nActive Stations: {len(all_stations)}")
        
            return "".join(result)
        
        except Exception as e:
            log('error', f'COVINANCE system_all_commodities error: {str(e)}')
            return f"COVINANCE: Error getting market data - {str(e)}"

    
    def covinance_station_commodities(self, args, projected_states) -> str:
        """Get full market for specific station"""
        try:
            station_name = args.get('station_name', '')
            system_name = args.get('system_name', '')
            
            if not station_name:
                return "COVINANCE: No station name specified."
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Getting market for {station_name} in {system_name}')
            
            endpoint = f'/system/name/{system_name}/market/name/{station_name}/commodities'
            response = self.call_ardent_api(endpoint, {})
            
            if "error" in response:
                if response.get('status_code') == 404:
                    return f"COVINANCE: Station '{station_name}' not found in {system_name} or has no market data."
                return f"COVINANCE: Error - {response['error']}"
            
            if not isinstance(response, list) or len(response) == 0:
                return f"COVINANCE: No market data for {station_name} in {system_name}."
            
            # Separate buy/sell
            buy_orders = [o for o in response if o.get('stock', 0) > 0]
            sell_orders = [o for o in response if o.get('demand', 0) > 0]
            
            result = [f"COVINANCE: Market at {station_name} ({system_name})"]
            result.append(f"\n\nCommodities Available:")
            result.append(f"\n  You can BUY: {len(buy_orders)} commodities")
            result.append(f"\n  You can SELL: {len(sell_orders)} commodities")
            result.append(f"\n  Total: {len(response)} trade orders")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE station_commodities error: {str(e)}')
            return f"COVINANCE: Error getting station market - {str(e)}"
    
    def covinance_system_markets(self, args, projected_states) -> str:
        """List stations with active commodity markets"""
        try:
            system_name = args.get('system_name', '')
            
            if not system_name:
                if not self.current_system:
                    return "COVINANCE: No system specified and current location unknown."
                system_name = self.current_system
            
            log('info', f'COVINANCE: Listing markets in {system_name}')
            
            endpoint = f'/system/name/{system_name}/markets'
            response = self.call_ardent_api(endpoint, {})
            
            if "error" in response:
                if response.get('status_code') == 404:
                    return f"COVINANCE: No market data for '{system_name}'."
                return f"COVINANCE: Error - {response['error']}"
            
            if not isinstance(response, list) or len(response) == 0:
                return f"COVINANCE: No active markets in {system_name}."
            
            # Sort by distance
            sorted_markets = sorted(response, key=lambda x: x.get('distanceToArrival', 999))
            
            result = [f"COVINANCE: {len(sorted_markets)} stations with commodity markets in {system_name}:\n"]
            
            for i, market in enumerate(sorted_markets, 1):
                name = market.get('stationName', 'Unknown')
                dist = market.get('distanceToArrival', 0)
                station_type = market.get('stationType', 'Unknown')
                updated = market.get('updatedAt', '')
                
                time_ago = self.format_time_ago(updated) if updated else "unknown"
                
                result.append(f"\n{i}. {name} ({station_type})")
                result.append(f"\n   {dist:,.0f} LS | Updated {time_ago}")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE system_markets error: {str(e)}')
            return f"COVINANCE: Error listing markets - {str(e)}"
    
    def _calculate_data_age(self, updated_at: str) -> int:
        """Calculate how many days old the data is"""
        try:
            from datetime import datetime, timezone
            updated = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            age = datetime.now(timezone.utc) - updated
            return age.days
        except Exception:
            return 999    # ==============================================================
    # PHASE 2: TRADE ROUTE PLANNING (9 actions)
    # ==============================================================
    
    def covinance_best_trade_from_here(self, args, projected_states) -> str:
        """
        Find most profitable commodities to buy at current location (v7.2).
        
        Parameters:
        - max_distance: Search radius in LY (default: your jump range)
        - min_profit_margin: Minimum profit per unit (default: None = show all)
        - include_surface_stations: Include planetary bases (default: True)
          Set to False when user says: "no surface", "exclude surface", "no planetary", "without surface"
        - include_fleet_carriers: Include carriers (default: False)
          Set to True when user says: "include carriers", "with carriers"
        
        Returns: Top 5 profitable commodities with sell locations.
        """
        try:
            # Get Batch 2 optional parameters
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            min_profit_margin = args.get('min_profit_margin', None)
            
            # v7.2.1: Show incompatible opportunities
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            # Get Batch 1 critical parameters from Journal
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '')
            required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            jump_range = journal_data.get('MaxJumpRange', 20)
            max_distance = args.get('max_distance', jump_range)
            
            # Legacy parameter (now optional, defaults to min_profit_margin)
            min_profit = args.get('min_profit', min_profit_margin)  # Don't default to 1000!
            if min_profit_margin:
                min_profit = min_profit_margin
            
            # Get current location
            if not self.current_system:
                return "COVINANCE: Current location unknown. Dock at a station first."
            
            log('info', f'COVINANCE: Finding best trades from {self.current_system} within {max_distance}ly (ship: {ship_type or "Unknown"}, pad: {required_pad})')
            
            # Get all exports (what we can buy here) with pad filtering
            exports_endpoint = f'/system/name/{self.current_system}/commodities/exports'
            exports_params = {
                'minVolume': 1,  # API default: no arbitrary restriction
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                'fleetCarriers': str(include_carriers).lower()
            }
            exports = self.call_ardent_api(exports_endpoint, exports_params)
            
            if "error" in exports or not isinstance(exports, list) or len(exports) == 0:
                return f"COVINANCE: No commodities available to buy in {self.current_system} (pad size: {required_pad})."
            
            # Client-side filter for surface stations if needed
            if not include_surface:
                exports = [e for e in exports if e.get('stationType') != 'OnFootSettlement']
            
            total_exports = len(exports)
            
            # For each commodity, find best sell price nearby
            opportunities = []
            commodities_checked = 0
            
            for export in exports[:10]:  # Check top 10 commodities by stock
                commodity = export.get('commodityName', '')
                buy_price = export.get('buyPrice', 0)
                buy_station = export.get('stationName', '')
                buy_station_type = export.get('stationType', '')
                
                if buy_price == 0:
                    continue
                
                commodities_checked += 1
                
                # Find nearby sell opportunities with pad filtering
                nearby_endpoint = f'/system/name/{self.current_system}/commodity/name/{commodity}/nearby/imports'
                nearby_params = {
                    'maxDistance': max_distance,
                    'minVolume': 1,  # API default: no arbitrary restriction
                    'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                    'maxDaysAgo': 365,
                    'fleetCarriers': str(include_carriers).lower()
                }
                
                nearby_sells = self.call_ardent_api(nearby_endpoint, nearby_params)
                
                if isinstance(nearby_sells, list) and len(nearby_sells) > 0:
                    # Client-side filter for surface stations if needed
                    if not include_surface:
                        nearby_sells = [s for s in nearby_sells if s.get('stationType') != 'OnFootSettlement']
                    
                    if len(nearby_sells) == 0:
                        continue
                    
                    # Get best sell price
                    best_sell = max(nearby_sells, key=lambda x: x.get('sellPrice', 0))
                    sell_price = best_sell.get('sellPrice', 0)
                    sell_station = best_sell.get('stationName', '')
                    sell_system = best_sell.get('systemName', '')
                    distance = best_sell.get('distance', 0)
                    
                    profit = sell_price - buy_price
                    
                    # Only filter if min_profit explicitly set
                    if not min_profit or profit >= min_profit:
                        opportunities.append({
                            'commodity': commodity,
                            'buy_price': buy_price,
                            'buy_station': buy_station,
                            'sell_price': sell_price,
                            'sell_station': sell_station,
                            'sell_system': sell_system,
                            'profit': profit,
                            'distance': distance
                        })
            
            # Build response with transparent scope
            import re
            result = [f"COVINANCE: Top profitable trades from {self.current_system}\n"]
            
            # Transparent scope - COVAS MUST READ VERBATIM
            result.append(f"\n[COVAS: READ VERBATIM - DO NOT PARAPHRASE]\n")
            result.append(f"ðŸ” SEARCH SCOPE:\n")
            result.append(f"  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)\n")
            result.append(f"  â€¢ Distance: {max_distance:.1f} LY")
            if max_distance == jump_range:
                result.append(f" (your 1-jump range)")
            result.append(f"\n  â€¢ Commodities checked: {commodities_checked} of {total_exports} available\n")
            result.append(f"  â€¢ Opportunities found: {len(opportunities)}\n")
            
            # Show active filters
            filters_active = []
            if not include_surface:
                filters_active.append("Surface stations excluded")
            if include_carriers:
                filters_active.append("Fleet carriers included")
            if min_profit:
                filters_active.append(f"Min profit: {min_profit:,} CR")
            if filters_active:
                result.append(f"  â€¢ Filters: {', '.join(filters_active)}\n")
            if show_all_pad_sizes:
                result.append(f"  â€¢ All pad sizes: Shown (incompatible marked with âš ï¸)\n")
            
            result.append(f"\nâš ï¸  LIMITED SEARCH - To expand:\n")
            result.append(f"  â€¢ Longer range: max_distance={int(max_distance * 1.5)}\n")
            if min_profit:
                result.append(f"  â€¢ Lower profit: min_profit_margin={int(min_profit * 0.5)}\n")
            if show_all_pad_sizes:
                result.append(f"  â€¢ All pad sizes: Shown (incompatible marked with âš ï¸)\n")
            result.append(f"[END VERBATIM SECTION]\n")
            
            if len(opportunities) == 0:
                result.append(f"\nâŒ No profitable trades found matching your criteria.")
                return "".join(result)
            
            # Sort by profit
            opportunities.sort(key=lambda x: x['profit'], reverse=True)
            
            # Main results
            result.append(f"\nðŸ“Š TOP OPPORTUNITIES:\n")
            
            for i, opp in enumerate(opportunities[:5], 1):
                commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', opp['commodity']).title()
                result.append(f"\n{i}. {commodity_formatted}: {opp['profit']:,} CR/unit profit")
                result.append(f"\n   Buy at {opp['buy_station']}: {opp['buy_price']:,} CR")
                result.append(f"\n   Sell at {opp['sell_station']} ({opp['sell_system']}): {opp['sell_price']:,} CR")
                result.append(f"\n   Distance: {opp['distance']:.1f} ly")
            
            if len(opportunities) > 5:
                result.append(f"\n\nðŸ’¡ {len(opportunities) - 5} more opportunities available")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE best_trade_from_here error: {str(e)}')
            return f"COVINANCE: Error finding trades - {str(e)}"
    
    def covinance_trade_route(self, args, projected_states) -> str:
        """
        Find optimal route for specific commodity between systems (v7.2).
        
        Parameters:
        - commodity_name: Commodity to trade (required)
        - origin_system: Starting system (default: current location)
        - destination_system: Ending system (required)
        - include_surface_stations: Include planetary bases (default: True)
        - include_fleet_carriers: Include carriers (default: False)
        
        Returns: Best buy station at origin, best sell station at destination.
        """
        try:
            # Get Batch 2 optional parameters
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            
            # v7.2.1: Show incompatible alternatives
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            # Get Batch 1 critical parameters from Journal
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '')
            required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            jump_range = journal_data.get('MaxJumpRange', 20) if journal_data else 20
            
            commodity_name = self._normalize_commodity_name(args.get('commodity_name', ''))
            origin_system = args.get('origin_system', '')
            destination_system = args.get('destination_system', '')
            
            if not commodity_name:
                return "COVINANCE: No commodity specified."
            
            # Use current system as origin if not specified
            if not origin_system:
                if not self.current_system:
                    return "COVINANCE: No origin system specified and current location unknown."
                origin_system = self.current_system
            
            if not destination_system:
                return "COVINANCE: No destination system specified."
            
            log('info', f'COVINANCE: Finding route for {commodity_name}: {origin_system} â†’ {destination_system} (ship: {ship_type or "Unknown"}, pad: {required_pad})')
            
            # Find best buy price at origin with pad filtering
            origin_endpoint = f'/system/name/{origin_system}/commodity/name/{commodity_name}'
            origin_params = {
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                'fleetCarriers': str(include_carriers).lower()
            }
            origin_data = self.call_ardent_api(origin_endpoint, origin_params)
            
            # Find best sell price at destination with pad filtering
            dest_endpoint = f'/system/name/{destination_system}/commodity/name/{commodity_name}'
            dest_params = {
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                'fleetCarriers': str(include_carriers).lower()
            }
            dest_data = self.call_ardent_api(dest_endpoint, dest_params)
            
            # Parse origin (buy) data
            buy_orders = []
            if isinstance(origin_data, list):
                buy_orders = [o for o in origin_data if o.get('stock', 0) > 0]
            
            # Client-side filter for surface stations if needed
            if not include_surface:
                buy_orders = [o for o in buy_orders if o.get('stationType') != 'OnFootSettlement']
            
            # Parse destination (sell) data
            sell_orders = []
            if isinstance(dest_data, list):
                sell_orders = [o for o in dest_data if o.get('demand', 0) > 0]
            
            # Client-side filter for surface stations if needed
            if not include_surface:
                sell_orders = [o for o in sell_orders if o.get('stationType') != 'OnFootSettlement']
            
            if len(buy_orders) == 0:
                return f"COVINANCE: No {commodity_name} available to buy in {origin_system} (pad: {required_pad})."
            
            if len(sell_orders) == 0:
                return f"COVINANCE: No demand for {commodity_name} in {destination_system} (pad: {required_pad})."
            
            # v7.2.1: Split compatible/incompatible if showing all
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            compatible_buy = []
            incompatible_buy = []
            for o in buy_orders:
                station_pad_size = pad_size_map.get(o.get('maxLandingPadSize', 'S'), 1)
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_buy.append(o)
                else:
                    compatible_buy.append(o)
            
            compatible_sell = []
            incompatible_sell = []
            for o in sell_orders:
                station_pad_size = pad_size_map.get(o.get('maxLandingPadSize', 'S'), 1)
                if show_all_pad_sizes and station_pad_size < required_pad_size:
                    incompatible_sell.append(o)
                else:
                    compatible_sell.append(o)
            
            # Find best buy and sell (prefer compatible)
            if compatible_buy:
                best_buy = min(compatible_buy, key=lambda x: x.get('buyPrice', 999999))
            else:
                best_buy = min(buy_orders, key=lambda x: x.get('buyPrice', 999999))
            
            if compatible_sell:
                best_sell = max(compatible_sell, key=lambda x: x.get('sellPrice', 0))
            else:
                best_sell = max(sell_orders, key=lambda x: x.get('sellPrice', 0))
            
            buy_price = best_buy.get('buyPrice', 0)
            buy_station = best_buy.get('stationName', 'Unknown')
            buy_stock = best_buy.get('stock', 0)
            buy_pad = best_buy.get('maxLandingPadSize', 'S')
            
            sell_price = best_sell.get('sellPrice', 0)
            sell_station = best_sell.get('stationName', 'Unknown')
            sell_demand = best_sell.get('demand', 0)
            sell_pad = best_sell.get('maxLandingPadSize', 'S')
            
            # Check if best options are incompatible
            buy_incompatible = best_buy in incompatible_buy if show_all_pad_sizes else False
            sell_incompatible = best_sell in incompatible_sell if show_all_pad_sizes else False
            
            profit = sell_price - buy_price
            profit_pct = (profit / buy_price * 100) if buy_price > 0 else 0
            
            import re
            commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', commodity_name).title()
            
            result = [f"COVINANCE: Route for {commodity_formatted}\n"]
            
            # Transparent scope - COVAS MUST READ VERBATIM
            result.append(f"\n[COVAS: READ VERBATIM - DO NOT PARAPHRASE]\n")
            result.append(f"ðŸ” SEARCH SCOPE:\n")
            result.append(f"  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)\n")
            result.append(f"  â€¢ Origin: {origin_system}\n")
            result.append(f"  â€¢ Destination: {destination_system}\n")
            
            # Show active filters
            filters_active = []
            if not include_surface:
                filters_active.append("Surface stations excluded")
            if include_carriers:
                filters_active.append("Fleet carriers included")
            if filters_active:
                result.append(f"  â€¢ Filters: {', '.join(filters_active)}\n")
            if show_all_pad_sizes:
                result.append(f"  â€¢ All pad sizes: Shown (incompatible hops marked)\n")
            result.append(f"[END VERBATIM SECTION]\n")
            
            result.append(f"\nðŸ“Š OPTIMAL ROUTE:\n")
            
            if buy_incompatible:
                result.append(f"\nâš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {buy_pad} PAD - YOUR {ship_type.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
            result.append(f"\nBUY at {buy_station} ({origin_system})")
            result.append(f"\n  Price: {buy_price:,} CR")
            result.append(f"\n  Stock: {buy_stock:,} units")
            
            if sell_incompatible:
                result.append(f"\n\nâš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {sell_pad} PAD - YOUR {ship_type.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
            result.append(f"\n\nSELL at {sell_station} ({destination_system})")
            result.append(f"\n  Price: {sell_price:,} CR")
            result.append(f"\n  Demand: {sell_demand:,} units")
            result.append(f"\n\nPROFIT: {profit:,} CR/unit ({profit_pct:.1f}%)")
            
            # v7.2.1: Add pad compatibility summary
            if show_all_pad_sizes and (incompatible_buy or incompatible_sell):
                result.append(f"\n\nðŸ“Š PAD COMPATIBILITY:")
                if buy_incompatible or sell_incompatible:
                    result.append(f"\n  âš ï¸  Best route requires stations your {ship_type or 'ship'} cannot access!")
                    result.append(f"\n  Switch to: Python, Krait, AspX for better access")
                
                if incompatible_buy and compatible_buy:
                    compat_best = min(compatible_buy, key=lambda x: x.get('buyPrice', 999999))
                    compat_price = compat_best.get('buyPrice', 0)
                    result.append(f"\n  â€¢ Compatible buy: {compat_price:,} CR (vs {buy_price:,} CR incompatible)")
                
                if incompatible_sell and compatible_sell:
                    compat_best = max(compatible_sell, key=lambda x: x.get('sellPrice', 0))
                    compat_price = compat_best.get('sellPrice', 0)
                    result.append(f"\n  â€¢ Compatible sell: {compat_price:,} CR (vs {sell_price:,} CR incompatible)")
            
            # Show alternative options if available
            if len(buy_orders) > 1:
                result.append(f"\n\nðŸ’¡ {len(buy_orders) - 1} other buy option(s) available in {origin_system}")
            if len(sell_orders) > 1:
                result.append(f"\nðŸ’¡ {len(sell_orders) - 1} other sell option(s) available in {destination_system}")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE trade_route error: {str(e)}')
            return f"COVINANCE: Error finding route - {str(e)}"
    
    def covinance_nearby_profitable_trades(self, args, projected_states) -> str:
        """
        Find all profitable opportunities within radius (v7.2).
        
        Parameters:
        - reference_system: Center system (default: current location)
        - max_distance: Search radius in LY (default: your jump range)
        - min_profit_margin: Minimum profit per unit (default: None = show all)
        - include_surface_stations: Include planetary bases (default: True)
        - include_fleet_carriers: Include carriers (default: False)
        
        Returns: Top 5 profitable trades within range.
        """
        try:
            # Get Batch 2 optional parameters
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            min_profit_margin = args.get('min_profit_margin', None)
            
            # v7.2.1: Show incompatible opportunities
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            # Get Batch 1 critical parameters from Journal
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '')
            required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            jump_range = journal_data.get('MaxJumpRange', 20)
            max_distance = args.get('max_distance', jump_range)
            
            # Legacy parameter (now optional, defaults to min_profit_margin)
            min_profit = args.get('min_profit', min_profit_margin)  # Don't default to 2000!
            if min_profit_margin:
                min_profit = min_profit_margin
            
            reference_system = args.get('reference_system', '')
            
            if not reference_system:
                self.update_location_from_journal()
                if not self.current_system:
                    return "COVINANCE: No reference system specified and current location unknown."
                reference_system = self.current_system
            
            log('info', f'COVINANCE: Finding profitable trades within {max_distance}ly of {reference_system} (ship: {ship_type or "Unknown"}, pad: {required_pad})')
            
            # Get nearby systems
            nearby_endpoint = f'/system/name/{reference_system}/nearby'
            nearby_systems = self.call_ardent_api(nearby_endpoint, {'maxDistance': max_distance})
            
            if not isinstance(nearby_systems, list) or len(nearby_systems) == 0:
                return f"COVINANCE: No systems found within {max_distance}ly of {reference_system}."
            
            total_systems = len(nearby_systems)
            
            # Sample top commodities to check
            test_commodities = ['palladium', 'gold', 'bertrandite', 'indite', 'gallite', 
                              'painite', 'platinum', 'osmium', 'praseodymium']
            
            all_opportunities = []
            
            for commodity in test_commodities:
                # Find nearby buy opportunities with pad filtering
                buy_endpoint = f'/system/name/{reference_system}/commodity/name/{commodity}/nearby/exports'
                buy_params = {
                    'maxDistance': max_distance,
                    'minVolume': 1,  # API default: no arbitrary restriction
                    'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                    'maxDaysAgo': 365,
                    'fleetCarriers': str(include_carriers).lower()
                }
                buys = self.call_ardent_api(buy_endpoint, buy_params)
                
                # Find nearby sell opportunities with pad filtering
                sell_endpoint = f'/system/name/{reference_system}/commodity/name/{commodity}/nearby/imports'
                sell_params = {
                    'maxDistance': max_distance,
                    'minVolume': 1,  # API default: no arbitrary restriction
                    'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                    'maxDaysAgo': 365,
                    'fleetCarriers': str(include_carriers).lower()
                }
                sells = self.call_ardent_api(sell_endpoint, sell_params)
                
                # Client-side filter for surface stations if needed
                if isinstance(buys, list) and not include_surface:
                    buys = [b for b in buys if b.get('stationType') != 'OnFootSettlement']
                
                if isinstance(sells, list) and not include_surface:
                    sells = [s for s in sells if s.get('stationType') != 'OnFootSettlement']
                
                if isinstance(buys, list) and isinstance(sells, list):
                    # Cross-reference for profit
                    for buy in buys[:20]:  # Limit to top 20 to avoid timeout
                        buy_price = buy.get('buyPrice', 0)
                        if buy_price == 0:
                            continue
                            
                        for sell in sells[:20]:
                            sell_price = sell.get('sellPrice', 0)
                            profit = sell_price - buy_price
                            
                            # Sanity check: Filter suspicious prices
                            if profit > 1_000_000:  # More than 1M CR/unit is suspicious
                                log('warning', f'COVINANCE: Suspicious profit for {commodity}: {profit:,} CR - skipping')
                                continue
                            
                            # Only filter if min_profit explicitly set
                            if not min_profit or profit >= min_profit:
                                all_opportunities.append({
                                    'commodity': commodity,
                                    'buy_system': buy.get('systemName', ''),
                                    'buy_station': buy.get('stationName', ''),
                                    'buy_price': buy_price,
                                    'buy_pad': buy.get('maxLandingPadSize', 'S'),
                                    'sell_system': sell.get('systemName', ''),
                                    'sell_station': sell.get('stationName', ''),
                                    'sell_price': sell_price,
                                    'sell_pad': sell.get('maxLandingPadSize', 'S'),
                                    'profit': profit,
                                    'buy_distance': buy.get('distance', 0),
                                    'sell_distance': sell.get('distance', 0)
                                })
            
            # Build response with transparent scope
            import re
            result = [f"COVINANCE: Profitable trades within {max_distance}ly of {reference_system}\n"]
            
            # Transparent scope - COVAS MUST READ VERBATIM
            result.append(f"\n[COVAS: READ VERBATIM - DO NOT PARAPHRASE]\n")
            result.append(f"ðŸ” SEARCH SCOPE:\n")
            result.append(f"  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)\n")
            result.append(f"  â€¢ Distance: {max_distance:.1f} LY")
            if max_distance == jump_range:
                result.append(f" (your 1-jump range)")
            result.append(f"\n  â€¢ Systems nearby: {total_systems}\n")
            result.append(f"  â€¢ Commodities checked: {len(test_commodities)}\n")
            result.append(f"  â€¢ Opportunities found: {len(all_opportunities)}\n")
            
            # Show active filters
            filters_active = []
            if not include_surface:
                filters_active.append("Surface stations excluded")
            if include_carriers:
                filters_active.append("Fleet carriers included")
            if min_profit:
                filters_active.append(f"Min profit: {min_profit:,} CR")
            if filters_active:
                result.append(f"  â€¢ Filters: {', '.join(filters_active)}\n")
            if show_all_pad_sizes:
                result.append(f"  â€¢ All pad sizes: Shown (incompatible marked with âš ï¸)\n")
            
            result.append(f"\nâš ï¸  LIMITED SEARCH - To expand:\n")
            result.append(f"  â€¢ Longer range: max_distance={int(max_distance * 1.5)}\n")
            if min_profit:
                result.append(f"  â€¢ Lower profit: min_profit_margin={int(min_profit * 0.5)}\n")
            result.append(f"[END VERBATIM SECTION]\n")
            
            if len(all_opportunities) == 0:
                result.append(f"\nâŒ No profitable trades found matching your criteria.")
                return "".join(result)
            
            # Sort by profit
            all_opportunities.sort(key=lambda x: x['profit'], reverse=True)
            
            # Main results
            result.append(f"\nðŸ“Š TOP OPPORTUNITIES:\n")
            
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            
            for i, opp in enumerate(all_opportunities[:5], 1):
                # v7.2.1: Check compatibility
                buy_pad_size = pad_size_map.get(opp.get('buy_pad', 'S'), 1)
                sell_pad_size = pad_size_map.get(opp.get('sell_pad', 'S'), 1)
                buy_incompatible = show_all_pad_sizes and buy_pad_size < required_pad_size
                sell_incompatible = show_all_pad_sizes and sell_pad_size < required_pad_size
                
                commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', opp['commodity']).title()
                result.append(f"\n{i}. {commodity_formatted}: {opp['profit']:,} CR/unit")
                
                if buy_incompatible:
                    result.append(f"\n   âš ï¸âš ï¸âš ï¸ [BUY INCOMPATIBLE: {opp.get('buy_pad', 'S')} PAD - YOUR {ship_type.upper()} CANNOT LAND!]")
                result.append(f"\n   Buy: {opp['buy_station']} ({opp['buy_system']}) - {opp['buy_distance']:.1f} ly")
                
                if sell_incompatible:
                    result.append(f"\n   âš ï¸âš ï¸âš ï¸ [SELL INCOMPATIBLE: {opp.get('sell_pad', 'S')} PAD - YOUR {ship_type.upper()} CANNOT LAND!]")
                result.append(f"\n   Sell: {opp['sell_station']} ({opp['sell_system']}) - {opp['sell_distance']:.1f} ly")
            
            if len(all_opportunities) > 5:
                result.append(f"\n\nðŸ’¡ {len(all_opportunities) - 5} more opportunities available")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE nearby_profitable_trades error: {str(e)}')
            return f"COVINANCE: Error finding trades - {str(e)}"
    
    def covinance_optimal_trade_now(self, args, projected_states) -> str:
        """
        Find best trade based on current ship state (cargo, credits, location) (v7.2).
        
        Parameters:
        - cargo_capacity: Cargo space in tons (default: from Journal)
        - available_credits: Budget in CR (default: from Journal)
        - max_distance: Search radius in LY (default: your jump range)
        - include_surface_stations: Include planetary bases (default: True)
        - include_fleet_carriers: Include carriers (default: False)
        
        Returns: Single best affordable trade for your current situation.
        """
        try:
            # Get Batch 2 optional parameters
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            
            # Get user-provided parameters (can override Journal)
            cargo_capacity = args.get('cargo_capacity', None)
            available_credits = args.get('available_credits', None)
            
            # Try to read from Journal if not provided
            journal_data = self.read_latest_journal()
            if journal_data:
                cargo_capacity = cargo_capacity or journal_data.get('CargoCapacity', 0)
                available_credits = available_credits or journal_data.get('Credits', 0)
            
            # Get Batch 1 critical parameters from Journal
            ship_type = journal_data.get('ShipType', '') if journal_data else ''
            required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            jump_range = journal_data.get('MaxJumpRange', 20) if journal_data else 20
            max_distance = args.get('max_distance', jump_range)
            
            if not self.current_system:
                return "COVINANCE: Current location unknown."
            
            if cargo_capacity is None or cargo_capacity == 0:
                return "COVINANCE: Cargo capacity unknown. Please specify or ensure Journal is accessible."
            
            if available_credits is None or available_credits == 0:
                return "COVINANCE: Available credits unknown. Please specify or ensure Journal is accessible."
            
            log('info', f'COVINANCE: Finding optimal trade with {cargo_capacity}T cargo, {available_credits:,} CR (ship: {ship_type or "Unknown"}, pad: {required_pad})')
            
            # Get exports with pad filtering
            exports_endpoint = f'/system/name/{self.current_system}/commodities/exports'
            # v7.2.1: Get show_all_pad_sizes parameter
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            exports_params = {
                'minVolume': cargo_capacity,
                'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                'fleetCarriers': str(include_carriers).lower()
            }
            exports = self.call_ardent_api(exports_endpoint, exports_params)
            
            if "error" in exports or not isinstance(exports, list):
                return f"COVINANCE: No commodities available in {self.current_system} (pad: {required_pad})."
            
            # Client-side filter for surface stations if needed
            if not include_surface:
                exports = [e for e in exports if e.get('stationType') != 'OnFootSettlement']
            
            total_exports = len(exports)
            affordable_opportunities = []
            commodities_checked = 0
            
            for export in exports[:15]:
                commodity = export.get('commodityName', '')
                buy_price = export.get('buyPrice', 0)
                buy_station = export.get('stationName', '')
                stock = export.get('stock', 0)
                
                commodities_checked += 1
                
                # Check if we can afford at least one full cargo load
                cost_per_load = buy_price * cargo_capacity
                if cost_per_load > available_credits or buy_price == 0:
                    continue
                
                # Find nearby sell with pad filtering
                nearby_endpoint = f'/system/name/{self.current_system}/commodity/name/{commodity}/nearby/imports'
                nearby_params = {
                    'maxDistance': max_distance,
                    'minVolume': cargo_capacity,
                    'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,
                    'maxDaysAgo': 365,
                    'fleetCarriers': str(include_carriers).lower()
                }
                nearby_sells = self.call_ardent_api(nearby_endpoint, nearby_params)
                
                # Client-side filter for surface stations if needed
                if isinstance(nearby_sells, list) and not include_surface:
                    nearby_sells = [s for s in nearby_sells if s.get('stationType') != 'OnFootSettlement']
                
                if isinstance(nearby_sells, list) and len(nearby_sells) > 0:
                    best_sell = max(nearby_sells, key=lambda x: x.get('sellPrice', 0))
                    sell_price = best_sell.get('sellPrice', 0)
                    
                    profit_per_unit = sell_price - buy_price
                    total_profit = profit_per_unit * cargo_capacity
                    
                    if profit_per_unit > 0:
                        affordable_opportunities.append({
                            'commodity': commodity,
                            'buy_price': buy_price,
                            'buy_station': buy_station,
                            'sell_price': sell_price,
                            'sell_station': best_sell.get('stationName', ''),
                            'sell_system': best_sell.get('systemName', ''),
                            'profit_per_unit': profit_per_unit,
                            'total_profit': total_profit,
                            'distance': best_sell.get('distance', 0),
                            'investment': cost_per_load
                        })
            
            # Build response with transparent scope
            import re
            result = [f"COVINANCE: Optimal trade RIGHT NOW\n"]
            
            # Transparent scope - COVAS MUST READ VERBATIM
            result.append(f"\n[COVAS: READ VERBATIM - DO NOT PARAPHRASE]\n")
            result.append(f"ðŸ” SEARCH SCOPE:\n")
            result.append(f"  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)\n")
            result.append(f"  â€¢ Cargo: {cargo_capacity}T\n")
            result.append(f"  â€¢ Budget: {available_credits:,} CR\n")
            result.append(f"  â€¢ Distance: {max_distance:.1f} LY")
            if max_distance == jump_range:
                result.append(f" (your 1-jump range)")
            result.append(f"\n  â€¢ Commodities checked: {commodities_checked} of {total_exports} available\n")
            result.append(f"  â€¢ Affordable options found: {len(affordable_opportunities)}\n")
            
            # Show active filters
            filters_active = []
            if not include_surface:
                filters_active.append("Surface stations excluded")
            if include_carriers:
                filters_active.append("Fleet carriers included")
            if filters_active:
                result.append(f"  â€¢ Filters: {', '.join(filters_active)}\n")
            if show_all_pad_sizes:
                result.append(f"  â€¢ All pad sizes: Shown (incompatible marked with âš ï¸)\n")
            
            result.append(f"\nâš ï¸  LIMITED SEARCH - To expand:\n")
            result.append(f"  â€¢ Longer range: max_distance={int(max_distance * 1.5)}\n")
            result.append(f"[END VERBATIM SECTION]\n")
            
            if len(affordable_opportunities) == 0:
                result.append(f"\nâŒ No affordable profitable trades found with {available_credits:,} CR budget.")
                return "".join(result)
            
            # Sort by total profit
            affordable_opportunities.sort(key=lambda x: x['total_profit'], reverse=True)
            best = affordable_opportunities[0]
            
            commodity_formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', best['commodity']).title()
            
            # v7.2.1: Check pad compatibility
            pad_size_map = {'S': 1, 'M': 2, 'L': 3}
            required_pad_size = pad_size_map.get(required_pad, 1)
            buy_pad_size = pad_size_map.get(best.get('buy_pad', 'S'), 1)
            sell_pad_size = pad_size_map.get(best.get('sell_pad', 'S'), 1)
            buy_incompatible = show_all_pad_sizes and buy_pad_size < required_pad_size
            sell_incompatible = show_all_pad_sizes and sell_pad_size < required_pad_size
            
            result.append(f"\nðŸ“Š BEST TRADE:\n")
            result.append(f"\nCommodity: {commodity_formatted}")
            
            if buy_incompatible:
                result.append(f"\n\nâš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {best.get('buy_pad', 'S')} PAD - YOUR {ship_type.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
            result.append(f"\n\n1. Buy {cargo_capacity}T at {best['buy_station']}")
            result.append(f"\n   Cost: {best['buy_price']:,} CR/unit ({best['investment']:,} CR total)")
            
            if sell_incompatible:
                result.append(f"\n\nâš ï¸âš ï¸âš ï¸ [INCOMPATIBLE: {best.get('sell_pad', 'S')} PAD - YOUR {ship_type.upper()} CANNOT LAND!] âš ï¸âš ï¸âš ï¸")
            result.append(f"\n\n2. Sell at {best['sell_station']} ({best['sell_system']})")
            result.append(f"\n   Revenue: {best['sell_price']:,} CR/unit")
            result.append(f"\n   Distance: {best['distance']:.1f} ly")
            result.append(f"\n\nTOTAL PROFIT: {best['total_profit']:,} CR")
            
            if len(affordable_opportunities) > 1:
                result.append(f"\n\nðŸ’¡ {len(affordable_opportunities) - 1} other affordable option(s) available")
            
            # v7.2.1: Add compatibility summary if showing all pad sizes
            if show_all_pad_sizes and (buy_incompatible or sell_incompatible):
                result.append(f"\n\nðŸ“Š PAD COMPATIBILITY:")
                result.append(f"\n  âš ï¸  Best trade requires stations your {ship_type or 'ship'} cannot access!")
                
                # Find best compatible alternative
                compatible_trades = [opp for opp in affordable_opportunities 
                                   if pad_size_map.get(opp.get('buy_pad', 'S'), 1) >= required_pad_size
                                   and pad_size_map.get(opp.get('sell_pad', 'S'), 1) >= required_pad_size]
                
                if compatible_trades:
                    compat_best = compatible_trades[0]
                    result.append(f"\n  â€¢ Compatible alternative: {compat_best['total_profit']:,} CR total")
                    result.append(f"\n    (vs {best['total_profit']:,} CR incompatible)")
                else:
                    result.append(f"\n  â€¢ No compatible alternatives found within constraints")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE optimal_trade_now error: {str(e)}')
            return f"COVINANCE: Error finding optimal trade - {str(e)}"
    
    def covinance_trade_within_jump_range(self, args, projected_states) -> str:
        """
        Find trades within ship's actual jump range (v7.2).
        
        Parameters:
        - jump_range: Jump range in LY (default: from Journal)
        - min_profit_margin: Minimum profit per unit (default: None = show all)
        - include_surface_stations: Include planetary bases (default: True)
        - include_fleet_carriers: Include carriers (default: False)
        
        Returns: Profitable trades within one jump.
        """
        try:
            # Get Batch 2 optional parameters (pass through)
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            min_profit_margin = args.get('min_profit_margin', None)
            
            # v7.2.1: Pass through show_all_pad_sizes
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            # Get jump range from args or Journal
            jump_range = args.get('jump_range', None)
            
            # Try to read from Journal
            if jump_range is None:
                journal_data = self.read_latest_journal()
                if journal_data:
                    jump_range = journal_data.get('MaxJumpRange', None)
                    ship_type = journal_data.get('ShipType', '')
                else:
                    ship_type = ''
            else:
                journal_data = self.read_latest_journal()
                ship_type = journal_data.get('ShipType', '') if journal_data else ''
            
            if jump_range is None or jump_range == 0:
                return "COVINANCE: Jump range unknown. Please specify or ensure Journal is accessible."
            
            if not self.current_system:
                return "COVINANCE: Current location unknown."
            
            log('info', f'COVINANCE: Finding trades within {jump_range:.1f}ly jump range (ship: {ship_type or "Unknown"})')
            
            # Delegate to nearby_profitable_trades with jump range
            # This will automatically inherit all v7.2 parameters since we retrofitted it
            return self.covinance_nearby_profitable_trades({
                'max_distance': jump_range,  # Use actual jump range, not int()
                'min_profit_margin': min_profit_margin or args.get('min_profit'),  # Don't default!
                'reference_system': self.current_system,
                'include_surface_stations': include_surface,
                'include_fleet_carriers': include_carriers,
                'show_all_pad_sizes': show_all_pad_sizes  # v7.2.1: Pass through
            }, projected_states)
            
        except Exception as e:
            log('error', f'COVINANCE trade_within_jump_range error: {str(e)}')
            return f"COVINANCE: Error finding trades - {str(e)}"
    
    def covinance_fill_remaining_cargo(self, args, projected_states) -> str:
        """
        Optimize profit with partial cargo space (v7.2).
        
        Parameters:
        - remaining_space: Cargo space left in tons (default: from Journal)
        - available_credits: Budget in CR (default: from Journal)
        - max_distance: Search radius in LY (default: your jump range)
        - include_surface_stations: Include planetary bases (default: True)
        - include_fleet_carriers: Include carriers (default: False)
        
        Returns: Best trade for remaining cargo capacity.
        """
        try:
            # Get Batch 2 optional parameters (pass through)
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            
            # v7.2.1: Pass through show_all_pad_sizes
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            # Get user parameters or read from Journal
            remaining_space = args.get('remaining_space', None)
            available_credits = args.get('available_credits', None)
            max_distance = args.get('max_distance', None)  # Will use jump range default in optimal_trade_now
            
            # Try Journal
            journal_data = self.read_latest_journal()
            if journal_data:
                cargo_capacity = journal_data.get('CargoCapacity', 0)
                cargo_used = journal_data.get('Cargo', 0)
                remaining_space = remaining_space or (cargo_capacity - cargo_used)
                available_credits = available_credits or journal_data.get('Credits', 0)
                ship_type = journal_data.get('ShipType', '')
            else:
                ship_type = ''
            
            if remaining_space is None or remaining_space == 0:
                return "COVINANCE: No remaining cargo space or unable to determine."
            
            if not self.current_system:
                return "COVINANCE: Current location unknown."
            
            log('info', f'COVINANCE: Optimizing {remaining_space}T remaining cargo (ship: {ship_type or "Unknown"})')
            
            # Delegate to optimal_trade_now with remaining space as capacity
            # This will automatically inherit all v7.2 parameters since we retrofitted it
            params = {
                'cargo_capacity': remaining_space,
                'available_credits': available_credits,
                'include_surface_stations': include_surface,
                'include_fleet_carriers': include_carriers,
                'show_all_pad_sizes': show_all_pad_sizes  # v7.2.1: Pass through
            }
            
            # Only add max_distance if user specified it (otherwise let optimal_trade_now use jump range)
            if max_distance is not None:
                params['max_distance'] = max_distance
            
            return self.covinance_optimal_trade_now(params, projected_states)
            
        except Exception as e:
            log('error', f'COVINANCE fill_remaining_cargo error: {str(e)}')
            return f"COVINANCE: Error optimizing cargo - {str(e)}"
    
    
    def covinance_circular_route(self, args, projected_states) -> str:
        """
        Build multi-hop circular trading loop (v7.2).
        
        Parameters:
        - num_hops: Number of stops (2-5, default 3)
        - start_system: Starting system (default: current location)
        - optimize_by: Optimization mode (default: 'profit')
          * 'profit' - Maximum credits per unit
            Examples: "most profitable", "best profit", "maximize profit"
          * 'distance_ly' - Shortest total distance
            Examples: "shortest distance", "closest", "minimum distance", "least LY"
          * 'jumps' - Fewest jumps
            Examples: "fewest jumps", "minimum jumps", "least jumps"
        - max_distance: Search radius in LY (default: your jump range)
        - include_surface_stations: Include planetary bases (default: True)
          Set to False when user says: "no surface", "exclude surface", "no planetary"
        - include_fleet_carriers: Include carriers (default: False)
          Set to True when user says: "include carriers", "with carriers"
        - min_profit_margin: Minimum profit per unit (optional)
        
        IMPORTANT: Infer optimize_by from user's natural language:
        - If user says "shortest" or "closest" or "minimum distance" â†’ use optimize_by='distance_ly'
        - If user says "fewest jumps" or "minimum jumps" â†’ use optimize_by='jumps'
        - If user says "most profitable" or "best profit" â†’ use optimize_by='profit'
        
        Returns: Circular route with trade opportunities at each hop.
        """
        try:
            # Get user parameters
            num_hops = args.get('num_hops', 3)
            start_system = args.get('start_system', '')
            optimize_by = args.get('optimize_by', 'profit')  # 'profit', 'distance_ly', 'jumps'
            
            # BATCH 2 OPTIONAL PARAMETERS (v7.2)
            include_surface = args.get('include_surface_stations', True)
            include_carriers = args.get('include_fleet_carriers', True)  # Default TRUE: don't hide info
            min_profit_margin = args.get('min_profit_margin', None)
            
            # v7.2.1: Show incompatible opportunities
            show_all_pad_sizes = args.get('show_all_pad_sizes', False)
            
            # BATCH 1 CRITICAL PARAMETERS (v7.2)
            # 1. Get ship type and map to landing pad size
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '')
            required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
            
            # 2. Get jump range from Journal (default to 20 LY)
            jump_range = journal_data.get('MaxJumpRange', 20)
            max_distance = args.get('max_distance', jump_range)  # User can override
            
            # Validation
            if optimize_by not in ['profit', 'distance_ly', 'jumps']:
                return "COVINANCE: optimize_by must be 'profit', 'distance_ly', or 'jumps'."
            
            if not start_system:
                if not self.current_system:
                    return "COVINANCE: No start system specified and current location unknown."
                start_system = self.current_system
            
            if num_hops < 2 or num_hops > 5:
                return "COVINANCE: Number of hops must be between 2 and 5."
            
            log('info', f'COVINANCE: Building {num_hops}-hop route from {start_system}, optimized by {optimize_by}')
            log('info', f'COVINANCE: Ship {ship_type} requires {required_pad} pad, jump range {jump_range:.1f}ly')
            
            # Get ALL nearby systems within range
            nearby_endpoint = f'/system/name/{start_system}/nearby'
            nearby_systems = self.call_ardent_api(nearby_endpoint, {'maxDistance': max_distance})
            
            if not isinstance(nearby_systems, list) or len(nearby_systems) < num_hops:
                return f"COVINANCE: Not enough systems within {max_distance} LY for {num_hops}-hop route."
            
            total_systems = len(nearby_systems)
            systems_to_check = min(8, total_systems)  # Reduced to 8 for performance (was 50)
            
            # Calculate profit for EACH nearby system
            system_evaluations = []
            
            for nearby_sys in nearby_systems[:systems_to_check]:
                sys_name = nearby_sys.get('systemName', '')
                sys_distance = nearby_sys.get('distance', 0)
                
                # Get exports from this system with pad size filter
                exports_endpoint = f'/system/name/{sys_name}/commodities/exports'
                exports_params = {
                    'minVolume': 1,  # API default: no arbitrary restriction
                    'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,  # v7.2.1: Conditional
                    'fleetCarriers': str(include_carriers).lower()  # v7.2 OPTIONAL
                }
                exports = self.call_ardent_api(exports_endpoint, exports_params)
                
                if not isinstance(exports, list) or len(exports) == 0:
                    continue
                
                # Filter out surface stations if requested
                if not include_surface:
                    exports = [e for e in exports if e.get('stationType') != 'OnFootSettlement']
                
                # Find best trade FROM this system
                best_profit = 0
                best_commodity = None
                best_sell_system = None
                best_sell_station = None
                
                for export in exports[:5]:  # Check top 5 commodities
                    commodity = export.get('commodityName', '')
                    buy_price = export.get('buyPrice', 0)
                    
                    if buy_price == 0:
                        continue
                    
                    # Find sell opportunity nearby with same filters
                    nearby_sell_endpoint = f'/system/name/{sys_name}/commodity/name/{commodity}/nearby/imports'
                    sell_params = {
                        'maxDistance': max_distance,
                        'minVolume': 1,  # API default: no arbitrary restriction
                        'minLandingPadSize': 'S' if show_all_pad_sizes else required_pad,  # v7.2.1: Conditional
                    'maxDaysAgo': 365,
                        'fleetCarriers': str(include_carriers).lower()  # v7.2 OPTIONAL
                    }
                    sells = self.call_ardent_api(nearby_sell_endpoint, sell_params)
                    
                    if isinstance(sells, list) and len(sells) > 0:
                        # Filter out surface stations if requested
                        if not include_surface:
                            sells = [s for s in sells if s.get('stationType') != 'OnFootSettlement']
                        
                        if not sells:
                            continue
                        
                        top_sell = max(sells, key=lambda x: x.get('sellPrice', 0))
                        sell_price = top_sell.get('sellPrice', 0)
                        profit = sell_price - buy_price
                        
                        # Apply min profit margin filter (v7.2 OPTIONAL)
                        if min_profit_margin and profit < min_profit_margin:
                            continue
                        
                        if profit > best_profit:
                            best_profit = profit
                            best_commodity = commodity
                            best_sell_system = top_sell.get('systemName', '')
                            best_sell_station = top_sell.get('stationName', '')
                
                if best_profit > 0:
                    system_evaluations.append({
                        'system': sys_name,
                        'distance': sys_distance,
                        'profit': best_profit,
                        'commodity': best_commodity,
                        'sell_system': best_sell_system,
                        'sell_station': best_sell_station,
                        'jumps': 1  # All within max_distance = 1 jump
                    })
            
            if len(system_evaluations) < num_hops - 1:
                return f"COVINANCE: Only found {len(system_evaluations)} profitable systems within {max_distance} LY that match your ship's requirements."
            
            # Sort based on optimization preference
            if optimize_by == 'profit':
                system_evaluations.sort(key=lambda x: x['profit'], reverse=True)
            elif optimize_by == 'distance_ly':
                system_evaluations.sort(key=lambda x: x['distance'])
            elif optimize_by == 'jumps':
                # All are 1 jump, so secondary sort by profit
                system_evaluations.sort(key=lambda x: (x['jumps'], -x['profit']))
            
            # Pick top N systems
            route_systems = [start_system]
            route_systems.extend([s['system'] for s in system_evaluations[:num_hops-1]])
            
            # Build output with TRANSPARENT SCOPE (v7.2 CRITICAL)
            route_info = [f"COVINANCE: {num_hops}-hop circular route from {start_system}\n"]
            
            # TRANSPARENT SCOPE OUTPUT (v7.2 BATCH 1)
            # CRITICAL: COVAS must read this section verbatim to user
            route_info.append(f"\n[COVAS: READ VERBATIM - DO NOT PARAPHRASE]\n")
            route_info.append(f"ðŸ” SEARCH SCOPE:\n")
            route_info.append(f"  â€¢ Ship: {ship_type or 'Unknown'} ({required_pad} pad required)\n")
            route_info.append(f"  â€¢ Distance: {max_distance:.1f} LY")
            if max_distance == jump_range:
                route_info.append(f" (your 1-jump range)")
            route_info.append(f"\n  â€¢ Systems checked: {systems_to_check} of {total_systems} nearby\n")
            route_info.append(f"  â€¢ Routes found: {len(system_evaluations)}\n")
            
            # Show active filters
            filters_active = []
            if not include_surface:
                filters_active.append("Surface stations excluded")
            if include_carriers:
                filters_active.append("Fleet carriers included")
            if min_profit_margin:
                filters_active.append(f"Min profit: {min_profit_margin:,} CR")
            if filters_active:
                route_info.append(f"  â€¢ Filters: {', '.join(filters_active)}\n")
            if show_all_pad_sizes:
                route_info.append(f"  â€¢ All pad sizes: Shown (incompatible hops marked)\n")
            
            route_info.append(f"\nâš ï¸  LIMITED SEARCH - To expand:\n")
            route_info.append(f"  â€¢ More systems: (currently checking {systems_to_check})\n")
            route_info.append(f"  â€¢ Longer range: max_distance={int(max_distance * 1.5)}\n")
            route_info.append(f"[END VERBATIM SECTION]\n")
            
            route_info.append(f"\nOptimization: {optimize_by.upper()}\n")
            route_info.append(f"\n=== ROUTE & TRADES ===\n")
            
            # Show each hop
            for i in range(len(route_systems)):
                current = route_systems[i]
                next_sys = route_systems[(i + 1) % len(route_systems)]
                
                # Find system evaluation data
                sys_data = None
                if i > 0:  # Not the start system
                    sys_data = system_evaluations[i-1]
                
                route_info.append(f"\n{i+1}. {current}")
                
                if sys_data:
                    route_info.append(f" ({sys_data['distance']:.1f} LY from origin)")
                    
                    import re
                    commodity_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', sys_data['commodity']).title()
                    route_info.append(f"\n   Buy: {commodity_name}")
                    route_info.append(f"\n   Sell at: {sys_data['sell_station']}, {sys_data['sell_system']}")
                    route_info.append(f"\n   Profit: {sys_data['profit']:,} CR/unit")
            
            route_info.append(f"\n\n{len(route_systems)}. Return to {start_system}")
            
            # Add analysis
            route_info.append(f"\n\nðŸ“Š ROUTE ANALYSIS:")
            
            if optimize_by == 'profit':
                top_profit = system_evaluations[0]['profit']
                route_info.append(f"\nâœ“ Optimized for PROFIT (best: {top_profit:,} CR/unit)")
                
                # Warn about excluded high-profit systems if they exist
                if len(system_evaluations) > num_hops - 1:
                    excluded_profitable = [s for s in system_evaluations[num_hops-1:num_hops+2] 
                                          if s['profit'] > system_evaluations[num_hops-2]['profit'] * 0.5]
                    if excluded_profitable:
                        route_info.append(f"\n\nâ„¹ï¸  Other profitable options not in route:")
                        for sys in excluded_profitable[:2]:
                            route_info.append(f"\n  â€¢ {sys['system']} ({sys['distance']:.1f} LY): {sys['profit']:,} CR/unit")
            
            elif optimize_by == 'distance_ly':
                route_info.append(f"\nâœ“ Optimized for SHORTEST DISTANCE")
                best_profit_sys = max(system_evaluations, key=lambda x: x['profit'])
                if best_profit_sys not in system_evaluations[:num_hops-1]:
                    route_info.append(f"\nâš ï¸  Higher profit available at {best_profit_sys['system']}")
                    route_info.append(f" ({best_profit_sys['distance']:.1f} LY, {best_profit_sys['profit']:,} CR/unit)")
                    route_info.append(f"\n  Use optimize_by='profit' to include this system.")
            
            return "".join(route_info)
            
        except Exception as e:
            log('error', f'COVINANCE circular_route error: {str(e)}')
            return f"COVINANCE: Error building route - {str(e)}"
    def covinance_multi_commodity_chain(self, args, projected_states) -> str:
        """Swap commodities at each hop for max profit"""
        try:
            num_hops = args.get('num_hops', 3)
            max_distance = args.get('max_distance', 50)
            
            if not self.current_system:
                return "COVINANCE: Current location unknown."
            
            log('info', f'COVINANCE: Building {num_hops}-commodity chain')
            
            result = [f"COVINANCE: Multi-commodity chain trading:\n"]
            result.append(f"\nAdvanced feature - Full implementation in progress.")
            result.append(f"\n\nSuggested approach:")
            result.append(f"\n1. Use 'best_trade_from_here' at current location")
            result.append(f"\n2. After selling, use 'best_trade_from_here' again at destination")
            result.append(f"\n3. Repeat for {num_hops} hops")
            result.append(f"\n\nThis ensures optimal commodity selection at each stop.")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE multi_commodity_chain error: {str(e)}')
            return f"COVINANCE: Error building chain - {str(e)}"
    
    def covinance_max_profit_per_hour(self, args, projected_states) -> str:
        """Time-optimized routes (CR/hour)"""
        try:
            max_distance = args.get('max_distance', 50)
            
            if not self.current_system:
                return "COVINANCE: Current location unknown."
            
            log('info', f'COVINANCE: Calculating profit per hour for routes')
            
            # Simplified implementation
            # Full version would calculate:
            # - Jump time (distance / jump_range * 45 seconds)
            # - Docking time (~60 seconds)
            # - Supercruise time (distance_ls / speed)
            # - Buy/sell time (~30 seconds each)
            
            result = [f"COVINANCE: Time-optimized trading:\n"]
            result.append(f"\nAdvanced feature - Full implementation in progress.")
            result.append(f"\n\nTime factors:")
            result.append(f"\nâ€¢ Jump time: ~45 sec per jump")
            result.append(f"\nâ€¢ Supercruise: ~2-5 min (distance dependent)")
            result.append(f"\nâ€¢ Docking: ~60 sec")
            result.append(f"\nâ€¢ Trading: ~60 sec total")
            result.append(f"\n\nUse 'nearby_profitable_trades' and sort by:")
            result.append(f"\nProfit Ã· (estimated_time_minutes Ã· 60)")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE max_profit_per_hour error: {str(e)}')
            return f"COVINANCE: Error calculating - {str(e)}"        # ===================================
    # ACTION #35: RARE GOODS DISCOVERY (FIXED!)
    # ===================================
    
    def covinance_list_rare_goods(self, args, projected_states) -> str:
        """
        Find and discover RARE GOODS within radius (Azure Milk, Lavian Brandy, etc.)
        
        USE THIS FOR: Finding rare goods by name or discovering all nearby rare goods
        - "Find azure milk nearby"
        - "List rare goods within 100 LY"
        - "Show me all rare goods sorted by distance"
        
        Rare goods are special commodities with:
        - Limited allocation (typically 1-50 units)
        - Sold at only ONE specific station
        - Price increases with distance (peaks at 150-200 LY)
        - Examples: Azure Milk, Lavian Brandy, Onionhead, Leathery Eggs
        
        This function identifies ALL 143 rare goods and shows proper display names.
        
        🚨 IMPORTANT: When user mentions a specific rare good name, ALWAYS pass commodity parameter!
        This enables fast-path (2-4 sec) vs full scan (60-150 sec).
        
        Args:
            commodity: (OPTIONAL) Specific rare good name for fast search.
                      Pass EXACTLY what user said (e.g. "azure milk", "lavian brandy").
                      Examples: "azure milk" ✅, "Azure Milk" ✅, "blue milk" ✅
                      Plugin handles normalization - do NOT pre-normalize.
                      Omit for full discovery of all rare goods.
            max_distance: Search radius in LY (default: 150)
            min_allocation: Minimum stock to show (default: 1)
            max_allocation: Maximum stock to show (default: 999)
            include_carriers: Include fleet carriers (default: True)
            include_surface_stations: Include planetary stations (default: True)
            max_days_old: Maximum data age in days (default: 365)
            sort_by: Sort by 'distance' or 'allocation' (default: 'distance')
        
        Returns: List of rare goods within radius with station info
        
        Performance:
            With commodity: 2-4 seconds (1 API call, fast-path)
            Without commodity: 60-150 seconds (143 API calls, full scan)
        """
        try:
            max_distance = args.get('max_distance', 150)
            min_allocation = args.get('min_allocation', 1)
            max_allocation = args.get('max_allocation', 999)  # ✅ v7.5.1: Liberal default (was 50)
            sort_by = args.get('sort_by', 'distance')
            
            # v7.5: Standard filtering parameters (matching nearby_buy pattern)
            include_carriers = args.get('include_carriers', True)
            include_surface_stations = args.get('include_surface_stations', True)
            max_days_old = args.get('max_days_old', 90)  # ✅ v7.6.1: API max is 90 days (was 365)
            
            # 🔍 DEBUG LOGGING: See what Claude actually passes
            commodity_param = args.get('commodity', '')
            log('info', f'COVINANCE RARE_GOODS: commodity={repr(commodity_param)}, max_distance={max_distance}, current_system={self.current_system}')
            
            if not self.current_system:
                return "COVINANCE: Current location unknown. Cannot search for rare goods."
            
            # Use embedded rare goods data (no external JSON needed)
            rare_goods_data = RARE_GOODS_DATA            
            # ✅ ACTION 8: FAST-PATH for single commodity queries
            # If user asks for specific rare good, search only that commodity (instant response)
            commodity = args.get('commodity', '').strip().lower()
            
            if not commodity:
                log('info', f'COVINANCE RARE_GOODS: No commodity specified -> SLOW PATH (143 API calls, 60-150s)')
            
            if commodity:
                log('info', f'COVINANCE RARE_GOODS: Attempting fast-path for: {repr(commodity)}')
                try:
                    # Normalize and verify it's a rare good
                    normalized = self._normalize_commodity_name(commodity)
                    log('info', f'COVINANCE RARE_GOODS: Normalization: {repr(commodity)} -> {repr(normalized)}')
                    
                    if normalized in rare_goods_data:
                        log('info', f'COVINANCE RARE_GOODS: ✅ FAST-PATH ACTIVATED for {repr(normalized)}')
                        
                        # Use direct commodity search (much faster than checking all 143)
                        endpoint = f'/system/name/{quote(self.current_system)}/commodity/name/{normalized}/nearby/exports'
                        params = {
                            'maxDistance': max_distance,
                            'maxDaysAgo': min(max_days_old, 90),  # ✅ v7.6.1: Clamp to API limit
                            'fleetCarriers': str(include_carriers).lower(),  # ✅ v7.6.1: Explicit string conversion
                            'minVolume': min_allocation
                        }
                        
                        result = self.call_ardent_api(endpoint, params)
                        
                        # Check for API errors first
                        if "error" in result:
                            display_name = RARE_GOODS_DISPLAY_NAMES.get(normalized, normalized)
                            log('error', f'COVINANCE RARE_GOODS: API error for {normalized} - {result["error"]}')
                            return f"COVINANCE: Error searching for {display_name} - {result['error']}"
                        
                        if isinstance(result, list) and len(result) > 0:
                            # Apply filters (same as slow path)
                            filtered = []
                            for item in result:
                                stock = item.get('stock', 0)
                                if stock > max_allocation:
                                    continue
                                
                                is_planetary = item.get('isPlanetary', False)
                                if not include_surface_stations and is_planetary:
                                    continue
                                
                                # Data freshness filter
                                updated_at = item.get('updatedAt', '')
                                if updated_at and max_days_old:
                                    from datetime import datetime, timedelta
                                    try:
                                        updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                                        if datetime.now(updated_time.tzinfo) - updated_time > timedelta(days=max_days_old):
                                            continue
                                    except:
                                        pass
                                
                                filtered.append(item)
                            
                            if filtered:
                                display_name = RARE_GOODS_DISPLAY_NAMES.get(normalized, normalized)
                                max_count = rare_goods_data.get(normalized, 0)
                                
                                # Sort results
                                if sort_by == 'allocation':
                                    filtered.sort(key=lambda x: x.get('stock', 0), reverse=True)
                                else:
                                    filtered.sort(key=lambda x: x.get('distanceToArrival', 0))
                                
                                # Format response
                                response_lines = [
                                    f"COVINANCE: Found {len(filtered)} location(s) for {display_name} (max: {max_count} units):",
                                    ""
                                ]
                                
                                for item in filtered[:20]:  # Limit to 20 for voice
                                    station = item.get('stationName', 'Unknown')
                                    system = item.get('systemName', 'Unknown')
                                    stock = item.get('stock', 0)
                                    distance = item.get('distance', 0)
                                    updated = self.format_time_ago(item.get('updatedAt', ''))
                                    
                                    response_lines.append(
                                        f"• {station} ({system}) - {stock} units, {distance:.1f} LY ({updated})"
                                    )
                                
                                return "\n".join(response_lines)
                            else:
                                display_name = RARE_GOODS_DISPLAY_NAMES.get(normalized, normalized)
                                return f"COVINANCE: No {display_name} found within {max_distance} LY (or filtered out by constraints)."
                        else:
                            display_name = RARE_GOODS_DISPLAY_NAMES.get(normalized, normalized)
                            return f"COVINANCE: No {display_name} found within {max_distance} LY."
                    else:
                        # Not a rare good, inform user
                        log('warning', f'COVINANCE RARE_GOODS: {repr(normalized)} not in rare_goods_data - not a rare good')
                        return f"COVINANCE: '{commodity}' is not a rare good. Use this function to discover rare goods, or search for regular commodities with other functions."
                except ValueError as e:
                    # Salvage item or other error
                    log('warning', f'COVINANCE RARE_GOODS: ValueError during normalization: {str(e)}')
                    return f"COVINANCE: {str(e)}"
            
            # SLOW-PATH: Search all rare goods
            log('info', f'COVINANCE RARE_GOODS: Starting SLOW PATH - scanning all {len(rare_goods_data)} rare goods within {max_distance} LY of {self.current_system}')
            
            # Get all nearby systems
            endpoint = f'/system/name/{quote(self.current_system)}/nearby'
            params = {'maxDistance': max_distance}
            
            nearby_systems = self.call_ardent_api(endpoint, params)
            
            # Check for API errors first
            if "error" in nearby_systems:
                log('error', f'COVINANCE RARE_GOODS: API error getting nearby systems - {nearby_systems["error"]}')
                return f"COVINANCE: Error getting nearby systems - {nearby_systems['error']}"
            
            if not isinstance(nearby_systems, list) or len(nearby_systems) == 0:
                return f"COVINANCE: No systems found within {max_distance} LY."
            
            log('info', f'COVINANCE: Checking {len(nearby_systems)} systems for rare goods')
            
            # Search for rare goods in nearby systems
            # ✅ v7.6: PARALLEL EXECUTION - Check all systems concurrently
            rare_goods_found = []
            rare_goods_names = set(rare_goods_data.keys())
            
            # Build tasks for parallel execution
            def make_system_task(sys):
                """Create a task function for checking one system's exports"""
                system_name = sys.get('systemName')
                distance = sys.get('distance', 0)
                
                def check_system():
                    if not system_name:
                        return []
                    
                    try:
                        # Get system exports (what you can buy)
                        exports_endpoint = f'/system/name/{quote(system_name)}/commodities/exports'
                        exports_response = self.call_ardent_api(exports_endpoint, {})
                        
                        system_rare_goods = []
                        if isinstance(exports_response, list):
                            # Filter to only rare goods (using our complete list)
                            for commodity in exports_response:
                                commodity_name = commodity.get('commodityName', '')
                                stock = commodity.get('stock', 0)
                                
                                # Check if this is a known rare good
                                if commodity_name in rare_goods_names:
                                    # Apply min_allocation filter
                                    if stock < min_allocation:
                                        continue
                                    
                                    # Apply max_allocation filter  
                                    if stock > max_allocation:
                                        continue
                                    
                                    # Fleet carrier filtering
                                    station_type = commodity.get('stationType', '')
                                    if not include_carriers and station_type and 'FleetCarrier' in station_type:
                                        continue
                                    
                                    # Surface station filtering
                                    is_planetary = commodity.get('isPlanetary', False)
                                    if not include_surface_stations and is_planetary:
                                        continue
                                    
                                    # Data freshness filtering
                                    updated_at = commodity.get('updatedAt', '')
                                    if updated_at and max_days_old:
                                        from datetime import datetime, timedelta
                                        try:
                                            updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                                            if datetime.now(updated_time.tzinfo) - updated_time > timedelta(days=max_days_old):
                                                continue
                                        except:
                                            pass  # If date parsing fails, include the result
                                    
                                    # Get max allocation (RARE_GOODS_DATA maps name -> maxCount directly)
                                    max_count = rare_goods_data.get(commodity_name)
                                    
                                    system_rare_goods.append({
                                        'commodity': commodity_name,
                                        'station': commodity.get('stationName', 'Unknown'),
                                        'system': system_name,
                                        'distance': distance,
                                        'allocation': stock,
                                        'max_allocation': max_count,
                                        'buy_price': commodity.get('buyPrice', 0),
                                        'pad_size': commodity.get('maxLandingPadSize', 'Unknown'),
                                        'distance_to_arrival': commodity.get('distanceToArrival', 0),
                                        'updated_at': commodity.get('updatedAt', ''),
                                        'station_type': commodity.get('stationType', 'Unknown'),
                                        'market_id': commodity.get('marketId', 0)
                                    })
                        
                        return system_rare_goods
                    except Exception as e:
                        log('warning', f'COVINANCE: Error checking system {system_name}: {str(e)}')
                        return []
                
                return check_system
            
            # Create tasks for all systems
            tasks = [make_system_task(sys) for sys in nearby_systems]
            
            log('info', f'COVINANCE: Running parallel scan of {len(tasks)} systems (8 workers)...')
            
            # Execute in parallel
            results, errors = self.parallel_runner.run_batch(tasks, timeout_per_task=10.0)
            
            # Aggregate results from all systems
            for system_results in results:
                rare_goods_found.extend(system_results)
            
            systems_checked = len(tasks)
            
            if errors:
                log('warning', f'COVINANCE: {len(errors)} systems failed during parallel scan')
            
            if len(rare_goods_found) == 0:
                return f"COVINANCE: No rare goods found within {max_distance} LY with stock >= {min_allocation} units (checked {systems_checked} systems)."
            
            # Sort results
            if sort_by == 'distance':
                rare_goods_found.sort(key=lambda x: x['distance'])
            elif sort_by == 'allocation':
                rare_goods_found.sort(key=lambda x: x['allocation'], reverse=True)
            
            # Format for voice output
            result = []
            result.append(f"COVINANCE: Found {len(rare_goods_found)} rare goods within {max_distance} LY" + chr(10))
            result.append(f"(Checked {systems_checked} systems using complete rare goods database)" + chr(10))
            result.append(chr(10) + "🌟 RARE GOODS DISCOVERED:" + chr(10))
            
            # Show top 10 for voice (Claude can see all in raw data)
            for i, rare in enumerate(rare_goods_found[:10], 1):
                # ✅ FIX: Use proper display name
                api_name = rare['commodity']
                display_name = RARE_GOODS_DISPLAY_NAMES.get(api_name, api_name.replace('_', ' ').title())
                
                time_ago = self.format_time_ago(rare['updated_at']) if rare['updated_at'] else 'unknown'
                max_alloc = rare['max_allocation'] if rare['max_allocation'] else '?'
                
                result.append(chr(10) + f"{i}. {display_name}")
                result.append(chr(10) + f"   Station: {rare['station']} ({rare['station_type']}), {rare['system']}")
                result.append(chr(10) + f"   Distance: {rare['distance']:.1f} LY | Stock: {rare['allocation']}/{max_alloc} units")
                result.append(chr(10) + f"   Buy Price: {rare['buy_price']:,} CR | Pad: {rare['pad_size']}")
                result.append(chr(10) + f"   {rare['distance_to_arrival']:,} Ls from star | Updated {time_ago}")
            
            if len(rare_goods_found) > 10:
                result.append(chr(10) + chr(10) + f"... and {len(rare_goods_found) - 10} more rare goods.")
            
            # Add trading tip
            result.append(chr(10) + chr(10) + "💡 RARE GOODS TIP:")
            result.append(chr(10) + "Sell 150-200 LY from origin for maximum profit!")
            result.append(chr(10) + "Use 'best trade from here' or 'circular route' to plan trades.")
            
            # ✅ v7.5.1: Transparency footer (show filter settings)
            filter_info = []
            if max_days_old < 90:
                filter_info.append(f"data ≤{max_days_old} days")
            if max_allocation < 999:
                filter_info.append(f"stock ≤{max_allocation} units")
            if not include_carriers:
                filter_info.append("no carriers")
            if not include_surface_stations:
                filter_info.append("no surface stations")
            
            if filter_info:
                result.append(chr(10) + chr(10) + f"📊 Filters: {', '.join(filter_info)}")
                result.append(chr(10) + "(Use 'max data age 365' or 'max allocation 999' to see all data)")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE list_rare_goods error: {str(e)}')
            return f"COVINANCE: Error searching for rare goods - {str(e)}"
    
    # ===================================
    # ACTION #37: SAFE INTERSTELLAR FACTORS
    # ===================================
    
    def covinance_safe_interstellar_factors(self, args, projected_states) -> str:
        """
        Find Interstellar Factors in low-security systems (safe for bounty clearing).
        
        USE THIS FOR: Finding safe places to pay off bounties without authority scans
        - "Safe place to pay bounties"
        - "Interstellar factors without scans"
        - "Where to clear bounties safely"
        
        Safety criteria:
        - Anarchy systems (no authorities)
        - Low security systems (minimal patrols)
        - Filters out High/Medium security (dangerous for wanted commanders)
        
        Args:
            max_distance: Search radius in LY (default: 100)
            reference_system: System to search from (optional, uses current)
            min_pad_size: Landing pad requirement (optional, auto from Journal)
        
        Returns: List of safe Interstellar Factors sorted by distance
        """
        try:
            max_distance = args.get('max_distance', 100)
            reference_system = args.get('reference_system', '').strip()
            pad_size_override = args.get('min_pad_size')
            
            # Get Journal data for defaults
            journal_data = self.read_latest_journal()
            ship_type = journal_data.get('ShipType', '') if journal_data else ''
            
            # Determine pad size requirement
            if pad_size_override:
                min_pad_size = pad_size_override
            else:
                pad_map = {'S': 1, 'M': 2, 'L': 3}
                required_pad = self._get_landing_pad_size(ship_type) if ship_type else 'S'
                min_pad_size = pad_map.get(required_pad, 1)
            
            # Get reference system
            if not reference_system:
                self.update_location_from_journal()
                if not self.current_system:
                    return "COVINANCE: Unable to determine your location. Dock somewhere or specify a system."
                reference_system = self.current_system
            
            log('info', f'COVINANCE: Finding safe Interstellar Factors within {max_distance} LY of {reference_system}')
            
            # Step 1: Get nearest Interstellar Factors (returns up to 20 stations)
            endpoint = f'/system/name/{quote(reference_system)}/nearest/interstellar-factors'
            params = {'minLandingPadSize': min_pad_size}
            
            stations = self.call_ardent_api(endpoint, params)
            
            if "error" in stations:
                return f"COVINANCE: Error finding Interstellar Factors - {stations['error']}"
            
            if not isinstance(stations, list) or len(stations) == 0:
                return f"COVINANCE: No Interstellar Factors found within range (pad size: {['S','M','L'][min_pad_size-1]})."
            
            log('info', f'COVINANCE: Found {len(stations)} Interstellar Factors, checking security levels')
            
            # Step 2: Check security level for each station's system
            safe_stations = []
            
            for station in stations:
                system_name = station.get('systemName')
                distance = station.get('distance', 0)
                
                # Skip if outside max_distance
                if distance > max_distance:
                    continue
                
                # Get system security level
                status_endpoint = f'/system/name/{quote(system_name)}/status'
                status = self.call_ardent_api(status_endpoint, {})
                
                if isinstance(status, dict):
                    security = status.get('security', '').lower()
                    
                    # Filter to safe systems only (Anarchy, Low, or None)
                    if security in ['anarchy', 'low', 'none', '']:
                        safe_stations.append({
                            'station': station.get('stationName', 'Unknown'),
                            'system': system_name,
                            'distance': distance,
                            'distance_to_arrival': station.get('distanceToArrival', 0),
                            'pad_size': station.get('maxLandingPadSize', 'Unknown'),
                            'station_type': station.get('stationType', 'Unknown'),
                            'security': security if security else 'none',
                            'updated_at': station.get('updatedAt', '')
                        })
            
            if len(safe_stations) == 0:
                return f"COVINANCE: No SAFE Interstellar Factors found within {max_distance} LY. All nearby stations are in High/Medium security systems (dangerous for wanted commanders)."
            
            # Sort by distance
            safe_stations.sort(key=lambda x: x['distance'])
            
            # Format for voice output
            result = []
            result.append(f"COVINANCE: Found {len(safe_stations)} SAFE Interstellar Factors within {max_distance} LY" + chr(10))
            result.append(f"(Anarchy/Low security systems only - no authority scans)" + chr(10))
            result.append(chr(10) + "🛡️ SAFE LOCATIONS:" + chr(10))
            
            # Show top 5 for voice
            for i, station in enumerate(safe_stations[:5], 1):
                time_ago = self.format_time_ago(station['updated_at']) if station['updated_at'] else 'unknown'
                security_label = station['security'].upper() if station['security'] != 'none' else 'NO SECURITY'
                
                result.append(chr(10) + f"{i}. {station['station']}, {station['system']}")
                result.append(chr(10) + f"   Security: {security_label} ✅ SAFE")
                result.append(chr(10) + f"   Distance: {station['distance']:.1f} LY | {station['distance_to_arrival']:,} Ls from star")
                result.append(chr(10) + f"   Type: {station['station_type']} | Pad: {station['pad_size']}")
                result.append(chr(10) + f"   Updated {time_ago}")
            
            if len(safe_stations) > 5:
                result.append(chr(10) + chr(10) + f"... and {len(safe_stations) - 5} more safe options.")
            
            # Add safety tip
            result.append(chr(10) + chr(10) + "💡 SAFETY TIP:")
            result.append(chr(10) + "Anarchy and Low security systems have minimal/no authority presence.")
            result.append(chr(10) + "Perfect for clearing bounties without scans!")
            
            return "".join(result)
            
        except Exception as e:
            log('error', f'COVINANCE safe_interstellar_factors error: {str(e)}')
            return f"COVINANCE: Error finding safe Interstellar Factors - {str(e)}"

    def covinance_cache_stats(self, args, projected_states) -> str:
        """
        Get cache performance statistics
        
        Shows how well the caching system is performing, including:
        - Cache hit rate (% of requests served from cache)
        - Total requests processed
        - API calls saved by caching
        - Cache hits, misses, in-flight hits
        
        Voice triggers:
        - "Show cache stats"
        - "Cache performance"
        - "How's the cache doing"
        
        Returns: Cache performance metrics
        """
        try:
            stats = self.reliability_client.get_stats()
            
            return (
                f"COVINANCE: Cache Performance\n"
                f"Hit Rate: {stats['cache_hit_rate']}\n"
                f"Total Requests: {stats['total_requests']}\n"
                f"API Calls Saved: {stats['api_calls_saved']}\n"
                f"Cache Hits: {stats['cache_hits']}\n"
                f"Cache Misses: {stats['cache_misses']}\n"
                f"In-Flight Hits: {stats['inflight_hits']}"
            )
        except Exception as e:
            log('error', f'COVINANCE: Error getting cache stats: {str(e)}')
            return f"COVINANCE: Error retrieving cache statistics: {str(e)}"

    def shutdown(self):
        """Cleanup resources on plugin shutdown"""
        try:
            if hasattr(self, 'parallel_runner'):
                self.parallel_runner.shutdown()
                log('info', 'COVINANCE: Parallel runner shut down cleanly')
        except Exception as e:
            log('error', f'COVINANCE: Error during shutdown: {str(e)}')