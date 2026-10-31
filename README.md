# Busos del Baix Empordà

Mapa de La TdG amb els busos de línia que passen per la comarca i les rutes del Clic.cat a demanda.

- **Dades:** GTFS dels autobusos interurbans de la Generalitat de Catalunya.
- **Actualització:** l'Action «Horaris dels busos» s'executa cada matí i desa `data/busos.json` (avui i demà).
- **Posició dels busos:** calculada a partir de l'horari. No és GPS: ni Moventis ni el Clic publiquen la posició real en obert.
- **Clic.cat:** rutes R1, R2 i R3 i franges horàries copiades del full oficial del servei.

Si la Generalitat canvia l'adreça del GTFS, es pot posar la nova a la variable del repo `GTFS_URL` (Settings → Secrets and variables → Actions → Variables), sense tocar el codi.

Per esborrar-ho tot n'hi ha prou d'esborrar el repo: no depèn de cap altre projecte de La TdG ni cap altre en depèn.
