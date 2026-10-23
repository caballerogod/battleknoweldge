import {describe,it,expect} from 'vitest';
import {filterTopics} from './PresentationTopics';
const topics=[{name:'Баскетбол',aliases:['NBA','нба']},{name:'Парфюмерия',aliases:['духи','парфюм']},{name:'Еда',aliases:['зелёный чай']}];
describe('presentation topic search',()=>{
 it('finds popular alternative names case insensitively',()=>{expect(filterTopics(topics,' nba ').map(t=>t.name)).toEqual(['Баскетбол']);expect(filterTopics(topics,'парфюм').map(t=>t.name)).toEqual(['Парфюмерия']);});
 it('normalizes Russian ё and whitespace',()=>expect(filterTopics(topics,'ЗЕЛЕНЫЙ   ЧАЙ').map(t=>t.name)).toEqual(['Еда']));
 it('shows full catalog for an empty query and no invented topics',()=>{expect(filterTopics(topics,'')).toHaveLength(3);expect(filterTopics(topics,'unknown')).toEqual([]);});
});
