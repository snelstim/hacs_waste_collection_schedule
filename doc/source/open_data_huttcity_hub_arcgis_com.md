# Hutt City Council / open-data-huttcity.hub.arcgis.com

Collection data is retrieved from the [Hutt City Council Open Data](https://open-data-huttcity.hub.arcgis.com/datasets/64e6414e56ce4d379ce532960fe592b3_0/about) ArcGIS service. Public holidays are fetched dynamically from [Nager.Date](https://date.nager.at) — no API key required.

## Configuration via configuration.yaml

```yaml
waste_collection_schedule:
  sources:
    - name: open_data_huttcity_hub_arcgis_com
      args:
        address: ADDRESS
```

Or with coordinates:

```yaml
waste_collection_schedule:
  sources:
    - name: open_data_huttcity_hub_arcgis_com
      args:
        lat: LATITUDE
        lon: LONGITUDE
```

### Configuration Variables

**address** *(string) (optional)*
Your full street address within Lower Hutt, e.g. `20 Buick Street, Petone, Lower Hutt`. Not required if `lat` and `lon` are provided. When an address is used, coordinates are resolved once via Nominatim and cached for all subsequent updates — no repeated geocoding requests are made.

**lat** *(float) (optional)*
Latitude of your property. Find it by right-clicking your address in Google Maps → "What's here?". Must be used with `lon`. **Recommended** — providing coordinates directly skips geocoding entirely.

**lon** *(float) (optional)*
Longitude of your property. Must be used with `lat`. **Recommended** — providing coordinates directly skips geocoding entirely.

## Collection Types

| Type | Description |
|------|-------------|
| `Rubbish` | Red-lid bin — every week |
| `Recycling` | Yellow-lid bin — fortnightly |
| `Glass` | Blue crate — fortnightly (alternating with Recycling) |
| `Green Waste Zone 1` | Green bin — every 4 weeks (zone 1) |
| `Green Waste Zone 2` | Green bin — every 4 weeks (zone 2) |
| `Green Waste Zone 3` | Green bin — every 4 weeks (zone 3) |
| `Green Waste Zone 4` | Green bin — every 4 weeks (zone 4) |

## Green Waste Zones

Green waste has 4 independent collection zones that do **not** correspond to the recycling zones. The ArcGIS open data layer does not expose green waste zone information, so this source returns entries for all 4 green waste zones by default — this is an inherent limitation of the available data.

To identify your zone, check the [HCC bin collection calendar](https://www.huttcity.govt.nz/services/rubbish-and-recycling/rubbish-and-recycling-collection) and look up your address. Once you know your zone, use the `customize` block to hide the zones that don't apply to you (see the full example below).

If you don't have a green bin at all, hide all green waste types using `show: false`.

## Public Holidays

Collection shifts to the **following Saturday** if it falls on Good Friday, Christmas Day, or New Year's Day. All other NZ public holidays collect as normal. Holiday dates are fetched automatically from [date.nager.at](https://date.nager.at) — no configuration required.

## Full Example

```yaml
waste_collection_schedule:
  sources:
    - name: open_data_huttcity_hub_arcgis_com
      args:
        address: "20 Buick Street, Petone, Lower Hutt"
      customize:
        - type: Rubbish
          icon: mdi:trash-can
        - type: Recycling
          icon: mdi:recycle
        - type: Glass
          icon: mdi:bottle-soda
        - type: Green Waste Zone 1
          alias: Green Waste   # rename to just "Green Waste" once you know your zone
          icon: mdi:leaf
        - type: Green Waste Zone 2
          show: false
        - type: Green Waste Zone 3
          show: false
        - type: Green Waste Zone 4
          show: false
```