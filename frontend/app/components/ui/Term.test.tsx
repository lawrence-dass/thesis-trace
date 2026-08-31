// @vitest-environment jsdom
//
// The one component in this app whose behaviour is worth mounting (see
// vitest.config.ts's rationale for defaulting every other test to `node`):
// Term's whole value is real DOM interaction — a native <button> toggling
// aria-expanded — which a pure-function test cannot verify.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Term } from "./Term";

afterEach(cleanup);

describe("Term", () => {
  it("renders the trigger as a real <button>, not a span — this is what makes Enter/Space work for free", () => {
    render(<Term id="dsri">DSRI</Term>);
    expect(screen.getByRole("button", { name: "DSRI" }).tagName).toBe("BUTTON");
  });

  it("starts collapsed: aria-expanded false and the definition is aria-hidden", () => {
    render(<Term id="dsri">DSRI</Term>);
    const button = screen.getByRole("button", { name: "DSRI" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    const definitionId = button.getAttribute("aria-controls");
    expect(document.getElementById(definitionId!)?.getAttribute("aria-hidden")).toBe("true");
  });

  it("clicking toggles aria-expanded and the definition's aria-hidden state, and renders the real definition text", () => {
    render(<Term id="dsri">DSRI</Term>);
    const button = screen.getByRole("button", { name: "DSRI" });
    const definitionId = button.getAttribute("aria-controls")!;

    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById(definitionId)?.getAttribute("aria-hidden")).toBe("false");
    expect(document.getElementById(definitionId)?.textContent).toMatch(/Days Sales in Receivables/);

    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(document.getElementById(definitionId)?.getAttribute("aria-hidden")).toBe("true");
  });

  it("the trigger's aria-controls points at an id that actually exists in the DOM", () => {
    render(<Term id="x1_working_capital">X1</Term>);
    const button = screen.getByRole("button", { name: "X1" });
    const definitionId = button.getAttribute("aria-controls");
    expect(definitionId).toBeTruthy();
    expect(document.getElementById(definitionId!)).not.toBeNull();
  });

  it("the expand transition is gated behind motion-safe:, never applied unconditionally", () => {
    render(<Term id="dsri">DSRI</Term>);
    const button = screen.getByRole("button", { name: "DSRI" });
    const definition = document.getElementById(button.getAttribute("aria-controls")!);
    expect(definition?.className).toMatch(/motion-safe:transition-/);
  });
});
