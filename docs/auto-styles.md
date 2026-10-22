# Automatic video styles

DuckMMO uses its existing FFmpeg renderer with the installed libass subtitle filter.
The production structure was reviewed against MoneyPrinterTurbo, but DuckMMO does not
install, call or copy the MoneyPrinterTurbo application. Its MoviePy application is not a dependency.
References: https://github.com/harry0703/MoneyPrinterTurbo and https://github.com/libass/libass

New renders automatically choose a bundled style by content branch: novel -> cinematic,
comic -> bold, research -> clean. Uploaded images use slow zoom for story/comic presets;
research uses static images. Captions are separate ASS overlays, with outlines and fades.
The original narration chunks are synthesized unchanged. Shorter subtitle phrases divide each
chunk's measured audio duration proportionally by word count. This is estimated phrase timing,
not word alignment or karaoke. UTF-8 Vietnamese is retained and ASS overrides are escaped.
SRT, ASS and the selected style JSON are available as job artifacts.

## Updating the catalog

The bundled catalog is app/services/styles.json. It is read for every new render request.
An optional STUDIO_STYLE_CATALOG_URL connects a public JSON catalog using that same schema.
It is fetched before each new render, validates all fields and content branches, and caches
only valid catalogs. Failed updates use the last valid catalog or the built-in catalog and
record this in job events. No code, font downloads, effect plugins or shell commands are loaded.
The chosen complete style, catalog version and hash are pinned in render_config and manifest;
updates do not affect running jobs or retries. Connecting a source is deployment setup, not
per-video styling. No external source is configured by default. This is not a CapCut-template
scraper or a service that discovers trending styles automatically.

The API artifact kinds styled_subtitles and style return subtitles.ass and style.json.
The final review remains mandatory. Already rendered videos keep their original appearance;
select Render again to produce a new version.
