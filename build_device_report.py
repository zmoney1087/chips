#!/usr/bin/env python3
"""Turn iFixit chip inventories into a self-contained, human-readable HTML report.

Python 3.9+; standard library only. No network requests are made by this script.
Run next to the JSON inventories: python build_device_report.py --open
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROLE_RULES = [
    (r'battery.*charg|charg.*(?:IC|chip|controller)|battery management|gas gauge|fuel gauge', 'Battery care', 'Charges the battery, tracks its charge, or protects it while charging.'),
    (r'power management|PMIC|\bPMU\b|regulator|DC.?DC|buck|boost converter|power supply|power delivery|load switch|over.?voltage', 'Power control', 'Supplies or controls the electricity that other components need.'),
    (r'\bSDRAM\b|\bDRAM\b|\bSRAM\b|\bRAM\b|LPDDR\w*|DDR\d\w*', 'Working memory', 'Holds information temporarily while the device is running.'),
    (r'NAND|NOR|flash memory|flash storage|\bUFS\b|eMMC|EEPROM|serial flash', 'Storage', 'Keeps files, settings, or software, including when power is off.'),
    (r'audio|codec|microphone|\bADC\b|analog.to.digital', 'Sound or signal conversion', 'Processes sound or converts an electrical signal into digital information.'),
    (r'Wi.?Fi|Bluetooth|\bBLE\b|wireless connectivity|wireless combo', 'Wireless connection', 'Helps the device communicate with nearby wireless devices or networks.'),
    (r'modem|baseband|RF trans|RF receiv|cellular|front.end|power amplifier|antenna switch|antenna tun|envelope track|low.noise amplifier|\bLNA\b', 'Radio connection', 'Helps send, receive, route, or strengthen wireless radio signals.'),
    (r'\bNFC\b', 'Tap-to-connect', 'Supports very short-range communication, such as contactless cards or payments.'),
    (r'security|secure element|secure micro|encryption|secure enclave', 'Security', 'Helps protect sensitive information or carry out secure operations.'),
    (r'\bGPU\b|graphics processor|graphics chipset|GeForce|Radeon', 'Graphics', 'Helps draw images, video, games, and the screen interface.'),
    (r'processor|\bCPU\b|system.on.(?:a.)?chip|\bSoC\b|\bMCU\b|microcontroller|\bFPGA\b|Kirin|Snapdragon', 'Processing or control', 'Runs software or controls one part of the device; some chips combine several jobs.'),
    (r'accelerometer|gyroscope|inertial|\bIMU\b', 'Movement sensing', 'Detects movement, tilt, or rotation.'),
    (r'baromet|pressure sensor', 'Air-pressure sensing', 'Measures air pressure, which can help estimate changes in height.'),
    (r'magnetometer|compass|hall sensor', 'Magnetic sensing', 'Detects magnetic fields, direction, or the position of a nearby magnet.'),
    (r'GPS|GNSS|GLONASS|BeiDou|Galileo', 'Location', 'Helps work out the device’s position using satellite signals.'),
    (r'touchscreen|touch.screen|touch controller|capaciti.*sensor|fingerprint|biometric', 'Touch or fingerprint sensing', 'Detects touch input or reads a fingerprint, depending on the named component.'),
    (r'temperature sensor|thermal sensor', 'Temperature sensing', 'Measures temperature so the device can monitor its operating conditions.'),
    (r'camera|image sensor|image signal|\bISP\b|CMOS|\bIMX\d', 'Camera', 'Captures light or helps process information from a camera.'),
    (r'haptic|taptic|vibrat', 'Vibration feedback', 'Controls the small vibrations you feel when interacting with the device.'),
    (r'display|LCD|OLED|backlight|LED driver|timing controller', 'Screen or lights', 'Helps control a screen, its backlight, or indicator lights.'),
    (r'USB|Thunderbolt|PCIe|ethernet|card reader|I/O expander|interface|port multiplex', 'Wired connections', 'Helps data or signals move between components, ports, or accessories.'),
    (r'oscillator|clock generator|real.time clock', 'Timing', 'Provides a timing signal or keeps track of time.'),
    (r'MOSFET|transistor|rectifier|diode', 'Electrical switching', 'Switches, directs, or controls the flow of electricity.'),
]
ROLE_PATTERNS = [(re.compile(pattern, re.I), label, text) for pattern, label, text in ROLE_RULES]


def safe_url(value: object) -> str | None:
    """Keep external URLs inert unless they are ordinary HTTPS/HTTP links."""
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
            return None
        return value
    except ValueError:
        return None


def describe_role(identification: str) -> list[dict[str, str]]:
    roles = [{'label': label, 'explanation': text} for pattern, label, text in ROLE_PATTERNS if pattern.search(identification)]
    return roles[:5] or [{'label': 'Job not clearly stated', 'explanation': 'The source does not provide enough information to explain this component’s job reliably.'}]


def load_catalog(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding='utf-8'))
    entries = raw.get('entries')
    if not isinstance(entries, dict):
        raise ValueError(f'{path}: expected an entries object')
    result = {}
    for part, entry in entries.items():
        if not isinstance(part, str) or not part or not isinstance(entry, dict):
            raise ValueError(f'{path}: invalid datasheet entry')
        url = safe_url(entry.get('url'))
        if not url:
            raise ValueError(f'{path}: invalid datasheet URL for {part}')
        # A catalog entry requires its verification record, not just a guessed URL.
        if not entry.get('checked_on') or not entry.get('verification'):
            raise ValueError(f'{path}: {part} is missing its verification record')
        result[part] = {**entry, 'url': url}
    return result


def find_datasheets(identification: str, catalog: dict[str, dict]) -> list[dict]:
    matches = []
    for part, entry in catalog.items():
        # Exact identifiers only: BMA280 must not silently match BMA282 or BMA2800.
        if re.search(r'(?<![A-Za-z0-9])' + re.escape(part) + r'(?![A-Za-z0-9])', identification, re.I):
            matches.append({'part': part, **entry})
    return matches


def build_report(paths: list[Path], catalog: dict[str, dict]) -> dict:
    devices = []
    dataset_notes = []
    seen = set()
    for path in paths:
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or not isinstance(raw.get('devices'), list):
            raise ValueError(f'{path}: expected a chip inventory with a devices array')
        # Reject coverage indexes, which otherwise look like empty chip inventories.
        if raw['devices'] and any(not isinstance(d, dict) or not isinstance(d.get('chips'), list) for d in raw['devices']):
            raise ValueError(f'{path}: every device needs a chips array; coverage indexes are not chip inventories')
        metadata = raw.get('metadata', {})
        brand = metadata.get('brand') or path.name.split('_')[0].title()
        dataset_notes.append({'brand': brand, 'file': path.name, 'scope': metadata.get('scope', ''), 'attribution': metadata.get('attribution', {})})
        guides = {g['guide_id']: g for g in raw.get('source_guides', []) if isinstance(g, dict) and 'guide_id' in g}
        for d in raw['devices']:
            if not isinstance(d.get('name'), str):
                raise ValueError(f'{path}: device name must be text')
            key = (brand, d['name'])
            if key in seen:
                raise ValueError(f'{path}: duplicate device/category record: {brand} / {d["name"]}')
            seen.add(key)
            chips = []
            for chip in d['chips']:
                if not isinstance(chip, dict) or not isinstance(chip.get('identification'), str):
                    raise ValueError(f'{path}: chip identification must be text')
                identification = chip['identification']
                mentions = chip.get('manufacturers_mentioned', [])
                if not isinstance(mentions, list):
                    mentions = []
                # Older extraction data includes the ordinary word "on" as a false manufacturer.
                manufacturers = list(dict.fromkeys(m for m in mentions if isinstance(m, str) and m.lower() != 'on'))
                refs = []
                for src in chip.get('sources', []):
                    if not isinstance(src, dict):
                        continue
                    url = safe_url(src.get('url'))
                    if url and url not in [ref['url'] for ref in refs]:
                        guide = guides.get(src.get('guide_id'), {})
                        title = guide.get('title', 'iFixit source')
                        step = f' · step {src["step_number"]}' if src.get('step_number') else ''
                        method = src.get('extraction_method', 'article_text' if src.get('source_type') == 'article' else 'guide_text')
                        refs.append({'url': url, 'label': title + step,
                                     'extraction_method': method,
                                     'image_url': safe_url(src.get('image_url')),
                                     'guide_id': src.get('guide_id'), 'step_id': src.get('step_id'),
                                     'revision_id': guide.get('revision_id'), 'author': guide.get('author')})
                notes = chip.get('source_notes', [])
                if isinstance(notes, str):
                    notes = [notes]
                notes = [n for n in notes if isinstance(n, str)] if isinstance(notes, list) else []
                uncertain = bool(chip.get('tentative')) or bool(re.search(r'likely|possibly|probably|suspect|unconfirmed|disputed|unknown|[?]', identification, re.I))
                chips.append({'identification': identification, 'manufacturers': manufacturers,
                              'roles': describe_role(identification), 'tentative': uncertain,
                              'verification_status': 'not_independently_verified',
                              'source_uncertainty': 'flagged' if uncertain else 'not_flagged',
                              'datasheets': find_datasheets(identification, catalog),
                              'search_url': 'https://www.google.com/search?' + urlencode({'q': identification + ' datasheet'}),
                              'sources': refs, 'notes': notes})
            guide_links = []
            for gid in d.get('reviewed_guide_ids', []):
                guide = guides.get(gid, {})
                url = safe_url(guide.get('url'))
                if url:
                    guide_links.append({'url': url, 'label': guide.get('title', 'iFixit guide')})
            devices.append({'id': brand + '::' + d['name'], 'name': d['name'], 'brand': brand, 'chips': chips,
                            'dataset_file': path.name,
                            'url': safe_url(d.get('ifixit_device_url')), 'note': d.get('brand_attribution_note') or '',
                            'has_children': bool(d.get('category_has_children')), 'guides': guide_links,
                            'coverage_status': d.get('coverage_status', '')})
    devices.sort(key=lambda d: (d['brand'].casefold(), d['name'].casefold()))
    return {'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'devices': devices, 'datasets': dataset_notes,
            'stats': {'records': len(devices), 'with_chips': sum(bool(d['chips']) for d in devices),
                      'entries': sum(len(d['chips']) for d in devices),
                      'with_datasheets': sum(bool(c['datasheets']) for d in devices for c in d['chips']),
                      'catalog_parts': len(catalog)}}


def csv_cell(value: str) -> str:
    return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


def write_csv(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Brand', 'Device', 'Chip identification', 'What it does', 'Source uncertainty flag', 'Project verification status', 'Verified datasheets', 'Datasheet search (not verified)', 'iFixit evidence', 'Extraction methods', 'Image evidence', 'Source notes'])
        for d in report['devices']:
            for c in d['chips']:
                row = [d['brand'], d['name'], c['identification'], ' / '.join(r['explanation'] for r in c['roles']),
                       'Uncertainty flagged' if c['tentative'] else 'No uncertainty flag found; not verification',
                       'Not independently verified by this project',
                       ' | '.join(x['part'] + ': ' + x['url'] for x in c['datasheets']), c['search_url'],
                       ' | '.join(x['url'] for x in c['sources']),
                       ' | '.join(dict.fromkeys(x['extraction_method'] for x in c['sources'])),
                       ' | '.join(x['image_url'] for x in c['sources'] if x['image_url']), ' | '.join(c['notes'])]
                writer.writerow([csv_cell(value) for value in row])


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inside your devices — chip guide</title>
<style>
:root{color-scheme:light;--ink:#172b39;--muted:#536572;--paper:#f5f7f8;--line:#d8e1e5;--teal:#006d77;--soft:#e5f2f1;--warn:#805000}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}button,input,select{font:inherit}button,a,input,select{outline-offset:4px}a{color:var(--teal)}header{padding:30px 34px;background:#fff;border-bottom:1px solid var(--line)}h1{font-size:30px;letter-spacing:-1px;margin:0 0 6px}header p{margin:0;max-width:1000px;color:var(--muted)}.eyebrow{font-size:12px;letter-spacing:1.6px;font-weight:800;text-transform:uppercase;color:var(--teal)}.stats{display:flex;gap:26px;flex-wrap:wrap;margin-top:20px}.stats strong{font-size:23px;display:block}.stats span{font-size:13px;color:var(--muted)}.layout{display:grid;grid-template-columns:310px minmax(0,1fr);max-width:1600px;margin:auto}aside{padding:24px 18px;border-right:1px solid var(--line);height:calc(100vh - 20px);position:sticky;top:0;display:flex;flex-direction:column;gap:12px}label{font-size:13px;font-weight:700}.control{display:block;width:100%;padding:11px;border:1px solid #a8b9c3;border-radius:8px;background:white;color:var(--ink)}.check{display:flex;align-items:center;gap:9px;font-weight:500;font-size:14px}.check input{width:18px;height:18px;flex-shrink:0}.list{overflow:auto;flex:1;min-height:150px}.device-button{width:100%;border:0;border-bottom:1px solid var(--line);text-align:left;padding:12px;background:transparent;color:var(--ink);cursor:pointer;border-radius:6px}.device-button:hover{background:#eaf0f2}.device-button[aria-current=true]{background:var(--soft);box-shadow:inset 3px 0 var(--teal)}.device-button span{display:block;font-size:12px;color:var(--muted)}main{min-width:0;padding:30px}.device-heading{margin:0;font-size:28px;line-height:1.2;overflow-wrap:anywhere}.muted{color:var(--muted)}.small{font-size:13px}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:18px 0}.toolbar .control{width:min(100%,330px)}.button{background:white;color:var(--teal);border:1px solid #a5c8c9;border-radius:7px;padding:8px 12px;cursor:pointer;text-decoration:none;display:inline-block;font-size:13px;font-weight:600}.button:hover{background:var(--soft)}.notice{background:white;border:1px solid var(--line);border-left:4px solid #a8bec7;padding:14px 18px;border-radius:8px;margin:18px 0;font-size:14px}.chip-list{display:grid;gap:16px}.chip{border:1px solid var(--line);border-radius:12px;background:white;overflow:hidden}.chip-head{padding:18px 20px 10px}.chip h3{font-size:17px;line-height:1.5;margin:0;overflow-wrap:anywhere}.badge{display:inline-block;border-radius:5px;padding:2px 7px;background:var(--soft);color:var(--teal);font-size:11px;font-weight:700;margin:8px 5px 0 0}.badge.warn{background:#fff1d6;color:var(--warn)}.badge.neutral{background:#edf1f4;color:#536572}.provenance{padding:12px 20px;background:#f7fafb;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.source-row{margin-top:7px;display:flex;flex-direction:column;align-items:flex-start;overflow-wrap:anywhere}.chip-body{padding:0 20px 18px;display:grid;grid-template-columns:minmax(0,1fr) minmax(250px,1fr);gap:24px}.chip-body h4{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin:12px 0 8px}.role{font-size:14px;margin:7px 0}.role b{font-weight:650}.docs{display:flex;flex-direction:column;align-items:flex-start;gap:8px}.doc-note{font-size:12px;color:var(--muted)}details{border-top:1px solid var(--line);padding:10px 20px;font-size:13px}summary{cursor:pointer;font-weight:600}.sources a{display:block;padding:4px 0;overflow-wrap:anywhere}.empty{padding:30px;background:#fff;border:1px solid var(--line);border-radius:10px}.footer{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding:24px 34px}#list-count,#chip-count{min-height:20px}.no-script{margin:20px;padding:20px;border:2px solid #805000}body:has(#device:empty) #device{min-height:300px}@media(max-width:850px){header,main{padding:20px}.layout{grid-template-columns:1fr}aside{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:18px}.list{max-height:230px}.chip-body{grid-template-columns:1fr;gap:5px}.stats{gap:18px}.device-heading{font-size:25px}}@media print{aside,.toolbar,header,.footer{display:none!important}.layout{display:block}main{padding:0}.chip{break-inside:avoid}.chip-list{display:block}.chip{margin-bottom:15px}details{display:none}.button{border:0;padding:0}a:after{content:" (" attr(href) ")";font-size:9px;overflow-wrap:anywhere}.chip-body{grid-template-columns:1fr}.notice{border:1px solid #999}body{background:white}}
</style></head><body>
<header><div class="eyebrow">A plain-language guide to your electronics</div><h1>Inside your devices</h1><p>Choose a device to see the chips identified in its teardown, what their descriptions mean, and links to available datasheets.</p><div class="notice">The links show the original iFixit evidence. Chip identities have not been independently verified by this project. Uncertainty flags describe source wording or extraction notes, not a confidence ranking. Checking a datasheet PDF is a separate document check.</div><div class="stats" id="stats"></div></header>
<noscript><div class="no-script">This report uses local JavaScript for browsing and filtering. Enable JavaScript, or generate the CSV with <code>python build_device_report.py --csv chips.csv</code> and open it in a spreadsheet.</div></noscript>
<div class="layout"><aside aria-label="Choose a device"><label for="search">Find a device or chip</label><input id="search" class="control" type="search" placeholder="e.g. iPhone 13, TPS62743…"><label for="brand">Brand</label><select id="brand" class="control"><option value="">All brands</option></select><label class="check"><input id="show-empty" type="checkbox">Include records without chip lists</label><div id="list-count" class="muted small" role="status"></div><nav id="device-list" class="list" aria-label="Device records"></nav></aside><main><section id="device" aria-label="Selected device"></section></main></div>
<footer class="footer"><b>About this report.</b> These are source-linked identification entries, not a complete list of every chip physically inside each device. One entry may describe several chips, a stacked package, a sensor, or a module. Device variants may differ. Datasheet links describe the named part; they do not prove the part is present in the device. Plain-language roles are inferred from the wording of each identification. A missing document means no verified link is in this catalog, not that no datasheet exists. Custom parts may have no public datasheet. <p>Data: iFixit and its credited authors/contributors, under source-specific notices and <a href="https://creativecommons.org/licenses/by-nc-sa/3.0/" target="_blank" rel="noopener noreferrer">CC BY-NC-SA 3.0</a>. This report adds explanations, filtering, and a manufacturer datasheet catalog; source text and uncertainty are retained. Document links require internet access; browsing the report itself works offline.</p><span id="generated"></span></footer>
<script type="application/json" id="report-data">__REPORT_DATA__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('report-data').textContent);
if(DATA.source_records){for(const d of DATA.devices){d.id=d.id||d.brand+'::'+d.name;for(const c of d.chips){c.sources=c.sources.map(index=>DATA.source_records[index]);if(DATA.role_records)c.roles=c.roles.map(index=>DATA.role_records[index]);c.datasheets=c.datasheets||[];if(DATA.datasheet_records)c.datasheets=c.datasheets.map(index=>DATA.datasheet_records[index]);c.manufacturers=c.manufacturers||[];c.notes=c.notes||[];c.tentative=!!c.tentative;c.search_url=c.search_url||'https://www.google.com/search?q='+encodeURIComponent(c.identification+' datasheet');c.verification_status='not_independently_verified';c.source_uncertainty=c.tentative?'flagged':'not_flagged';}}}
const $=id=>document.getElementById(id);
let selected=null;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const link=(text,url,cls='')=>{const a=el('a',text,cls);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;};
function chipText(c){return [c.identification,...c.manufacturers,...c.roles.map(r=>r.label)].join(' ').toLowerCase();}
function deviceMatches(d){const q=$('search').value.trim().toLowerCase();return (!$('brand').value||d.brand===$('brand').value)&&($('show-empty').checked||d.chips.length)&&(!q||d.name.toLowerCase().includes(q)||d.chips.some(c=>chipText(c).includes(q)));}
function choose(d){selected=d;history.replaceState(null,'','#'+encodeURIComponent(d.id));renderList();renderDevice();if(window.innerWidth>850){window.scrollTo(0,0);}else{$('device').scrollIntoView({block:'start'});}}
function renderList(){const list=$('device-list');list.replaceChildren();const visible=DATA.devices.filter(deviceMatches);$('list-count').textContent=visible.length.toLocaleString()+' device/category records';for(const d of visible){const b=el('button',undefined,'device-button');b.type='button';b.setAttribute('aria-current',String(selected?.id===d.id));b.append(el('strong',d.name),el('span',d.brand+' · '+(d.chips.length?d.chips.length+' chip entries':'No chip list extracted')));b.addEventListener('click',()=>choose(d));list.append(b);}if(!visible.length)list.append(el('p','No matching records. Try another search or include records without chip lists.','muted small'));}
function filterChanged(){const visible=DATA.devices.filter(deviceMatches);if(!selected||!visible.some(d=>d.id===selected.id)){selected=visible[0]||null;renderDevice();}renderList();}
function methodLabel(method){return ({guide_text:'Written teardown / chip guide',article_text:'Written iFixit article',manual_transcription_of_source_image_annotation:'Transcribed label from an annotated source image'})[method]||method||'Extraction method not recorded';}
function makeChip(c){
 const card=el('article',undefined,'chip');const top=el('div',undefined,'chip-head');top.append(el('h3',c.identification));
 if(c.manufacturers.length)top.append(el('div','Recorded manufacturer names: '+c.manufacturers.join(', '),'muted small'));
 top.append(el('span','Not independently verified by this project','badge neutral'));
 top.append(el('span',c.tentative?'Uncertainty flagged in source / extraction':'No uncertainty flag recorded — not a confirmation',c.tentative?'badge warn':'badge neutral'));
 if(c.notes.length)top.append(el('span','Source disagreement / note','badge warn'));card.append(top);
 const evidence=el('div',undefined,'provenance');evidence.append(el('b','Where this identification came from','small'));
 if(c.sources.length){for(const ref of c.sources){const row=el('div',undefined,'source-row');row.append(link(ref.label,ref.url),el('span',methodLabel(ref.extraction_method),'doc-note'));if(ref.image_url)row.append(link('View the annotated source image',ref.image_url,'small'));evidence.append(row);}}
 else evidence.append(el('p','No source URL supplied in this record. This identification needs a traceable source.','small'));
 card.append(evidence);
 const body=el('div',undefined,'chip-body');const roles=el('div');roles.append(el('h4','What the description means'));
 for(const r of c.roles){const paragraph=el('p',undefined,'role');paragraph.append(el('b',r.label+'. '),document.createTextNode(r.explanation));roles.append(paragraph);}
 const docs=el('div');docs.append(el('h4','Datasheets'));const links=el('div',undefined,'docs');
 if(c.datasheets.length){for(const doc of c.datasheets){links.append(link(doc.part+' · manufacturer PDF',doc.url,'button'),el('span',doc.manufacturer+' · PDF checked '+doc.checked_on,'doc-note'));}
 links.append(el('span','Document check only: this does not verify that the part is in this device. Combined entries may contain other components.','doc-note'));}
 else links.append(el('p','No verified datasheet linked.','muted small'));
 links.append(link('Search for datasheets',c.search_url,'button'),el('span','Search results are not verified datasheets.','doc-note'));docs.append(links);body.append(roles,docs);card.append(body);
 const detail=el('details');detail.append(el('summary','Source details and identification notes'));const refs=el('div',undefined,'sources');
 refs.append(el('p','Independent hardware verification has not been recorded by this project. The source may have been reviewed by its authors; that is separate from independent confirmation here.'));
 for(const ref of c.sources){if(ref.author)refs.append(el('p','Source author: '+ref.author));if(ref.revision_id)refs.append(el('p','Source guide revision: '+ref.revision_id,'muted small'));}
 for(const note of c.notes)refs.append(el('p',note,'notice'));detail.append(refs);card.append(detail);return card;
}
function renderDevice(){const root=$('device');root.replaceChildren();if(!selected){root.append(el('div','Choose a device, or change the filters to see matching records.','empty'));return;}const d=selected;root.append(el('div',d.brand,'eyebrow'),el('h2',d.name,'device-heading'),el('p',d.chips.length?d.chips.length+' identification entries from the source inventory.':'No chip identifications were extracted for this record.','muted'));if(d.url)root.append(link('View device on iFixit',d.url,'small'));root.append(el('p','Source inventory: '+d.dataset_file,'muted small'));if(d.note)root.append(el('p',d.note,'notice'));if(d.has_children)root.append(el('p','iFixit lists subcategories under this record. It may represent a family or several related variants.','notice'));if(!d.chips.length){const box=el('div',undefined,'empty');box.append(el('h3','This is a coverage gap, not an empty device.'),el('p',d.guides.length?'The reviewed guides did not yield chip identifications. They may contain video, unlabeled images, or disassembly instructions only.':'No relevant teardown or chip-identification guide was discovered in the scan.'));for(const g of d.guides)box.append(link(g.label+'',g.url,'sources'));root.append(box);return;}
const toolbar=el('div',undefined,'toolbar');const q=el('input',undefined,'control');q.type='search';q.placeholder='Search chips in this device…';q.setAttribute('aria-label','Search chips in selected device');const label=el('label',undefined,'check');const verified=el('input');verified.type='checkbox';label.append(verified,document.createTextNode('With linked datasheets only'));const save=el('button','Save this device as CSV','button');save.type='button';save.addEventListener('click',()=>downloadDevice(d));const print=el('button','Print this view','button');print.type='button';print.addEventListener('click',()=>window.print());toolbar.append(q,label,save,print);root.append(toolbar);const count=el('p',undefined,'muted small');count.id='chip-count';count.setAttribute('role','status');const chips=el('div',undefined,'chip-list');root.append(count,chips);function draw(){const query=q.value.trim().toLowerCase();const filtered=d.chips.filter(c=>(!query||chipText(c).includes(query))&&(!verified.checked||c.datasheets.length));count.textContent=filtered.length+' of '+d.chips.length+' entries shown';chips.replaceChildren(...filtered.map(makeChip));if(!filtered.length)chips.append(el('div','No entries match these chip filters.','empty'));}q.addEventListener('input',draw);verified.addEventListener('change',draw);draw();}
function csvCell(value){let s=String(value??'');if(/^[=+\-@\t\r\n]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
function downloadDevice(d){const rows=[['Brand','Device','Chip identification','What it does','Source uncertainty flag','Project verification status','Verified datasheets','Datasheet search (not verified)','iFixit evidence','Extraction methods','Image evidence','Source notes'],...d.chips.map(c=>[d.brand,d.name,c.identification,c.roles.map(r=>r.explanation).join(' / '),c.tentative?'Uncertainty flagged':'No uncertainty flag found; not verification','Not independently verified by this project',c.datasheets.map(x=>x.part+': '+x.url).join(' | '),c.search_url,c.sources.map(s=>s.url).join(' | '),[...new Set(c.sources.map(s=>s.extraction_method))].join(' | '),c.sources.filter(s=>s.image_url).map(s=>s.image_url).join(' | '),c.notes.join(' | ')])];const blob=new Blob(['\ufeff'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8;'});const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download=(d.brand+'_'+d.name).replace(/[^a-z0-9_-]/gi,'_')+'_chips.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
for(const brand of [...new Set(DATA.devices.map(d=>d.brand))].sort()){const option=el('option',brand);option.value=brand;$('brand').append(option);}
for(const [value,label] of [[DATA.stats.with_chips,'records with chip lists'],[DATA.stats.entries,'identification entries'],[DATA.stats.with_datasheets,'entries with linked datasheets']]){const box=el('div');box.append(el('strong',value.toLocaleString()),el('span',label));$('stats').append(box);}
$('generated').textContent='Generated '+new Date(DATA.generated_at).toLocaleString()+'.';
function fromHash(){try{const id=decodeURIComponent(location.hash.slice(1));return DATA.devices.find(d=>d.id===id);}catch{return null;}}
selected=fromHash()||DATA.devices.find(d=>d.chips.length)||null;if(selected&&!selected.chips.length)$('show-empty').checked=true;
$('search').addEventListener('input',filterChanged);$('brand').addEventListener('change',filterChanged);$('show-empty').addEventListener('change',filterChanged);window.addEventListener('hashchange',()=>{const d=fromHash();if(d){selected=d;renderList();renderDevice();}});renderList();renderDevice();
</script></body></html>'''


def pack_report(report: dict) -> dict:
    """Deduplicate repeated citations, explanations and documents for offline HTML."""
    packed = {**report, 'devices': [], 'source_records': [], 'role_records': [], 'datasheet_records': []}
    indexes = {name: {} for name in ('source_records', 'role_records', 'datasheet_records')}

    def reference(table: str, value: dict) -> int:
        key = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if key not in indexes[table]:
            indexes[table][key] = len(packed[table])
            packed[table].append(value)
        return indexes[table][key]

    for device in report['devices']:
        chips = []
        for chip in device['chips']:
            item = {
                'identification': chip['identification'],
                'sources': [reference('source_records', source) for source in chip['sources']],
                'roles': [reference('role_records', role) for role in chip['roles']],
            }
            if chip['manufacturers']:
                item['manufacturers'] = chip['manufacturers']
            if chip['tentative']:
                item['tentative'] = True
            if chip['notes']:
                item['notes'] = chip['notes']
            if chip['datasheets']:
                item['datasheets'] = [reference('datasheet_records', doc) for doc in chip['datasheets']]
            chips.append(item)
        packed['devices'].append({**{k: v for k, v in device.items() if k not in ('id', 'coverage_status')}, 'chips': chips})
    return packed


def write_html(path: Path, report: dict) -> None:
    # Escape script-closing tags and JS line separators in untrusted source text.
    payload = json.dumps(pack_report(report), ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    page = HTML_TEMPLATE.replace('__REPORT_DATA__', payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inputs', type=Path, nargs='*', help='Chip inventory JSON files; defaults to *_ifixit_chips.json beside this script')
    parser.add_argument('--catalog', type=Path, default=here / 'datasheet_catalog.json', help='Verified datasheet catalog JSON')
    parser.add_argument('--output', '-o', type=Path, default=here / 'device_chip_report.html', help='Output HTML file')
    parser.add_argument('--csv', type=Path, help='Also export all entries as a spreadsheet-friendly CSV')
    parser.add_argument('--open', action='store_true', help='Open the generated HTML in your default browser')
    args = parser.parse_args(argv)
    paths = args.inputs or sorted(here.glob('*_ifixit_chips.json'))
    if not paths:
        parser.error('No inventories found. Put the *_ifixit_chips.json files beside this script or pass their paths.')
    outputs = [args.output] + ([args.csv] if args.csv else [])
    protected = {p.resolve() for p in paths} | {args.catalog.resolve()}
    if any(p.resolve() in protected for p in outputs) or len({p.resolve() for p in outputs}) != len(outputs):
        parser.error('Output paths must be different from inputs, the catalog, and each other.')
    try:
        catalog = load_catalog(args.catalog)
        report = build_report(paths, catalog)
        write_html(args.output, report)
        if args.csv:
            write_csv(args.csv, report)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    print(f'Created {args.output.resolve()}')
    print(f'{report["stats"]["with_chips"]} records with chip lists; {report["stats"]["entries"]} identification entries; {report["stats"]["with_datasheets"]} entries with verified datasheet links.')
    if not catalog:
        print('No datasheet catalog loaded; the report contains clearly labeled datasheet search links only.', file=sys.stderr)
    if args.csv:
        print(f'Created {args.csv.resolve()}')
    if args.open:
        webbrowser.open(args.output.resolve().as_uri())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
