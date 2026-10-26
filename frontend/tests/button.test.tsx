import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/Button";

describe("Button", () => {
  it("renders a keyboard-sized labelled action", () => {
    render(<Button>Run analysis</Button>);

    const button = screen.getByRole("button", { name: "Run analysis" });
    expect(button).toBeVisible();
    expect(button.className).toContain("min-h-11");
    expect(button.className).toContain("cursor-pointer");
  });
});
