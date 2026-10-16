import { describe, expect, it } from "vitest";
import { fold } from "./fold";

describe("fold", () => {
  it("lower-cases and strips Vietnamese diacritics, including đ", () => {
    expect(fold("Tuấn Đức")).toBe("tuan duc");
    expect(fold("PHẠM")).toBe("pham");
    expect(fold("Nguyễn Phúc Hoàng Vy")).toBe("nguyen phuc hoang vy");
  });

  it("leaves plain ASCII untouched apart from case", () => {
    expect(fold("Anna")).toBe("anna");
    expect(fold("")).toBe("");
  });
});
