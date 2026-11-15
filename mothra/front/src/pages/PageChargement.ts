// What the bundle shows while it looks for the server (task 19.7): the loading state of the catalogue, before the application is rendered.
// It reads the language of the provider around it; it has no state of its own.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

export function PageChargement(): ReactElement {
  const intl = useIntl();
  return h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" }));
}
