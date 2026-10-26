/** Dependency-free pressure-aware answer paper; persisted per account and attempt. */
import {icon} from './appearance.js';
export function createWritingUI(ui) {
  const {S,el,btn,api,error}=ui, records=new Map();
  function reset(){for(const r of records.values())clearTimeout(r.timer);records.clear();}
  function paper(work,onSubmit){
    const key=`${S.student.student_id}/${work.source}/${work.attempt_id}`;
    let r=records.get(key);
    if(!r){r={strokes:[],undo:[],redo:[],loaded:false,open:false,wide:false,tool:'pen',width:3,penSeen:false,finger:false,chain:Promise.resolve()};records.set(key,r);}
    const endpoint=`/writing/${work.source}/${work.attempt_id}`;
    const status=el('span',{class:'writing-status',role:'status'});
    function save(){
      clearTimeout(r.timer);if(!r.loaded)return Promise.resolve();
      const data=JSON.parse(JSON.stringify({strokes:r.strokes}));
      status.textContent='保存中';
      r.chain=r.chain.catch(()=>{}).then(()=>api(endpoint,data,'PUT')).then(()=>{status.textContent='已保存';}).catch(e=>{status.textContent='未保存';error(e.message);throw e;});
      // Keep rejected saves observable by submit while avoiding unhandled rejections.
      r.chain.catch(()=>{});return r.chain;
    }
    const schedule=()=>{clearTimeout(r.timer);r.timer=setTimeout(()=>save(),500);};
    const canvas=el('canvas',{width:1500,height:2100,'aria-label':'答题纸，可用触控笔书写',tabIndex:0});
    const ctx=canvas.getContext('2d');
    const scroll=el('div',{class:'writing-scroll'},canvas);
    const controls=[];
    function tool(name,label,fn){const b=btn(icon(name),fn,'icon-button');b.title=label;b.setAttribute('aria-label',label);controls.push(b);return b;}
    const pen=tool('pen','写字',()=>{r.tool='pen';sync();});
    const eraser=tool('eraser','擦除整笔',()=>{r.tool='eraser';sync();});
    const undo=tool('undo','撤销',()=>{if(r.undo.length){r.redo.push(r.strokes);r.strokes=r.undo.pop();draw();schedule();sync();}});
    const redo=tool('redo','重做',()=>{if(r.redo.length){r.undo.push(r.strokes);r.strokes=r.redo.pop();draw();schedule();sync();}});
    const finger=tool('hand','手指书写',()=>{r.finger=!r.finger;sync();});
    const clear=tool('trash','清空答题纸',()=>{
      if(!r.strokes.length)return;
      // Local inline confirmation preserves the current question and paper.
      confirm.hidden=false;
    });
    const confirm=el('div',{class:'writing-confirm',hidden:true},el('span',{},'清空这张纸？'),btn('清空',()=>{r.undo.push(r.strokes);r.strokes=[];r.redo=[];confirm.hidden=true;draw();schedule();sync();},'quiet'),btn('取消',()=>confirm.hidden=true,'quiet'));
    const expand=tool('expand','展开 / 收起大答题纸',()=>{r.wide=!r.wide;node.classList.toggle('writing-wide',r.wide);expand.setAttribute('aria-pressed',String(r.wide));});
    const widths=el('select',{'aria-label':'笔粗',onChange:e=>r.width=Number(e.target.value)},[2,3,5].map(w=>el('option',{value:w},w===2?'细':w===3?'中':'粗')));widths.value=r.width;
    const toolbar=el('div',{class:'writing-toolbar'},pen,eraser,undo,redo,widths,finger,clear,expand);
    const submit=work.question.answer_mode==='written'?btn('提交作答',async()=>{
      if(!r.loaded||!r.strokes.length)throw new Error('请先写下答案');
      await save();
      const image=document.createElement('canvas');image.width=1500;image.height=2100;
      const c=image.getContext('2d');c.fillStyle='#ffffff';c.fillRect(0,0,image.width,image.height);c.drawImage(canvas,0,0);
      const blob=await new Promise(resolve=>image.toBlob(resolve,'image/png'));
      if(!blob)throw new Error('答题纸导出失败，请重试');
      await onSubmit(new File([blob],'answer-paper.png',{type:'image/png'}));
    },'primary'):null;
    const summary=el('summary',{'aria-label':'答题纸',title:'答题纸'},icon('paper'));
    const node=el('details',{class:`answer-board${r.wide?' writing-wide':''}`,open:r.open},summary,
      el('div',{class:'writing-panel'},toolbar,confirm,scroll,el('div',{class:'writing-footer'},status,submit)));
    function sync(){
      pen.setAttribute('aria-pressed',String(r.tool==='pen'));eraser.setAttribute('aria-pressed',String(r.tool==='eraser'));finger.setAttribute('aria-pressed',String(r.finger));
      undo.disabled=!r.loaded||!r.undo.length;redo.disabled=!r.loaded||!r.redo.length;
      canvas.style.touchAction=r.penSeen&&!r.finger?'pan-y':'none';
    }
    let active=null,frame=null,erased=false,dragScroll=null,pointLimit=8000;
    function draw(){
      ctx.setTransform(1.5,0,0,1.5,0,0);ctx.clearRect(0,0,1000,1400);ctx.strokeStyle='#40362e';ctx.fillStyle='#40362e';ctx.lineCap='round';ctx.lineJoin='round';
      for(const stroke of r.strokes){const ps=stroke.points;
        if(ps.length===1){ctx.beginPath();ctx.arc(ps[0][0],ps[0][1],stroke.width/2,0,Math.PI*2);ctx.fill();continue;}
        for(let i=1;i<ps.length;i++){
          const a=ps[i-1],b=ps[i],prev=ps[Math.max(0,i-2)];
          ctx.lineWidth=stroke.width*(.55+((a[2]+b[2])/2)*.9);
          ctx.beginPath();ctx.moveTo(i===1?a[0]:(prev[0]+a[0])/2,i===1?a[1]:(prev[1]+a[1])/2);
          ctx.quadraticCurveTo(a[0],a[1],(a[0]+b[0])/2,(a[1]+b[1])/2);ctx.stroke();
          if(i===ps.length-1){ctx.beginPath();ctx.moveTo((a[0]+b[0])/2,(a[1]+b[1])/2);ctx.lineTo(b[0],b[1]);ctx.stroke();}
        }
      }
    }
    const paint=()=>{if(frame===null)frame=requestAnimationFrame(()=>{frame=null;draw();});};
    const point=e=>{const b=canvas.getBoundingClientRect();return [Math.max(0,Math.min(1000,(e.clientX-b.left)/b.width*1000)),Math.max(0,Math.min(1400,(e.clientY-b.top)/b.height*1400)),e.pointerType==='pen'?Math.max(.05,e.pressure):.5];};
    function distance(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);}
    function erase(p){const kept=r.strokes.filter(s=>!s.points.some((a,i)=>distance(p,a,s.points[Math.min(i+1,s.points.length-1)])<14+s.width));if(kept.length!==r.strokes.length){r.strokes=kept;erased=true;paint();}}
    canvas.addEventListener('pointerdown',e=>{
      if(!r.loaded||S.busy||active!==null)return;
      if(e.pointerType==='pen'){r.penSeen=true;sync();}
      if(e.pointerType==='touch'&&r.penSeen&&!r.finger)return;
      e.preventDefault();canvas.setPointerCapture(e.pointerId);active=e.pointerId;erased=false;
      if(r.strokes.length>=2000||r.strokes.reduce((n,s)=>n+s.points.length,0)>=59000){error('这张答题纸已满，请提交或清空后继续');active=null;return;}
      pointLimit=Math.min(8000,60000-r.strokes.reduce((n,s)=>n+s.points.length,0));
      r.undo.push(r.strokes);if(r.undo.length>60)r.undo.shift();r.redo=[];
      if(r.tool==='eraser'||(e.buttons&32)){dragScroll='eraser';erase(point(e));}
      else{dragScroll=null;r.strokes=[...r.strokes,{width:r.width,points:[point(e)]}];paint();}sync();
    });
    canvas.addEventListener('pointermove',e=>{
      if(e.pointerId!==active)return;e.preventDefault();
      if(dragScroll==='eraser'){erase(point(e));return;}
      const stroke=r.strokes.at(-1);
      const samples=e.getCoalescedEvents?.();
      for(const sample of samples?.length?samples:[e]){const p=point(sample),last=stroke.points.at(-1);if(Math.hypot(last[0]-p[0],last[1]-p[1])>.6&&stroke.points.length<pointLimit)stroke.points.push(p);}
      paint();
    });
    function finish(e){if(e.pointerId!==active)return;active=null;if(dragScroll==='eraser'&&!erased)r.undo.pop();dragScroll=null;draw();schedule();sync();}
    canvas.addEventListener('pointerup',finish);canvas.addEventListener('pointercancel',finish);
    node.addEventListener('toggle',async()=>{
      r.open=node.open;
      if(!node.open){r.wide=false;node.classList.remove('writing-wide');if(r.loaded)save();return;}
      if(!r.loaded){controls.forEach(b=>b.disabled=true);if(submit)submit.disabled=true;status.textContent='载入中';try{
        const data=await api(endpoint);r.strokes=data.strokes||[];r.loaded=true;status.textContent='';controls.forEach(b=>b.disabled=false);if(submit)submit.disabled=false;
      }catch(e){status.textContent='载入失败';error(e.message);}}
      draw();sync();
    });
    node.addEventListener('keydown',e=>{if(e.key==='Escape'&&r.wide){e.stopPropagation();r.wide=false;node.classList.remove('writing-wide');}});
    if(r.loaded){draw();sync();}
    return node;
  }
  return {paper,reset};
}
