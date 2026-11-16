# Road Classification SOP

## Edge Weight System

Edge weight = `road_type_factor × length_meters`. Lower weight = preferred road.

### Road Type Weights

| OSM highway tag | Weight factor | Rationale |
|-----------------|--------------|-----------|
| cycleway | 1.0 | Best — dedicated bike paths |
| living_street | 1.0 | Shared space, very low traffic |
| residential | 1.2 | Quiet neighborhood streets |
| tertiary | 1.5 | Small connecting roads, good for cycling |
| tertiary_link | 1.5 | Connectors for tertiary roads |
| unclassified | 1.5 | Minor roads, often rural |
| path | 1.8 | May be paved paths suitable for cycling |
| service | 2.0 | Access roads, parking areas |
| secondary | 3.0 | Larger roads, more traffic |
| secondary_link | 3.0 | Secondary connectors |
| primary | 8.0 | Major roads — use only if necessary |
| primary_link | 8.0 | Primary connectors |
| trunk | ∞ | EXCLUDED — highway-grade roads |
| trunk_link | ∞ | EXCLUDED |
| motorway | ∞ | EXCLUDED — motorways |
| motorway_link | ∞ | EXCLUDED |
| (unknown) | 5.0 | Default for unmapped road types |

### Excluded Surfaces

Edges with these surface tags get weight = ∞ (excluded, paved roads only):

gravel, dirt, unpaved, ground, grass, sand, mud, compacted, fine_gravel, earth, woodchips

### Dynamic Penalties

| Condition | Penalty | Purpose |
|-----------|---------|---------|
| Already-visited edge | ×10 | Forces return leg onto different roads |

### OSMnx Edge Attribute Handling

- `highway` may be a list on simplified edges → take worst (highest) weight
- `surface` may be a list → exclude if any value is in excluded set
- Missing `highway` → use default weight (5.0)
- Missing `surface` → assume paved (no penalty)
