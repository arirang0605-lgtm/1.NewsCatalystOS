"""The download contains exactly the rendered comparison and its query."""
from pathlib import Path
import json,subprocess

def test_browser_download_copies_click_snapshot_with_sources_assessments_and_pit():
    script=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
let blob,link,revoked=false;
const ctx={TextEncoder,Blob,Uint8Array,crypto:crypto.webcrypto,
URL:{createObjectURL(b){blob=b;return 'blob:local'},revokeObjectURL(u){assert.equal(u,'blob:local');revoked=true}},
document:{body:{append(x){link=x}},createElement(){return {click(){this.clicked=true},remove(){this.removed=true}}}}};
vm.runInNewContext(src.slice(src.indexOf('async function saveFollowupComparison('),src.indexOf('function renderRecentThemeComparison(')),ctx);
const data={notes:[{note_id:'a'.repeat(64),source_company:'가상전기',available_at:'2026-10-18',
note:{analysis_text:'새로 읽은 과거 자료',recent_source:{headline:'계약 제목',source_url:'https://example.org/source'}}}],
period_comparison:{since:'2026-10-17',company_results:[{status:'HISTORICAL_READING_ADDED'}]},
company_assessment_comparison:{as_of:'2026-10-18',company_results:[{current:{status:'AVAILABLE',source_sha256:'b'.repeat(64)}}]}};
const query={since:'2026-10-17',as_of:'2026-10-18',outlook_id:'exact-group'};
const original=JSON.parse(JSON.stringify(data));
(async()=>{
const pending=ctx.saveFollowupComparison(data,query);data.notes[0].note.analysis_text='later mutation';await pending;
const bytes=Buffer.from(await blob.arrayBuffer()),doc=JSON.parse(bytes.toString());
assert.equal(doc.schema,'newscatalyst.company_followup_comparison.v1');
assert.deepEqual(doc.comparison,original);assert.deepEqual(doc.query,query);
assert.equal(doc.source_text_stored,false);assert.equal(doc.orders_enabled,false);
const pin=crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(link.download,'news_company_comparison_'+pin+'.json');
assert(link.clicked&&link.removed&&revoked);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,text=True,check=True)
