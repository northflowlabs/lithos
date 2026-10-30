# Attribution

LITHOS would not exist without the open science it stands on. If you publish research,
reporting, or analysis made with LITHOS, please attribute these sources correctly and
prominently.

## COMET LiCSAR

> LiCSAR contains modified Copernicus Sentinel data [years used] analysed by the Centre for the
> Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET). LiCSAR uses JASMIN,
> the UK's collaborative data analysis environment (http://jasmin.ac.uk).

For the bundled Bologna scene the years are 2021 to 2024.

- Citation: Lazecky, M.; Maghsoudi, Y. (2022): LiCSAR interferometry products. NERC EDS Centre
  for Environmental Data Analysis, date of citation.
  <https://catalogue.ceda.ac.uk/uuid/52cda2e0e6c04272ae15ac836c1e8493>
- Licence: [UK Open Government Licence v3.0](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/),
  per the CEDA record, and the Copernicus terms for Sentinel data, of which these products are
  derived works.
- Method: Lazecky et al. (2020), *LiCSAR: An Automatic InSAR Tool for Measuring and Monitoring
  Tectonic and Volcanic Activity*, Remote Sensing 12(15), 2430.
- LiCSAR products are used as a **network data source** only; LITHOS does not bundle or
  modify LiCSAR/LiCSBAS source code (see [`licensing.md`](licensing.md)).
- The small-baseline inversion follows Berardino et al. (2002), IEEE TGRS 40(11), 2375-2383.

## GNSS

Scenes are tied to, and checked against, GNSS rates fitted to daily positions from the Nevada
Geodetic Laboratory.

- Citation: Blewitt, G., W. C. Hammond, and C. Kreemer (2018), Harnessing the GPS data explosion
  for interdisciplinary science, Eos, 99, doi:10.1029/2018EO104623, plus the provider of each
  station's data.
- Providers: BOLG, whose RINEX header reads "GEOFISICA BOLOGNA" (institution not confirmed); BLGN,
  INGV; MEDI, ASI Telespazio.

## Copernicus EGMS

> Contains modified Copernicus data. European Ground Motion Service, Copernicus Land
> Monitoring Service.

- Service: <https://egms.land.copernicus.eu/>
- Licence: free and open under the Copernicus data policy; download needs a CLMS API key.
- When showing an EGMS-derived view, keep the "Contains modified Copernicus data" notice
  visible.

## How to cite LITHOS

```
Northflow Technologies AS (2026). LITHOS: open ground motion intelligence.
https://github.com/northflowlabs/lithos
```

The web UI has a one-click "Cite LITHOS" button in the point panel,
and a "copy permalink" so a specific view can be referenced directly in an article.

**Used LITHOS in a story or a study?** Tell us: open an issue with the `showcase` label or
write to hello@northflow.no. Real-world use is the only metric we care about.
