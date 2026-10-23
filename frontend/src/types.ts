export type Player = {id:number;nickname:string;xp:number;level:number;title:string;level_progress:number;next_level_xp:number};
export type Question = {id:number;text:string;category:string;difficulty:string;options:string[];number:number;total:number;deadline_at:number;server_time:number;time_limit:number;client_deadline?:number};
export type Answer = {question_id:number;question:string;category:string;selected:number|null;timed_out:boolean;correct:number;is_correct:boolean;xp:number;explanation:string;options:string[];created_at:string};
export type Category = {category:string;attempts:number;correct:number;accuracy:number|null;mastery:number;next_difficulty:string;probability:number};
export type Game = {id:string;player_id:number;total:number;answered:number;correct:number;wrong:number;accuracy:number;xp:number;streak:number;finished:boolean;initial_level:number;current_level:number;achievements:string[];strong:string[];weak:string[];categories:Category[];recommendation:string;last_answer:Answer|null;pending_id:number|null};
export type Stats = {player:Player;games:number;categories:Category[];history:Answer[];active_session:string|null};
export type Achievement = {id:string;name:string;description:string;earned_at:string|null};
export const difficultyLabel:Record<string,string>={easy:'Лёгкий',medium:'Средний',hard:'Сложный'};
