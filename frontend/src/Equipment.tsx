import type {Station} from './types';
export default function Equipment({station:s}:{station:Station}){
  const active=s.state==='running';
  return <svg className={`equipment ${active?'equipment-running':''}`} viewBox="0 0 300 110" role="img" aria-label={`${s.name}, ${s.state}. Simulated equipment.`}>
    <defs><linearGradient id={`body-${s.id}`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#34414a"/><stop offset="1" stopColor="#1d2932"/></linearGradient></defs>
    {s.id==='ventilation'?<>
      <path d="M40 83H260M86 38H213M86 70H213" stroke="#3c4b56" strokeWidth="2"/>
      <path d="M40 35H93V75H40L30 65V45Z M207 35H260L270 45V65L260 75H207Z" fill={`url(#body-${s.id})`} stroke="#4a5b65"/>
      <rect x="94" y="14" width="112" height="82" rx="7" fill="#18222a" stroke="#566873"/>
      <circle cx="150" cy="55" r="32" fill="#10191f" stroke="#44555f"/>
      <g className="fan-rotor" style={{transformOrigin:'150px 55px',animationPlayState:active?'running':'paused'}} fill={active?'#61bfae':'#617582'}>
        {[0,90,180,270].map(a=><path key={a} d="M150 55C121 50 122 28 141 29C152 29 158 38 150 55Z" transform={`rotate(${a} 150 55)`}/>)}</g>
      <circle cx="150" cy="55" r="8" fill="#94b0b8"/><circle cx="150" cy="55" r="3" fill="#23343e"/>
      {[103,197].flatMap(x=>[22,88].map(y=><circle key={`${x}-${y}`} cx={x} cy={y} r="2" fill="#71838c"/>))}
      <path d="M57 48H76M57 55H76M57 62H76M226 48H244M226 55H244M226 62H244" stroke="#758b95" strokeWidth="1.5"/>
    </>:s.id==='conveyor'?<>
      <path d="M55 79L49 102M246 79L252 102M65 83H236" stroke="#4b626e" strokeWidth="6"/>
      <rect x="34" y="56" width="232" height="28" rx="14" fill="#1d2c35" stroke="#627782" strokeWidth="2"/>
      <path d="M49 65H251M49 75H251" stroke="#405661"/>
      {Array.from({length:10},(_,i)=><circle key={i} cx={51+i*22} cy="70" r="7" fill="#293f4a" stroke="#627b86"/>)}
      {[0,1,2].map((_,i)=><g key={i} transform={`translate(${54+((s.progress+i/3)%1)*175},0)`}><rect x="0" y="26" width="35" height="29" rx="2" fill={active?'#4d8b81':'#4e626d'} stroke="#7ba39e"/><path d="M0 34H35M17 26V34" stroke="#a1bbb7" opacity=".55"/></g>)}
      <rect x="35" y="87" width="230" height="3" fill="#18242c"/>
    </>:<>
      <path d="M78 91V27H222V91" fill="none" stroke="#4b6270" strokeWidth="8"/><path d="M69 95H231" stroke="#6c818c" strokeWidth="5"/>
      <rect x="132" y="14" width="36" height="24" rx="3" fill="#435d6a" stroke="#91a7af"/><circle cx="150" cy="39" r="7" fill="#1c2c34" stroke="#73ab9d"/>
      <rect x="105" y="82" width="90" height="9" rx="3" fill="#2a414d" stroke="#5c7985"/><path d="M119 80L129 59H171L181 80Z" fill="#405762" stroke="#7d9caa"/>
      {active&&<><path d={`M150 45L${116+s.progress*63} 80`} stroke="#6cd7be" strokeWidth="1.5"/><path d="M150 45L119 80H181Z" fill="#56ccb1" opacity=".07"/></>}
      <rect x="234" y="41" width="29" height="24" rx="3" fill="#1c2a32" stroke="#4d6470"/><circle cx="242" cy="49" r="2" fill={active?'#58ceb0':'#758591'}/><path d="M240 57H256" stroke="#68818c"/>
    </>}
  </svg>
}
