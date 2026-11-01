# Busos del Baix Empordà

Mapa de La TdG amb els busos de línia que passen per la comarca i les rutes del Clic.cat a demanda.

- **Dades:** GTFS dels autobusos interurbans de la Generalitat de Catalunya.
- **Actualització:** l'Action «Horaris dels busos» s'executa cada matí i desa `data/busos.json` (avui i demà).
- **Posició dels busos:** calculada a partir de l'horari. No és GPS: ni Moventis ni el Clic publiquen la posició real en obert.
- **Clic.cat:** rutes R1, R2 i R3 i franges horàries copiades del full oficial del servei.
- **Només busos i Clic.cat.** Les altres capes de prova (aeronaus, balises, terratrèmols, Bombers, talls de llum i d'aigua, desfibril·ladors i antenes) es van treure l'01.11.2026: ja tenen el seu lloc al tauler.
- **Inici i final:** cada capçalera de trajecte surt amb una rodona vermella més grossa.
- **Horaris en PDF i bitllets:** a la llista «Línies, horaris en PDF i bitllets», al clicar una línia i a la fitxa de cada bus. El PDF surt de `data/horaris.json` (l'Action el busca a la pàgina de la línia, vegeu `scripts/horaris_fonts.json`). El bitllet porta a la web de compra de l'empresa: Moventis (`compras.moventis.es/online`) o TEISA; el Clic.cat es reserva amb l'app o per telèfon. El díptic del Clic és una còpia pròpia (`data/clic-baix-emporda.pdf`, del web de Palau-sator, setembre 2025), perquè el de la web oficial no es troba.

Si la Generalitat canvia l'adreça del GTFS, es pot posar la nova a la variable del repo `GTFS_URL` (Settings → Secrets and variables → Actions → Variables), sense tocar el codi.

Per esborrar-ho tot n'hi ha prou d'esborrar el repo: només llegeix fitxers del tauler i cap altre projecte de La TdG en depèn.
