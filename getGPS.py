from PIL import Image
import piexif

def get_gps(path):
    img = Image.open(path)

    # Safely get EXIF bytes
    exif_bytes = img.info.get('exif')
    if exif_bytes is None:
        print("No EXIF metadata found.")
        return None

    exif_dict = piexif.load(exif_bytes)

    gps = exif_dict.get("GPS", {})
    if not gps:
        print("EXIF found but no GPS tags.")
        return None
    
    def conv(value):
        return (
            float(value[0][0]) / float(value[0][1]),
            float(value[1][0]) / float(value[1][1]),
            float(value[2][0]) / float(value[2][1])
        )

    lat_vals = conv(gps[piexif.GPSIFD.GPSLatitude])
    lon_vals = conv(gps[piexif.GPSIFD.GPSLongitude])

    lat_ref = gps[piexif.GPSIFD.GPSLatitudeRef].decode()
    lon_ref = gps[piexif.GPSIFD.GPSLongitudeRef].decode()

    def to_deg(values, ref):
        deg = values[0] + values[1]/60 + values[2]/3600
        return -deg if ref in ["S", "W"] else deg

    lat = to_deg(lat_vals, lat_ref)
    lon = to_deg(lon_vals, lon_ref)

    return lat, lon

print(get_gps("foto/11-25-12-30-25.jpg"))
