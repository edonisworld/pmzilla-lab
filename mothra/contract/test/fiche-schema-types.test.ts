// The static types of the request schemas of the sheet (design D29): the management question is the closed list's own type, not a
// type that resolved to nothing. The assignments below are checked by the typecheck; the run-time checks follow the schema.
import assert from "node:assert/strict";
import { test } from "node:test";

import Value from "typebox/value";

import { SchemaCreationFiche, SchemaModificationFiche, SchemaTexteRefuse } from "../src/fiche-schema.ts";
import type { CreationFiche, ModificationFiche, TexteRefuse } from "../src/fiche-schema.ts";

test("the refusal of a written text is typed from its schema: the field is effect or cause", () => {
  const valide: TexteRefuse = { error: "TEXT_REFUSED", field: "effect", reason: "too_long", count: 612, max: 500 };
  // @ts-expect-error a field outside the list does not compile
  const hors: TexteRefuse = { error: "TEXT_REFUSED", field: "title", reason: "email" };
  assert.equal(Value.Check(SchemaTexteRefuse, valide), true);
  assert.equal(Value.Check(SchemaTexteRefuse, hors), false);
});

test("the management question of the completion and of the creation is typed as the closed list", () => {
  const modification: ModificationFiche = { managementQuestion: "predictability" };
  const creation: CreationFiche = { chart: "lead_cycle_h5", scope: "team.a", dataDate: "2026-10-27", managementQuestion: "scope_growth" };
  // @ts-expect-error a code outside the list does not compile
  const hors: ModificationFiche = { managementQuestion: "not_a_question" };
  // @ts-expect-error a question is a code, not a number
  const nombre: ModificationFiche = { managementQuestion: 3 };
  assert.equal(Value.Check(SchemaModificationFiche, modification), true);
  assert.equal(Value.Check(SchemaCreationFiche, creation), true);
  assert.equal(Value.Check(SchemaModificationFiche, hors), false);
  assert.equal(Value.Check(SchemaModificationFiche, nombre), false);
});
