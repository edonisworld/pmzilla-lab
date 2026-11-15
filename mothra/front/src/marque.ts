// The one point that names the logo files and the displayed name of the application (mothra-demo-habillage D17): the shell, the home and
// the catalogue read them here, nothing else writes a logo path or the catalogue key `app.title`. A brand change is made by the values of
// the tokens and by the files under public/logos/, without touching a component.
// Replaces: the two paths and the key that Application.ts and PageSquelette.ts wrote themselves. Removal: permanent while the design system exists.
export const MARQUE = {
  logo: "/logos/mothra-logo-clair.svg",
  icone: "/logos/mothra-icone-clair.svg",
  nom: "app.title",
} as const;
