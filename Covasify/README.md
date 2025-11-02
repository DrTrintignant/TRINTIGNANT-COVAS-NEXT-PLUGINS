# Covinance v7.6

Voice-controlled commodity trading and market analysis for Elite Dangerous via COVAS NEXT using the Ardent API. Real-time market data, route planning, and rare goods discovery.

## What It Does

- Find best commodity prices galaxy-wide or within radius
- Calculate profitable trade routes (single-hop, circular, multi-commodity)
- Discover rare goods and their stations
- Locate services (markets, outfitting, shipyard, Interstellar Factors)
- Auto-detect ship constraints from Journal (cargo, pad size, jump range)
- Smart commodity name mapping (100+ aliases for voice queries)
- Safe bounty clearing (Anarchy/Low security systems)

## Installation

1. Place the `Covinance` folder in: `%appdata%\com.covas-next.ui\plugins\`

2. Restart COVAS NEXT

3. Test with: "Test Covinance"

**No API key required** - Uses Ardent Insight API for Elite Dangerous market data.

## Voice Commands

### Finding Prices

```
"Find best gold buy nearby"
"Best sell for painite within 50 light years"
"Where can I sell Azure Milk?"
"Cheapest tritium at fleet carriers"
```

### Trade Routes

```
"Show profitable trades from here"
"Best single-hop trade now"
"Fill my remaining cargo with high-profit goods"
"Circular route for rare goods"
```

### Services

```
"Nearest station with large pad"
"Safe place to clear bounties"
"Find Interstellar Factors in Anarchy systems"
"Where can I find outfitting?"
```

### Market Analysis

```
"What does this system export?"
"Show carrier markets selling gold"
"List stations within 20 light years"
"System coordinates for Shinrarta Dezhra"
```

### Rare Goods

```
"List rare goods within 100 light years"
"Where can I buy Lavian Brandy?"
"Show rare goods at planetary stations"
```

## Available Commands (38 Actions)

### Price Searches & Market Data
- **Best Buy Galaxy-Wide** - Find absolute best buy prices anywhere
- **Best Sell Galaxy-Wide** - Find absolute best sell prices anywhere
- **Best Buy Nearby** - Find best buy within radius (up to 1000 results)
- **Best Sell Nearby** - Find best sell within radius (up to 1000 results)
- **Commodity Price Comparison** - Compare prices across stations
- **Profit Margin Calculator** - Calculate buy→sell profits
- **Fleet Carrier Markets** - Search carrier-specific markets
- **System Exports** - What a system sells (exports)
- **System Imports** - What a system buys (imports)
- **Station Market Snapshot** - Full commodity list for a station
- **System All Commodities** - Every commodity available in system
- **Station Commodities** - Specific station's commodity list

### Station & System Information
- **List Stations** - All stations in a system
- **Find Station** - Search for specific station
- **List Large Ports** - Stations with large landing pads
- **List Outposts** - Small/medium pad stations
- **List Settlements** - Planetary surface bases
- **List Megaships** - Dockable megaships
- **List Fleet Carriers** - Player-owned carriers
- **System Info** - Coordinates, allegiance, economy, security
- **Nearby Systems** - Systems within radius (up to 1000)
- **Distance Calculator** - Light years between systems
- **System Markets** - All market stations in system

### Services & Facilities
- **Find Service** - Locate nearest station with service (market, outfitting, shipyard, etc.)
- **Safe Interstellar Factors** - Find bounty clearance in Anarchy/Low security (avoid scans)

### Trade Route Planning
- **Best Trade From Here** - Optimal single-hop trade from current location
- **Trade Route A→B** - Best commodity for specific route
- **Nearby Profitable Trades** - All good trades within radius
- **Optimal Trade Now** - Best trade considering ship/cargo/credits (Journal-aware)
- **Trade Within Jump Range** - Only show reachable destinations (Journal-aware)
- **Fill Remaining Cargo** - Optimize partial cargo loads (Journal-aware)
- **Circular Route** - Round-trip trading (return to start)
- **Multi-Commodity Chain** - Complex multi-stop routes
- **Max Profit Per Hour** - Time-optimized route planning

### Rare Goods Discovery
- **List Rare Goods** - All rare goods within radius with stations and allocations

### System Utilities
- **Current Location** - Show current system from Journal
- **Test Connection** - Verify plugin and API connectivity
- **Cache Stats** - View performance metrics

## Features

### Smart Commodity Mapping
- 100+ voice-friendly aliases ("Azure Milk" → bluemilk)
- Handles natural variations automatically
- Detects salvage items with helpful messages
- 97% commodity coverage (386/397)

### Journal Integration
- Auto-detects ship type and cargo capacity
- Respects pad size limitations
- Considers jump range constraints
- Optimizes trades for current situation

### Advanced Search
- 1000 nearby results (10x more than competitors)
- Fleet carrier market tracking
- Filter by pad size, planetary/orbital
- Optional incompatible stations display

### Performance
- 1-hour intelligent caching
- Parallel API execution for rare goods
- Thread-safe operations
- Response times under 2 seconds

## Troubleshooting

**Plugin won't load**
- Restart COVAS NEXT completely
- Check COVAS logs for errors

**"Commodity not found"**
- Try variations: "gold" vs "Gold"
- Check spelling with: "Test Covinance"
- Some items are salvage-only (plugin will inform you)

**No results for trades**
- Increase search radius (try 50-100 LY)
- Check if system has market data
- Verify commodity name is correct

**Stale data warnings**
- Market data older than 30 days flagged
- Normal for remote systems
- Visit system to update market data

## Files

```
Covinance/
├── Covinance.py           # Main plugin
├── manifest.json          # Plugin metadata
├── deps/                  # Bundled dependencies
└── README.txt             # This file
```

## Version History

**v7.6** - Performance optimization, caching system, parallel execution  
**v7.5** - Rare goods discovery, safe Interstellar Factors  
**v7.4** - Commodity mapping (100 aliases), salvage detection  
**v7.0** - Initial release

## Credits

**Author**: D. Trintignant  
**Version**: 7.6  
**COVAS NEXT**: https://ratherrude.github.io/Elite-Dangerous-AI-Integration/  
**API**: Ardent Insight (Elite Dangerous market data)  
**Game**: Elite Dangerous (Frontier Developments)  
**License**: MIT
