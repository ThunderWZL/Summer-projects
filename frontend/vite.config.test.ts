import { describe, expect, it } from "vitest";

import config from "./vite.config.ts";

describe("Vite development proxy", () => {
  it("forwards evidence images to the backend", () => {
    expect(config.server?.proxy).toMatchObject({
      "/evidence": "http://localhost:8000",
    });
  });
});
