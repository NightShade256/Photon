from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

__all__ = ["welcome_leave_image"]


def welcome_leave_image(avatar: bytes, author, mode) -> BytesIO:
    """Returns a welcome/leave image.

    If mode == True then welcome image.
    If mode == False then leave image.
    """

    name_length = len(author.display_name)
    name_font = ImageFont.truetype("assets/font/unifont.ttf", 44 if name_length < 25 else 38)
    with Image.new("RGB", (1024, 450)) as canvas:
        with Image.open(BytesIO(avatar)) as pfp_original:
            asset_path = "assets/img/guild_"
            asset_path += "join.png" if mode else "leave.png"
            with Image.open(asset_path) as base:
                pfp = pfp_original.resize((256, 256))
                bigsize = (pfp.size[0] * 3, pfp.size[1] * 3)
                with Image.new("L", bigsize, 0) as mask:
                    mask_drawer = ImageDraw.Draw(mask)
                    mask_drawer.ellipse((0, 0) + bigsize, fill=255)
                    del mask_drawer
                    mask = mask.resize(pfp.size, Image.ANTIALIAS)
                    pfp.putalpha(mask)
                    canvas.paste(base, (0, 0))
                    canvas.paste(pfp, (58, 95), pfp)
                    canvas_drawer = ImageDraw.Draw(canvas, "RGB")
                    canvas_drawer.text(
                        (360, 160), author.display_name, font=name_font, fill=(255, 255, 255))
                    canvas_drawer.text(
                        (400, 233), author.discriminator, font=name_font, fill=(255, 255, 255))
                    del canvas_drawer
                    buffer = BytesIO()
                    canvas.save(buffer, "PNG")
    buffer.seek(0)
    return buffer
