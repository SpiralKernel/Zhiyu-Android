import { icon, skins } from './appearance.js';
export function createAppSettings(ui, appearance) {
  const {el,btn,field,select,api,error,dialog}=ui;
  let config=null;
  async function load(){config=await api('/settings');appearance.setSkin(config.profile.skin||'paper',config.profile.custom||{});appearance.setTheme(config.profile.theme||'system');appearance.setSize(config.profile.font_size||'normal');return config;}
  const logo=p=>p.logo?el('img',{src:`/static/providers/${p.logo}.svg`,alt:'',class:'provider-logo',onError:e=>e.target.hidden=true}):icon('settings');
  async function connections(first=false) {
    await load();
    const body=el('div',{class:'connection-settings'});
    let editing=null,provider='deepseek';
    const name=el('input',{maxlength:60,placeholder:'连接名称（可选）'});
    const key=el('input',{type:'password',autocomplete:'off',spellcheck:false,placeholder:'API Key',maxlength:4096});
    const model=el('input',{placeholder:'模型名称',required:true,maxlength:150});
    const vision=el('input',{placeholder:'识图模型（可选）',maxlength:150});
    const base=el('input',{type:'url',placeholder:'https://…/v1',maxlength:500});
    const status=el('p',{class:'connection-status',role:'status'});
    const providers=el('div',{class:'provider-grid'});
    const advanced=el('details',{},el('summary',{},'更多选项'),field('名称',name),field('接口地址',base),field('识图模型',vision));
    const setProvider=(id,entry=null)=>{
      provider=id;editing=entry?.id||null;
      const p=config.providers.find(x=>x.id===id);
      name.value=entry?.name||'';base.value=entry?.base_url||p.url;model.value=entry?.model||p.model;vision.value=entry?.vision_model||'';key.value='';
      key.placeholder=entry?.has_key?'留空保留已保存的 Key':'API Key';advanced.open=id==='compatible';status.textContent='';
      providers.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.provider===id)));
    };
    providers.append(...config.providers.map(p=>{
      const b=btn([logo(p),el('span',{},p.name)],()=>setProvider(p.id),'provider-option');b.dataset.provider=p.id;return b;
    }));
    if(config.connections.length)body.append(el('div',{class:'connection-list'},...config.connections.map(c=>el('div',{class:'connection-row'},
      btn([logo(config.providers.find(p=>p.id===c.provider)),el('span',{},c.name,el('small',{},c.model)),config.profile.selected_connection===c.id?'●':'○'],async()=>{await api(`/settings/connections/${c.id}/activate`,{});await connections();},'connection-choice'),
      btn('编辑',()=>setProvider(c.provider,c),'quiet'),btn('删除',async()=>{await api(`/settings/connections/${c.id}`,null,'DELETE');await connections();},'quiet')))));
    const form=el('form',{onSubmit:e=>{e.preventDefault();ui.action(async()=>{
      const saved=await api('/settings/connections',{id:editing,provider,name:name.value,base_url:base.value,model:model.value,vision_model:vision.value,api_key:key.value});
      key.value='';await load();status.textContent='已保存';editing=saved.id;
      const test=btn('测试连接',async()=>{status.textContent='连接中…';try{await api(`/settings/connections/${saved.id}/test`,{});status.textContent='连接成功';}catch(e){status.textContent=e.message;}},'full');
      status.parentElement.querySelector('.connection-test')?.remove();test.classList.add('connection-test');status.after(test);
    });}},providers,field('模型',model),field('API Key',key),advanced,el('button',{type:'submit',class:'primary full'},'保存并使用'),status);
    body.append(form);
    const close=dialog(first?'连接 AI':'AI 连接',body,'connection-dialog');setProvider(config.connections.find(c=>c.id===config.profile.selected_connection)?.provider||'deepseek',config.connections.find(c=>c.id===config.profile.selected_connection));
    if(first)body.append(btn('稍后设置',close,'quiet full'));
  }
  function appearancePanel(){
    const body=el('div',{class:'appearance-panel'});
    const persist=()=>api('/settings/appearance',{skin:appearance.skin,custom:appearance.custom,theme:appearance.theme,font_size:appearance.size},'PUT');
    body.append(field('模式',select('模式',[['system','跟随系统'],['light','亮色'],['dark','暗色']],appearance.theme,async v=>{appearance.setTheme(v);try{await persist();}catch(e){error(e.message);}})));
    const grid=el('div',{class:'skin-grid'});
    const save=async(id,custom={})=>{appearance.setSkin(id,custom);await persist();};
    grid.append(...skins.map(s=>{
      const b=btn([el('span',{class:'skin-swatch',style:`background:${s.background};color:${s.ink};border-color:${s.accent}`},el('i',{style:`background:${s.accent}`})),el('span',{},s.name)],async()=>{await save(s.id);grid.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));},'skin-option');b.setAttribute('aria-pressed',String(s.id===appearance.skin));return b;
    }));body.append(grid);
    const colors={...skins.find(s=>s.id===appearance.skin)||skins[0],...appearance.custom};
    const inputs={};const custom=el('details',{},el('summary',{},'自定义配色'));
    for(const [k,n] of Object.entries({background:'背景',paper:'纸面',ink:'文字',accent:'强调色'})){
      inputs[k]=el('input',{type:'color',value:colors[k]});custom.append(field(n,inputs[k]));
    }
    custom.append(btn('应用配色',()=>save('custom',Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value]))),'full'));
    body.append(custom,el('p',{class:'font-preview'},'知域 · 每一步，都更清楚。'),field('字号',select('字号',[['small','小 · 90%'],['normal','标准 · 100%'],['medium','舒适 · 112%'],['large','大 · 125%'],['xlarge','特大 · 140%']],appearance.size,async v=>{appearance.setSize(v);try{await persist();}catch(e){error(e.message);}})));return body;
  }
  function avatarImage(small=false){
    const fallback=icon('user');
    const image=el('img',{src:'/api/v1/settings/avatar?v='+Date.now(),alt:'',class:'student-avatar',onError:e=>e.target.hidden=true,onLoad:()=>fallback.hidden=true});
    return el('span',{class:small?'avatar-frame avatar-small':'avatar-frame'},fallback,image);
  }
  function avatar(onDone=()=>{}){
    const button=btn(avatarImage(),()=>editAvatar(onDone),'avatar-button');button.title='更换头像';button.setAttribute('aria-label','更换头像');return button;
  }
  function editAvatar(onDone){
    const body=el('div',{class:'avatar-editor'});
    const input=el('input',{type:'file',accept:'image/jpeg,image/png,image/webp',hidden:true});
    const pick=btn('从相册选择',()=>{input.value='';input.click();},'full');
    body.append(pick,input);
    const close=dialog('更换头像',body,'avatar-dialog');
    input.addEventListener('change',()=>ui.action(async()=>{
      const file=input.files[0];if(!file)return;
      if(file.size>5*1024*1024)throw new Error('头像最多5MB');
      const url=URL.createObjectURL(file),image=new Image();
      try{await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error('图片无法打开'));image.src=url;});}finally{URL.revokeObjectURL(url);}
      if(image.width*image.height>20000000)throw new Error('图片尺寸太大，请换一张');
      const canvas=el('canvas',{width:640,height:640,'aria-label':'拖动图片定位头像'}),ctx=canvas.getContext('2d');
      let zoom=1,panX=0,panY=0,drag=null;
      const base=Math.max(640/image.width,640/image.height);
      function draw(){const scale=base*zoom;panX=Math.max(-(image.width*scale-640)/2,Math.min((image.width*scale-640)/2,panX));panY=Math.max(-(image.height*scale-640)/2,Math.min((image.height*scale-640)/2,panY));ctx.clearRect(0,0,640,640);ctx.drawImage(image,(640-image.width*scale)/2+panX,(640-image.height*scale)/2+panY,image.width*scale,image.height*scale);}
      canvas.addEventListener('pointerdown',e=>{e.preventDefault();if(drag)return;canvas.setPointerCapture(e.pointerId);drag={id:e.pointerId,x:e.clientX,y:e.clientY};});
      canvas.addEventListener('pointermove',e=>{if(drag?.id!==e.pointerId)return;e.preventDefault();const scale=640/canvas.getBoundingClientRect().width;panX+=(e.clientX-drag.x)*scale;panY+=(e.clientY-drag.y)*scale;drag.x=e.clientX;drag.y=e.clientY;draw();});
      for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,e=>{if(drag?.id===e.pointerId)drag=null;});
      const slider=el('input',{type:'range',min:1,max:4,step:.01,value:1,'aria-label':'缩放头像',onInput:e=>{zoom=Number(e.target.value);draw();}});
      body.replaceChildren(el('div',{class:'avatar-crop'},canvas,el('div',{class:'avatar-crop-guide','aria-hidden':'true'})),field('缩放',slider),el('div',{class:'actions'},btn('重新选择',()=>{input.value='';input.click();},'quiet'),btn('保存头像',async()=>{
        const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.9));if(!blob)throw new Error('图片处理失败');
        const form=new FormData();form.append('file',blob,'avatar.jpg');await api('/settings/avatar',form,'PUT');close();onDone();
      },'primary')),input);draw();
    }));
  }
  function accountPanel(onDone){
    const username=el('input',{value:ui.S.student.username,minLength:2,maxLength:40,autocomplete:'username',required:true});
    const nickname=el('input',{value:ui.S.student.nickname,maxLength:30,required:true});
    return el('div',{class:'account-panel'},avatar(onDone),el('form',{onSubmit:e=>{e.preventDefault();ui.action(async()=>{
      const value=await api('/auth/profile',{username:username.value,nickname:nickname.value},'PUT');ui.S.student=value.student;ui.render();onDone();
    });}},field('称呼',nickname),field('用户名',username),el('button',{type:'submit',class:'primary full'},'保存')));
  }
  return {load,connections,appearancePanel,avatar,avatarImage,accountPanel};
}
