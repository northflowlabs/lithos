# Bundled data

The Apache-2.0 licence of LITHOS covers the code. The data has its own terms.

`scenes/` holds values derived from LiCSAR interferograms and GNSS rates.

- **LiCSAR.** LiCSAR contains modified Copernicus Sentinel data 2021 to 2024 analysed by the
  Centre for the Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET).
  LiCSAR uses JASMIN, the UK's collaborative data analysis environment (<http://jasmin.ac.uk>).
  Licence: [UK Open Government Licence v3.0](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/),
  and the Copernicus terms for Sentinel data. Citation: Lazecky, M.; Maghsoudi, Y. (2022):
  LiCSAR interferometry products. NERC EDS Centre for Environmental Data Analysis.
  <https://catalogue.ceda.ac.uk/uuid/52cda2e0e6c04272ae15ac836c1e8493>
- **GNSS.** Rates are fitted to daily positions from the Nevada Geodetic Laboratory. Cite
  Blewitt, G., W. C. Hammond, and C. Kreemer (2018), Harnessing the GPS data explosion for
  interdisciplinary science, Eos, 99, and the provider of each station's data.

`packages/ingest/lithos_ingest/data/licsar_frames.json` lists frame footprints and dates from
the same archive. The recordings in `packages/ingest/tests/fixtures/` carry their own notes.
