# LiCSAR recordings

Real files from the public COMET LiCSAR archive, recorded on 30 October 2026, so the tests
can read real data without a network.

- `track_117.html`: the listing of track 117, unchanged.
- `interferograms.html`: the listing of `117A_04454_131312/interferograms/`, cut to 16 pairs.
- `117A_04454_131312-poly.txt`: that frame's footprint, unchanged.
- `20230710_20230722.geo.unw.tif`: a 30 by 30 pixel window of that interferogram, north of Bologna.
- `cell_north_of_bologna.json`: unwrapped phase for one 400 m cell of frame
  `095D_04589_131313`, one value per interferogram, averaged and tied to the reference ground
  as `lithos_ingest.scene` does.

LiCSAR contains modified Copernicus Sentinel data 2021 to 2024 analysed by the Centre for the
Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET).
