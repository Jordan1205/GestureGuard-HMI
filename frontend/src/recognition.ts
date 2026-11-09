import type {RecognitionDiagnostics,RecognitionSettings,Snapshot} from './types';
import {gestureNames} from './types';

export function diagnostics(s:Snapshot):RecognitionDiagnostics{return {...s.engine,...s.engine.diagnostics,unlocked:s.engine.unlocked??s.engine.diagnostics?.unlocked}}
export function numericSetting(settings:RecognitionSettings,key:string,fallback:number):number{return typeof settings[key]==='number'?settings[key] as number:fallback}
export function activation(s:Snapshot):string{return diagnostics(s).activation_gesture??s.engine.settings.activation_gesture??(s.engine.settings.easy_demo?'Open_Palm':'ILoveYou')}
export function gestureName(value:string|null|undefined):string{return value?gestureNames[value]??value.replaceAll('_',' '):'None'}
export function instruction(s:Snapshot,compact=false):string{
  const e=s.engine,d=diagnostics(s);
  if(s.vision.source==='live'&&s.vision.status!=='streaming')return compact?'Retry camera':'Check camera permissions and close other apps using the webcam. Retry the camera or switch to Simulated input.';
  if(s.recording?.active)return compact?'Recording · controls locked':'Recording real gesture samples. Command interaction stays locked until capture stops.';
  if(e.pending)return compact?'Pinch to confirm':'Review the action, then hold Pinch to confirm. Open palm cancels.';
  if(s.vision.hands>1||d.tracking_status==='multiple_hands')return compact?'Use one hand':'Keep only one hand in view so the system can follow your intention.';
  if(e.requires_release)return compact?'Relax your hand':'Relax your hand briefly before making the next gesture.';
  if(d.unlocked===false||e.state==='LOCKED')return compact?`Hold ${gestureName(activation(s))}`:`Hold ${gestureName(activation(s))} for ${numericSetting(e.settings,'unlock_seconds',1.2).toFixed(1)} seconds to unlock. Then relax your hand.`;
  if(d.candidate_gesture&&d.candidate_gesture!=='None')return compact?'Keep the gesture comfortable':`Keep ${gestureName(d.candidate_gesture)} in view while the evidence builds.`;
  if(e.state==='COOLDOWN'||e.state==='EXECUTING')return compact?'Command accepted':'Command accepted. Relax your hand before making another request.';
  if(s.vision.hands===0)return compact?'Show one hand':'Show one hand, then Thumb up to request a start or Closed fist to request a pause.';
  return compact?'Choose your next gesture':'Thumb up requests start. Closed fist requests pause. Open palm returns to neutral.';
}
