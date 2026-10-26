import {icon,initAppearance} from './appearance.js';
import {createBankImportUI} from './bank-import.js';
const appearance=initAppearance();
const root=document.querySelector('#admin-root'),notice=document.querySelector('#admin-notice');
const S={student:null,page:location.hash==='#import'?'import':'questions',catalog:null,list:{items:[],total:0},preview:null,busy:false,
  filters:{family:'bank',subject:'',stage:'',grade:'',term:'',status:'',reviewed:'all',difficulty:'',query:'',offset:0}};
let noticeTimer;
function el(tag,attrs={},...children){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs)){if(v==null||v===false)continue;if(k.startsWith('on'))n.addEventListener(k.slice(2).toLowerCase(),v);else if(k==='class')n.className=v;else if(k in n&&!k.startsWith('aria-'))n[k]=v;else n.setAttribute(k,v);}for(const child of children.flat(Infinity))if(child!=null&&child!==false)n.append(child instanceof Node?child:document.createTextNode(String(child)));return n;}
function message(text){notice.textContent=text;notice.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>notice.hidden=true,6500);}
async function api(path,body){const options={credentials:'same-origin',headers:{}};if(body!==undefined){options.method='POST';if(body instanceof FormData)options.body=body;else{options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}}
  const response=await fetch('/api/v1'+path,options);const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'文件或参数有误');return value;}
async function action(fn){if(S.busy)return;S.busy=true;root.setAttribute('aria-busy','true');try{await fn();}catch(error){message(error.message);}finally{S.busy=false;root.setAttribute('aria-busy','false');}}
const btn=(text,fn,cls='')=>el('button',{type:'button',class:cls,onClick:()=>action(fn)},text);
function iconButton(name,label,fn){return el('button',{type:'button',class:'icon-button','aria-label':label,title:label,onClick:()=>action(fn)},icon(name));}
function field(label,node){return el('label',{class:'field'},el('span',{},label),node);}
function select(label,options,value,change){const n=el('select',{'aria-label':label,onChange:e=>change(e.target.value)},options.map(([id,text])=>el('option',{value:String(id)},text)));n.value=String(value??'');return n;}
function math(node){window.renderMathInElement?.(node,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false}],throwOnError:false,trust:false});}
const importer=createBankImportUI({el,btn,field,select,api,message,render,catalog:()=>S.catalog,visible:()=>S.page==='import'&&!!S.student?.is_admin});
async function loadList(){const query=new URLSearchParams(Object.entries(S.filters).filter(([,v])=>v!==''));S.list=await api('/admin/questions?'+query);}
async function load(){S.student=(await api('/auth/session')).student;if(S.student?.is_admin){S.catalog=await api('/admin/catalog');await Promise.all([loadList(),importer.load()]);}render();}
async function page(name){S.page=name;S.preview=null;if(name==='questions')await loadList();else await importer.load();render();window.scrollTo({top:0});}
function login(){if(S.student)return el('main',{class:'admin-login'},el('h1',{},'需要题库权限'),el('a',{href:'/'},'返回做题'),btn('切换账号',async()=>{await api('/auth/logout',{});S.student=null;render();},'quiet'));
  const username=el('input',{autocomplete:'username',required:true,minLength:2,maxLength:40}),password=el('input',{type:'password',autocomplete:'current-password',required:true,minLength:8});
  return el('main',{class:'admin-login'},el('a',{href:'/',class:'wordmark'},'知域'),el('h1',{},'题库'),el('form',{onSubmit:e=>{e.preventDefault();action(async()=>{await api('/auth/login',{username:username.value,password:password.value});password.value='';await load();});}},field('用户名',username),field('密码',password),el('button',{type:'submit',class:'primary full'},'登录工作台')));}
function filters(){const f=S.filters;const change=async(key,value)=>{f[key]=value;f.offset=0;if(key==='family')f.status='';S.preview=null;await loadList();render();};
  const search=el('input',{type:'search','aria-label':'搜索题目',placeholder:'搜索题目、题型或编号',value:f.query});
  return el('form',{class:'bank-filters',onSubmit:e=>{e.preventDefault();action(()=>change('query',search.value));}},
    el('div',{class:'search-line'},icon('book'),search,el('button',{type:'submit'},'搜索')),
    el('div',{class:'filter-line'},select('科目',[['','全部科目'],...Object.entries(S.catalog.subjects)],f.subject,v=>action(()=>change('subject',v))),
      select('学段',[['','全部学段'],['junior','初中'],['senior','高中']],f.stage,v=>action(()=>change('stage',v))),
      select('年级',[['','全部年级'],[7,'七年级'],[8,'八年级'],[9,'九年级']],f.grade,v=>action(()=>change('grade',v))),
      select('学期',[['','全部册次'],[1,'上册'],[2,'下册']],f.term,v=>action(()=>change('term',v))),
      select('难度',[['','全部难度'],[1,'基础'],[2,'进阶'],[3,'挑战']],f.difficulty,v=>action(()=>change('difficulty',v)))),
    el('details',{class:'extra-filters'},el('summary',{},'更多筛选'),el('div',{class:'filter-line'},
      select('题目来源',[['bank','来源题库'],['original','原创核验题']],f.family,v=>action(()=>change('family',v))),
      select('AI审核筛选',[['all','全部题目'],['calibrated','AI审核通过']],f.reviewed,v=>action(()=>change('reviewed',v))),
      select('题目状态',[['','当前题目'],['ready','选择题'],['reference','过程题'],['quarantine','已隔离'],['superseded','历史版本']],f.status,v=>action(()=>change('status',v))))));}
function questionList(){return el('div',{class:'bank-list'},el('p',{class:'list-count'},`${S.list.total.toLocaleString()} 道题`),
  S.list.items.length?S.list.items.map(q=>el('button',{type:'button',class:'bank-row',onClick:()=>action(async()=>{S.preview=await api('/admin/question?'+new URLSearchParams({family:S.filters.family,id:q.id}));render();window.scrollTo({top:0});})},
    el('span',{class:'row-meta'},`${S.catalog.subjects[q.subject]||q.subject} · ${['','基础','进阶','挑战'][q.difficulty]||''}`,q.ai_calibrated?el('span',{class:'calibrated-label'},'AI 已标注'):null),
    el('span',{class:'row-stem'},q.stem.slice(0,240)+(q.stem.length>240?'…':'')),el('span',{class:'row-tags'},(q.type_tags||[]).slice(0,3).join(' · ')),icon('arrow'))):el('p',{class:'empty'},'没有匹配的题目'),
  el('div',{class:'pagination'},el('button',{type:'button',disabled:S.filters.offset===0,'aria-label':'上一页',onClick:()=>action(async()=>{S.filters.offset=Math.max(0,S.filters.offset-20);await loadList();render();})},icon('back')),
    el('span',{},`${Math.floor(S.filters.offset/20)+1} / ${Math.max(1,Math.ceil(S.list.total/20))}`),
    el('button',{type:'button',disabled:S.filters.offset+20>=S.list.total,'aria-label':'下一页',onClick:()=>action(async()=>{S.filters.offset+=20;await loadList();render();})},icon('arrow'))));}
function detail() {
  const q=S.preview, annotation=q.annotation||{}, parts=annotation.parts||[];
  const paper=el('article',{class:'detail-paper'},
    el('div',{class:'detail-meta'},
      el('span',{},`${S.catalog.subjects[q.subject]||q.subject} · ${q.grade||''}${q.grade?'年级':''}`),
      el('small',{},q.id)),
    el('h1',{class:'visually-hidden'},'题目详情'),
    el('div',{class:'question-stem'},q.stem),
    (q.options||[]).map(option=>el('p',{class:'detail-option'},`${option.key}. ${option.text}`)),
    (q.assets||[]).map(asset=>el('img',{
      src:typeof asset==='string'?asset:asset.url||asset.src,alt:'题图',class:'detail-image'})),
    el('section',{class:'answer-section'},el('h2',{},'答案'),el('p',{},q.answer),
      el('ol',{},(q.steps||[]).map(line=>el('li',{},line)))));
  const formats={single_choice:'单选',multiple_choice:'多选',fill_blank:'填空',calculation:'计算',
    proof:'证明',application:'应用',composite:'综合解答',short_answer:'解答'};
  const tags=el('dl',{class:'annotation-tags'},
    el('dt',{},'知识点'),el('dd',{},(q.knowledge_tags||[]).join('、')||'未标注'),
    el('dt',{},'题型'),el('dd',{},(q.type_tags||[]).join('、')||'未标注'),
    el('dt',{},'难度'),el('dd',{},`${['','基础','进阶','挑战'][q.difficulty]||'未标注'}${annotation.difficulty?.basis?' · '+annotation.difficulty.basis:''}`),
    el('dt',{},'作答形式'),el('dd',{},formats[annotation.response_format]||q.kind));
  const partDetails=parts.map((part,index)=>el('details',{class:'part-annotation'},
    el('summary',{},parts.length>1?`第 ${index+1} 问`:'答案规则与评分标准'),
    el('p',{},part.prompt),el('p',{},'参考答案：'+part.reference_answer),
    el('ol',{},(part.solution_steps||[]).map(line=>el('li',{},line))),
    el('ul',{},(part.rubric||[]).map(rule=>el('li',{},rule.description,rule.evidence_required?' · '+rule.evidence_required:''))),
    el('pre',{},JSON.stringify(part.answer_spec||{},null,2))));
  const full=el('details',{class:'full-annotation'},el('summary',{},'完整标注'),
    el('pre',{class:'calibration-command'},JSON.stringify(annotation,null,2)));
  return el('section',{class:'question-detail'},
    btn([icon('back'),'返回题库'],()=>{S.preview=null;render();},'back-link'),paper,
    el('section',{class:'annotation-section'},el('h2',{},'题目标注'),tags,partDetails,full));
}
function render(){const expanded=new Set([...root.querySelectorAll('details[open][data-persist]')].map(n=>n.dataset.persist));root.replaceChildren();if(!S.student?.is_admin){root.append(login());return;}
  const theme=iconButton(document.documentElement.dataset.theme==='dark'?'sun':'moon','切换主题',()=>{appearance.setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');render();});
  root.append(el('header',{class:'admin-topbar'},el('a',{class:'wordmark',href:'/'},'知域'),el('nav',{'aria-label':'题库功能'},btn([icon('book'),'题库'],()=>page('questions'),S.page==='questions'?'active':''),btn([icon('upload'),'导入'],()=>page('import'),S.page==='import'?'active':'')),
    el('div',{class:'admin-top-actions'},theme,el('a',{href:'/',class:'icon-button','aria-label':'返回做题',title:'返回做题'},icon('back')))),
    el('main',{class:'admin-shell'},S.page==='import'?importer.panel():S.preview?detail():el('section',{},el('h1',{},'题库'),filters(),questionList())));
  root.querySelectorAll('details[data-persist]').forEach(node=>{if(expanded.has(node.dataset.persist))node.open=true;});
  math(root);
}
load().catch(error=>{message(error.message);root.replaceChildren(el('main',{class:'admin-login'},el('p',{},'暂时无法打开题库'),btn('重试',load)));});
