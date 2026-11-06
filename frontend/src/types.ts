export type Mode='baseline'|'protected'|'gestureguard';
export type Source='live'|'simulated'|'replay';
export interface Station {id:string;name:string;state:string;target_speed:number;rpm:number;airflow:number;throughput:number;items:number;passed:number;failed:number;progress:number}
export interface AuditEvent {id:number;timestamp:string;monotonic?:number;type:string;severity:string;message:string;mode:string;session_id:string;station_id?:string;gesture?:string;details:Record<string,unknown>}
export interface Engine {state:string;mode:Mode;gesture:string;score:number;hold_progress:number;confirm_progress:number;pending:null|{action:string;station_id:string;station_name:string};reason:string;selected_station:number;requires_release:boolean;settings:Record<string,number>}
export interface Snapshot {engine:Engine;stations:Station[];events:AuditEvent[];vision:{status:string;source:Source;fps:number;recognition_ms:number;frame_age_ms:number|null;hands:number;landmarks:unknown[];hand_scale?:number|null;error?:string|null};session:{id:string;operator_id:string;lighting:string;distance:string;glove:string};scenario:{running:boolean;name:string;step:number;total:number}}
export interface Metric {key:string;label:string;value:number|null;unit:string;samples:number;note:string}
export interface Evaluation {total_events:number;source_counts:Record<string,number>;sessions:string[]|number;metrics:Metric[];series:{mode:string;commands:number;rejections:number;tracking_losses:number}[]}
export const gestureNames:Record<string,string>={ILoveYou:'Activation sign',Open_Palm:'Open palm',Closed_Fist:'Closed fist',Thumb_Up:'Thumb up',Victory:'Victory',Pointing_Up:'Pointing up',Pinch:'Pinch',None:'No gesture'};
export const modes:Record<Mode,string>={baseline:'Baseline',protected:'Protected',gestureguard:'GestureGuard'};
