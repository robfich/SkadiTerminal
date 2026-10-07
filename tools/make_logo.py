# Erzeugt skaditerminal.ico + skaditerminal_1024.png (im Repo-Root ausfuehren, braucht Pillow)
import math, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops
S = 1024
c = S // 2

# Hintergrund: abgerundetes Quadrat, radialer Verlauf dunkelblau
bg = Image.new("RGBA", (S, S))
px = bg.load()
for y in range(S):
    for x in range(S):
        d = math.hypot(x - c, y - c * 0.9) / (S * 0.75)
        t = min(d, 1)
        px[x, y] = (int(18 + 10*(1-t)), int(40 + 50*(1-t)), int(70 + 90*(1-t)), 255)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([24, 24, S-24, S-24], radius=200, fill=255)
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img.paste(bg, (0, 0), mask)

# Augenform (Mandel) aus zwei Kreisbögen
eye = Image.new("L", (S, S), 0)
r, off = 520, 300
a = Image.new("L", (S, S), 0); ImageDraw.Draw(a).ellipse([c-r, c-off-r, c+r, c-off+r], fill=255)
b = Image.new("L", (S, S), 0); ImageDraw.Draw(b).ellipse([c-r, c+off-r, c+r, c+off+r], fill=255)
eye = ImageChops.multiply(a, b)

# Glow um das Auge
glow = Image.new("RGBA", (S, S), (120, 220, 255, 0))
glow.putalpha(eye.filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.9)))
img = Image.alpha_composite(img, glow)

# Auge füllen: helles Eisweiß -> Cyan
fill = Image.new("RGBA", (S, S), (215, 245, 255, 255))
img.paste(fill, (0, 0), eye)
inner = eye.filter(ImageFilter.MinFilter(41))
fill2 = Image.new("RGBA", (S, S), (150, 225, 255, 255))
img.paste(fill2, (0, 0), inner.filter(ImageFilter.GaussianBlur(20)))

# Iris
d = ImageDraw.Draw(img)
ir = 190
d.ellipse([c-ir, c-ir, c+ir, c+ir], fill=(20, 90, 170, 255))
d.ellipse([c-ir+22, c-ir+22, c+ir-22, c+ir-22], fill=(40, 150, 230, 255))

# Schneeflocke in der Iris
w = 26
for k in range(6):
    ang = math.radians(90 + k * 60)
    x2, y2 = c + math.cos(ang) * 150, c - math.sin(ang) * 150
    d.line([c, c, x2, y2], fill=(235, 250, 255, 255), width=w)
    for frac in (0.55, 0.8):
        bx, by = c + math.cos(ang) * 150 * frac, c - math.sin(ang) * 150 * frac
        for side in (-1, 1):
            a2 = ang + side * math.radians(45)
            d.line([bx, by, bx + math.cos(a2) * 55, by - math.sin(a2) * 55],
                   fill=(235, 250, 255, 255), width=w - 8)
d.ellipse([c-40, c-40, c+40, c+40], fill=(10, 40, 90, 255))

img.save("skaditerminal_1024.png")
img.save("skaditerminal.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
