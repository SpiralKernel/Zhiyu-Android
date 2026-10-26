/** File -> local AI -> existing source-pinned calibration -> automatic inclusion. */
import {icon} from './appearance.js';
export function createBankImportUI(ui) {
  const {el,btn,field,select,api,message,render}=ui;
  const C={book:'math-7-1',model:'',status:null,jobs:[],files:[],submitting:false,error:''};
  let timer=null,loading=false;
  async function load() {
    const [status,jobs]=await Promise.all([api('/admin/ingest/status'),api('/admin/ingest/jobs')]);
    C.status=status;C.jobs=jobs.items;
    if(!C.model)C.model=status.models.includes(status.model)?status.model:status.models[0]||status.model;
    schedule();
  }
  function schedule(){clearTimeout(timer);if(C.jobs.some(j=>['running','queued'].includes(j.status)))timer=setTimeout(poll,3000);}
  async function poll(){if(loading)return;loading=true;try{C.jobs=(await api('/admin/ingest/jobs')).items;if(ui.visible())render();}catch{}finally{loading=false;schedule();}}
  const names={queued:'排队中',running:'AI 审核中',completed:'处理完成',failed:'处理失败',interrupted:'已暂停'};
  const results={pending:'待处理',ready:'校验通过',hold:'未通过',excluded:'已排除',published:'已入库'};
  function job(j){const finished=Object.entries(j.counts).filter(([k])=>k!=='pending').reduce((n,[,v])=>n+v,0),total=Object.values(j.counts).reduce((a,b)=>a+b,0),active=['running','queued'].includes(j.status);
    return el('article',{class:'import-job'},el('div',{class:'job-heading'},el('div',{},el('strong',{},j.files.join('、')),el('p',{class:'muted'},`${names[j.status]} · ${finished} / ${total}`)),
      active?btn([icon('close'),el('span',{class:'visually-hidden'},'暂停任务')],async()=>{await api(`/admin/ingest/jobs/${j.id}/stop`,{});await load();render();},'stop-job'):
      ['failed','interrupted'].includes(j.status)?btn('继续',async()=>{await api(`/admin/ingest/jobs/${j.id}/resume`,{});await load();render();},'quiet'):el('span',{class:'job-total'},`已入库 ${j.counts.published}`)),
      active?el('progress',{max:Math.max(total,1),value:finished,'aria-label':'审核进度'}):null,
      j.error?el('p',{class:'import-error'},j.error):null,
      el('details',{class:'job-results','data-persist':'job-'+j.id},el('summary',{},`入库 ${j.counts.published} · 未通过 ${j.counts.hold} · 排除 ${j.counts.excluded}`),
        j.items.map(i=>el('div',{class:'import-result'},el('span',{class:'result-state'},results[i.status]),el('div',{},el('p',{},i.stem||'图片题'),i.issues.length?el('p',{class:'muted'},i.issues.join('；')):null)))));
  }
  function panel() {
    const books=ui.catalog().books.filter(b=>['math','physics'].includes(b.subject));
    const book=select('教材册次',books.map(b=>[b.id,`${b.subject==='math'?'数学':'物理'} · ${b.stage==='junior'?({7:'七',8:'八',9:'九'}[b.grade]+'年级'+(b.subject==='physics'&&b.grade===9?'全一册 · '+(b.term===1?'前半':'后半'):b.term===1?'上册':'下册')):(b.title||b.id).replace('普通高中教科书 ','')}`]),C.book,v=>C.book=v);
    const model=select('审核模型',(C.status?.models||[]).map(m=>[m,m]),C.model,v=>C.model=v);
    const input=el('input',{type:'file',accept:'.json,.jsonl,.txt,.md,.pdf,.jpg,.jpeg,.png,.webp',multiple:true,id:'bank-files','aria-label':'导入习题文件',class:'visually-hidden',onChange:e=>{C.files=[...e.target.files];C.error='';render();}});
    const picker=el('label',{class:'file-drop',htmlFor:'bank-files',onDragover:e=>{e.preventDefault();e.currentTarget.classList.add('dragging');},onDragleave:e=>e.currentTarget.classList.remove('dragging'),onDrop:e=>{e.preventDefault();C.files=[...e.dataTransfer.files];C.error='';render();}},
      icon('upload'),el('strong',{},C.files.length?`${C.files.length} 个文件`:'选择或拖入习题文件'),
      el('span',{},C.files.length?C.files.map(f=>f.name).join('、'):'照片 / PDF / JSON / 文本'),input);
    const unavailable=!C.status?.enabled || !C.status?.models.length;
    const submit=el('button',{type:'submit',class:'primary',disabled:unavailable||C.submitting},C.submitting?'正在提交…':'交给 AI');
    return el('section',{class:'bank-import-page'},
      el('form',{class:'import-form',onSubmit:async e=>{e.preventDefault();if(C.submitting)return;C.submitting=true;C.error='';
        try{
          if(!C.files.length)throw new Error('请先选择习题文件');
          if(C.files.length>8)throw new Error('每次最多 8 个文件');
          const body=new FormData();body.append('book_id',C.book);body.append('model',C.model);C.files.forEach(f=>body.append('files',f));
          await api('/admin/ingest/jobs',body);C.files=[];await load();message('已开始，审核通过后自动入库');
        }catch(error){C.error=error.message;}finally{C.submitting=false;render();}}},
        el('div',{class:'import-config'},field('教材册次',book),field('审核模型',model)),picker,
        C.error?el('p',{class:'import-error',role:'alert'},C.error):null,
        unavailable?el('p',{class:'muted'},C.status?.enabled?'请在做题页面的 AI 连接中配置模型':'当前服务尚未开启 AI 入库'):null,
        el('div',{class:'import-submit'},el('span',{class:'muted'},'通过后自动入库'),submit),
        el('details',{class:'format-example','data-persist':'file-example'},el('summary',{},'文件示例'),el('pre',{},'{"stem":"计算 -5 - (-4)。","reference_answer":"-1"}'),el('p',{class:'muted'},'JSONL 每行一道题，参考答案可省略。文字文件使用连续题号；题图以 images 数据字段提供。'),
          el('a',{href:'/api/v1/admin/ingest/example',download:'习题示例.jsonl'},'下载示例'))),
      C.jobs.length?el('section',{class:'import-jobs'},el('h2',{},'最近导入'),C.jobs.map(job)):null);
  }
  return {load,panel};
}
