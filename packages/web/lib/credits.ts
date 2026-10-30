// Every credit in one place, so the map, the panels and the exports cannot drift apart.

export const YEARS = "2021 to 2024";

// The wording the CEDA catalogue record asks for.
export const LICSAR_ACK = `LiCSAR contains modified Copernicus Sentinel data ${YEARS} analysed by the Centre for the Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET). LiCSAR uses JASMIN, the UK's collaborative data analysis environment (http://jasmin.ac.uk).`;

export const OGL_URL = "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/";
export const CEDA_URL = "https://catalogue.ceda.ac.uk/uuid/52cda2e0e6c04272ae15ac836c1e8493";

export const GNSS_CREDIT =
  "GNSS: Blewitt, G., W. C. Hammond, and C. Kreemer (2018), Eos, 99, doi:10.1029/2018EO104623. BOLG, University of Bologna; BLGN, INGV; MEDI, ASI.";

export const EGMS_NOTICE =
  "Contains modified Copernicus data. European Ground Motion Service, Copernicus Land Monitoring Service.";

export const ESRI_CREDIT =
  "Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community";

export function cedaCitation(on: Date = new Date()): string {
  const day = on.toISOString().slice(0, 10);
  return `Lazecky, M.; Maghsoudi, Y. (2022): LiCSAR interferometry products. NERC EDS Centre for Environmental Data Analysis, date of citation ${day}. ${CEDA_URL}`;
}

// Lines that travel with any export of the data.
export function exportCredits(caveat?: string | null): string[] {
  return [
    LICSAR_ACK,
    `Licence: Open Government Licence v3.0, ${OGL_URL}`,
    GNSS_CREDIT,
    ...(caveat ? [caveat] : []),
  ];
}
