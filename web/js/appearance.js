/** Student appearance and shared, labelled line icons. */
const paths = {
  report: ['M6 3h9l4 4v14H6z','M14 3v5h5M9 12h7M9 16h7'],
  paper: ['M5 3h10l4 4v14H5z','M14 3v5h5M8 12h5M8 16h3m2 0 4-4'],
  pen: ['m5 16-1 4 4-1L20 7l-3-3Z','m14 7 3 3'],
  eraser: ['m4 14 9-10 7 6-9 10H9Z','m9 9 7 6M11 20h10'],
  undo: ['M8 5 3 10l5 5','M3 10h11a6 6 0 0 1 0 12'],
  redo: ['m16 5 5 5-5 5','M21 10H10a6 6 0 0 0 0 12'],
  trash: ['M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7'],
  hand: ['M7 12V6a2 2 0 0 1 4 0v5-7a2 2 0 0 1 4 0v7-5a2 2 0 0 1 4 0v9c0 5-3 7-7 7-3 0-5-2-7-5l-2-4a2 2 0 0 1 3-2l3 4'],
  menu: ['M4 7h16M4 12h16M4 17h16'],
  settings: ['M4 7h10m4 0h2M4 17h2m4 0h10', 'M14 4v6M6 14v6'],
  book: ['M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4z','M13 7a3 3 0 0 1 3-3h5v15h-4a4 4 0 0 0-4 2'],
  chat: ['M20 11a8 8 0 0 1-8 8H5l-3 3V11a9 9 0 0 1 18 0Z','M7 10h8M7 14h5'],
  chart: ['M4 4v16h16M8 15v-4m5 4V7m5 8v-6'],
  upload: ['M12 15V3m-4 4 4-4 4 4M4 14v6h16v-6'],
  user: ['M20 21a8 8 0 0 0-16 0'],
  sun: ['M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1'],
  moon: ['M20 14a8 8 0 0 1-10-10 9 9 0 1 0 10 10Z'],
  close: ['m6 6 12 12M6 18 18 6'],
  arrow: ['M4 12h16m-6-6 6 6-6 6'],
  back: ['M20 12H4m6-6-6 6 6 6'],
  camera: ['M3 7h4l2-3h6l2 3h4v13H3z'],
  history: ['M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2'],
  logout: ['M9 4H4v16h5M9 12h12m-5-5 5 5-5 5'],
  expand: ['M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6'],
};
export function icon(name) {
  const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
  for (const [key,value] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':1.6,'stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',class:'icon'})) svg.setAttribute(key,value);
  if(name==='brand'){svg.classList.add('brand-mark');svg.setAttribute('viewBox','0 0 512 512');svg.innerHTML='<path d="M308 180H358Q374 180 374 196V246M204 332H154Q138 332 138 316V266" stroke-width="26"/><rect x="226" y="226" width="60" height="60" rx="9" fill="#C5A0CF" stroke="none" transform="rotate(45 256 256)"/>';return svg;}
  for (const d of paths[name] || paths.book) { const path=document.createElementNS(ns,'path');path.setAttribute('d',d);svg.append(path); }
  if (['sun','user','camera'].includes(name)) {
    const c=document.createElementNS(ns,'circle');
    for(const [k,v] of Object.entries({cx:12,cy:name==='user'?8:name==='camera'?13:12,r:name==='sun'?4:3})) c.setAttribute(k,v);
    svg.append(c);
  }
  return svg;
}
export const skins=[
  {id:'paper',name:'纸白',background:'#F7F3EA',paper:'#FFFCF5',ink:'#40362E',accent:'#AA7058'},
  {id:'rose',name:'陶粉',background:'#F3DED9',paper:'#FFF6F2',ink:'#4C3935',accent:'#A65D4B'},
  {id:'forest',name:'森林',background:'#DCE6D6',paper:'#F5FAF0',ink:'#344336',accent:'#59765A'},
  {id:'ocean',name:'海盐',background:'#D7E8ED',paper:'#F2FAFC',ink:'#30484D',accent:'#537C85'},
  {id:'lavender',name:'淡紫',background:'#E8DEF0',paper:'#FBF5FF',ink:'#493C53',accent:'#856894'},
];
export function initAppearance() {
  let theme = 'system', size = 'normal', skin='paper', custom={};
  try { theme=localStorage.getItem('teacher-theme') || theme;size=localStorage.getItem('teacher-font') || size; } catch {}
  try{skin=localStorage.getItem('teacher-skin')||skin;custom=JSON.parse(localStorage.getItem('teacher-colors')||'{}');}catch{}
  const system=matchMedia('(prefers-color-scheme: dark)');
  function apply() {
    document.documentElement.dataset.theme=theme==='system'?(system.matches?'dark':'light'):theme;
    document.documentElement.dataset.font=size;
    document.documentElement.dataset.skin=skin;
    const preset=skins.find(s=>s.id===skin)||skins[0];
    const colors=skin==='custom'?{...preset,...custom}:preset;
    const dark=document.documentElement.dataset.theme==='dark';
    const accents={paper:'#D29A7D',rose:'#E4A28F',forest:'#ABC3A0',ocean:'#9DC6D0',lavender:'#C5ABDA'};
    const darkBases={paper:['#211F1C','#2B2824'],rose:['#2B2022','#36292B'],forest:['#1D2821','#29362D'],ocean:['#19272E','#24363E'],lavender:['#272131','#342B40']};
    const base=darkBases[skin]||darkBases.paper;
    const palette=dark&&skin!=='custom'?{background:base[0],paper:base[1],ink:'#EEE6DF',accent:accents[skin]||accents.paper}:colors;
    for(const k of ['background','paper','ink','accent'])
      if(/^#[0-9a-f]{6}$/i.test(palette[k]))document.documentElement.style.setProperty('--'+k,palette[k]);
    document.documentElement.style.fontSize=16*({small:.9,normal:1,medium:1.12,large:1.25,xlarge:1.4}[size]||1)+'px';
    try{window.AndroidTheme?.apply(getComputedStyle(document.documentElement).getPropertyValue('--background').trim(),document.documentElement.dataset.theme==='dark');}catch{}
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',palette.background);
  }
  system.addEventListener('change',apply);apply();
  return {get skin(){return skin;},get custom(){return custom;},setSkin(value,colors={}){skin=value;custom=colors;try{localStorage.setItem('teacher-skin',skin);localStorage.setItem('teacher-colors',JSON.stringify(custom));}catch{}apply();}, get theme(){return theme;},get size(){return size;},setTheme(value){theme=value;try{localStorage.setItem('teacher-theme',value);}catch{}apply();},setSize(value){size=value;try{localStorage.setItem('teacher-font',value);}catch{}apply();} };
}
