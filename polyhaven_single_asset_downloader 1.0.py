import bpy
import json
import hashlib
import subprocess
from pathlib import Path

# ============================================================
# Poly Haven plugin— Single Asset Downloader
# Blender 5.2
#
# Downloads ONE Poly Haven asset and processes it using the
# exact make_blend.py and hdri_template.blend from the
# installed Poly Haven add-on.
# ============================================================


# ============================================================
# user request 
# ============================================================

ASSET_SLUG = "asphalt_04"

TYPE = "1"

# ------------------------------------------------------------
# TYPE GUIDE
#
# Type 0 = HDRIs
# Type 1 = Textures
# Type 2 = 3D Models
# ------------------------------------------------------------

RESOLUTION = "1k"


# ========================================================================================================================
# Replace this with your exact make_blend.py in your add-on path // polyhavenassets-main  > utils > make_blend.py
# ========================================================================================================================

MAKE_BLEND = Path(
    r"C:\Users\ASUS\AppData\Roaming\Blender Foundation\Blender\5.2"
    r"\scripts\addons\polyhavenassets-main\utils\make_blend.py"
)




API_BASE = "https://api.polyhaven.com"

REQ_HEADERS = {
    "User-Agent": "Poly Haven Blender Asset Downloader"
}



TYPE_MAP = {
    "0": "hdris",
    "1": "textures",
    "2": "models",
}




def log(message):
    print(f"[Poly Haven Single Asset] {message}")



def md5_file(path):
    h = hashlib.md5()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


# ============================================================
# API GET
# ============================================================

def api_get(url):
    import requests

    log(f"API: {url}")

    response = requests.get(
        url,
        headers=REQ_HEADERS,
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Error retrieving {url}, "
            f"status code: {response.status_code}"
        )

    return response.json()


# ============================================================
# DOWNLOAD FILE
# ============================================================

def download_file(url, dest, expected_hash=None, retries=3):
    """
    Download a file and verify the MD5 when supplied.
    """

    import requests

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Already downloaded?
    # --------------------------------------------------------

    if expected_hash and dest.exists():

        if md5_file(dest).lower() == expected_hash.lower():
            log(f"Skipping {dest.name}, already downloaded")
            return

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    for attempt in range(1, retries + 1):

        log(
            f"Downloading {dest.name} "
            f"(attempt {attempt}/{retries})"
        )

        response = requests.get(
            url,
            headers=REQ_HEADERS,
            timeout=180,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Error retrieving {url}, "
                f"status code: {response.status_code}"
            )

        with dest.open("wb") as f:
            f.write(response.content)

        # ----------------------------------------------------
        # No hash supplied
        # ----------------------------------------------------

        if not expected_hash:
            return

        # ----------------------------------------------------
        # Verify MD5
        # ----------------------------------------------------

        actual = md5_file(dest)

        if actual.lower() == expected_hash.lower():
            return

        dest.unlink(missing_ok=True)

        if attempt < retries:
            log("MD5 mismatch; retrying...")

    raise RuntimeError(
        f"Error downloading {url}: "
        f"MD5 hash mismatch after {retries} attempts."
    )


# ============================================================
# FIND POLY HAVEN LIBRARY
# ============================================================

def find_poly_haven_library():

    for library in bpy.context.preferences.filepaths.asset_libraries:

        if library.name.lower() == "poly haven":

            return Path(
                bpy.path.abspath(library.path)
            ).resolve()

    current = "\n".join(
        f"  {lib.name}: {bpy.path.abspath(lib.path)}"
        for lib in bpy.context.preferences.filepaths.asset_libraries
    )

    raise RuntimeError(
        'No Blender Asset Library named exactly "Poly Haven" '
        "was found.\n\n"
        "Current Asset Libraries:\n"
        + (current or "  (none)")
        + "\n\n"
        "Create one in Preferences > File Paths > "
        "Asset Libraries."
    )


# ============================================================
# GET ASSET INFO
# ============================================================

def get_asset_info():

    # --------------------------------------------------------
    # Convert numeric TYPE to Poly Haven API type
    # --------------------------------------------------------

    if TYPE not in TYPE_MAP:

        raise RuntimeError(
            f"Invalid TYPE '{TYPE}'.\n\n"
            "Valid types are:\n"
            "  0 = HDRIs\n"
            "  1 = Textures\n"
            "  2 = 3D Models"
        )

    api_type = TYPE_MAP[TYPE]

    # --------------------------------------------------------
    # Request only assets of the selected type.
    #
    # Example:
    # TYPE 2 -> /assets?t=models
    # TYPE 1 -> /assets?t=textures
    # TYPE 0 -> /assets?t=hdris
    # --------------------------------------------------------

    assets = api_get(
        f"{API_BASE}/assets?t={api_type}"
    )

    if ASSET_SLUG not in assets:

        raise RuntimeError(
            f"Asset '{ASSET_SLUG}' was not found in "
            f"Poly Haven type '{api_type}'.\n\n"
            f"Selected TYPE: {TYPE}"
        )

    info = assets[ASSET_SLUG]

    # --------------------------------------------------------
    # Verify the numeric type too.
    # --------------------------------------------------------

    if str(info.get("type")) != TYPE:

        raise RuntimeError(
            f"Asset type mismatch.\n\n"
            f"Requested TYPE: {TYPE}\n"
            f"Asset's actual type: {info.get('type')}"
        )

    return info


# ============================================================
# DOWNLOAD THUMBNAIL
# ============================================================

def download_thumbnail(asset_dir):

    thumbnail = asset_dir / "thumbnail.webp"

    thumb_path = (
        f"/asset_img/thumbs/{ASSET_SLUG}.png"
        f"?width=256&height=256"
    )

    primary_url = (
        "https://cdn.polyhaven.com" + thumb_path
    )

    fallback_url = (
        "https://cdn.polyhaven.org" + thumb_path
    )

    try:

        download_file(
            primary_url,
            thumbnail
        )

    except Exception as primary_error:

        log(
            "Primary thumbnail CDN failed; "
            "trying fallback CDN..."
        )

        try:

            download_file(
                fallback_url,
                thumbnail
            )

        except Exception:

            raise primary_error

    return thumbnail



def download_blend_asset(info, asset_dir):

    try:

        blend_info = (
            info["files"]
            ["blend"]
            [RESOLUTION]
            ["blend"]
        )

    except KeyError as exc:

        raise RuntimeError(
            f"The Poly Haven manifest does not contain "
            f"a {RESOLUTION} Blender file for "
            f"'{ASSET_SLUG}'."
        ) from exc

    blend_file = (
        asset_dir /
        f"{ASSET_SLUG}.blend"
    )

    # --------------------------------------------------------
    # Download .blend
    # --------------------------------------------------------

    download_file(
        blend_info["url"],
        blend_file,
        blend_info.get("md5"),
    )

    # --------------------------------------------------------
    # Download included files
    #
    # These include textures and other dependencies.
    # --------------------------------------------------------

    include = blend_info.get("include", {})

    log(
        f"Included files to download: "
        f"{len(include)}"
    )

    for relative_path, file_info in include.items():

        destination = (
            asset_dir / relative_path
        )

        download_file(
            file_info["url"],
            destination,
            file_info.get("md5"),
        )

    return blend_file




def process_blend_asset(
    blend_file,
    info,
    thumbnail
):

    authors = ", ".join(
        info.get("authors", {}).keys()
    )

    categories = ";".join(
        info.get("categories", [])
    )

    tags = ";".join(
        info.get("tags", [])
    )

    dimensions = (
        ";".join(
            str(x)
            for x in info["dimensions"]
        )
        if "dimensions" in info
        else "NONE"
    )

    command = [

        str(bpy.app.binary_path),

        "--background",

        str(blend_file),

        "--factory-startup",

        "--python",

        str(MAKE_BLEND),

        "--",

        ASSET_SLUG,

        str(info["type"]),

        str(thumbnail),

        authors,

        categories,

        tags,

        dimensions,

        "NONE",
    ]

    log(
        "Running the installed "
        "make_blend.py..."
    )

    result = subprocess.run(
        command,
        check=False
    )

    if result.returncode != 0:

        raise RuntimeError(
            "make_blend.py failed with "
            f"Blender exit code "
            f"{result.returncode}."
        )




def process_hdri_asset(
    hdr_file,
    info,
    thumbnail
):

    # --------------------------------------------------------
    # The official add-on stores the HDRI template beside
    # make_blend.py.
    # --------------------------------------------------------

    hdri_template = (
        MAKE_BLEND.parent /
        "hdri_template.blend"
    )

    if not hdri_template.is_file():

        raise FileNotFoundError(
            "Could not find the Poly Haven HDRI "
            "template:\n"
            + str(hdri_template)
            + "\n\n"
            "This file is required for HDRI "
            "processing."
        )

    authors = ", ".join(
        info.get("authors", {}).keys()
    )

    categories = ";".join(
        info.get("categories", [])
    )

    tags = ";".join(
        info.get("tags", [])
    )


    command = [

        str(bpy.app.binary_path),

        "--background",

        str(hdri_template),

        "--factory-startup",

        "--python",

        str(MAKE_BLEND),

        "--",

        ASSET_SLUG,

        "0",

        str(thumbnail),

        authors,

        categories,

        tags,

        "NONE",

        str(hdr_file),
    ]

    log(
        "Running the installed "
        "make_blend.py for HDRI..."
    )

    result = subprocess.run(
        command,
        check=False
    )

    if result.returncode != 0:

        raise RuntimeError(
            "HDRI make_blend.py processing "
            "failed with Blender exit code "
            f"{result.returncode}."
        )


# ============================================================
# DOWNLOAD HDRI
# ============================================================

def download_hdri_asset(info, asset_dir):

    try:

        hdr_info = (
            info["files"]
            ["hdri"]
            [RESOLUTION]
            ["hdr"]
        )

    except KeyError as exc:

        raise RuntimeError(
            f"The Poly Haven manifest does not contain "
            f"a {RESOLUTION} HDRI file for "
            f"'{ASSET_SLUG}'."
        ) from exc

    # --------------------------------------------------------
    # Preserve the original filename from the URL.
    # --------------------------------------------------------

    hdr_filename = Path(
        hdr_info["url"]
    ).name

    hdr_file = (
        asset_dir / hdr_filename
    )

    download_file(
        hdr_info["url"],
        hdr_file,
        hdr_info.get("md5"),
    )

    return hdr_file


# ============================================================
# SAVE INFO.JSON
# ============================================================

def save_info(asset_dir, info):

    with open(
        asset_dir / "info.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            info,
            f,
            indent=4
        )


# ============================================================
# MAIN
# ============================================================

def main():

    log("Starting...")

    log(
        f"Asset:      {ASSET_SLUG}"
    )

    log(
        f"Type:       {TYPE} "
        f"({TYPE_MAP.get(TYPE, 'INVALID')})"
    )

    log(
        f"Resolution: {RESOLUTION}"
    )

    # --------------------------------------------------------
    # Validate make_blend.py
    # --------------------------------------------------------

    if not MAKE_BLEND.is_file():

        raise FileNotFoundError(
            "Could not find the installed "
            "Poly Haven make_blend.py at:\n"
            + str(MAKE_BLEND)
        )

    # --------------------------------------------------------
    # Validate TYPE
    # --------------------------------------------------------

    if TYPE not in TYPE_MAP:

        raise RuntimeError(
            f"Invalid TYPE '{TYPE}'.\n\n"
            "Use:\n"
            "  0 = HDRI\n"
            "  1 = Texture\n"
            "  2 = 3D Model"
        )

    # --------------------------------------------------------
    # Find Blender Asset Library
    # --------------------------------------------------------

    library_dir = (
        find_poly_haven_library()
    )

    asset_dir = (
        library_dir / ASSET_SLUG
    )

    asset_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    log(
        f"Asset Library: {library_dir}"
    )

    log(
        f"Asset folder:  {asset_dir}"
    )

    # --------------------------------------------------------
    # 1. Get metadata
    # --------------------------------------------------------

    info = get_asset_info()

    # --------------------------------------------------------
    # 2. Get authoritative file manifest
    # --------------------------------------------------------

    info["files"] = api_get(
        f"{API_BASE}/files/{ASSET_SLUG}"
    )

    # --------------------------------------------------------
    # 3. Thumbnail
    # --------------------------------------------------------

    thumbnail = download_thumbnail(
        asset_dir
    )

    # ========================================================
    # TYPE 0 — HDRI
    # ========================================================

    if TYPE == "0":

        log(
            "Asset type detected: HDRI"
        )

        # ----------------------------------------------------
        # Download HDR file
        # ----------------------------------------------------

        hdr_file = download_hdri_asset(
            info,
            asset_dir
        )

        # ----------------------------------------------------
        # Create Blender asset from HDRI template
        # ----------------------------------------------------

        process_hdri_asset(
            hdr_file,
            info,
            thumbnail
        )

    # ========================================================
    # TYPE 1 / TYPE 2 — TEXTURE OR MODEL
    # ========================================================

    else:

        if TYPE == "1":

            log(
                "Asset type detected: Texture"
            )

        elif TYPE == "2":

            log(
                "Asset type detected: 3D Model"
            )

        # ----------------------------------------------------
        # Download .blend + all included files
        # ----------------------------------------------------

        blend_file = download_blend_asset(
            info,
            asset_dir
        )

        # ----------------------------------------------------
        # Process using official make_blend.py
        # ----------------------------------------------------

        process_blend_asset(
            blend_file,
            info,
            thumbnail
        )

    # --------------------------------------------------------
    # Save info.json
    # --------------------------------------------------------

    save_info(
        asset_dir,
        info
    )

    # --------------------------------------------------------
    # Refresh Asset Browser
    # --------------------------------------------------------

    try:

        bpy.ops.asset.library_refresh()

    except Exception as exc:

        log(
            f"Asset library refresh returned: "
            f"{exc}"
        )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    log("")

    log("=" * 65)

    log("SUCCESS")

    log(
        f"Asset:      {ASSET_SLUG}"
    )

    log(
        f"Type:       {TYPE} "
        f"({TYPE_MAP[TYPE]})"
    )

    log(
        f"Location:   {asset_dir}"
    )

    log(
        "The asset has been downloaded "
        "and processed."
    )

    log(
        "Check the Poly Haven Asset Library "
        "in the Asset Browser."
    )

    log("=" * 65)


# ============================================================
# RUN
# ============================================================

try:

    main()

except Exception as exc:

    print("")

    print("=" * 65)

    print(
        "POLY HAVEN SINGLE-ASSET "
        "DOWNLOAD FAILED"
    )

    print("=" * 65)

    print(str(exc))

    print("=" * 65)

    raise