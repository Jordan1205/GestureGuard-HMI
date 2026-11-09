import {useEffect,useState} from 'react';
import {Activity,Camera,Check,Focus,Hand,Info,LockKeyhole,ScanLine,ShieldCheck,UnlockKeyhole} from 'lucide-react';
import type {ReactNode} from 'react';
import type {Snapshot} from './types';
import {activation,diagnostics,gestureName,instruction,numericSetting} from './recognition';

type Request=(path:string,body?:unknown)=>Promise<unknown>;
const number=(value:number|undefined,digits=2)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'—';

export function RecognitionDiagnostics({s,preview}:{s:Snapshot;preview:ReactNode}){
  const d=diagnostics(s),v=s.vision;
  const geometryPinch=d.threshold_kind==='maximum_normalized_tip_distance'||d.score_kind==='geometric_quality_index';
  const rawGesture=d.geometry?.raw_canned_gesture??d.raw_gesture??s.engine.gesture;
  const rawScore=d.geometry?.raw_canned_score??d.raw_score??s.engine.score;
  const live=v.source==='live'&&v.status==='streaming',unlocked=d.unlocked??s.engine.state!=='LOCKED';
  const freshLiveHand=live&&v.hands>0&&typeof v.frame_age_ms==='number'&&v.frame_age_ms<=numericSetting(s.engine.settings,'max_observation_gap_seconds',.3)*1000;
  const hasObservation=v.source!=='live'||freshLiveHand;
  const classificationLabel=v.source==='simulated'?'Injected classification':v.source==='replay'?'Recorded observation classification':'Raw MediaPipe classification';
  const scoreLabel=v.source==='simulated'?'Injected test score':v.source==='replay'?'Recorded observation score':'Raw classifier score';
  const progress=Math.max(0,Math.min(1,d.evidence_progress??s.engine.hold_progress));
  return <div className="recognition-workspace">
    <section className="panel studio-preview"><div className="panel-heading"><h2><Camera size={17}/>{v.source==='live'?'Live gesture practice':v.source==='replay'?'Recorded gesture practice':'Simulated gesture practice'}</h2><span className={`badge ${live?'teal':'neutral'}`}><span className="status-dot"/>{v.source==='live'?'Live camera':v.source==='replay'?'Recorded replay':'Simulated input'}</span></div>{preview}<div className="practice-instruction"><Hand size={18}/><div><strong>{instruction(s,true)}</strong><p>{instruction(s)}</p></div></div></section>
    <section className="panel diagnostics-panel"><div className="panel-heading"><h2><ScanLine size={17}/>Recognition diagnostics</h2><span className={`badge ${unlocked?'teal':'amber'}`}><span className="status-dot"/>{unlocked?'Unlocked':'Locked'}</span></div>
      <div className="diagnostics-grid">
        <div><span>Camera status</span><strong>{v.source==='live'?v.status.replaceAll('_',' '):'Not in live mode'}</strong></div>
        <div><span>Hands {v.source==='live'?'detected':v.source==='replay'?'recorded':'injected'}</span><strong>{v.hands}</strong></div>
        <div><span>Filtered classification</span><strong>{gestureName(d.filtered_gesture??s.engine.gesture)}</strong></div>
        <div><span>Current candidate</span><strong>{gestureName(d.candidate_gesture)}</strong></div>
        <div><span>Tracking status</span><strong>{d.tracking_status?.replaceAll('_',' ')??(v.hands===1?'One hand present':'No hand present')}</strong></div>
        <div><span>Filter status</span><strong>{d.status?.replaceAll('_',' ')??'Waiting for evidence'}</strong></div>
        <div><span>Recognition FPS</span><strong>{live?number(v.fps,1):'—'}<small>{live?' fps':'Live samples only'}</small></strong></div>
        <div><span>Inference latency</span><strong>{live?number(v.recognition_ms,1):'—'}<small>{live?' ms':'Live samples only'}</small></strong></div>
      </div>
      <div className="diagnostic-evidence"><div><span>Accumulated gesture evidence</span><strong>{number(progress*100,0)}%</strong></div><div className="progress-track"><div style={{width:`${progress*100}%`}}/></div><p>Brief noise can pause progress; it does not automatically mean a rejected command.</p></div>
      <details className="classifier-details" open><summary>Classifier details <span>Advanced diagnosis</span></summary><dl><div><dt>{classificationLabel}</dt><dd>{hasObservation?gestureName(rawGesture):'—'}</dd></div><div><dt>{scoreLabel}</dt><dd>{number(hasObservation?rawScore:undefined,3)}</dd></div>{geometryPinch?<><div><dt>Interpreted gesture</dt><dd>{hasObservation?`${gestureName(d.interpreted_gesture??'Pinch')} · geometry`:'—'}</dd></div><div><dt>Pinch distance ratio (≤ limit)</dt><dd>{number(hasObservation?d.geometry?.pinch_ratio:undefined,3)} ≤ {number(d.threshold??numericSetting(s.engine.settings,'pinch_ratio',.28),3)}</dd></div></>:<div><dt>Classifier minimum score</dt><dd>{number(d.classifier_threshold??d.threshold??numericSetting(s.engine.settings,'min_score',.7),3)}</dd></div>}<div><dt>Hold interruptions</dt><dd>{d.hold_interruptions??'—'}</dd></div><div><dt>Engine state</dt><dd>{s.engine.state}</dd></div><div><dt>Evidence path</dt><dd>{d.acceptance_path?.replaceAll('_',' ')??'Collecting'}</dd></div></dl><p><Info size={13}/>{geometryPinch?'Pinch uses fingertip distance divided by palm width. Its maximum distance limit is separate from the input score.':v.source==='simulated'?'Injected scores are explicit test inputs, not live MediaPipe measurements or calibrated probabilities.':v.source==='replay'?'Recorded scores preserve the observation stream. Replay does not perform new camera inference or establish calibrated probabilities.':'Classifier scores are model outputs, not calibrated probabilities. Inspect recorded samples before tuning thresholds.'}</p></details>
      <div className="diagnostic-reason"><Info size={15}/><div><span>Current decision / lock reason</span><p>{s.engine.reason||'No command has been rejected. Waiting for a gesture.'}</p></div></div>
    </section>
  </div>
}

export function ActivationSettings({s,request}:{s:Snapshot;request:Request}){
  const current=activation(s),[selected,setSelected]=useState(current),[busy,setBusy]=useState(false);
  useEffect(()=>setSelected(current),[current]);
  const apply=async()=>{setBusy(true);await request('settings',{activation_gesture:selected,easy_demo:selected==='Open_Palm'});setBusy(false)};
  return <section className="panel activation-settings"><div className="panel-heading"><h2><ShieldCheck size={17}/>Choose your activation gesture</h2><span className="subtle">Start deliberately, then control naturally</span></div><div className="activation-options" role="radiogroup" aria-label="Activation gesture"><button role="radio" aria-checked={selected==='Open_Palm'} className={selected==='Open_Palm'?'activation-option selected':'activation-option'} onClick={()=>setSelected('Open_Palm')}><Hand size={25} strokeWidth={1.5}/><div><strong>Easy Demo · Open palm</strong><p>A deliberate hold unlocks the interface. Once unlocked, Open palm cancels pending actions and returns to neutral.</p></div><span className="selection-check checked">{selected==='Open_Palm'&&<Check size={12}/>}</span></button><button role="radio" aria-checked={selected==='ILoveYou'} className={selected==='ILoveYou'?'activation-option selected':'activation-option'} onClick={()=>setSelected('ILoveYou')}><UnlockKeyhole size={25} strokeWidth={1.5}/><div><strong>Distinct activation sign</strong><p>Extend thumb, index, and little finger. This keeps activation separate from the command and cancel gestures.</p></div><span className="selection-check checked">{selected==='ILoveYou'&&<Check size={12}/>}</span></button></div><div className="activation-submit"><span><LockKeyhole size={14}/>Open palm never directly starts a workstation.</span><button className="button primary" disabled={busy||current===selected} onClick={()=>void apply()}>{busy?'Applying…':current===selected?'Activation setting applied':'Apply activation setting'}</button></div></section>
}

export function CameraSourceControl({s,request}:{s:Snapshot;request:Request}){
  return <div className="studio-camera-controls"><div><Focus size={16}/><span>Practice with your real webcam; inspect what changes at each stage.</span></div><button className="button secondary" onClick={()=>void request('source',{source:s.vision.source==='live'?'simulated':'live'})}>{s.vision.source==='live'?<Activity size={15}/>:<Camera size={15}/>} {s.vision.source==='live'?'Switch to simulated input':'Open live camera'}</button></div>
}
