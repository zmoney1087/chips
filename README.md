# Device chip identifications from iFixit

## Read the results without JSON

**[Download the ready-made HTML report](device_chip_report.html)** using GitHub’s **Download raw file** button, then open the saved file in your browser. No Python or installation is needed to use that report.

Choose a device to see its identified chips, plain-language descriptions of what they do, verified manufacturer datasheet links, and iFixit evidence. Search by device/chip, filter by brand, print a device view, or download its chip list as CSV. The report works offline; external document/search links need internet access.

- [Python script](build_device_report.py): regenerate with `python build_device_report.py --open` (Python 3.9+, no dependencies).
- [Full instructions and datasheet limitations](USING_REPORT.md).
- [All entries as a spreadsheet CSV](device_chips.csv).
- [Verified datasheet catalog](datasheet_catalog.json): 125 part identifiers, matching 200 of the current 3,381 identification entries. Every other entry has a clearly labeled search link; that is not a verified datasheet. A public datasheet is not established for many custom or unidentified chips.

Validation: nine Python tests plus browser checks for selection, filtering, CSV download, source disagreements, empty searches and mobile layout. The script makes no network requests and preserves the original inventories.

## JSON inventories

Source-linked chip-identification datasets for Apple, Xiaomi and Huawei, covering all years discoverable in the reviewed English iFixit categories and guides.

| Dataset | Identification entries | Device/category records with identifications | Total coverage records | Notes |
|---|---:|---:|---:|---|
| [Apple JSON](apple_ifixit_chips.json) | 3,056 | 181 | 645 | See Apple notes below |
| [Xiaomi JSON](xiaomi_ifixit_chips.json) | 79 | 6 | 253 | [Scope, methods and limitations](xiaomi_README.md) |
| [Huawei JSON](huawei_ifixit_chips.json) | 246 | 11 | 196 | [Scope, methods and limitations](huawei_README.md) |

Coverage indexes: [Apple](apple_ifixit_coverage.json), [Xiaomi](xiaomi_ifixit_coverage.json), [Huawei](huawei_ifixit_coverage.json).

These are best-effort source inventories, not exhaustive bills of materials. Counts are textual identification entries, not unique physical chips. Empty arrays indicate no identification extracted in the scan, not an absence of chips. Many guides contain video or unlabeled photos without written chip identifications. Uncertain identifications, source inconsistencies and variant limitations are documented in the datasets.

Xiaomi includes Redmi/POCO and explicitly Xiaomi-labeled ecosystem devices, with attribution caveats. Huawei includes Huawei-era Honor categories; three clearly post-divestment Honor models misplaced in the Huawei hierarchy are excluded and recorded. Five explicit Mi Band image annotations were manually transcribed; this is not a systematic image/OCR inventory.

## Apple dataset notes

`apple_ifixit_chips.json` contains devices, written chip identifications, uncertainty flags and source references. `apple_ifixit_coverage.json` is a smaller coverage index.

Scope: all years, Apple-branded devices, English iFixit categories and teardown / Chip ID guides, plus selected linked articles. Third-party accessories and Beats are excluded. Product-family categories are retained and marked with `category_has_children`.

This is a best-effort text extraction, not an exhaustive bill of materials. Photos were not OCRed; videos, reader comments, PDF-only labels, the full news archive and all replacement guides were not searched. Empty arrays mean no entries extracted in this scan. Identification counts are textual entries rather than unique physical chips: one entry may describe multiple components, stacked chips, or an unnamed device function.

Each entry includes an `identification`, `manufacturers_mentioned`, a `tentative` flag and one or more source references. Manufacturer mentions are not verified manufacturer/foundry fields. False `tentative` means no tentative wording was detected, not independent verification. Part numbers remain in the identification string to avoid guessing how stacked packages and alternate markings should be split.

Sources are attributed to iFixit and the original guide authors/contributors, listed in `source_guides`. Extracted/condensed text follows the source CC BY-NC-SA 3.0 license and source-specific notices: https://creativecommons.org/licenses/by-nc-sa/3.0/ . API reference: https://www.ifixit.com/api-docs .

The source unit can differ from other storage sizes, regions and revisions. A combined-device teardown remains grouped under its source category; identification does not automatically propagate to related models.
