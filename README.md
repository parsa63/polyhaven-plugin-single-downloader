# polyhaven-plugin-single-downloader
Blender script for downloading single Poly Haven assets. (not affiliated with Poly Haven)
I couldn't find any method to download single assets through the Poly Haven Blender plugin. Manually downloading an asset and copying it into the Asset Library also didn't work. This script downloads a single Poly Haven asset (HDRI, Texture, or 3D Model), processes it using the installed Poly Haven add-on's workflow, and automatically adds it to Blender's Asset Browser without requiring the entire asset library to be downloaded.

How to use

Install the Poly Haven Blender add-on.

Change the MAKE_BLEND path in the script to your local Poly Haven add-on location(line 41,42).

Open the script in Blender's Scripting workspace.

Set:ASSET_SLUG and TYPE
Example:     ASSET_SLUG = "asphalt_04"
            TYPE = "1"
Run the script in Blender's Scripting workspace.

ASSET_SLUG and TYPE guide
Copy the asset slug (Asset name) from the Poly Haven website URL. This avoids mistakes with characters in the asset name.
Example:      https://polyhaven.com/a/metal_office_desk            Slug: metal_office_desk
Type 0 = HDRIs Type 1 = Textures Type 2 = 3D Models
