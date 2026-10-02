#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点图标与分享卡片：从 assets/avatar-source.png（大叔头像）生成
  assets/favicon-32.png / favicon-192.png / apple-touch-icon.png / favicon.ico  浏览器标签页图标（圆形裁切、透明底）
  assets/avatar-96.png                                                    侧边栏 / 分享长图里用的小头像
  assets/og.png                                                           推特 / 微信链接预览卡片（1200×630）
只在换头像时跑一次，产物提交进仓库，出网站.py 每次原样拷到 site/assets/。
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "assets")
SRC = os.path.join(A, "avatar-source.png")

BG = (5, 7, 12)
MINT = (0, 255, 204)
LIME = (163, 230, 53)
INK = (232, 236, 243)
MUTED = (140, 148, 166)


def circle(img, size):
    """居中裁成正方形 → 缩放 → 圆形蒙版，边缘 4 倍超采样抗锯齿。"""
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).convert("RGBA")
    big = size * 4
    img = img.resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


SANS_B = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"]
SANS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
MONO = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]


def og_card(av):
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(glow)
    d.ellipse((-200, -260, 620, 560), fill=(0, 70, 58))
    d.ellipse((760, 300, 1400, 900), fill=(40, 60, 12))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(160)), 0.9)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 40):                       # 终端网格
        d.line((x, 0, x, H), fill=(14, 18, 28), width=1)
    for y in range(0, H, 40):
        d.line((0, y, W, y), fill=(14, 18, 28), width=1)
    a = circle(av, 250)
    ring = Image.new("RGBA", (270, 270), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, 269, 269), outline=LIME + (255,), width=4)
    im.paste(ring, (80, 180), ring)
    im.paste(a, (90, 190), a)
    d.text((400, 190), "链上大叔研究台", font=font(SANS_B, 76), fill=INK)
    d.text((402, 292), "宏观四层仪表盘 · 发射台矩阵 · 每日解读日志", font=font(SANS, 34), fill=MUTED)
    d.rectangle((402, 370, 408, 420), fill=MINT)
    d.text((426, 368), "uncleonchain.com", font=font(MONO, 40), fill=MINT)
    d.text((426, 426), "@Uncle_Onchain", font=font(MONO, 28), fill=MUTED)
    d.text((80, 560), "只给数据和过程记录 · 不构成投资建议", font=font(SANS, 22), fill=(90, 98, 116))
    im.save(os.path.join(A, "og.png"), optimize=True)


def main():
    av = Image.open(SRC)
    for size, name in [(32, "favicon-32.png"), (192, "favicon-192.png"), (96, "avatar-96.png")]:
        circle(av, size).save(os.path.join(A, name), optimize=True)
    # apple-touch-icon 不支持透明（iOS 会补黑/白底），直接给终端底色的方形
    t = Image.new("RGB", (180, 180), BG)
    c = circle(av, 164)
    t.paste(c, (8, 8), c)
    t.save(os.path.join(A, "apple-touch-icon.png"), optimize=True)
    circle(av, 64).save(os.path.join(A, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    og_card(av)
    print("图标与分享卡片已生成到", A)


if __name__ == "__main__":
    main()
