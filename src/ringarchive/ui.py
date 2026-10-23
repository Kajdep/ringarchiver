"""
python -m ringarchive.ui
Flask UI: unified event+clip view, video viewer, export to disk/Dropbox/Drive.
"""
from __future__ import annotations
import os, logging
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
from flask import Flask, jsonify, render_template_string
import boto3
from .state import list_recent
from .ring_client import RingClient

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
BUCKET = os.environ.get("ARCHIVE_BUCKET", "")
REGION = os.environ.get("AWS_REGION", "eu-west-2")

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RingArchive</title>
<style>
:root{--bg:#0f1117;--card:#1a1d27;--accent:#ff6b35;--text:#e8eaf0;--sub:#8b8fa8;--border:#2a2d3a;--purple:#ce93d8;--green:#6fcf97}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;padding:24px;max-width:1140px;margin:auto}
h1{font-size:1.4rem;font-weight:700;margin-bottom:4px}h1 span{color:var(--accent)}
.sub{color:var(--sub);font-size:.85rem;margin-bottom:20px}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.card{background:var(--card);border-radius:10px;padding:14px 18px;flex:1;min-width:120px}
.card .num{font-size:1.9rem;font-weight:700;color:var(--accent)}.card .lbl{font-size:.78rem;color:var(--sub);margin-top:2px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
button{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:8px 15px;font-size:.84rem;cursor:pointer;font-weight:600;white-space:nowrap}
button:hover{opacity:.85}button:disabled{opacity:.4;cursor:default}
button.sec{background:#2a2d3a;color:var(--text)}button.sec:hover{background:#353848}
select{background:#1a1d27;color:var(--text);border:1px solid var(--border);border-radius:8px;padding:7px 12px;font-size:.84rem;cursor:pointer;outline:none}
select:focus{border-color:var(--accent)}
#status{font-size:.81rem;color:var(--sub);min-height:16px;margin-bottom:10px}
.sec-title{font-size:.88rem;font-weight:600;color:var(--sub);margin:18px 0 8px;text-transform:uppercase;letter-spacing:.05em}
.filter-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px;font-size:.82rem;color:var(--sub)}
/* unified event+clip table */
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{text-align:left;color:var(--sub);padding:7px 10px;border-bottom:1px solid var(--border)}
td{padding:8px 10px;border-bottom:1px solid #1e2130;vertical-align:middle}
tr.clickable{cursor:pointer}tr.clickable:hover td{background:#1e2130}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:600}
.b-dev{background:#2a1a30;color:var(--purple)}
.b-archived{background:#1b3a1e;color:var(--green)}
.b-event{background:#1a2030;color:#90caf9}
.b-type{background:#2a2010;color:#ffa726}
.clip-name{color:var(--accent);text-decoration:underline;font-size:.81rem;word-break:break-all}
input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:var(--accent)}
/* bulk bar */
#bulk-bar{display:none;background:#1e2538;border-radius:8px;padding:9px 14px;margin-bottom:10px;align-items:center;gap:8px;flex-wrap:wrap;font-size:.83rem}
#bulk-bar.show{display:flex}#bulk-count{color:var(--accent);font-weight:700}
/* tiny buttons */
button.t{font-size:.73rem;padding:4px 9px;border-radius:6px}
button.dl{background:#1a2a1a;color:var(--green)}
button.db{background:#1a2050;color:#90caf9}
button.gd{background:#2a1a10;color:#ffa726}
/* modal */
#mbg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.87);z-index:200;align-items:center;justify-content:center}
#mbg.open{display:flex}
#modal{background:var(--card);border-radius:12px;padding:22px;max-width:860px;width:95%;position:relative;max-height:90vh;overflow-y:auto}
#mcls{position:absolute;top:12px;right:14px;background:none;border:none;color:var(--sub);font-size:1.5rem;cursor:pointer;line-height:1}
#mtitle{font-size:.9rem;font-weight:600;margin-bottom:3px;word-break:break-all}
#mmeta{font-size:.78rem;color:var(--sub);margin-bottom:12px;display:flex;gap:10px;flex-wrap:wrap}
#mvid{width:100%;border-radius:8px;background:#000;max-height:440px}
#mnoclip{color:var(--sub);font-size:.84rem;padding:18px 0;text-align:center;line-height:1.7;display:none}
.mexp{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
</head>
<body>
<h1>Ring<span>Archive</span></h1>
<p class="sub">Personal Ring clip backup &mdash; eu-west-2</p>

<div class="row">
  <div class="card"><div class="num" id="c-total">-</div><div class="lbl">Total events</div></div>
  <div class="card"><div class="num" id="c-arch">-</div><div class="lbl">Archived to S3</div></div>
  <div class="card"><div class="num" id="c-dev">-</div><div class="lbl">Devices</div></div>
  <div class="card"><div class="num" id="c-sel">0</div><div class="lbl">Selected</div></div>
</div>

<div class="toolbar">
  <button id="run-btn" onclick="runArchive()">&#9654; Run archive now</button>
  <button class="sec" onclick="load()">&#8635; Refresh</button>
</div>
<div id="status"></div>

<div id="bulk-bar">
  <span><span id="bulk-count">0</span> selected</span>
  <button class="t dl" onclick="bExp('download')">&#8681; Download all</button>
  <button class="t db" onclick="bExp('dropbox')">Dropbox all</button>
  <button class="t gd" onclick="bExp('gdrive')">Drive all</button>
  <button class="sec t" onclick="clrSel()">Clear</button>
</div>

<div class="sec-title">Events &amp; clips</div>
<div class="filter-row">
  Filter:
  <select id="f-dev" onchange="applyFilter()"><option value="">All devices</option></select>
  <select id="f-type" onchange="applyFilter()"><option value="">All types</option></select>
  <select id="f-status" onchange="applyFilter()">
    <option value="">All statuses</option>
    <option value="archived">Archived</option>
    <option value="event">Event only</option>
  </select>
  <span id="f-count" style="color:var(--sub)"></span>
</div>

<table>
  <thead><tr>
    <th><input type="checkbox" id="chk-all" onchange="togAll(this)"></th>
    <th>Name / ID</th><th>Device</th><th>Type</th><th>Time</th><th>Status</th><th>Actions</th>
  </tr></thead>
  <tbody id="tbody"><tr><td colspan="7" style="color:var(--sub);padding:14px">Loading&hellip;</td></tr></tbody>
</table>

<!-- Modal -->
<div id="mbg" onclick="closeMod(event)">
 <div id="modal">
  <button id="mcls" onclick="closeMod()">&times;</button>
  <div id="mtitle"></div>
  <div id="mmeta"></div>
  <video id="mvid" controls preload="metadata"></video>
  <div id="mnoclip">
    Video not available from the Playground simulator.<br>
    The Ring Playground returns event metadata but does not serve MP4 files.<br>
    Clips download automatically when using a real Ring device.
  </div>
  <div class="mexp">
    <button class="t dl" onclick="mExp('download')">&#8681; Save to disk</button>
    <button class="t db" onclick="mExp('dropbox')">Save to Dropbox</button>
    <button class="t gd" onclick="mExp('gdrive')">Save to Google Drive</button>
  </div>
 </div>
</div>

<script>
let rows=[], devNames={}, cur=null;

function devN(id){if(!id)return'Unknown';return devNames[id]||('…'+id.slice(-8));}
function fname(k){if(!k)return'';return k.split('/').pop();}
function ts(ms){if(!ms)return'—';return new Date(ms).toLocaleString();}

async function load(){
  const [evR,clR,dvR]=await Promise.all([fetch('/api/events'),fetch('/api/clips'),fetch('/api/devices')]);
  const evs=await evR.json(), cls=await clR.json(), dvs=await dvR.json();
  devNames={};
  if(Array.isArray(dvs)) dvs.forEach(d=>devNames[d.id]=d.name);

  // Build unified row list: start from events, enrich with clip data if archived
  const clipMap={};
  if(Array.isArray(cls)) cls.forEach(c=>{ clipMap[c.event_id]=c; });

  rows=[];
  if(Array.isArray(evs)) evs.forEach(e=>{
    const clip=clipMap[e.id];
    rows.push({
      id: e.id,
      device_id: e.device_id,
      event_type: e.event_type,
      start: e.start,
      archived: !!clip,
      s3_key: clip?.s3_key||null,
      url: clip?.url||null,
      summary: clip?.summary||null,
      archived_at: clip?.archived_at||null,
    });
    if(clip) delete clipMap[e.id];
  });
  // Add archived clips that have no matching live event
  Object.values(clipMap).forEach(c=>{
    rows.push({
      id: c.event_id,
      device_id: c.device_id,
      event_type: c.event_type||'on_demand',
      start: null,
      archived: true,
      s3_key: c.s3_key,
      url: c.url||null,
      summary: c.summary||null,
      archived_at: c.archived_at||null,
    });
  });

  // Stats
  document.getElementById('c-total').textContent=rows.length;
  document.getElementById('c-arch').textContent=rows.filter(r=>r.archived).length;
  document.getElementById('c-dev').textContent=Object.keys(devNames).length||new Set(rows.map(r=>r.device_id)).size;

  // Populate filter dropdowns
  populateFilter('f-dev', [...new Set(rows.map(r=>r.device_id).filter(Boolean))].map(id=>({v:id,l:devN(id)})));
  populateFilter('f-type', [...new Set(rows.map(r=>r.event_type).filter(Boolean))].map(t=>({v:t,l:t})));

  applyFilter();
}

function populateFilter(id, opts){
  const s=document.getElementById(id), cur=s.value;
  s.innerHTML='<option value="">'+s.options[0].text+'</option>';
  opts.forEach(o=>{const el=document.createElement('option');el.value=o.v;el.textContent=o.l;s.appendChild(el);});
  s.value=cur;
}

function applyFilter(){
  const fd=document.getElementById('f-dev').value;
  const ft=document.getElementById('f-type').value;
  const fs=document.getElementById('f-status').value;
  const fil=rows.filter(r=>
    (!fd||r.device_id===fd)&&
    (!ft||r.event_type===ft)&&
    (!fs||(fs==='archived'?r.archived:!r.archived))
  );
  document.getElementById('f-count').textContent=(fd||ft||fs)?`${fil.length} of ${rows.length}`:'';
  renderTable(fil);
}

function renderTable(list){
  const tb=document.getElementById('tbody');
  if(!list.length){
    tb.innerHTML='<tr><td colspan="7" style="color:var(--sub);padding:14px">No rows match the current filter.</td></tr>';
    updSel();return;
  }
  tb.innerHTML=list.map(r=>{
    const gi=rows.indexOf(r);
    const name=r.s3_key?`<span class="clip-name">${fname(r.s3_key)}</span>`:`<span style="font-size:.75rem;color:var(--sub)">${r.id.slice(-20)}</span>`;
    const status=r.archived
      ?'<span class="badge b-archived">Archived</span>'
      :'<span class="badge b-event">Event only</span>';
    return`<tr class="clickable" onclick="openMod(${gi})">
      <td onclick="event.stopPropagation()"><input type="checkbox" class="rchk" data-i="${gi}" onchange="updSel()"></td>
      <td>${name}</td>
      <td><span class="badge b-dev">${devN(r.device_id)}</span></td>
      <td><span class="badge b-type">${r.event_type||'—'}</span></td>
      <td style="color:var(--sub);white-space:nowrap;font-size:.8rem">${ts(r.start)}</td>
      <td>${status}</td>
      <td onclick="event.stopPropagation()"><div style="display:flex;gap:5px;flex-wrap:wrap">
        <button class="t dl" onclick="exp('download',${gi})">&#8681; Disk</button>
        <button class="t db" onclick="exp('dropbox',${gi})">Dropbox</button>
        <button class="t gd" onclick="exp('gdrive',${gi})">Drive</button>
      </div></td>
    </tr>`;
  }).join('');
  updSel();
}

function updSel(){
  const n=document.querySelectorAll('.rchk:checked').length;
  document.getElementById('c-sel').textContent=n;
  document.getElementById('bulk-bar').className=n?'show':'';
  document.getElementById('bulk-count').textContent=n;
}
function togAll(cb){document.querySelectorAll('.rchk').forEach(c=>c.checked=cb.checked);updSel();}
function clrSel(){document.querySelectorAll('.rchk').forEach(c=>c.checked=false);document.getElementById('chk-all').checked=false;updSel();}
function selRows(){return[...document.querySelectorAll('.rchk:checked')].map(c=>rows[+c.dataset.i]).filter(Boolean);}

function exp(dest,i){doExp(dest,[rows[i]]);}
function bExp(dest){doExp(dest,selRows());}
function mExp(dest){if(cur)doExp(dest,[cur]);}

function doExp(dest,list){
  if(!list.length)return;
  if(dest==='download'){
    list.forEach(r=>{
      if(!r.url||r.url==='#'){alert('No presigned URL — clip not archived to S3 yet.');return;}
      const a=document.createElement('a');a.href=r.url;a.download=fname(r.s3_key)||'clip.mp4';
      a.target='_blank';a.rel='noopener noreferrer';document.body.appendChild(a);a.click();document.body.removeChild(a);
    });return;
  }
  if(dest==='dropbox'){
    if(!window.Dropbox){
      const s=document.createElement('script');s.src='https://www.dropbox.com/static/api/2/dropins.js';
      s.id='dropboxjs';s.setAttribute('data-app-key','DROPBOX_APP_KEY');
      s.onload=()=>toDropbox(list);document.head.appendChild(s);
    }else toDropbox(list);return;
  }
  if(dest==='gdrive')toGDrive(list);
}
function toDropbox(list){
  const fs=list.filter(r=>r.url&&r.url!=='#').map(r=>({url:r.url,filename:fname(r.s3_key)||'clip.mp4'}));
  if(!fs.length){alert('No downloadable URLs — clips not in S3 yet.');return;}
  if(window.Dropbox&&window.Dropbox.save) fs.forEach(f=>window.Dropbox.save(f.url,f.filename,{success:()=>{},error:e=>alert('Dropbox: '+e)}));
  else alert('Dropbox SDK not loaded. Set DROPBOX_APP_KEY in .env and reload.');
}
function toGDrive(list){
  list.filter(r=>r.url&&r.url!=='#').forEach(r=>{
    alert('Download the clip first, then upload to Google Drive.\nFile: '+fname(r.s3_key)+'\n\nFull OAuth requires a GCP project with Drive API scope.');
    window.open('https://drive.google.com/drive/my-drive','_blank','noopener,noreferrer');
  });
  if(!list.some(r=>r.url&&r.url!=='#')) alert('No downloadable URLs — clips not in S3 yet.');
}

function openMod(i){
  cur=rows[i];
  document.getElementById('mtitle').textContent=fname(cur.s3_key)||cur.id.slice(-24);
  document.getElementById('mmeta').innerHTML=
    `<span class="badge b-dev">${devN(cur.device_id)}</span>`+
    `<span class="badge b-type">${cur.event_type||'—'}</span>`+
    (cur.start?`<span style="color:var(--sub)">${ts(cur.start)}</span>`:'')+
    (cur.archived?`<span class="badge b-archived">Archived</span>`:`<span class="badge b-event">Event only</span>`);
  const vid=document.getElementById('mvid'),nc=document.getElementById('mnoclip');
  if(cur.url&&cur.url!=='#'){vid.src=cur.url;vid.style.display='block';nc.style.display='none';}
  else{vid.src='';vid.style.display='none';nc.style.display='block';}
  document.getElementById('mbg').className='open';
}
function closeMod(e){
  if(e&&e.target!==document.getElementById('mbg'))return;
  document.getElementById('mbg').className='';
  document.getElementById('mvid').pause();document.getElementById('mvid').src='';cur=null;
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMod({target:document.getElementById('mbg')});});

async function runArchive(){
  const btn=document.getElementById('run-btn'),st=document.getElementById('status');
  btn.disabled=true;st.textContent='Running\u2026';
  try{
    const r=await fetch('/api/run',{method:'POST'});const d=await r.json();
    st.textContent=d.error?'Error: '+d.error:`Done — archived:${d.archived} skipped:${d.skipped} errors:${d.errors}`;
    load();
  }catch(e){st.textContent='Error: '+e;}finally{btn.disabled=false;}
}
load();
</script>
</body></html>"""

@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/api/devices")
def api_devices():
    try:
        c=RingClient.from_env()
        return jsonify([{"id":d["id"],"name":d.get("attributes",{}).get("name",d["id"][-8:])} for d in c.list_devices()])
    except Exception as ex: return jsonify({"error":str(ex)}),500

@app.route("/api/events")
def api_events():
    try:
        c=RingClient.from_env(); out=[]
        for d in c.list_devices():
            evs,_=c.list_events(d["id"])
            for e in evs:
                a=e.get("attributes",{})
                out.append({"id":e["id"],"event_type":a.get("event_type","unknown"),"start":a.get("start",0),"end":a.get("end",0),"device_id":d["id"]})
        return jsonify(out)
    except Exception as ex: return jsonify({"error":str(ex)}),500

@app.route("/api/clips")
def api_clips():
    try:
        items=list_recent(100)
        s3=boto3.client("s3",region_name=REGION)
        for item in items:
            if item.get("s3_key") and BUCKET:
                try: item["url"]=s3.generate_presigned_url("get_object",Params={"Bucket":BUCKET,"Key":item["s3_key"]},ExpiresIn=3600)
                except: item["url"]="#"
            else: item["url"]="#"
        return jsonify(items)
    except Exception as ex: return jsonify({"error":str(ex)}),500

@app.route("/api/run",methods=["POST"])
def api_run():
    try:
        from .handler import run_once
        return jsonify(run_once(RingClient.from_env()))
    except Exception as ex: return jsonify({"error":str(ex)}),500

def main():
    port=int(os.environ.get("PORT",5000))
    print(f"RingArchive UI -> http://localhost:{port}")
    app.run(host="0.0.0.0",port=port,debug=False)

if __name__=="__main__": main()
