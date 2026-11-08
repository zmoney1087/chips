# Read the chip inventories without reading JSON

## Open the ready-made report — no Python needed

1. Open [device_chip_report.html](device_chip_report.html) on GitHub.
2. Click **Download raw file** (the download icon). GitHub's source view will not run the report.
3. Open the downloaded `.html` file in Chrome, Edge, Firefox, or Safari.
4. Search for a device, select it, and read its chip list.

The report is a single file. It needs no server, installation, account, or internet connection to browse. Datasheet PDFs, iFixit evidence, and search links open external websites and need internet access. If a managed browser blocks local HTML files, use an approved browser or your organization's approved way to open HTML reports.

You can filter by Apple, Xiaomi, or Huawei; search for a chip; show records with no extracted chip list; print the current device view; or save a device's chip list as CSV for Excel or another spreadsheet.

## What the report tells you

- **Device:** the model or category name recorded by iFixit. Some names represent a product family rather than one model. Variant and brand-attribution notes appear when supplied by the inventory.
- **Chip:** the identification from the source. One description can name several chips or a stacked package; the displayed counts are descriptions, not a verified count of physical chips.
- **What it does:** a plain-language explanation based on the teardown wording. This is an interpretation, not a new electrical analysis or a wiring guide.
- **Datasheets:** matching manufacturer-hosted PDFs in the verified catalog, labeled with their part identifiers and check dates.
- **Identification uncertain:** the source uses tentative wording, or the inventory records a dispute. A correct datasheet link does not establish that the chip identification itself is correct.
- **Teardown evidence:** links back to the source steps and source-disagreement notes.

**Important:** a datasheet cannot be supplied reliably for every entry. Many Apple custom chips, Huawei parts, unexplained markings, and unnamed components do not have an established public datasheet in this catalog. Those rows explicitly say **No verified datasheet linked**, with a separate **Search for datasheets** button. Search results are not verified documents. A missing link does not prove no datasheet exists.

The starting catalog contains **125 verified part identifiers**, matching **200 of the 3,381 identification entries** in the current inventories. Each PDF was fetched from a manufacturer's site and checked for its identifier on its first two pages on November 8, 2026. Document revisions, regional devices, ordering suffixes, source errors, and combined entries still require review. Photos, videos, and chips outside the original extraction scope are not made complete by this report.

## Regenerate it with Python

Download the repository with **Code → Download ZIP**, extract it, and open a terminal in the extracted folder. Python 3.9 or newer is required; no third-party packages are needed.

```sh
python build_device_report.py --open
```

On systems where Python is called `python3`, use:

```sh
python3 build_device_report.py --open
```

On Windows, `py build_device_report.py --open` is another option.

The script automatically reads all `*_ifixit_chips.json` inventories beside it, plus `datasheet_catalog.json`, and writes `device_chip_report.html`. It makes **no network requests** and does not change the inventories.

Also export every chip description to one spreadsheet-friendly CSV:

```sh
python build_device_report.py --csv device_chips.csv
```

Or generate a report for one dataset:

```sh
python build_device_report.py xiaomi_ifixit_chips.json --output xiaomi_report.html --open
```

Do not use the coverage-index JSON files as inputs: they contain no chip arrays. If the catalog file is absent, the script still runs and supplies clearly labeled search links only.

## Add verified datasheets

`datasheet_catalog.json` is separate from the inventories. Add an entry keyed by the **exact part identifier** as it appears in a source identification:

```json
{
  "entries": {
    "EXACT-PART-ID": {
      "manufacturer": "Manufacturer name",
      "url": "https://manufacturer.example/actual-datasheet.pdf",
      "checked_on": "YYYY-MM-DD",
      "verification": "Explain how the manufacturer PDF and exact identifier were checked.",
      "kind": "datasheet"
    }
  }
}
```

This is a format example, not a real datasheet. Only add URLs you actually checked. Confirm the document is the manufacturer's datasheet for that identifier, rather than a similar part, reseller listing, marketing page, or merely a URL that responds successfully. Do not relabel a related-part datasheet as the exact chip's document. Keep any required family/ordering-variant caveats in the verification record.

The script matches complete identifiers. For example, `BMA280` will not match `BMA282`, `BMA2800`, or `BMA280A`. It never manufactures a PDF URL from a chip name. Regenerate the HTML after editing the catalog or updating the inventories. Checks are historical records; the script does not recheck live links when it runs.

## Validation

```sh
python -m unittest discover -s tests -v
```

Tests cover exact part matching, uncertainty, unknown-chip fallbacks, empty records, multi-function descriptions, invalid inputs, unsafe source content, spreadsheet formulas, and accidental overwriting of input files. Browser checks were also run for brand/device selection, chip search, the datasheet-only filter, CSV download, disagreement notes, empty search results, and mobile layout.

## Sources and rights

The inventories retain attribution to iFixit and credited contributors under source-specific notices and [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). The report adds explanations and links; it does not redistribute datasheet PDFs. Those PDFs remain hosted by their manufacturers and subject to their own terms.
