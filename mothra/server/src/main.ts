// Entry of the server: `npm start` in mothra/server. Exit codes of design D7: 2 usage, 3 contract, 4 environment, 5 configuration.
import { demarrer } from "./demarrage.ts";
import { lireEnvironnement } from "./config/index.ts";
import { RefusDemarrage, SORTIE_USAGE } from "./refus.ts";

async function main(): Promise<void> {
  if (process.argv.length > 2) {
    console.error("mothra: usage");
    process.exit(SORTIE_USAGE);
  }
  try {
    const { app, config } = await demarrer(lireEnvironnement(), {
      cheminContrat: new URL("../../../contrats/vues.json", import.meta.url),
    });
    const arreter = (): void => {
      void app.close().then(() => process.exit(0));
    };
    process.on("SIGINT", arreter);
    process.on("SIGTERM", arreter);
    await app.listen({ host: config.ecoute.hote, port: config.ecoute.port });
  } catch (erreur) {
    if (erreur instanceof RefusDemarrage) {
      console.error(erreur.phrase);
      process.exit(erreur.sortie);
    }
    // No detail: an error of the driver or of the listener may hold a path or a value.
    console.error("mothra: failed");
    process.exit(1);
  }
}

await main();
