#!/usr/bin/env python3
"""Draw text exactly as iTerm2 3.5 would draw it with Vaagdevi: CoreText
shaping, then iTerm2's grid re-placement (ligate.iterm_x). Use it to check
rendering without a screenshot.

    .venv/bin/python preview.py out.png "line one" "line two" ...
"""

import os
import sys
from pathlib import Path

import CoreText as CT
import Quartz as Q
from Foundation import NSURL

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import LINE_SPACING, OUT  # noqa: E402
from ligate import iterm_x  # noqa: E402

SIZE = float(os.environ.get("SIZE", 36))   # points; set SIZE=110 to inspect details
CELL = 0.6 * SIZE
# iTerm2's row: Monaco's line (ascent 1000 + descent 250 + gap 83 per 1000)
# times the profile's vertical spacing, extra space split above and below.
ROW = SIZE * 1.333 * float(os.environ.get("LINE_SPACING", LINE_SPACING))


def load_font(size, path=OUT):
    descs = CT.CTFontManagerCreateFontDescriptorsFromURL(NSURL.fileURLWithPath_(str(path)))
    return CT.CTFontCreateWithFontDescriptor(descs[0], size, None)


def layout_line(font, text, x, y):
    """[(run font, glyph, x, y)] for `text` with its baseline at (x, y), each
    glyph where iTerm2 puts it. Characters the font has no glyph for are
    left out, as iTerm2 would draw them with the main font."""
    scale = CT.CTFontGetSize(font) / 1000.0
    attrs = {CT.kCTFontAttributeName: font}
    line = CT.CTLineCreateWithAttributedString(CT.CFAttributedStringCreate(None, text, attrs))
    out = []
    for run in CT.CTLineGetGlyphRuns(line):
        n = CT.CTRunGetGlyphCount(run)
        rf = CT.CTRunGetAttributes(run)[CT.kCTFontAttributeName]
        g = CT.CTRunGetGlyphs(run, (0, n), None)
        p = CT.CTRunGetPositions(run, (0, n), None)
        a = CT.CTRunGetAdvances(run, (0, n), None)
        i = CT.CTRunGetStringIndices(run, (0, n), None)
        glyphs = [dict(x=p[k].x / scale, adv=a[k].width / scale, idx=i[k]) for k in range(n)]
        xs = iterm_x(glyphs, text)
        out += [(rf, g[k], x + xs[k] * scale, y + p[k].y) for k in range(n)]
    return out


def draw_line(ctx, font, text, x, y):
    """Draw `text` with its baseline at (x, y) as iTerm2 would."""
    for rf, g, gx, gy in layout_line(font, text, x, y):
        CT.CTFontDrawGlyphs(rf, [g], [Q.CGPointMake(gx, gy)], 1, ctx)


def ink(font, text, x, y):
    """Ink rectangles (x0, y0, x1, y1) of `text` drawn as iTerm2 would."""
    out = []
    for rf, g, gx, gy in layout_line(font, text, x, y):
        _, rects = CT.CTFontGetBoundingRectsForGlyphs(rf, CT.kCTFontOrientationDefault, [g], None, 1)
        r = rects[0]
        if r.size.width > 0:
            out.append((gx + r.origin.x, gy + r.origin.y,
                        gx + r.origin.x + r.size.width, gy + r.origin.y + r.size.height))
    return out


def main():
    out, lines = Path(sys.argv[1]), sys.argv[2:]
    font = load_font(SIZE)
    cols = max(len(l) for l in lines) + 2
    W, H = int(CELL * cols + 40), int(ROW * len(lines) + 30)
    ctx = Q.CGBitmapContextCreate(None, W, H, 8, 0, Q.CGColorSpaceCreateDeviceRGB(),
                                  Q.kCGImageAlphaPremultipliedLast)
    Q.CGContextSetRGBFillColor(ctx, 0.157, 0.157, 0.157, 1)
    Q.CGContextFillRect(ctx, Q.CGRectMake(0, 0, W, H))
    Q.CGContextSetRGBStrokeColor(ctx, 1, 1, 1, 0.07)
    for k in range(cols + 1):
        Q.CGContextMoveToPoint(ctx, 20 + k * CELL, 0)
        Q.CGContextAddLineToPoint(ctx, 20 + k * CELL, H)
    Q.CGContextStrokePath(ctx)
    Q.CGContextSetRGBFillColor(ctx, 0.92, 0.86, 0.70, 1)
    for r, text in enumerate(lines):
        y = H - 20 - (r + 1) * ROW + (ROW - 1.333 * SIZE) / 2 + 0.29 * SIZE
        draw_line(ctx, font, text, 20, y)
    img = Q.CGBitmapContextCreateImage(ctx)
    dest = Q.CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(str(out)), "public.png", 1, None)
    Q.CGImageDestinationAddImage(dest, img, None)
    Q.CGImageDestinationFinalize(dest)
    print(out)


if __name__ == "__main__":
    main()
