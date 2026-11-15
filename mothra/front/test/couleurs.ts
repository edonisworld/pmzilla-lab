// Colour computations for the tests, no package: sRGB to CIELAB (D65), the colour-vision-deficiency simulation of Machado, Oliveira and
// Fernandes (2009, severity 1.0, applied on linear RGB) and the CIEDE2000 colour difference (Sharma, Wu and Dalal, 2005).
export type Lab = readonly [number, number, number];
export type Matrice = readonly [readonly [number, number, number], readonly [number, number, number], readonly [number, number, number]];
export type Rgb = readonly [number, number, number];

// A colour written #RRGGBB as linear RGB, each channel in 0..1.
export function hexVersLineaire(hex: string): Rgb {
  const m = /^#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$/.exec(hex);
  if (m === null) throw new Error(`couleur #RRGGBB attendue : ${hex}`);
  const lin = (c: string): number => {
    const v = Number.parseInt(c, 16) / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return [lin(m[1]), lin(m[2]), lin(m[3])];
}

// Machado, Oliveira and Fernandes 2009, severity 1.0 (full dichromacy), on linear RGB.
export const PROTANOPIE: Matrice = [
  [0.152286, 1.052583, -0.204868],
  [0.114503, 0.786281, 0.099216],
  [-0.003882, -0.048116, 1.051998],
];
export const DEUTERANOPIE: Matrice = [
  [0.367322, 0.860646, -0.227968],
  [0.280085, 0.672501, 0.047413],
  [-0.01182, 0.04294, 0.968881],
];
export const TRITANOPIE: Matrice = [
  [1.255528, -0.076749, -0.178779],
  [-0.078411, 0.930809, 0.147602],
  [0.004733, 0.691367, 0.3039],
];

export function simuler(lineaire: Rgb, matrice: Matrice): Rgb {
  const borne = (v: number): number => Math.min(1, Math.max(0, v));
  const [r, g, b] = lineaire;
  return matrice.map((l) => borne(l[0] * r + l[1] * g + l[2] * b)) as unknown as Rgb;
}

const BLANC_D65: Rgb = [0.95047, 1, 1.08883];

export function lineaireVersLab([r, g, b]: Rgb): Lab {
  const x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b;
  const y = 0.2126729 * r + 0.7151522 * g + 0.072175 * b;
  const z = 0.0193339 * r + 0.119192 * g + 0.9503041 * b;
  const f = (t: number): number => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
  const fx = f(x / BLANC_D65[0]);
  const fy = f(y / BLANC_D65[1]);
  const fz = f(z / BLANC_D65[2]);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

export function hexVersLab(hex: string): Lab {
  return lineaireVersLab(hexVersLineaire(hex));
}

const RAD = Math.PI / 180;

// CIEDE2000 (kL = kC = kH = 1), in the formulation of Sharma, Wu and Dalal (2005).
export function ecart00(lab1: Lab, lab2: Lab): number {
  const [L1, a1, b1] = lab1;
  const [L2, a2, b2] = lab2;
  const C1 = Math.hypot(a1, b1);
  const C2 = Math.hypot(a2, b2);
  const Cm = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)));
  const a1p = (1 + G) * a1;
  const a2p = (1 + G) * a2;
  const C1p = Math.hypot(a1p, b1);
  const C2p = Math.hypot(a2p, b2);
  const teinte = (b: number, a: number): number => (b === 0 && a === 0 ? 0 : ((Math.atan2(b, a) / RAD) + 360) % 360);
  const h1p = teinte(b1, a1p);
  const h2p = teinte(b2, a2p);
  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  let dhp = 0;
  if (C1p * C2p !== 0) {
    dhp = h2p - h1p;
    if (dhp > 180) dhp -= 360;
    else if (dhp < -180) dhp += 360;
  }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin((dhp / 2) * RAD);
  const Lpm = (L1 + L2) / 2;
  const Cpm = (C1p + C2p) / 2;
  let hpm = h1p + h2p;
  if (C1p * C2p !== 0) {
    if (Math.abs(h1p - h2p) <= 180) hpm /= 2;
    else hpm = hpm < 360 ? (hpm + 360) / 2 : (hpm - 360) / 2;
  }
  const T = 1 - 0.17 * Math.cos((hpm - 30) * RAD) + 0.24 * Math.cos(2 * hpm * RAD) + 0.32 * Math.cos((3 * hpm + 6) * RAD) - 0.2 * Math.cos((4 * hpm - 63) * RAD);
  const dTheta = 30 * Math.exp(-(((hpm - 275) / 25) ** 2));
  const Rc = 2 * Math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7));
  const Sl = 1 + (0.015 * (Lpm - 50) ** 2) / Math.sqrt(20 + (Lpm - 50) ** 2);
  const Sc = 1 + 0.045 * Cpm;
  const Sh = 1 + 0.015 * Cpm * T;
  const Rt = -Math.sin(2 * dTheta * RAD) * Rc;
  return Math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh));
}

export const VISIONS: ReadonlyArray<readonly [string, Matrice | null]> = [
  ["normal", null],
  ["protanopia", PROTANOPIE],
  ["deuteranopia", DEUTERANOPIE],
  ["tritanopia", TRITANOPIE],
];

// The colour as seen under one vision (null: normal vision), in CIELAB.
export function vue(hex: string, matrice: Matrice | null): Lab {
  const lin = hexVersLineaire(hex);
  return lineaireVersLab(matrice === null ? lin : simuler(lin, matrice));
}
