// Check of the logo files (task 24.7): each SVG keeps the C2PA provenance block it was delivered with. The block is a metadata element
// holding a `c2pa:manifest` element; the failure names the file, never its content.
export interface FichierLogo {
  nom: string;
  contenu: string;
}

const BLOC_C2PA = /<metadata\b[^>]*>[\s\S]*<c2pa:manifest\b[^>]*>[^<]+<\/c2pa:manifest>[\s\S]*<\/metadata>/;

export function controlerProvenance(fichiers: readonly FichierLogo[]): string[] {
  return fichiers.filter((f) => !BLOC_C2PA.test(f.contenu)).map((f) => `bloc de provenance C2PA absent : ${f.nom}`);
}
