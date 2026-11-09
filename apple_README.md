# Apple chip identifications from iFixit

- [apple_ifixit_chips.json](apple_ifixit_chips.json): **3,056 identification entries** across **181 device/category records** with identifications.
- [apple_ifixit_coverage.json](apple_ifixit_coverage.json): coverage for **645 device/family records**, including records with no extracted chip list.

Reviewed 639 category pages and 292 related guides, cross-checked against the 2,114-entry public teardown index. Selected linked teardown articles supplement the guide identifications. All years are in scope.

`apple_ifixit_chips.json` contains devices, written chip identifications, uncertainty flags and source references. `apple_ifixit_coverage.json` is a smaller coverage index.

Scope: all years, Apple-branded devices, English iFixit categories and teardown / Chip ID guides, plus selected linked articles. Third-party accessories and Beats are excluded. Product-family categories are retained and marked with `category_has_children`.

This is a best-effort text extraction, not an exhaustive bill of materials. Photos were not OCRed; videos, reader comments, PDF-only labels, the full news archive and all replacement guides were not searched. Empty arrays mean no entries extracted in this scan. Identification counts are textual entries rather than unique physical chips: one entry may describe multiple components, stacked chips, or an unnamed device function.

Each entry includes an `identification`, `manufacturers_mentioned`, a `tentative` flag and one or more source references. Manufacturer mentions are not verified manufacturer/foundry fields. False `tentative` means no tentative wording was detected, not independent verification. Part numbers remain in the identification string to avoid guessing how stacked packages and alternate markings should be split.

Sources are attributed to iFixit and the original guide authors/contributors, listed in `source_guides`. Extracted/condensed text follows the source CC BY-NC-SA 3.0 license and source-specific notices: https://creativecommons.org/licenses/by-nc-sa/3.0/ . API reference: https://www.ifixit.com/api-docs .

The source unit can differ from other storage sizes, regions and revisions. A combined-device teardown remains grouped under its source category; identification does not automatically propagate to related models.

## Read it without JSON

Download [device_chip_report.html](device_chip_report.html) using GitHub’s **Download raw file** button, then open the saved file in your browser and select Apple. See [USING_REPORT.md](USING_REPORT.md) for instructions, Python regeneration, and datasheet-link limitations. The inventory itself does not establish public datasheet availability for custom Apple parts.
