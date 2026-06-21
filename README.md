## Features

### Maintenance Ticket Management
- Add maintenance tickets with ticket number, time window, and affected services
- **Auto-extract Service IDs** from pasted text — just paste raw data and all `WL`-prefixed IDs are extracted automatically
- Modify ticket time windows and affected services at any time
- Delete tickets when no longer needed

### Disruption Detection
- **Cross-ticket only** — if the same ticket affects both paths of a service, it does not count as a disruption (we should handle it when creating the PW/EW/FI)
- Automatically computes the exact overlap time window when different tickets cause a disruption
- Recalculates all disruptions whenever tickets are added, modified, or deleted

### Overlapping Ticket Pairs
- Groups all affected services by ticket pair
- Combines both directions: Ticket A → main + Ticket B → backup, and Ticket A → backup + Ticket B → main
- Shows the count of disrupted services per pair for quick assessment

### Reschedule Impossible
- Mark a maintenance ticket as "Reschedule Impossible" when the provider cannot change the maintenance window
- Visual indicators propagate into the Overlapping Ticket Pairs view so you can immediately see which overlaps have no flexibility

### Update Notes(to add DI ticket or any updates on each overflap)
- Zabbix-style timestamped notes on each disruption and ticket pair
- Track communication history, decisions, and status updates
