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
Your full street address within Lower Hutt, e.g. `20 Buick Street, Petone, Lower Hutt`. Not required if `lat` and `lon` are provided.

**lat** *(float) (optional)*
Latitude of your property. Find it by right-clicking your address in Google Maps → "What's here?". Must be used with `lon`.

**lon** *(float) (optional)*
Longitude of your property. Must be used with `lat`.

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

Green waste has 4 independent collection zones that do not correspond to the recycling zones. All 4 green waste zones are returned so you can identify which one matches your property. Use the `customize` block to hide the zones that don't apply to you.

To find your green waste zone, visit [toogoodtowaste.co.nz/bin-enquiries/collection-zones-and-calendars](https://www.toogoodtowaste.co.nz/bin-enquiries/collection-zones-and-calendars) and look up your area.

If you don't have a green bin at all, hide all green waste types using `show: false`.

## Public Holidays

Collection shifts to the **following Saturday** if it falls on Good Friday, Christmas Day, or New Year's Day. All other NZ public holidays collect as normal. Holiday dates are fetched automatically from [date.nager.at](https://date.nager.at) — no configuration required.

## Full Example

```yaml
waste_collection_schedule:
  sources:
    - name: toogoodtowaste_co_nz
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